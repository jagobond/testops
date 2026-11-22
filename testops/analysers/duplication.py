"""Deterministic duplication analysis.

The question: does more than one test assert the same claim, and if so, is the copy at the expensive level
adding anything? A copy that reaches the UI to assert what the API already asserts adds a mechanism, not a
claim — and it costs maintenance forever.

No model is involved. This runs in CI and can fail a build.

v2.2.0 (TESTOPS-31) — the table is part of the assertion.

v2.1.0 compared scenarios by their step *words*. Two scenarios that said "Then the suggestions
list should be" over different tables therefore had one signature, and the page told a reader the
project ran the same test twice when it ran two different lists. The signature now includes the
rows of every data table and the text of every doc string, and the claim's ``assertion_text``
carries them too, so it reads as something a reader can check rather than a sentence that stops at
"should be". Digits are no longer parameterised: "12 questions" and "3 questions" are different
test data. A genuinely identical pair - same words, same rows - stays a duplicate.

v2.1.0 (TESTOPS-29) — the action states the change, and the statement states the finding.

The action used to restate the statement before saying what to do: "this copy calls the HTTP
client to establish what … settles in-process; keep one." Once the page kept the whole action
instead of cutting at the semicolon (TESTOPS-28), the reader met the same finding twice and the
second copy arrived as an instruction. The action is now the change only — "Raise this with the
team: keep one." — and the statement keeps the finding, which is where a reader looks for it.

v2.0 (TESTOPS-21) — a duplication claim is a v2 claim about one scenario's assertion.

v1 stated the relation and nothing else ("asserts the same claim as 1 cheaper copy(ies) at controller; this
copy drives api"). That sentence is identical across every finding in a group, and it records the verdict
instead of the assertion, so a reader opening eighteen cases saw eighteen identical statements and no
finding. This version writes what the Product Owner asked for:

  * every claim carries the coordinates of the step that asserts - the first ``Then`` (or the step that
    follows it) in the scenario - plus the commit, so the page can show the source inline as TESTOPS-19
    established for level fitness;
  * the statement names the scenario's own file and line, quotes what the scenario asserts, and names the
    copy that already establishes it with *that* copy's ``file:line``. Two findings cannot share a
    statement, because each names its own scenario and the copy it duplicates;
  * the proposed action raises the duplicate for the team and asks them to keep one copy. It never
    condemns the test and never recommends deletion outright;
  * the scenario's step-definition observations are recorded in ``support`` (the asserting step's binding
    first), so the evidence resolves from the claim's coordinates rather than from a live source.

The grouping rule is identical normalised step sequence *and data*: the rows of every table, the text
of every doc string and an outline's examples, judged by the highest layer any step's binding reaches,
cheapest known layer first. One claim per duplicated scenario remains the unit - the ticket is explicit
that duplicates are not merged into one finding.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .. import sources
from ..extract import gherkin, stepbindings
from .base import Claim, Evidence

name = "duplication"
version = "2.2.0"
uses_model = False

# Duplication is a question about test code, so test code is what its verdict rests on. Requirements
# are consulted for context and recorded as a blind spot when they cannot be read - the same
# capability declaration as the level analyser, and no knowledge of which source provides either.
NEEDS = frozenset({sources.TEST_CODE})
CONSULTS = frozenset({sources.REQUIREMENTS})

# What a decision recorded on a duplication case covers (TESTOPS-47). Its identity is the scenario
# and the normalised signature of its steps and tables - the commit is not in it, so a deploy keeps
# the decision; renaming or moving the scenario changes the subject, and changing either copy's
# steps changes the signature, so both ask again. This is a different contract from the level
# analyser's, which is why the page renders the declaring analyser's sentence and never a global one.
COVER = ("A decision covers one duplicated scenario, recognised by its steps and data tables rather "
         "than the commit; renaming or moving the scenario, or changing the steps in either copy, "
         "asks you again.")

# How a reader says what this copy does, per layer it reaches.
_LAYER_READS = {
    "ui": "drives a browser",
    "api": "calls the HTTP client",
    "controller": "calls the application's own controllers in-process",
    "engine": "talks to the engine",
    "storage": "reads the database",
    "unknown": "reaches nothing that could establish it",
}

# What settles an assertion established at each layer, as the end of a sentence.
_SETTLED = {
    "ui": "through the browser",
    "api": "over HTTP",
    "controller": "in-process",
    "engine": "through the engine",
    "storage": "against the stored data",
    "unknown": "at no identified level",
}

# The reader's phrase for what settles the assertion at the cheapest copy. No debugging code appears
# in any reader-facing text.
_LABEL = {
    "ui": "settled by what a person sees while acting",
    "api": "settled by the response the server sends over HTTP",
    "controller": "settled by the application's own controllers in-process",
    "engine": "settled by the engine's own answer",
    "storage": "settled by the data as stored",
    "unknown": "unclear what would settle it",
}


def _scenario_ref(feature_path: str, scenario: gherkin.Scenario) -> str:
    return f"scenario:{feature_path}#{scenario.name}"


def _suite(path: str) -> str:
    """Top-level project segment of a spec path, e.g. 'ReqOverflow.Specs.API'."""
    head = path.split("/", 1)[0]
    return head


def _asserting_steps(scenario: gherkin.Scenario) -> list[gherkin.Step]:
    """`Then`, and every `And`/`But`/`*` after it. `Given`/`When` are context and assert nothing."""
    out, asserting = [], False
    for step in scenario.steps:
        keyword = step.keyword.strip().lower()
        if keyword == "then":
            asserting = True
        elif keyword in ("given", "when"):
            asserting = False
        if asserting:
            out.append(step)
    return out


def _assertion_step(scenario: gherkin.Scenario) -> gherkin.Step:
    """The step this claim is pinned to: the first asserting step, or the scenario's last step.

    A scenario with no `Then` still makes a claim (its steps were judged duplicates), so a claim with
    no assertion would have nothing to point at. The last step is the most it can say, and it is
    recorded as fact rather than invented.
    """
    asserting = _asserting_steps(scenario)
    if asserting:
        return asserting[0]
    return scenario.steps[-1]


def _quote(text: str) -> str:
    """Quote a step verbatim. A step that already carries double quotes gets typographic ones."""
    return f"\u201c{text}\u201d" if '"' in text else f'"{text}"'


def _assertion_phrase(scenario: gherkin.Scenario) -> str:
    """What the scenario asserts, quoted: every asserting step, or its one fallback step.

    The quote is the step's words *with its data*. Quoting only the words produced "the suggestions
    list should be", which is not an assertion - the list was in the table underneath it
    (TESTOPS-31).
    """
    steps = _asserting_steps(scenario) or [scenario.steps[-1]]
    texts = [_quote(step.assertion_text) for step in steps]
    if len(texts) == 1:
        return texts[0]
    return ", ".join(texts[:-1]) + " and " + texts[-1]


def _where(feature: gherkin.Feature, scenario: gherkin.Scenario) -> str:
    return f"{feature.path}:{_assertion_step(scenario).line}"


def _level_phrase(layer: str) -> str:
    return "at an unidentified level" if layer == "unknown" else f"at the same level ({layer})"


@dataclass
class _Member:
    """One scenario in a duplicate group, with what the claim about it must record."""
    feature: gherkin.Feature
    scenario: gherkin.Scenario
    layer: str
    span: list[str]
    support: list[int]


def _support_for(scenario: gherkin.Scenario, bound_for: dict[int, stepbindings.Binding],
                 support_index: dict[tuple[str, str, str], int]) -> list[int]:
    """The observation ids behind this scenario, the asserting step's binding first.

    The read model marks ``evidence[0]`` as the step that is asserted, so the order is load-bearing:
    the scenario's other bindings follow it because the span - and therefore the verdict - is a fact
    about the whole scenario. A binding with no recorded observation contributes nothing; an empty
    list is then the truth ("nothing was recorded"), not zero evidence.
    """
    assertion = _assertion_step(scenario)
    ordered = [bound_for.get(assertion.line)] + list(bound_for.values())
    out: list[int] = []
    for binding in ordered:
        if binding is None:
            continue
        observation = support_index.get((binding.path, binding.verb, binding.pattern))
        if observation is not None and observation not in out:
            out.append(observation)
    return out


def _claim(member: _Member, other: _Member, *, cheapest: str, same_level: bool, signature: str,
           group_size: int, commit: str, assessed: bool, missing: list[str] | None,
           assessment_record: dict | None, uri_for_path) -> Claim:
    """One duplicated scenario as a v2 claim that names its own assertion and the copy that covers it."""
    scenario, feature = member.scenario, member.feature
    assertion = _assertion_step(scenario)
    other_where = _where(other.feature, other.scenario)
    if same_level:
        statement = (f'The scenario "{scenario.name}" at {_where(feature, scenario)} asserts '
                     f"{_assertion_phrase(scenario)}, which {other_where} already asserts "
                     f"{_level_phrase(member.layer)}.")
    else:
        statement = (f'The scenario "{scenario.name}" at {_where(feature, scenario)} '
                     f"{_LAYER_READS[member.layer]} to assert {_assertion_phrase(scenario)}, "
                     f"which {other_where} already establishes {_SETTLED[cheapest]}.")
    # What to do, and nothing else (TESTOPS-29). The clause that used to sit here - "this copy
    # calls the HTTP client to establish what <where> settles in-process" - was the statement
    # restated, so the reader met the same finding twice, the second time in the field they act on.
    # The statement above names the copy; the action names the change.
    proposed = "Raise this with the team: keep one."

    label = _LABEL[member.layer if same_level else cheapest]
    detail = {
        "signature": signature,
        "layer": member.layer,
        "cheapest": member.layer if same_level else cheapest,
        "group_size": group_size,
        "duplicate_of": other_where,
        "intra_level": same_level,
        "assertion_text": assertion.assertion_text,
        "assertion_path": feature.path,
        "assertion_line": assertion.line,
        "assertion_commit": commit,
        "interaction_label": label,
        "instrument": member.layer,
        "established_by": (f"the scenario's steps match those of {other_where} after normalisation, "
                           f"tables and doc strings included, and its step definitions place this "
                           f"copy at {member.layer}"),
        "sources_assessed": assessed,
        "sources_missing": list(missing) if assessed else None,
        "assessment": assessment_record,
        "proposed_action": proposed,
        "support": member.support,
        "span": member.span,
        "evidence_key": f"duplicate|{gherkin.normalise(scenario.name)}|{signature}",
    }
    return Claim(
        subject_ref=_scenario_ref(feature.path, scenario),
        statement=statement,
        verdict="duplicate",
        confidence=0.9,
        evidence=[Evidence(uri=uri_for_path(feature.path), line=assertion.line, note=scenario.name),
                  Evidence(uri=uri_for_path(other.feature.path),
                           line=_assertion_step(other.scenario).line, note=other.scenario.name)],
        detail=detail,
    )


def analyse(features: list[gherkin.Feature], bindings: list[stepbindings.Binding],
            uri_for_path, *, sources_missing=None, assessment=None, commit: str = "",
            support_index: dict[tuple[str, str, str], int] | None = None) -> list[Claim]:
    """Group scenarios by normalised step signature and judge the surplus copies.

    ``sources_missing`` and ``assessment`` are the caller's registry-derived records, copied onto
    every claim exactly as the level analyser does. The analyser never names a source itself.
    ``sources_missing=None`` means no registry was consulted, and the claim records "not assessed";
    a list - including an empty one - means it was, and this is what it said.

    ``commit`` is the commit the coordinates were read at, and ``support_index`` maps a binding's
    ``(path, verb, pattern)`` to the observation row the caller recorded for it. Both are handed in
    by the caller: this module never touches the store, so a claim's provenance and evidence are
    facts the run recorded, not values guessed here.
    """
    assessed = sources_missing is not None
    missing = list(sources_missing) if assessed else None
    assessment_record = None if assessment is None else assessment.record()
    support_index = support_index or {}
    groups: dict[str, list[_Member]] = defaultdict(list)

    # Each suite defines its own step bindings for the same step text. Matching globally meant every step
    # resolved to whichever suite happened to be parsed first, which collapsed the layering entirely.
    by_suite: dict[str, list[stepbindings.Binding]] = defaultdict(list)
    for b in bindings:
        by_suite[_suite(b.path)].append(b)

    for feat in features:
        suite_bindings = by_suite.get(_suite(feat.path)) or bindings
        for sc in feat.scenarios:
            if not sc.steps:
                continue
            bound_for: dict[int, stepbindings.Binding] = {}
            for step in sc.steps:
                b = stepbindings.match_step(suite_bindings, step.text)
                if b:
                    bound_for[step.line] = b
            layer = stepbindings.highest([b.layer for b in bound_for.values()]) \
                if bound_for else "unknown"
            span = sorted({b.layer for b in bound_for.values()})
            groups[sc.signature].append(_Member(
                feature=feat, scenario=sc, layer=layer, span=span,
                support=_support_for(sc, bound_for, support_index)))

    claims: list[Claim] = []
    for signature, members in groups.items():
        if len(members) < 2:
            continue
        layers = {m.layer for m in members}
        known = {l for l in layers if l != "unknown"}

        def make(member: _Member, other: _Member, *, cheapest: str, same_level: bool) -> Claim:
            return _claim(member, other, cheapest=cheapest, same_level=same_level,
                          signature=signature, group_size=len(members), commit=commit,
                          assessed=assessed, missing=missing,
                          assessment_record=assessment_record, uri_for_path=uri_for_path)

        if len(known) > 1:
            cheapest = min(known, key=stepbindings.LAYER_ORDER.index)
            at_cheapest = [m for m in members if m.layer == cheapest]
            seen_at_cheapest = 0
            for member in members:
                if member.layer != cheapest:
                    claims.append(make(member, at_cheapest[0], cheapest=cheapest, same_level=False))
                else:
                    # A repeat *at* the cheapest layer is waste too, and the earlier code dropped it
                    # entirely because it looked like "the copy that earns its place".
                    seen_at_cheapest += 1
                    if seen_at_cheapest > 1:
                        claims.append(make(member, at_cheapest[0], cheapest=cheapest,
                                           same_level=True))
        elif len(members) > 1:
            # Same level, same steps: duplication inside one layer. Still waste, different fix.
            # When exactly one member's layer is identifiable the unknown copies are judged against
            # that copy, not against whichever scenario was parsed first.
            cheapest = next(iter(known)) if known else "unknown"
            reference = next(m for m in members if m.layer == cheapest)
            for member in members:
                if member is reference:
                    continue
                claims.append(make(member, reference, cheapest=cheapest,
                                   same_level=member.layer == reference.layer))
    return claims
