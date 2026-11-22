"""The source registry: what a run could look at, declared before it looks.

TESTOPS-5. A source is a kind of thing evidence can come from - a code host, an issue tracker, a
build service. Each one declares an identity, the capabilities it can provide, and a *state*:

  * ``available``  - the run may consult it;
  * ``absent``     - it is not configured for this run, and there is a reason;
  * ``blocked``    - it exists and could be consulted, but somebody with authority forbids it. The
                     reason names why, and ``blocked_by`` names who.

The distinction this module exists to protect is the one that collapses in every analysis tool: a
source nobody could look at is **not** a source that was consulted and held nothing. The first is
``not_assessable``; the second is a real zero. They have different verdicts and different sentences,
and neither is ever produced by swallowing an exception:

  * a state is set by explicit configuration (:func:`registry`) or by an explicit probe that returns
    a :class:`SourceState`. There is no code path that turns a failure into ``absent``;
  * a source declared ``available`` that fails when used raises :class:`SourceFailed`, and the run
    stops. Rewriting its state to ``absent`` would silently rewrite history - the snapshot would say
    the source was never there, when the truth is that it was there and broke;
  * a source that is not ``available`` cannot be used at all: :meth:`Registry.use` refuses, rather
    than returning an empty result that a caller could mistake for a zero.

The registry is also the seam that keeps analysers away from collectors. An analyser declares the
capabilities it needs and consults (``NEEDS``/``CONSULTS``); the pipeline asks the registry what is
missing and whether the claim can be assessed. Adding a source is a change to this module's
configuration, never a change to an analyser.

No credentials live here. A source is declared from its identity and policy, not from a token, so
the registry can be written into a snapshot and read by anyone. A test asserts that.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable

# ---------------------------------------------------------------- capabilities

REQUIREMENTS = "requirements"
TEST_EXECUTION = "test_execution"
CODE = "code"
TEST_CODE = "test_code"

# Canonical order. Every list this module returns follows it, so two runs over the same declarations
# produce the same order and a diff means something.
CAPABILITIES = (REQUIREMENTS, TEST_EXECUTION, CODE, TEST_CODE)

CAPABILITY_TITLE = {
    REQUIREMENTS: "requirements",
    TEST_EXECUTION: "test-execution evidence",
    CODE: "code",
    TEST_CODE: "test code",
}

# ---------------------------------------------------------------- source states

AVAILABLE = "available"
ABSENT = "absent"
BLOCKED = "blocked"
STATES = (AVAILABLE, ABSENT, BLOCKED)

# ---------------------------------------------------------------- assessment verdicts

# Nobody could look. Never a zero, never a gap.
NOT_ASSESSABLE = "not_assessable"
# Available, but the run did not record what it returned. Neither a zero nor a blind spot.
NOT_RECORDED = "not_recorded"
# We looked, and there is nothing. A real zero.
ZERO = "zero"
# We looked, and there is something.
FOUND = "found"

# TESTOPS-41. A capability whose reader could not read this repository: the source was available,
# the run consulted it, and nothing it reads as this capability was fetched. It is not ``absent``
# (the source is configured), it is not ``zero`` (a zero means a reader looked and found nothing),
# and it is not ``found``. A file nothing read is never counted as consulted.
NOT_READABLE = "not_readable"


@dataclass(frozen=True)
class Reading:
    """What one capability got from one source in one run - one of three states, never shared.

      * ``observed`` is a count and ``unreadable`` is empty: the reader read this kind of file and
        returned that many. ``0`` is a real zero.
      * one or more files were fetched but the capability could not be read as this capability:
        ``observed`` is ``None``, ``unreadable`` says why, and ``skipped`` records what fell
        outside the reader's reach.

    ``arms`` is the count per repository, so a record can say which of two repositories supplied
    the items without anyone guessing. Nothing here is a percentage: counts, or an absence.

    ``skipped`` is every file the run did not fetch from the arms that serve this capability.
    ``lost`` is the subset of those the reader *would* have read - a kind it handles, refused for
    its size - which is the only thing that makes a reading partial. A file of a kind no reader
    here reads is not a file this capability lost: it is a kind the run never had, and the run
    page lists it under *Files this run could not read* (TESTOPS-43). Keeping the two apart is
    what lets the sentence say "code returned 12 items (3 .cs files unreadable)" without turning
    every README in the tree into a caveat on a complete reading.
    """
    capability: str
    observed: int | None = None
    unreadable: str = ""
    arms: dict[str, int] = field(default_factory=dict)
    skipped: tuple[dict, ...] = ()
    lost: tuple[dict, ...] = ()

    def __post_init__(self) -> None:
        if self.capability not in CAPABILITIES:
            raise ValueError(f"unknown capability {self.capability!r}; expected one of {CAPABILITIES}")
        if self.observed is not None and (not isinstance(self.observed, int) or self.observed < 0):
            raise ValueError(f"{self.capability}: observed must be a count or None, "
                             f"found {self.observed!r}")
        if self.unreadable.strip():
            if self.observed not in (None, 0):
                raise ValueError(f"{self.capability}: a capability that could not be read cannot "
                                 f"report {self.observed} items read")
        elif self.observed is None:
            # The other direction of the same mistake: "read, and I will not say what it returned"
            # is not a state this record has. It is either a count or a reason.
            raise ValueError(f"{self.capability}: a readable capability must record what it "
                             "returned, even when that is 0")

    @property
    def readable(self) -> bool:
        return not self.unreadable.strip()

    def record(self, *, include_skipped: bool = False) -> dict:
        out = {"capability": self.capability, "observed": self.observed,
               "unreadable": self.unreadable, "arms": dict(self.arms)}
        if include_skipped:
            out["skipped"] = [dict(entry) for entry in self.skipped]
            if self.lost:
                # Counts and kinds only: these are already inside ``skipped`` with their file
                # lists, and the sentence needs the summary, not a second copy of the tree.
                out["lost"] = [{"reason": entry.get("reason", ""),
                                "kind": entry.get("kind", ""),
                                "count": int(entry.get("count") or 0)} for entry in self.lost]
        return out

# ---------------------------------------------------------------- the Quilter deployment

GITHUB = "github"
JIRA = "jira"
ADO = "ado"

QUILTER_POLICY = "Quilter policy"

# The reason Jira and ADO are declared blocked wherever a project names them. It is a policy fact,
# not a transient failure: no token can be issued, so no retry and no configuration change will make
# the source available at Quilter.
QUILTER_NO_PAT = ("no credentials can be created for it, and policy forbids issuing a personal "
                  "access token because of breach risk")


class SourceFailed(RuntimeError):
    """A source declared ``available`` failed when it was used. The run must stop.

    Not converted to ``absent``: the source was there, and its failure is a fact about this run, not
    about the source's existence. Degrading would make the snapshot claim the run never had the
    source at all.
    """


class SourceNotAvailable(RuntimeError):
    """A run tried to consult a source that is not declared ``available``."""


# ---------------------------------------------------------------- declarations

@dataclass(frozen=True)
class SourceState:
    """The declared state of one source, with the reason anything not available is not.

    ``observed`` is how many items the run actually took from the source, when it was consulted.
    ``None`` means "not recorded" - it is never spelled ``0``, because zero is a real result.

    ``readings`` is the per-capability answer (TESTOPS-41): what this source returned for each
    capability it was asked for. A record written before that field existed has none, and is read
    through ``observed`` exactly as it always was - an old snapshot must render as it rendered.
    """
    state: str
    reason: str = ""
    blocked_by: str = ""
    observed: int | None = None
    readings: tuple[Reading, ...] = ()

    def __post_init__(self) -> None:
        if self.state not in STATES:
            raise ValueError(f"unknown source state {self.state!r}; expected one of {STATES}")
        if self.state != AVAILABLE and not self.reason.strip():
            # A state with no reason is an assumption wearing a declaration's clothes.
            raise ValueError(f"a source declared {self.state!r} must say why")
        if self.state == BLOCKED and not self.blocked_by.strip():
            raise ValueError("a blocked source must name who blocked it")
        if self.observed is not None and (not isinstance(self.observed, int) or self.observed < 0):
            raise ValueError(f"observed must be a count or None, found {self.observed!r}")
        if self.state != AVAILABLE and self.observed is not None:
            # "We counted zero" and "nobody could look" are the two facts this module keeps apart.
            # A source nobody could consult has no count at all, not a count of zero.
            raise ValueError(f"a source declared {self.state!r} cannot have an observed count")
        if self.readings and self.state != AVAILABLE:
            raise ValueError(f"a source declared {self.state!r} cannot have readings")
        if self.readings and self.observed is None:
            # The aggregate and the readings cannot disagree: when a run records the split, the
            # whole is the sum of the capabilities it could read, and nothing else.
            countable = [reading.observed for reading in self.readings if reading.readable]
            if countable:
                object.__setattr__(self, "observed", sum(countable or ()))

    @property
    def available(self) -> bool:
        return self.state == AVAILABLE

    def record(self) -> dict:
        out = {"state": self.state, "reason": self.reason, "blocked_by": self.blocked_by,
               "observed": self.observed}
        if self.readings:
            # Only when the run recorded them. A snapshot taken before this field existed must
            # read back as it was written, not as if it had said something it never said.
            out["readings"] = [reading.record(include_skipped=True) for reading in self.readings]
        return out


@dataclass(frozen=True)
class SourceKind:
    """One kind of source: who it is, what it can provide, and how this run stands with it."""
    id: str
    title: str
    capabilities: frozenset[str]
    state: SourceState
    route: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("a source needs an id")
        if not self.title.strip():
            raise ValueError(f"source {self.id!r} needs a title a reader can see")
        capabilities = frozenset(self.capabilities)
        if not capabilities:
            raise ValueError(f"source {self.id!r} provides nothing, so it is not a source")
        unknown = capabilities - set(CAPABILITIES)
        if unknown:
            raise ValueError(f"source {self.id!r} claims unknown capabilities: {sorted(unknown)}")
        object.__setattr__(self, "capabilities", capabilities)
        for reading in self.state.readings:
            if reading.capability not in capabilities:
                raise ValueError(f"source {self.id!r} recorded a reading for {reading.capability!r}, "
                                 f"which it does not declare")

    @classmethod
    def available(cls, source_id: str, title: str, capabilities: Iterable[str], *,
                  route: str = "", note: str = "", observed: int | None = None) -> "SourceKind":
        return cls(source_id, title, frozenset(capabilities),
                   SourceState(AVAILABLE, observed=observed), route, note)

    @classmethod
    def absent(cls, source_id: str, title: str, capabilities: Iterable[str], reason: str, *,
               route: str = "", note: str = "") -> "SourceKind":
        return cls(source_id, title, frozenset(capabilities),
                   SourceState(ABSENT, reason=reason), route, note)

    @classmethod
    def blocked(cls, source_id: str, title: str, capabilities: Iterable[str], reason: str,
                blocked_by: str, *, route: str = "", note: str = "") -> "SourceKind":
        return cls(source_id, title, frozenset(capabilities),
                   SourceState(BLOCKED, reason=reason, blocked_by=blocked_by), route, note)

    @classmethod
    def probed(cls, source_id: str, title: str, capabilities: Iterable[str],
               probe: Callable[[], "SourceState"], *, route: str = "",
               note: str = "") -> "SourceKind":
        """Declare a source from an explicit probe.

        The probe returns a :class:`SourceState` or raises. There is deliberately no ``try`` around
        it: a probe that fails is a failure, and converting it to ``absent`` is the exact mistake
        this module exists to prevent. A caller that wants to record an absence must return
        ``SourceState(ABSENT, reason=...)`` and say why.
        """
        state = probe()
        if not isinstance(state, SourceState):
            raise TypeError(f"probe for {source_id!r} returned {type(state).__name__}, "
                            "not a SourceState")
        return cls(source_id, title, frozenset(capabilities), state, route, note)

    def record(self) -> dict:
        """The declaration as it is written into a snapshot. Contains no credential, by design."""
        return {"id": self.id, "title": self.title,
                "capabilities": sorted(self.capabilities),
                **self.state.record(), "route": self.route, "note": self.note}


@dataclass(frozen=True)
class BlindSpot:
    """One reason a capability could not be assessed, in the reader's words."""
    source: str
    title: str
    state: str
    reason: str
    blocked_by: str = ""

    def record(self) -> dict:
        return {"source": self.source, "title": self.title, "state": self.state,
                "reason": self.reason, "blocked_by": self.blocked_by}


@dataclass(frozen=True)
class Assessment:
    """Whether a set of capabilities could be assessed, and if so what was found.

    ``state`` is one of :data:`NOT_ASSESSABLE`, :data:`NOT_RECORDED`, :data:`ZERO`, :data:`FOUND`.
    The two the product turns on are ``not_assessable`` ("nobody could look") and ``zero`` ("we
    looked, there is nothing"); they are different verdicts with different sentences.

    ``readings`` is the per-capability detail when the run recorded it (TESTOPS-41). With it, a
    claim that needed two capabilities and got only one says so: the capability that was read is
    reported with its count, the one that could not be read is reported with the reason, and the
    two never share a sentence. Without it - a snapshot written before the field existed - the
    sentence is exactly the one that snapshot's readers saw.
    """
    capabilities: tuple[str, ...]
    state: str
    observed: int | None = None
    blind_spots: tuple[BlindSpot, ...] = ()
    readings: tuple[Reading, ...] = ()

    @property
    def assessable(self) -> bool:
        return self.state != NOT_ASSESSABLE

    def record(self) -> dict:
        """The assessment without its sentence: wording is derived, the facts are stored."""
        out = {"state": self.state, "capabilities": list(self.capabilities),
               "observed": self.observed,
               "blind_spots": [spot.record() for spot in self.blind_spots]}
        if self.readings:
            # Per capability, without the skipped file lists: a claim row is not a place to copy a
            # repository's tree. The full record lives once, in the snapshot's registry.
            out["readings"] = [reading.record() for reading in self.readings]
        return out

    def sentence(self) -> str:
        """What a reader is told. Different states never share wording."""
        titles = _titles(self.capabilities)
        plural = len(self.capabilities) > 1
        if self.state == NOT_ASSESSABLE:
            # The source-level blind spots (blocked, absent) are stated by _blind_sentence. A
            # capability that was consulted and could not be read is stated per capability, so it
            # is not repeated here.
            parts = " ".join(_blind_sentence(spot) for spot in self.blind_spots
                             if spot.state != NOT_READABLE)
            if self.readings:
                clauses = "; ".join(_reading_clause(reading) for reading in self.readings)
                return f"Cannot assess this claim: {clauses}. {parts}".strip()
            return f"Cannot assess this claim: nobody could look at {titles}. {parts}".strip()
        if self.state == ZERO:
            verb = "were" if plural else "was"
            return (f"Assessed: {titles} {verb} consulted and returned nothing. That is a real "
                    "zero \u2014 there is nothing there, not that nobody looked.")
        if self.state == FOUND:
            verb = "were" if plural else "was"
            count = self.observed if self.observed is not None else 0
            item = "item" if count == 1 else "items"
            # TESTOPS-43. An aggregate is only enough when it hides nothing: every capability it
            # adds up returned something, and none of them lost a file it would have read. When a
            # capability returned nothing, the total cannot say which one did, so each capability
            # is named with its own count - "code and test code returned 2 items" is true of a
            # 2-and-0 and of a 1-and-1, and a reader cannot tell them apart.
            if any(reading.observed == 0 for reading in self.readings if reading.readable):
                return "Assessed: " + "; ".join(_result_clause(reading)
                                                for reading in self.readings) + "."
            partial = _lost_clause([entry for reading in self.readings
                                    for entry in reading.lost])
            note = f" ({partial})" if partial else ""
            return f"Assessed: {titles} {verb} consulted and returned {count} {item}{note}."
        verb = "were" if plural else "was"
        return (f"Assessed: {titles} {verb} available, but the run did not record what was "
                "returned.")


def _titles(capabilities: Iterable[str]) -> str:
    names = [CAPABILITY_TITLE.get(capability, capability) for capability in capabilities]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _blind_sentence(spot: BlindSpot) -> str:
    reason = spot.reason.strip().rstrip(".")
    if spot.state == BLOCKED:
        by = f" by {spot.blocked_by}" if spot.blocked_by else ""
        return f"{spot.title} is blocked{by}: {reason}." if reason else f"{spot.title} is blocked{by}."
    if spot.state == ABSENT:
        return f"{spot.title} is absent: {reason}." if reason else f"{spot.title} is absent."
    if spot.state == NOT_READABLE:
        return (f"{spot.title} could not be read: {reason}." if reason
                else f"{spot.title} could not be read.")
    return f"{spot.title} is {spot.state}: {reason}." if reason else f"{spot.title} is {spot.state}."


def _reading_clause(reading: Reading) -> str:
    """One capability, in the reader's words: what it returned, or why it could not be read."""
    title = CAPABILITY_TITLE.get(reading.capability, reading.capability)
    if reading.readable:
        count = reading.observed or 0
        item = "item" if count == 1 else "items"
        return f"{title} was consulted and returned {count} {item}"
    return f"{title} was not read: {reading.unreadable.strip().rstrip('.')}"


def _result_clause(reading: Reading) -> str:
    """One capability in a sentence that names each: what it returned, and what it lost.

    Used when the capabilities' counts must not be added up (TESTOPS-43): a total cannot say
    that one capability returned nothing. The parenthetical is only there when the reading is
    genuinely partial, so a complete reading stays one short clause.
    """
    title = CAPABILITY_TITLE.get(reading.capability, reading.capability)
    count = reading.observed or 0
    item = "item" if count == 1 else "items"
    clause = f"{title} returned {count} {item}"
    lost = _lost_clause(reading.lost)
    return f"{clause} ({lost})" if lost else clause


def _lost_clause(lost) -> str:
    """What one reading could not read, as the parenthetical a reader meets: kind and count.

    "142 .java files and 3 other kinds unreadable". No reason and no file list: the run page
    names every skipped kind with its reason and lets the reader open the list (TESTOPS-43).
    """
    entries = [entry for entry in lost or () if int(entry.get("count") or 0)]
    if not entries:
        return ""
    entries.sort(key=lambda entry: (-int(entry.get("count") or 0),
                                    str(entry.get("kind") or "")))
    biggest = entries[0]
    count = int(biggest.get("count") or 0)
    kind = str(biggest.get("kind") or "").strip() or "file"
    clause = f"{count} {kind} file" if count == 1 else f"{count} {kind} files"
    others = len(entries) - 1
    if others:
        clause += f" and {others} other kind" + ("s" if others != 1 else "")
    return clause + " unreadable"


# ---------------------------------------------------------------- the registry

class Registry:
    """The declared sources for one run, and the questions an analyser is allowed to ask them."""

    def __init__(self, kinds: Iterable[SourceKind]) -> None:
        self._kinds = tuple(kinds)
        seen: set[str] = set()
        for kind in self._kinds:
            if kind.id in seen:
                raise ValueError(f"two sources share the id {kind.id!r}; one declaration per source")
            seen.add(kind.id)

    def __iter__(self):
        return iter(self._kinds)

    def __len__(self) -> int:
        return len(self._kinds)

    def __contains__(self, source_id: object) -> bool:
        return any(kind.id == source_id for kind in self._kinds)

    def get(self, source_id: str) -> SourceKind | None:
        for kind in self._kinds:
            if kind.id == source_id:
                return kind
        return None

    def state_of(self, source_id: str) -> SourceState | None:
        """The declared state, or ``None`` when this run never declared that source."""
        kind = self.get(source_id)
        return kind.state if kind else None

    def for_capability(self, capability: str) -> tuple[SourceKind, ...]:
        if capability not in CAPABILITIES:
            raise ValueError(f"unknown capability {capability!r}; expected one of {CAPABILITIES}")
        return tuple(kind for kind in self._kinds if capability in kind.capabilities)

    def missing(self, capabilities: Iterable[str]) -> list[str]:
        """The declared sources that cannot serve any of ``capabilities``, in declaration order.

        This is what a claim records as ``sources_missing``. A source the run never declared is not
        named here - it is not a missing source, it is a capability with no source at all, which
        :meth:`assess` reports as a blind spot with its own reason.
        """
        wanted = _check_capabilities(capabilities)
        return [kind.id for kind in self._kinds
                if not kind.state.available and kind.capabilities & wanted]

    def assess(self, capabilities: Iterable[str]) -> Assessment:
        """Can these capabilities be assessed, and what did the sources return?

        A capability is assessable when at least one declared source provides it and is available.
        When none can, every source that would have served it becomes a blind spot with its reason;
        when no source was ever declared for it, the blind spot names the capability and says so.
        """
        requested = tuple(c for c in CAPABILITIES if c in _check_capabilities(capabilities))
        if not requested:
            raise ValueError("an assessment must ask about at least one capability")

        blind: list[BlindSpot] = []
        readings: list[Reading] = []
        # Counted per source, not per capability: one repository serving both code and test code is
        # one repository, and adding its count once per capability would report double what it saw.
        # That is the legacy reading, used only for a record written before per-capability counts.
        observed: dict[str, int] = {}
        for capability in requested:
            candidates = self.for_capability(capability)
            if not candidates:
                blind.append(BlindSpot(
                    source="", title=CAPABILITY_TITLE[capability], state=ABSENT,
                    reason="no source is declared that could provide it"))
                continue
            usable = [kind for kind in candidates if kind.state.available]
            if not usable:
                blind.extend(BlindSpot(kind.id, kind.title, kind.state.state,
                                       kind.state.reason, kind.state.blocked_by)
                             for kind in candidates)
                continue
            served = [(kind, reading) for kind in usable
                      for reading in kind.state.readings if reading.capability == capability]
            if not served:
                for kind in usable:
                    if kind.state.observed is not None:
                        observed[kind.id] = kind.state.observed
                continue
            readable = [(kind, reading) for kind, reading in served if reading.readable]
            if readable:
                readings.append(Reading(
                    capability,
                    observed=sum(reading.observed or 0 for _kind, reading in readable),
                    arms=_merge_arms(reading for _kind, reading in readable),
                    skipped=tuple(entry for _kind, reading in readable
                                  for entry in reading.skipped),
                    # Only the files this reader would have read: what makes the count partial
                    # rather than complete, and the one thing the sentence has to say out loud.
                    lost=tuple(entry for _kind, reading in readable
                               for entry in reading.lost)))
                continue
            # Every source that could serve this capability was consulted and none could read it.
            for kind, reading in served:
                blind.append(BlindSpot(kind.id, CAPABILITY_TITLE[capability], NOT_READABLE,
                                       reading.unreadable))
                readings.append(reading)

        if readings:
            if blind:
                return Assessment(requested, NOT_ASSESSABLE, None, tuple(blind), tuple(readings))
            total = sum(reading.observed or 0 for reading in readings)
            return Assessment(requested, ZERO if total == 0 else FOUND, total, (), tuple(readings))
        if blind:
            return Assessment(requested, NOT_ASSESSABLE, None, tuple(blind))
        if not observed:
            return Assessment(requested, NOT_RECORDED, None)
        total = sum(observed.values())
        return Assessment(requested, ZERO if total == 0 else FOUND, total)

    def with_readings(self, readings: dict[str, Iterable[Reading]]) -> "Registry":
        """A copy of the registry recording, per source and capability, what this run took.

        TESTOPS-41. This is the record that stops one count standing for two capabilities: the
        source's aggregate ``observed`` is the sum of the capabilities it could read, and a
        capability it could not read carries no count at all - it carries a reason.
        """
        kinds = []
        for kind in self._kinds:
            given = list(readings.get(kind.id) or ())
            if not given:
                kinds.append(kind)
                continue
            ordered = tuple(reading for capability in CAPABILITIES
                            for reading in given if reading.capability == capability)
            countable = [reading.observed for reading in ordered if reading.readable]
            total = sum(value or 0 for value in countable) if countable else None
            kinds.append(replace(kind, state=replace(kind.state, readings=ordered,
                                                      observed=total)))
        return Registry(kinds)

    def use(self, source_id: str, call: Callable[[], Any], *, role: str = "") -> Any:
        """Consult a source, or refuse. A failure at use stops the run; it never changes a state.

        This is the only way the pipeline reaches a collector. It exists so that "available" is a
        promise with a consequence: if the promise breaks, the run says so loudly instead of
        recording the source as absent after the fact.
        """
        kind = self.get(source_id)
        label = f"{kind.title} ({role})" if kind is not None and role else (
            kind.title if kind is not None else source_id)
        if kind is None:
            raise SourceNotAvailable(
                f"no source {source_id!r} is declared for this run. A run cannot consult what it "
                "never declared, and an undeclared source is not an empty one.")
        if not kind.state.available:
            by = f" by {kind.state.blocked_by}" if kind.state.blocked_by else ""
            raise SourceNotAvailable(
                f"{label} is declared {kind.state.state}{by}: {kind.state.reason} A run cannot "
                "consult it, and must not treat it as having returned nothing.")
        try:
            return call()
        except Exception as exc:
            raise SourceFailed(
                f"{label} is declared available but failed when used "
                f"({type(exc).__name__}: {exc}). The run stops here; the source stays declared "
                "available, because a failure at use is not evidence that the source is absent."
            ) from exc

    def record(self) -> dict:
        """The whole registry as stored in a snapshot, ordered so a rebuild reads it back the same."""
        out: dict[str, dict] = {}
        for order, kind in enumerate(self._kinds):
            entry = kind.record()
            entry["order"] = order
            out[kind.id] = entry
        return out

    @classmethod
    def from_record(cls, record: dict) -> "Registry":
        """Read a stored registry back. A record that cannot be read is refused, not guessed."""
        if not isinstance(record, dict):
            raise ValueError(f"a source registry record must be a mapping, found {type(record).__name__}")
        entries = sorted(record.items(), key=lambda item: (
            int((item[1] or {}).get("order", 0)), item[0]))
        kinds = []
        for key, entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"source record {key!r} is not a mapping")
            kinds.append(SourceKind(
                id=entry.get("id") or key,
                title=entry.get("title") or key,
                capabilities=frozenset(entry.get("capabilities") or ()),
                state=SourceState(
                    state=entry.get("state", ""),
                    reason=entry.get("reason") or "",
                    blocked_by=entry.get("blocked_by") or "",
                    observed=entry.get("observed"),
                    readings=_readings_from(entry.get("readings")),
                ),
                route=entry.get("route") or "",
                note=entry.get("note") or "",
            ))
        return cls(kinds)


def _readings_from(stored) -> tuple[Reading, ...]:
    """The per-capability readings a stored source record holds, or none when it predates them.

    A malformed reading is refused rather than dropped: a record that says something unreadable
    about what a run could see must not read back as a record that says nothing.
    """
    if not stored:
        return ()
    if not isinstance(stored, list):
        raise ValueError(f"a source record's readings must be a list, found {type(stored).__name__}")
    out: list[Reading] = []
    for entry in stored:
        if not isinstance(entry, dict):
            raise ValueError(f"a reading must be a mapping, found {entry!r}")
        arms = entry.get("arms") or {}
        if not isinstance(arms, dict):
            raise ValueError(f"a reading's arms must be a mapping, found {arms!r}")
        skipped = entry.get("skipped") or ()
        lost = entry.get("lost") or ()
        out.append(Reading(
            capability=entry.get("capability") or "",
            observed=entry.get("observed"),
            unreadable=entry.get("unreadable") or "",
            arms={str(arm): int(count) for arm, count in arms.items()},
            skipped=tuple(entry for entry in skipped if isinstance(entry, dict)),
            lost=tuple(entry for entry in lost if isinstance(entry, dict)),
        ))
    return tuple(out)


def _check_capabilities(capabilities: Iterable[str]) -> set[str]:
    wanted = set(capabilities)
    unknown = wanted - set(CAPABILITIES)
    if unknown:
        raise ValueError(f"unknown capabilities {sorted(unknown)}; expected a subset of {CAPABILITIES}")
    return wanted


def _merge_arms(readings: Iterable[Reading]) -> dict[str, int]:
    """The per-repository counts behind one capability, summed across the sources that served it."""
    arms: dict[str, int] = {}
    for reading in readings:
        for arm, count in reading.arms.items():
            arms[arm] = arms.get(arm, 0) + int(count)
    return arms


# ---------------------------------------------------------------- the deployment's declarations

def registry(project=None) -> Registry:
    """The sources declared for a run.

    With no project, this is the Quilter deployment: every source this build knows about is
    declared, and Jira and ADO are blocked by policy. That is the state the product will actually be
    in, not a hypothetical one.

    Given a project, only the sources the project names are declared. A project that names no
    tracker has no requirements source at all - a different fact from a blocked one, and one the
    registry reports as a blind spot with its own reason rather than borrowing a policy's.
    """
    kinds: list[SourceKind] = [
        SourceKind.available(
            GITHUB, "GitHub", (CODE, TEST_CODE), route="github-api",
            note=("reached through the existing GitHub collector this build already uses; "
                  "Quilter's MCP transport is out of scope and is not declared here")),
    ]
    if project is None or getattr(project, "jira_key", ""):
        kinds.append(SourceKind.blocked(JIRA, "Jira", (REQUIREMENTS,), QUILTER_NO_PAT,
                                        QUILTER_POLICY))
    if project is None or getattr(project, "ado_org", None):
        kinds.append(SourceKind.blocked(ADO, "Azure DevOps", (TEST_EXECUTION, REQUIREMENTS),
                                        QUILTER_NO_PAT, QUILTER_POLICY))
    return Registry(kinds)


# ---------------------------------------------------------------- reading a stored run

def assessment_for(meta: dict | None, analyser: str) -> Assessment | None:
    """The assessment a stored snapshot supports for one analyser, or ``None`` when not recorded.

    ``None`` is not ``not_assessable``: it means the snapshot predates the registry, so nobody
    recorded what the run could see. A page must say that rather than invent either verdict.
    """
    return _stored_assessment(meta, analyser, "needs")


def consulted_for(meta: dict | None, analyser: str) -> Assessment | None:
    """What the stored snapshot says about the capabilities the analyser only consulted.

    This is a separate question from :func:`assessment_for`: a claim can stand on the sources it
    needs and still record that it was never checked against requirements. Keeping the two apart is
    what stops a blocked tracker making every level claim unreadable.
    """
    return _stored_assessment(meta, analyser, "consults")


def _stored_assessment(meta: dict | None, analyser: str, field: str) -> Assessment | None:
    if not isinstance(meta, dict):
        return None
    record = meta.get("sources")
    analysers = meta.get("analysers")
    spec = analysers.get(analyser) if isinstance(analysers, dict) else None
    if not isinstance(record, dict) or not isinstance(spec, dict) or not spec.get(field):
        return None
    return Registry.from_record(record).assess(spec[field])


def notes(record: dict | None, names: Iterable[str]) -> list[dict]:
    """What the run recorded about each blind spot it named, for a page to render.

    A name the record does not explain keeps ``recorded: False``: the page then says the reason was
    not recorded, which is true, instead of borrowing a reason from somewhere else.
    """
    out: list[dict] = []
    for name in names or ():
        entry = record.get(name) if isinstance(record, dict) else None
        if isinstance(entry, dict):
            out.append({"source": name, "title": entry.get("title") or name,
                        "state": entry.get("state") or "",
                        "reason": entry.get("reason") or "",
                        "blocked_by": entry.get("blocked_by") or "", "recorded": True})
        else:
            out.append({"source": name, "title": name, "state": "", "reason": "",
                        "blocked_by": "", "recorded": False})
    return out
