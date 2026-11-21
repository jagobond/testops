"""The smallest web surface that lets a person verify a finding and decide on it.

Two screens. Server-rendered HTML, one form, no JavaScript, nothing behind a disclosure.

The case page is an argument in six sections, in this order, because that is the order a person
needs them to decide:

  1. what is asserted - the step, verbatim, with a permalink at the commit it was read at
  2. where the name came from - the test's own scenario title, labelled as such, never a requirement
  3. what the test actually does - the layers it reaches and the instrument, in words
  4. why that does or does not establish it - the statement and the rule that placed it
  5. what could not be checked - the sources that were never connected
  6. what to do about it - the action, then the decision form

Design decisions that matter, from ui-design-v2 and the Product Owner's reading of the old page:

  - a heading that does not say where it came from is not a heading, it is a riddle; section 2
    exists because the old page showed a scenario title and let the reader guess it was a requirement
  - a list of links is not evidence; every link says what it shows
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

from .. import cases, queries
from ..extract.stepbindings import LAYER_ORDER
from ..store import db

LABEL = {
    "gap": "Never actually proved",
    "review": "Browser not needed",
    "duplicate": "Already covered",
    "unplaced": "Could not be judged",
    "distinct": "Established",
}
STATE_LABEL = {"open": "Open", "needs_fix": "Needs a fix", "resolved": "Resolved",
               "false_positive": "Not a real finding"}

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
.warn { color:var(--bad); font-size:.9rem; }
.quiet { color:var(--dim); }
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
    """The state a reader is shown. An empty case has nothing open, whatever the stored row says."""
    if findings == 0 and state == "open":
        return "Resolved"
    return STATE_LABEL.get(state, state)


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


def label_sentence(label: str | None) -> str:
    """The interaction label as a sentence a reader meets, not as a code."""
    if not label:
        return "What settles this claim was not recorded."
    if label.startswith("settled by ") or label.startswith("unclear "):
        return f"It is {label}."
    return f"It {label}."


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
            # mid-sentence and leaves the reader to guess what is alleged.
            statement = r.get("statement") or "No claim: this case raised nothing to act on."
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


# ---------------------------------------------------------------- one claim, six sections

def section_asserted(c: dict) -> list[str]:
    """1. What is asserted - verbatim, with a permalink at the claim's own commit."""
    prov = c["provenance"]
    assertion = prov["assertion_text"]
    if c["schema_version"] != 2 or not assertion:
        return ['<p class="quiet">What this claim asserts was recorded before provenance was '
                'captured: there is no exact step and no line to point at. The claim as it was '
                'originally worded is in section 4.</p>']

    path, line = prov["assertion_path"], prov["assertion_line"]
    where = f"{path}:{line}"
    commit = (prov["assertion_commit"] or "")[:8]
    if c.get("permalink"):
        source = f'<a href="{esc(c["permalink"])}">{esc(where)}</a>'
        tail = "the commit this claim was read at."
    else:
        source = f'<span class="code">{esc(where)}</span>'
        tail = ("the commit this claim was read at. This run did not record which repository the "
                "file lives in, so there is no link to open.")
    return [f'<blockquote class="assertion">\u201c{esc(assertion)}\u201d</blockquote>',
            f'<p class="meta">Test source: {source} at commit '
            f'<span class="code">{esc(commit)}</span> \u2014 {tail}</p>']


def section_name(c: dict) -> list[str]:
    """2. Where the name came from - the test's own title, never a requirement."""
    if not c["scenario"]:
        return ['<p class="quiet">The scenario this assertion belongs to was not recorded.</p>']
    return [f'<p>This name comes from the test\u2019s own scenario title: '
            f'<em>\u201c{esc(c["scenario"])}\u201d</em>. It is the test author\u2019s name for the '
            f'scenario, not a requirement: nothing here was checked against one.</p>']


def section_does(c: dict) -> list[str]:
    """3. What the test actually does - the layers and the instrument, in words, plus evidence."""
    out: list[str] = []
    span = c["span"]
    if span is None:
        out.append('<p class="quiet">What this test reaches was not recorded for this claim.</p>')
    elif not span:
        out.append('<p class="quiet">This run recorded no layer that this test reaches.</p>')
    else:
        used = instrument(span)
        if used == "unknown":
            out.append('<p>No instrument could be identified for this test.</p>')
        elif len([l for l in span if l in LAYER_ORDER]) <= 1:
            out.append(f'<p>It {INSTRUMENT_WORD[used]}.</p>')
        else:
            out.append(f'<p>It {INSTRUMENT_WORD[used]}. It reaches {layer_words(span)}.</p>')

    evidence = c.get("evidence")
    if evidence is None:
        out.append('<p class="quiet">Evidence for this claim was not recorded.</p>')
    elif not evidence:
        out.append('<p class="quiet">This run recorded no observations at these coordinates, so the '
                   'source link above is the only evidence there is.</p>')
    else:
        out.append('<p>Evidence recorded at this claim\u2019s own coordinates in this run:</p>')
        out.append('<ul class="ev">')
        for e in evidence:
            where = esc(e.get("where") or e.get("uri"))
            if e.get("link"):
                where = f'<a href="{esc(e["link"])}">{where}</a>'
            else:
                where = f'<span class="code">{where}</span>'
            out.append(f'<li>{where} \u2014 {esc(e.get("shows"))}.</li>')
        out.append("</ul>")
    return out


def section_why(c: dict) -> list[str]:
    """4. Why that does or does not establish it - statement, label and rule in the reader's words."""
    out = [f'<p>{esc(c["statement"])}</p>',
           f'<p><strong>What settles it.</strong> {esc(label_sentence(c["interaction_label"]))}</p>']
    if c["established_by"]:
        rule = c["established_by"].strip().rstrip(".")
        rule = rule[0].lower() + rule[1:] if rule else rule
        out.append(f'<p><strong>Why it was classified this way:</strong> {esc(rule)}.</p>')
    else:
        out.append('<p class="quiet">The rule that classified this claim was not recorded.</p>')
    return out


def section_unchecked(c: dict) -> list[str]:
    """5. What could not be checked. Absence is a state, never a blank and never a zero."""
    missing = c["sources_missing"]
    if missing is None:
        return ['<p class="quiet">Whether any source needed for this claim was missing was not '
                'recorded.</p>']
    if not missing:
        return ['<p>Every source needed for this claim was available.</p>']
    names = [SOURCE_NAME.get(m, m) for m in missing]
    listed = ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]
    return [f'<p>Not connected when this claim was checked: <strong>{esc(listed)}</strong>. '
            f'They were never consulted, so nothing here says they were clean \u2014 only that this '
            f'claim was never checked against them.</p>']


def section_action(c: dict) -> list[str]:
    """6. The action, in one sentence naming the step to change."""
    if c["proposed_action"]:
        return [f'<p>{esc(c["proposed_action"])}</p>']
    return ['<p class="quiet">No proposed action was recorded for this claim.</p>']


def claim_sections(c: dict) -> list[str]:
    out: list[str] = []
    # The verdict in English before the argument: a reader deciding in one pass needs to know what
    # kind of shortfall this is before reading why.
    verdict_label = LABEL.get(c["verdict"])
    if verdict_label:
        hot = " hot" if c["verdict"] in ("gap", "review", "duplicate") else ""
        out.append(f'<p><span class="badge{hot}">{esc(verdict_label)}</span></p>')
    for heading, parts in (
            ("1. What is asserted", section_asserted(c)),
            ("2. Where the name came from", section_name(c)),
            ("3. What the test actually does", section_does(c)),
            ("4. Why that does or does not establish it", section_why(c)),
            ("5. What could not be checked", section_unchecked(c)),
            ("6. Proposed action and decision", section_action(c))):
        out.append(f'<h2 class="section">{esc(heading)}</h2>')
        out.extend(parts)
    return out


def decision_form(conn, row: dict, case_id: str, findings: list[dict]) -> list[str]:
    """The decision, after section 6's action. One case, one decision, and it says what it hides."""
    n = len(findings)
    suppressed_here = conn.execute(
        """SELECT s.state, s.actor, s.at, s.note FROM suppression s
           JOIN finding f ON f.fingerprint = s.fingerprint WHERE f.case_id = ?
           ORDER BY s.at DESC LIMIT 1""", (case_id,)).fetchone()
    terminal = row["state"] in cases.TERMINAL
    out: list[str] = []

    if n and terminal:
        d = suppressed_here
        out.append(f'<form class="decide" method="post" action="/case/{esc(case_id)}/state">')
        out.append(f'<p><strong>Suppressed</strong> \u2014 {n} finding{"s" if n != 1 else ""} in '
                   f'this case {"are" if n != 1 else "is"} hidden from future runs'
                   f'{esc(" (" + (d["actor"] if d else "") + ", " + age(d["at"]) + ")") if d else ""}'
                   f'{esc(" \u2014 " + d["note"]) if d and d["note"] else ""}.</p>')
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
                   '<button name="state" value="needs_fix">Needs a fix</button>'
                   '<button class="term" name="state" value="resolved">Resolved \u2014 stop reporting</button>'
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
    state_label = display_state(row["state"], len(findings))

    body = [f'<p class="meta"><a href="/">\u2190 all cases</a></p>',
            f'<h1>{esc(row["project"])} \u00b7 {esc(analyser_text(row["analyser"]))}</h1>',
            f'<p class="meta"><span class="badge'
            f'{" hot" if STATE_LABEL.get(row["state"]) in ("Open", "Needs a fix") else ""}">'
            f'{esc(state_label)}</span>'
            f' \u00b7 Analysed {esc(age(row["created_at"]))}'
            f'{" at " + esc(versions) if versions else ""}</p>']

    if not findings:
        superseded = conn.execute(
            """SELECT s.state, s.actor, s.at, s.note FROM suppression s
               JOIN finding f ON f.fingerprint = s.fingerprint WHERE f.case_id = ?
               ORDER BY s.at DESC LIMIT 1""", (case_id,)).fetchone()
        if superseded:
            body.append(f'<p>Every finding in this case has been suppressed. '
                        f'Last decision: <strong>{esc(STATE_LABEL.get(superseded["state"], superseded["state"]))}</strong> '
                        f'by {esc(superseded["actor"])} {esc(age(superseded["at"]))}'
                        f'{esc(" \u2014 " + superseded["note"]) if superseded["note"] else ""}.</p>')
        else:
            body.append('<p>This case is resolved: the analysis raised nothing to act on. That is a '
                        'result, not an error \u2014 and not a claim that the code is clean, only '
                        'that nothing in this run fell short.</p>')
    else:
        for i, f in enumerate(findings, start=1):
            if len(findings) > 1:
                body.append(f'<h2>Finding {i} of {len(findings)}</h2>')
            for j, c in enumerate(f["claims"], start=1):
                if len(f["claims"]) > 1:
                    body.append(f'<h3>Claim {j} of {len(f["claims"])}</h3>')
                body.extend(claim_sections(c))

    body.extend(decision_form(conn, row, case_id, findings))
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
