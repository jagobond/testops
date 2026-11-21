"""AC1 and AC2: pytest is a declared dev dependency; the package list names only real packages."""
from __future__ import annotations

import importlib
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def _pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _requirement_name(spec: str) -> str:
    """'pytest>=8' -> 'pytest'."""
    return re.split(r"[<>=!~;\[ ]", spec.strip(), maxsplit=1)[0].lower()


def test_pytest_is_a_declared_dev_dependency_with_a_documented_command():
    dev = _pyproject()["project"]["optional-dependencies"]["dev"]
    assert "pytest" in {_requirement_name(spec) for spec in dev}, f"dev extras are {dev}"

    readme = (ROOT / "tests" / "README.md").read_text(encoding="utf-8")
    assert 'pip install -e ".[dev]"' in readme

    # The declared dependency is genuinely installed in this interpreter.
    assert importlib.import_module("pytest").__name__ == "pytest"


def test_every_declared_package_exists_on_disk():
    packages = _pyproject()["tool"]["setuptools"]["packages"]
    missing = [name for name in packages
               if not (ROOT / name.replace(".", "/")).is_dir()]
    assert missing == [], f"pyproject declares packages that do not exist: {missing}"

    # Existing on disk is not enough: each declared name must be importable as a package.
    # (testops.store and testops.surfaces are implicit namespace packages and have no
    # __init__.py, so a directory check alone is the correct existence test.)
    for name in packages:
        importlib.import_module(name)


def test_web_and_scripts_are_declared_and_the_cases_module_is_not():
    packages = _pyproject()["tool"]["setuptools"]["packages"]
    assert "testops.cases" not in packages, "testops.cases is a module, not a package"
    assert not (ROOT / "testops" / "cases" / "__init__.py").exists()
    assert "testops.web" in packages, "the web UI would be missing from an editable install"
    assert "testops.scripts" in packages

    # The point of the fix: both import as packages from the tree.
    importlib.import_module("testops.web")
    importlib.import_module("testops.scripts")