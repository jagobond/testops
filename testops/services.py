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

# TESTOPS-51. One screen, every field. Before this ticket the check was "does the value contain
# token/password/secret/bearer anywhere", it was called only from :func:`validate_settings`, and the
# service *name* - a free-text field with no format of its own - never called it at all, so
# `name=password=hunter2` was stored and echoed. A per-field check is a check the next field skips;
# the rules below are applied at the store boundary, to every settings value and every human-entered
# name, so a field added tomorrow is covered by existing.
#
# A credential is a *shape*, not a word. Three shapes are recognised, in this order:
#
#   1. a `name=value` pair whose name is a credential word - `password=hunter2`,
#      `Authorization: Bearer ...`, `api_key = "..."`. The name stands alone, so `tokens` is not
#      `token` and `cotw-continuity` contains no credential name at all;
#   2. an issued-token shape: a known prefix, a PEM block, a JWT, an `Authorization` scheme;
#   3. a value that is one unbroken token containing a credential word (`my-password`,
#      `an-api-token`). Prose is not one token, which is why "test password reset flow" is
#      configuration and is stored.
_CREDENTIAL_NAME = (r"(?:password|passwd|pwd|token|api[ _-]?key|apikey|secret|bearer|"
                    r"authorization|private[ _-]?key|access[ _-]?key|client[ _-]?secret)")
# The pair's name is followed by `=` or `:` and then something - the shape a secret is pasted in.
_CREDENTIAL_PAIR = re.compile(rf"(?i)(?<![A-Za-z0-9])({_CREDENTIAL_NAME})[ \t]*[:=][ \t]*[^\s,;]")
# A name on its own, used for the settings *key* and for the single-token rule.
_CREDENTIAL_NAME_ALONE = re.compile(rf"(?i)(?:^|[^A-Za-z0-9]){_CREDENTIAL_NAME}(?:$|[^A-Za-z0-9])")
# `Bearer abc123`, `Basic dXNlcjpwYXNz`: an authorization scheme and a value behind it.
_AUTH_SCHEME = re.compile(r"(?i)^\s*(?:bearer|basic|digest|token)\s+[^\s,;]+")
# A PEM private-key block, wherever it was pasted in a longer value.
_PEM_BLOCK = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
# A JWT: the base64 header, a payload and a signature, three dot-separated segments.
_JWT = re.compile(r"^eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*$")

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

# TESTOPS-44 fix round. The entropy floors below only judge values of 32+ characters, so the
# shortest AWS credential - an `AKIA` key ID at 20 characters - passed by being short. A known token
# prefix is a shape, not a length, so this rule runs before the floors. Each entry is the literal
# start of a published credential format and, since TESTOPS-56 AC1, its body shape as well: a prefix
# alone is also how ordinary identifiers start (`AKIA-reviews-team`, `xoxb-not-a-token`,
# `ghp_only_a_document_path`), and no reader of those would expect a credential refusal. Matching is
# case-sensitive, because these prefixes are case-sensitive in the formats themselves and lower-case
# lookalikes (`skipton-branch`, `masking/x`, `task-akia-review`) are real configuration. Only the
# prefix is named in the refusal - never the value.
#
# The body shapes are the formats' own: a 20-character AWS key ID in upper-case base32; a GitHub
# classic token as one unbroken base62 run after `ghp_`/`gho_`/`ghu_`/`ghs_`; a GitLab PAT as one
# unbroken run after `glpat-`; a Slack token as digit-and-hyphen segments with a base62 tail; a JWT
# header followed by base64url segments. `github_pat_` and `sk-` keep the qualification they were
# given in TESTOPS-44, because their prefixes begin ordinary repository paths too.
_AWS_KEY_ID = re.compile(r"A(?:KIA|SIA)[A-Z0-9]{16}")
_GITHUB_CLASSIC = re.compile(r"gh[pous]_[A-Za-z0-9]+")
_GITLAB_PAT = re.compile(r"glpat-[A-Za-z0-9_-]{14,}")
_SLACK_TOKEN = re.compile(r"xox[bp]-[A-Za-z0-9-]{12,}")
_JWT_HEAD = re.compile(r"eyJ[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]+)*")
_PEM_KEY = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
_SK_MIN = 32                    # an `sk-` key body is an unbroken run, never a short word
_GITHUB_PAT = re.compile(r"^github_pat_[A-Za-z0-9]{22,}(?:_[A-Za-z0-9]+)*$")
#                                          ^ 22+ base62: the documented `github_pat_` body, with or
#                                            without the `_`-split suffix. `github_pat_docs` is 4.
_WORD_CHAIN = re.compile(r"[a-z]+(?:-[a-z]+)+")     # `sk-and-words`: words, not a key
_SK_BODY = re.compile(r"[A-Za-z0-9_\-]+")


def _is_sk_key(value: str) -> bool:
    """`sk-` and then a key body: 32+ characters, one unbroken run, no path separator, no words."""
    body = value[len("sk-"):]
    return (len(body) >= _SK_MIN
            and _SK_BODY.fullmatch(body) is not None
            and _WORD_CHAIN.fullmatch(body) is None)


def _fullmatches(pattern: re.Pattern):
    return lambda value: pattern.fullmatch(value) is not None


def _is_unbroken_token(pattern: re.Pattern):
    """The format's body, and not a chain of ordinary words joined by hyphens.

    `glpat-migration-plan` and `xoxb-not-a-token` are names; a real token's body is a mixed-case run
    with digits in it, which is never a lowercase word chain (TESTOPS-56 AC1).
    """
    return lambda value: (pattern.fullmatch(value) is not None
                          and _WORD_CHAIN.fullmatch(value) is None)


# TESTOPS-56 AC1: every prefix rule is qualified by body shape. The prefix says which format the
# value claims to be; the body decides whether it is one.
_PREFIXED_TOKENS = (
    ("AKIA", _fullmatches(_AWS_KEY_ID)),
    ("ASIA", _fullmatches(_AWS_KEY_ID)),
    ("ghp_", _fullmatches(_GITHUB_CLASSIC)),
    ("gho_", _fullmatches(_GITHUB_CLASSIC)),
    ("ghu_", _fullmatches(_GITHUB_CLASSIC)),
    ("ghs_", _fullmatches(_GITHUB_CLASSIC)),
    ("xoxb-", _is_unbroken_token(_SLACK_TOKEN)),
    ("xoxp-", _is_unbroken_token(_SLACK_TOKEN)),
    ("glpat-", _is_unbroken_token(_GITLAB_PAT)),
    ("eyJ", _fullmatches(_JWT_HEAD)),
    ("-----BEGIN ", _fullmatches(_PEM_KEY)),
    ("github_pat_", _fullmatches(_GITHUB_PAT)),
    ("sk-", _is_sk_key),
)

# TESTOPS-56 AC2: the parts a compound name may end with without the name reading as a credential.
# `password-manager` and `token-bucket` are the names of tools and of a rate-limiting algorithm, and
# they are what a person types. `my-password` is a credential name written plainly, and it has no such
# part - which is exactly where the boundary is drawn.
_TECHNICAL_SUFFIXES = frozenset({
    "manager", "store", "storage", "service", "bucket", "policy", "rotation", "refresh", "reset",
    "flow", "file", "path", "dialog", "prompt", "field", "input", "hint", "header", "label",
    "name", "value", "length", "strength", "expiry", "provider", "plugin",
})
_CREDENTIAL_WORD = re.compile(rf"(?i)^{_CREDENTIAL_NAME}$")


def _names_a_credential(parts: list[str]) -> bool:
    """Whether a short identifier, split into its parts, reads as *the name of a credential*.

    TESTOPS-56 AC2 scopes this rule deliberately. A bare credential word is refused; so is a name of
    up to three parts that **ends** in the credential word, which is how a credential is named out
    loud (`my-password`, `an-api-token`). A two-part name whose other part is a known technical
    suffix (`password-manager`, `token-bucket`) is the name of a tool, and a longer compound whose
    last part is not the credential word - `token-bucket-limiter`, the rate-limiting algorithm, or
    `xoxb-not-a-token`, a label about one - is a technical name. That is the whole of the decision,
    and the boundary table in ``tests/test_config_credential_screen.py`` pins both sides of it.
    """
    credential = [i for i, part in enumerate(parts) if _CREDENTIAL_WORD.fullmatch(part)]
    if not credential:
        return False
    if len(parts) == 1:
        return True                                   # `password` on its own names the thing
    if len(parts) == 2 and parts[1 - credential[0]] in _TECHNICAL_SUFFIXES:
        return False                                  # `password-manager`: a tool, not a secret
    return len(parts) <= 3 and credential[-1] == len(parts) - 1   # `my-password`, `an-api-token`


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
    """Why ``value`` reads as a credential, or ``None`` when it reads as configuration.

    The reason never contains the value: refusing a secret must not become the way it is printed.
    Names and prefixes may be named, because they are what the reader has to change.
    """
    plain = (value or "").strip()
    if not plain:
        return None
    # 1. A pasted `name=value` (or `name: value`) pair: the shape a credential arrives in.
    pair = _CREDENTIAL_PAIR.search(plain)
    if pair:
        return (f"it reads as a credential: the name {pair.group(1)!r} is followed by '=' or ':' "
                f"and a value")
    # 2. Issued-token shapes. A PEM block, a JWT and an authorization scheme are refused wherever
    #    they sit in the value, because a real one pasted into a longer string is still a secret.
    if _PEM_BLOCK.search(plain):
        return "it contains a PEM private-key block ('-----BEGIN ... PRIVATE KEY-----')"
    if _JWT.fullmatch(plain):
        return ("it is a JSON Web Token: three dot-separated segments beginning 'eyJ', the header "
                "of every JWT")
    if _AUTH_SCHEME.match(plain):
        return ("it begins with an authorization scheme ('Bearer', 'Basic', 'Digest' or 'Token') "
                "and a value")
    # 3. One short unbroken identifier naming a credential: `my-password`, `client-secret`. Two
    #    boundaries keep real names out: prose (whitespace) is not a token, a repository coordinate
    #    or path (a '/') is a coordinate, and a longer snake_cased label
    #    (`test_password_reset_flow`) is a name, not a secret. TESTOPS-56 AC2 scopes the rule itself
    #    in :func:`_names_a_credential`, so a compound name is not a credential name. The pair,
    #    prefix, PEM and JWT rules above still catch a real credential written in any of those forms.
    if not any(ch.isspace() for ch in plain) and "/" not in plain:
        parts = [part for part in re.split(r"[^A-Za-z0-9]+", plain) if part]
        if _names_a_credential(parts):
            return "it is a short identifier containing a credential word"
    # TESTOPS-56 AC1: every known credential prefix is qualified by the body shape the format is
    # issued with, so `AKIA-reviews-team` and `ghp_only_a_document_path` are names, not keys, while a
    # real token of each format - written at that format's own length and charset - is still
    # refused, before the entropy floors (the shortest AWS key ID is 20 characters).
    for prefix, looks_issued in _PREFIXED_TOKENS:
        if plain.startswith(prefix) and looks_issued(plain):
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
        if _CREDENTIAL_NAME_ALONE.search(key.strip()):
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


def refuse_credential_in(value: str, what: str) -> None:
    """The one screen for a human-entered name, applied at the store boundary (TESTOPS-51 AC1).

    A name is a label a reader sees, and it is stored and printed exactly like a settings value -
    so it is screened by the same rules, through the same call. Every create/edit path calls this
    rather than repeating the detection, which is what keeps a field added tomorrow covered.
    """
    reason = _looks_like_secret(value)
    if reason is None:
        return
    _LOG.warning("%s refused: %s", what, reason)
    raise ConfigError(
        f"the {what} was refused: {reason}. A {what} is a label a reader sees, and it is written "
        f"to the store and printed on the page - a credential written there would leak through "
        f"both. Secrets resolve from the environment when the connector runs, so a credential "
        f"must not be entered here.")


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
    # TESTOPS-51: the screen runs before the format checks, so a credential-shaped value is refused
    # with a reason that does not repeat it, whichever field it was typed into.
    refuse_credential_in(slug, "project slug")
    refuse_credential_in(name, "project name")
    if not _SLUG.fullmatch(slug):
        raise ConfigError(f"project slug {slug!r} must be lower-case letters, digits and hyphens, "
                          f"starting with a letter or digit (for example: cotw)")
    if get_project(conn, slug) is not None:
        raise ConfigError(f"a project {slug!r} already exists; choose another slug")
    conn.execute("INSERT INTO project (slug, name, created_at) VALUES (?,?,?)",
                 (slug, name, _now()))
    conn.commit()
    return {"slug": slug, "name": name}


def evidence_counts(conn, slug: str) -> dict:
    """How much evidence a project holds: runs, snapshots and cases, counted, not assumed.

    The three are counted separately because a reader asked to delete a project needs to know what
    would be lost, and "it has evidence" is not a count.
    """
    return {
        "runs": int(conn.execute("SELECT COUNT(*) FROM run WHERE project = ?", (slug,)).fetchone()[0]),
        "snapshots": int(conn.execute("SELECT COUNT(*) FROM snapshot WHERE project = ?",
                                      (slug,)).fetchone()[0]),
        "cases": int(conn.execute("SELECT COUNT(*) FROM case_ WHERE project = ?",
                                  (slug,)).fetchone()[0]),
    }


def remove_project(conn, slug: str) -> None:
    """Remove a project with its services, if it holds no evidence (TESTOPS-51 AC6).

    Evidence is immutable: a configuration action removes configuration. A project that still holds
    runs, snapshots or cases is refused, with the counts named, so nobody deletes the store's memory
    from a page that says "configuration". A project with no evidence - the empty
    ``contract-audit-*`` rows the contract suite leaves - is removed with its services.
    """
    require_project(conn, slug)
    counts = evidence_counts(conn, slug)
    if any(counts.values()):
        held = ", ".join(f"{n} {name}" for name, n in counts.items())
        _LOG.warning("project %r not deleted: it holds %s", slug, held)
        raise ConfigError(
            f"project {slug!r} was not deleted: it holds {held}. Runs, snapshots and cases are "
            f"evidence and are never deleted by a configuration action; only a project with no "
            f"evidence can be removed from this page.")
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
    # TESTOPS-51: the name is a user-supplied value like any other. It was the field the blind
    # author used, and the only reason it was accepted is that this screen was never applied here.
    refuse_credential_in(name, "service name")
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
