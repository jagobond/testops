"""Gherkin parser.

Deliberately small: features, tags, background, scenarios, outlines with examples, and steps with their
keywords. It keeps line numbers because evidence must be clickable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

STEP = re.compile(r"^\s*(Given|When|Then|And|But|\*)\s+(.*)$", re.I)
SCENARIO = re.compile(r"^\s*Scenario(?: Outline)?:\s*(.*)$", re.I)
EXAMPLE = re.compile(r"^\s*Examples?:\s*(.*)$", re.I)


@dataclass
class Step:
    keyword: str
    text: str
    line: int


@dataclass
class Scenario:
    name: str
    line: int
    tags: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    examples: list[dict[str, str]] = field(default_factory=list)
    background: bool = False

    @property
    def signature(self) -> str:
        """Normalised step sequence: what the scenario asserts, independent of formatting."""
        return " | ".join(normalise(s.text) for s in self.steps)


@dataclass
class Feature:
    name: str
    path: str
    tags: list[str] = field(default_factory=list)
    scenarios: list[Scenario] = field(default_factory=list)
    backgrounds: list[Scenario] = field(default_factory=list)


def normalise(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation. Two scenarios that differ only in style match."""
    t = text.strip().lower()
    t = re.sub(r"[\"'`]", "", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    # Parameterise data so "12 questions" and "3 questions" describe the same claim shape; duplicates that
    # differ only in test data are still duplicates.
    t = re.sub(r"\b\d+\b", "#", t)
    return re.sub(r"\s+", " ", t).strip()


def parse(path: str, text: str) -> Feature | None:
    # A UTF-8 BOM in front of "Feature:" made whole files parse as empty; three suites in the control repo
    # are BOM-prefixed.
    lines = text.lstrip("\ufeff").splitlines()
    feature: Feature | None = None
    tags: list[str] = []
    current: Scenario | None = None
    in_background = False
    in_examples = False
    headers: list[str] = []

    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("@"):
            tags.extend(t.strip() for t in stripped.split() if t.startswith("@"))
            continue
        if stripped.lower().startswith("feature:"):
            feature = Feature(name=stripped.split(":", 1)[1].strip(), path=path, tags=list(tags))
            tags.clear()
            current = None
            continue
        if stripped.lower().startswith("background:"):
            current = Scenario(name="background", line=i, tags=[], background=True)
            in_background = True
            in_examples = False
            if feature:
                feature.backgrounds.append(current)
            continue
        if stripped.lower().startswith("rule:"):
            continue          # rule blocks group scenarios; they hold no steps of their own
        m = SCENARIO.match(stripped)
        if m:
            current = Scenario(name=m.group(1).strip(), line=i, tags=list(tags))
            tags.clear()
            in_background = False
            in_examples = False
            if feature:
                feature.scenarios.append(current)
            continue
        if EXAMPLE.match(stripped):
            in_examples = True
            headers = []
            continue
        if in_examples and current is not None:
            if stripped.startswith("|"):
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                if not headers:
                    headers = cells
                else:
                    current.examples.append(dict(zip(headers, cells)))
            continue
        m = STEP.match(line)
        if m and current is not None:
            current.steps.append(Step(keyword=m.group(1), text=m.group(2).strip(), line=i))
            continue
        if stripped.startswith('"""') or stripped.startswith("|"):
            # doc strings and tables inside steps carry no extra weight for this analysis
            continue

    return feature if feature and feature.scenarios else feature
