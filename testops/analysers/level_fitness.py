"""Level fitness v0.11 - one claim per assertion, in words a reader can act on.

v0.11 is TESTOPS-72: the product becomes evidence, and ``surfaces`` stops being a parameter nobody
reads.

  * a claim is ``repeats_product`` when **all** of these hold, and each is recorded on the claim in
    ``detail["product"]``: the claim needs a browser (``I3``/``I4``, the expensive instrument, and a
    browser actually ran, so the verdict would otherwise be ``distinct``); a product surface's route
    or claim shares a *meaningful* word with the assertion - not a word from the stop list of
    generic testing words, and not a word that appears in more than half of the product's surfaces,
    because a word that common is the noun the whole repository is about and not evidence; and the
    matched surface id, the matched route, the matched word and the surface's own claim travel with
    the verdict, so the page can show *why*. A verdict with no quotable evidence is not published;
  * the product is consulted, not assumed. A browser claim is only ever ``repeats_product`` when the
    product was read and a surface matched. When the product could not be read (no product
    repository, a reader that parses nothing it holds) the claim says so - ``not_assessable`` - and
    keeps its own verdict, the same distinction ``sources_missing`` already makes. A claim that does
    not need a browser records ``none``: the product is not evidence about it either way. Nothing is
    silent, and a product nobody read is never a zero;
  * a claim that needs a browser but ran without one (``gap``) is not ``repeats_product``: nothing
    was spent, so nothing is being repeated. The match is still recorded, because it tells a reader
    where the check belongs;
  * the statement and the action say what a reader can act on: the product already publishes this at
    a route, so a browser check re-verifies the developer's work rather than deciding anything the
    API does not; and the action names the API-level check while saying what a browser is still
    needed for (rendering, interaction), so nobody is told the UI test is worthless.

The precision guards are the point. v0.1's "a cheaper surface exists" was true for almost every
scenario in any product and scored precision 0.118; a shared word has to be specific to count, and
two of the four conditions exist only to refuse a match that is proximity rather than evidence.

v0.10.3 is TESTOPS-40: identical assertions carry their occurrence count in their identity.

  * two assertions with the same words in one scenario are told apart by where they occur, and the
    key now includes how many occurrences the scenario has (``interaction|words#n@total``). Delete
    one twin and the survivor used to keep the number it had, so a decision recorded against the
    first silently covered whichever assertion became first. With the count in the key, a scenario
    that gains or loses an identical assertion re-keys every one of them and the decision asks to be
    judged again instead of quietly moving to a different line. The key still holds no line and no
    commit, so reformatting and a new deploy leave decisions alone;
  * not one verdict moves. The identity is not the argument, and the corpus counts are pinned.

v0.10.2 is TESTOPS-29: the action states the change, the statement states the reason, once each.

  * TESTOPS-28 stopped the renderer cutting a stored action at its semicolon, which made the
    analyser's own redundancy visible: a review claim's action read "Rewrite this step to call the
    HTTP client instead of the browser. The response decides everything the browser is being used
    for." The second sentence is the *reason*, and the argument one line above already gives it
    ("the page the server sends settles it, ... so it pays for a browser that decides nothing
    extra"). A reason dressed as an instruction is worse than a missing one, because the reader
    acts on it. Every action here now states the change and stops; the reason was never the
    action's to carry, so nothing is deleted from the page - a corpus test asserts the reason is
    still in the statement and still reaches the reader through the argument (AC1-AC3). The
    repetition measure is the TESTOPS-28 review's own: a content word repeated between the two
    sentences of one action box, which was 2 of 94 and is now 0;
  * the duplicate-action wording lives in the duplication analyser and follows the same rule
    (AC4): its trailing restatement of the statement goes, "keep one" stays;
  * one action keeps a second clause: the distinct claim's "at the cheapest level that
    establishes it". That fact appears nowhere else on the page - the statement says the run
    settles the claim and never says this was the cheapest level that could - so deleting it would
    be the TESTOPS-27 leak again: information a reader had and can no longer see (AC2). It is
    folded into the instruction so the action states a disposition rather than a justification;
  * not one verdict moves. Rewording an action cannot move a verdict, and the corpus test pins the
    counts to prove it.

v0.10.1 is TESTOPS-18: two wording defects from the TESTOPS-12 review, and not one verdict moves.

  * an I1 claim checked through an HTTP response no longer says "that answer says what is stored".
    The response is evidence *about* the store, not the store: the sentence now takes the answer as
    the report of what is stored and stops where the answer stops speaking for it. The KP sentence
    says where its inference stops for the page, and the I2 sentence names the response as the
    thing asked about rather than borrowing the store's authority;
  * the multi-label pass note never quotes a label back at the reader. What each assertion asks is
    read from its interaction code; a row with a label and no code withholds the explanation
    instead of producing "one is about settled by the response the server sends".

v0.10 is TESTOPS-12: four readability defects, recorded by reviewers, and not one verdict moves.

  * one verification pass carries one label. The label answers "what settles it", so the suite
    answers it, not the assertion's subject: an api suite's store claim and response claim now both
    read "settled by the response the server sends". What the assertion is *about* moved into the
    statement ("The assertion is about the data as stored: ..."), which is where a reader can use
    it. Eleven scenarios used to show two or three wordings for one run answering one way; two
    still do, and each says why on the page (a claim naming nothing that could settle it, or one
    only a browser can work out);
  * restraint recognises a judgement by meaning, not by be-verb + adjective. "That number comes out
    right", "the report checks out" and "it verifies the count" are judgements with no comparison,
    and they now stay `unplaced` for the same reason "is correct" does;
  * a compound assertion is not unplaced by its meta half. "The stored hash is correct and the
    response returns 200" is placed by the half that says what settles it;
  * statements do not open "This test" on every claim and do not repeat their own subject inside one
    statement. The opener follows what the assertion is about, and the second sentence - the one
    that says what settles it - has its own subject.

Level fitness v0.9 - one claim per assertion, in words a reader can act on.

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
  repeats_product  a browser was spent on a claim the product already publishes at a route of its
            own, so the check re-verifies the developer's work (TESTOPS-72)
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
version = "0.11"
uses_model = False

# What this analyser's verdict rests on, and what it would like to check itself against but does
# not depend on. A source that cannot provide a needed capability makes every claim not_assessable;
# a source that only serves the consulted set is a blind spot the claim records and still stands.
# Adding a source never edits these - it changes the registry.
NEEDS = frozenset({sources.TEST_CODE, sources.CODE})
CONSULTS = frozenset({sources.REQUIREMENTS})

# What a decision recorded on one of this analyser's cases covers (TESTOPS-47). It states the
# *identity* the suppression key is built from - scenario, interaction, words, and the count of
# identical assertions in the scenario - and not a promise about edits: a net-zero twin edit (delete
# one identical assertion, add another) leaves the count unchanged, so the decision holds, and a
# sentence that said "adding or removing one asks you again" would be false. The last clause is
# the reverse case the store cannot prevent: once the twin is removed the lone key returns, and a
# decision recorded before the twin existed covers again. Stated, not solved - the cover is always
# over identical words in the same scenario, and preventing it would mean keying on something
# outside (scenario, interaction, words, count) - a run or edit identity - which is the re-ask on
# every deploy or reformat TESTOPS-40 deliberately removed.
COVER = ("A decision covers one assertion in one scenario: the same interaction, words, and count "
         "of identical assertions, in any commit and with any test data; removing an identical "
         "assertion can let an earlier decision cover again.")

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

# A claim that asserts a *meta* property - "that count is correct", "the report is accurate",
# "that number comes out right", "the report checks out" - judges something instead of saying what
# settles the judgement. The nouns such a claim leans on ("count", "report", "result", "store",
# "data") appear in almost any sentence, so no noun in it can place the claim. Only an explicit
# comparison makes it checkable, because a comparison is something a test can actually run. This is
# restraint, not coverage: a claim checked only in name is worse than an honest `unplaced`, because
# a reader trusts it.
#
# The judgement is recognised by what the words mean, not by one verb: "is correct" was the only
# shape TESTOPS-11 caught, and "that number comes out right" - a judgement with the same meaning and
# a different verb - walked straight past it (TESTOPS-12, AC3).
META_PROPERTY = re.compile(
    # A judgement adjective after any verb that ends in a verdict: is/comes out/turns out/stays.
    r"(?:\b(?:is|are|was|were|stays?|remains?|seems?|appears?|looks?|comes? out|turns? out|"
    r"ends? up|works? out)\b"
    r"\s+(?:not\s+|only\s+|still\s+|also\s+|all\s+|just\s+|quite\s+)?"
    r"(?:correct|accurate|right|wrong|as expected|as it should(?: be)?|in order)\b"
    # A judgement verb with no adjective at all: "the report checks out", "the check holds up".
    r"|\b(?:checks?|holds?|passes?)\s+(?:out|up)\b"
    # "it verifies the count" - the judgement is the verb, and the object is a generic noun that
    # appears in almost any sentence.
    r"|\b(?:verif(?:y|ies|ied)|validates?|validated|confirm(?:s|ed)?)\s+"
    r"(?:that\s+)?(?:the\s+|this\s+|its\s+|a\s+)?"
    r"(?:count|counts|number|numbers|total|report|reports|result|results|data|store|output|"
    r"summary|figure|figures)\b)",
    re.I)
COMPARISON = re.compile(r"\b(matches?|matched|matching|equals?|identical to|the same as|"
                        r"agrees? with|compares?|compared (with|against)|reconcil\w*|"
                        r"differs? from|as many as|consistent with)\b", re.I)

# A compound assertion can carry a checkable claim beside a meta one: "the stored hash is correct
# and the response returns 200". The meta half says nothing about what settles the claim, but it
# must not unplace the sibling that does say (TESTOPS-12, AC2). Split on the words that join two
# assertions, never on a comma alone - a list inside one assertion is not two assertions.
_CLAUSE_SPLIT = re.compile(r"\s+(?:and|but|while|yet)\s+|;\s*")

# The one reason an assertion stays unplaced after its instrument is known: the words made a
# judgement and never said what the judgement is against, so no instrument could settle it.
WHY_META = ("the words judge something correct or accurate and never say what it is compared "
            "with, so nothing could settle it")

NEEDS_BROWSER = {"I3", "I4"}

# ---------------------------------------------------------------- the product, as evidence (v0.11)
#
# TESTOPS-72. The question this tool exists to answer - "is the tester essentially repeating work
# the developer has already done?" - cannot be answered from the suite alone, so the product's own
# surfaces are read here. A surface is evidence when a word is shared between the assertion and the
# surface's route or its own claim; these two tables decide which words are allowed to count.
#
# A word in this list names the act of testing or the kind of thing, not the thing tested. "the
# data", "the result", "the page", "should", "correct", "displayed" appear in almost any assertion,
# and a match on one of them would be proximity dressed as evidence - the failure that scored v0.1 at
# precision 0.118. The UI and code vocabulary below earned its place the same way: on the CotW corpus
# "class" matched a docstring's ``:class:`` reference and "accessible" matched a test name in the
# product repository, and neither said the product publishes what the assertion checks.
PRODUCT_STOP = frozenset("""
a an the and or but if then than that this these those it its is are was were be been being
of to in on at by for with from as into over under about after before while yet so such
not no nor only just also very more most less least all any each every some both either
which who whom whose what when where why how
has have had do does did done can could may might must shall should will would
i you we they he she them his her their our your my me us
test tests testing check checks checked checking verify verifies verified verification
assert asserts asserted assertion expect expects expected actual result results
data value values content contents element elements button buttons field fields form forms
input label labels text displayed display displays visible shown show shows
render renders rendered rendering click clicks clicked type types typed enter enters
response request requests status code codes error errors
api http https json body header headers url route routes endpoint endpoints id ids
get post put delete patch head options
user users visitor visitors customer customers person people new old first last
same different correct accurate right wrong true false success successful
one two three four five six seven eight nine ten
class classes control controls interactive accessible accessibility position document
style styles css html markup attribute attributes name names named
expose exposes exposed provide provides return returns take takes give gives
use uses used make makes include includes contain contains hold holds allow allows
support supports line lines file files path paths module modules method methods
function functions call calls code source library package object objects item items
part parts thing things way ways case cases example examples step steps
""".split())

# A word that appears in more than this share of the product's surfaces is the noun the whole
# repository is about, not evidence about one route (AC3). Strictly more than half: with 25 surfaces
# a word in 13 of them is the product's subject, and a word in 12 is not. A product that declares a
# single surface can therefore never produce a repeat - every word in it is the whole product - and
# that is stated rather than worked around.
PRODUCT_COMMON_SHARE = 0.5

# The verbs a route's claim is written with. They are stop words - no match may rest on them - but
# they break a tie between two surfaces that share the assertion's noun, by preferring the surface
# whose own claim uses the assertion's verb ("get message" over "delete message" for a claim that
# says "will get ... message"). Without the tie-break the winner would be whichever id sorted first.
PRODUCT_CLAIM_VERBS = frozenset({"get", "list", "read", "create", "add", "update", "delete",
                                 "remove", "clear", "validate", "mark", "check"})

# What a target has to start with to be a route rather than a file path.
_ROUTE_VERBS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "ANY"})

_PRODUCT_WORD = re.compile(r"[a-z0-9]+")


def _product_words(text: str) -> list[str]:
    """The words of a phrase, lower-cased. Punctuation, quotes and path syntax are not words."""
    return _PRODUCT_WORD.findall((text or "").lower())


def _product_meaningful(text: str) -> set[str]:
    """The words of a phrase that could be evidence: not generic, not a one- or two-letter token."""
    return {word for word in _product_words(text)
            if len(word) >= 3 and word not in PRODUCT_STOP}


def _surface_field(surface, name: str, default):
    """One field of a surface, from an object or a plain record.

    The analyser never imports the surface reader: it is handed surfaces and reads their fields, so
    a caller can pass the reader's own objects, or plain dicts in a test, without this module
    depending on either.
    """
    if isinstance(surface, dict):
        return surface.get(name, default)
    return getattr(surface, name, default)


def _first_sentence(text: str, limit: int = 160) -> str:
    """The first sentence of a claim, cut to a quotable length.

    A surface's claim is quoted back to a reader as the evidence, so it has to be one thing the
    product says, not a docstring's whole list of public functions. The cut is marked, so a reader
    can see the quote stops rather than reading a truncated sentence as the product's whole claim.
    """
    text = " ".join(str(text or "").split())
    for stop in (". ", "; "):
        if stop in text:
            text = text.split(stop)[0]
            break
    text = text.rstrip(".")
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "\u2026"
    return text


def _claim_carrying(claims, word: str) -> str:
    """The surface's claim that carries the matched word, as one quotable sentence."""
    for claim in claims:
        if word in _product_words(str(claim)):
            return _first_sentence(claim)
    return _first_sentence(claims[0]) if claims else ""


def _surface_reading(surface) -> tuple[str, str, tuple, set[str], set[str], set[str]]:
    """(id, route, claims, route words, claim words, every word) for one surface.

    Only a target that *is* a route contributes route words. An engine surface's target is a file
    path, and a module's name is not an address the product publishes anything at: matching
    ``src/cotw/citation.py`` on the word "citation" would say the product exposes citations, when all
    it says is that a file is called that. Such a surface can still be evidence through its claims,
    which are its own words.
    """
    identifier = str(_surface_field(surface, "id", "") or "")
    route = str(_surface_field(surface, "target", "") or "")
    claims = tuple(str(claim) for claim in (_surface_field(surface, "claims", ()) or ()))
    words = _product_words(route)
    route_words = (set(words) if words and (route.startswith("/") or words[0].upper() in _ROUTE_VERBS)
                   else set())
    claim_words = set(_product_words(" ".join(claims)))
    return identifier, route, claims, route_words, claim_words, route_words | claim_words


def product_match(assertion: str, surfaces) -> dict | None:
    """The strongest surface the assertion's words share, or ``None`` when nothing matches.

    Deterministic and total: every candidate is scored and the lowest key wins, so the same assertion
    over the same surfaces always names the same route. The ranking, in order, prefers

      1. a word the surface's *route* carries over a word only its claim carries - the route names
         the thing, so a shared route word says the product publishes that thing at an address;
      2. the rarer word, because a word in 3 of 25 surfaces is more specific than one in 12;
      3. the surface sharing more of the assertion's meaningful words;
      4. the surface whose claim uses the assertion's own verb ("get message" for "will get ...
         message"), which separates a read from a delete that happens to name the same noun;
      5. the surface id, so the choice is stable when everything else ties.

    Two guards refuse a candidate outright: a stop word is never evidence, and a word carried by more
    than :data:`PRODUCT_COMMON_SHARE` of the surfaces is the product's subject rather than this
    surface's. A word must appear literally - "created" does not match "create" - because the matched
    word is quoted back to a reader as the evidence, and a stem nobody wrote is not quotable.
    """
    assertion_words = _product_meaningful(assertion)
    readings = [_surface_reading(surface) for surface in surfaces or ()]
    if not assertion_words or not readings:
        return None
    total = len(readings)
    frequency: dict[str, int] = {}
    for _identifier, _route, _claims, _route_words, _claim_words, doc_words in readings:
        for word in doc_words:
            frequency[word] = frequency.get(word, 0) + 1
    assertion_verbs = set(_product_words(assertion)) & PRODUCT_CLAIM_VERBS

    best = None
    for identifier, route, claims, route_words, claim_words, doc_words in readings:
        shared = assertion_words & doc_words
        if not shared:
            continue
        agrees = bool(assertion_verbs & claim_words)
        for word in sorted(shared):
            if word in PRODUCT_STOP:
                continue
            if frequency[word] > PRODUCT_COMMON_SHARE * total:
                continue
            key = (0 if word in route_words else 1, frequency[word], -len(shared),
                   0 if agrees else 1, identifier, word)
            if best is None or key < best[0]:
                best = (key, identifier, route, _claim_carrying(claims, word), word,
                        frequency[word], total)
    if best is None:
        return None
    _key, identifier, route, claim_text, word, shared_with, total = best
    return {"surface": identifier, "route": route, "claim": claim_text, "word": word,
            "shared_with": shared_with, "surfaces": total}


# The four states a claim's product record can be in. They never share wording, and none of them is
# a default: ``found`` (a surface matched), ``zero`` (the product was read and offered no match),
# ``not_assessable`` (the product could not be consulted, with the reason attached) and ``none``
# (the product is not evidence about this claim - it does not need a browser, or nothing placed it,
# or the run recorded no product reading at all).
PRODUCT_FOUND = "found"
PRODUCT_ZERO = "zero"
PRODUCT_NOT_ASSESSABLE = "not_assessable"
PRODUCT_NONE = "none"


def _product_record(interaction: str, assertion: str, surfaces, state: str, reason: str, *,
                    placed: bool = True) -> dict:
    """What the product said about one claim, as a record the claim and the page carry (AC1).

    Every claim gets one, so no verdict can be read as if the product had been silent when it was
    consulted, or as if it had said zero when nobody could read it. ``state`` is the caller's record
    of the product arm (``found``/``zero``/``not_assessable``, or ``""`` for a caller that recorded
    nothing) - the analyser never reads a product itself.
    """
    surfaces = list(surfaces or ())
    record = {"state": PRODUCT_NONE, "needs_browser": interaction in NEEDS_BROWSER,
              "surfaces": len(surfaces), "surface": None, "route": None, "claim": None,
              "word": None, "shared_with": 0, "reason": ""}
    if not placed or interaction == "U":
        record["reason"] = ("nothing placed this claim, so nothing is known about what would settle "
                            "it and the product is not evidence about it")
        return record
    if interaction not in NEEDS_BROWSER:
        record["reason"] = ("this claim does not need a browser, so the product is not evidence "
                            "about it")
        return record
    if state == PRODUCT_NOT_ASSESSABLE:
        record["state"] = PRODUCT_NOT_ASSESSABLE
        record["reason"] = (f"the product could not be consulted: {reason}" if reason
                            else "the product could not be consulted")
        return record
    if not state:
        record["reason"] = ("this run recorded no product reading, so nothing here says whether "
                            "the product already exposes this")
        return record
    if state != PRODUCT_FOUND or not surfaces:
        record["state"] = PRODUCT_ZERO
        record["reason"] = (f"the product was read and declares {len(surfaces)} surfaces, none of "
                            f"which shares a meaningful word with this assertion"
                            if surfaces else
                            "the product was read and declares no surface at all")
        return record
    match = product_match(assertion, surfaces)
    if match is None:
        record["state"] = PRODUCT_ZERO
        record["reason"] = (f"the product was read and declares {len(surfaces)} surfaces, and none "
                            f"of them shares a meaningful word with this assertion")
        return record
    record.update(match)
    record["state"] = PRODUCT_FOUND
    record["reason"] = (f'the product declares {match["route"]}, whose own claim is '
                        f'"{match["claim"]}", and it shares the word "{match["word"]}" with the '
                        f'assertion - a word that appears in {match["shared_with"]} of the '
                        f'product\'s {len(surfaces)} surfaces')
    return record


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


# What the assertion is about, keyed by interaction. This is the statement's opening, and it is
# what varies between claims: "This test asserts that ..." on all ninety-four opened every claim
# with the same four words, and the subject then repeated inside the same statement ("This test ...
# This test ..."), which reads as a stutter rather than a sentence (TESTOPS-12, AC4). The opener
# says what the assertion is about; the second sentence says what settles it, which is the label's
# question and never the opener's.
_OPENER = {
    "I1": "The assertion is about the data as stored",
    "I2": "The assertion is about the response itself",
    "KP": "The assertion is about the page as served",
    "I3": "The assertion is about what a person sees",
    "I4": "The assertion is about what only a browser works out",
}


def _opening(interaction: str, clause: str) -> str:
    """The statement's first sentence: what is asserted, without a repeated subject.

    A step may continue the sentence before it ("And says the approval no longer covers the text"),
    so it can arrive with no subject of its own. It is quoted as the step's words rather than
    forced into "the assertion is about ...: says ...", which is not English.
    """
    if _SUBJECTLESS.match(clause):
        return f'The step reads "{clause}"'
    return f"{_OPENER.get(interaction, 'The assertion')}: {clause}"


def _repeats_opening(interaction: str, clause: str) -> str:
    """The statement's first sentence for a claim the product already publishes.

    A browser claim's usual opener says what only a browser can work out, and a statement that then
    says the API already publishes it would contradict its own first sentence. The subject is the
    same - what a person is shown - and the second sentence carries the finding.
    """
    if _SUBJECTLESS.match(clause):
        return f'The step reads "{clause}"'
    label = {
        "I3": "The assertion is about what a person sees while acting",
        "I4": "The assertion is about what a browser puts in front of a person",
    }.get(interaction)
    if label is None:
        return _opening(interaction, clause)
    return f"{label}: {clause}"


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
    if _meta_without_comparison(text):
        # A compound sentence can carry a checkable claim beside the meta half. The meta half
        # cannot place anything, but it must not unplace a sibling that can be placed (AC2): the
        # claim a reader is asked to trust is the checkable one, and "I cannot place half of this"
        # is not "nothing here is placeable".
        siblings = [part.strip() for part in _CLAUSE_SPLIT.split(text)
                    if part.strip() and not _meta_without_comparison(part)]
        placed = _place(" and ".join(siblings)) if siblings else []
        if placed:
            return [(code, f"the sentence also judges something correct without saying what it is "
                           f"compared with, so that half places nothing; {why}")
                    for code, why in placed]
        return [("U", WHY_META)]
    return _place(text)


def _place(text: str) -> list[tuple[str, str]]:
    """Where an assertion that has already passed restraint belongs, from its own words."""
    out: list[tuple[str, str]] = []
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

    The label answers one question - what settles it - and the suite gives one answer, so a
    verification pass that runs one suite carries one label (TESTOPS-12, AC1). What the assertion
    is *about* (the stored data, the response, the page) is the statement's job, not the label's:
    TESTOPS-11 gave an api suite's store claim a different label from its response claim, and a
    reader then met two or three wordings for one run answering one way. The distinction was real;
    it belonged in the statement, which now names both what the assertion is about and what
    settles it.

    A suite with no server behind it (engine, storage) gives its own answer, because telling a
    reader that "the response the server sends" settles a claim in a suite with no server is a
    contradiction. In a browser suite the interaction still decides: a claim the page as served
    settles is the finding (`review`), and a claim only a browser can work out needs one.
    """
    if interaction in NEEDS_BROWSER or interaction == "U":
        return INTERACTION_LABEL[interaction]
    if instrument == "engine":
        return "settled by the engine's own answer about the stored data"
    if instrument == "storage":
        return "settled by the data as stored"
    if instrument == "controller":
        return "settled by the answer the application returns"
    if instrument in ("ui", "unknown"):
        return INTERACTION_LABEL[interaction]
    # api: every answer this suite can give arrives in the response the server sends.
    return INTERACTION_LABEL["I2"]


def _settles(interaction: str) -> str:
    """What settles a claim at this interaction, as the subject of a sentence."""
    phrase = _SETTLED_BY.get(interaction, INTERACTION_LABEL.get(interaction, "something settles that"))
    return phrase[0].upper() + phrase[1:]


def _second(interaction: str, instrument: str) -> str:
    """The sentence after the opening: what settles it, as the run actually reads it.

    Built from the same table as the label, so the two cannot name different instruments. Where an
    api suite settles a claim about stored data, the sentence says how the answer arrives rather
    than leaving a reader to wonder how a store can be read without opening it.

    It also says where the inference stops. An HTTP response is evidence *about* the store, never
    the store itself: a handler can return cached state or a value it computed without touching the
    disk, so "that answer says what is stored" granted the response authority it does not have
    (TESTOPS-18, AC3). The sentence names the inference - the answer is *taken as* the report of
    what is stored, and the check reaches only as far as that answer speaks for the store. The
    same discipline applies to the page the response carries (KP) and to the response claim (I2),
    which may say the response is the thing asked about but may not borrow the store's authority.
    """
    if interaction == "I1" and instrument in ("api", "controller"):
        return (f"The run {_reads(instrument)}, and takes that answer as the report of what is "
                f"stored, so the assertion is checked as far as that answer speaks for the store.")
    if interaction == "KP" and instrument in ("api", "controller"):
        return (f"The run {_reads(instrument)}, and takes that answer as the page the server "
                f"sends, so the assertion is checked as far as that answer speaks for the page.")
    if interaction == "I2" and instrument in ("api", "controller"):
        return (f"The run {_reads(instrument)}, which is exactly the answer the assertion asks "
                f"about, so the assertion is checked.")
    if instrument == "engine":
        return (f"The run {_reads(instrument)}, whose own answer about the stored data settles it, "
                f"so the assertion is checked.")
    return f"The run {_reads(instrument)}, which settles it, so the assertion is checked."


def _statement(interaction: str, clause: str, verdict: str, instrument: str,
               why: str = "", product: dict | None = None) -> str:
    """What is asserted, what establishing it needs, and what the test actually did."""
    if verdict == "repeats_product":
        route = (product or {}).get("route") or "a route"
        claim = (product or {}).get("claim") or ""
        own = f', and its own claim for that route is "{claim}"' if claim else ""
        return (f"{_repeats_opening(interaction, clause)}. The product already publishes this at "
                f"{route}{own}, so a browser check here re-verifies the developer's work rather "
                f"than deciding anything the API has not already said.")
    opening = _opening(interaction, clause)
    if verdict == "gap":
        return (f"{opening}. Nothing short of a browser can decide it, and the run "
                f"{_reads(instrument)} instead, so nothing checks it.")
    if verdict == "review":
        return (f"{opening}. {_settles(interaction)} settles it, yet the run drives a browser, so it "
                f"pays for a browser that decides nothing extra.")
    if verdict == "unplaced":
        if why == WHY_META:
            return (f'The step reads "{clause}". Those words judge something right without saying '
                    f"what it is compared with, so nothing can be said about whether it is checked.")
        if interaction == "U":
            return (f'The step reads "{clause}". Its words name no data, response, page or anything '
                    f"a person sees, so nothing can be said about whether it is checked.")
        return (f"{opening}. None of its steps could be tied to a layer of the system, so nothing "
                f"can be said about whether it is checked.")
    # distinct
    if interaction in NEEDS_BROWSER:
        return (f"{opening}. The run drives a browser, which is what decides it, so the assertion "
                f"is checked.")
    return f"{opening}. {_second(interaction, instrument)}"


def _proposed_action(interaction: str, clause: str, verdict: str, why: str = "",
                     product: dict | None = None) -> str:
    """What to change, and never why. This is the field a case reviewer acts on (TESTOPS-29).

    The action is not a summary of the case: the statement above it is. A second sentence giving
    the reason duplicates the argument in the reader's own scan line, and - worse - presents a
    reason as an instruction, so a reader who acts on the plan takes the justification with it.
    Where a reason used to trail an action here, the statement already said it; where it did not,
    the fact is folded into the instruction (the distinct claim's level) rather than dropped.

    One instruction, one or two sentences, no restatement of the statement (AC1).
    """
    if verdict == "repeats_product":
        # The one action here whose second sentence is a scope, not a reason: the ticket requires
        # that a reader is not told the UI test is worthless, and a browser is still the only
        # instrument that shows a result is rendered and can be acted on. It shares no content word
        # with the first sentence, so the box does not restate itself (TESTOPS-29's measure).
        route = (product or {}).get("route") or "that route"
        return (f"Assert this at the API: call {route} and check the response, rather than reading "
                f"it through a UI run. A browser is still needed for what only a person sees - that "
                f"the result is rendered, and that someone can act on it.")
    if verdict == "gap":
        return f'Move the step "{clause}" into a test that drives a browser, or delete it.'
    if verdict == "review":
        return f'Rewrite the step "{clause}" to call the HTTP client instead of the browser.'
    if verdict == "unplaced":
        if why == WHY_META:
            return (f'Rewrite the step "{clause}" to say what it is compared with - the value, the '
                    f"row or the report it should agree with - then re-run.")
        if interaction == "U":
            return (f'Rewrite the step "{clause}" to say whether it is about the data, the response, '
                    f"the page, or what a person sees, then re-run.")
        return (f'Bind the step "{clause}" to a step definition whose driver can be identified, '
                f"then re-run.")
    # A distinct claim's one extra fact: this level is the cheapest that establishes the assertion,
    # and nothing else on the page says so. It is stated as the disposition ("keep it at the
    # cheapest level") rather than as a reason for it, because an action that reads "keep it,
    # because ..." leaves a reader holding an argument where they asked for a plan.
    return f'No change: keep the step "{clause}" at the cheapest level that establishes it.'


def _unbound_statement(unbound: dict) -> str:
    """A step nothing binds, in the ecosystem's own words (TESTOPS-42C-3, AC2).

    It names the step text and the patterns that came closest, so a reader can see that the suite
    drifted from its own bindings rather than being told the tool could not see the test.
    """
    nearly = [f'"{pattern}"' for pattern in unbound.get("nearly") or ()]
    nearest = ""
    if len(nearly) == 2:
        nearest = f" The two nearest patterns are {nearly[0]} and {nearly[1]}."
    elif nearly:
        nearest = f" The nearest pattern is {nearly[0]}."
    return (f'The step reads "{unbound.get("step", "")}", but no binding matches these words.'
            f"{nearest}")


def _unbound_reason_text(unbound: dict) -> str:
    nearly = ", ".join(f'"{pattern}"' for pattern in unbound.get("nearly") or ())
    return ("no binding matches these words" + (f"; the nearest declared patterns are {nearly}"
                                                if nearly else ""))


def _unbound_action(unbound: dict) -> str:
    nearly = [f'"{pattern}"' for pattern in unbound.get("nearly") or ()]
    if len(nearly) == 2:
        return (f"Rewrite the step so it matches {nearly[0]} or {nearly[1]}, or add a step "
                f"definition for these words, then re-run.")
    return "Rewrite the step so it matches a declared pattern, or add a step definition for these words, then re-run."


def _binding_provenance(binding) -> dict:
    """The binding a layer came from, and the commands/helpers on its chain (AC4).

    ``path:line`` lets a reader open the step definition. ``via`` is the chain that reached the
    signal; ``commands`` names every custom command on it with the command's own ``path:line`` and
    the tokens its body reached, so a claim can be walked to ``cy.request`` in the command file.
    """
    return {
        "path": binding.path,
        "line": binding.line,
        "verb": binding.verb,
        "pattern": binding.pattern,
        "layer": binding.layer,
        "suite": binding.suite,
        "via": list(binding.layer_via),
        "commands": [{"name": name, "path": path, "line": line, "via": list(via)}
                     for name, path, line, via in getattr(binding, "layer_commands", ())],
    }


def analyse(features, bindings, surfaces, uri_for_path, budget: dict | None = None, *,
            sources_missing=None, assessment=None, commit: str = "",
            support_index: dict[tuple[str, str, str], int] | None = None,
            extractor: str = "", unmatched=None, product_state: str = "",
            product_reason: str = "") -> list[Claim]:
    """One claim per asserting step, in deterministic order.

    ``sources_missing`` is the caller's record of which sources were never connected, and *whether*
    the caller looked at all. ``None`` - the default - means no registry was consulted for this claim,
    and the claim records that: not assessed. A list, including an empty one, means the registry was
    consulted and this is what it said; ``[]`` is "assessed, nothing was missing", never "not
    recorded". The default must not be the clean bill, because a caller that forgets the argument
    would otherwise write a guarantee nobody produced.

    ``assessment`` is the registry's verdict for the capabilities this analyser needs (see
    :data:`NEEDS`). It is copied onto every claim as a plain record, with the reason attached when a
    source nobody could consult is involved. ``None`` means the caller did not record an assessment,
    and it travels with ``sources_missing=None``: an assessment without a list, or a list without
    one, would be half a record.

    ``support_index`` maps a binding's ``(path, verb, pattern)`` to the id of the observation row the
    caller recorded for it. It is how a claim learns *which rows* back it without this module ever
    touching the store. When it is omitted - or holds no row for a binding - the claim's support is
    an explicit empty list: nothing was recorded, which is the truth, not zero evidence.

    ``extractor`` and ``unmatched`` are the ecosystem seam (TESTOPS-42C-3). When a caller names the
    extractor, every claim records the binding its layer came from - path, line, layer and the
    commands/helpers the chain passed through - and the scenario's background steps join the span,
    because a scenario does run its background. ``unmatched`` is the ecosystem's own explanation of
    a step it could not bind: when it is supplied, an asserting step with no binding of its own is
    **unplaced for that reason**, never rescued by a sibling step's layer. The .NET path supplies
    neither, so its claims are exactly what they were.

    ``surfaces`` are the product's own routes and claims, and ``product_state``/``product_reason``
    are the caller's record of whether the product could be read at all (TESTOPS-72). Together they
    decide whether a browser claim is ``repeats_product``; every claim records the answer in
    ``detail["product"]``, including the claims the product is not evidence about. ``product_state``
    defaults to ``""`` - "this run recorded no product reading" - and never to ``found``, because a
    caller that forgets the argument would otherwise let every claim be judged against a product
    nobody read.
    """
    assessed = sources_missing is not None
    missing = list(sources_missing) if assessed else None
    assessment_record = None if assessment is None else assessment.record()
    index = support_index or {}
    claims: list[Claim] = []

    for feat in features:
        # The background belongs to every scenario in the file, and a scenario executes it. It is
        # only read into the span on the ecosystem path, so the .NET counts cannot move (AC7).
        background: list = []
        if extractor:
            for block in getattr(feat, "backgrounds", ()) or ():
                for step in block.steps:
                    bound = stepbindings.match_step(bindings, step.text,
                                                    stepbindings.suite_of(feat.path))
                    if bound is not None:
                        background.append(bound)
        for sc in feat.scenarios:
            if not sc.steps:
                continue
            suite = stepbindings.suite_of(feat.path)
            matched = [b for step in sc.steps if (b := stepbindings.match_step(bindings, step.text, suite))]
            matched = matched + background
            steps = asserting_steps(sc.steps)
            assert_binding = {step.line: stepbindings.match_step(bindings, step.text, suite)
                              for step in steps}
            span = sorted({b.layer for b in matched})
            instrument = stepbindings.highest([b.layer for b in matched]) if matched else "unknown"
            uses_browser = "ui" in span
            ref = f"scenario:{feat.path}#{sc.name}"

            # Occurrence identity (TESTOPS-40). Two assertions with the same words in one scenario
            # are told apart by where they occur, which makes the count part of the identity: if a
            # scenario gains or loses an identical assertion, every occurrence in it is re-keyed and
            # a decision recorded against one of them asks to be judged again. Without the count a
            # decision on the first of two identical assertions silently covered whichever assertion
            # happened to become first when the other was deleted.
            classified = []
            for step in steps:
                binding = assert_binding.get(step.line)
                # A step with no binding of its own is not placed by a sibling's layer when the
                # ecosystem says placement is per step: the reason is the ecosystem's, and the
                # claim is unplaced (AC2). Without the seam this is exactly the old behaviour.
                unbound = (unmatched(step.text, bindings, suite)
                           if unmatched is not None and binding is None else None)
                own_layer = binding.layer if binding is not None else "unknown"
                interaction, why = classify_with_instrument(
                    step.text, own_layer, sc.name, uses_browser=uses_browser)
                if unbound is not None:
                    # Nothing binds this step, so nothing can be said about the instrument the
                    # claim needs: the code is the honest "unclear", and the reason is the
                    # ecosystem's own sentence naming the nearest patterns.
                    interaction, why = "U", unbound["reason"]
                classified.append((step, binding, interaction, why, unbound,
                                   f"{interaction}|{normalise(step.text)}"))
            occurrences: dict[str, int] = {}
            for entry in classified:
                occurrences[entry[5]] = occurrences.get(entry[5], 0) + 1
            seen: dict[str, int] = {}

            for step, binding, interaction, why, unbound, base_key in classified:
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

                clause = _clause(step.text)
                # What the product says about this claim (TESTOPS-72). Read for every claim, so a
                # claim nobody could judge against the product says which of the four states it is
                # in rather than falling silent - and a claim that does not need a browser says so,
                # instead of borrowing a zero it never looked for.
                product = _product_record(interaction, step.text, surfaces, product_state,
                                          product_reason, placed=unbound is None)
                if unbound is not None:
                    # The ecosystem's own account of why nothing placed this step. The claim is
                    # unplaced for that reason, whoever else was bound in the scenario.
                    verdict = "unplaced"
                elif instrument == "unknown" or interaction == "U":
                    verdict = "unplaced"
                elif interaction in NEEDS_BROWSER and not uses_browser:
                    verdict = "gap"
                elif interaction in NEEDS_BROWSER:
                    # A browser claim the run actually paid for. When the product declares a route
                    # for it, the browser is re-verifying the developer's work rather than deciding
                    # anything (AC1); when it does not, the claim stays `distinct`.
                    verdict = "distinct"
                    if product["state"] == PRODUCT_FOUND:
                        verdict = "repeats_product"
                        # The rule that decided it, in the reader's words, beside the rule that
                        # placed the claim: the evidence is the product's, so it is named here too.
                        why = f"{why}, and {product['reason']}"
                elif uses_browser:
                    verdict = "review"
                else:
                    verdict = "distinct"

                # Identity of the assertion for suppression: the interaction and the assertion's own
                # words, never its line, so reformatting the file does not resurrect a judged case.
                # The occurrence count joins the key only when the words repeat in the scenario, so
                # a scenario that gains or loses a twin re-keys its occurrences and the decision
                # asks again instead of silently covering a different one (TESTOPS-40).
                total = occurrences[base_key]
                seen[base_key] = seen.get(base_key, 0) + 1
                evidence_key = (base_key if total == 1
                                else f"{base_key}#{seen[base_key]}@{total}")

                detail = {
                    "claim": interaction,
                    "interaction_code": interaction,
                    "interaction_label": _label(interaction, "unknown" if unbound is not None
                                                else instrument),
                    "assertion_text": step.text,
                    "assertion_path": feat.path,
                    "assertion_line": step.line,
                    "assertion_commit": commit,
                    "span": span,
                    "instrument": "unknown" if unbound is not None else instrument,
                    "placed": unbound is None,
                    "established_by": (_unbound_reason_text(unbound) if unbound is not None else why),
                    "sources_assessed": assessed,
                    "sources_missing": list(missing) if assessed else None,
                    "assessment": assessment_record,
                    # What the product said about this claim, always - found, zero, not_assessable
                    # or none, with the matched surface, route and word when there was a match
                    # (TESTOPS-72, AC1). A claim nobody could judge against the product says why.
                    "product": product,
                    "proposed_action": (_unbound_action(unbound) if unbound is not None
                                        else _proposed_action(interaction, clause, verdict, why,
                                                              product)),
                    "support": support,
                    "evidence_key": evidence_key,
                    "uses_browser": uses_browser,
                    "needs_browser": interaction in NEEDS_BROWSER,
                    "cheapest": "ui" if interaction in NEEDS_BROWSER else "api",
                    "why": why,
                    "stage": "rule",
                }
                if unbound is not None:
                    detail["unbound"] = unbound
                if extractor:
                    # What placed this claim, and where to go to check it (AC4): the extractor's
                    # name, the binding's own path:line, the chain it followed, and for every
                    # custom command on that chain the command's path:line so a reader can walk
                    # from the claim to the command's body and the cy.* call in it. The scenario's
                    # other matched bindings - the background included - travel too: the verdict is
                    # a fact about the whole scenario, and the background is where an API command
                    # such as createRoomViaApi (and its cy.request) usually sits.
                    scenario_bindings: list[dict] = []
                    seen_bindings: set[tuple[str, str, str]] = set()
                    for bound in matched:
                        key = (bound.path, bound.verb, bound.pattern)
                        if key in seen_bindings:
                            continue
                        seen_bindings.add(key)
                        scenario_bindings.append(_binding_provenance(bound))
                    detail["provenance"] = {
                        "extractor": extractor,
                        "binding": (_binding_provenance(binding) if binding is not None else None),
                        "scenario_bindings": scenario_bindings,
                    }
                claims.append(Claim(
                    subject_ref=ref,
                    statement=(_unbound_statement(unbound) if unbound is not None else
                               _statement(interaction, clause, verdict, instrument, why, product)),
                    verdict=verdict,
                    confidence=0.8,
                    evidence=[Evidence(uri=uri_for_path(feat.path), line=step.line, note=step.text)],
                    detail=detail,
                ))
    return claims
