"""TESTOPS-44: the secret guard must err in neither direction, and must not echo what it refuses.

The guard failed twice in the TESTOPS-38 review. It **accepted** a complete AWS key in a free-text
field, because base64 - the most common credential encoding - contains ``/`` and any value containing
``/`` was exempt. It **refused** ``COTW-PROJ-KEY-0123456789-ABCDEFG``, a plausible project key, as
high-entropy. Both are pinned here.

AC2 is the one that matters most: a guard that refuses real configuration gets switched off, and a
switched-off guard protects nothing. Every value in ``CONFIGURATION`` is a thing somebody would
legitimately type into a settings field, and each is pinned so that tightening the guard cannot
silently break it.

AC3: a refusal is a page and a log line naming the field and the reason. Neither may contain the
value - refusing a secret must not become another way to print it.
"""
from __future__ import annotations

import base64
import logging
import random
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from testops import services
from testops.store import db
from testops.web import app

# The reviewer's probe, from the TESTOPS-38 review: a complete AWS access key.
AWS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

# Every one of these is configuration a person could type, and every one must be accepted.
CONFIGURATION = {
    "repo": "owner/repo",
    "board": "COTW-PROJ-KEY-0123456789-ABCDEFG",
    "host": "https://jira.example.com",
    "project": "PROJ",
    "correlation_id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
    "label": "thunderstorm",
}


def _forty_bytes_as_base64() -> str:
    """A deterministic stand-in for a random 40-byte secret, chosen to contain '/'."""
    for seed in range(1000):
        blob = base64.b64encode(random.Random(seed).randbytes(40)).decode("ascii")
        if "/" in blob:
            return blob
    raise AssertionError("no seed produced a base64 blob containing '/'")


def _server(monkeypatch, path):
    real = db.connect                      # captured before the caller patches it
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


# --------------------------------------------------------------------------- AC1

@pytest.mark.parametrize("blob", [AWS_KEY, _forty_bytes_as_base64()],
                         ids=["aws-key", "forty-random-bytes"])
def test_base64_is_refused_even_though_it_contains_a_slash(blob):
    """AC1: charset and length are checked before the '/' exemption, so base64 cannot hide in it."""
    assert "/" in blob, "this probe is worthless unless the value contains the exempt character"

    with pytest.raises(services.ConfigError) as refused:
        services.validate_settings({"board": blob})

    message = str(refused.value)
    assert "base64" in message
    assert "board" in message
    assert blob not in message, "refusing a secret must not print the secret"


def test_the_reviewers_aws_key_is_no_longer_stored(tmp_path):
    """The exact false negative the review found: a complete AWS key written into free text."""
    conn = db.connect(tmp_path / "secrets.db")
    try:
        services.add_project(conn, "team", "Team")
        with pytest.raises(services.ConfigError):
            services.add_service(conn, "team", "jira_board", "", "board", {"board": AWS_KEY})
        assert services.list_services(conn, "team") == [], "a refused value reached the store"
    finally:
        conn.close()


# --------------------------------------------------------------------------- AC2

@pytest.mark.parametrize("field,value", sorted(CONFIGURATION.items()))
def test_real_configuration_is_accepted(field, value):
    """AC2: pinned one by one, so tightening the guard cannot silently break configuration."""
    assert services._looks_like_secret(value) is None, f"{field} was read as a secret"
    assert services.validate_settings({field: value}) == {field: value}


def test_all_pinned_configuration_is_accepted_together():
    assert services.validate_settings(CONFIGURATION) == CONFIGURATION


def test_a_token_shaped_value_is_still_refused():
    """The positive control: accepting everything would pass the tests above and protect nothing."""
    with pytest.raises(services.ConfigError):
        services.validate_settings({"repo": "ghp_" + "a1B2c3D4e5F6g7H8i9J0" * 2})
    with pytest.raises(services.ConfigError):
        services.validate_settings({"org": "abcdef0123456789abcdef0123456789abcdef01"})


def test_the_configuration_page_accepts_a_structured_key_and_stores_it(tmp_path, monkeypatch):
    path = tmp_path / "ui.db"
    httpd, base = _server(monkeypatch, path)
    try:
        status, page = _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})
        assert status == 200
        status, page = _post(f"{base}/config/services",
                             {"project": "team", "type": "jira_board", "role": "",
                              "name": "COTW board",
                              "board": CONFIGURATION["board"],
                              "host": CONFIGURATION["host"]})
        assert status == 200, page
        assert "COTW board" in page
    finally:
        httpd.shutdown()
        httpd.server_close()

    conn = db.connect(path)
    try:
        services_ = services.list_services(conn, "team")
    finally:
        conn.close()
    assert len(services_) == 1
    assert services_[0].settings["board"] == "COTW-PROJ-KEY-0123456789-ABCDEFG"
    assert services_[0].settings["host"] == "https://jira.example.com"


def test_the_configuration_page_accepts_a_repository_coordinate(tmp_path, monkeypatch):
    path = tmp_path / "repo.db"
    httpd, base = _server(monkeypatch, path)
    try:
        _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})
        status, page = _post(f"{base}/config/services",
                             {"project": "team", "type": "git_repo", "role": "test",
                              "name": "API tests", "repo": "owner/repo"})
        assert status == 200, page
    finally:
        httpd.shutdown()
        httpd.server_close()

    conn = db.connect(path)
    try:
        assert [s.settings["repo"] for s in services.list_services(conn, "team")] == ["owner/repo"]
    finally:
        conn.close()


# --------------------------------------------------------------------------- AC3

def test_a_refusal_logs_the_field_and_the_reason_but_not_the_value(caplog):
    with caplog.at_level(logging.WARNING, logger="testops.services"):
        with pytest.raises(services.ConfigError):
            services.validate_settings({"board": AWS_KEY})

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "board" in logged
    assert "base64" in logged
    assert AWS_KEY not in logged, "the log printed the secret it refused"


def test_the_refusal_page_names_the_field_and_the_reason_but_not_the_value(tmp_path, monkeypatch,
                                                                          caplog):
    path = tmp_path / "refusal.db"
    httpd, base = _server(monkeypatch, path)
    try:
        _post(f"{base}/config/projects", {"slug": "team", "name": "Team"})
        with caplog.at_level(logging.WARNING, logger="testops.services"):
            status, body = _post(f"{base}/config/services",
                                 {"project": "team", "type": "jira_board", "role": "",
                                  "name": "board", "board": AWS_KEY})
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert status == 400
    assert "board" in body
    assert "base64" in body
    assert AWS_KEY not in body, "the refusal page printed the secret"

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "board" in logged and "base64" in logged
    assert AWS_KEY not in logged, "the log printed the secret"

    conn = db.connect(path)
    try:
        assert services.list_services(conn, "team") == []
    finally:
        conn.close()
