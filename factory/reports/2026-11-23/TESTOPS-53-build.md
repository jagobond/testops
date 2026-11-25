# TESTOPS-53 — build report

Date: 2026-11-23 (the ticket asked for 2026-11-24; the machine clock reads 23 Nov 2026, so this is
filed under its own date). Branch: `factory/testops-53-self-contained-contracts`. Worktree:
`C:/Users/<name>/Projects/testops-t53`. Dependency: TESTOPS-52 (see AC5/AC6 — this branch does
not contain the 52 merge, which matters for one contract promise).

## What changed

| file | change |
|---|---|
| `tests/contracts/harness.py` | **new.** Builds the disposable store, refuses a non-temp store, launches the child on port 0, reads the port it reports, waits for readiness, stops it. |
| `tests/contracts/_server.py` | **new.** Child process: `ThreadingHTTPServer(("127.0.0.1", 0), Handler)`, prints `PORT <n>`. |
| `tests/contracts/conftest.py` | **new.** Session autouse fixture: start the server or `pytest.skip(reason)`. |
| `tests/contracts/test_contract_harness.py` | **new.** Six tests pinning AC1/AC2/AC3. |
| `tests/contracts/seed/{seed.json,blobs/,README.md,make_seed.py}` | **new.** 3 runs, 103 claims, 21 cases, 96 artefacts, 110 observations, 48 blobs (575 KB); generator opens a store `mode=ro`. |
| `tests/contracts/test_page_contracts.py` | setup only: `BASE = os.environ.get("TESTOPS_BASE", "http://<tailnet-address>:8791")` removed; `get`/`post` use `base_url()` from the started server; `front`/`runs` depend on the session fixture. **No assertion or test body was edited.** |
| `.github/workflows/ci.yml` | comment on the whole-suite step + a named "Page-contract gate" step. |
| `tests/README.md` | documents the owned server, the seed and regeneration. |

## AC1 — the suite starts and owns its own server over a disposable store

- The store is **built** by `harness.build_seed_store` under `tmp_path_factory.mktemp(...)`: the
  product's `schema.sql`, rows from `seed/seed.json`, blobs into `<data>/blobs/<sha[:2]>/<sha[2:]>`.
  Nothing copies or opens `data/`.
- `harness.require_disposable_store` resolves the path and refuses anything not under
  `tempfile.gettempdir()`; `start_contract_server` calls it *before* launching anything.
- The child is launched with `TESTOPS_DATA` set to that temp directory and **every inherited
  `TESTOPS_*` variable removed** (the env is filtered, not overridden), `PYTHONPATH=<repo>`,
  `TESTOPS_ENV` pointed at a non-existent temp path.
- The child binds port **0** and prints `PORT n`; the parent connects only to that number. This is
  deliberate: a chosen port can be silently hijacked on Windows (observed during this build: two
  unrelated `demo-product.panel` processes had bound 8811 and received requests meant for a test server -
  the pages served were another store's, not the one under test).
- Demonstration in the suite: `test_an_inherited_store_variable_cannot_redirect_the_server` sets
  `TESTOPS_DATA=<repo>/data` and `TESTOPS_BASE=http://<tailnet-address>:8791` in the parent, starts the
  suite's server, and asserts `/runs` shows `demo-booking` and **not** `demo-product` (the live store's
  project). It passes.

## AC2 — cannot start ⇒ skip with a reason; no fallback, no guessed host

The session fixture catches `ServerUnavailable` and calls `pytest.skip("the contract suite could not
start its own server: <reason>")`. `base_url()` asserts a server exists; there is no default.

Proof (scratch copy, `_server.py` replaced with `raise SystemExit('cannot bind here')`):

```
sssssssssssssssssssssssssssssssssss                                      [100%]
35 skipped in 3.91s                      (exit 0)

SKIPPED [1] tests\contracts\test_contract_harness.py:30: the contract suite could not start its
own server: the server process did not report a port (exit 1). Its output: cannot bind here
```

`test_a_server_that_cannot_start_is_unavailable_not_a_fallback` also pins the exception and message.

## AC3 — the prohibition is pinned

`tests/contracts/test_contract_harness.py` (6 tests, all passing):

1. configured base host is `127.0.0.1`, port > 0 and `!= 8791`, `LIVE_HOST` absent from the URL;
2. the server's store resolves under `tempfile.gettempdir()` and is not `<repo>/data/testops.db`;
3. `require_disposable_store` and `build_seed_store` raise `StoreNotDisposable` for `<repo>/data`
   and for `~/testops-data`;
4. an inherited `TESTOPS_DATA`/`TESTOPS_BASE` cannot redirect the child (above);
5. a server that cannot start raises `ServerUnavailable`, never a URL;
6. **source scan of `test_page_contracts.py`**: fails if `<tailnet-address>`, `8791` or `TESTOPS_BASE`
   appear in it again. This is the test that fails if a live default is reintroduced.

## AC4 — the live store is byte-identical before and after the full suite

Command run (the ticket's interpreter, from the worktree):

```
env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
  C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q
```

- sha256 of `C:/Users/<name>/Projects/testops/data/testops.db`, before **and** after:
  `6b0d38bd11e4b2ffe3ab8b677a9ebd20a3b61937db82f4eef1779d0e92e4c47c`
- project list, before **and** after (read-only URI `file:...?mode=ro`):
  `demo-product`, `demo-service`, `demo-booking`, `testops` — `diff` of the two lists is empty.
- Result: `5 failed, 703 passed, 3 skipped in 149.11s`. The five failures are all in
  `tests/contracts`; every non-contract test passed. The live server on 8791 was never contacted.

## AC5 — CI runs the whole suite including contracts, and fails on a contract failure

`.github/workflows/ci.yml` already ran `python -m pytest -q` (whole suite, 3.11 + 3.12); that run
now includes `tests/contracts` on its own temporary server. Added a second, explicitly named step so
the gate is legible and cannot be quietly filtered out:

```yaml
      - name: Page-contract gate (the suite's own temporary server and store)
        shell: bash
        run: |
          set -o pipefail
          env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
            python -m pytest tests/contracts -q | tee "$RUNNER_TEMP/contracts-${{ matrix.python }}.log"
```

Any contract failure is a non-zero pytest exit and fails the build (the existing failure-naming step
already prints every `FAILED`/`ERROR` line into the job summary).

**Honest state of the local run:** it is not green, and cannot be in this ticket. It is red on
exactly the promises other tickets own:

| red promise | owner |
|---|---|
| P04 uncertain verdict styled as settled | **TESTOPS-52** — merged on `main`, **not on this branch** (`de78567` predates the 52 merge) |
| P05 case → its run | TESTOPS-54 |
| P05 `/config` reachable | TESTOPS-54 |
| P07 front-page totals | TESTOPS-55 |
| P10 per-kind read counts incl. explicit zero | TESTOPS-55 |

On a scratch copy of `main` (52 + 57 merged) with this ticket's contracts directory and seed, P04
passes (`1 passed, 34 deselected`). So with 52 merged and 54/55 landed, the same command is green;
until then the gate is correctly red rather than reported and ignored. I did not weaken or skip any
contract assertion to manufacture a green run.

## AC6 — proof the gate can fail

Scratch copy (`git archive main` → `.../scratch/maincopy`, plus this ticket's
`tests/contracts/`), never the worktree tree:

```
python -m pytest tests/contracts -q -k P04      → 1 passed, 34 deselected
# edit maincopy/testops/web/tone.py: NOT_ASSESSABLE_TONE = SOFT → ALARM
#   (the alarm class "Checked, but this repeats another test" wears: "Cannot assess" was put
#    back on a settled verdict's tone)
python -m pytest tests/contracts -q -k P04      → 1 failed, 34 deselected
```

Failing test: `tests/contracts/test_page_contracts.py::test_P04_uncertain_verdict_is_not_styled_as_settled`

```
AssertionError: An uncertain verdict ('Cannot assess', class 'verdict hot') is styled identically
to a settled one ('Checked, but this repeats another test', class 'verdict hot'): 'Cannot tell' is
dressed as settled (P4).
assert 'verdict hot' != 'verdict hot'
```

(On this branch P04 is already red for the same styling, because the 52 merge is absent — that is
the dependency, not a fixture artefact.)

## The soft BADGE class / unplaced claims

The fixture store **does contain** 18 `unplaced` claims (from `demo-booking-levels-20261123T132456`),
but no case: the analyser raises no finding for a claim it could not place, and `app.verdict_badge`
only renders `badge verdict soft` on a case-list row. So the seed cannot witness `.badge.verdict.soft`
or the unplaced case tone without inventing a case the analyser never raised — a fixture that lies.
Witnessing that class needs a **product change** (a case/row for an unplaced claim, or the placement
summary carrying the badge). On `main` this is written up as TESTOPS-57; it is not done here.

## Limits

- The seed is a pinned slice generated from the live store **read-only** on 23 Nov 2026
  (`make_seed.py`), not a copy of it: 2 demo-booking runs + 1 demo-service run, and no `inference`
  rows. Regeneration requires a populated store; CI does not regenerate.
- P9 (failed run), P14 (credit) and P20 (unplaced looks less settled) remain skipped for the
  reasons the blind author gave; nothing in this ticket changes them.
- CI's contract step duplicates ~5 s of work for a named gate; the distribution tests are not run
  twice.
