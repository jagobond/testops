---
id: TESTOPS-58
title: The disposable-store check is anchored to a root that can be moved
feature: F2
status: done
autonomy: build
depends_on: TESTOPS-53
---

# TESTOPS-58 - The disposable-store check is anchored to a root that can be moved

## Why this exists

`harness.require_disposable_store` refuses any offered path outside `tempfile.gettempdir()`. That is structural - it
checks the resolved path, not a variable - but the root it compares against is itself movable: `tempfile.gettempdir()`
honours `TMPDIR`/`TEMP`/`TMP`, and on this host `TMPDIR` with a pre-created directory wins. The T53 review proved it:
with `TMPDIR=C:/Users/<name>/Projects/attack-tmp`, the suite built its store inside the Projects directory and ran
normally, so the guarantee "no environment variable can point it at a persistent store" was false as written.

It cannot reach the live store - the fixture hands the store to the child rather than reading it from the environment,
and `tests/conftest.py`'s `store_guard` still refuses any writable open of a checkout's `data/` - so this is "a fixture
writes into a junk persistent directory", not "evidence is corrupted". But the sentence in TESTOPS-53 is wrong, and a
wrong guarantee is worse than no guarantee because nobody re-checks it.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The disposable check refuses to proceed when `TMPDIR`/`TEMP`/`TMP` resolves **under the repository, the user's home, or either checkout's `data/`** - refused with a reason naming the variable and the resolved path, and the suite skips rather than running against it. |
| AC2 | The root the check trusts is discovered **without** environment variables (a platform default resolved from the OS, e.g. `GetTempPath`-equivalent or `Path(tempfile.gettempdir()).resolve()` captured once at import *after* AC1's refusal), and a test pins that moving the variable cannot move the root. |
| AC3 | Prove both directions: with the poison `TMPDIR` set, the suite **skips with a reason** instead of building a store there; with a clean environment, it runs as it does today (same pass/fail set). |
| AC4 | The child process's environment is stripped of `PYTHONHOME`-class variables as well as `TESTOPS_*` (the T53 review found `PYTHONHOME` kills the child before the harness can react - an environment error that looks like a harness failure, and one more inherited variable the harness should not tolerate). |
| AC5 | The ticket's claim is rewritten to match what is actually true: the suite cannot be pointed at a **persistent evidence store**, and the residual ability to choose a junk directory is stated rather than denied. |
| AC6 | Full suite unchanged in outcome; the contract gate's known-red set (P07/P10 at the time of writing, minus whatever has landed) unchanged. |
