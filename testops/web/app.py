"""The smallest web surface that lets a person verify a finding and decide on it.

Two screens. Server-rendered HTML, one form, no JavaScript. The one disclosure is a fold: an
over-long list is collapsed behind a stated count, never silently truncated, and every folded entry
keeps a permalink that reveals it.

The list is the way in, and every row is a link a reader would follow: a judgement in the verdict's
own words and the scenario title, never the raw assertion fragment it used to print, and never a
phrase that stops on "should be" (TESTOPS-33). The rows are grouped by project, and the verdict
sits as a badge beside the case's state so a claim nobody could place does not read as settled.

The case page is one argument, said once, in the order a reader needs it (TESTOPS-23). The page used
to be six sections that narrated the analysis: the claim restated three times, a numbered section on
where a scenario's name came from, sentences about "the words" a rule had read, and fragment
headings such as "What settles it." A reader had to rebuild the argument from the tool's own
vocabulary, which is what the Product Owner meant by "the verbiage is still not right".

What the page says now:

  1. a scan block - the judgement as a headline, one sentence saying what is wrong, and one line
     saying what to do, on its own row so the eye lands on it; then the quote's provenance
  2. where another analyser raised a claim about the same asserting step, a short "Also reported
     by ..." cross-reference with a link to that case, and one sentence saying what the two mean
     together (TESTOPS-36)
  3. the step that is asserted - the feature file around it and the definition that runs it
  4. for a duplicate, the copy the claim names - its file:line, scenario, steps with their data,
     and the definition that runs the asserted step there (TESTOPS-32)
  5. the other steps in this scenario, for context - never presented as evidence
  6. what could not be checked - the sources that were never connected
  7. the decision

The copy a duplicate claim names is evidence, so it is shown before the context list and never in
its place: a page that withholds the copy has no way for a reader to check the claim.

Every sentence above is built from the stored row by a rule (``wrong_sentence``, ``action_line``
and the label functions below), not written for one claim, so any claim gets the same shape. The
step text is quoted once, in monospace; the action refers to "this step" rather than repeating it.
No reader-facing sentence mentions the analyser, its rules or its vocabulary; where a rule matters,
the page states the fact it found.

Design decisions that matter, from ui-design-v2 and the Product Owner's reading of the old page:

  - the provenance of the quote is a labelled footnote under it, never a numbered step in the
    argument; a heading that does not say where it came from is a riddle, and a section spent on the
    riddle is in the way
  - the verdict states what is true of the claim, not what is absent: "Checked, but over-tested"
    rather than "Browser not needed", which left the reader to invert it into a cost
  - a list of links is not evidence; every link says what it shows, and the steps that are only
    context sit in their own group, introduced together
  - ``I1``..``I4`` and ``KP`` are debugging shorthand and appear only in a footnote below the decision
  - decisions belong to the CASE, and the panel says how many findings ride on them
  - suppression is reversible, and reopening actually deletes the suppression
  - the empty screen reports freshness, never "all clear"
"""
from __future__ import annotations

import datetime as dt
import html
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .. import cases, queries, services, sources
from ..analysers import cover, is_registered
from ..extract.ecosystems import UNSUPPORTED as ECOSYSTEM_UNSUPPORTED
from ..extract.stepbindings import LAYER_ORDER
from ..store import db
from . import tone


# What is true of each verdict, as a reader meets it (TESTOPS-23, AC7). The old vocabulary named an
# absence - "Browser not needed", "Never actually proved" - and left the reader to invert it into a
# cost. These name the state of the claim; a gap's label names the one instrument the assertion needs
# and the test does not run, because that is what makes it a gap rather than a shortfall.
VERDICT_LABEL = {
    "distinct": "Checked",
    "review": "Checked, but over-tested for what it asserts",
    "gap": "Not proved \u2014 nothing runs a browser",
    "duplicate": "Checked, but this repeats another test",
    "repeats_product": "Checked, but the product already exposes this",
    "unplaced": "Cannot tell",
}
STATE_LABEL = {"open": "Open", "needs_fix": "Needs a fix", "resolved": "Resolved",
               "false_positive": "Not a real finding"}
# A run that raised nothing is a fact about the code, not a decision about it. It gets its own
# label so no screen can borrow the word a person's decision owns (TESTOPS-22).
NO_FINDINGS_LABEL = "No findings"
# A run whose every case carries a recorded decision is a real case, closed - never a quiet run
# (TESTOPS-34). The label says what is true of the run without borrowing a single case's state.
ALL_DECIDED_LABEL = "All decided"

# What each instrument does, as a verb phrase. ``ui`` and ``api`` are the ticket's own words.
INSTRUMENT_WORD = {
    "storage": "reads the database",
    "engine": "talks to the engine in-process",
    "controller": "calls the application's own controllers in-process",
    "api": "drives the HTTP API",
    "ui": "drives a browser",
    "unknown": "reaches no layer we could identify",
}
LAYER_WORD = {
    "storage": "the database",
    "engine": "the engine",
    "controller": "the application's own controllers",
    "api": "the HTTP API",
    "ui": "a browser",
    "unknown": "no layer we could identify",
}
SOURCE_NAME = {"jira": "Jira", "ado": "Azure DevOps"}
ANALYSER_LABEL = {"level_fitness": "Level fitness", "duplication": "Duplication"}

CSS = """
:root { --ink:#1b1f24; --dim:#5b6672; --line:#dfe3e8; --bg:#fbfbfa; --accent:#8C5E2C; --bad:#8a2b2b; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:16px/1.55 -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }
main { max-width: 60rem; margin: 0 auto; padding: 2rem 1.25rem 5rem; }
h1 { font-size: 1.15rem; letter-spacing:.02em; text-transform:uppercase; color:var(--dim); font-weight:600; }
h2 { font-size: 1.35rem; margin: 1.9rem 0 .35rem; }
h2.section { font-size: 1.02rem; letter-spacing:.01em; border-bottom:1px solid var(--line);
             padding-bottom:.3rem; margin-top:2rem; }
a { color: var(--accent); }
.fresh { color: var(--dim); font-size:.92rem; border-bottom:1px solid var(--line); padding-bottom:.9rem; }
.fresh strong { color: var(--ink); font-weight:600; }
ul.cases { list-style:none; padding:0; margin:1.5rem 0; }
ul.cases li { border:1px solid var(--line); border-radius:6px; background:#fff; margin-bottom:.6rem; }
ul.cases li a { display:block; padding:.85rem 1rem; text-decoration:none; color:inherit; }
ul.cases li a:hover { background:#f6f4f0; }
.claimtext { margin:.35rem 0 0; font-size:1rem; }
.meta { color:var(--dim); font-size:.9rem; }
.badge { display:inline-block; font-size:.78rem; letter-spacing:.03em; text-transform:uppercase;
         border:1px solid var(--line); border-radius:99px; padding:.1rem .55rem; color:var(--dim); }
.badge.hot { border-color:var(--bad); color:var(--bad); }
/* The verdict beside the case state (TESTOPS-33): a claim that could not be placed wears a dashed
   badge, so "Cannot tell" never looks as settled as "Checked".
   TESTOPS-52: a verdict that asserts a problem wears the same alarm as any other warning, and a
   verdict that asserts nothing is wrong wears neither. The tone is declared in web/tone.py. */
.badge.verdict { border-color:var(--accent); color:var(--accent); }
.badge.verdict.soft { border-style:dashed; border-color:var(--dim); color:var(--dim); }
.badge.verdict.hot { border-color:var(--bad); color:var(--bad); }
blockquote.assertion { margin:.6rem 0 .5rem; padding:.6rem .9rem; background:#fff;
                       border-left:3px solid var(--accent); font-size:1.12rem; }
.code { font-family: ui-monospace, Consolas, monospace; font-size:.8rem; color:var(--dim); }
ul.ev { margin:.35rem 0 0; padding-left:1.1rem; }
ul.ev li { margin:.2rem 0; }
.footnote { margin-top:2.2rem; border-top:1px solid var(--line); padding-top:.7rem; }
form.decide { margin-top:2rem; border-top:1px solid var(--line); padding-top:1.2rem; }
form.decide button { font:inherit; padding:.5rem .9rem; border-radius:5px; border:1px solid var(--line);
                     background:#fff; cursor:pointer; margin:.25rem .35rem .25rem 0; }
form.decide button.term { border-color:var(--bad); color:var(--bad); }
form.decide input[type=text] { font:inherit; padding:.45rem .6rem; border:1px solid var(--line);
                               border-radius:5px; width:min(28rem,100%); }
.warn { color: var(--bad); font-size:.9rem; }
.quiet { color:var(--dim); }
.scan { margin:1.15rem 0 1rem; padding:.85rem 1rem .9rem; background:#fff;
        border:1px solid var(--line); border-left:4px solid var(--accent); border-radius:6px; }
p.judgement { margin:0 0 .5rem; }
p.judgement strong.verdict { font-size:1.32rem; font-weight:700; line-height:1.25; }
/* TESTOPS-52: the headline wears the verdict's declared tone, not one alarm for everything.
   Alarm red is for a verdict that asserts a problem; a conclusion the tool could not reach is
   dim and dashed; "checked, nothing wrong" is the ordinary ink. */
p.judgement strong.verdict.hot { color:var(--bad); }
p.judgement strong.verdict.soft { color:var(--dim);
                                   border-bottom:1px dashed var(--dim); padding-bottom:.05rem; }
p.wrong { margin:0 0 .85rem; font-size:1.06rem; line-height:1.6; }
/* The font puts more of its line box above the baseline than below, so equal padding leaves the
   descenders closer to the box's bottom edge. The half-leading is paid on the bottom instead, so
   the space a reader sees above and below the text is the same (AC11). */
p.action { margin:0; padding:.51rem .8rem .69rem; background:#f6f4f0; border-radius:5px;
           font-weight:600; line-height:1.5; }
p.action .act { display:inline-block; margin-right:.55rem; font-size:.72rem; font-weight:700;
                letter-spacing:.09em; text-transform:uppercase; color:var(--accent); }
/* A code span ends where its identifier ends: the padding is cancelled by an equal negative margin,
   so a comma written against the span sits against the word it follows, not a gap away (AC10). */
code.ident { font-family: ui-monospace, Consolas, monospace; font-size:.9em; background:#f3f1ec;
             padding:.05em .25em; margin:0 -.25em; border-radius:3px; white-space:nowrap; }
p.provenance { margin:0 0 1rem; }
p.provenance .fn { font-weight:600; color:var(--ink); }
ul.context { margin:.35rem 0 0; padding-left:1.1rem; color:var(--dim); }
ul.context li { margin:.2rem 0; }
figure.snippet { margin:.7rem 0 1rem; }
figure.snippet figcaption { font-size:.86rem; color:var(--dim); margin-bottom:.3rem; }
pre.snippet { margin:0; background:#f3f1ec; border:1px solid var(--line); border-radius:5px;
              padding:.55rem .7rem; overflow-x:auto; font-size:.82rem; line-height:1.45; }
pre.snippet code { font-family: ui-monospace, Consolas, monospace; }
pre.snippet .sline { display:block; white-space:pre; }
pre.snippet .ln { display:inline-block; width:2.6rem; color:var(--dim); user-select:none; }
pre.snippet .sline.hit { background:#f6e7c8; }
pre.snippet mark.hit { background:transparent; color:inherit; font-weight:600; }
aside.xref { margin:.2rem 0 1rem; padding:.55rem .85rem .6rem; background:#f6f4f0;
             border-radius:5px; font-size:.94rem; }
aside.xref p { margin:.15rem 0; }
nav.site { margin-top:3rem; border-top:1px solid var(--line); padding-top:.8rem;
           font-size:.92rem; color:var(--dim); }
"""


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


def age(iso: str | None) -> str:
    if not iso:
        return "never"
    try:
        then = dt.datetime.fromisoformat(iso)
    except ValueError:
        return iso
    if then.tzinfo is None:
        then = then.replace(tzinfo=dt.timezone.utc)
    delta = dt.datetime.now(dt.timezone.utc) - then
    mins = int(delta.total_seconds() // 60)
    if mins < 2:
        return "just now"
    if mins < 90:
        return f"{mins} minutes ago"
    if mins < 48 * 60:
        return f"{mins // 60} hours ago"
    return f"{mins // (60 * 24)} days ago"


# The one navigation every page carries (TESTOPS-54 AC2). It lives here, in the wrapper all pages
# are rendered through, rather than in each page's body: a page whose address is only knowable by
# someone who already knows it is not a page a reader can reach. The footer is identical everywhere
# on purpose - one affordance, the same words, whatever page you are on.
SITE_NAV = ('<nav class="site" aria-label="All pages">'
            '<a href="/">\u2190 all cases</a> \u00b7 '
            '<a href="/runs">all runs</a> \u00b7 '
            '<a href="/config">configure projects and services</a></nav>')


def page(title: str, body: str) -> bytes:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head>
<body><main>{body}{SITE_NAV}</main></body></html>""".encode("utf-8")


def versions_text(versions: dict | None) -> str:
    """"cotw-bdd@a3f19853" - what was looked at, abbreviated but unambiguous."""
    return ", ".join(f"{k.split('/')[-1]}@{v[:8]}" for k, v in (versions or {}).items())


def display_state(state: str, findings: int) -> str:
    """The state a reader is shown. An empty case has no decision on it, whatever the row says.

    A finding count of zero is not a decision and must not wear one's word: this used to return
    "Resolved" here, which told every reader that a person had closed a claim nobody had ever made
    (TESTOPS-22). A recorded terminal state still wins, because that *is* a person's decision.
    """
    if findings == 0 and state not in cases.TERMINAL:
        return NO_FINDINGS_LABEL
    return STATE_LABEL.get(state, state)


def case_badge(decision: dict | None, findings: int) -> str:
    """The badge for a case page: the recorded decision if there is one, else what the run found."""
    if decision is not None:
        return STATE_LABEL.get(decision["state"], decision["state"])
    return NO_FINDINGS_LABEL if findings == 0 else STATE_LABEL["open"]


def freshness_line(fr: dict) -> str:
    """Never 'all clear'. Say what was looked at, and when."""
    if not fr.get("ever_run"):
        return ('<p class="fresh">Nothing has been analysed yet. '
                '<span class="quiet">Run <span class="code">python -m testops.cli levels --project cotw</span> '
                'to produce a first case.</span></p>')
    versions = versions_text(fr.get("versions"))
    return (f'<p class="fresh">Last analysed <strong>{esc(age(fr.get("finished_at")))}</strong>'
            f'{" at " + esc(versions) if versions else ""}'
            f' <span class="quiet">({esc(analyser_text(fr.get("analyser")))})</span></p>')


def analyser_text(name: str | None) -> str:
    return ANALYSER_LABEL.get(name or "", (name or "").replace("_", " "))


def instrument(layers) -> str:
    """The dearest layer a test reached - what it actually used, as a key."""
    known = [l for l in (layers or []) if l in LAYER_ORDER]
    return max(known, key=LAYER_ORDER.index) if known else "unknown"


def layer_words(layers) -> str:
    """The span in the reader's words, cheapest layer first."""
    seen, words = set(), []
    for layer in LAYER_ORDER:
        if layer in (layers or []) and layer not in seen:
            seen.add(layer)
            words.append(LAYER_WORD[layer])
    for layer in layers or []:
        if layer not in seen:
            seen.add(layer)
            words.append(LAYER_WORD.get(layer, "an unnamed layer"))
    if len(words) < 2:
        return "".join(words)
    return " and ".join([", ".join(words[:-1]), words[-1]])


# ---------------------------------------------------------------- one claim, one argument
#
# TESTOPS-23. Every sentence a reader meets is built here from the stored row, by a rule, so that
# any claim gets the same shape and no sentence is written for one case. The shape is the reader's
# order: the assertion quoted once, the fact that settles it, what the test does about that, and
# what should happen - then evidence, caveats and the decision.

# A Gherkin assertion line, as the test file holds it. The keyword is part of the sentence the test
# author wrote, so the quote carries it (AC4): "Then each fact's data-fact-id ...".
GHERKIN = re.compile(r"^(Given|When|Then|And|But)\s+(.*)$")
SETTLED_BY = "settled by "
NEEDS_BROWSER = "needs a browser"
UNCLEAR = "unclear what would settle it"


def verdict_label(claim: dict) -> str:
    """What is true of this claim, in words that state the fact rather than an absence (AC7).

    ``review`` used to read "Browser not needed", which asked the reader to invert a negation and
    infer the cost; ``gap`` read "Never actually proved", which said what was missing but not what
    the assertion needed. Each label here says the state of the claim, and a gap's says which
    instrument the assertion needs and the test does not run.
    """
    verdict = claim.get("verdict")
    if verdict == "gap" and claim.get("interaction_label") != NEEDS_BROWSER:
        return "Not proved \u2014 nothing reaches what would settle it"
    return VERDICT_LABEL.get(verdict) or (verdict or "Unjudged").replace("_", " ").capitalize()


def _asserted_line(claim: dict) -> str | None:
    """The asserted line of the feature file, as the store kept it, or ``None`` without a blob."""
    snippet = (claim.get("snippets") or {}).get("assertion") or {}
    if snippet.get("state") != queries.SNIPPET_OK:
        return None
    for line in snippet.get("lines") or []:
        if line.get("asserted"):
            return str(line.get("text") or "").strip()
    return None


def quoted_assertion(claim: dict) -> str | None:
    """The assertion as a sentence, keyword included, or ``None`` when there is no step recorded.

    The quote comes from the test file, not from the claim's stored fragment: a reader sees the line
    the author wrote, not the analyser's lower-case subject. An assertion written with ``And`` or
    ``But`` is quoted as ``Then``: out of context those words continue a sentence the reader cannot
    see, which is the bare fragment this criterion exists to remove, and the assertion is what the
    line is. The excerpt below still shows the line exactly as the file holds it.
    """
    text = (claim.get("provenance") or {}).get("assertion_text") or ""
    if not text.strip():
        return None
    line = _asserted_line(claim)
    match = GHERKIN.match(line or "")
    # The stored assertion may carry its step's table or doc string after the step's words
    # (TESTOPS-31); the file line stops at the words, so the line is a prefix of what was stored.
    if match and text.strip().startswith(match.group(2).strip()):
        keyword = match.group(1)
        if keyword in ("And", "But"):
            keyword = "Then"
        return f"{keyword} {text.strip()}"
    return "Then " + text.strip()


def _fact_clause(label: str | None) -> str:
    """What settles this claim, as a subject-and-verb clause.

    The label is the stored phrase for what decides the claim ("settled by the page the server
    sends", "needs a browser"). It is used as a fact about the claim, never quoted back at the
    reader and never dropped into a sentence as a placeholder.
    """
    if label and label.startswith(SETTLED_BY):
        return f"{label[len(SETTLED_BY):]} settles it"
    if label == NEEDS_BROWSER:
        return "nothing short of a browser settles it"
    if label and label.startswith(UNCLEAR):
        return "nothing in it says what it is compared with, so nothing settles it"
    return "what would settle it was not recorded"


def _does_clause(claim: dict) -> str | None:
    """What the test does, as a lower-case clause, or ``None`` when the run could not say."""
    span = claim.get("span")
    if span is None:
        return None
    if not span:
        return None
    used = instrument(span)
    if used == "unknown":
        return None
    return f"the test {INSTRUMENT_WORD[used]}"


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def _typo(text: str) -> str:
    """One quote style for prose: curly double quotes, typographic apostrophes.

    Code spans are built after this runs and skip it, so an identifier matched by ``IDENTIFIER``
    keeps its own characters (AC5). A spaced hyphen used as a dash becomes an em dash; the
    unspaced hyphens inside an identifier such as ``data-fact-id`` are untouched.
    """
    text = text.replace(" - ", " \u2014 ")
    out: list[str] = []
    opening = True
    for ch in text:
        if ch == '"':
            out.append("\u201c" if opening else "\u201d")
            opening = not opening
        elif ch == "'":
            out.append("\u2019")
        else:
            out.append(ch)
    return "".join(out)


# An identifier a reader may meet in the summary: the HTTP client by its product name, an
# attribute name, a path, a snake_case symbol or the CSS class an assertion is about. These are
# read as code, not as prose that happens to contain punctuation (AC4).
IDENTIFIER = re.compile(
    r"(?:HTTP client"
    r"|\bdata-[a-z0-9]+(?:-[a-z0-9]+)*\b"
    r"|\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b"
    r"|\b[\w.-]+(?:/[\w.-]+)+\b"
    r"|\bCSS class\b)")


def rich_prose(text: str) -> str:
    """Escaped prose with identifiers in monospace and one typographic quote style (AC4, AC5)."""
    text = _typo(text)
    out: list[str] = []
    at = 0
    for match in IDENTIFIER.finditer(text):
        out.append(esc(text[at:match.start()]))
        out.append(f'<code class="ident">{esc(match.group(0))}</code>')
        at = match.end()
    out.append(esc(text[at:]))
    return "".join(out)


def _step_quote(quote: str) -> str:
    """The step text, in monospace - the one place the block quotes it (AC2)."""
    return f'<code class="ident">{esc(quote)}</code>'


def _without_step(action: str, step: str | None) -> str:
    """The action with its quoted copy of the step replaced by "this step" (AC2).

    The stored action repeats the step in straight quotes. The block has already quoted it once,
    so the action refers to it rather than quoting it a second time.
    """
    if not step:
        return action
    for form in (f'the step "{step}"', f'step "{step}"', f'"{step}"'):
        if form in action:
            return action.replace(form, "this step", 1)
    return action


# The page shows the whole stored action (TESTOPS-28).
#
# A stored action is one string, and it may hold more than one clause: an instruction, then -
# after a semicolon - a second order ("keep one"), or the reason for the first ("this level is the
# cheapest one that establishes it"). The page cannot tell which, and does not try. Two review
# passes read that tail's grammar to decide, and between them lost three orders - "the duplicate
# is deletable", "the second one can go", "the copy would be deleted by whoever owns it" - each one
# a different shape. A word list is the wrong tool for a judgement about a reader's reading.
#
# The asymmetry decides it: a clause cut from a stored action is invisible, and the reader holds
# half an instruction without knowing it; a clause kept is merely wordy, and the reader can see it
# and skip it. So nothing is removed here. The whole stored action is rendered, split at its
# semicolons into sentences so that two clauses never run together.
#
# Redundancy belongs to the analyser that writes the action. If a tail repeats the argument, that
# is the analyser's copy to fix, not something the renderer may delete (TESTOPS-28, AC4).


def _sentences(text: str) -> list[str]:
    """The stored action's clauses, split at its semicolons and nowhere else."""
    return [part.strip() for part in re.split(r";\s*", text) if part.strip()]


def _as_sentence(text: str) -> str:
    """One clause with an initial capital and one full stop, so two clauses never run together."""
    text = text.strip().strip(";").strip().rstrip(".").strip()
    if not text:
        return ""
    return text[:1].upper() + text[1:] + "."


def action_line(claim: dict, step: str | None) -> str:
    """The whole stored action, rendered as sentences: nothing classified, nothing cut.

    The store keeps one string and may hold two clauses; the page shows both, as two sentences
    with one full stop each, so the action reads as an instruction and never as a run-on
    (TESTOPS-28, AC1, AC5). "No change" is an action: a distinct claim says plainly that nothing
    needs doing.
    """
    action = (claim.get("proposed_action") or "").strip()
    if not action:
        return "No proposed action was recorded for this claim."
    raw_step = (claim.get("provenance") or {}).get("assertion_text") or step
    action = _without_step(action, raw_step)
    sentences = (_as_sentence(part) for part in _sentences(action))
    return " ".join(sentence for sentence in sentences if sentence)


def wrong_sentence(claim: dict, quote: str | None) -> str:
    """The one sentence that says what is wrong, built from the stored row.

    It names the assertion once, in monospace, and then the fact the rule found. The verdict only
    changes the connective: what a distinct claim lacks is a fault, and its sentence says so.
    """
    assessment = claim.get("assessment") or {}
    if assessment.get("state") == sources.NOT_ASSESSABLE:
        sentence = assessment.get("sentence") or ("Nobody could look at the sources this claim "
                                                  "needs.")
        if quote:
            return (f"The test asserts the step {_step_quote(quote)}, but "
                    f"{rich_prose(_lower_first(sentence))}")
        return rich_prose(sentence)
    if quote is None:
        recorded = (claim.get("statement") or "").strip()
        sentence = ("This claim was recorded before provenance was captured, so there is no quoted "
                    "step, no line and no commit to check it against.")
        if recorded:
            sentence += f' The claim as recorded was: \u201c{rich_prose(recorded)}\u201d.'
        return sentence

    q = _step_quote(quote)
    fact = rich_prose(_fact_clause(claim.get("interaction_label")))
    does = _does_clause(claim)
    verdict = claim.get("verdict")
    if verdict == "distinct":
        return f"The test asserts the step {q}, and {fact}."
    if verdict == "duplicate":
        return (f"The test asserts the step {q}, but another scenario in this run already asserts "
                f"the same thing, so the project runs it twice.")
    if verdict == "unplaced":
        return f"The test asserts the step {q}, but {fact}."
    if verdict == "repeats_product":
        # The evidence below the scan block names the route, the word and the surface's own claim;
        # this sentence is the judgement a reader acts on (TESTOPS-72, AC5). It stays short because
        # the headline above it and the action below it carry the rest, and a long step text must not
        # push the scan block past the prose lint's sentence limit.
        product = (claim.get("detail") or {}).get("product") or {}
        route = product.get("route")
        where = (f"already declares {esc(route)}" if route else "already exposes this")
        return (f"The test asserts the step {q} through a browser, but the product {where}, so the "
                f"check re-verifies work the developer has already done.")
    if verdict == "review" and does is not None:
        return f"The test asserts the step {q}, but {fact}, and {rich_prose(does)} to read it."
    if does is not None:
        return f"The test asserts the step {q}, but {fact}, and {rich_prose(does)} instead."
    return f"The test asserts the step {q}, but {fact}."


def argument_block(claim: dict) -> list[str]:
    """The opening block: three parts a reader can scan, in the order they decide with (AC1).

    The judgement is a headline, not a category. One sentence says what is wrong; one line says
    what to do, on its own row with its own label, so the eye lands on the action. The argument
    itself is not shortened away: the evidence, the context and the blind spots follow below.
    A claim the run could not assess says so in the headline, and a v1 claim says it has no
    quoted step instead of inventing one.
    """
    assessment = claim.get("assessment") or {}
    not_assessable = assessment.get("state") == sources.NOT_ASSESSABLE
    label = "Cannot assess" if not_assessable else verdict_label(claim)
    # TESTOPS-52: the tone is declared per verdict in web/tone.py; a claim nobody could consult
    # says the tool did not conclude, so it wears the soft treatment whatever its stored verdict.
    verdict = claim.get("verdict")
    assert isinstance(verdict, str)          # claim.verdict is NOT NULL
    tone_name = tone.NOT_ASSESSABLE_TONE if not_assessable else tone.tone_of(verdict)
    quote = quoted_assertion(claim)
    return ['<section class="scan">',
            f'<p class="judgement"><strong class="verdict{tone.class_suffix(tone_name)}">'
            f'{esc(label)}</strong></p>',
            f'<p class="wrong">{wrong_sentence(claim, quote)}</p>',
            f'<p class="action"><span class="act">What to do</span> '
            f'{rich_prose(action_line(claim, quote))}</p>',
            "</section>"]



def assessment_note(claim: dict) -> list[str]:
    """What the run's sources returned, when that is a fact the argument does not already carry.

    Distinct from the headline: a zero or an unrecorded answer is a fact about the sources, not a
    reason to withhold the verdict, so it is said once, plainly, under the argument.
    """
    assessment = claim.get("assessment") or {}
    if assessment.get("state") in (sources.ZERO, sources.NOT_RECORDED) and assessment.get("sentence"):
        return [f'<p class="meta">{esc(assessment["sentence"])}</p>']
    return []


def product_evidence_block(claim: dict) -> list[str]:
    """What the product said about this claim, in the product's own words (TESTOPS-72, AC5).

    A verdict that says the test repeats the product is only checkable if the page shows the route
    the product declares, the word the two share, and the claim the surface makes for itself. The
    block also speaks for the two states that are not a match: a product that was read and offered
    nothing, and a product nobody could consult. A claim the product is not evidence about (it does
    not need a browser) renders nothing - the claim's record still carries the state, but a line on
    every case page saying "the product is irrelevant here" is noise, not evidence.
    """
    product = (claim.get("detail") or {}).get("product")
    if not isinstance(product, dict):
        return []
    state = product.get("state")
    if state == "none":
        return []
    if state == "found":
        route = esc(product.get("route") or "a route")
        word = esc(product.get("word") or "")
        shared = product.get("shared_with")
        total = product.get("surfaces")
        own = esc(product.get("claim") or "")
        surface = (f'it declares <span class="code">{route}</span>, and its own claim for that '
                   f'route is \u201c{own}\u201d' if own
                   else f'it declares <span class="code">{route}</span>')
        counted = (f', which appears in {shared} of the product\u2019s {total} surfaces'
                   if isinstance(shared, int) and isinstance(total, int) else "")
        return [f'<p class="meta"><span class="fn">What the product says:</span> {surface}. The '
                f'assertion and that surface share the word \u201c{word}\u201d{counted}, so it is '
                f'not the noun the whole product is about.</p>']
    if state == "not_assessable":
        reason = (product.get("reason") or "").strip().rstrip(".")
        return [f'<p class="meta"><span class="fn">What the product says:</span> '
                f'{esc(reason) if reason else "the product could not be consulted"}, so nothing '
                f'here says whether this claim repeats it. That is not a zero.</p>']
    if state == "zero":
        total = product.get("surfaces")
        held = (f'it was read and declares {total} surfaces, and none of them shares a meaningful '
                f'word with this assertion' if isinstance(total, int) and total
                else 'it was read and declares no surface at all')
        return [f'<p class="meta"><span class="fn">What the product says:</span> {held}, so nothing '
                f'here says the product already does this.</p>']
    return []


def provenance_line(claim: dict) -> list[str]:
    """The quote's provenance, as a labelled footnote under it - never a numbered step (AC3).

    Scenario title, file:line and commit, read from the claim's own row. The scenario title is
    labelled as the test author's name for the scenario, because a title that is not labelled is a
    riddle and a reader will take it for a requirement.
    """
    prov = claim.get("provenance") or {}
    if claim.get("schema_version") != 2 or not prov.get("assertion_text"):
        return []
    where = f'{prov.get("assertion_path")}:{prov.get("assertion_line")}'
    commit = (prov.get("assertion_commit") or "")[:8]
    if claim.get("permalink"):
        source = f'<a href="{esc(claim["permalink"])}">{esc(where)}</a>'
        tail = ""
    else:
        source = f'<span class="code">{esc(where)}</span>'
        tail = (" This run did not record which repository the file lives in, so there is no link "
                "to open.")
    scenario = claim.get("scenario")
    if scenario:
        title = (f', in the scenario \u201c{rich_prose(scenario)}\u201d \u2014 the test author\u2019s '
                 f'own name for the scenario, not a requirement; nothing here was checked '
                 f'against one.')
    else:
        title = ". The scenario this assertion belongs to was not recorded."
    return [f'<p class="meta provenance"><span class="fn">Where this comes from:</span> {source} '
            f'at commit <span class="code">{esc(commit)}</span>{title}{tail}</p>']


_NUMBER = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}


def _needs(label: str, n: int) -> str:
    """One label as a clause a reader meets: "two are settled by the response the server sends"."""
    if label.startswith(SETTLED_BY):
        verb = "is" if n == 1 else "are"
        return f"{verb} {label}"
    if label == NEEDS_BROWSER:
        return label
    if label.startswith(UNCLEAR):
        return "says nothing about what would settle it"
    return label


def pass_aside(claim: dict) -> list[str]:
    """Why this scenario's other assertions are judged differently, when they are.

    One scenario can hold claims that need different things to settle them. A reader who sees two
    answers inside one scenario can only conclude the tool disagreed with itself, so the page says
    what is true of the scenario - in the reader's words, from the stored labels, once.
    """
    counts = claim.get("pass_labels") or {}
    if len(counts) < 2:
        return []
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    parts = [f"{_NUMBER.get(n, str(n))} {_needs(label, n)}" for label, n in ordered]
    listed = (parts[0] + " and " + parts[1]) if len(parts) == 2 else \
        ", ".join(parts[:-1]) + ", and " + parts[-1]
    return [f'<p class="meta">This scenario holds other assertions that need something different '
            f'to settle them: {esc(listed)}.</p>']


# ---------------------------------------------------------------- also reported by another analyser
#
# TESTOPS-36. Two analysers can judge the same asserting step and give separate instructions:
# level fitness says to rewrite the step, duplication says to keep one of two copies. They stay
# separate claims - a team may keep a duplicated pair and fix the level of one, or delete the copy
# and never touch its level - but each page has to say the other exists, or a reader is holding
# half of a decision. The section is two lines: what the other analyser found, and what the two
# mean together. Both come from the stored claims (``queries.cross_references``); a page with no
# counterpart renders nothing at all.

# How the level analyser's verdict reads when it is the other page's finding. A verdict is named,
# never re-described: the entry says what state the step is in, in the words a reader acts on.
_OTHER_LEVEL = {
    "review": "over-tested for what it asserts",
    "gap": "not proved, because nothing runs what would settle it",
    "unplaced": "not judged, because no instrument that settles it could be identified",
    "distinct": "already asserted at the level it should be",
    "repeats_product": "already exposed by the product, so a browser check re-verifies it",
}


def _copy_where(ref: dict) -> str:
    """The copy a duplicate claim names, in monospace, or the fact that it named none."""
    path, line = ref.get("copy_path"), ref.get("copy_line")
    if path and isinstance(line, int):
        return f'<span class="code">{esc(path)}:{line}</span>'
    return "a copy this run did not record"


def _other_finding(ref: dict) -> str:
    """One line saying what the other analyser found, from the stored verdict."""
    if ref.get("analyser") == "duplication":
        return f"the same step is also raised as a repeat of {_copy_where(ref)}."
    if ref.get("analyser") == "level_fitness":
        state = _OTHER_LEVEL.get(ref.get("verdict"), "judged at a level of its own")
        return f"the same step is also raised as {state}."
    return "the same step is also raised there."


def _relationship(claim: dict, ref: dict) -> str | None:
    """What the two findings mean together, in one sentence a reader can act on.

    The sentence names the decision the two pages do not share: fixing the level leaves the
    duplication in place, and choosing which copy to keep leaves the level of the survivor as it
    was. ``None`` when this build has no such pair of analysers to explain - the page then carries
    only the reference, never a sentence invented for the pair.
    """
    mine, theirs = claim.get("analyser"), ref.get("analyser")
    if mine == "level_fitness" and theirs == "duplication":
        return (f"This step is also reported as duplicating {_copy_where(ref)}; fixing the level "
                f"here does not remove the duplication.")
    if mine == "duplication" and theirs == "level_fitness":
        state = _OTHER_LEVEL.get(ref.get("verdict"), "judged at a level of its own")
        return (f"This step is also reported as {state}; deciding which copy to keep does not "
                f"change the level the remaining test runs at.")
    return None


def also_reported_block(claim: dict) -> list[str]:
    """The other analyser's claim about this step, and what the two mean together.

    A cross-reference, not a second argument: the reader came for one claim, so this is at most
    two lines per analyser and links to the page where that claim is decided. It is derived from
    the stored claims, so a missing counterpart is silence rather than an inference.
    """
    refs: list[dict] = claim.get("also_reported") or []
    if not refs:
        return []
    out = ['<aside class="xref">']
    for ref in refs:
        name = esc(analyser_text(ref.get("analyser")))
        out.append(f'<p><strong>Also reported by {name}</strong>: {_other_finding(ref)} '
                   f'<a href="/case/{esc(ref["case_id"])}">Read that case</a>.</p>')
        sentence = _relationship(claim, ref)
        if sentence:
            out.append(f'<p>{sentence}</p>')
    out.append("</aside>")
    return out


# ---------------------------------------------------------------- inline source

def _snippet_caption(snip: dict, label: str) -> str:
    where = f'{esc(snip["path"])}:{snip["line"]}'
    link = (f' \u2014 <a href="{esc(snip["link"])}">view in repository</a>'
            if snip.get("link") else "")
    return f'{label} <span class="code">{where}</span>{link}'


def snippet_block(snip: dict | None, label: str) -> list[str]:
    """One source excerpt, or the sentence that says why this store cannot show it.

    The code is escaped line by line, so a feature file containing markup is text on this page and
    never markup in it. A missing blob is an absence with a name, not an empty box.
    """
    if not snip:
        return []
    state = snip.get("state")
    if state == queries.SNIPPET_NO_COORDINATES:
        return []
    if state in (queries.SNIPPET_NOT_STORED, queries.SNIPPET_NOT_RECORDED):
        where = f'{snip["path"]}:{snip["line"]}'
        return [f'<p class="quiet">The source was recorded but its content is not in this store: '
                f'<span class="code">{esc(where)}</span>.</p>']
    if state == queries.SNIPPET_PAST_END:
        where = f'{snip["path"]}:{snip["line"]}'
        return [f'<p class="quiet">The source was recorded at <span class="code">{esc(where)}'
                f'</span>, but the stored file holds only {snip["total"]} lines, so there is '
                f'nothing at that line to show.</p>']
    if state == queries.SNIPPET_NO_BINDING:
        return ['<p class="quiet">No step definition in this run binds the asserted step, so there '
                'is no body to show.</p>']
    if state != queries.SNIPPET_OK:
        return []
    rendered: list[str] = []
    for ln in snip["lines"]:
        # Built outside an f-string expression: a backslash there is a SyntaxError before 3.12,
        # and 3.11 is an interpreter this product still serves (TESTOPS-13).
        text = esc(ln["text"])
        if ln["asserted"]:
            rendered.append(f'<span class="sline hit"><span class="ln">{ln["n"]}</span>'
                            f'<mark class="hit">{text}</mark></span>')
        else:
            rendered.append(f'<span class="sline"><span class="ln">{ln["n"]}</span>'
                            f'{text}</span>')
    code = "\n".join(rendered)
    return [f'<figure class="snippet"><figcaption>{_snippet_caption(snip, label)}</figcaption>'
            f'<pre class="snippet"><code>{code}</code></pre></figure>']


def assertion_snippet(c: dict) -> list[str]:
    """The feature file around the asserted step, above the permalink that gives it context."""
    return snippet_block((c.get("snippets") or {}).get("assertion"),
                         "The feature file, with the asserted line marked:")


def step_definition_snippet(c: dict) -> list[str]:
    """The step definition's body, labelled as the step that is asserted."""
    return snippet_block((c.get("snippets") or {}).get("step_definition"),
                         "The step definition that runs it:")


# ---------------------------------------------------------------- the case list's headline
#
# TESTOPS-33. The list rendered the claim's stored assertion fragment as the link text -
# "the suggestions list should be" - and the Product Owner's verdict was that he would not click it:
# it says what the step reads, not what the case is about, and it is not even a complete phrase.
#
# A row now reads "<judgement> — <subject>". The judgement is the verdict in the reader's words -
# a statement, not a category (TESTOPS-23's rule, applied to the list) - and the subject is the
# scenario title, which is the test author's name for the case. Only a claim with no scenario
# recorded falls back to its step text, normalised: keyword stripped, dangling tail trimmed. A
# headline never ends on a word that cannot end a phrase, and never exceeds 90 characters: a link
# that dangles is not a title, whichever end it dangles from.

# The judgement each verdict makes, short enough to sit in a list. These are the same statements
# the case page opens with, cut to a heading: "Not proved", not "gap"; "Already asserted elsewhere",
# not "duplicate".
LIST_JUDGEMENT = {
    "distinct": "Checked",
    "review": "Checked, but over-tested",
    "duplicate": "Already asserted elsewhere",
    "repeats_product": "Already exposed by the product",
    "gap": "Not proved",
    "unplaced": "Cannot tell",
}
# Verdicts the analyser no longer writes. A row that still carries one is a claim recorded before
# the vocabulary changed (TESTOPS-9); it gets the judgement its old word made, so an old case can
# be listed without the list inventing a new verdict for it.
LEGACY_JUDGEMENT = {"necessary": "Checked", "optimal": "Checked",
                    "overbuilt": "Checked, but over-tested"}

HEADLINE_MAX = 90
HEADLINE_SEP = " \u2014 "

# States whose badge wears the "hot" class, on the list and on the case page.
HOT_STATES = ("Open", "Needs a fix")
# Run badges that state a quiet or closed run, and therefore do not wear the alarm. Every other run
# badge counts findings, which is the alarm.
QUIET_RUN_BADGES = (NO_FINDINGS_LABEL, ALL_DECIDED_LABEL)


def badge_classes(label: str, hot: bool, base: str = "badge") -> str:
    """A badge's ``class`` attribute, built as a list and joined once.

    The row used to interpolate a whole attribute into another - ``f'class="badge{hot}"'`` with
    ``hot = ' class="hot"'`` - which rendered ``class="badge class="hot""``: the browser took
    ``badge`` and silently dropped ``hot`` (TESTOPS-33 review, defect 1; the same pattern survived
    on the run pages until TESTOPS-52). A class is appended to a list, never spliced into an
    attribute string, and ``hot`` is passed by the caller so no page inherits a default.
    """
    classes = [base]
    if hot:
        classes.append("hot")
    return " ".join(classes)


# A word that cannot end a phrase. "the suggestions list should be" ends on "be", "the panel at" on
# "at": the reader is left holding half a clause. The list trims these rather than printing them,
# and ``headline_problems`` lets a test refuse any that survives.
DANGLING = frozenset("""
a an the this that these those its their his her our your my
and or but nor so yet either neither both each every all any no not none some such
is are was were be been being am has have had do does did
should would could will shall may might must can cannot
about above across after against along among around as at before behind below beneath beside
between beyond by despite down during except for from in inside into like near of off on onto
opposite out outside over past per since than through throughout till to toward towards under
underneath until up upon via with within without
if then when whenever while because although though whether which who whom whose what
there here more most much many few less least very only just also too again ever never still
yet rather quite own same other another
""".split())

# Words that carry the meaning of the clause they end. ``DANGLING`` says they cannot end a phrase,
# but deleting one silently inverts the claim: "the row is skipped if not" must never be trimmed to
# "the row is skipped", and "the value is set no" must never read "the value is set" (TESTOPS-33
# review, defect 2). A tail that ends on one of these is kept, and a headline that keeps it is
# accepted rather than refused - an unfinished tail is honest, an inverted one is not.
MEANING = frozenset("""
not no never none without unless except only cannot isn't doesn't won't
""".split())

_TRAILING_MARKS = re.compile(r"[\s,;:.\-\u2013\u2014/|]+$")
_WORDS = re.compile(r"[A-Za-z0-9']+")



def list_judgement(verdict: str | None) -> str | None:
    """The verdict as the list's judgement, or ``None`` when the row records no verdict."""
    if not verdict:
        return None
    if verdict in LIST_JUDGEMENT:
        return LIST_JUDGEMENT[verdict]
    if verdict in LEGACY_JUDGEMENT:
        return LEGACY_JUDGEMENT[verdict]
    return verdict.replace("_", " ").capitalize()


def _dangling_word(text: str) -> bool:
    """True when the last word cannot end a phrase and is not one the trim must keep."""
    words = _WORDS.findall(text or "")
    if not words:
        # Punctuation is not a word: there is nothing here to dangle, and an empty string is an
        # absent subject rather than a fragment.
        return False
    word = words[-1].lower().strip("'")
    if word in MEANING:
        # A negation or modifier is the meaning of its clause. It is never a fragment to trim and
        # never a tail to refuse: removing it would invert the claim (TESTOPS-33 review, defect 2).
        return False
    return word in DANGLING


def ends_in_fragment(headline: str) -> bool:
    """True when a headline stops on a word that cannot end a phrase: "should be", "at", "the"."""
    return _dangling_word(headline)


def _trim_tail(text: str) -> str:
    """The subject without a tail that cannot end a phrase, and without trailing punctuation."""
    text = " ".join((text or "").split())
    while True:
        trimmed = _TRAILING_MARKS.sub("", text)
        words = trimmed.split()
        if len(words) <= 1:
            # One word left: keep it only if it is a phrase on its own. A lone "with" is the
            # fragment this rule exists to remove, and a headline made of nothing is worse.
            return "" if _dangling_word(trimmed) else trimmed
        if not _dangling_word(trimmed):
            return trimmed
        text = " ".join(words[:-1])


def _middle_ellipsis(text: str, limit: int) -> str:
    """``head … tail``: a subject's two ends, its middle dropped, never the subject itself.

    The last resort for a subject that cannot be shortened at a word boundary: dropping the tail
    can drop the negation that gave the sentence its meaning, and dropping the subject entirely
    leaves a reader with a judgement and no case (TESTOPS-33 review, defect 2).
    """
    if limit <= 1:
        return "\u2026"
    budget = limit - 3                    # the two spaces and the ellipsis
    if budget < 2:
        return text[:limit - 1] + "\u2026"
    words = text.split()
    tail: list[str] = []
    for word in reversed(words):
        candidate = " ".join([word, *tail])
        if len(candidate) > budget // 2:
            break
        tail.insert(0, word)
    tail_text = " ".join(tail)
    head_room = budget - (len(tail_text) + 1 if tail_text else 0)
    head: list[str] = []
    for word in words:
        candidate = " ".join([*head, word])
        if len(candidate) > head_room:
            break
        head.append(word)
    head_text = " ".join(head)
    if not head_text:
        # An unbroken run has no whole words to place: keep its first characters instead.
        head_text = text[:max(head_room, 0)].rstrip()
    if head_text and tail_text:
        return f"{head_text} \u2026 {tail_text}"
    if tail_text:
        return f"\u2026 {tail_text}"
    return f"{head_text} \u2026"


def _fit(text: str, limit: int) -> str:
    """``text`` within ``limit`` characters: whole words where possible, never nothing.

    A subject is shortened by dropping whole words before the ellipsis. It is never dropped to
    ``""``: an unbroken run of 200 characters has no word boundary, so it keeps its first
    characters and an ellipsis too - a reader must be able to see that a subject exists and was
    cut, rather than being shown the judgement alone (TESTOPS-33 review, defect 2).
    """
    if len(text) <= limit:
        return text
    if limit < 1:
        return ""
    if limit == 1:
        return "\u2026"
    cut = text[:limit - 1]                # one character is kept for the ellipsis
    if " " in cut:
        prefix = _trim_tail(cut[:cut.rindex(" ")])
        if prefix:
            return prefix + "\u2026"
    return _middle_ellipsis(text, limit)


def normalised_subject(text: str | None) -> str:
    """A claim's step text, fit to be a headline's subject: no keyword, no dangling tail."""
    cleaned = " ".join((text or "").split())
    match = GHERKIN.match(cleaned)
    if match:
        cleaned = match.group(2)
    return _trim_tail(cleaned)


def case_headline(judgement: str | None, subject: str | None) -> str:
    """``<judgement> — <subject>``: one line, never a trailing fragment, never over 90 characters.

    The subject is never dropped while one exists: a claim that cannot be stated cleanly is
    stated cut-short with an ellipsis, because the judgement alone tells a reader nothing about
    what the case is about (TESTOPS-33 review, defect 2).
    """
    head = " ".join((judgement or "").split())
    body = normalised_subject(subject)
    if not body:
        return head
    if not head:
        return _fit(body, HEADLINE_MAX)
    room = HEADLINE_MAX - len(head) - len(HEADLINE_SEP)
    return f"{head}{HEADLINE_SEP}{_fit(body, room)}"


def headline_problems(headline: str) -> list[str]:
    """What is wrong with a rendered headline: too long, or ending on a word that cannot end one."""
    problems: list[str] = []
    if len(headline) > HEADLINE_MAX:
        problems.append(f"{len(headline)} characters: {headline!r}")
    if _dangling_word(headline):
        problems.append(f"ends on a dangling word: {headline!r}")
    return problems


def row_headline(row: dict) -> str:
    """The case list's link text for one row: a judgement and a subject, or the run's own words."""
    judgement = list_judgement(row.get("verdict"))
    subject = row.get("scenario") or normalised_subject(row.get("assertion")
                                                        or row.get("statement"))
    if judgement is None:
        # A case with no claim (a quiet run) has no verdict to state. It keeps its own label rather
        # than borrowing a judgement nobody made (TESTOPS-22, TESTOPS-34).
        return case_headline(NO_FINDINGS_LABEL, subject) if subject else NO_FINDINGS_LABEL
    return case_headline(judgement, subject)


def verdict_badge(row: dict) -> str:
    """The row's verdict badge, wearing the verdict's declared tone (TESTOPS-52, AC1/AC5).

    A verdict that could not conclude is dashed and muted; a verdict that asserts a problem wears
    the alarm; a settled verdict wears neither. The tone comes from web/tone.py, never from a
    default that catches whatever the judgement vocabulary left over.
    """
    judgement = list_judgement(row.get("verdict"))
    if not judgement:
        return ""
    verdict = row.get("verdict")
    assert isinstance(verdict, str)          # list_judgement returned a judgement, so it exists
    suffix = tone.class_suffix(tone.tone_of(verdict))
    return f'<span class="badge verdict{suffix}">{esc(judgement)}</span> '


# ---------------------------------------------------------------- home screen

def totals_line(totals: dict) -> str:
    """What the store holds, counted and labelled, so a newcomer can say what exists.

    TESTOPS-55. The three numbers are the store's own counts, read when the page is rendered -
    never a text literal. Each number carries the noun it counts, and the sentence says what each
    noun means here, because "47 runs" is only useful if a reader knows a run is one analysis.
    """
    projects = int(totals.get("projects") or 0)
    runs = int(totals.get("runs") or 0)
    cases = int(totals.get("cases") or 0)
    return (f'<p class="totals">The store holds <strong>{_count(projects, "project")}</strong>, '
            f'<strong>{_count(runs, "run")}</strong> and <strong>{_count(cases, "case")}</strong>. '
            f'A project is a set of repositories this tool is set up to analyse; a run is one '
            f'analysis of a project at a fixed commit; a case is one finding waiting for a '
            f'decision.</p>')


def index(conn) -> bytes:
    fr = queries.freshness(conn)
    rows, older = queries.latest_per_analyser(conn)
    body = ["<h1>TestOps</h1>",
            '<p class="meta"><a href="/runs">all runs</a></p>',
            freshness_line(fr),
            totals_line(queries.store_totals(conn))]
    if not rows:
        if fr.get("ever_run"):
            versions = versions_text(fr.get("versions"))
            run_link = (f' <a href="/run/{esc(fr["run"])}">Open the run</a>' if fr.get("run") else "")
            body.append(
                f'<p>No cases are open. The newest analysis ran '
                f'<strong>{esc(age(fr.get("finished_at")))}</strong>'
                f'{" at " + esc(versions) if versions else ""} and raised nothing that needs a '
                f'decision. That is what this run found, not a claim that the code is clean.'
                f'{run_link}</p>')
        else:
            body.append('<p class="quiet">No cases yet. Nothing has been analysed, so this page '
                        'cannot say anything about the code.</p>')
    else:
        # Grouped by project (AC5): a person reads the list one repository at a time, and a heading
        # per project is what says which repository the rows below belong to. A project that has
        # more than one case gets one heading, not one per case: the newest case still comes first.
        groups: dict[str, list[dict]] = {}
        for r in rows:
            groups.setdefault(r["project"], []).append(r)
        for project, group in groups.items():
            body.append(f'<h2 class="section">{esc(project)}</h2>')
            body.append('<ul class="cases">')
            for r in group:
                n = r["findings"]
                shown = display_state(r["state"], n)
                badge_class = badge_classes(shown, shown in HOT_STATES)
                # TESTOPS-33: the link text is a judgement and a subject, never the raw assertion
                # fragment. A row whose step text is all there is falls back to its normalised step,
                # and the badge beside it says which verdict the headline is stating.
                body.append(
                    f'<li><a href="/case/{esc(r["id"])}">'
                    f'<div><span class="{badge_class}">{esc(shown)}</span> {verdict_badge(r)}'
                    f'<span class="meta">{esc(analyser_text(r["analyser"]))} '
                    f'\u00b7 {n} finding{"s" if n != 1 else ""} \u00b7 {esc(age(r["created_at"]))}</span>'
                    f'</div><p class="claimtext">{esc(row_headline(r))}</p></a></li>')
            body.append("</ul>")
    if older:
        body.append(f'<p class="quiet">{older} earlier run{"s" if older != 1 else ""} not shown '
                    f'\u2014 only the newest case per analyser is listed.</p>')
    return page("TestOps", "".join(body))


# ---------------------------------------------------------------- the claim's evidence

def _evidence_parts(claim: dict) -> tuple[dict | None, list[dict]]:
    """The row the claim rests on, and the rows that only say what the scenario contains.

    The analyser marks the binding of the asserting step ``asserted``. Everything else it kept -
    the other steps' definitions, the scenario row that says where the claim sits - is context: it
    tells a reader what the test does around the claim, and it never proves the claim. The page
    renders the two in different places so they cannot be read as equal support (AC6).
    """
    evidence = claim.get("evidence") or []
    asserted = next((item for item in evidence if item.get("asserted")), None)
    context = [item for item in evidence if item is not asserted]
    return asserted, context


def _where(item: dict) -> str:
    """An evidence location, linked when the store recorded enough to link it."""
    where = item.get("where") or item.get("uri") or ""
    if item.get("link"):
        return f'<a href="{esc(item["link"])}">{esc(where)}</a>'
    return f'<span class="code">{esc(where)}</span>'


def _evidence_absence(claim: dict) -> list[str]:
    """What the page says when there is no evidence list at all - never a silent gap."""
    evidence = claim.get("evidence")
    if evidence is None:
        if claim.get("schema_version") != 2:
            return ['<p class="quiet">Evidence for this claim was not recorded: it was recorded '
                    'before provenance was captured, so there is no run to look in and no '
                    'coordinates to look at.</p>']
        return ['<p class="quiet">Evidence for this claim was not recorded.</p>']
    if evidence:
        return []
    recorded = claim.get("observations_recorded")
    if claim.get("support"):
        return ['<p class="quiet">This claim records the observations it rests on, but none of '
                'them could be read back from this store. That is a defect in the stored evidence, '
                'not an absence of it.</p>']
    if recorded == 0:
        sentence = ('This run holds no observations, so the source above is the only evidence '
                    'there is \u2014 and the emptiness here is not a sign the claim is clean.')
        collected = claim.get("artefacts_recorded")
        if isinstance(collected, int):
            if collected:
                sentence += (f' Its snapshot holds {collected} '
                             f'artefact{"s" if collected != 1 else ""}, none of which produced an '
                             f'observation.')
            else:
                sentence += ' Its snapshot holds no artefacts either, so nothing was collected.'
        return [f'<p class="quiet">{esc(sentence)}</p>']
    if isinstance(recorded, int):
        return [f'<p class="quiet">Nothing in this run bears on this claim, so the source above is '
                f'the only evidence there is. The run recorded {recorded} '
                f'observation{"s" if recorded != 1 else ""} in total; none of them is at these '
                f'coordinates.</p>']
    return ['<p class="quiet">Nothing in this run bears on this claim, so the source above is the '
            'only evidence there is. How many observations the run recorded was not recorded.</p>']


def evidence_block(claim: dict) -> list[str]:
    """2. The step that is asserted: its file around it, and the definition that runs it.

    The feature excerpt comes first because it is the step a reader checks; the definition follows
    because it says what is actually done with it. Nothing here is a list of equal-weight links: the
    excerpt marks the one line the claim is about, and the definition is read from that same row.
    """
    out = assertion_snippet(claim)
    out.extend(_evidence_absence(claim))
    out.extend(step_definition_snippet(claim))
    return out


def _context_layers(context: list[dict]) -> set[str]:
    return {item.get("layer") for item in context
            if (item.get("key") or "").startswith("binding:") and item.get("layer") in LAYER_ORDER}


def _context_line(item: dict, *, hoisted: str | None) -> str:
    """One context row as the reader's sentence, with the shared instrument said once by the intro."""
    key = item.get("key") or ""
    if key.startswith("binding:"):
        _, verb, pattern = key.split(":", 2)
        line = (f'a {verb.capitalize()} step definition for '
                f'<code class="ident">{esc(pattern)}</code>')
        if hoisted is None:
            word = INSTRUMENT_WORD.get(item.get("layer") or "", INSTRUMENT_WORD["unknown"])
            line += f" that {rich_prose(word)}"
        return f"<li>{_where(item)} \u2014 {line}.</li>"
    return f'<li>{_where(item)} \u2014 {rich_prose(item.get("shows") or "")}.</li>'


def context_block(claim: dict) -> list[str]:
    """3. The other steps in this scenario - introduced together, and separated from evidence (AC6).

    These rows are the scenario's other bindings and the scenario row itself. They are what the test
    does around the claim, not what proves it, so they get their own heading and a sentence that
    says so. When every one of them uses the same instrument, the intro says it once instead of
    ending every line with the same clause.
    """
    _asserted, context = _evidence_parts(claim)
    if claim.get("evidence") is None:
        return ['<p class="quiet">The steps of this scenario were not recorded for this claim.</p>']
    if not context:
        return ['<p class="quiet">This run recorded no other step in this scenario.</p>']
    layers = _context_layers(context)
    hoisted = next(iter(layers)) if len(layers) == 1 else None
    intro = "These are the other steps in the same scenario"
    if hoisted:
        intro += f", and each of them uses {rich_prose(LAYER_WORD[hoisted])}"
    intro += (". They are not evidence for this claim; they are here so you can see what the test "
              "does around it.")
    out = [f"<p>{intro}</p>", '<ul class="ev context">']
    out.extend(_context_line(item, hoisted=hoisted) for item in context)
    out.append("</ul>")
    return out


def counterpart_block(claim: dict) -> list[str]:
    """The copy a duplicate claim names, shown as the evidence it is - never as context.

    The claim's ``established_by`` records the copy's ``file:line``; this block renders the copy
    from the snapshot's own artefact and blob. Its scenario is shown verbatim - the steps with the
    tables and doc strings that make the assertions what they are - so a reader can see whether the
    two really are the same claim. When the store cannot produce it, the block says which absence
    it is instead of leaving a blank where the evidence should be.
    """
    copy = claim.get("counterpart")
    if not copy:
        return []
    where = f'{copy["path"]}:{copy["line"]}'
    out = [f'<p>The claim names <span class="code">{esc(where)}</span> as the scenario that '
           f'already asserts the same thing. That copy is evidence for the claim, not context '
           f'around it.</p>']
    if copy.get("state") == queries.SNIPPET_OK:
        out.append(f'<p>The copy is the scenario \u201c{rich_prose(copy["scenario"])}\u201d, the '
                   f'test author\u2019s own name for it. Its steps follow, with the data they '
                   f'carry, and the line the claim names is marked.</p>')
        out.extend(snippet_block(copy.get("snippet"),
                                 "The copy\u2019s own scenario, as the store recorded it:"))
    elif copy.get("state") == queries.COUNTERPART_NO_SCENARIO:
        out.append(f'<p class="quiet">The stored file holds no scenario at <span class="code">'
                   f'{esc(where)}</span>, so this page cannot show the copy the claim '
                   f'meant.</p>')
    else:
        out.extend(snippet_block({"state": copy.get("state"), "path": copy["path"],
                                  "line": copy["line"], "total": copy.get("total"),
                                  "link": copy.get("link")}, ""))
    definition = copy.get("definition")
    if definition is not None:
        out.extend(snippet_block(definition,
                                 "The step definition that runs the copy\u2019s step there:"))
    return out


def section_unchecked(c: dict) -> list[str]:
    """4. What could not be checked. Absence is a state, never a blank and never a zero.

    TESTOPS-38 AC4 adds the per-service record: when the run's snapshot carries what each service
    said about itself, those sentences follow the source sentences, naming the service and its
    reason. A snapshot written before the model carries no such record, so its page is byte-for-byte
    what it always was (AC2).
    """
    out = _section_unchecked_sources(c)
    states = c.get("service_states")
    if isinstance(states, list) and states:
        out.extend(_service_state_lines(states))
    return out


def _service_state_lines(states: list[dict]) -> list[str]:
    """One sentence per service the project could not fully consult, and one when all were."""
    words = {
        "available": "available",
        "not_connected": "not connected",
        "policy": "policy",
        "absent": "absent",
        "not_assessable": "cannot assess",
    }
    unconsulted = [state for state in states
                   if isinstance(state, dict) and state.get("state") != "available"]
    if not unconsulted:
        return ['<p>Every service this project configures was available when this claim was '
                'checked.</p>']
    out = ['<p>Services this project configures, and what each could say:</p>']
    for state in unconsulted:
        name = state.get("name") or state.get("type") or "a service"
        word = words.get(state.get("state") or "", state.get("state") or "unrecorded")
        reason = (state.get("reason") or "").strip().rstrip(".")
        out.append(f'<p>{esc(name)} \u2014 {esc(word)}: {esc(reason)}.</p>' if reason
                   else f'<p>{esc(name)} \u2014 {esc(word)}.</p>')
    return out


def _section_unchecked_sources(c: dict) -> list[str]:
    """The source-level answer: which sources were never consulted, and why.

    The sentence comes from the claim's recorded *state*, not from the length of a list. A claim
    whose sources were never assessed says exactly that: the empty list it may have been written
    with is a default, and a default must not render as a clean bill. A claim that was assessed and
    found nothing missing gets its own sentence, distinguishable at a glance from the unassessed one.

    The recorded registry is the source of truth for *which* sources were missing and why, not the
    claim's list alone: the list names the source, and the registry says why it was not consulted and
    who decided. A name the registry record cannot explain keeps the older sentence, which names the
    source and says plainly that it was never consulted - it just cannot give a reason it never
    recorded.
    """
    state = c.get("sources_state")
    if state == queries.SOURCES_NOT_ASSESSED:
        # AC2. Not a blank, not an exception, and above all not "every source was available": the
        # claim is silent about its sources because nobody looked, and the page says so.
        return ['<p class="quiet">Nothing was checked against any source for this claim, so nothing '
                'here says its sources were clean.</p>']

    missing = c["sources_missing"]
    notes = c.get("source_notes") or []
    recorded = [note for note in notes if note.get("recorded")]
    if state == queries.SOURCES_NONE_MISSING and not recorded:
        # AC3. Assessed, and the assessment found nothing missing. This is the only sentence that
        # is allowed to be a clean bill, and it is reachable only through a recorded assessment.
        return ['<p>Every source needed for this claim was available.</p>']

    if recorded:
        # A capability the run consulted and could not read is not a source that was never
        # connected: saying "never consulted" about it would be the TESTOPS-41 fault in a new
        # place. The two get their own lead-in and their own sentence.
        absent = [note for note in notes if note.get("state") != sources.NOT_READABLE]
        unread = [note for note in notes if note.get("state") == sources.NOT_READABLE]
        out = []
        if absent:
            out.append('<p>Not connected when this claim was checked:</p>')
            out.extend(f'<p>{esc(_blind_spot_sentence(note))}</p>' for note in absent)
            out.append('<p>They were never consulted, so nothing here says they were clean '
                       '\u2014 only that this claim was never checked against them.</p>')
        if unread:
            out.append('<p>Could not be read when this claim was checked:</p>')
            out.extend(f'<p>{esc(_blind_spot_sentence(note))}</p>' for note in unread)
        return out

    names = [SOURCE_NAME.get(m, m) for m in missing]
    listed = ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]
    return [f'<p>Not connected when this claim was checked: <strong>{esc(listed)}</strong>. '
            f'They were never consulted, so nothing here says they were clean \u2014 only that this '
            f'claim was never checked against them.</p>']


def _blind_spot_sentence(note: dict) -> str:
    """One blind spot as a reader's sentence: the source, its state, the reason and who decided."""
    title = note.get("title") or note.get("source") or "a source"
    if not note.get("recorded"):
        return f"{title} \u2014 this run did not record why it was not connected."
    state = note.get("state")
    reason = (note.get("reason") or "").strip().rstrip(".")
    if state == sources.NOT_READABLE:
        return (f"{title} \u2014 could not be read: {reason}." if reason
                else f"{title} \u2014 could not be read.")
    if state == sources.BLOCKED:
        by = f" by {note['blocked_by']}" if note.get("blocked_by") else ""
        return f"{title} \u2014 blocked{by}: {reason}." if reason else f"{title} \u2014 blocked{by}."
    if state == sources.ABSENT:
        return f"{title} \u2014 absent: {reason}." if reason else f"{title} \u2014 absent."
    return f"{title} \u2014 {state}: {reason}." if state and reason else f"{title}."


def claim_sections(c: dict) -> tuple[list[str], int]:
    """One claim, one argument: the sections a reader needs, in the order they decide with.

    1. a scan block - the judgement, the one wrong thing, and the action on its own line; the
       provenance footnote sits under it, never as a section of its own
    2. a cross-reference to another analyser's claim about the same step, when one exists, and one
       sentence saying what the two mean together (TESTOPS-36); absent when there is none
    3. the step that is asserted - the file around it and the definition that runs it
    4. for a duplicate, the copy the claim names - its coordinates, scenario and definition, before
       any context (TESTOPS-32); the context list is about the claim's *own* scenario and can never
       stand in for the evidence
    5. the other steps in this scenario, for context - separated from evidence, introduced together
    6. what could not be checked

    Returns the sections and the number the decision section takes, so the numbering stays one
    sequence whether or not the copy is shown.
    """
    number = 1
    out = [f'<h2 class="section">{number}. What is asserted, and what settles it</h2>']
    number += 1
    out.extend(argument_block(c))
    out.extend(provenance_line(c))
    out.extend(binding_provenance_block(c))
    out.extend(assessment_note(c))
    out.extend(product_evidence_block(c))
    out.extend(pass_aside(c))
    out.extend(also_reported_block(c))
    out.extend([f'<h2 class="section">{number}. The step that is asserted</h2>'])
    number += 1
    out.extend(evidence_block(c))
    if c.get("counterpart"):
        out.extend([f'<h2 class="section">{number}. The copy this claim names</h2>'])
        number += 1
        out.extend(counterpart_block(c))
    out.extend([f'<h2 class="section">{number}. The other steps in this scenario, '
                f'for context</h2>'])
    number += 1
    out.extend(context_block(c))
    out.extend([f'<h2 class="section">{number}. What could not be checked</h2>'])
    number += 1
    out.extend(section_unchecked(c))
    return out, number


# ---------------------------------------------------------------- a run, or a decision

def _count(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def analysed_sentence(run: dict) -> str:
    """One sentence saying what this run examined, from counts the store can prove.

    Every number is a count over the case's own snapshot: feature files recorded as artefacts, the
    exclusions read from the stored project file by the same reader the analyser used, the scenario
    observations recorded against the files the build keeps, and the claims the run wrote. A count
    the snapshot cannot support is said to be unrecorded, not shown as zero.
    """
    name = ANALYSER_LABEL.get(run.get("analyser") or "",
                              (run.get("analyser") or "").replace("_", " ")).lower()
    if run.get("features") is None:
        return ("This run cannot be counted from the store: it records no snapshot, or a project "
                "file whose content is not in this store, so what it analysed cannot be stated "
                "here.")
    features = _count(run["features"], "feature file")
    scenarios = _count(run["scenarios"], "scenario")
    files = _count(run["feature_files"], "stored feature file")
    if not run.get("project_files"):
        exclusions = (f"no project file is stored for this snapshot, so no exclusion patterns "
                      f"were read and all {files} were in the build")
    else:
        project = ", ".join(run["project_files"])
        exclusions = (f"{_count(len(run['patterns']), 'exclusion pattern')} read from {project} "
                      f"left {run['dormant']} of {files} outside the build")
    return (f"This run analysed {features} and {scenarios}: {exclusions}, and the {name} analyser "
            f"{_coverage(run['claims'])}.")


def _coverage(claims: int) -> str:
    """The analyser's own coverage, as the count the store holds - never a percentage."""
    if claims == 0:
        return "recorded no claim about any of them"
    return f"recorded {_count(claims, 'claim')} in this run"


def quiet_run_block(run: dict | None) -> list[str]:
    """A run that raised nothing, described as a run - never as a decision somebody took.

    The heading is about the run; the sentence is what it examined; the last section is what it
    could not consult, read from the snapshot's recorded registry. No source is named from today's
    configuration: a snapshot that recorded no registry says exactly that.
    """
    out = ['<h2>No findings in this run</h2>']
    if run is None:
        out.append('<p class="quiet">This case records no run, so there is nothing to describe.</p>')
        return out
    out.append(f'<p>{esc(analysed_sentence(run))}</p>')
    if run.get("assessment") and run["assessment"].get("sentence"):
        out.append(f'<p class="meta">{esc(run["assessment"]["sentence"])}</p>')
    out.append('<h2 class="section">What this run could not consult</h2>')
    out.extend(_blind_spot_lines(run))
    if isinstance(run.get("service_states"), list):
        out.extend(_service_state_lines(run["service_states"]))
    out.extend(could_not_read_lines(run))
    return out


def _blind_spot_lines(run: dict) -> list[str]:
    if not run.get("registry_recorded"):
        # Not "every source was available": this snapshot predates the registry, so nobody recorded
        # what the run could see, and today's declarations are not evidence about that run.
        return ['<p class="quiet">This run recorded no source registry, so it cannot say which '
                'sources it could not consult. Nothing here says the sources it did not have were '
                'clean.</p>']
    if not run.get("assessment_recorded"):
        return ['<p class="quiet">This run recorded its sources but not what this analysis needed, '
                'so it cannot say which of them it could not consult.</p>']
    spots = run.get("blind_spots") or []
    if not spots:
        return ['<p>Its recorded source registry names no source it could not consult.</p>']
    # TESTOPS-42A. An ecosystem is not a source that was never connected: the tests are there and
    # the vocabulary to read them is not. It gets its own lead-in so "not connected" is never said
    # about a repository the run fetched and read.
    unsupported = [spot for spot in spots if spot.get("state") == ECOSYSTEM_UNSUPPORTED]
    absent = [spot for spot in spots
              if spot.get("state") not in (sources.NOT_READABLE, ECOSYSTEM_UNSUPPORTED)]
    unread = [spot for spot in spots if spot.get("state") == sources.NOT_READABLE]
    lines: list[str] = []
    if unsupported:
        lines.append('<p>Written in a vocabulary this run cannot read:</p>')
        lines.extend(f'<p>{esc(_blind_spot_sentence(spot))}</p>' for spot in unsupported)
        lines.append('<p>The files are there and were read; what does not exist is support for '
                     'reading them as steps. Nothing here says they are wrong.</p>')
    if absent:
        lines.append('<p>Not connected when this run looked:</p>')
        lines.extend(f'<p>{esc(_blind_spot_sentence(spot))}</p>' for spot in absent)
        lines.append('<p>They were never consulted, so nothing here says they held nothing \u2014 only '
                     'that this run was never checked against them.</p>')
    if unread:
        # A capability the run consulted and could not read. Not "never consulted", and not a zero.
        lines.append('<p>Could not be read when this run looked:</p>')
        lines.extend(f'<p>{esc(_blind_spot_sentence(spot))}</p>' for spot in unread)
    return lines


def could_not_read_lines(run: dict | None) -> list[str]:
    """What the readers could not read: the surface reader, then every skipped file by kind.

    TESTOPS-41. Two facts a run page has to be able to state, and could not before: that a reader
    could not look at the product's language at all, and which files fell outside the collector's
    kinds. A snapshot that predates the record renders nothing here - inventing "nothing was
    skipped" for it would be the same fault as inventing a zero.
    """
    if not run:
        return []
    out: list[str] = []
    surfaces = run.get("surfaces")
    if isinstance(surfaces, dict) and surfaces.get("state") == "not_assessable":
        reason = surfaces.get("reason") or "the surface reader could not look at this product"
        out.append('<h2 class="section">What the surface reader could not read</h2>')
        out.append(f'<p>{esc(reason)}. No surface was found and none was ruled out.</p>')

    reads = run.get("reads")
    if not isinstance(reads, dict) or not reads:
        return out
    # TESTOPS-43. The list prints for every run that skipped anything, whatever the verdict. It
    # used to print only when it explained a capability the run could not read at all, so a run
    # that skipped 500 `.sql` files and read its code fine said nothing about the 500: the skip was
    # in the store and absent from the page, which is the one combination this section may not
    # have. Each kind carries its count and its reason, and the names sit behind a disclosure.
    #
    # Files passed over by a rule (generated code-behind, vendored libraries) are counted in one
    # quiet line rather than listed: they were not missed, and their names belong in the record.
    skipped = [(role, entry) for role in sorted(reads)
               for entry in ((reads.get(role) or {}).get("skipped") or [])
               if entry.get("reason") != "ignore pattern"]
    ignored = [(role, entry) for role in sorted(reads)
               for entry in ((reads.get(role) or {}).get("skipped") or [])
               if entry.get("reason") == "ignore pattern"]
    if not skipped and not ignored:
        return out
    if skipped:
        skipped.sort(key=lambda item: (-int(item[1].get("count") or 0),
                                       item[1].get("kind") or ""))
        total = sum(int(entry.get("count") or 0) for _role, entry in skipped)
        kinds = len({entry.get("kind") or "" for _role, entry in skipped})
        out.append('<h2 class="section">Files this run could not read</h2>')
        out.append(f'<p>The repositories hold {_count(total, "file")} in {_count(kinds, "kind")} '
                   f'that this run did not fetch. Nothing in this run says what they contain, so '
                   f'nothing here counts them as consulted.</p>')
        for role, entry in skipped:
            files = entry.get("files") or []
            out.append(f'<p><strong>{entry.get("count")} {esc(entry.get("kind") or "")}</strong> in the '
                       f'{esc(role)} repository \u2014 {esc(entry.get("reason") or "")}.</p>')
            if files:
                out.append('<details><summary>Name them</summary><ul>')
                out.extend(f'<li><span class="code">{esc(path)}</span></li>' for path in files)
                out.append('</ul></details>')
    if ignored:
        # Nothing recorded may be silent. These were passed over by a rule rather than missed, so
        # they get a count and no list: their names belong in the record, not on every page.
        passed = sum(int(entry.get("count") or 0) for _role, entry in ignored)
        out.append(f'<p class="quiet">It also passed over {_count(passed, "file")} of generated or '
                   f'vendored code, which this tool never reads.</p>')
    return out


# ---------------------------------------------------------------- the runs view
#
# TESTOPS-34. A case carries a decision about a finding; a run is the record that an analysis
# happened, whether or not it raised anything. Before this, a run that raised nothing was reachable
# only through a `case_` row it should never have had. The run now has its own page and its own
# list, and the two facts stay distinct: a run that raised nothing says "No findings in this run",
# while a run whose findings were all closed by decisions says so and links to the closed cases.

def run_badge(run: dict) -> str:
    """What the run did: raised nothing, raised findings, or raised findings all of them decided."""
    findings = run.get("findings") or 0
    if findings == 0:
        return NO_FINDINGS_LABEL
    total = run.get("case_count")
    decided = run.get("decided_cases")
    if total is None or decided is None:
        raised = run.get("cases") or []
        total = len(raised)
        decided = sum(1 for case in raised if case["state"] in cases.TERMINAL)
    if total and decided >= total:
        return ALL_DECIDED_LABEL
    return _count(findings, "finding")


def run_sentence(run: dict) -> str:
    """One line saying what the run raised, and in how many cases, as the store counts them."""
    findings = run.get("findings") or 0
    raised = run.get("case_count")
    if raised is None:
        raised = len(run.get("cases") or [])
    if findings == 0:
        return "Raised no finding, so it created no case. The run is the record."
    return f"Raised {_count(findings, 'finding')} in {_count(raised, 'case')}."


def _names(items: list[str]) -> str:
    """One name, two names joined by ``and``, three or more with the commas a reader expects."""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def run_sources_sentence(run: dict) -> str:
    """What the run could not consult, in one line - or which absence stops it being said.

    TESTOPS-42A adds the ecosystem to the same sentence, because "we read it as X" is the other
    half of "what we could not consult": a reader who is told only that GitHub was available has
    not been told whether the suite's steps could be read at all.
    """
    read_as = _ecosystem_clause(run)
    if not run.get("registry_recorded"):
        line = "Recorded no source registry, so what it could not consult is unknown."
    elif not run.get("assessment_recorded"):
        line = ("Recorded its sources but not what this analysis needed, so what it could not "
                "consult is unknown.")
    else:
        spots = run.get("blind_spots") or []
        # The ecosystem is not a source that was not connected: it was detected and this build
        # cannot read it, and the ecosystem clause below already says so. Counting it as an
        # unconsulted source would be the mislabel AC4 forbids, in a different sentence.
        spots = [spot for spot in spots if (spot.get("source") or "") != "ecosystem"]
        if not spots:
            line = "Its recorded registry names no source it could not consult."
        else:
            names = [spot.get("title") or spot.get("source") or "a source" for spot in spots]
            line = f"Could not consult {_names(names)}."
    return f"{line} {read_as}" if read_as else line


def _ecosystem_clause(run: dict) -> str:
    """Which ecosystem the test repository was read as, or ``""`` when the snapshot did not say."""
    record = run.get("ecosystems")
    if not isinstance(record, dict):
        return ""
    test = record.get("test")
    if not isinstance(test, dict):
        return ""
    name = test.get("ecosystem") or ""
    if name == "unknown":
        return ("No ecosystem this build recognises was detected in its test repository, so its "
                "tests were read as no particular ecosystem.")
    title = test.get("title") or name
    if test.get("supported") is False:
        return (f"Its tests are written for {title}, which this build has no support for, so no "
                f"claim was made about its steps.")
    return f"Its test repository was read as {title}."


def binding_provenance_block(claim: dict) -> list[str]:
    """What placed this claim, and how to walk from it to the call that does the work (AC4).

    TESTOPS-42C-3. A layer reached through a custom command is only checkable if the reader can
    open the command; this block names the extractor, the step binding's own ``path:line``, the
    chain it followed, and every command's own coordinates.
    """
    detail = claim.get("detail") or {}
    provenance = detail.get("provenance")
    if not isinstance(provenance, dict) or not provenance.get("extractor"):
        return []
    binding = provenance.get("binding")
    if not isinstance(binding, dict):
        return []
    extractor = esc(provenance["extractor"])
    where = esc(f'{binding.get("path")}:{binding.get("line")}')
    layer = esc(binding.get("layer") or "unknown")
    out = [f'<p class="meta"><span class="fn">What placed this claim:</span> the {extractor} '
           f"extractor read the step binding at <span class=\"code\">{where}</span>, which reaches "
           f"the {layer} layer."]
    via = [str(step) for step in binding.get("via") or []]
    if via:
        out.append(f'<p class="meta">The chain it followed: <span class="code">'
                   f'{esc(" then ".join(via))}</span>.</p>')
    for command in binding.get("commands") or []:
        if not isinstance(command, dict):
            continue
        command_where = esc(f'{command.get("path")}:{command.get("line")}')
        reaches = ", ".join(str(token) for token in command.get("via") or [])
        out.append(f'<p class="meta"><span class="code">cy.{esc(command.get("name") or "")}()</span>'
                   f" is defined at <span class=\"code\">{command_where}</span>"
                   f'{f", and its own body reaches {esc(reaches)}" if reaches else ""}.</p>')
    # The scenario's other bindings: the background is where an API command usually sits, and a
    # claim's verdict is a fact about the whole scenario. Only chains that pass through a command
    # are shown - a direct cy.get chain is already above and would repeat.
    own = (binding.get("path"), binding.get("line"), binding.get("pattern"))
    for other in provenance.get("scenario_bindings") or []:
        if not isinstance(other, dict):
            continue
        if (other.get("path"), other.get("line"), other.get("pattern")) == own:
            continue
        commands = [command for command in other.get("commands") or [] if isinstance(command, dict)]
        if not commands:
            continue
        other_where = esc(f'{other.get("path")}:{other.get("line")}')
        out.append(f'<p class="meta">This scenario also runs the step definition at '
                   f'<span class="code">{other_where}</span> ({esc(other.get("pattern") or "")}), '
                   f'which reaches the {esc(other.get("layer") or "unknown")} layer:</p>')
        for command in commands:
            command_where = esc(f'{command.get("path")}:{command.get("line")}')
            reaches = ", ".join(str(token) for token in command.get("via") or [])
            out.append(f'<p class="meta">— <span class="code">cy.{esc(command.get("name") or "")}()</span> '
                       f'at <span class="code">{command_where}</span>'
                       f'{f", and its own body reaches {esc(reaches)}" if reaches else ""}.</p>')
    return out


def analysis_scope_block(run: dict) -> list[str]:
    """What this run placed, what it did not, and why - in the same voice as the other analyzers.

    TESTOPS-42C-3 (AC3). Read from the snapshot's own ``placement`` record, so a page opened
    months later says the same thing. A snapshot without one renders nothing: silence, not a zero.
    """
    placement = run.get("placement")
    if not isinstance(placement, dict):
        # A run that does not place claims (duplication) can still have hit an unreadable
        # declaration. Its cost is visible here too: nothing was claimed for it, and the run says
        # so rather than refusing the suite (AC9).
        unreadable = run.get("unreadable_declarations") or []
        if not unreadable:
            return []
        out = ['<h2 class="section">What this run could not read</h2>',
               f"<p>{_count(len(unreadable), 'declaration')} could not be read. Nothing was "
               f"claimed for {'it' if len(unreadable) == 1 else 'them'}, and the rest of the "
               f"suite was analysed:</p>"]
        for entry in unreadable:
            where = esc(f'{entry.get("path")}:{entry.get("line")}')
            out.append(f'<p class="meta"><span class="code">{where}</span> — '
                       f'{esc(entry.get("reason") or "")}.</p>')
        return out
    extractor = placement.get("extractor") or "the extractor"
    asserting = int(placement.get("asserting") or 0)
    placed = int(placement.get("placed") or 0)
    unplaced = int(placement.get("unplaced") or 0)
    layers = placement.get("layers") or {}
    split = ", ".join(f"{count} {layer}" for layer, count in sorted(layers.items()))
    out = ['<h2 class="section">What this run placed</h2>']
    out.append(f"<p>The suite was read as {esc(extractor)}. Of its {_count(asserting, 'asserting step')}, "
               f"{placed} {'was' if placed == 1 else 'were'} placed on a layer"
               f"{f' ({esc(split)})' if split else ''} and {unplaced} "
               f"matched no step binding.</p>")
    nearly = [pattern for pattern in placement.get("nearly") or [] if pattern]
    if unplaced and nearly:
        quoted = " and ".join(f'<span class="code">{esc(pattern)}</span>' for pattern in nearly[:2])
        out.append(f"<p>The {unplaced} matched no binding because no binding matches these words: "
                   f"they name messages the suite never declared. The two nearest patterns are "
                   f"{quoted}; each unplaced claim is listed below with the step it could not "
                   f"place.</p>")
    unreadable = placement.get("unreadable") or []
    if unreadable:
        out.append(f"<p>{_count(len(unreadable), 'declaration')} could not be read. Nothing was "
                   f"placed for {'it' if len(unreadable) == 1 else 'them'}, and the rest of the "
                   f"suite was analysed:</p>")
        for entry in unreadable:
            where = esc(f'{entry.get("path")}:{entry.get("line")}')
            out.append(f'<p class="meta"><span class="code">{where}</span> — '
                       f'{esc(entry.get("reason") or "")}.</p>')
    else:
        out.append("<p>Every declaration in the suite was readable.</p>")
    return out


# TESTOPS-60 AC2: each group shows this many entries before folding the remainder into a
# disclosure. The threshold is stated on the page whenever it is reached, never silent.
UNPLACED_PREVIEW = 20

# TESTOPS-60 AC1/AC3: the heading and the shared sentence for each shape of failure. The reason
# clause that TESTOPS-57 repeated on every entry lives here, once per group.
UNPLACED_GROUP_COPY = {
    queries.GROUP_NO_BINDING: (
        "No binding matches these words",
        "{these} this in common: no step binding declared by this run matches their words, so no "
        "binding could place the step. Why they were not assessed: no binding matches these "
        "words. The nearest declared patterns shown under a step are the closest ones the suite "
        "declared; none of them matches these words."),
    queries.GROUP_NO_PATTERNS: (
        "This run declared no binding patterns",
        "{these} this in common: the run's snapshot declared no binding patterns at all, so "
        "there was nothing to compare the steps' words with. No nearest patterns are claimed for "
        "these steps, because the run declared none."),
    queries.GROUP_OTHER: (
        "Other reasons",
        "{these} this in common: they were left unplaced for a reason other than the two above."),
}


def _unplaced_entry(entry: dict, *, show_reason: bool = True) -> list[str]:
    """One entry: the step's own words and patterns, under a structural anchor.

    The anchor is the claim id (``#unplaced-claim-<id>``), so deleting an earlier claim cannot
    move it. There is deliberately no ordinal anchor (``#unplaced-<n>``): it was positional, so
    pruning the first claim of a group re-rendered it onto the next claim and silently changed
    what an old citation meant. A link that moves is worse than a link that no longer exists.
    """
    claim_id = entry["id"]
    anchor = f"unplaced-claim-{esc(str(claim_id))}"
    text = entry.get("assertion_text") or entry.get("statement") or ""
    nearest = [pattern for pattern in entry.get("nearly") or [] if pattern]
    out = [f'<li id="{anchor}">',
           f'{verdict_badge({"verdict": "unplaced"})}'
           f'<p class="claimtext">{esc(text)}</p>']
    if entry.get("group") == queries.GROUP_NO_BINDING and nearest:
        quoted = " and ".join(f'<span class="code">{esc(pattern)}</span>' for pattern in nearest)
        out.append(f'<p class="meta">Nearest declared patterns: {quoted}.</p>')
    elif entry.get("group") == queries.GROUP_OTHER and show_reason and entry.get("reason"):
        out.append(f'<p class="meta">Why it was not assessed: {esc(entry["reason"])}.</p>')
    out.append("</li>")
    return out


def unplaced_block(conn, run: dict) -> list[str]:
    """The claims the run could not place, grouped by why, with a disclosure and stable anchors.

    TESTOPS-57. An unplaced claim is the one verdict whose point is "I could not tell", and it is
    the most actionable thing the run produces: the suite and the code do not meet. It does not
    become a case - a case per unplaced claim would bury the real findings in near-identical
    pages - so the run page gives the claims a section of their own instead. The count and the
    entries are both derived from the same list, so the sentence cannot disagree with the list.

    TESTOPS-60. The section groups the claims by shape of failure, states the shared reason once
    per group, and folds each group past ``UNPLACED_PREVIEW`` into a disclosure that says exactly
    how many it holds. At 351 claims the reader sees three headings and three counts before any
    row, not a flat wall.
    """
    entries = queries.unplaced_claims(conn, run["id"])
    if not entries:
        return []
    count = len(entries)
    groups = queries.unplaced_groups(entries)
    out = ['<h2 class="section">What this run could not place</h2>',
           f"<p>{_count(count, 'step')} in this run {'was' if count == 1 else 'were'} not "
           f"assessed. They are not absent from the run: each is a claim the suite recorded but "
           f"could not place, so the tool reached no conclusion about it.</p>"]
    if len(groups) > 1:
        out.append(f"<p class=\"meta\">They fall into {len(groups)} groups; each group states "
                   f"what its steps have in common.</p>")
    for group in groups:
        items = group["entries"]
        title, sentence = UNPLACED_GROUP_COPY[group["key"]]
        these = ("This step has" if len(items) == 1
                 else f"These {len(items)} steps have")
        common = sentence.replace("{these}", these)
        show_reason = True
        if group["key"] == queries.GROUP_OTHER:
            reasons = sorted({entry.get("reason") or "" for entry in items})
            if len(reasons) == 1:
                # One recorded reason for the whole group: state it once here, not on each row.
                common += f" Why they were not assessed: {reasons[0]}."
                show_reason = False
            else:
                common += " Why each was not assessed is stated under its entry."
        out.append(f'<h3 class="unplaced-group">{esc(title)} '
                   f'<span class="meta unplaced-group-count">'
                   f'{_count(len(items), "step")}</span></h3>')
        out.append(f'<p class="unplaced-common">{esc(common)}</p>')
        shown = items[:UNPLACED_PREVIEW]
        hidden = items[UNPLACED_PREVIEW:]
        out.append('<ul class="unplaced">')
        for entry in shown:
            out.extend(_unplaced_entry(entry, show_reason=show_reason))
        out.append("</ul>")
        if hidden:
            out.append(f'<p class="meta">{len(shown)} of {len(items)} shown in this group; '
                       f'the other {len(hidden)} are folded below. Expand the disclosure to '
                       f'read them, or open any entry directly by its anchor '
                       f'(<span class="code">#unplaced-claim-&lt;claim id&gt;</span>).</p>')
            out.append(f'<details class="unplaced-overflow">'
                       f'<summary>Show the other {len(hidden)} of {len(items)} steps in this '
                       f'group</summary><ul class="unplaced">')
            for entry in hidden:
                out.extend(_unplaced_entry(entry, show_reason=show_reason))
            out.append("</ul></details>")
    return out


def ecosystem_block(run: dict) -> list[str]:
    """What each repository was read as, and the counted evidence, on the run's own page (AC2)."""
    record = run.get("ecosystems")
    if not isinstance(record, dict):
        return []
    out: list[str] = []
    for role in ("test", "product"):
        entry = record.get(role)
        if not isinstance(entry, dict):
            continue
        out.append(f'<p class="meta">{esc(_repository_read_as(role, entry))}</p>')
    return out


def _repository_read_as(role: str, entry: dict) -> str:
    """One repository's ecosystem, in the reader's words - with counts, never an adjective."""
    repo = entry.get("repository") or ""
    where = (f"the {role} repository {repo}" if repo else f"the {role} repository")
    name = entry.get("ecosystem") or "unknown"
    evidence = "; ".join(entry.get("evidence") or [])
    if name == "unknown":
        reason = (entry.get("reason") or "").strip().rstrip(".")
        return (f"{where[0].upper()}{where[1:]} was read as no ecosystem this build recognises"
                f"{': ' + reason if reason else ''}.")
    title = entry.get("title") or name
    counted = f" ({evidence})" if evidence else ""
    if entry.get("supported") is False:
        return (f"{where[0].upper()}{where[1:]} is written for {title}{counted}. This build has no "
                f"support for {title}, so it made no claim about its steps.")
    return f"{where[0].upper()}{where[1:]} was read as {title}{counted}."


def product_block(conn, run: dict) -> list[str]:
    """What the product said about this run's claims: two counts, kept apart (TESTOPS-72, AC6).

    A run page that showed only the repeats would hide the claims nobody could judge, and a page
    that added them together would report a blind spot as a finding. A run from before this analysis
    recorded no product reading at all, and says exactly that instead of printing two zeroes.
    """
    evidence = queries.product_evidence(conn, run["id"])
    if not evidence["recorded"]:
        return ['<h2 class="section">What the product says</h2>',
                '<p class="quiet">This run recorded no reading of the product for its claims, so '
                'nothing here says whether any of them repeats work the product already exposes. '
                'That is not a zero.</p>']
    repeats, unconsulted = evidence["repeats"], evidence["unconsulted"]
    out = ['<h2 class="section">What the product says</h2>']
    if repeats:
        out.append(f'<p>{_count(repeats, "claim")} repeat work the product already exposes: each '
                   f'shares a meaningful word with a route the product declares, so a browser check '
                   f'on {"it" if repeats == 1 else "them"} re-verifies what the developer has '
                   f'already published.</p>')
    else:
        out.append('<p>No claim in this run repeats work the product already exposes.</p>')
    if unconsulted:
        out.append(f'<p>{_count(unconsulted, "claim")} needed a browser and the product could not be '
                   f'consulted, so nothing here says whether '
                   f'{"it repeats" if unconsulted == 1 else "they repeat"} it. '
                   f'{"It is" if unconsulted == 1 else "They are"} not counted among the repeats '
                   f'above.</p>')
    elif evidence["matched"] or repeats:
        out.append('<p>Every claim that needed the product could be judged against it.</p>')
    else:
        out.append('<p>No claim in this run needed the product: none of them is settled by a '
                   'browser.</p>')
    return out


def read_counts_block(run: dict) -> list[str]:
    """How many files of each kind each repository gave this run, zeroes included (TESTOPS-55).

    A run page used to say "27 files read" per repository and list skipped files by kind, so a
    reader could not tell an unread kind from a kind that was read and held nothing. Every kind
    this collector reads is named with its count, and ``0`` is a real answer. The skipped list is
    a different section with different words: a kind here is a file the reader opened; a kind
    there is a file it could not.
    """
    entries = run.get("read_counts")
    if not entries:
        return []
    out = ['<h2 class="section">What this run read</h2>',
           '<p class="meta">Files this run read, per repository and per kind. A 0 is a kind this '
           'reader handles and that repository holds none of. Files it could not read are '
           'counted in their own section further down the page.</p>']
    for entry in entries:
        role = entry.get("role") or "repository"
        repo = entry.get("repository") or ""
        where = f'the {esc(role)} repository' + (f' ({esc(repo)})' if repo else '')
        out.append(f'<p>From {where} it read {_kind_counts(entry.get("counts") or {})}.</p>')
    return out


def _kind_counts(counts: dict) -> str:
    """Kinds with their counts, biggest first, zeroes last, each kind carrying its unit."""
    order = {kind: index for index, kind in enumerate(counts)}
    ranked = sorted(counts.items(), key=lambda item: (-int(item[1]), order[item[0]]))
    return _names([_count(int(n), f"{kind} file") for kind, n in ranked])


def runs_index(conn) -> bytes:
    """Every run in the store, newest first - the view a run that raised nothing is reachable from."""
    rows = queries.list_runs(conn)
    body = ['<h1>TestOps runs</h1>', '<p class="meta"><a href="/">← all cases</a></p>']
    if not rows:
        body.append('<p class="quiet">No runs are recorded in this store, so nothing has been '
                    'analysed.</p>')
        return page("TestOps · runs", "".join(body))
    body.append('<ul class="cases">')
    for run in rows:
        badge = run_badge(run)
        badge_class = badge_classes(badge, badge not in QUIET_RUN_BADGES)
        versions = versions_text(run.get("versions"))
        body.append(
            f'<li><a href="/run/{esc(run["id"])}">'
            f'<div><span class="{badge_class}">{esc(badge)}</span> '
            f'<span class="meta">{esc(run["project"])} · '
            f'{esc(analyser_text(run.get("analyser")))} · '
            f'{_count(run.get("claims") or 0, "claim")} · '
            f'{esc(age(run.get("finished_at")))}'
            f'{" at " + esc(versions) if versions else ""}</span></div>'
            f'<p class="claimtext">{esc(run_sentence(run))}</p>'
            f'<p class="meta">{esc(run_sources_sentence(run))} '
            f'<span class="code">{esc(run["id"])}</span></p></a></li>')
    body.append("</ul>")
    return page("TestOps · runs", "".join(body))


def _case_line(conn, case: dict) -> str:
    """One case on the run page: what it asserts, its badge, and the way in."""
    shown = display_state(case["state"], case["findings"])
    badge_class = badge_classes(shown, shown in HOT_STATES)
    text = (queries.case_assertion(conn, case["id"]) or queries.case_statement(conn, case["id"])
            or "No claim recorded for this case.")
    return (f'<li><a href="/case/{esc(case["id"])}">'
            f'<div><span class="{badge_class}">{esc(shown)}</span> '
            f'<span class="meta">{_count(case["findings"], "finding")} · '
            f'{esc(age(case["created_at"]))} · '
            f'<span class="code">{esc(case["id"])}</span></span></div>'
            f'<p class="claimtext">{esc(text)}</p></a></li>')


def run_response(conn, run_id: str) -> tuple[bytes, int]:
    """The page for a run id, with the status it must be served under.

    This is the page TESTOPS-22 built, addressed by the thing it describes. A run that raised
    nothing renders the same honest block - what it examined, at which commit, and what it could
    not consult - and says why there is no case to open. A run that raised findings lists its
    cases, and a run whose cases were all decided says so: a closed finding is not a quiet run.
    """
    run = queries.run_read(conn, run_id)
    if run is None:
        return stale_run_page(run_id), 404
    # A run naming an analyser this build cannot run is not evidence about the code (TESTOPS-35):
    # its claims are not an argument anything here could make, so the page says which analyser it
    # named rather than presenting its rows as a result.
    if not is_registered(run.get("analyser")):
        return stale_run_page(run_id, run.get("analyser")), 404

    versions = versions_text(run.get("versions"))
    badge = run_badge(run)
    badge_class = badge_classes(badge, badge not in QUIET_RUN_BADGES)
    body = ['<p class="meta"><a href="/">← all cases</a> · '
            '<a href="/runs">all runs</a></p>',
            f'<h1>{esc(run["project"])} · {esc(analyser_text(run.get("analyser")))}</h1>',
            f'<p class="meta"><span class="{badge_class}">{esc(badge)}</span>'
            f' · Ran {esc(age(run.get("finished_at")))}'
            f'{" at " + esc(versions) if versions else ""}'
            f' · <span class="code">{esc(run_id)}</span></p>']
    body.extend(ecosystem_block(run))
    body.extend(read_counts_block(run))
    body.extend(analysis_scope_block(run))
    body.extend(product_block(conn, run))
    body.extend(unplaced_block(conn, run))

    if not (run.get("findings") or 0):
        # The TESTOPS-22 page, unchanged: the run described as a run.
        body.extend(quiet_run_block(run))
        body.append('<p>A case carries a decision about a finding. This run raised none, so it '
                    'created no case: the run itself is the record, and it stays in the store '
                    'with the counts above.</p>')
    else:
        body.append(f'<h2>This run raised {_count(run["findings"], "finding")}</h2>')
        body.append(f'<p>{esc(analysed_sentence(run))}</p>')
        raised = run.get("cases") or []
        if raised:
            body.append('<ul class="cases">')
            body.extend(_case_line(conn, case) for case in raised)
            body.append("</ul>")
            if all(case["state"] in cases.TERMINAL for case in raised):
                body.append('<p>Every case this run raised has been decided, so its findings are '
                            'closed. The run still recorded them: a closed finding is evidence, '
                            'not a clean bill.</p>')
        body.append('<h2 class="section">What this run could not consult</h2>')
        body.extend(_blind_spot_lines(run))
        if isinstance(run.get("service_states"), list):
            body.extend(_service_state_lines(run["service_states"]))
        body.extend(could_not_read_lines(run))
    return page(f"TestOps · {run_id}", "".join(body)), 200


def run_page(conn, run_id: str) -> bytes:
    """The run page as bytes. Always a page: an id the store does not hold has one too."""
    return run_response(conn, run_id)[0]


def stale_run_page(run_id: str, unregistered_analyser: str | None = None) -> bytes:
    """A run id the store no longer holds, answered with the reason retention gives for cases."""
    body = ['<p class="meta"><a href="/">← all cases</a> · <a href="/runs">all runs</a></p>',
            '<h1>This run is no longer in the store</h1>',
            f'<p>The run <span class="code">{esc(run_id)}</span> is not in the store any more.</p>']
    if unregistered_analyser is not None:
        body.extend([
            f'<p>It was recorded under the analyser <span class="code">'
            f'{esc(unregistered_analyser)}</span>, which is not one this build can run. A run is '
            'evidence about the code only when an analyser here produced it, so a row naming an '
            'analyser nobody has is not rendered. Nothing it said should be acted on.</p>',
            '<p>If it is still in the store it was written by something other than this analysis '
            '- a review harness or a hand-written row - and '
            '<span class="code">testops scrub-fixtures</span> reports and removes it.</p>'])
    else:
        body.extend([
            '<p>Its evidence was pruned by retention. A run lives with the snapshot its claims '
            'were raised from, and retention deletes snapshots outside the keep window '
            '(<span class="code">retention --prune --keep N</span>). The run, its claims and its '
            'cases went together, so there is nothing left to render.</p>',
            '<p>An id that was never in the store reads the same way: the store keeps no record '
            'of what it has deleted, so it cannot tell a pruned id from one it never held.</p>'])
    return page(f"TestOps · {run_id}", "".join(body))


def decision_block(decision: dict | None) -> list[str]:
    """The decision a person recorded, with who made it, when, and their note.

    "Resolved" is reachable only from here, and only from a stored ``case_state`` row whose state
    is ``resolved``. The sentence says what the decision was about, so a reader cannot take it for
    a statement about the run (TESTOPS-22, AC2).
    """
    if decision is None:
        return []
    state = decision["state"]
    label = STATE_LABEL.get(state, state)
    actor = decision["actor"]
    when = age(decision["at"])
    note = (decision["note"] or "").strip()
    if state == "resolved":
        sentence = f"Resolved by {actor} {when}."
    elif state == "false_positive":
        sentence = f"Judged not a real finding by {actor} {when}."
    elif state == "needs_fix":
        sentence = f"Marked as needing a fix by {actor} {when}."
    elif state == "open":
        sentence = f"Reopened by {actor} {when}."
    else:
        sentence = f"Set to {label.lower()} by {actor} {when}."
    # Built outside the f-string expression: 3.11 serves this UI and rejects a backslash inside one.
    quote = "\u201c" + note + "\u201d."
    if note:
        sentence += f" The note recorded with that decision: {quote}"
    else:
        sentence += " No note was recorded with that decision."
    if state in cases.TERMINAL:
        sentence += (" This is a decision about the findings in this case; it did not change what "
                     "the run analysed.")
    return [f'<h2>{esc(label)}</h2>', f'<p>{esc(sentence)}</p>']


def decision_form(conn, row: dict, case_id: str, findings: list[dict], analyser: str) -> list[str]:
    """The decision, at the end of the argument. One case, one decision, and it says what it hides."""
    n = len(findings)
    suppressed_here = conn.execute(
        """SELECT s.state, s.actor, s.at, s.note FROM suppression s
           JOIN finding f ON f.fingerprint = s.fingerprint WHERE f.case_id = ?
           ORDER BY s.at DESC LIMIT 1""", (case_id,)).fetchone()
    terminal = row["state"] in cases.TERMINAL
    out: list[str] = []

    if n and terminal:
        d = suppressed_here
        # Built outside the f-string: a backslash inside an f-string expression is a SyntaxError
        # before Python 3.12, and 3.11 is the interpreter that serves this UI (TESTOPS-13).
        note_suffix = esc(" \u2014 " + d["note"]) if d and d["note"] else ""
        out.append(f'<form class="decide" method="post" action="/case/{esc(case_id)}/state">')
        out.append(f'<p><strong>Suppressed</strong> \u2014 {n} finding{"s" if n != 1 else ""} in '
                   f'this case {"are" if n != 1 else "is"} hidden from future runs'
                   f'{esc(" (" + (d["actor"] if d else "") + ", " + age(d["at"]) + ")") if d else ""}'
                   f'{note_suffix}.</p>')
        out.append('<p><button name="state" value="open">Reopen \u2014 report this again</button></p>')
        out.append('<p class="quiet">Reopening deletes the suppression for this case, so the next '
                   'run raises it again. No other case is affected.</p>')
        out.append("</form>")
    elif n:
        out.append(f'<form class="decide" method="post" action="/case/{esc(case_id)}/state">')
        out.append(f'<p><strong>Decide this case</strong> \u2014 {n} finding'
                   f'{"s" if n != 1 else ""} ride{"s" if n == 1 else ""} on this decision, and it '
                   f'applies to this case only.</p>')
        out.append('<p><input type="text" name="note" placeholder="Why? (optional, shown next time)"></p>')
        out.append('<p>'
                   '<button name="state" value="needs_fix">Needs a fix</button> '
                   '<button class="term" name="state" value="resolved">Resolved \u2014 stop reporting</button> '
                   '<button class="term" name="state" value="false_positive">Not a real finding \u2014 stop reporting</button>'
                   '</p>')
        out.append('<p class="warn">Resolved and \u201cnot a real finding\u201d hide this evidence '
                   'from future runs, for this case only. You can reopen the case later; reopening '
                   'deletes the suppression and makes it report again.</p>')
        out.append("</form>")
    elif terminal:
        out.append(f'<form class="decide" method="post" action="/case/{esc(case_id)}/state">'
                   '<p><button name="state" value="open">Reopen this case</button></p>'
                   '<p class="quiet">Reopening deletes the suppression, so the next run reports it '
                   'again.</p></form>')
    if n:
        # The contract of *this* decision, in the words of the analyser that raised the case
        # (TESTOPS-47). A duplication case and a level-fitness case have different identities, so
        # there is no global sentence here and no fallback: the declaring analyser's own sentence
        # or nothing. A reader must not need the ticket to understand a re-ask.
        out.append(f'<p class="quiet">{esc(cover(analyser))}</p>')
    return out


def footnote(claims: list[dict]) -> list[str]:
    """The only place a code is allowed, and it says what it is: shorthand for debugging."""
    codes = sorted({c["interaction_code"] for c in claims if c["interaction_code"]})
    verdicts = sorted({c["verdict"] for c in claims if c["verdict"]})
    if not (codes or verdicts):
        return []
    parts = []
    if codes:
        parts.append("interaction " + ", ".join(codes))
    if verdicts:
        parts.append("verdict " + ", ".join(verdicts))
    return [f'<p class="code footnote">Debugging shorthand, not part of the finding: '
            f'{esc("; ".join(parts))}.</p>']


def stale_case_page(case_id: str, unregistered_analyser: str | None = None) -> bytes:
    """A case id the store no longer holds.

    Retention deletes a snapshot together with the cases that rest on it (TESTOPS-24), so a
    bookmark or a link in an old report outlives the evidence. Answering that request with a
    page that names the id and says why the evidence is gone is the whole job here; a caller
    rendering this must never get an exception or an empty page (TESTOPS-30).

    A case whose analyser this build does not know is answered with the same page (TESTOPS-35):
    the row may still be in the store, but nothing here could have raised it, so its argument is
    not the store's to make. Saying "pruned by retention" about that row would be false, so the
    explanation changes while the heading, the status and the way back do not.
    """
    body = [f'<p class="meta"><a href="/">\u2190 all cases</a></p>',
            '<h1>This case is no longer in the store</h1>',
            f'<p>The case <span class="code">{esc(case_id)}</span> is not in the store any '
            'more.</p>']
    if unregistered_analyser is not None:
        body.extend([
            f'<p>It was recorded under the analyser <span class="code">'
            f'{esc(unregistered_analyser)}</span>, which is not one this build can run. A case is '
            'a finding an analyser raised, so a row naming an analyser nobody has is not a claim '
            'about the code and is not rendered. Nothing it said should be acted on.</p>',
            '<p>If it is still in the store it was written by something other than this analysis '
            '- a review harness or a hand-written row - and '
            '<span class="code">testops scrub-fixtures</span> reports and removes it.</p>'])
    else:
        body.extend([
            '<p>Its evidence was pruned by retention. A case lives with the snapshot its '
            'findings were raised from, and retention deletes snapshots outside the keep window '
            '(<span class="code">retention --prune --keep N</span>). The case, its '
            'findings and the run that raised it went together, so there is nothing left to '
            'render.</p>',
            '<p>An id that was never in the store reads the same way: the store keeps no record '
            'of what it has deleted, so it cannot tell a pruned id from one it never '
            'held.</p>'])
    return page(f"TestOps \u00b7 {case_id}", "".join(body))


def case_response(conn, case_id: str) -> tuple[bytes, int]:
    """The page for a case id, with the status it must be served under.

    A pruned case answers 404 with an explanatory page rather than ``None``: the web layer had
    to invent a status for ``None``, and every other caller crashed on it (TESTOPS-30).
    """
    row = queries.case_row(conn, case_id)
    if not row:
        return stale_case_page(case_id), 404
    # A case naming an analyser this build does not have cannot be an argument about the code
    # (TESTOPS-35): nothing here could have raised it, so its row is treated exactly like an id
    # the store does not hold and the page says which analyser it named.
    if not is_registered(row["analyser"]):
        return stale_case_page(case_id, row["analyser"]), 404
    findings = queries.finding_rows(conn, case_id)
    claims = [c for f in findings for c in f["claims"]]
    versions = versions_text(row["versions"])
    decision = queries.latest_decision(conn, case_id)
    run = queries.run_analysis(conn, case_id)
    state_label = case_badge(decision, len(findings))

    body = [f'<p class="meta"><a href="/">\u2190 all cases</a> \u00b7 '
            f'<a href="/runs">all runs</a></p>',
            f'<h1>{esc(row["project"])} \u00b7 {esc(analyser_text(row["analyser"]))}</h1>']
    badge_class = badge_classes(state_label, state_label in HOT_STATES)
    body.append(f'<p class="meta"><span class="{badge_class}">'
                f'{esc(state_label)}</span>'
                f' \u00b7 Analysed {esc(age(row["created_at"]))}'
                f'{" at " + esc(versions) if versions else ""}</p>')

    # A case row can outlive its run: retention deletes them together today, but a hand-imported
    # row or a future change to that path leaves the case and not the run. The link is therefore
    # emitted only when the store still holds the run; otherwise the page names the run and says it
    # is gone, so a 200 page never points at a 404 (TESTOPS-54 review, the unguarded run link).
    run_present = bool(row.get("run_id")) and queries.run_read(conn, row["run_id"]) is not None

    if findings and row.get("run_id"):
        # AC1 of TESTOPS-54: the case's own run, named by the link, not a bare "back". The run
        # index says which runs exist; this says which one raised the case under a reader's eyes.
        run_id = row["run_id"]
        if run_present:
            body.append(f'<p class="meta">Raised by the run '
                        f'<a href="/run/{esc(run_id)}">{esc(run_id)}</a>'
                        f' <span class="quiet">\u2014 what that run analysed, and what it could not '
                        f'consult.</span></p>')
        else:
            body.append(f'<p class="meta">Raised by the run '
                        f'<span class="code">{esc(run_id)}</span>'
                        f' <span class="quiet">\u2014 which is not in the store any more, so what it '
                        f'analysed, and what it could not consult, cannot be read.</span></p>')

    if not findings:
        # A run that raised nothing is described as a run: what it examined, and what it could not
        # consult. It is never called resolved - that word belongs to a person's recorded decision,
        # which is rendered beside it when one exists (TESTOPS-22).
        #
        # Since TESTOPS-34 this row is not a case: it carries no finding, so it is absent from every
        # case list. The run is the record, and its page is the way in. The row stays where it is -
        # the URL that was shared still explains what it was - and this line names where to go.
        if row.get("run_id"):
            if run_present:
                body.append(f'<p class="meta">This row raised no finding, so it is not a case. '
                            f'The run it recorded is <a href="/run/{esc(row["run_id"])}">'
                            f'{esc(row["run_id"])}</a>.</p>')
            else:
                body.append(f'<p class="meta">This row raised no finding, so it is not a case. '
                            f'The run it recorded is <span class="code">{esc(row["run_id"])}'
                            f'</span>, which is not in the store any more.</p>')
        body.extend(quiet_run_block(run))
    if decision is not None:
        body.extend(decision_block(decision))
    next_section = 1
    if findings:
        # Each claim opens with a scan block: the judgement as a headline, one sentence saying
        # what is wrong, and the action on its own line (TESTOPS-26). The evidence follows below,
        # and the step is quoted once, in monospace, inside the block.
        for i, f in enumerate(findings, start=1):
            if len(findings) > 1:
                body.append(f'<h2>Finding {i} of {len(findings)}</h2>')
            for j, c in enumerate(f["claims"], start=1):
                if len(f["claims"]) > 1:
                    body.append(f'<h3>Claim {j} of {len(f["claims"])}</h3>')
                sections, next_section = claim_sections(c)
                body.extend(sections)

    form = decision_form(conn, row, case_id, findings, row["analyser"])
    if form:
        body.append(f'<h2 class="section">{next_section}. Decision</h2>' if findings
                    else "<h2>Decision</h2>")
        body.extend(form)
    body.extend(footnote(claims))
    return page(f"TestOps \u00b7 {case_id}", "".join(body)), 200


def case_page(conn, case_id: str) -> bytes:
    """The case page as bytes. Always a page: a pruned id has one too, served with 404."""
    return case_response(conn, case_id)[0]


# ---------------------------------------------------------------- configuration

def _form(payload: dict, key: str, default: str = "") -> str:
    return (payload.get(key) or [default])[0].strip()


# TESTOPS-56 AC4. The fields this form understands, split into the ones that ride along with every
# service (and are not settings) and the ones that become a service's settings. A key outside these
# sets is *refused*, never dropped: the whitelist that used to build this dict made the screen safe
# only by accident, and a refactor that forwarded unknown keys would have bypassed it with no test
# failing. The refusal says so, and says nothing about the value.
_FORM_FIELDS = frozenset({"project", "type", "role", "name", "slug"})
_SETTINGS_FIELDS = frozenset({"repo", "board", "host", "org", "ado_project", "pipeline_id"})


def _settings_from_form(kind: str, payload: dict) -> dict:
    """The settings a service row may hold, from the fields a person actually typed.

    Repositories, board keys, hosts and paths - never a credential. :func:`services.validate_settings`
    is the guard, and it runs on every submitted settings value here, whether or not this kind stores
    it, so a value cannot reach the store - or quietly evaporate - without having been screened.
    A field this form does not know is refused rather than discarded (TESTOPS-56 AC4).
    """
    unknown = sorted(key for key in payload if key not in _FORM_FIELDS | _SETTINGS_FIELDS)
    if unknown:
        raise services.ConfigError(
            f"settings field {unknown[0]!r} is not a field this form knows, so the configuration was "
            f"refused rather than saved without it: an unrecognised field would be stored unscreened "
            f"or dropped unrecorded, and neither is a configuration. Remove it, or add the field and "
            f"its screen together.")
    for name in sorted(_SETTINGS_FIELDS):
        if name in payload:
            value = _form(payload, name)
            if value:
                services.validate_settings({name: value})
    if kind == "git_repo":
        return {"repo": _form(payload, "repo")}
    if kind == "jira_board":
        settings = {"board": _form(payload, "board")}
        host = _form(payload, "host")
        if host:
            settings["host"] = host
        return settings
    settings = {"org": _form(payload, "org"), "project": _form(payload, "ado_project")}
    pipeline = _form(payload, "pipeline_id")
    if pipeline:
        if not pipeline.isdigit():
            raise services.ConfigError("settings.pipeline_id must be a whole number")
        settings["pipeline_id"] = int(pipeline)
    return settings


def _service_form(action: str, project: str, service: dict | None = None) -> list[str]:
    """The add/edit form. One form for both, because they are the same configuration decision."""
    s = service or {}
    settings = s.get("settings") or {}
    kind = s.get("type") or "git_repo"
    options = "".join(
        f'<option value="{value}"{" selected" if kind == value else ""}>{label}</option>'
        for value, label in (("git_repo", "git repository"), ("jira_board", "Jira board"),
                             ("ado_pipeline", "Azure DevOps pipeline")))
    role = s.get("role") or "test"
    roles = "".join(
        f'<option value="{value}"{" selected" if role == value else ""}>{value}</option>'
        for value in services.ROLES)
    return [
        f'<form method="post" action="{esc(action)}">',
        f'<input type="hidden" name="project" value="{esc(project)}">',
        f'<label>Type <select name="type">{options}</select></label> ',
        f'<label>Role <select name="role"><option value=""{" selected" if not role else ""}>'
        f'(none)</option>{roles}</select></label> ',
        f'<label>Name <input name="name" value="{esc(s.get("name", ""))}" required></label><br>',
        f'<label>Repository <input name="repo" placeholder="owner/name" '
        f'value="{esc(settings.get("repo", ""))}"></label> ',
        f'<label>Board key <input name="board" value="{esc(settings.get("board", ""))}"></label> ',
        f'<label>Jira host <input name="host" value="{esc(settings.get("host", ""))}"></label><br>',
        f'<label>ADO organisation <input name="org" value="{esc(settings.get("org", ""))}"></label> ',
        f'<label>ADO project <input name="ado_project" '
        f'value="{esc(settings.get("project", ""))}"></label> ',
        f'<label>Pipeline id <input name="pipeline_id" '
        f'value="{esc(settings.get("pipeline_id", ""))}"></label><br>',
        '<p class="quiet">Hosts, repository coordinates, board keys and paths only. A token, '
        'password or key is refused: secrets resolve from the environment when the connector '
        'runs.</p>',
        '<button type="submit">Save service</button></form>',
    ]


def config_error(exc: Exception) -> bytes:
    body = ['<p class="meta"><a href="/config">\u2190 configuration</a></p>',
            '<h1>That configuration was not saved</h1>',
            f'<p>{esc(exc)}</p>']
    return page("TestOps \u00b7 configuration refused", "".join(body))


def config_page(conn) -> bytes:
    """Projects and services, and the forms that change them (AC3).

    Every change is a row written in this request and read by the next one: nothing is cached, so
    adding a service or a whole project needs no code change and no restart. There is deliberately
    no login - this is a local tool - but the secret refusal is here, because it protects a harm.
    """
    projects = services.list_projects(conn)
    body = ['<p class="meta"><a href="/">\u2190 all cases</a> \u00b7 '
            '<a href="/runs">all runs</a></p>',
            '<h1>Projects and services</h1>',
            '<p>A project is a grouping: a display name and a slug. Its services are the resources '
            'an analysis can consult - git repositories, a Jira board, Azure DevOps pipelines. '
            'Adding one here is configuration; runs and cases keep their project slug.</p>',
            '<h2 class="section">Add a project</h2>',
            '<form method="post" action="/config/projects">'
            '<label>Slug <input name="slug" placeholder="cotw" required></label> '
            '<label>Name <input name="name" placeholder="Children of the Old War"></label> '
            '<button type="submit">Add project</button></form>']
    if not projects:
        body.append('<p class="quiet">No projects are configured in this store yet.</p>')
    for project in projects:
        slug = project["slug"]
        rows = services.list_services(conn, slug)
        body.append(f'<h2 class="section">{esc(project["name"])} '
                    f'<span class="meta">{esc(slug)}</span></h2>')
        if not rows:
            body.append('<p class="quiet">This project has no services yet.</p>')
        for service in rows:
            state = service.last_state or "not yet consulted"
            role = f" \u00b7 {service.role}" if service.role else ""
            reason = f' \u2014 {esc(service.last_reason)}' if service.last_reason else ""
            body.append('<details><summary>'
                        f'<strong>{esc(service.name)}</strong> '
                        f'<span class="meta">{esc(service.type)}{esc(role)} \u00b7 '
                        f'last state: {esc(state)}{reason}</span></summary>')
            body.extend(_service_form(f"/config/service/{service.id}", slug,
                                      {"id": service.id, "type": service.type,
                                       "role": service.role, "name": service.name,
                                       "settings": service.settings}))
            body.append(f'<form method="post" action="/config/service/{service.id}/delete">'
                        f'<button type="submit">Remove this service</button></form></details>')
        body.append('<h3>Add a service</h3>')
        body.extend(_service_form("/config/services", slug))
        # TESTOPS-51 AC6: a project can be removed from the page that made it, but only while it
        # holds no evidence. The control says what it removes; the store refuses otherwise, naming
        # the counts, so the rule does not depend on this page rendering it.
        counts = services.evidence_counts(conn, slug)
        held = ", ".join(f"{n} {name}" for name, n in counts.items() if n)
        held_note = f"; this project holds {esc(held)}" if held else ""
        body.append(f'<form method="post" action="/config/project/{esc(slug)}/delete">'
                    f'<button type="submit">Delete this project and its services</button> '
                    f'<span class="quiet">Runs, snapshots and cases are never deleted here'
                    f'{held_note}.</span></form>')
    return page("TestOps \u00b7 configuration", "".join(body))


def _service_from_payload(conn, payload: dict, service_id: int | None = None):
    kind = _form(payload, "type")
    role = _form(payload, "role")
    name = _form(payload, "name")
    settings = _settings_from_form(kind, payload)
    if service_id is None:
        return services.add_service(conn, _form(payload, "project"), kind, role, name, settings)
    return services.update_service(conn, service_id, kind=kind, role=role, name=name,
                                   settings=settings)


# The addresses only a form posts to. They are real addresses, so a GET on one answers 405 - the
# page exists, the method does not - rather than 404: a dead-end sweep has to be able to tell "a
# form posts here" from "no such page" (TESTOPS-54 review, AC4's blindness to form actions).
CONFIG_POSTS = tuple(re.compile(p) for p in (
    r"/config/projects", r"/config/services", r"/config/service/\d+",
    r"/config/service/\d+/delete", r"/config/project/[^/]+/delete"))
CASE_POST = re.compile(r"/case/([^/]+)/state")
POST_ONLY = CONFIG_POSTS + (CASE_POST,)


class Handler(BaseHTTPRequestHandler):
    server_version = "TestOps/0.1"

    def log_message(self, fmt, *a):          # quiet by default; the terminal is not the UI
        pass

    def _send(self, body: bytes, code: int = 200, headers: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _not_found(self):
        self._send(page("Not found", '<h1>TestOps</h1><p>No such case.</p>'
                                     '<p><a href="/">\u2190 all cases</a></p>'), 404)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        conn = db.connect()
        try:
            if path == "/":
                self._send(index(conn))
                return
            if path == "/runs":
                self._send(runs_index(conn))
                return
            if path == "/config":
                self._send(config_page(conn))
                return
            m = re.fullmatch(r"/case/([^/]+)", path)
            if m:
                body, code = case_response(conn, urllib.parse.unquote(m.group(1)))
                self._send(body, code)
                return
            m = re.fullmatch(r"/run/([^/]+)", path)
            if m:
                body, code = run_response(conn, urllib.parse.unquote(m.group(1)))
                self._send(body, code)
                return
            if any(p.fullmatch(path) for p in POST_ONLY):
                self._send(page("Method not allowed",
                                '<h1>TestOps</h1><p>This address answers a form, not a page.</p>'),
                           405, {"Allow": "POST"})
                return
            self._not_found()
        finally:
            conn.close()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        length = int(self.headers.get("Content-Length") or 0)
        payload = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
        if path == "/config/projects" or path == "/config/services" \
                or re.fullmatch(r"/config/service/\d+", path) \
                or re.fullmatch(r"/config/service/\d+/delete", path) \
                or re.fullmatch(r"/config/project/[^/]+/delete", path):
            self._config_post(path, payload)
            return
        m = re.fullmatch(r"/case/([^/]+)/state", path)
        if not m:
            self._not_found()
            return
        state = (payload.get("state") or [""])[0]
        note = (payload.get("note") or [""])[0]
        case_id = urllib.parse.unquote(m.group(1))
        conn = db.connect()
        try:
            cases.set_state(conn, case_id, state, "harry", note)
        except ValueError as exc:
            self._send(page("Rejected", f'<h1>TestOps</h1><p>{esc(exc)}</p>'), 400)
            return
        finally:
            conn.close()
        # Post/redirect/get: a refresh must not re-apply the decision.
        self._send(b"", 303, {"Location": f"/case/{urllib.parse.quote(case_id)}"})

    def _config_post(self, path: str, payload: dict) -> None:
        """Apply one configuration change and redirect. A refusal is a page, not a traceback."""
        conn = db.connect()
        try:
            if path == "/config/projects":
                services.add_project(conn, _form(payload, "slug"), _form(payload, "name"))
            elif re.fullmatch(r"/config/project/[^/]+/delete", path):
                # TESTOPS-51 AC6. The slug is the identity in the path, so it is unquoted, not
                # re-derived from a form field a caller could swap.
                services.remove_project(
                    conn, urllib.parse.unquote(path.split("/")[3]))
            elif path == "/config/services":
                _service_from_payload(conn, payload)
            else:
                service_id = int(re.fullmatch(r"/config/service/(\d+)(?:/delete)?", path).group(1))
                if path.endswith("/delete"):
                    services.remove_service(conn, service_id)
                else:
                    _service_from_payload(conn, payload, service_id)
        except (services.ConfigError, ValueError, KeyError) as exc:
            self._send(config_error(exc), 400)
            return
        finally:
            conn.close()
        self._send(b"", 303, {"Location": "/config"})


def serve(port: int = 8787, host: str = "127.0.0.1") -> None:
    db.connect().close()                     # create the schema before the first request
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"TestOps UI on http://{host}:{port}", flush=True)
    httpd.serve_forever()
