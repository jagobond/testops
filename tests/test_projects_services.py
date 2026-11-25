"""TESTOPS-38: a project is a group of services, and a user sets it up without touching code.

Every test writes to ``tmp_path``. The AC2 baseline is a v3 store captured at the commit before this
ticket (``fixtures/projects_services/before_v3.db``); opening it here runs the migration, and the
pages it renders are compared with the bytes captured before the change.
"""
from __future__ import annotations

import json
import shutil
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from testops import cli, config, pipeline, services, sources
from testops.collectors import github
from testops.config import Repo
from testops.store import db
from testops.web import app

FIXTURES = Path(__file__).parent / "fixtures" / "projects_services"
COMMIT = "c" * 40
FEATURE = {
    "features/panel.feature":
        "Feature: Panel\n\n  Scenario: the panel is served\n    Given a user\n    Then the panel is served\n",
    "steps/panel.cs":
        '[Then("the panel is served")]\npublic void ThenPanel() { new HttpClient().Get("/"); }\n',
}


# --------------------------------------------------------------------------- helpers

def _migrated_store(tmp_path) -> Path:
    """A copy of the pre-ticket store, opened once so the migration runs."""
    target = tmp_path / "store.db"
    shutil.copyfile(FIXTURES / "before_v3.db", target)
    db.connect(target).close()
    return target


def _connect_factory(path: Path):
    """A ``db.connect`` that ignores its argument, for modules that open the default store."""
    real = db.connect                     # captured before the caller patches it
    def connect(_path=None):
        return real(path)
    return connect


def _server(handler, monkeypatch):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def _get(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.status, response.read().decode("utf-8")


def _post(url: str, fields: dict) -> tuple[int, str]:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:      # a refusal is a page, and the test reads it
        return exc.code, exc.read().decode("utf-8")


def _fake_collect(files=None):
    files = dict(FEATURE if files is None else files)
    collected_files = {}
    for path, text in files.items():
        rule = config.kind_for(path)
        assert rule is not None, path
        collected_files[path] = (github.blobs.put(text.encode("utf-8")), rule.kind)
    collected = github.Collected(COMMIT, collected_files)
    return lambda repo, token, role="": collected


# --------------------------------------------------------------------------- AC1 / AC2

def test_the_migration_brings_the_projects_across_with_their_services(tmp_path):
    store = _migrated_store(tmp_path)
    conn = db.connect(store)
    try:
        projects = {row["slug"]: row for row in services.list_projects(conn)}
        demo_product = services.list_services(conn, "demo-product")
        req = services.list_services(conn, "demo-service")
        # Existing rows keep their project column and it holds the slug - nothing rewritten.
        assert conn.execute("SELECT DISTINCT project FROM case_ ORDER BY project").fetchall()
    finally:
        conn.close()

    assert {"demo-product", "demo-service"} <= set(projects)
    assert {s.type for s in demo_product} == {"git_repo", "jira_board", "ado_pipeline"}
    assert {s.settings.get("repo") for s in demo_product if s.type == "git_repo"} == {
        "example-org/demo-product", "example-org/demo-product-tests"}
    assert [s.settings.get("board") for s in demo_product if s.type == "jira_board"] == ["DEMO"]
    assert sorted(s.settings.get("pipeline_id") for s in demo_product
                  if s.type == "ado_pipeline") == [2, 4]
    assert [s.settings.get("repo") for s in req if s.type == "git_repo"] == [
        "reqnroll/demo-service", "reqnroll/demo-service"]
    assert not [s for s in req if s.type in ("jira_board", "ado_pipeline")]


def test_every_case_page_and_the_indexes_are_byte_identical_after_the_migration(tmp_path,
                                                                               monkeypatch):
    store = _migrated_store(tmp_path)
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["cases"]) >= 10

    # The pages carry an age sentence; the baseline was rendered with the same frozen clock.
    monkeypatch.setattr(app, "age", lambda iso: "a fixed time ago")
    conn = db.connect(store)
    try:
        assert app.index(conn) == (FIXTURES / "index.html").read_bytes()
        assert app.runs_index(conn) == (FIXTURES / "runs.html").read_bytes()
        for case_id in manifest["cases"]:
            rendered = app.case_page(conn, case_id)
            assert rendered == (FIXTURES / f"{case_id}.html").read_bytes(), case_id
    finally:
        conn.close()


def test_the_migration_does_not_seed_over_a_store_that_already_has_projects(tmp_path):
    path = tmp_path / "team.db"
    conn = db.connect(path)
    services.add_project(conn, "team", "Team")
    conn.close()
    conn = db.connect(path)          # a second open is a no-op for configuration
    try:
        assert [row["slug"] for row in services.list_projects(conn)] == ["team"]
    finally:
        conn.close()


# --------------------------------------------------------------------------- AC8

def test_the_cli_resolves_a_project_from_the_store_and_refuses_an_unknown_slug_by_name(
        tmp_path, monkeypatch, capsys):
    path = _migrated_store(tmp_path)
    monkeypatch.setattr(cli.db, "connect", _connect_factory(path))
    assert cli.main(["runs", "--project", "demo-product"]) == 0

    with pytest.raises(SystemExit) as refused:
        cli.main(["runs", "--project", "no-such-project"])
    message = str(refused.value)
    assert "unknown project 'no-such-project'" in message
    assert "demo-product" in message


# --------------------------------------------------------------------------- AC5

def test_settings_refuse_a_credential_and_say_why(tmp_path):
    conn = db.connect(tmp_path / "secrets.db")
    services.add_project(conn, "team", "Team")
    try:
        for secret in ("ghp_" + "a1B2c3D4e5F6g7H8i9J0" * 2,
                       "Bearer abc123", "my-password", "the-secret", "an-api-token"):
            with pytest.raises(services.ConfigError) as refused:
                services.add_service(conn, "team", "git_repo", "test", "tests",
                                     {"repo": "o/tests", "credential": secret})
            assert "credential" in str(refused.value).lower()
            assert secret not in str(refused.value)       # refusing must not print the secret

        with pytest.raises(services.ConfigError) as named:
            services.validate_settings({"token": "anything"})
        assert "named like a credential" in str(named.value)

        # Hosts, paths, board keys and repository coordinates are what settings are for.
        assert services.validate_settings({"host": "https://example.atlassian.net",
                                           "board": "DEMO", "path": "/mnt/data/repo",
                                           "repo": "owner/name"})
    finally:
        conn.close()


# --------------------------------------------------------------------------- AC4 / AC7

def _project_with_services(conn, slug, *, product=True, jira=False):
    services.add_project(conn, slug, slug.title())
    if product:
        services.add_service(conn, slug, "git_repo", "product", "product repo",
                             {"repo": "owner/product"})
    services.add_service(conn, slug, "git_repo", "test", "test repo", {"repo": "owner/tests"})
    if jira:
        services.add_service(conn, slug, "jira_board", "", "board",
                             {"board": "TEAM"})


def test_a_project_with_no_jira_board_says_so_per_service_on_the_page(tmp_path, monkeypatch):
    path = tmp_path / "store.db"
    conn = db.connect(path)
    _project_with_services(conn, "team")
    project = services.project_from_store(conn, "team")
    conn.close()
    assert any(state["name"] == "Jira board" and state["state"] == "absent"
               for state in project.service_states)

    monkeypatch.setattr(pipeline.db, "connect", _connect_factory(path))
    monkeypatch.setattr(pipeline.blobs, "BLOB_DIR", tmp_path / "blobs")
    monkeypatch.setattr(pipeline.github, "collect", _fake_collect())
    result = pipeline.run_level_fitness(project, token="unused")

    conn = db.connect(path)
    try:
        page = app.run_page(conn, result.run_id).decode("utf-8")
        meta = json.loads(conn.execute("SELECT meta FROM snapshot WHERE id = ?",
                                       (result.snapshot_id,)).fetchone()[0])
    finally:
        conn.close()
    assert "Jira board" in page
    assert "absent" in page
    assert "no Jira board is configured for this project" in page
    assert any(state["name"] == "Jira board" for state in meta["service_states"])


def test_a_project_with_tests_and_no_product_is_not_assessable_with_the_reason(tmp_path,
                                                                              monkeypatch):
    path = tmp_path / "store.db"
    conn = db.connect(path)
    _project_with_services(conn, "team", product=False)
    assessment = services.assess_services(conn, "team")
    project = services.project_from_store(conn, "team")
    conn.close()
    assert assessment.state == services.NOT_ASSESSABLE
    assert "product" in assessment.reason
    assert project.product is None

    monkeypatch.setattr(pipeline.db, "connect", _connect_factory(path))
    monkeypatch.setattr(pipeline.blobs, "BLOB_DIR", tmp_path / "blobs")
    monkeypatch.setattr(pipeline.github, "collect", _fake_collect())
    result = pipeline.run_level_fitness(project, token="unused")   # must not crash

    assert result.stats["surfaces_state"] == "not_assessable"
    conn = db.connect(path)
    try:
        meta = json.loads(conn.execute("SELECT meta FROM snapshot WHERE id = ?",
                                       (result.snapshot_id,)).fetchone()[0])
    finally:
        conn.close()
    assert meta["project_assessment"]["state"] == "not_assessable"
    assert "no product git repository" in meta["project_assessment"]["reason"]
    assert any(state["name"] == "Product repository" and state["state"] == "absent"
               for state in meta["service_states"])


def test_each_service_records_its_own_last_consulted_state(tmp_path, monkeypatch):
    path = tmp_path / "store.db"
    conn = db.connect(path)
    _project_with_services(conn, "team", jira=True)
    project = services.project_from_store(conn, "team")
    conn.close()

    monkeypatch.setattr(pipeline.db, "connect", _connect_factory(path))
    monkeypatch.setattr(pipeline.blobs, "BLOB_DIR", tmp_path / "blobs")
    monkeypatch.setattr(pipeline.github, "collect", _fake_collect())
    pipeline.run_level_fitness(project, token="unused")

    conn = db.connect(path)
    try:
        rows = {s.name: s for s in services.list_services(conn, "team")}
    finally:
        conn.close()
    assert rows["board"].last_state == "policy"
    assert "no Jira connector" in (rows["board"].last_reason or "")
    assert rows["test repo"].last_state == "available"
    assert rows["test repo"].last_consulted_at


# --------------------------------------------------------------------------- AC6

def test_the_app_runs_against_a_temporary_data_directory_outside_the_checkout(tmp_path,
                                                                              monkeypatch):
    data = tmp_path / "mounted-volume"
    data.mkdir()
    shutil.copyfile(FIXTURES / "before_v3.db", data / "testops.db")
    monkeypatch.setenv("TESTOPS_DATA", str(data))
    assert config.settings().db_path == data / "testops.db"
    assert config.settings().blob_dir == data / "blobs"

    httpd, base = _server(app.Handler, monkeypatch)
    try:
        status, body = _get(f"{base}/case/case-page-01")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert status == 200
    assert "What could not be checked" in body


def test_the_default_settings_are_relative_not_host_paths():
    settings = config.Settings.from_env({})
    assert not settings.db_path.is_absolute()
    assert not settings.blob_dir.is_absolute()
    assert config.Settings.from_env({"TESTOPS_DATA": "/mnt/testops"}).db_path == \
        Path("/mnt/testops/testops.db")


# --------------------------------------------------------------------------- AC3

def test_projects_and_services_are_added_edited_and_removed_without_a_restart(tmp_path,
                                                                             monkeypatch):
    path = tmp_path / "ui.db"
    monkeypatch.setattr(app.db, "connect", _connect_factory(path))
    httpd, base = _server(app.Handler, monkeypatch)
    try:
        status, page = _get(f"{base}/config")
        assert status == 200
        assert "Add a project" in page

        # A whole project, then a service inside it.
        assert _post(f"{base}/config/projects", {"slug": "newteam", "name": "New Team"})[0] == 200
        status, page = _post(f"{base}/config/services",
                             {"project": "newteam", "type": "git_repo", "role": "test",
                              "name": "API tests", "repo": "acme/api-tests"})
        assert status == 200 and "API tests" in page

        conn = db.connect(path)
        try:
            service = services.list_services(conn, "newteam")[0]
        finally:
            conn.close()

        # Edit it - same page, no restart.
        status, page = _post(f"{base}/config/service/{service.id}",
                             {"project": "newteam", "type": "git_repo", "role": "test",
                              "name": "Renamed tests", "repo": "acme/api-tests"})
        assert status == 200 and "Renamed tests" in page

        # A credential is refused, and the refusal explains itself.
        status, page = _post(f"{base}/config/services",
                             {"project": "newteam", "type": "jira_board", "role": "",
                              "name": "board", "board": "TEAM",
                              "host": "Bearer abcdef"})
        assert status == 400
        assert "never a token" in page or "credential" in page.lower()

        status, page = _post(f"{base}/config/service/{service.id}/delete", {})
        assert status == 200 and "Renamed tests" not in page

        # There is deliberately no login on this local tool.
        assert 'type="password"' not in page
    finally:
        httpd.shutdown()
        httpd.server_close()
