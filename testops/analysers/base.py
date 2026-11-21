"""Analyser contract: a pure function of a snapshot.

An analyser never fetches, never mutates the store, and never needs a model unless it declares one. That
keeps the deterministic tier runnable in CI for free.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Evidence:
    """One cited artefact, with enough to build a permalink."""
    uri: str
    line: int | None = None
    note: str = ""


@dataclass
class Claim:
    subject_ref: str
    statement: str
    verdict: str                  # optimal | overbuilt | necessary | unplaced | duplicate
    confidence: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


class Analyser(Protocol):
    name: str
    version: str
    uses_model: bool

    def run(self, snapshot, ctx) -> list[Claim]: ...
