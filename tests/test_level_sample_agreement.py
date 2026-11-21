"""TESTOPS-10 AC3, AC4, AC5: twenty hand-labelled real assertions.

The labels in ``fixtures/level_sample_20.json`` were written before ``level_fitness`` v0.7 existed,
from the scenario each assertion sits in and the code its step definition calls. They are the
yardstick the change is measured against, so this file must not be adjusted to make a result look
better - a recorded miss is the useful outcome.

The agreements are asserted per assertion, first as a list of misses (a failing test that names
only the ratio hides which labels disagree), and then as the ratio itself.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from testops.analysers import level_fitness as lf
from testops.extract import gherkin, stepbindings

FIXTURE = Path(__file__).with_name("fixtures") / "level_sample_20.json"
CODE = re.compile(r"\b(I[1-4]|KP)\b")
AGREEMENT_FLOOR = 0.85
SUITE = "sample"


def samples() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["samples"]


def _feature_and_bindings(sample: dict):
    """One scenario holding the one real assertion, bound at the layer its own step definition has."""
    text = (f"Feature: sampled assertions\n"
            f"  Scenario: {sample['scenario']}\n"
            f"    Then {sample['assertion']}\n")
    feature = gherkin.parse(f"features/sample.feature", text)
    assert feature is not None
    binding = stepbindings.Binding(pattern=sample["assertion"], verb="Then", cls="SampleSteps",
                                   path="Steps/SampleSteps.cs", layer=sample["binding_layer"],
                                   suite=SUITE)
    return feature, [binding]


def _analyse(sample: dict):
    feature, bindings = _feature_and_bindings(sample)
    return lf.analyse(
        features=[feature], bindings=bindings, surfaces=[],
        uri_for_path=lambda path: f"github:fixture/fixture@deadbeef:{path}",
        budget={"calls": 0, "tokens_in": 0, "tokens_out": 0},
    )[0]


def test_the_sample_is_twenty_real_assertions_with_expected_interactions():
    rows = samples()
    assert len(rows) == 20
    assert all(row["expected_interaction"] in {"I1", "I2", "KP", "I3", "I4"} for row in rows)
    # The sample was drawn from the real run, not invented: the unplaced half is represented.
    assert sum(1 for row in rows if row["baseline_verdict"] == "unplaced") >= 5


def test_the_classifier_agrees_with_the_hand_labels_at_85_percent_or_better():
    rows = samples()
    agree, disagree = [], []
    for row in rows:
        got, _ = lf.classify_with_instrument(row["assertion"], row["binding_layer"])
        (agree if got == row["expected_interaction"] else disagree).append(
            (row["assertion"], row["expected_interaction"], got))

    ratio = len(agree) / len(rows)
    detail = "\n".join(f"  expected {want}, got {got}: {text}" for text, want, got in disagree)
    assert ratio >= AGREEMENT_FLOOR, (
        f"agreement {len(agree)}/{len(rows)} = {ratio:.3f}, below {AGREEMENT_FLOOR}:\n{detail}")
    # A miss is a fact about the vocabulary, not a reason to edit the labels.
    assert len(disagree) <= 3, f"more misses than the ticket's floor allows:\n{detail}"


def test_every_classified_sample_names_the_rule_that_classified_it():
    """AC4: `established_by` says which rule decided, so a reader can see why."""
    for row in samples():
        claim = _analyse(row)
        established_by = claim.detail["established_by"]
        assert established_by, f"no rule recorded for: {row['assertion']}"
        assert established_by.startswith(("the words", "the step's definition")), established_by


def test_the_newly_classified_claims_keep_reader_readable_text():
    """AC5: no codes, a statement in words, and an action that names the step."""
    newly = [row for row in samples() if row["baseline_verdict"] == "unplaced"]
    assert newly, "the sample holds no claim that was unplaced before this change"
    for row in newly:
        claim = _analyse(row)
        assert claim.verdict != "unplaced", f"still unplaced: {row['assertion']}"

        for field, text in (("statement", claim.statement),
                            ("interaction_label", claim.detail["interaction_label"]),
                            ("proposed_action", claim.detail["proposed_action"]),
                            ("established_by", claim.detail["established_by"])):
            assert text and text.strip(), f"{field} is empty for: {row['assertion']}"
            assert not CODE.search(text), f"{field} carries a code: {text!r}"

        spoken = row["assertion"].lstrip()
        spoken = spoken[:1].lower() + spoken[1:]
        assert spoken in claim.detail["proposed_action"], claim.detail["proposed_action"]
        assert "asserts that" in claim.statement or "This step says" in claim.statement, \
            claim.statement


def test_the_sample_analysis_is_deterministic():
    """AC6, on this sample: same input, same claims, including the words."""
    for row in samples():
        first, second = _analyse(row), _analyse(row)
        assert (first.statement, first.verdict, first.detail) == \
            (second.statement, second.verdict, second.detail)


def test_a_step_with_no_subject_still_reads_as_english():
    """A real assertion whose step continues the sentence the step before it began.

    "And says the approval no longer covers the text" has no subject. It was unplaced before this
    change, so its reader-facing text is new - and "This test asserts that says ..." is not a
    sentence a developer should meet.
    """
    claim = _analyse({"scenario": "An edited claim is reported as no longer covered by its approval",
                      "assertion": "says the approval no longer covers the text",
                      "binding_layer": "api", "baseline_verdict": "unplaced"})
    assert "asserts that says" not in claim.statement
    assert 'asserts the step "says the approval no longer covers the text"' in claim.statement
