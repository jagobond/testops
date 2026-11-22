"""Level fitness v0.9 - one claim per assertion, in words a reader can act on.

v0.9 records what the claim could be checked against, and what the run could not see. Every claim
carries, in ``detail["assessment"]``, the verdict the source registry reached for the capabilities
this analyser needs: ``found`` (we looked, there was something), ``zero`` (we looked, there was
nothing) or ``not_assessable`` (nobody could look, with the reason attached). The two the product
turns on are the last two; a claim that needs a source nobody could consult is not a zero and must
never be rendered as one.

The analyser still never imports a collector. It declares ``NEEDS`` - the capabilities without
which its verdict cannot stand - and ``CONSULTS`` - the capabilities it would like to check itself
against but does not depend on. The caller asks the registry what is missing and whether the claim
is assessable, and hands both back here to be copied onto every claim. Adding a source is therefore
a change to the registry, never a change to this module.

The level verdicts are untouched by v0.9. Recording a blind spot must not move a verdict: a claim
can be ``distinct`` as a statement about the test and still be ``not_assessable`` as a statement
about the sources behind it, and the two are reported separately.

v0.8.1 records what each claim rests on. Every claim carries, in ``detail["support"]``, the ids of the
step-binding observations its verdict was derived from: the binding of its own step first, then the
bindings of the scenario's other steps, because the span and the instrument are a fact about the whole
scenario. The ids come from the caller's observation index; the caller records the rows. The analysis
itself is untouched - recording evidence must not change a verdict.

v0.8 adds restraint, after v0.7 wrote the failure itself:

  * a claim that asserts a *meta* property - that a count is correct, that a report is accurate,
    that a result is right - is not placed by any noun in it. "Store", "data", "result", "count"
    and "correct" appear in almost any sentence, so a claim built on them says nothing about what
    would settle it. Such a claim is placed only when it says what the judgement is made against
    (it matches, equals or agrees with something); otherwise it goes back to `unplaced`, even
    though its step is bound to a layer and the instrument fallback could place it. A claim
    checked only in name is worse than an honest `unplaced`, because a reader trusts it;
  * one verification pass yields one label. The instrument a claim is settled by now decides the
    reader's phrase, from one table that also feeds the statement: a suite with no server behind it
    (engine, storage) cannot tell a reader that "the response the server sends" settles anything, so
    every claim in such a suite is labelled by the answer the instrument itself gives. The CotW
    verification feature's twelve claims - "the pass fails", "the overall result is a failure",
    "the clean store exits with the success status" and their siblings - now carry one label
    instead of three wordings, while their interaction codes stay what the words and the binding
    said. Codes are for scoring; the label is what a reader trusts;
  * the statement's account of what settles a claim comes from that same table, so a label and a
    statement cannot describe different instruments. A page claim in a browser suite no longer
    tells the reader the response settles it.

v0.7 answers the coverage miss v0.6 left: on the real CotW repository pair it classified 48 of 94
claims `unplaced`, because the vocabulary only knew a handful of nouns. A person classified every
one of them at once. The ruling this version implements:

  * the words still decide first, and the vocabulary now covers what a claim about a store, a
    report, a sheet, an API body or a served page actually says - reporting, naming, grouping,
    counting, recording, refusing;
  * a page claim no longer needs a person acting to be recognisable: "the page's search state is
    not-searched" is the page as served, and v0.6 could only see it when the same step also said
    "clicked";
  * when the words name nothing settleable, the assertion's own step binding decides - a step
    definition that only calls the HTTP client makes its claim an HTTP claim, one that drives a
    browser makes it a browser claim. That is evidence about the instrument, never a substitute
    for intent: the title is still never consulted, and a step with no binding stays `unplaced`
    rather than being guessed at;
  * each claim records, in `established_by`, the rule that classified it, in the reader's words.

Widening the vocabulary must not manufacture findings, which is the failure mode that killed the
v0.1 analyser. Only the accessibility rule and a browser interaction make a claim need a browser,
so no new rule here can turn an API-suite claim into a `gap`.

Level fitness v0.6 - one claim per assertion, in words a reader can act on.

v0.5 was unreadable and title-driven. It classified a scenario from `name + every step
concatenated`, so a scenario titled "...with stable fact anchors" whose third step asserted an
accessibility property was judged by whatever words the title happened to contain, and its
statement read:

  "I4 claim needs a browser to be established; the suite asserts it over api, so the claim is not
   actually established"

A reader cannot tell from that what is asserted, where, or what to do about it.

The ruling this version implements:

  * a claim is one asserting step - the `Then`, or any `And`/`But` after it. `Given`/`When` are
    context and make no claim;
  * the step's own words decide what the claim is about. The scenario title is accepted as context
    and never consulted, so a title that disagrees with its step cannot change the verdict;
  * the statement says what is asserted, what establishing it needs and what the test actually did,
    in plain language with no shorthand;
  * every claim carries a proposed action naming the step to change, a reader-language interaction
    label, and the caller's record of which sources were never connected.

The `I1`..`I4`/`KP` vocabulary still exists - it is precise, and the analysis is still expressed in
it - but it lives in `interaction_code` and `detail`, for scoring and debugging. It never appears in
text a reader sees.

The span rule from v0.5 is unchanged: a test is not "at a level"; it reaches a SPAN of layers on
the way to its assertion, and the one thing that is waste is paying for a browser when the
assertion is decidable without one.

Verdicts:
  distinct  the instrument is adequate for the claim and no browser was bought unnecessarily
  review    a browser was used for a claim that the response body settles
  gap       the claim needs a browser and no browser ran - the claim is not established at all
  unplaced  the claim or the instrument cannot be identified
"""
from __future__ import annotations

import re

from .. import sources
from ..extract import stepbindings
from ..extract.gherkin import normalise
from .base import Claim, Evidence

name = "level_fitness"
version = "0.9.0"
uses_model = False

# What this analyser's verdict rests on, and what it would like to check itself against but does
# not depend on. A source that cannot provide a needed capability makes every claim not_assessable;
# a source that only serves the consulted set is a blind spot the claim records and still stands.
# Adding a source never edits these - it changes the registry.
NEEDS = frozenset({sources.TEST_CODE, sources.CODE})
CONSULTS = frozenset({sources.REQUIREMENTS})

BEHAVIOUR = re.compile(r"\b(click(s|ed)?|submit(s|ted)?|type(s|d)?|fills?|enters?|press(es)?|selects?|"
                       r"navigates?|visits?|opens? the page|interacts?|drags?|hovers?)\b", re.I)
PRESENTATION = re.compile(r"\b(render(s|ed)?|page|pages?|displayed (to|on)|visible|shown?|shows?|"
                          r"markup|element|heading|layout|screen|html)\b", re.I)
ACCESSIBILITY = re.compile(r"\b(accessible|assistive technolog(?:y|ies)|aria|label(?!led)|button text|"
                           r"screen reader|accessibility tree|landmark|alt text|wcag|css class|"
                           r"document order|position in the document)\b", re.I)
MARKUP = re.compile(r"\b(anchor(s|ed)?|data-[a-z-]+|attribute|element carrying|markup|server-rendered|"
                    r"rendered by the server|html source|response body)\b", re.I)
# What a claim about content says it does with the content: reporting, naming, grouping, counting,
# recording. A claim that no vocabulary at all could place is the one that stays unplaced.
CONTENT = re.compile(r"\b(lists?|listed|every sheet|each fact|every fact|value|citation|subject|kind|"
                     r"fact count|book count|the data|contents?|rows?|columns?|paragraph|reports?|"
                     r"reported|names?|named|groups?|grouped|entries|entry|counts?|numbers?|"
                     r"appears?|order|proposals?|proposed|sheets?)\b", re.I)
HTTP = re.compile(r"\b(status|404|400|422|500|json|http|header|content-type|response|endpoint|route|"
                  r"api|error|refus(ed|es|al)|exit(s|ed)?( with)?|returns? (a|an|the)? ?"
                  r"(json|list|object|error|null))\b", re.I)
STORE = re.compile(r"\b(bytes?|byte-identical|persist(s|ed)?|stored|stores?|database|datastore|canon|"
                   r"hash|fingerprint|file|admits?|admitted|excludes?|excluded|commits?|transaction|"
                   r"records?|recorded|tables?)\b", re.I)

# A claim that asserts a *meta* property - "that count is correct", "the report is accurate" -
# judges something instead of saying what settles the judgement. The nouns such a claim leans on
# ("count", "report", "result", "store", "data") appear in almost any sentence, so no noun in it
# can place the claim. Only an explicit comparison makes it checkable, because a comparison is
# something a test can actually run. This is restraint, not coverage: a claim checked only in name
# is worse than an honest `unplaced`, because a reader trusts it.
META_PROPERTY = re.compile(r"\b(is|are|was|were|stays?|remains?|seems?|appears?)\s+"
                           r"(?:not\s+|only\s+|still\s+|also\s+)?(correct|accurate|right|wrong)\b", re.I)
COMPARISON = re.compile(r"\b(matches?|matched|matching|equals?|identical to|the same as|"
                        r"agrees? with|compares?|compared (with|against)|reconcil\w*|"
                        r"differs? from|as many as|consistent with)\b", re.I)

# The one reason an assertion stays unplaced after its instrument is known: the words made a
# judgement and never said what the judgement is against, so no instrument could settle it.
WHY_META = ("the words judge something correct or accurate and never say what it is compared "
            "with, so nothing could settle it")

NEEDS_BROWSER = {"I3", "I4"}

# One claim per step means a step that asserts two things is read strictly: a step cannot assert
# less than it says, so if any part of it needs a browser, the claim needs a browser.
_STRENGTH = {"U": 0, "I1": 1, "I2": 2, "KP": 3, "I3": 4, "I4": 5}

# The reader's phrase for each interaction. This is what a case page shows; the codes are for
# scoring and debugging only.
INTERACTION_LABEL = {
    "I1": "settled by the data as stored",
    "I2": "settled by the response the server sends",
    "I3": "settled by what a person sees while acting",
    "I4": "needs a browser",
    "KP": "settled by the page the server sends",
    "U": "unclear what would settle it",
}

# What a run whose highest layer is <instrument> actually reads, as a reader would say it.
_READS = {
    "ui": "drives a browser",
    "api": "only reads the responses the server sends",
    "controller": "only calls the application's own controllers in-process",
    "engine": "only talks to the engine",
    "storage": "only reads the database",
    "unknown": "reaches nothing that could establish it",
}

# What settles a claim at each interaction, as a noun phrase. The reader's label and the statement
# are both built from this, so the two cannot describe different instruments.
_SETTLED_BY = {
    "I1": "the data as stored",
    "I2": "the response the server sends",
    "KP": "the page the server sends",
}

# Debugging shorthand that must never reach a reader. AC4.
_CODE_TOKEN = re.compile(r"\b(I[1-4]|KP)\b")

# A step may continue the sentence before it ("And says the approval no longer covers the text"),
# so it can arrive with no subject. "This test asserts that says ..." is not English; the step's
# own words are quoted instead.
_SUBJECTLESS = re.compile(r"^(says|shows|records|reports|names|lists|contains|holds|appears|renders|"
                          r"returns|exits|reads|writes|includes|carries)\b", re.I)


def _assertion_phrase(clause: str) -> str:
    """The clause as the object of "This test asserts ...", keeping the sentence grammatical."""
    return f'the step "{clause}"' if _SUBJECTLESS.match(clause) else f"that {clause}"


def _meta_without_comparison(text: str) -> bool:
    """True when the words judge something (correct, accurate, right) and never say against what.

    A comparison is the only thing a test can run, so without one the claim is unplaceable however
    many nouns it contains - and it must not be rescued by the instrument fallback, which can only
    name a layer, never a comparison.
    """
    return bool(META_PROPERTY.search(text)) and not COMPARISON.search(text)


def classify_claims(text: str, context: str = "") -> list[tuple[str, str]]:
    """Return the interactions one assertion's words belong to, in a stable order.

    ``text`` is a single step's text. ``context`` is the scenario title - it exists so a caller is
    never tempted to concatenate the two, and it is deliberately never consulted: a title is
    context, and a title that disagrees with its step must not change what the step asserts.

    Kept pure: no repository, no bindings, no model. More than one pair is returned only when one
    sentence genuinely asserts two different things; :func:`classify_step` reduces that to the
    single claim a step is allowed.

    Order matters and is deliberate. A meta claim comes first: if the words judge something
    correct without saying what it is compared with, no noun in the sentence can place it, and no
    instrument can settle a judgement that names no comparison. Then a page-structure or
    accessibility claim is about the page even when it also says "response body" or "returns"; a
    response claim is about the response even when it also names the store it read; and a claim
    about a page's content, with no person acting, is the page as served (``KP``) rather than data
    reaching a presentation (``I3``).
    """
    out: list[tuple[str, str]] = []
    if _meta_without_comparison(text):
        return [("U", WHY_META)]
    markup, access = bool(MARKUP.search(text)), bool(ACCESSIBILITY.search(text))
    if markup:
        out.append(("KP", "the words name the page as served, which the response body settles"))
    if access:
        out.append(("I4", "the words name an accessibility property the browser computes"))
    if out:
        return out
    if HTTP.search(text):
        return [("I2", "the words name the response the tool sends")]
    if STORE.search(text):
        return [("I1", "the words name a guarantee about the data as stored")]
    if PRESENTATION.search(text) and BEHAVIOUR.search(text):
        return [("I4", "the words name what a person sees while acting")]
    if PRESENTATION.search(text):
        return [("KP", "the words name the page as served")]
    if CONTENT.search(text):
        return [("I3", "the words name data reaching the presentation")]
    return []


def classify_step(step_text: str, context: str = "") -> tuple[str, str]:
    """The single claim an asserting step makes, classified by its own words.

    A step that mentions both markup and accessibility is still one step, and therefore one claim.
    The strictest reading wins because the step cannot assert less than it says; splitting such a
    step is a job for the test's author, not for the reader of the claim.
    """
    pairs = classify_claims(step_text, context)
    if not pairs:
        return "U", "the step's words name nothing that could settle it"
    return max(pairs, key=lambda pair: _STRENGTH[pair[0]])


# The last resort, and evidence rather than guesswork: a step whose words place nothing is still
# bound to a step definition, and that definition's instrument is a fact about the test. It can
# never create a `gap` (a browser suite's fallback is a browser claim, a non-browser suite's is
# not), and a step with no binding is not covered here - it stays unplaced, because nothing at all
# is known about it.
_INSTRUMENT_CLAIM = {
    "ui": ("I4", "the step's definition drives a browser, so what a browser shows is what settles it"),
    "api": ("I2", "the step's definition only calls the HTTP client, so the response settles it"),
    "controller": ("I2", "the step's definition calls the application's controller in-process, "
                         "so the answer it returns settles it"),
    "engine": ("I1", "the step's definition only talks to the engine, so the engine's own answer settles it"),
    "storage": ("I1", "the step's definition only reads the database, so the stored rows settle it"),
}


def classify_with_instrument(step_text: str, layer: str, context: str = "",
                             *, uses_browser: bool = False) -> tuple[str, str]:
    """The claim, from its words first and its step's instrument only when the words fail.

    ``layer`` is the layer of the step's own binding (``ui``/``api``/``controller``/``engine``/
    ``storage``), or ``unknown`` when the step is unbound. The returned ``why`` always names which
    rule decided, so a reader can see that an instrument fallback was used.

    Two refusals are deliberate. A meta claim (the words judge something correct without saying
    what it is compared with) is never rescued by the instrument: the binding can name a layer but
    it cannot name a comparison, so the claim stays unplaced however confidently it is bound. And a
    response claim in a suite with no server behind it keeps its code - the words did name the
    response the tool sends - but is labelled, and described, as the answer that instrument
    actually gives; the reader must not be told about a server the run does not have.

    ``uses_browser`` says whether any step of the scenario drives a browser. A content claim
    (``I3``) is about data reaching a presentation, which only a browser can show someone: without
    one, the same content is whatever the step actually calls - the response an HTTP step sends, or
    the engine's own answer. v0.6 called all of these "the page the server sends", which was wrong
    about an API suite and made the interaction label mislead a reader.
    """
    interaction, why = classify_step(step_text, context)
    if interaction == "U" and why != WHY_META:
        claim = _INSTRUMENT_CLAIM.get(layer)
        if claim is not None:
            interaction, why = claim[0], f"the words place it nowhere, and {claim[1]}"
    if interaction == "I3" and not uses_browser:
        if layer in ("api", "controller"):
            interaction, why = "I2", "the words name content, and with no user acting the response settles it"
        elif layer in ("engine", "storage"):
            interaction, why = "I1", "the words name content, and with no user acting the stored rows settle it"
    return interaction, why


def asserting_steps(steps) -> list:
    """`Then`, and every `And`/`But`/`*` after it. `Given`/`When` are context and make no claim."""
    out, asserting = [], False
    for step in steps:
        keyword = step.keyword.strip().lower()
        if keyword == "then":
            asserting = True
        elif keyword in ("given", "when"):
            asserting = False
        # And / But / * inherit the phase of the step before them.
        if asserting:
            out.append(step)
    return out


def _for_reader(text: str) -> str:
    """Strip debugging shorthand and tidy the result, so a reader never meets `I4` or `KP`."""
    return re.sub(r"\s{2,}", " ", _CODE_TOKEN.sub("", text)).strip()


def _clause(step_text: str) -> str:
    """The assertion as the middle of a sentence: 'the citation sits inside a named element'."""
    text = _for_reader(step_text).rstrip(".")
    if len(text) > 1 and text[0].isupper() and not text[1].isupper() and not text.startswith("I "):
        text = text[0].lower() + text[1:]
    return text


def _reads(instrument: str) -> str:
    """What the test actually did, in the reader's words."""
    return _READS.get(instrument, _READS["unknown"])


def _label(interaction: str, instrument: str) -> str:
    """The reader's phrase for what settles this claim, in the suite it actually ran in.

    One table feeds both this and the statement, so a label cannot name one instrument while the
    statement names another. A suite with no server behind it (engine, storage) gives its own
    answer; telling a reader that "the response the server sends" settles a claim in a suite with
    no server is the contradiction that made one verification pass read as three stories.
    """
    if interaction in NEEDS_BROWSER or interaction == "U":
        return INTERACTION_LABEL[interaction]
    if interaction in ("I1", "I2") and instrument == "engine":
        return "settled by the engine's own answer about the stored data"
    if interaction in ("I1", "I2") and instrument == "storage":
        return "settled by the data as stored"
    if interaction == "I1" and instrument in ("api", "controller"):
        return "settled by the data as stored, read through the response the server sends"
    return INTERACTION_LABEL[interaction]


def _settles(interaction: str) -> str:
    """What settles a claim at this interaction, as the subject of a sentence."""
    phrase = _SETTLED_BY.get(interaction, INTERACTION_LABEL.get(interaction, "something settles that"))
    return phrase[0].upper() + phrase[1:]


def _statement(interaction: str, clause: str, verdict: str, instrument: str,
               why: str = "") -> str:
    """What is asserted, what establishing it needs, and what the test actually did."""
    is_asserted = _assertion_phrase(clause)
    if verdict == "gap":
        return (f"This test asserts {is_asserted}. Only a browser works that out, and this test "
                f"{_reads(instrument)} instead, so nothing checks it.")
    if verdict == "review":
        return (f"This test asserts {is_asserted}. {_settles(interaction)} settles that, but this "
                f"test drives a browser, so it pays for a browser that decides nothing extra.")
    if verdict == "unplaced":
        if why == WHY_META:
            return (f"This step says \"{clause}\", which calls it correct without saying what it is "
                    f"compared with, so nothing can be said about whether it is checked.")
        if interaction == "U":
            return (f"This step says \"{clause}\", which does not name data, a response, a page or "
                    f"anything a person sees, so nothing can be said about whether it is checked.")
        return (f"This test asserts {is_asserted}, but none of its steps could be tied to a layer of "
                f"the system, so nothing can be said about whether it is checked.")
    # distinct
    if interaction in NEEDS_BROWSER:
        return (f"This test asserts {is_asserted}. It drives a browser, which is what works that out, "
                f"so the assertion is checked.")
    return (f"This test asserts {is_asserted}. This test {_reads(instrument)}, which settles that, "
            f"so the assertion is checked.")


def _proposed_action(interaction: str, clause: str, verdict: str, why: str = "") -> str:
    """One sentence naming the step to change. This is the field a case reviewer acts on."""
    if verdict == "gap":
        return (f"Move the step \"{clause}\" into a test that drives a browser, or delete it; at this "
                f"level nothing establishes what it asserts.")
    if verdict == "review":
        return (f"Rewrite the step \"{clause}\" to call the HTTP client instead of the browser; the "
                f"response decides everything the browser is being used for.")
    if verdict == "unplaced":
        if why == WHY_META:
            return (f"Rewrite the step \"{clause}\" to say what it is compared with - the value, the "
                    f"row or the report it should agree with - then re-run; a judgement with no "
                    f"comparison in it cannot be checked at any level.")
        if interaction == "U":
            return (f"Rewrite the step \"{clause}\" to say whether it is about the data, the response, "
                    f"the page, or what a person sees, then re-run.")
        return (f"Bind the step \"{clause}\" to a step definition whose driver can be identified, then "
                f"re-run; nothing can be judged until then.")
    return (f"No change: keep the step \"{clause}\" where it is; this level is the cheapest one that "
            f"establishes it.")


def analyse(features, bindings, surfaces, uri_for_path, budget: dict | None = None, *,
            sources_missing=None, assessment=None, commit: str = "",
            support_index: dict[tuple[str, str, str], int] | None = None) -> list[Claim]:
    """One claim per asserting step, in deterministic order.

    ``sources_missing`` is the caller's record of which sources were never connected. It is copied
    onto every claim, and a caller that passes nothing records an explicit empty list: a claim may
    say "nothing was missing", it may never imply it.

    ``assessment`` is the registry's verdict for the capabilities this analyser needs (see
    :data:`NEEDS`). It is copied onto every claim as a plain record, with the reason attached when a
    source nobody could consult is involved. ``None`` means the caller did not record an assessment,
    which is different from an assessment of "nothing was missing" and is stored as ``None``.

    ``support_index`` maps a binding's ``(path, verb, pattern)`` to the id of the observation row the
    caller recorded for it. It is how a claim learns *which rows* back it without this module ever
    touching the store. When it is omitted - or holds no row for a binding - the claim's support is
    an explicit empty list: nothing was recorded, which is the truth, not zero evidence.
    """
    missing = [] if sources_missing is None else list(sources_missing)
    assessment_record = None if assessment is None else assessment.record()
    index = support_index or {}
    claims: list[Claim] = []

    for feat in features:
        for sc in feat.scenarios:
            if not sc.steps:
                continue
            suite = stepbindings.suite_of(feat.path)
            matched = [b for step in sc.steps if (b := stepbindings.match_step(bindings, step.text, suite))]
            assert_binding = {step.line: stepbindings.match_step(bindings, step.text, suite)
                              for step in asserting_steps(sc.steps)}
            span = sorted({b.layer for b in matched})
            instrument = stepbindings.highest([b.layer for b in matched]) if matched else "unknown"
            uses_browser = "ui" in span
            ref = f"scenario:{feat.path}#{sc.name}"
            seen: dict[str, int] = {}

            for step in asserting_steps(sc.steps):
                # The words decide; the assertion's own step binding decides only when the words
                # name nothing that could settle it.
                binding = assert_binding.get(step.line)
                # The assertion's own binding first: that is what the reader is pointed at. The
                # scenario's other matched steps follow, because the span and the instrument - and
                # therefore the verdict - are a fact about the whole scenario.
                support: list[int] = []
                for bound in [binding] + matched:
                    if bound is None:
                        continue
                    observation = index.get((bound.path, bound.verb, bound.pattern))
                    if observation is not None and observation not in support:
                        support.append(observation)

                interaction, why = classify_with_instrument(
                    step.text, binding.layer if binding else "unknown", sc.name,
                    uses_browser=uses_browser)

                clause = _clause(step.text)
                if instrument == "unknown" or interaction == "U":
                    verdict = "unplaced"
                elif interaction in NEEDS_BROWSER and not uses_browser:
                    verdict = "gap"
                elif interaction in NEEDS_BROWSER:
                    verdict = "distinct"
                elif uses_browser:
                    verdict = "review"
                else:
                    verdict = "distinct"

                # Identity of the assertion for suppression: the interaction and the assertion's own
                # words, never its line, so reformatting the file does not resurrect a judged case.
                base_key = f"{interaction}|{normalise(step.text)}"
                seen[base_key] = seen.get(base_key, 0) + 1
                evidence_key = base_key if seen[base_key] == 1 else f"{base_key}#{seen[base_key]}"

                detail = {
                    "claim": interaction,
                    "interaction_code": interaction,
                    "interaction_label": _label(interaction, instrument),
                    "assertion_text": step.text,
                    "assertion_path": feat.path,
                    "assertion_line": step.line,
                    "assertion_commit": commit,
                    "span": span,
                    "instrument": instrument,
                    "established_by": why,
                    "sources_missing": list(missing),
                    "assessment": assessment_record,
                    "proposed_action": _proposed_action(interaction, clause, verdict, why),
                    "support": support,
                    "evidence_key": evidence_key,
                    "uses_browser": uses_browser,
                    "needs_browser": interaction in NEEDS_BROWSER,
                    "cheapest": "ui" if interaction in NEEDS_BROWSER else "api",
                    "why": why,
                    "stage": "rule",
                }
                claims.append(Claim(
                    subject_ref=ref,
                    statement=_statement(interaction, clause, verdict, instrument, why),
                    verdict=verdict,
                    confidence=0.8,
                    evidence=[Evidence(uri=uri_for_path(feat.path), line=step.line, note=step.text)],
                    detail=detail,
                ))
    return claims
