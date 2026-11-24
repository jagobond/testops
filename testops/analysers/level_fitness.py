"""Level fitness v0.16 - one claim per assertion, in words a reader can act on.

v0.16 is TESTOPS-85: refusing costs too. v0.15 refused in four places it should have assessed.

  * **a compound domain noun is an entity, not a caption.** ``a "room" booking exists`` was refused
    as copy because the quoted word sat in front of a product noun. When the quoted word is itself
    a word the product carries and an existence or intent verb governs the noun phrase, the pair is
    a compound entity and the head noun is the subject (``booking``). A caption in front of a
    product noun (``a "Welcome" message``) has a quoted word the product does not carry, and stays
    copy;
  * **the copy refusal is word-aware.** A quoted caption suppresses the words inside it and the
    noun it modifies, per occurrence. A word that also occurs unquoted is named there, and the
    quoted run cannot hide it: ``the "booking" booking`` is assessed on the unquoted ``booking``;
  * **a refusal names the copy it refuses.** The stored reason interpolated a field that is only
    populated for display copy, so every ``quoted_copy`` record read ``quotes display copy ""`` -
    the TESTOPS-78 empty-reason fault recurring. The record now carries the caption that hides the
    word and the reason quotes it;
  * **the passive is declared, not misread.** ``a "room" gets booked`` was recorded as a read
    because ``gets`` is spelled like the method, and it agreed with ``GET /room``. A passive
    auxiliary that is also an intent form is no longer the sentence's act; when the participle
    names no act the intent table knows, the record says in words that a passive claim was not
    assessed and why (``near_miss_kind: "passive_voice"``). ``a "room" gets created`` still reads
    create/POST.

v0.15 is TESTOPS-82's review response: the second mark is read in both directions.

  * **the rule reads after the run as well as before.** v0.14 only looked in front of the quotes and
    only at a closed verb list, so a caption walked through as the subject whenever the sentence
    carried an intent verb elsewhere - ``a "Welcome" message is created`` accused ``POST /message``
    and ``the response contains "Booking" once it is created`` accused ``POST /booking``. A quoted
    word followed by a noun the product itself names (``a "Welcome" MESSAGE``, the banner case
    ``"Booking Successful" BANNER``) modifies that noun: it is copy or a value, never the subject.
    An intent or existence verb immediately after the quotes (``a "booking" is created``, ``the
    "booking" exists``, ``the "booking" is shown``) says the quotes named the subject, so the gate
    passes in both directions;
  * **punctuation inside a one-word run is the banner mark it is.** ``"Saved."``, ``"Booking."``,
    ``"Booking,"``, ``"Booking)"``, ``"Booking..."`` are captions - text a person reads - and were
    previously accepted as entities;
  * **two quoted runs: the sentence's subject is named, not the rarest word.** ``the "booking" is
    shown in the "message" panel`` used to record a repeat on ``GET /message`` because ``message``
    was rarer. The record now names the run an intent or existence verb governs, or the first run
    when none does, and where the sentence genuinely names both (a compound subject, a run either
    side of the verb, two clauses with their own verbs) it names both and refuses
    (``near_miss_kind: "ambiguous_quotes"``);
  * **a quoted caption can never be a repeat.** A claim that reproduces display copy in quotes is
    about what a person is shown; whatever else it shares with the product it is refused
    (``near_miss_kind: "quoted_copy"``). A false accusation is the one outcome the tool must never
    produce.

v0.14 is TESTOPS-82: quoting is not by itself a signal of copy.

  * **a quoted run is display copy only when a second mark says so.** v0.13 refused any shared
    word that occurred only inside a quoted literal, which refused exactly the best-written
    assertions: ``the "booking" record is shown``, ``a "booking" is created``, ``the "booking"
    exists``, ``search for "room" returns results``. Well-written Gherkin quotes its subject to be
    unambiguous, so a single quoted word that is the sentence's only naming of its subject stays a
    candidate shared word. Copy now needs one of three marks beside the quotes: the run holds more
    than one word, a display verb stands immediately in front of it (``shows``, ``sees``,
    ``displays``, ``reads``, ``gets``, ``receives``, ``says``), or banner punctuation sits inside it
    (``!``). ``the "booking" record is shown`` is judged on its merits - the verb ``shown`` and a
    GET route - and is no longer refused for quoting alone;
  * **the quoted noun outranks an incidental word.** ``verify the "room" type appears in the list``
    used to withhold ``room`` and then accuse on ``list``, a word that happens to sit in a route.
    When a quoted run names a noun the product also carries, that is the noun the record uses;
    a weaker word outside the run is never allowed to justify the match;
  * **the refusal says which case it is.** A display-copy refusal says the word is "text a person
    is shown"; a quoted entity refused because the act does not agree says so instead, and never
    calls the assertion's own subject something other than the subject of the check.

v0.13 is TESTOPS-79: display copy is not the subject of the claim.

  * **a word that appears only in the assertion's display copy is not a candidate shared word.**
    The first real corpus run proposed nine repeats and eight were wrong on one shape: "Visitor
    will get Booking Successful! message" shares the word "message" with a contact message's
    ``GET /{id}`` route. The assertion is about a banner; the route returns a different service's
    entity. A word that occurs *only* inside text the assertion reproduces - a quoted string, or a
    capitalised banner the sentence hands to a person ("Thanks for getting in touch message") - is
    display copy, and sharing it with the product says the two sentences use the same English noun,
    not that the product publishes what the check is about. Such a claim is a near miss
    (``near_miss_kind: "display_copy"``) whose reason names the word and the copy it sits in. The
    rule is typographic, not a list of nouns: a quoted placeholder (``'<room_name>'``) is a slot,
    not copy, and a capitalised domain noun with no display phrase in front of it ("New Booking is
    created") stays a candidate - so the room-creation assertion still repeats ``POST /``;
  * **a quoted verb is not the assertion's intent.** ``Visitor sees "Booking created"`` used to
    read ``create`` from the quoted copy and let a POST route outrank the sentence's own verb
    (``see``, a GET). Display copy is now excluded from the intent as well, so a word inside it can
    neither be the shared word nor decide the act;
  * **a ``KP`` claim is not silently outside the product question.** A claim settled by the page
    the server sends used to record the product as irrelevant, so a whole class of browser claims
    never reached the rule. Where the run drove a browser, the claim is now assessed like any other
    browser claim: the product's surface, route and word are recorded (its verdict stays
    ``review`` - the browser was the waste, which is the stronger finding). Where no browser ran,
    the record says why the product is not evidence instead of falling silent.

v0.12 is TESTOPS-78: two holes in the product verdict that v0.11 left open.

  * **a verb-less assertion does not accuse.** v0.11's verb rule only protected a sentence that
    named an act the intent table knows; a presence/absence sentence ("booking details present")
    had no verb, so `verb_agrees` was vacuously true and the round-1 noun-only match ran - and
    counted a bare noun shared with ``DELETE /booking/{id}`` as a repeat over the ``GET`` that was
    also there. A shared noun with no recognised intent is not evidence of anything, so it is now
    refused as a near miss, exactly as a method disagreement is. The record says why in words:
    the assertion names no act this rule recognises, so a shared noun alone is not a repeat;
  * **the intent table is an explicit list of English forms.** ``_intent_forms`` generated
    inflections by string surgery, which produced forms no English speaker writes (``getted``,
    ``readed``). The table is now a pinned literal, and a test asserts its contents exactly, so a
    future change to it is a deliberate one rather than a side effect of a generator;
  * **the near miss is shown.** A near-miss claim stays ``distinct`` and so raises no case, but the
    run page counts the claims it refused on one line and lists them with their sentence and a
    link to the case page of their scenario when one exists; and a case page shows the near-miss
    sentence of any claim in its own scenario that the product did not count. The refusal is
    recorded, and now a reader can reach it. Nothing here moves a verdict.

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
version = "0.16"
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
#
# TESTOPS-72 amendment: this is a tie-break *within* a chosen method, never the rule itself. The
# rule is below, and it is what stops a creation assertion being matched to a read route.
PRODUCT_CLAIM_VERBS = frozenset({"get", "list", "read", "create", "add", "update", "delete",
                                 "remove", "clear", "validate", "mark", "check"})

# What a target has to start with to be a route rather than a file path.
_ROUTE_VERBS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "ANY"})

# The assertion's intent, as the HTTP methods that could settle it (TESTOPS-72; the table is
# explicit from TESTOPS-78). The verb is a rule, not a tie-break: "New room will be created" is
# creation, and a route that happens to name the noun "room" but answers a GET is a near miss, not
# evidence that the product publishes creation.
#
# The table is a pinned literal, one entry per form an assertion may actually use, because a
# generated form is not a reading. v0.11 built it by string surgery and produced ``getted`` and
# ``readed`` - forms no English speaker writes, and a form nobody writes can never be a deliberate
# intent. Every entry maps a form to (the verb recorded on the claim, the methods that settle it),
# and ``tests/test_product_evidence.py`` asserts the whole table exactly, so adding a form is a
# change somebody made on purpose rather than a side effect of a generator.
_INTENT_FORMS: dict[str, tuple[str, frozenset[str]]] = {
    # creation
    "create": ("create", frozenset({"POST"})),
    "creates": ("create", frozenset({"POST"})),
    "created": ("create", frozenset({"POST"})),
    "creating": ("create", frozenset({"POST"})),
    "add": ("add", frozenset({"POST"})),
    "adds": ("add", frozenset({"POST"})),
    "added": ("add", frozenset({"POST"})),
    "adding": ("add", frozenset({"POST"})),
    # An adjective that implies creation. "news" is not an intent to create, so it is the one form.
    "new": ("new", frozenset({"POST"})),
    # reading
    "read": ("read", frozenset({"GET"})),
    "reads": ("read", frozenset({"GET"})),
    "reading": ("read", frozenset({"GET"})),
    "get": ("get", frozenset({"GET"})),
    "gets": ("get", frozenset({"GET"})),
    "getting": ("get", frozenset({"GET"})),
    "show": ("show", frozenset({"GET"})),
    "shows": ("show", frozenset({"GET"})),
    "showed": ("show", frozenset({"GET"})),
    "shown": ("show", frozenset({"GET"})),
    "showing": ("show", frozenset({"GET"})),
    "display": ("display", frozenset({"GET"})),
    "displays": ("display", frozenset({"GET"})),
    "displayed": ("display", frozenset({"GET"})),
    "displaying": ("display", frozenset({"GET"})),
    "list": ("list", frozenset({"GET"})),
    "lists": ("list", frozenset({"GET"})),
    "listed": ("list", frozenset({"GET"})),
    "listing": ("list", frozenset({"GET"})),
    "view": ("view", frozenset({"GET"})),
    "views": ("view", frozenset({"GET"})),
    "viewed": ("view", frozenset({"GET"})),
    "viewing": ("view", frozenset({"GET"})),
    "see": ("see", frozenset({"GET"})),
    "sees": ("see", frozenset({"GET"})),
    "saw": ("see", frozenset({"GET"})),
    "seen": ("see", frozenset({"GET"})),
    "seeing": ("see", frozenset({"GET"})),
    "fetch": ("fetch", frozenset({"GET"})),
    "fetches": ("fetch", frozenset({"GET"})),
    "fetched": ("fetch", frozenset({"GET"})),
    "fetching": ("fetch", frozenset({"GET"})),
    "retrieve": ("retrieve", frozenset({"GET"})),
    "retrieves": ("retrieve", frozenset({"GET"})),
    "retrieved": ("retrieve", frozenset({"GET"})),
    "retrieving": ("retrieve", frozenset({"GET"})),
    # update
    "update": ("update", frozenset({"PUT", "PATCH"})),
    "updates": ("update", frozenset({"PUT", "PATCH"})),
    "updated": ("update", frozenset({"PUT", "PATCH"})),
    "updating": ("update", frozenset({"PUT", "PATCH"})),
    "edit": ("edit", frozenset({"PUT", "PATCH"})),
    "edits": ("edit", frozenset({"PUT", "PATCH"})),
    "edited": ("edit", frozenset({"PUT", "PATCH"})),
    "editing": ("edit", frozenset({"PUT", "PATCH"})),
    "change": ("change", frozenset({"PUT", "PATCH"})),
    "changes": ("change", frozenset({"PUT", "PATCH"})),
    "changed": ("change", frozenset({"PUT", "PATCH"})),
    "changing": ("change", frozenset({"PUT", "PATCH"})),
    "modify": ("modify", frozenset({"PUT", "PATCH"})),
    "modifies": ("modify", frozenset({"PUT", "PATCH"})),
    "modified": ("modify", frozenset({"PUT", "PATCH"})),
    "modifying": ("modify", frozenset({"PUT", "PATCH"})),
    # deletion
    "delete": ("delete", frozenset({"DELETE"})),
    "deletes": ("delete", frozenset({"DELETE"})),
    "deleted": ("delete", frozenset({"DELETE"})),
    "deleting": ("delete", frozenset({"DELETE"})),
    "remove": ("remove", frozenset({"DELETE"})),
    "removes": ("remove", frozenset({"DELETE"})),
    "removed": ("remove", frozenset({"DELETE"})),
    "removing": ("remove", frozenset({"DELETE"})),
    "destroy": ("destroy", frozenset({"DELETE"})),
    "destroys": ("destroy", frozenset({"DELETE"})),
    "destroyed": ("destroy", frozenset({"DELETE"})),
    "destroying": ("destroy", frozenset({"DELETE"})),
}


_PRODUCT_WORD = re.compile(r"[a-z0-9]+")


def _product_words(text: str) -> list[str]:
    """The words of a phrase, lower-cased. Punctuation, quotes and path syntax are not words."""
    return _PRODUCT_WORD.findall((text or "").lower())


def _product_meaningful(text: str, *, skip: frozenset[str] = frozenset()) -> set[str]:
    """The words of a phrase that could be evidence: not generic, not a one- or two-letter token.

    ``skip`` removes words the caller has already refused as evidence - display copy (TESTOPS-79).
    It is a set rather than a rule here so this function stays the one place that decides *which*
    words are too generic to count, and the caller stays the one place that decides *which* words
    the assertion is actually about.
    """
    return {word for word in _product_words(text)
            if len(word) >= 3 and word not in PRODUCT_STOP and word not in skip}


# ------------------------------------------------------- the assertion's display copy (v0.13/82)
#
# A word a person is *shown* is not the subject of the check. "Visitor will get Booking Successful!
# message" is about a banner; "message" is part of the copy on it, and the product's ``get message``
# route is a contact message in another service. Sharing the word says the two sentences use the
# same English noun, not that the product publishes what the check is about.
#
# Display copy is recognised from the assertion's own typography, never from a list of nouns:
#
#   * a quoted run (``"..."``, ``'...'``, the curly forms) is *only* copy when a second mark says so
#     (TESTOPS-82). Quoting a noun is how well-written Gherkin names its subject, so a single
#     quoted word is a candidate shared word unless the run holds more than one word, a display
#     verb stands immediately in front of it, or banner punctuation (``!``) sits inside it. A
#     quoted *placeholder* (``'<room_name>'``, ``'{room}'``) is a parameter, not copy, and stays a
#     candidate word - ``room`` in the room-creation assertion is a slot, not a literal;
#   * a capitalised phrase introduced by a display verb (``get``, ``see``, ``show``, ``display``,
#     ``render``) is a banner: a mid-sentence capital is the typographic mark of a title or a
#     banner, and the phrase runs to the next connective, determiner, verb, quote or the end of the
#     sentence. "Thanks for getting in touch message" is one such phrase.
#
# A word is display copy only when *every* occurrence of it lies in such a run. A capitalised
# domain noun with no display phrase in front of it ("New Booking is created") is therefore still a
# candidate, which is why this rule cannot refuse the room-creation assertion by accident. The
# detector can only ever *withhold* a candidate from the match; it can never manufacture one, so a
# misread banner can turn a repeat into a near miss but can never turn a claim into an accusation.
_DISPLAY_VERBS = frozenset({"get", "gets", "getting", "got", "see", "sees", "saw", "seen",
                            "seeing", "show", "shows", "showed", "shown", "showing", "display",
                            "displays", "displayed", "displaying", "render", "renders",
                            "rendered", "rendering", "read", "reads", "reading", "receive",
                            "receives", "received", "receiving", "say", "says", "said", "saying"})

# The words that, standing immediately *after* a quoted run, say the run named the subject rather
# than reproduced a caption: an intent verb (``a "booking" is created``) or a verb of existence or
# appearance (``the "booking" exists``, ``the "booking" is shown``). The rule reads in both
# directions (TESTOPS-82 amendment, review concern 1): a verb of this kind after the quotes means
# the quotes are what the sentence is about, whatever verb stands in front of them.
_FOLLOWING_SUBJECT_VERBS = (frozenset(_INTENT_FORMS) - frozenset({
    # Intent forms that are also ordinary nouns. Standing immediately after a quoted word they
    # usually name the noun - ``the "list" VIEW``, ``the "room" list`` - so on their own they do not
    # say the quotes were the sentence's subject.
    "list", "lists", "view", "views", "new", "display", "update", "change", "delete",
})) | frozenset({
    "is", "are", "was", "were", "be", "been", "being", "will", "has", "have", "had", "gets",
    "got", "exists", "exist", "existed", "existing", "appears", "appear", "appeared",
    "appearing", "remains", "remain", "remained", "returns", "return", "returned", "contains",
    "contain", "contained", "includes", "include", "included", "holds", "hold", "held"})

# Copulas and auxiliaries that can stand between a noun and the verb that governs it. They are
# stepped over when looking for a governing verb (TESTOPS-85, AC1) and are never themselves the
# sentence's act: ``is`` in ``a "Welcome" message is created`` is the copula of a caption, not an
# intent, and ``gets`` in ``a "room" gets booked`` is a passive auxiliary, not a read.
_AUXILIARIES = frozenset({"is", "are", "was", "were", "be", "been", "being", "will", "has",
                          "have", "had", "gets", "got", "can", "could", "should", "must", "shall",
                          "may", "might", "not", "never", "also", "then", "once"})

# The verbs that govern a noun phrase: an intent (create/read/update/delete) or a verb of existence
# and appearance. ``is`` alone is not one - a caption takes it too - so the auxiliaries above are
# stepped over first. This is what tells a compound entity claim from a caption in front of a noun
# (TESTOPS-85, AC1).
_GOVERNING_VERBS = _FOLLOWING_SUBJECT_VERBS - _AUXILIARIES

# Verbs that take the quoted text as their object - a caption the assertion reproduces, or a value
# the product hands back (``the response contains "Booking"``). A quoted run standing immediately
# behind one of these is copy or a value, never the subject (TESTOPS-82 amendment, review concern 1).
# This set widens only the *quoted-run* mark: the unquoted banner-phrase rule keeps ``_DISPLAY_VERBS``
# so the eight real-corpus refusals keep their ground.
_VALUE_VERBS = _DISPLAY_VERBS | frozenset({"contains", "contain", "contained", "includes",
                                           "include", "included", "holds", "hold", "held",
                                           "carries", "carry", "carried", "returns", "return",
                                           "returned", "prints", "print", "printed", "outputs",
                                           "output", "writes", "write", "wrote", "logs", "log",
                                           "logged"})

# The words that can only join two quoted runs into one noun phrase. When everything between two
# runs is one of these, the sentence names both runs as one subject and the record cannot pick one.
_CONNECTIVES = frozenset({"and", "or", "nor", "plus", "the", "a", "an", "this", "that", "these",
                          "those", "its", "their", "both", "&"})


# Where a banner phrase stops. These are connectives, determiners and auxiliaries - words that
# cannot be part of a banner's own text - and not prepositions: "Thanks for getting in touch" has
# three of those inside it, and cutting at one would stop the phrase before the word it explains.
_BANNER_STOPS = frozenset({"regarding", "about", "concerning", "and", "or", "but", "then", "while",
                           "when", "after", "before", "if", "because", "the", "a", "an", "this",
                           "that", "these", "those", "its", "their", "his", "her", "will", "is",
                           "are", "was", "were", "has", "have", "had", "can", "could", "should",
                           "must", "shall", "may", "might"})

_WORD_TOKEN = re.compile(r"[A-Za-z0-9]+")
# A past participle, as the second word of a passive construction. The test is typographic - the
# ending - and only ever used to recognise an auxiliary that is not the sentence's act; the intent
# table still decides what the act is (TESTOPS-85, AC4).
_PARTICIPLE = re.compile(r"[a-z]{3,}(?:ed|en)$")
# The auxiliaries that form a passive *and* are spelled like an intent: `gets booked` is the case
# that matters, because `gets` was being read as the read intent `get`. A passive with `is`
# (`is redirected`) never supplied an intent, so it stays an ordinary no-intent refusal and the
# corpus's near-miss kinds do not move (TESTOPS-85, AC5).
_PASSIVE_AUXILIARIES = frozenset({"get", "gets", "getting", "got", "gotten"})

# Straight and curly quotes, each pair matched on the same line - an assertion is one line of
# Gherkin, so an unbalanced quote is a typo rather than a sign to read further.
_QUOTED_RUN = re.compile(r"'[^']*'|\"[^\"]*\"|\u2018[^\u2019]*\u2019|\u201c[^\u201d]*\u201d")


def _is_slot(content: str) -> bool:
    """True when a quoted run names a parameter rather than reproducing text.

    ``'<room_name>'`` and ``'{roomPrice}'`` are slots: the step substitutes a value, so the words
    inside them are the parameter's name, not copy a person is shown. An empty literal is the same
    kind of thing - a value, not a caption.
    """
    text = content.strip()
    return (not text or "<" in text or ">" in text
            or (text.startswith("{") and text.endswith("}")))


def _quoted_runs(text: str) -> list[tuple[int, int]]:
    """The character spans of the assertion's quoted literals, excluding placeholder slots."""
    return [(match.start() + 1, match.end() - 1) for match in _QUOTED_RUN.finditer(text)
            if not _is_slot(match.group(0)[1:-1])]


def _governed_by_verb(tokens: list[tuple[str, int, int]], index: int) -> bool:
    """True when an intent or existence verb governs the noun at ``tokens[index]``.

    Copulas and auxiliaries between the noun and its verb are stepped over, so ``a "room" booking
    is created`` reads the same as ``a "room" booking exists``: the noun phrase is the sentence's
    subject and the verb says what is claimed about it (TESTOPS-85, AC1). A caption's copula
    (``a "Welcome" message is created``) is stepped over too; what keeps that case copy is that
    ``Welcome`` is not a word the product carries, not the absence of a verb.
    """
    for word, _start, _end in tokens[index + 1:]:
        lowered = word.lower()
        if lowered in _AUXILIARIES:
            continue
        return lowered in _GOVERNING_VERBS
    return False


def _quoted_compound_heads(text: str, domain_words: frozenset[str] = frozenset()
                           ) -> dict[tuple[int, int], str]:
    """Quoted runs that are the first element of a compound domain noun, with that noun's head.

    ``a "room" booking exists`` is an entity claim about a booking, not a caption: the quoted word
    is itself a word the product carries, so ``"room" booking`` is a compound noun and ``booking``
    is what the sentence asserts existence of. ``the "booking" booking`` is the same shape with the
    head repeating the quoted word - the unquoted occurrence is the subject (TESTOPS-85, AC1/AC2).

    A caption in front of a product noun is not this case: ``a "Welcome" message`` has a quoted
    word the product does not carry, so it stays copy. When the quoted word *is* a domain word,
    only an existence or intent verb governing the noun phrase distinguishes the compound entity
    from a caption (``"room" booking is created`` vs ``"room" booking``), which is why the verb is
    read past the noun rather than at the quotes.
    """
    tokens = [(match.group(0), match.start(), match.end())
              for match in _WORD_TOKEN.finditer(text)]
    heads: dict[tuple[int, int], str] = {}
    for match in _QUOTED_RUN.finditer(text):
        content = match.group(0)[1:-1]
        if _is_slot(content):
            continue
        start, end = match.start() + 1, match.end() - 1
        inside = [token for token in tokens if start <= token[1] and token[2] <= end]
        stripped = content.strip()
        if len(inside) != 1 or "!" in content:
            continue
        if stripped.endswith((".", ",", ")", "]", "}", "\u2026")):
            continue
        word = inside[0][0].lower()
        after_index = next((index for index, token in enumerate(tokens)
                            if token[1] >= match.end()), None)
        if after_index is None:
            continue
        head = tokens[after_index][0].lower()
        if head not in domain_words:
            continue
        if word == head or (word in domain_words and _governed_by_verb(tokens, after_index)):
            heads[(start, end)] = head
    return heads


def _quoted_copy_suppressed(text: str, domain_words: frozenset[str] = frozenset()
                            ) -> dict[str, str]:
    """``word -> the copy it is shown in``, for words quoted copy suppresses (TESTOPS-85, AC2).

    A copy run suppresses the words inside it and the noun it modifies: ``a "Welcome" message``
    makes ``message`` the noun the caption is about, so neither word is a candidate subject. The
    suppression is per occurrence, exactly as ``_display_copy`` is: a word that also occurs
    unquoted outside the copy names its own subject there, and the quoted run cannot hide it
    (``the user sees "booking" and a booking exists`` is assessed on the unquoted ``booking``).
    """
    runs = _quoted_copy_runs(text, domain_words)
    tokens = [(match.group(0), match.start(), match.end())
              for match in _WORD_TOKEN.finditer(text)]
    suppressed = [False] * len(tokens)
    for run_start, run_end in runs:
        for index, (_word, start, end) in enumerate(tokens):
            if run_start <= start and end <= run_end:
                suppressed[index] = True
        head = next((index for index, token in enumerate(tokens) if token[1] >= run_end), None)
        if head is not None and tokens[head][0].lower() in domain_words:
            suppressed[head] = True
    free = {tokens[index][0].lower() for index in range(len(tokens)) if not suppressed[index]}
    phrases: dict[str, str] = {}
    for run_start, run_end in runs:
        phrase = " ".join(text[run_start:run_end].split())
        for index, (word, start, end) in enumerate(tokens):
            if suppressed[index] and word.lower() not in free:
                phrases.setdefault(word.lower(), phrase)
    return phrases


def _passive_phrase(text: str) -> str:
    """The assertion's passive construction (``gets booked``), or ``""`` when it has none.

    A passive here is an auxiliary that is also an intent form (``gets``) followed by a past
    participle the intent table does not know. When the participle *is* an intent form the sentence
    already names its act (``is created`` reads ``create``), so that is not this case. The
    distinction matters because ``gets`` in ``a "room" gets booked`` was being read as the read
    intent ``get`` and agreeing with a ``GET /room`` route - a read recorded where the sentence
    asserts a change of state (TESTOPS-85, AC4).
    """
    tokens = [(match.group(0), match.start(), match.end())
              for match in _WORD_TOKEN.finditer(text)]
    for index in range(len(tokens) - 1):
        word = tokens[index][0].lower()
        following = tokens[index + 1][0].lower()
        if (word in _PASSIVE_AUXILIARIES and _PARTICIPLE.fullmatch(following)
                and following not in _INTENT_FORMS):
            return f"{word} {following}"
    return ""


def _quoted_copy_runs(text: str, domain_words: frozenset[str] = frozenset()
                      ) -> list[tuple[int, int]]:
    """The quoted runs that carry a mark of display copy (TESTOPS-82, AC1 + amendment).

    Quoting a noun is how well-written Gherkin names its subject, so the quotes alone say nothing.
    Copy needs a mark, and the marks are read on both sides of the run (review concern 1):

      * the run holds more than one word (``"Booking created"``);
      * banner punctuation sits inside it - ``!`` anywhere, or a trailing period, comma or bracket
        (``"Saved."``, ``"Booking."``) - which is the typography of a caption, not an entity;
      * a verb that takes a caption or a value as its object stands immediately in front of it
        (``shows``, ``sees``, ``contains``, ``returns``...);
      * the word after the quotes is a noun the product itself names (``a "Welcome" MESSAGE``,
        ``the "Booking Successful" BANNER``): the quoted text modifies that noun and is copy or a
        value, not the subject.

    Nothing else is copy. In particular an intent or existence verb immediately after the quotes
    (``a "booking" is created``, ``the "booking" exists``) says the quotes named the subject.
    """
    tokens = [(match.group(0), match.start(), match.end())
              for match in _WORD_TOKEN.finditer(text)]
    runs: list[tuple[int, int]] = []
    for match in _QUOTED_RUN.finditer(text):
        content = match.group(0)[1:-1]
        if _is_slot(content):
            continue
        start, end = match.start() + 1, match.end() - 1
        inside = [token for token in tokens if start <= token[1] and token[2] <= end]
        stripped = content.strip()
        if len(inside) > 1 or "!" in content:
            runs.append((start, end))
            continue
        # Punctuation written inside a one-word run is the banner mark it is: a person reads
        # "Saved." as a caption, and an entity is never quoted with its full stop.
        if stripped.endswith((".", ",", ")", "]", "}", "\u2026")):
            runs.append((start, end))
            continue
        after = next((token for token in tokens if token[1] >= match.end()), None)
        if after is not None and after[0].lower() in _FOLLOWING_SUBJECT_VERBS:
            # An intent or existence verb right after the quotes: the quotes named the subject.
            continue
        before = next((token for token in reversed(tokens) if token[2] <= match.start()), None)
        if before is not None and before[0].lower() in _VALUE_VERBS:
            runs.append((start, end))
            continue
        if after is not None and after[0].lower() in domain_words:
            # The quoted word modifies a noun the product carries, so it is that noun's copy or
            # value - never the subject the check is about. Unless the quoted word is itself a
            # word the product carries and a verb governs the noun phrase: then it is the first
            # element of a compound domain noun, and the noun is what the sentence is about
            # (TESTOPS-85, AC1: `a "room" booking exists` is a claim about a booking).
            if (start, end) not in _quoted_compound_heads(text, domain_words):
                runs.append((start, end))
    return runs


def _quoted_subject_runs(text: str, domain_words: frozenset[str] = frozenset()
                         ) -> tuple[list[tuple[int, int]], bool]:
    """The quoted run(s) naming the sentence's subject, and whether the choice is ambiguous.

    With one non-copy run the answer is that run. With two or more, the subject is the run an intent
    or existence verb governs - the run the verb follows (``the "booking" is shown in the "message"
    panel``) - and when no run is governed it is the first run (``search for "room" in the "list"
    view``). Where the sentence genuinely names both runs as one thing (a compound subject joined by
    ``and``), gives each its own verb, or puts one either side of the sentence's verb, there is no
    subject to name: the second element of the result is ``True`` and the caller must refuse,
    naming both runs, rather than let the rarity tie-break invent one (review concern 3).
    """
    copy_runs = _quoted_copy_runs(text, domain_words)
    heads = _quoted_compound_heads(text, domain_words)
    if heads:
        # The sentence's subject is the head noun of the compound (``"room" booking`` ->
        # ``booking``), not the quoted modifier. `_quoted_subject_words` returns that head, and
        # other quoted runs are incidental to it (TESTOPS-85, AC1/AC2).
        return [], False
    runs = [(start, end) for start, end in _quoted_runs(text)
            if not any(copy_start <= start and end <= copy_end
                       for copy_start, copy_end in copy_runs)]
    if len(runs) <= 1:
        return runs, False
    tokens = [(match.group(0), match.start(), match.end())
              for match in _WORD_TOKEN.finditer(text)]

    def following(run: tuple[int, int]) -> str:
        token = next((token for token in tokens if token[1] >= run[1]), None)
        return token[0].lower() if token is not None else ""

    governed = [run for run in runs if following(run) in _FOLLOWING_SUBJECT_VERBS]
    if len(governed) > 1:
        # Each run is the subject of its own clause: two claims, and one record cannot be both.
        return runs, True
    if len(governed) == 1:
        subject = governed[0]
        for earlier in [run for run in runs if run[1] <= subject[0]]:
            between = [token[0].lower() for token in tokens
                       if earlier[1] <= token[1] and token[2] <= subject[0]]
            if all(word in _CONNECTIVES for word in between):
                # "the "booking" and the "message" are created" - one verb, two subjects.
                return [earlier, subject], True
        return [subject], False
    verbs = [token[1] for token in tokens
             if token[0].lower() in _FOLLOWING_SUBJECT_VERBS or token[0].lower() in _DISPLAY_VERBS]
    if verbs and len({run[0] < min(verbs) for run in runs}) > 1:
        # One run before the sentence's verb and one after it: the sentence names two things and
        # nothing says which one the check is about.
        return runs, True
    return [runs[0]], False


def _quoted_subject_words(text: str, domain_words: frozenset[str] = frozenset()) -> frozenset[str]:
    """The words a quoted run names as the assertion's subject, not as copy (TESTOPS-82, AC2).

    ``verify the "room" type appears in the list`` names ``room``; ``list`` is incidental. When one
    of these words is also carried by the product, it is the noun the record must use - a weaker
    word outside the run may never justify the match.
    """
    runs, _ambiguous = _quoted_subject_runs(text, domain_words)
    words: set[str] = set()
    for start, stop in runs:
        for match in _WORD_TOKEN.finditer(text, start, stop):
            words.add(match.group(0).lower())
    # A compound domain noun is the subject even though only its modifier is quoted: `a "room"
    # booking exists` is a claim about the booking, so `booking` is the noun the record uses
    # (TESTOPS-85, AC1).
    words.update(_quoted_compound_heads(text, domain_words).values())
    return frozenset(words)


def _display_runs(text: str, domain_words: frozenset[str] = frozenset()) -> list[tuple[int, int]]:
    """The character spans of the assertion's display copy and banner phrases (TESTOPS-79/82)."""
    runs = list(_quoted_copy_runs(text, domain_words))
    # Every quoted literal bounds a banner phrase, copy or not: a title cannot swallow a quote.
    quoted_spans = _quoted_runs(text)
    tokens = [(match.group(0), match.start(), match.end())
              for match in _WORD_TOKEN.finditer(text)]
    quoted = [any(start <= s and e <= stop for start, stop in quoted_spans)
              for _w, s, e in tokens]

    for index, (word, start, _end) in enumerate(tokens):
        if index == 0 or quoted[index]:
            continue
        # A capitalised word that is not an all-caps acronym: the typographic mark of a title.
        if not (word[0].isupper() and not word.isupper()):
            continue
        previous = tokens[index - 1][0].lower()
        j = index
        while j < len(tokens):
            candidate, _s, _e = tokens[j]
            if j > index and (quoted[j] or candidate.lower() in _BANNER_STOPS):
                break
            j += 1
        last = j - 1
        phrase_end = tokens[last][2]
        opened_by_verb = previous in _DISPLAY_VERBS
        exclaims = "!" in text[start:phrase_end] or "?" in text[start:phrase_end]
        if opened_by_verb or exclaims:
            runs.append((start, phrase_end))
    return runs


def _display_copy(assertion: str, domain_words: frozenset[str] = frozenset()) -> dict[str, str]:
    """``word -> the display copy it occurs in``, for words that occur *only* there (TESTOPS-79).

    A word with even one occurrence outside display copy is absent: the assertion names it as its
    subject somewhere, and that occurrence is the one the product may be evidence about.

    ``domain_words`` is what the product itself names, and only ever tightens the quoted-run test
    (TESTOPS-82 amendment): a quoted word modifying one of the product's nouns is copy.
    """
    text = assertion or ""
    runs = _display_runs(text, domain_words)
    display: dict[str, str] = {}
    outside: set[str] = set()
    for match in _WORD_TOKEN.finditer(text):
        start, end = match.start(), match.end()
        spans = [(run_start, run_end) for run_start, run_end in runs
                 if run_start <= start and end <= run_end]
        if not spans:
            outside.add(match.group(0).lower())
            continue
        # The widest run containing the word is the phrase a reader is shown - a banner can open at
        # more than one capital, and the shortest span would quote only its tail.
        run_start, run_end = max(spans, key=lambda span: span[1] - span[0])
        display.setdefault(match.group(0).lower(), " ".join(text[run_start:run_end].split()))
    return {word: phrase for word, phrase in display.items() if word not in outside}



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


def _surface_method(route: str) -> str | None:
    """The HTTP method a surface's route declares, or ``None`` when it declares no method.

    A file-path surface (an engine module) and a route written without a verb both return ``None``:
    nothing in them says what the product does, so nothing in them can disagree with the assertion.
    ``ANY`` is the same - a route that answers every method settles every verb.
    """
    words = (route or "").split()
    if words and words[0].upper() in _ROUTE_VERBS and words[0].upper() != "ANY":
        return words[0].upper()
    return None


def _assertion_intent(assertion: str, *, skip: frozenset[str] = frozenset()
                      ) -> tuple[str, frozenset[str]] | None:
    """The assertion's own verb and the HTTP methods that could settle it, or ``None``.

    A mutation outranks a read when a step says both ("create the booking and see the message") -
    what the step asks the product to *do* is creation - and otherwise the first intent word in the
    assertion wins, which is deterministic for a given sentence.

    ``skip`` is the display copy (TESTOPS-79): a verb inside a quoted banner is the banner's word,
    not the assertion's act. ``Visitor sees "Booking created"`` is a read; the quoted ``create``
    must not outrank the sentence's own ``see`` and hand the claim a POST route.
    """
    found = [intent for intent in (_INTENT_FORMS.get(word) for word in _product_words(assertion)
                                   if word not in skip) if intent is not None]
    passive = _passive_phrase(assertion)
    if passive:
        # The auxiliary of a passive is not the sentence's act: `gets booked` is a change of state,
        # not a read, and recording `get` made it agree with a GET route (TESTOPS-85, AC4). The
        # participle decides the act when the intent table knows it; when it does not, the
        # assertion names no act this rule recognises, and the record says the claim is passive.
        auxiliary = passive.split()[0]
        found = [intent for word, intent in
                 ((word, _INTENT_FORMS.get(word)) for word in _product_words(assertion)
                  if word not in skip and word != auxiliary)
                 if intent is not None]
    if not found:
        return None
    mutations = [intent for intent in found if intent[1] - {"GET"}]
    # "new" is an adjective that implies creation; when the sentence also names the act ("will be
    # created") the act is the better verb to record, so it is only used as a fallback.
    for base, methods in mutations:
        if base != "new":
            return base, methods
    if mutations:
        return mutations[0]
    return found[0]


def product_match(assertion: str, surfaces) -> dict | None:
    """The strongest surface the assertion's words share, or ``None`` when nothing matches.

    Deterministic and total: every candidate is scored and the lowest key wins, so the same assertion
    over the same surfaces always names the same route. The ranking, in order, prefers

      0. a word a single quoted run names - the assertion quoting its own subject - over any word
         outside the quotes (TESTOPS-82, AC2), so an incidental word in a route cannot justify the
         match;
      1. a surface whose HTTP method is one the assertion's verb is settled by (TESTOPS-72
         amendment: "create/add/new" -> POST, "read/get/show/display/list" -> GET, "update/edit/
         change" -> PUT/PATCH, "delete/remove" -> DELETE). This is a rule, not a tie-break: a
         creation assertion is not evidence about a read route however well the nouns agree;
      2. a word the surface's *route* carries over a word only its claim carries - the route names
         the thing, so a shared route word says the product publishes that thing at an address;
      3. the rarer word, because a word in 3 of 25 surfaces is more specific than one in 12;
      4. the surface sharing more of the assertion's meaningful words;
      5. the surface whose claim uses the assertion's own verb ("get message" for "will get ...
         message"), which separates a read from a delete that happens to name the same noun;
      6. the surface id, so the choice is stable when everything else ties.

    Two guards refuse a candidate outright: a stop word is never evidence, and a word carried by more
    than :data:`PRODUCT_COMMON_SHARE` of the surfaces is the product's subject rather than this
    surface's. A word must appear literally - "created" does not match "create" - because the matched
    word is quoted back to a reader as the evidence, and a stem nobody wrote is not quotable.

    The returned record always names the assertion's verb, the surface's method and whether they
    agree. Where they do not, this is still the nearest surface, and :func:`_product_record` records
    it as a near miss rather than a repeat: the caller decides the verdict, but the evidence names
    both verbs so the refusal is arguable. An assertion that names no act at all has no verb to
    agree with anything, and a shared noun alone is likewise a near miss, not a repeat (TESTOPS-78).

    TESTOPS-79: a word that occurs only in the assertion's display copy is not a candidate. When a
    surface shares nothing but such a word, the nearest one is still returned - with
    ``display_copy`` set and the copy it sits in - so the refusal names the route, the word and the
    banner rather than falling silent.

    TESTOPS-82: a word inside a single quoted run is the assertion naming its subject, and such a
    word ranks above any word outside it. ``verify the "room" type appears in the list`` must record
    ``room``; ``list`` may never be the word a match is justified with.

    TESTOPS-82 amendment (review concerns 1-3): with two quoted runs only the run the sentence is
    about is a subject - the run an intent or existence verb governs, or the first run when none
    does - and where the choice is genuinely ambiguous the record says so (``quotes_ambiguous``) and
    names both runs, so the caller refuses rather than accusing an incidental surface. The record
    also carries the quoted copy the assertion reproduces (``quoted_copy``): a claim that quotes a
    caption is about what a person is shown and can never be a repeat.

    TESTOPS-85: a quoted word that is itself a word the product carries, in front of a product noun
    and governed by an existence or intent verb, is the first element of a compound entity
    (``"room" booking``), so the head noun is the subject and the run is not copy. A quoted caption
    suppresses the words inside it and the noun it modifies, per occurrence, so a word that also
    occurs unquoted is still a candidate. The record carries the copy that suppresses the matched
    word (``quoted_copy_text``) and the passive construction the assertion uses (``passive``), so
    neither refusal can be stored without the words that explain it.
    """
    readings = [_surface_reading(surface) for surface in surfaces or ()]
    domain_words = frozenset(word for reading in readings for word in reading[5])
    display = _display_copy(assertion, domain_words)
    display_words = frozenset(display)
    # The words a quoted caption suppresses: the words inside it and the product noun it modifies
    # (`a "Welcome" message`). They are not candidates - a caption is not the subject - but the
    # suppression is per occurrence, so a word that also occurs unquoted stays a candidate and the
    # quoted run cannot hide it (TESTOPS-85, AC2).
    suppressed = _quoted_copy_suppressed(assertion, domain_words)
    subject_runs, quotes_ambiguous = _quoted_subject_runs(assertion, domain_words)
    subject_words = _quoted_subject_words(assertion, domain_words)
    head_words = frozenset(_quoted_compound_heads(assertion, domain_words).values())
    assertion_words = _product_meaningful(assertion, skip=display_words | frozenset(suppressed))

    if not readings or not (assertion_words or display_words or suppressed):
        return None
    total = len(readings)
    frequency: dict[str, int] = {}
    for _identifier, _route, _claims, _route_words, _claim_words, doc_words in readings:
        for word in doc_words:
            frequency[word] = frequency.get(word, 0) + 1
    assertion_verbs = set(_product_words(assertion)) & PRODUCT_CLAIM_VERBS
    intent = _assertion_intent(assertion, skip=display_words)
    intent_verb, intent_methods = intent if intent is not None else ("", frozenset())

    def key_for(identifier, route, route_words, claim_words, word, shared):
        agrees = bool(assertion_verbs & claim_words)
        method = _surface_method(route)
        method_agrees = not (intent_methods and method and method not in intent_methods)
        # A quoted noun is the assertion's own naming of its subject, so it outranks any word
        # outside the quotes - including one that happens to sit in a route (TESTOPS-82, AC2).
        return (0 if word in subject_words else 1,
                0 if method_agrees else 1,
                0 if word in route_words else 1, frequency[word], -len(shared),
                0 if agrees else 1, identifier, word)

    best, refused, quoted = None, None, None
    for identifier, route, claims, route_words, claim_words, doc_words in readings:
        visible = assertion_words & doc_words
        hidden = display_words & doc_words
        for word in sorted(visible):
            if word in PRODUCT_STOP:
                continue
            if frequency[word] > PRODUCT_COMMON_SHARE * total:
                continue
            key = key_for(identifier, route, route_words, claim_words, word, visible)
            if best is None or key < best[0]:
                best = (key, identifier, route, _claim_carrying(claims, word), word,
                        frequency[word], total, "visible")
        # The same ranking over the words refused as display copy, kept only in case nothing the
        # assertion actually names matches. A refused word is never allowed to beat a real one.
        for word in sorted(hidden):
            if frequency[word] > PRODUCT_COMMON_SHARE * total:
                continue
            key = key_for(identifier, route, route_words, claim_words, word, hidden)
            if refused is None or key < refused[0]:
                refused = (key, identifier, route, _claim_carrying(claims, word), word,
                           frequency[word], total, "display")
        # And the same over the words a quoted caption suppresses. `a "Welcome" message is
        # created` has no candidate subject left, but the refusal must still name the route, the
        # noun and the caption rather than fall silent (TESTOPS-85, AC3).
        for word in sorted(frozenset(suppressed) & doc_words):
            if word in PRODUCT_STOP:
                continue
            if frequency[word] > PRODUCT_COMMON_SHARE * total:
                continue
            key = key_for(identifier, route, route_words, claim_words, word,
                          frozenset(suppressed))
            if quoted is None or key < quoted[0]:
                quoted = (key, identifier, route, _claim_carrying(claims, word), word,
                          frequency[word], total, "quoted")
    chosen = best or refused or quoted
    if chosen is None:
        return None
    _key, identifier, route, claim_text, word, shared_with, total, source = chosen
    is_copy = source == "display"
    method = _surface_method(route)
    return {"surface": identifier, "route": route, "claim": claim_text, "word": word,
            "shared_with": shared_with, "surfaces": total,
            "assertion_verb": intent_verb, "surface_verb": method or "",
            # With no recognised intent nothing can agree, and nothing can disagree either: the
            # match is a shared noun, which is not evidence (TESTOPS-78, AC1). ``intent_known`` is
            # carried separately so the record can say *which* refusal it is - a method that
            # differs, or an assertion that names no act at all.
            "intent_known": intent is not None,
            # The word is display copy the assertion reproduces, not the subject of the check
            # (TESTOPS-79). ``display_text`` is the phrase it sits in, so the refusal can quote it.
            "display_copy": is_copy, "display_text": display.get(word, "") if is_copy else "",
            # A word inside a single quoted run is the assertion naming its subject, not copy
            # (TESTOPS-82). The refusal can then say which case it is instead of blaming the
            # quoting. A compound head is the subject but is not itself quoted (TESTOPS-85).
            "word_quoted": word in subject_words and word not in head_words,
            # Two quoted runs and no way to tell which one the sentence is about: the record names
            # both and the caller refuses (TESTOPS-82 amendment, review concern 3).
            "quotes_ambiguous": quotes_ambiguous,
            "quoted_runs": [assertion[start:stop].strip() for start, stop in subject_runs],
            # The quoted copy the assertion reproduces, if any. A claim that quotes a caption is
            # about what a person is shown, so no shared word may make it a repeat (review
            # concern 1: copy must never escalate into a false finding).
            "quoted_copy": [assertion[start:stop].strip()
                            for start, stop in _quoted_copy_runs(assertion, domain_words)],
            # The copy that suppresses the chosen word, when it does. `quoted_copy[0]` can name a
            # caption other than the one hiding this word, and an empty interpolation was the
            # TESTOPS-78 fault recurring (TESTOPS-85, AC3).
            "quoted_copy_text": suppressed.get(word, ""),
            # The passive construction the assertion uses, if any: `gets booked`. A passive's
            # auxiliary is not its act, so the record declares the claim unassessed rather than
            # recording a read (TESTOPS-85, AC4).
            "passive": _passive_phrase(assertion),
            "verb_agrees": (intent is not None
                            and not (intent_methods and method and method not in intent_methods))}


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
                    placed: bool = True, uses_browser: bool = False) -> dict:
    """What the product said about one claim, as a record the claim and the page carry (AC1).

    Every claim gets one, so no verdict can be read as if the product had been silent when it was
    consulted, or as if it had said zero when nobody could read it. ``state`` is the caller's record
    of the product arm (``found``/``zero``/``not_assessable``, or ``""`` for a caller that recorded
    nothing) - the analyser never reads a product itself.

    ``uses_browser`` decides what a ``KP`` claim records (TESTOPS-79, AC7). A claim settled by the
    page the server sends was previously excluded from the product rule outright, which put a whole
    class of browser claims outside the question the tool exists to ask. When the run drove a
    browser, the product's surfaces are evidence about that claim like any other: the route and the
    word are recorded, and the verdict stays ``review`` (the browser was the waste - a stronger
    finding than "the product already publishes this"). When no browser ran there is nothing to
    repeat, and the record says that rather than falling silent.
    """
    surfaces = list(surfaces or ())
    record = {"state": PRODUCT_NONE, "needs_browser": interaction in NEEDS_BROWSER,
              "surfaces": len(surfaces), "surface": None, "route": None, "claim": None,
              "word": None, "shared_with": 0, "reason": "",
              # The verb rule's evidence, on every record in every state: the assertion's own intent
              # (when it named one) and, when a surface was read, that surface's method. A near miss
              # keeps both so a reader can argue with the refusal rather than take it on trust.
              "assertion_verb": "", "surface_verb": "", "verb_agrees": None, "near_miss": False,
              # Which near miss this is, when it is one (TESTOPS-78, AC3): a method that differs,
              # an assertion with no recognised act at all, or a word that is only display copy
              # (TESTOPS-79). ``None`` on every other record.
              "near_miss_kind": None, "intent_known": None,
              # The display copy a refused word sat in, so the page can quote it (TESTOPS-79), and
              # whether the word is the assertion's quoted subject rather than copy (TESTOPS-82).
              "display_text": "", "word_quoted": False,
              # Two quoted runs the sentence does not choose between, and the copy the assertion
              # quotes at all (TESTOPS-82 amendment, review concerns 1 and 3).
              "quotes_ambiguous": False, "quoted_runs": [], "quoted_copy": [],
              # The copy that suppresses the matched word, and the passive construction the
              # assertion uses (TESTOPS-85, AC3/AC4).
              "quoted_copy_text": "", "passive": ""}
    if not placed or interaction == "U":
        record["reason"] = ("nothing placed this claim, so nothing is known about what would settle "
                            "it and the product is not evidence about it")
        return record
    if interaction == "KP" and not uses_browser:
        record["reason"] = ("this claim is settled by the page the server sends, and the run did "
                            "not drive a browser, so no browser was spent and the product's routes "
                            "are not evidence about it")
        return record
    if interaction not in NEEDS_BROWSER and interaction != "KP":
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
    if match["display_copy"]:
        # The only word the two share is text the assertion reproduces - a banner or a quoted
        # string (TESTOPS-79, AC1/AC3). It says the two sentences use the same English noun, not
        # that the product publishes what the check is about, so the claim is a near miss whose
        # reason names the word and the copy it sits in.
        record["state"] = PRODUCT_ZERO
        record["near_miss"] = True
        record["near_miss_kind"] = "display_copy"
        own = f', whose own claim is "{match["claim"]}"' if match["claim"] else ""
        record["reason"] = (f'the product declares {match["route"]}{own}, and the only word the '
                            f'two share is "{match["word"]}", which appears only inside the '
                            f'assertion\'s display copy "{match["display_text"]}" - text a person '
                            f'is shown rather than the subject of the check - so it is not counted '
                            f'as a repeat. Name the thing the assertion checks rather than the copy '
                            f'it is shown in, or check this one by hand')
        return record
    if match["quotes_ambiguous"]:
        # Two quoted runs and nothing in the sentence says which one the check is about. Naming
        # either would let the rarity tie-break accuse an incidental surface, so the record names
        # both and refuses (TESTOPS-82 amendment, review concern 3).
        record["state"] = PRODUCT_ZERO
        record["near_miss"] = True
        record["near_miss_kind"] = "ambiguous_quotes"
        record["word"] = None
        named = " and ".join(f'"{run}"' for run in match["quoted_runs"])
        record["reason"] = (f'the product declares {match["route"]}, but the assertion quotes two '
                            f'things - {named} - and nothing in the sentence says which one the '
                            f'check is about, so no shared word is counted as a repeat. Name the '
                            f'one thing the check is about, or check this one by hand')
        return record
    if match["quoted_copy"]:
        # The assertion quotes a caption. Whatever it shares with the product, the claim is about
        # what a person is shown rather than about the product's behaviour, so a shared word can
        # never make it a repeat (TESTOPS-82 amendment, review concern 1: copy never accuses).
        record["state"] = PRODUCT_ZERO
        record["near_miss"] = True
        record["near_miss_kind"] = "quoted_copy"
        # Name the caption that suppresses the matched word when one does, otherwise the caption
        # the assertion quotes. Interpolating `match["display_text"]` printed an empty pair on
        # every quoted_copy record, because that field only carries display copy and a quoted
        # caption is not one - the TESTOPS-78 fault recurring (TESTOPS-85, AC3).
        copy_text = match["quoted_copy_text"] or match["quoted_copy"][0]
        record["display_text"] = copy_text
        own = f', whose own claim is "{match["claim"]}"' if match["claim"] else ""
        if match["quoted_copy_text"]:
            record["reason"] = (f'the product declares {match["route"]}{own}, and it shares the '
                                f'word "{match["word"]}" with the assertion, but "{match["word"]}" '
                                f'is text a person is shown inside the assertion\'s display copy '
                                f'"{copy_text}" - not the subject of the check - so it is not '
                                f'counted as a repeat. Name the thing the assertion checks rather '
                                f'than the copy it is shown in, or check this one by hand')
        else:
            record["reason"] = (f'the product declares {match["route"]}{own}, and it shares the '
                                f'word "{match["word"]}" with the assertion, but the assertion '
                                f'reproduces display copy "{copy_text}" - text a person is shown '
                                f'rather than the subject of the check - so the claim is about the '
                                f'copy and no shared word is counted as a repeat. Name the thing '
                                f'the assertion checks rather than the copy it is shown in, or '
                                f'check this one by hand')
        return record
    if not match["verb_agrees"]:
        # The nearest surface names the same noun without settling the assertion - a GET route for
        # an assertion about creation, or a bare noun for an assertion that names no act at all.
        # Neither is evidence that the product publishes the act, so the state is ``zero`` (the
        # product was read and settles nothing here), and the route and the word are recorded so the
        # refusal is arguable rather than silent.
        record["state"] = PRODUCT_ZERO
        record["near_miss"] = True
        if not match["intent_known"]:
            if match["passive"]:
                # `a "room" gets booked` asserts a change of state in the passive voice. The
                # auxiliary `gets` is not the act, and this rule does not assess what a passive
                # claim asks the product to do, so the record says so in words rather than
                # recording a read that only looks right (TESTOPS-85, AC4).
                record["near_miss_kind"] = "passive_voice"
                record["reason"] = (f'the product declares {match["route"]}, and it shares the '
                                    f'word "{match["word"]}", but the assertion is passive '
                                    f'("{match["passive"]}"): this rule does not assess what a '
                                    f'passive claim asks the product to do, so a shared noun alone '
                                    f'is not counted as a repeat. Rewrite the claim in the active '
                                    f'voice naming the act, or check this one by hand.')
                if match["word_quoted"]:
                    record["reason"] += (f' The word is quoted because the assertion quotes its '
                                         f'own subject; quoting is not why it is refused')
                return record
            # v0.11 treated "no verb" as "any verb agrees", which handed a presence sentence back to
            # round-1 noun matching and accused a DELETE of being a repeat over the GET beside it
            # (TESTOPS-78, AC1). A shared noun with no recognised act is not evidence of anything.
            record["near_miss_kind"] = "no_intent"
            record["reason"] = (f'the product declares {match["route"]}, and it shares the word '
                                f'"{match["word"]}", but the assertion names no act this rule '
                                f'recognises (none of get, create, update or delete), so a shared '
                                f'noun alone is not evidence that the product already does this - '
                                f'it is not counted as a repeat. Name the act the assertion checks, '
                                f'or check this one by hand')
            if match["word_quoted"]:
                # AC4: the word is the assertion's subject, quoted for clarity. The refusal is
                # about the act, and the record must not read as if the quoting were the fault.
                record["reason"] += (f' The word is quoted because the assertion quotes its own '
                                     f'subject; quoting is not why it is refused')
            return record
        record["near_miss_kind"] = "verb_differs"
        record["reason"] = (f'the product declares {match["route"]}, and it shares the word '
                            f'"{match["word"]}", but the assertion\'s verb is "{match["assertion_verb"]}" '
                            f'and the route\'s method is {match["surface_verb"]} - a '
                            f'{match["surface_verb"]} route does not settle "{match["assertion_verb"]}" '
                            f'- so it is not counted as a repeat. Check whether the product declares '
                            f'a route for "{match["assertion_verb"]}", or check this one by hand')
        if match["word_quoted"]:
            record["reason"] += (f' The word is quoted because the assertion quotes its own subject; '
                                 f'quoting is not why it is refused')
        return record
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
                                          product_reason, placed=unbound is None,
                                          uses_browser=uses_browser)
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
