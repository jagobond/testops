"""The claim verdict vocabulary, and the one function that decides membership.

TESTOPS-45. The store accepted any string until this ticket: there was no ``CHECK`` and no trigger,
so a reviewer could write ``verdict = 'total_nonsense'`` into a copy of the live store and SQLite
said yes. The enforcement now lives in the store, as two triggers in ``schema.sql`` that read the
``verdict_vocabulary`` table. That table is the one definition of the allowed set; this module reads
it, so the CLI and the tests ask the store what it will accept instead of keeping a second list.

SQLite cannot call a Python function from a trigger, so the rule is expressed twice: once as SQL
(for every writer, whatever code path it came by) and once in :func:`validate_verdict` (for callers
that want to refuse before touching the database, and as the description a Postgres trigger would
re-implement). ``tests/test_verdict_trigger.py`` reads both and fails if they disagree, so a future
move to Postgres starts from this function rather than from a rediscovery of the vocabulary.

The 128 rows written before the vocabulary settled still carry ``optimal``, ``overbuilt`` and
``necessary``. They are not unknown: the table records them as retired, with the ticket that retired
them, and the triggers never consult them - a retired name is history, not something to write again.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Collection

_CURRENT = "SELECT name FROM verdict_vocabulary WHERE status = 'current' ORDER BY name"
_RETIRED = "SELECT name, retired_by FROM verdict_vocabulary WHERE status = 'retired' ORDER BY name"


class UnknownVerdict(ValueError):
    """A verdict outside the set the store will accept."""


def validate_verdict(value: str, allowed: Collection[str]) -> str:
    """Return ``value`` if it is in ``allowed``; otherwise refuse, naming value and set.

    This is the rule in one place. It names the offending value because SQLite's ``RAISE()`` takes
    a string literal only: the trigger can name the allowed set, but not the value it just saw.
    Callers use this function when they want that sentence; the trigger is the backstop for every
    caller that does not.
    """
    names = sorted(allowed)
    if value not in allowed:
        raise UnknownVerdict(
            f"verdict {value!r} is not one of {', '.join(names)}; the store refuses an unknown verdict")
    return value


def current(conn: sqlite3.Connection) -> frozenset[str]:
    """The verdicts this store accepts on a new claim, read from the store itself."""
    return frozenset(row[0] for row in conn.execute(_CURRENT))


def retired(conn: sqlite3.Connection) -> dict[str, str]:
    """The historical verdicts stored evidence may carry, mapped to the ticket that retired them."""
    return {row[0]: row[1] for row in conn.execute(_RETIRED)}


def inventory(conn: sqlite3.Connection) -> dict:
    """Every claim whose verdict is not current, split into historical and unknown.

    ``unknown`` is the defect: a value the store has no record of at all, whether it predates the
    vocabulary or arrived through a store written before the guard. ``historical`` is the 128 rows
    under retired names - reported so an operator can see them, never treated as corruption and
    never rewritten. One query, so the counts cannot disagree with the rows printed beside them.
    """
    allowed = current(conn)
    retired_names = retired(conn)
    rows = conn.execute(
        "SELECT c.id, c.run_id, c.analyser, c.subject_ref, c.verdict"
        " FROM claim c ORDER BY c.id")
    unknown: list[dict] = []
    historical: dict[str, int] = {name: 0 for name in retired_names}
    for row in rows:
        verdict = row[4]
        if verdict in allowed:
            continue
        if verdict in retired_names:
            historical[verdict] += 1
            continue
        unknown.append({"id": row[0], "run_id": row[1], "analyser": row[2],
                        "subject_ref": row[3], "verdict": verdict})
    return {"allowed": allowed, "retired": retired_names,
            "unknown": unknown, "historical": historical,
            "historical_total": sum(historical.values())}
