"""Configuration: where things live, and how to reach each project.

Credentials are read from an existing .env and never copied into the repo, the store or a prompt.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

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
