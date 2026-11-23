"""AC1 and AC2: pytest is a declared dev dependency; the package list names only real packages.

TESTOPS-8 AC5 lives here too: ``[tool.setuptools.package-data]`` must ship every non-Python file in
the package, checked against the built wheel's namelist rather than against a glob. The behavioural
half of TESTOPS-8 - install the wheel and serve pages from it - is ``test_distribution.py``, which
needs no network but does need a build backend.
"""
from __future__ import annotations

import importlib
import re
import tomllib
import zipfile
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


def _patterns_matching(rel: str, patterns: list[str]) -> list[str]:
    """Only a suggestion for the error message; the wheel decides coverage, never this."""
    return [pattern for pattern in patterns if PurePosixPath(rel).match(pattern)]


def _data_files_on_disk() -> list[str]:
    """Every non-Python file under the package, relative to it, in the form the build sees it."""
    return sorted(
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*")
        if path.is_file() and path.suffix != ".py" and "__pycache__" not in path.parts
    )


def _wheel_names(built_wheel: dict) -> set[str]:
    with zipfile.ZipFile(built_wheel["wheel"]) as archive:
        return set(archive.namelist())


# TESTOPS-49: today the package ships exactly these two non-Python files. A minimum count and a
# name list, not an equality, so a third file needs no edit here - but a deleted or renamed one
# fails, which is the difference between "everything checked" and "nothing to check".
MIN_DATA_FILES = 2
KNOWN_DATA_FILES = (
    "judgement/prompts/level_fitness.md",
    "store/schema.sql",
)


def _assert_enumeration_is_real(files: list[str]) -> None:
    """TESTOPS-49 AC1 and AC3: no coverage verdict is drawn from a walk that found nothing.

    An empty enumeration (missing package directory, wrong ``PACKAGE``, a monkeypatched
    ``_data_files_on_disk``) used to make the test below pass with zero files checked. That is a
    pass about nothing, so this refuses it first and names the directory it walked.
    """
    assert files, (
        f"the package-data walk of {PACKAGE} found no non-Python files at all. That is a broken "
        "probe - a missing or wrong package directory - not a statement that packaging is "
        "complete, so no wheel-coverage verdict is drawn from it."
    )
    assert len(files) >= MIN_DATA_FILES, (
        f"the walk of {PACKAGE} found only {len(files)} non-Python file(s) ({files}); the "
        f"package ships at least {MIN_DATA_FILES}, so files have gone missing from the tree, not "
        "from the wheel."
    )
    absent = [name for name in KNOWN_DATA_FILES if name not in files]
    assert not absent, (
        f"the walk of {PACKAGE} no longer finds {absent}, which the package ships today. It "
        f"found {files}. Renaming or deleting a shipped data file needs a deliberate edit to "
        "KNOWN_DATA_FILES, not a silently smaller coverage check."
    )


def test_package_data_ships_every_non_python_file_in_the_package(built_wheel):
    """AC1: the built wheel, not a glob, decides whether package-data is complete.

    ``package-data`` patterns are relative to the package root. ``PurePosixPath.match``
    right-anchors, so ``templates/probe.html`` matches ``web/templates/probe.html`` even though
    the build would ship nothing. The wheel's namelist cannot be fooled that way, so it is the
    authority; the matching patterns are shown only to point at the glob to fix.

    TESTOPS-49: the enumeration is checked before it is trusted. Zero files found means the probe
    is broken, and that is a failure here, never a pass.
    """
    files = _data_files_on_disk()
    _assert_enumeration_is_real(files)

    names = _wheel_names(built_wheel)
    patterns = _declared_data_patterns()

    missing = []
    for rel in files:
        expected = f"testops/{rel}"
        if expected not in names:
            missing.append((rel, expected, _patterns_matching(rel, patterns)))

    assert missing == [], (
        "the built wheel is missing non-Python files that are in the package tree; "
        "package-data patterns are relative to the package root, and the wheel is the authority:\n"
        + "\n".join(
            f"  {rel}: expected in wheel as {expected}; "
            f"declared patterns matching this file: {matches or 'none'}"
            for rel, expected, matches in missing)
        + f"\n  all declared patterns: {patterns}"
    )
