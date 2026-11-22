"""TESTOPS-29: the action states the change, and the statement states the reason.

TESTOPS-28 stopped the renderer cutting a stored action at its semicolon, so the page kept the whole
action - and the analyser's own redundancy became visible in the reader's scan line:

    What to do  Rewrite this step to call the HTTP client instead of the browser. The response
                decides everything the browser is being used for.

The second sentence is the argument from the paragraph above, dressed as a second instruction. A
reason in the action is worse than a reason missing: a reader who acts on the plan takes the
justification with it, and the argument they already read is restated where they asked for a plan.

The fix belongs to the analyser's action vocabulary, not to the renderer (TESTOPS-28 made the
renderer dumb on purpose, and it stays dumb). Every action here is asserted to be one instruction of
at most two sentences that does not restate its own statement, and the reason is asserted to still
be in the statement and still on the page.

The corpus arm reads the store, so it skips in a clean checkout: the store is a build artefact.
"""
from __future__ import annotations

import html as htmllib
import re
import sqlite3
from pathlib import Path

import level_fixtures as fixtures
import pytest
from testops import rebuild
from testops.web import app
from testops.web import lint as english

ROOT = Path(__file__).resolve().parents[1]
STORED = ROOT / "data" / "testops.db"
# The run TESTOPS-28 reviewed. Its snapshot is what the corpus arm rebuilds, so the analyser is
# measured against the same 94 assertions the review counted, at the same commits.
PINNED_RUN = "cotw-levels-20261122T011316"

STOPWORDS = frozenset("""
    a an the this that these those it its they them their there here and or but nor so if then
    than as of to in on at for with by from into over under about is are was were be been being
    am do does did has have had no not
""".split())
WORD = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")


# ------------------------------------------------------------------------------ the measure


def content_words(text: str) -> list[str]:
    return [word for word in WORD.findall(text.lower()) if word not in STOPWORDS]


def box_sentences(action: str) -> list[str]:
    """The action box's sentences: the stored action split at its semicolons, as the page does."""
    return [part for part in re.split(r"[.!?;]\s+", action.strip()) if part.strip()]


def repeated_between_sentences(action: str) -> tuple[str, ...]:
    """The content words an action's later sentence repeats from its first (the review's measure).

    The quoted step is not the action's prose - the box has already quoted it above and refers to
    it as "this step" - so callers pass the action with ``_without_step`` applied, exactly as the
    page renders it.
    """
    sentences = box_sentences(action)
    if len(sentences) < 2:
        return ()
    first = set(content_words(sentences[0]))
    return tuple(sorted(first & set(content_words(" ".join(sentences[1:])))))


def page_action(action: str, step: str) -> str:
    """The action as the action box shows it: the step referred to rather than quoted again."""
    for form in (f'the step "{step}"', f'step "{step}"', f'"{step}"'):
        if step and form in action:
            return action.replace(form, "this step", 1)
    return action


# ------------------------------------------------------------------------------ the corpus


def _rebuilt():
    """The 94 claims of the pinned snapshot, written by the working-tree analyser."""
    conn = sqlite3.connect(f"file:{STORED.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT snapshot_id FROM run WHERE id = ?", (PINNED_RUN,)).fetchone()
        assert row is not None, f"the pinned run {PINNED_RUN} is not in the store"
        claims, _stats, _snap = rebuild.rebuild(conn, row["snapshot_id"])
    finally:
        conn.close()
    return claims


def page_claim(claim) -> dict:
    """The claim as the read model hands it to the page: stored fields only, no live source."""
    detail = claim.detail
    return {
        "schema_version": 2,
        "verdict": claim.verdict,
        "statement": claim.statement,
        "interaction_label": detail["interaction_label"],
        "span": detail["span"],
        "assessment": None,
        "proposed_action": detail["proposed_action"],
        "provenance": {"assertion_text": detail["assertion_text"],
                       "assertion_path": detail["assertion_path"],
                       "assertion_line": detail["assertion_line"],
                       "assertion_commit": detail["assertion_commit"]},
    }


def rendered_scan_block(claim) -> str:
    """Section 1 of the case page for this claim, as the reader's text."""
    block = "".join(app.argument_block(page_claim(claim)))
    return " ".join(english.reader_text(block).split())


def action_box(claim) -> str:
    """The action as the reader meets it: the stored string, step referred to, split at ``;``."""
    stored = page_action(claim.detail["proposed_action"], claim.detail["assertion_text"])
    return " ".join(part.strip()[:1].upper() + part.strip()[1:].rstrip(".") + "."
                    for part in re.split(r";\s*", stored) if part.strip())


@pytest.mark.skipif(not STORED.exists(), reason="the product store is a build artefact")
def test_every_action_in_the_corpus_is_one_instruction_of_at_most_two_sentences():
    """AC1 over the real 94: an action is a plan, not a paragraph."""
    claims = _rebuilt()
    assert len(claims) == 94
    for claim in claims:
        sentences = box_sentences(action_box(claim))
        assert 1 <= len(sentences) <= 2, (claim.detail["assertion_text"], sentences)
        assert action_box(claim).endswith("."), claim.detail["assertion_text"]


@pytest.mark.skipif(not STORED.exists(), reason="the product store is a build artefact")
def test_no_action_in_the_corpus_repeats_a_content_word_between_its_own_sentences():
    """AC3: the review's measure, over the same 94 assertions, is zero.

    TESTOPS-28's review measured 2 of 94 - the two review claims, which shared the word "browser"
    between the order and the restatement. The analyser no longer writes a restatement, so the
    count is 0 and this test is the guard against it coming back.
    """
    claims = _rebuilt()
    repeated = [(claim.detail["assertion_text"], repeated_between_sentences(action_box(claim)))
                for claim in claims]
    offenders = [(text, words) for text, words in repeated if words]
    assert offenders == [], offenders
    assert len(repeated) == 94


@pytest.mark.skipif(not STORED.exists(), reason="the product store is a build artefact")
def test_the_scan_block_of_every_claim_passes_the_no_repeat_lint():
    """AC4: the T26 lint over the whole corpus, with no exemptions.

    The lint was never the tool that found this defect - it counts a six-word clause, and the
    worst case here was one word - so it is not what proves the fix. It is run anyway because the
    ticket asks the corpus to pass it unexempted, and the analyser's shorter actions must not
    trade one kind of repetition for another.
    """
    for claim in _rebuilt():
        block = rendered_scan_block(claim)
        assert english.repeated_clause(block) is None, (claim.detail["assertion_text"], block)
        assert english.plain_english(block) == [], claim.detail["assertion_text"]


# --------------------------------------------------------------- the shape, per verdict


@pytest.mark.skipif(not STORED.exists(), reason="the product store is a build artefact")
def test_the_corpus_still_carries_the_verdicts_the_ticket_pins():
    """AC5: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review. Rewording moves no verdict."""
    counts: dict[str, int] = {}
    for claim in _rebuilt():
        counts[claim.verdict] = counts.get(claim.verdict, 0) + 1
    assert counts == {"distinct": 90, "unplaced": 1, "gap": 1, "review": 2}, counts


# The clauses v0.10.1 put after the semicolon, and the sentence of the *statement* that says the
# same thing. The action must no longer carry the clause; the statement must still carry the reason
# in the analyser's own words, so the page's argument says it one line above the action.
RELOCATED = {
    "review": ("the response decides everything the browser is being used for",
               "pays for a browser that decides nothing extra"),
    "gap": ("at this level nothing establishes what it asserts",
            "so nothing checks it"),
    "unplaced": ("a judgement with no comparison in it cannot be checked at any level",
                 "nothing can be said about whether it is checked"),
}


def _claim_for(verdict: str):
    if verdict == "review":
        claims = fixtures.analyse_text(fixtures.BROWSER_FEATURE_TEXT, fixtures.browser_bindings(),
                                       path=fixtures.BROWSER_FEATURE_PATH)
    elif verdict == "gap":
        claims = [claim for claim in fixtures.analyse_fact_sheet() if claim.verdict == "gap"]
    else:
        text = ("Feature: counts\n"
                "  Scenario: the count is reported\n"
                "    Then that count is correct for the store it was run against\n")
        claims = fixtures.analyse_text(text, fixtures.api_bindings())
    assert len(claims) == 1, (verdict, [claim.verdict for claim in claims])
    claim = claims[0]
    assert claim.verdict == verdict, (verdict, claim.verdict)
    return claim


@pytest.mark.parametrize("verdict", sorted(RELOCATED))
def test_the_action_no_longer_carries_the_reason_the_statement_gives(verdict):
    """AC1 and AC2: the clause leaves the action and stays in the statement."""
    removed, kept = RELOCATED[verdict]
    claim = _claim_for(verdict)
    action, statement = claim.detail["proposed_action"], claim.statement
    assert removed not in action, action
    assert kept in statement, statement


@pytest.mark.parametrize("verdict", sorted(RELOCATED))
def test_the_reason_still_reaches_the_reader_through_the_page(verdict):
    """AC2 on the rendered page, not on the stored string.

    The statement is section 1's argument, and section 1 is built from the stored row, so this
    asserts the reason the action used to repeat is still something the reader can read.
    """
    claim = _claim_for(verdict)
    block = rendered_scan_block(claim)
    # What the removed clause was for: for a review, that a browser buys nothing; for a gap, that
    # nothing checks the assertion; for an unplaced claim, that nothing says what it is compared
    # with. Each is the reason the verdict says what it says, and each must survive somewhere a
    # reader looks.
    needed = {"review": ("browser", "settles"),
              "gap": ("browser", "nothing"),
              "unplaced": ("compared",)}[verdict]
    missing = [word for word in needed if word not in block.lower()]
    assert missing == [], (missing, block)


def test_the_distinct_action_states_its_level_as_a_disposition_not_a_justification():
    """The one fact that has nowhere else to live.

    A distinct claim's statement says the run settles the assertion and never says this was the
    cheapest level that could. So the fact stays in the action - folded into the instruction, one
    sentence, so the reader holds a disposition ("keep it at the cheapest level") instead of an
    argument ("keep it, because ...").
    """
    claim = next(claim for claim in fixtures.analyse_fact_sheet() if claim.verdict == "distinct")
    action = claim.detail["proposed_action"]
    assert action.startswith("No change:"), action
    assert "cheapest level that establishes it" in action, action
    assert "because" not in action and "This level" not in action, action
    assert len(box_sentences(action)) == 1, action
    # And it is not in the argument: the sentence exists because nothing else on the page says it.
    assert "cheapest" not in claim.statement.lower(), claim.statement
    assert claim.statement.strip(), claim.statement


# ------------------------------------------------------------------- duplication (AC4)


def _duplication_claims(tmp_path, monkeypatch):
    import reqoverflow_fixtures as corpus
    from testops import pipeline
    from testops.config import Project, Repo

    path, connect = corpus.stub_pipeline(monkeypatch, pipeline, tmp_path)
    project = Project(key="reqoverflow", product=Repo("reqnroll", "Sample-ReqOverflow"),
                      test=Repo("reqnroll", "Sample-ReqOverflow"), jira_key="")
    result = pipeline.run_duplication(project, token="unused")
    return result


def test_a_duplicate_action_asks_for_one_copy_and_nothing_more(tmp_path, monkeypatch):
    """AC4: "keep one" stays; the trailing restatement of the statement goes.

    The stored action used to read "Raise this with the team: this copy calls the HTTP client to
    establish what <where> settles in-process; keep one." - the statement, said a second time in
    the field the reader acts on.
    """
    result = _duplication_claims(tmp_path, monkeypatch)
    assert len(result.claims) == 17
    for claim in result.claims:
        action = claim.detail["proposed_action"]
        assert action == "Raise this with the team: keep one.", action
        assert repeated_between_sentences(action) == ()
        # The finding is not lost: the statement names the copy that already covers this one.
        assert claim.detail["duplicate_of"] in claim.statement, claim.statement
