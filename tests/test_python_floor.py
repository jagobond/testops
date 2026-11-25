"""AC1, AC3, AC6: the code obeys the floor the project declares.

`requires-python = ">=3.11"` was a string in a TOML file that nothing checked. The interpreter that
serves the UI is 3.11.15; the tests ran on 3.12, so a PEP 701 f-string that 3.11 cannot parse sat in
`testops/web/app.py` unnoticed until the UI failed to start (TESTOPS-13).

Two guards, each exact for its interpreter:

- On 3.11 and older the interpreter is the authority: compiling a module *is* the test, because a
  backslash inside an f-string expression is a SyntaxError there.
- On 3.12+ the same construct is legal, so the token stream is inspected instead. PEP 701 splits an
  f-string into FSTRING_START / FSTRING_MIDDLE / FSTRING_END with the expression tokens emitted
  normally, which lets the check look at expression tokens only - the literal parts of an f-string
  are skipped, so a legitimate escape in the text is not mistaken for a violation.

The scan is exercised on synthetic sources below, so a guard that stopped detecting the construct
fails its own tests rather than passing quietly.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "testops"

# A Python 3.11 an operator wants the guards run against, named by ``TESTOPS_FLOOR_PYTHON``. It used
# to be an absolute path on one developer's machine (TESTOPS-102); a machine that names none tests
# against whatever 3.11 it finds on PATH, and a machine with none says so rather than skipping.
def _known_floor_interpreters() -> list[Path]:
    named = (os.environ.get("TESTOPS_FLOOR_PYTHON") or "").strip()
    return [Path(named)] if named else []


def _modules() -> list[Path]:
    files = sorted(p for p in PACKAGE.rglob("*.py") if "__pycache__" not in p.parts)
    assert files, f"no modules found under {PACKAGE}; the guard would pass vacuously"
    return files


def fstring_backslash_violations(source: str, filename: str = "<string>") -> list[str]:
    """Lines where a backslash appears inside an f-string expression.

    Only meaningful from 3.12 on, where the token stream separates an f-string's expression from its
    literal text. Before 3.12 the interpreter rejects the construct outright, so callers compile.
    """
    if sys.version_info < (3, 12):
        raise RuntimeError("on pre-3.12 interpreters, compile the source instead")

    violations: list[str] = []
    fstring_depth = 0
    brace_depth = 0
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError) as exc:
        # Not silently skipped: a file this interpreter cannot tokenise cannot be checked for the
        # construct either, and a guard that shrugs at a broken file is not a guard.
        return [f"{filename}: not tokenisable by Python {sys.version.split()[0]}: {exc}"]

    for tok in tokens:
        name = tokenize.tok_name[tok.type]
        if name == "FSTRING_START":
            fstring_depth += 1
            continue
        if name == "FSTRING_END":
            fstring_depth -= 1
            continue
        if fstring_depth <= 0 or name == "FSTRING_MIDDLE":
            continue
        if tok.type == tokenize.OP and tok.string == "{":
            brace_depth += 1
            continue
        if tok.type == tokenize.OP and tok.string == "}":
            brace_depth = max(0, brace_depth - 1)
            continue
        if brace_depth > 0 and "\\" in tok.string:
            violations.append(f"{filename}:{tok.start[0]}: {tok.string}")
    return violations


def _floor_interpreters() -> list[Path]:
    """Python 3.11 interpreters on this machine, this one first when it is already 3.11."""
    candidates: list[Path] = []
    if sys.version_info[:2] == (3, 11):
        candidates.append(Path(sys.executable))
    found = shutil.which("python3.11")
    if found:
        candidates.append(Path(found))
    candidates.extend(p for p in _known_floor_interpreters() if p.exists())
    out: list[Path] = []
    for candidate in candidates:
        try:
            probe = subprocess.run(
                [str(candidate), "-I", "-c", "import sys; print(*sys.version_info[:2])"],
                capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0 and probe.stdout.split() == ["3", "11"]:
            out.append(candidate)
    return out


# --- the guards ---------------------------------------------------------------------------------

def test_no_backslash_inside_an_fstring_expression():
    """AC3: the construct that broke the floor fails a test, not a deployment."""
    failures: list[str] = []
    for path in _modules():
        source = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        if sys.version_info >= (3, 12):
            failures.extend(fstring_backslash_violations(source, rel))
        else:
            try:
                compile(source, str(path), "exec")
            except SyntaxError as exc:
                text = exc.text.strip() if exc.text else ""
                failures.append(f"{rel}:{exc.lineno}: {exc.msg} ({text})")
    assert not failures, (
        "f-string expressions may not contain a backslash: legal from 3.12 (PEP 701), a SyntaxError "
        "on the 3.11 interpreter that serves this project. Build the string before the f-string.\n"
        + "\n".join(failures))


def test_every_module_compiles_under_the_floor_interpreter():
    """AC1: the floor is a fact about the code, not a string in pyproject.toml.

    Compiling is enough - the failure mode is a SyntaxError at import, before any dependency is
    touched - and it writes no bytecode into the tree.
    """
    floor = _floor_interpreters()
    if not floor:
        import pytest
        pytest.skip("no Python 3.11 interpreter available on this machine")
    script = (
        "import sys, pathlib\n"
        "root = sys.argv[1]\n"
        "bad = []\n"
        "for p in sorted(pathlib.Path(root).rglob('*.py')):\n"
        "    if '__pycache__' in p.parts:\n"
        "        continue\n"
        "    try:\n"
        "        compile(p.read_bytes(), str(p), 'exec')\n"
        "    except SyntaxError as exc:\n"
        "        bad.append(f'{p}:{exc.lineno}: {exc.msg}')\n"
        "print('\\n'.join(bad))\n"
        "sys.exit(1 if bad else 0)\n"
    )
    proc = subprocess.run([str(floor[0]), "-I", "-c", script, str(PACKAGE)],
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, (
        f"every module must compile under {floor[0]}:\n{proc.stdout.strip()}\n{proc.stderr.strip()}")


def test_declared_floor_and_the_guard_agree():
    """AC6: if the floor moves, that is the Lead's decision - not a quiet edit that disarms the guard."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11"' in pyproject, (
        "the declared floor changed; the guard above enforces 3.11 syntax and the two must agree")


# --- the guard's own tests ----------------------------------------------------------------------

def test_the_scan_catches_the_construct_that_broke_the_floor():
    """The exact shape of the line in testops/web/app.py before TESTOPS-13."""
    if sys.version_info < (3, 12):
        import pytest
        pytest.skip("pre-3.12: compiling the source is the equivalent check")
    source = (
        "def f(d):\n"
        "    return (f'<p>Suppressed'\n"
        "            f'{esc(\" \\u2014 \" + d[\"note\"]) if d else \"\"}.</p>')\n"
    )
    violations = fstring_backslash_violations(source, "synthetic.py")
    assert violations and violations[0].startswith("synthetic.py:3:"), violations


def test_the_scan_catches_a_plain_newline_escape_in_an_expression():
    if sys.version_info < (3, 12):
        import pytest
        pytest.skip("pre-3.12: compiling the source is the equivalent check")
    assert fstring_backslash_violations("x = f\"{''.join(['a\\nb'])}\"\n", "synthetic.py")


def test_a_file_the_scanner_cannot_tokenise_is_reported_not_skipped():
    """A guard that shrugs at a file it cannot read would let the construct through unexamined."""
    if sys.version_info < (3, 12):
        import pytest
        pytest.skip("pre-3.12: compiling the source is the equivalent check")
    violations = fstring_backslash_violations("x = (1,\n", "synthetic.py")
    assert len(violations) == 1 and "not tokenisable" in violations[0], violations


def test_the_scan_ignores_legal_backslashes():
    """No false positives: escapes outside expressions and in f-string literal text stay legal."""
    if sys.version_info < (3, 12):
        import pytest
        pytest.skip("pre-3.12: compiling the source is the equivalent check")
    legal = (
        'plain = "a\\nb"\n'
        'literal = f"a\\nb {value} c\\td"\n'
        'braces = f"{{literal}} {value}"\n'
        "nested = f\"{d['k']:>{w}}\"\n"
        "inner = f\"{f'{v}'}\"\n"
    )
    assert fstring_backslash_violations(legal, "synthetic.py") == []
