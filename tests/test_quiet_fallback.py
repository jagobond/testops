"""TESTOPS-71: the quiet fallback when git is down, the reading field, and the placeholder.

Suite: tests/test_quiet_fallback.py.

Three findings from the TESTOPS-69 residuals review, one test group each:

1. when git was unavailable at walk time at both ends of a run, ``tracked_paths`` returned an empty
   set and the walk fell back to pruning ``.venv`` and ignoring ``*.pyc`` by name - so a rewrite of a
   commit-tracked ``*.pyc`` was report-only churn, exactly what TESTOPS-69 AC4 was written to prevent;
2. ``git readable: yes`` could print when git had been unreadable at snapshot time, because the field
   reflected state reads and commit trees but not the walk's tracked-path lookup;
3. the pair rule fired before the reference check, so ``?token=${TOKEN}`` and ``page_token=abc`` were
   refused by the pair branch, and ``?api_key=YOUR_KEY_HERE`` because ``YOUR_KEY_HERE`` was not a
   recognised placeholder - and a filter that refuses a placeholder trains people to paste the real
   value.

The guard tests use disposable repositories in ``tmp_path`` and synthetic snapshots; nothing here
touches the real checkout, the live store or port 8791.
"""
from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

import support
from support import (GitRepository, RepoState, attribute_differences, guard_baseline,
                     guard_report, repository_ignored_snapshot, repository_snapshot, tracked_paths)
from testops import services

BEFORE_HEAD = "1111111111111111111111111111111111111111"
AFTER_HEAD = "2222222222222222222222222222222222222222"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


# ------------------------------------------------------- AC1: an unknown set is not an empty one

@pytest.fixture()
def blind_git(monkeypatch):
    """Git cannot be read: every repository read the guard makes returns ``None``.

    This is the walk-time failure the ticket names. Setup happens before the fixture is active, so
    the repository is real and committed; only the guard's reads are blind.
    """
    monkeypatch.setattr(GitRepository, "_git", lambda self, *args: None)


def test_tracked_paths_is_none_not_empty_when_git_cannot_be_read(tmp_path):
    """AC1: an unreadable repository must not be reported as one that tracks nothing."""
    assert tracked_paths(tmp_path) is None


def test_a_readable_repository_that_tracks_nothing_is_an_empty_set(tmp_path):
    """The other side: ``frozenset()`` is a real answer and keeps the ignore policy honest."""
    _git(tmp_path, "init", "-q")
    assert tracked_paths(tmp_path) == frozenset()


def test_an_unknown_tracked_set_walks_every_path_as_content(tmp_path):
    """AC1: no name-based pruning or ignoring when the tracked set is unknown."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.txt").write_bytes(b"kept\n")
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "vendored.py").write_bytes(b"vendored\n")
    (tmp_path / "generated.pyc").write_bytes(b"committed-looking bytecode\n")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.bin").write_bytes(b"build output\n")

    normal = repository_snapshot(tmp_path)
    ignored = repository_ignored_snapshot(tmp_path)

    assert set(normal) == {"src/a.txt", ".venv/lib/vendored.py", "generated.pyc", "build/out.bin"}
    assert set(ignored) == set(), "an unknown set must not license name-based ignoring"
    assert normal.tracked_known is False
    assert ignored.tracked_known is False


def test_a_rewrite_of_a_committed_pyc_fails_when_git_is_unavailable_at_walk_time(
        tmp_path, blind_git):
    """AC1: the exact shape T69 AC4 was written to close - and it now fails, loudly."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "generated.pyc").write_bytes(b"committed bytecode\n")
    _git(repo, "add", "-f", "generated.pyc")
    _git(repo, "commit", "-q", "-m", "content")

    before = repository_snapshot(repo)
    before_ignored = repository_ignored_snapshot(repo)
    (repo / "generated.pyc").write_bytes(b"rewritten by nobody\n")
    after = repository_snapshot(repo)
    after_ignored = repository_ignored_snapshot(repo)

    assert "generated.pyc" in before and "generated.pyc" in after, (
        "with git unreadable at walk time the tracked .pyc must still be content")
    report = attribute_differences(before, after,
                                   before_state=RepoState(None, {}, readable=False),
                                   after_state=RepoState(None, {}, readable=False),
                                   commit_blobs=lambda _: None,
                                   before_alphabet=before.alphabet,
                                   after_alphabet=after.alphabet,
                                   before_ignored=before_ignored,
                                   after_ignored=after_ignored)

    assert "generated.pyc" in report.unreadable
    assert "generated.pyc" in report.failures, "the rewrite must fail, not ride the ignored channel"
    assert "generated.pyc" not in report.ignored_changed
    assert report.git_readable is False
    assert "git readable: no" in report.summary()[0]


# ------------------------------------- AC2: git readable means every read, including the walk

def test_git_readable_is_false_when_the_walks_tracked_path_lookup_failed():
    """AC2: state reads and commit trees can succeed while the walk's lookup did not."""
    report = attribute_differences({}, {},
                                   before_state=RepoState(BEFORE_HEAD, {}),
                                   after_state=RepoState(BEFORE_HEAD, {}),
                                   commit_blobs=lambda _: {},
                                   walk_readable=False)

    assert report.walk_readable is False
    assert report.git_readable is False, "a field that says yes here is the lie the ticket names"
    line = report.summary()[0]
    assert "git readable: no" in line
    assert any("tracked-path lookup failed" in line for line in report.summary()), (
        "the summary must say the walk treated every path as content")


def test_the_guard_entry_point_says_git_readable_no_for_an_unreadable_walk(tmp_path):
    """AC2: pinned through ``guard_baseline``/``guard_report``, not only the internals."""
    (tmp_path / "a.txt").write_bytes(b"content\n")
    baseline = guard_baseline(tmp_path)
    report = guard_report(baseline)

    assert getattr(baseline.snapshot, "tracked_known") is False
    assert report.git_readable is False
    assert "git readable: no" in report.summary()[0]


# ---------------------------------------------- AC3: a slot reference is accepted wherever read

SLOT_REFERENCES_ACCEPTED = [
    "?token=${TOKEN}",
    "page_token=${TOKEN}",
    "token=${PAGE_TOKEN}",
    "api_key=os.environ[\"X\"]",
    "key = from-env",
    "dsn=${DATABASE_URL}",
]


@pytest.mark.parametrize("value", SLOT_REFERENCES_ACCEPTED)
def test_a_slot_reference_is_accepted_wherever_a_value_is_read(value):
    assert services._looks_like_secret(value) is None, f"{value!r} names a slot and was refused"
    services.validate_settings({"name": value})


@pytest.mark.parametrize("value", ["?page_token=abc", "page_token=abc", "token=hunter2",
                                   "password=hunter2"])
def test_a_literal_after_the_same_names_is_still_refused(value):
    """The reference check must not become a gate for the strong words' literal form."""
    reason = services._looks_like_secret(value)
    assert reason is not None, f"{value!r} carries a literal and was accepted"
    assert "hunter2" not in reason and "abc" not in reason


def test_the_pair_branch_consults_is_reference_for_strong_words_too():
    """AC3: `token` and `api_key` reach the same verdict; the check is not the key family's."""
    for name in ("token", "api_key", "client_secret", "access_key"):
        assert services._looks_like_secret(f"{name}=${{SLOT}}") is None, (
            f"{name}=${{SLOT}} names a slot and was refused")
        assert services._looks_like_secret(f"{name}=literal123") is not None, (
            f"{name}=literal123 is a literal and was accepted")
    source = inspect.getsource(services)
    assert 'if _is_reference(pair.group("value")):' in source
    assert '_KEY_FAMILY.match(pair.group(1)) and _is_reference' not in source, (
        "the reference check must no longer be limited to the key family")


# ------------------------------------------------------------ AC4: placeholders are not secrets

PLACEHOLDER_PAIRS_ACCEPTED = [
    "api_key=YOUR_KEY_HERE",
    "token=YOUR_KEY_HERE",
    "password=YOUR_API_KEY",
    "api_key=<your-key>",
    "password=changeme",
    "token=xxxx",
    "password=***",
    "token=REDACTED",
    "token=TODO",
    "api_key=example",
]

PLACEHOLDER_QUERIES_ACCEPTED = [
    "?api_key=YOUR_KEY_HERE",
    "?token=YOUR_KEY_HERE",
    "&password=changeme",
    "?secret=REDACTED",
    "?pwd=***",
]


@pytest.mark.parametrize("value", PLACEHOLDER_PAIRS_ACCEPTED)
def test_a_placeholder_in_a_pair_is_configuration(value):
    assert services._looks_like_secret(value) is None, (
        f"{value!r} is a placeholder; refusing it trains people to paste the real value")
    services.validate_settings({"name": value})


@pytest.mark.parametrize("value", PLACEHOLDER_QUERIES_ACCEPTED)
def test_a_placeholder_in_a_query_string_is_configuration(value):
    assert services._looks_like_secret(value) is None, f"{value!r} is a placeholder and was refused"
    services.validate_settings({"name": value})


@pytest.mark.parametrize("value", [
    "token=hunter2",
    "?token=hunter2",
    "password=Zx9Qw3Er7Ty1Ui5Op8As2Df4Gh6Jk0Lm9Nb3",   # 36 characters of base62
    "api_key=AKIAIOSFODNN7EXAMPLE",                     # an AKIA-shaped value
])
def test_a_real_secret_is_still_refused_beside_the_placeholders(value):
    """AC4, the other side: the placeholder vocabulary did not become a door."""
    reason = services._looks_like_secret(value)
    assert reason is not None, f"{value!r} is a secret shape and was accepted"
    assert "hunter2" not in reason
    with pytest.raises(services.ConfigError):
        services.validate_settings({"name": value})


# ------------------------------------------ AC5: the tab's false-positive family, stated with it

def test_the_tab_false_positive_family_is_stated_beside_the_wrapped_sentence_limit():
    """AC5: it is written where the wrapped-sentence limit is, not discovered later."""
    value = "notes\tkey: in the vault"
    reason = services._looks_like_secret(value)
    assert reason is not None, "a tab-separated prose line is refused as configuration"

    source = inspect.getsource(services)
    before_pattern = source.split("_BARE_KEY_PAIR = ", 1)[0]
    comment = " ".join(before_pattern.split())
    assert "TESTOPS-71 AC5" in comment
    assert "wrapped" in comment, "the tab family must sit beside the wrapped-sentence limit"
    assert "false-positive" in comment
    assert "notes\\tkey: in the vault" in comment
