"""The real demo-service duplication corpus, as test data.

These are the 108 test-suite files - 18 feature files and 90 step-definition/driver/support files - that
the run ``demo-service-dup-20261120T153431`` analysed, read back from that run's stored snapshot
(``demo-service-20261120-78153818``, test arm ``reqnroll/demo-service@78153818``). They are here so
the suite measures the corpus the Product Owner opened, not a toy rewrite of it: the same 48 scenarios,
the same step bindings, the same 18 duplicate findings.

Nothing is fetched: the files are content the run already collected. The helper stores them in the
throwaway blob store of a test and hands the pipeline the same in-memory repository shape the other
pipeline tests use.

The corpus is somebody else's MIT-licensed code, not ours: `PROVENANCE.md` in the fixture directory
names the upstream repository, the commit and exactly what was copied and left out, and `LICENSE`
carries the upstream notice verbatim. Read those before changing anything here.
"""
from __future__ import annotations

from pathlib import Path

from testops import blobs
from testops.collectors.github import Collected

ROOT = Path(__file__).with_name("fixtures") / "demo-service"
COMMIT = "78153818b81d7c9a324af81b4e95f65aead705b4"
SUITE_COMMIT = COMMIT
REPO_SLUG = "reqnroll/demo-service"
# The copied test files are all `.cs` or `.feature`. The fixture directory also holds `LICENSE` and
# `PROVENANCE.md` for attribution; those are notices, not corpus, and must not reach the analyser.
CORPUS_SUFFIXES = (".cs", ".feature")


def texts() -> dict[str, str]:
    """Every corpus file, keyed by its repo-relative path with forward slashes."""
    return {path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(ROOT.rglob("*"))
            if path.is_file() and path.suffix in CORPUS_SUFFIXES}


def files() -> dict[str, tuple[str, str]]:
    """The corpus as ``github.collect`` would return it: path -> (blob sha, kind).

    Call after ``testops.blobs.BLOB_DIR`` has been pointed at a throwaway directory: the blobs are
    written there, and every render in the same test reads them back from the same place.
    """
    out: dict[str, tuple[str, str]] = {}
    for path, text in texts().items():
        kind = "feature" if path.endswith(".feature") else "stepdef"
        out[path] = (blobs.put(text.encode("utf-8")), kind)
    return out


def stub_pipeline(monkeypatch, pipeline, tmp_path):
    """Point the real ``run_duplication`` at the real corpus and a throwaway store.

    Returns ``(store_path, connect)`` where ``connect`` is the genuine ``db.connect``. The caller runs
    the pipeline, then reads back what it wrote - cases, claims, findings - from that store.
    """
    from testops.store import db

    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")
    path = tmp_path / "demo-service.db"
    real_connect = db.connect
    corpus = files()

    monkeypatch.setattr(pipeline, "load_env", lambda: {})
    monkeypatch.setattr(pipeline.db, "connect", lambda: real_connect(path))
    # The real blob store is already pointed at the throwaway directory, so `blobs.text` reads the
    # corpus back the way the product does. Do not patch it here: `pipeline.blobs` is the same module.
    monkeypatch.setattr(pipeline.github, "collect",
                        lambda repo, token, role="product": Collected(commit=COMMIT, files=corpus))
    monkeypatch.setattr(pipeline.surface_discovery, "discover",
                        lambda product_texts: pipeline.surface_discovery.Discovery((), "zero"))
    return path, real_connect
