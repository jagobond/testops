"""The analysers this build can run, and the only names a case may carry.

A case is a finding an analyser raised. If the name on the case is not one of these, nothing in
this build could have raised it: the row was written by something else - a review harness, a
hand-written INSERT, a checkout of a different branch - and its page would be an argument nobody
can reproduce. The web surface refuses such a case (TESTOPS-35) and ``testops scrub-fixtures``
reports and removes it.

The names are read from the analyser modules themselves, never typed here twice: a module that
renames itself must not leave its old name registered by a second copy of the string.
"""
from __future__ import annotations

from . import duplication, level_fitness

REGISTERED = {analyser.name: analyser for analyser in (duplication, level_fitness)}


def registered_names() -> frozenset[str]:
    return frozenset(REGISTERED)


def is_registered(name: str | None) -> bool:
    return bool(name) and name in REGISTERED
