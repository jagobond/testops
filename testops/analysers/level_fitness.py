"""Level fitness v0.6 - one claim per assertion, in words a reader can act on.

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

from ..extract import stepbindings
from ..extract.gherkin import normalise
from .base import Claim, Evidence

name = "level_fitness"
version = "0.6.0"
uses_model = False

BEHAVIOUR = re.compile(r"\b(click(s|ed)?|submit(s|ted)?|type(s|d)?|fills?|enters?|press(es)?|selects?|"
                       r"navigates?|visits?|opens? the page|interacts?|drags?|hovers?)\b", re.I)
PRESENTATION = re.compile(r"\b(render(s|ed)?|page|displayed (to|on)|visible|shown to|shows? (the|a) |markup|"
                          r"element|heading|layout|screen|html)\b", re.I)
ACCESSIBILITY = re.compile(r"\b(accessible|assistive technolog(?:y|ies)|aria|label(?!led)|button text|"
                           r"screen reader|accessibility tree|landmark|alt text|wcag|css class|"
                           r"document order)\b", re.I)
MARKUP = re.compile(r"\b(anchor(s|ed)?|data-[a-z-]+|attribute|element carrying|markup|server-rendered|"
                    r"html source|response body)\b", re.I)
CONTENT = re.compile(r"\b(lists?|every sheet|each fact|value|citation|subject|kind|fact count|book count|"
                     r"the data|contents?|rows?|columns?|paragraph)\b", re.I)
HTTP = re.compile(r"\b(status|404|400|422|500|json|http|header|content-type|response|endpoint|route|"
                  r"api|returns? (a|an|the)? ?(json|list|object|error|null))\b", re.I)
STORE = re.compile(r"\b(bytes?|byte-identical|persist(s|ed)?|stored|database|datastore|canon|hash|file|"
                   r"admits?|admitted|excludes?|excluded|commits?|transaction)\b", re.I)

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

# Debugging shorthand that must never reach a reader. AC4.
_CODE_TOKEN = re.compile(r"\b(I[1-4]|KP)\b")


def classify_claims(text: str, context: str = "") -> list[tuple[str, str]]:
    """Return the interactions one assertion's words belong to, in a stable order.

    ``text`` is a single step's text. ``context`` is the scenario title - it exists so a caller is
    never tempted to concatenate the two, and it is deliberately never consulted: a title is
    context, and a title that disagrees with its step must not change what the step asserts.

    Kept pure: no repository, no bindings, no model. More than one pair is returned only when one
    sentence genuinely asserts two different things; :func:`classify_step` reduces that to the
    single claim a step is allowed.
    """
    out: list[tuple[str, str]] = []
    markup, access = bool(MARKUP.search(text)), bool(ACCESSIBILITY.search(text))
    if markup:
        out.append(("KP", "asserts the page as served, which the response body settles"))
    if access:
        out.append(("I4", "asserts an accessibility property the browser computes"))
    if out:
        return out
    if STORE.search(text):
        return [("I1", "asserts a datastore guarantee")]
    if HTTP.search(text) and not PRESENTATION.search(text):
        return [("I2", "asserts an HTTP contract")]
    if PRESENTATION.search(text) and BEHAVIOUR.search(text):
        return [("I4", "asserts what a person sees while acting")]
    if CONTENT.search(text):
        return [("I3", "asserts data reaching the presentation")]
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


def _statement(interaction: str, clause: str, verdict: str, instrument: str) -> str:
    """What is asserted, what establishing it needs, and what the test actually did."""
    if verdict == "gap":
        return (f"This test asserts that {clause}. Only a browser works that out, and this test "
                f"{_reads(instrument)} instead, so nothing checks it.")
    if verdict == "review":
        return (f"This test asserts that {clause}. The response the server sends settles that, but this "
                f"test drives a browser, so it pays for a browser that decides nothing extra.")
    if verdict == "unplaced":
        if interaction == "U":
            return (f"This step says \"{clause}\", which does not name data, a response, a page or "
                    f"anything a person sees, so nothing can be said about whether it is checked.")
        return (f"This test asserts that {clause}, but none of its steps could be tied to a layer of "
                f"the system, so nothing can be said about whether it is checked.")
    # distinct
    if interaction in NEEDS_BROWSER:
        return (f"This test asserts that {clause}. It drives a browser, which is what works that out, "
                f"so the assertion is checked.")
    return (f"This test asserts that {clause}. This test {_reads(instrument)}, which settles that, "
            f"so the assertion is checked.")


def _proposed_action(interaction: str, clause: str, verdict: str) -> str:
    """One sentence naming the step to change. This is the field a case reviewer acts on."""
    if verdict == "gap":
        return (f"Move the step \"{clause}\" into a test that drives a browser, or delete it; at this "
                f"level nothing establishes what it asserts.")
    if verdict == "review":
        return (f"Rewrite the step \"{clause}\" to call the HTTP client instead of the browser; the "
                f"response decides everything the browser is being used for.")
    if verdict == "unplaced":
        if interaction == "U":
            return (f"Rewrite the step \"{clause}\" to say whether it is about the data, the response, "
                    f"the page, or what a person sees, then re-run.")
        return (f"Bind the step \"{clause}\" to a step definition whose driver can be identified, then "
                f"re-run; nothing can be judged until then.")
    return (f"No change: keep the step \"{clause}\" where it is; this level is the cheapest one that "
            f"establishes it.")


def analyse(features, bindings, surfaces, uri_for_path, budget: dict | None = None, *,
            sources_missing=None, commit: str = "") -> list[Claim]:
    """One claim per asserting step, in deterministic order.

    ``sources_missing`` is the caller's record of which sources were never connected. It is copied
    onto every claim, and a caller that passes nothing records an explicit empty list: a claim may
    say "nothing was missing", it may never imply it.
    """
    missing = [] if sources_missing is None else list(sources_missing)
    claims: list[Claim] = []

    for feat in features:
        for sc in feat.scenarios:
            if not sc.steps:
                continue
            suite = stepbindings.suite_of(feat.path)
            matched = [b for step in sc.steps if (b := stepbindings.match_step(bindings, step.text, suite))]
            span = sorted({b.layer for b in matched})
            instrument = stepbindings.highest([b.layer for b in matched]) if matched else "unknown"
            uses_browser = "ui" in span
            ref = f"scenario:{feat.path}#{sc.name}"
            seen: dict[str, int] = {}

            for step in asserting_steps(sc.steps):
                interaction, why = classify_step(step.text, sc.name)
                # Without a user acting there is no user-to-datastore claim: what the suite
                # establishes is the served content.
                if interaction == "I3" and not uses_browser:
                    interaction, why = "KP", "asserts served content without a user acting"

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
                    "interaction_label": INTERACTION_LABEL[interaction],
                    "assertion_text": step.text,
                    "assertion_path": feat.path,
                    "assertion_line": step.line,
                    "assertion_commit": commit,
                    "span": span,
                    "instrument": instrument,
                    "established_by": why,
                    "sources_missing": list(missing),
                    "proposed_action": _proposed_action(interaction, clause, verdict),
                    "evidence_key": evidence_key,
                    "uses_browser": uses_browser,
                    "needs_browser": interaction in NEEDS_BROWSER,
                    "cheapest": "ui" if interaction in NEEDS_BROWSER else "api",
                    "why": why,
                    "stage": "rule",
                }
                claims.append(Claim(
                    subject_ref=ref,
                    statement=_statement(interaction, clause, verdict, instrument),
                    verdict=verdict,
                    confidence=0.8,
                    evidence=[Evidence(uri=uri_for_path(feat.path), line=step.line, note=step.text)],
                    detail=detail,
                ))
    return claims
