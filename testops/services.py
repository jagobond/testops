"""Projects and services: the store's model of what is being analysed, and how it is reached.

TESTOPS-38 implements ADR-1. A **project** is an identity - a slug and a name. A **service** is one
analysable resource inside it: a ``git_repo`` (role ``product`` or ``test``), a ``jira_board`` or an
``ado_pipeline``. Nothing here talks to Jira or ADO; the connectors land on top of this model in the
next tickets. What exists now is the seam they will use:

  * a project and its services are **rows**, so a second team adds one on the configuration page and
    needs no build, no deploy and no restart;
  * each service records its **own** last-consulted state and reason, so a page can say which
    service was not connected and why instead of one sentence standing for the whole project;
  * ``settings`` holds hosts, repository coordinates, board keys and paths. It never holds a
    credential: :func:`validate_settings` refuses one, and secrets resolve from the environment at
    call time (AC5).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import math
import re
from dataclasses import dataclass, field

from . import sources
from .config import Project, Repo

TYPES = ("git_repo", "jira_board", "ado_pipeline")
ROLES = ("product", "test")

# What a service can say about itself. These are the words a page prints, and they never share a
# meaning: "not connected" is a connector this build does not have, "policy" is a source somebody
# forbids, "absent" is a service the project does not declare at all.
AVAILABLE = "available"
NOT_CONNECTED = "not_connected"
POLICY = "policy"
ABSENT = "absent"
NOT_ASSESSABLE = "not_assessable"
SERVICE_STATES = (AVAILABLE, NOT_CONNECTED, POLICY, ABSENT, NOT_ASSESSABLE)

CREATE_AT = "%Y-%m-%dT%H:%M:%S+00:00"

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_CREDENTIAL_WORDS = ("token", "password", "secret", "bearer")

# TESTOPS-44. Base64 is the most common way a credential is written down, and its alphabet contains
# `/` - the very character the separator exemption below used to read as proof of configuration. So
# the charset is checked first: a long blob of the base64 alphabet is refused whatever punctuation it
# contains. The entropy floor separates an encoded secret from a path or a coordinate made of words:
# word-shaped settings measured here sit below 4.1 bits per character
# (`SomeOrg/SomeVeryLongRepositoryName2` is 4.023), base64 of arbitrary bytes above 4.4. The floor is
# a threshold, not a proof, and is set to keep every plausible configuration in AC2 accepted.
_BLOB_MIN = 32
_BASE64 = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
_BASE64_ENTROPY = 4.3

# TESTOPS-44 fix round. The entropy floors below only judge values of 32+ characters, so the shortest
# AWS credential - an `AKIA` key ID at 20 characters - passed by being short. A known token prefix is
# a shape, not a length, so this rule runs at *any* length and before the floors. Each entry is the
# literal start of a published credential format; matching is case-sensitive, because these prefixes
# are case-sensitive in the formats themselves and lower-case lookalikes (`skipton-branch`,
# `masking/x`, `task-akia-review`) are real configuration. Only the prefix is matched, and only the
# prefix is named in the refusal - never the value.
_TOKEN_PREFIXES = (
    "AKIA",             # AWS access key ID
    "ASIA",             # AWS temporary access key ID
    "ghp_", "gho_", "ghu_", "ghs_",   # GitHub personal / OAuth / user / server tokens
    "github_pat_",      # GitHub fine-grained personal access token
    "xoxb-", "xoxp-",   # Slack bot / user tokens
    "glpat-",           # GitLab personal access token
    "sk-",              # OpenAI-style secret key
    "eyJ",              # base64-encoded '{"' - the header of every JWT
    "-----BEGIN ",      # PEM private key (and any other PEM block)
)

# What divides a structured key into readable parts. `COTW-PROJ-KEY-0123456789-ABCDEFG` and a UUID
# are configuration written as short parts; a token is one long unbroken run. Judging the longest run
# rather than the whole value is what lets a hyphenated key through while a `ghp_...` token stays out.
_SEPARATORS = re.compile(r"[/\\\-._:]")

_LOG = logging.getLogger(__name__)


class ConfigError(ValueError):
    """A configuration the store or the model cannot express, in words a user can act on."""


class UnknownProject(ConfigError):
    """No project with that slug. The message names the slug and the projects that do exist."""

    def __init__(self, slug: str, known: list[str]) -> None:
        self.slug = slug
        known_text = ", ".join(known) if known else "none"
        super().__init__(f"unknown project {slug!r}; this store holds: {known_text}. "
                         f"Add it on the configuration page (/config) or as a row in the project "
                         f"table - no code change is needed.")


# ---------------------------------------------------------------- credentials (AC5)

def _entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = {ch: text.count(ch) for ch in set(text)}
    return -sum((n / len(text)) * math.log2(n / len(text)) for n in counts.values())


def _looks_like_secret(value: str) -> str | None:
    """Why ``value`` reads as a credential, or ``None`` when it reads as configuration."""
    lower = value.lower()
    for word in _CREDENTIAL_WORDS:
        if word in lower:
            return f"it contains {word!r}"
    plain = value.strip()
    # A known credential prefix is refused at any length, before the floors: the shortest realistic
    # AWS key ID is 20 characters and would otherwise sit below `_BLOB_MIN`.
    for prefix in _TOKEN_PREFIXES:
        if plain.startswith(prefix):
            return f"it begins with {prefix!r}, the prefix of a known credential format"
    # A long blob of one alphabet is a token shape, not a host, a path or a repository. URLs and
    # paths are exempt: they are what settings are for.
    if len(plain) >= _BLOB_MIN and not any(ch.isspace() for ch in plain) \
            and not plain.startswith(("http://", "https://")):
        # AC1: before the separator exemption, because base64 always contains '/' and often '+' or
        # '='. A blob that is entirely the base64 alphabet and carries encoded-secret entropy is
        # refused even though it looks like a path.
        if _BASE64.fullmatch(plain) and _entropy(plain) >= _BASE64_ENTROPY:
            return (f"it looks like a base64-encoded secret ({len(plain)} characters of the "
                    f"base64 alphabet)")
        # AC2: a structured key is written in short parts; a token is one long unbroken run. Only
        # the longest run is judged, so a UUID or COTW-PROJ-KEY-... is configuration and ghp_... is
        # still a token.
        longest = max(len(part) for part in _SEPARATORS.split(plain))
        if longest >= 32 and (re.fullmatch(r"[A-Fa-f0-9]+", plain)
                              or (_entropy(plain) >= 3.5 and len(set(plain)) >= 12)):
            return "it looks like a high-entropy secret (32+ characters, no separators)"
    return None


def validate_settings(settings: dict) -> dict:
    """Refuse a credential in service settings, saying which field and why (AC5).

    Settings are written to the store, printed on the configuration page and copied into backups. A
    token there is a token in every one of them. Credentials resolve from the environment when a
    connector is called; the row holds the host, the key or the path, never the secret. The value is
    never echoed in the error - refusing a secret must not be another way to print it.
    """
    if not isinstance(settings, dict):
        raise ConfigError("settings must be a mapping of field names to values")
    for key, value in settings.items():
        if not isinstance(key, str) or not key.strip():
            raise ConfigError("every settings field needs a name")
        if any(word in key.lower() for word in _CREDENTIAL_WORDS):
            # AC3: the field name and the reason are logged; the value never is. A refusal that
            # printed the secret would be a second way to leak it.
            _LOG.warning("settings field %r refused: the field name reads as a credential", key)
            raise ConfigError(
                f"settings field {key!r} is named like a credential. Settings hold hosts, "
                f"repository coordinates, board keys and paths only; a secret resolves from the "
                f"environment at call time, so it must not be stored here.")
        if isinstance(value, (dict, list, tuple)):
            raise ConfigError(f"settings field {key!r} must be a single value, not a nested "
                              f"{type(value).__name__}")
        reason = _looks_like_secret(str(value))
        if reason:
            _LOG.warning("settings field %r refused: %s", key, reason)
            raise ConfigError(
                f"settings field {key!r} was refused: {reason}. Settings hold hosts, repository "
                f"coordinates, board keys and paths only - never a token, password or key. A "
                f"credential written here would leak through the store, the page and every backup. "
                f"Resolve it from the environment when the connector runs.")
    return dict(settings)


# ---------------------------------------------------------------- projects

@dataclass(frozen=True)
class Service:
    id: int
    project: str
    type: str
    role: str
    name: str
    settings: dict
    last_state: str | None = None
    last_reason: str | None = None
    last_consulted_at: str | None = None

    def record(self) -> dict:
        """The service as a snapshot records it: no settings, so no host leaks into a run page."""
        return {"id": self.id, "name": self.name, "type": self.type, "role": self.role,
                "state": self.last_state or "", "reason": self.last_reason or ""}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _rows(conn, sql: str, args: tuple = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, args)]


def list_projects(conn) -> list[dict]:
    return _rows(conn, "SELECT slug, name, created_at FROM project ORDER BY slug")


def get_project(conn, slug: str) -> dict | None:
    rows = _rows(conn, "SELECT slug, name, created_at FROM project WHERE slug = ?", (slug,))
    return rows[0] if rows else None


def require_project(conn, slug: str) -> dict:
    """The project row, or :class:`UnknownProject` naming the slug and the store's projects."""
    project = get_project(conn, slug)
    if project is None:
        raise UnknownProject(slug, [row["slug"] for row in list_projects(conn)])
    return project


def add_project(conn, slug: str, name: str) -> dict:
    """Add a project. A slug is an identity: it may not be blank, re-used or decorative."""
    slug = (slug or "").strip()
    name = (name or "").strip() or slug
    if not _SLUG.fullmatch(slug):
        raise ConfigError(f"project slug {slug!r} must be lower-case letters, digits and hyphens, "
                          f"starting with a letter or digit (for example: cotw)")
    if get_project(conn, slug) is not None:
        raise ConfigError(f"a project {slug!r} already exists; choose another slug")
    conn.execute("INSERT INTO project (slug, name, created_at) VALUES (?,?,?)",
                 (slug, name, _now()))
    conn.commit()
    return {"slug": slug, "name": name}


def remove_project(conn, slug: str) -> None:
    """Remove a project with its services. Runs and cases keep their rows: evidence is not config."""
    conn.execute("DELETE FROM project WHERE slug = ?", (slug,))
    conn.commit()


# ---------------------------------------------------------------- services

def _service(row: dict) -> Service:
    try:
        settings = json.loads(row.get("settings") or "{}")
    except json.JSONDecodeError as exc:
        raise ConfigError(f"service {row.get('id')} holds unreadable settings: {row.get('settings')!r}"
                          ) from exc
    return Service(id=row["id"], project=row["project"], type=row["type"], role=row["role"],
                   name=row["name"], settings=settings if isinstance(settings, dict) else {},
                   last_state=row.get("last_state"), last_reason=row.get("last_reason"),
                   last_consulted_at=row.get("last_consulted_at"))


def list_services(conn, slug: str) -> list[Service]:
    return [_service(row) for row in
            _rows(conn, "SELECT * FROM service WHERE project = ? ORDER BY type, role, id", (slug,))]


def get_service(conn, service_id: int) -> Service | None:
    rows = _rows(conn, "SELECT * FROM service WHERE id = ?", (service_id,))
    return _service(rows[0]) if rows else None


def _check_service(conn, project: str, kind: str, role: str, name: str, settings: dict) -> None:
    if get_project(conn, project) is None:
        raise ConfigError(f"no project {project!r}; add the project before adding services to it")
    if kind not in TYPES:
        raise ConfigError(f"unknown service type {kind!r}; expected one of {', '.join(TYPES)}")
    if kind == "git_repo" and role not in ROLES:
        raise ConfigError("a git repository service is either the product or the tests: "
                          "role must be 'product' or 'test'")
    if kind != "git_repo" and role:
        raise ConfigError(f"a {kind} service has no role; leave it empty")
    if not (name or "").strip():
        raise ConfigError("a service needs a name a reader can see")
    validate_settings(settings)
    if kind == "git_repo":
        repo = str(settings.get("repo") or "")
        if not _REPO.fullmatch(repo):
            raise ConfigError(f"a git repository service needs settings.repo as 'owner/name', "
                              f"found {repo!r}")
    if kind == "jira_board" and not str(settings.get("board") or "").strip():
        raise ConfigError("a Jira board service needs settings.board (the board or project key)")
    if kind == "ado_pipeline":
        if not str(settings.get("org") or "").strip():
            raise ConfigError("an Azure DevOps service needs settings.org")
        pipeline_id = settings.get("pipeline_id")
        if pipeline_id is not None and not isinstance(pipeline_id, int):
            raise ConfigError("settings.pipeline_id must be a number when present")


def add_service(conn, project: str, kind: str, role: str, name: str, settings: dict) -> Service:
    settings = dict(settings or {})
    _check_service(conn, project, kind, role, name, settings)
    cur = conn.execute(
        "INSERT INTO service (project, type, role, name, settings, created_at) VALUES (?,?,?,?,?,?)",
        (project, kind, role, name.strip(), json.dumps(settings, sort_keys=True), _now()))
    conn.commit()
    return get_service(conn, int(cur.lastrowid))  # type: ignore[arg-type]


def update_service(conn, service_id: int, *, kind: str, role: str, name: str,
                   settings: dict) -> Service:
    existing = get_service(conn, service_id)
    if existing is None:
        raise ConfigError(f"no service {service_id}")
    settings = dict(settings or {})
    _check_service(conn, existing.project, kind, role, name, settings)
    conn.execute("UPDATE service SET type=?, role=?, name=?, settings=? WHERE id=?",
                 (kind, role, name.strip(), json.dumps(settings, sort_keys=True), service_id))
    conn.commit()
    return get_service(conn, service_id)  # type: ignore[return-value]


def remove_service(conn, service_id: int) -> None:
    conn.execute("DELETE FROM service WHERE id = ?", (service_id,))
    conn.commit()


# ---------------------------------------------------------------- the project as the pipeline sees it

@dataclass(frozen=True)
class ProjectAssessment:
    """What the store's own services can say about a project, before any connector is called."""
    slug: str
    state: str                      # available | not_assessable
    reason: str
    services: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def assessable(self) -> bool:
        return self.state != NOT_ASSESSABLE

    def record(self) -> list[dict]:
        return [dict(state) for state in self.services]


def _repo_of(service: Service) -> Repo | None:
    text = str(service.settings.get("repo") or "")
    if "/" not in text:
        return None
    owner, name = text.split("/", 1)
    return Repo(owner, name)


def assess_services(conn, slug: str) -> ProjectAssessment:
    """Per-service state for a project, with an absent service named rather than omitted (AC4/AC7).

    A missing product repository is the case AC7 exists for: the project can still be listed, its
    test repository read, and the page must say the product code could not be assessed. A project
    with no Jira board says so as a *service* that is absent, not as silence.
    """
    rows = list_services(conn, slug)
    product = next((s for s in rows if s.type == "git_repo" and s.role == "product"), None)
    test = next((s for s in rows if s.type == "git_repo" and s.role == "test"), None)

    states: list[dict] = []
    missing: list[str] = []
    for role, found, title in (("product", product, "Product repository"),
                               ("test", test, "Test repository")):
        if found is not None:
            states.append({"id": found.id, "name": found.name, "type": "git_repo", "role": role,
                           "state": AVAILABLE, "reason": ""})
            continue
        reason = (f"no {'product' if role == 'product' else 'test'} git repository is configured "
                  f"for this project, so nothing can be said about it - which is not the same as "
                  f"finding nothing")
        states.append({"id": None, "name": title, "type": "git_repo", "role": role,
                       "state": ABSENT, "reason": reason})
        missing.append(reason)

    jira = next((s for s in rows if s.type == "jira_board"), None)
    if jira is None:
        states.append({"id": None, "name": "Jira board", "type": "jira_board", "role": "",
                       "state": ABSENT,
                       "reason": "no Jira board is configured for this project"})
    else:
        # No connector in this ticket. The reason says both facts: this build lacks the connector,
        # and at Quilter the source is blocked by policy. Neither is a zero.
        states.append({"id": jira.id, "name": jira.name, "type": "jira_board", "role": "",
                       "state": POLICY,
                       "reason": ("no Jira connector is installed in this build, and Quilter "
                                  "policy forbids issuing a personal access token because of "
                                  "breach risk")})
    pipelines = [s for s in rows if s.type == "ado_pipeline"]
    if not pipelines:
        states.append({"id": None, "name": "Azure DevOps pipeline", "type": "ado_pipeline",
                       "role": "", "state": ABSENT,
                       "reason": "no Azure DevOps pipeline is configured for this project"})
    for pipeline in pipelines:
        states.append({"id": pipeline.id, "name": pipeline.name, "type": "ado_pipeline",
                       "role": "", "state": POLICY,
                       "reason": ("no connector for Azure DevOps is installed in this build, and "
                                  "Quilter policy forbids a personal access token")})

    if missing:
        return ProjectAssessment(slug, NOT_ASSESSABLE, " ".join(missing), tuple(states))
    return ProjectAssessment(slug, AVAILABLE, "", tuple(states))


def project_from_store(conn, slug: str) -> Project:
    """Assemble the pipeline's :class:`Project` from a store project and its services (AC8).

    ``service_states`` is what the services said when the project was resolved, so the run can write
    that record into its snapshot instead of re-deriving it at render time. A project with no
    product repository is returned with ``product=None`` - not refused and not defaulted to the test
    repository - so the pipeline reports ``not_assessable`` rather than collecting the wrong arm.
    """
    if get_project(conn, slug) is None:
        raise UnknownProject(slug, [row["slug"] for row in list_projects(conn)])
    services = list_services(conn, slug)
    assessment = assess_services(conn, slug)
    product = next((s for s in services if s.type == "git_repo" and s.role == "product"), None)
    test = next((s for s in services if s.type == "git_repo" and s.role == "test"), None)
    if test is None:
        raise ConfigError(f"project {slug!r} has no test git repository service, so there is "
                          f"nothing to analyse. Add one on the configuration page (/config).")
    jira = next((s for s in services if s.type == "jira_board"), None)
    ado = [s for s in services if s.type == "ado_pipeline"]
    return Project(
        key=slug,
        product=_repo_of(product) if product else None,
        test=_repo_of(test),  # type: ignore[arg-type]
        jira_key=str((jira.settings if jira else {}).get("board") or ""),
        ado_org=str(ado[0].settings.get("org") or "") if ado else None,
        ado_project=str(ado[0].settings.get("project") or "") if ado else None,
        ado_pipeline_ids=tuple(int(s.settings["pipeline_id"]) for s in ado
                               if isinstance(s.settings.get("pipeline_id"), int)),
        service_states=tuple(dict(state) for state in assessment.services),
        assessment_state=assessment.state,
        assessment_reason=assessment.reason,
    )


def record_consultation(conn, slug: str, states: list[dict]) -> list[dict]:
    """Write each service's last-consulted state and reason to its own row (AC4).

    Called when a run resolves a project. A state with no service row (the absent product/test
    repository, for instance) has nowhere to live and is not written: inventing a row for it would
    turn "the project does not declare this" into "somebody configured it".
    """
    now = _now()
    written: list[dict] = []
    for state in states:
        service_id = state.get("id")
        if service_id is None:
            written.append(dict(state))
            continue
        conn.execute("UPDATE service SET last_state=?, last_reason=?, last_consulted_at=? "
                     "WHERE id=?", (state.get("state"), state.get("reason"), now, service_id))
        row = dict(state)
        row["at"] = now
        written.append(row)
    conn.commit()
    return written
