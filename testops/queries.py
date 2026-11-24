"""Read models for the UI.

Deliberately separate from the analysers: a view may not need every column, and a UI that reaches into the store
for raw joins ends up encoding analysis logic in templates. Each function here answers one screen's question and
returns plain dicts.
"""
from __future__ import annotations

import ast
import difflib
import json
import re
import sqlite3

from . import blobs, cases, config, services, sources
from .analysers import is_registered
from .extract import csproj, gherkin, stepbindings
from .links import GITHUB, blob_permalink, permalink, short_location
from .surfaces import discover as surface_discovery
from .surfaces import java as java_surface


def _json(s, default=None):
    try:
        return json.loads(s) if s else (default if default is not None else {})
    except json.JSONDecodeError:
        return default if default is not None else {}


# The four fields that answer "where is this asserted?". A claim is unverifiable without them, so
# every read model carries them together and a v1 claim carries them as None - not as "" and not as 0.
PROVENANCE_FIELDS = ("assertion_text", "assertion_path", "assertion_line", "assertion_commit")

# The three states a claim's source assessment can be in. They are distinct values because they are
# distinct facts: "nobody looked", "looked, nothing missing", "looked, these were not connected". A
# page that derives its sentence from anything but this value can put a guarantee on the wrong one.
SOURCES_NOT_ASSESSED = "not_assessed"
SOURCES_NONE_MISSING = "none_missing"
SOURCES_SOME_MISSING = "some_missing"


def _list_or_none(text: str | None, field: str):
    """Decode a JSON list, keeping NULL and [] distinct.

    NULL means "nothing was recorded"; [] means "nothing was missing". Coercing either into the other
    turns absence into a result, which is the one thing this store may never do.
    """
    if text is None:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"claim.{field} holds unparseable JSON: {text!r}") from exc
    if not isinstance(value, list):
        raise ValueError(f"claim.{field} should hold a JSON list, found {value!r}")
    return value


SUMMARY_CHARS = 400
SNIPPET_CONTEXT = 2
STEPDEF_LINES = 10


def _first_sentence(text: str) -> str:
    """The first sentence of ``text``, whole. A string with no sentence break is returned as is."""
    return re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]


def summary_of(statement: str | None, proposed_action: str | None) -> dict:
    """The stored statement and action as one record, for callers that want them together.

    Since TESTOPS-23 the case page does not render this block: the argument quotes the asserted step
    once, so a summary that repeated the analyser's statement was the repetition the Product Owner
    was reading. The read model keeps the pair because it is a faithful copy of two stored fields.
    ``action`` is ``None`` when no action was recorded - a page must say that, not invent one.
    """
    text = (statement or "").strip()
    truncated = False
    if text and len(text) > SUMMARY_CHARS:
        first = _first_sentence(text)
        truncated = first != text
        text = first
    return {"statement": text, "action": (proposed_action or "").strip() or None,
            "truncated": truncated}


def claim_view(row, repo: str | None = None) -> dict:
    """One claim as a screen sees it: statement, provenance and blind spots, always together.

    The only constructor of a claim read model - callers never assemble these keys themselves, so no
    page can render a claim that is missing the coordinates its reader needs to check it.

    ``permalink`` is built from the claim's *own* commit, never from the snapshot's current tip and
    never from HEAD: a reader following it must land on the file as it was when the claim was read.
    ``repo`` is the repository the assertion's path lives in, which the claim does not store.
    """
    _, _, scenario = row["subject_ref"].partition("#")
    provenance = {field: row[field] for field in PROVENANCE_FIELDS}
    assessed, missing, sources_state = _sources_state(row)
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "analyser": row["analyser"],
        "schema_version": row["schema_version"],
        "verdict": row["verdict"],
        "statement": row["statement"],
        "confidence": row["confidence"],
        "subject": row["subject_ref"],
        "scenario": scenario,
        "provenance": provenance,
        "permalink": blob_permalink(repo, provenance["assertion_commit"],
                                    provenance["assertion_path"], provenance["assertion_line"]),
        # The observation rows this claim rests on. ``[]`` - not NULL - is the honest answer for a
        # claim whose steps bound nothing: the column is NOT NULL, so an empty list is a recorded
        # fact, and a page may say "the run bound nothing here" rather than "nothing was recorded".
        "support": [int(v) for v in (_list_or_none(row["support"], "support") or [])],
        # Three facts, three fields. ``sources_assessed`` says whether a registry was consulted at
        # all; ``sources_missing`` is what it said (NULL when it was never asked); ``sources_state``
        # names the combination so no caller has to infer it from a falsy list.
        "sources_assessed": assessed,
        "sources_missing": missing,
        "sources_state": sources_state,
        "span": _list_or_none(row["span"], "span"),
        "interaction_label": row["interaction_label"],
        "interaction_code": row["interaction_code"],
        "established_by": row["established_by"],
        "proposed_action": row["proposed_action"],
        # The stored statement, as the row recorded it. The case page no longer renders it: since
        # TESTOPS-23 the page argues from the quoted step, and the index shows that step too. The
        # field survives because the statement is evidence of what the analyser concluded.
        "summary": summary_of(row["statement"], row["proposed_action"]),
    }


def _sources_state(row) -> tuple[bool, list | None, str]:
    """Decode the source-assessment pair, refusing a row whose two halves contradict each other.

    ``sources_assessed = 0`` with a list is a list nobody recorded a question for; ``1`` with NULL is
    "assessed" with nothing to show. The store's CHECK refuses both, so a row that holds either has
    been written around the store - and reading it as a fact is exactly the guarantee this state
    exists to prevent. Loud beats plausible here.
    """
    missing = _list_or_none(row["sources_missing"], "sources_missing")
    assessed = bool(row["sources_assessed"])
    if assessed and missing is None:
        raise ValueError("claim.sources_assessed is set but claim.sources_missing is NULL: a claim "
                         "cannot have been assessed without recording what the assessment said")
    if not assessed and missing is not None:
        raise ValueError(f"claim.sources_missing is {missing!r} but no assessment was recorded: a "
                         "list without an assessment is a default, not a fact")
    if not assessed:
        return False, None, SOURCES_NOT_ASSESSED
    return True, missing, (SOURCES_SOME_MISSING if missing else SOURCES_NONE_MISSING)


def claim_read(conn, claim_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM claim WHERE id = ?", (claim_id,)).fetchone()
    if not row:
        return None
    project = _project_of_run(conn, row["run_id"])
    claim = claim_view(row, repo=_repo_for_coordinates(conn, project, row["assertion_commit"],
                                                       row["assertion_path"]))
    return _with_snippets(conn, claim)


def _with_snippets(conn, claim: dict) -> dict:
    """The one place evidence, sources and snippets are assembled, so no screen can omit them."""
    claim = _attach_sources(conn, _attach_pass(conn, _attach_evidence(conn, claim)))
    return _attach_snippets(conn, claim)


# What each interaction asks of the run, in the words a reader needs when one verification pass
# shows more than one label. The label answers "what settles it"; where two labels appear in one
# scenario, the difference is what the assertions *ask*, and the page has to say so or the pass
# reads as two runs disagreeing (TESTOPS-12, AC1).
_ASKS = {
    "I1": "one is about a guarantee on the data as stored",
    "I2": "one is about the response itself",
    "KP": "one is about the page the response carries",
    "I3": "one is about what a person sees while acting",
    "I4": "one is about what only a browser works out",
    "U": "one names nothing that could settle it",
}


def pass_note_from_rows(rows: list[tuple[str | None, str | None]]) -> str | None:
    """Why one scenario carries more than one label, or ``None`` when it carries one.

    Produced from the stored rows, so the page can explain the corpus it is reading rather than a
    live source. Two labels are honest - a pass can hold a claim nothing settles beside a claim a
    browser settles - but a reader who sees two answers and no reason can only conclude the run was
    two runs. The note names the labels and says what each assertion asks.

    The unit is the scenario, not the Gherkin ``Then``..``And`` pass: a claim row records its line
    but not the keyword, so the store cannot tell where one pass ends and the next begins. Saying
    "this scenario" is a fact the rows hold; saying "this pass" would be a guess about rows that
    were never kept.
    """
    counts: dict[str, int] = {}
    codes: dict[str, str] = {}
    for label, code in rows:
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
        codes.setdefault(label, code or "")
    if len(counts) < 2:
        return None
    parts = [f'"{label}" for {_assertions(n)}' for label, n in counts.items()]
    asks = _asks(counts, codes)
    sentence = (f"This scenario carries {len(counts)} answers to one run: "
                + _listed(parts) + ".")
    # A label is a phrase for what settles a claim, not a subject a sentence can be built around:
    # "one is about settled by the response the server sends" is a placeholder wearing the label's
    # clothes (TESTOPS-18, AC1). The code says what the assertion asks; a row that has a label and
    # no code cannot be explained from the label, so the note says only what it can stand behind.
    if asks:
        return (f"{sentence} The run is one: {asks}, so the answers differ in what the assertions "
                f"ask, not in which instrument read them.")
    return (f"{sentence} The run is one: the answers differ in what the assertions ask, not in "
            f"which instrument read them.")


def _asks(counts: dict[str, int], codes: dict[str, str]) -> str | None:
    """What each label's assertions ask, or ``None`` when the rows cannot say.

    Every clause is read from ``_ASKS`` by interaction code. The label is never interpolated: it
    answers "what settles it", and a label beginning "settled by ..." dropped after "one is about"
    produces a clause no reader would write. When any label has no code, the whole list is withheld
    rather than half-guessed - the sentence still explains why one run carries two answers.
    """
    asks = [_ASKS.get(codes.get(label) or "") for label in counts]
    if any(ask is None for ask in asks):
        return None
    return _listed(asks)


def _listed(items: list[str]) -> str:
    """Two things are joined by ``and``; three or more get the commas a reader expects."""
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _assertions(n: int) -> str:
    return f"{n} assertion" if n == 1 else f"{n} assertions"


def _attach_pass(conn, claim: dict) -> dict:
    """Attach the explanation for a pass whose claims do not share one label.

    Read from the claim's own run and scenario: another run's claims say nothing about this pass,
    and a live re-analysis at read time is exactly what the store exists to make unnecessary.
    """
    rows = conn.execute(
        "SELECT interaction_label, interaction_code FROM claim"
        " WHERE run_id = ? AND subject_ref = ? ORDER BY assertion_line, id",
        (claim["run_id"], claim["subject"])).fetchall()
    claim["pass_note"] = pass_note_from_rows(
        [(row["interaction_label"], row["interaction_code"]) for row in rows])
    # The same rows, as counts by label, so a page can say what the scenario needs in its own words
    # rather than serving the analyser's sentence (TESTOPS-23). One label is silence: a scenario
    # whose assertions all need the same thing has nothing to explain.
    counts: dict[str, int] = {}
    for label, _code in rows:
        if label:
            counts[label] = counts.get(label, 0) + 1
    claim["pass_labels"] = counts if len(counts) > 1 else None
    return claim


def _attach_evidence(conn, claim: dict) -> dict:
    """Attach the evidence for a claim and the count it must be read against, together.

    The two are one read: ``[]`` evidence on a run that recorded nothing means "nobody was looking",
    and on a run that recorded plenty it means "we looked, none of it was here". A read model that
    carried only the list would let a page collapse those two into one sentence again.

    ``artefacts_recorded`` travels with them because it is the one thing the store knows beyond the
    count: whether anything was collected at all. It is reported as a count, never as a reason -
    a zero observation count cannot prove *why* no observation exists (TESTOPS-12, AC-b).
    """
    claim["evidence"] = evidence_for_claim(conn, claim)
    claim["observations_recorded"] = observations_in_snapshot(conn, claim)
    claim["artefacts_recorded"] = artefacts_in_snapshot(conn, claim)
    return claim


def artefacts_in_snapshot(conn, claim: dict) -> int | None:
    """How many artefact rows the claim's own snapshot holds, or ``None`` with no snapshot to count.

    Two runs can both hold no observations and mean different things: one collected nothing, the
    other collected files and extracted nothing from them. The count is the difference the store can
    actually show.
    """
    run = conn.execute("SELECT snapshot_id FROM run WHERE id = ?", (claim["run_id"],)).fetchone()
    if run is None:
        return None
    total = conn.execute("SELECT COUNT(*) FROM artefact WHERE snapshot_id = ?",
                         (run["snapshot_id"],)).fetchone()[0]
    return int(total)


def observations_in_snapshot(conn, claim: dict) -> int | None:
    """How many observation rows the claim's own snapshot holds.

    Counted over the claim's run's snapshot, not over the whole store: a claim is about one run,
    and another run's observations say nothing about whether this one looked. Returns ``None``
    when the claim's run has no snapshot row to count - "cannot say", never a zero.
    """
    run = conn.execute("SELECT snapshot_id FROM run WHERE id = ?", (claim["run_id"],)).fetchone()
    if run is None:
        return None
    total = conn.execute(
        """SELECT COUNT(*) FROM observation o JOIN artefact a ON a.id = o.artefact_id
            WHERE a.snapshot_id = ?""", (run["snapshot_id"],)).fetchone()[0]
    return int(total)


# The two questions a run page must keep apart (TESTOPS-72, AC6): claims the product's own routes
# show are repeats of work already done, and claims that needed the product and could not be judged
# against it. Folding the second into the first would report a blind spot as a finding.
PRODUCT_NOT_CONSULTED = "not_assessable"
PRODUCT_FOUND = "found"


def product_evidence(conn, run_id: str) -> dict:
    """What the product said about one run's claims, counted from the run's own rows.

    ``recorded`` is whether any claim carries a product record at all - a run from before TESTOPS-72
    recorded none, and a page must say that rather than print two zeroes nobody produced. ``repeats``
    counts claims whose verdict says the product already publishes them; ``unconsulted`` counts
    claims that needed the product and whose record says it could not be consulted. The two sets do
    not overlap: a claim nobody could judge is never counted as a repeat, and a repeat is never
    counted as unconsulted.

    ``near_miss`` counts claims the rule looked at and declined (TESTOPS-78, AC3): a noun shared with
    a product route that was not counted as a repeat, split by why - ``near_miss_verb_differs`` (the
    route's method settles a different act), ``near_miss_no_intent`` (the assertion names no act
    the intent table knows) and ``near_miss_display_copy`` (the shared word occurs only in text the
    assertion reproduces, so it is not the subject of the check - TESTOPS-79). They are counted
    here, never folded into ``repeats`` or ``unconsulted``.
    """
    rows = conn.execute(
        """SELECT c.id, c.verdict, c.interaction_code,
                  (SELECT i.output FROM inference i WHERE i.claim_id = c.id
                    ORDER BY i.id DESC LIMIT 1) AS output
             FROM claim c WHERE c.run_id = ? ORDER BY c.id""", (run_id,)).fetchall()
    recorded = repeats = unconsulted = examined = 0
    near_miss = near_miss_verb_differs = near_miss_no_intent = near_miss_display_copy = 0
    near_miss_ambiguous_quotes = 0
    for row in rows:
        detail = _json(row["output"]) if row["output"] else {}
        product = detail.get("product") if isinstance(detail, dict) else None
        if not isinstance(product, dict):
            continue
        recorded += 1
        if row["verdict"] == "repeats_product":
            repeats += 1
        elif product.get("state") == PRODUCT_NOT_CONSULTED:
            unconsulted += 1
        elif product.get("near_miss"):
            near_miss += 1
            if product.get("near_miss_kind") in ("display_copy", "quoted_copy"):
                near_miss_display_copy += 1
            elif product.get("near_miss_kind") == "ambiguous_quotes":
                # The record named two quoted runs and refused to choose between them
                # (TESTOPS-82 amendment): a refusal of its own kind, not a verb disagreement.
                near_miss_ambiguous_quotes += 1
            elif (product.get("near_miss_kind") == "no_intent"
                  or not product.get("assertion_verb")):
                near_miss_no_intent += 1
            else:
                near_miss_verb_differs += 1
        elif product.get("state") == PRODUCT_FOUND:
            examined += 1
    return {"recorded": recorded, "claims": len(rows), "repeats": repeats,
            "unconsulted": unconsulted, "matched": examined,
            "near_miss": near_miss, "near_miss_verb_differs": near_miss_verb_differs,
            "near_miss_no_intent": near_miss_no_intent,
            "near_miss_display_copy": near_miss_display_copy,
            "near_miss_ambiguous_quotes": near_miss_ambiguous_quotes}


def near_miss_claims(conn, run_id: str, scenarios: set[str] | None = None) -> list[dict]:
    """The claims this run's product rule looked at and declined, as records a page can render.

    A near-miss claim is ``distinct``, so it raises no finding and gets no case page of its own. That
    made its refusal invisible in the build before TESTOPS-78: recorded on the claim, rendered
    nowhere. This read model is what the run page lists and what a case page uses to show the near
    misses belonging to its own scenario.

    ``scenarios`` restricts the answer to those ``subject_ref`` values - the case page passes the
    scenarios its findings belong to. Each entry carries the claim's identity, its own words, and the
    product record (route, shared word, kind of refusal, reason). Order is deterministic.
    """
    rows = conn.execute(
        """SELECT c.id, c.subject_ref, c.assertion_text, c.verdict, c.assertion_line,
                  (SELECT i.output FROM inference i WHERE i.claim_id = c.id
                    ORDER BY i.id DESC LIMIT 1) AS output
             FROM claim c WHERE c.run_id = ? ORDER BY c.subject_ref, c.assertion_line, c.id""",
        (run_id,)).fetchall()
    out: list[dict] = []
    for row in rows:
        if scenarios is not None and row["subject_ref"] not in scenarios:
            continue
        detail = _json(row["output"]) if row["output"] else {}
        product = detail.get("product") if isinstance(detail, dict) else None
        if not isinstance(product, dict) or not product.get("near_miss"):
            continue
        _, _, scenario = row["subject_ref"].partition("#")
        out.append({"id": row["id"], "subject_ref": row["subject_ref"], "scenario": scenario,
                    "assertion_text": row["assertion_text"] or "", "verdict": row["verdict"],
                    "product": product})
    return out


def case_for_scenario(conn, run_id: str) -> dict[str, str]:
    """``subject_ref -> case id`` for the cases this run raised, first case wins.

    A near-miss claim has no case of its own, so the run page can only point a reader at the case
    page of the scenario it belongs to - when that scenario raised a finding. Read from the
    findings' own claim ids, so the link is a fact about stored rows rather than a guess from titles.
    """
    links: dict[str, str] = {}
    claim_scenario: dict[int, str] = {}
    for finding in conn.execute(
            """SELECT f.case_id, f.claim_ids FROM finding f
                 JOIN case_ c ON c.id = f.case_id WHERE c.run_id = ?""", (run_id,)):
        for claim_id in _json(finding["claim_ids"], []):
            if claim_id not in claim_scenario:
                row = conn.execute("SELECT subject_ref FROM claim WHERE id = ?",
                                   (claim_id,)).fetchone()
                if row is None:
                    continue
                claim_scenario[claim_id] = row["subject_ref"]
            links.setdefault(claim_scenario[claim_id], finding["case_id"])
    return links


def _attach_sources(conn, claim: dict) -> dict:
    """Attach what the run recorded about its sources, and the assessment they support.

    Three keys, all read from the claim's own snapshot:

    - ``sources``: the registry record, or ``None`` when the snapshot predates the registry. It is
      the record itself, not a re-probe: a reader sees what the run could see, not what today's
      configuration would see.
    - ``assessment``: the registry's verdict for the capabilities this analyser needed, with the
      sentence derived at read time. ``None`` means not recorded, which is not ``not_assessable``.
    - ``source_notes``: for each name in ``sources_missing``, the reason the run recorded, so the
      page can name the reason rather than only the source. A name the record does not explain is
      marked ``recorded: False``; the page says so instead of borrowing a reason.
    """
    meta = _snapshot_meta(conn, claim["run_id"])
    record = meta.get("sources") if isinstance(meta, dict) else None
    claim["sources"] = record if isinstance(record, dict) else None
    assessment = sources.assessment_for(meta, claim.get("analyser") or "")
    if assessment is None:
        claim["assessment"] = None
    else:
        view = assessment.record()
        view["sentence"] = assessment.sentence()
        claim["assessment"] = view
    notes = sources.notes(record, claim.get("sources_missing") or [])
    # What the run needed, and what it only consulted, are different questions. A needed capability
    # with no declared source has a blind spot but no source id, so it cannot appear in
    # ``sources_missing``; the same is true of a consulted capability. Both belong in section 5:
    # otherwise the page could say "every source was available" beside a "cannot assess" headline,
    # or stay silent about requirements the run never looked at.
    named = {(note["source"], note["title"]) for note in notes}
    for found in (assessment, sources.consulted_for(meta, claim.get("analyser") or "")):
        if found is None:
            continue
        for spot in found.blind_spots:
            key = (spot.source, spot.title)
            if key not in named:
                named.add(key)
                notes.append({"source": spot.source, "title": spot.title, "state": spot.state,
                              "reason": spot.reason, "blocked_by": spot.blocked_by,
                              "recorded": True})
    claim["source_notes"] = notes
    # TESTOPS-38 AC4: what each service said about itself when this run resolved the project. A
    # snapshot written before the model has no such record and the page is unchanged.
    service_states = meta.get("service_states") if isinstance(meta, dict) else None
    claim["service_states"] = service_states if isinstance(service_states, list) else None
    return claim


def _snapshot_meta(conn, run_id: str) -> dict | None:
    """The snapshot meta for a claim's run, or ``None`` when there is no snapshot to read.

    Unparseable JSON raises: a corrupt record of what a run could see must not read back as "nothing
    was recorded", which is a truthful answer to a different question.
    """
    row = conn.execute(
        "SELECT s.meta FROM run r JOIN snapshot s ON s.id = r.snapshot_id WHERE r.id = ?",
        (run_id,)).fetchone()
    if row is None or not row["meta"]:
        return None
    try:
        value = json.loads(row["meta"])
    except json.JSONDecodeError as exc:
        raise ValueError(f"snapshot.meta holds unparseable JSON: {row['meta']!r}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"snapshot.meta should hold a JSON object, found {value!r}")
    return value


def _project_of_run(conn, run_id: str) -> str | None:
    row = conn.execute("SELECT project FROM run WHERE id = ?", (run_id,)).fetchone()
    return row["project"] if row else None


def _repo_for_coordinates(conn, project: str | None, commit: str | None,
                          path: str | None) -> str | None:
    """Which repository a claim's assertion path lives in, found by exact coordinates.

    The claim stores a path and a commit, not an owner/name, and a GitHub URL needs the name. The
    lookup is an identity question, not an evidence one: it is answered by an artefact row whose
    commit and path are *equal* to the claim's (the ``LIKE`` only pre-filters the suffix; the match
    is completed in Python), so a file at a different commit cannot name the repository. Evidence
    itself is never taken from here - see :func:`evidence_for_claim`.
    """
    if not (project and commit and path):
        return None
    rows = conn.execute(
        """SELECT a.uri FROM artefact a JOIN snapshot s ON s.id = a.snapshot_id
           WHERE s.project = ? AND a.uri LIKE ?""",
        (project, f"%@{commit}:{path}")).fetchall()
    for row in rows:
        m = GITHUB.match(row["uri"])
        if m and m["sha"] == commit and m["path"] == path:
            return f"{m['owner']}/{m['repo']}"
    return None


def case_row(conn, case_id: str) -> dict | None:
    r = conn.execute("""SELECT c.*, r.status AS run_status, r.finished_at, s.artefact_versions
                        FROM case_ c LEFT JOIN run r ON r.id = c.run_id
                        LEFT JOIN snapshot s ON s.id = c.snapshot_id
                        WHERE c.id = ?""", (case_id,)).fetchone()
    if not r:
        return None
    return {"id": r["id"], "run_id": r["run_id"], "project": r["project"],
            "analyser": r["analyser"], "created_at": r["created_at"],
            "snapshot": r["snapshot_id"], "summary": _json(r["summary"]),
            "state": cases.state_of(conn, case_id), "versions": _json(r["artefact_versions"])}


def finding_rows(conn, case_id: str) -> list[dict]:
    ctx = conn.execute("SELECT project FROM case_ WHERE id = ?", (case_id,)).fetchone()
    project = ctx["project"] if ctx else None
    out = []
    for f in conn.execute("SELECT * FROM finding WHERE case_id = ? ORDER BY id", (case_id,)):
        claim_ids = _json(f["claim_ids"], [])
        claims = []
        for cid in claim_ids:
            c = conn.execute("SELECT * FROM claim WHERE id = ?", (cid,)).fetchone()
            if not c:
                continue
            inf = conn.execute("SELECT * FROM inference WHERE claim_id = ? ORDER BY id DESC LIMIT 1",
                               (cid,)).fetchone()
            detail = _json(inf["output"]) if inf else {}
            claim = claim_view(c, repo=_repo_for_coordinates(conn, project, c["assertion_commit"],
                                                             c["assertion_path"]))
            # The analyser's products record is what the product snippet is resolved from, so it is
            # on the claim before the read model attaches the snippet (TESTOPS-83).
            claim["detail"] = detail
            claim = _with_snippets(conn, claim)
            claim.update({"used_model": bool(detail.get("model") and detail.get("model") != "none")})
            claims.append(claim)
        out.append({"id": f["id"], "title": f["title"], "severity": f["severity"],
                    "fingerprint": f["fingerprint"], "claims": claims,
                    "suppressed": cases.suppressed(conn, f["fingerprint"]) is not None})
    return out


# ---------------------------------------------------------------- the source band
#
# TESTOPS-73. The top of a case page names what the case examined, before the statement, so a
# reader can see at a glance whether the finding rests on test code, the product, a tracker item,
# a pipeline run or a requirements document - and which of those was wanted and could not be
# consulted. Everything here is read from the case's own snapshot: today's configuration says
# nothing about what that run could see.

CONSULTED = "consulted"
NOT_CONSULTED = "not_consulted"

# A kind that is not linked is not a tag (AC2). These are the kinds an analyser may record as
# linked to a claim, in ``detail["links"]``: a list of ``{"kind", "name", "url"}``. Nothing in this
# build emits them yet; the seam exists so that a future collector links an issue or a run exactly
# as a repository is linked, instead of inventing a second way to say "this item was examined".
LINKED_KIND_TITLE = {
    "jira_issue": "Jira issue",
    "ado_work_item": "Azure DevOps work item",
    "pipeline_run": "Pipeline run",
    "requirements_document": "Requirements document",
}


def _analyser_needs(meta: dict, analyser: str | None) -> set[str]:
    """The capabilities this case's analysis needed, from the snapshot, then this build.

    The snapshot is the record of what that run needed; the analyser's declaration is only a
    fallback for a snapshot written before the list was recorded. Neither is today's registry.
    """
    spec = (meta.get("analysers") or {}).get(analyser or "") if isinstance(
        meta.get("analysers"), dict) else None
    needs = set(spec.get("needs") or ()) if isinstance(spec, dict) else set()
    if needs:
        return needs
    from .analysers import REGISTERED        # local: the analysers import this-vicinity modules

    module = REGISTERED.get(analyser or "")
    return set(getattr(module, "NEEDS", ()) or ())


def _service_state(meta: dict, *, kind: str, role: str) -> dict | None:
    """One recorded service state from the snapshot, or ``None`` when none was recorded."""
    states = meta.get("service_states")
    if not isinstance(states, list):
        return None
    for state in states:
        if isinstance(state, dict) and state.get("type") == kind and state.get("role") == role:
            return state
    return None


def _repo_from_service(meta: dict, role: str) -> str:
    """The repository a git-repo service names, from the recorded state's display name."""
    state = _service_state(meta, kind="git_repo", role=role)
    name = (state or {}).get("name") or ""
    suffix = f" ({role})"
    return name[:-len(suffix)] if name.endswith(suffix) else name


def _parsed_languages(record: dict) -> str:
    """The files the surface reader parsed, said as ``142 .java`` (TESTOPS-80 AC3).

    ``parsed`` is the count this reader read, so it cannot become the snapshot's total artefact
    count; the suffixes are narrowed to the languages the reader parses, so a repository's
    TypeScript files cannot be counted as routes read.
    """
    parsed = record.get("parsed")
    entries = [entry for entry in (record.get("languages") or ())
               if isinstance(entry, dict)
               and entry.get("suffix") in surface_discovery.LANGUAGES
               and isinstance(entry.get("count"), int)]
    if not entries:
        return f"{parsed} files" if isinstance(parsed, int) else "the product's files"
    if len(entries) == 1:
        count = parsed if isinstance(parsed, int) else entries[0]["count"]
        return f"{count} {entries[0]['suffix']}"
    held = ", ".join(f"{entry['count']} {entry['suffix']}" for entry in entries)
    return f"{parsed} files ({held})" if isinstance(parsed, int) else f"files ({held})"


def product_routes_tag(meta: dict, product_repo: str) -> dict | None:
    """Whether the product's routes were read, answered by the snapshot's surface state (AC1).

    One place computes this, from the record the surface reader wrote, so the band cannot say
    "not consulted" about routes the verdict is quoting. The test-ecosystem detector answers a
    different question - whether a test suite's steps could be parsed - and is not consulted here
    (AC4). ``None`` means this snapshot predates the record: no tag, because "not recorded" is not
    "not consulted".
    """
    record = meta.get("surfaces")
    if not isinstance(record, dict):
        return None
    tag = {"kind": "Product routes", "name": product_repo or "the product's routes", "href": ""}
    state = record.get("state")
    if state == surface_discovery.FOUND:
        count = record.get("surfaces")
        # The record's ``surfaces`` is the routes the reader resolved *plus* the engine modules
        # it found (discover.py:301), so a count of them is not a count of routes: say what the
        # number counts (TESTOPS-80 review, concern 2).
        found = ("1 surface" if count == 1 else f"{count} surfaces"
                 if isinstance(count, int) else "surfaces")
        return {**tag, "state": CONSULTED, "reason": "",
                "detail": (f"{_parsed_languages(record)} parsed, {found} "
                           f"(routes and engine modules)")}
    if state == surface_discovery.ZERO:
        return {**tag, "state": CONSULTED, "reason": "",
                "detail": f"{_parsed_languages(record)} parsed, no routes found"}
    if state == surface_discovery.NOT_ASSESSABLE:
        reason = (record.get("reason") or "").strip().rstrip(".")
        return {**tag, "state": NOT_CONSULTED, "detail": "", "reason": reason
                or "the surface reader could not look at this product"}
    return None


def source_band(conn, row: dict, claims: list[dict]) -> dict:
    """What the case examined, and what it needed and could not consult (TESTOPS-73).

    Returns ``tags`` - consulted first, in a stable order - plus the two sentences a reader needs:
    ``absent_note`` (what an absent tag means) and ``sentence`` (the case that rests on test code
    alone). A tag is ``{"kind", "name", "href", "state", "detail", "reason"}``; ``href`` is empty
    when the store cannot build the link AC2 asks for, and the tag says so rather than hiding the
    source. No tag is invented for a kind that is not linked: an unconsulted tag appears only for a
    source the analysis needed (AC3).
    """
    snapshot = row.get("snapshot")
    stored = conn.execute("SELECT meta, artefact_versions FROM snapshot WHERE id = ?",
                          (snapshot,)).fetchone() if snapshot else None
    meta = _json(stored["meta"]) if stored and stored["meta"] else {}
    versions = _json(stored["artefact_versions"], {}) if stored else {}
    if not isinstance(meta, dict):
        meta = {}
    arms_value = meta.get("arms")
    arms = arms_value if isinstance(arms_value, dict) else {}
    reads_value = meta.get("reads")
    reads = reads_value if isinstance(reads_value, dict) else {}
    needs = _analyser_needs(meta, row.get("analyser"))
    recorded = bool(meta) or bool(versions)

    tags: list[dict] = []

    # ---- the test repository: link to the file the assertion was read from, at its commit.
    first = next((claim for claim in claims
                  if (claim.get("provenance") or {}).get("assertion_path")), None)
    prov = (first or {}).get("provenance") or {}
    test_repo = (first.get("repo") if first is not None else "") or arms.get("test") or ""
    if not test_repo and len(versions) == 1:
        test_repo = next(iter(versions))
    commit = prov.get("assertion_commit") or (versions.get(test_repo) if test_repo else None)
    path = prov.get("assertion_path")
    line = prov.get("assertion_line")
    href = blob_permalink(test_repo, commit, path, line) if (test_repo and path) else None
    if test_repo or path:
        detail = f"{path}:{line}" if path else ""
        if not href:
            note = ("this run recorded no link to the file" if path
                    else "this run recorded no assertion to open")
            detail = f"{detail}; {note}" if detail else note
        tags.append({"kind": "Test repository", "name": test_repo or "the test repository",
                     "href": href, "state": CONSULTED, "detail": detail, "reason": ""})

    # ---- the product repository: read by the run, or wanted and not consultable.
    product_repo = arms.get("product") or _repo_from_service(meta, "product")
    if not product_repo:
        ecosystems = meta.get("ecosystems")
        product_eco = (ecosystems or {}).get("product") if isinstance(ecosystems, dict) else None
        product_repo = (product_eco or {}).get("repository") or ""
    product_read = reads.get("product") if isinstance(reads.get("product"), dict) else None
    examined = "product" in arms or product_read is not None
    product_commit = (product_read or {}).get("commit") or (versions.get(product_repo)
                                                            if product_repo else None)
    if examined:
        href = (f"https://github.com/{product_repo}/tree/{product_commit}"
                if product_repo and product_commit
                else f"https://github.com/{product_repo}" if product_repo else "")
        detail = (f"at commit {product_commit[:8]}" if product_commit
                  else "the run did not record its commit")
        tags.append({"kind": "Product repository",
                     "name": product_repo or "the product repository", "href": href,
                     "state": CONSULTED, "detail": detail, "reason": ""})
    else:
        reason = _product_absent_reason(meta)
        if "code" in needs:
            tags.append({"kind": "Product repository", "name": product_repo
                         or "the product repository", "href": "", "state": NOT_CONSULTED,
                         "detail": "", "reason": reason})

    # ---- the product's routes: answered by the surface discovery state this snapshot recorded,
    # never by the test-ecosystem detector. The detector asks whether a *test* suite could be
    # parsed; the surface reader asks what the product exposes, and only its answer can say
    # whether the routes the verdict rests on were read (TESTOPS-80 AC1). A snapshot written
    # before the record existed renders no routes tag - "not recorded" is not "not consulted".
    # One tag per case, not per claim: this reads only the snapshot's record and the analyser's
    # needs, so appending it inside the claim loop below rendered it twice for a case with two
    # claims and never for a case with none (TESTOPS-80 review, concern 1).
    if examined and "code" in needs:
        routes_tag = product_routes_tag(meta, product_repo)
        if routes_tag is not None:
            tags.append(routes_tag)

    # ---- kinds a claim links explicitly: an issue, a work item, a pipeline run, a document.
    for claim in claims:
        detail = claim.get("detail") or {}
        for entry in (detail.get("links") or ()):
            if not isinstance(entry, dict):
                continue
            title = LINKED_KIND_TITLE.get(entry.get("kind") or "")
            url = entry.get("url") or ""
            if not title or not url:
                continue                            # not linked is not a tag (AC2)
            if any(tag["kind"] == title and tag["href"] == url for tag in tags):
                continue
            tags.append({"kind": title, "name": entry.get("name") or url, "href": url,
                         "state": CONSULTED, "detail": "", "reason": ""})

    sentence = None
    if not examined:
        reason = _product_absent_reason(meta)
        sentence = ("Assessed against test code only: the product\u2019s routes could not be "
                    "consulted")
        if reason:
            sentence += f", because {reason}"
        sentence += "."

    return {"tags": tags, "recorded": recorded, "sentence": sentence,
            "absent_note": ("A kind that is not tagged here was not linked to this case, so an "
                            "absent tag means it was not part of the evidence.")}


def _product_absent_reason(meta: dict) -> str:
    """Why the product could not be consulted, from the snapshot's own record."""
    state = _service_state(meta, kind="git_repo", role="product")
    if state:
        reason = (state.get("reason") or "").strip().rstrip(".")
        if reason:
            return reason
        if state.get("state"):
            return f"the product repository is {state['state']}"
    assessment = meta.get("project_assessment")
    if isinstance(assessment, dict) and (assessment.get("reason") or "").strip():
        return assessment["reason"].strip().rstrip(".")
    return "the run recorded no product repository"


# ---------------------------------------------------------------- what happened in this run
#
# TESTOPS-22. A run that raised nothing and a case a person resolved are two different facts, and
# the page used one word - "Resolved" - for both. These read models supply the facts each page
# needs, and only facts the store can prove: every count is a COUNT over rows this case's own
# snapshot holds. A count the store cannot support is None, which a page renders as "cannot say" -
# never as zero, and never re-derived from today's configuration at render time.

def latest_decision(conn, case_id: str) -> dict | None:
    """The last decision a person recorded for this case, or ``None`` when nobody decided.

    ``None`` is the fact that matters: a run that raised nothing has had no decision taken, and a
    page that rendered "Resolved" for it was inventing a person's act.
    """
    row = conn.execute(
        "SELECT state, actor, at, note FROM case_state WHERE case_id = ? ORDER BY id DESC LIMIT 1",
        (case_id,)).fetchone()
    return dict(row) if row else None


def run_analysis(conn, case_id: str) -> dict | None:
    """What the run behind this case examined, counted from stored rows only.

    ``features`` counts the feature-file artefacts the build keeps - the same test the analyser
    applies, :func:`csproj.is_active` over :func:`csproj.excluded_patterns` read from the *stored*
    project file. ``scenarios`` counts the scenario observations recorded against those files, so a
    dormant file's scenarios cannot inflate it. ``claims`` counts the claim rows this run wrote.

    ``patterns`` is the exclusion list the analyser would have used, or ``None`` when the project
    file is recorded but its content is not in this store - in which case the feature and scenario
    counts are ``None`` too, because which files the build keeps is exactly what cannot be known.

    The source facts come from the snapshot's recorded registry, never from
    :func:`sources.registry`: what today's deployment declares says nothing about what this run
    could see.
    """
    ctx = conn.execute(
        "SELECT c.run_id, c.analyser, r.snapshot_id, r.finished_at, r.status"
        " FROM case_ c LEFT JOIN run r ON r.id = c.run_id WHERE c.id = ?", (case_id,)).fetchone()
    if ctx is None:
        return None
    findings = conn.execute("SELECT COUNT(*) FROM finding WHERE case_id = ?",
                            (case_id,)).fetchone()[0]
    return _run_analysis(conn, ctx["run_id"], ctx["analyser"], ctx["snapshot_id"],
                         ctx["finished_at"], ctx["status"], int(findings))


def run_analysis_by_id(conn, run_id: str) -> dict | None:
    """The same record as :func:`run_analysis`, for a run rather than one of its cases.

    ``findings`` counts every finding the run raised - over all of its cases, not one - because a
    run is the unit here. A run that raised nothing and a run whose findings were all closed by
    decisions both reach this function; the counts and :func:`cases.list_cases` say which is which.
    """
    ctx = conn.execute(
        "SELECT id, analyser, snapshot_id, finished_at, status FROM run WHERE id = ?",
        (run_id,)).fetchone()
    if ctx is None:
        return None
    findings = conn.execute(
        "SELECT COUNT(*) FROM finding f JOIN case_ c ON c.id = f.case_id WHERE c.run_id = ?",
        (run_id,)).fetchone()[0]
    return _run_analysis(conn, ctx["id"], ctx["analyser"], ctx["snapshot_id"],
                         ctx["finished_at"], ctx["status"], int(findings))


def _run_analysis(conn, run_id: str, analyser: str | None, snapshot: str | None,
                  finished_at: str | None, status: str | None, findings: int) -> dict:
    record = {"run_id": run_id, "analyser": analyser, "snapshot": snapshot,
              "finished_at": finished_at, "status": status, "findings": findings,
              # None = this store cannot support a count, which is not a count of zero.
              "claims": None, "features": None, "scenarios": None, "dormant": None,
              "feature_files": None, "patterns": None, "project_files": [],
              "registry_recorded": False, "assessment_recorded": False,
              "blind_spots": [], "assessment": None}
    if not snapshot:
        return record

    record["claims"] = int(conn.execute("SELECT COUNT(*) FROM claim WHERE run_id = ?",
                                        (run_id,)).fetchone()[0])

    features: list[tuple[int, str]] = []
    projects: list[tuple[str, str | None]] = []
    for art in conn.execute(
            "SELECT id, uri, kind, blob_sha FROM artefact WHERE snapshot_id = ? ORDER BY id",
            (snapshot,)):
        m = GITHUB.match(art["uri"] or "")
        if m is None:
            continue                             # jira:/ado: rows carry no file path
        if art["kind"] == "feature":
            features.append((art["id"], m["path"]))
        elif art["kind"] == "build":
            projects.append((m["path"], art["blob_sha"]))
    record["project_files"] = [path for path, _sha in projects]

    patterns: list[str] | None = []
    unreadable = False
    for _path, sha in projects:
        try:
            text = blobs.text(sha) if sha else None
        except FileNotFoundError:
            text = None
        if text is None:
            unreadable = True
            break
        patterns.extend(csproj.excluded_patterns(text))
    if unreadable:
        patterns = None
    record["patterns"] = patterns

    if patterns is not None:
        active = [artefact_id for artefact_id, path in features
                  if csproj.is_active(path, patterns)]
        record["feature_files"] = len(features)
        record["features"] = len(active)
        record["dormant"] = len(features) - len(active)
        record["scenarios"] = int(sum(
            conn.execute("SELECT COUNT(*) FROM observation"
                         " WHERE artefact_id = ? AND key LIKE 'scenario:%'",
                         (artefact_id,)).fetchone()[0] for artefact_id in active))

    record.update(_source_facts(conn, run_id, analyser))
    record["read_counts"] = read_counts(conn, snapshot, record.get("reads"))
    return record


def known_file_kinds() -> tuple[str, ...]:
    """Every kind of file this build's collector reads, in the order it declares them.

    A run page lists all of them for every repository, so a kind the repository holds none of is
    a stated zero rather than a silence (TESTOPS-55).
    """
    return tuple(rule.suffix for rule in config.FILE_KINDS)


def _file_suffix(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    return "." + name.rsplit(".", 1)[1] if "." in name.lstrip(".") else "(no suffix)"


def read_counts(conn, snapshot: str | None, reads) -> list[dict] | None:
    """Per repository, how many files of each kind this run read - zeroes included.

    TESTOPS-55. The counts are derived from the store, never hardcoded and never stored twice:
    every file a run fetched is an artefact of its snapshot, and the snapshot's ``reads`` record
    says which commit belongs to which repository. A kind the collector reads that a repository
    holds none of is reported as 0, because "0 .js files" and "the page never said" are different
    facts. ``None`` when the snapshot cannot support the count at all - a run that recorded no
    reads says nothing, rather than claiming zeroes it never counted.
    """
    if not snapshot or not isinstance(reads, dict) or not reads:
        return None
    owner: dict[str, str] = {}
    for role, entry in reads.items():
        commit = (entry or {}).get("commit") if isinstance(entry, dict) else None
        if commit:
            owner[str(commit)] = role
    if not owner:
        return None
    counts: dict[str, dict[str, int]] = {role: {} for role in reads}
    names: dict[str, str] = {}
    for row in conn.execute("SELECT uri FROM artefact WHERE snapshot_id = ? ORDER BY id",
                            (snapshot,)):
        match = GITHUB.match(row["uri"] or "")
        if match is None:
            continue                        # jira:/ado: rows are not files read from a repository
        role = owner.get(match["sha"])
        if role is None:
            continue                        # a commit this run did not record reading
        suffix = _file_suffix(match["path"])
        counts[role][suffix] = counts[role].get(suffix, 0) + 1
        names.setdefault(role, f"{match['owner']}/{match['repo']}")
    out: list[dict] = []
    known = known_file_kinds()
    for role in sorted(reads):
        counted = counts.get(role) or {}
        every_kind = list(known) + sorted(set(counted) - set(known))
        out.append({"role": role, "repository": names.get(role, ""),
                    "counts": {kind: int(counted.get(kind, 0)) for kind in every_kind}})
    return out


def store_totals(conn) -> dict[str, int]:
    """How many projects, runs and cases the store holds - the front page's totals (TESTOPS-55).

    A project is anything the store knows as one: a configured project, or a project a run names.
    Counting only configured rows would contradict a front page that is listing a project heading
    with no configuration row behind it.
    """
    return {
        "projects": int(conn.execute(
            "SELECT COUNT(*) FROM (SELECT slug FROM project UNION SELECT project FROM run)"
        ).fetchone()[0]),
        "runs": int(conn.execute("SELECT COUNT(*) FROM run").fetchone()[0]),
        "cases": int(conn.execute("SELECT COUNT(*) FROM case_").fetchone()[0]),
    }


def _source_facts(conn, run_id: str, analyser: str | None) -> dict:
    """What the run's snapshot recorded about its sources, and the assessment it supports.

    One reader for the run page, the runs list and the case page, so no screen can derive a
    different answer from the same recorded registry. ``registry_recorded`` is whether a registry
    was written at all; ``assessment_recorded`` is whether the record says what *this* analyser
    needed. They are separate because "no registry" and "a registry that does not mention this
    analysis" are different absences.
    """
    meta = _snapshot_meta(conn, run_id)
    stored = meta.get("sources") if isinstance(meta, dict) else None
    facts = {"registry_recorded": isinstance(stored, dict), "assessment_recorded": False,
             "blind_spots": [], "assessment": None,
             # TESTOPS-41: what the readers could not read, and what the surface reader made of the
             # product repository. ``None`` means the snapshot predates the record - not "nothing
             # was skipped", which is the same mistake in a different place.
             "reads": meta.get("reads") if isinstance(meta, dict) else None,
             "surfaces": meta.get("surfaces") if isinstance(meta, dict) else None,
             # TESTOPS-42A: which ecosystem each repository was read as. ``None`` means the
             # snapshot predates the record - not "no ecosystem was needed".
             "ecosystems": (meta.get("ecosystems")
                            if isinstance(meta, dict)
                            and isinstance(meta.get("ecosystems"), dict) else None),
             "service_states": (meta.get("service_states")
                                if isinstance(meta, dict)
                                and isinstance(meta.get("service_states"), list) else None),
             # TESTOPS-42C-3: what the run placed and what it could not read. ``None`` means the
             # snapshot was written before placement was recorded - not "everything was placed".
             "placement": (meta.get("placement")
                           if isinstance(meta, dict) and isinstance(meta.get("placement"), dict)
                           else None),
             "unreadable_declarations": (meta.get("unreadable_declarations")
                                         if isinstance(meta, dict)
                                         and isinstance(meta.get("unreadable_declarations"), list)
                                         else None)}
    if not facts["registry_recorded"]:
        return facts
    assessment = sources.assessment_for(meta, analyser or "")
    consulted = sources.consulted_for(meta, analyser or "")
    facts["assessment_recorded"] = assessment is not None or consulted is not None
    if assessment is not None:
        view = assessment.record()
        view["sentence"] = assessment.sentence()
        facts["assessment"] = view
    spots: list[dict] = []
    named: set[tuple[str, str]] = set()
    for found in (assessment, consulted):
        if found is None:
            continue
        for spot in found.blind_spots:
            key = (spot.source, spot.title)
            if key in named:
                continue
            named.add(key)
            spots.append({"source": spot.source, "title": spot.title, "state": spot.state,
                          "reason": spot.reason, "blocked_by": spot.blocked_by,
                          "recorded": True})
    facts["blind_spots"] = spots
    return facts


def cases_for_run(conn, run_id: str) -> list[dict]:
    """The cases a run raised, newest first. A run that raised nothing has none."""
    return cases.list_cases(conn, run_id=run_id, limit=200)


def run_read(conn, run_id: str) -> dict | None:
    """Everything the run's page needs, or ``None`` when the store holds no such run.

    ``versions`` is the commit record the snapshot stored - what the run looked at - and is never
    re-read from a live source. ``cases`` is the list query, so a run whose only ``case_`` row raised
    nothing reports no cases, which is the fact.
    """
    row = conn.execute(
        "SELECT r.id, r.project, r.analyser, r.status, r.started_at, r.finished_at, r.snapshot_id,"
        " s.artefact_versions FROM run r LEFT JOIN snapshot s ON s.id = r.snapshot_id"
        " WHERE r.id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    record = run_analysis_by_id(conn, run_id)
    if record is None:
        return None
    raised = cases_for_run(conn, run_id)
    record.update({"id": run_id, "project": row["project"], "started_at": row["started_at"],
                   "status": row["status"], "versions": _json(row["artefact_versions"]),
                   "cases": raised, "case_count": len(raised),
                   "decided_cases": sum(1 for case in raised
                                        if case["state"] in cases.TERMINAL)})
    return record


# The three shapes of "the tool could not tell" (TESTOPS-60, AC1). Every unplaced claim belongs
# to exactly one; the page uses the key to state the shared reason once instead of once per row.
GROUP_NO_BINDING = "no-binding-match"
GROUP_NO_PATTERNS = "no-patterns"
GROUP_OTHER = "other"
GROUP_ORDER = (GROUP_NO_BINDING, GROUP_NO_PATTERNS, GROUP_OTHER)

UNPLACED_NO_BINDING = "no binding matches these words"
UNPLACED_NO_PATTERNS = "this run declared no binding patterns"


def unplaced_claims(conn, run_id: str) -> list[dict]:
    """The claims a run could not place, each with the nearest patterns the suite declared.

    TESTOPS-57. ``unplaced`` is the one verdict whose point is "I could not tell", and it never
    becomes a case because only ``RAISES`` verdicts do. The run page therefore shows these claims
    as a section of their own, one entry per claim. The nearest patterns are computed from the
    run's own binding observations - the same comparison the ecosystem's ``explain_unmatched``
    makes - so a page opened months later still says what the suite came closest to matching.

    TESTOPS-60 adds ``group`` and ``reason``. The group says which of three shapes of failure the
    claim is, so the page can state the shared sentence once per group rather than repeating it on
    every row. A snapshot that declared no patterns at all is its own group: the nearest-pattern
    comparison could not run, and the page must not imply that it did.

    The order is the claim id, which is the order the run wrote them, and the id itself is the
    anchor (``#unplaced-claim-<id>``), so pruning an earlier claim cannot move a cited anchor.
    """
    row = conn.execute("SELECT snapshot_id FROM run WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        return []
    patterns = _declared_patterns(conn, row["snapshot_id"])
    out: list[dict] = []
    for claim in conn.execute(
            "SELECT * FROM claim WHERE run_id = ? AND verdict = 'unplaced' ORDER BY id",
            (run_id,)).fetchall():
        entry = dict(claim)
        text = entry.get("assertion_text") or entry.get("statement") or ""
        entry["nearly"] = _nearest_patterns(patterns, text, 2)
        entry["group"], entry["reason"] = _classify_unplaced(entry, patterns)
        out.append(entry)
    return out


def _classify_unplaced(entry: dict, patterns: list[str]) -> tuple[str, str]:
    """Which shape of "could not place" this claim is, and the reason clause for its group.

    With no declared patterns there was nothing to compare the words with, whatever an older
    claim recorded, so that state wins: the page must not claim nearest patterns it does not have.
    """
    recorded = " ".join(str(entry.get("established_by") or "").split()).rstrip(".")
    if not patterns:
        return GROUP_NO_PATTERNS, UNPLACED_NO_PATTERNS
    if recorded.lower().startswith(UNPLACED_NO_BINDING):
        return GROUP_NO_BINDING, UNPLACED_NO_BINDING
    return GROUP_OTHER, recorded or "no reason was recorded"


def unplaced_groups(entries: list[dict]) -> list[dict]:
    """The entries of one run grouped by shape of failure, in the fixed order of the three.

    An empty group is omitted rather than shown with a zero, so a reader never reads a heading
    that says "0 steps". The group's count is ``len`` of its own entries, so it cannot disagree
    with what is rendered under it.
    """
    buckets: dict[str, list[dict]] = {key: [] for key in GROUP_ORDER}
    for entry in entries:
        buckets.setdefault(entry.get("group") or GROUP_OTHER, []).append(entry)
    return [{"key": key, "entries": buckets[key]}
            for key in GROUP_ORDER if buckets.get(key)]


def _declared_patterns(conn, snapshot_id: str) -> list[str]:
    """Every step-binding pattern the run's snapshot recorded, in the order the run read them."""
    patterns: list[str] = []
    for row in conn.execute(
            "SELECT o.value FROM observation o JOIN artefact a ON a.id = o.artefact_id"
            " WHERE a.snapshot_id = ? AND o.key LIKE 'binding:%' ORDER BY o.id",
            (snapshot_id,)):
        pattern = _json(row["value"]).get("pattern")
        if pattern and pattern not in patterns:
            patterns.append(pattern)
    return patterns


def _nearest_patterns(patterns: list[str], text: str, n: int) -> list[str]:
    """The ``n`` declared patterns closest to ``text``, by the same ratio the ecosystem uses."""
    if not text:
        return []
    ranked = sorted(patterns, key=lambda pattern: -difflib.SequenceMatcher(
        None, pattern.lower(), text.lower()).ratio())
    return ranked[:n]


def list_runs(conn, project: str | None = None, limit: int = 40) -> list[dict]:
    """Every run in the store, newest first, with the counts the store can prove.

    A run whose analyser this build cannot run is skipped for the same reason the dashboard skips
    its case (TESTOPS-35): nothing here could have produced it. The counts are cheap - claims, the
    cases that carry a finding, and those findings - so the list can afford one query per row for
    the source facts without reading a single artefact.
    """
    terminals = ",".join("?" * len(cases.TERMINAL))
    sql = ("SELECT r.id, r.project, r.analyser, r.status, r.started_at, r.finished_at,"
           "       s.artefact_versions,"
           "       (SELECT COUNT(*) FROM claim c WHERE c.run_id = r.id) AS claims,"
           "       (SELECT COUNT(*) FROM case_ k WHERE k.run_id = r.id"
           "          AND EXISTS (SELECT 1 FROM finding f WHERE f.case_id = k.id)) AS case_count,"
           "       (SELECT COUNT(*) FROM case_ k WHERE k.run_id = r.id"
           "          AND EXISTS (SELECT 1 FROM finding f WHERE f.case_id = k.id)"
           "          AND (SELECT st.state FROM case_state st WHERE st.case_id = k.id"
           "                ORDER BY st.id DESC LIMIT 1) IN (" + terminals + "))"
           "         AS decided_cases,"
           "       (SELECT COUNT(*) FROM finding f JOIN case_ k ON k.id = f.case_id"
           "         WHERE k.run_id = r.id) AS findings"
           "  FROM run r LEFT JOIN snapshot s ON s.id = r.snapshot_id")
    args: tuple = tuple(cases.TERMINAL)
    if project:
        sql += " WHERE r.project = ?"
        args += (project,)
    sql += " ORDER BY COALESCE(r.finished_at, r.started_at) DESC, r.id DESC LIMIT ?"
    rows = conn.execute(sql, args + (200,)).fetchall()
    out: list[dict] = []
    for row in rows:
        if not is_registered(row["analyser"]):
            continue
        record = {"id": row["id"], "project": row["project"], "analyser": row["analyser"],
                  "status": row["status"], "started_at": row["started_at"],
                  "finished_at": row["finished_at"], "claims": int(row["claims"]),
                  "case_count": int(row["case_count"]), "decided_cases": int(row["decided_cases"]),
                  "findings": int(row["findings"]),
                  "versions": _json(row["artefact_versions"])}
        record.update(_source_facts(conn, row["id"], row["analyser"]))
        out.append(record)
        if len(out) >= limit:
            break
    return out


def evidence_for_claim(conn, claim: dict) -> list[dict] | None:
    """The observations that bear on this claim, and nothing else.

    A v2 claim records, in ``support``, the observation rows its verdict was derived from - for a
    level claim, the step definitions that bind its steps. Those rows are returned first and in the
    claim's own order, so the page shows exactly what the analysis used; the first is the binding of
    the step that is asserted. The scenario observation that contains the assertion is then added,
    because the verdict's span is a fact about the whole scenario.

    When the claim records no support (nothing bound, or a run written before support was wired) the
    evidence is derived from the coordinates instead - but only the observations that bear on the
    claim: the binding whose pattern matches the asserting step, and the scenario whose span contains
    the assertion's line. Sharing a file is not bearing on a claim. A claim at line 59 in a file of
    six scenarios gets its own scenario, never the other five.

    A v2 claim names a commit and a path; the coordinate fallback matches artefacts of the claim's
    *own run* whose uri carries that commit and that path, character for character. There is
    deliberately no ``LIKE %feature%`` here: that lookup resolved a scenario name to any file whose
    path contained it, which is how a claim in ``a/x.feature`` acquired links to ``b/x.y.feature``
    and to same-named files from other snapshots.

    Returns ``None`` when the claim has no coordinates to resolve (a v1 claim): "nothing was
    recorded" and "nothing was found" are different facts, and the page renders them differently.
    An empty list means the coordinates are known and this run recorded no observations that bear on
    the claim.
    """
    prov = claim["provenance"]
    if claim["schema_version"] != 2 or not prov["assertion_path"] or not prov["assertion_commit"]:
        return None
    run = conn.execute("SELECT snapshot_id FROM run WHERE id = ?", (claim["run_id"],)).fetchone()
    if not run:
        return None
    snapshot = run["snapshot_id"]

    supported = _observations_by_id(conn, claim.get("support") or [], snapshot)
    if supported:
        asserted = _mark_asserting(supported, claim)
        return _with_containing_scenario(conn, claim, snapshot, supported, asserted)

    return _relevant_at_coordinates(conn, claim, snapshot)


def _binds_assertion(item: dict, text: str) -> bool:
    """Whether this evidence row is the binding of the step the claim asserts."""
    key = str(item.get("key") or "")
    if not key.startswith("binding:") or not text:
        return False
    try:
        _, _, pattern = key.split(":", 2)
    except ValueError:
        return False
    try:
        return bool(stepbindings.pattern_to_regex(pattern).match(text))
    except re.error:
        return False


def _mark_asserting(items: list[dict], claim: dict) -> bool:
    """Name the asserting step's binding as such, when it is the first row.

    The analyser puts the asserting step's binding first. A claim whose asserting step is unbound
    has only its scenario's other bindings in support, and none of those is the step asserted - the
    page must not call one of them that.
    """
    text = claim["provenance"]["assertion_text"] or ""
    if items and _binds_assertion(items[0], text):
        items[0]["asserted"] = True
        return True
    return False


def _with_containing_scenario(conn, claim: dict, snapshot: str,
                              items: list[dict], asserted: bool) -> list[dict]:
    """Insert the scenario that contains the assertion, after the asserting step."""
    scenario = _containing_scenario(conn, claim, snapshot)
    if scenario is None or any(item["id"] == scenario["id"] for item in items):
        return items
    if not items:
        return [scenario]
    return [items[0], scenario, *items[1:]] if asserted else [scenario, *items]


def _relevant_at_coordinates(conn, claim: dict, snapshot: str) -> list[dict]:
    """Evidence for a claim with no recorded support: only what bears on its own assertion."""
    out: list[dict] = []
    binding = _asserting_binding(conn, claim, snapshot)
    if binding is not None:
        binding["asserted"] = True
        out.append(binding)
    scenario = _containing_scenario(conn, claim, snapshot)
    if scenario is not None:
        out.append(scenario)
    return out


def _artefacts_at_coordinates(conn, claim: dict, snapshot: str):
    prov = claim["provenance"]
    for a in conn.execute("SELECT id, uri, kind FROM artefact WHERE snapshot_id = ? ORDER BY id",
                          (snapshot,)):
        m = GITHUB.match(a["uri"])
        if m and m["sha"] == prov["assertion_commit"] and m["path"] == prov["assertion_path"]:
            yield a


def _containing_scenario(conn, claim: dict, snapshot: str) -> dict | None:
    """The scenario observation whose span contains the assertion's line.

    Scenario rows carry the line the scenario starts at. The containing scenario is the latest one
    that starts at or before the assertion - never another scenario in the same file, however close.
    """
    line = claim["provenance"]["assertion_line"]
    if not isinstance(line, int):
        return None
    best: tuple[int, dict] | None = None
    for a in _artefacts_at_coordinates(conn, claim, snapshot):
        for o in conn.execute(
                "SELECT id, key, value FROM observation WHERE artefact_id = ? AND key LIKE 'scenario:%'"
                " ORDER BY id", (a["id"],)):
            value = _json(o["value"])
            start = value.get("line")
            if not isinstance(start, int) or start > line:
                continue
            if best is None or start > best[0]:
                best = (start, _evidence_item(o["key"], value, a["uri"], a["kind"], o["id"]))
    return best[1] if best else None


def _asserting_binding(conn, claim: dict, snapshot: str) -> dict | None:
    """The binding observation whose pattern matches the asserting step, from the claim's own snapshot.

    A run that recorded no support still recorded the step definitions. The binding is found by
    matching the assertion's own text, exactly as the analyser matched it, so the row shown is the
    one the verdict would have rested on. A binding in another suite may match the same text; the
    suite the feature belongs to wins, then the earliest line, so the choice is deterministic.
    """
    prov = claim["provenance"]
    text = prov["assertion_text"]
    if not text:
        return None
    return _binding_for(conn, snapshot, text, prov["assertion_path"])


def _binding_for(conn, snapshot: str, text: str, path: str | None) -> dict | None:
    """The binding that runs ``text`` in ``path``'s suite, resolved from the snapshot's own rows.

    The same resolution the claim's own evidence uses, offered as a function so the copy a duplicate
    claim names can be bound by the text the store recorded for it - never by re-reading today's
    corpus. The suite the file belongs to wins on a tie, then the earliest line.
    """
    if not text:
        return None
    suite = stepbindings.suite_of(path or "")
    candidates: list[tuple[bool, int, int, dict]] = []
    for row in conn.execute(
            """SELECT o.id, o.key, o.value, a.uri, a.kind
                 FROM observation o JOIN artefact a ON a.id = o.artefact_id
                WHERE a.snapshot_id = ? AND o.key LIKE 'binding:%' ORDER BY o.id""", (snapshot,)):
        value = _json(row["value"])
        pattern = value.get("pattern")
        if not pattern:
            continue
        m = GITHUB.match(row["uri"])
        binding = stepbindings.Binding(
            pattern=pattern, verb=value.get("verb", ""), cls=value.get("class", ""),
            path=m["path"] if m else row["uri"], layer=value.get("layer") or "unknown",
            suite=value.get("suite") or "", line=value.get("line") or 0)
        if stepbindings.match_step([binding], text, suite) is None:
            continue
        candidates.append((binding.suite != suite, binding.line, row["id"],
                           _evidence_item(row["key"], value, row["uri"], row["kind"], row["id"])))
    if not candidates:
        return None
    candidates.sort(key=lambda candidate: (candidate[0], candidate[1], candidate[2]))
    return candidates[0][3]


def _observations_by_id(conn, ids: list[int], snapshot_id: str) -> list[dict]:
    """The rows a claim names, in the claim's order, and only if they belong to its own snapshot.

    A support id from another run would be an artefact of the wrong snapshot wearing this claim's
    coordinates; it is skipped rather than shown.
    """
    out: list[dict] = []
    for observation_id in ids:
        row = conn.execute(
            """SELECT o.id, o.key, o.value, a.uri, a.kind, a.snapshot_id
                 FROM observation o JOIN artefact a ON a.id = o.artefact_id
                WHERE o.id = ?""", (observation_id,)).fetchone()
        if row is None or row["snapshot_id"] != snapshot_id:
            continue
        out.append(_evidence_item(row["key"], _json(row["value"]), row["uri"], row["kind"],
                                  row["id"]))
    return out


def _evidence_item(key: str, value: dict, uri: str, kind: str, observation_id: int) -> dict:
    line = value.get("line")
    # ``layer`` is carried as a value, not only baked into ``shows``: a page that groups the steps
    # around a claim needs to say "each of them uses a browser" once, rather than ending every line
    # with the same clause (TESTOPS-23, AC6).
    return {"id": observation_id, "uri": uri, "kind": kind, "key": key, "line": line,
            "layer": value.get("layer"), "link": permalink(uri, line),
            "where": short_location(uri, line), "shows": _shows(key, value), "asserted": False}


# What a step definition's layer means, as the sentence a reader gets next to the link. The same
# words the case page uses for the instrument, so a binding and a claim cannot describe the test
# differently.
BINDING_WORD = {
    "storage": "reads the database",
    "engine": "talks to the engine in-process",
    "controller": "calls the application's own controllers in-process",
    "api": "drives the HTTP API",
    "ui": "drives a browser",
    "unknown": "reaches no layer we could identify",
}


def _shows(key: str, value: dict) -> str:
    """One line saying what an observation shows - the sentence a bare link cannot give."""
    line = value.get("line")
    if key.startswith("scenario:"):
        name = key[len("scenario:"):]
        where = f"line {line}" if line else "an unrecorded line"
        steps = value.get("steps")
        count = f", {steps} step{'s' if steps != 1 else ''}" if isinstance(steps, int) else ""
        return f"the scenario \u201c{name}\u201d begins at {where}{count}"
    if key.startswith("binding:"):
        _, verb, pattern = key.split(":", 2)
        layer = value.get("layer")
        layer_words = BINDING_WORD.get(layer, BINDING_WORD["unknown"])
        # No line number here: the link beside this sentence already ends at the binding's line.
        return f"a {verb.capitalize()} step definition for \u201c{pattern}\u201d that {layer_words}"
    return f"an observation of {key}" + (f" at line {line}" if line else "")


# ---------------------------------------------------------------- source snippets
#
# The Product Owner's second finding: a list of links is not evidence a reader can check without
# leaving the tool. Both excerpts are read from the content-addressed blob store, so the page
# renders from the store alone and the same bytes are shown today as on the day of the claim. A
# snippet the store cannot produce says so; it never renders an empty box.

# The states a snippet can be in. They are distinct because they are distinct facts: no coordinates
# for a v1 claim, coordinates but no artefact row, an artefact whose blob was not kept, or a line the
# stored file is too short to hold. Only one of them is "there is nothing to show".
SNIPPET_NO_COORDINATES = "no_coordinates"
SNIPPET_NOT_RECORDED = "not_recorded"
SNIPPET_NOT_STORED = "not_stored"
SNIPPET_PAST_END = "past_end"
SNIPPET_NO_BINDING = "no_binding"
SNIPPET_OK = "ok"


def source_snippets(conn, claim: dict) -> dict:
    """The two code excerpts a reader needs: the asserted step, and the body that runs it."""
    return {"assertion": _assertion_snippet(conn, claim),
            "step_definition": _step_definition_snippet(conn, claim)}


def _claim_snapshot(conn, claim: dict) -> str | None:
    row = conn.execute("SELECT snapshot_id FROM run WHERE id = ?", (claim["run_id"],)).fetchone()
    return row["snapshot_id"] if row else None


def _blob_lines(sha: str | None) -> list[str] | None:
    """The stored file's lines, or ``None`` when this store does not hold the blob.

    A missing blob is an absence of stored content, not an empty file: the caller renders the
    recorded-but-not-stored sentence rather than an empty box.
    """
    if not sha:
        return None
    try:
        return blobs.text(sha).splitlines()
    except FileNotFoundError:
        return None


def _artefact_blob(conn, snapshot: str | None, uri: str) -> sqlite3.Row | None:
    if not snapshot:
        return None
    return conn.execute(
        "SELECT uri, kind, blob_sha FROM artefact WHERE snapshot_id = ? AND uri = ?",
        (snapshot, uri)).fetchone()


def _artefact_blob_at(conn, snapshot: str | None, commit: str | None,
                      path: str | None) -> sqlite3.Row | None:
    """The artefact whose commit and path are *equal* to the claim's - never a suffix match."""
    if not (snapshot and commit and path):
        return None
    for row in conn.execute(
            "SELECT uri, kind, blob_sha FROM artefact WHERE snapshot_id = ?", (snapshot,)):
        m = GITHUB.match(row["uri"])
        if m and m["sha"] == commit and m["path"] == path:
            return row
    return None


def _assertion_snippet(conn, claim: dict) -> dict:
    """The feature file's lines around the asserted step, with that line marked."""
    prov = claim["provenance"]
    path, line = prov["assertion_path"], prov["assertion_line"]
    if claim["schema_version"] != 2 or not path or not isinstance(line, int):
        return {"state": SNIPPET_NO_COORDINATES}
    snapshot = _claim_snapshot(conn, claim)
    artefact = _artefact_blob_at(conn, snapshot, prov["assertion_commit"], path)
    if artefact is None:
        return {"state": SNIPPET_NOT_RECORDED, "path": path, "line": line,
                "link": claim.get("permalink")}
    lines = _blob_lines(artefact["blob_sha"])
    if lines is None:
        return {"state": SNIPPET_NOT_STORED, "path": path, "line": line,
                "link": claim.get("permalink")}
    if line < 1 or line > len(lines):
        return {"state": SNIPPET_PAST_END, "path": path, "line": line, "total": len(lines),
                "link": claim.get("permalink")}
    start = max(1, line - SNIPPET_CONTEXT)
    end = min(len(lines), line + SNIPPET_CONTEXT)
    return {"state": SNIPPET_OK, "path": path, "line": line, "start": start, "end": end,
            "commit": prov["assertion_commit"],
            "lines": [{"n": n, "text": lines[n - 1], "asserted": n == line}
                      for n in range(start, end + 1)],
            "link": claim.get("permalink")}


def _asserted_binding(claim: dict) -> dict | None:
    """The evidence row the analyser named as the step that is asserted, if it did."""
    for item in claim.get("evidence") or []:
        if item.get("asserted"):
            return item
    return None


def _step_definition_snippet(conn, claim: dict) -> dict:
    """The step definition that runs the assertion, as lines starting at its attribute."""
    if claim["schema_version"] != 2:
        return {"state": SNIPPET_NO_COORDINATES}
    binding = _asserted_binding(claim)
    if binding is None:
        return {"state": SNIPPET_NO_BINDING}
    return _binding_snippet(conn, _claim_snapshot(conn, claim), binding)


def _binding_snippet(conn, snapshot: str | None, binding: dict) -> dict:
    """A step definition's body, from the row that records its file and line.

    Shared with the copy a duplicate claim names, so both definitions are read the same way: the
    body starts at the attribute's line and ends at the first blank line after it.
    """
    uri, line = binding.get("uri"), binding.get("line")
    m = GITHUB.match(uri or "")
    path = m["path"] if m else (uri or "")
    if not isinstance(line, int) or line < 1:
        return {"state": SNIPPET_NOT_RECORDED, "path": path, "line": line,
                "link": binding.get("link")}
    artefact = _artefact_blob(conn, snapshot, uri)
    if artefact is None:
        return {"state": SNIPPET_NOT_RECORDED, "path": path, "line": line,
                "link": binding.get("link")}
    lines = _blob_lines(artefact["blob_sha"])
    if lines is None:
        return {"state": SNIPPET_NOT_STORED, "path": path, "line": line,
                "link": binding.get("link")}
    if line > len(lines):
        return {"state": SNIPPET_PAST_END, "path": path, "line": line, "total": len(lines),
                "link": binding.get("link")}
    end = min(len(lines), line + STEPDEF_LINES - 1)
    window = lines[line - 1:end]
    # A body ends at the blank line after it; the next attribute is the next step, not this one.
    for offset, text in enumerate(window[1:], start=1):
        if not text.strip():
            window = window[:offset]
            break
    end = line + len(window) - 1
    return {"state": SNIPPET_OK, "path": path, "line": line, "start": line, "end": end,
            "commit": m["sha"] if m else None,
            "lines": [{"n": n, "text": window[n - line], "asserted": n == line}
                      for n in range(line, end + 1)],
            "link": binding.get("link")}


# ---------------------------------------------------------------- the product's own line (TESTOPS-83)
#
# The case page made two claims and showed one line of code. "The product already declares POST /"
# is a claim about the product's own source, and a reader had to leave the page to check it - which
# for a tool whose claim is that it read both sides is the argument missing. The matched surface is
# recorded on the claim as an id (``api:POST /@room/src/.../RoomController.java:createRoom``), and
# the run stored the product repository at the commit it read. This module resolves that id against
# the stored bytes: the annotation and the method signature, with their file, line and commit. It
# never opens a checkout, never fetches anything, and says which absence it found when the store
# cannot produce the line.
#
# The trim is honest: a handful of declaration lines are shown, and when the declaration is longer
# the page states how many of its lines were not shown. The matched word is marked per occurrence, so
# the reader sees the word that justified the match rather than being told about it.

PRODUCT_LINE_OK = "ok"
PRODUCT_LINE_NO_COORDINATES = "no_coordinates"
PRODUCT_LINE_NOT_STORED = "not_stored"
PRODUCT_LINE_NOT_FOUND = "not_found"
PRODUCT_LINE_AMBIGUOUS = "ambiguous"
PRODUCT_LINE_BLIND = "blind"

# The most declaration lines the page shows. The annotation and signature normally fit well within
# it; a longer declaration states the rest as a count, never as a silent cut.
PRODUCT_SNIPPET_MAX = 8

# ``api:<VERB> <route>@<path>:<method>``, with an optional ``#2`` for a duplicate declaration.
_JAVA_SURFACE = re.compile(r"^api:(?P<target>.+)@(?P<path>.+):(?P<method>[^:#]+?)(?:#\d+)?$")
# A Python route surface records the route only: ``api:GET /booking``.
_ROUTE_SURFACE = re.compile(r"^api:(?P<verb>[A-Z]+) (?P<route>.+)$")


def _line_starts(text: str) -> list[int]:
    """The offset at which each line starts, so a token offset becomes a line number."""
    starts = [0]
    for offset, char in enumerate(text):
        if char == "\n":
            starts.append(offset + 1)
    return starts


def _line_at(starts: list[int], offset: int) -> int:
    """The 1-based line holding ``offset``."""
    import bisect
    return bisect.bisect_right(starts, offset)


def _locate_java_declaration(lines: list[str], method: str) -> dict | None:
    """The annotation block and signature that declare ``method``, by line, from stored bytes.

    The Java reader's own lexer is used, so a method name inside a comment or a string cannot be
    mistaken for the declaration. Returns ``None`` when the stored file holds no such declaration -
    an absence the page names rather than guesses around.
    """
    text = "\n".join(lines)
    tokens = java_surface.lex(text)
    starts = _line_starts(text)
    found = None
    for index, token in enumerate(tokens[:-1]):
        if (token.kind == "word" and token.value == method
                and tokens[index + 1].kind == "symbol" and tokens[index + 1].value == "("):
            found = index
            break
    if found is None:
        return None
    decl_line = _line_at(starts, tokens[found].start)
    signature_end = decl_line
    depth = 0
    for index in range(found + 1, len(tokens)):
        token = tokens[index]
        if token.kind != "symbol":
            continue
        if token.value == "(":
            depth += 1
        elif token.value == ")":
            depth -= 1
            if depth == 0:
                signature_end = _line_at(starts, token.start)
                break
    else:
        return None
    # The declaration's extent: the method body, so the count of lines not shown is the handler's
    # own length and not the file's.
    decl_end = signature_end
    index = found
    while index < len(tokens):
        token = tokens[index]
        if token.kind == "symbol" and token.value in ("{", ";"):
            if token.value == ";":
                break
            level = 0
            for following in range(index, len(tokens)):
                if tokens[following].kind != "symbol":
                    continue
                if tokens[following].value == "{":
                    level += 1
                elif tokens[following].value == "}":
                    level -= 1
                    if level == 0:
                        decl_end = _line_at(starts, tokens[following].start)
                        break
            break
        index += 1
    # Annotations sit above the signature, contiguously. A multi-line annotation is walked through
    # by its own unbalanced parentheses, so a wrapped argument cannot be mistaken for the signature.
    start = decl_line
    above = decl_line - 1
    while above >= 1:
        stripped = lines[above - 1].strip()
        if not stripped:
            break
        if stripped.startswith("@"):
            start = above
            above -= 1
            continue
        block = "\n".join(lines[above - 1:decl_line - 1])
        if block.count("(") > block.count(")"):
            start = above
            above -= 1
            continue
        break
    return {"start": start, "decl_line": decl_line,
            "signature_end": signature_end, "end": decl_end}


def _locate_python_declarations(lines: list[str], route: str):
    """Every function in one stored Python file whose declaration holds ``route`` as a literal.

    The declaration includes its decorators: a route may be named by ``@app.route("/booking")`` or
    by a literal inside the body, and the surface reader counts a function as a route handler when
    the route appears in its source.
    """
    source = "\n".join(lines)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    pattern = re.compile("[\"']" + re.escape(route) + "[\"']")
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = min([node.lineno] + [decorator.lineno for decorator in node.decorator_list])
        end = node.end_lineno or node.lineno
        if pattern.search("\n".join(lines[start - 1:end])):
            out.append(node)
    return out


def _python_signature_end(lines: list[str], first_line: int) -> int:
    """The line on which the ``def`` parameter list closes."""
    depth = 0
    for number in range(first_line, len(lines) + 1):
        text = lines[number - 1]
        for char in text:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
        if depth <= 0 and "(" in "\n".join(lines[first_line - 1:number]):
            return number
    return first_line


def _snapshot_product_coordinates(conn, claim: dict) -> tuple[str | None, str | None]:
    """The product repository slug and the commit this claim's run read it at."""
    row = conn.execute("SELECT meta, artefact_versions FROM snapshot WHERE id = ?",
                       (_claim_snapshot(conn, claim),)).fetchone()
    if row is None:
        return None, None
    meta = _json(row["meta"])
    versions = _json(row["artefact_versions"])
    slug = ((meta.get("arms") or {}).get("product")) if isinstance(meta, dict) else None
    return slug, versions.get(slug) if slug else None


def _product_artefact(conn, claim: dict, path: str):
    """The stored product file at the exact path this run read, or ``None``.

    The artefact rows are searched for a ``repo@commit:path`` whose path is *equal* to the surface's
    and whose repository is the product arm; the commit recorded for the product arm is preferred, so
    a file at another commit in the same store cannot stand in for this run's evidence.
    """
    snapshot = _claim_snapshot(conn, claim)
    slug, commit = _snapshot_product_coordinates(conn, claim)
    best = None
    for row in conn.execute("SELECT uri, kind, blob_sha FROM artefact WHERE snapshot_id = ?",
                            (snapshot,)):
        match = GITHUB.match(row["uri"] or "")
        if match is None or match["path"] != path:
            continue
        repo = f"{match['owner']}/{match['repo']}"
        if slug and repo != slug:
            continue
        if commit and match["sha"] == commit:
            return row, match
        if best is None:
            best = (row, match)
    return best if best else (None, None)


def _declaration_lines(lines: list[str], start: int, signature_end: int, total_end: int,
                       ceiling: int) -> tuple[list[dict], int]:
    """The annotation and signature lines shown, and how many declaration lines are not.

    The declaration's *body* is not shown: the line a verdict rests on is the annotation and the
    signature, not the handler's implementation. The count of lines not shown still describes the
    whole declaration, so a 400-line handler says so rather than appearing to be two lines.
    """
    shown_end = min(signature_end, start + ceiling - 1)
    shown = [{"n": number, "text": lines[number - 1], "asserted": False}
             for number in range(start, shown_end + 1)]
    return shown, max(0, total_end - shown_end)


def _product_record(record: dict, shown: list[dict], omitted: int, end: int) -> dict:
    """Fill a product-snippet record once the declaration has been located."""
    text = "\n".join(line["text"] for line in shown)
    reason = services.credential_reason(text)
    if reason is not None:
        record.update({"state": PRODUCT_LINE_BLIND, "reason": reason})
        return record
    record.update({"state": PRODUCT_LINE_OK, "lines": shown, "omitted": omitted,
                   "total": end - record["start"] + 1, "max": PRODUCT_SNIPPET_MAX})
    return record


def _java_product_line(conn, claim: dict, record: dict, path: str, method: str) -> dict:
    """The annotation and signature of the Java method the matched route came from."""
    artefact, match = _product_artefact(conn, claim, path)
    record.update({"path": path, "method": method,
                   "link": blob_permalink(f"{match['owner']}/{match['repo']}", match["sha"], path)
                   if match else None, "commit": match["sha"] if match else None})
    if artefact is None:
        return record                            # no recorded line and no stored file
    assert match is not None
    lines = _blob_lines(artefact["blob_sha"])
    if lines is None:
        record["state"] = PRODUCT_LINE_NOT_STORED
        return record
    located = _locate_java_declaration(lines, method)
    if located is None:
        record["state"] = PRODUCT_LINE_NOT_FOUND
        record["total"] = len(lines)
        return record
    start, end = located["start"], located["end"]
    shown, omitted = _declaration_lines(lines, start, located["signature_end"], end,
                                        PRODUCT_SNIPPET_MAX)
    record.update({"start": start, "line": start,
                   "signature_line": located["signature_end"], "end": end,
                   "link": blob_permalink(f"{match['owner']}/{match['repo']}", match["sha"],
                                          path, start)})
    return _product_record(record, shown, omitted, end)


def _python_product_line(conn, claim: dict, record: dict, surface_id: str) -> dict:
    """The decorator and signature of the Python function behind a matched route surface.

    A Python route surface records its route and nothing else, so the declaration is resolved from
    the stored product files by the surface reader's own rule: a function whose source holds the
    route as a string literal. One match is evidence; none, or more than one, is said rather than
    guessed at.
    """
    target = _ROUTE_SURFACE.match(surface_id or "")
    if target is None:
        return record
    route = target["route"]
    snapshot = _claim_snapshot(conn, claim)
    candidates = []
    for row in conn.execute("SELECT uri, blob_sha FROM artefact WHERE snapshot_id = ?",
                            (snapshot,)):
        match = GITHUB.match(row["uri"] or "")
        if match is None or not match["path"].endswith(".py"):
            continue
        lines = _blob_lines(row["blob_sha"])
        if lines is None:
            continue
        for node in _locate_python_declarations(lines, route):
            candidates.append((row, match, lines, node))
    record.update({"route": route, "state": PRODUCT_LINE_NOT_FOUND})
    if not candidates:
        record["reason"] = "the stored product holds no function that declares this route"
        return record
    if len(candidates) > 1:
        record["state"] = PRODUCT_LINE_AMBIGUOUS
        record["reason"] = (f"the stored product holds {len(candidates)} functions that declare "
                            f"this route, so the page cannot say which one the verdict rests on")
        return record
    row, match, lines, node = candidates[0]
    start = min([node.lineno] + [decorator.lineno for decorator in node.decorator_list])
    signature_end = _python_signature_end(lines, node.lineno)
    end = node.end_lineno or signature_end
    shown, omitted = _declaration_lines(lines, start, signature_end, end, PRODUCT_SNIPPET_MAX)
    record.update({"path": match["path"], "method": node.name, "line": start,
                   "signature_line": signature_end, "start": start, "end": end,
                   "commit": match["sha"],
                   "link": blob_permalink(f"{match['owner']}/{match['repo']}", match["sha"],
                                          match["path"], start)})
    return _product_record(record, shown, omitted, end)


def product_line_for(conn, claim: dict) -> dict | None:
    """The product's own declaration for the surface this claim matched, or ``None``.

    ``None`` when the claim recorded no product surface at all: the page then has nothing it could
    show, and a block saying so on every claim the product is not evidence about would be noise. A
    recorded surface the store cannot resolve is a dict in one of the absence states, which the page
    names.
    """
    product = (claim.get("detail") or {}).get("product")
    if not isinstance(product, dict) or product.get("state") not in ("found", "zero"):
        return None
    surface_id = product.get("surface")
    if not surface_id:
        return None
    record = {"state": PRODUCT_LINE_NO_COORDINATES, "surface": surface_id,
              "route": product.get("route"), "word": product.get("word") or ""}
    java = _JAVA_SURFACE.match(surface_id)
    if java is not None:
        return _java_product_line(conn, claim, record, java["path"], java["method"])
    if (surface_id or "").startswith("api:") and "@" not in surface_id:
        return _python_product_line(conn, claim, record, surface_id)
    return record


# ---------------------------------------------------------------- the copy a duplicate claim names
#
# TESTOPS-32. A duplicate claim says another scenario already asserts the same thing, and records
# that copy's coordinates in ``established_by``. A page that names a copy and does not show it is
# unfalsifiable: the reader cannot see for themselves whether the two assertions are the same. The
# counterpart is resolved from the recorded coordinates and the stored blob - never by re-parsing
# the corpus at render time - so the copy shown is the one the claim was raised against.

# The one state a counterpart can be in that is not a snippet state: the stored file parsed, but no
# scenario holds the recorded line. Distinct from "not stored", because the bytes are here.
COUNTERPART_NO_SCENARIO = "no_scenario"

# The coordinates a duplicate claim records, as the rule wrote them: the copy's ``file:line``. A
# path may hold dots, slashes and hyphens, and a feature file ends in ``.feature``.
COUNTERPART = re.compile(r"([\w./\\-]+\.feature):(\d+)")


def counterpart_coordinates(claim: dict) -> tuple[str, int] | None:
    """The ``file:line`` a duplicate claim names for its copy, read from ``established_by``.

    ``None`` when the claim is not a duplicate, or when no coordinates were recorded: a v1 row, or
    one written before the rule put the copy in its evidence. That is "nothing was recorded", and a
    page must say so rather than invent a copy.
    """
    if claim.get("verdict") != "duplicate":
        return None
    match = COUNTERPART.search(claim.get("established_by") or "")
    if match is None:
        return None
    return match.group(1), int(match.group(2))


def counterpart_for(conn, claim: dict) -> dict | None:
    """The copy this duplicate claim names, resolved from its own coordinates and stored blob.

    The record carries the copy's ``file:line``, the title of the scenario that holds that line,
    the scenario's source (its steps, tables and doc strings verbatim) and the step definition that
    runs the step there. ``state`` says which of those are readable: a coordinate this snapshot
    cannot place, or an artefact whose blob was not kept, is an absence with a name - never a blank
    box and never a copy composed from somewhere else.
    """
    coordinates = counterpart_coordinates(claim)
    if coordinates is None:
        return None
    path, line = coordinates
    commit = (claim.get("provenance") or {}).get("assertion_commit")
    snapshot = _claim_snapshot(conn, claim)
    repo = _repo_for_coordinates(conn, _project_of_run(conn, claim["run_id"]), commit, path)
    record = {"path": path, "line": line, "link": blob_permalink(repo, commit, path, line),
              "state": SNIPPET_NOT_RECORDED, "scenario": None, "scenario_line": None,
              "snippet": None, "definition": None}
    artefact = _artefact_blob_at(conn, snapshot, commit, path)
    if artefact is None:
        return record
    lines = _blob_lines(artefact["blob_sha"])
    if lines is None:
        record["state"] = SNIPPET_NOT_STORED
        return record
    if line < 1 or line > len(lines):
        record["state"] = SNIPPET_PAST_END
        record["total"] = len(lines)
        return record
    feature = gherkin.parse(path, "\n".join(lines))
    scenario = _scenario_containing(feature, line)
    if scenario is None:
        record["state"] = COUNTERPART_NO_SCENARIO
        return record
    start = scenario.line
    end = _scenario_end(feature, scenario, len(lines))
    while end > start and not lines[end - 1].strip():
        end -= 1
    record.update({
        "state": SNIPPET_OK,
        "scenario": scenario.name,
        "scenario_line": scenario.line,
        "snippet": {"state": SNIPPET_OK, "path": path, "line": line, "start": start, "end": end,
                    "lines": [{"n": n, "text": lines[n - 1], "asserted": n == line}
                              for n in range(start, end + 1)],
                    "link": record["link"]},
    })
    step = _step_at(scenario, line)
    binding = _binding_for(conn, snapshot or "", step.text if step is not None else "", path)
    if binding is None:
        record["definition"] = {"state": SNIPPET_NO_BINDING, "path": path, "line": line,
                                "link": record["link"]}
    else:
        record["definition"] = _binding_snippet(conn, snapshot, binding)
    return record


def _scenario_containing(feature, line: int):
    """The scenario that holds ``line``: the latest one starting at or before it."""
    if feature is None:
        return None
    best = None
    for scenario in feature.scenarios:
        if scenario.line <= line and (best is None or scenario.line > best.line):
            best = scenario
    return best


def _scenario_end(feature, scenario, total: int) -> int:
    """The last line of the scenario, before the next scenario starts, or the end of the file."""
    later = [other.line for other in feature.scenarios if other.line > scenario.line]
    return min(later) - 1 if later else total


def _step_at(scenario, line: int):
    """The step the claim names inside the copy's scenario, by the line the claim recorded."""
    for step in scenario.steps:
        if step.line == line:
            return step
    return None


def _attach_snippets(conn, claim: dict) -> dict:
    """Attach the source excerpts after the evidence, which names the asserting binding."""
    claim["snippets"] = source_snippets(conn, claim)
    claim["snippets"]["product"] = product_line_for(conn, claim)
    claim["counterpart"] = counterpart_for(conn, claim)
    claim["also_reported"] = cross_references(conn, claim)
    return claim


# ---------------------------------------------------------------- the other analyser's claim
#
# TESTOPS-36. The level-fitness and duplication analysers both examine the same asserting step and
# raise separate claims with separate instructions. Keeping them separate is the decision; leaving
# the reader to find the other page is the defect. This read model answers one question - which
# other analysers have already raised a claim about this exact step? - from stored rows only.
#
# The identity is the claim's own coordinates: ``assertion_path``, ``assertion_line`` and
# ``assertion_commit``. In this product each analyser writes its own snapshot over the same commit,
# so the snapshot id is not shared and cannot be the key; the three coordinates are what both runs
# recorded about the same line of the same file at the same commit. Nothing is re-analysed here: a
# counterpart exists only because a stored claim row says so, and it is offered only when a case
# exists to open. Anything else - a claim with no case, an analyser this build cannot run - is
# silence, because a cross-reference that cannot be followed is a guess.

def cross_references(conn, claim: dict) -> list[dict]:
    """Other analysers' claims about the same asserting step, one per analyser, or ``[]``.

    A reference carries the analyser, the verdict it reached, the id of the case a reader can open,
    and - for a duplicate claim - the copy's ``file:line``, decoded from that claim's own
    ``established_by``. ``[]`` means the store holds no followable counterpart, which a page renders
    as nothing rather than as an empty section.
    """
    prov = claim.get("provenance") or {}
    path, line, commit = (prov.get("assertion_path"), prov.get("assertion_line"),
                          prov.get("assertion_commit"))
    if claim.get("schema_version") != 2 or not path or not isinstance(line, int) or not commit:
        return []
    rows = conn.execute(
        "SELECT id, analyser, verdict, established_by FROM claim"
        " WHERE assertion_path = ? AND assertion_line = ? AND assertion_commit = ?"
        "   AND analyser <> ? AND schema_version = 2"
        " ORDER BY id",
        (path, line, commit, claim.get("analyser") or "")).fetchall()
    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        if not is_registered(row["analyser"]) or row["analyser"] in seen:
            continue
        case_id = _case_for_claim(conn, row["id"])
        if case_id is None:
            continue
        seen.add(row["analyser"])
        copy = counterpart_coordinates({"verdict": row["verdict"],
                                        "established_by": row["established_by"]})
        out.append({"analyser": row["analyser"], "verdict": row["verdict"], "case_id": case_id,
                    "claim_id": row["id"],
                    "copy_path": copy[0] if copy else None,
                    "copy_line": copy[1] if copy else None})
    return out


def _case_for_claim(conn, claim_id: int) -> str | None:
    """The case whose finding names this claim, or ``None`` when it raised no case.

    A claim is evidence; a case is a decision waiting for a person. Only the second has a page, and
    a cross-reference to a claim nobody can open would be a dead link presented as evidence.
    """
    for row in conn.execute(
            "SELECT f.case_id, f.claim_ids FROM finding f JOIN case_ c ON c.id = f.case_id"
            " ORDER BY f.id"):
        if claim_id in _json(row["claim_ids"], []):
            return row["case_id"]
    return None


def recent(conn, project: str | None = None, limit: int = 25) -> list[dict]:
    return cases.list_cases(conn, project, limit)


def freshness(conn, project: str | None = None) -> dict:
    """What the UI must say instead of "all clear": when did we last actually look, and at what commit.

    An empty case list is ambiguous - it can mean "nothing wrong" or "nothing has run since Tuesday". Those are
    the same pixels and different facts, and the second one is how a monitoring tool lies to you.
    """
    sql = """SELECT r.id, r.project, r.analyser, r.status, r.finished_at, s.artefact_versions
             FROM run r LEFT JOIN snapshot s ON s.id = r.snapshot_id
             WHERE r.status IN ('ok','partial')"""
    args: tuple = ()
    if project:
        sql += " AND r.project = ?"
        args = (project,)
    sql += " ORDER BY r.finished_at DESC LIMIT 1"
    row = conn.execute(sql, args).fetchone()
    if not row:
        return {"ever_run": False, "finished_at": None, "project": project, "versions": {}}
    return {"ever_run": True, "finished_at": row["finished_at"], "project": row["project"],
            "analyser": row["analyser"], "run": row["id"], "versions": _json(row["artefact_versions"])}


def latest_per_analyser(conn, project: str | None = None) -> tuple[list[dict], int]:
    """The newest case per (project, analyser) - what a person actually wants to see.

    Older runs are history, not a work queue. Showing every run ever made turns the home screen into a log, and
    a log with 40 rows is a screen nobody opens.

    Each row carries ``statement``: the claim's own words, so the list says what is alleged. The
    stored ``finding.title`` is a truncated copy of that statement (160 characters, cut mid-sentence)
    and never belongs on a screen.

    Each row also carries ``verdict`` and ``scenario``, read from the same claim as ``assertion``.
    The list headline is a judgement plus the scenario title (TESTOPS-33), so the three facts a row
    needs have to come from one claim - a verdict from one claim beside a subject from another
    would describe a case nobody raised.
    """
    rows = cases.list_cases(conn, project, 200)
    seen: set[tuple[str, str]] = set()
    latest, older = [], 0
    for r in rows:
        # A case written by something this build cannot run is not a work item on the dashboard
        # (TESTOPS-35). The page for it answers 404, and a list that links to a 404 while
        # repeating its statement would still be showing the fixture.
        if not is_registered(r["analyser"]):
            continue
        key = (r["project"], r["analyser"])
        if key in seen:
            older += 1
            continue
        seen.add(key)
        r["statement"] = case_statement(conn, r["id"])
        # TESTOPS-23: the list says what the claim asserts, in the test's own words, rather than
        # the analyser's essay about it. A v1 claim has no recorded assertion, so its statement is
        # all there is.
        r["assertion"] = case_assertion(conn, r["id"])
        lead = case_lead(conn, r["id"])
        r["verdict"] = lead["verdict"]
        r["scenario"] = lead["scenario"]
        latest.append(r)
    return latest, older


def case_lead(conn, case_id: str) -> dict:
    """The first claim's verdict and scenario title, or ``None`` for each when it holds no claim.

    The case list's headline names a judgement and a subject, and both must be facts about the same
    claim: the one whose assertion the row already shows. A case with no finding has no verdict,
    and that absence is returned as ``None`` rather than as the words "open" or "resolved".
    """
    row = conn.execute("SELECT claim_ids FROM finding WHERE case_id = ? ORDER BY id LIMIT 1",
                       (case_id,)).fetchone()
    for cid in (_json(row["claim_ids"], []) if row else []):
        claim = conn.execute("SELECT verdict, subject_ref FROM claim WHERE id = ?",
                             (cid,)).fetchone()
        if claim:
            _, _, scenario = claim["subject_ref"].partition("#")
            return {"verdict": claim["verdict"], "scenario": scenario or None}
    return {"verdict": None, "scenario": None}


def case_assertion(conn, case_id: str) -> str | None:
    """The first claim's asserted step, in the test's words, or None when none was recorded."""
    row = conn.execute("SELECT claim_ids FROM finding WHERE case_id = ? ORDER BY id LIMIT 1",
                       (case_id,)).fetchone()
    for cid in (_json(row["claim_ids"], []) if row else []):
        claim = conn.execute("SELECT assertion_text FROM claim WHERE id = ?", (cid,)).fetchone()
        if claim and claim["assertion_text"]:
            return claim["assertion_text"]
    return None


def case_statement(conn, case_id: str) -> str | None:
    """The first claim's statement in a case, or None when the case has no finding."""
    row = conn.execute("SELECT claim_ids FROM finding WHERE case_id = ? ORDER BY id LIMIT 1",
                       (case_id,)).fetchone()
    for cid in (_json(row["claim_ids"], []) if row else []):
        claim = conn.execute("SELECT statement FROM claim WHERE id = ?", (cid,)).fetchone()
        if claim:
            return claim["statement"]
    return None
