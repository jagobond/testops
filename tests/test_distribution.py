"""TESTOPS-8: the package, installed, not the checkout beside it.

``test_packaging.py`` imports ``testops`` through ``sys.path``, so it proves the *tree* is complete.
A tree is not what Harry installs at work: a wheel is. If ``package-data`` omitted
``store/schema.sql``, every page of an installed copy would answer 500 while this suite stayed
green - the false confidence the ticket exists to remove.

So this module builds a wheel from a **copy** of the source tree, installs it into a freshly
created venv, and runs the app **only** through that venv's site-packages: no repo on ``sys.path``,
no editable install. The wheel is built with ``--no-build-isolation`` (the backend comes from the
dev extras) and installed with ``--no-index``, so the check touches no network.

Marked ``distribution``: it spends ~20 seconds proving a distribution, which is not the fast lane's
business (``pytest -m "not distribution"``). CI runs it - see ``tests/README.md``.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile

import pytest

pytestmark = pytest.mark.distribution

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMEOUT = 240  # seconds: a wheel build plus an install on a cold Windows disk


# --------------------------------------------------------------------------- plumbing


def _python(venv):
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _env(**extra):
    """The environment a child gets: no inherited repo path, no user site, no active venv."""
    clean = {key: value for key, value in os.environ.items()
             if key not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX")}
    clean["PYTHONNOUSERSITE"] = "1"
    clean.update(extra)
    return clean


def _run(argv, cwd, **extra):
    done = subprocess.run([str(arg) for arg in argv], cwd=str(cwd), env=_env(**extra),
                          text=True, capture_output=True, timeout=TIMEOUT)
    assert done.returncode == 0, (
        f"command failed: {' '.join(str(a) for a in argv)}\n{done.stdout}\n{done.stderr}")
    return done


def _copy_source(work):
    """A copy of the source tree, so the build cannot see the tests, the venv or git."""
    source = work / "source"
    source.mkdir()
    shutil.copy(os.path.join(ROOT, "pyproject.toml"), source / "pyproject.toml")
    shutil.copytree(os.path.join(ROOT, "testops"), source / "testops",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return source


def _build_wheel(source, wheels):
    wheels.mkdir()
    _run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
          "--wheel-dir", wheels, source], cwd=source.parent)
    built = sorted(wheels.glob("testops-*.whl"))
    assert len(built) == 1, f"expected one wheel, found {[p.name for p in built]}"
    return built[0]


def _install(work, wheel):
    venv = work / "venv"
    _run([sys.executable, "-m", "venv", venv], cwd=work)
    python = _python(venv)
    assert python.exists(), f"the fresh venv has no interpreter at {python}"
    _run([python, "-m", "pip", "install", "--no-index", "--disable-pip-version-check", wheel],
         cwd=work)
    return venv, python


@pytest.fixture(scope="module")
def distribution(tmp_path_factory):
    # --no-build-isolation means the wheel must be built by this interpreter's own backend, which
    # is what the dev extras install. Say so in one line if it is missing, rather than letting pip
    # fail with "No module named 'setuptools'" forty lines later.
    probe = subprocess.run([sys.executable, "-c", "import setuptools, wheel"],
                           capture_output=True, text=True)
    assert probe.returncode == 0, (
        "the distribution check needs the build backend: pip install -e '.[dev]'\n"
        f"{probe.stderr}")

    work = tmp_path_factory.mktemp("testops-distribution")
    source = _copy_source(work)
    wheel = _build_wheel(source, work / "wheels")
    venv, python = _install(work, wheel)
    return {"work": work, "wheel": wheel, "venv": venv, "python": python}


# --------------------------------------------------------------------------- AC1: the wheel


def test_the_wheel_carries_the_file_the_app_reads_at_startup(distribution):
    """AC1, first half: the artefact really contains what the app opens at startup."""
    with zipfile.ZipFile(distribution["wheel"]) as archive:
        names = set(archive.namelist())
    assert "testops/store/schema.sql" in names, (
        "schema.sql is read at startup but is not in the wheel: "
        f"{sorted(n for n in names if not n.endswith('.py'))}")


def test_the_import_comes_from_the_venv_not_from_the_checkout(distribution):
    """AC1: a fresh interpreter, ``-I`` (no repo path, no user site), says where it came from."""
    script = distribution["work"] / "where.py"
    script.write_text("import json, sys, testops\n"
                      "print(json.dumps([testops.__file__, sys.path]))\n", encoding="utf-8")
    done = _run([distribution["python"], "-I", script], cwd=distribution["work"])
    location, paths = json.loads(done.stdout)

    venv = str(distribution["venv"].resolve()).lower()
    repo = str(ROOT).replace("\\", "/").lower()
    assert "site-packages" in location.replace("\\", "/").lower(), (
        f"testops was imported from {location}")
    assert location.replace("\\", "/").lower().startswith(venv.replace("\\", "/")), (
        f"{location} is not inside the fresh venv")
    assert not any(str(path).replace("\\", "/").lower().startswith(repo) for path in paths if path), (
        f"the checkout is on the child's sys.path: {paths}")


# --------------------------------------------------------------------------- AC2: it serves


SERVE = '''
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import testops
from testops.store import db
from testops.web import app

TS = "2020-01-01T00:00:00+00:00"
SNAP, RUN, CASE, COMMIT = "snap-dist", "run-dist", "case-dist", "a" * 40
PATH = "features/panel_api.feature"

result = {"file": testops.__file__, "statuses": {}}

conn = db.connect()
db.upsert_snapshot(conn, SNAP, "fixture", TS, {"owner/test": COMMIT}, schema_version=2)
db.start_run(conn, RUN, "fixture", SNAP, "level_fitness", TS)
claim = db.add_claim(
    conn, RUN, "level_fitness", "0.8.0",
    "scenario:features/panel_api.feature#the panel is served",
    "This test asserts that the panel is served. Only a browser works that out, and this test "
    "only reads the responses the server sends instead, so nothing checks it.",
    "gap", 0.5, [], schema_version=2,
    assertion_text="each fact's citation is in an element reachable by an accessible name",
    assertion_path=PATH, assertion_line=17, assertion_commit=COMMIT,
    interaction_label="needs a browser", interaction_code="I4", span=["api"],
    established_by="asserts an accessibility property the browser computes",
    sources_missing=["jira", "ado"],
    proposed_action='Move the step "the panel is served" into a test that drives a browser.')
conn.execute(
    "INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
    " VALUES (?,?,?,?,?,?,?)",
    (CASE, RUN, "fixture", "level_fitness", SNAP, TS, "{}"))
conn.execute(
    "INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids) VALUES (?,?,?,?,?)",
    (CASE, "the panel is served"[:160], "high", "f" * 32, db.j([claim])))
conn.commit()
conn.close()

httpd = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = "http://127.0.0.1:" + str(httpd.server_address[1])
for path in ("/", "/runs", "/config", "/case/" + CASE):
    with urllib.request.urlopen(base + path, timeout=20) as response:
        body = response.read()
        result["statuses"][path] = [response.status, len(body)]
httpd.shutdown()
print(json.dumps(result))
'''


def test_the_installed_copy_serves_every_page_from_its_own_store(distribution):
    """AC2: a store created by the installed package, served by the installed package, all 200."""
    work = distribution["work"]
    script = work / "serve.py"
    script.write_text(SERVE, encoding="utf-8")
    data = work / "data"
    done = _run([distribution["python"], "-I", script], cwd=work, TESTOPS_DATA=str(data))

    report = json.loads(done.stdout)
    assert "site-packages" in report["file"].replace("\\", "/").lower(), (
        f"served from {report['file']}")

    statuses = report["statuses"]
    for page in ("/", "/runs", "/config", "/case/case-dist"):
        assert page in statuses, f"{page} was never requested: {sorted(statuses)}"
        status, length = statuses[page]
        assert status == 200, f"{page} answered {status} from the installed copy"
        assert length > 500, f"{page} answered {status} with {length} bytes"

    store = data / "testops.db"
    assert store.is_file(), f"the installed package created no store under {data}"
    assert store.stat().st_size > 0
