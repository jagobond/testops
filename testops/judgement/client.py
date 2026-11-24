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
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field

# The Azure resource an AAD token is minted for. Not a secret: it is a well-known audience.
COGNITIVE_RESOURCE = "https://cognitiveservices.azure.com"

# Where a managed identity lives. The metadata service is link-local and answers a Container Apps
# instance; a workstation answers nothing at all, which is the ordinary local case.
IMDS_ENDPOINT = "http://169.254.169.254/metadata/identity/oauth2/token"

# TESTOPS-89. The two api-versions a Container Apps instance actually answers. The old code asked
# one of them once, and three seconds was not enough for a cold container to be told anything.
IMDS_API_VERSIONS = ("2018-02-01", "2019-08-01")
IMDS_TIMEOUT = 10.0
IMDS_RETRIES = 1

# The two pieces of configuration. Both are overridable; neither is a secret.
DEFAULT_PROJECT = "testops-resource"
DEFAULT_MODEL = "deepseek-flash"

# TESTOPS-93. The hosted agent's own defaults: its name in the Foundry project, and how long the
# page is willing to wait for it. Twenty seconds is the ticket's limit, and a page that has waited
# that long says so rather than substituting the model route for it.
DEFAULT_AGENT_NAME = "testops-narrator"
DEFAULT_AGENT_TIMEOUT = 20.0


def endpoint(environ: Mapping[str, str] | None = None, project: str | None = None) -> str:
    """The chat-completions URL for a Foundry project, or the deployment's own endpoint verbatim.

    An explicit endpoint wins, because a deployment may front the project with its own gateway. The
    derived form is the project's own OpenAI-compatible surface. :func:`endpoint_variable` names the
    setting that supplied an explicit value, because a page that says "configured" without saying
    which variable said it cannot explain a deployment that set the other one.
    """
    env = os.environ if environ is None else environ
    explicit = endpoint_variable(env)
    if explicit:
        return (env.get(explicit) or "").strip()
    name = project or (env.get("TESTOPS_AGENT_PROJECT") or "").strip() or DEFAULT_PROJECT
    return f"https://{name}.services.ai.azure.com/openai/v1/chat/completions"


# The two names an explicit endpoint has been given. The first is this build's; the second is what
# the documented Container Apps deployment sets, and was silently ignored until TESTOPS-89 - the
# demo only worked because the derived URL happened to be the same string.
ENDPOINT_VARIABLES = ("TESTOPS_AGENT_ENDPOINT", "TESTOPS_FOUNDRY_ENDPOINT")


def endpoint_variable(environ: Mapping[str, str] | None = None) -> str:
    """The environment variable that set the endpoint explicitly, or ``""`` when none did."""
    env = os.environ if environ is None else environ
    for name in ENDPOINT_VARIABLES:
        if (env.get(name) or "").strip():
            return name
    return ""


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


@dataclass
class Attempt:
    """One request to the metadata service, and what it said. Never holds the token."""

    api_version: str
    attempt: int
    ok: bool = False
    status: int | None = None
    error_code: str = ""
    exception: str = ""
    detail: str = ""
    elapsed_ms: int = 0

    def as_dict(self) -> dict:
        return {"api_version": self.api_version, "attempt": self.attempt, "ok": self.ok,
                "status": self.status, "error_code": self.error_code,
                "exception": self.exception, "detail": self.detail,
                "elapsed_ms": self.elapsed_ms}


@dataclass
class Probe:
    """What one managed-identity lookup did, in full, and *not* the token it may have returned.

    The token is a field on this dataclass and deliberately absent from :meth:`as_dict` - the only
    form that is ever cached, stored or rendered. That is the structural half of AC3: a page cannot
    print a secret it was never handed, and the ledger row cannot hold one either.
    """

    endpoint: str
    resource: str
    client_id: str
    timeout: float
    retries: int
    token: str = ""
    attempts: list[Attempt] = field(default_factory=list)
    cause: str = "not_attempted"
    status: int | None = None
    error_code: str = ""
    detail: str = ""
    elapsed_ms: int = 0
    answered_api_version: str = ""
    answered_attempt: int = 0

    @property
    def attempted(self) -> bool:
        return bool(self.attempts)

    @property
    def answered(self) -> bool:
        return bool(self.token)

    def as_dict(self) -> dict:
        """The probe without its token: the shape the ledger stores and the page renders."""
        return {"endpoint": self.endpoint, "resource": self.resource,
                "client_id": self.client_id, "timeout": self.timeout,
                "retries": self.retries, "attempted": self.attempted,
                "answered": self.answered, "cause": self.cause, "status": self.status,
                "error_code": self.error_code, "detail": self.detail,
                "elapsed_ms": self.elapsed_ms,
                "answered_api_version": self.answered_api_version,
                "answered_attempt": self.answered_attempt,
                "attempts": [attempt.as_dict() for attempt in self.attempts]}


# The last lookup in this process, in its token-free form. TESTOPS-89: the reason a token did not
# arrive used to be thrown away with the exception; here it is kept so a page can say it.
_LAST_PROBE: dict = {"attempted": False, "answered": False, "cause": "never asked",
                     "attempts": [], "status": None, "error_code": "", "detail": "",
                     "elapsed_ms": 0, "endpoint": IMDS_ENDPOINT, "resource": COGNITIVE_RESOURCE,
                     "client_id": "", "timeout": IMDS_TIMEOUT, "retries": IMDS_RETRIES,
                     "answered_api_version": "", "answered_attempt": 0}

# The last ``az`` lookup, the same way: present, answered, and why not.
_LAST_AZ: dict = {"present": bool(shutil.which("az")), "attempted": False, "answered": False,
                  "cause": "never asked", "detail": "", "elapsed_ms": 0}


def last_identity_probe() -> dict:
    """A copy of the last managed-identity lookup, so a caller cannot edit the record."""
    probe = dict(_LAST_PROBE)
    probe["attempts"] = [dict(attempt) for attempt in _LAST_PROBE.get("attempts") or []]
    return probe


def last_az_probe() -> dict:
    return dict(_LAST_AZ)


def _error_body(exc: urllib.error.HTTPError) -> tuple[str, str]:
    """``(code, message)`` from an HTTP error body, for the two shapes AAD and IMDS use.

    IMDS answers a 400 with ``{"error": "invalid_request", "error_description": "..."}``; ARM-style
    errors nest ``{"error": {"code": ..., "message": ...}}``. The code is usually the whole answer -
    a wrong resource, a wrong api-version, or an identity the resource does not have.
    """
    try:
        raw = exc.read() or b""
    except (OSError, ValueError, AttributeError):
        return "", ""
    try:
        body = json.loads(raw.decode("utf-8", "replace"))
    except (ValueError, UnicodeDecodeError):
        return "", ""
    if not isinstance(body, dict):
        return "", ""
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("code") or ""), str(error.get("message") or "")
    code = str(error or "")
    message = str(body.get("error_description") or body.get("message") or "")
    return code, message


def _scrub(text, limit: int = 300) -> str:
    """One line of diagnostic text, short enough for a ledger cell. No token is ever passed here."""
    return " ".join(str(text or "").split())[:limit]


def probe_identity(timeout: float = IMDS_TIMEOUT, retries: int = IMDS_RETRIES,
                   environ: Mapping[str, str] | None = None, opener=None) -> Probe:
    """Ask the metadata service for a token, and keep the whole of what happened.

    Each api-version in :data:`IMDS_API_VERSIONS` is tried, and a transport failure is retried once
    within that api-version: a cold container is allowed ten seconds to answer, not three. A
    definitive answer - a 400 with an error code, a 401, a 404 - is *not* retried, because asking
    again cannot change what it says; it moves to the next api-version instead, and which version
    and attempt answered is recorded on the probe.
    """
    env = os.environ if environ is None else environ
    client_id = (env.get("TESTOPS_AGENT_CLIENT_ID") or "").strip()
    ask = opener or urllib.request.urlopen
    started_at = time.monotonic()
    probe = Probe(endpoint=IMDS_ENDPOINT, resource=COGNITIVE_RESOURCE, client_id=client_id,
                  timeout=float(timeout), retries=int(retries))

    for api_version in IMDS_API_VERSIONS:
        for number in range(1, int(retries) + 2):
            query = (f"?api-version={api_version}&resource={urllib.parse.quote(COGNITIVE_RESOURCE, safe='')}")
            if client_id:
                # A user-assigned identity: without the client id IMDS picks whichever it likes.
                query += f"&client_id={urllib.parse.quote(client_id)}"
            request = urllib.request.Request(IMDS_ENDPOINT + query, headers={"Metadata": "true"})
            attempt = Attempt(api_version=api_version, attempt=number)
            began = time.monotonic()
            retry = False
            try:
                with ask(request, timeout=timeout) as response:
                    attempt.status = int(getattr(response, "status", 0) or 0) or None
                    payload = json.loads(response.read() or b"{}")
                token = payload.get("access_token") if isinstance(payload, dict) else None
                attempt.ok = isinstance(token, str) and bool(token.strip())
                if attempt.ok:
                    attempt.elapsed_ms = int((time.monotonic() - began) * 1000)
                    probe.attempts.append(attempt)
                    probe.token = str(token)
                    probe.cause = "answered"
                    probe.status = attempt.status
                    probe.answered_api_version = api_version
                    probe.answered_attempt = number
                    probe.elapsed_ms = int((time.monotonic() - started_at) * 1000)
                    _remember(probe)
                    return probe
                probe.cause = "no access_token in the reply"
                attempt.detail = probe.detail = _scrub(payload, 120)
            except urllib.error.HTTPError as exc:
                attempt.status = int(exc.code)
                attempt.error_code, message = _error_body(exc)
                attempt.detail = _scrub(message or exc.reason or "")
                attempt.exception = type(exc).__name__
                probe.cause = f"http_{int(exc.code)}"
                probe.error_code = attempt.error_code
                probe.detail = _scrub(f"{attempt.error_code} - {attempt.detail}".strip(" -")
                                      if attempt.error_code else attempt.detail)
                retry = int(exc.code) >= 500
            except (TimeoutError, urllib.error.URLError, OSError, ValueError) as exc:
                attempt.exception = type(exc).__name__
                attempt.detail = _scrub(exc)
                probe.cause = ("timeout" if isinstance(exc, TimeoutError) or "timed out" in str(exc)
                               else "unreachable")
                attempt.ok = False
                retry = True
            attempt.elapsed_ms = int((time.monotonic() - began) * 1000)
            probe.attempts.append(attempt)
            if retry and number <= int(retries):
                continue
            break

    probe.status = next((attempt.status for attempt in reversed(probe.attempts)
                         if attempt.status is not None), None)
    probe.elapsed_ms = int((time.monotonic() - started_at) * 1000)
    if probe.cause == "not_attempted":
        probe.cause = "no attempt was made"
    _remember(probe)
    return probe


def _remember(probe: Probe) -> None:
    """Cache the probe's token-free form. The token stays in the frame that asked for it."""
    global _LAST_PROBE
    _LAST_PROBE = probe.as_dict()


def managed_identity_token(timeout: float = IMDS_TIMEOUT, retries: int = IMDS_RETRIES,
                           environ: Mapping[str, str] | None = None, opener=None) -> str:
    """An AAD token from the instance metadata service, or ``""`` when not running in Azure.

    The metadata endpoint is link-local and refuses the request without ``Metadata: true``. A
    non-Azure host answers nothing within the timeout, which is the ordinary local case and not an
    error: the caller moves on to ``az``. What was tried, and why nothing came back, is kept in
    :func:`last_identity_probe` (TESTOPS-89).
    """
    return probe_identity(timeout=timeout, retries=retries, environ=environ, opener=opener).token


def az_token(timeout: float = 120.0) -> str:
    """An AAD token from a locally logged-in ``az``, or ``""``.

    ``--query accessToken -o tsv`` prints the token alone. The token is read from stdout, never from
    the command line, never from a file this tool writes: it lives in this frame and in one request
    header, and nowhere else. Whether ``az`` was there and whether it answered is kept in
    :func:`last_az_probe`, because "no token from the az CLI" is a claim a page has to be able to
    stand behind (TESTOPS-89).
    """
    az = az_command()
    started = time.monotonic()
    if not az:
        _LAST_AZ.update(present=False, attempted=False, answered=False,
                        cause="no az CLI on this PATH", detail="", elapsed_ms=0)
        return ""
    try:
        result = subprocess.run(
            [az, "account", "get-access-token", "--resource", COGNITIVE_RESOURCE,
             "--query", "accessToken", "-o", "tsv"],
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        _LAST_AZ.update(present=True, attempted=True, answered=False, cause="timeout",
                        detail=f"az did not answer within {int(timeout)}s",
                        elapsed_ms=int((time.monotonic() - started) * 1000))
        return ""
    except (OSError, subprocess.SubprocessError) as exc:
        _LAST_AZ.update(present=True, attempted=True, answered=False,
                        cause=type(exc).__name__, detail=_scrub(exc),
                        elapsed_ms=int((time.monotonic() - started) * 1000))
        return ""
    if result.returncode != 0:
        _LAST_AZ.update(present=True, attempted=True, answered=False,
                        cause=f"az exited {int(result.returncode)}",
                        detail=_scrub(result.stderr), 
                        elapsed_ms=int((time.monotonic() - started) * 1000))
        return ""
    for line in result.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith("{"):
            _LAST_AZ.update(present=True, attempted=True, answered=True, cause="answered",
                            detail="", elapsed_ms=int((time.monotonic() - started) * 1000))
            return line
    _LAST_AZ.update(present=True, attempted=True, answered=False,
                    cause="az printed no token", detail=_scrub(result.stderr),
                    elapsed_ms=int((time.monotonic() - started) * 1000))
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


# ---------------------------------------------------------------- the hosted-agent route (TESTOPS-93)
#
# A second route to an explanation, and it is the agent itself rather than a model call this build
# makes. ``testops-narrator`` is a hosted agent in the Foundry project, and it speaks OpenAI's
# Responses shape at its own endpoint:
#
#   POST {project}/agents/{name}/endpoint/protocols/openai/responses?api-version=v1
#   header: api-key: <the Cognitive Services key, from TESTOPS_AGENT_TOKEN only>
#   body:   {"input": "<a JSON string holding {system, user}>"}
#
# The reply is ``output[].content[].text`` for the entries whose type is ``output_text``, and its
# text is the agent's message followed by a final line ``USAGE {"prompt_tokens": n, ...}``. Those
# token counts are the agent's own, which is the whole reason the ledger can price this route
# honestly instead of estimating it.
#
# Nothing here decides whether the prose may be shown: this module returns text and its counts,
# exactly as :func:`complete` does, and ``testops/judgement/agent.py`` holds both against the same
# citation guard. The model route above is untouched.


def agent_name(environ: Mapping[str, str] | None = None) -> str:
    """The hosted agent's name, configuration rather than a constant (``TESTOPS_AGENT_NAME``)."""
    env = os.environ if environ is None else environ
    return (env.get("TESTOPS_AGENT_NAME") or "").strip() or DEFAULT_AGENT_NAME


def agent_endpoint(environ: Mapping[str, str] | None = None,
                   project: str | None = None) -> str:
    """The hosted agent's responses URL, or a deployment's own verbatim.

    ``TESTOPS_AGENT_ROUTE_ENDPOINT`` names a complete URL and wins, because a gateway may stand in
    front of the project. It is deliberately a *different* variable from
    :data:`ENDPOINT_VARIABLES`: those already name the model route's chat-completions address, and
    giving one variable two meanings would let a deployment point both routes at one address and
    believe it had configured two. The derived form is the project's own hosted-agent surface, which
    the ticket verified live.
    """
    env = os.environ if environ is None else environ
    explicit = (env.get(AGENT_ROUTE_VARIABLE) or "").strip()
    if explicit:
        return explicit
    project = project or (env.get("TESTOPS_AGENT_PROJECT") or "").strip() or DEFAULT_PROJECT
    return (f"https://{project}.services.ai.azure.com/api/projects/{project}"
            f"/agents/{agent_name(env)}/endpoint/protocols/openai/responses?api-version=v1")


# The agent endpoint's own override. Named in :func:`agent_endpoint`'s docstring; see the note there
# on why it is not ``TESTOPS_AGENT_ENDPOINT``.
AGENT_ROUTE_VARIABLE = "TESTOPS_AGENT_ROUTE_ENDPOINT"


def agent_token(environ: Mapping[str, str] | None = None) -> str:
    """The api-key for the hosted agent: ``TESTOPS_AGENT_TOKEN`` and nothing else (AC6).

    The model route may also use a managed identity or the ``az`` CLI, because it takes an AAD
    bearer token. A hosted agent's endpoint takes an ``api-key`` header, and the ticket's rule is
    that this credential comes from the environment only - so this lookup does not fall back to
    IMDS or to ``az``, and an unset variable means the route is unconfigured rather than that some
    other identity was quietly tried.
    """
    env = os.environ if environ is None else environ
    return (env.get("TESTOPS_AGENT_TOKEN") or "").strip()


def agent_timeout(environ: Mapping[str, str] | None = None) -> float:
    """How long the agent route waits, in seconds: 20 by default (``TESTOPS_AGENT_TIMEOUT``).

    Configuration rather than a literal so a test can pin the timeout branch in a fraction of a
    second instead of spending twenty, and so a deployment behind a slow gateway can say what it
    is willing to wait.
    """
    env = os.environ if environ is None else environ
    raw = (env.get("TESTOPS_AGENT_TIMEOUT") or "").strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_AGENT_TIMEOUT
    return value if value > 0 else DEFAULT_AGENT_TIMEOUT


class AgentReplyError(Exception):
    """A reply that arrived and could not be read: the kind names why, and detail is one line."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}".strip(": "))
        self.kind = kind
        self.detail = detail


@dataclass(frozen=True)
class AgentUsage:
    """The agent's own accounting, from the ``USAGE`` line it ends its reply with.

    ``present`` is a fact about the reply, not a default: an agent that answered without a USAGE
    line still gave an explanation, and its tokens are unknown - zero here, never an estimate.
    """

    present: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    served_by: str = ""

    @property
    def tokens_in(self) -> int:
        return int(self.prompt_tokens or 0)

    @property
    def tokens_out(self) -> int:
        return int(self.completion_tokens or 0)


def split_usage(text: str) -> tuple[str, AgentUsage]:
    """``(message text, usage)``: the reply with its final ``USAGE {...}`` line taken off.

    The line is read only where it is the *last* line, because that is where the agent puts it. A
    reply whose USAGE line is unreadable is still an answer: the text survives, the counts are
    honestly absent, and the ledger shows zero rather than a number nobody measured.
    """
    lines = str(text or "").splitlines()
    for index in range(len(lines) - 1, -1, -1):
        line = lines[index].strip()
        if not line:
            continue
        if not line.startswith("USAGE"):
            break
        payload = line[len("USAGE"):].strip()
        try:
            value = json.loads(payload)
        except (ValueError, TypeError):
            break
        if not isinstance(value, dict):
            break
        try:
            usage = AgentUsage(
                present=True,
                prompt_tokens=int(value.get("prompt_tokens") or 0),
                completion_tokens=int(value.get("completion_tokens") or 0),
                model=str(value.get("model") or ""),
                served_by=str(value.get("served_by") or ""))
        except (TypeError, ValueError):
            break
        return "\n".join(lines[:index]).rstrip(), usage
    return str(text or "").strip(), AgentUsage()


def read_agent_reply(payload) -> tuple[str, AgentUsage]:
    """``(message text, usage)`` from an OpenAI-shaped responses body, or raise ``AgentReplyError``.

    The text is every ``output[].content[]`` entry whose type is ``output_text``, in order. A body
    with no such entry is ``missing_text``: the request was answered and the answer holds no
    explanation, which is a fact the page has to carry rather than an empty block.
    """
    if not isinstance(payload, dict):
        raise AgentReplyError("malformed_reply", "the body is not a JSON object")
    texts: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            continue
        for entry in item.get("content") or []:
            if isinstance(entry, dict) and entry.get("type") == "output_text":
                value = entry.get("text")
                if isinstance(value, str) and value.strip():
                    texts.append(value)
    if not texts:
        raise AgentReplyError("missing_text",
                              "the reply held no output_text entry, so it has no explanation")
    return split_usage("\n".join(texts))


def complete_agent(system: str, user: str, *, endpoint_url: str, api_key: str,
                   agent: str = "", timeout: float = DEFAULT_AGENT_TIMEOUT) -> Completion:
    """One call to the hosted agent. Raises ``urllib`` errors and ``AgentReplyError``.

    ``prompt_hash`` is computed the same way :func:`complete` computes it, so a ledger row can be
    matched to the prompt that produced it whichever route wrote it. The api-key is placed in one
    request header and is never part of a return value or an exception: the errors this function
    raises carry a status or a kind, never the request.
    """
    chosen = agent or DEFAULT_AGENT_NAME
    prompt = f"{system}\n\n{user}"
    prompt_hash = hashlib.sha256(f"{prompt}\n--\n{chosen}".encode()).hexdigest()[:16]
    body = json.dumps({"input": json.dumps({"system": system, "user": user})}).encode()
    request = urllib.request.Request(
        endpoint_url, data=body,
        headers={"api-key": api_key, "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AgentReplyError("malformed_reply",
                              f"the reply was not JSON ({type(exc).__name__})") from None
    text, usage = read_agent_reply(payload)
    if not text:
        raise AgentReplyError("missing_text", "the reply's output_text was blank")
    return Completion(text=text, model=usage.model or chosen, prompt_hash=prompt_hash,
                      tokens_in=usage.tokens_in, tokens_out=usage.tokens_out)
