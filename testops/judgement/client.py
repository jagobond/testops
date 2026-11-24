"""Model transport. One HTTP call, an AAD token, and no credential of its own.

TESTOPS-88. What stood here was the baseline design's adapter: it *decided* things, it hard-coded
the Azure CLI's install directory and it fixed one endpoint. Three things were wrong with that, and
they are the three things this module now gets right:

* **No host path.** The ``az`` CLI is found the way the shell finds it (``shutil.which``), so a
  container without ``az`` fails honestly instead of pointing at a directory that is not there. A
  deployment inside Azure never calls ``az`` at all: it asks the managed identity.
* **No credential of its own.** A token comes from ``TESTOPS_AGENT_TOKEN`` when a deployment sets it,
  otherwise from the managed identity over IMDS, otherwise from the locally logged-in ``az``. The
  token is never stored, never logged and never returned in an error message.
* **Endpoint and model are configuration.** They default to the Foundry project ``testops-resource``
  and ``deepseek-flash`` and can be pointed anywhere without editing code.

Nothing in this module decides whether a claim is right. It returns text and its token counts;
``testops/judgement/agent.py`` decides whether that text may be shown.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass

# The Azure resource an AAD token is minted for. Not a secret: it is a well-known audience.
COGNITIVE_RESOURCE = "https://cognitiveservices.azure.com"

# The two pieces of configuration. Both are overridable; neither is a secret.
DEFAULT_PROJECT = "testops-resource"
DEFAULT_MODEL = "deepseek-flash"


def endpoint(environ: Mapping[str, str] | None = None, project: str | None = None) -> str:
    """The chat-completions URL for a Foundry project, or ``TESTOPS_AGENT_ENDPOINT`` verbatim.

    An explicit endpoint wins, because a deployment may front the project with its own gateway. The
    derived form is the project's own OpenAI-compatible surface.
    """
    env = os.environ if environ is None else environ
    explicit = (env.get("TESTOPS_AGENT_ENDPOINT") or "").strip()
    if explicit:
        return explicit
    name = project or (env.get("TESTOPS_AGENT_PROJECT") or "").strip() or DEFAULT_PROJECT
    return f"https://{name}.services.ai.azure.com/openai/v1/chat/completions"


def model_name(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    return (env.get("TESTOPS_AGENT_MODEL") or "").strip() or DEFAULT_MODEL


def az_command() -> str | None:
    """Where ``az`` is, or ``None`` when this machine has none.

    The path is resolved, never assumed: the image this tool ships in has no Azure CLI, and a
    hard-coded ``C:\\Program Files\\...`` made every call there fail with a traceback from
    ``subprocess`` rather than a sentence about a missing CLI.
    """
    return shutil.which("az")


def managed_identity_token(timeout: float = 3.0) -> str:
    """An AAD token from the instance metadata service, or ``""`` when not running in Azure.

    The metadata endpoint is link-local and refuses the request without ``Metadata: true``. A
    non-Azure host answers nothing within the timeout, which is the ordinary local case and not an
    error: the caller moves on to ``az``.
    """
    url = ("http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01"
           f"&resource={COGNITIVE_RESOURCE}")
    headers = {"Metadata": "true"}
    client_id = (os.environ.get("TESTOPS_AGENT_CLIENT_ID") or "").strip()
    if client_id:
        # A user-assigned identity: without the client id IMDS picks whichever identity it likes.
        url += f"&client_id={urllib.parse.quote(client_id)}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers),
                                    timeout=timeout) as response:
            data = json.loads(response.read() or b"{}")
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return ""
    token = data.get("access_token") or ""
    return token if isinstance(token, str) else ""


def az_token(timeout: float = 120.0) -> str:
    """An AAD token from a locally logged-in ``az``, or ``""``.

    ``--query accessToken -o tsv`` prints the token alone. The token is read from stdout, never from
    the command line, never from a file this tool writes: it lives in this frame and in one request
    header, and nowhere else.
    """
    az = az_command()
    if not az:
        return ""
    try:
        result = subprocess.run(
            [az, "account", "get-access-token", "--resource", COGNITIVE_RESOURCE,
             "--query", "accessToken", "-o", "tsv"],
            capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    for line in result.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith("{"):
            return line
    return ""


def token(environ: Mapping[str, str] | None = None) -> str:
    """The token this deployment can obtain: the environment first, then IMDS, then ``az``.

    ``TESTOPS_AGENT_TOKEN`` is not read from ``.env`` and is not written anywhere; it exists for a
    local experiment and for an environment that already injects a token. In Azure the managed
    identity answers; on a workstation the developer's own ``az login`` answers. No token is
    cached in a module global, so a rotated token is picked up on the next call.
    """
    env = os.environ if environ is None else environ
    supplied = (env.get("TESTOPS_AGENT_TOKEN") or "").strip()
    if supplied:
        return supplied
    return managed_identity_token() or az_token()


@dataclass
class Completion:
    text: str
    model: str
    prompt_hash: str
    tokens_in: int
    tokens_out: int


def complete(system: str, user: str, model: str | None = None, *,
             endpoint_url: str | None = None, access_token: str | None = None,
             max_tokens: int = 900, timeout: float = 180.0) -> Completion:
    """One completion. Raises ``urllib`` errors; the caller turns them into sentences.

    ``access_token`` and ``endpoint_url`` are injectable so a caller that already resolved them (the
    agent, which records whether it was configured) does not resolve them twice, and so a test never
    needs the network.
    """
    chosen = model or model_name()
    prompt = f"{system}\n\n{user}"
    prompt_hash = hashlib.sha256(f"{prompt}\n--\n{chosen}".encode()).hexdigest()[:16]
    body = json.dumps({
        "model": chosen,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_completion_tokens": max_tokens,
        "temperature": 0,
    }).encode()
    bearer = access_token if access_token is not None else token()
    request = urllib.request.Request(
        endpoint_url or endpoint(), data=body,
        headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read())
    usage = data.get("usage") or {}
    return Completion(text=(data["choices"][0]["message"].get("content") or ""),
                      model=data.get("model") or chosen, prompt_hash=prompt_hash,
                      tokens_in=int(usage.get("prompt_tokens") or 0),
                      tokens_out=int(usage.get("completion_tokens") or 0))


def extract_json(text: str) -> dict | None:
    """The first JSON object in ``text``, or ``None``.

    Kept because the level-fitness baseline prompt asked for JSON and a reader may still be holding
    that prompt's output; nothing on the agent path uses it - the explanation is prose.
    """
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = None
    return None
