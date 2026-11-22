"""TESTOPS-31: the table is part of the assertion.

The Product Owner opened a duplication case and found no evidence of the copy the page named.
Investigating that found a false positive instead: ``QuestionSuggestions.feature:17`` asserts one
suggestion and ``:39`` asserts three, but the analyser compared step *text* only, so the two
scenarios had one signature and the page told the reader the project ran one test twice.

These tests pin the corrected rule against the real corpus and against small in-memory features:

  * AC1 - tables and doc strings are part of a scenario's signature, so scenarios that differ only
    in their data are not duplicates;
  * AC2 - ``assertion_text`` carries the data, so a claim never ends at "should be";
  * AC3 - the before/after counts on reqoverflow, and what each resolved pair differed by;
  * AC4 - the exact pair is not a duplicate, and a genuinely identical pair still is;
  * AC5 - a run written before the fix keeps its stored text;
  * AC6 - the level-fitness corpus is untouched (``test_level_fitness`` owns those counts).
"""
from __future__ import annotations

import re

import pytest

import reqoverflow_fixtures as corpus
from testops.analysers import duplication
from testops.extract import gherkin

FEATURE_PATH = "features/suggestions.feature"


# ------------------------------------------------------------------ helpers


def _feature(text: str, path: str = FEATURE_PATH) -> gherkin.Feature:
    feature = gherkin.parse(path, text)
    assert feature is not None
    return feature


def _claims(text: str, path: str = FEATURE_PATH):
    return duplication.analyse([_feature(text, path)], [], lambda p: f"github:o/r@c:{p}")


def _corpus_features() -> list[gherkin.Feature]:
    return [f for f in (_feature(text, path) for path, text in corpus.texts().items()
                        if path.endswith(".feature")) if f is not None]


def _old_normalise(text: str) -> str:
    """The 2.1.0 rule: step words only, digits parameterised. Used only to count the before."""
    t = text.strip().lower()
    t = re.sub(r"[\"'`]", "", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\b\d+\b", "#", t)
    return re.sub(r"\s+", " ", t).strip()


def _old_signature(scenario: gherkin.Scenario) -> str:
    return " | ".join(_old_normalise(step.text) for step in scenario.steps)


def _groups(signature_of) -> dict[str, list[tuple[str, gherkin.Scenario]]]:
    groups: dict[str, list[tuple[str, gherkin.Scenario]]] = {}
    for feature in _corpus_features():
        for scenario in feature.scenarios:
            groups.setdefault(signature_of(scenario), []).append((feature.path, scenario))
    return groups


def _claimed(groups) -> list[tuple[str, gherkin.Scenario]]:
    """One claim per duplicated scenario except each group's reference copy."""
    return [member for members in groups.values() if len(members) > 1 for member in members[1:]]


def _suggestions(feature: gherkin.Feature) -> dict[int, gherkin.Scenario]:
    return {scenario.line: scenario for scenario in feature.scenarios}


# ------------------------------------------------------------------ AC1


def test_the_pair_the_product_owner_opened_now_asserts_differently():
    """:17 asserts one suggestion; :39 asserts three. Their signatures must differ in the rows."""
    feature = next(f for f in _corpus_features()
                   if f.path.endswith("QuestionSuggestions.feature"))
    scenarios = _suggestions(feature)
    one, three = scenarios[8], scenarios[29]          # the stored run names lines 17 and 39 for the
    # Then steps; the scenarios begin at 8 and 29 and the assertion lines are 17 and 39.
    assert (one.steps[-1].line, three.steps[-1].line) == (17, 39)
    assert one.signature != three.signature

    one_rows = [row for step in one.steps for row in step.table]
    three_rows = [row for step in three.steps for row in step.table]
    assert ["What is Reqnroll?"] in one_rows
    assert ["What is Reqnroll?"] in three_rows
    assert ["Question 2"] in three_rows and ["Question 3"] in three_rows
    assert ["Question 2"] not in one_rows and ["Question 3"] not in one_rows
    # The Then step alone has the same words and different rows, which is the whole defect.
    assert one.steps[-1].text == three.steps[-1].text == "the suggestions list should be"
    assert one.steps[-1].table != three.steps[-1].table


def test_scenarios_that_differ_only_in_table_rows_are_not_duplicates():
    feature = """\
Feature: suggestions
  Scenario: one suggestion
    Given the questions are asked as
      | title             |
      | What is Reqnroll? |
    When the user starts asking
    Then the suggestions list should be
      | title             |
      | What is Reqnroll? |

  Scenario: three suggestions
    Given the questions are asked as
      | title             |
      | What is Reqnroll? |
    When the user starts asking
    Then the suggestions list should be
      | title             |
      | What is Reqnroll? |
      | Question 2        |
      | Question 3        |
"""
    assert _claims(feature) == []


def test_doc_strings_are_part_of_the_signature():
    feature = """\
Feature: request bodies
  Scenario: twelve
    When the request body is
      \"\"\"json
      {"questions": 12}
      \"\"\"
    Then the response status is 200

  Scenario: three
    When the request body is
      \"\"\"json
      {"questions": 3}
      \"\"\"
    Then the response status is 200
"""
    assert _claims(feature) == []


def test_outline_examples_are_part_of_the_signature():
    feature = """\
Feature: counting
  Scenario Outline: the count is reported
    Then there are <count> questions
    Examples:
      | count |
      | 12    |

  Scenario Outline: the count is reported again
    Then there are <count> questions
    Examples:
      | count |
      | 3     |
"""
    assert _claims(feature) == []


def test_digits_in_step_text_are_not_parameterised():
    feature = """\
Feature: counting
  Scenario: twelve
    Then there are 12 questions

  Scenario: three
    Then there are 3 questions
"""
    assert _claims(feature) == []


# ------------------------------------------------------------------ AC2


def test_the_assertion_carries_the_table_so_it_never_ends_at_should_be():
    claims = _claims("""\
Feature: suggestions
  Scenario: one suggestion
    Then the suggestions list should be
      | title             |
      | What is Reqnroll? |

  Scenario: one suggestion again
    Then the suggestions list should be
      | title             |
      | What is Reqnroll? |
""")
    assert len(claims) == 1
    detail = claims[0].detail
    assert detail["assertion_text"] == ("the suggestions list should be: What is Reqnroll?")
    assert not detail["assertion_text"].rstrip().endswith("should be")
    assert detail["assertion_text"] in claims[0].statement


def test_the_reqoverflow_claims_never_stop_at_should_be():
    claims = duplication.analyse(_corpus_features(), [], lambda p: f"github:o/r@c:{p}")
    assert claims
    for claim in claims:
        text = claim.detail["assertion_text"]
        assert not text.rstrip().endswith("should be"), text
        assert text in claim.statement, text
    # At least one claim's assertion is a table, because that is what the fix must render.
    assert any(": " in claim.detail["assertion_text"] for claim in claims)


def test_the_page_quotes_the_table_with_the_step():
    from testops.web import app

    claim = {
        "provenance": {"assertion_text": "the suggestions list should be: What is Reqnroll?"},
        "snippets": {"assertion": {"state": "ok", "lines": [
            {"n": 17, "text": "  Then the suggestions list should be", "asserted": True}]}},
    }
    assert app.quoted_assertion(claim) == "Then the suggestions list should be: What is Reqnroll?"


# ------------------------------------------------------------------ AC4


def test_a_genuinely_identical_pair_is_still_a_duplicate():
    feature = """\
Feature: suggestions
  Scenario: the fact sheet is served
    Then the suggestions list should be
      | title             |
      | What is Reqnroll? |

  Scenario: the fact sheet is served again
    Then the suggestions list should be
      | title             |
      | What is Reqnroll? |
"""
    claims = _claims(feature)
    assert len(claims) == 1
    assert claims[0].verdict == "duplicate"
    assert claims[0].detail["assertion_text"] == ("the suggestions list should be: What is Reqnroll?")
    assert "the fact sheet is served" in claims[0].statement


def test_the_identical_pair_in_the_corpus_is_still_a_duplicate():
    """The fix must not be "stop reporting duplicates": the same rows still duplicate."""
    claims = duplication.analyse(_corpus_features(), [], lambda p: f"github:o/r@c:{p}")
    subjects = [claim.subject_ref for claim in claims]
    assert not any("QuestionSuggestions.feature" in subject for subject in subjects)
    # AskingQuestions.feature:6 asks the same question over the same table in three suites.
    shared = [claim for claim in claims if claim.subject_ref.endswith("#The question is posted")]
    assert len(shared) == 2
    assert all("[table]" in claim.detail["signature"] for claim in shared)


# ------------------------------------------------------------------ AC3


def test_rerun_counts_before_and_after_and_names_what_resolved():
    before = _groups(_old_signature)
    after = _groups(lambda scenario: scenario.signature)
    before_claims = {f"{path}:{scenario.line}": (path, scenario) for path, scenario in _claimed(before)}
    after_claims = {f"{path}:{scenario.line}": (path, scenario) for path, scenario in _claimed(after)}

    assert len(before_claims) == 18, "the stored run's own count, on step text alone"
    assert len(after_claims) == 17, "one finding was a false positive"

    resolved = sorted(set(before_claims) - set(after_claims))
    assert resolved == [
        "ReqOverflow.Specs.Controller/Features/Question/QuestionSuggestions.feature:29",
    ]
    # The pair differs twice over: the Given table and the Then table. The Then table is the one
    # the claim quoted.
    _, scenario = before_claims[resolved[0]]
    other = next(sc for _path, sc in before[_old_signature(scenario)]
                 if sc.line != scenario.line)
    assert scenario.steps[-1].table != other.steps[-1].table
    assert scenario.steps[0].table != other.steps[0].table
    assert "Question 2" in str(scenario.steps[-1].table)
    assert "Question 2" not in str(other.steps[-1].table)


# ------------------------------------------------------------------ AC5


def test_an_older_run_keeps_its_stored_text(tmp_path):
    """Only new runs carry the corrected text; reading an old row does not rewrite it."""
    from testops.store import db
    from testops.web import app

    conn = db.connect(tmp_path / "old.db")
    db.upsert_snapshot(conn, "snap-old", "reqoverflow", "2026-11-20T15:34:30+00:00",
                       {corpus.REPO_SLUG: corpus.COMMIT}, schema_version=2)
    db.start_run(conn, "run-old", "reqoverflow", "snap-old", duplication.name,
                 "2026-11-20T15:34:31+00:00")
    path = "ReqOverflow.Specs.Controller/Features/Question/QuestionSuggestions.feature"
    claim_id = db.add_claim(
        conn, "run-old", duplication.name, "2.1.0", f"scenario:{path}#The same word is in different fields",
        'The scenario "The same word is in different fields" asserts "the suggestions list should be".',
        "duplicate", 0.9, [], schema_version=2,
        assertion_text="the suggestions list should be", assertion_path=path,
        assertion_line=39, assertion_commit=corpus.COMMIT,
        interaction_label="settled by the answer the application returns",
        span=["controller"], proposed_action="Raise this with the team: keep one.")
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
                 " VALUES (?,?,?,?,?,?,?)",
                 ("case-old", "run-old", "reqoverflow", duplication.name, "snap-old",
                  "2026-11-20T15:34:31+00:00", "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)",
                 ("case-old", "old finding", "medium", "b" * 32, db.j([claim_id])))
    conn.commit()
    try:
        row = conn.execute("SELECT assertion_text FROM claim WHERE id = ?", (claim_id,)).fetchone()
        body = app.case_page(conn, "case-old")
    finally:
        conn.close()

    assert row["assertion_text"] == "the suggestions list should be"
    assert body is not None


# ------------------------------------------------------------------ guards


@pytest.mark.parametrize("text", ["| a |", "| |", "|a|b|"])
def test_table_rendering_never_drops_a_cell(text):
    step = _feature("Feature: x\n  Scenario: y\n    Then z\n      " + text).scenarios[0].steps[0]
    assert step.table
    assert all(cell in step.assertion_text or cell.strip() == "" for cell in step.table[0])


def test_a_step_that_already_ends_in_a_colon_does_not_get_two():
    step = _feature("Feature: x\n  Scenario: y\n    Then the body is:\n      | a |\n").scenarios[0].steps[0]
    assert step.assertion_text == "the body is: a"
