"""A Foundry agent that explains one case, and the honest accounting around it.

TESTOPS-88. The deterministic verdict stays evidence. This module adds commentary beside it: a
plain-English explanation of *this* case, written from the stored record only, shown when a reader
asks for it with ``?agent=on`` and never otherwise.

Four rules this module is built around.

**The record is the whole world.** :func:`case_record` assembles exactly what the page reads -
the verdict, the assertion text, the matched word, the product file and line, the near-miss reason,
the sources that were consulted and the ones that were not. The prompt says so, and
:func:`violations` checks the reply against the same record: a route, a file, a count or a
named entity that the record does not contain makes the reply unusable, and the page falls back to
its agent-off content plus one sentence saying why. A model that invents a route cannot put it in
front of a reader.

**Every call is in the ledger.** Case, variant, model, prompt hash, tokens in, tokens out, whether
the answer came from the cache, and the wall time - one row in ``agent_call``. Every page view is a
row in ``agent_view``, including the ones served with the agent off, so ``/agent-report`` can put
value beside cost instead of asserting it.

**The cache is (case, prompt hash, model).** A second view of the same case with the same record is
free, and the page says the explanation is a stored one. The prompt hash covers the prompt text and
the model, so a changed record is a new key rather than a stale hit.

**Failure is a sentence, never a blank.** No token, an unreachable model, a non-200, a rate limit, an
empty reply, a malformed one: the agent-off page plus one sentence, and the cause in the ledger.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
from collections.abc import Mapping
from dataclasses import dataclass, field

from .. import queries
from . import client

VARIANT_ON = "on"
VARIANT_OFF = "off"
VARIANTS = (VARIANT_OFF, VARIANT_ON)

# Part of the prompt hash. Bump it when the prompt changes: an explanation written under an older
# instruction is not the same artefact, and a reader comparing two of them is owed the difference.
PROMPT_VERSION = "explain-a-case/1"

# How long a resolved (or failed) token lookup is trusted. Long enough that a page view does not
# wait three seconds on IMDS every time, short enough that a rotated token is picked up.
TOKEN_TTL_SECONDS = 300.0

# How many findings of one case the prompt quotes. A rare case holds dozens; quoting all of them
# buys a long prompt and a vague explanation, so the first few are quoted and the prompt says so in
# as many words. The *check* on the reply still uses the whole record, so a fact from a finding the
# prompt did not quote is not a fabrication.
PROMPT_FINDING_LIMIT = 6

SYSTEM_PROMPT = """You explain one finding from a code-analysis tool to the person who has to act on it.

You will be given a record. It is the only thing you know about this case.

Rules, all of them absolute:
- Use only the facts in the record. Do not add a fact from your own knowledge, however obvious.
- Do not name any file, path, route, endpoint, number, class, function, ticket or service that does
  not appear in the record. Do not round, estimate or invent a count.
- Do not decide anything. The verdict in the record is the finding; you are explaining it, not
  reviewing it, and you may not suggest it is wrong.
- Four to six sentences of plain English, no headings, no bullet lists, no markdown.
- Say what was asserted, what the rule found, and what the reader would do about it - in that order,
  using the record's own words for the assertion.
- If something a reader would want to know is not in the record, say that the record does not
  contain it. Do not fill the gap."""


@dataclass(frozen=True)
class Config:
    """Where the agent talks, as what, with what credential. Never a credential value in a log."""

    project: str
    endpoint: str
    model: str
    token: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.token)

    @property
    def why_not(self) -> str:
        if self.token:
            return ""
        return ("The model-written explanation is not available: this deployment has no token from "
                "TESTOPS_AGENT_TOKEN, a managed identity or the az CLI.")


@dataclass
class Outcome:
    """What the page should carry, and why. ``state`` is the ledger's word for it."""

    state: str                      # explanation | cached | rejected | error | not_configured
    text: str = ""
    model: str = ""
    cause: str = ""                 # unreachable | http_429 | empty | ... | rejected:<faith>
    detail: str = ""                # the offending token, or the model name; never a credential
    prompt_hash: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    call_id: int | None = None
    violations: list[str] = field(default_factory=list)

    @property
    def served(self) -> bool:
        return self.state in ("explanation", "cached")

    @property
    def sentence(self) -> str:
        """The one sentence the page shows instead of an explanation. Empty when one was served."""
        if self.served:
            return ""
        return REFUSALS.get(self.cause) or REFUSALS["unexpected"]


# ---------------------------------------------------------------- configuration

_TOKEN_CACHE: dict[str, object] = {"at": None, "token": ""}


def reset_token_cache() -> None:
    """Forget the resolved token. For a test, and for an operator who has just logged in."""
    _TOKEN_CACHE["at"] = None
    _TOKEN_CACHE["token"] = ""


def config(environ: Mapping[str, str] | None = None, now: float | None = None) -> Config:
    """This deployment's agent configuration, with the token resolved at most once per TTL.

    ``TESTOPS_AGENT_TOKEN`` first, then the managed identity, then ``az`` (see
    :func:`testops.judgement.client.token`). Absent all three, the config is unconfigured and the
    site serves agent-off pages - it does not fail to start, and it does not pretend.
    """
    env = os.environ if environ is None else environ
    project = (env.get("TESTOPS_AGENT_PROJECT") or "").strip() or client.DEFAULT_PROJECT
    model = client.model_name(env)
    supplied = (env.get("TESTOPS_AGENT_TOKEN") or "").strip()
    if supplied:
        token = supplied
    else:
        clock = time.monotonic() if now is None else now
        cached_at = _TOKEN_CACHE.get("at")
        if not isinstance(cached_at, float) or clock - cached_at > TOKEN_TTL_SECONDS:
            _TOKEN_CACHE["token"] = client.managed_identity_token() or client.az_token()
            _TOKEN_CACHE["at"] = clock
        token = str(_TOKEN_CACHE.get("token") or "")
    return Config(project=project, endpoint=client.endpoint(env, project), model=model,
                  token=token)


# ---------------------------------------------------------------- the stored record

def case_record(conn, case_id: str, row: dict | None = None,
                findings: list[dict] | None = None) -> dict | None:
    """What the page knows about one case, assembled for the model and for the check on its reply.

    This is a *read*: it calls the same read model the page calls, so the explanation can only ever
    be about facts a reader can also see. Nothing is fetched, and nothing is resolved live. The page
    may pass the rows it has already read, so the explanation is written from exactly the rows it
    renders and not from a second read that could have moved.
    """
    row = queries.case_row(conn, case_id) if row is None else row
    if row is None:
        return None
    findings = queries.finding_rows(conn, case_id) if findings is None else findings
    claims = [claim for finding in findings for claim in finding["claims"]]
    band = queries.source_band(conn, row, claims)
    record = {
        "case": {
            "id": row["id"],
            "project": row["project"],
            "analyser": row["analyser"],
            "analysed_at": row["created_at"],
            "state": row["state"],
            "versions": row.get("versions") or {},
        },
        "findings": [_finding_record(finding) for finding in findings],
        "counts": {"findings": len(findings), "claims": len(claims),
                   "sources": len(band.get("tags") or [])},
        "sources": [{"kind": tag.get("kind") or "", "name": tag.get("name") or "",
                     "state": tag.get("state") or "", "reason": tag.get("reason") or ""}
                    for tag in (band.get("tags") or [])],
    }
    return record


def _finding_record(finding: dict) -> dict:
    return {"title": finding.get("title") or "",
            "claims": [_claim_record(claim) for claim in finding.get("claims") or []]}


def _claim_record(claim: dict) -> dict:
    """One claim as the model sees it: the verdict, the assertion, the product fact, the blind spots."""
    detail = claim.get("detail") or {}
    product = detail.get("product") or {}
    provenance = claim.get("provenance") or {}
    out = {
        "verdict": claim.get("verdict") or "",
        "statement": claim.get("statement") or "",
        "assertion_text": detail.get("assertion_text") or "",
        "path": provenance.get("assertion_path") or "",
        "line": provenance.get("assertion_line") or "",
        "settled_by": claim.get("interaction_label") or "",
        "established_by": claim.get("established_by") or "",
        "proposed_action": claim.get("proposed_action") or "",
        "levels": claim.get("span") or [],
        "sources_not_consulted": claim.get("sources_missing") or [],
    }
    if detail.get("cheapest"):
        out["cheapest_surface"] = detail.get("cheapest")
    if product:
        out["product"] = {}
        for key in ("route", "surface", "word", "reason", "claim", "near_miss"):
            value = product.get(key)
            if value not in (None, "", False):
                out["product"][key] = value
    counterpart = claim.get("counterpart")
    if counterpart:
        out["copied_from"] = {"path": counterpart.get("path") or "",
                              "line": counterpart.get("line") or "",
                              "scenario": counterpart.get("scenario") or ""}
    return {key: value for key, value in out.items() if value not in (None, "", [], {})}


def facts_text(record: dict) -> str:
    """The record as the numbered lines the prompt carries. Stable ordering, so the hash is stable."""
    lines: list[str] = []
    case = record.get("case") or {}
    lines.append(f"CASE {case.get('id', '')}")
    lines.append(f"  project: {case.get('project', '')}")
    lines.append(f"  recorded by: {case.get('analyser', '')}")
    lines.append(f"  recorded at: {case.get('analysed_at', '')}")
    lines.append(f"  state: {case.get('state', '')}")
    versions = case.get("versions") or {}
    if versions:
        lines.append("  looked at: " + ", ".join(f"{k}@{str(v)[:8]}" for k, v in versions.items()))
    findings = record.get("findings") or []
    lines.append(f"FINDINGS: {len(findings)}")
    quoted = findings[:PROMPT_FINDING_LIMIT]
    if len(findings) > len(quoted):
        lines.append(f"  (the first {len(quoted)} are quoted below; the record holds "
                     f"{len(findings)}, and the rest are not summarised here - say so rather than "
                     f"guessing what they say)")
    for i, finding in enumerate(quoted, start=1):
        lines.append(f"FINDING {i}")
        if finding.get("title"):
            lines.append(f"  title: {finding['title']}")
        for j, claim in enumerate(finding.get("claims") or [], start=1):
            lines.append(f"  CLAIM {j}")
            for key in ("verdict", "statement", "assertion_text", "path", "line", "settled_by",
                        "established_by", "proposed_action", "cheapest_surface"):
                value = claim.get(key)
                if value not in (None, "", []):
                    lines.append(f"    {key}: {value}")
            levels = claim.get("levels") or []
            if levels:
                lines.append(f"    levels the test reaches: {', '.join(str(v) for v in levels)}")
            product = claim.get("product") or {}
            for key in ("route", "surface", "word", "claim", "reason", "near_miss"):
                if product.get(key) not in (None, ""):
                    lines.append(f"    product {key}: {product[key]}")
            copied = claim.get("copied_from") or {}
            if copied:
                lines.append(f"    copied from: {copied.get('path', '')}:{copied.get('line', '')}"
                             f" scenario {copied.get('scenario', '')}".rstrip())
            missing = claim.get("sources_not_consulted") or []
            if missing:
                lines.append(f"    sources not consulted: {', '.join(str(v) for v in missing)}")
    sources = record.get("sources") or []
    lines.append(f"SOURCES EXAMINED: {len(sources)}")
    for source in sources:
        line = f"  {source.get('kind', '')} {source.get('name', '')}: {source.get('state', '')}"
        if source.get("reason"):
            line += f" - {source['reason']}"
        lines.append(line.rstrip())
    counts = record.get("counts") or {}
    if counts:
        lines.append("COUNTS " + ", ".join(f"{k}: {v}" for k, v in counts.items()))
    return "\n".join(lines)


def prompt(record: dict, model: str) -> tuple[str, str, str]:
    """The system prompt, the user message, and the hash that keys the cache.

    The hash covers the prompt version, both messages and the model: a changed record, a changed
    instruction or a different model is a different key, so a stale explanation can never be served
    as if it were written about what the page is showing now.
    """
    user = (f"Here is the record for one case. Explain it.\n\n{facts_text(record)}\n\n"
            f"Write the explanation now, in plain English, four to six sentences.")
    try:
        digest = hashlib.sha256(
            f"{PROMPT_VERSION}\n{SYSTEM_PROMPT}\n{user}\n--\n{model}".encode()).hexdigest()[:16]
    except UnicodeEncodeError:  # a record with undecodable text still gets a stable key
        digest = hashlib.sha256(
            f"{PROMPT_VERSION}\n{SYSTEM_PROMPT}\n{user}\n--\n{model}"
            .encode("utf-8", "replace")).hexdigest()[:16]
    return SYSTEM_PROMPT, user, digest


# ---------------------------------------------------------------- the check on the reply

_ROUTE = re.compile(r"(?<![\w:/])/[A-Za-z0-9_.{}\-]+(?:/[A-Za-z0-9_.{}\-]+)*")
_FILE = re.compile(r"\b[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)*\.(?:feature|js|ts|tsx|jsx|py|java|cs|"
                   r"csproj|json|xml|yml|yaml|md|sql|html|css|txt|sh|ps1)\b")
_COUNT = re.compile(r"(?<![\w.])\d+(?![\w.])")
_ENTITY = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b")


def violations(text: str, record: dict) -> list[str]:
    """Every route, file, count or named entity in ``text`` that the record does not contain.

    Four kinds of fact are what a plausible-sounding fabrication is made of: an endpoint nobody
    declared (``/api/orders``), a file that does not exist (``CheckoutController.cs``), a count
    that flatters the story ("three duplicates"), and a class or component named as if it had been
    read. Each is checked against the record's own text, so the check is mechanical and the same on
    every reply.

    A short file name is accepted when it names a path the record holds - a reader writing
    ``login.feature`` for ``cypress/e2e/.../login.feature`` is abbreviating, not inventing. Anything
    else is a violation and the reply is discarded.
    """
    corpus = json.dumps(record, sort_keys=True, ensure_ascii=False).lower()
    numbers = set(re.findall(r"\d+", corpus))
    found: list[str] = []

    for match in _ROUTE.finditer(text):
        route = match.group(0).rstrip(".,;:!?)\"'")
        if route and route.lower() not in corpus:
            found.append(f"the route {route}")
    for match in _FILE.finditer(text):
        name = match.group(0)
        low = name.lower()
        if low in corpus or f"/{low}" in corpus:
            continue
        found.append(f"the file {name}")
    for match in _COUNT.finditer(text):
        if match.group(0) not in numbers:
            found.append(f"the number {match.group(0)}")
    for match in _ENTITY.finditer(text):
        name = match.group(0)
        if name.lower() not in corpus:
            found.append(f"the name {name}")
    # One statement per kind: a reply that invents two routes is not five failures.
    return list(dict.fromkeys(found))


# ---------------------------------------------------------------- ledger

def _now(now: str | None) -> str:
    return now or f"{time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime())}"


def start_view(conn, case_id: str, variant: str, now: str | None = None) -> int:
    """Open a view row before the page is rendered, so its feedback links can name it.

    The row starts as ``pending`` and is closed by :func:`finish_view` with what the page actually
    carried. A view that never closes is a render that died, and it stays visible as ``pending``
    rather than being counted as a served explanation.
    """
    cur = conn.execute(
        "INSERT INTO agent_view (case_id, variant, at, served) VALUES (?,?,?,?)",
        (case_id, variant, _now(now), "pending"))
    conn.commit()
    return int(cur.lastrowid)


def finish_view(conn, view_id: int | None, outcome: Outcome | None) -> None:
    """Record what the page carried. ``None`` outcome means the page was the agent-off one."""
    if view_id is None:
        return
    if outcome is None:
        conn.execute("UPDATE agent_view SET served=? WHERE id=?", (VARIANT_OFF, view_id))
    else:
        conn.execute(
            "UPDATE agent_view SET served=?, detail=?, call_id=? WHERE id=?",
            (outcome.state, (outcome.detail or outcome.cause or "")[:200],
             outcome.call_id, view_id))
    conn.commit()


def record_view(conn, case_id: str, variant: str, served: str = VARIANT_OFF,
                detail: str = "", now: str | None = None) -> int:
    """Record one view in one statement - what an off page, or a test, needs."""
    cur = conn.execute(
        "INSERT INTO agent_view (case_id, variant, at, served, detail) VALUES (?,?,?,?,?)",
        (case_id, variant, _now(now), served, detail[:200]))
    conn.commit()
    return int(cur.lastrowid)


def _record_call(conn, *, case_id, variant, model, prompt_hash, tokens_in, tokens_out,
                 cached, wall_ms, outcome, cause) -> int:
    cur = conn.execute(
        "INSERT INTO agent_call (case_id, variant, model, prompt_hash, tokens_in, tokens_out,"
        " cached, wall_ms, outcome, cause) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (case_id, variant, model, prompt_hash, int(tokens_in), int(tokens_out),
         1 if cached else 0, int(wall_ms), outcome, cause[:200]))
    conn.commit()
    return int(cur.lastrowid)


def cached_explanation(conn, case_id: str, prompt_hash: str, model: str):
    return conn.execute(
        "SELECT * FROM agent_explanation WHERE case_id=? AND prompt_hash=? AND model=?",
        (case_id, prompt_hash, model)).fetchone()


def _store_explanation(conn, case_id, prompt_hash, model, text, tokens_in, tokens_out, now):
    conn.execute(
        "INSERT OR REPLACE INTO agent_explanation"
        " (case_id, prompt_hash, model, text, created_at, tokens_in, tokens_out)"
        " VALUES (?,?,?,?,?,?,?)",
        (case_id, prompt_hash, model, text, _now(now), int(tokens_in), int(tokens_out)))
    conn.commit()


def record_feedback(conn, view_id: int, case_id: str, variant: str, verdict: str,
                    now: str | None = None) -> bool:
    """Record one vote. ``False`` when this view has already voted for this case and variant.

    No cookie and no reader identity: the view id is the session. Clicking "this helped" and then
    "this did not" on the same page counts once, which is the most either link can honestly mean.
    """
    before = conn.total_changes
    conn.execute(
        "INSERT OR IGNORE INTO agent_feedback (case_id, variant, verdict, at, view_id)"
        " VALUES (?,?,?,?,?)", (case_id, variant, verdict, _now(now), int(view_id)))
    conn.commit()
    return conn.total_changes > before


# ---------------------------------------------------------------- the call

REFUSALS = {
    "not_configured": ("The model-written explanation is not available: this deployment has no "
                       "token from the environment, a managed identity or the az CLI."),
    "unreachable": "The model could not be reached, so no explanation was added.",
    "http_429": "The model was rate-limited, so no explanation was added.",
    "empty": "The model returned an empty reply, so no explanation was added.",
    "malformed": "The model's reply was not readable prose, so no explanation was added.",
    "rejected": "",           # filled in by the page, which names the offending fact
    "no_finding": "This case raised no finding, so there was nothing for the model to explain.",
    "unexpected": "The explanation could not be produced, so nothing was added.",
}


def rejection_sentence(outcome: Outcome) -> str:
    """The sentence for a discarded reply: what was invented, and that nothing was added."""
    invented = outcome.detail or "a fact"
    return (f"The model-written explanation was rejected because it named {invented}, which is not "
            f"in this case's record. Nothing it wrote was added to this page.")


def explain_case(conn, record: dict, *, cfg: Config, completer=None,
                 now: str | None = None, variant: str = VARIANT_ON) -> Outcome:
    """Ask the model for one explanation of ``record``, or say in one cause why there is none.

    The order matters: the cache is consulted first, so a repeat view costs nothing; the reply is
    checked before it is stored, so a fabricated fact is never written down as an answer; and every
    branch writes a ledger row, so ``/agent-report`` can weigh what was shown against what it cost.
    """
    case_id = str((record.get("case") or {}).get("id") or "")
    model = cfg.model
    system, user, prompt_hash = prompt(record, model)

    if not cfg.configured:
        return Outcome(state="not_configured", model=model, cause="not_configured",
                       detail=cfg.why_not, prompt_hash=prompt_hash)

    hit = cached_explanation(conn, case_id, prompt_hash, model)
    if hit is not None:
        call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                               prompt_hash=prompt_hash, tokens_in=0, tokens_out=0, cached=True,
                               wall_ms=0, outcome="cached", cause="")
        return Outcome(state="cached", text=hit["text"], model=model, prompt_hash=prompt_hash,
                       call_id=call_id)

    ask = completer or client.complete
    started = time.monotonic()
    try:
        completion = ask(system, user, model, endpoint_url=cfg.endpoint, access_token=cfg.token)
    except urllib.error.HTTPError as exc:
        wall = int((time.monotonic() - started) * 1000)
        cause = "http_429" if exc.code == 429 else f"http_{int(exc.code)}"
        call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                               prompt_hash=prompt_hash, tokens_in=0, tokens_out=0, cached=False,
                               wall_ms=wall, outcome="error", cause=cause)
        return Outcome(state="error", model=model, cause=cause, detail=cause,
                       prompt_hash=prompt_hash, call_id=call_id)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        wall = int((time.monotonic() - started) * 1000)
        call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                               prompt_hash=prompt_hash, tokens_in=0, tokens_out=0, cached=False,
                               wall_ms=wall, outcome="error", cause="unreachable")
        return Outcome(state="error", model=model, cause="unreachable",
                       detail=type(exc).__name__, prompt_hash=prompt_hash, call_id=call_id)
    except Exception as exc:  # noqa: BLE001 - a transport surprise is not a page crash
        wall = int((time.monotonic() - started) * 1000)
        call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                               prompt_hash=prompt_hash, tokens_in=0, tokens_out=0, cached=False,
                               wall_ms=wall, outcome="error", cause="unreachable")
        return Outcome(state="error", model=model, cause="unreachable",
                       detail=type(exc).__name__, prompt_hash=prompt_hash, call_id=call_id)
    wall = int((time.monotonic() - started) * 1000)

    text = " ".join((completion.text or "").split())
    tokens_in, tokens_out = int(completion.tokens_in or 0), int(completion.tokens_out or 0)
    cause = ""
    if not text:
        cause = "empty"
    elif len(text) < 40 or not re.search(r"[A-Za-z]{3}", text) or client.extract_json(text):
        cause = "malformed"
    if cause:
        call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                               prompt_hash=prompt_hash, tokens_in=tokens_in,
                               tokens_out=tokens_out, cached=False, wall_ms=wall,
                               outcome="error", cause=cause)
        return Outcome(state="error", model=model, cause=cause, detail=cause,
                       prompt_hash=prompt_hash, tokens_in=tokens_in, tokens_out=tokens_out,
                       call_id=call_id)

    invented = violations(text, record)
    call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                           prompt_hash=prompt_hash, tokens_in=tokens_in, tokens_out=tokens_out,
                           cached=False, wall_ms=wall,
                           outcome="rejected" if invented else "ok",
                           cause=("rejected: " + invented[0]) if invented else "")
    if invented:
        return Outcome(state="rejected", model=model, cause="rejected", detail=invented[0],
                       prompt_hash=prompt_hash, tokens_in=tokens_in, tokens_out=tokens_out,
                       call_id=call_id, violations=invented)

    _store_explanation(conn, case_id, prompt_hash, model, text, tokens_in, tokens_out, now)
    return Outcome(state="explanation", text=text, model=model, detail=model,
                   prompt_hash=prompt_hash, tokens_in=tokens_in, tokens_out=tokens_out,
                   call_id=call_id)


# ---------------------------------------------------------------- the report

# How the two variants are named to a reader. A variant is a page, not a feature: one shows the
# stored evidence, the other shows it with a model-written explanation beside it.
VARIANT_LABEL = {VARIANT_OFF: "Agent off", VARIANT_ON: "Agent on"}


def report(conn) -> list[dict]:
    """Per variant: views, explanations served, cache hits, tokens, feedback. Arithmetic only.

    Every number is a count of stored rows or a sum over them, so the page cannot say something the
    ledger does not hold. ``mean_tokens_per_explanation`` is ``None`` - rendered as "no explanation
    has been served" - rather than ``0``, which would read as a measured zero.
    """
    rows: list[dict] = []
    for variant in VARIANTS:
        views = conn.execute("SELECT COUNT(*) FROM agent_view WHERE variant=?",
                             (variant,)).fetchone()[0]
        served = conn.execute(
            "SELECT COUNT(*) FROM agent_view WHERE variant=? AND served IN ('explanation','cached')",
            (variant,)).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM agent_view WHERE variant=? AND served='rejected'",
            (variant,)).fetchone()[0]
        errors = conn.execute(
            "SELECT COUNT(*) FROM agent_view WHERE variant=? AND served IN "
            "('error','not_configured','pending')", (variant,)).fetchone()[0]
        calls, cached, fresh, tokens = conn.execute(
            "SELECT COUNT(*), SUM(cached), SUM(CASE WHEN cached=0 AND outcome='ok' THEN 1 ELSE 0 END),"
            " SUM(tokens_in + tokens_out) FROM agent_call WHERE variant=?", (variant,)).fetchone()
        calls, cached = int(calls or 0), int(cached or 0)
        fresh, tokens = int(fresh or 0), int(tokens or 0)
        wall = conn.execute("SELECT SUM(wall_ms) FROM agent_call WHERE variant=?",
                            (variant,)).fetchone()[0]
        helped, unhelpful = conn.execute(
            "SELECT SUM(verdict='helped'), SUM(verdict='did_not_help')"
            " FROM agent_feedback WHERE variant=?", (variant,)).fetchone()
        rows.append({
            "variant": variant,
            "label": VARIANT_LABEL[variant],
            "views": int(views),
            "explanation_views": int(served),
            "rejected": int(rejected),
            "errors": int(errors),
            "calls": calls,
            "cache_hits": cached,
            "explanations_written": fresh,
            "total_tokens": tokens,
            "mean_tokens_per_explanation": (round(tokens / fresh, 1) if fresh else None),
            "wall_ms": int(wall or 0),
            "helped": int(helped or 0),
            "did_not_help": int(unhelpful or 0),
        })
    return rows


def recent_calls(conn, limit: int = 20) -> list[dict]:
    """The last few calls, with what happened, so a failure is a row an operator can read."""
    out = []
    for row in conn.execute(
            "SELECT id, case_id, variant, model, tokens_in, tokens_out, cached, wall_ms, outcome,"
            " cause FROM agent_call ORDER BY id DESC LIMIT ?", (int(limit),)):
        out.append({key: row[key] for key in row.keys()})
    return out