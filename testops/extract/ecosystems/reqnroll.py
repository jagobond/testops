"""Reqnroll/.NET: C# attribute step bindings, read exactly as they always were.

This module is the old extractor with a door in front of it. TESTOPS-42A changes no regex and no
rule here - ``BINDING``, ``SIGNALS`` and ``LAYER_ORDER`` are re-exported from
:mod:`testops.extract.stepbindings` unchanged, and callers that always used those names keep
working. What is new is that the pipeline now finds this module by *detecting* a .NET repository,
instead of assuming every repository is one.
"""
from __future__ import annotations

import re
from typing import Mapping

from .. import stepbindings
from ..stepbindings import Binding
from . import Ecosystem

NAME = "reqnroll"
TITLE = "Reqnroll/.NET"

# Kept importable under their historical names (AC3): the analysers and the web layer read these
# and must not have to learn a new home for them.
BINDING = stepbindings.BINDING
SIGNALS = stepbindings.SIGNALS
LAYER_ORDER = stepbindings.LAYER_ORDER

# A project file that names the BDD framework. Used only when no binding was found: a repository
# whose step definitions were generated away still has a recognisable build file.
PROJECT_MARKER = re.compile(r"\b(Reqnroll|SpecFlow)\b", re.I)


def _csharp(files: Mapping[str, str]) -> dict[str, str]:
    return {path: text for path, text in files.items() if path.endswith(".cs")}


class ReqnrollEcosystem:
    name = NAME

    def detect(self, files: Mapping[str, str]) -> Ecosystem | None:
        """A C# binding attribute, or a Reqnroll/SpecFlow project file, is the marker."""
        sources = _csharp(files)
        bindings = sum(len(BINDING.findall(text)) for text in sources.values())
        if bindings:
            files_with = sum(1 for text in sources.values() if BINDING.search(text))
            return Ecosystem(
                NAME, TITLE, True,
                evidence=(f"{bindings} C# step-binding attributes in {files_with} .cs files",))
        projects = [path for path, text in files.items()
                    if path.endswith(".csproj") and PROJECT_MARKER.search(text)]
        if projects and any(path.endswith(".feature") for path in files):
            return Ecosystem(
                NAME, TITLE, True,
                evidence=(f"a Reqnroll/SpecFlow project file ({projects[0]}) and feature files",))
        return None

    def bindings(self, files: Mapping[str, str]) -> list[Binding]:
        """Every binding in the files given, file by file.

        The driver map is built from *all* the files given - that is the point of building it once:
        a step definition names a driver class whose body lives in another file.
        """
        driver_map = self.drivers(files)
        out: list[Binding] = []
        for path, text in files.items():
            if BINDING.search(text) is None:
                continue
            out.extend(stepbindings.parse_file(path, text, driver_map))
        return out

    def drivers(self, files: Mapping[str, str]) -> dict[str, str]:
        """Driver class -> layer, from ``*Driver.cs/.py/.ts`` bodies, as before."""
        return stepbindings.build_driver_map(dict(files))


ECOSYSTEM = ReqnrollEcosystem()
