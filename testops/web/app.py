"""The smallest web surface that lets a person verify a finding and decide on it.

Two screens. Server-rendered HTML, one form, no JavaScript, nothing behind a disclosure.

The case page is one argument, said once, in the order a reader needs it (TESTOPS-23). The page used
to be six sections that narrated the analysis: the claim restated three times, a numbered section on
where a scenario's name came from, sentences about "the words" a rule had read, and fragment
headings such as "What settles it." A reader had to rebuild the argument from the tool's own
vocabulary, which is what the Product Owner meant by "the verbiage is still not right".

What the page says now:

  1. a scan block - the judgement as a headline, one sentence saying what is wrong, and one line
     saying what to do, on its own row so the eye lands on it; then the quote's provenance
  2. the step that is asserted - the feature file around it and the definition that runs it
  3. the other steps in this scenario, for context - never presented as evidence
  4. what could not be checked - the sources that were never connected
  5. the decision

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

from .. import cases, queries, sources
from ..extract.stepbindings import LAYER_ORDER
from ..store import db

# What is true of each verdict, as a reader meets it (TESTOPS-23, AC7). The old vocabulary named an
# absence - "Browser not needed", "Never actually proved" - and left the reader to invert it into a
# cost. These name the state of the claim; a gap's label names the one instrument the assertion needs
# and the test does not run, because that is what makes it a gap rather than a shortfall.
VERDICT_LABEL = {
    "distinct": "Checked",
    "review": "Checked, but over-tested for what it asserts",
    "gap": "Not proved \u2014 nothing runs a browser",
    "duplicate": "Checked, but this repeats another test",
    "unplaced": "Cannot tell",
}
STATE_LABEL = {"open": "Open", "needs_fix": "Needs a fix", "resolved": "Resolved",
               "false_positive": "Not a real finding"}
# A run that raised nothing is a fact about the code, not a decision about it. It gets its own
# label so no screen can borrow the word a person's decision owns (TESTOPS-22).
NO_FINDINGS_LABEL = "No findings"

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
p.judgement strong.verdict.hot { color:var(--bad); }
p.wrong { margin:0 0 .85rem; font-size:1.06rem; line-height:1.6; }
p.action { margin:0; padding:.6rem .8rem; background:#f6f4f0; border-radius:5px;
           font-weight:600; line-height:1.5; }
p.action .act { display:inline-block; margin-right:.55rem; font-size:.72rem; font-weight:700;
                letter-spacing:.09em; text-transform:uppercase; color:var(--accent); }
code.ident { font-family: ui-monospace, Consolas, monospace; font-size:.9em; background:#f3f1ec;
             padding:.05em .25em; border-radius:3px; white-space:nowrap; }
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


def page(title: str, body: str) -> bytes:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head>
<body><main>{body}</main></body></html>""".encode("utf-8")


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
    if match and match.group(2).strip() == text.strip():
        keyword = match.group(1)
        if keyword in ("And", "But"):
            keyword = "Then"
        return f"{keyword} {match.group(2).strip()}"
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


def action_line(claim: dict, step: str | None) -> str:
    """The action as one line a reader can act on: the stored first clause, and nothing after it.

    The store keeps one string with the action in its first clause and the argument's conclusion
    in the clauses after a semicolon. The opening block already states the argument, so the tail
    is dropped here instead of restating it (TESTOPS-26, AC3). "No change" is an action: a
    distinct claim says plainly that nothing needs doing.
    """
    action = (claim.get("proposed_action") or "").strip()
    if not action:
        return "No proposed action was recorded for this claim."
    raw_step = (claim.get("provenance") or {}).get("assertion_text") or step
    action = _without_step(action, raw_step)
    first = action.split("; ")[0].strip().rstrip(".")
    return first + "."


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
            return f"The test asserts {_step_quote(quote)}, but {rich_prose(_lower_first(sentence))}"
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
        return f"The test asserts {q}, and {fact}."
    if verdict == "duplicate":
        return (f"The test asserts {q}, but another scenario in this run already asserts the same "
                f"thing, so the project runs it twice.")
    if verdict == "unplaced":
        return f"The test asserts {q}, but {fact}."
    if verdict == "review" and does is not None:
        return f"The test asserts {q}, but {fact}, and {rich_prose(does)} to read it."
    if does is not None:
        return f"The test asserts {q}, but {fact}, and {rich_prose(does)} instead."
    return f"The test asserts {q}, but {fact}."


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
    hot = " hot" if not_assessable or claim.get("verdict") in ("gap", "review", "duplicate") else ""
    quote = quoted_assertion(claim)
    return ['<section class="scan">',
            f'<p class="judgement"><strong class="verdict{hot}">{esc(label)}</strong></p>',
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


# ---------------------------------------------------------------- home screen

def index(conn) -> bytes:
    fr = queries.freshness(conn)
    rows, older = queries.latest_per_analyser(conn)
    body = ["<h1>TestOps</h1>", freshness_line(fr)]
    if not rows:
        if fr.get("ever_run"):
            versions = versions_text(fr.get("versions"))
            body.append(
                f'<p>No cases are open. The newest analysis ran '
                f'<strong>{esc(age(fr.get("finished_at")))}</strong>'
                f'{" at " + esc(versions) if versions else ""} and raised nothing that needs a '
                f'decision. That is what this run found, not a claim that the code is clean.</p>')
        else:
            body.append('<p class="quiet">No cases yet. Nothing has been analysed, so this page '
                        'cannot say anything about the code.</p>')
    else:
        body.append('<ul class="cases">')
        for r in rows:
            n = r["findings"]
            shown = display_state(r["state"], n)
            hot = ' class="hot"' if shown in ("Open", "Needs a fix") else ""
            # The claim's own words, never finding.title: a title cut to 160 characters ends
            # mid-sentence and leaves the reader to guess what is alleged. The asserted step is
            # what the claim is; the stored statement is the analyser's essay about it, and only a
            # v1 claim (which recorded no step) falls back to it (TESTOPS-23).
            statement = (r.get("assertion") or r.get("statement")
                         or "No claim: this run raised no finding.")
            body.append(
                f'<li><a href="/case/{esc(r["id"])}">'
                f'<div><span class="badge{hot}">{esc(shown)}</span> '
                f'<span class="meta">{esc(r["project"])} \u00b7 {esc(analyser_text(r["analyser"]))} '
                f'\u00b7 {n} finding{"s" if n != 1 else ""} \u00b7 {esc(age(r["created_at"]))}</span>'
                f'</div><p class="claimtext">{esc(statement)}</p></a></li>')
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


def section_unchecked(c: dict) -> list[str]:
    """4. What could not be checked. Absence is a state, never a blank and never a zero.

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
        out = ['<p>Not connected when this claim was checked:</p>']
        for note in notes:
            out.append(f'<p>{esc(_blind_spot_sentence(note))}</p>')
        out.append('<p>They were never consulted, so nothing here says they were clean '
                   '\u2014 only that this claim was never checked against them.</p>')
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
    if state == sources.BLOCKED:
        by = f" by {note['blocked_by']}" if note.get("blocked_by") else ""
        return f"{title} \u2014 blocked{by}: {reason}." if reason else f"{title} \u2014 blocked{by}."
    if state == sources.ABSENT:
        return f"{title} \u2014 absent: {reason}." if reason else f"{title} \u2014 absent."
    return f"{title} \u2014 {state}: {reason}." if state and reason else f"{title}."


def claim_sections(c: dict) -> list[str]:
    """One claim, one argument: five sections, and the claim stated once (TESTOPS-23, AC3).

    1. a scan block - the judgement, the one wrong thing, and the action on its own line; the
       provenance footnote sits under it, never as a section of its own
    2. the step that is asserted - the file around it and the definition that runs it
    3. the other steps in this scenario, for context - separated from evidence, introduced together
    4. what could not be checked
    5. the decision (rendered once per case, by ``case_page``)
    """
    out = ['<h2 class="section">1. What is asserted, and what settles it</h2>']
    out.extend(argument_block(c))
    out.extend(provenance_line(c))
    out.extend(assessment_note(c))
    out.extend(pass_aside(c))
    out.extend(['<h2 class="section">2. The step that is asserted</h2>'])
    out.extend(evidence_block(c))
    out.extend(['<h2 class="section">3. The other steps in this scenario, for context</h2>'])
    out.extend(context_block(c))
    out.extend(['<h2 class="section">4. What could not be checked</h2>'])
    out.extend(section_unchecked(c))
    return out


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
    lines = ['<p>Not connected when this run looked:</p>']
    lines.extend(f'<p>{esc(_blind_spot_sentence(spot))}</p>' for spot in spots)
    lines.append('<p>They were never consulted, so nothing here says they held nothing \u2014 only '
                 'that this run was never checked against them.</p>')
    return lines


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


def decision_form(conn, row: dict, case_id: str, findings: list[dict]) -> list[str]:
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


def case_page(conn, case_id: str) -> bytes | None:
    row = queries.case_row(conn, case_id)
    if not row:
        return None
    findings = queries.finding_rows(conn, case_id)
    claims = [c for f in findings for c in f["claims"]]
    versions = versions_text(row["versions"])
    decision = queries.latest_decision(conn, case_id)
    run = queries.run_analysis(conn, case_id)
    state_label = case_badge(decision, len(findings))

    body = [f'<p class="meta"><a href="/">\u2190 all cases</a></p>',
            f'<h1>{esc(row["project"])} \u00b7 {esc(analyser_text(row["analyser"]))}</h1>']
    hot = ' class="hot"' if state_label in ("Open", "Needs a fix") else ""
    body.append(f'<p class="meta"><span class="badge{hot}">'
                f'{esc(state_label)}</span>'
                f' \u00b7 Analysed {esc(age(row["created_at"]))}'
                f'{" at " + esc(versions) if versions else ""}</p>')

    if not findings:
        # A run that raised nothing is described as a run: what it examined, and what it could not
        # consult. It is never called resolved - that word belongs to a person's recorded decision,
        # which is rendered beside it when one exists (TESTOPS-22).
        body.extend(quiet_run_block(run))
    if decision is not None:
        body.extend(decision_block(decision))
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
                body.extend(claim_sections(c))

    form = decision_form(conn, row, case_id, findings)
    if form:
        body.append('<h2 class="section">5. Decision</h2>' if findings else "<h2>Decision</h2>")
        body.extend(form)
    body.extend(footnote(claims))
    return page(f"TestOps \u00b7 {case_id}", "".join(body))


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
            m = re.fullmatch(r"/case/([^/]+)", path)
            if m:
                body = case_page(conn, urllib.parse.unquote(m.group(1)))
                self._send(body) if body else self._not_found()
                return
            self._not_found()
        finally:
            conn.close()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        m = re.fullmatch(r"/case/([^/]+)/state", path)
        if not m:
            self._not_found()
            return
        length = int(self.headers.get("Content-Length") or 0)
        payload = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
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


def serve(port: int = 8787, host: str = "127.0.0.1") -> None:
    db.connect().close()                     # create the schema before the first request
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"TestOps UI on http://{host}:{port}", flush=True)
    httpd.serve_forever()
