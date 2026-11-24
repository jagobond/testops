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

# A reply that only uses facts the seeded record holds: structured evidence, each sentence citing the
# record identifier it rests on. Every test that expects an explanation to be served uses this, so a
# failure here is a change in the checker, not in a fixture.
GOOD_SENTENCES = (
    ("This test asserts that the panel is served.", ("claim",)),
    ("The rule found that the assertion is settled by the page the server sends.", ("claim",)),
    ("The next step is to read the response instead of driving a browser.", ("claim",)),
)


def _reply(pairs, explanation=None):
    """A JSON reply from (sentence, facts) pairs - the shape the prompt asks for."""
    sentences = [sentence for sentence, _ in pairs]
    return json.dumps({"explanation": explanation or " ".join(sentences),
                       "citations": [{"sentence": number, "facts": list(facts)}
                                     for number, (_, facts) in enumerate(pairs, start=1)]})


def _claim_id(conn) -> int:
    return int(conn.execute("SELECT id FROM claim ORDER BY id LIMIT 1").fetchone()[0])


def _good_reply(conn) -> str:
    """The honest reply for the seeded record: it re-quotes the claim id and nothing invented."""
    claim = f"claim:{_claim_id(conn)}"
    return _reply([(sentence, (claim,)) for sentence, _ in GOOD_SENTENCES])


CONFIG = agent.Config(project="testops-resource",
                      endpoint="https://example.invalid/openai/v1/chat/completions",
                      model="deepseek-flash", token="test-token-value")


class FakeModel:
    """A model that answers from a script: a string, a Completion, or an exception to raise."""

    def __init__(self, *replies):
        assert replies, "a fake model needs at least one scripted reply"
        self.replies = list(replies)
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
        fake = FakeModel(_good_reply(conn))
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
        fake = FakeModel(_good_reply(conn))
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
        _on(conn, FakeModel(_good_reply(conn)))
        after = json.dumps(agent.case_record(conn, CASE), sort_keys=True)
    finally:
        conn.close()
    assert before == after


# --------------------------------------------------------------------------- AC3: the check
#
# The review probed the old check with four ordinary lies and all four got through: a wrong verb on a
# real route, a real filename with a wrong line number before a full stop, a count written as a word,
# and a confident claim citing nothing. Each is pinned here as a reply that is now rejected, and the
# honest prose that re-quotes the record is pinned as a reply that still survives.

def _record(findings: int = 6) -> dict:
    """The shape of record the review probed: a route, a file and line, and counts."""
    claim = {"id": 1, "verdict": "gap", "path": PATH, "line": LINE,
             "product": {"route": "GET /rooms", "word": "rooms"}}
    return {"case": {"id": CASE},
            "counts": {"findings": findings, "claims": findings, "sources": 2},
            "findings": [{"claims": [dict(claim)]} for _ in range(findings)]}


# The sentence the real model wrote and was rejected for, quoted from the reply to
# case-restfulbooker-levels-20261124T123451-05 (TESTOPS-90's evidence). The 2405 is the claim id.
REAL_SENTENCE = ("The record does not contain the defect's origin, and claim:2405 is the claim whose "
                 "record that gap concerns.")


def _citation_record(claim_id: int = 2405) -> dict:
    """A record whose claim is 2405, with a near-miss reason, so both id forms can be cited."""
    return {"case": {"id": CASE},
            "counts": {"findings": 1, "claims": 1, "sources": 3},
            "findings": [{"claims": [{
                "id": claim_id,
                "verdict": "repeats_product",
                "statement": "The assertion re-verifies what the product already publishes.",
                "assertion_text": "a room will be created",
                "path": PATH, "line": LINE,
                "product": {"route": "POST /", "word": "room",
                            "reason": "the product declares POST /, whose own claim is create room"}}]}]}


@pytest.mark.parametrize("sentence,facts,expected", [
    # 1. A real route with the wrong verb. The record says GET; the reply says PATCH.
    ("The product declares PATCH /rooms, which is where the panel is served.",
     ["route:GET /rooms"], "the verb PATCH"),
    # 2. A real filename with a wrong line number, with the digit before a full stop.
    (f"The assertion lives in {PATH}, line 99.", [f"file:{PATH}:{LINE}"], "the line 99"),
    # 3. A count written as a word. The record says 6; the reply says four.
    ("The analyser raised four findings for this case.", ["count:findings:6"], "the number four"),
    # 4. A confident product claim that cites nothing at all.
    ("The product validates the token before the handler runs.", [], "the sentence 1"),
])
def test_each_of_the_reviewers_four_lies_is_rejected(sentence, facts, expected):
    record = _record()
    # The facts the replies below cite, or fail to cite, are ones the record really offers - so each
    # rejection is the check disagreeing, not the citation being unknown.
    for fact in facts:
        assert fact in agent.citation_index(record), fact
    reply, cause = agent.parse_reply(_reply([(sentence, facts)]))
    assert cause == "" and reply is not None, "the reply is well-formed; its content is the problem"
    found = agent.violations(reply, record)
    assert any(expected in violation for violation in found), found


def test_honest_prose_that_requotes_the_record_survives():
    """The opposite failure: re-quoting the record's own route, file, count and word is accepted."""
    record = _record()
    honest = [
        ("The analyser raised 6 findings, and the first of them is about the panel.",
         ["count:findings:6"]),
        (f"The assertion lives in {PATH}, line {LINE}.", [f"file:{PATH}:{LINE}"]),
        ("The product declares GET /rooms, matched on the word rooms.", ["route:GET /rooms"]),
        ("The next step is to read the response instead of driving a browser.", ["claim:1"]),
    ]
    reply, cause = agent.parse_reply(_reply(honest))
    assert cause == "" and reply is not None
    assert agent.violations(reply, record) == []


def test_a_citation_the_record_does_not_offer_is_rejected():
    record = _record()
    reply, cause = agent.parse_reply(_reply([
        ("The product already serves the orders endpoint.", ["route:/api/orders"])]))
    assert cause == "" and reply is not None
    assert agent.violations(reply, record) == ["the citation route:/api/orders"]


def test_a_fabricated_route_citation_is_discarded_and_the_page_falls_back(tmp_path):
    conn = _seed(tmp_path)
    fabricated = _reply([("The assertion checks GET /api/orders, which the product already serves, "
                          "so the browser is not needed.", ["route:/api/orders"])])
    try:
        off = _off(conn)
        on = _on(conn, FakeModel(fabricated))
        call = conn.execute("SELECT outcome, cause FROM agent_call"
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


def test_a_wrong_verb_on_a_real_route_reaches_the_page_and_is_rejected(tmp_path):
    """The first lie, end to end: the page falls back and the sentence names the verb."""
    conn = _seed(tmp_path)
    written = _reply([("The product declares PATCH /rooms, matched on the word rooms.",
                       ["route:GET /rooms"])])
    try:
        off = _off(conn)
        on = _on(conn, FakeModel(written))
        row = conn.execute("SELECT outcome, cause FROM agent_call ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    assert row["outcome"] == "rejected" and "PATCH" in row["cause"]
    assert b"agent-text" not in on
    sentence = ("The model-written explanation was rejected: the verb PATCH, where the record says "
                "GET /rooms. Nothing it wrote was added to this page.")
    import html as htmllib
    assert on.decode("utf-8") == _with_note(off, htmllib.escape(sentence))


def test_an_honest_reply_that_requotes_the_record_is_served(tmp_path):
    """A reply that cites the record's own route, file, count and claim is served, not refused."""
    conn = _seed(tmp_path)
    claim = f"claim:{_claim_id(conn)}"
    honest = _reply([
        ("The analyser raised 1 finding, settled by the page the server sends.",
         ["count:findings:1", claim]),
        (f"The assertion lives in {PATH} line {LINE}.", [f"file:{PATH}:{LINE}"]),
        ("The product declares GET /rooms, matched on the word rooms.", ["route:GET /rooms"]),
        ("The next step is to read the response instead of driving a browser.", [claim]),
    ])
    try:
        on = _on(conn, FakeModel(honest))
        row = conn.execute("SELECT outcome FROM agent_call ORDER BY id DESC LIMIT 1").fetchone()
        stored = conn.execute("SELECT text FROM agent_explanation").fetchone()
        view = conn.execute("SELECT served FROM agent_view ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    assert row["outcome"] == "ok"
    assert b"agent-text" in on and "rejected" not in _text(on)
    assert stored is not None and stored["text"].startswith("The analyser raised 1 finding")
    assert view is None or view["served"] in ("fresh", "off")


def test_a_fabricated_file_and_an_invented_name_are_both_caught():
    record = _record()
    reply, _ = agent.parse_reply(_reply([
        ("The check runs in CheckoutController.cs and the class CheckoutService decides it.",
         ["claim:1"])]))
    found = agent.violations(reply, record)
    assert "the file CheckoutController.cs, which no cited fact names" in found
    assert "the name CheckoutService, which no cited fact holds" in found


def test_a_reply_that_is_not_the_agreed_json_is_unusable(tmp_path):
    conn = _seed(tmp_path)
    try:
        on = _on(conn, FakeModel("The product declares GET /rooms and that is all there is to say."))
        row = conn.execute("SELECT outcome, cause FROM agent_call ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    assert row["outcome"] == "error" and row["cause"] == "malformed"
    assert b"agent-text" not in on


def test_a_citation_id_written_in_the_prose_is_not_a_statistic():
    """TESTOPS-90 AC1: the exact sentence the real model wrote, with the id it was rejected for.

    The number scan used to read the 2405 of ``claim:2405`` as a fabricated count. The sentence is
    the model's own, quoted from the rejected reply on
    ``case-restfulbooker-levels-20261124T123451-05``; it is honest, it cites the row it names, and it
    is accepted now.
    """
    record = _citation_record()
    assert "claim:2405" in agent.citation_index(record)
    reply, cause = agent.parse_reply(_reply([(REAL_SENTENCE, ["claim:2405"])]))
    assert cause == "" and reply is not None
    assert agent.violations(reply, record) == []


def test_a_reason_id_written_in_the_prose_is_not_a_statistic_either():
    record = _citation_record()
    assert "reason:2405" in agent.citation_index(record)
    reply, cause = agent.parse_reply(_reply([
        ("The near-miss reason:2405 records that the route shares a word with the assertion.",
         ["reason:2405"])]))
    assert cause == "" and reply is not None
    assert agent.violations(reply, record) == []


def test_a_plain_number_beside_a_real_citation_is_still_refused():
    """The mask is the identifier, not the sentence: a bare ``the number 7`` still rejects."""
    record = _citation_record()
    reply, cause = agent.parse_reply(_reply([
        ("The record does not contain the defect's origin, and the number 7 is not in it.",
         ["claim:2405"])]))
    assert cause == "" and reply is not None
    assert agent.violations(reply, record) == ["the number 7, which no cited fact holds"]


def test_the_prompt_keeps_citation_ids_out_of_the_prose_and_its_version_changed(monkeypatch):
    """AC2: belt and braces, so the model is not relying on the mask."""
    assert agent.PROMPT_VERSION == "explain-a-case/3"
    assert agent.PROMPT_VERSION != "explain-a-case/2"
    assert 'The identifiers belong in the "citations" array and nowhere else' in agent.SYSTEM_PROMPT
    assert "never write one in the explanation's prose" in agent.SYSTEM_PROMPT
    # And the version is part of the cache key, so an explanation written under the old instruction
    # can never be served as one written under this one.
    record = _record()
    _, _, current = agent.prompt(record, "deepseek-flash")
    monkeypatch.setattr(agent, "PROMPT_VERSION", "explain-a-case/2")
    _, _, older = agent.prompt(record, "deepseek-flash")
    assert current != older


def test_one_rejection_is_repaired_once_and_the_good_repair_is_served(tmp_path):
    """AC3, first pin: fail once, succeed on the repair, and the reader gets the explanation."""
    conn = _seed(tmp_path)
    written = _reply([("The product declares PATCH /rooms, which is where the panel is served.",
                       ["route:GET /rooms"])])
    fake = FakeModel(written, _good_reply(conn))
    try:
        view_id = agent.start_view(conn, CASE, "on")
        on = _on(conn, fake, view_id=view_id)
        calls = conn.execute("SELECT outcome, cause, tokens_in, tokens_out FROM agent_call"
                             " ORDER BY id").fetchall()
        stored = conn.execute("SELECT text FROM agent_explanation").fetchone()
        view = conn.execute("SELECT served FROM agent_view WHERE id=?", (view_id,)).fetchone()
    finally:
        conn.close()
    assert len(fake.calls) == 2, "one ask, then one repair"
    assert "the verb PATCH" in fake.calls[1]["user"], "the repair quotes the exact violation"
    assert "Change only the sentences those violations name" in fake.calls[1]["user"]
    assert [call["outcome"] for call in calls] == ["rejected", "ok"]
    assert b"agent-text" in on and "was rejected" not in _text(on)
    assert stored is not None and stored["text"].startswith("This test asserts")
    assert view["served"] == "fresh"


def test_a_second_rejection_falls_back_to_the_honest_sentence_with_state_rejected(tmp_path):
    """AC3, second pin: the repair fails too, so nothing is served and the view says rejected."""
    conn = _seed(tmp_path)
    written = _reply([("The product declares PATCH /rooms, which is where the panel is served.",
                       ["route:GET /rooms"])])
    fake = FakeModel(written)          # the same bad reply every time
    try:
        view_id = agent.start_view(conn, CASE, "on")
        on = _on(conn, fake, view_id=view_id)
        calls = conn.execute("SELECT outcome, cause FROM agent_call ORDER BY id").fetchall()
        stored = conn.execute("SELECT COUNT(*) FROM agent_explanation").fetchone()[0]
        view = conn.execute("SELECT served FROM agent_view WHERE id=?", (view_id,)).fetchone()
    finally:
        conn.close()
    assert len(fake.calls) == 2, "exactly one repair round, not a loop"
    assert [call["outcome"] for call in calls] == ["rejected", "rejected"]
    assert "PATCH" in calls[-1]["cause"]
    assert view["served"] == "rejected"
    assert stored == 0
    assert "The model-written explanation was rejected" in _text(on)
    assert b"agent-text" not in on


def test_the_prompt_offers_the_citations_and_the_check_reads_the_whole_record():
    """A case with dozens of findings buys a bounded prompt; every fact still has an identifier."""
    findings = [{"title": f"finding {i}", "claims": [{"id": i, "verdict": "gap"}]} for i in range(9)]
    findings[-1]["claims"][0]["path"] = "late/last_one.feature"
    record = {"case": {"id": CASE}, "counts": {"findings": 9}, "findings": findings}
    text = agent.facts_text(record)
    assert "FINDINGS: 9" in text
    assert f"the first {agent.PROMPT_FINDING_LIMIT} are quoted" in text
    assert "title: finding 5" in text    # the sixth and last quoted one
    assert "title: finding 6" not in text  # the seventh is not
    # Every citation the record offers is printed in the prompt, including one from a finding the
    # prompt did not quote - so the model can cite what it was told, and the check accepts it.
    index = agent.citation_index(record)
    assert "file:late/last_one.feature" in index
    assert "CITATIONS" in text and "file:late/last_one.feature" in text
    reply, _ = agent.parse_reply(_reply([
        ("The finding is recorded in late/last_one.feature.", ["file:late/last_one.feature"])]))
    assert agent.violations(reply, record) == []


def test_the_rejection_sentence_names_the_invented_fact(tmp_path):
    conn = _seed(tmp_path)
    fabricated = _reply([("The route /api/orders is what the test should have called.",
                          ["route:/api/orders"])])
    try:
        off = _off(conn)
        on = _on(conn, FakeModel(fabricated))
    finally:
        conn.close()
    sentence = ("The model-written explanation was rejected: the citation route:/api/orders. "
                "Nothing it wrote was added to this page.")
    import html as htmllib
    assert on.decode("utf-8") == _with_note(off, htmllib.escape(sentence))



# --------------------------------------------------------------------------- AC5: the cache

def test_a_second_view_is_served_from_the_store_and_says_so(tmp_path):
    conn = _seed(tmp_path)
    fake = FakeModel(_good_reply(conn))
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
    fake = FakeModel(_good_reply(conn))
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
        on = _on(conn, FakeModel(_good_reply(conn)), view_id=view_id)
        agent.finish_view(conn, view_id, agent.Outcome(state=agent.STATE_FRESH))
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
        _on(conn, FakeModel(_good_reply(conn)), view_id=view_id)
        conn.execute("UPDATE agent_view SET served='fresh' WHERE id=?", (view_id,))
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
    fake = FakeModel(_good_reply(conn))
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
    # The same ledger, broken down by what each view actually was.
    fresh, cached = on["states"]["fresh"], on["states"]["cached"]
    assert fresh["views"] == 1 and fresh["explanations_written"] == 1
    assert fresh["total_tokens"] == 180 and fresh["helped"] == 1
    assert cached["views"] == 1 and cached["cache_hits"] == 1
    assert cached["total_tokens"] == 0 and cached["explanations_written"] == 0


def _other_config(model: str) -> agent.Config:
    """The same deployment, a different model: a different cache key, so the model is really asked."""
    return agent.Config(project="testops-resource", endpoint="https://example.invalid/v1/chat",
                        model=model, token="test-token-value")


def test_the_report_separates_every_state_so_value_and_loss_are_not_confused(tmp_path):
    """Six kinds of view, and each figure counted in the state it belongs to.

    A fresh explanation, a cached one, a rejected reply (paid for, thrown away), a failure where the
    model could not answer, a view with no token, and an agent-off view. The point of the breakdown:
    the cached view adds no value of its own, and the rejected and failed views are not a loss of a
    reader's explanation - they are cost, and they say so.
    """
    conn = _seed(tmp_path)
    try:
        # A fresh explanation, which is also the one the cache will serve.
        fresh_view = agent.start_view(conn, CASE, "on")
        _on(conn, FakeModel(_good_reply(conn)), view_id=fresh_view)
        # A second view of the same case: served from the store, zero tokens.
        cached_view = agent.start_view(conn, CASE, "on")
        _on(conn, FakeModel(_good_reply(conn)), view_id=cached_view)
        # A rejected reply: the model was paid for it and nothing was shown. A different model is a
        # different cache key, so the store cannot answer for this view.
        rejected_view = agent.start_view(conn, CASE, "on")
        _on(conn, FakeModel(_reply([("The product declares PATCH /rooms, which is where the panel "
                                     "is served.", ["route:GET /rooms"])])), view_id=rejected_view,
            cfg=_other_config("reject-model"))
        # A failure where the model could not be reached.
        failed_view = agent.start_view(conn, CASE, "on")
        _on(conn, FakeModel(urllib.error.URLError("no route to host")), view_id=failed_view,
            cfg=_other_config("fail-model"))
        # No token: nothing was attempted, so there is nothing to attribute to the model.
        unconfigured = agent.Config(project="p", endpoint="https://x.invalid",
                                    model="deepseek-flash", token="")
        unconfigured_view = agent.start_view(conn, CASE, "on")
        _on(conn, FakeModel(_good_reply(conn)), view_id=unconfigured_view, cfg=unconfigured)
        # An agent-off view.
        agent.record_view(conn, CASE, "off")
        # One vote, cast on the cached page - so it is counted in the cached state.
        app.feedback_page(conn, CASE, str(cached_view), "helped")
        rows = {row["variant"]: row for row in agent.report(conn)}
        calls = conn.execute(
            "SELECT v.served, c.tokens_in + c.tokens_out AS tokens, c.cached FROM agent_call c"
            " JOIN agent_view v ON v.call_id = c.id").fetchall()
    finally:
        conn.close()

    on, states = rows["on"], rows["on"]["states"]
    assert [states[s]["views"] for s in ("fresh", "cached", "rejected", "failed_unavailable",
                                         "failed_unconfigured")] == [1, 1, 1, 1, 1]
    # Tokens belong to the call the view made, so a rejected reply's tokens are visible as cost and
    # a cached view's are zero.
    assert states["fresh"]["total_tokens"] == 180
    assert states["cached"]["total_tokens"] == 0
    assert states["rejected"]["total_tokens"] == 180
    assert states["failed_unavailable"]["total_tokens"] == 0
    assert states["failed_unconfigured"]["calls"] == 0
    # Value and cost are named as such, and never swapped.
    assert states["fresh"]["value"] and states["cached"]["value"]
    assert states["rejected"]["cost"] and not states["rejected"]["value"]
    assert not states["failed_unconfigured"]["value"]
    # The vote is the cached page's, not the fresh one's.
    assert states["cached"]["helped"] == 1 and states["fresh"]["helped"] == 0
    assert on["helped"] == 1
    # And the variant total is the sum of the states, call for call and token for token. A rejected
    # reply now buys one repair attempt (TESTOPS-90), so its view made two calls: the row the view
    # closed on is the repair (180 tokens), and the first attempt is an unlinked call of the same
    # cost. Both are paid for, so both are in the variant total.
    assert on["explanation_views"] == 2      # fresh + cached, not the five views
    assert on["views"] == 5
    assert on["rejected"] == 1 and on["errors"] == 2
    assert sum(int(c["tokens"]) for c in calls) == 360
    assert on["unlinked_calls"] == 1 and on["unlinked_tokens"] == 180
    assert on["total_tokens"] == sum(int(c["tokens"]) for c in calls) + 180 == 540
    assert rows["off"]["states"]["off"]["views"] == 1


def test_the_report_page_breaks_the_numbers_down_by_state(tmp_path):
    conn = _seed(tmp_path)
    try:
        fresh_view = agent.start_view(conn, CASE, "on")
        _on(conn, FakeModel(_good_reply(conn)), view_id=fresh_view)
        cached_view = agent.start_view(conn, CASE, "on")
        _on(conn, FakeModel(_good_reply(conn)), view_id=cached_view)
        body = app.agent_report(conn)
    finally:
        conn.close()
    text = _text(body)
    assert "What each view actually was" in text
    assert "fresh - an explanation written for this view" in text
    assert "cached - an explanation served from the store" in text
    # The cached row is present and its tokens are zero: a cached page is not an explanation's value.
    cached_index = text.index("cached - an explanation served from the store")
    assert " 0 " in text[cached_index:cached_index + 120]


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
        _on(conn, FakeModel(_good_reply(conn)), view_id=view_id)
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
        on = _on(conn, FakeModel(_good_reply(conn)), cfg=unconfigured)
    finally:
        conn.close()
    assert b"agent-text" not in on
    assert "not available" in _text(on)
    assert "no token" in _text(on)


def test_a_case_with_no_finding_says_there_is_nothing_to_explain(tmp_path):
    conn = _seed(tmp_path, findings=0)
    try:
        off = _off(conn)
        on = _on(conn, FakeModel(_good_reply(conn)))
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
        on = _on(conn, FakeModel(_good_reply(conn)), cfg=cfg)
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