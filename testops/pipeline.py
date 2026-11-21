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
from . import cases
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


def _missing_sources(project: Project) -> list[str]:
    """Sources this run never consulted, named rather than assumed clean.

    Jira and ADO are absent at Quilter by policy. A level-fitness run reads the test repository and
    the product repository only, so every claim records which requirement sources it could not
    check against. "Nothing was found" is never what a missing source means.
    """
    missing: list[str] = []
    if getattr(project, "jira_key", ""):
        missing.append("jira")
    if getattr(project, "ado_org", None):
        missing.append("ado")
    return missing


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


def run_duplication(project: Project, token: str) -> RunResult:
    env = load_env()
    conn = db.connect()

    # 1. collect
    test_repo = github.collect(project.test, token, role="test")
    product = None
    if project.product.slug != project.test.slug:
        product = github.collect(project.product, token, role="product")

    snapshot_id = f"{project.key}-{dt.date.today():%Y%m%d}-{test_repo.commit[:8]}"
    versions = {project.test.slug: test_repo.commit}
    if product:
        versions[project.product.slug] = product.commit
    db.upsert_snapshot(conn, snapshot_id, project.key, _now(), versions)

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
            bindings.extend(stepbindings.parse_file(path, text, driver_map))

    # 3. optional requirements
    jira_count = 0
    if project.jira_key:
        site = env.get("JIRA_SITE", "")
        issues = jira.collect(site, env["JIRA_EMAIL"], env["JIRA_API_TOKEN"], project.jira_key)
        for key, sha in issues.items():
            db.add_artefact(conn, snapshot_id, f"jira:{key}", "issue", sha,
                            jira.summary_of(sha))
        jira_count = len(issues)

    # 4. analyse
    def uri_for_path(path: str) -> str:
        return f"github:{project.test.slug}@{test_repo.commit}:{path}"

    claims = duplication.analyse(features, bindings, uri_for_path)

    # 5. persist
    run_id = f"{project.key}-dup-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}"
    db.start_run(conn, run_id, project.key, snapshot_id, duplication.name, _now())
    case_id = f"case-{run_id}"
    # The case row must exist before its findings: findings carry a foreign key to it.
    conn.execute(
        "INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary) VALUES (?,?,?,?,?,?,?)",
        (case_id, run_id, project.key, duplication.name, snapshot_id, _now(),
         db.j({"claims": len(claims), "features": len(features),
               "scenarios": sum(len(f.scenarios) for f in features),
               "dormant_features": len(dormant), "jira_issues": jira_count})),
    )
    emitted = 0
    for c in claims:
        cid = db.add_claim(conn, run_id, duplication.name, duplication.version, c.subject_ref,
                           c.statement, c.verdict, c.confidence, [])
        c.claim_id = cid
        emitted += _emit(conn, case_id, duplication.name, c)
    db.finish_run(conn, run_id, "ok", _now(), budget={"model_calls": 0})
    conn.commit()
    conn.close()

    return RunResult(run_id=run_id, snapshot_id=snapshot_id, case_id=case_id, claims=claims,
                     stats={"features": len(features), "bindings": len(bindings),
                            "scenarios": sum(len(f.scenarios) for f in features),
                            "dormant_features": len(dormant), "jira_issues": jira_count,
                            "excludes": excludes})


def run_level_fitness(project: Project, token: str) -> RunResult:
    """Collect both arms, discover the product's surfaces, judge each scenario's level."""
    env = load_env()
    conn = db.connect()
    test_repo = github.collect(project.test, token, role="test")
    product = github.collect(project.product, token, role="product")

    snapshot_id = f"{project.key}-levels-{dt.date.today():%Y%m%d}-{test_repo.commit[:8]}"
    db.upsert_snapshot(conn, snapshot_id, project.key, _now(),
                       {project.test.slug: test_repo.commit, project.product.slug: product.commit},
                       schema_version=2)

    texts, product_texts = {}, {}
    for path, (sha, kind) in test_repo.files.items():
        texts[path] = blobs.text(sha)
    for path, (sha, kind) in product.files.items():
        product_texts[path] = blobs.text(sha)
        db.add_artefact(conn, snapshot_id, f"github:{project.product.slug}@{product.commit}:{path}", kind, sha)

    excludes: list[str] = []
    for path, text in texts.items():
        if test_repo.files[path][1] == "build":
            excludes.extend(csproj.excluded_patterns(text))

    driver_map = stepbindings.build_driver_map(texts)
    features, bindings = [], []
    for path, text in sorted(texts.items()):
        kind = test_repo.files[path][1]
        if kind == "feature" and csproj.is_active(path, excludes):
            f = gherkin.parse(path, text)
            if f:
                features.append(f)
        elif kind == "stepdef":
            bindings.extend(stepbindings.parse_file(path, text, driver_map))

    surfaces = surface_discovery.discover(product_texts)

    def uri_for_path(path: str) -> str:
        return f"github:{project.test.slug}@{test_repo.commit}:{path}"

    budget = {"calls": 0, "tokens_in": 0, "tokens_out": 0}
    claims = level_fitness.analyse(features, bindings, surfaces, uri_for_path, budget,
                                   sources_missing=_missing_sources(project),
                                   commit=test_repo.commit)

    run_id = f"{project.key}-levels-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}"
    db.start_run(conn, run_id, project.key, snapshot_id, level_fitness.name, _now())

    # Every claim is written with the coordinates its reader needs to check it. The store refuses a
    # v2 row without them, so this loop cannot quietly fall back to a subject-only claim.
    for c in claims:
        cid = db.add_claim(conn, run_id, level_fitness.name, level_fitness.version, c.subject_ref,
                           c.statement, c.verdict, c.confidence, [],
                           schema_version=2,
                           assertion_text=c.detail["assertion_text"],
                           assertion_path=c.detail["assertion_path"],
                           assertion_line=c.detail["assertion_line"],
                           assertion_commit=c.detail["assertion_commit"],
                           interaction_label=c.detail["interaction_label"],
                           interaction_code=c.detail["interaction_code"],
                           span=c.detail["span"],
                           established_by=c.detail["established_by"],
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

