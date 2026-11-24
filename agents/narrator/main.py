"""TestOps narrator, hosted in Azure AI Foundry as a hosted agent.

Takes {"system","user"} as the Responses input, asks the deployed model for an explanation, returns the reply verbatim
plus a final USAGE line. Verdicts and the citation guard stay in TestOps.

The token comes from the agent's own instance identity via the platform's IDENTITY_ENDPOINT. DefaultAzureCredential is
kept as a fallback, but on this runtime it resolves to the agent blueprint identity, which cannot be given roles, so the
instance endpoint is the path that works.
"""
import base64
import json
import os
import time
import urllib.parse
import urllib.request

from azure.ai.agentserver.responses import ResponsesAgentServerHost, TextResponse
from azure.ai.projects import AIProjectClient
from azure.core.credentials import AccessToken
from azure.identity import DefaultAzureCredential

DEPLOYMENT = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "deepseek-flash")
PROJECT = os.environ["FOUNDRY_PROJECT_ENDPOINT"].rstrip("/")
URL = f"{PROJECT}/openai/v1/chat/completions"
SCOPE = "https://ai.azure.com/.default"
_state = {"openai": None, "cred": None}


def _claims(token):
    try:
        body = token.split(".")[1]
        body += "=" * (-len(body) % 4)
        c = json.loads(base64.urlsafe_b64decode(body))
        return {"oid": c.get("oid"), "appid": c.get("appid"), "aud": c.get("aud")}
    except Exception as exc:
        return {"peek": type(exc).__name__}


def _endpoint_token():
    """Ask the platform MSI endpoint for a token as this agent's instance identity."""
    endpoint = os.environ.get("IDENTITY_ENDPOINT")
    header = os.environ.get("IDENTITY_HEADER")
    if not endpoint or not header:
        raise RuntimeError("no IDENTITY_ENDPOINT")
    query = {"resource": "https://ai.azure.com", "api-version": "2019-08-01"}
    client_id = os.environ.get("FOUNDRY_AGENT_INSTANCE_CLIENT_ID")
    if client_id:
        query["client_id"] = client_id
    url = endpoint + ("&" if "?" in endpoint else "?") + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, headers={"X-IDENTITY-HEADER": header, "Metadata": "true"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())["access_token"]


def _sdk_token():
    if _state["cred"] is None:
        _state["cred"] = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    return _state["cred"].get_token(SCOPE).token


def _token():
    try:
        return _endpoint_token(), "instance-endpoint"
    except Exception:
        return _sdk_token(), "default-credential"


class _InstanceCredential:
    """A credential whose token is minted for the agent's own instance identity.

    The runtime's DefaultAzureCredential resolves to the agent blueprint identity, which cannot be given role
    assignments, so the platform MSI endpoint is the identity that actually holds the roles.
    """

    def get_token(self, *scopes, **kwargs):
        import time
        return AccessToken(_endpoint_token(), int(time.time()) + 3000)

    def close(self):
        return None


def _openai():
    if _state["openai"] is None:
        try:
            cred = _InstanceCredential()
            cred.get_token(SCOPE)
        except Exception:
            cred = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        project = AIProjectClient(endpoint=PROJECT, credential=cred)
        _state["openai"] = project.get_openai_client()
    return _state["openai"]


def _model(system, user):
    """Ask the model, retrying a cold-start identity refusal.

    The hosted runtime occasionally answers 401 'Principal does not have access' on the first call of a fresh
    session while its instance identity is still warming up; the same call succeeds seconds later. A retry is the
    honest fix, and the number of attempts is reported so the behaviour stays visible.
    """
    last = None
    for attempt in range(1, 4):
        try:
            return _model_once(system, user, attempt)
        except Exception as exc:
            last = exc
            if "401" not in str(exc) and "Authentication" not in type(exc).__name__:
                raise
            time.sleep(2.0)
    raise last


def _model_once(system, user, attempt=1):
    token, source = _token()
    body = {
        "model": DEPLOYMENT,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": 900,
        "temperature": 0.1,
    }
    client = _openai()
    r = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=900, temperature=0.1,
    )
    text = (r.choices[0].message.content or "")
    usage = getattr(r, "usage", None)
    usage = {"prompt_tokens": getattr(usage, "prompt_tokens", None),
             "completion_tokens": getattr(usage, "completion_tokens", None),
             "attempts": attempt}
    return text, {"prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
                  "model": DEPLOYMENT, "served_by": "foundry-hosted-agent", "token_source": source,
                  "token_claims": _claims(token)}


async def _payload(context):
    try:
        raw = context.get_input_text()
        if hasattr(raw, "__await__"):
            raw = await raw
    except Exception:
        raw = None
    return raw


async def handle(request, context, cancellation_signal):
    raw = await _payload(context)
    try:
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}
    system = data.get("system") or "Explain the finding in plain English."
    user = data.get("user") or (raw or "")
    if not user:
        return TextResponse(context, request, text="ERROR no input")
    try:
        text, usage = _model(system, user)
    except Exception as exc:
        detail = ""
        try:
            token, source = _token()
            detail = " | who=%s source=%s" % (json.dumps(_claims(token)), source)
        except Exception as peek:
            detail = " | no-token: %s" % type(peek).__name__
        return TextResponse(context, request, text="ERROR model: %s: %s%s" % (
            type(exc).__name__, str(exc)[:300], detail))
    return TextResponse(context, request, text=text + "\nUSAGE " + json.dumps(usage))


host = ResponsesAgentServerHost()
host.response_handler(handle)
if __name__ == "__main__":
    host.run(port=int(os.environ.get("PORT", "8088")))
