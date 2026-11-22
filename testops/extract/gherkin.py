"""Gherkin parser.

Deliberately small: features, tags, background, scenarios, outlines with examples, and steps with their
keywords and the data they carry (tables and doc strings). It keeps line numbers because evidence must
be clickable.
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
    # The data the step carries. It is part of what the step asserts: two steps with the same words
    # and different rows are different assertions (TESTOPS-31).
    table: list[list[str]] = field(default_factory=list)
    doc_string: list[str] = field(default_factory=list)

    @property
    def data(self) -> str:
        """The step's table or doc string, rendered on one line for a reader."""
        if self.table:
            return render_table(self.table)
        if self.doc_string:
            return " ".join(line.strip() for line in self.doc_string if line.strip())
        return ""

    @property
    def assertion_text(self) -> str:
        """The step's words with its data, so the claim states something a reader can check.

        A step that says "the suggestions list should be" and stops is not an assertion - the
        meaning was in the table underneath it. The table is rendered after the words rather than
        kept as a shape only the analyser understands, and a step with no data is unchanged.
        """
        data = self.data
        if not data:
            return self.text
        separator = "" if self.text.rstrip().endswith(":") else ":"
        return f"{self.text.rstrip()}{separator} {data}"

    @property
    def signature_part(self) -> str:
        """This step's contribution to a scenario signature, data included."""
        parts = [normalise(self.text)]
        if self.table:
            parts.append("[table] " + " / ".join(
                ", ".join(normalise(cell) for cell in row) for row in self.table))
        if self.doc_string:
            parts.append("[doc] " + normalise("\n".join(self.doc_string)))
        return " ".join(parts)



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
        """Normalised step sequence with its data: what the scenario asserts, not how it is formatted.

        Examples are the outline's test data, so they belong to the signature for the same reason a
        step's table does: two outlines with different rows run different tests.
        """
        parts = [s.signature_part for s in self.steps]
        if self.examples:
            parts.append("[examples] " + " / ".join(
                ", ".join(f"{normalise(name)}={normalise(value)}" for name, value in row.items())
                for row in self.examples))
        return " | ".join(parts)


@dataclass
class Feature:
    name: str
    path: str
    tags: list[str] = field(default_factory=list)
    scenarios: list[Scenario] = field(default_factory=list)
    backgrounds: list[Scenario] = field(default_factory=list)


def normalise(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation. Two scenarios that differ only in style match.

    Digits are kept. Parameterising them made "12 questions" and "3 questions" one signature, which
    told a reader those were the same claim when they are different test data (TESTOPS-31). A
    scenario's data now tells the scenarios apart; only wording and formatting are normalised.
    """
    t = text.strip().lower()
    t = re.sub(r"[\"'`]", "", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def render_table(rows: list[list[str]]) -> str:
    """A step's data table as one reader-facing line.

    A table is a header row and its data rows, which is what Gherkin means by a data table; a table
    with one row is just that row. One column reads as its values ("What is Reqnroll?, Question 2");
    several columns keep their names ("title: What is Reqnroll?; body: Body 1") so a reader can tell
    which value is which. A ragged table falls back to every row, cells separated by commas - no cell
    is ever dropped.
    """
    if not rows:
        return ""
    if len(rows) == 1:
        return ", ".join(rows[0])
    header, body = rows[0], rows[1:]
    if all(len(row) == len(header) for row in body):
        columns = []
        for index, name in enumerate(header):
            values = ", ".join(row[index] for row in body)
            columns.append(values if len(header) == 1 else f"{name}: {values}")
        return "; ".join(columns)
    return "; ".join(", ".join(row) for row in rows)


def parse(path: str, text: str) -> Feature | None:
    # A UTF-8 BOM in front of "Feature:" made whole files parse as empty; three suites in the control repo
    # are BOM-prefixed.
    lines = text.lstrip("\ufeff").splitlines()
    feature: Feature | None = None
    tags: list[str] = []
    current: Scenario | None = None
    step: Step | None = None
    in_background = False
    in_examples = False
    in_doc = False
    doc_lines: list[str] = []
    headers: list[str] = []

    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        stripped = line.strip()
        if in_doc:
            # A doc string is the step's data, verbatim: blank lines and `#` inside it are content,
            # not formatting, so it is read before anything else can dismiss them.
            if stripped.startswith('"""'):
                if step is not None:
                    step.doc_string = doc_lines
                in_doc = False
                doc_lines = []
            else:
                doc_lines.append(stripped)
            continue
        if not stripped or stripped.startswith("#"):
            step = None       # a blank line ends a table; whatever follows is not its rows
            continue
        if stripped.startswith("@"):
            tags.extend(t.strip() for t in stripped.split() if t.startswith("@"))
            continue
        if stripped.lower().startswith("feature:"):
            feature = Feature(name=stripped.split(":", 1)[1].strip(), path=path, tags=list(tags))
            tags.clear()
            current = None
            step = None
            continue
        if stripped.lower().startswith("background:"):
            current = Scenario(name="background", line=i, tags=[], background=True)
            in_background = True
            in_examples = False
            step = None
            if feature:
                feature.backgrounds.append(current)
            continue
        if stripped.lower().startswith("rule:"):
            step = None
            continue          # rule blocks group scenarios; they hold no steps of their own
        m = SCENARIO.match(stripped)
        if m:
            current = Scenario(name=m.group(1).strip(), line=i, tags=list(tags))
            tags.clear()
            in_background = False
            in_examples = False
            step = None
            if feature:
                feature.scenarios.append(current)
            continue
        if EXAMPLE.match(stripped):
            in_examples = True
            headers = []
            step = None
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
            step = Step(keyword=m.group(1), text=m.group(2).strip(), line=i)
            current.steps.append(step)
            continue
        if stripped.startswith('"""'):
            # A step's doc string is part of what it asserts; read it rather than dropping it.
            in_doc = True
            doc_lines = []
            continue
        if stripped.startswith("|"):
            if step is not None:
                step.table.append([c.strip() for c in stripped.strip("|").split("|")])
            continue
        step = None           # a description line is not a step and owns no data

    return feature if feature and feature.scenarios else feature
