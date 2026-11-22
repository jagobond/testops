"""Read models for the UI.

Deliberately separate from the analysers: a view may not need every column, and a UI that reaches into the store
for raw joins ends up encoding analysis logic in templates. Each function here answers one screen's question and
returns plain dicts.
"""
from __future__ import annotations

import json
import re
import sqlite3

from . import blobs, cases, sources
from .extract import csproj, stepbindings
from .links import GITHUB, blob_permalink, permalink, short_location


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
    return {"id": r["id"], "project": r["project"], "analyser": r["analyser"],
            "created_at": r["created_at"], "snapshot": r["snapshot_id"],
            "summary": _json(r["summary"]), "state": cases.state_of(conn, case_id),
            "versions": _json(r["artefact_versions"])}


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
            claim = _with_snippets(conn, claim)
            claim.update({"used_model": bool(detail.get("model") and detail.get("model") != "none"),
                          "detail": detail})
            claims.append(claim)
        out.append({"id": f["id"], "title": f["title"], "severity": f["severity"],
                    "fingerprint": f["fingerprint"], "claims": claims,
                    "suppressed": cases.suppressed(conn, f["fingerprint"]) is not None})
    return out


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
    snapshot = ctx["snapshot_id"]
    findings = conn.execute("SELECT COUNT(*) FROM finding WHERE case_id = ?",
                            (case_id,)).fetchone()[0]
    record = {"run_id": ctx["run_id"], "analyser": ctx["analyser"], "snapshot": snapshot,
              "finished_at": ctx["finished_at"], "findings": int(findings),
              # None = this store cannot support a count, which is not a count of zero.
              "claims": None, "features": None, "scenarios": None, "dormant": None,
              "feature_files": None, "patterns": None, "project_files": [],
              "registry_recorded": False, "assessment_recorded": False,
              "blind_spots": [], "assessment": None}
    if not snapshot:
        return record

    record["claims"] = int(conn.execute("SELECT COUNT(*) FROM claim WHERE run_id = ?",
                                       (ctx["run_id"],)).fetchone()[0])

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

    meta = _snapshot_meta(conn, ctx["run_id"])
    stored = meta.get("sources") if isinstance(meta, dict) else None
    record["registry_recorded"] = isinstance(stored, dict)
    if record["registry_recorded"]:
        assessment = sources.assessment_for(meta, ctx["analyser"])
        consulted = sources.consulted_for(meta, ctx["analyser"])
        record["assessment_recorded"] = assessment is not None or consulted is not None
        if assessment is not None:
            view = assessment.record()
            view["sentence"] = assessment.sentence()
            record["assessment"] = view
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
        record["blind_spots"] = spots
    return record


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
    suite = stepbindings.suite_of(prov["assertion_path"])
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
    uri, line = binding.get("uri"), binding.get("line")
    m = GITHUB.match(uri or "")
    path = m["path"] if m else (uri or "")
    if not isinstance(line, int) or line < 1:
        return {"state": SNIPPET_NOT_RECORDED, "path": path, "line": line,
                "link": binding.get("link")}
    snapshot = _claim_snapshot(conn, claim)
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
            "lines": [{"n": n, "text": window[n - line], "asserted": n == line}
                      for n in range(line, end + 1)],
            "link": binding.get("link")}


def _attach_snippets(conn, claim: dict) -> dict:
    """Attach the source excerpts after the evidence, which names the asserting binding."""
    claim["snippets"] = source_snippets(conn, claim)
    return claim



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
    """
    rows = cases.list_cases(conn, project, 200)
    seen: set[tuple[str, str]] = set()
    latest, older = [], 0
    for r in rows:
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
        latest.append(r)
    return latest, older


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
