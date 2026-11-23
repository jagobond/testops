"""TESTOPS-51: the credential screen is one check at the boundary, applied to every field.

Before this ticket the screen was a per-field call from :func:`validate_settings`, and the service
**name** - a free-text box with no format of its own - never called it. A blind author typed
``password=hunter2`` into that box; ``/config`` accepted it, stored it and echoed it back, while the
same value in the repository field was refused. A field somebody adds tomorrow would have had the
same hole, which is why the fix is at the store boundary rather than in the Name field.

AC4 is the other half, and it is the half that decides whether the guard survives: a screen that
refuses ordinary words is worse than none, because it gets switched off. Every value in
:data:`ORDINARY` is something a person would legitimately type, and each is pinned one by one.
"""
from __future__ import annotations

import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from testops import services
from testops.store import db
from testops.web import app

# The value the blind author posted into the Name field. It is a joke credential, not a real one,
# which is exactly why it is safe to pin: the shape is what is being refused.
PROBE = "password=hunter2"


# --------------------------------------------------------------------------- HTTP harness

def _server(monkeypatch, path):
    real = db.connect                          # captured before the caller patches it
    monkeypatch.setattr(app.db, "connect", lambda _path=None: real(path))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def _post(url: str, fields: dict) -> tuple[int, str]:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:      # a refusal is a page, and the test reads it
        return exc.code, exc.read().decode("utf-8")


def _get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read().decode("utf-8")


@pytest.fixture
def live(tmp_path, monkeypatch):
    path = tmp_path / "screen.db"
    httpd, base = _server(monkeypatch, path)
    try:
        yield base, path
    finally:
        httpd.shutdown()
        httpd.server_close()


def _service_fields(**over) -> dict:
    fields = {"project": "team", "type": "git_repo", "role": "test", "name": "API tests",
              "repo": "owner/keep", "board": "", "host": "", "org": "", "ado_project": "",
              "pipeline_id": ""}
    fields.update(over)
    return fields


# --------------------------------------------------------------------------- AC3 detection

# One probe per credential-shaped NAME the ticket names, in the two written forms a value arrives
# in: an unbroken `name=value` and a spaced/quoted one.
CREDENTIAL_PAIRS = {
    "password=«secret»": "password",
    "passwd=«secret»": "passwd",
    "pwd=«secret»": "pwd",
    "token=«secret»": "token",
    "api_key=«secret»": "api_key",
    "apikey=«secret»": "apikey",
    "secret=«secret»": "secret",
    "bearer=«secret»": "bearer",
    "authorization=«secret»": "authorization",
    "private_key=«secret»": "private_key",
    "access_key=«secret»": "access_key",
    "client_secret=«secret»": "client_secret",
    "password = «secret»": "password",
    'password:"«secret»"': "password",
    "authorization: Bearer «secret»": "authorization",
    "x password=«secret» y": "password",
}

# Issued-token shapes, each at something like the real format's body so the probe is a shape and
# not an accident of length. None of these is a live credential.
ISSUED_TOKENS = {
    "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8": "ghp_",
    "gho_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8": "gho_",
    "ghs_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8": "ghs_",
    "github_pat_" + "a1B2c3D4e5F6g7H8i9J0k1": "github_pat_",
    "sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0": "sk-",
    "AKIA" + "ABCDEFGHIJKLMNOP": "AKIA",
    "xoxb-" + "0123456789ab": "xoxb-",
    "xoxp-" + "0123456789ab": "xoxp-",
}

PEM_BLOCK = ("-----BEGIN RSA PRIVATE KEY-----\n"
             "MIIEowIBAAKCAQEA0000000000000000000000000000000000\n"
             "-----END RSA PRIVATE KEY-----")

JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJwcm9iZSJ9.c2lnbmF0dXJl"


@pytest.mark.parametrize("value", sorted(CREDENTIAL_PAIRS))
def test_a_pasted_name_value_pair_is_refused(value):
    reason = services._looks_like_secret(value)
    assert reason is not None, f"{value!r} was read as configuration"
    assert "credential" in reason


@pytest.mark.parametrize("value", sorted(ISSUED_TOKENS))
def test_an_issued_token_shape_is_refused(value):
    reason = services._looks_like_secret(value)
    assert reason is not None, f"an issued-token shape was read as configuration: {value[:8]}..."
    assert ISSUED_TOKENS[value] in reason, "the refusal should name the prefix it recognised"


def test_a_pem_private_key_block_is_refused():
    assert services._looks_like_secret(PEM_BLOCK) is not None
    assert services._looks_like_secret("key: " + PEM_BLOCK) is not None


def test_a_jwt_is_refused():
    assert services._looks_like_secret(JWT) is not None


# --------------------------------------------------------------------------- AC4 no false positives

# The ticket's list, verbatim, each against the field it would really be typed into. Every one of
# these must be accepted and stored.
ORDINARY = {
    "repo": "jagobond/cotw-continuity",
    "name": "Jira board COTW",
    "org": "RuckoldtAndRylander",
    "project": "cotw-continuity pipeline #2",
    "repo_restful": "mwinteringham/restful-booker-platform",
    "host": "100.121.128.21",
    "host_port": "localhost:8791",
    "repo_url": "https://github.com/org/repo.git",
    "board": "COTW",
    "jira_key": "TOPS",
    "name_prose": "test password reset flow",
    # Boundaries of the "short credential-word identifier" rule, pinned so tightening it further
    # cannot swallow a name or a repository coordinate unremarked.
    "name_snake": "test_password_reset_flow",
    "repo_path": "password-manager/tool",
}


@pytest.mark.parametrize("field,value", sorted(ORDINARY.items()),
                         ids=[f"{field}-{value[:18]}" for field, value in
                              sorted(ORDINARY.items())])
def test_ordinary_configuration_is_accepted_and_pinned(field, value):
    """AC4: a screen that refuses ordinary words gets switched off, so each is pinned."""
    assert services._looks_like_secret(value) is None, \
        f"{field} was read as a credential: {value!r}"
    stored = services.validate_settings({field: value})
    assert stored == {field: value}


def test_a_service_named_in_ordinary_words_is_accepted(tmp_path):
    conn = db.connect(tmp_path / "ordinary.db")
    try:
        services.add_project(conn, "cotw", "Children of the Old War")
        for name in ("Jira board COTW", "cotw-continuity pipeline #2", "test password reset flow"):
            services.add_service(conn, "cotw", "jira_board", "", name, {"board": "COTW"})
        assert [service.name for service in services.list_services(conn, "cotw")] == \
            ["Jira board COTW", "cotw-continuity pipeline #2", "test password reset flow"]
    finally:
        conn.close()


# --------------------------------------------------------------------------- AC1 one shared check

@pytest.mark.parametrize("value", [PROBE, "ghp_" + "a1B2" * 12, PEM_BLOCK, JWT])
def test_a_settings_field_that_does_not_exist_yet_is_screened(value):
    """AC1: the check is on the way into the store, so a field added tomorrow cannot opt out."""
    with pytest.raises(services.ConfigError):
        services.validate_settings({"a_field_added_next_year": value})


@pytest.mark.parametrize("what", ["service name", "project name"])
def test_every_human_entered_name_goes_through_the_same_screen(what, tmp_path):
    conn = db.connect(tmp_path / "names.db")
    try:
        with pytest.raises(services.ConfigError) as refused:
            if what == "service name":
                services.add_project(conn, "team", "Team")
                services.add_service(conn, "team", "git_repo", "test", PROBE,
                                     {"repo": "owner/keep"})
            else:
                services.add_project(conn, "team", PROBE)
        message = str(refused.value)
        assert what in message
        assert "credential" in message
        assert PROBE not in message, "refusing a credential must not print it"
        if what == "service name":
            assert services.list_services(conn, "team") == []
        else:
            assert services.list_projects(conn) == []
    finally:
        conn.close()


def test_editing_a_service_name_is_screened_too(tmp_path):
    conn = db.connect(tmp_path / "edit.db")
    try:
        services.add_project(conn, "team", "Team")
        service = services.add_service(conn, "team", "git_repo", "test", "API tests",
                                       {"repo": "owner/keep"})
        with pytest.raises(services.ConfigError):
            services.update_service(conn, service.id, kind="git_repo", role="test", name=PROBE,
                                    settings={"repo": "owner/keep"})
        kept = services.get_service(conn, service.id)
        assert kept is not None and kept.name == "API tests"
    finally:
        conn.close()


# --------------------------------------------------------------------------- AC2/AC5 every route

def test_the_name_field_that_let_the_probe_through_now_refuses_it(live):
    """AC2: HTTP 400, a reason in the same voice as the repo refusal, nothing stored or echoed."""
    base, path = live
    _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})

    status, body = _post(f"{base}/config/services", _service_fields(name=PROBE))

    assert status == 400, "the Name field accepted a credential-shaped value again"
    assert "service name" in body and "credential" in body, "the refusal does not say what and why"
    assert PROBE not in body, "the refusal page echoed the credential"
    assert PROBE not in _get(f"{base}/config"), "the credential appears in the stored configuration"

    conn = db.connect(path)
    try:
        assert services.list_services(conn, "team") == [], "a refused value reached the store"
    finally:
        conn.close()


def test_every_write_route_refuses_the_probe_and_writes_no_row(live):
    """AC5: the service form, the project-create form and the inline service edit."""
    base, path = live
    _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})

    conn = db.connect(path)
    try:
        existing = services.add_service(conn, "team", "git_repo", "test", "API tests",
                                        {"repo": "owner/keep"})
        existing_id = existing.id
    finally:
        conn.close()

    # 1. create a service
    status, body = _post(f"{base}/config/services", _service_fields(name=PROBE))
    assert status == 400 and "service name" in body

    # 2. edit that service inline, renaming it
    status, body = _post(f"{base}/config/service/{existing_id}", _service_fields(name=PROBE))
    assert status == 400 and "service name" in body, "the inline edit route was bypassable"

    # 3. create a project whose human-entered name is the probe
    status, body = _post(f"{base}/config/projects", {"slug": "probe", "name": PROBE})
    assert status == 400 and "project name" in body, "the project-create route was bypassable"
    assert PROBE not in body

    conn = db.connect(path)
    try:
        assert [service.name for service in services.list_services(conn, "team")] == ["API tests"]
        assert [row["slug"] for row in services.list_projects(conn)] == ["team"]
    finally:
        conn.close()
    assert PROBE not in _get(f"{base}/config")


def test_a_credential_in_any_settings_field_is_refused_over_http(live):
    """AC3 by the route a person uses: board, host, org and repo all meet the same screen."""
    base, _path = live
    _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})
    for fields in (_service_fields(repo="token=«secret»"),
                   _service_fields(type="jira_board", role="", board="token=«secret»"),
                   _service_fields(type="jira_board", role="", board="COTW",
                                   host="password=hunter2"),
                   _service_fields(type="ado_pipeline", role="", org="AKIAABCDEFGHIJKLMNOP")):
        status, body = _post(f"{base}/config/services", fields)
        assert status == 400, f"a credential-shaped settings value was accepted: {fields}"
        assert "credential" in body


# --------------------------------------------------------------------------- AC6 project delete

def test_a_project_with_no_evidence_is_deleted_with_its_services(live):
    base, path = live
    _post(f"{base}/config/projects", {"slug": "contract-audit-1", "name": "Contract audit"})
    _post(f"{base}/config/services", _service_fields(project="contract-audit-1"))
    assert "contract-audit-1" in _get(f"{base}/config")

    status, page = _post(f"{base}/config/project/contract-audit-1/delete", {})

    assert status == 200, page
    assert "contract-audit-1" not in _get(f"{base}/config")
    conn = db.connect(path)
    try:
        assert services.list_projects(conn) == []
        assert services.list_services(conn, "contract-audit-1") == []
    finally:
        conn.close()


def test_a_project_that_holds_evidence_refuses_to_be_deleted_and_names_the_counts(live):
    base, path = live
    _post(f"{base}/config/projects", {"slug": "cotw", "name": "Children of the Old War"})
    conn = db.connect(path)
    try:
        conn.execute("INSERT INTO snapshot (id, project, created_at, artefact_versions) "
                     "VALUES ('snap-1', 'cotw', '2026-01-01T00:00:00+00:00', '{}')")
        conn.execute("INSERT INTO run (id, project, snapshot_id, analyser, status, started_at) "
                     "VALUES ('run-1', 'cotw', 'snap-1', 'duplication', 'ok', "
                     "'2026-01-01T00:00:00+00:00')")
        conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at) "
                     "VALUES ('case-1', 'run-1', 'cotw', 'duplication', 'snap-1', "
                     "'2026-01-01T00:00:00+00:00')")
        conn.commit()
    finally:
        conn.close()

    status, body = _post(f"{base}/config/project/cotw/delete", {})

    assert status == 400, "a project holding evidence was deleted by a configuration action"
    assert "1 runs" in body and "1 snapshots" in body and "1 cases" in body, \
        "the refusal does not name the counts that block it"
    conn = db.connect(path)
    try:
        assert [row["slug"] for row in services.list_projects(conn)] == ["cotw"]
        assert conn.execute("SELECT COUNT(*) FROM run").fetchone()[0] == 1, \
            "the refusal deleted evidence"
    finally:
        conn.close()


def test_the_page_says_what_the_delete_control_removes(live):
    base, _path = live
    _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})
    page = _get(f"{base}/config")
    assert "Delete this project and its services" in page
    assert "Runs, snapshots and cases are never deleted here" in page


def test_remove_project_names_an_unknown_project(tmp_path):
    conn = db.connect(tmp_path / "unknown.db")
    try:
        with pytest.raises(services.UnknownProject):
            services.remove_project(conn, "no-such-project")
    finally:
        conn.close()


# --------------------------------------------------------------------------- AC3 boundary table

# TESTOPS-56 AC3. Every value is something a person or a pasted field could really hold, and every
# line says what the screen must do with it and why. This is the argument the rule can be had with:
# change a rule, and a line here has to change with it. The first eleven are the original ticket's
# values, the next fourteen the reviewer's, and the rest pin the boundary the two faults found.
BOUNDARY = [
    # --- the original ticket's eleven: ordinary configuration, all accepted
    ("jagobond/cotw-continuity", "accepted", "a repository coordinate: the '/' marks a path"),
    ("Jira board COTW", "accepted", "prose - whitespace means it is not one identifier"),
    ("RuckoldtAndRylander", "accepted", "one word and no credential word inside it"),
    ("cotw-continuity pipeline #2", "accepted", "prose around a project name"),
    ("mwinteringham/restful-booker-platform", "accepted", "a repository coordinate"),
    ("100.121.128.21", "accepted", "an IPv4 address: four digit parts"),
    ("localhost:8791", "accepted", "host:port, with no credential name before the ':'"),
    ("https://github.com/org/repo.git", "accepted", "a URL"),
    ("COTW", "accepted", "a board key"),
    ("TOPS", "accepted", "a Jira project key"),
    ("test password reset flow", "accepted", "prose: whitespace, so not one identifier"),
    # --- the reviewer's fourteen
    ("password-manager/tool", "accepted", "a path; the '/' makes it a coordinate, not a name"),
    ("secrets-service", "accepted", "'secrets' is not the credential word 'secret'"),
    ("vault.internal", "accepted", "a hostname"),
    ("vault-prod", "accepted", "a hostname with a short compound part"),
    ("https://vault.internal:8200/v1/secret", "accepted", "a URL; a trailing 'secret' has no value"),
    ("skypoint-dashboard", "accepted", "a name that merely begins with 'sk'"),
    ("docs/token-refresh.md", "accepted", "a path"),
    ("token-bucket-limiter", "accepted",
     "three parts whose last is not the credential word: a compound technical name"),
    ("my-password-manager", "accepted", "three parts, credential word in the middle: a tool name"),
    ("client_secret_manager", "accepted", "three parts, credential word in the middle: a module name"),
    ("Bearer token rotation work", "refused",
     "it begins with an authorization scheme; refused by shape, and called out in the report"),
    ("AKIA-reviews-team", "accepted", "the prefix needs a 16-character upper-case key body"),
    ("xoxb-not-a-token", "accepted", "the prefix needs a digit-and-hyphen token body"),
    ("ghp_only_a_document_path", "accepted",
     "a real ghp_ body is one unbroken base62 run; this carries underscores"),
    # --- the boundary itself, in both directions
    ("my-password", "refused", "two parts, the last a credential word: a credential named plainly"),
    ("an-api-token", "refused", "the last part is the credential word itself"),
    ("client-secret", "refused", "two parts, the last a credential word, the other no suffix"),
    ("password", "refused", "a bare credential word names the thing itself"),
    ("password-manager", "accepted", "'manager' is a technical suffix: the name of a tool"),
    ("token-bucket", "accepted", "'bucket' is a technical suffix: the rate-limiting algorithm"),
    ("password=hunter2", "refused", "a pasted name=value pair"),
    ("ghp_" + "aB3dE5fG7hJ9kL2mN4pQ6rS8tU0vW1xY2zAb", "refused",
     "a real GitHub classic token: ghp_ and 36 base62 characters"),
    ("AKIA" + "Q7FZ2K9M4T8X1B6N", "refused", "a real AWS key ID: AKIA and 16 upper-case characters"),
    ("xoxb-" + "123456789012-1234567890123-Ab3dE5fG7hJ9", "refused",
     "a real Slack token: xoxb-, digit segments and a base62 tail"),
    ("glpat-" + "aB3dE5fG7hJ9kL2mN4pQ", "refused", "a real GitLab PAT: glpat- and a 20-character run"),
    ("sk-" + "aB3dE5fG7hJ9kL2mN4pQ6rS8tU0vW1xY2zAbAb3dE5fG", "refused",
     "a real sk- key: sk- and an unbroken 32+ character run"),
    ("github_pat_" + "aB3dE5fG7hJ9kL2mN4pQAb", "refused",
     "a real fine-grained GitHub token"),
]


@pytest.mark.parametrize("value,verdict,why", BOUNDARY,
                         ids=[f"{verdict}-{value[:24]}" for value, verdict, _why in BOUNDARY])
def test_the_false_positive_boundary_is_pinned(value, verdict, why):
    """AC3: the rule is argued with here, not guessed at. ``why`` is the one-line argument."""
    reason = services._looks_like_secret(value)
    if verdict == "accepted":
        assert reason is None, f"{value!r} was refused ({reason}); the table says: {why}"
        assert services.validate_settings({"name": value}) == {"name": value}
    else:
        assert reason is not None, f"{value!r} was accepted; the table says: {why}"
        assert value not in reason, "refusing a value must not become a way to print it"
        with pytest.raises(services.ConfigError):
            services.validate_settings({"name": value})


def test_the_boundary_table_covers_both_verdicts_and_at_least_twenty_five_values():
    assert len(BOUNDARY) >= 25
    assert {verdict for _v, verdict, _r in BOUNDARY} == {"accepted", "refused"}


# --------------------------------------------------------------------------- AC1 real bodies

# Each real token is built from the body its format actually issues - the length and the charset are
# asserted before the refusal is asked for, so this table cannot decay into "a prefix and some
# characters". No value here is a live credential.
REAL_TOKENS = [
    ("AKIA" + "Q7FZ2K9M4T8X1B6N", re.compile(r"AKIA[A-Z0-9]{16}"), "AKIA"),
    ("ASIA" + "Y34FZKBOKMUTVV7A", re.compile(r"ASIA[A-Z0-9]{16}"), "ASIA"),
    ("ghp_" + "aB3dE5fG7hJ9kL2mN4pQ6rS8tU0vW1xY2zAb", re.compile(r"ghp_[A-Za-z0-9]{36}"), "ghp_"),
    ("gho_" + "aB3dE5fG7hJ9kL2mN4pQ6rS8tU0vW1xY2zAb", re.compile(r"gho_[A-Za-z0-9]{36}"), "gho_"),
    ("ghs_" + "aB3dE5fG7hJ9kL2mN4pQ6rS8tU0vW1xY2zAb", re.compile(r"ghs_[A-Za-z0-9]{36}"), "ghs_"),
    ("xoxb-" + "123456789012-1234567890123-Ab3dE5fG7hJ9",
     re.compile(r"xoxb-[0-9]{12}-[0-9]{13}-[A-Za-z0-9]{12}"), "xoxb-"),
    ("xoxp-" + "123456789012-1234567890123-Ab3dE5fG7hJ9",
     re.compile(r"xoxp-[0-9]{12}-[0-9]{13}-[A-Za-z0-9]{12}"), "xoxp-"),
    ("glpat-" + "aB3dE5fG7hJ9kL2mN4pQ", re.compile(r"glpat-[A-Za-z0-9_-]{20}"), "glpat-"),
    ("github_pat_" + "aB3dE5fG7hJ9kL2mN4pQAb",
     re.compile(r"github_pat_[A-Za-z0-9]{22}"),
     "github_pat_"),
    ("sk-" + "aB3dE5fG7hJ9kL2mN4pQ6rS8tU0vW1xY2zAbAb3dE5fG",
     re.compile(r"sk-[A-Za-z0-9]{40,}"), "sk-"),
]


@pytest.mark.parametrize("token,shape,prefix", REAL_TOKENS,
                         ids=[f"{prefix}-real-body" for _t, _s, prefix in REAL_TOKENS])
def test_a_real_token_of_each_format_is_still_refused(token, shape, prefix):
    """AC1: the prefix is qualified, not dropped - the format's own body still trips the rule."""
    assert shape.fullmatch(token), "this probe must be the format's real body, or it proves nothing"
    reason = services._looks_like_secret(token)
    assert reason is not None, f"a real-shaped {prefix} token was read as configuration"
    assert prefix in reason, "the refusal should name the format it recognised"
    assert token not in reason, "refusing a token must not print it"
    with pytest.raises(services.ConfigError):
        services.validate_settings({"board": token})


PREFIX_LOOKALIKES = {
    "AKIA-reviews-team": "AKIA",
    "xoxb-not-a-token": "xoxb-",
    "ghp_only_a_document_path": "ghp_",
    "glpat-migration-plan": "glpat-",
}


@pytest.mark.parametrize("value,prefix", sorted(PREFIX_LOOKALIKES.items()))
def test_a_prefix_followed_by_ordinary_words_is_not_a_refusal(value, prefix):
    """AC1: the first characters alone are not a shape - these are names that begin with one."""
    assert value.startswith(prefix)
    assert services._looks_like_secret(value) is None, \
        f"{value!r} was refused for its first characters alone"


# --------------------------------------------------------------------------- AC2 the scoped rule

def test_the_short_identifier_rule_accepts_a_tool_name_and_refuses_a_credential_name():
    """AC2: the class is scoped deliberately, and the two ends of it are pinned here."""
    assert services._looks_like_secret("token-bucket-limiter") is None, \
        "a rate-limiting algorithm is not a credential"
    reason = services._looks_like_secret("my-password")
    assert reason is not None, "a plain credential name was accepted"
    assert "credential word" in reason


def test_the_scoped_rule_over_http_stores_the_tool_and_refuses_the_credential(live):
    base, _path = live
    _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})

    status, body = _post(f"{base}/config/services",
                         _service_fields(name="token-bucket-limiter"))
    assert status == 200, body
    assert "token-bucket-limiter" in _get(f"{base}/config")

    status, body = _post(f"{base}/config/services", _service_fields(name="my-password"))
    assert status == 400, "a bare credential name was stored"
    assert "credential" in body
    assert "my-password" not in body


# --------------------------------------------------------------------------- AC4 unknown keys

# A real-shaped GitHub token, used to prove an unknown key is refused *and* not echoed. It is a
# synthetic body, not a live credential.
PROBE_TOKEN = "ghp_" + "aB3dE5fG7hJ9kL2mN4pQ6rS8tU0vW1xY2zAb"


def test_an_unknown_settings_key_is_refused_with_a_reason_and_nothing_is_stored(live):
    """AC4: the form layer refuses an unseen key instead of dropping it, so nothing bypasses the
    screen by being in a field this build does not know."""
    base, path = live
    _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})

    status, body = _post(f"{base}/config/services",
                         _service_fields(a_field_added_next_year=PROBE_TOKEN))

    assert status == 400, "an unseen settings key was accepted"
    assert "a_field_added_next_year" in body, "the refusal does not name the field it refused"
    assert "refused" in body, "the refusal does not say it was refused rather than dropped"
    assert PROBE_TOKEN not in body, "the refusal page printed the value"

    conn = db.connect(path)
    try:
        assert services.list_services(conn, "team") == [], "a refused configuration reached the store"
    finally:
        conn.close()
    raw = path.read_bytes()
    assert b"a_field_added_next_year" not in raw, "the unseen key was written to the store"
    assert PROBE_TOKEN.encode() not in raw, "the refused value was written to the store"


def test_an_unknown_settings_key_is_refused_even_when_its_value_is_ordinary(live):
    """The refusal is about the key, not about what it happens to hold: a key nobody screens
    must not be accepted at all."""
    base, _path = live
    _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})
    status, body = _post(f"{base}/config/services",
                         _service_fields(a_field_added_next_year="COTW-PROJ-KEY-1"))
    assert status == 400
    assert "a_field_added_next_year" in body


# --------------------------------------------------------------------------- AC5 bypass re-run

# The TESTOPS-51 AC5 bypass table, re-run attempt by attempt after the tuning. Commented with what
# the previous ticket observed, so a change in one of them is visible rather than implied.
def test_the_tesops_51_bypass_table_is_still_closed(live):
    base, path = live
    _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})

    # 1. Unknown settings key carrying a token. Was: 303 with the value silently dropped.
    status, body = _post(f"{base}/config/services",
                         _service_fields(a_field_added_next_year=PROBE_TOKEN))
    assert status == 400, "an unknown key still reaches a redirect"

    # 2. A project named like a credential.
    status, body = _post(f"{base}/config/projects", {"slug": "password", "name": "Password"})
    assert status == 400, "a project named like a credential was created"

    # 3. Leading whitespace before the token in the repository field.
    status, body = _post(f"{base}/config/services", _service_fields(repo=" " + PROBE_TOKEN))
    assert status == 400, "leading whitespace defeated the screen"

    # 4. A trailing newline after the token in the name field.
    status, body = _post(f"{base}/config/services", _service_fields(name=PROBE_TOKEN + "\n"))
    assert status == 400, "a trailing newline defeated the screen"

    # 5. Double-URL-encoded token in the board field. Was: 303, storing the literal percent string,
    #    which nothing decodes - not a credential in the store. Still not one, and never the token.
    encoded = "".join(f"%{ord(ch):02X}" for ch in PROBE_TOKEN)
    status, body = _post(f"{base}/config/services",
                         _service_fields(type="jira_board", role="", board=encoded))
    assert status == 200, "the encoded value was refused (a change from the last ticket)"
    conn = db.connect(path)
    try:
        boards = [row.settings.get("board") for row in services.list_services(conn, "team")
                  if "board" in row.settings]
    finally:
        conn.close()
    assert boards == [encoded], \
        "the encoded value was decoded into a credential before it was stored"
    assert PROBE_TOKEN not in boards

    # 6. Mixed-case credential word.
    status, body = _post(f"{base}/config/services", _service_fields(name="PaSsWoRd=hunter2"))
    assert status == 400, "changing case defeated the screen"

    # 7. Value split across fields: the name of a credential in one, its value in the next.
    status, body = _post(f"{base}/config/services",
                         _service_fields(name="token=", board="hunter2"))
    assert status == 400, "splitting the pair across fields defeated the screen"

    # Nothing the attempts carried is in the store, and the only rows are the ones that were stored
    # as ordinary configuration.
    raw = path.read_bytes()
    for probe in (PROBE_TOKEN, "hunter2", "password"):
        assert probe.encode() not in raw, f"{probe!r} reached the store"


def test_a_real_token_is_refused_on_every_settings_field_over_http(live):
    """AC1/AC5 at the route a person uses: each field the form knows meets the same screen."""
    base, _path = live
    _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})
    for fields in (_service_fields(repo=PROBE_TOKEN),
                   _service_fields(type="jira_board", role="", board=PROBE_TOKEN),
                   _service_fields(type="jira_board", role="", host=PROBE_TOKEN),
                   _service_fields(type="ado_pipeline", role="", org=PROBE_TOKEN),
                   _service_fields(type="ado_pipeline", role="", ado_project=PROBE_TOKEN)):
        status, body = _post(f"{base}/config/services", fields)
        assert status == 400, f"a real token was accepted: {sorted(fields)}"
        assert PROBE_TOKEN not in body
