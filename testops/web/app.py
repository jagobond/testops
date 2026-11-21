"""The smallest web surface that lets a person verify a finding and decide on it.

Two screens. Server-rendered HTML, one form, no JavaScript. The design decisions that matter, from ui-design-v2:

  - decisions belong to the CASE, and the panel says how many findings ride on them
  - suppression is reversible, and reopening actually deletes the suppression
  - the empty screen reports freshness, never absence
  - verdicts are labelled in English with the internal code secondary
"""
from __future__ import annotations

import datetime as dt
import html
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .. import cases, queries
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

CSS = """
:root { --ink:#1b1f24; --dim:#5b6672; --line:#dfe3e8; --bg:#fbfbfa; --accent:#8C5E2C; --bad:#8a2b2b; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:16px/1.55 -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }
main { max-width: 60rem; margin: 0 auto; padding: 2rem 1.25rem 5rem; }
h1 { font-size: 1.15rem; letter-spacing:.02em; text-transform:uppercase; color:var(--dim); font-weight:600; }
h2 { font-size: 1.35rem; margin:.2rem 0 .35rem; }
a { color: var(--accent); }
.fresh { color: var(--dim); font-size:.92rem; border-bottom:1px solid var(--line); padding-bottom:.9rem; }
.fresh strong { color: var(--ink); font-weight:600; }
ul.cases { list-style:none; padding:0; margin:1.5rem 0; }
ul.cases li { border:1px solid var(--line); border-radius:6px; background:#fff; margin-bottom:.6rem; }
ul.cases li a { display:block; padding:.85rem 1rem; text-decoration:none; color:inherit; }
ul.cases li a:hover { background:#f6f4f0; }
.meta { color:var(--dim); font-size:.9rem; }
.badge { display:inline-block; font-size:.78rem; letter-spacing:.03em; text-transform:uppercase;
         border:1px solid var(--line); border-radius:99px; padding:.1rem .55rem; color:var(--dim); }
.badge.hot { border-color:var(--bad); color:var(--bad); }
.finding { background:#fff; border:1px solid var(--line); border-radius:6px; padding:1.1rem 1.2rem;
           margin:1rem 0; }
.finding h3 { margin:0 0 .15rem; font-size:1.05rem; }
.code { font-family: ui-monospace, Consolas, monospace; font-size:.8rem; color:var(--dim); }
.claim { margin:.9rem 0 0; padding-left:.9rem; border-left:2px solid var(--line); }
.ev { margin:.35rem 0 0; padding:0; list-style:none; }
.ev li { font-family: ui-monospace, Consolas, monospace; font-size:.82rem; }
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


def freshness_line(fr: dict) -> str:
    """Never 'all clear'. Say what was looked at, and when."""
    if not fr.get("ever_run"):
        return ('<p class="fresh">Nothing has been analysed yet. '
                '<span class="quiet">Run <span class="code">python -m testops.cli levels --project cotw</span> '
                'to produce a first case.</span></p>')
    versions = ", ".join(f"{k.split('/')[-1]}@{v[:8]}" for k, v in (fr.get("versions") or {}).items())
    return (f'<p class="fresh">Last analysed <strong>{esc(age(fr.get("finished_at")))}</strong>'
            f'{" at " + esc(versions) if versions else ""}'
            f' <span class="quiet">({esc(fr.get("analyser") or "")})</span></p>')


def index(conn) -> bytes:
    fr = queries.freshness(conn)
    rows, older = queries.latest_per_analyser(conn)
    quiet = older
    body = ["<h1>TestOps</h1>", freshness_line(fr)]
    if not rows:
        body.append('<p class="quiet">No open cases. When an analysis raises something, it appears here.</p>')
    else:
        body.append('<ul class="cases">')
        for r in rows:
            hot = ' class="hot"' if r["state"] in ("open", "needs_fix") else ""
            body.append(
                f'<li><a href="/case/{esc(r["id"])}">'
                f'<span class="badge{hot}">{esc(STATE_LABEL.get(r["state"], r["state"]))}</span> '
                f'<strong>{esc(r["project"])}</strong> · {esc(r["analyser"])} · '
                f'{r["findings"]} finding{"s" if r["findings"] != 1 else ""}'
                f'<div class="meta">{esc(age(r["created_at"]))}</div></a></li>')
        body.append("</ul>")
    if quiet:
        body.append(f'<p class="quiet">{quiet} earlier run{"s" if quiet != 1 else ""} not shown '
                    f'— only the newest case per analyser is listed.</p>')
    return page("TestOps", "".join(body))


def case_page(conn, case_id: str) -> bytes | None:
    row = queries.case_row(conn, case_id)
    if not row:
        return None
    findings = queries.finding_rows(conn, case_id)
    versions = ", ".join(f"{k}@{v[:8]}" for k, v in (row["versions"] or {}).items())
    body = [f'<p class="meta"><a href="/">← all cases</a></p>',
            f'<h1>{esc(row["analyser"])} · {esc(row["project"])}</h1>',
            f'<h2>{esc(STATE_LABEL.get(row["state"], row["state"]))}</h2>',
            f'<p class="meta">Analysed {esc(age(row["created_at"]))}'
            f'{" · " + esc(versions) if versions else ""}</p>']

    if not findings:
        superseded = conn.execute(
            """SELECT s.state, s.actor, s.at, s.note FROM suppression s
               JOIN finding f ON f.fingerprint = s.fingerprint WHERE f.case_id = ?
               ORDER BY s.at DESC LIMIT 1""", (case_id,)).fetchone()
        if superseded:
            body.append(f'<p>Every finding in this case has been suppressed. '
                        f'Last decision: <strong>{esc(STATE_LABEL.get(superseded["state"], superseded["state"]))}</strong> '
                        f'by {esc(superseded["actor"])} {esc(age(superseded["at"]))}'
                        f'{esc(" — " + superseded["note"]) if superseded["note"] else ""}.</p>')
        else:
            body.append('<p class="quiet">This case produced no findings. That usually means the analysis was '
                        'interrupted rather than that nothing was wrong.</p>')
    else:
        for f in findings:
            badge = "hot" if any(c["verdict"] in ("gap", "review", "duplicate") for c in f["claims"]) else ""
            body.append('<div class="finding">')
            head = (f["claims"][0]["scenario"] if f["claims"] and f["claims"][0]["scenario"]
                    else f["title"][:120])
            body.append(f'<h3><span class="badge {badge}">'
                       f'{esc(LABEL.get(f["claims"][0]["verdict"]) if f["claims"] else "Finding")}</span> '
                       f'{esc(head)}</h3>')
            for c in f["claims"]:
                label = LABEL.get(c["verdict"], c["verdict"])
                body.append(f'<div class="claim"><strong>{esc(label)}</strong> '
                            f'<span class="code">{esc(c["verdict"])} · {esc(c["detail"].get("claim", ""))}</span>'
                            f'<p>{esc(c["statement"])}</p>')
                if c["scenario"]:
                    body.append(f'<p class="meta">Scenario: <em>{esc(c["scenario"])}</em></p>')
                if c["evidence"]:
                    body.append('<ul class="ev">')
                    for e in c["evidence"][:4]:
                        href = e.get("link") or "#"
                        body.append(f'<li><a href="{esc(href)}">{esc(e.get("where") or e.get("uri"))}</a></li>')
                    body.append("</ul>")
                body.append("</div>")
            body.append("</div>")

    n = len(findings)
    suppressed_here = conn.execute(
        """SELECT s.state, s.actor, s.at, s.note FROM suppression s
           JOIN finding f ON f.fingerprint = s.fingerprint WHERE f.case_id = ?
           ORDER BY s.at DESC LIMIT 1""", (case_id,)).fetchone()
    terminal = row["state"] in ("resolved", "false_positive")

    if n and terminal:
        # Suppressed but still visible: say who decided, when, and offer the undo that actually undoes.
        d = suppressed_here
        body.append('<form class="decide" method="post" action="/case/'
                    f'{esc(case_id)}/state">')
        body.append(f'<p><strong>Suppressed</strong> — {n} finding{"s" if n != 1 else ""} in this case '
                    f'{"are" if n != 1 else "is"} hidden from future runs'
                    f'{esc(" (" + (d["actor"] if d else "") + ", " + age(d["at"]) + ")") if d else ""}'
                    f'{esc(" — " + d["note"]) if d and d["note"] else ""}.</p>')
        body.append('<p><button name="state" value="open">Reopen — report this again</button></p>')
        body.append('<p class="quiet">Reopening deletes the suppression, so the next run raises it again.</p>')
        body.append('</form>')
    elif n:
        body.append('<form class="decide" method="post" '
                    f'action="/case/{esc(case_id)}/state">')
        body.append(f'<p><strong>Decide this case</strong> — {n} finding'
                    f'{"s" if n != 1 else ""} on this decision.</p>')
        body.append('<p><input type="text" name="note" placeholder="Why? (optional, shown next time)"></p>')
        body.append('<p>'
                    '<button name="state" value="needs_fix">Needs a fix</button>'
                    '<button class="term" name="state" value="resolved">Resolved — stop reporting</button>'
                    '<button class="term" name="state" value="false_positive">Not a real finding — stop reporting</button>'
                    '</p>')
        body.append('<p class="warn">Resolved and “not a real finding” hide this evidence from future runs. '
                    'You can reopen the case later; reopening makes it report again.</p>')
        body.append('</form>')
    elif terminal:
        body.append(f'<form class="decide" method="post" action="/case/{esc(case_id)}/state">'
                    '<p><button name="state" value="open">Reopen this case</button></p>'
                    '<p class="quiet">Reopening deletes the suppression, so the next run reports it again.</p>'
                    '</form>')
    return page(f"TestOps · {case_id}", "".join(body))


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
                                     '<p><a href="/">← all cases</a></p>'), 404)

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
