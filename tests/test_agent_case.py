"""TESTOPS-88. The agent explains a case, and every claim about it is pinned here.

What these tests are for, in the ticket's own order:

  * AC1 - with the agent off, every real case page is byte-identical to what the build rendered
    before this ticket. The corpus is the product's own store (226 cases and 49 run pages at the
    time of writing), and ``fixtures/agent/off-golden.json`` holds their digests, captured from the
    unmodified build with the clock pinned so relative ages are stable.
  * AC2 / AC3 - with it on, the page is the off page plus exactly one block, and a reply that names
    a route, file, count or entity the record does not hold is discarded and replaced by one
    sentence.
  * AC4 / AC5 / AC6 - the ledger arithmetic, the cache, and the two links.
  * AC7 - every failure mode is one honest sentence and a cause in the ledger.
  * AC8 - no credential anywhere, and no host path to ``az``.

No test touches the network: every model call here is a fake, and no test writes to the product's
store.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import urllib.error
from pathlib import Path

import pytest

from testops import queries
from testops.judgement import agent, client
from testops.store import db
from testops.web import app

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "fixtures" / "agent" / "off-golden.json"
REAL_STORE = ROOT / "data" / "testops.db"

TS = "2020-01-01T00:00:00+00:00"
CASE = "case-agent"
SNAP = "snap-agent"
RUN = "run-agent"
COMMIT = "a" * 40
PATH = "features/panel_api.feature"
LINE = 17

# A reply that only uses facts the seeded record holds. Every test that expects an explanation to be
# served uses this text, so a failure here is a change in the checker, not in a fixture.
GOOD_REPLY = ("This test asserts that the panel is served. The rule found that the assertion is "
              "settled by the page the server sends, and that the run reached the browser to "
              "arrive at it. The next step is to move that step into a test that reads the "
              "response instead.")

CONFIG = agent.Config(project="testops-resource",
                      endpoint="https://example.invalid/openai/v1/chat/completions",
                      model="deepseek-flash", token="test-token-value")


class FakeModel:
    """A model that answers from a script: a string, a Completion, or an exception to raise."""

    def __init__(self, *replies):
        self.replies = list(replies) or [GOOD_REPLY]
        self.calls: list[dict] = []

    def __call__(self, system, user, model, **kwargs):
        self.calls.append({"system": system, "user": user, "model": model, **kwargs})
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, BaseException):
            raise reply
        if isinstance(reply, str):
            return client.Completion(text=reply, model=model, prompt_hash="fake",
                                     tokens_in=120, tokens_out=60)
        return reply


# --------------------------------------------------------------------------- store fixture

def _seed(tmp_path, *, verdict="gap", statement="This test asserts that the panel is served.",
          route="GET /rooms", word="rooms", reason="", findings=1, code="I4"):
    """One case, one finding, one claim with the product facts an explanation is written from."""
    conn = db.connect(tmp_path / "agent.db")
    db.upsert_snapshot(conn, SNAP, "fixture", TS, {"owner/test": COMMIT}, schema_version=2)
    db.start_run(conn, RUN, "fixture", SNAP, "level_fitness", TS)
    claim_id = db.add_claim(
        conn, RUN, "level_fitness", "0.8.0",
        f"scenario:{PATH}#the panel is served",
        "The assertion is about the page as served, yet the run drives a browser.",
        verdict, 0.5, [], schema_version=2,
        assertion_text="the panel is served with each fact's citation present",
        assertion_path=PATH, assertion_line=LINE, assertion_commit=COMMIT,
        interaction_label="settled by the page the server sends", interaction_code=code,
        span=["ui"], established_by="the words name the page as served",
        sources_missing=None, proposed_action="Read the response instead of driving a browser.")
    product = {"route": route, "surface": f"api:{route}@src/RoomController.java:getRooms",
               "word": word, "reason": reason, "claim": "get rooms", "near_miss": True}
    db.add_inference(conn, claim_id, "level_fitness", "0.8.0", "p" * 16, [],
                     {"assertion_text": "the panel is served with each fact's citation present",
                      "cheapest": "api", "product": product, "instrument": "ui"}, 0, 0)
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
                 " VALUES (?,?,?,?,?,?,?)",
                 (CASE, RUN, "fixture", "level_fitness", SNAP, TS, "{}"))
    if findings:
        conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                     " VALUES (?,?,?,?,?)",
                     (CASE, "The panel is over-tested", "high", "f" * 32, db.j([claim_id])))
    conn.commit()
    return conn


def _off(conn, case_id=CASE):
    return app.case_page(conn, case_id)


def _on(conn, fake, case_id=CASE, view_id=None, cfg=CONFIG):
    body, code = app.case_response(conn, case_id, variant=agent.VARIANT_ON, view_id=view_id,
                                   agent_config=cfg, completer=fake)
    assert code == 200
    return body


_EXPLANATION = re.compile(
    r'<h2 class="section">Explanation of this case</h2>.*?'
    r'(?=<h2|<p class="code footnote"|</main>)', re.S)


def _without_explanation(body: bytes) -> str:
    """The on page with the one added block removed - which must equal the off page exactly."""
    text = body.decode("utf-8")
    stripped, count = _EXPLANATION.subn("", text)
    assert count == 1, f"expected exactly one explanation block, found {count}"
    return stripped


def _with_note(off: bytes, sentence: str) -> str:
    """The off page plus one paragraph, placed where the page would have carried the block.

    The block sits after the claims and before the near-miss section, so the note goes in the same
    place: a page whose notes appeared somewhere else would not be "the off page plus one sentence".
    """
    text = off.decode("utf-8")
    for marker in ('<h2 class="section">', '<p class="code footnote"', '<nav class="site"'):
        if marker == '<h2 class="section">':
            match = re.search(r'<h2 class="section">\d+\. (?:What the product refused|Decision)'
                              r'</h2>', text)
            if match:
                return text[:match.start()] + f'<p class="agent-note">{sentence}</p>' + text[match.start():]
            continue
        if marker in text:
            return text.replace(marker, f'<p class="agent-note">{sentence}</p>{marker}', 1)
    raise AssertionError("no place to put the note")  # pragma: no cover


def _text(body: bytes) -> str:
    import html as htmllib
    html = body.decode("utf-8")
    html = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    return " ".join(htmllib.unescape(html).split())


# --------------------------------------------------------------------------- AC1: off is untouched

class _FixedDatetime(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return dt.datetime(2026, 11, 24, 12, 0, 0, tzinfo=dt.timezone.utc)


class _DtShim:
    datetime = _FixedDatetime
    timezone = dt.timezone
    timedelta = dt.timedelta
    date = dt.date


def _real_store():
    if not REAL_STORE.exists():
        pytest.skip("the product's evidence store is not in this checkout")
    conn = sqlite3.connect(f"file:{REAL_STORE.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def test_every_real_case_page_is_byte_identical_to_the_pre_change_build(tmp_path, monkeypatch):
    """AC1's hard gate, over the real cases and the real run pages rather than one fixture.

    The digests were captured from the build as it stood before this ticket, with the clock pinned
    at 2026-11-24T12:00Z so relative ages do not drift. A case the store no longer holds (pruned by
    retention) is reported, not failed; a case whose bytes changed is a failure naming it.
    """
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    conn = _real_store()
    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(app, "dt", _DtShim)
    try:
        import hashlib
        mismatched, compared, absent = [], 0, []
        for case_id, digest in sorted(golden["cases"].items()):
            if conn.execute("SELECT 1 FROM case_ WHERE id = ?", (case_id,)).fetchone() is None:
                absent.append(case_id)
                continue
            rendered = app.case_page(conn, case_id)
            compared += 1
            if hashlib.sha256(rendered).hexdigest() != digest:
                mismatched.append(case_id)
        for run_id, digest in sorted(golden["runs"].items()):
            if conn.execute("SELECT 1 FROM run WHERE id = ?", (run_id,)).fetchone() is None:
                continue
            rendered = app.run_page(conn, run_id)
            compared += 1
            if hashlib.sha256(rendered).hexdigest() != digest:
                mismatched.append(run_id)
    finally:
        conn.close()
    assert compared > 0, "no real case page was compared, so the gate proved nothing"
    assert not mismatched, f"the agent-off page changed for: {mismatched[:5]}"
    assert len(absent) < len(golden["cases"]) / 2, (
        f"{len(absent)} of {len(golden['cases'])} golden cases are no longer in the store")


def test_off_is_the_default_and_the_two_ways_of_asking_for_it_agree(tmp_path, monkeypatch):
    conn = _seed(tmp_path)
    try:
        monkeypatch.chdir(ROOT)
        default = app.case_page(conn, CASE)
        explicit, code = app.case_response(conn, CASE, variant=agent.VARIANT_OFF)
    finally:
        conn.close()
    assert code == 200
    assert default == explicit
    assert b"agent-text" not in default and b"agent-note" not in default


def test_the_flag_parses_to_off_unless_it_says_on():
    assert app._agent_variant(None) == "off"
    assert app._agent_variant("") == "off"
    assert app._agent_variant("no") == "off"
    assert app._agent_variant("ON") == "on"


# --------------------------------------------------------------------------- AC2: one block

def test_on_is_the_off_page_plus_one_labelled_block(tmp_path):
    conn = _seed(tmp_path)
    try:
        off = _off(conn)
        fake = FakeModel(GOOD_REPLY)
        on = _on(conn, fake)
    finally:
        conn.close()
    assert _without_explanation(on) == off.decode("utf-8")
    text = on.decode("utf-8")
    assert "Explanation of this case" in text
    assert "deepseek-flash" in text, "the block must name the model that wrote it"
    assert "commentary, not evidence" in text
    # The verdict still precedes it: the block is after the claim's own section.
    assert text.index("Not proved") < text.index("Explanation of this case")


def test_the_explanation_is_written_from_the_record_and_nothing_else(tmp_path):
    """The prompt carries the stored facts - assertion, verdict, matched word, route, reason."""
    conn = _seed(tmp_path, reason="the product declares GET /rooms, which shares the word \u201crooms\u201d")
    try:
        fake = FakeModel(GOOD_REPLY)
        _on(conn, fake)
    finally:
        conn.close()
    sent = fake.calls[0]["user"]
    assert "the panel is served" in sent
    assert "GET /rooms" in sent
    assert "settled by the page the server sends" in sent
    assert "the product declares GET /rooms" in sent
    assert PATH in sent
    assert str(LINE) in sent
    # The record is what the prompt says it is: a case, its finding, its claim, its sources.
    assert "CASE case-agent" in sent and "FINDINGS: 1" in sent and "SOURCES EXAMINED" in sent


def test_the_record_is_read_from_the_store_not_written_by_the_agent(tmp_path):
    conn = _seed(tmp_path)
    try:
        record = agent.case_record(conn, CASE)
        before = json.dumps(record, sort_keys=True)
        _on(conn, FakeModel(GOOD_REPLY))
        after = json.dumps(agent.case_record(conn, CASE), sort_keys=True)
    finally:
        conn.close()
    assert before == after


# --------------------------------------------------------------------------- AC3: the check

def test_a_fabricated_route_is_discarded_and_the_page_falls_back(tmp_path):
    conn = _seed(tmp_path)
    fabricated = ("The assertion checks GET /api/orders, which the product already serves, so the "
                  "browser is not needed.")
    try:
        off = _off(conn)
        on = _on(conn, FakeModel(fabricated))
        call = conn.execute("SELECT outcome, cause, tokens_in, tokens_out FROM agent_call"
                            " ORDER BY id DESC LIMIT 1").fetchone()
        stored = conn.execute("SELECT COUNT(*) FROM agent_explanation").fetchone()[0]
    finally:
        conn.close()
    assert "/api/orders" in _text(on), "the reader must be told which fact was rejected"
    assert "rejected" in _text(on)
    assert b"agent-text" not in on, "no block was added for a rejected reply"
    assert call["outcome"] == "rejected"
    assert "/api/orders" in call["cause"]
    assert stored == 0, "a rejected reply must never be stored as an explanation"


def test_a_fabricated_file_a_wrong_count_and_an_invented_name_are_all_caught(tmp_path):
    record = {"case": {"id": CASE}, "counts": {"findings": 1},
              "findings": [{"claims": [{"verdict": "gap", "path": PATH, "line": 17}]}]}
    assert agent.violations("it reads CheckoutController.cs", record) == [
        "the file CheckoutController.cs", "the name CheckoutController"]
    assert agent.violations("there are 3 copies at line 17", record) == ["the number 3"]
    assert agent.violations("the class CheckoutService decides it", record) == [
        "the name CheckoutService"]
    assert agent.violations("the route /api/orders is used", record) == ["the route /api/orders"]
    # A fact the record does hold is not a violation, and a short file name for a stored path is
    # an abbreviation rather than an invention.
    assert agent.violations(f"it is at {PATH} line 17, one finding", record) == []
    assert agent.violations("it is in panel_api.feature", record) == []


def test_the_rejection_sentence_names_the_invented_fact(tmp_path):
    conn = _seed(tmp_path)
    fabricated = "The route /api/orders is what the test should have called."
    try:
        off = _off(conn)
        on = _on(conn, FakeModel(fabricated))
    finally:
        conn.close()
    sentence = ("The model-written explanation was rejected because it named the route "
                "/api/orders, which is not in this case's record. Nothing it wrote was added to "
                "this page.")
    import html as htmllib
    assert on.decode("utf-8") == _with_note(off, htmllib.escape(sentence))


def test_the_prompt_quotes_the_first_findings_and_the_check_uses_them_all():
    """A case with dozens of findings buys a bounded prompt; the check still reads the whole record."""
    findings = [{"title": f"finding {i}", "claims": [{"verdict": "gap"}]} for i in range(9)]
    findings[-1]["claims"][0]["path"] = "late/last_one.feature"
    record = {"case": {"id": CASE}, "counts": {"findings": 9}, "findings": findings}
    text = agent.facts_text(record)
    assert "FINDINGS: 9" in text
    assert f"the first {agent.PROMPT_FINDING_LIMIT} are quoted" in text
    assert "title: finding 5" in text    # the sixth and last quoted one
    assert "title: finding 6" not in text  # the seventh is not
    # A fact the prompt did not quote is still in the record, so it is not a fabrication.
    assert agent.violations("it is in late/last_one.feature", record) == []


# --------------------------------------------------------------------------- AC5: the cache

def test_a_second_view_is_served_from_the_store_and_says_so(tmp_path):
    conn = _seed(tmp_path)
    fake = FakeModel(GOOD_REPLY)
    try:
        first = _on(conn, fake)
        second = _on(conn, fake)
        calls = conn.execute("SELECT COUNT(*) FROM agent_call").fetchone()[0]
    finally:
        conn.close()
    assert len(fake.calls) == 1, "the second view must not call the model"
    assert b"agent-cached" not in first
    assert "stored from an earlier view" in _text(second)
    assert _without_explanation(first) == _without_explanation(second)
    assert calls == 2  # one real call, one cache hit, both in the ledger


def test_the_cache_key_is_case_prompt_hash_and_model(tmp_path):
    conn = _seed(tmp_path)
    fake = FakeModel(GOOD_REPLY)
    try:
        _on(conn, fake)
        record = agent.case_record(conn, CASE)
        _, _, digest = agent.prompt(record, "deepseek-flash")
        other, _, other_digest = agent.prompt(record, "another-model")
        row = conn.execute("SELECT case_id, prompt_hash, model FROM agent_explanation").fetchone()
        again = agent.cached_explanation(conn, CASE, digest, "deepseek-flash")
    finally:
        conn.close()
    assert row["case_id"] == CASE and row["model"] == "deepseek-flash"
    assert row["prompt_hash"] == digest
    assert digest != other_digest, "the model is part of the key"
    assert again is not None


# --------------------------------------------------------------------------- AC6: feedback

def test_the_page_offers_two_plain_links_and_no_script(tmp_path):
    conn = _seed(tmp_path)
    try:
        view_id = agent.start_view(conn, CASE, "on")
        on = _on(conn, FakeModel(GOOD_REPLY), view_id=view_id)
        agent.finish_view(conn, view_id, agent.Outcome(state="explanation"))
    finally:
        conn.close()
    text = on.decode("utf-8")
    block = _EXPLANATION.search(text).group(0)
    assert "This helped" in block and "This did not" in block
    assert f'/case/{CASE}/feedback?view={view_id}&amp;vote=helped' in block
    assert f'/case/{CASE}/feedback?view={view_id}&amp;vote=did_not_help' in block
    assert "<script" not in text.lower()
    assert "set-cookie" not in text.lower()
    assert "<form" not in block, "feedback is two links, not a form"


def test_one_view_counts_one_vote_and_the_report_counts_it_per_variant(tmp_path):
    conn = _seed(tmp_path)
    try:
        view_id = agent.start_view(conn, CASE, "on")
        _on(conn, FakeModel(GOOD_REPLY), view_id=view_id)
        conn.execute("UPDATE agent_view SET served='explanation' WHERE id=?", (view_id,))
        conn.commit()
        first, first_code = app.feedback_page(conn, CASE, str(view_id), "helped")
        second, second_code = app.feedback_page(conn, CASE, str(view_id), "did_not_help")
        votes = conn.execute("SELECT verdict FROM agent_feedback").fetchall()
        rows = {row["variant"]: row for row in agent.report(conn)}
    finally:
        conn.close()
    assert first_code == 200 and b"Recorded" in first
    assert second_code == 200 and b"Already recorded" in second
    assert [v["verdict"] for v in votes] == ["helped"]
    assert rows["on"]["helped"] == 1 and rows["on"]["did_not_help"] == 0


def test_a_vote_for_a_page_that_showed_no_explanation_is_refused(tmp_path):
    conn = _seed(tmp_path)
    try:
        view_id = agent.record_view(conn, CASE, "off")
        body, code = app.feedback_page(conn, CASE, str(view_id), "helped")
    finally:
        conn.close()
    assert code == 400
    assert b"did not show an explanation" in body


# --------------------------------------------------------------------------- AC4: the ledger

def test_the_report_arithmetic_is_the_ledger(tmp_path):
    conn = _seed(tmp_path)
    fake = FakeModel(GOOD_REPLY)
    try:
        for _ in range(2):
            view_id = agent.start_view(conn, CASE, "on")
            _on(conn, fake, view_id=view_id)      # closes the view with its outcome
        agent.record_view(conn, CASE, "off")
        agent.record_feedback(conn, 1, CASE, "on", "helped")
        rows = {row["variant"]: row for row in agent.report(conn)}
        calls = conn.execute("SELECT tokens_in, tokens_out, cached FROM agent_call").fetchall()
    finally:
        conn.close()
    on = rows["on"]
    assert on["views"] == 2
    assert on["explanation_views"] == 2
    assert on["cache_hits"] == 1
    assert on["calls"] == 2
    assert on["explanations_written"] == 1
    assert on["total_tokens"] == sum(int(c["tokens_in"]) + int(c["tokens_out"]) for c in calls) == 180
    assert on["mean_tokens_per_explanation"] == 180.0
    assert on["helped"] == 1
    assert rows["off"]["views"] == 1
    assert rows["off"]["total_tokens"] == 0
    assert rows["off"]["mean_tokens_per_explanation"] is None


def test_a_variant_nobody_viewed_reports_no_mean_rather_than_zero(tmp_path):
    conn = _seed(tmp_path)
    try:
        rows = {row["variant"]: row for row in agent.report(conn)}
    finally:
        conn.close()
    assert rows["on"]["views"] == 0
    assert rows["on"]["mean_tokens_per_explanation"] is None


def test_the_report_page_prints_the_numbers_and_no_price(tmp_path):
    conn = _seed(tmp_path)
    try:
        view_id = agent.start_view(conn, CASE, "on")
        _on(conn, FakeModel(GOOD_REPLY), view_id=view_id)
        body = app.agent_report(conn)
    finally:
        conn.close()
    text = _text(body)
    assert "The agent, measured" in text
    assert "180" in text            # 120 in + 60 out
    assert "Agent on" in text and "Agent off" in text
    assert "$" not in text and "\u00a3" not in text, "the page does not invent a price"


# --------------------------------------------------------------------------- AC7: failure is honest

@pytest.mark.parametrize("reply,cause", [
    (urllib.error.URLError("no route to host"), "unreachable"),
    (urllib.error.HTTPError("https://x", 429, "Too Many Requests", {}, None), "http_429"),
    (urllib.error.HTTPError("https://x", 500, "Server Error", {}, None), "http_500"),
    ("", "empty"),
    ('{"cheapest_surface": "api"}', "malformed"),
    ("Too short", "malformed"),
])
def test_every_failure_is_one_sentence_and_a_cause_in_the_ledger(tmp_path, reply, cause):
    conn = _seed(tmp_path)
    try:
        off = _off(conn)
        on = _on(conn, FakeModel(reply))
        row = conn.execute("SELECT outcome, cause FROM agent_call ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    assert b"agent-text" not in on, "a failed call must not leave a block behind"
    assert b'<p class="agent-note">' in on
    assert len(re.findall(r'<p class="agent-note">', on.decode("utf-8"))) == 1
    assert row["outcome"] == "error" and row["cause"] == cause
    # And the page is the off page plus that one sentence, nothing else.
    sentence = re.search(r'<p class="agent-note">(.*?)</p>', on.decode("utf-8")).group(1)
    assert on.decode("utf-8") == _with_note(off, sentence)


def test_an_unconfigured_agent_serves_the_off_page_and_one_sentence(tmp_path):
    conn = _seed(tmp_path)
    unconfigured = agent.Config(project="testops-resource", endpoint="https://x.invalid",
                                model="deepseek-flash", token="")
    try:
        off = _off(conn)
        on = _on(conn, FakeModel(GOOD_REPLY), cfg=unconfigured)
    finally:
        conn.close()
    assert b"agent-text" not in on
    assert "not available" in _text(on)
    assert "no token" in _text(on)


def test_a_case_with_no_finding_says_there_is_nothing_to_explain(tmp_path):
    conn = _seed(tmp_path, findings=0)
    try:
        off = _off(conn)
        on = _on(conn, FakeModel(GOOD_REPLY))
    finally:
        conn.close()
    assert _with_note(off, "This case raised no finding, so there was nothing for the model to "
                           "explain.") == on.decode("utf-8")


# --------------------------------------------------------------------------- AC8: no credentials

def test_no_credential_reaches_the_page_or_the_ledger(tmp_path):
    conn = _seed(tmp_path)
    secret = "super-secret-token-do-not-print"
    try:
        cfg = agent.Config(project="p", endpoint="https://x.invalid", model="deepseek-flash",
                           token=secret)
        on = _on(conn, FakeModel(GOOD_REPLY), cfg=cfg)
        rows = [dict(row) for row in conn.execute("SELECT * FROM agent_call")]
        views = [dict(row) for row in conn.execute("SELECT * FROM agent_view")]
    finally:
        conn.close()
    assert secret not in on.decode("utf-8")
    assert secret not in json.dumps(rows) and secret not in json.dumps(views)


def test_the_az_path_is_resolved_and_never_assumed():
    source = (ROOT / "testops" / "judgement" / "client.py").read_text(encoding="utf-8")
    assert 'shutil.which("az")' in source, "az must be found on PATH, not assumed"
    assert "wbin" not in source, "no host directory for az may be hard-coded"
    assert not re.search(r'["\']C:', source), "no host path may be hard-coded"
    assert not re.search(r'^AZ\s*=', source, re.M)
    assert client.az_command() in (None,) or isinstance(client.az_command(), str)


def test_endpoint_and_model_default_to_the_foundry_project():
    assert client.endpoint({}) == (
        "https://testops-resource.services.ai.azure.com/openai/v1/chat/completions")
    assert client.model_name({}) == "deepseek-flash"
    assert client.endpoint({"TESTOPS_AGENT_PROJECT": "other-project"}).startswith(
        "https://other-project.services.ai.azure.com/")
    assert client.endpoint({"TESTOPS_AGENT_ENDPOINT": "http://localhost:1234/v1/chat"}) == (
        "http://localhost:1234/v1/chat")
    assert client.model_name({"TESTOPS_AGENT_MODEL": "gpt-x"}) == "gpt-x"


def test_a_supplied_token_is_used_without_asking_azure(monkeypatch):
    monkeypatch.setattr(client, "managed_identity_token", lambda *a, **k: "")
    monkeypatch.setattr(client, "az_token", lambda *a, **k: "")
    assert client.token({"TESTOPS_AGENT_TOKEN": "abc"}) == "abc"
    assert client.token({}) == ""


def test_the_config_reports_why_it_is_unconfigured(monkeypatch):
    agent.reset_token_cache()
    monkeypatch.setattr(client, "managed_identity_token", lambda *a, **k: "")
    monkeypatch.setattr(client, "az_token", lambda *a, **k: "")
    cfg = agent.config(environ={})
    assert not cfg.configured
    assert "no token" in cfg.why_not