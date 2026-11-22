"""Collect -> extract -> analyse -> persist. One run, one snapshot, one case."""
from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field

from . import blobs
from .analysers import duplication, level_fitness
from .surfaces import discover as surface_discovery
from .collectors import github, jira
from .config import Project, load_env
from .extract import csproj, gherkin, stepbindings
from . import cases, sources
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


RAISES = {"review", "gap", "duplicate"}


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
    if project.product.slug != project.test.slug:
        product = declared.use(sources.GITHUB,
                               lambda: github.collect(project.product, token, role="product"),
                               role="product")
    declared = declared.with_observed({sources.GITHUB: len(test_repo.files)
                                       + (len(product.files) if product else 0)})
    missing_sources = declared.missing(duplication.NEEDS | duplication.CONSULTS)
    assessment = declared.assess(duplication.NEEDS)

    snapshot_id = _new_snapshot_id(conn, f"{project.key}-{dt.date.today():%Y%m%d}-{test_repo.commit[:8]}")
    versions = {project.test.slug: test_repo.commit}
    if product:
        versions[project.product.slug] = product.commit
    # The registry is recorded with the snapshot, so a reader can reconstruct what this run could
    # and could not consult without probing anything. No "arms" here: a duplication snapshot is not
    # a level-fitness rebuild, and recording arms would invite one to be attempted.
    db.upsert_snapshot(conn, snapshot_id, project.key, _now(), versions,
                       schema_version=2,
                       meta={"sources_missing": missing_sources,
                             "sources": declared.record(),
                             "analysers": _analyser_record(duplication)})

    # 2. artefacts + observations
    texts = {}
    artefact_ids = {}
    for path, (sha, kind) in test_repo.files.items():
        uri = f"github:{project.test.slug}@{test_repo.commit}:{path}"
        artefact_ids[path] = db.add_artefact(conn, snapshot_id, uri, kind, sha)
        texts[path] = blobs.text(sha)

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

    driver_map = stepbindings.build_driver_map(texts)
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
            parsed = stepbindings.parse_file(path, text, driver_map)
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

    claims = duplication.analyse(features, bindings, uri_for_path,
                                 sources_missing=missing_sources, assessment=assessment,
                                 commit=test_repo.commit, support_index=support_index)

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
                            "cases": len(case_ids)})


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
    product = declared.use(sources.GITHUB,
                           lambda: github.collect(project.product, token, role="product"),
                           role="product")
    declared = declared.with_observed({sources.GITHUB: len(test_repo.files) + len(product.files)})
    missing_sources = declared.missing(level_fitness.NEEDS | level_fitness.CONSULTS)
    assessment = declared.assess(level_fitness.NEEDS)

    snapshot_id = _new_snapshot_id(
        conn, f"{project.key}-levels-{dt.date.today():%Y%m%d}-{test_repo.commit[:8]}")
    db.upsert_snapshot(conn, snapshot_id, project.key, _now(),
                       {project.test.slug: test_repo.commit, project.product.slug: product.commit},
                       schema_version=2,
                       # What a rebuild needs and an artefact cannot say. All of it is recorded now,
                       # so rebuilding from this snapshot alone cannot invent a clean bill of health
                       # and cannot invent a source state the run did not have.
                       meta={"sources_missing": missing_sources,
                             "arms": {"test": project.test.slug, "product": project.product.slug},
                             "sources": declared.record(),
                             "analysers": _analyser_record(level_fitness)})

    texts, product_texts = {}, {}
    artefact_ids: dict[str, int] = {}
    for path, (sha, kind) in sorted(test_repo.files.items()):
        texts[path] = blobs.text(sha)
        artefact_ids[path] = db.add_artefact(
            conn, snapshot_id, f"github:{project.test.slug}@{test_repo.commit}:{path}",
            kind, sha, {"role": "test"})
    for path, (sha, kind) in sorted(product.files.items()):
        product_texts[path] = blobs.text(sha)
        db.add_artefact(conn, snapshot_id,
                        f"github:{project.product.slug}@{product.commit}:{path}",
                        kind, sha, {"role": "product"})

    excludes: list[str] = []
    for path, text in texts.items():
        if test_repo.files[path][1] == "build":
            excludes.extend(csproj.excluded_patterns(text))

    driver_map = stepbindings.build_driver_map(texts)
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
            parsed = stepbindings.parse_file(path, text, driver_map)
            bindings.extend(parsed)
            for binding in parsed:
                observation = db.add_observation(
                    conn, artefact_ids[path], "stepbinding", "1.0.0",
                    f"binding:{binding.verb.lower()}:{binding.pattern}",
                    {"verb": binding.verb, "pattern": binding.pattern, "class": binding.cls,
                     "layer": binding.layer, "suite": binding.suite, "line": binding.line})
                support_index.setdefault((binding.path, binding.verb, binding.pattern),
                                         observation)

    surfaces = surface_discovery.discover(product_texts)

    def uri_for_path(path: str) -> str:
        return f"github:{project.test.slug}@{test_repo.commit}:{path}"

    budget = {"calls": 0, "tokens_in": 0, "tokens_out": 0}
    claims = level_fitness.analyse(features, bindings, surfaces, uri_for_path, budget,
                                   sources_missing=missing_sources,
                                   assessment=assessment,
                                   commit=test_repo.commit,
                                   support_index=support_index)

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
                 "high" if c.verdict in ("review", "gap") else "info"):
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
                            "cases": len(case_ids), "surfaces": len(surfaces), "budget": budget})

