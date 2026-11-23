"""cucumber-js: the declaration parser, with claim placement still switched off.

TESTOPS-42C-1 builds the parsing floor and nothing above it. This module can now read the
declarations - all 44 of this corpus's, in both layouts - and it deliberately still places no
claim. ``detect`` continues to return an unsupported ecosystem, so the pipeline's existing gate
keeps the run ``not_assessable`` and the analysers are neither called nor changed. T42C-3 wires
placement.

Why the parse is not line-oriented: 16 of the 44 declarations put the opening parenthesis at the
end of a line and the pattern on the next. A line-oriented scan reports 28, which is the defect
that made counting-before-costing necessary (docs/ecosystem-inventory-cucumber-js.md §2). The
expression here is allowed to cross a newline and records which layout it saw.

Quoting: the declaration may be single-quoted, double-quoted or a template literal. Those three
are parsed the same way and the quote is recorded. A regular-expression literal (``Given(/^...$/)``)
is *not* parsed: a repository containing one is reported as unsupported from ``bindings`` and in
the detection record, rather than having the declaration silently dropped. This corpus has none
(0 of 44), so the unsupported arm costs it nothing and the alternative - a quiet undercount - is
the failure this ticket exists to prevent.

The layer of every binding is ``unknown``. Inferring a layer is T42C-2's vocabulary work; a guess
here would be a wrong claim arriving through the back door.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from ..stepbindings import Binding, suite_of
from . import Ecosystem, UnsupportedEcosystem

NAME = "cucumber-js"
TITLE = "cucumber-js"
REASON = ("this build can recognise JavaScript step definitions and cannot read them, so it will "
          "not guess what they do")

KEYWORDS = ("Given", "When", "Then", "And", "But")

# A declaration starts a line with the keyword (or `this.`), then its opening parenthesis. The
# quoting character after it decides the syntax and is captured separately. The gap is captured so
# the layout can be reported, and it explicitly contains newlines: the expression is not
# line-oriented.
DECLARATION = re.compile(
    r"^[ \t]*(?P<this>this\.)?(?P<verb>Given|When|Then|And|But)"
    r"[ \t]*\((?P<gap>[ \t\r\n]*)(?P<quote>['\"`/])",
    re.M)
CUSTOM_COMMAND = re.compile(r"Cypress\.Commands\.(?:add|overwrite|addAll)\s*\(\s*['\"`]([^'\"`]+)")

# A file is a step-definition file when its path says so or it imports a cucumber binding module.
# Without this, `Then(` in a Jest file would be counted as a binding declaration.
STEP_FILE = re.compile(r"(stepdef|steps?/|\.cy\.[jt]s$|/steps/|_steps\.[jt]s$)", re.I)
CUCUMBER_IMPORT = re.compile(r"['\"][^'\"]*cucumber[^'\"]*['\"]", re.I)


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


def _is_step_file(path: str, text: str) -> bool:
    return bool(STEP_FILE.search(path) or CUCUMBER_IMPORT.search(text))


def _strip_comments(text: str) -> str:
    """Comments are not statements. The corpus carries four commented-out commands in one file."""
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))


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
    and ``background.stepdef.js``.
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


def _declarations_in(path: str, text: str) -> list[Declaration]:
    out: list[Declaration] = []
    for match in DECLARATION.finditer(text):
        quote = match.group("quote")
        start = match.end()
        close = _regex_close(text, start) if quote == "/" else _string_close(text, start, quote)
        out.append(Declaration(
            verb=match.group("verb"), pattern=text[start:close], path=path,
            line=text.count("\n", 0, match.start()) + 1, quote=quote,
            layout="next-line" if "\n" in match.group("gap") else "same-line",
            regex=quote == "/", world_style=bool(match.group("this"))))
    return out


def parse_declarations(files: Mapping[str, str]) -> list[Declaration]:
    """Every declaration in every step-definition file, in file then source order."""
    out: list[Declaration] = []
    for path, text in sorted(_files(files).items()):
        if not _is_step_file(path, text):
            continue
        out.extend(_declarations_in(path, text))
    return out


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
        commands = sum(len(CUSTOM_COMMAND.findall(_strip_comments(text)))
                       for text in _files(files).values())
        syntax = ", ".join(_quote_name(quote, count) for quote, count in sorted(quotes.items()))
        same_line = sum(1 for declaration in declarations if declaration.layout == "same-line")
        next_line = len(declarations) - same_line
        regex_literals = sum(1 for declaration in declarations if declaration.regex)
        evidence = [f"{len(declarations)} cucumber-js step-binding declarations in {step_files} files",
                    f"declaration syntax: {syntax}",
                    f"{this_style} declared as this.<Verb>(...)",
                    f"{same_line} same-line, {next_line} with the pattern on the following line",
                    f"{regex_literals} regex-literal declarations; regex-literal patterns are "
                    "unsupported by this build"]
        if commands:
            evidence.append(f"{commands} Cypress custom commands")
        return Ecosystem(NAME, TITLE, False, evidence=tuple(evidence), reason=REASON)

    def bindings(self, files: Mapping[str, str]) -> list[Binding]:
        """The declarations, with the facts a claim will need once placement is wired.

        The layer is ``unknown``: this ticket adds no layer vocabulary. A regex-literal declaration
        raises rather than being skipped, so the caller can never receive a quietly short list.
        """
        declarations = parse_declarations(files)
        regex_literals = [declaration for declaration in declarations if declaration.regex]
        if regex_literals:
            first = regex_literals[0]
            raise UnsupportedEcosystem(
                f"{TITLE} regular-expression patterns are not supported by this build: "
                f"{first.path}:{first.line} declares a regex literal "
                f"({first.verb}(/{first.pattern}/)). The declaration would otherwise be dropped "
                "silently, so this build refuses to return a partial binding list.")
        return [Binding(pattern=declaration.pattern, verb=declaration.verb, cls="",
                        path=declaration.path, layer="unknown",
                        suite=suite_of_path(declaration.path), line=declaration.line)
                for declaration in declarations]

    def drivers(self, files: Mapping[str, str]) -> dict[str, str]:
        """Refused for the same reason: a guessed driver map is a wrong layer on every claim."""
        raise UnsupportedEcosystem(f"{TITLE} driver detection is not supported by this build")


def _quote_name(quote: str, count: int) -> str:
    name = {"'": "single-quoted strings", '"': "double-quoted strings", "`": "template literals",
            "/": "regular expressions"}.get(quote, repr(quote))
    return f"{count} {name}"


ECOSYSTEM = CucumberJsEcosystem()
