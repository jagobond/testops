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
    """One thing an analyser asserts about a snapshot.

    ``verdict`` is one of the names the analysers emit, and nothing else. A reader builds against
    this word, so a name here that no analyser writes is a branch that can never fire:

    Verdicts: distinct | gap | review | unplaced | duplicate | repeats_product

    ``tests/test_verdict_vocabulary.py`` reads the emitted names from the analysers' own literals
    and fails if this list, the field comment below, or the store's column comment names a verdict
    no analyser emits - or misses one it does.
    """
    subject_ref: str
    statement: str
    verdict: str                  # distinct | gap | review | unplaced | duplicate | repeats_product
    confidence: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


class Analyser(Protocol):
    """What every registered analyser declares, beside its verdicts and actions.

    ``COVER`` is the sentence the case page shows beside the decision, and it is the *declaring*
    analyser's sentence - a duplication case shows the duplication contract, a level-fitness case
    the level-fitness one (TESTOPS-47). There is deliberately no default anywhere: a module that
    fails to declare ``COVER`` raises when the page asks for it, rather than inheriting another
    analyser's wording, which is exactly the bug a single global sentence caused.
    """
    name: str
    version: str
    uses_model: bool
    COVER: str

    def run(self, snapshot, ctx) -> list[Claim]: ...
