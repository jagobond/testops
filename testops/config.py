"""Configuration: where things live, and how to reach each project.

Credentials are read from an existing .env and never copied into the repo, the store or a prompt.

TESTOPS-41. The collector's file kinds are **data**, declared here, not a list buried in a loop.
The rule the ticket turns on is not "know every language" - that list can never be complete, and a
longer list is the same bug with more entries. The rule is that the list is configuration, and the
collector *reports everything that fell outside it*, with a reason and a count, in the run's own
record. A file nothing read is then never counted as consulted.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from . import sources

HOME = Path(os.environ.get("TESTOPS_HOME", Path.home() / "Projects" / "testops"))
DATA = HOME / "data"
DB_PATH = DATA / "testops.db"
BLOB_DIR = DATA / "blobs"
ENV_FILE = Path(os.environ.get("TESTOPS_ENV", Path.home() / "Projects" / "cotw-continuity" / ".env"))
KEYS_DIR = HOME.parent / "cotw-eval"


def load_env(path: Path = ENV_FILE) -> dict[str, str]:
    """Read KEY=VALUE pairs. Returns {} when the file is absent rather than raising."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


@dataclass(frozen=True)
class FileKind:
    """One kind of file the collector reads: its suffix, its artefact kind, what it can serve.

    ``capability`` is the capability a fetched file of this kind can stand as evidence for.
    ``""`` means the capability of the arm that fetched it - a `.py` file is product code when the
    product repository holds it and test code when the test repository does, and a `.csproj` is
    configuration belonging to whichever arm it was read from.

    ``kind`` is the artefact kind written to the store. It is a separate fact from the capability:
    a `.js` file is a step definition to this collector (the vocabulary it was built with), so it
    serves test code even when it is fetched from the product repository. That misfiling is
    TESTOPS-39's finding and is not fixed here; what this ticket adds is that a repository whose
    files fall outside this list says so, instead of counting them as consulted.
    """
    suffix: str
    kind: str
    capability: str = ""
    note: str = ""


# The list is this tuple, and only this tuple. Add a suffix here to widen the collector - and the
# run will still report, per repository, every file that fell outside it.
FILE_KINDS: tuple[FileKind, ...] = (
    FileKind(".csproj", "build",
             note="MSBuild project file: read for its exclusion patterns, an artefact of its arm"),
    FileKind(".feature", "feature", sources.TEST_CODE),
    FileKind(".py", "source",
             note="the only source kind declared: product code in the product arm, test code in "
                  "the test arm"),
    FileKind(".cs", "stepdef", sources.TEST_CODE),
    FileKind(".ts", "stepdef", sources.TEST_CODE),
    FileKind(".js", "stepdef", sources.TEST_CODE),
)

# Paths the collector refuses on purpose. Not the same as "a kind it does not read": these are
# ignored by pattern, and the run records them as ignored rather than as unsupported.
IGNORE_PATTERNS = ("/bin/", "/obj/", "/.git/", "/node_modules/", "/.venv/", "__pycache__")

# Suffixes dropped by rule: generated code-behind, recorded as an ignore pattern rather than
# silently filtered after the fact.
DROPPED_SUFFIXES = (".feature.cs",)

MAX_FILE_BYTES = 512 * 1024


def kind_for(path: str) -> FileKind | None:
    """The rule that reads ``path``, or ``None`` when no rule does.

    The arm a file came from never decides *whether* a kind is read - that is the whole point of the
    list being configuration. It decides only what a source file *is*: the test arm's Python is test
    code, which the collector settles after this call.
    """
    for rule in FILE_KINDS:
        if path.endswith(rule.suffix):
            return rule
    return None


def arm_capability(role: str) -> str:
    """Which capability an arm can serve: the product is code, the test repository is test code."""
    return sources.CODE if role == "product" else sources.TEST_CODE


@dataclass(frozen=True)
class Repo:
    owner: str
    name: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True)
class Project:
    """A project is coordinates: repos, a Jira key, an ADO query."""
    key: str
    product: Repo
    test: Repo
    jira_key: str
    ado_org: str | None = None
    ado_project: str | None = None
    ado_pipeline_ids: tuple[int, ...] = field(default_factory=tuple)


PROJECTS: dict[str, Project] = {
    "cotw": Project(
        key="cotw",
        product=Repo("jagobond", "cotw-continuity"),
        test=Repo("jagobond", "cotw-bdd"),
        jira_key="COTW",
        ado_org="RuckoldtAndRylander",
        ado_project="cotw-continuity",
        ado_pipeline_ids=(2, 4),
    ),
    "testops": Project(
        key="testops",
        product=Repo("jagobond", "testops"),
        test=Repo("jagobond", "testops"),
        jira_key="TOPS",
    ),
    # External positive control: the answer is known to be "nine WebUI scenarios duplicate lower layers".
    "reqoverflow": Project(
        key="reqoverflow",
        product=Repo("reqnroll", "Sample-ReqOverflow"),
        test=Repo("reqnroll", "Sample-ReqOverflow"),
        jira_key="",
    ),
    # TESTOPS-39 second specimen: a different ecosystem and separate repositories. JavaScript
    # Cypress + Cucumber tests against a Java multi-service product, both public.
    "restfulbooker": Project(
        key="restfulbooker",
        product=Repo("mwinteringham", "restful-booker-platform"),
        test=Repo("m-pujic-levi9-com", "cypress-cucumber-e2e-tests"),
        jira_key="",
    ),
}


def project(name: str) -> Project:
    if name not in PROJECTS:
        raise SystemExit(f"unknown project {name!r}; known: {', '.join(PROJECTS)}")
    return PROJECTS[name]
