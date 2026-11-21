"""Level fitness v0.5 - span, not level.

Harry's correction (2026-11-21) killed the wide/narrow binary:

  "It is both wide and narrow, depending on your perspective. It is wider than the api<->datastore interaction,
   as it will exercise this interaction as well as the web server layer. But it is also narrower than a full
   browser test. The same test could be run with a browser, but we're running it at the HTML-only level because
   we don't NEED a browser, so it's better to run that test without the extra complexity and resource use."

So a test is not at a level; it has a SPAN - the set of interactions it drags in on the way to its assertion -
and a CLAIM - the single interaction the assertion belongs to. Spanning extra layers on the way to the assertion
is not itself waste: reaching the store through the server is how a real system behaves, and HTML-only is the
minimum-cost instrument that covers that span.

The one thing that IS waste is paying for a browser when the claim is decidable without one. That is the whole
of the review rule, and it is why the browser - not the layer count - is what we measure.

Verdicts:
  distinct  the instrument is adequate for the claim and no browser was bought unnecessarily
  review    a browser was used for a claim that the response body settles
  gap       the claim needs a browser and no browser ran - the claim is not established at all
  unplaced  the claim or the instrument cannot be identified
"""
from __future__ import annotations

import re

from ..extract import stepbindings
from .base import Claim, Evidence

name = "level_fitness"
version = "0.5.0"
uses_model = False

BEHAVIOUR = re.compile(r"\b(click(s|ed)?|submit(s|ted)?|type(s|d)?|fills?|enters?|press(es)?|selects?|"
                       r"navigates?|visits?|opens? the page|interacts?|drags?|hovers?)\b", re.I)
PRESENTATION = re.compile(r"\b(render(s|ed)?|page|displayed (to|on)|visible|shown to|shows? (the|a) |markup|"
                          r"element|heading|layout|screen|html)\b", re.I)
ACCESSIBILITY = re.compile(r"\b(accessible name|accessible citation|aria|label(?!led)|button text|"
                           r"screen reader|accessibility tree|css class|document order)\b", re.I)
MARKUP = re.compile(r"\b(anchor(s|ed)?|data-[a-z-]+|attribute|element carrying|markup|server-rendered|"
                    r"html source|response body)\b", re.I)
CONTENT = re.compile(r"\b(lists?|every sheet|each fact|value|citation|subject|kind|fact count|book count|"
                     r"the data|contents?|rows?|columns?|paragraph)\b", re.I)
HTTP = re.compile(r"\b(status|404|400|422|500|json|http|header|content-type|response|endpoint|route|"
                  r"api|returns? (a|an|the)? ?(json|list|object|error|null))\b", re.I)
STORE = re.compile(r"\b(bytes?|byte-identical|persist(s|ed)?|stored|database|datastore|canon|hash|file|"
                   r"admits?|admitted|excludes?|excluded|commits?|transaction)\b", re.I)


def classify_claims(text: str) -> list[tuple[str, str]]:
    """Return one or more (interaction, why) pairs.

    A scenario can assert two independent things at once - "server-rendered with stable fact anchors AND every
    citation accessible" is a markup claim and an accessibility claim, and they need different instruments.
    Harry's ruling (B): split them. One claim per distinguishable assertion.
    """
    out = []
    markup, access = bool(MARKUP.search(text)), bool(ACCESSIBILITY.search(text))
    if markup:
        out.append(("KP", "asserts the page-as-served, which the response body settles"))
    if access:
        out.append(("I4", "asserts an accessibility property the browser computes"))
    if out:
        # A markup or accessibility signal is decisive: it names the instrument the claim needs.
        return out
    if STORE.search(text):
        return [("I1", "asserts a datastore guarantee")]
    if HTTP.search(text) and not PRESENTATION.search(text):
        return [("I2", "asserts an HTTP contract")]
    if not out and PRESENTATION.search(text) and BEHAVIOUR.search(text):
        return [("I4", "asserts what a person sees while acting")]
    if not out and CONTENT.search(text):
        return [("I3", "asserts data reaching the presentation")]
    return out or [("U", "not identifiable")]


NEEDS_BROWSER = {"I3", "I4"}


def analyse(features, bindings, surfaces, uri_for_path, budget: dict | None = None) -> list[Claim]:
    claims: list[Claim] = []
    for feat in features:
        for sc in feat.scenarios:
            if not sc.steps:
                continue
            suite = stepbindings.suite_of(feat.path)
            matched = [b for step in sc.steps if (b := stepbindings.match_step(bindings, step.text, suite))]
            span = sorted({b.layer for b in matched})
            uses_browser = "ui" in span
            instrument = stepbindings.highest([b.layer for b in matched]) if matched else "unknown"
            ref = f"scenario:{feat.path}#{sc.name}"
            evidence = [Evidence(uri=uri_for_path(feat.path), line=sc.line, note=sc.name)]
            text = sc.name + " " + " ".join(s.text for s in sc.steps)

            for interaction, why in classify_claims(text):
                # Without a user acting there is no user-to-datastore claim: what the suite establishes is the
                # served content. Harry's model reserves I3 for a person using the product.
                if interaction == "I3" and not uses_browser:
                    interaction, why = "KP", "asserts served content without a user acting"
                detail = {"claim": interaction, "span": span, "instrument": instrument,
                          "uses_browser": uses_browser, "needs_browser": interaction in NEEDS_BROWSER,
                          "cheapest": "ui" if interaction in NEEDS_BROWSER else "api",
                          "why": why, "stage": "rule"}
                if instrument == "unknown":
                    verdict, statement = "unplaced", "instrument not identifiable from the step bindings"
                elif interaction == "U":
                    verdict, statement = "unplaced", "claim not identifiable"
                elif interaction in NEEDS_BROWSER and not uses_browser:
                    verdict = "gap"
                    statement = (f"{interaction} claim needs a browser to be established; the suite asserts it "
                                 f"over {'/'.join(span) or 'nothing'}, so the claim is not actually established")
                elif interaction in NEEDS_BROWSER:
                    verdict, statement = "distinct", f"{interaction} claim, browser present - {why}"
                elif uses_browser:
                    verdict = "review"
                    statement = (f"{interaction} claim decided by the response body, but a browser is used - "
                                 f"{why}. Running it HTML-only would establish the same claim without the browser")
                else:
                    verdict, statement = "distinct", (
                        f"{interaction} claim established at the {'/'.join(span) or instrument} boundary - {why}")
                claims.append(Claim(subject_ref=ref, statement=statement, verdict=verdict,
                                    confidence=0.8, evidence=evidence, detail=detail))
    return claims
