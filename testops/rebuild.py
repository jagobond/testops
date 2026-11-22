"""Rebuild a level-fitness claim set from one stored snapshot, and from nothing else.

This is the module behind "the store is the product's memory". A run is explainable only if its own
snapshot is sufficient to reproduce it: the test arm's features and step definitions, the product
arm's source the surfaces were read from, the sources the run knew it could not consult, and the
observation rows that back each claim. All of that is written by
:func:`testops.pipeline.run_level_fitness`; none of it needs the network, and none of it needs a
second snapshot taken at the same commit.

Two refusals are deliberate:

- A snapshot that does not say which repository is the test arm, or that does not record which
  sources were missing, cannot be rebuilt. The alternative is to guess a commit or to read "nothing
  was recorded" as "nothing was missing", and either would produce a claim set that looks like the
  original while saying something the original never said.
- A snapshot whose blobs are gone cannot be rebuilt. Text is never reconstructed from a path.

Support ids are read back from the snapshot's own observation rows, so a rebuilt claim carries the
same ids as the original. That is what makes the comparison an equality rather than a similarity.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import blobs, sources
from .analysers import level_fitness
from .extract import csproj, gherkin, stepbindings
from .links import GITHUB
from .surfaces import discover as surface_discovery


class SnapshotNotSelfContained(RuntimeError):
    """The snapshot cannot rebuild its own claims: something the run knew was never written down."""


@dataclass
class Snapshot:
    id: str
    project: str
    created_at: str
    test_slug: str
    product_slug: str
    test_commit: str
    product_commit: str
    sources_missing: list[str] | None
    # The registry's verdict for this analyser's needed capabilities, rebuilt from the snapshot's
    # own record. ``None`` means the snapshot predates the registry, not "nothing was missing" -
    # and it stays ``None`` in the rebuilt claims too: a rebuild that turned "no registry was
    # recorded" into "nothing was missing" would print a clean bill the original run never gave.
    assessment: sources.Assessment | None = None
    test_files: dict[str, tuple[str, str]] = field(default_factory=dict)  # path -> (blob_sha, kind)
    product_texts: dict[str, str] = field(default_factory=dict)           # path -> text
    support_index: dict[tuple[str, str, str], int] = field(default_factory=dict)


def _json(text, what: str):
    try:
        return json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise SnapshotNotSelfContained(f"snapshot {what} is not readable JSON: {text!r}") from exc


def _slug(match) -> str:
    return f"{match['owner']}/{match['repo']}"


def _text(sha: str, path: str, snapshot_id: str) -> str:
    try:
        return blobs.text(sha)
    except FileNotFoundError as exc:
        raise SnapshotNotSelfContained(
            f"snapshot {snapshot_id}: the stored blob for {path} is missing from the blob store, "
            "so the file cannot be rebuilt without the network. That is a broken snapshot, not an "
            "empty file.") from exc


def load(conn, snapshot_id: str) -> Snapshot:
    """Everything a level-fitness rebuild needs, read from this snapshot alone."""
    row = conn.execute("SELECT * FROM snapshot WHERE id = ?", (snapshot_id,)).fetchone()
    if row is None:
        raise SnapshotNotSelfContained(f"no such snapshot: {snapshot_id}")

    versions = _json(row["artefact_versions"], "artefact_versions")
    meta = _json(row["meta"], "meta")
    arms = meta.get("arms") or {}
    test_slug, product_slug = arms.get("test"), arms.get("product")
    if not (test_slug and product_slug):
        raise SnapshotNotSelfContained(
            f"snapshot {snapshot_id} does not record which repository is the test arm and which "
            "the product arm, so a rebuild could only guess. It predates TESTOPS-14; re-run the "
            "levels analysis to take a snapshot that knows.")
    if "sources_missing" not in meta:
        raise SnapshotNotSelfContained(
            f"snapshot {snapshot_id} does not record which sources the run could not consult. "
            "Rebuilding it would print a clean bill of health the original run never gave.")
    if ("sources" in meta) != ("analysers" in meta):
        raise SnapshotNotSelfContained(
            f"snapshot {snapshot_id} records half of the source registry: a rebuild could see the "
            "declared sources but not what the analyser needed, or the reverse, and would have to "
            "guess the assessment the original run made.")

    test_commit, product_commit = versions.get(test_slug), versions.get(product_slug)
    if not (test_commit and product_commit):
        raise SnapshotNotSelfContained(
            f"snapshot {snapshot_id} does not pin both arms: versions are {versions!r}")

    assessment = sources.assessment_for(meta, level_fitness.name)
    snap = Snapshot(id=snapshot_id, project=row["project"], created_at=row["created_at"],
                    test_slug=test_slug, product_slug=product_slug,
                    test_commit=test_commit, product_commit=product_commit,
                    # A snapshot that recorded the registry was assessed; its stored list is what the
                    # assessment said. A snapshot without one recorded only a list, and carrying that
                    # list forward would be carrying an answer nobody recorded a question for.
                    sources_missing=(list(meta["sources_missing"]) if assessment is not None else None),
                    assessment=assessment)

    stepdef_artefacts: list[tuple[int, str]] = []
    for art in conn.execute("SELECT id, uri, kind, blob_sha FROM artefact WHERE snapshot_id = ?"
                            " ORDER BY id", (snapshot_id,)):
        match = GITHUB.match(art["uri"] or "")
        if not match:
            continue                       # jira:/ado: rows carry no file text
        path, slug, commit = match["path"], _slug(match), match["sha"]
        if not art["blob_sha"]:
            raise SnapshotNotSelfContained(
                f"snapshot {snapshot_id} records {path} with no blob; a rebuild would guess the "
                "file's contents")
        if slug == test_slug and commit == test_commit:
            snap.test_files[path] = (art["blob_sha"], art["kind"])
            if art["kind"] == "stepdef":
                stepdef_artefacts.append((art["id"], path))
        elif slug == product_slug:
            snap.product_texts[path] = _text(art["blob_sha"], path, snapshot_id)

    if not any(kind == "feature" for _sha, kind in snap.test_files.values()):
        raise SnapshotNotSelfContained(
            f"snapshot {snapshot_id} records no feature file for the test arm "
            f"({test_slug}@{test_commit}), so there is nothing to rebuild the claim set from")

    for artefact_id, path in stepdef_artefacts:
        for obs in conn.execute(
                "SELECT id, value FROM observation WHERE artefact_id = ?"
                " AND extractor = 'stepbinding' ORDER BY id", (artefact_id,)):
            value = _json(obs["value"], f"observation {obs['id']}")
            verb, pattern = value.get("verb"), value.get("pattern")
            if verb and pattern:
                snap.support_index.setdefault((path, verb, pattern), obs["id"])
    return snap


def rebuild(conn, snapshot_id: str) -> tuple[list, dict, Snapshot]:
    """Reproduce a levels run's claims from its snapshot. Returns (claims, stats, snapshot)."""
    snap = load(conn, snapshot_id)

    texts = {path: _text(sha, path, snapshot_id) for path, (sha, _kind) in snap.test_files.items()}
    kinds = {path: kind for path, (_sha, kind) in snap.test_files.items()}

    excludes: list[str] = []
    for path, text in texts.items():
        if kinds[path] == "build":
            excludes.extend(csproj.excluded_patterns(text))

    driver_map = stepbindings.build_driver_map(texts)
    features, bindings = [], []
    for path, text in sorted(texts.items()):
        if kinds[path] == "feature":
            if not csproj.is_active(path, excludes):
                continue
            feature = gherkin.parse(path, text)
            if feature:
                features.append(feature)
        elif kinds[path] == "stepdef":
            bindings.extend(stepbindings.parse_file(path, text, driver_map))

    discovery = surface_discovery.discover(snap.product_texts)
    claims = level_fitness.analyse(
        features, bindings, list(discovery.surfaces),
        lambda path: f"github:{snap.test_slug}@{snap.test_commit}:{path}",
        {"calls": 0, "tokens_in": 0, "tokens_out": 0},
        sources_missing=snap.sources_missing, assessment=snap.assessment,
        commit=snap.test_commit, support_index=snap.support_index,
    )
    stats = {"features": len(features), "bindings": len(bindings),
             "scenarios": sum(len(f.scenarios) for f in features),
             "surfaces": len(discovery.surfaces), "surfaces_state": discovery.state}
    return claims, stats, snap
