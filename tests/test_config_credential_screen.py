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
CLASSIC_BODY = "aB3dE5fG7hJ9kL2mN4pQ6rS8tU0vW1xY2zAb"          # 36: today's GitHub classic body
FINE_BODY = "aB3dE5fG7hJ9kL2mN4pQAb"                            # 22: fine-grained, first segment
FINE_TAIL = "aB3dE5fG7hJ9kL2mN4pQ6rS8tU0vW1xY2zAb" + "aB3dE5fG7hJ9kL2mN4pQ" + "abc"  # 59
SLACK_TAIL = "aB3dE5fG7hJ9kL2mN4pQ6rS8"                        # 24: Slack secret segment
ISSUED_TOKENS = {
    "ghp_" + CLASSIC_BODY: "ghp_",
    "gho_" + CLASSIC_BODY: "gho_",
    "ghs_" + CLASSIC_BODY: "ghs_",
    "github_pat_" + FINE_BODY + "_" + FINE_TAIL: "github_pat_",
    "sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0": "sk-",
    "AKIA" + "ABCDEFGHIJKLMNOP": "AKIA",
    "xoxb-" + "012345678901" + "-" + "0123456789012" + "-" + SLACK_TAIL: "xoxb-",
    "xoxp-" + "012345678901" + "-" + "0123456789012" + "-" + SLACK_TAIL: "xoxp-",
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

@pytest.mark.parametrize("value", [PROBE, "ghp_" + CLASSIC_BODY, PEM_BLOCK, JWT])
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
    ("secrets-service", "accepted", "the credential word is not the head: a service name"),
    ("vault.internal", "accepted", "a hostname"),
    ("vault-prod", "accepted", "a hostname with a short compound part"),
    ("https://vault.internal:8200/v1/secret", "accepted", "a URL; a trailing 'secret' has no value"),
    ("skypoint-dashboard", "accepted", "a name that merely begins with 'sk'"),
    ("docs/token-refresh.md", "accepted", "a path"),
    ("token-bucket-limiter", "accepted",
     "three parts whose last is not the credential word: a compound technical name"),
    ("my-password-manager", "accepted", "three parts, credential word in the middle: a tool name"),
    ("client_secret_manager", "accepted", "three parts, credential word in the middle: a module name"),
    ("Bearer token rotation work continues", "accepted",
     "prose: the scheme is only a header when a single unbroken value is the whole remainder"),
    ("AKIA-reviews-team", "accepted", "the prefix needs a 16-character upper-case key body"),
    ("«redacted:xox…»", "accepted", "the prefix needs digit segments and a 24-character tail"),
    ("ghp_only_a_document_path", "accepted",
     "a real ghp_ body is one unbroken base62 run; this carries underscores"),
    # --- TESTOPS-59 AC3: the boundary states itself by structure
    ("my-password", "refused", "a determiner and a credential head: a particular credential"),
    ("an-api-token", "refused", "a determiner and a credential head: a particular credential"),
    ("the-secret", "refused", "a determiner and a credential head: a particular credential"),
    ("password", "refused", "a bare credential word names the thing itself"),
    ("passwords", "refused", "the plural names the things themselves"),
    ("session-token", "accepted", "a compound naming a kind of token: the credential word is a head"),
    ("vault-token", "accepted",
     "the same grammatical shape as session-token: a compound noun naming a kind of token, with no "
     "determiner"),
    ("client-secret", "accepted",
     "a compound naming a kind of secret, like session-token; a determiner is what marks an instance"),
    ("shhh-secret", "accepted", "a compound noun whose head is a credential word: a label"),
    ("password-list", "accepted",
     "a collection name; plural and singular credential words are matched alike"),
    ("passwords-list", "accepted", "the same value as password-list, spelled with the plural"),
    ("password-manager", "accepted", "the credential word is not the head: the name of a tool"),
    ("token-bucket", "accepted", "the credential word is not the head: a rate-limiting algorithm"),
    ("ghp_notes", "accepted",
     "below the GitHub classic floor (36); the prefix alone is not a shape"),
    ("github_pat_docs", "accepted", "below the fine-grained floor (82): a documentation name"),
    # --- TESTOPS-61 AC1/AC2/AC3/AC5: every part is read, a statement is not a label, and a cut-off
    #     prefix is refused with its reason rather than accepted silently.
    ("this-is-not-a-password", "accepted",
     "a clause: 'is' is a finite verb, so the determiner belongs to the sentence, not to a credential"),
    ("this-is-my-password", "accepted", "a clause for the same reason: it states something"),
    ("xox-not-a-slack-token", "accepted",
     "a denial with a subject before 'not' and the credential word as its complement"),
    ("not-a-password", "refused",
     "a denial fragment: no subject before 'not', so it states nothing"),
    # --- TESTOPS-62 AC1/AC2/AC3/AC4: a word in the name is not a clause. The exemption holds only
    #     for a predication about the credential word, and the one word in two classes is settled by
    #     precedence (`no` is a determiner, never a negator that excuses).
    ("my-password-is-here", "refused",
     "the credential word is the subject before the verb, not its complement: it labels an instance"),
    ("the-token-is-abcd1234", "refused",
     "the credential word is the subject before the verb, not its complement"),
    ("this-token-was-leaked", "refused",
     "the credential word is the subject before the verb, not its complement"),
    ("my-secret-has-value", "refused",
     "the credential word is the subject before the verb, not its complement"),
    ("has-my-token", "refused", "a verb fragment: nothing sits before 'has', so there is no subject"),
    ("is-my-password", "refused", "a verb fragment: nothing sits before 'is', so there is no subject"),
    ("never-the-api-token", "refused",
     "a denial fragment: nothing sits before 'never', so there is no subject"),
    ("x-not-a-token-but-abcdef", "refused",
     "the credential word is not the final complement of the predicate: no clause"),
    ("not-my-password", "refused",
     "a denial fragment with no subject before 'not': the determiner labels an instance"),
    ("no-password-yet", "refused",
     "'no' is read as a determiner, so it marks an instance and cannot excuse it as a negator"),
    ("acme-no-password", "refused",
     "'no' is a determiner by precedence: it never supplies the predicate that would excuse it"),
    ("acme-their-no-password", "refused",
     "'no' is a determiner and no predicate is made about the credential word"),
    ("acme-not-password", "accepted",
     "a denial with a subject ('acme') and the credential word as the final complement"),
    ("acme-their-password", "refused",
     "a possessive in a middle position names a particular credential as plainly as my-password"),
    ("their-password", "refused", "a possessive and a credential head: an instance"),
    ("acme-our-token", "refused", "a possessive in a middle position: an instance"),
    ("my-old-api-token", "refused",
     "a determiner, two modifiers and a credential head: an instance label"),
    ("acme-their-prod-db-password", "refused",
     "a possessive anywhere is enough: the parts state nothing, so the name is a label"),
    ("prod-db-password", "accepted", "no determiner or possessive anywhere: a type name"),
    ("github_pat_" + FINE_BODY, "refused",
     "a real prefix with 22 of its 82 characters: a cut-off paste, refused with that reason"),
    ("ghp_" + "aB3dE5fG7hJ9kL2mN4p", "refused",
     "a real prefix with 19 of its 36 characters: a cut-off paste"),
    ("AKIA" + "Q7FZ2K9M4T8X1B", "refused",
     "a real prefix with 15 of its 16 characters: a cut-off paste"),
    ("glpat-migration-plan", "accepted", "a lowercase word chain, not a token body"),
    # --- AC2: prose with ordinary words must still be accepted
    ("the password reset flow is documented", "accepted", "prose"),
    ("the api key rotation schedule is quarterly", "accepted", "prose"),
    ("secret scanning runs on every pull request", "accepted", "prose"),
    ("session tokens expire after thirty minutes", "accepted", "prose"),
    ("our refresh token job runs nightly", "accepted", "prose"),
    ("read the private key exchange note first", "accepted", "prose"),
    ("passwords are rotated quarterly by the platform team", "accepted", "prose"),
    ("client secrets live in the environment, not here", "accepted", "prose"),
    ("vault-token-helper wrapper script", "accepted", "a command name in prose"),
    ("auth token cache warming at startup", "accepted", "prose"),
    ("leveraging the token budget is a management concern", "accepted", "prose"),
    # --- the refusals the screen still owes
    ("password=hunter2", "refused", "a pasted name=value pair"),
    ("ghp_" + CLASSIC_BODY, "refused",
     "a real GitHub classic token: ghp_ and a 36-character base62 body"),
    ("AKIA" + "Q7FZ2K9M4T8X1B6N", "refused", "a real AWS key ID: AKIA and 16 upper-case characters"),
    ("xoxb-" + "012345678901-0123456789012-" + SLACK_TAIL, "refused",
     "a real Slack token: xoxb-, two digit segments and a 24-character tail"),
    ("glpat-" + "aB3dE5fG7hJ9kL2mN4pQ", "refused", "a real GitLab PAT: glpat- and a 20-character run"),
    ("sk-" + "aB3dE5fG7hJ9kL2mN4pQ6rS8tU0vW1xY2zAbAb3dE5fG", "refused",
     "a real sk- key: sk- and an unbroken 40-character run"),
    ("github_pat_" + FINE_BODY + "_" + FINE_TAIL, "refused",
     "a real fine-grained GitHub token: 22 characters, an underscore, 59 more"),
    # --- and the leak this ticket closes: a real token inside a sentence
    ("the key is " + "ghp_" + CLASSIC_BODY, "refused",
     "a real token pasted in prose is still a token (TESTOPS-59 AC1)"),
    ("aws id AKIA" + "Q7FZ2K9M4T8X1B6N", "refused", "a real AWS key ID inside a sentence"),
    # --- TESTOPS-63: `key` - the commonest credential word - is screened in the instance position.
    #     Qualification is what makes it a credential word; the branch it enters then decides the
    #     verdict, exactly as it does for `secret` (`my-secret` refused, `client-secret` accepted).
    ("the-api-key-is-xyz", "refused",
     "`key` is the subject of the verb, not its complement: the name labels an instance"),
    ("the-api-key", "refused", "a determiner and a qualified `key` head: a particular credential"),
    ("my-key", "refused", "a possessive and the credential word `key` as the head: an instance"),
    ("my-signing-key", "refused",
     "a qualifier makes `key` the credential word and the possessive makes it an instance"),
    ("key", "accepted",
     "a bare `key` with no determiner names a configuration slot, not a particular credential"),
    ("signing-key", "accepted",
     "qualified but determiner-less: a kind name, the same branch that accepts client-secret"),
    ("key-metrics", "accepted", "`key` qualifies the head `metrics`: a measurement, not a credential"),
    ("primary-key", "accepted", "a database index, with no determiner: a kind name"),
    ("foreign-key", "accepted", "the same grammatical shape as primary-key"),
    ("key-value-store", "accepted", "a store of pairs; `key` is a qualifier and the head is `store`"),
    ("sorting-keys", "accepted", "a collection name: `key` is a qualifier, not the head"),
    ("keyboard", "accepted", "one word, and not the word `key`: nothing here is a credential"),
    ("keynote", "accepted", "one word, and not the word `key`"),
    ("keycloak", "accepted", "one word, and not the word `key`"),
    ("keystore", "accepted", "one word, and not the word `key`"),
    ("hotkey", "accepted", "one word, and not the word `key`"),
    ("monkey", "accepted", "one word that merely ends in the letters k-e-y"),
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


def test_the_boundary_table_covers_both_verdicts_and_more_than_forty_values():
    """TESTOPS-59 AC5: the table grows past 40 values and still argues both verdicts."""
    assert len(BOUNDARY) > 40, f"the boundary table holds only {len(BOUNDARY)} values"
    assert {verdict for _v, verdict, _r in BOUNDARY} == {"accepted", "refused"}


# --------------------------------------------------------------------------- AC1 real bodies

# Each real token is built from the body its format actually issues - the length and the charset are
# asserted before the refusal is asked for, so this table cannot decay into "a prefix and some
# characters". No value here is a live credential.
REAL_TOKENS = [
    ("AKIA" + "Q7FZ2K9M4T8X1B6N", re.compile(r"AKIA[A-Z0-9]{16}"), "AKIA"),
    ("ASIA" + "Y34FZKBOKMUTVV7A", re.compile(r"ASIA[A-Z0-9]{16}"), "ASIA"),
    ("ghp_" + CLASSIC_BODY, re.compile(r"ghp_[A-Za-z0-9]{36}"), "ghp_"),
    ("gho_" + CLASSIC_BODY, re.compile(r"gho_[A-Za-z0-9]{36}"), "gho_"),
    ("ghs_" + CLASSIC_BODY, re.compile(r"ghs_[A-Za-z0-9]{36}"), "ghs_"),
    ("ghp_" + CLASSIC_BODY + "Ab3d", re.compile(r"ghp_[A-Za-z0-9]{40}"), "ghp_"),
    ("github_pat_" + FINE_BODY + "_" + FINE_TAIL,
     re.compile(r"github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}"), "github_pat_"),
    ("xoxb-" + "012345678901" + "-" + "0123456789012" + "-" + SLACK_TAIL,
     re.compile(r"xoxb-[0-9]{12}-[0-9]{13}-[A-Za-z0-9]{24}"), "xoxb-"),
    ("xoxp-" + "012345678901" + "-" + "0123456789012" + "-" + SLACK_TAIL,
     re.compile(r"xoxp-[0-9]{12}-[0-9]{13}-[A-Za-z0-9]{24}"), "xoxp-"),
    ("glpat-" + "aB3dE5fG7hJ9kL2mN4pQ", re.compile(r"glpat-[A-Za-z0-9_-]{20}"), "glpat-"),
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


# TESTOPS-59 AC1: detection is a **search**, not a prefix match. Each probe is a real format body
# wrapped in the sentence a paste really arrives in, with the punctuation a paste carries.
def test_a_real_token_pasted_inside_a_sentence_is_refused():
    probes = [
        ("the key is " + "ghp_" + CLASSIC_BODY, "ghp_"),
        ("our bot token is " + "gho_" + CLASSIC_BODY + ", rotate it", "gho_"),
        ("aws id AKIA" + "Q7FZ2K9M4T8X1B6N", "AKIA"),
        ("the slack app uses xoxp-012345678901-0123456789012-" + SLACK_TAIL + " here", "xoxp-"),
        ("the pat glpat-aB3dE5fG7hJ9kL2mN4pQ is in the vault", "glpat-"),
        ("openai key sk-" + "aB3dE5fG7hJ9kL2mN4pQ6rS8tU0vW1xY2zAbAb3dE5fG" + " was rotated",
         "sk-"),
        ("fine-grained " + "github_pat_" + FINE_BODY + "_" + FINE_TAIL + " rotated", "github_pat_"),
        ("the key is " + "ghp_" + CLASSIC_BODY + ".", "ghp_"),
    ]
    for value, prefix in probes:
        reason = services._looks_like_secret(value)
        assert reason is not None, f"a token pasted in prose was accepted: {prefix}"
        assert prefix in reason, "the refusal should name the format it found"
        assert value not in reason, "refusing a token must not print it"

    assert services._looks_like_secret("the jwt is " + JWT) is not None, \
        "a JWT pasted inside a sentence was accepted"
    assert services._looks_like_secret("paste this:\n" + PEM_BLOCK) is not None, \
        "a PEM block pasted inside a value was accepted"
    assert services._looks_like_secret("export token=«secret» then run it") is not None, \
        "a name=value pair inside a sentence was accepted"


def test_scanning_inside_a_string_does_not_refuse_ordinary_sentences():
    """AC2: the other side of AC1 - prose that merely mentions a credential is accepted."""
    for value in ("the key is in the vault", "the token is rotated monthly by CI",
                  "ask the platform team for a key", "paste the token into the environment"):
        assert services._looks_like_secret(value) is None, f"prose was refused: {value!r}"


def test_a_prose_wrapped_token_is_refused_over_http(live):
    """AC1 at the route a person uses: the repository field carries a sentence, not a coordinate."""
    base, path = live
    _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})
    wrapped = "the key is " + "ghp_" + CLASSIC_BODY
    status, body = _post(f"{base}/config/services", _service_fields(name=wrapped))
    assert status == 400, "a token pasted inside a sentence was stored"
    assert "ghp_" in body and wrapped not in body
    conn = db.connect(path)
    try:
        assert services.list_services(conn, "team") == []
    finally:
        conn.close()


# TESTOPS-59 AC3: the identifier boundary is structural, and singular/plural are decided together.
def test_the_identifier_boundary_is_structural_not_a_word_list():
    assert services._looks_like_secret("session-token") is None, \
        "a compound naming a kind of token was refused"
    assert services._looks_like_secret("vault-token") is None, \
        "the same grammatical shape as session-token was refused"
    assert services._looks_like_secret("my-password") is not None, \
        "a determiner plus a credential head was accepted"
    assert services._looks_like_secret("my password") is None, \
        "prose is not an identifier"


def test_singular_and_plural_credential_words_are_decided_together():
    assert services._looks_like_secret("password-list") is None
    assert services._looks_like_secret("passwords-list") is None
    assert services._looks_like_secret("passwords") is not None, \
        "the plural of a bare credential word names the things themselves"
    assert services._looks_like_secret("my-passwords") is not None


# TESTOPS-61 AC1: the rule reads every part, not the first and the last.
def test_a_determiner_or_possessive_in_any_position_names_an_instance():
    for value in ("my-password", "acme-their-password", "acme-our-token", "their-password",
                  "my-old-api-token", "acme-their-prod-db-password"):
        assert services._looks_like_secret(value) is not None, \
            f"{value!r} names a particular credential and was accepted"
    # The other direction: without a determiner the same head names a kind, wherever the word sits.
    for value in ("session-token", "vault-token", "prod-db-password", "password-list"):
        assert services._looks_like_secret(value) is None, f"{value!r} names a kind and was refused"


# TESTOPS-61 AC2 / TESTOPS-62 AC1/AC2: a predication about a credential is not a label for one. The
# deciding rule is stated in services._is_predication: a subject before a predicate head, and the
# credential word as the complement after it. A verb or a negator anywhere is not enough.
def test_a_statement_about_a_credential_is_not_an_instance_label():
    assert services._looks_like_secret("this-is-not-a-password") is None, \
        "a sentence-name was refused for opening with a determiner"
    assert services._looks_like_secret("this-is-my-password") is None, "a clause is not a label"
    assert services._looks_like_secret("xox-not-a-slack-token") is None, \
        "a denial with a subject and the credential word as its complement is not a label"
    # TESTOPS-62 AC1: the credential word as the *subject* of the verb is a label, not a statement.
    for value in ("my-password-is-here", "the-token-is-abcd1234", "this-token-was-leaked",
                  "my-secret-has-value"):
        assert services._looks_like_secret(value) is not None, \
            f"{value!r} was excused although the credential word is the verb's subject"
    # AC2: a fragment is not a clause, and the credential word must be the final complement.
    for value in ("has-my-token", "is-my-password", "never-the-api-token", "no-password-yet",
                  "x-not-a-token-but-abcdef"):
        assert services._looks_like_secret(value) is not None, \
            f"{value!r} was excused although it is a fragment, not a clause"
    assert services._looks_like_secret("acme-their-prod-db-password") is not None, \
        "the boundary: the same possessive with no predicate is a label"


# TESTOPS-62 AC3: precedence, stated once and pinned. `no` is a determiner before it is a negator, so
# it takes a name into the instance test and never supplies the excuse. A true negator still needs a
# subject before it and the credential word as its complement.
def test_a_word_in_two_classes_cannot_satisfy_both_tests():
    assert "no" in services._DETERMINERS and "no" in services._NEGATORS
    assert "no" not in services._PREDICATE_HEADS, \
        "`no` must not be a predicate head: it can never excuse what it just marked as an instance"
    for value in ("no-password-yet", "acme-no-password", "acme-their-no-password"):
        assert services._looks_like_secret(value) is not None, \
            f"{value!r} was excused by `no`, which is read as a determiner"
    # The same shape with a true negator and a subject is a denial and is accepted.
    assert services._looks_like_secret("acme-not-password") is None
    assert services._looks_like_secret("never-the-api-token") is not None, \
        "a true negator with no subject is still a fragment"


# TESTOPS-63 AC1: `key` is the commonest credential word in real repositories and it was in no
# vocabulary at all, so `the-api-key-is-xyz` was screened by nothing and accepted. It is a credential
# word when qualified (`api-key`, `signing-key`, ...) or bare after a determiner/possessive
# (`the-key`, `my-key`), and it enters the same branches as every other credential word - the same
# refusals, the same reason.
@pytest.mark.parametrize("value", [
    "my-key", "their-key", "our-key", "the-key", "my_keys", "the_keys", "their_key",
    "the-api-key", "the-private-key", "my-secret-key", "the-signing-key", "the-access-key",
    "the-auth-key", "the-ssh-key", "the-encryption-key", "my-deploy-key",
])
def test_key_with_a_determiner_or_qualifier_names_an_instance(value):
    reason = services._looks_like_secret(value)
    assert reason is not None, f"{value!r} names a particular credential and was accepted"
    assert reason == services._looks_like_secret("my-password"), \
        "a key must be refused by the same branch, with the same reason, as every credential word"
    with pytest.raises(services.ConfigError):
        services.validate_settings({"name": value})


def test_key_as_the_subject_of_a_verb_is_a_label_not_a_clause():
    """TESTOPS-63 AC1: the T62 grammar applies unchanged - `key` is not a free pass to a verb."""
    assert services._looks_like_secret("the-api-key-is-xyz") is not None, \
        "`key` is the subject of `is`, not its complement, so the name labels an instance"
    assert services._looks_like_secret("my-key-is-here") is not None
    # The other direction: a predication about a key is still a statement, not a label.
    assert services._looks_like_secret("this-is-not-a-key") is None


# TESTOPS-63 AC2: `key` is not a credential word where it means something else. Each is pinned
# here on its own, so the boundary cannot drift into refusing an honest name.
KEY_MEANS_SOMETHING_ELSE = [
    "key-value-store", "keyboard", "keynote", "keycloak", "monkey", "primary-key",
    "foreign-key", "hotkey", "keystore", "key-metrics", "sorting-keys",
    "key", "keys",
]


@pytest.mark.parametrize("value", KEY_MEANS_SOMETHING_ELSE)
def test_key_that_means_something_else_is_accepted(value):
    assert services._looks_like_secret(value) is None, \
        f"{value!r} means something other than a credential and was refused"
    assert services.validate_settings({"name": value}) == {"name": value}


def test_key_is_not_a_credential_word_in_a_pair_or_a_settings_field_name():
    """TESTOPS-63: qualification is applied in the instance rule only, and this is why.

    A `name=value` pair and a settings field name are named by a word, not by a position: `sort_keys=`
    is an honest setting, and `board_keys` is exactly the field the refusal message says settings may
    hold. Refusing those to catch `my-key=` would be the false positive the ticket forbids.
    """
    for honest in ("sort_keys=True", "sorting_keys=asc", "board_keys", "primary_key=id"):
        assert services._looks_like_secret(honest) is None, f"{honest!r} was refused"
        assert services.validate_settings({"sorting_keys": honest}) == {"sorting_keys": honest}
    assert services.validate_settings({"board_keys": "COTW"}) == {"board_keys": "COTW"}
    # A `key` stated with its determiner *and* a value is a pasted credential, and the pair branch is
    # where that shape is caught - the instance rule cannot see a value after '='.
    for pasted in ("my-key=hunter2", "the-key: abc123", "their_keys=v"):
        reason = services._looks_like_secret(pasted)
        assert reason is not None, f"{pasted!r} is a pasted key and was accepted"
        assert pasted not in reason, "refusing a pasted key must not print it"
    # And prose that mentions a key with a colon stays prose: only a hyphen or underscore joins the
    # two, so the determiner rule cannot reach into a sentence.
    for prose in ("the key: it is in the vault", "ask the platform team for the key, then paste it"):
        assert services._looks_like_secret(prose) is None, f"prose was refused: {prose!r}"


# TESTOPS-63 AC3: the false-positive risk is asymmetric, so the measurement is written down. The
# twelve T62 refusals keep their verdicts, the twenty T59 ordinary values and every AC2 value stay
# accepted - and one new refusal of an honest name is a failure, not a cost.
T62_REFUSED = [
    "my-password-is-here", "the-token-is-abcd1234", "this-token-was-leaked", "my-secret-has-value",
    "has-my-token", "is-my-password", "never-the-api-token", "no-password-yet",
    "x-not-a-token-but-abcdef", "acme-no-password", "acme-their-no-password", "not-a-password",
]
T59_ORDINARY = [
    "the token is validated in middleware", "our password policy is documented",
    "Bearer tokens are refreshed hourly", "secrets are rotated weekly",
    "jwt.decode lives in lib/auth.py", "no token needed for this endpoint",
    "docs/how-to-reset-your-password.md", "pat-notes.md", "gh_workflows/", "akia-notes",
    "xox-not-a-slack-token", "the private key is in vault", "my-password-manager",
    "session-token", "vault-token", "password-list", "passwords-list", "token-refresh-service",
    "the-token-service", "my-secret-store",
]


def test_the_key_vocabulary_refuses_no_honest_name_from_the_earlier_probe_sets():
    assert len(T62_REFUSED) == 12 and len(T59_ORDINARY) == 20, "the probe sets are transcribed whole"
    refused = {value: services._looks_like_secret(value) for value in T62_REFUSED}
    assert all(reason is not None for reason in refused.values()), \
        f"a T62 refusal was lost: {[v for v, r in refused.items() if r is None]}"
    accepted = {value: services._looks_like_secret(value) for value in T59_ORDINARY}
    new = [value for value, reason in accepted.items() if reason is not None]
    assert not new, f"an honest T59 name is now refused: {new}"
    newly_refused = [value for value in KEY_MEANS_SOMETHING_ELSE
                     if services._looks_like_secret(value) is not None]
    assert not newly_refused, f"a name where `key` means something else is refused: {newly_refused}"


def test_the_key_probes_are_refused_over_http_at_the_name_field(live):
    """TESTOPS-63: the hole was at the route a person uses, so the fix is pinned there too."""
    base, path = live
    _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})
    for value in ("the-api-key-is-xyz", "the-api-key", "my-key"):
        status, body = _post(f"{base}/config/services", _service_fields(name=value))
        assert status == 400, f"{value!r} was stored"
        assert value not in body, "the refusal page printed the value"
    conn = db.connect(path)
    try:
        assert services.list_services(conn, "team") == []
    finally:
        conn.close()


# TESTOPS-61 AC3: a cut-off prefix is refused with a reason that says it is too short, and the
# alphabet - not the length alone - is what keeps a word-shaped body a name.
def test_a_truncated_prefix_is_refused_and_the_reason_says_it_is_too_short():
    value = "github_pat_" + FINE_BODY
    reason = services._looks_like_secret(value)
    assert reason is not None, "a 22-character fine-grained paste was accepted silently"
    assert "github_pat_" in reason, "the reason should name the prefix it recognised"
    assert "too short" in reason, "the reason should say why it was refused"
    assert value not in reason, "the refusal printed the paste"
    assert services._looks_like_secret("github_pat_docs") is None, \
        "a lower-case word after the same prefix is a name, not a fragment"
    assert services._looks_like_secret("ghp_notes") is None


def test_a_truncated_fine_grained_prefix_is_refused_over_http(live):
    base, path = live
    _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})
    value = "github_pat_" + FINE_BODY
    status, body = _post(f"{base}/config/services", _service_fields(name=value))
    assert status == 400, "a cut-off fine-grained paste was stored"
    assert "github_pat_" in body and "too short" in body
    assert value not in body, "the refusal page printed the paste"
    conn = db.connect(path)
    try:
        assert services.list_services(conn, "team") == []
    finally:
        conn.close()


# TESTOPS-59 AC4: every prefix has a floor and a ceiling from the format's real body.
def test_every_prefix_carries_a_floor_and_a_ceiling():
    for prefix, _pattern, floor, ceiling, _words in services._TOKEN_FORMATS:
        assert 0 < floor <= ceiling, f"{prefix} has no usable body range"
    # `ghp_notes` is below the classic floor and is a name, because its body is a word.
    assert services._looks_like_secret("ghp_notes") is None
    # TESTOPS-61 AC3: a fragment of a real body below the floor is a cut-off paste, and is refused
    # with a reason that says so - no silent green tick on a recognisable prefix.
    cut_off = services._looks_like_secret("ghp_" + "aB3dE5fG7hJ9kL2mN4p")
    assert cut_off is not None and "too short" in cut_off
    # A fine-grained token is 82 body characters, not 22: a 22-character paste is a truncation, and
    # TESTOPS-61 AC3 refuses it by name rather than accepting it silently.
    truncated = services._looks_like_secret("github_pat_" + FINE_BODY)
    assert truncated is not None and "too short" in truncated
    assert services._looks_like_secret("github_pat_" + FINE_BODY + "_" + FINE_TAIL) is not None
    # And a body past the ceiling is not the format's body.
    assert services._looks_like_secret("ghp_" + "aB3d" * 11) is None
    assert services._looks_like_secret("AKIA" + "Q7FZ2K9M4T8X1B6NEXTRA") is None


# --------------------------------------------------------------------------- AC2 the scoped rule

def test_the_short_identifier_rule_accepts_a_tool_name_and_refuses_a_credential_name():
    """AC2: the class is scoped deliberately, and the two ends of it are pinned here."""
    assert services._looks_like_secret("token-bucket-limiter") is None, \
        "a rate-limiting algorithm is not a credential"
    reason = services._looks_like_secret("my-password")
    assert reason is not None, "a plain credential name was accepted"
    assert "credential" in reason


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
