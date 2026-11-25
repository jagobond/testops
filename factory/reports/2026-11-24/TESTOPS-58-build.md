# TESTOPS-58 — build

Builder: 2026-11-23 (run date; report filed under the ticket's 2026-11-24 folder), worktree
`C:/Users/<name>/Projects/testops-t58` on `factory/testops-58-pinned-temp-root`. Every number
below is from my own runs with the ticket's interpreter
(`env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 …/.venv/Scripts/python.exe`).
No run wrote to the live store and nothing contacted 8791.

## The fault, restated exactly

`harness.require_disposable_store` checked the resolved path against
`tempfile.gettempdir()`. The path check was structural; the root was not. `tempfile.gettempdir()`
honours `TMPDIR`/`TEMP`/`TMP`, so the T53 review moved the root with
`TMPDIR=C:/Users/<name>/Projects/attack-tmp` and the suite built its store inside `Projects/`
and ran normally.

What that reached: junk in a persistent directory. What it could not reach: the live store. The
fixture hands the store to the child (`TESTOPS_DATA` is set from the fixture's own `Path`, never
read from the environment), and `tests/conftest.py`'s `store_guard` still refuses any writable open
of a checkout's `data/`. So the T53 guarantee "no environment variable can point it at a
persistent store" was false as written, but the failure mode is a leftover store in a directory
nobody treats as evidence — not corrupted evidence.

## What changed

| file | change |
|---|---|
| `tests/contracts/harness.py` | trusted temp root discovered from the OS (`SHGetKnownFolderPath(FOLDERID_LocalAppData)/Temp` on Windows, platform defaults with `TMPDIR`/`TEMP`/`TMP` removed on POSIX), captured once at import as `TRUSTED_TEMP_ROOT`; `temp_root_problem()` refuses a temp variable resolving into the repository, the user's home (outside the OS temp directory) or any checkout's `data/`, naming the variable and the resolved path; `require_disposable_store` raises that refusal; child env drops `PYTHONHOME`, `PYTHONPATH`, `PYTHONSTARTUP`, `PYTHONUSERBASE`, `PYTHONOPTIMIZE`, `PYTHONEXECUTABLE` as well as `TESTOPS_*`. |
| `tests/contracts/conftest.py` | checks `TEMP_ROOT_PROBLEM` *before* asking pytest for a temp directory, so a poisoned environment skips rather than creating `pytest-of-*` there; `StoreNotDisposable` from the gate is now a skip with the reason, like `ServerUnavailable`. |
| `tests/contracts/test_contract_harness.py` | four new tests: the root does not move when `TMPDIR` does; repo/home/data temp values are refused by variable name and resolved path (and the OS temp directory is not); a real interpreter run with a poison `TMPDIR` skips and writes no `.db`; an inherited `PYTHONHOME` cannot stop the child. |
| `tests/contracts/test_page_contracts.py`, `tests/README.md`, `factory/tickets/TESTOPS-53.md` | the claim rewritten (AC5). |

## AC evidence

**AC1 — refusal, with a reason.** `test_a_temp_variable_inside_the_repository_is_refused_by_name`
covers `TMPDIR=<repo>/build/junk`, `TEMP=<repo>/data/junk`, `TMP=~/testops-tmp-attack`; each
refusal contains the variable name and the resolved path. One deviation, stated rather than
hidden: "under the user's home" is enforced as "under home **except** the OS temp directory",
because on Windows the OS temp directory lives under home — including it would make every clean
run skip, contradicting AC3. Evidence from the reviewer's own reproduction path:

```
$ TMPDIR=C:/Users/<name>/Projects/attack-tmp python -m pytest tests/contracts -q -rs
39 skipped in 1.60s
SKIPPED … the contract suite will not build a store there: TMPDIR='C:\\Users\\Chester\\Projects\\attack-tmp'
  resolves to C:\\Users\\Chester\\Projects\\attack-tmp, inside the user's home directory (C:\\Users\\Chester).
$ find C:/Users/<name>/Projects/attack-tmp -name '*.db'   → (nothing)
```

**AC2 — root discovered without environment variables.** Discovered at import from the shell
known folder (verified directly: `SHGetKnownFolderPath(LocalAppData)` returned
`C:\Users\<name>\AppData\Local`, which is not read from `TMPDIR`). `TRUSTED_TEMP_ROOT` is a module
constant; `under_temp`/`require_disposable_store`/the store test use `harness.temp_root()`.
`test_the_trusted_temp_root_is_discovered_without_environment_variables` moves `TMPDIR`, proves
`tempfile.gettempdir()` followed it, and asserts `harness.temp_root()` did not and that a store
there is refused.

**AC3 — both directions.**

1. Poison, full suite, `TMPDIR=C:/Users/<name>/Projects/attack-tmp` (dir pre-created):
   `698 passed, 39 skipped in 154.50s`, exit 0. Every contract test skipped with the reason
   (34+3+2 = 39 clean-run contract tests became skips), everything else unchanged. The residual is
   visible and measured: the non-contract tests still use `tmp_path`, so 321 `.db` files were built
   under the poison directory — its own junk, not evidence. Directory removed afterwards.
2. Clean environment, same interpreter, whole suite: **before this branch's changes**
   (`git stash` of `tests/contracts`): `2 failed, 728 passed, 3 skipped in 172.93s`. **After:**
   `2 failed, 732 passed, 3 skipped in 176.06s`. Identical failure and skip sets; the four extra
   passes are the four new tests.

**AC4 — child environment.** `PYTHONHOME` (and its relatives) are dropped from the child's
environment before `Popen`. `test_an_inherited_pythonhome_cannot_stop_the_child_server` sets
`PYTHONHOME` to a non-interpreter and asserts the child still binds and serves `/runs` 200.

**AC5 — claim rewritten.** `tests/README.md`, the harness and contract-suite docstrings, and
`factory/tickets/TESTOPS-53.md` AC1 now say: the suite cannot be pointed at a persistent
**evidence** store; the temp root comes from the OS; a temp variable into the repository, home or
a checkout's `data/` skips; a temp variable into some other persistent directory still chooses
where the disposable store is built, and that is junk, not evidence.

**AC6 — outcome unchanged.** Full suite `2 failed, 732 passed, 3 skipped`; the contract gate is
`2 failed, 34 passed, 3 skipped`, the same known-red set: **P07** (front page does not state what
analysed and how much exists) and **P10** (no explicit zero read-count per file kind). Both are
product promises still open, not harness noise; nothing was tuned to make them pass.

## What I did not do

- Did not run the tests as any other interpreter user, did not touch the main checkout or other
  worktrees, did not write to `data/`, did not contact 8791.
- Did not pin pytest's own `basetemp` to a fixture-created directory (the review's alternate fix).
  The OS-discovered root plus the skip is the smaller change and keeps `tmp_path` semantics; the
  cost is that a `TMPDIR` outside home/repo/data still moves the junk directory, now stated in the
  claim instead of denied.
- The 2026-11-24/ticket-dated report path was kept as written while the run date is 2026-11-23;
  both are stated above.
