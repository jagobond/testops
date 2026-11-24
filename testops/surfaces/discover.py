"""Surface discovery: what the product exposes, and what each surface owns.

Discovery lives in the product, not in the rig. A rig-side inventory would be a crutch that exists nowhere
real, and would let the analyser "find" surfaces it never had to look for.

v0.2 adds the thing v0.1 lacked: **claims**. Without them, "a cheaper surface exists" is true for almost
every scenario in any product, which is how a precision of 0.118 happened.

TESTOPS-41. The reader parsed Python only. Against a Java product it used to return ``[]``, and the
run printed ``"surfaces": 0`` - a zero produced by a reader that could not read, reported like a zero
produced by one that read and found nothing. The two are now different values, and the reason travels
with the second of them: which languages the repository holds, and how many files of each.

TESTOPS-70. A Java product is no longer one of those absent languages. ``.java`` is parsed by
:mod:`testops.surfaces.java` - lexed first, then read for Spring MVC mappings - so a repository whose
routes were read is ``found``, one whose Java declares no route is ``zero``, and ``not_assessable``
is now reserved for a repository holding nothing these readers can parse.

TESTOPS-74. A mapping the reader cannot place is no longer a surface with a guessed route. A
class-level prefix inherited from a superclass or an implemented interface is read from that type
in the same repository, one level, and the resolution is recorded; a type this repository does not
hold, or a path that is not a string literal, makes the mapping ``unread`` with a reason - and
``unread`` is carried on the run, not dropped, so the page can say how many mappings it could not
read and why.

TESTOPS-77. The reason a mapping is unread must be true, because the reason is what a reader acts
on. Type names in a file this reader could not lex are read in code position only - the lexer
consumes comments and literals first, so ``"class BaseController"`` in a string is not a
declaration and a refusal cannot claim the repository holds a type it does not. And every refusal
names the thing that is missing with its own noun: a superclass, an interface, an ambiguous name
held more than once, or - when nothing is missing - two inherited prefixes it cannot choose
between.

The languages this reader can parse are :data:`LANGUAGES`, which is data. Adding one widens the
reader; it does not make a repository it cannot parse look empty.
"""
from __future__ import annotations

import ast
import re
from collections import Counter
from dataclasses import dataclass, field

from . import java

ROUTE = re.compile(r"""["'](/[a-zA-Z0-9_\-/]*)["']""")

# suffix -> language, for the readers below.
LANGUAGES = {".py": "Python", ".java": "Java"}

# What the discovery can say about a product repository. These three never share wording.
FOUND = "found"
ZERO = "zero"
NOT_ASSESSABLE = "not_assessable"


@dataclass
class Surface:
    id: str
    layer: str            # ui | api | engine | storage
    target: str
    claims: list[str] = field(default_factory=list)
    source: str = ""


@dataclass(frozen=True)
class Discovery:
    """The surfaces found, and - just as important - what the reader could not look at.

    ``state`` is ``found`` (there are surfaces), ``zero`` (this reader read the files and found
    none) or ``not_assessable`` (there was nothing here it could read, with the language and the
    file count in ``reason``). A caller must not print the second and the third the same way.

    ``unread`` is the mappings the reader saw but could not turn into a route: a constant path, or a
    class prefix it could not resolve. They are here so the run can report them; a mapping in this
    list has no surface, because a route the reader invented is worse than a route it did not read.
    ``inherited`` records every prefix it recovered from a superclass, so the resolution is a fact a
    reader can check rather than an assumption.
    """
    surfaces: tuple[Surface, ...]
    state: str
    reason: str = ""
    languages: tuple[tuple[str, int], ...] = ()
    parsed: int = 0        # files this reader could parse
    unread: tuple[java.Unread, ...] = ()
    inherited: tuple[dict, ...] = ()

    def record(self) -> dict:
        return {"state": self.state, "surfaces": len(self.surfaces), "parsed": self.parsed,
                "reason": self.reason,
                "languages": [{"suffix": suffix, "count": count}
                              for suffix, count in self.languages],
                "unread": [entry.record() for entry in self.unread],
                "inherited_prefixes": [dict(entry) for entry in self.inherited]}


def _first_sentence(text: str) -> str:
    text = " ".join(text.split())
    for stop in (". ", "; "):
        if stop in text:
            return text.split(stop)[0].strip()
    return text.strip()


def _humanise(name: str) -> str:
    return name.replace("_", " ").strip()


def _suffix(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    if "." not in name.lstrip("."):
        return "(no suffix)"
    return "." + name.rsplit(".", 1)[1]


def _languages(files: dict[str, str]) -> tuple[tuple[str, int], ...]:
    counts = Counter(_suffix(path) for path in files)
    return tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _reader() -> str:
    """The reader's languages, said in a sentence: ``Python (.py) and Java (.java)``."""
    named = [f"{name} ({suffix})" for suffix, name in LANGUAGES.items()]
    if len(named) < 2:
        return "".join(named)
    return ", ".join(named[:-1]) + " and " + named[-1]


def _declared_type_names(text: str) -> list[str]:
    """The type names a file declares, read from its lexer's token stream (TESTOPS-77 AC1).

    The file is unlexable only in the sense that its delimiters do not balance - the lexer still
    consumes comments, string literals, character literals and text blocks, so a ``class X`` inside
    a string or a comment is a literal's contents, not a declaration. Reading the token stream is
    what makes that true; a regex over the raw text, even with comments stripped, would harvest
    ``\"class BaseController ...\"`` and let a refusal claim the repository *holds* a type it does
    not. A word follows the keyword in code position, and ``Foo.class`` (a class literal) is not a
    declaration because its keyword is preceded by a dot.
    """
    tokens = java.lex(text)
    names: list[str] = []
    for index, token in enumerate(tokens[:-1]):
        if token.kind != "word" or token.value not in java.TYPE_KEYWORDS:
            continue
        if index and tokens[index - 1].value == ".":
            continue
        following = tokens[index + 1]
        if following.kind == "word":
            names.append(following.value)
    return names


def _not_read(kind: str) -> str:
    """The reason for a type that could not be read, with the noun for how it was inherited."""
    return java.REASON_INTERFACE_NOT_READ if kind == "interface" else java.REASON_PREFIX_NOT_READ


def _inherited_prefix(name: str, path: str, declared_types: dict[str, list[str]],
                      unreadable_types: dict[str, list[str]],
                      readings: dict[str, java.Reading],
                      kind: str = "superclass"
                      ) -> tuple[tuple[str, ...] | None, str | None, tuple[str, str] | None]:
    """The prefix a class-level ``@RequestMapping`` on ``name`` supplies, or why it cannot be known.

    Returns ``(prefix, file, None)`` when the type is held once and declares a literal prefix;
    ``(None, None, None)`` when it is held once and declares no prefix at all (there is none to
    drop); and ``(None, None, (reason, detail))`` when knowing it would take a guess. ``kind`` is
    how the type reached the class - ``superclass`` or ``interface`` - and it picks the noun in the
    reason: a refusal that arrived through an interface must not call the interface a superclass.
    The reason carried for a parent whose own prefix is a constant is the parent's own, named
    against the parent, so the child is refused for the fact that made the parent unreadable.
    """
    simple = name.rsplit(".", 1)[-1]
    candidates = [candidate for candidate in declared_types.get(simple, []) if candidate != path]
    if len(candidates) > 1:
        return None, None, (java.REASON_TYPE_AMBIGUOUS,
                            f"{name}, which this repository holds more than once "
                            f"({', '.join(candidates)})")
    if not candidates:
        held = unreadable_types.get(simple, [])
        if held:
            return None, None, (_not_read(kind),
                                f"{name} ({held[0]}), which this repository holds but this "
                                f"reader could not read")
        return None, None, (_not_read(kind),
                            f"{name}, which this repository does not hold")
    parent = readings[candidates[0]]
    if parent.class_problem is not None:
        reason, expression = parent.class_problem
        return None, None, (reason, f"{name}, whose own prefix could not be read "
                                    f"({reason}: {expression})")
    if parent.own_prefix is not None:
        return parent.own_prefix, candidates[0], None
    if parent.superclass:
        return None, None, (_not_read(kind),
                            f"{name}, whose own prefix is inherited from {parent.superclass} "
                            f"(this reader reads one level)")
    return None, None, None


def _refusal(refusals: list[tuple[str, str, tuple[str, str]]]) -> tuple[str, str]:
    """One reason for one or more types that could not supply a prefix, saying what is missing.

    One source keeps its own reason and detail. Several sources are named together, each with its
    kind, so the sentence is true of every one of them rather than only of whichever came first:
    when their reasons agree, that reason is the summary; when they do not, the summary names no
    single type as missing and the detail names each (TESTOPS-77 AC2).
    """
    if len(refusals) == 1:
        _kind, _name, why = refusals[0]
        return why
    reasons = {why[0] for _kind, _name, why in refusals}
    reason = reasons.pop() if len(reasons) == 1 else java.REASON_PREFIX_SOURCES_UNREAD
    detail = "; ".join(f"{kind} {why[1]}" for kind, _name, why in refusals)
    return reason, detail


def discover(files: dict[str, str]) -> Discovery:
    """files: path -> text for the product repo. Returns the surfaces, and what it could read."""
    routes: dict[str, Surface] = {}
    modules: list[Surface] = []
    python_files = [path for path in files if path.endswith(".py")]
    java_files = [path for path in files if path.endswith(".java")]
    parsed = len(python_files)

    for path in python_files:
        text = files[path]
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue

        # Route handlers: the route literal sits inside a function whose docstring says what it is for.
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            segment = ast.get_source_segment(text, node) or ""
            found = [m.group(1) for m in ROUTE.finditer(segment)
                     if not m.group(1).startswith("//") and m.group(1) not in ("/", "")]
            if not found:
                continue
            doc = _first_sentence(ast.get_docstring(node) or "") or _humanise(node.name)
            is_json = bool(re.search(r"json\.dumps|application/json|JSONResponse|to_json", segment)) \
                or any("/api/" in r for r in found)
            layer = "api" if is_json else "ui"
            for route in found:
                sid = f"{layer}:{route}"
                if sid not in routes:
                    routes[sid] = Surface(id=sid, layer=layer, target=route, claims=[doc], source=path)
                elif doc not in routes[sid].claims:
                    routes[sid].claims.append(doc)

        # Engine modules: each public function is a claim-bearing surface.
        if "/src/" in f"/{path}" and path.endswith(".py") and "__init__" not in path:
            claims = []
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                    doc = _first_sentence(ast.get_docstring(node) or "")
                    claims.append(doc or _humanise(node.name))
            if claims:
                modules.append(Surface(id=f"engine:{path}", layer="engine", target=path,
                                       claims=claims[:8], source=path))

    # Spring MVC: a route is what a mapping annotation says, prefixed by its class's @RequestMapping.
    # Two methods that map the same route are two surfaces - the duplicate is a fact worth showing -
    # so the id carries the source and the method, and never collapses two declarations into one.
    readings: dict[str, java.Reading] = {}
    for path in java_files:
        reading = java.read(files[path], path)
        if reading is None:
            continue                       # not lexed as Java; not counted as a file this read
        parsed += 1
        readings[path] = reading

    # TESTOPS-74 AC1. A class-level prefix can live on a superclass or on an interface the class
    # implements; Spring honours both, so both are read - one level, no more - from this repository,
    # and every resolution is recorded. When the type is not held, is held more than once, or its
    # own prefix could not be read, every mapping under the subclass is unread and names the type it
    # needed: the alternative is emitting ``GET /{id}`` for a route that is really
    # ``GET /booking/{id}``. A refusal is never dropped just because it arrived through an interface.
    declared_types: dict[str, list[str]] = {}
    unreadable_types: dict[str, list[str]] = {}
    for path in sorted(readings):
        name = readings[path].type_name
        if name:
            declared_types.setdefault(name, []).append(path)
    for path in java_files:
        if path in readings:
            continue
        # A file this repository holds but that does not lex may still declare the type a
        # subclass needs. Its declarations are readable without lexing it, and saying "held but
        # not read" keeps the refusal true: the file is there (review 2026-11-24, concern 3).
        for name in _declared_type_names(files[path]):
            unreadable_types.setdefault(name, []).append(path)

    inherited: list[dict] = []
    for path in sorted(readings):
        reading = readings[path]
        if reading.own_prefix is not None or reading.class_problem is not None:
            continue                       # its own prefix answers the question, or already refuses
        sources: list[tuple[str, str]] = []
        if reading.superclass:
            sources.append(("superclass", reading.superclass))
        sources.extend(("interface", name) for name in reading.interfaces)
        if not sources:
            continue
        prefixes: list[tuple[str, str, str | None, tuple[str, ...]]] = []
        refusals: list[tuple[str, str, tuple[str, str]]] = []
        for kind, name in sources:
            prefix, read_from, why = _inherited_prefix(
                name, path, declared_types, unreadable_types, readings, kind)
            if why is not None:
                refusals.append((kind, name, why))  # never reflected in the route below
            elif prefix is not None:
                prefixes.append((kind, name, read_from, prefix))
        if refusals:
            readings[path] = java.read(files[path], path,
                                       unresolved=_refusal(refusals)) or reading
            continue
        if len(prefixes) > 1:
            # Nothing is missing here: the class has two inherited prefixes, so the reader cannot
            # say which one the route sits under. Say that, and name both types (TESTOPS-77 AC2).
            named = " and ".join(f"{kind} {name}" for kind, name, _from, _prefix in prefixes)
            readings[path] = java.read(files[path], path, unresolved=(
                java.REASON_PREFIX_MULTIPLE,
                f"{named}, whose prefixes it inherits through more than one type "
                f"(this reader reads one level)")) or reading
            continue
        if not prefixes:
            continue                       # the types are here and declare no prefix to drop
        kind, name, read_from, prefix = prefixes[0]
        readings[path] = java.read(files[path], path, inherited=prefix) or reading
        inherited.append({"source": path, "type": reading.type_name, kind: name,
                          "read_from": read_from, "prefix": list(prefix)})

    unread: list[java.Unread] = []
    for path in sorted(readings):
        declared_routes = readings[path]
        unread.extend(declared_routes.unread)
        for declared in declared_routes.routes:
            target = f"{declared.verb} {declared.path}"
            sid = f"api:{target}@{path}:{declared.method}"
            if sid in routes:
                number = 2
                while f"{sid}#{number}" in routes:
                    number += 1
                sid = f"{sid}#{number}"
            routes[sid] = Surface(id=sid, layer="api", target=target,
                                  claims=list(declared.claims), source=path)

    surfaces = tuple(sorted(routes.values(), key=lambda s: s.id) + modules)
    languages = _languages(files)
    reader = _reader()
    if not parsed:
        # Nothing here this reader could parse. Say what was there, not "0 surfaces".
        if not files:
            reason = ("this run fetched no product file at all, so there was nothing for the surface "
                      "reader to look at")
        else:
            held = ", ".join(f"{count} {suffix}" for suffix, count in languages[:4])
            reason = (f"the surface reader parses {reader} only, and the product repository holds no "
                      f"file it can read: {held}" + (", ..." if len(languages) > 4 else ""))
        return Discovery((), NOT_ASSESSABLE, reason, languages, 0)
    if not surfaces and not unread:
        return Discovery((), ZERO, "", languages, parsed)
    return Discovery(surfaces, FOUND, "", languages, parsed, tuple(unread),
                     tuple(inherited))

