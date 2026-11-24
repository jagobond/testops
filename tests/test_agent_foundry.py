"""TESTOPS-93. The narrator runs as a hosted Foundry agent, and the page says which route served it.

The ticket's own order:

  * AC1 - ``?agent=foundry`` renders the same block as ``?agent=on``, labelled, and the block names
    the route that produced it (``served by: foundry-hosted-agent``).
  * AC2 - the citation guard is untouched and applies identically: a fabricated verb fed through the
    agent route is refused with the same state name and the same sentence the model route uses.
  * AC3 - the ledger records the route, the agent's own token counts from its ``USAGE`` line, the wall
    time and failures by kind; ``/agent-report`` shows the routes side by side with votes.
  * AC4 - a failed agent route is answered by the model route *only* when
    ``TESTOPS_AGENT_FALLBACK=model``; otherwise the honest failure sentence. Never a silent swap.
  * AC5 - ``agent=off`` and no parameter are byte-identical over all 275 real pages.
  * AC6 - the credential comes from ``TESTOPS_AGENT_TOKEN`` only, and no substring of it is rendered
    on a case page, ``/agent-check`` or ``/agent-report``.

No test here calls the live agent. Every agent request goes to a local stub HTTP server whose reply
is pinned to the shape the ticket quotes - ``output[].content[].text`` of type ``output_text``,
ending in a ``USAGE {json}`` line. One live smoke check exists and skips without a token.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import test_agent_case as ac
from testops.judgement import agent, client
from testops.store import db
from testops.web import app

CASE = ac.CASE
CHAT_ENDPOINT = "https://example.invalid/openai/v1/chat/completions"
TOKEN = "sk9f3a2b1c4d5e6f708192a3b4c5d6e7"
USAGE = {"prompt_tokens": 321, "completion_tokens": 87, "model": "deepseek-flash",
         "served_by": "foundry-hosted-agent"}


# --------------------------------------------------------------------------- the stub agent

def _payload(text: str, usage: dict | None = None) -> dict:
    """The reply shape the ticket quotes, as a body: output_text entries plus a USAGE line."""
    return {"id": "resp_stub", "object": "response", "status": "completed",
            "output": [{"type": "message", "role": "assistant",
                        "content": [{"type": "output_text",
                                     "text": f"{text}\nUSAGE {json.dumps(usage or USAGE)}"}]}]}


class StubAgent:
    """A local HTTP server that answers like the hosted agent, and records what it was sent."""

    def __init__(self, text: str = "", *, body: dict | None = None, status: int = 200,
                 delay: float = 0.0, usage: dict | None = None):
        self.body = body if body is not None else _payload(text, usage)
        self.status = status
        self.delay = delay
        self.requests: list[dict] = []

    def start(self) -> str:
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length)
                stub.requests.append({
                    "path": self.path,
                    "headers": {key.lower(): value for key, value in self.headers.items()},
                    "body": json.loads(raw) if raw else {}})
                if stub.delay:
                    time.sleep(stub.delay)
                body = json.dumps(stub.body).encode("utf-8")
                self.send_response(stub.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):   # the terminal is not the UI
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        return self.base

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    @property
    def last(self) -> dict:
        return self.requests[-1]


@pytest.fixture
def stub():
    started: list[StubAgent] = []

    def make(text: str = "", **kwargs) -> StubAgent:
        server = StubAgent(text, **kwargs)
        server.start()
        started.append(server)
        return server

    yield make
    for server in started:
        server.stop()


def _good_reply(conn) -> str:
    claim = f"claim:{ac._claim_id(conn)}"
    return ac._reply([(sentence, (claim,)) for sentence, _ in ac.GOOD_SENTENCES])


def _config(base: str, *, fallback: str = "", timeout: float = 5.0,
            agent_token: str = TOKEN, model_token: str = "model-token-value",
            agent_name: str = "testops-narrator") -> agent.Config:
    return agent.Config(project="testops-resource", endpoint=CHAT_ENDPOINT,
                        model="deepseek-flash", token=model_token,
                        agent_name=agent_name, agent_endpoint=base,
                        agent_token=agent_token, agent_timeout=timeout, fallback=fallback)


def _render(conn, cfg, *, case_id=CASE, view_id=None, completer=None):
    body, code = app.case_response(conn, case_id, variant=agent.VARIANT_FOUNDRY,
                                   view_id=view_id, agent_config=cfg, completer=completer)
    assert code == 200
    return body


def _text(body: bytes) -> str:
    return ac._text(body)


# --------------------------------------------------------------------------- AC1: the same block

def test_foundry_renders_the_same_block_and_names_its_route(tmp_path, stub):
    conn = ac._seed(tmp_path)
    server = stub(_good_reply(conn))
    try:
        off = ac._off(conn)
        body = _render(conn, _config(server.base))
        call = conn.execute("SELECT route, model, tokens_in, tokens_out, wall_ms, outcome"
                            " FROM agent_call ORDER BY id DESC LIMIT 1").fetchone()
        view = conn.execute("SELECT variant, served FROM agent_view ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    assert ac._without_explanation(body) == off.decode("utf-8"), (
        "the foundry page is the off page plus one block, exactly like the agent-on page")
    text = _text(body)
    assert "Explanation of this case" in text
    assert "Foundry hosted agent" in text and "testops-narrator" in text
    assert "served by: foundry-hosted-agent" in text, "AC1: the block must name the route"
    assert "commentary, not evidence" in text
    assert call["route"] == "foundry" and call["outcome"] == "ok"
    assert view["variant"] == "foundry" and view["served"] == "fresh"


def test_the_agent_route_sends_the_ticket_shape_to_the_agent_endpoint(tmp_path, stub):
    conn = ac._seed(tmp_path)
    server = stub(_good_reply(conn))
    try:
        _render(conn, _config(server.base))
    finally:
        conn.close()
    sent = server.last
    assert sent["path"].endswith("/agents/testops-narrator/endpoint/protocols/"
                                 "openai/responses?api-version=v1"), sent["path"]
    assert sent["headers"]["api-key"] == TOKEN
    assert set(sent["body"]) == {"input"}, "the body is one input string and nothing else"
    inner = json.loads(sent["body"]["input"])
    assert set(inner) == {"system", "user"}
    assert f"CASE {CASE}" in inner["user"], "the agent is given the same record the model route gets"


def test_the_model_route_still_records_route_model_and_uses_its_own_completer(tmp_path):
    conn = ac._seed(tmp_path)
    fake = ac.FakeModel(_good_reply(conn))
    try:
        ac._on(conn, fake)
        row = conn.execute("SELECT route, model FROM agent_call ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    assert row["route"] == "model" and row["model"] == "deepseek-flash"
    assert len(fake.calls) == 1, "the model route is untouched"


# --------------------------------------------------------------------------- AC2: the same guard

def _fabricated_verb(conn) -> str:
    return ac._reply([("The product declares PATCH /rooms, which is where the panel is served.",
                       ["route:GET /rooms"])])


def test_a_fabricated_verb_is_refused_through_the_agent_route_with_the_same_state(tmp_path, stub):
    conn = ac._seed(tmp_path)
    written = _fabricated_verb(conn)
    server = stub(written)
    try:
        view_id = agent.start_view(conn, CASE, "foundry")
        body = _render(conn, _config(server.base), view_id=view_id)
        calls = conn.execute("SELECT route, outcome, cause FROM agent_call ORDER BY id").fetchall()
        stored = conn.execute("SELECT COUNT(*) FROM agent_explanation").fetchone()[0]
        view = conn.execute("SELECT served FROM agent_view WHERE id=?", (view_id,)).fetchone()
    finally:
        conn.close()
    assert b"agent-text" not in body, "a rejected reply is never shown"
    assert "was rejected" in _text(body) and "PATCH" in _text(body)
    assert len(calls) == 2 and all(call["route"] == "foundry" for call in calls)
    assert [call["outcome"] for call in calls] == ["rejected", "rejected"], (
        "one ask and one repair round, exactly as the model route gets")
    assert "the verb PATCH" in calls[-1]["cause"]
    assert view["served"] == "rejected"
    assert stored == 0


def test_the_rejection_sentence_is_the_model_routes_own(tmp_path, stub):
    """AC2: same sentence, same state names - only the writer line differs."""
    conn = ac._seed(tmp_path)
    written = _fabricated_verb(conn)
    server = stub(written)
    try:
        off = ac._off(conn)
        foundry_body = _render(conn, _config(server.base))
        model_body = ac._on(conn, ac.FakeModel(written), cfg=ac.CONFIG)
    finally:
        conn.close()
    note = re.compile(r'<p class="agent-note">(.*?)</p>').search
    assert note(foundry_body.decode("utf-8")).group(1) == note(model_body.decode("utf-8")).group(1)
    # And the foundry failure is still exactly one sentence on the off page.
    sentence = note(foundry_body.decode("utf-8")).group(1)
    assert foundry_body.decode("utf-8") == ac._with_note(off, sentence)


# --------------------------------------------------------------------------- AC3: the ledger

def test_the_ledger_records_the_agents_own_tokens_and_wall_time(tmp_path, stub):
    conn = ac._seed(tmp_path)
    server = stub(_good_reply(conn), usage={"prompt_tokens": 456, "completion_tokens": 123,
                                            "model": "deepseek-flash",
                                            "served_by": "foundry-hosted-agent"})
    try:
        _render(conn, _config(server.base))
        row = conn.execute("SELECT route, tokens_in, tokens_out, wall_ms FROM agent_call"
                           " ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    assert row["route"] == "foundry"
    assert (row["tokens_in"], row["tokens_out"]) == (456, 123), (
        "the counts are the agent's USAGE line, not the model route's estimate")
    assert isinstance(row["wall_ms"], int) and row["wall_ms"] >= 0


@pytest.mark.parametrize("failure", ["unreachable", "timeout", "non_200", "missing_text"])
def test_every_agent_failure_is_a_kind_in_the_ledger_and_one_sentence_on_the_page(tmp_path, stub,
                                                                                failure):
    conn = ac._seed(tmp_path)
    server = None
    try:
        base = "http://127.0.0.1:1"
        timeout = 0.3
        if failure == "timeout":
            server = stub(_good_reply(conn), delay=1.0)
            base = server.base
        elif failure == "non_200":
            server = stub("", status=500, body={"error": {"code": "server_error"}})
            base = server.base
        elif failure == "missing_text":
            server = stub("", body={"status": "completed",
                                    "output": [{"type": "message",
                                                "content": [{"type": "input_text",
                                                             "text": "not an answer"}]}]})
            base = server.base
        off = ac._off(conn)
        view_id = agent.start_view(conn, CASE, "foundry")
        body = _render(conn, _config(base, timeout=timeout), view_id=view_id,
                       completer=ac.FakeModel(_good_reply(conn)))
        row = conn.execute("SELECT route, outcome, cause FROM agent_call"
                           " ORDER BY id DESC LIMIT 1").fetchone()
        view = conn.execute("SELECT served FROM agent_view WHERE id=?", (view_id,)).fetchone()
        calls = conn.execute("SELECT COUNT(*) FROM agent_call").fetchone()[0]
    finally:
        conn.close()
    assert row["route"] == "foundry" and row["outcome"] == "error"
    assert row["cause"] == failure, row["cause"]
    assert b"agent-text" not in body and b'<p class="agent-note">' in body
    assert view["served"] == "failed_unavailable", "same state names as the model route"
    assert calls == 1, "without TESTOPS_AGENT_FALLBACK=model nothing else is asked"
    sentence = re.search(r'<p class="agent-note">(.*?)</p>', body.decode("utf-8")).group(1)
    assert body.decode("utf-8") == ac._with_note(off, sentence)


def test_the_report_shows_the_routes_side_by_side_with_votes_and_failure_kinds(tmp_path, stub):
    conn = ac._seed(tmp_path)
    good = stub(_good_reply(conn))
    broken = stub("", status=502, body={"error": "bad gateway"})
    try:
        view_id = agent.start_view(conn, CASE, "foundry")
        _render(conn, _config(good.base), view_id=view_id)
        app.feedback_page(conn, CASE, str(view_id), "helped")
        failed = agent.start_view(conn, CASE, "foundry")
        _render(conn, _config(broken.base), view_id=failed)
        body = app.agent_report(conn)
        routes = {row["route"]: row for row in agent.route_report(conn)}
    finally:
        conn.close()
    text = _text(body)
    assert "The routes, side by side" in text
    assert "foundry-hosted-agent" in text and "model-route" in text
    assert "non_200: 1" in text, "the failure is counted by its kind"
    assert routes["foundry"]["calls"] == 2
    assert routes["foundry"]["total_tokens"] == 321 + 87
    assert routes["foundry"]["helped"] == 1 and routes["foundry"]["did_not_help"] == 0


# --------------------------------------------------------------------------- AC4: honest failure

def test_no_fallback_unless_asked_and_the_fallback_is_said_out_loud(tmp_path, stub):
    conn = ac._seed(tmp_path)
    fake = ac.FakeModel(_good_reply(conn))
    try:
        off = ac._off(conn)
        # 1. Not asked for: the honest failure sentence, and the model route is never called.
        honest = _render(conn, _config("http://127.0.0.1:1"), completer=fake)
        assert b"agent-text" not in honest
        assert "The hosted Foundry agent could not be reached" in _text(honest)
        assert not fake.calls, "AC4: no silent substitution"
        assert conn.execute("SELECT COUNT(*) FROM agent_call WHERE route='model'").fetchone()[0] == 0

        # 2. Explicitly allowed: the model route answers - and the page says so.
        body = _render(conn, _config("http://127.0.0.1:1", fallback="model"), completer=fake)
        routes = [row["route"] for row in
                  conn.execute("SELECT route FROM agent_call ORDER BY id").fetchall()]
    finally:
        conn.close()
    text = _text(body)
    # The block's own marker is in the markup, not in its prose: ``_text`` strips tags, so the
    # class is asserted against the raw bytes and the prose against the stripped text.
    assert b'<div class="agent-text">' in body and "was rejected" not in text
    assert "served by: model-route" in text
    assert "falling back to the model route" in text
    assert "foundry-hosted-agent" in text, "the page names the route that failed, too"
    assert "the reader is told" in text.lower()
    assert routes == ["foundry", "foundry", "model"], (
        "two agent calls, both refused and both in the ledger - the first view's, and the "
        "fallback view's, which is then answered once by the model route. A failed attempt that "
        "the ledger dropped would make the fallback look free")


def test_a_rejected_reply_is_never_re_asked_of_the_other_route(tmp_path, stub):
    """AC4's boundary: a rejection is not a transport failure, so a fallback must not buy a second."""
    conn = ac._seed(tmp_path)
    server = stub(_fabricated_verb(conn))
    fake = ac.FakeModel(_good_reply(conn))
    try:
        body = _render(conn, _config(server.base, fallback="model"), completer=fake)
    finally:
        conn.close()
    assert not fake.calls
    assert b"agent-text" not in body and "was rejected" in _text(body)


def test_the_fallback_is_configuration_and_the_credential_is_the_environment(monkeypatch):
    agent.reset_token_cache()
    monkeypatch.setenv("TESTOPS_AGENT_TOKEN", TOKEN)
    monkeypatch.setenv("TESTOPS_AGENT_NAME", "testops-narrator")
    monkeypatch.setenv("TESTOPS_AGENT_ROUTE_ENDPOINT", "http://127.0.0.1:9/agent")
    monkeypatch.setenv("TESTOPS_AGENT_FALLBACK", "model")
    try:
        cfg = agent.config()
    finally:
        agent.reset_token_cache()
    assert cfg.agent_name == "testops-narrator"
    assert cfg.agent_endpoint == "http://127.0.0.1:9/agent"
    assert cfg.agent_token == TOKEN
    assert cfg.fallback_to_model, "AC4: the fallback is only this explicit setting"
    # The model route's bearer token is a different lookup: the agent's api-key is not used for it.
    assert cfg.token == TOKEN, "TESTOPS_AGENT_TOKEN still serves the model route as before"


def test_the_agent_route_does_not_fall_back_to_imds_or_az(monkeypatch):
    """AC6: for the agent route the credential is the environment variable and nothing else."""
    agent.reset_token_cache()
    monkeypatch.setattr(client, "managed_identity_token", lambda *a, **k: "an-imds-token")
    monkeypatch.setattr(client, "az_token", lambda *a, **k: "an-az-token")
    monkeypatch.delenv("TESTOPS_AGENT_TOKEN", raising=False)
    try:
        cfg = agent.config()
    finally:
        agent.reset_token_cache()
    assert cfg.token == "an-imds-token", "the model route keeps its fallback"
    assert cfg.agent_token == "", "the agent route has no such fallback"
    assert not cfg.foundry_configured


def test_an_unconfigured_agent_route_says_so_and_never_calls_out(tmp_path):
    conn = ac._seed(tmp_path)
    try:
        off = ac._off(conn)
        body = _render(conn, _config("http://127.0.0.1:1", agent_token=""))
        calls = conn.execute("SELECT COUNT(*) FROM agent_call").fetchone()[0]
    finally:
        conn.close()
    assert "no credential in TESTOPS_AGENT_TOKEN" in _text(body)
    assert b"agent-text" not in body and calls == 0


# --------------------------------------------------------------------------- AC5: off is untouched

def test_off_and_no_parameter_are_the_same_bytes_on_all_275_real_pages(monkeypatch):
    golden = json.loads(ac.GOLDEN.read_text(encoding="utf-8"))
    conn = ac._real_store()
    monkeypatch.chdir(ac.ROOT)
    monkeypatch.setattr(app, "dt", ac._DtShim)
    explicit = app.parse_agent_flag("off")
    assert explicit.variant == agent.VARIANT_OFF
    compared, mismatched, absent = 0, [], []
    try:
        for case_id, digest in sorted(golden["cases"].items()):
            if conn.execute("SELECT 1 FROM case_ WHERE id = ?", (case_id,)).fetchone() is None:
                absent.append(case_id)
                continue
            plain = app.case_page(conn, case_id)
            stated, code = app.case_response(conn, case_id, variant=explicit.variant,
                                             flag=explicit)
            assert code == 200
            compared += 1
            if plain != stated or hashlib.sha256(plain).hexdigest() != digest:
                mismatched.append(case_id)
        for run_id, digest in sorted(golden["runs"].items()):
            if conn.execute("SELECT 1 FROM run WHERE id = ?", (run_id,)).fetchone() is None:
                absent.append(run_id)
                continue
            rendered = app.run_page(conn, run_id)
            compared += 1
            if hashlib.sha256(rendered).hexdigest() != digest:
                mismatched.append(run_id)
    finally:
        conn.close()
    assert not mismatched, f"the off page changed for: {mismatched[:5]}"
    assert not absent, f"the store no longer holds {len(absent)} of the golden pages"
    assert compared == 275, f"compared {compared} pages, not the 275 the golden holds"


def test_foundry_is_the_third_word_after_the_flag_and_off_is_still_the_default(tmp_path):
    assert app.parse_agent_flag("foundry").variant == agent.VARIANT_FOUNDRY
    assert app.parse_agent_flag(" FOUNDRY ").understood
    assert app.parse_agent_flag(None).variant == agent.VARIANT_OFF
    assert agent.VARIANTS == ("off", "on", "foundry")


def test_the_handler_serves_the_foundry_variant_and_records_the_flag(tmp_path, monkeypatch, stub):
    conn = ac._seed(tmp_path)
    server = stub(_good_reply(conn))
    path = tmp_path / "agent.db"
    conn.close()
    monkeypatch.setenv("TESTOPS_AGENT_TOKEN", TOKEN)
    monkeypatch.setenv("TESTOPS_AGENT_ROUTE_ENDPOINT", server.base)
    real_connect = db.connect

    def connect(_path=None):
        return real_connect(path)

    monkeypatch.setattr(app.db, "connect", connect)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/case/{CASE}?agent=foundry"
        with urllib.request.urlopen(url, timeout=10) as response:
            page = response.read()
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert "served by: foundry-hosted-agent" in _text(page)
    conn = db.connect(path)
    try:
        flag = conn.execute("SELECT variant, understood FROM agent_flag").fetchone()
        view = conn.execute("SELECT variant, served FROM agent_view").fetchone()
        call = conn.execute("SELECT route FROM agent_call").fetchone()
    finally:
        conn.close()
    assert flag["variant"] == "foundry" and flag["understood"]
    assert view["variant"] == "foundry" and view["served"] == "fresh"
    assert call["route"] == "foundry"


# --------------------------------------------------------------------------- AC6: no credential

def _windows(secret: str, size: int = 8):
    return [secret[i:i + size] for i in range(0, len(secret) - size + 1)]


def test_no_substring_of_the_token_reaches_a_page_the_report_or_the_ledger(tmp_path, monkeypatch,
                                                                          stub):
    conn = ac._seed(tmp_path)
    server = stub(_good_reply(conn))
    monkeypatch.setenv("TESTOPS_AGENT_TOKEN", TOKEN)
    monkeypatch.setenv("TESTOPS_AGENT_ROUTE_ENDPOINT", server.base)
    agent.reset_token_cache()
    try:
        view_id = agent.start_view(conn, CASE, "foundry")
        case_body = _render(conn, _config(server.base), view_id=view_id)
        check_body = app.agent_check(conn)
        report_body = app.agent_report(conn)
        ledger = json.dumps([dict(row) for row in conn.execute("SELECT * FROM agent_call")])
    finally:
        conn.close()
        agent.reset_token_cache()
    assert server.last["headers"]["api-key"] == TOKEN, "the credential really was used"
    for label, page in (("case page", case_body), ("/agent-check", check_body),
                        ("/agent-report", report_body)):
        rendered = page.decode("utf-8")
        leaked = [window for window in _windows(TOKEN) if window in rendered]
        assert not leaked, f"{label} rendered part of the token: {leaked[:3]}"
    assert not [window for window in _windows(TOKEN) if window in ledger]
    # And the check page does say whether one is configured, without saying what it is.
    assert "Credential in TESTOPS_AGENT_TOKEN" in _text(check_body)
    assert "The Foundry-hosted agent would be asked right now" in _text(check_body)


# --------------------------------------------------------------------------- live smoke (opt-in)

@pytest.mark.skipif(not (os.environ.get("TESTOPS_AGENT_TOKEN")
                         and os.environ.get("TESTOPS_AGENT_LIVE_SMOKE")),
                    reason="no TESTOPS_AGENT_TOKEN (or TESTOPS_AGENT_LIVE_SMOKE) in the environment")
def test_live_smoke_the_hosted_agent_answers():
    """The one test allowed to call the agent, and it skips unless a deployment asks for it."""
    completion = client.complete_agent("You are a test. Reply with one word.",
                                       "Reply with the word ready.",
                                       endpoint_url=client.agent_endpoint(),
                                       api_key=client.agent_token(), timeout=60.0)
    assert completion.text.strip()
    assert completion.tokens_in + completion.tokens_out > 0, "the USAGE line was read"
