"""Surface discovery: what the product exposes, and what each surface owns.

Discovery lives in the product, not in the rig. A rig-side inventory would be a crutch that exists nowhere
real, and would let the analyser "find" surfaces it never had to look for.

v0.2 adds the thing v0.1 lacked: **claims**. Without them, "a cheaper surface exists" is true for almost
every scenario in any product, which is how a precision of 0.118 happened.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

ROUTE = re.compile(r"""["'](/[a-zA-Z0-9_\-/]*)["']""")


@dataclass
class Surface:
    id: str
    layer: str            # ui | api | engine | storage
    target: str
    claims: list[str] = field(default_factory=list)
    source: str = ""


def _first_sentence(text: str) -> str:
    text = " ".join(text.split())
    for stop in (". ", "; "):
        if stop in text:
            return text.split(stop)[0].strip()
    return text.strip()


def _humanise(name: str) -> str:
    return name.replace("_", " ").strip()


def discover(files: dict[str, str]) -> list[Surface]:
    """files: path -> text for the product repo. Returns deduplicated surfaces with claims."""
    routes: dict[str, Surface] = {}
    modules: list[Surface] = []

    for path, text in files.items():
        if not path.endswith(".py"):
            continue
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

    return sorted(routes.values(), key=lambda s: s.id) + modules
