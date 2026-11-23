"""cucumber-js: the declarations, the commands they call, and the layer that happens in.

TESTOPS-42C-2 is part 2 of 3. Part 1 (T42C-1) read the 44 declarations in both layouts. Part 2
answers the question the inventory's §3 raises: the layer is **per command, not per file.**
``room-management.js`` holds ``createRoom`` (browser) beside ``createRoomViaApi`` (HTTP), and
``login.js`` holds ``loginViaUI`` beside ``loginViaApi``. A file-level answer would be wrong for
one of each pair whichever way it fell, so this module resolves a layer for every command and
every declaration separately, by following:

    step body -> ``cy.<customCommand>(...)`` -> one level of module-local helper -> the JS signal

Where the chain does not reach a signal the answer is ``unknown`` and the reason is recorded on
the row - never a guess. Placement is still switched off: ``detect`` returns an unsupported
ecosystem, so the pipeline keeps the run ``not_assessable`` and the analysers are unchanged. The
claim wiring is T42C-3's.

Why the parse is not line-oriented: 16 of the 44 declarations put the opening parenthesis at the
end of a line and the pattern on the next. A line-oriented scan reports 28, which is the defect
that made counting-before-costing necessary (docs/ecosystem-inventory-cucumber-js.md §2).

Refusals, not truncations. Three declaration shapes cannot be read honestly by this build and are
refused loudly rather than returned short:

* a regular-expression literal (``Given(/^...$/)``) - this corpus has none;
* a pattern split across a string concatenation (``'half/' + 'rest {string}'``) - this corpus has
  none, but the first attempt at part 1 returned the first half silently, so the refusal is here
  before it can happen to the next corpus. The review of T42C-1 recorded that probe.

The JS/TS vocabulary is **not** ``stepbindings.SIGNALS``. That table names .NET types, and two of
its entries fire on JavaScript by accident - see :data:`DOTNET_ONLY_SIGNALS`. ``LAYER_ORDER``
stays shared because the analysers, the verdicts and the prose are written in those layer names.

Two measured qualifications of the signal table, both required by this corpus:

* ``cy.get('@alias')`` retrieves a value stored with ``.as()``, and ``cy.get(<array>)`` iterates
  data; neither touches the page. Only a **selector literal** is a browser command. Without that
  distinction ``createRoomViaApi`` reads as ``ui`` because of its ``cy.get('@roomIds')`` plumbing,
  and the per-command test would have nothing to prove.
* ``Step(this, '...')`` re-invokes another step by text that is assembled at run time. It is not
  followed, and the row says so instead of inheriting a layer from anywhere.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from ..stepbindings import Binding, LAYER_ORDER, highest, suite_of
from . import Ecosystem, UnsupportedEcosystem

NAME = "cucumber-js"
TITLE = "cucumber-js"
REASON = ("this build can read JavaScript step definitions and follow them to the call that does the "
          "work, but placing a cucumber-js claim is not wired yet, so it will not guess what they do")

KEYWORDS = ("Given", "When", "Then", "And", "But")
SPACE = " \t\r\n"

# A declaration starts a line with the keyword (or `this.`), then its opening parenthesis. The
# quoting character after it decides the syntax and is captured separately. The gap is captured so
# the layout can be reported, and it explicitly contains newlines: the expression is not
# line-oriented.
DECLARATION = re.compile(
    r"^[ \t]*(?P<this>this\.)?(?P<verb>Given|When|Then|And|But)"
    r"[ \t]*\((?P<gap>[ \t\r\n]*)(?P<quote>['\"`/])",
    re.M)
CUSTOM_COMMAND = re.compile(
    r"Cypress\.Commands\.(?P<kind>add|overwrite|addAll)\s*\(\s*"
    r"(?P<quote>['\"`])(?P<name>[^'\"`]+)(?P=quote)")

# A file is a step-definition file when its path says so or it imports a cucumber binding module.
# Without this, `Then(` in a Jest file would be counted as a binding declaration.
STEP_FILE = re.compile(r"(stepdef|steps?/|\.cy\.[jt]s$|/steps/|_steps\.[jt]s$)", re.I)
CUCUMBER_IMPORT = re.compile(r"['\"][^'\"]*cucumber[^'\"]*['\"]", re.I)

# A `cy.<name>(` call is how a custom command is invoked. `cy.get` and friends are signals, not
# commands, and are not in the command index, so the intersection below cannot mistake one.
CY_CALL = re.compile(r"\bcy\.(\w+)\s*\(")
STEP_DELEGATION = re.compile(r"\bStep\s*\(\s*this\b")

# Module-local helpers, one level deep: `const name = (...) => ...` and `function name(...) {...}`.
HELPER_ARROW = re.compile(r"^[ \t]*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?"
                          r"(?:\([^)]*\)|\w+)\s*=>", re.M)
HELPER_FUNCTION = re.compile(r"^[ \t]*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(", re.M)

# The JS/TS signal table: layer -> token -> pattern. Separate from `stepbindings.SIGNALS` on
# purpose (inventory §6: the .NET table names types, this one must name calls), and it shares only
# the layer names and their order.
JS_SIGNALS: dict[str, dict[str, str]] = {
    "ui": {
        # A selector literal, not an alias (`cy.get('@x')`) and not a data expression
        # (`cy.get(response.body.rooms)`). See the module docstring.
        "cy.get": r"cy\.get\(\s*['\"`](?!@)",
        "cy.contains": r"cy\.contains\(",
        "cy.xpath": r"cy\.xpath\(",
        "cy.visit": r"cy\.visit\(",
        ".click": r"\.click\(",
        ".type": r"\.type\(",
        ".select": r"\.select\(",
        ".should": r"\.should\(",
    },
    "api": {
        "cy.request": r"cy\.request\(",
        "supertest": r"\bsupertest\b",
        "axios": r"\baxios\b",
        "fetch(": r"\bfetch\(",
    },
    "storage": {
        "prisma": r"\bprisma\b",
        "knex": r"\bknex\b",
        "mongoose": r"\bmongoose\b",
    },
}

# ---- the .NET-only signals, stated because two of them fire on JS by accident (AC5) ------------
#
# `stepbindings.SIGNALS` is the .NET vocabulary: it names **types**, not calls. These entries look
# framework-generic but are not, and every one of them is deliberately absent from `JS_SIGNALS`:
#
#   storage  \bRepository\b   a very common JavaScript class name. It fires on JS 0 times in this
#                             corpus, but the day it does, it produces a confidently wrong
#                             "storage" layer instead of an honest unknown.
#   ui       \bPlaywright\b   matches `GetByRole`/`ClickAsync`, which are the **.NET** Playwright
#                             spellings. JavaScript Playwright writes `getByRole(` (lower-case g)
#                             and `click(` - neither matches. So this signal is not evidence of JS
#                             Playwright support, and is not counted as any.
#   ui       \bGetByRole\b, \bClickAsync\b, \bIPage\b, \bIWebDriver\b, \bSelenium\b, \bFindElement\b,
#            \bPageDriver\b, \bBy\s*\.        C# type and method names.
#   api      \bHttpClient\b, \bExecutePost\b, \bExecuteGet\b, \bApiDriver\b, \bRestRequest\b,
#            \bWebApiResponse\b, \bPostAsJsonAsync\b, System\.Net\.Http   .NET types and namespaces.
#   storage  \bDbContext\b, \bSqlite\b, CREATE TABLE
#   engine   \bengine\s*\.     \bEngineClient\b, \badmit\s*\(, \bStore\b, \bRunDriverAsync\b,
#            \bDriverReply\b
#   controller  \bIMediator\b, \bIActionResult\b, \bsut\s*\.   \bControllerBase\b, *Controller
#
# Nothing in the JS path reads `stepbindings.SIGNALS`; the guard below fails the import if the two
# tables ever share a pattern, so the accident cannot be reintroduced by an edit.
DOTNET_ONLY_SIGNALS: dict[str, tuple[str, ...]] = {
    "ui": (r"\bIPage\b", r"\bPlaywright\b", r"\bSelenium\b", r"\bFindElement\b", r"\bBy\s*\.",
           r"\bGetByRole\b", r"\bClickAsync\b", r"\bPageDriver\b", r"\bIWebDriver\b"),
    "controller": (r"\bIMediator\b", r"\bIActionResult\b", r"\bsut\s*\.", r"\bControllerBase\b"),
    "api": (r"\bHttpClient\b", r"\bExecutePost\b", r"\bExecuteGet\b", r"\bApiDriver\b",
            r"\bRestRequest\b", r"\bWebApiResponse\b", r"\bPostAsJsonAsync\b", r"System\.Net\.Http"),
    "engine": (r"\bengine\s*\.", r"\bEngineClient\b", r"\badmit\s*\(", r"\bStore\b",
               r"\bRunDriverAsync\b", r"\bDriverReply\b"),
    "storage": (r"\bDbContext\b", r"\bRepository\b", r"\bSqlite\b", r"CREATE TABLE"),
}


def _guard_tables_are_disjoint() -> None:
    net = {pattern for patterns in DOTNET_ONLY_SIGNALS.values() for pattern in patterns}
    js = {pattern for tokens in JS_SIGNALS.values() for pattern in tokens.values()}
    shared = sorted(net & js)
    if shared:
        raise RuntimeError(
            "the JS/TS signal table must not contain a .NET-only signal: " + ", ".join(shared))


_guard_tables_are_disjoint()


@dataclass(frozen=True)
class Declaration:
    """One declaration, as read - before it becomes a :class:`Binding`."""

    verb: str
    pattern: str
    path: str
    line: int
    quote: str
    layout: str
    regex: bool
    world_style: bool
    # The steps the declaration's body makes, so a layer can be found where the work happens.
    body: str = ""
    # A pattern split across `'a/' + 'b'`. Recorded so `bindings` can refuse it: the first part
    # alone is a pattern that matches nothing, and returning it silently is the undercount this
    # module exists to prevent.
    concatenated: bool = False


@dataclass(frozen=True)
class CustomCommand:
    """One ``Cypress.Commands.add`` registration, with the layer its own body resolves to."""

    name: str
    path: str
    line: int
    body: str
    kind: str = "add"
    layer: str = "unknown"
    reason: str = ""
    via: tuple[str, ...] = ()


def _is_step_file(path: str, text: str) -> bool:
    return bool(STEP_FILE.search(path) or CUCUMBER_IMPORT.search(text))


def _skip_quote(text: str, start: int) -> int:
    """Index just past the closing quote, honouring escapes; ``len(text)`` if unterminated."""
    quote = text[start]
    i = start + 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == quote:
            return i + 1
        i += 1
    return len(text)


def _strip_comments(text: str) -> str:
    """Comments are not statements - excluded by parsing, not by knowing which file they are in.

    Quote-aware, so ``'https://images.example/x.jpeg'`` is not mistaken for a comment. Line
    numbers survive: newlines are kept, and a block comment is replaced by the newlines it spanned.
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        char = text[i]
        if char in "'\"`":
            end = _skip_quote(text, i)
            out.append(text[i:end])
            i = end
            continue
        if char == "/" and i + 1 < n and text[i + 1] == "/":
            end = text.find("\n", i)
            i = n if end < 0 else end
            continue
        if char == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            chunk = text[i:] if end < 0 else text[i:end + 2]
            out.append("\n" * chunk.count("\n"))
            i = n if end < 0 else end + 2
            continue
        out.append(char)
        i += 1
    return "".join(out)


def _block(text: str, pos: int) -> tuple[int, int]:
    """``(start, end)`` of the first balanced ``{...}`` at or after ``pos``; ``(-1, -1)`` if none.

    Quotes are skipped, so a brace inside a string or a template literal cannot unbalance the walk.
    """
    start = text.find("{", pos)
    if start < 0:
        return -1, -1
    depth = 0
    i = start
    while i < len(text):
        char = text[i]
        if char in "'\"`":
            i = _skip_quote(text, i)
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    return -1, -1


def _body_after(text: str, pos: int) -> str:
    """The brace body of a function whose parameter list ends before ``pos``."""
    start, end = _block(text, pos)
    # A `{...}` block immediately followed by `=>` is a destructured parameter list, not the body.
    while start >= 0 and re.match(r"\s*=>", text[end:]):
        start, end = _block(text, end)
    # `_block` returns the index just past the closing brace; the body excludes both braces.
    return "" if start < 0 else text[start + 1:end - 1]


def _statement_end(text: str, pos: int) -> int:
    """Index of the ``;`` that ends the statement at ``pos`` (or the line break that ends it)."""
    depth = 0
    i = pos
    while i < len(text):
        char = text[i]
        if char in "'\"`":
            i = _skip_quote(text, i)
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                return i
            depth -= 1
        elif char == ";" and depth == 0:
            return i
        elif char == "\n" and depth == 0:
            return i
        i += 1
    return len(text)


def _skip_space(text: str, pos: int) -> int:
    i = pos
    while i < len(text) and text[i] in SPACE:
        i += 1
    return i


def _arrow_body(text: str, pos: int) -> str:
    """The body of an arrow function whose ``=>`` ends before ``pos``.

    Brace bodies are returned without their braces; an expression body is returned as its text up
    to the end of the statement. Returning a brace body for an expression-bodied arrow was the way
    this function could have swallowed the *next* function's body - the reason it is explicit.
    """
    i = _skip_space(text, pos)
    if i < len(text) and text[i] == "{":
        return _body_after(text, i)
    end = _statement_end(text, i)
    return text[i:end]


def _call_body(text: str, open_paren: int) -> str:
    """The body of the call whose ``(`` is at ``open_paren``, skipping the parameter list."""
    depth = 0
    i = open_paren
    while i < len(text):
        char = text[i]
        if char in "'\"`":
            i = _skip_quote(text, i)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                j = _skip_space(text, i + 1)
                if text.startswith("=>", j):
                    return _arrow_body(text, j + 2)
                return _body_after(text, i + 1)
        i += 1
    return ""


def _command_body(text: str, pos: int) -> str:
    """Body of ``Cypress.Commands.add('name', <options?>, <fn>)``, given ``pos`` after the name."""
    i = _skip_space(text, pos)
    if i < len(text) and text[i] == ",":
        i = _skip_space(text, i + 1)
    if i < len(text) and text[i] == "{":
        # The `{ prevSubject: ... }` options object; the function follows it.
        _start, end = _block(text, i)
        i = _skip_space(text, end)
        if i < len(text) and text[i] == ",":
            i = _skip_space(text, i + 1)
    if i < len(text) and text[i] == "(":
        return _call_body(text, i)
    return _body_after(text, i)


def _files(files: Mapping[str, str]) -> dict[str, str]:
    return {path: text for path, text in files.items()
            if path.endswith((".js", ".ts")) and not path.endswith(".d.ts")}


def suite_of_path(path: str) -> str:
    """The suite a feature or step-definition file belongs to.

    The corpus co-locates a suite's ``.feature`` files with its ``.stepdef.js``; the directory is
    therefore the suite, and the existing stem rule is applied to it. This is the rule that makes
    all six features resolve (booking's two features share ``booking``; contact's two share
    ``contact``) and it is why the filename stem alone is not used: ``book-a-room.feature`` and
    ``booking.stepdef.js`` do not share a filename stem, and neither do ``contact-hotel.feature``
    and ``background.stepdef.js``. The stem rule, measured, gives ``bookingstepdef`` and matches
    0 of this corpus's 5 step-definition files (docs/ecosystem-inventory-cucumber-js.md,
    Corrections 2026-11-23).
    """
    normalised = path.replace("\\", "/")
    parent = normalised.rsplit("/", 1)[0] if "/" in normalised else ""
    return suite_of(parent)


def _string_close(text: str, start: int, quote: str) -> int:
    i = start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == quote:
            return i
        i += 1
    raise ValueError("unterminated string literal")


def _regex_close(text: str, start: int) -> int:
    """End of a regex literal, respecting escapes and character classes."""
    i = start
    in_class = False
    while i < len(text):
        char = text[i]
        if char == "\\":
            i += 2
            continue
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif char == "/" and not in_class:
            return i
        elif char == "\n":
            break
        i += 1
    raise ValueError("unterminated regular-expression literal")


def _is_concatenated(text: str, close: int, quote: str) -> bool:
    """True when the pattern string is immediately followed by ``+``, i.e. it is only one half."""
    if quote == "/":
        return False
    rest = text[close + 1:]
    stripped = rest.lstrip(" \t\r\n")
    return stripped.startswith("+")


def _declarations_in(path: str, text: str) -> list[Declaration]:
    cleaned = _strip_comments(text)
    out: list[Declaration] = []
    for match in DECLARATION.finditer(cleaned):
        quote = match.group("quote")
        start = match.end()
        close = _regex_close(cleaned, start) if quote == "/" else _string_close(cleaned, start, quote)
        concatenated = _is_concatenated(cleaned, close, quote)
        body = "" if concatenated else _command_body(cleaned, close + 1)
        out.append(Declaration(
            verb=match.group("verb"), pattern=cleaned[start:close], path=path,
            line=cleaned.count("\n", 0, match.start()) + 1, quote=quote,
            layout="next-line" if "\n" in match.group("gap") else "same-line",
            regex=quote == "/", world_style=bool(match.group("this")),
            body=body, concatenated=concatenated))
    return out


def parse_declarations(files: Mapping[str, str]) -> list[Declaration]:
    """Every declaration in every step-definition file, in file then source order."""
    out: list[Declaration] = []
    for path, text in sorted(_files(files).items()):
        if not _is_step_file(path, text):
            continue
        out.extend(_declarations_in(path, text))
    return out


# ------------------------------------------------------------------ the JS/TS layer vocabulary

def signals_in(text: str) -> list[tuple[str, str]]:
    """Every ``(layer, token)`` whose pattern matches ``text``, in table order."""
    return [(layer, token) for layer, tokens in JS_SIGNALS.items()
            for token, pattern in tokens.items() if re.search(pattern, text)]


def infer_layer_from_body(text: str) -> str:
    """The layer of one body, read with the JS/TS table only. ``unknown`` when nothing matches."""
    return highest([layer for layer, _token in signals_in(text)])


# ------------------------------------------------------------------ helpers and commands

def helper_bodies(text: str) -> dict[str, str]:
    """Module-local function bodies: ``const x = (...) => {...}`` and ``function x(...) {...}``."""
    out: dict[str, str] = {}
    for match in HELPER_ARROW.finditer(text):
        out[match.group(1)] = _body_after(text, match.end())
    for match in HELPER_FUNCTION.finditer(text):
        out.setdefault(match.group(1), _call_body(text, match.end() - 1))
    return out


def _local_signals(body: str, helpers: Mapping[str, str]) -> tuple[list[tuple[str, str]], list[str]]:
    """Signals in ``body`` plus **one level** of the module-local helpers it calls.

    One level, deliberately: a helper that calls a helper is not followed, because the second hop
    stops being evidence and starts being a search. The row records that it stopped.
    """
    found = signals_in(body)
    called = [name for name in helpers if re.search(rf"\b{re.escape(name)}\s*\(", body)]
    for name in called:
        found.extend(signals_in(helpers[name]))
    return found, called


def _reason_and_layer(body: str, helpers: Mapping[str, str], commands: Mapping[str, CustomCommand],
                      known_commands: frozenset[str]) -> tuple[str, str, tuple[str, ...]]:
    """``(layer, reason, via)`` for one body. ``reason`` is empty when the layer resolved.

    ``commands`` is the resolved index a caller wants followed (declarations: all of it);
    ``known_commands`` is every registered name, so a body that calls a command *without* it being
    followed says so instead of reporting that nothing was called.
    """
    found, helpers_called = _local_signals(body, helpers)
    layers = [layer for layer, _token in found]
    via = list(dict.fromkeys(token for _layer, token in found))
    via.extend(f"{name}()" for name in helpers_called)

    cy_calls = list(dict.fromkeys(CY_CALL.findall(body)))
    command_calls = [name for name in cy_calls if name in known_commands]
    called_and_followed = [name for name in command_calls if name in commands]
    called_and_unknown: list[tuple[str, str]] = []
    for name in called_and_followed:
        command = commands[name]
        if command.layer == "unknown":
            called_and_unknown.append((name, command.reason))
            continue
        layers.append(command.layer)
        via.extend([f"cy.{name}()", *(f"cy.{name}() -> {step}" for step in command.via)])

    if layers:
        return highest(layers), "", tuple(dict.fromkeys(via))

    if not body.strip():
        return "unknown", "the body could not be read from the source: no {...} block follows it", ()
    if STEP_DELEGATION.search(body):
        return ("unknown", "the body re-invokes another step by text (Step(this, ...)); the text is "
                           "assembled at run time, so this build does not follow it", tuple(via))
    if called_and_unknown:
        detail = "; ".join(f"cy.{name}(): {reason}" for name, reason in called_and_unknown)
        return ("unknown", f"the body calls {', '.join('cy.' + n + '()' for n, _ in called_and_unknown)}"
                           f", which this build could not resolve to a cy.* signal ({detail})",
                tuple(via))
    if command_calls:
        return ("unknown", f"the body calls {', '.join('cy.' + n + '()' for n in command_calls)}, "
                           "another custom command; a command's own body is the unit here, so it "
                           "contributes no signal", tuple(via))
    if helpers_called:
        return ("unknown", f"the body calls the module-local helpers "
                           f"{', '.join(name + '()' for name in helpers_called)}, which reach no "
                           "JS signal", tuple(via))
    if cy_calls:
        return ("unknown", f"the body calls {', '.join('cy.' + n + '()' for n in cy_calls)}, none "
                           "of which matches a JS signal and none of which is a registered "
                           "Cypress command", tuple(via))
    return ("unknown", "the body calls no cy.* command, no custom command and no module-local "
                       "helper", ())


def _commands(files: Mapping[str, str]) -> dict[str, CustomCommand]:
    """Every real ``Cypress.Commands.add`` registration, with the layer of its own body.

    Comments are stripped first, so the four commented-out registrations in this corpus's sample
    ``commands.js`` are excluded because they are comments - not because of which file they are in.
    """
    sources = {path: _strip_comments(text) for path, text in sorted(_files(files).items())}
    helpers = {path: helper_bodies(text) for path, text in sources.items()}
    drafts: list[CustomCommand] = []
    for path, text in sources.items():
        for match in CUSTOM_COMMAND.finditer(text):
            drafts.append(CustomCommand(
                name=match.group("name"), path=path,
                line=text.count("\n", 0, match.start()) + 1,
                body=_command_body(text, match.end()), kind=match.group("kind")))

    # Cypress registers commands globally (the support file requires every command module), so a
    # command may be called from a step file that never imported it. Resolve in two passes, then
    # read each body against the whole index.
    index: dict[str, CustomCommand] = {}
    for draft in drafts:
        index[draft.name] = draft  # a later registration of the same name is the one that runs
    resolved: dict[str, CustomCommand] = {}
    names = frozenset(index)
    for name, draft in index.items():
        # A command's own body is the unit: other commands are resolved separately, so none is
        # followed from here. `names` is still passed so a body that calls one says so.
        layer, reason, via = _reason_and_layer(draft.body, helpers.get(draft.path, {}), {}, names)
        resolved[name] = CustomCommand(name=name, path=draft.path, line=draft.line, body=draft.body,
                                       kind=draft.kind, layer=layer, reason=reason, via=via)
    return resolved


class CucumberJsEcosystem:
    name = NAME

    def detect(self, files: Mapping[str, str]) -> Ecosystem | None:
        """A cucumber-style ``Given('...')`` declaration in a step-definition file."""
        declarations = parse_declarations(files)
        if not declarations:
            return None
        step_files = len({declaration.path for declaration in declarations})
        quotes: dict[str, int] = {}
        for declaration in declarations:
            quotes[declaration.quote] = quotes.get(declaration.quote, 0) + 1
        this_style = sum(1 for declaration in declarations if declaration.world_style)
        commands = _commands(files)
        syntax = ", ".join(_quote_name(quote, count) for quote, count in sorted(quotes.items()))
        same_line = sum(1 for declaration in declarations if declaration.layout == "same-line")
        next_line = len(declarations) - same_line
        regex_literals = sum(1 for declaration in declarations if declaration.regex)
        concatenated = sum(1 for declaration in declarations if declaration.concatenated)
        evidence = [f"{len(declarations)} cucumber-js step-binding declarations in {step_files} files",
                    f"declaration syntax: {syntax}",
                    f"{this_style} declared as this.<Verb>(...)",
                    f"{same_line} same-line, {next_line} with the pattern on the following line",
                    f"{regex_literals} regex-literal declarations; regex-literal patterns are "
                    "unsupported by this build"]
        if concatenated:
            evidence.append(f"{concatenated} declarations split across a string concatenation; "
                            "concatenated patterns are unsupported by this build")
        if commands:
            by_layer: dict[str, int] = {}
            for command in commands.values():
                by_layer[command.layer] = by_layer.get(command.layer, 0) + 1
            split = ", ".join(f"{count} {layer}" for layer, count in sorted(by_layer.items()))
            evidence.append(f"{len(commands)} Cypress custom commands ({split})")
        return Ecosystem(NAME, TITLE, False, evidence=tuple(evidence), reason=REASON)

    def bindings(self, files: Mapping[str, str]) -> list[Binding]:
        """The declarations with the layer their call graph resolves to, and no claim.

        Every row carries either a layer from the JS vocabulary or ``unknown`` with
        ``layer_reason`` saying why. Two shapes that cannot be read honestly - a regex literal and
        a pattern split across a concatenation - raise here rather than returning a short list.
        """
        declarations = parse_declarations(files)
        _refuse_unreadable(declarations)
        commands = _commands(files)
        helpers = {path: helper_bodies(_strip_comments(text))
                   for path, text in _files(files).items()}
        out: list[Binding] = []
        known = frozenset(commands)
        for declaration in declarations:
            layer, reason, via = _reason_and_layer(declaration.body,
                                                   helpers.get(declaration.path, {}), commands,
                                                   known)
            out.append(Binding(pattern=declaration.pattern, verb=declaration.verb, cls="",
                               path=declaration.path, layer=layer,
                               suite=suite_of_path(declaration.path), line=declaration.line,
                               layer_via=via, layer_reason=reason))
        return out

    def drivers(self, files: Mapping[str, str]) -> Mapping[str, object]:
        """The registered custom commands: name -> :class:`CustomCommand` (file, line, body, layer).

        Not the .NET driver map's shape (name -> layer), because there is no file-level answer to
        give: the layer belongs to each command, and two commands in one file disagree.
        """
        return _commands(files)


def _refuse_unreadable(declarations: list[Declaration]) -> None:
    concatenated = [declaration for declaration in declarations if declaration.concatenated]
    if concatenated:
        first = concatenated[0]
        raise UnsupportedEcosystem(
            f"{TITLE} step patterns split across a string concatenation are not supported by this "
            f"build: {first.path}:{first.line} declares {first.verb}("
            f"'{first.pattern}' + ...). Only the first half is readable, which would be a pattern "
            "that matches nothing, so this build refuses to return a partial binding list.")
    regex_literals = [declaration for declaration in declarations if declaration.regex]
    if regex_literals:
        first = regex_literals[0]
        raise UnsupportedEcosystem(
            f"{TITLE} regular-expression patterns are not supported by this build: "
            f"{first.path}:{first.line} declares a regex literal "
            f"({first.verb}(/{first.pattern}/)). The declaration would otherwise be dropped "
            "silently, so this build refuses to return a partial binding list.")


def _quote_name(quote: str, count: int) -> str:
    name = {"'": "single-quoted strings", '"': "double-quoted strings", "`": "template literals",
            "/": "regular expressions"}.get(quote, repr(quote))
    return f"{count} {name}"


ECOSYSTEM = CucumberJsEcosystem()
