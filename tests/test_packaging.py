"""AC1 and AC2: pytest is a declared dev dependency; the package list names only real packages.

TESTOPS-8 AC5 lives here too: ``[tool.setuptools.package-data]`` must list every non-Python file the
app resolves at runtime, checked against the files that actually resolve rather than a hand-kept
list. The behavioural half of TESTOPS-8 - install the wheel and serve pages from it - is
``test_distribution.py``, which needs no network but does need a build backend.
"""
from __future__ import annotations

import importlib
import re
import tomllib
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
PACKAGE = ROOT / "testops"


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


# --------------------------------------------------------------------- TESTOPS-8 AC5

def _declared_data_patterns() -> list[str]:
    """Every glob ``package-data`` declares for the ``testops`` package, as the build reads it."""
    block = _pyproject()["tool"]["setuptools"]["package-data"]
    patterns = list(block.get("testops", []))
    # A pattern declared on a subpackage is relative to that subpackage's directory.
    for package, globs in block.items():
        if package != "testops":
            prefix = package.replace(".", "/").removeprefix("testops/")
            patterns.extend(f"{prefix}/{glob}" for glob in globs)
    return patterns


def _covered(rel: str, patterns: list[str]) -> bool:
    return any(PurePosixPath(rel).match(pattern) for pattern in patterns)


def _data_files_on_disk() -> list[str]:
    """Every non-Python file under the package, relative to it, in the form the build sees it."""
    return sorted(
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*")
        if path.is_file() and path.suffix != ".py" and "__pycache__" not in path.parts
    )


def test_package_data_lists_every_file_the_app_resolves_at_startup():
    """AC5: the declaration is checked against what resolves, not against a copy of itself.

    ``store/schema.sql`` is the file startup actually opens (``db.SCHEMA``), so it is resolved
    through the module rather than spelled out: rename or move it and this test follows it, while
    ``package-data`` has to follow too or the check fails.
    """
    from testops.store import db

    schema = db.SCHEMA
    assert schema.is_file(), f"the store's schema is not on disk at {schema}"

    # The startup path, expressed the way the build expresses it: relative to the package root.
    resolved = schema.resolve().relative_to(PACKAGE.resolve()).as_posix()
    patterns = _declared_data_patterns()
    assert _covered(resolved, patterns), (
        f"{resolved} is read at startup but package-data does not ship it: {patterns}")

    # The general rule the ticket asks for - a new template or static directory cannot be
    # forgotten, because every non-Python file in the package must be covered by a pattern.
    uncovered = [rel for rel in _data_files_on_disk() if not _covered(rel, patterns)]
    assert uncovered == [], (
        f"these files ship with the package only if package-data lists them: {uncovered}; "
        f"declared: {patterns}")
