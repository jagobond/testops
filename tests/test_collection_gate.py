"""AC9: a suite with no test files exits 5 (no tests collected), never 0.

A broken collection that reads as success is the failure mode this asserts against: pytest's exit
code 5 is distinct from 0 (passed), 1 (failed) and 2 (interrupted), so the factory's gate can tell
"nothing ran" from "everything passed".
"""
from __future__ import annotations

import os
import subprocess
import sys

NO_TESTS_COLLECTED = 5


def _clean_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"}}
    env["PYTHONNOUSERSITE"] = "1"
    return env


def test_empty_suite_exits_no_tests_collected(tmp_path):
    empty = tmp_path / "no-tests-here"
    empty.mkdir()

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(empty)],
        cwd=tmp_path, env=_clean_env(), capture_output=True, text=True, timeout=120,
    )

    output = proc.stdout + proc.stderr
    assert proc.returncode == NO_TESTS_COLLECTED, output
    assert proc.returncode != 0