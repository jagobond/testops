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
    """
    surfaces: tuple[Surface, ...]
    state: str
    reason: str = ""
    languages: tuple[tuple[str, int], ...] = ()
    parsed: int = 0        # files this reader could parse

    def record(self) -> dict:
        return {"state": self.state, "surfaces": len(self.surfaces), "parsed": self.parsed,
                "reason": self.reason,
                "languages": [{"suffix": suffix, "count": count}
                              for suffix, count in self.languages]}


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
    for path in sorted(java_files):
        read = java.routes(files[path], path)
        if read is None:
            continue                       # not lexed as Java; not counted as a file this read
        parsed += 1
        for declared in read:
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
    if not surfaces:
        return Discovery((), ZERO, "", languages, parsed)
    return Discovery(surfaces, FOUND, "", languages, parsed)

