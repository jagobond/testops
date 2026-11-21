"""AC8: cases.fingerprint is a pure function of the evidence, not of the verdict, the clock or the process."""
from __future__ import annotations

import os
import subprocess
import sys

from testops import cases

from support import ROOT

SUBJECT_A = "scenario:features/panel_api.feature#the panel is served"
SUBJECT_B = "scenario:features/panel_api.feature#the panel is cached"


def test_same_evidence_produces_the_same_fingerprint():
    first = cases.fingerprint("level_fitness", SUBJECT_A, "KP")
    second = cases.fingerprint("level_fitness", SUBJECT_A, "KP")
    assert first == second
    assert len(first) == 32


def test_different_subject_produces_a_different_fingerprint():
    assert cases.fingerprint("level_fitness", SUBJECT_A, "KP") != \
        cases.fingerprint("level_fitness", SUBJECT_B, "KP")


def test_different_evidence_shape_produces_a_different_fingerprint():
    # Two assertions from one scenario are two cases, not one.
    assert cases.fingerprint("level_fitness", SUBJECT_A, "KP") != \
        cases.fingerprint("level_fitness", SUBJECT_A, "I4")


def test_fingerprint_is_stable_across_processes(tmp_path):
    script = ("from testops import cases; "
              "print(cases.fingerprint('level_fitness', " + repr(SUBJECT_A) + ", 'KP'))")
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"}}
    env["PYTHONPATH"] = str(cases.__file__).rsplit("testops", 1)[0].rstrip("\\/")
    env["PYTHONNOUSERSITE"] = "1"

    proc = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip() == cases.fingerprint("level_fitness", SUBJECT_A, "KP")