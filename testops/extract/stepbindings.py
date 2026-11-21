"""Step definitions -> which surface a scenario actually touches.

The layer is inferred from the *code the step calls* (page drivers, API drivers, controllers, repositories),
never from a folder name or a tag. Folder names would hand the analyser the answer, which is the one cheat
the design forbids on a blind specimen.

Two-stage inference, because a step-definition file is mostly plumbing:
  1. Build a map of driver class -> layer by reading each driver's *body* (IPage/Selenium -> ui,
     HttpClient/ExecutePost -> api, IMediator/Controller -> controller).
  2. For each step-definition file, take the highest layer among the driver classes it references.

Namespace and `using` lines are stripped first. A namespace called `Specs.Controller` says nothing about what
the code does, and matching on it collapsed every suite in the control repo to the same layer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Cheapest first. A controller test drives MVC in-process: no network, no serialisation. That is
# cheaper than an HTTP round trip, so controller sits below api.
LAYER_ORDER = ["storage", "engine", "controller", "api", "ui"]

BINDING = re.compile(r'\[(Given|When|Then|And|But)\s*\(\s*"((?:[^"\\]|\\.)*)"', re.I)
HEADER_NOISE = re.compile(r"^\s*namespace\s+[\w.]+", re.M)

SIGNALS = (
    ("ui", (r"\bIPage\b", r"\bPlaywright\b", r"\bSelenium\b", r"\bFindElement\b", r"\bBy\s*\.",
            r"\bGetByRole\b", r"\bClickAsync\b", r"\bPageDriver\b", r"\bIWebDriver\b")),
    ("controller", (r"\bIMediator\b", r"\bIActionResult\b", r"\bsut\s*\.", r"\bControllerBase\b",
                r"new\s+\w+Controller\b", r"\b\w+Controller\s*\(")),
    ("api", (r"\bHttpClient\b", r"\bExecutePost\b", r"\bExecuteGet\b", r"\bApiDriver\b",
             r"\bRestRequest\b", r"\bWebApiResponse\b", r"\bPostAsJsonAsync\b", r"\brequests\b",
             r"\bhttpx\b", r"\burlopen\b", r"System\.Net\.Http", r"\bcontinuity_driver\b",
             r"\bsubprocess\b")),
    ("engine", (r"\bengine\s*\.", r"\bEngineClient\b", r"\badmit\s*\(", r"\bStore\b",
                # A suite that speaks to the product's own driver shim is testing the engine
                # in-process, not over HTTP: the step definition runs the driver, not a client.
                r"\bRunDriverAsync\b", r"\bDriverReply\b")),
    ("storage", (r"\bDbContext\b", r"\bRepository\b", r"\bSqlite\b", r"CREATE TABLE")),
)


@dataclass
class Binding:
    pattern: str
    verb: str
    cls: str
    path: str
    layer: str
    # Step definitions live in per-suite files (BrowserSteps.cs, PanelSteps.cs, ...). Without this, a step text
    # defined in two suites resolves to whichever file was parsed first, and every scenario collapses to one
    # instrument. That is what made all 154 CotW bindings look like API calls.
    suite: str = ""
    # 1-based line of the [Given("...")] attribute, so evidence can link to the binding itself. 0 means
    # the parser did not record it - never a line number it guessed.
    line: int = 0


def highest(layers) -> str:
    known = [l for l in layers if l in LAYER_ORDER]
    return max(known, key=LAYER_ORDER.index) if known else "unknown"


def infer_layer_from_body(text: str) -> str:
    body = HEADER_NOISE.sub("", text)
    found = [layer for layer, pats in SIGNALS if any(re.search(p, body) for p in pats)]
    return highest(found)


def build_driver_map(files: dict[str, str]) -> dict[str, str]:
    """driver class name -> layer, from the driver implementations themselves."""
    out: dict[str, str] = {}
    for path, text in files.items():
        name = path.rsplit("/", 1)[-1]
        if not name.endswith(("Driver.cs", "Driver.py", "Driver.ts")):
            continue
        cls = re.search(r"\bclass\s+(\w+)", text)
        if not cls:
            continue
        layer = infer_layer_from_body(text)
        if layer != "unknown":
            out[cls.group(1)] = layer
    return out


def suite_of(path: str) -> str:
    return _suite_of(path)


def _suite_of(path: str) -> str:
    """Feature and step-def files name the same suite differently: CanonQuerySteps.cs vs canon_query_api.feature.

    Normalise to the shared stem so the two can be matched, and strip the file-type words rather than a fixed
    list of extensions - the order matters, and getting it wrong silently disabled scoping.
    """
    stem = re.sub(r"[^a-z0-9]", "", path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower())
    for suffix in ("feature", "steps", "stepdefs", "stepdefinitions", "cs", "py", "js", "ts"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem


def _suite_matches(feature_suite: str, binding_suite: str) -> bool:
    if not feature_suite or not binding_suite:
        return False
    return feature_suite.startswith(binding_suite) or binding_suite in feature_suite


def parse_file(path: str, text: str, driver_map: dict[str, str] | None = None) -> list[Binding]:
    driver_map = driver_map or {}
    referenced = set(re.findall(r"\b(\w+Driver)\b", text))
    layers = [driver_map[d] for d in referenced if d in driver_map]
    layer = highest(layers) if layers else infer_layer_from_body(text)
    m = re.search(r"\bclass\s+(\w+)", text)
    cls = m.group(1) if m else ""
    suite = _suite_of(path)
    return [Binding(pattern=match.group(2), verb=match.group(1), cls=cls, path=path, layer=layer,
                    suite=suite, line=text.count("\n", 0, match.start()) + 1)
            for match in BINDING.finditer(text)]


def pattern_to_regex(pattern: str) -> re.Pattern:
    """Reqnroll placeholders ({string}, {int}, (.*)) become permissive groups."""
    p = re.escape(pattern)
    p = re.sub(r"\\\{[^}]+\\\}", "(.+?)", p)
    p = p.replace(r"\(\.\*\)", "(.+?)")
    return re.compile("^" + p + "$", re.I)


def match_step(bindings: list[Binding], text: str, suite: str = "") -> Binding | None:
    """Match a step, preferring the suite the feature belongs to.

    Falls back to any suite so an unusual layout still analyses, but the suite-specific binding wins when both
    exist - which is the whole point: the same sentence can be a browser step in one suite and an HTTP step in
    another, and the two are different instruments.
    """
    if suite:
        for b in bindings:
            if not _suite_matches(suite, b.suite):
                continue
            try:
                if pattern_to_regex(b.pattern).match(text):
                    return b
            except re.error:
                continue
    return _match_any(bindings, text)


def _match_any(bindings: list[Binding], text: str) -> Binding | None:
    for b in bindings:
        try:
            if pattern_to_regex(b.pattern).match(text):
                return b
        except re.error:
            continue
    return None