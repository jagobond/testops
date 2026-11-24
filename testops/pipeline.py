"""Collect -> extract -> analyse -> persist. One run, one snapshot, one case."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field

from . import blobs
from .analysers import duplication, level_fitness
from .surfaces import discover as surface_discovery
from .collectors import github, jira
from .config import Project, load_env
from .extract import csproj, gherkin
from .extract import ecosystems
from . import cases, config, services, sources
from .store import db


@dataclass
class RunResult:
    run_id: str
    snapshot_id: str
    case_id: str
    claims: list
    stats: dict
    # One case per actionable claim (TESTOPS-4). ``case_id`` keeps the first for callers that want
    # a single handle; an analyser whose run raises nothing actionable has no case at all.
    case_ids: list[str] = field(default_factory=list)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


RAISES = {"review", "gap", "duplicate", "repeats_product"}


def _fingerprint(analyser_name: str, claim) -> str:
    """Identity of the evidence behind a claim - never of its verdict.

    ``evidence_key`` is the analyser's own name for the assertion (for a level claim: the
    interaction plus the assertion's words), so two claims from one scenario no longer collide in
    one case. Analysers that predate the field fall back to their coarser key.
    """
    return cases.fingerprint(analyser_name, claim.subject_ref,
                             claim.detail.get("evidence_key")
                             or claim.detail.get("claim")
                             or claim.detail.get("signature")
                             or claim.verdict)


def _declared(project: Project, registry: sources.Registry | None) -> sources.Registry:
    """The sources this run may consult: the caller's registry, or the deployment's declaration.

    A caller may hand in a registry (a test, or a future deployment with different policy). The
    pipeline never consults a source that is not in it, and never names a source itself.
    """
    return sources.registry(project) if registry is None else registry


def _analyser_record(analyser) -> dict:
    """What the analyser needed, stored beside the registry so a read can rebuild its assessment.

    The capabilities live here rather than in the claim because they are a property of the analysis,
    not of one assertion. A reader reconstructing a snapshot gets the same answer the run got, with
    no live source and no knowledge of today's analyser code.
    """
    return {analyser.name: {"needs": sorted(analyser.NEEDS),
                            "consults": sorted(analyser.CONSULTS)}}


def _ecosystem_record(role: str, slug: str, texts: dict[str, str]) -> tuple[dict, object | None]:
    """Which ecosystem one repository arm was read as, and the module that reads it (AC2).

    ``unknown`` is a recorded fact, not a fallback: it means no marker this build knows was found
    in the files the run actually read. A repository recognised as two ecosystems is also recorded
    as unknown, with the reason, because naming one of them would be a guess.
    """
    try:
        module, ecosystem = ecosystems.registry().match(texts)
    except (ecosystems.UnknownEcosystem, ecosystems.AmbiguousEcosystem) as exc:
        return ({"role": role, "repository": slug, "ecosystem": "unknown",
                 "evidence": [], "reason": str(exc)}, None)
    return ({"role": role, "repository": slug, **ecosystem.record()}, module)


def _ecosystem_records(project: Project,
                       texts_by_role: dict[str, dict[str, str]]) -> tuple[dict, object | None]:
    """The ecosystem record per repository arm, and the module the test arm's analysis uses.

    The test arm decides the analysis: an ecosystem this build cannot read stops it (AC4). The
    product arm is recorded because the question is per repository, but its ecosystem never stops a
    run - a product is not a suite, and "its files are not step definitions" is not a fault.
    """
    records: dict = {}
    module: object | None = None
    for role, texts in texts_by_role.items():
        repo = project.product if role == "product" else project.test
        record, found = _ecosystem_record(role, repo.slug if repo is not None else "", texts)
        records[role] = record
        if role == "test":
            module = found
    return records, module


def _unsupported(records: dict) -> sources.BlindSpot | None:
    """The ecosystem blind spot this run's record carries, or ``None`` when it can be analysed."""
    spot = ecosystems.unsupported_spot(records)
    if spot is None:
        return None
    return sources.BlindSpot(spot["source"], spot["title"], spot["state"], spot["reason"])


def _assessable(assessment: sources.Assessment, records: dict) -> sources.Assessment:
    """Not assessable when the suite's ecosystem is detected and this build cannot read it.

    The sources were available and were read - the readings travel unchanged, because they are
    true - and the reason no claim can be made about the steps is named beside them. This is the
    difference between "we looked and there was nothing" and "we cannot look", applied to a
    vocabulary rather than a source.
    """
    spot = _unsupported(records)
    if spot is None:
        return assessment
    return sources.Assessment(assessment.capabilities, sources.NOT_ASSESSABLE,
                              observed=assessment.observed,
                              blind_spots=assessment.blind_spots + (spot,),
                              readings=assessment.readings)


def _bindings_by_path(module, texts: dict[str, str]) -> dict[str, list]:
    """The module's bindings, grouped by the file they were declared in.

    Grouped rather than flattened because the run stores one observation per binding against its
    own artefact, in the order the files are read - the same order the pre-seam pipeline used, so
    a run's observation ids do not move because of a refactor.
    """
    out: dict[str, list] = {}
    if module is None:
        return out
    for binding in module.bindings(texts):
        out.setdefault(binding.path, []).append(binding)
    return out


def _ecosystem_hooks(module) -> tuple[str, object | None, object | None]:
    """The optional placement hooks a module exposes: (extractor, unmatched, suite_of).

    A module that can place claims per step says so by exposing ``explain_unmatched``; the .NET
    module does not, so it keeps the old behaviour exactly (TESTOPS-42C-3, AC7). ``suite_of`` is
    the module's own suite rule where one exists - cucumber-js co-locates a suite in a directory,
    so the .NET top-level-segment rule would pair every JS feature with every step definition.
    """
    if module is None or not hasattr(module, "explain_unmatched"):
        return "", None, None
    return (module.name, module.explain_unmatched, getattr(module, "suite_of_path", None))


def _unreadable(module, texts: dict[str, str]) -> list[dict]:
    """The declarations a module recorded but could not read, as the run page prints them (AC9)."""
    reader = getattr(module, "unreadable", None)
    return list(reader(texts)) if callable(reader) else []


def _placement(claims: list, module, texts: dict[str, str]) -> dict | None:
    """What a run placed, what it did not, and why - a record a page can read months later.

    Only a module that places per step contributes one (AC3). Every number is counted from the
    run's own claims: a claim whose detail names the binding it rests on was placed; an unplaced
    claim carries the ecosystem's own explanation, which is aggregated here by the nearest patterns
    it named.
    """
    extractor, _unmatched, _suite = _ecosystem_hooks(module)
    if not extractor:
        return None
    placed = [claim for claim in claims if claim.detail.get("placed") is not False]
    layers: dict[str, int] = {}
    for claim in placed:
        layer = (claim.detail.get("provenance") or {}).get("binding", {}).get("layer")
        if layer:
            layers[layer] = layers.get(layer, 0) + 1
    unplaced = [claim for claim in claims if claim.detail.get("placed") is False]
    nearly: list[str] = []
    for claim in unplaced:
        for pattern in (claim.detail.get("unbound") or {}).get("nearly") or ():
            if pattern not in nearly:
                nearly.append(pattern)
    return {
        "extractor": extractor,
        "asserting": len(claims),
        "placed": len(placed),
        "unplaced": len(unplaced),
        "layers": dict(sorted(layers.items())),
        "unplaced_reason": ("no binding matches these words" if unplaced else ""),
        "nearly": nearly,
        "unreadable": _unreadable(module, texts),
    }


def _record_placement(conn, snapshot_id: str, placement: dict) -> None:
    """Add the placement facts to a snapshot's meta after the claims that produce them exist.

    The snapshot is written before analysis so its id can key the artefacts; this updates only the
    ``placement`` key, so a page can still state what was placed when it reads the store months
    later. ``INSERT OR REPLACE`` is not reused here: recreating the snapshot row could orphan the
    artefacts keyed by its id.
    """
    row = conn.execute("SELECT meta FROM snapshot WHERE id = ?", (snapshot_id,)).fetchone()
    if row is None:
        return
    try:
        meta = json.loads(row["meta"] or "{}")
    except (TypeError, ValueError):
        return
    meta["placement"] = placement
    conn.execute("UPDATE snapshot SET meta = ? WHERE id = ?", (json.dumps(meta), snapshot_id))


def _service_meta(project: Project, conn) -> dict:
    """The services the project resolved, and their states, written into this run's snapshot (AC4).

    A project assembled by a test, or by an older caller, has no services; it records nothing and
    the page is exactly the page it was. A project resolved from the store records one entry per
    service, so the page can name the service that was not connected and why - including the
    service the project does not declare at all.
    """
    states = [dict(state) for state in getattr(project, "service_states", ()) or ()]
    if not states:
        return {}
    services.record_consultation(conn, project.key, states)
    out: dict = {"service_states": states}
    if getattr(project, "assessment_state", ""):
        out["project_assessment"] = {"state": project.assessment_state,
                                     "reason": project.assessment_reason}
    return out


def _skip_reason(capability: str, arms: list[tuple[str, github.Collected]]) -> str:
    """Why a capability could not be read, in the words a page will print (TESTOPS-41).

    The count and the kind come from the collector's own record; the repository is named because
    "the product code was not read" is only checkable if a reader can tell which repository held it.
    """
    title = sources.CAPABILITY_TITLE[capability]
    skipped = [entry for _role, collected in arms for entry in collected.skipped
               if entry.reason != github.IGNORE]
    if not skipped:
        return (f"no file the collector reads as {title} was fetched, and the tree recorded nothing "
                f"that fell outside its kinds")
    biggest = sorted(skipped, key=lambda entry: (-entry.count, entry.kind))[0]
    kind = biggest.kind
    if biggest.reason == github.UNSUPPORTED:
        why = f"{kind} is not a kind this collector reads ({biggest.reason})"
    elif biggest.reason == github.SIZE_CAP:
        why = (f"they are over the {config.MAX_FILE_BYTES // 1024} KB size cap ({biggest.reason})")
    else:
        why = f"readers ignored them by pattern ({biggest.reason})"
    noun = "file" if biggest.count == 1 else "files"
    where = ", ".join(sorted({f"the {role} repository" for role, _c in arms}))
    others = len(skipped) - 1
    also = (f", along with {sum(entry.count for entry in skipped if entry is not biggest)} more "
            f"in {others} other kind{'s' if others != 1 else ''}") if others else ""
    lead = "no product code file was fetched" if capability == sources.CODE else \
        "no test code file was fetched"
    return (f"{biggest.count} {kind} {noun} in {where} were skipped because {why}{also}, so {lead}")


def _readings(arms: list[tuple[str, github.Collected]]) -> dict[str, list[sources.Reading]]:
    """What one source (GitHub) read and could not read, per capability, for this run.

    TESTOPS-41. The counts come from the collector's own kind table, so a file fetched as one kind
    can never be counted for another. An arm with no fetched file for a capability, in a run that
    read that arm, is not a zero: it is a capability this reader could not read, and it carries the
    reason and the skipped kinds that explain it.
    """
    readings: list[sources.Reading] = []
    for capability in (sources.CODE, sources.TEST_CODE):
        serving = [(role, collected) for role, collected in arms
                   if config.arm_capability(role) == capability]
        # A file counts toward the capability its *kind* serves, whichever arm fetched it: the
        # product repository's `.js` assets are step definitions to this collector, so they are
        # counted as test code and appear in that count rather than vanishing between the two.
        per_arm = {role: collected.counts.get(capability, 0) for role, collected in arms}
        observed = sum(per_arm.values())
        if not serving and not observed:
            continue                       # this run had no arm for it; not a result about it
        skipped = tuple(entry.record() for role, collected in serving
                        for entry in collected.skipped)
        # TESTOPS-43. A file this reader handles, refused for its size, is a file the capability
        # lost - the count it reports is partial, and the sentence says so. A file of a kind no
        # reader here handles is not this capability's loss: the run never claimed to read that
        # kind, and the page lists it under "Files this run could not read" with its reason.
        # Folding the two together would make every README in a .NET repository a caveat on a
        # complete reading, which is the noise the sentence exists to avoid.
        lost = tuple(entry.record() for role, collected in serving
                     for entry in collected.skipped if entry.reason == github.SIZE_CAP)
        # A capability with nothing fetched is only *unreadable* when the tree held files that fell
        # outside the kinds. An arm that fetched nothing and skipped nothing is a real zero: the
        # reader looked and the repository had nothing for it.
        unread = [entry for _role, collected in serving for entry in collected.unread]
        readings.append(sources.Reading(
            capability,
            observed=observed,
            unreadable="" if observed or not unread else _skip_reason(capability, serving),
            arms={role: count for role, count in per_arm.items() if count},
            skipped=skipped,
            lost=lost,
        ))
    return {sources.GITHUB: readings}


def _counts(arms: list[tuple[str, github.Collected]]) -> dict[str, int]:
    """Files fetched per capability, summed over the arms - the run's own reading of the tree."""
    out: dict[str, int] = {}
    for _role, collected in arms:
        for capability, count in collected.counts.items():
            out[capability] = out.get(capability, 0) + count
    return dict(sorted(out.items()))


def _skips(arms: list[tuple[str, github.Collected]]) -> list[dict]:
    """Per kind, how many files this run refused and why - counts and reasons, not paths."""
    return [{"reason": entry.reason, "kind": entry.kind, "count": entry.count}
            for _role, collected in arms for entry in collected.skipped]


def _new_snapshot_id(conn, base: str) -> str:
    """A snapshot id no stored snapshot already holds.

    Two runs over the same commits on the same day are two looks, not an update of the first. The
    old id scheme was ``project-date-commit`` and a second run of the day replaced the row - and then
    added its own artefacts to what the first run's claims point at. A collision bumps a suffix; the
    earlier snapshot and everything under it are left exactly as they were.
    """
    taken = {row[0] for row in conn.execute(
        "SELECT id FROM snapshot WHERE id = ? OR id LIKE ?", (base, base + "-r%"))}
    if base not in taken:
        return base
    number = 2
    while f"{base}-r{number}" in taken:
        number += 1
    return f"{base}-r{number}"


def _emit(conn, case_id: str, analyser_name: str, claim, severity: str = "medium") -> bool:
    """Insert a finding unless a human has already judged this evidence.

    The fingerprint covers the evidence, not the conclusion: analyser, subject, and the shape of the assertion.
    A later run that reaches a different verdict about the same subject is still the same case, and a person who
    has already ruled on it should not be asked again.
    """
    # Only a finding that asks something of a person becomes a case. Distinct claims are recorded as claims -
    # evidence, not noise. A case that lists 42 clean scenarios is a report, and nobody reads reports daily.
    if claim.verdict not in RAISES:
        return False
    fp = _fingerprint(analyser_name, claim)
    if cases.suppressed(conn, fp):
        return False
    conn.execute(
        "INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids) VALUES (?,?,?,?,?)",
        (case_id, claim.statement[:160], severity, fp, db.j([claim.claim_id] if hasattr(claim, "claim_id") else [])),
    )
    return True


def run_duplication(project: Project, token: str,
                    registry: sources.Registry | None = None) -> RunResult:
    env = load_env()
    conn = db.connect()
    declared = _declared(project, registry)

    # 1. collect. A source declared available that fails here stops the run (SourceFailed); a source
    # declared blocked is refused before it is touched (SourceNotAvailable). Neither becomes "absent".
    test_repo = declared.use(sources.GITHUB,
                             lambda: github.collect(project.test, token, role="test"), role="test")
    product = None
    if project.product is not None and project.product.slug != project.test.slug:
        product = declared.use(sources.GITHUB,
                               lambda: github.collect(project.product, token, role="product"),
                               role="product")
    arms = [("test", test_repo)] + ([("product", product)] if product else [])
    declared = declared.with_readings(_readings(arms))
    missing_sources = declared.missing(duplication.NEEDS | duplication.CONSULTS)
    assessment = declared.assess(duplication.NEEDS)
    if project.product is None and "product" not in missing_sources:
        # AC7: the project has tests and no product repository. That is not a zero and not a
        # failure - it is "cannot assess", with the reason travelling beside it.
        missing_sources = list(missing_sources) + ["product"]
        assessment = sources.Assessment(
            (sources.CODE, sources.TEST_CODE), sources.NOT_ASSESSABLE,
            blind_spots=(sources.BlindSpot(
                "product", "Product repository", sources.ABSENT,
                "this project has no product git repository configured"),))

    snapshot_id = _new_snapshot_id(conn, f"{project.key}-{dt.date.today():%Y%m%d}-{test_repo.commit[:8]}")
    versions = {project.test.slug: test_repo.commit}
    if product:
        versions[project.product.slug] = product.commit

    # Read the text before the snapshot is written: which ecosystem each repository was read as is
    # part of the snapshot's own record (AC2), and whether the test arm's is one this build can read
    # decides whether there is an analysis to record at all (AC4).
    texts = {path: blobs.text(sha) for path, (sha, _kind) in test_repo.files.items()}
    product_texts = ({path: blobs.text(sha) for path, (sha, _kind) in product.files.items()}
                     if product else {})
    ecosystems_record, module = _ecosystem_records(
        project, {"test": texts, **({"product": product_texts} if product else {})})
    assessment = _assessable(assessment, ecosystems_record)
    readable = _unsupported(ecosystems_record) is None

    # The registry is recorded with the snapshot, so a reader can reconstruct what this run could
    # and could not consult without probing anything. No "arms" here: a duplication snapshot is not
    # a level-fitness rebuild, and recording arms would invite one to be attempted.
    db.upsert_snapshot(conn, snapshot_id, project.key, _now(), versions,
                       schema_version=2,
                       meta={"sources_missing": missing_sources,
                             "sources": declared.record(),
                             "reads": {role: collected.record() for role, collected in arms},
                             "ecosystems": ecosystems_record,
                             "analysers": _analyser_record(duplication),
                             **_service_meta(project, conn)})

    # 2. artefacts + observations
    artefact_ids = {}
    for path, (sha, kind) in test_repo.files.items():
        uri = f"github:{project.test.slug}@{test_repo.commit}:{path}"
        artefact_ids[path] = db.add_artefact(conn, snapshot_id, uri, kind, sha)

    if product:
        for path, (sha, kind) in product.files.items():
            uri = f"github:{project.product.slug}@{product.commit}:{path}"
            db.add_artefact(conn, snapshot_id, uri, kind, sha)

    # A .feature on disk is not a test: the build removes unbound files on purpose. Read the project file
    # first, or the analyser reports on 141 scenarios when 43 actually run.
    excludes: list[str] = []
    for path, text in texts.items():
        if test_repo.files[path][1] == "build":
            excludes.extend(csproj.excluded_patterns(text))

    parsed_by_path = _bindings_by_path(module, texts) if readable else {}
    features, bindings, dormant = [], [], []
    # (binding path, verb, pattern) -> observation id. The analyser never sees the store; it is given
    # the row ids by key so a duplication claim can carry the evidence its reader needs inline.
    support_index: dict[tuple[str, str, str], int] = {}
    for path, text in sorted(texts.items()):
        kind = test_repo.files[path][1]
        if kind == "feature":
            if not csproj.is_active(path, excludes):
                dormant.append(path)
                continue
            f = gherkin.parse(path, text)
            if f:
                features.append(f)
                for sc in f.scenarios:
                    db.add_observation(conn, artefact_ids[path], "gherkin", "1.0.0", f"scenario:{sc.name}",
                                       {"line": sc.line, "steps": len(sc.steps), "signature": sc.signature})
        elif kind == "stepdef":
            parsed = parsed_by_path.get(path, [])
            bindings.extend(parsed)
            for binding in parsed:
                observation = db.add_observation(
                    conn, artefact_ids[path], "stepbinding", "1.0.0",
                    f"binding:{binding.verb.lower()}:{binding.pattern}",
                    {"verb": binding.verb, "pattern": binding.pattern, "class": binding.cls,
                     "layer": binding.layer, "suite": binding.suite, "line": binding.line})
                support_index.setdefault((binding.path, binding.verb, binding.pattern),
                                         observation)

    # 3. optional requirements. Jira is declared blocked wherever a project names it, so in the
    # Quilter deployment this branch is never taken and jira_count stays None - "not consulted",
    # which is not zero issues. If a later deployment declares Jira available, this is the seam that
    # uses it; a failure there stops the run like any other available source.
    jira_count = None
    jira_kind = declared.get(sources.JIRA)
    if jira_kind is not None and jira_kind.state.available:
        site = env.get("JIRA_SITE", "")
        issues = declared.use(
            sources.JIRA,
            lambda: jira.collect(site, env["JIRA_EMAIL"], env["JIRA_API_TOKEN"], project.jira_key))
        for key, sha in issues.items():
            db.add_artefact(conn, snapshot_id, f"jira:{key}", "issue", sha,
                            jira.summary_of(sha))
        jira_count = len(issues)

    # 4. analyse
    def uri_for_path(path: str) -> str:
        return f"github:{project.test.slug}@{test_repo.commit}:{path}"

    claims: list = []
    if readable:
        extractor, _unmatched, suite_of = _ecosystem_hooks(module)
        claims = duplication.analyse(features, bindings, uri_for_path,
                                     sources_missing=missing_sources, assessment=assessment,
                                     commit=test_repo.commit, support_index=support_index,
                                     suite_of=suite_of, extractor=extractor)
    # A declaration this build recorded but could not read is visible on the run, and nothing is
    # claimed for it (AC9). The rest of the suite was analysed above.
    unreadable = _unreadable(module, texts) if readable else []
    if unreadable:
        meta = json.loads(conn.execute("SELECT meta FROM snapshot WHERE id = ?",
                                       (snapshot_id,)).fetchone()["meta"] or "{}")
        meta["unreadable_declarations"] = unreadable
        conn.execute("UPDATE snapshot SET meta = ? WHERE id = ?", (json.dumps(meta), snapshot_id))

    # 5. persist
    run_id = f"{project.key}-dup-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}"
    db.start_run(conn, run_id, project.key, snapshot_id, duplication.name, _now())

    # Every duplication claim is written with the coordinates its reader needs to check it. The store
    # refuses a v2 row without them, so this loop cannot quietly fall back to a subject-only claim -
    # which is exactly how the eighteen reqoverflow findings came to say nothing (TESTOPS-21).
    for c in claims:
        cid = db.add_claim(conn, run_id, duplication.name, duplication.version, c.subject_ref,
                           c.statement, c.verdict, c.confidence, c.detail.get("support", []),
                           schema_version=2,
                           assertion_text=c.detail["assertion_text"],
                           assertion_path=c.detail["assertion_path"],
                           assertion_line=c.detail["assertion_line"],
                           assertion_commit=c.detail["assertion_commit"],
                           interaction_label=c.detail["interaction_label"],
                           span=c.detail["span"],
                           established_by=c.detail["established_by"],
                           sources_assessed=c.detail["sources_assessed"],
                           sources_missing=c.detail["sources_missing"],
                           proposed_action=c.detail["proposed_action"])
        c.claim_id = cid

    # One case per claim, one finding each. A single case for the whole run meant one decision would
    # silence every duplicate in it, which is the defect TESTOPS-4 fixed for level fitness and this
    # analyser never received. A claim a human has already ruled on raises nothing at all.
    actionable = [c for c in claims if c.verdict in RAISES]
    case_ids: list[str] = []
    for number, c in enumerate(actionable, start=1):
        fp = _fingerprint(duplication.name, c)
        if cases.suppressed(conn, fp):
            continue
        case_id = f"case-{run_id}-{number:02d}"
        conn.execute(
            "INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
            " VALUES (?,?,?,?,?,?,?)",
            (case_id, run_id, project.key, duplication.name, snapshot_id, _now(),
             db.j({"verdict": c.verdict, "assertion_line": c.detail.get("assertion_line"),
                   "claims": len(claims), "actionable": len(actionable),
                   "features": len(features),
                   "scenarios": sum(len(f.scenarios) for f in features),
                   "dormant_features": len(dormant), "jira_issues": jira_count})),
        )
        if _emit(conn, case_id, duplication.name, c):
            case_ids.append(case_id)
        else:
            conn.execute("DELETE FROM case_ WHERE id = ?", (case_id,))
    db.finish_run(conn, run_id, "ok", _now(), budget={"model_calls": 0})
    conn.commit()
    conn.close()

    return RunResult(run_id=run_id, snapshot_id=snapshot_id,
                     case_id=(case_ids[0] if case_ids else ""), claims=claims,
                     case_ids=case_ids,
                     stats={"features": len(features), "bindings": len(bindings),
                            "scenarios": sum(len(f.scenarios) for f in features),
                            "dormant_features": len(dormant), "jira_issues": jira_count,
                            "excludes": excludes, "claims": len(claims),
                            "cases": len(case_ids),
                            "ecosystems": ecosystems_record,
                            "read": _counts(arms), "skipped": _skips(arms)})


def run_level_fitness(project: Project, token: str,
                      registry: sources.Registry | None = None) -> RunResult:
    """Collect both arms, record both as artefacts, and judge each scenario's level.

    A levels run is the run that has to be able to rebuild itself. The test arm's features and step
    definitions are what every claim is *about*, so they are recorded here as artefacts of this
    snapshot - not borrowed from a duplication snapshot taken at the same commit. The scenario and
    step-binding observations are recorded too, and each claim carries the ids of the binding rows
    its verdict rests on, so a case page has something to show at the claim's coordinates.

    The source registry is consulted, not assumed: it says which sources this run may use, which it
    could not, and why. Both the registry and the capabilities the analyser needed are written into
    the snapshot, so a reader can reconstruct the assessment without probing anything.
    """
    conn = db.connect()
    declared = _declared(project, registry)
    test_repo = declared.use(sources.GITHUB,
                             lambda: github.collect(project.test, token, role="test"), role="test")
    product = None
    if project.product is not None:
        product = declared.use(sources.GITHUB,
                               lambda: github.collect(project.product, token, role="product"),
                               role="product")
    arms = [("test", test_repo)] + ([("product", product)] if product else [])
    declared = declared.with_readings(_readings(arms))
    missing_sources = declared.missing(level_fitness.NEEDS | level_fitness.CONSULTS)
    assessment = declared.assess(level_fitness.NEEDS)
    if project.product is None and "product" not in missing_sources:
        # AC7. A test repository with no product repository is `not_assessable` with a reason: the
        # run has something to read and nothing to judge it against, and saying "zero" would be a
        # claim nobody made.
        missing_sources = list(missing_sources) + ["product"]
        assessment = sources.Assessment(
            (sources.CODE, sources.TEST_CODE), sources.NOT_ASSESSABLE,
            blind_spots=(sources.BlindSpot(
                "product", "Product repository", sources.ABSENT,
                "this project has no product git repository configured"),))

    snapshot_id = _new_snapshot_id(
        conn, f"{project.key}-levels-{dt.date.today():%Y%m%d}-{test_repo.commit[:8]}")

    # The product's text is read here, before the snapshot is written, because what the surface
    # reader could make of it is part of the snapshot's record (TESTOPS-41): a run that found no
    # surface because it cannot read the language must say that, and a run page read months later
    # has no blob of its own to ask.
    if product is None:
        product_texts: dict[str, str] = {}
        discovery = surface_discovery.Discovery(
            (), surface_discovery.NOT_ASSESSABLE,
            reason="this project has no product git repository, so there was no product to read")
    else:
        product_texts = {path: blobs.text(sha) for path, (sha, _kind) in sorted(product.files.items())}
        discovery = surface_discovery.discover(product_texts)
    surfaces = list(discovery.surfaces)

    # Which ecosystem each repository was read as (AC2). The test arm's answer decides whether the
    # analyser has a vocabulary to read the suite with at all (AC4): a detected ecosystem this build
    # does not support makes every claim unmakeable, and saying so is not the same as saying the
    # suite has a problem.
    texts = {path: blobs.text(sha) for path, (sha, _kind) in sorted(test_repo.files.items())}
    ecosystems_record, module = _ecosystem_records(
        project, {"test": texts, **({"product": product_texts} if product is not None else {})})
    assessment = _assessable(assessment, ecosystems_record)
    readable = _unsupported(ecosystems_record) is None

    versions = {project.test.slug: test_repo.commit}
    if product is not None and project.product is not None:
        versions[project.product.slug] = product.commit
    db.upsert_snapshot(conn, snapshot_id, project.key, _now(), versions,
                       schema_version=2,
                       # What a rebuild needs and an artefact cannot say. All of it is recorded now,
                       # so rebuilding from this snapshot alone cannot invent a clean bill of health
                       # and cannot invent a source state the run did not have.
                       meta={"sources_missing": missing_sources,
                             # TESTOPS-74 AC4: the noun these counts are counted in. Written, not
                             # derived at render time, so an old snapshot keeps the sentence it had.
                             "count_unit": sources.COUNT_UNIT_FILES,
                             "arms": {"test": project.test.slug,
                                      **({"product": project.product.slug}
                                         if project.product is not None else {})},
                             "sources": declared.record(),
                             "reads": {role: collected.record() for role, collected in arms},
                             "ecosystems": ecosystems_record,
                             "surfaces": discovery.record(),
                             "analysers": _analyser_record(level_fitness),
                             **_service_meta(project, conn)})

    artefact_ids: dict[str, int] = {}
    for path, (sha, kind) in sorted(test_repo.files.items()):
        artefact_ids[path] = db.add_artefact(
            conn, snapshot_id, f"github:{project.test.slug}@{test_repo.commit}:{path}",
            kind, sha, {"role": "test"})
    for path, (sha, kind) in (sorted(product.files.items()) if product is not None else []):
        db.add_artefact(conn, snapshot_id,
                        f"github:{project.product.slug}@{product.commit}:{path}",
                        kind, sha, {"role": "product"})

    excludes: list[str] = []
    for path, text in texts.items():
        if test_repo.files[path][1] == "build":
            excludes.extend(csproj.excluded_patterns(text))

    parsed_by_path = _bindings_by_path(module, texts) if readable else {}
    features, bindings = [], []
    # (binding path, verb, pattern) -> observation id. The analyser never sees the store; it is
    # given the row ids by key so a claim can say which rows it rests on.
    support_index: dict[tuple[str, str, str], int] = {}
    for path, text in sorted(texts.items()):
        kind = test_repo.files[path][1]
        if kind == "feature" and csproj.is_active(path, excludes):
            f = gherkin.parse(path, text)
            if f:
                features.append(f)
                for sc in f.scenarios:
                    db.add_observation(conn, artefact_ids[path], "gherkin", "1.0.0",
                                       f"scenario:{sc.name}",
                                       {"line": sc.line, "steps": len(sc.steps),
                                        "signature": sc.signature})
        elif kind == "stepdef":
            parsed = parsed_by_path.get(path, [])
            bindings.extend(parsed)
            for binding in parsed:
                observation = db.add_observation(
                    conn, artefact_ids[path], "stepbinding", "1.0.0",
                    f"binding:{binding.verb.lower()}:{binding.pattern}",
                    {"verb": binding.verb, "pattern": binding.pattern, "class": binding.cls,
                     "layer": binding.layer, "suite": binding.suite, "line": binding.line})
                support_index.setdefault((binding.path, binding.verb, binding.pattern),
                                         observation)

    def uri_for_path(path: str) -> str:
        return f"github:{project.test.slug}@{test_repo.commit}:{path}"

    budget = {"calls": 0, "tokens_in": 0, "tokens_out": 0}
    claims: list = []
    extractor, unmatched, _suite_of = _ecosystem_hooks(module)
    if readable:
        claims = level_fitness.analyse(features, bindings, surfaces, uri_for_path, budget,
                                       sources_missing=missing_sources,
                                       assessment=assessment,
                                       commit=test_repo.commit,
                                       support_index=support_index,
                                       extractor=extractor, unmatched=unmatched,
                                       # What the surface reader made of the product arm, so a
                                       # browser claim can be judged against it - or say that it
                                       # could not be (TESTOPS-72). The state and its reason travel
                                       # together: a run that found no surface and a run that could
                                       # not read the product are different facts.
                                       product_state=discovery.state,
                                       product_reason=discovery.reason)

    # What this run placed, what it did not, and why - recorded with the snapshot so the run page
    # can still say it months later (AC3), and so an unreadable declaration is visible rather than
    # fatal (AC9). A .NET run has no placement record and its page is unchanged.
    placement = _placement(claims, module, texts) if readable else None
    if placement is not None:
        _record_placement(conn, snapshot_id, placement)

    run_id = f"{project.key}-levels-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}"
    db.start_run(conn, run_id, project.key, snapshot_id, level_fitness.name, _now())

    # Every claim is written with the coordinates its reader needs to check it. The store refuses a
    # v2 row without them, so this loop cannot quietly fall back to a subject-only claim.
    for c in claims:
        cid = db.add_claim(conn, run_id, level_fitness.name, level_fitness.version, c.subject_ref,
                           c.statement, c.verdict, c.confidence, c.detail.get("support", []),
                           schema_version=2,
                           assertion_text=c.detail["assertion_text"],
                           assertion_path=c.detail["assertion_path"],
                           assertion_line=c.detail["assertion_line"],
                           assertion_commit=c.detail["assertion_commit"],
                           interaction_label=c.detail["interaction_label"],
                           interaction_code=c.detail["interaction_code"],
                           span=c.detail["span"],
                           established_by=c.detail["established_by"],
                           sources_assessed=c.detail["sources_assessed"],
                           sources_missing=c.detail["sources_missing"],
                           proposed_action=c.detail["proposed_action"])
        c.claim_id = cid
        db.add_inference(conn, cid, c.detail.get("model", "none"), c.detail.get("model", "none"),
                         c.detail.get("prompt_hash", ""), [], c.detail,
                         c.detail.get("tokens", 0), 0)

    # One case per actionable claim, one finding each. Grouping two claims into one case is how a
    # single decision used to silence both, so a case never holds more than one finding here. A
    # claim a human has already ruled on raises nothing at all - not even an empty case.
    actionable = [c for c in claims if c.verdict in RAISES]
    case_ids: list[str] = []
    for number, c in enumerate(actionable, start=1):
        fp = _fingerprint(level_fitness.name, c)
        if cases.suppressed(conn, fp):
            continue
        case_id = f"case-{run_id}-{number:02d}"
        conn.execute(
            "INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
            " VALUES (?,?,?,?,?,?,?)",
            (case_id, run_id, project.key, level_fitness.name, snapshot_id, _now(),
             db.j({"claim": c.detail.get("claim"), "verdict": c.verdict,
                   "assertion_line": c.detail.get("assertion_line"),
                   "claims": len(claims), "actionable": len(actionable),
                   "surfaces": len(surfaces), "budget": budget})),
        )
        if _emit(conn, case_id, level_fitness.name, c,
                 "high" if c.verdict in ("review", "gap")
                 else ("medium" if c.verdict == "repeats_product" else "info")):
            case_ids.append(case_id)
        else:
            conn.execute("DELETE FROM case_ WHERE id = ?", (case_id,))
    db.finish_run(conn, run_id, "ok", _now(), budget=budget)
    conn.commit()
    conn.close()
    return RunResult(run_id=run_id, snapshot_id=snapshot_id, case_id=(case_ids[0] if case_ids else ""),
                     claims=claims, case_ids=case_ids,
                     stats={"features": len(features), "scenarios": sum(len(f.scenarios) for f in features),
                            "claims": len(claims), "actionable": len(actionable),
                            "cases": len(case_ids), "surfaces": len(surfaces),
                            # A count of 0 is not the answer on its own: "found none" and "could
                            # not look" are different runs (AC3), so the state and the reason travel
                            # beside the count.
                            "surfaces_state": discovery.state,
                            "surfaces_reason": discovery.reason,
                            # Two counts that are not each other (TESTOPS-72, AC6): claims the
                            # product's own routes show are repeats of work already done, and
                            # claims that needed the product and could not be judged against it.
                            "repeats_product": sum(1 for c in claims
                                                   if c.verdict == "repeats_product"),
                            "product_not_consulted": sum(
                                1 for c in claims
                                if (c.detail.get("product") or {}).get("state") == "not_assessable"),
                            # Claims the product rule looked at and declined (TESTOPS-78). Counted
                            # here so the run's own record says the rule looked, not only the page.
                            "product_near_miss": sum(
                                1 for c in claims
                                if (c.detail.get("product") or {}).get("near_miss")),
                            "ecosystems": ecosystems_record,
                            "placement": placement,
                            "read": _counts(arms), "skipped": _skips(arms), "budget": budget})

