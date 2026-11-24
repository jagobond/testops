"""TESTOPS-89. Why a token did not arrive, and that it is said where a reader can see it.

The ticket's problem is not that the fallback sentence is wrong - it is that it was the *whole*
answer. These tests pin the four things that make the fallback explainable:

  * AC1 - a failed managed-identity lookup keeps its exception class, HTTP status, error code,
    endpoint, api-versions and elapsed time, in the client's record and in the store's ledger.
  * AC2 - both api-versions Container Apps answers are tried, a transport failure is retried once,
    ten seconds is the timeout, and which version and attempt answered is recorded.
  * AC3 - /agent-check states each fact for this process in words, and the token value appears
    nowhere on the page and nowhere in the ledger row it writes.
  * AC4 - a case page that finds no token records the probe it already paid for, so the deployed
    container's reason reaches the ledger without anyone opening a console.

No test touches the network: the metadata service is a fake response, and the model is never called.
"""
from __future__ import annotations

import json
import urllib.error

import pytest

from testops.judgement import agent, client
from testops.store import db
from testops.web import app

# A token whose value must never be rendered. Long enough that no accidental run of eight characters
# could match a word the page says by itself.
SECRET = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.EXAMPLEONLYNOTAREALTOKEN-" + "Q" * 40
WINDOW = 8


class FakeResponse:
    """A urlopen result: a status and a body, and the context-manager protocol."""

    def __init__(self, body: bytes, status: int = 200):
        self.body = body
        self.status = status

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(status: int, payload: dict | None = None,
               raw: bytes | None = None) -> urllib.error.HTTPError:
    """An ``HTTPError`` with a readable body, as IMDS and AAD send one."""
    body = raw if raw is not None else json.dumps(payload or {}).encode()
    import email.message
    return urllib.error.HTTPError(client.IMDS_ENDPOINT, status, "Bad Request",
                                  email.message.Message(), __import__("io").BytesIO(body))


def opener_script(*results):
    """Callable for ``opener=``: hands back the scripted results, in order.

    A scripted callable is invoked per request, which is how a test keeps an ``HTTPError``'s body
    readable across two attempts - a real request gets a fresh error body each time.
    """
    queue = list(results)
    calls: list[str] = []

    def open_(request, timeout=None):
        calls.append(request.full_url)
        result = queue.pop(0) if len(queue) > 1 else queue[0]
        if callable(result) and not isinstance(result, FakeResponse):
            result = result()
        if isinstance(result, BaseException):
            raise result
        return result

    open_.calls = calls
    return open_


def raises_http_error(status: int, payload: dict | None = None, raw: bytes | None = None):
    """A scripted request that fails with a fresh ``HTTPError``, body included."""
    def raise_():
        raise http_error(status, payload, raw)
    return raise_


def test_the_two_api_versions_and_the_cold_container_timeout_are_the_ones_tried():
    assert client.IMDS_API_VERSIONS == ("2018-02-01", "2019-08-01")
    assert client.IMDS_TIMEOUT == 10.0
    assert client.IMDS_RETRIES == 1


def test_a_400_body_records_its_error_code_and_is_not_retried():
    """AC1 and the ticket's tip: a 400 with a JSON body is usually the whole answer."""
    opener = opener_script(raises_http_error(400, {"error": "invalid_request",
                                                   "error_description": "Identity not found for resource"}))
    probe = client.probe_identity(opener=opener)

    assert probe.token == ""
    assert probe.cause == "http_400"
    assert probe.status == 400
    assert probe.error_code == "invalid_request"
    assert "Identity not found" in probe.detail
    # One request per api-version: a definitive answer is not retried, but the next version is asked.
    assert [attempt.api_version for attempt in probe.attempts] == list(client.IMDS_API_VERSIONS)
    assert [attempt.attempt for attempt in probe.attempts] == [1, 1]
    assert all(attempt.exception == "HTTPError" for attempt in probe.attempts)


def test_an_arm_shaped_error_body_is_read_too():
    payload = {"error": {"code": "AuthenticationFailed", "message": "No identity assigned"}}
    probe = client.probe_identity(opener=opener_script(raises_http_error(400, payload)))
    assert probe.error_code == "AuthenticationFailed"
    assert "No identity assigned" in probe.detail


def test_a_transport_failure_is_retried_once_per_api_version():
    opener = opener_script(TimeoutError("timed out"))
    probe = client.probe_identity(opener=opener)

    assert [attempt.api_version for attempt in probe.attempts] == [
        "2018-02-01", "2018-02-01", "2019-08-01", "2019-08-01"]
    assert [attempt.attempt for attempt in probe.attempts] == [1, 2, 1, 2]
    assert probe.cause == "timeout"
    assert all(attempt.exception == "TimeoutError" for attempt in probe.attempts)


def test_which_api_version_and_attempt_answered_is_recorded():
    """The cold-container case: the first version times out twice, the second answers."""
    token_body = json.dumps({"access_token": SECRET, "expires_in": "3599"}).encode()
    opener = opener_script(TimeoutError("timed out"), TimeoutError("timed out"),
                           FakeResponse(token_body))
    probe = client.probe_identity(opener=opener)

    assert probe.token == SECRET
    assert probe.answered
    assert probe.answered_api_version == "2019-08-01"
    assert probe.answered_attempt == 1
    assert probe.cause == "answered"
    assert [attempt.ok for attempt in probe.attempts] == [False, False, True]
    # The record that is cached, stored and rendered carries no token, in any form.
    stored = json.dumps(probe.as_dict())
    assert SECRET not in stored
    assert client.last_identity_probe() == probe.as_dict()


def test_the_request_asks_the_metadata_service_with_the_metadata_header():
    opener = opener_script(raises_http_error(400, {"error": "invalid_request"}))
    seen: list[dict] = []

    def open_(request, timeout=None):
        seen.append({"url": request.full_url, "headers": dict(request.headers),
                     "timeout": timeout})
        return opener(request, timeout=timeout)

    client.probe_identity(opener=open_)
    assert all(entry["headers"].get("Metadata") == "true" for entry in seen)
    assert all(entry["timeout"] == client.IMDS_TIMEOUT for entry in seen)
    assert seen[0]["url"].startswith(client.IMDS_ENDPOINT)
    assert "api-version=2018-02-01" in seen[0]["url"]


# --------------------------------------------------------------------------- the ledger and the page

def _no_token_window(text: str, secret: str = SECRET) -> str | None:
    """The first substring of ``secret`` (eight characters or more) that ``text`` contains."""
    for start in range(0, max(0, len(secret) - WINDOW) + 1):
        chunk = secret[start:start + WINDOW]
        if chunk in text:
            return chunk
    return None


@pytest.fixture()
def store(tmp_path):
    conn = db.connect(tmp_path / "check.db")
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _clean_token_state(monkeypatch):
    agent.reset_token_cache()
    monkeypatch.setattr(client, "_LAST_PROBE", dict(client._LAST_PROBE))
    yield
    agent.reset_token_cache()


def _fake_failed_probe():
    """A failed lookup, as the deployed container would produce it."""
    return client.probe_identity(opener=opener_script(
        raises_http_error(400, {"error": "invalid_request",
                                "error_description": "Identity not found for resource"})))


def test_the_page_states_every_fact_in_words(store, monkeypatch):
    _fake_failed_probe()
    monkeypatch.setattr(client, "managed_identity_token", lambda *a, **k: "")
    monkeypatch.setattr(client, "az_token", lambda *a, **k: "")
    agent.reset_token_cache()
    monkeypatch.setenv("TESTOPS_FOUNDRY_ENDPOINT", "https://example.invalid/chat")
    monkeypatch.setenv("TESTOPS_AGENT_MODEL", "deepseek-flash")

    page = app.agent_check(store).decode("utf-8")
    text = " ".join(page.replace("<", " <").split())

    assert "No explanation would be served right now" in text
    assert "https://example.invalid/chat" in text
    assert "TESTOPS_FOUNDRY_ENDPOINT" in text          # which variable configured it
    assert "deepseek-flash" in text
    assert "TESTOPS_AGENT_MODEL" in text
    assert "Token in the environment" in text
    assert "answered 400" in text
    assert "invalid_request" in text
    assert "Identity not found" in text
    assert "2018-02-01" in text and "2019-08-01" in text


def test_the_page_and_the_ledger_never_carry_the_token(store, monkeypatch):
    """AC3's hard gate: a known token is fed in, and no substring of it is rendered or stored."""
    monkeypatch.setenv("TESTOPS_AGENT_TOKEN", SECRET)
    agent.reset_token_cache()

    page = app.agent_check(store).decode("utf-8")
    assert _no_token_window(page) is None, f"the page rendered {_no_token_window(page)!r}"
    # The environment answered, so the page says yes and nothing more than yes.
    assert "</th><td>yes " in page
    assert "An explanation would be served right now" in page
    # Nothing was probed, so there is nothing to explain and nothing to record - and the ledger
    # that was not written cannot hold what the page does not print.
    assert agent.last_probe(store) is None
    every_row = [dict(row) for row in store.execute("SELECT * FROM agent_token_probe")]
    assert _no_token_window(json.dumps(every_row, default=str)) is None


def test_the_case_page_records_the_probe_it_already_paid_for(store, monkeypatch):
    """AC4: a failed lookup reaches the ledger from the case page, not only from /agent-check."""
    _fake_failed_probe()
    monkeypatch.setattr(client, "managed_identity_token", lambda *a, **k: "")
    monkeypatch.setattr(client, "az_token", lambda *a, **k: "")
    agent.reset_token_cache()
    cfg = agent.config()
    assert not cfg.configured

    outcome = agent.explain_case(store, {"case": {"id": "case-x"}}, cfg=cfg)
    assert outcome.state == agent.STATE_UNCONFIGURED
    row = agent.last_probe(store)
    assert row is not None
    assert row["imds_attempted"] == 1
    assert row["imds_answered"] == 0
    assert row["imds_status"] == 400
    assert row["imds_error_code"] == "invalid_request"
    assert row["imds_api_version"] == ""
    assert row["imds_attempts"][0]["api_version"] == "2018-02-01"
    assert row["imds_elapsed_ms"] >= 0
    # The honest fallback sentence is untouched: this ticket is about the cause, not the sentence.
    assert "a managed identity or the az CLI" in cfg.why_not


def test_nothing_is_recorded_when_nothing_was_probed(store):
    """A caller's injected config has probed nothing, and an empty row would be a claim it did not make."""
    agent.reset_token_cache()
    cfg = agent.Config(project="p", endpoint="https://example.invalid", model="m", token="")
    agent.explain_case(store, {"case": {"id": "case-y"}}, cfg=cfg)
    assert agent.last_probe(store) is None
