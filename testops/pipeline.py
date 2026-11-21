"""Collect -> extract -> analyse -> persist. One run, one snapshot, one case."""
from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass

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


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


RAISES = {"review", "gap", "duplicate"}


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
    fp = cases.fingerprint(analyser_name, claim.subject_ref,
                           claim.detail.get("claim") or claim.detail.get("signature") or claim.verdict)
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
                       {project.test.slug: test_repo.commit, project.product.slug: product.commit})

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
    claims = level_fitness.analyse(features, bindings, surfaces, uri_for_path, budget)

    run_id = f"{project.key}-levels-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}"
    db.start_run(conn, run_id, project.key, snapshot_id, level_fitness.name, _now())
    case_id = f"case-{run_id}"
    conn.execute(
        "INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary) VALUES (?,?,?,?,?,?,?)",
        (case_id, run_id, project.key, level_fitness.name, snapshot_id, _now(),
         db.j({"claims": len(claims), "surfaces": len(surfaces), "budget": budget, "emitted": 0})),
    )
    emitted = 0
    for c in claims:
        cid = db.add_claim(conn, run_id, level_fitness.name, level_fitness.version, c.subject_ref,
                           c.statement, c.verdict, c.confidence, [])
        c.claim_id = cid
        db.add_inference(conn, cid, c.detail.get("model", "none"), c.detail.get("model", "none"),
                         c.detail.get("prompt_hash", ""), [], c.detail,
                         c.detail.get("tokens", 0), 0)
        emitted += _emit(conn, case_id, level_fitness.name, c,
                         "high" if c.verdict in ("review", "gap") else "info")
    db.finish_run(conn, run_id, "ok", _now(), budget=budget)
    conn.commit()
    conn.close()
    return RunResult(run_id=run_id, snapshot_id=snapshot_id, case_id=case_id, claims=claims,
                     stats={"features": len(features), "scenarios": sum(len(f.scenarios) for f in features),
                            "surfaces": len(surfaces), "budget": budget})
