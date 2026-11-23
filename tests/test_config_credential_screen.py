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
