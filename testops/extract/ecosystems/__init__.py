"""Ecosystems: what a repository's tests are written *for*, and the vocabulary that reads them.

TESTOPS-42A. Before this module, "the ecosystem" was an assumption baked into one extractor:
`stepbindings.BINDING` was a C# attribute regex, `SIGNALS` named .NET types, and a JavaScript
suite was read with it and returned zero bindings. Zero bindings then became "none of its steps
could be tied to a layer", which is a claim about the suite rather than about the reader.

The seam this module builds is deliberately small, and it is built before anything is plugged into
it:

  * an ecosystem is a **module** under this package with a declared ``name`` and three functions -
    ``detect(files)``, ``bindings(files)`` and ``drivers(files)`` (:class:`EcosystemModule`);
  * the **registry** asks every module in a fixed order and refuses ambiguity: two modules claiming
    the same name raise, two modules recognising the same repository raise, and a repository no
    module recognises raises :class:`UnknownEcosystem`. There is no default and no silent fallback -
    the same lesson as TESTOPS-47, where a missing answer was rendered as a default one;
  * detection returns an :class:`Ecosystem` that says whether this build **supports** it. A detected
    ecosystem that is not supported is a fact the run records and prints, and it stops the
    analysis rather than being read with the wrong vocabulary.

``bindings`` on an unsupported module raises :class:`UnsupportedEcosystem` instead of returning an
empty list. An empty list is the lie this ticket exists to prevent: it says "I looked and there was
nothing", when the truth is "I cannot look". A caller that has checked ``supported`` never sees it.

Nothing here knows about the store, the analysers or the network. The seam is in extraction: the
analysers take ``list[Binding]`` from whichever module produced it and are not told which one did.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable

from ..stepbindings import Binding

__all__ = [
    "Ecosystem",
    "EcosystemModule",
    "Registry",
    "UnknownEcosystem",
    "AmbiguousEcosystem",
    "DuplicateEcosystem",
    "UnsupportedEcosystem",
    "UNSUPPORTED",
    "registry",
    "resolve",
    "unsupported_spot",
]


# A blind spot's state, in the product's own vocabulary: the ecosystem was recognised, and support
# for it does not exist in this build. It is not ``absent`` (the tests are there), not ``blocked``
# (nobody forbade it) and not ``not_readable`` (that is a reader that exists and failed on a file).
UNSUPPORTED = "unsupported"


class UnknownEcosystem(Exception):
    """No module recognised this repository. Deliberately raised, never defaulted."""


class AmbiguousEcosystem(Exception):
    """Two modules recognised the same repository. Naming one would be a guess."""


class DuplicateEcosystem(Exception):
    """Two modules declare the same name. One of them is unreachable, and the other is a coin toss."""


class UnsupportedEcosystem(Exception):
    """Asked an unsupported module to extract bindings. It must not answer with an empty list."""


@dataclass(frozen=True)
class Ecosystem:
    """What a repository's tests are written for, and whether this build can read them.

    ``evidence`` is what in the repository made it recognisable, as counted phrases a record can
    print later ("44 cucumber-js step-binding declarations in 5 files"). It is evidence about
    *detection*; it is never a claim that any of those declarations was read.
    """
    name: str
    title: str
    supported: bool
    evidence: tuple[str, ...] = ()
    # Why support does not exist, in the reader's words. Required when ``supported`` is False:
    # "unsupported" without a reason is the kind of dead end this product refuses to print.
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("an ecosystem needs a name")
        if not self.title.strip():
            raise ValueError(f"ecosystem {self.name!r} needs a title a reader can see")
        if not self.supported and not self.reason.strip():
            raise ValueError(f"ecosystem {self.name!r} is unsupported and must say why")

    def record(self) -> dict:
        """What the store keeps: the facts, without any wording derived from them."""
        return {"ecosystem": self.name, "title": self.title, "supported": self.supported,
                "evidence": list(self.evidence), "reason": self.reason}


@runtime_checkable
class EcosystemModule(Protocol):
    """One ecosystem, as a module implements it.

    ``files`` is ``path -> text`` for the repository arm being read; the module never opens a file
    itself. ``bindings`` returns the same :class:`Binding` rows the Reqnroll extractor always
    returned, so no analyser needs to know which module produced them.
    """

    name: str

    def detect(self, files: Mapping[str, str]) -> Ecosystem | None: ...

    def bindings(self, files: Mapping[str, str]) -> list[Binding]: ...

    def drivers(self, files: Mapping[str, str]) -> Mapping[str, object]: ...


class Registry:
    """The modules this build has, asked in a fixed order.

    Order is not a precedence rule: a repository two modules recognise is an error, not a tie to
    break. The order only makes ``detect`` deterministic, so two runs over the same files agree.
    """

    def __init__(self, modules: tuple[EcosystemModule, ...]):
        if not modules:
            raise ValueError("an ecosystem registry needs at least one module")
        names = [getattr(module, "name", "") for module in modules]
        for module in modules:
            if not isinstance(getattr(module, "name", ""), str) or not module.name.strip():
                raise DuplicateEcosystem(f"module {module!r} declares no name")
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise DuplicateEcosystem(
                f"two ecosystem modules claim the name {duplicates[0]!r}; a name has one module")
        self.modules = tuple(modules)

    def names(self) -> list[str]:
        return [module.name for module in self.modules]

    def match(self, files: Mapping[str, str]) -> tuple[EcosystemModule, Ecosystem]:
        """The one module that recognises this repository, with what it recognised."""
        found: list[tuple[EcosystemModule, Ecosystem]] = []
        for module in self.modules:
            ecosystem = module.detect(files)
            if ecosystem is None:
                continue
            if ecosystem.name != module.name:
                raise DuplicateEcosystem(
                    f"module {module.name!r} detected an ecosystem named {ecosystem.name!r}")
            found.append((module, ecosystem))
        if not found:
            raise UnknownEcosystem(
                f"none of the {len(self.modules)} ecosystems this build knows was recognised in "
                f"the {len(files)} files read ({', '.join(self.names())})")
        if len({ecosystem.name for _module, ecosystem in found}) > 1:
            names = sorted({ecosystem.name for _module, ecosystem in found})
            raise AmbiguousEcosystem(
                f"this repository was recognised as more than one ecosystem ({', '.join(names)}), "
                "so naming one of them would be a guess")
        return found[0]

    def detect(self, files: Mapping[str, str]) -> Ecosystem:
        return self.match(files)[1]

    def module(self, name: str) -> EcosystemModule:
        for module in self.modules:
            if module.name == name:
                return module
        raise UnknownEcosystem(f"no ecosystem module is named {name!r}")


# The modules this build ships. cucumber-js and Python BDD are detected and refused on purpose:
# TESTOPS-42A does not add an extractor for either, and a half-extractor is worse than a refusal.
def _shipped() -> tuple[EcosystemModule, ...]:
    from . import cucumber_js, python_bdd, reqnroll

    return (reqnroll.ECOSYSTEM, python_bdd.ECOSYSTEM, cucumber_js.ECOSYSTEM)


def registry() -> Registry:
    """The registry this build runs with, rebuilt per call so tests can substitute modules."""
    return Registry(_shipped())


def resolve(files: Mapping[str, str]) -> tuple[EcosystemModule, Ecosystem] | tuple[None, None]:
    """The module and ecosystem for these files, or ``(None, None)`` when nothing matches.

    ``(None, None)`` is the honest answer for a repository with no test-binding vocabulary this
    build knows - not a guess and not an exception the pipeline has to swallow to keep going. The
    run records it as ``unknown``. Ambiguity still raises: two matches is a defect here, not a fact
    about the repository.
    """
    try:
        return registry().match(files)
    except UnknownEcosystem:
        return None, None


def unsupported_spot(record: dict | None) -> dict | None:
    """The ecosystem blind spot a stored ``ecosystems`` record implies, or ``None``.

    A page reads a snapshot months later, so the fact "we detected cucumber-js and cannot read it"
    must be reconstructable from the record alone. This is the one reader of that record; the
    assessment in :mod:`testops.sources` uses it so the sentence a reader sees is the sentence the
    run would have produced.
    """
    if not isinstance(record, dict):
        return None
    test = record.get("test")
    if not isinstance(test, dict) or test.get("supported") is not False:
        return None
    title = test.get("title") or test.get("ecosystem") or "the test ecosystem"
    reason = (test.get("reason") or "").strip() or "this build has no support for it"
    return {"source": "ecosystem", "title": title, "state": UNSUPPORTED, "reason": reason}
