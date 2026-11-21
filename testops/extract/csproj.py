"""Which feature files the build actually generates tests from.

A .feature file on disk is not a test. The project file removes unbound files deliberately - an unbound
scenario would fail for the wrong reason - so an analyser that reads the working tree instead of the build
analyses tests nobody runs. On this repository that is 141 scenarios versus 43 executed.
"""
from __future__ import annotations

import fnmatch
import re

REMOVE = re.compile(r'<ReqnrollFeatureFile\s+Remove="([^"]+)"', re.I)
DEFAULT_EXCLUDES = (".lead-draft/*", "*/bin/*", "*/obj/*")


def excluded_patterns(csproj_text: str) -> list[str]:
    pats = [p.strip() for p in REMOVE.findall(csproj_text)]
    return pats + list(DEFAULT_EXCLUDES)


def _normalise(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def is_active(feature_path: str, patterns: list[str]) -> bool:
    p = _normalise(feature_path)
    for pattern in patterns:
        pat = _normalise(pattern)
        # csproj globs use **; fnmatch needs a translation for it
        pat = pat.replace("**/", "*/")
        if fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(p, pat.replace("/*", "/*")):
            return False
    return True
