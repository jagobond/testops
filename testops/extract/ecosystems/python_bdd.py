"""Python BDD (pytest-bdd / behave): detected and refused.

The product has always read Python *source* - the surface reader parses it, the layer vocabulary
carries Python HTTP signals - but it has never had a Python step-binding extractor. Before
TESTOPS-42A a Python BDD repository was read by the C# attribute regex, found no bindings, and its
scenarios were reported as having no layer. That is the same fault as the JavaScript corpus, in a
second language, so the same answer applies: name it, count it, and refuse.

This changes nothing about any corpus in the store today: none of them binds steps with
``@given``. It changes only what a Python BDD repository would be told, from "none of its steps
could be tied to a layer" to "Python BDD was detected and this build has no support for it".
"""
from __future__ import annotations

import re
from typing import Mapping

from ..stepbindings import Binding
from . import Ecosystem, UnsupportedEcosystem

NAME = "python-bdd"
TITLE = "Python BDD (pytest-bdd/behave)"
REASON = ("this build reads Python as product source, not as step definitions, so it will not "
          "guess what they do")

# pytest-bdd and behave both decorate a function with the Gherkin keyword. The target form
# (`@given("...")` / `@when("...")`) is the one that carries the step text; the parser form sits
# beside it and is counted too, because a reader asking what exists needs the whole count.
DECORATOR = re.compile(r"^[ \t]*@(?P<verb>given|when|then|and|but)\s*\(", re.M | re.I)
IMPORT_MARKER = re.compile(r"^\s*(?:from\s+pytest_bdd\b|import\s+pytest_bdd\b|from\s+behave\b)",
                           re.M)
STEP_FILE = re.compile(r"(step|bdd|feature)", re.I)


def _files(files: Mapping[str, str]) -> dict[str, str]:
    return {path: text for path, text in files.items() if path.endswith(".py")}


class PythonBddEcosystem:
    name = NAME

    def detect(self, files: Mapping[str, str]) -> Ecosystem | None:
        """A Gherkin decorator in a .py file that imports a BDD framework."""
        declarations = 0
        step_files = 0
        verbs: dict[str, int] = {}
        for path, text in _files(files).items():
            found = list(DECORATOR.finditer(text))
            if not found:
                continue
            if not (IMPORT_MARKER.search(text) or STEP_FILE.search(path)):
                continue
            step_files += 1
            declarations += len(found)
            for match in found:
                verb = match.group("verb").lower()
                verbs[verb] = verbs.get(verb, 0) + 1
        if not declarations:
            return None
        split = ", ".join(f"{verb} {count}" for verb, count in sorted(verbs.items()))
        return Ecosystem(NAME, TITLE, False, evidence=(
            f"{declarations} Gherkin step decorators in {step_files} .py files", f"verbs: {split}"),
            reason=REASON)

    def bindings(self, files: Mapping[str, str]) -> list[Binding]:
        raise UnsupportedEcosystem(
            f"{TITLE} is detected in this repository and this build cannot extract its bindings. "
            "An empty list would be a claim that it binds nothing (TESTOPS-42A, AC5).")

    def drivers(self, files: Mapping[str, str]) -> dict[str, str]:
        raise UnsupportedEcosystem(f"{TITLE} driver detection is not supported by this build")


ECOSYSTEM = PythonBddEcosystem()
