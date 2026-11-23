"""TESTOPS-9: the documented verdict vocabulary is the one the analysers emit.

Three places tell a reader what a claim's ``verdict`` can be: the store's column comment, the
``Claim`` dataclass docstring, and the field comment beside the field. Each is prose, so each can
drift from the code that writes the value - and did: the schema and the dataclass named
``optimal``, ``overbuilt`` and ``necessary`` long after the analysers stopped emitting them. A
reader who trusts the schema builds against verdicts that never appear, and a builder codes a
branch for ``overbuilt`` that can never fire.

This test reads the emitted names from the analysers themselves - the string literals they assign
to ``verdict`` - and compares each documented list to that set. It fails in both directions (AC2):

  * a documented name no analyser emits - the stale-vocabulary defect this ticket fixes;
  * an emitted name no place documents - a new verdict a reader would never learn about.

Equality is the check, not containment, because either one-way test passes a store that is wrong
in the other direction.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ANALYSERS = ROOT / "testops" / "analysers"
SCHEMA = ROOT / "testops" / "store" / "schema.sql"
BASE = ANALYSERS / "base.py"


def _literal(found: set[str], value: ast.expr, path: Path) -> None:
    """Record a verdict literal, and refuse a verdict that is not one.

    A name computed at runtime would be invisible to this scan, and a vocabulary a reader cannot
    find in the code is not a vocabulary. The refusal is deliberate: if a builder ever replaces a
    literal with an expression, this test says so instead of silently checking a smaller set.
    """
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        found.add(value.value)
        return
    raise AssertionError(
        f"{path.name}: a verdict is not a string literal ({ast.dump(value)}). Keep verdicts as "
        f"literals so the documented vocabulary can be checked against them.")


def emitted_verdicts() -> set[str]:
    """The verdict names the analysers write, read from their own source.

    A verdict reaches a claim in one of two shapes: ``verdict = "..."`` inside the analysis, or
    ``Claim(..., verdict="...")``. Both are string literals in the analyser package, so the AST
    finds them without importing a module or running a corpus - the set is what the code can emit,
    not what one fixture happened to exercise.
    """
    found: set[str] = set()
    for path in sorted(ANALYSERS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "verdict":
                        _literal(found, node.value, path)
            elif isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == "verdict":
                        # ``Claim(..., verdict=verdict)`` passes the local the assignment scan
                        # above already read; anything else must still be a literal.
                        if isinstance(keyword.value, ast.Name) and keyword.value.id == "verdict":
                            continue
                        _literal(found, keyword.value, path)
    return found


def _names(text: str) -> set[str]:
    return {part.strip() for part in text.split("|") if part.strip()}


def schema_verdicts() -> set[str]:
    """The verdicts the store's column comment documents."""
    text = SCHEMA.read_text(encoding="utf-8")
    match = re.search(r"^\s*verdict TEXT NOT NULL,\s*--\s*(.+)$", text, re.MULTILINE)
    assert match, "schema.sql no longer documents the verdict column"
    return _names(match.group(1))


def claim_docstring_verdicts() -> set[str]:
    """The verdicts the ``Claim`` dataclass docstring documents."""
    text = BASE.read_text(encoding="utf-8")
    match = re.search(r"^\s*Verdicts:\s*(.+)$", text, re.MULTILINE)
    assert match, "the Claim docstring no longer documents its verdicts"
    return _names(match.group(1))


def claim_field_verdicts() -> set[str]:
    """The verdicts the comment beside ``Claim.verdict`` documents."""
    text = BASE.read_text(encoding="utf-8")
    match = re.search(r"^\s*verdict: str\s*#\s*(.+)$", text, re.MULTILINE)
    assert match, "the Claim.verdict field no longer documents its verdicts"
    return _names(match.group(1))


PLACES = [
    ("schema.sql verdict column", schema_verdicts),
    ("Claim docstring", claim_docstring_verdicts),
    ("Claim.verdict field comment", claim_field_verdicts),
]


def disagreement(documented: set[str], emitted: set[str]) -> tuple[list[str], list[str]]:
    """Both directions of the comparison: (stale, undocumented)."""
    return sorted(documented - emitted), sorted(emitted - documented)


def test_the_analysers_emit_a_vocabulary_at_all():
    """A scan that finds nothing would make every comparison below vacuously true."""
    emitted = emitted_verdicts()
    assert emitted, (
        f"the verdict scan of {ANALYSERS} found no verdict literals - it walked no analyser "
        "modules, or they no longer assign verdicts as string literals - so the comparisons "
        "below would be vacuously true"
    )


@pytest.mark.parametrize("place, read", PLACES, ids=[place for place, _ in PLACES])
def test_documented_verdicts_are_exactly_the_emitted_ones(place, read):
    """AC1 and AC2: each documented list equals the set the analysers can write."""
    emitted = emitted_verdicts()
    documented = read()
    stale, undocumented = disagreement(documented, emitted)
    assert not stale, (
        f"{place} names verdicts no analyser emits: {stale}. "
        f"The analysers emit {sorted(emitted)}.")
    assert not undocumented, (
        f"{place} does not document verdicts the analysers emit: {undocumented}. "
        f"It documents {sorted(documented)}.")


def test_the_comparison_reports_both_directions():
    """AC2, mechanically: a stale name and a missing name are each reported, not swallowed."""
    stale, undocumented = disagreement({"distinct", "overbuilt"}, {"distinct", "gap"})
    assert stale == ["overbuilt"]
    assert undocumented == ["gap"]
