"""AC8: running the analyser twice over the same snapshot produces identical claims.

Same order, same statements, same actions. Nothing inside the text may carry a timestamp, a run id
or anything else that changes between two looks at one commit - a case page that differs on every
re-run cannot be read as evidence.
"""
from __future__ import annotations

import re

import level_fixtures as fixtures

VOLATILE = re.compile(r"\b\d{4}-\d{2}-\d{2}|\b\d{2}:\d{2}:\d{2}|\bcase-|\brun-")


def _fingerprint_of_the_run(claims):
    return [(claim.subject_ref, claim.verdict, claim.statement,
             claim.detail["assertion_text"], claim.detail["assertion_line"],
             claim.detail["interaction_label"], claim.detail["proposed_action"],
             tuple(claim.detail["sources_missing"]))
            for claim in claims]


def test_two_runs_produce_identical_claims_in_the_same_order():
    first = fixtures.analyse_fact_sheet(commit=fixtures.COMMIT, sources_missing=["jira"])
    second = fixtures.analyse_fact_sheet(commit=fixtures.COMMIT, sources_missing=["jira"])
    assert _fingerprint_of_the_run(first) == _fingerprint_of_the_run(second)
    assert len(first) == len(second) == 3


def test_no_statement_carries_a_timestamp_or_a_run_identifier():
    claims = fixtures.analyse_fact_sheet(commit=fixtures.COMMIT)
    for claim in claims:
        for field in ("statement", "interaction_label", "proposed_action"):
            text = claim.statement if field == "statement" else claim.detail[field]
            assert not VOLATILE.search(text), f"{field} is not stable: {text!r}"


def test_a_second_run_over_the_same_store_adds_the_same_claims(tmp_path, monkeypatch):
    """Determinism at the store boundary too: the same snapshot analysed twice writes the same rows."""
    from testops import pipeline
    from testops.config import Project, Repo
    from testops.store import db

    path, connect = fixtures.stub_pipeline(monkeypatch, pipeline, tmp_path)
    project = Project(key="fixture", product=Repo("o", "product"), test=Repo("o", "tests"),
                      jira_key="")

    first = pipeline.run_level_fitness(project, token="unused")
    conn = connect(path)
    try:
        before = conn.execute(
            "SELECT statement, verdict, assertion_line, proposed_action FROM claim ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    # A second run needs its own run id; the store keeps both, like any re-run does.
    monkeypatch.setattr(pipeline, "dt", _DtShim())
    second = pipeline.run_level_fitness(project, token="unused")

    assert [claim.statement for claim in first.claims] == [claim.statement for claim in second.claims]
    assert [claim.detail["proposed_action"] for claim in first.claims] == \
        [claim.detail["proposed_action"] for claim in second.claims]
    assert [claim.detail["assertion_line"] for claim in first.claims] == \
        [claim.detail["assertion_line"] for claim in second.claims]

    conn = connect(path)
    try:
        after = conn.execute(
            "SELECT statement, verdict, assertion_line, proposed_action FROM claim ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    assert [tuple(row) for row in after[len(before):]] == [tuple(row) for row in before]


class _Later:
    """A datetime whose now() is a second later, so two runs in one test do not share a run id."""

    @staticmethod
    def now(tz=None):
        import datetime as real

        return real.datetime.now(tz) + real.timedelta(seconds=1)

    def __getattr__(self, item):
        import datetime as real

        return getattr(real.datetime, item)


class _DtShim:
    """Stands in for the ``datetime`` module *inside pipeline only*, one second in the future."""

    def __init__(self):
        import datetime as real

        self.date = real.date
        self.timezone = real.timezone
        self.timedelta = real.timedelta
        self.datetime = _Later()
