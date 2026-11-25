# TESTOPS-25 — Review

## Verdict — PASS

The licence is byte-identical to upstream, every provenance claim I could test held exactly, the guard genuinely guards, and the suite is green (277 passed).

## Criteria

- AC1 — HOLDS. `tests/fixtures/demo-service/LICENSE` is byte-for-byte identical to upstream's `LICENSE` at `main` (same SHA-256: `97b3daee1fb4…a693a`).
- AC2 — HOLDS. Every claim in `PROVENANCE.md` checked out: commit hash, date, file counts, "no text modified", and "BOM stripped on 21 files" — all verified against upstream directly. Nothing exaggerated, nothing omitted.
- AC3 — HOLDS. `THIRD-PARTY-NOTICES.md` names the fixture, the MIT licence and the copyright holder, and correctly defers to the fixture's own `LICENSE` rather than restating the notice (no misstated scope; it accurately describes the 108-file corpus scope).
- AC4 — HOLDS. `tests/demo-service_fixtures.py` docstring keeps the candid sentence ("The corpus is somebody else's MIT-licensed code, not ours") and points at `PROVENANCE.md`.
- AC5 — HOLDS. No `.csproj`, `.sln`, `.slnx`, `.props`, `.targets` or `global.json` anywhere under `tests/fixtures/demo-service/`; the analyser sees exactly 108 corpus files and the notices are excluded from analysis; CI green.
- AC6 — HOLDS. Verified by deletion: removing `PROVENANCE.md` fails `test_provenance_names_the_upstream_commit_and_what_travelled`; restoring it makes the suite pass again.

## The licence, diffed

Command:

```
curl -s https://raw.githubusercontent.com/reqnroll/demo-service/main/LICENSE -o _upstream_LICENSE.tmp
cmp _upstream_LICENSE.tmp tests/fixtures/demo-service/LICENSE
sha256sum both
```

Output: `BYTE-IDENTICAL`; both files SHA-256 `97b3daee1fb482163923337773a46a904e97b57e8f500da0146ffae409ea693a`. No differences of any kind. (Temp file removed afterwards.)

## The provenance, checked

Each claim, and how I tested it:

- **Commit `78153818b81d7c9a324af81b4e95f65aead705b4` exists and is the right one.** GitHub API `/repos/reqnroll/demo-service/commits/78153818…` returned that exact SHA, author Gáspár Nagy, message "update dependencies and code cleanup".
- **Date 2026-01-15.** Same API response: `2026-01-15T09:45:32Z`.
- **108 files = 18 `.feature` + 90 `.cs`.** Counted via `git ls-files`: 108, counter `{.cs: 90, .feature: 18}`. Per-project splits in PROVENANCE (31/44/33) are consistent with the directory layout.
- **No text modified.** For all 108 files I fetched the upstream blob at that commit from `raw.githubusercontent.com` and compared against the committed git blob (not the working tree): 87 files are byte-identical; the remaining 21 differ only as claimed (see next line). Zero content differences.
- **Only a BOM differs on 21 files.** Upstream carries a UTF-8 BOM on exactly 21 files — all 18 `.feature` plus the 3 `MSTestSettings.cs` — and the local blobs are identical to those files after stripping the upstream BOM. The 21 differing files are precisely the 21 BOM files. Spot-checked one explicitly (`DemoService.Specs.API/Features/Authentication.feature`): `blob == up[3:]` is True.
- **One subtlety worth recording:** the *working tree* on this machine shows CRLF in all fixture files, but `git config core.autocrlf` is `true` and the committed blobs contain no CRLF — the repository stores LF, as PROVENANCE claims. Working-tree checkout artefact, not a provenance error.

## Three sharpest concerns

1. **The guard's commit-check is content-shaped, not integrity-shaped.** It asserts a 40-hex hash appears in `PROVENANCE.md`; it cannot tell whether that hash names the commit the fixture was actually copied from. Today it does (I checked against upstream); a future editor could swap the hash and the test would stay green.
2. **`UPSTREAM_LICENSE_SHA256` is a re-pinned hash of our own copy.** It protects against drift from what we pinned, but if the pin itself were edited alongside the file, the test follows the edit. The independent diff I ran closes this for today, but the test alone would not.
3. **The corpus is re-derived from the fixture at test time, not from the store.** Consistent with the factory rule about analysing from the store, the 48-scenario/18-duplicate story depends on this fixture never drifting; the pinned commit in PROVENANCE is the anchor, but nothing diffs the fixture against that commit in CI (that check lived in this review, not the suite).

## Demo

- **The problem:** the repository shipped a verbatim subset of someone else's MIT code with no licence notice and no record of provenance — a licence violation and an untraceable claim.
- **What changed:** `tests/fixtures/demo-service/LICENSE` (verbatim upstream MIT notice), `tests/fixtures/demo-service/PROVENANCE.md` (upstream, commit, date, exact file set, omissions, the one mechanical difference), root `THIRD-PARTY-NOTICES.md` (visible index), a candid docstring in `tests/demo-service_fixtures.py`, and `tests/test_third_party_attribution.py` to keep all of it from being tidied away.
- **How we know it works:** licence byte-identical to live upstream (`cmp` + SHA-256 match); all 108 files compared against upstream blobs at the named commit — byte-equal modulo the 21 BOMs, exactly as documented; suite 277 passed; deleting `PROVENANCE.md` turns the suite red, restoring it green.
- **What it does not solve:** the attribution tests cannot detect a coordinated, consistent edit (hash re-pinned alongside licence change), nor re-verify the fixture against the upstream commit in CI; and the licence's requirement is satisfied for the fixture but the repo's own licence posture is out of scope of this ticket.
- **Where to look:** `tests/fixtures/demo-service/LICENSE`, `tests/fixtures/demo-service/PROVENANCE.md`, `THIRD-PARTY-NOTICES.md`, `tests/test_third_party_attribution.py`, `tests/demo-service_fixtures.py` (docstring).
