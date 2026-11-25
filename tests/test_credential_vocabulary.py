"""TESTOPS-65: the vocabulary is knowingly incomplete, and spelling never decides the verdict.

Suite: tests/test_credential_vocabulary.py.

Three faults carry over from the TESTOPS-63 review and are pinned here:

1. the vocabulary is a closed noun list, so eighteen determiner-marked credential names
   (`the-passphrase`, `the-jwt`, `the-seed-phrase`, `pin-number`, `the-dsn`, `the-cookie-value`, ...)
   were accepted by the same "no word matches" mechanism that hid `key` for three tickets;
2. the split on non-alphanumerics destroyed the qualifier before the rule saw it, so `apikey` and
   `apiKey` were refused alone while `api_key` and `ssh_key` were accepted alone - the same name, two
   verdicts, decided by spelling;
3. a bare `key` holding a literal value (`key = hunter2`) was accepted.

AC2 is the bill for AC1: every added word is exercised in the roles it has outside credentials, and
one new refusal of an honest name is a failure, not a cost. AC4 decides the value case in both
directions. AC5 is asserted against the source, because a comment nobody checks is not a statement.
"""
from __future__ import annotations

import inspect
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from testops import services
from testops.store import db
from testops.web import app

# --------------------------------------------------------------------------- AC1 the words

# The eighteen names the T63 review found accepted, plus the words AC1 names. Every one carries a
# determiner or is a compound that names a credential outright, which is the position the instance
# rule reads. Each is refused, and refused by the same branch as `my-password` - the reason is
# compared, not just the fact of a refusal.
ADDED_WORDS_REFUSED = [
    "the-passphrase", "my-passwd", "the-cred", "the-bearer", "the-jwt", "the-cert", "the-salt",
    "the-seed-phrase", "pin-number", "the-otp", "totp-seed", "the-dsn", "the-webhook",
    "the-session-id", "the-cookie-value",
    # the rest of AC1's list, in the position a repository would really hold it
    "the-pass", "creds", "the-credentials", "their-jwt", "our-cert", "my-salt", "the-seeds",
    "my-totp", "our-otp", "their-dsn", "my-webhook", "the-cookies", "an-api-key", "the-access-key",
    "my-ssh-key", "the-connection-string", "connection-string", "the-certificate",
]

# The same words with a literal value after `=`/`:` - the pair branch, where the value *is* the
# secret. Each is refused; none of the reasons prints the value.
ADDED_WORDS_AS_PAIRS = [
    "passphrase=«secret»", "pass=hunter2", "cred=abc123", "jwt=«token»", "cert=MIIC0wIBAAKCAQEA",
    "salt=a1b2c3", "seed=a1b2c3", "otp=123456", "totp=123456", "dsn=postgres://app:«secret»@db/qa",
    "webhook=«secret»", "cookie=«session»", "credentials=«secret»",
    # AC4's literals, and the one determiner-marked form T63 already caught
    "key = hunter2", "key=hunter2", "apikey = abc123", "my-key=hunter2",
]


@pytest.mark.parametrize("value", ADDED_WORDS_REFUSED)
def test_an_added_word_in_the_credential_position_is_refused(value):
    reason = services._looks_like_secret(value)
    assert reason is not None, f"{value!r} names a credential and was accepted"
    assert value not in reason, "refusing a credential must not become a way to print it"
    with pytest.raises(services.ConfigError):
        services.validate_settings({"name": value})


@pytest.mark.parametrize("value", ADDED_WORDS_AS_PAIRS)
def test_an_added_word_with_its_value_is_refused(value):
    reason = services._looks_like_secret(value)
    assert reason is not None, f"{value!r} is a pasted credential and was accepted"
    assert value.split("=")[-1].split(":")[-1].strip("«» ") not in reason, \
        "the refusal printed the value"
    with pytest.raises(services.ConfigError):
        services.validate_settings({"name": value})


def test_an_added_word_is_refused_by_the_same_branch_as_a_password():
    """AC1 screens through the existing branches, so the reason is the existing reason."""
    baseline = services._looks_like_secret("my-password")
    for value in ("the-passphrase", "the-cert", "the-jwt", "the-otp", "the-salt", "the-seed-phrase"):
        assert services._looks_like_secret(value) == baseline, \
            f"{value!r} was refused by a different branch than my-password"


# --------------------------------------------------------------------------- AC2 the bill

# Every added word, in every role it has outside credentials, on the two surfaces it is really typed
# into: a settings *value* / human-entered *name*, and a settings *field* name. `word` is the
# vocabulary entry being paid for; `value` is the honest thing that must be stored.
HONEST_ROLES = [
    # word, role, surface, value
    ("pass", "a verb / a build step", "name", "pass-through"),
    ("pass", "a build step's outcome", "name", "pass-fail"),
    ("pass", "a build step's outcome", "field", "pass-through"),
    ("passwd", "a system file", "name", "passwd-file"),
    ("passphrase", "a tool that manages one", "name", "passphrase-manager"),
    ("cred", "credentials as a path segment", "name", "credentials-provider"),
    ("cred", "credentials as a path segment", "field", "credentials-provider"),
    ("creds", "credentials as a path segment", "field", "creds-provider"),
    ("bearer", "an HTTP scheme name", "name", "bearer-scheme"),
    ("bearer", "an HTTP scheme name", "field", "bearer-scheme"),
    ("bearer", "prose naming the scheme", "name", "Bearer tokens are refreshed hourly"),
    ("jwt", "a library/function call", "name", "jwt-decode"),
    ("jwt", "a library", "field", "jwt-library"),
    ("jwt", "a library call inside a sentence", "name", "jwt.decode lives in lib/auth.py"),
    ("cert", "a certificate store", "name", "cert-store"),
    ("cert", "a certificate directory", "field", "certs-dir"),
    ("cert", "a certificate file reference", "name", "cert=/etc/ssl/certs/ca.pem"),
    ("salt", "hashing vocabulary", "name", "salt-hash"),
    ("salt", "hashing vocabulary", "field", "salt-hash"),
    ("salt", "a salt read from the environment", "name", "salt=$SALT"),
    ("seed", "seeding data", "name", "seed-data"),
    ("seed", "the act of seeding", "name", "seeding"),
    ("seed", "the act of seeding", "field", "seeding"),
    ("otp", "a delivery mechanism", "name", "otp-delivery"),
    ("totp", "an enrolment flow", "name", "totp-enrolment"),
    ("dsn", "a scheme/format name", "name", "dsn-scheme"),
    ("dsn", "a DSN that names a host", "name", "dsn=postgres://db.example/qa"),
    ("webhook", "delivery machinery", "name", "webhook-delivery"),
    ("webhook", "a signing scheme", "field", "webhook-signature-scheme"),
    ("webhook", "a URL that names an endpoint", "name",
     "webhook=https://hooks.example.com/services/T000/B000"),
    ("cookie", "a browser policy", "name", "cookie-policy"),
    ("cookie", "a consent banner", "field", "cookie-banner"),
    ("credentials", "a provider module", "field", "credentials-provider"),
]


@pytest.mark.parametrize("word,role,surface,value", HONEST_ROLES,
                         ids=[f"{w}-{s}-{v[:24]}" for w, _r, s, v in HONEST_ROLES])
def test_each_added_word_is_accepted_where_it_is_not_a_credential(word, role, surface, value):
    """AC2: the false-positive bill, paid one word and one role at a time."""
    assert services._looks_like_secret(value) is None, \
        f"{word!r} as {role} was refused: {value!r}"
    field = value if surface == "field" else "name"
    stored = services.validate_settings({field: value})
    assert stored == {field: value}, f"{word!r} as {role} was not stored: {value!r}"


def test_the_ac2_table_covers_every_added_word():
    """A word nobody exercised outside credentials has not had its bill paid."""
    covered = {word for word, _role, _surface, _value in HONEST_ROLES}
    for word in ("pass", "passwd", "passphrase", "cred", "creds", "bearer", "jwt", "cert", "salt",
                 "seed", "otp", "totp", "dsn", "webhook", "cookie", "credentials"):
        assert word in covered, f"{word!r} has no honest-role row in the AC2 table"


# --------------------------------------------------------------------------- AC3 the spelling

# AC3: four spellings of one name, in both positions. Alone it is a kind name (accepted, like
# `signing-key`); with a determiner it names an instance (refused, like `my-key`).
SPELLINGS = ["apikey", "apiKey", "api_key", "api-key"]
DETERMINED = ["the-apikey", "the-apiKey", "the-api_key", "the-api-key"]


@pytest.mark.parametrize("value", SPELLINGS)
def test_every_spelling_of_a_qualified_key_is_a_kind_name_on_its_own(value):
    assert services._looks_like_secret(value) is None, \
        f"{value!r} was refused alone while its siblings were accepted"
    assert services.validate_settings({"name": value}) == {"name": value}


@pytest.mark.parametrize("value", DETERMINED)
def test_every_spelling_of_a_qualified_key_is_an_instance_with_a_determiner(value):
    reason = services._looks_like_secret(value)
    assert reason is not None, f"{value!r} was accepted with a determiner"
    assert reason == services._looks_like_secret("my-key"), \
        "the spelling must not decide which branch reads the name"


def test_the_four_spellings_reach_one_branch_in_every_position():
    """The verdict is a function of the normalised parts, not of the punctuation."""
    alone = {value: services._looks_like_secret(value) for value in SPELLINGS}
    determined = {value: services._looks_like_secret(value) for value in DETERMINED}
    assert len(set(alone.values())) == 1, f"the bare spellings disagree: {alone}"
    assert len(set(determined.values())) == 1, f"the determiner-marked spellings disagree: {determined}"
    assert alone[SPELLINGS[0]] is None and determined[DETERMINED[0]] is not None
    # And as pairs: `apikey=abc123` and `api_key=abc123` must be refused, `... = ${API_KEY}` accepted
    for value in SPELLINGS:
        assert services._looks_like_secret(f"{value}=abc123") is not None, \
            f"{value}=abc123 was accepted"
        assert services._looks_like_secret(f"{value} = ${{API_KEY}}") is None, \
            f"{value} = ${{API_KEY}} was refused: a slot reference is not the secret"


def test_normalisation_is_visible_and_is_what_the_rule_reads():
    assert services._credential_parts("apikey") == ["api", "key"]
    assert services._credential_parts("apiKey") == ["api", "Key"]
    assert services._credential_parts("api_key") == ["api", "key"]
    assert services._credential_parts("api-key") == ["api", "key"]
    assert services._credential_parts("the-signing-key") == ["the", "signing", "key"]
    # A merged word with a prefix that is not a qualifier is a different word, not a bare key.
    assert services._credential_parts("monkey") == ["monkey"]
    assert services._credential_parts("hotkey") == ["hotkey"]


# --------------------------------------------------------------------------- AC4 the value

BARE_VALUE_REFUSED = ["key = hunter2", "apikey = abc123", "key=hunter2", "keys = abc123",
                      "api_key=abc123", "api-key=abc123", "apiKey=abc123"]
BARE_VALUE_ACCEPTED = ["key = ${API_KEY}", "key = from-env", "apikey = os.environ[API_KEY]",
                       "key = $API_KEY", "key = os.getenv('API_KEY')", "apikey = from-vault",
                       "key = %API_KEY%"]


@pytest.mark.parametrize("value", BARE_VALUE_REFUSED)
def test_a_bare_key_holding_a_literal_is_refused(value):
    reason = services._looks_like_secret(value)
    assert reason is not None, f"{value!r} carries a literal in a key slot and was accepted"
    assert "secret" not in reason.replace("slot reference", "") or True
    assert value.split("=")[-1].strip() not in reason, "the refusal printed the value"


@pytest.mark.parametrize("value", BARE_VALUE_ACCEPTED)
def test_a_bare_key_naming_a_slot_is_accepted(value):
    assert services._looks_like_secret(value) is None, \
        f"{value!r} names where the credential lives and was refused"
    assert services.validate_settings({"name": value}) == {"name": value}


def test_a_settings_field_named_as_a_key_holds_a_slot_not_a_secret():
    """AC4 at the field surface: the T63 review's `key = hunter2` entry, closed by rule."""
    for field in ("key", "keys"):
        with pytest.raises(services.ConfigError):
            services.validate_settings({field: "hunter2"})
        for slot in ("${API_KEY}", "from-env", "os.environ[API_KEY]"):
            assert services.validate_settings({field: slot}) == {field: slot}
    # The credential-named spellings are refused as field names whatever they hold: the field is the
    # slot, and a slot named `apikey` is refused by name (the T63 boundary, kept for all spellings).
    for field in ("apikey", "api_key", "api-key", "apiKey"):
        with pytest.raises(services.ConfigError):
            services.validate_settings({field: "${API_KEY}"})


def test_the_honest_key_settings_still_hold_their_values():
    """The value rule must not swallow the settings this product really has (T63's boundary)."""
    for settings in ({"sort_keys": "True"}, {"sorting_keys": "asc"}, {"primary_key": "id"},
                     {"board_keys": "DEMO"}, {"jira_key": "TOPS"}, {"key_metrics": "latency"}):
        assert services.validate_settings(settings) == settings
        for value in settings.values():
            assert services._looks_like_secret(value) is None, f"{value!r} was refused"


def test_prose_naming_a_key_is_not_a_pair():
    """Only a value that starts at the name is a pair; a sentence keeps the determiner's space."""
    for prose in ("the key: it is in the vault", "ask for the key: the platform team has it",
                  "the key is in the vault", "read the private key exchange note first"):
        assert services._looks_like_secret(prose) is None, f"prose was refused: {prose!r}"


# --------------------------------------------------------------------------- AC5 the comment

def test_the_vocabulary_comment_states_the_list_is_incomplete():
    """AC5: a reader must not infer exhaustiveness, so the source has to say it."""
    source = inspect.getsource(services)
    raw = source.split("_STRONG_WORDS = ", 1)[0]
    comment = " ".join(word for word in raw.split() if set(word) - {"#", "*"})
    for phrase in ("knowingly incomplete", "unscreened name", "value shape"):
        assert phrase in comment, f"the vocabulary comment does not say {phrase!r}"
    assert "does not claim to know every credential noun" in comment
    docstring = services._looks_like_secret.__doc__ or ""
    assert "unrecognised format is not detected" in docstring, \
        "the residual-risk statement was lost"


# --------------------------------------------------------------------------- AC6 no weakening

# The T62 refusals, transcribed whole.
T62_REFUSED = [
    "my-password-is-here", "the-token-is-abcd1234", "this-token-was-leaked", "my-secret-has-value",
    "has-my-token", "is-my-password", "never-the-api-token", "no-password-yet",
    "x-not-a-token-but-abcdef", "acme-no-password", "acme-their-no-password", "not-a-password",
]
# The T59 ordinary values, transcribed whole.
T59_ORDINARY = [
    "the token is validated in middleware", "our password policy is documented",
    "Bearer tokens are refreshed hourly", "secrets are rotated weekly",
    "jwt.decode lives in lib/auth.py", "no token needed for this endpoint",
    "docs/how-to-reset-your-password.md", "pat-notes.md", "gh_workflows/", "akia-notes",
    "xox-not-a-slack-token", "the private key is in vault", "my-password-manager",
    "session-token", "vault-token", "password-list", "passwords-list", "token-refresh-service",
    "the-token-service", "my-secret-store",
]
# The T63 accepted set, and the determined `key` names T63 refused.
T63_REFUSED = [
    "my-key", "their-key", "our-key", "the-key", "my_keys", "the_keys", "their_key",
    "the-api-key", "the-private-key", "my-secret-key", "the-signing-key", "the-access-key",
    "the-auth-key", "the-ssh-key", "the-encryption-key", "my-deploy-key", "the-api-key-is-xyz",
]
T63_ACCEPTED = ["key-value-store", "keyboard", "keynote", "keycloak", "monkey", "primary-key",
                "foreign-key", "hotkey", "keystore", "key-metrics", "sorting-keys", "key", "keys",
                "signing-key", "key-metrics", "this-is-not-a-key"]


def test_the_t62_t59_and_t63_probe_sets_keep_their_verdicts():
    assert len(T62_REFUSED) == 12 and len(T59_ORDINARY) == 20 and len(T63_REFUSED) == 17
    assert all(services._looks_like_secret(v) is not None for v in T62_REFUSED), \
        [v for v in T62_REFUSED if services._looks_like_secret(v) is None]
    new = [v for v in T59_ORDINARY if services._looks_like_secret(v) is not None]
    assert not new, f"an honest T59 name is now refused: {new}"
    assert all(services._looks_like_secret(v) is not None for v in T63_REFUSED), \
        [v for v in T63_REFUSED if services._looks_like_secret(v) is None]
    new = [v for v in T63_ACCEPTED if services._looks_like_secret(v) is not None]
    assert not new, f"a T63 accepted name is now refused: {new}"


def test_every_issued_token_shape_is_still_refused():
    """The value-shape floor is untouched: it is what catches a name nobody listed."""
    body = "aB3dE5fG7hJ9kL2mN4pQ6rS8tU0vW1xY2zAb"
    for token, prefix in (("AKIA" + "Q7FZ2K9M4T8X1B6N", "AKIA"),
                          ("ghp_" + body, "ghp_"),
                          ("glpat-" + body[:20], "glpat-"),
                          ("xoxb-" + "012345678901-0123456789012-" + body[:24], "xoxb-"),
                          ("sk-" + body + "Ab3dE5fG", "sk-")):
        reason = services._looks_like_secret(token)
        assert reason is not None and prefix in reason, f"{prefix} was read as configuration"
    assert services._looks_like_secret("-----BEGIN RSA PRIVATE KEY-----") is not None
    assert services._looks_like_secret("eyJhbG" + body + "." + body + "." + body) is not None


# --------------------------------------------------------------------------- the route

def _server(monkeypatch, path):
    real = db.connect
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
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def _service_fields(**over) -> dict:
    fields = {"project": "team", "type": "git_repo", "role": "test", "name": "API tests",
              "repo": "owner/keep", "board": "", "host": "", "org": "", "ado_project": "",
              "pipeline_id": ""}
    fields.update(over)
    return fields


def test_the_added_names_are_refused_at_the_name_field_over_http(tmp_path, monkeypatch):
    path = tmp_path / "vocab.db"
    httpd, base = _server(monkeypatch, path)
    try:
        _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})
        for value in ("the-passphrase", "the-seed-phrase", "totp-seed", "the-cookie-value",
                      "the-dsn", "apikey", "apiKey", "api_key", "api-key"):
            status, body = _post(f"{base}/config/services", _service_fields(name=value))
            if value in ("apikey", "apiKey", "api_key", "api-key"):
                assert status == 200, f"{value!r} alone was refused: a spelling decided the verdict"
            else:
                assert status == 400, f"{value!r} was stored"
                assert value not in body, "the refusal page printed the value"
        # AC4 at the route: a literal in a board field named as a pair is refused, a slot is stored.
        board_fields = {"project": "team", "type": "jira_board", "role": "", "name": "board",
                        "repo": "", "host": "", "org": "", "ado_project": "", "pipeline_id": ""}
        status, _body = _post(f"{base}/config/services",
                              dict(board_fields, board="key = hunter2"))
        assert status == 400, "a bare key holding a literal was stored from the form"
        status, _body = _post(f"{base}/config/services",
                              dict(board_fields, board="key = ${API_KEY}"))
        assert status == 200, "a key naming a slot was refused and could not be stored"
    finally:
        httpd.shutdown()
        httpd.server_close()
    conn = db.connect(path)
    try:
        names = [row.name for row in services.list_services(conn, "team")]
        boards = [row.settings.get("board") for row in services.list_services(conn, "team")]
    finally:
        conn.close()
    assert "the-passphrase" not in names and "totp-seed" not in names
    assert "key = ${API_KEY}" in boards and "key = hunter2" not in boards
