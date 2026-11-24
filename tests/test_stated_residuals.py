"""TESTOPS-69: the six small residuals the credential and guard threads left behind.

Suite: tests/test_stated_residuals.py.

Each of the six is either fixed and pinned here, or documented in the code as a stated limit and
pinned *as* a limit - the report says which, and why. None of them was a leak; each was a place where
a message or a rule was slightly less true than it read.

1. the tab licensed nothing, because it sat in the lookbehind's exclusion class by accident;
2. the inline-password floor was one line shape - encoded userinfo, whitespace-split userinfo and a
   password in the query string were not read;
3. "0 unreadable files" could print when git was never readable, because the count is
   difference-driven;
4. a committed build artefact rode the report-only channel with nothing but a count;
5. pruning was by name at any depth, so a tracked ``*.pyc`` or a tracked file under ``.venv`` was
   invisible;
6. a wrapped sentence whose next line begins ``Key:`` is read as configuration - kept as a stated
   limit, in the comment where the rule lives.

The guard tests drive ``attribute_differences`` with synthetic snapshots and use a disposable
repository in ``tmp_path``; nothing here touches the real checkout, the live store or port 8791.
"""
from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

from support import (RepoState, attribute_differences, repository_ignored_snapshot,
                     repository_snapshot)
from testops import services

BEFORE_HEAD = "1111111111111111111111111111111111111111"
AFTER_HEAD = "2222222222222222222222222222222222222222"


# ------------------------------------------------------------------ 1. the tab, decided on purpose

# AC2: a tab IS a line boundary, so a tab-separated settings row is refused. Before the ticket the
# tab was in the lookbehind's exclusion class by accident and licensed nothing.
TAB_SEPARATED_REFUSED = [
    "x\tkey = hunter2",
    "row\tkey\t=\thunter2",
    "auth\tnone\tkey = hunter2",
    "columns\tkeys = abc123",
]


@pytest.mark.parametrize("value", TAB_SEPARATED_REFUSED)
def test_a_tab_before_a_bare_key_pair_is_a_line_boundary(value):
    reason = services._looks_like_secret(value)
    assert reason is not None, f"{value!r} is a tab-separated settings row and was accepted as prose"
    assert "hunter2" not in reason and "abc123" not in reason, "the refusal printed the value"
    with pytest.raises(services.ConfigError):
        services.validate_settings({"name": value})


def test_a_tab_is_the_difference_and_a_space_is_not():
    """AC2: the decision is stated, not incidental. One tab refuses where one space is prose."""
    assert services._looks_like_secret("x\tkey = hunter2") is not None
    assert services._looks_like_secret("x key = hunter2") is None
    # And the tab-separated pair reaches the same branch as the bare key pair it is one of.
    assert services._looks_like_secret("x\tkey = hunter2") == services._looks_like_secret(
        "key = hunter2")


def test_the_tab_decision_is_written_where_the_rule_lives():
    """AC2: a reader of the pattern can see that the tab is a boundary on purpose."""
    source = inspect.getsource(services)
    before_pattern = source.split("_BARE_KEY_PAIR = ", 1)[0]
    comment = " ".join(before_pattern.split())
    assert "TESTOPS-69 AC2" in comment
    assert "tab IS a line boundary" in comment
    assert "by accident" in comment, "the comment must say what the old behaviour was"


# ------------------------------------------------------------------ 2. the inline-password floor

ENCODED_AND_SPLIT_REFUSED = [
    # the colon percent-encoded in the userinfo
    "postgres://app:p%40ssw0rd@db/qa",
    "postgres://app%3Ap%40ssw0rd@db/qa",
    # the same URL split by whitespace, as a wrapped settings table writes it
    "postgres://app : hunter2 @db/qa",
    "dsn = postgres://app : hunter2 @db/qa",
    # the secret in the query string rather than the userinfo
    "postgres://app@db/qa?password=x",
    "postgres://app@db/qa?sslmode=require&pwd=hunter2",
    "see https://ci.example.com/job?token=tok3n",
]


@pytest.mark.parametrize("value", ENCODED_AND_SPLIT_REFUSED)
def test_the_inline_password_floor_is_not_one_line_shape(value):
    reason = services._looks_like_secret(value)
    assert reason is not None, f"{value!r} carries a password in a URL and was accepted"
    assert "URL" in reason, "the reason should name the shape the reader has to change"
    for secret in ("pa55word", "p%40ssw0rd", "hunter2", "pwd", "tok3n"):
        assert secret not in reason, f"the refusal printed part of the value: {secret!r}"
    with pytest.raises(services.ConfigError):
        services.validate_settings({"name": value})


HONEST_ADDRESSES_ACCEPTED = [
    "postgres://app@db/qa",
    "postgres://app@db/qa?sslmode=require",
    "https://example.com/path",
    "https://vault.internal:8200/v1/secret",
    "localhost:8791",
]


@pytest.mark.parametrize("value", HONEST_ADDRESSES_ACCEPTED)
def test_a_url_with_no_secret_is_still_configuration(value):
    assert services._looks_like_secret(value) is None, f"{value!r} was refused"


def test_a_port_is_not_a_password():
    """The widened floor must not read `host:port` as userinfo - there is no '@' to close it."""
    assert services._looks_like_secret("https://host.internal:8080/job") is None
    assert services._looks_like_secret("https://host.internal:8080/job@2") is None


# ------------------------------------------------------------------ 3. git readable: yes/no

def test_the_summary_says_git_was_readable_on_a_pass():
    """AC3: the field is printed on pass as well as failure."""
    report = attribute_differences({}, {},
                                   before_state=RepoState(BEFORE_HEAD, {}),
                                   after_state=RepoState(BEFORE_HEAD, {}),
                                   commit_blobs=lambda _: {})
    assert report.failures == ()
    assert "git readable: yes" in report.summary()[0]


def test_a_run_where_git_was_never_readable_says_so_even_with_nothing_to_count():
    """AC3: the unreadable count is difference-driven, so the field is what carries the truth."""
    report = attribute_differences({}, {},
                                   before_state=RepoState(None, {}, readable=False),
                                   after_state=RepoState(None, {}, readable=False),
                                   commit_blobs=lambda _: {})
    assert report.failures == ()
    assert report.unreadable == ()
    line = report.summary()[0]
    assert "git readable: no" in line, "a guard that read no git must not read as a clean run"
    assert "0 unreadable files" in line


def test_a_git_failure_still_prints_the_field_beside_its_failure():
    before = {"a.txt": (1, "b1")}
    after = {"a.txt": (2, "b2")}
    report = attribute_differences(before, after,
                                   before_state=RepoState(None, {}, readable=False),
                                   after_state=RepoState(None, {}, readable=False),
                                   commit_blobs=lambda _: {})
    assert report.failures == ("a.txt",)
    assert "git readable: no" in report.failure_message()


def test_the_tree_it_could_not_read_also_reads_as_git_not_readable():
    """A corrupt object store is git's failure too: readable is no, not a silent yes."""
    report = attribute_differences({"a.txt": (1, "b1")}, {"a.txt": (2, "b2")},
                                   before_state=RepoState(BEFORE_HEAD, {"a.txt": "b1"}),
                                   after_state=RepoState(AFTER_HEAD, {"a.txt": "b2"}),
                                   commit_blobs=lambda _: None)
    assert report.git_readable is False
    assert "git readable: no" in report.failure_message()


def test_the_live_guard_reports_a_readable_repository(repo_guard):
    from support import guard_report

    report = guard_report(repo_guard)
    assert report.git_readable is True
    assert "git readable: yes" in report.summary()[0]


# --------------------------------------------------- 4. a committed artefact is not ignore churn

def test_a_path_a_commit_now_tracks_leaves_the_ignored_channel():
    """AC1/AC4 (residual 4): committed `build/gen.txt` is content, not report-only cache churn."""
    report = attribute_differences({}, {},
                                   before_state=RepoState(BEFORE_HEAD, {}),
                                   after_state=RepoState(AFTER_HEAD, {"build/gen.txt": "g1"}),
                                   commit_blobs=lambda commit: (
                                       {} if commit == BEFORE_HEAD else
                                       {"build/gen.txt": "g1"}),
                                   before_ignored={},
                                   after_ignored={"build/gen.txt": (5, "g1")})
    assert report.ignored_changed == (), "a tracked path must not be counted as ignore-policy churn"


def test_untracked_cache_churn_stays_report_only():
    """The policy survives where it was meant to apply: a cache write with no commit behind it."""
    report = attribute_differences({}, {},
                                   before_state=RepoState(BEFORE_HEAD, {}),
                                   after_state=RepoState(BEFORE_HEAD, {}),
                                   commit_blobs=lambda _: {},
                                   before_ignored={},
                                   after_ignored={"build/gen.txt": (5, "g1")})
    assert report.ignored_changed == ("build/gen.txt",)
    assert report.failures == ()
    assert "1 path under policy-ignored directories changed (report-only: not attributed)" \
        in report.summary()[0]


# ------------------------------------- 5. a commit-tracked path is never pruned by name (AC4)

def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture()
def tracked_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "src").mkdir()
    (repo / "src" / "a.txt").write_bytes(b"kept\n")
    # A committed artefact under a policy-ignored directory, a committed .pyc, and a committed file
    # under .venv/: each is content by name, and each used to be invisible.
    (repo / "build").mkdir()
    (repo / "build" / "gen.pyc").write_bytes(b"committed bytecode\n")
    (repo / "generated.pyc").write_bytes(b"committed bytecode at the root\n")
    (repo / ".venv" / "lib").mkdir(parents=True)
    (repo / ".venv" / "lib" / "vendored.py").write_bytes(b"committed inside .venv\n")
    _git(repo, "add", "-A", "-f")
    _git(repo, "commit", "-q", "-m", "content")
    # Untracked churn beside them, which must stay report-only.
    (repo / "build" / "churn.txt").write_bytes(b"build output\n")
    (repo / "loose.pyc").write_bytes(b"cache\n")
    return repo


def test_a_tracked_pyc_is_never_pruned_by_name(tracked_repo):
    normal = repository_snapshot(tracked_repo)
    ignored = repository_ignored_snapshot(tracked_repo)
    assert "generated.pyc" in normal, "a commit-tracked .pyc must be in the attributed snapshot"
    assert "build/gen.pyc" in normal
    assert "generated.pyc" not in ignored and "build/gen.pyc" not in ignored


def test_a_tracked_file_under_venv_is_walked_not_pruned(tracked_repo):
    normal = repository_snapshot(tracked_repo)
    assert ".venv/lib/vendored.py" in normal, "a commit-tracked path under .venv must be attributed"
    assert ".venv/lib/vendored.py" not in repository_ignored_snapshot(tracked_repo)


def test_untracked_cache_writes_beside_them_stay_report_only(tracked_repo):
    ignored = repository_ignored_snapshot(tracked_repo)
    assert "build/churn.txt" in ignored
    assert "loose.pyc" in ignored


def test_a_change_to_a_tracked_artefact_is_attributed_like_any_other_file(tracked_repo):
    """AC4: the tracked path is compared, so a write to it is a change - not a silent ignore."""
    before = repository_snapshot(tracked_repo)
    before_ignored = repository_ignored_snapshot(tracked_repo)
    (tracked_repo / "generated.pyc").write_bytes(b"rewritten by nobody\n")
    after = repository_snapshot(tracked_repo)
    after_ignored = repository_ignored_snapshot(tracked_repo)

    report = attribute_differences(before, after,
                                   before_state=RepoState(BEFORE_HEAD, {}),
                                   after_state=RepoState(BEFORE_HEAD, {}),
                                   commit_blobs=lambda _: {},
                                   before_ignored=before_ignored,
                                   after_ignored=after_ignored)
    assert report.unexplained == ("generated.pyc",), "an unattributed write must fail and be named"
    assert "generated.pyc" not in report.ignored_changed


# ------------------------------------------------- 6. the wrapped prose sentence: a stated limit

def test_a_wrapped_sentence_whose_next_line_begins_key_is_read_as_configuration():
    """Residual 6, kept as a stated limit: positional rules cannot see intent."""
    value = "the password is in the vault\nKey: it is in the vault"
    reason = services._looks_like_secret(value)
    assert reason is not None
    assert "in the vault" not in reason, "the refusal printed the value"


def test_the_wrapped_sentence_limit_is_stated_in_the_comment_where_the_rule_lives():
    """AC1: a limit that is not written down is a surprise; this one is written where it happens."""
    source = inspect.getsource(services)
    before_pattern = source.split("_BARE_KEY_PAIR = ", 1)[0]
    comment = " ".join(before_pattern.split())
    assert "TESTOPS-69 residual 6" in comment
    assert "wrapped" in comment
    assert "positional" in comment
    assert "line break is the only evidence" in comment
