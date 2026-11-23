"""cucumber-js: detected and refused, on purpose.

TESTOPS-42A does not add cucumber-js support. This module exists so the product can tell the truth
about a JavaScript suite - it recognises the vocabulary, counts what it found, and says support does
not exist - instead of reading 44 JavaScript bindings with a C# attribute regex and reporting "none
of its steps could be tied to a layer".

Why detection is not extraction, and why ``bindings`` raises rather than returning ``[]``:

  * the counts below are a *reading of the repository*, used to say which ecosystem was recognised
    and how much of it this build cannot read. They place no claim about any step;
  * an empty binding list would travel to the analysers as "the suite binds nothing", which is the
    lie TESTOPS-39 caught. A wrongly placed claim and an unplaced claim are different failures, and
    only the second is honest - so the only honest extractor here is one that refuses.

The scan is bounded: only single-file statements whose keyword starts a line (or a ``this.`` method
call), and only in files that look like step definitions. That deliberately under-counts an exotic
form rather than over-counting a ``.then(`` in product code, because the number is published as a
count of declarations, not as an estimate.
"""
from __future__ import annotations

import re
from typing import Mapping

from ..stepbindings import Binding
from . import Ecosystem, UnsupportedEcosystem

NAME = "cucumber-js"
TITLE = "cucumber-js"
REASON = ("this build can recognise JavaScript step definitions and cannot read them, so it will "
          "not guess what they do")

KEYWORDS = ("Given", "When", "Then", "And", "But")

# A declaration starts a line with the keyword (or `this.`), then its opening parenthesis. The
# quoting character after it decides the syntax and is captured separately, because the corpus
# already contains all of them and a reader asking "which shapes exist" needs the split. The match
# is deliberately allowed to cross a newline: 16 of this corpus's 44 declarations put the pattern
# on its own line after the parenthesis, and a same-line-only scan under-counts them by a third.
DECLARATION = re.compile(
    r"^[ \t]*(?P<this>this\.)?(?P<verb>Given|When|Then|And|But)[ \t]*\([ \t\r\n]*(?P<quote>['\"`/])",
    re.M)
CUSTOM_COMMAND = re.compile(r"Cypress\.Commands\.(?:add|overwrite|addAll)\s*\(\s*['\"`]([^'\"`]+)")

# A file is a step-definition file when its path says so or it imports a cucumber binding module.
# Without this, `Then(` in a Jest file would be counted as a binding declaration.
STEP_FILE = re.compile(r"(stepdef|steps?/|\.cy\.[jt]s$|/steps/|_steps\.[jt]s$)", re.I)
CUCUMBER_IMPORT = re.compile(r"['\"][^'\"]*cucumber[^'\"]*['\"]", re.I)


def _is_step_file(path: str, text: str) -> bool:
    return bool(STEP_FILE.search(path) or CUCUMBER_IMPORT.search(text))


def _strip_comments(text: str) -> str:
    """Comments are not statements. The corpus carries four commented-out commands in one file."""
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))


def _files(files: Mapping[str, str]) -> dict[str, str]:
    return {path: text for path, text in files.items()
            if path.endswith((".js", ".ts")) and not path.endswith(".d.ts")}


class CucumberJsEcosystem:
    name = NAME

    def detect(self, files: Mapping[str, str]) -> Ecosystem | None:
        """A cucumber-style ``Given('...')`` declaration in a step-definition file."""
        declarations = 0
        step_files = 0
        quotes: dict[str, int] = {}
        this_style = 0
        for path, text in _files(files).items():
            if not _is_step_file(path, text):
                continue
            found = list(DECLARATION.finditer(text))
            if not found:
                continue
            step_files += 1
            declarations += len(found)
            for match in found:
                quotes[match.group("quote")] = quotes.get(match.group("quote"), 0) + 1
                this_style += 1 if match.group("this") else 0
        if not declarations:
            return None
        commands = sum(len(CUSTOM_COMMAND.findall(_strip_comments(text)))
                       for text in _files(files).values())
        syntax = ", ".join(_quote_name(quote, count) for quote, count in sorted(quotes.items()))
        evidence = [f"{declarations} cucumber-js step-binding declarations in {step_files} files",
                    f"declaration syntax: {syntax}",
                    f"{this_style} declared as this.<Verb>(...)"]
        if commands:
            evidence.append(f"{commands} Cypress custom commands")
        return Ecosystem(NAME, TITLE, False, evidence=tuple(evidence), reason=REASON)

    def bindings(self, files: Mapping[str, str]) -> list[Binding]:
        """Refused. Returning ``[]`` would say the suite binds nothing (TESTOPS-42A, AC5)."""
        raise UnsupportedEcosystem(
            f"{TITLE} is detected in this repository and this build cannot extract its bindings. "
            "An empty list would be a claim that it binds nothing; it binds "
            f"{self._count(files)} steps this build cannot read.")

    def drivers(self, files: Mapping[str, str]) -> dict[str, str]:
        """Refused for the same reason: a guessed driver map is a wrong layer on every claim."""
        raise UnsupportedEcosystem(f"{TITLE} driver detection is not supported by this build")

    @staticmethod
    def _count(files: Mapping[str, str]) -> int:
        return sum(len(DECLARATION.findall(text)) for path, text in _files(files).items()
                   if _is_step_file(path, text))


def _quote_name(quote: str, count: int) -> str:
    name = {"'": "single-quoted strings", '"': "double-quoted strings", "`": "template literals",
            "/": "regular expressions"}.get(quote, repr(quote))
    return f"{count} {name}"


ECOSYSTEM = CucumberJsEcosystem()
