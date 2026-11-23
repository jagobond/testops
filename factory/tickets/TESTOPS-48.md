---
id: TESTOPS-48
title: The packaging coverage rule accepts a pattern that ships nothing
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-8
---

# TESTOPS-48 — Coverage is not the same as shipping

## Finding (TESTOPS-8 review, concern 1)

AC5 asks: is every non-Python file under `testops/` covered by a declared `package-data` pattern? The matcher uses
`PurePosixPath.match`, which right-anchors, so a pattern declared as `templates/probe.html` under `"testops"` matches the
file `web/templates/probe.html` - but package-data patterns are resolved relative to the **package root**, so that
pattern ships nothing. The test would pass and the wheel would be missing the file.

Only `store/schema.sql` has a second line of defence, because the wheel's namelist is asserted for it by name. Everything
else rests on a matcher that is looser than the thing it claims.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The coverage rule is decided by the **built wheel**, not by string matching: every non-Python file found under `testops/` must appear in the wheel's namelist at its package-relative path. Remove the matcher as the authority. |
| AC2 | Prove it bites: create `testops/web/templates/probe.html`, run the test, watch it fail naming that path, delete the probe. Then declare the pattern wrongly (package-relative path omitted) and watch it fail too - the second case is the one the old matcher let through. |
| AC3 | A missing file is reported with the path it expected **and** the declared patterns that were supposed to ship it, so the reader is not left guessing which glob to fix. |
| AC4 | Runtime stays inside the AC4 budget from TESTOPS-8 (the wheel is built once per session, not per test), and no network is used. |
| AC5 | Suite green, counts unchanged, no product code touched. |

## Notes

- This closes the last known hole in the packaging proof. Keep `PurePosixPath` matching only for error-message
  suggestions, never for the verdict.
