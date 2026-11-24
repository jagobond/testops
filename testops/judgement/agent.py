"""A Foundry agent that explains one case, and the honest accounting around it.

TESTOPS-88. The deterministic verdict stays evidence. This module adds commentary beside it: a
plain-English explanation of *this* case, written from the stored record only, shown when a reader
asks for it with ``?agent=on`` and never otherwise.

Four rules this module is built around.

**The record is the whole world, and a reply must say which part of it it used.** :func:`case_record`
assembles exactly what the page reads - the verdict, the assertion text, the matched word, the
product file and line, the near-miss reason, the sources that were consulted and the ones that were
not - and gives every one of those facts an identifier the model may cite. The reply is JSON: the
explanation, and per sentence the identifiers it rests on. :func:`violations` then checks the reply
against the same record in a fixed order - an unknown citation, an uncited sentence, a fact that
disagrees with the row it cites, a number no cited row holds - and any one of them makes the reply
unusable. The page falls back to its agent-off content plus one sentence saying why. A model that
invents a route, swaps a verb, miscounts or asserts something it cannot cite cannot put it in front
of a reader.

**Every call is in the ledger.** Case, variant, model, prompt hash, tokens in, tokens out, whether
the answer came from the cache, and the wall time - one row in ``agent_call``. Every page view is a
row in ``agent_view``, including the ones served with the agent off, so ``/agent-report`` can put
value beside cost instead of asserting it.

**The cache is (case, prompt hash, model).** A second view of the same case with the same record is
free, and the page says the explanation is a stored one. The prompt hash covers the prompt text and
the model, so a changed record is a new key rather than a stale hit.

**Failure is a sentence, never a blank.** No token, an unreachable model, a non-200, a rate limit, an
empty reply, a malformed one: the agent-off page plus one sentence, and the cause in the ledger.

TESTOPS-90 adds two things to that. A citation identifier written in the prose (``claim:2405``) is
not a statistic and the number scan no longer reads it as one - the guard must never punish a model
for citing. And a rejected reply gets one repair round: the model is shown the exact violations and
asked to change only those sentences; a second rejection is the end, and the page falls back.
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

# What a view actually carried, as the ledger's word for it. A view is in exactly one of these
# states, and the report breaks every figure down by state so that a cached page is never counted as
# an explanation's value and a failed render is never counted as a loss.
STATE_FRESH = "fresh"                        # an explanation written for this view
STATE_FRESH_REPAIRED = "fresh_repaired"      # an explanation a repair round made acceptable
STATE_CACHED = "cached"                      # an explanation served from the store
STATE_REJECTED = "rejected"                  # a reply that failed the check
STATE_UNAVAILABLE = "failed_unavailable"     # the model could not answer, or answered unusably
STATE_UNCONFIGURED = "failed_unconfigured"   # no token, so nothing was attempted
STATE_NO_FINDING = "no_finding"              # the case raised no finding to explain
STATE_OFF = "off"                            # the agent was not asked for
STATE_PENDING = "pending"                    # the render started and never closed

VIEW_STATES = (STATE_FRESH, STATE_FRESH_REPAIRED, STATE_CACHED, STATE_REJECTED,
               STATE_UNAVAILABLE, STATE_UNCONFIGURED, STATE_NO_FINDING, STATE_OFF, STATE_PENDING)

# Rows written before this vocabulary existed. They are read as the state they meant, never
# rewritten: a ledger is history, and history is not edited to fit a later table.
_LEGACY_STATE = {"explanation": STATE_FRESH, "error": STATE_UNAVAILABLE,
                 "not_configured": STATE_UNCONFIGURED}


def canonical_state(served: str) -> str:
    """The state a stored ``agent_view.served`` value means in this build."""
    return _LEGACY_STATE.get(served, served)

# Part of the prompt hash. Bump it when the prompt changes: an explanation written under an older
# instruction is not the same artefact, and a reader comparing two of them is owed the difference.
PROMPT_VERSION = "explain-a-case/3"

# How long a resolved (or failed) token lookup is trusted. Long enough that a page view does not
# wait three seconds on IMDS every time, short enough that a rotated token is picked up.
TOKEN_TTL_SECONDS = 300.0

# How many findings of one case the prompt quotes. A rare case holds dozens; quoting all of them
# buys a long prompt and a vague explanation, so the first few are quoted and the prompt says so in
# as many words. The *check* on the reply still uses the whole record, so a fact from a finding the
# prompt did not quote is not a fabrication.
PROMPT_FINDING_LIMIT = 6

SYSTEM_PROMPT = """You explain one finding from a code-analysis tool to the person who has to act on it.

You will be given a record, and with it the identifiers that name each of its facts. It is the only
thing you know about this case.

You must reply with one JSON object, and nothing else:

  {"explanation": "sentence one. sentence two. ...",
   "citations": [{"sentence": 1, "facts": ["claim:12", "route:GET /rooms"]},
                 {"sentence": 2, "facts": ["file:features/panel_api.feature:17"]}]}

The explanation is four to six sentences of plain English, no headings, no bullet lists, no
markdown. Each sentence carries the identifiers it rests on. The identifiers are the ones printed
in the record and nothing else: a claim id, a route, a file and its line, a count, a reason. Copy
them exactly as they are printed.

Rules, all of them absolute:
- Every sentence must cite at least one identifier from the record. A sentence you cannot cite is a
  sentence you must not write. The identifiers belong in the "citations" array and nowhere else:
  never write one in the explanation's prose. If a sentence is about the claim whose id is 12, the
  prose says "the claim" and the citations array says "claim:12" - the prose never says "claim:12".
- Use only the facts in the record. Do not add a fact from your own knowledge, however obvious.
- A route must be quoted exactly as the record records it, with the same method. Do not change GET
  to PATCH or any other verb.
- A file must be quoted with the line number the record gives it, exactly.
- Do not use any number, digit or number word except one a cited fact holds. Do not round, estimate
  or invent a count.
- Do not name any class, function, ticket or service that the record does not name.
- Do not decide anything. The verdict in the record is the finding; you are explaining it, not
  reviewing it, and you may not suggest it is wrong.
- Say what was asserted, what the rule found, and what the reader would do about it - in that order,
  using the record's own words for the assertion.
- If something a reader would want to know is not in the record, say that the record does not
  contain it, and cite the claim whose record you are saying that about. Do not fill the gap."""



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

    state: str                      # fresh | cached | rejected | failed_* | no_finding
    text: str = ""
    model: str = ""
    cause: str = ""                 # unreachable | http_429 | empty | ... | rejected:
    detail: str = ""                # the offending fact, or the model name; never a credential
    prompt_hash: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    call_id: int | None = None
    violations: list[str] = field(default_factory=list)
    repairs: int = 0                # how many repair rounds this view paid for

    @property
    def served(self) -> bool:
        return self.state in (STATE_FRESH, STATE_FRESH_REPAIRED, STATE_CACHED)

    @property
    def sentence(self) -> str:
        """The one sentence the page shows instead of an explanation. Empty when one was served."""
        if self.served:
            return ""
        return REFUSALS.get(self.cause) or REFUSALS["unexpected"]


# ---------------------------------------------------------------- configuration

# The resolved token, its source, and the probes that produced them. ``imds`` and ``az`` are the
# token-free records :mod:`testops.judgement.client` keeps; they are cached beside the token so a
# page can explain a missing token without asking the metadata service again (TESTOPS-89).
_TOKEN_CACHE: dict[str, object] = {"at": None, "token": "", "source": "",
                                   "imds": None, "az": None}


def reset_token_cache() -> None:
    """Forget the resolved token. For a test, and for an operator who has just logged in."""
    _TOKEN_CACHE["at"] = None
    _TOKEN_CACHE["token"] = ""
    _TOKEN_CACHE["source"] = ""
    _TOKEN_CACHE["imds"] = None
    _TOKEN_CACHE["az"] = None


def _resolve(env: Mapping[str, str], clock: float) -> tuple[str, str]:
    """``(token, source)``, resolved at most once per TTL, with the probes kept beside them."""
    supplied = (env.get("TESTOPS_AGENT_TOKEN") or "").strip()
    if supplied:
        return supplied, "environment"
    cached_at = _TOKEN_CACHE.get("at")
    if not isinstance(cached_at, float) or clock - cached_at > TOKEN_TTL_SECONDS:
        token = client.managed_identity_token()
        source = "imds" if token else ""
        if not token:
            token = client.az_token()
            source = "az" if token else ""
        _TOKEN_CACHE.update(token=token, source=source, at=clock,
                            imds=client.last_identity_probe(), az=client.last_az_probe())
    return str(_TOKEN_CACHE.get("token") or ""), str(_TOKEN_CACHE.get("source") or "")


def config(environ: Mapping[str, str] | None = None, now: float | None = None) -> Config:
    """This deployment's agent configuration, with the token resolved at most once per TTL.

    ``TESTOPS_AGENT_TOKEN`` first, then the managed identity, then ``az`` (see
    :func:`testops.judgement.client.token`). Absent all three, the config is unconfigured and the
    site serves agent-off pages - it does not fail to start, and it does not pretend.
    """
    env = os.environ if environ is None else environ
    project = (env.get("TESTOPS_AGENT_PROJECT") or "").strip() or client.DEFAULT_PROJECT
    clock = time.monotonic() if now is None else now
    token, _source = _resolve(env, clock)
    return Config(project=project, endpoint=client.endpoint(env, project),
                  model=client.model_name(env), token=token)


# How each source of a token is named to a reader.
TOKEN_SOURCE_LABEL = {"environment": "the environment", "imds": "a managed identity",
                      "az": "the az CLI"}


def diagnosis(environ: Mapping[str, str] | None = None, now: float | None = None) -> dict:
    """Everything /agent-check states about this process, as plain values and no token.

    The token is resolved through the same cache the case pages use, so the page describes the
    lookup that is actually in force rather than paying for a second one. ``environment_token`` is a
    yes/no: the value never enters this dictionary (AC3).
    """
    env = os.environ if environ is None else environ
    project = (env.get("TESTOPS_AGENT_PROJECT") or "").strip() or client.DEFAULT_PROJECT
    clock = time.monotonic() if now is None else now
    token, source = _resolve(env, clock)
    imds = _as_dict(_TOKEN_CACHE.get("imds")) or client.last_identity_probe()
    az = _as_dict(_TOKEN_CACHE.get("az")) or client.last_az_probe()
    return {
        "endpoint": client.endpoint(env, project),
        "endpoint_variable": client.endpoint_variable(env),
        "model": client.model_name(env),
        "model_variable": "TESTOPS_AGENT_MODEL" if (env.get("TESTOPS_AGENT_MODEL") or "").strip() else "",
        "environment_token": bool((env.get("TESTOPS_AGENT_TOKEN") or "").strip()),
        "token_obtained": bool(token),
        "token_source": source,
        "imds": imds,
        "az": az,
    }


def _as_dict(value) -> dict:
    """A cached probe, copied, or ``{}`` when the cache holds nothing usable."""
    return dict(value) if isinstance(value, dict) else {}


def served_sentence(diag: dict) -> str:
    """One sentence: whether an explanation would be served right now, and if not, why (AC3).

    Built from the diagnosis rather than from a fresh probe, so it says what the process knows at
    the moment it is asked. It never names a token, only where one would come from.
    """
    if diag.get("token_obtained"):
        origin = TOKEN_SOURCE_LABEL.get(str(diag.get("token_source") or ""), "a token")
        return f"An explanation would be served right now: this process holds a token from {origin}."
    imds = diag.get("imds") or {}
    az = diag.get("az") or {}
    parts: list[str] = []
    if not imds.get("attempted"):
        parts.append("the metadata service was not asked")
    elif imds.get("answered"):
        parts.append("the metadata service answered")
    else:
        described = f"the metadata service answered {imds.get('status')}" \
            if imds.get("status") is not None else \
            f"the metadata service did not answer ({imds.get('cause') or 'no cause recorded'})"
        code = imds.get("error_code")
        parts.append(f"{described}{' with the error code ' + str(code) if code else ''}")
    if az.get("answered"):
        parts.append("the az CLI answered but no token was kept")
    elif not az.get("present"):
        parts.append("no az CLI is on this PATH")
    else:
        parts.append(f"the az CLI did not answer ({az.get('cause') or 'no cause recorded'})")
    return f"No explanation would be served right now: {' and '.join(parts)}."


def record_diagnosis(conn, diag: dict, now: str | None = None) -> int | None:
    """Store one diagnosis where the ledger stores everything else, and return its id.

    Nothing in ``diag`` can hold a token: the probe's own record is token-free by construction and
    the environment is reduced to a yes/no before it arrives here. ``None`` when there is nothing to
    record - a probe that was never attempted is not evidence of a failure (AC1).
    """
    if conn is None:
        return None
    imds = diag.get("imds") or {}
    az = diag.get("az") or {}
    if not imds.get("attempted") and not az.get("attempted"):
        return None
    cur = conn.execute(
        "INSERT INTO agent_token_probe (at, endpoint, endpoint_variable, model, model_variable,"
        " environment_token, token_obtained, token_source, imds_attempted, imds_answered,"
        " imds_status, imds_cause, imds_error_code, imds_detail, imds_api_version, imds_attempt,"
        " imds_elapsed_ms, imds_attempts, az_present, az_answered, az_cause, az_detail,"
        " az_elapsed_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (_now(now), str(diag.get("endpoint") or ""), str(diag.get("endpoint_variable") or ""),
         str(diag.get("model") or ""), str(diag.get("model_variable") or ""),
         1 if diag.get("environment_token") else 0, 1 if diag.get("token_obtained") else 0,
         str(diag.get("token_source") or ""), 1 if imds.get("attempted") else 0,
         1 if imds.get("answered") else 0, imds.get("status"),
         str(imds.get("cause") or ""), str(imds.get("error_code") or ""),
         str(imds.get("detail") or "")[:300], str(imds.get("answered_api_version") or ""),
         int(imds.get("answered_attempt") or 0), int(imds.get("elapsed_ms") or 0),
         json.dumps(list(imds.get("attempts") or []), sort_keys=True),
         1 if az.get("present") else 0, 1 if az.get("answered") else 0,
         str(az.get("cause") or ""), str(az.get("detail") or "")[:300],
         int(az.get("elapsed_ms") or 0)))
    conn.commit()
    return int(cur.lastrowid)


def last_probe(conn) -> dict | None:
    """The most recent stored diagnosis, as the page prints it, or ``None``."""
    row = conn.execute("SELECT * FROM agent_token_probe ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        return None
    out = {key: row[key] for key in row.keys()}
    try:
        out["imds_attempts"] = json.loads(out.get("imds_attempts") or "[]")
    except (ValueError, TypeError):
        out["imds_attempts"] = []
    return out


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
    out = {"title": finding.get("title") or "",
           "claims": [_claim_record(claim) for claim in finding.get("claims") or []]}
    if finding.get("id") not in (None, ""):
        out["id"] = finding["id"]
    return out


def _claim_record(claim: dict) -> dict:
    """One claim as the model sees it: the verdict, the assertion, the product fact, the blind spots."""
    detail = claim.get("detail") or {}
    product = detail.get("product") or {}
    provenance = claim.get("provenance") or {}
    out = {
        "id": claim.get("id"),
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


# ---------------------------------------------------------------- the citation vocabulary
#
# Every fact the check will accept a citation for, and nothing else. An identifier is a string the
# model copies: the row it names is what the prose is then held against. The set is derived from the
# record, so a citation cannot name a fact the page could not show a reader.

HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")


def _route_parts(value: str) -> tuple[str, str]:
    """``("GET", "/rooms")`` from a recorded route, or ``("", "/rooms")`` when no method is recorded."""
    text = str(value or "").strip()
    if not text:
        return "", ""
    method, _, rest = text.partition(" ")
    if method.upper() in HTTP_METHODS and rest.strip():
        return method.upper(), rest.strip()
    return "", text


def _surface_method(value) -> str:
    """A method recorded in a product surface (``api:GET /rooms@src/...``), when the route lacks one."""
    match = re.match(r"\s*[\w.-]*:?\s*(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+\S+@", str(value or ""))
    return match.group(1) if match else ""


def _row_text(values) -> str:
    """One row's values as the text the check searches. Sorted, so the prompt is stable."""
    return " \u00b7 ".join(str(v) for v in values if v not in (None, "", [], {}))


def citation_index(record: dict) -> dict[str, dict]:
    """The identifiers the record offers, each with the row it names.

    Five kinds, all drawn from what the record already holds: a claim (``claim:12``), a product route
    (``route:GET /rooms``), a file and its line (``file:features/panel_api.feature:17``), a count
    (``count:findings:6``) and a reason (``reason:12``, the near-miss reason recorded on a claim).
    The model may cite these and nothing else; :func:`violations` looks every citation up here.
    """
    index: dict[str, dict] = {}
    for finding in record.get("findings") or []:
        for claim in finding.get("claims") or []:
            claim_id = claim.get("id")
            product = claim.get("product") or {}
            copied = claim.get("copied_from") or {}
            fields = [claim.get("verdict"), claim.get("statement"), claim.get("assertion_text"),
                      claim.get("path"), claim.get("line"), claim.get("settled_by"),
                      claim.get("established_by"), claim.get("proposed_action"),
                      claim.get("cheapest_surface")] + list(claim.get("levels") or []) \
                + list(claim.get("sources_not_consulted") or []) + list(product.values()) \
                + list(copied.values())
            if claim_id not in (None, ""):
                index[f"claim:{claim_id}"] = {"kind": "claim", "id": str(claim_id),
                                              "text": _row_text(fields)}
            route = str(product.get("route") or "")
            if route:
                method, path = _route_parts(route)
                if not method:
                    method = _surface_method(product.get("surface"))
                index[f"route:{route}"] = {"kind": "route", "method": method, "path": path,
                                           "route": route, "text": _row_text([route,
                                                                              product.get("surface")])}
            path = str(claim.get("path") or "")
            if path:
                line = claim.get("line")
                suffix = f":{line}" if line not in (None, "") else ""
                index[f"file:{path}{suffix}"] = {"kind": "file", "path": path, "line": line,
                                                 "text": _row_text([path, line, copied.get("path"),
                                                                    copied.get("line")])}
            if copied.get("path"):
                suffix = f":{copied.get('line')}" if copied.get("line") not in (None, "") else ""
                index[f"file:{copied['path']}{suffix}"] = {
                    "kind": "file", "path": str(copied["path"]), "line": copied.get("line"),
                    "text": _row_text([copied.get("path"), copied.get("line"),
                                       copied.get("scenario")])}
            if claim_id not in (None, ""):
                reason = product.get("reason") or ("near miss" if product.get("near_miss") else "")
                if reason:
                    index[f"reason:{claim_id}"] = {"kind": "reason", "id": str(claim_id),
                                                   "text": _row_text([reason])}
    for name, value in (record.get("counts") or {}).items():
        index[f"count:{name}:{value}"] = {"kind": "count", "name": str(name), "value": int(value),
                                          "text": f"{name}: {value}"}
    return index


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
    # The identifiers the reply may cite, printed beside the facts they name. The model is told to
    # copy them exactly; the check accepts nothing else, so a reader of the prompt can see the same
    # closed world the check enforces.
    citations = citation_index(record)
    if citations:
        lines.append("CITATIONS - the only identifiers you may cite, one per fact:")
        for identifier, row in citations.items():
            lines.append(f"  {identifier} = {row['text']}")
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


# ---------------------------------------------------------------- the reply, and the check on it
#
# The reply is structured evidence, not prose to be pattern-matched. The model states the
# explanation and, for each sentence, the record identifiers that sentence rests on. The check then
# asks four questions in this order, and any "no" discards the reply:
#
#   (a) does every citation name a fact the record holds?
#   (b) does every sentence carry at least one citation?
#   (c) does what the sentence says agree with the row it cites - the verb with the route's method,
#       the line with the recorded line, a count with the recorded count?
#   (d) is every number in the sentence, digit or word, present in the rows the sentence cites?
#
# A deny-list of shapes could always be walked around, because it only knows what a lie looks like.
# This knows what a citation is, so a sentence that cites nothing, or cites something else, cannot
# be mistaken for evidence.

_ROUTE = re.compile(r"(?<![\w:/])/[A-Za-z0-9_.{}\-]+(?:/[A-Za-z0-9_.{}\-]+)*")
_FILE = re.compile(r"\b[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)*\.(?:feature|js|ts|tsx|jsx|py|java|cs|"
                   r"csproj|json|xml|yml|yaml|md|sql|html|css|txt|sh|ps1)\b")
_ENTITY = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b")
_METHOD = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b")
_DIGITS = re.compile(r"(?<!\w)\d+(?!\w)")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
_HAS_WORD = re.compile(r"[A-Za-z]{3,}")

# An identifier a model may write in the prose: ``claim:12``, ``reason:12``. The digits in it name a
# row; they are not a statistic about the case, so the number scan must not read them as one. A reply
# that writes its own citation id in a sentence is citing, and the guard must not punish it for that
# (TESTOPS-90: the number scan rejected the honest sentence that named ``claim:2405``).
_CITATION_ID = re.compile(r"\b(?:claim|reason):\d+\b")

# A count can be written as a word as easily as as a digit, and the reviewer's model wrote "four
# findings" where the record held six. Words are read as numbers, digits are read as numbers, and
# both are held against the same rows.
_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}
_NUMBER_WORD = re.compile(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b", re.I)


@dataclass(frozen=True)
class Reply:
    """A reply that parsed: the prose, and the facts each sentence (1-based) cites."""

    text: str
    citations: dict[int, tuple[str, ...]]


def split_sentences(text: str) -> list[str]:
    """The prose as sentences. Whitespace is normalised first, so the page renders one paragraph."""
    return [part for part in _SENTENCE_BREAK.split(" ".join(str(text).split())) if part]


def _as_json_object(raw: str) -> dict | None:
    """The reply as a JSON object, allowing a model that wraps it in a markdown fence."""
    candidate = raw.strip()
    for attempt in (candidate, candidate.strip("`"), candidate[candidate.find("{"):]
                    if "{" in candidate else candidate):
        try:
            value = json.loads(attempt)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict):
            return value
    return client.extract_json(candidate)


REPAIRABLE = "repairable"

# The exact faults a repair round quotes back at the model. A repairable reply is not a bad answer:
# it is one field short of an answer, and the fault names the field and the shape it must take.
FAULT_OMITTED_CITATIONS = (
    "you wrote the explanation but omitted the citations array - add one entry per sentence")
FAULT_CITATIONS_AS_STRING = (
    'you sent the citations as a string - send it as a JSON array of {"sentence": n, '
    '"facts": [...]} entries')
FAULT_EMPTY_CITATIONS = (
    "you sent an empty citations array - add one entry per sentence")
FAULT_MISSING_SENTENCE = (
    "the citations name sentence {number}, which does not exist - the explanation has "
    "{count} sentences")
FAULT_BAD_ENTRY = (
    'the citations array holds an entry that is not {"sentence": n, "facts": [...]} - send one '
    "entry per sentence, with the sentence's number and the facts it rests on")


@dataclass(frozen=True)
class Reading:
    """What a raw reply is, before anything is done about it.

    ``cause`` is empty for a usable reply, ``malformed`` or ``empty`` for one no second call could
    rescue, and ``repairable`` for one that carries its explanation but no usable citations - the
    shape that used to be thrown away as malformed. ``fault`` is the sentence the repair prompt
    quotes back at the model; ``text`` is the explanation it already wrote.
    """

    reply: Reply | None = None
    cause: str = ""
    fault: str = ""
    text: str = ""


def _citations_fault(citations, sentence_count: int) -> str:
    """Why the citations cannot be read, in the words the model is told - or ``""`` if they can."""
    if citations is None:
        return FAULT_OMITTED_CITATIONS
    if isinstance(citations, str):
        return FAULT_CITATIONS_AS_STRING
    if not isinstance(citations, list):
        return FAULT_OMITTED_CITATIONS
    if not citations:
        return FAULT_EMPTY_CITATIONS
    faults: list[str] = []
    for entry in citations:
        if not isinstance(entry, dict):
            faults.append(FAULT_BAD_ENTRY)
            continue
        number, facts = entry.get("sentence"), entry.get("facts")
        if isinstance(number, bool) or not isinstance(number, int):
            faults.append(FAULT_BAD_ENTRY)
            continue
        if not 1 <= number <= sentence_count:
            faults.append(FAULT_MISSING_SENTENCE.format(number=number, count=sentence_count))
            continue
        if not isinstance(facts, list) or not all(
                isinstance(fact, str) and fact.strip() for fact in facts):
            faults.append(FAULT_BAD_ENTRY)
    return "; ".join(dict.fromkeys(faults))


def read_reply(raw: str) -> Reading:
    """The reply as a :class:`Reading`: usable, repairable, or the cause it is neither.

    A JSON object with a real explanation and citations that do not parse is **repairable**: the
    prose is already written, only the citations array is missing or the wrong shape, and the one
    repair round can ask for it. A reply that is not JSON, or has no explanation at all, has nothing
    to repair - a second call would be a guess - so it stays ``malformed`` (AC2).
    """
    if not str(raw or "").strip():
        return Reading(cause="empty")
    payload = _as_json_object(raw)
    if payload is None:
        return Reading(cause="malformed")
    explanation, citations = payload.get("explanation"), payload.get("citations")
    if not isinstance(explanation, str):
        return Reading(cause="malformed")
    text = " ".join(explanation.split())
    sentences = split_sentences(text)
    if len(text) < 40 or not _HAS_WORD.search(text) or not sentences:
        return Reading(cause="malformed")
    fault = _citations_fault(citations, len(sentences))
    if fault:
        return Reading(cause=REPAIRABLE, fault=fault, text=text)
    assert isinstance(citations, list), "a fault-free citations value is a list"
    cited: dict[int, list[str]] = {}
    for entry in citations:
        number, facts = entry["sentence"], entry["facts"]
        cited.setdefault(number, []).extend(fact.strip() for fact in facts)
    return Reading(reply=Reply(text=text, citations={
        number: tuple(dict.fromkeys(facts)) for number, facts in cited.items()}))


def parse_reply(raw: str) -> tuple[Reply | None, str]:
    """The reply as :class:`Reply`, or the cause why it is not one.

    The causes are ``empty``, ``malformed`` and ``repairable``. ``repairable`` means the explanation
    is there and only the citations array is missing or unusable; :func:`read_reply` also returns
    the fault to quote at the model.
    """
    reading = read_reply(raw)
    return reading.reply, reading.cause


# One repair round. A reply that failed the check is shown its own violations once, and asked to
# change only the sentences they name. A second failure is the end of it: the page falls back to the
# honest sentence and the view is recorded as rejected. One round, because the alternative - asking
# again and again until something passes - is a way of buying a pass rather than writing an
# explanation, and it multiplies the cost of a model that cannot follow the instructions.
REPAIR_ROUNDS = 1


def repair_prompt(record: dict, model: str, reply: Reply,
                  invented: list[str]) -> tuple[str, str, str]:
    """The prompt that asks once for the named sentences to be fixed, and the hash that keys it.

    The model is shown its own reply and the *exact* violations the check found, and told that only
    the sentences those violations name may change. Every other sentence and every citation must
    come back as it was, so a repair cannot quietly rewrite a reply the check has already accepted
    sentence by sentence.
    """
    system, user, _ = prompt(record, model)
    reasons = "\n".join(f"  - {violation}" for violation in invented)
    previous = {"explanation": reply.text,
                "citations": [{"sentence": number, "facts": list(facts)}
                              for number, facts in sorted(reply.citations.items())]}
    user = (f"{user}\n\nYour previous reply was rejected. These are the exact violations:\n{reasons}\n\n"
            f"Your previous reply was:\n{json.dumps(previous)}\n\n"
            "Write the explanation again. Change only the sentences those violations name, and "
            "leave every other sentence and every citation exactly as it was. The identifiers from "
            "the record's CITATIONS list belong in the citations array only - never write one in the "
            "prose. Reply with one JSON object in the same shape, and nothing else.")
    body = f"{PROMPT_VERSION}\n{system}\n{user}\n--\n{model}"
    try:
        digest = hashlib.sha256(body.encode()).hexdigest()[:16]
    except UnicodeEncodeError:  # a record with undecodable text still gets a stable key
        digest = hashlib.sha256(body.encode("utf-8", "replace")).hexdigest()[:16]
    return system, user, digest


def citations_repair_prompt(record: dict, model: str, text: str,
                            fault: str) -> tuple[str, str, str]:
    """The prompt that asks once for the citations array a reply left out (TESTOPS-91 AC1).

    The explanation is already written, so the whole original prompt and the model's own prose are
    shown back, and the *exact* fault - not a summary of it - is quoted. Only the citations array is
    asked for: the prose is not to be rewritten, so a repair cannot become a second attempt at the
    answer. The hash keys the repair like any other call, so its tokens land in their own row.
    """
    system, user, _ = prompt(record, model)
    user = (f"{user}\n\nYour previous reply was rejected for one reason: {fault}.\n\n"
            f"Your previous explanation was:\n{text}\n\n"
            "Write the explanation again exactly as you wrote it, and add a \"citations\" array "
            "with one entry for each sentence, counting from 1: "
            "{\"sentence\": 1, \"facts\": [\"claim:12\"]}. Every fact must be an identifier from "
            "the record's CITATIONS list. Reply with one JSON object in the same shape, and "
            "nothing else.")
    body = f"{PROMPT_VERSION}\n{system}\n{user}\n--\n{model}"
    try:
        digest = hashlib.sha256(body.encode()).hexdigest()[:16]
    except UnicodeEncodeError:  # a record with undecodable text still gets a stable key
        digest = hashlib.sha256(body.encode("utf-8", "replace")).hexdigest()[:16]
    return system, user, digest


def _route_paths(sentence: str) -> list[str]:
    paths: list[str] = []
    for match in _ROUTE.finditer(sentence):
        path = match.group(0).rstrip(".,;:!?)\"'")
        if path and path not in paths:
            paths.append(path)
    return paths


def _numbers_in(text: str) -> set[int]:
    """Every whole number the text holds, read from digits and from words."""
    found = {int(digits) for digits in _DIGITS.findall(str(text))}
    for word in _NUMBER_WORD.findall(str(text)):
        found.add(_NUMBER_WORDS[word.lower()])
    return found


def _numbers_written(sentence: str) -> list[tuple[str, int]]:
    """Each number as it was written, so the rejection can quote the model's own word."""
    out: list[tuple[str, int]] = []
    for digits in _DIGITS.findall(sentence):
        out.append((digits, int(digits)))
    for word in _NUMBER_WORD.findall(sentence):
        out.append((word, _NUMBER_WORDS[word.lower()]))
    return out


def _file_matches(name: str, path: str) -> bool:
    """A short file name abbreviates a stored path; a different name does not."""
    low, stored = name.lower(), str(path or "").lower()
    return bool(low) and (low == stored or stored.endswith("/" + low))


def violations(reply, record: dict) -> list[str]:
    """Everything wrong with a reply, in the order the four questions are asked.

    ``reply`` is a :class:`Reply`; a bare string is accepted as prose that cites nothing, which is
    how every sentence in it fails question (b). The first violation is what the page names.
    """
    index = citation_index(record)
    if isinstance(reply, Reply):
        text, citations = reply.text, reply.citations
    else:
        text, citations = " ".join(str(reply).split()), {}
    sentences = split_sentences(text)
    found: list[str] = []

    # (a) A citation the record does not offer. Reported as the identifier, because that is what the
    # model claimed the record said.
    for facts in citations.values():
        for fact in facts:
            if fact not in index:
                found.append(f"the citation {fact}")

    for number, sentence in enumerate(sentences, start=1):
        facts = citations.get(number, ())
        rows = [index[fact] for fact in facts if fact in index]
        # (b) A sentence with no evidence behind it is not an explanation, however plausible.
        if not facts:
            found.append(f"the sentence {number}, which cites nothing")
            continue

        paths = _route_paths(sentence)
        methods = {method.upper() for method in _METHOD.findall(sentence)}
        reported_numbers: set[int] = set()
        for path in paths:
            cited = [row for row in rows if row["kind"] == "route" and row["path"] == path]
            if not cited:
                found.append(f"the route {path}, which no cited fact names")
        if len(paths) == 1:
            cited_routes = [row for row in rows if row["kind"] == "route"]
            allowed = {row["method"] for row in cited_routes if row["method"]}
            for method in sorted(methods):
                if allowed and method not in allowed:
                    for row in cited_routes:
                        if row["method"] and row["path"] == paths[0]:
                            # (c) The verb the prose used against the verb the row records.
                            found.append(f"the verb {method}, where the record says {row['route']}")

        for name in _FILE.findall(sentence):
            if not any(row["kind"] == "file" and _file_matches(name, row["path"]) for row in rows):
                found.append(f"the file {name}, which no cited fact names")

        # (c) A line number the prose attaches to a file must be the line the cited row records -
        # whether or not a full stop follows it.
        cited_lines = {int(str(row["line"])) for row in rows
                       if row["kind"] == "file" and str(row.get("line") or "").strip().isdigit()}
        for written in re.findall(r"\bline\s+(\d+)\b", sentence, re.I):
            value = int(written)
            if cited_lines and value not in cited_lines:
                reported_numbers.add(value)
                found.append(f"the line {value}, where the record says "
                             f"{sorted(cited_lines)[0]}")

        # (d) Every number, digit or word, must be one the cited rows hold. Identifiers written in
        # the prose are masked first: the digits in ``claim:2405`` name a row, they do not measure
        # anything, and scanning them punished the model for citing (TESTOPS-90).
        scanned = _CITATION_ID.sub(" ", sentence)
        allowed_numbers: set[int] = set()
        for row in rows:
            allowed_numbers |= _numbers_in(row["text"])
        count_rows = [row for row in rows if row["kind"] == "count"]
        for written, value in _numbers_written(scanned):
            if value in allowed_numbers or value in reported_numbers:
                continue
            named = [row for row in count_rows if row["name"].lower() in sentence.lower()]
            if named:
                # (c) A count against the count the cited row records.
                found.append(f"the number {written}, where the record says "
                             f"{named[0]['value']} {named[0]['name']}")
            else:
                found.append(f"the number {written}, which no cited fact holds")

        for name in _ENTITY.findall(sentence):
            if not any(name.lower() in row["text"].lower() for row in rows):
                found.append(f"the name {name}, which no cited fact holds")

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


def _record_unconfigured(conn) -> None:
    """Put today's cause in the ledger when a page finds it has no token (AC1).

    Only when this process has already probed: a page must not spend ten seconds talking to IMDS to
    decorate its own failure, and a config injected by a test or a caller has probed nothing. When it
    has probed, the probe is the answer and it belongs beside every other ledger row.
    """
    if not isinstance(_TOKEN_CACHE.get("imds"), dict) and not isinstance(_TOKEN_CACHE.get("az"), dict):
        return
    try:
        record_diagnosis(conn, diagnosis())
    except Exception:  # noqa: BLE001 - a ledger write must never break the page it describes
        pass


def rejection_sentence(outcome: Outcome) -> str:
    """The sentence for a discarded reply: what was wrong with it, and that nothing was added."""
    invented = outcome.detail or "a fact the record does not hold"
    return (f"The model-written explanation was rejected: {invented}. Nothing it wrote was added "
            f"to this page.")


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
        _record_unconfigured(conn)
        return Outcome(state=STATE_UNCONFIGURED, model=model, cause="not_configured",
                       detail=cfg.why_not, prompt_hash=prompt_hash)

    hit = cached_explanation(conn, case_id, prompt_hash, model)
    if hit is not None:
        call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                               prompt_hash=prompt_hash, tokens_in=0, tokens_out=0, cached=True,
                               wall_ms=0, outcome="cached", cause="")
        return Outcome(state=STATE_CACHED, text=hit["text"], model=model, prompt_hash=prompt_hash,
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
        return Outcome(state=STATE_UNAVAILABLE, model=model, cause=cause, detail=cause,
                       prompt_hash=prompt_hash, call_id=call_id)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        wall = int((time.monotonic() - started) * 1000)
        call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                               prompt_hash=prompt_hash, tokens_in=0, tokens_out=0, cached=False,
                               wall_ms=wall, outcome="error", cause="unreachable")
        return Outcome(state=STATE_UNAVAILABLE, model=model, cause="unreachable",
                       detail=type(exc).__name__, prompt_hash=prompt_hash, call_id=call_id)
    except Exception as exc:  # noqa: BLE001 - a transport surprise is not a page crash
        wall = int((time.monotonic() - started) * 1000)
        call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                               prompt_hash=prompt_hash, tokens_in=0, tokens_out=0, cached=False,
                               wall_ms=wall, outcome="error", cause="unreachable")
        return Outcome(state=STATE_UNAVAILABLE, model=model, cause="unreachable",
                       detail=type(exc).__name__, prompt_hash=prompt_hash, call_id=call_id)
    wall = int((time.monotonic() - started) * 1000)

    tokens_in, tokens_out = int(completion.tokens_in or 0), int(completion.tokens_out or 0)
    # A reply is read before it is judged. Three shapes matter: usable; *repairable* - the
    # explanation is written and only the citations array is missing or unusable, which used to be
    # thrown away as malformed (TESTOPS-91); and unusable, where a second call would be a guess.
    reading = read_reply(completion.text or "")
    repairs = 0
    if reading.cause == REPAIRABLE:
        # One repair round, sharing the budget with the violations repair below: the model is shown
        # the explanation it already wrote and the exact fault, and asked only for the citations.
        repairs = 1
        _record_call(conn, case_id=case_id, variant=variant, model=model,
                     prompt_hash=prompt_hash, tokens_in=tokens_in, tokens_out=tokens_out,
                     cached=False, wall_ms=wall, outcome="error", cause=REPAIRABLE)
        repair_system, repair_user, repair_hash = citations_repair_prompt(
            record, model, reading.text, reading.fault)
        started = time.monotonic()
        try:
            completion = ask(repair_system, repair_user, model,
                             endpoint_url=cfg.endpoint, access_token=cfg.token)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, TimeoutError):
            wall = int((time.monotonic() - started) * 1000)
            call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                                   prompt_hash=repair_hash, tokens_in=0, tokens_out=0,
                                   cached=False, wall_ms=wall, outcome="error", cause="unreachable")
            return Outcome(state=STATE_UNAVAILABLE, model=model, cause="unreachable",
                           detail="unreachable", prompt_hash=prompt_hash,
                           tokens_in=tokens_in, tokens_out=tokens_out, call_id=call_id,
                           repairs=repairs)
        except Exception:  # noqa: BLE001 - a transport surprise is not a page crash
            wall = int((time.monotonic() - started) * 1000)
            call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                                   prompt_hash=repair_hash, tokens_in=0, tokens_out=0,
                                   cached=False, wall_ms=wall, outcome="error", cause="unreachable")
            return Outcome(state=STATE_UNAVAILABLE, model=model, cause="unreachable",
                           detail="unreachable", prompt_hash=prompt_hash,
                           tokens_in=tokens_in, tokens_out=tokens_out, call_id=call_id,
                           repairs=repairs)
        wall = int((time.monotonic() - started) * 1000)
        repair_in, repair_out = int(completion.tokens_in or 0), int(completion.tokens_out or 0)
        tokens_in, tokens_out = tokens_in + repair_in, tokens_out + repair_out
        reading = read_reply(completion.text or "")
        if reading.cause or reading.reply is None:
            call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                                   prompt_hash=repair_hash, tokens_in=repair_in,
                                   tokens_out=repair_out, cached=False, wall_ms=wall,
                                   outcome="error", cause="malformed")
            return Outcome(state=STATE_UNAVAILABLE, model=model, cause="malformed",
                           detail="malformed", prompt_hash=prompt_hash,
                           tokens_in=tokens_in, tokens_out=tokens_out, call_id=call_id,
                           repairs=repairs)
        reply = reading.reply
        invented = violations(reply, record)
        call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                               prompt_hash=repair_hash, tokens_in=repair_in,
                               tokens_out=repair_out, cached=False, wall_ms=wall,
                               outcome="rejected" if invented else "ok",
                               cause=("rejected: " + invented[0]) if invented else "")
    elif reading.cause:
        call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                               prompt_hash=prompt_hash, tokens_in=tokens_in,
                               tokens_out=tokens_out, cached=False, wall_ms=wall,
                               outcome="error", cause=reading.cause)
        return Outcome(state=STATE_UNAVAILABLE, model=model, cause=reading.cause,
                       detail=reading.cause, prompt_hash=prompt_hash,
                       tokens_in=tokens_in, tokens_out=tokens_out, call_id=call_id)
    else:
        assert reading.reply is not None
        reply = reading.reply
        invented = violations(reply, record)
        call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                               prompt_hash=prompt_hash, tokens_in=tokens_in,
                               tokens_out=tokens_out, cached=False, wall_ms=wall,
                               outcome="rejected" if invented else "ok",
                               cause=("rejected: " + invented[0]) if invented else "")
    # One repair round (AC3): the model is shown the exact violations and asked to change only those
    # sentences. The reply is checked again from scratch, so a repair buys nothing but a second
    # chance to satisfy the same check - it cannot relax it.
    while invented and repairs < REPAIR_ROUNDS:
        repairs += 1
        repair_system, repair_user, repair_hash = repair_prompt(record, model, reply, invented)
        started = time.monotonic()
        try:
            completion = ask(repair_system, repair_user, model,
                             endpoint_url=cfg.endpoint, access_token=cfg.token)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, TimeoutError):
            # The repair could not be asked for. The original reply is still rejected, so the fallback
            # is the honest sentence - and the attempt is still a row in the ledger.
            wall = int((time.monotonic() - started) * 1000)
            call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                                   prompt_hash=repair_hash, tokens_in=0, tokens_out=0,
                                   cached=False, wall_ms=wall, outcome="error", cause="unreachable")
            break
        except Exception:  # noqa: BLE001 - a transport surprise is not a page crash
            wall = int((time.monotonic() - started) * 1000)
            call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                                   prompt_hash=repair_hash, tokens_in=0, tokens_out=0,
                                   cached=False, wall_ms=wall, outcome="error", cause="unreachable")
            break
        wall = int((time.monotonic() - started) * 1000)
        repair_in, repair_out = int(completion.tokens_in or 0), int(completion.tokens_out or 0)
        tokens_in, tokens_out = tokens_in + repair_in, tokens_out + repair_out
        candidate, cause = parse_reply(completion.text or "")
        if cause:
            call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                                   prompt_hash=repair_hash, tokens_in=repair_in,
                                   tokens_out=repair_out, cached=False, wall_ms=wall,
                                   outcome="error", cause=cause)
            break
        assert candidate is not None
        reply = candidate
        invented = violations(reply, record)
        call_id = _record_call(conn, case_id=case_id, variant=variant, model=model,
                               prompt_hash=repair_hash, tokens_in=repair_in,
                               tokens_out=repair_out, cached=False, wall_ms=wall,
                               outcome="rejected" if invented else "ok",
                               cause=("rejected: " + invented[0]) if invented else "")

    if invented:
        return Outcome(state=STATE_REJECTED, model=model, cause="rejected", detail=invented[0],
                       prompt_hash=prompt_hash, tokens_in=tokens_in, tokens_out=tokens_out,
                       call_id=call_id, violations=invented, repairs=repairs)

    text = reply.text
    _store_explanation(conn, case_id, prompt_hash, model, text, tokens_in, tokens_out, now)
    # A repaired explanation is distinguished from a first-time one in the ledger, so the A/B can
    # price the repair round separately instead of folding it into "fresh" (AC4).
    return Outcome(state=STATE_FRESH_REPAIRED if repairs else STATE_FRESH,
                   text=text, model=model, detail=model,
                   prompt_hash=prompt_hash, tokens_in=tokens_in, tokens_out=tokens_out,
                   call_id=call_id, repairs=repairs)


# ---------------------------------------------------------------- the report

# How the two variants are named to a reader. A variant is a page, not a feature: one shows the
# stored evidence, the other shows it with a model-written explanation beside it.
VARIANT_LABEL = {VARIANT_OFF: "Agent off", VARIANT_ON: "Agent on"}

# How each state is named to a reader, and whether it is value (an explanation a reader saw), cost
# (a call that was paid for and thrown away) or neither.
STATE_LABEL = {
    STATE_FRESH: "fresh - an explanation written for this view",
    STATE_FRESH_REPAIRED: "fresh_repaired - an explanation a repair round made acceptable",
    STATE_CACHED: "cached - an explanation served from the store",
    STATE_REJECTED: "rejected - a reply that failed the check",
    STATE_UNAVAILABLE: "failed, unavailable - the model could not answer, or answered unusably",
    STATE_UNCONFIGURED: "failed, unconfigured - no token, so nothing was attempted",
    STATE_NO_FINDING: "no finding - there was nothing to explain",
    STATE_OFF: "agent off - no explanation was asked for",
    STATE_PENDING: "pending - a render that never closed",
}

# The raw ``agent_view.served`` values that mean each state, legacy spellings included, so the
# arithmetic reads rows written before this vocabulary existed without rewriting them.
_STATE_VALUES = {state: tuple([state] + [raw for raw, canon in _LEGACY_STATE.items() if canon == state])
                 for state in VIEW_STATES}


def _state_numbers(conn, variant: str, state: str) -> dict:
    """One variant in one state: views, calls, tokens, cache hits and votes.

    Calls and their tokens are joined through ``agent_view.call_id``, so a rejected call's tokens are
    counted in the rejected state - they were paid for, and the reader is owed the distinction
    between what was shown and what was merely spent. Votes are joined the same way, through the
    view the reader voted on: a vote cast on a cached page is a vote about the cached page.
    """
    values = _STATE_VALUES[state]
    marks = ",".join("?" for _ in values)
    views = conn.execute(
        f"SELECT COUNT(*) FROM agent_view WHERE variant=? AND served IN ({marks})",
        (variant, *values)).fetchone()[0]
    calls, cached, written, tokens, wall = conn.execute(
        f"SELECT COUNT(*), SUM(c.cached),"
        f" SUM(CASE WHEN c.cached=0 AND c.outcome='ok' THEN 1 ELSE 0 END),"
        f" SUM(c.tokens_in + c.tokens_out), SUM(c.wall_ms)"
        f" FROM agent_call c JOIN agent_view v ON v.call_id = c.id"
        f" WHERE v.variant=? AND v.served IN ({marks})", (variant, *values)).fetchone()
    helped, unhelpful = conn.execute(
        f"SELECT SUM(f.verdict='helped'), SUM(f.verdict='did_not_help')"
        f" FROM agent_feedback f JOIN agent_view v ON v.id = f.view_id"
        f" WHERE v.variant=? AND v.served IN ({marks})", (variant, *values)).fetchone()
    calls, cached = int(calls or 0), int(cached or 0)
    written, tokens = int(written or 0), int(tokens or 0)
    return {"state": state, "label": STATE_LABEL[state], "views": int(views),
            "calls": calls, "cache_hits": cached, "explanations_written": written,
            "total_tokens": tokens, "wall_ms": int(wall or 0),
            "helped": int(helped or 0), "did_not_help": int(unhelpful or 0),
            "value": state in (STATE_FRESH, STATE_FRESH_REPAIRED, STATE_CACHED),
            "cost": state in (STATE_REJECTED, STATE_UNAVAILABLE)}


def report(conn) -> list[dict]:
    """Per variant, and per state within it: views, explanations, cache hits, tokens, votes.

    Every number is a count of stored rows or a sum over them, so the page cannot say something the
    ledger does not hold. ``mean_tokens_per_explanation`` is ``None`` - rendered as "no explanation
    has been served" - rather than ``0``, which would read as a measured zero.

    The variant totals are kept for the reader who wants one number, but they are no longer the only
    view: ``states`` breaks every figure down by what the view actually was, so a cached page is
    never counted as an explanation's value and a failed render is never counted as a loss.
    """
    rows: list[dict] = []
    for variant in VARIANTS:
        states = {state: _state_numbers(conn, variant, state) for state in VIEW_STATES}
        served = (states[STATE_FRESH]["views"] + states[STATE_FRESH_REPAIRED]["views"]
                  + states[STATE_CACHED]["views"])
        calls = sum(entry["calls"] for entry in states.values())
        cached_hits = sum(entry["cache_hits"] for entry in states.values())
        fresh = sum(entry["explanations_written"] for entry in states.values())
        tokens = sum(entry["total_tokens"] for entry in states.values())
        # A call that no view closed cannot be attributed to a state. It is counted here as itself,
        # so the variant total is the whole ledger and the states are a breakdown of it, not a
        # quieter number that happens to leave a call out.
        unlinked_calls, unlinked_tokens = conn.execute(
            "SELECT COUNT(*), SUM(tokens_in + tokens_out) FROM agent_call c WHERE variant=?"
            " AND NOT EXISTS (SELECT 1 FROM agent_view v WHERE v.call_id = c.id)",
            (variant,)).fetchone()
        unlinked_calls, unlinked_tokens = int(unlinked_calls or 0), int(unlinked_tokens or 0)
        rows.append({
            "variant": variant,
            "label": VARIANT_LABEL[variant],
            "views": sum(entry["views"] for entry in states.values()),
            "explanation_views": served,
            "repaired_accepts": states[STATE_FRESH_REPAIRED]["views"],
            "rejected": states[STATE_REJECTED]["views"],
            "errors": states[STATE_UNAVAILABLE]["views"] + states[STATE_UNCONFIGURED]["views"],
            "calls": calls + unlinked_calls,
            "cache_hits": cached_hits,
            "explanations_written": fresh,
            "total_tokens": tokens + unlinked_tokens,
            "unlinked_calls": unlinked_calls,
            "unlinked_tokens": unlinked_tokens,
            "mean_tokens_per_explanation": (round((tokens + unlinked_tokens) / fresh, 1)
                                            if fresh else None),
            "wall_ms": sum(entry["wall_ms"] for entry in states.values()),
            "helped": sum(entry["helped"] for entry in states.values()),
            "did_not_help": sum(entry["did_not_help"] for entry in states.values()),
            "states": states,
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