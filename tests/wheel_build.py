"""Build one wheel per session from a copy of the source tree.

TESTOPS-48 AC4: the wheel is evidence, so it must be built once and shared. The copy keeps the
build away from the tests, the venv and git; ``--no-build-isolation`` uses the dev extras' backend
and ``--no-index`` is used at install time, so nothing here reaches the network.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 240  # seconds: a wheel build plus an install on a cold Windows disk


def python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def env(**extra: str) -> dict[str, str]:
    """The environment a child gets: no inherited repo path, no user site, no active venv."""
    clean = {key: value for key, value in os.environ.items()
             if key not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX")}
    clean["PYTHONNOUSERSITE"] = "1"
    clean.update(extra)
    return clean


def run(argv, cwd: Path, **extra: str) -> subprocess.CompletedProcess:
    done = subprocess.run([str(arg) for arg in argv], cwd=str(cwd), env=env(**extra),
                          text=True, capture_output=True, timeout=TIMEOUT)
    assert done.returncode == 0, (
        f"command failed: {' '.join(str(a) for a in argv)}\n{done.stdout}\n{done.stderr}")
    return done


def copy_source(work: Path) -> Path:
    """A copy of the source tree, so the build cannot see the tests, the venv or git."""
    source = work / "source"
    source.mkdir()
    shutil.copy(os.path.join(ROOT, "pyproject.toml"), source / "pyproject.toml")
    shutil.copytree(os.path.join(ROOT, "testops"), source / "testops",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return source


def build_wheel(source: Path, wheels: Path) -> Path:
    wheels.mkdir()
    run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
         "--wheel-dir", wheels, source], cwd=source.parent)
    built = sorted(wheels.glob("testops-*.whl"))
    assert len(built) == 1, f"expected one wheel, found {[p.name for p in built]}"
    return built[0]


def install(work: Path, wheel: Path) -> tuple[Path, Path]:
    venv = work / "venv"
    run([sys.executable, "-m", "venv", venv], cwd=work)
    python_exe = python(venv)
    assert python_exe.exists(), f"the fresh venv has no interpreter at {python_exe}"
    run([python_exe, "-m", "pip", "install", "--no-index", "--disable-pip-version-check", wheel],
        cwd=work)
    return venv, python_exe


def build_wheel_for_session(tmp_path_factory) -> dict:
    """Probe the backend, copy the tree and build one wheel for the whole session."""
    probe = subprocess.run([sys.executable, "-c", "import setuptools, wheel"],
                           capture_output=True, text=True)
    assert probe.returncode == 0, (
        "the distribution check needs the build backend: pip install -e '.[dev]'\n"
        f"{probe.stderr}")

    work = tmp_path_factory.mktemp("testops-wheel")
    source = copy_source(work)
    wheel = build_wheel(source, work / "wheels")
    return {"work": work, "source": source, "wheel": wheel}
