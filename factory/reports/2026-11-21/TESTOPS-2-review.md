# TESTOPS-2 review — 2026-11-21

## Verdict

PASS — the suite is real, offline, self-policing, and every criterion is proven by a test that
would fail if the thing it claims to test broke.

## Criteria

AC1 — HOLDS. `pyproject.toml` declares `pytest>=8` under `[project.optional-dependencies] dev`,
and `tests/README.md` documents `pip install -e ".[dev]"`. I executed that exact command in a
fresh throwaway venv (build isolation on): install succeeded, pytest importable.

AC2 — HOLDS. `testops.cases` is gone from the package list (it is `testops/cases.py`, a module);
`testops.web` and `testops.scripts` are declared. The same fresh-venv probe above imported
`testops.web`, `testops.scripts` and `testops.cases` through the installed distribution, not just
from the tree — so the AC's real claim (an editable install can import the UI) is proven against
an actual install, not merely asserted.

AC3 — HOLDS. Ran the documented command from the repo root: `17 passed in 1.96s`, exit 0. No
network markers, no credentials anywhere in the suite; the level_fitness test additionally runs
the analysis with `socket.socket` monkeypatched to raise, so "offline" is enforced, not assumed.

AC4 — HOLDS. `test_store_schema.py` applies `db.SCHEMA` (verified `is_file()`) to a fresh
tmp_path database and asserts all ten named tables exist; a second test asserts `db.connect()`
applies the schema too. Both would fail on a missing table.

AC5 — HOLDS. `test_claim_roundtrip.py` writes via `db.add_claim` on one connection, closes it,
opens a fresh one and asserts statement, verdict, subject_ref, confidence and empty support
survive. Uses the real schema and real seeding calls (`upsert_snapshot`, `start_run`), so it
would fail on a persistence bug, not just on an API change.

AC6 — HOLDS. The fixture drives the real `level_fitness.analyse` over a parsed Gherkin feature
with real `stepbindings.Binding` objects. The gap scenario is named so the analyser's
ACCESSIBILITY path classifies it I4 (needs_browser) while the bindings say layer `api` —
exactly the gap condition — and the distinct scenario hits the MARKUP/KP path. Both tests assert
the detail fields (`uses_browser`, `needs_browser`, `claim`), so a broken classifier cannot pass
by accident. No repo checkout, no `demo-product-tests`, no network.

AC7 — HOLDS. Drives the real `pipeline._emit` against a real tmp_path store seeded with the
foreign-key rows it needs. Distinct → returns False, zero findings; gap → returns True, exactly
one finding whose stored fingerprint equals `cases.fingerprint(...)`. That last assertion also
welds AC7 to AC8.

AC8 — HOLDS. Same inputs → same fingerprint, different subject → different, different evidence
key → different, and a subprocess with a clean env and tmp_path cwd reproduces the identical
fingerprint, which is the strongest form of "not the clock or the process". Suppression depends
on exactly this function, and the emission-gate test confirms the value stored in `finding`.

AC9 — HOLDS. The test runs a clean-env pytest over an empty directory and asserts exit 5 and
non-zero. I additionally verified the repo's own config does the right thing when nothing is
collected (pytest from the repo root with an empty target: exit 5), so no repo setting can mask
a broken collection as success. Caveat: the in-repo test proves pytest's exit semantics; the
repo-level behaviour is only proven by my probe, not pinned by the suite.

AC10 — HOLDS. A session-scoped autouse fixture digests the whole working tree (sha256, ignoring
only interpreter caches) before the first test and compares after the last; `test_isolation.py`
names the comparison explicitly. `data/testops.db` sits inside the tree, so a write to it is
caught. The subprocess-based tests run with `no:cacheprovider` and tmp_path cwd, so they cannot
write into the repo.

## Three sharpest concerns

1. The `.venv` editable install is stale. `__editable___testops_0_1_0_finder.py` was built Nov 20
   — before the pyproject fix — and still maps `testops.cases` as a namespace package pointing
   at a directory that no longer exists. It imports today only because the finder maps the repo
   root wholesale. Re-run `pip install -e ".[dev]"` in the project venv, or the next fresh
   checkout works while this one rots.
2. AC10's guard can only see the repository tree. A test writing to `$HOME`, site-packages or any
   path outside the repo but outside tmp_path would pass silently. True of nothing currently in
   the suite, but the criterion's wording ("any path outside tmp_path") overclaims what the
   mechanism proves.
3. `test_packaging.py` imports through `sys.path` (cwd), not through the installed distribution —
   the fresh-install proof in AC2 exists only because I ran it during review. If someone later
   breaks `packages`/`package-data` in a way that still imports from the tree (e.g. missing
   schema.sql in package-data), the suite stays green. The documented-install test the ticket
   implies is one `subprocess.run` away and not written.

## Demo — for the Product Owner

The problem. Every number TestOps produced came from throwaway probe scripts that no longer
exist, and the factory's review gate is a test run that has nothing to run — a reviewer could
only take the builder's word.

What changed. A 17-test pytest suite plus a minimal fix to `pyproject.toml`: pytest declared as a
dev extra with a documented install command, and the package list corrected so an editable
install actually contains the web UI and scripts.

How we know it works. I ran the suite myself from the project venv with the environment stripped:
17 passed in under 2 seconds, no network (one test actively refuses any socket), no credentials.
The suite covers each invariant the factory depends on: the schema creates every table; a claim
survives a fresh database connection unchanged; a browser-needed claim asserted over HTTP is
classified a gap and a response-body claim is distinct; the emission gate raises one finding per
gap and none per distinct; fingerprints are stable across processes so suppression keys hold; and
an empty suite exits "no tests collected", never success. A guard digests the whole repository
before and after the run, so a test that writes to the repo or the live database fails its own
run. I also executed the documented install command in a fresh venv and imported the UI from it.

What it does not solve. It is a harness, not analysis confidence: no test yet exercises the
collectors, the full pipeline, or judgement prompts, and the repo-tree guard cannot see writes
outside the repository. The installed venv in this checkout predates the packaging fix and should
be re-installed.

Where to look. `tests/` (one file per criterion, named for it), `tests/conftest.py` for the
repo-write guard, `tests/README.md` for the documented commands, and the pyproject diff in
commit c7ab258.
