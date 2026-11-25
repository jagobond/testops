# TESTOPS-30 review — stale case id, --keep wording

Reviewed: worktree C:/Users/<name>/Projects/testops-t30, branch factory/testops-30-stale-id,
diff feature/f1..HEAD (cli.py, retention.py, web/app.py, tests/test_retention.py).
Imports verified to resolve to this worktree (testops.__file__ = C:\Users\<name>\Projects\testops-t30\testops\__init__.py).
Suite: 327 passed, 3 skipped (73 s).

## Verdict — PASS

Every malformed or pruned case id returns a real 404 HTML page (no traceback, no blank body), the help text and the prune report say "N per project" and print the per-project kept/held counts, the TESTOPS-24 refusal rule still holds, and the pinned verdict counts are unchanged.

## Criteria

- **AC1 HOLDS.** `retention --help` and the prune report both say "per project"; the report prints a per-project kept/held table (real run shown below). No behaviour change: retention.py's only edit is a docstring sentence.
- **AC2 HOLDS.** A case id whose snapshot was pruned answers 404 with the "This case is no longer in the store" page naming the id and saying the evidence was pruned by retention.
- **AC3 HOLDS.** Both new web tests drive the real handler over a real socket and assert 404 / 200 plus page contents; both pass.
- **AC4 HOLDS.** Only the /case route changed; suite green; verdicts verified (see below).

## Ids tried

Probed against a COPY of data/testops.db, pruned with keep=1 (16 snapshots deleted), served through the real handler:

| request | status | first line / h1 |
|---|---|---|
| pruned case id (`case-cotw-levels-20261120T194425`) | 404 | doctype... h1: "This case is no longer in the store" |
| never existed (`case-never-existed`) | 404 | doctype... h1: "This case is no longer in the store" |
| empty id (`/case/`) | 404 | doctype... h1: "TestOps" (generic not-found page) |
| slash in id (`/case/a/b`) | 404 | doctype... h1: "TestOps" (generic not-found page) |
| percent-encoded path (`case%2F..%2F..%2Fetc`) | 404 | doctype... h1: "This case is no longer in the store" |
| percent-encoded chars (`case%20with%20spaces%3Fq%3D1%23frag`) | 404 | doctype... h1: "This case is no longer in the store" |
| very long id (4000 chars) | 404 | doctype... h1: "This case is no longer in the store" |
| surviving id | 200 | doctype... h1: "cotw · Duplication" |

No crash anywhere. The pruned page names the id, says "no longer in the store", and explains the evidence was pruned by retention.

## Wording

`retention --help`:

    --prune      delete snapshots outside the --keep window (N per project);
                 does nothing without --yes
    --keep KEEP  keep N per project: the N most recent snapshots in each project
                 survive, and older ones are candidates for deletion

Report (`retention --prune --keep 2`, no --yes, on the copied store):

    prune plan — keep 2 per project (the 2 most recent snapshots in each project)
      per project (kept / held):
        cotw         4 / 14
        reqoverflow  3 / 7

The per-project counts are printed and honest (kept exceeds N where a decision or newest-run protects a snapshot). The missing-`--keep` refusal line also says "(N per project)".

## Nothing destructive changed

- retention.py's only product change is a docstring sentence; the plan/prune rules from TESTOPS-24 are untouched.
- Refusal re-run on a copy: decided `case-reqoverflow-dup-20261120T153431` (snapshot `reqoverflow-20261120-78153818`), then `prune(keep=1, yes=True)`. The snapshot was still in the store afterwards and absent from the deleted list (reason: "a case referencing it has a decision").
- Verdicts: ran the pinned count against the product store: 90 distinct + 1 unplaced + 1 gap + 2 review = 94. (The pinned tests themselves skip in a clean worktree because data/testops.db is a build artefact; the query confirms the same numbers.)

## Three sharpest concerns

1. **Malformed ids get a different, less helpful page.** An empty id or a slash-bearing id falls out of the `/case/([^/]+)` route to the generic "No such case" page, not the explanatory stale page. The stale page's own claim that "an id that was never in the store reads the same way" is only true for well-formed single-segment ids; a truncated or corrupted link (e.g. a cut-off id) can land on the generic page. Not a defect against AC2, but worth a thought if stale links are the motivating scenario.
2. **The stale page's keep mention omits "per project".** Its body renders `retention --prune --keep N` without the per-project qualifier that AC1 just established everywhere else; a reader sent there gets the old ambiguous wording back.
3. **The kept/held counts can exceed N without saying why in the table itself.** The real report shows `cotw 4 / 14` for `--keep 2`; the reasons appear only in the delete list's omissions, so a reader must infer that decisions and newest-run protections did the holding. Fine, but a one-line "kept more than N in some projects: protections applied" would close it.
