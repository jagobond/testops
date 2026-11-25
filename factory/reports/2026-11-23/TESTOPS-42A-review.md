# TESTOPS-42A review — reviewer, 23 November 2026

Everything below was verified from this worktree with
`env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe`,
against the store copy in `data/`. Full suite: **579 passed in 99.6s**.

## Verdict

**Accepted.** The seam is real, the refusals are real, AC3 is proven by absence of change against the
pre-build tree, and AC5 — the soul of the ticket — holds live on the demo-booking corpus. Two
auxiliary numbers in the inventory (§5's 46 of 76 and 29 of 33) do not reproduce from the blobs under
any matching rule I tried; the five numbers this review was asked to spot-check all do. Neither defect
undermines the decision the document supports, but §5 should be corrected before T42-C is costed from it.

## AC5 - unsupported means unsupported

Called `cucumber_js.ECOSYSTEM.bindings(files)` and `.drivers(files)` directly over the 14 non-`.d.ts`
JS/TS files of the stored demo-booking test arm (21 files, 6 features): **both raise
`UnsupportedEcosystem`**; neither returns `[]`. A full levels run over the same stored blobs, in a
throwaway store: **0 claims**, assessment `not_assessable`, sentence exactly
"cucumber-js is unsupported: this build can recognise JavaScript step definitions and cannot read
them, so it will not guess what they do." The rendered run page (HTTP 200) contains
"44 cucumber-js step-binding declarations in 5 files" and "no support for cucumber-js", and greps
clean for both banned phrases: "no layers found" absent, "could not be tied to a layer" absent
("no layers" absent as a substring too). The runs index prints cucumber-js and is likewise clean.
cucumber-js remains unsupported. Confirmed.

## AC3 - absence of change

- **Demo Product levels rebuilt** from the stored blobs of `demo-product-levels-20261122-a3f19853-r11`:
  **94 claims, verdicts 90 distinct / 2 review / 1 unplaced / 1 gap** — exactly the stored run's split
  (stored run `demo-product-levels-20261122T204947`, same 94 rows, same verdict counts).
- **DemoService duplication re-run** over the stored blobs of
  `demo-service-20261122-78153818-r8` (135 stepdefs, 18 features, 123 bindings, reqnroll detected):
  **17 claims, all `duplicate`** — 17/17 as stored.
- **Case pages byte-for-byte:** I checked out the pre-build tree (d9b81ab) as a scratch worktree,
  rendered **all 250 pages** (245 case pages + 5 run pages) from the same store copy with the old
  code and with this code, and diffed the byte trees and their sha256 manifests:
  **identical** — `diff` empty on both. (The build report's "goldens" are not committed anywhere;
  this is my own reconstruction of the comparison it claimed.)

Exact numbers: 94 / 90 / 1 / 1 / 2 and 17 / 17, and 250/250 pages byte-identical.

## AC1 registry

Proven live against the real corpus and registry: duplicate module name raises `DuplicateEcosystem`
("two ecosystem modules claim the name 'cucumber-js'"); a repository no module recognises raises
`UnknownEcosystem`; a Steps.cs beside a login.stepdef.js raises `AmbiguousEcosystem`. Then a fake
ecosystem (`detect` returns unsupported, `bindings`/`drivers` raise) registered as the only module and
run through the full levels pipeline: **no crash, no empty result** — 0 claims, `not_assessable`,
the sentence names "Fake Ecosystem is unsupported: support does not exist yet", and the per-repository
record was written to the snapshot. Confirmed.

## AC2 record survives rebuild

Read back from the store, not the page: a run's snapshot `meta` carries `ecosystems` with one record
per repository arm (`role`, `repository`, `ecosystem`, `title`, `supported`, `evidence`, `reason`) —
verified for the fake-ecosystem run and the real-corpus run. Survives rebuild in the sense that
matters: `rebuild.rebuild` over the pre-seam Cypress levels snapshot (`...-r3`) refuses to resurrect
claims the run never made — 0 claims, `ecosystem: cucumber-js`, `ecosystem_supported: False` — and
over the Demo Product snapshot still resolves `reqnroll`/supported. One caveat for T42-C: the rebuild
**recomputes** the ecosystem from the blobs rather than reading the stored record, so record and
recompute could drift silently; nothing checks them against each other.

## The inventory, spot-checked

Recounted independently from the stored blobs (own scanner, not the module's regexes):

| number | verdict |
|---|---|
| 44 declarations (26 When / 13 Then / 5 Given, 5 files, all single-quoted) | **confirmed** — independent line-anchored scan gives exactly 44, same verb split |
| 16 multi-line layouts (28 same-line) | **confirmed** — 16/28; a same-line-only scan yields 28, matching the doc's account of the v1 detector |
| 11 real custom commands (15 raw − 4 commented) | **confirmed** — raw 15, stripped 11, comments 4; file split matches the doc's table |
| 17 of 43 asserting steps match | **confirmed** — 43 asserting steps (33 Then + 10 And over 76 scenario steps, Backgrounds excluded); with `{string}` permissive, exactly 17 match and 26 do not |
| 26 match nothing | **confirmed** — 43 − 17 = 26, all naming validation/mandatory error messages against the 2 drifted patterns |

Also confirmed en route: 6 features, 33 scenarios, 43 distinct patterns with the one duplicate
("Visitor will get validation/mandatory error message: {string}" in booking.stepdef.js and
contact.stepdef.js), 86 `{string}` occurrences, 5 `{int}`, 15 no-placeholder patterns, 0 `cy.request`
in step bodies, 16/28 body split, 0 `*Driver.*` files, cy.get 64 / .should 17 / expect 6.

Two auxiliary numbers I could **not** reproduce:
- "steps that match a declared pattern 46 of 76" — I get 38 (with `{int}` = `\d+`) or 48 (with `{int}`
  fully permissive). No rule I tried gives 46.
- "Given/When steps that match 29 of 33" — I get 21 or 31 of 33 under the same two rules. No rule
  gives 29.

The headline 17/43 and 26/43 are solid under a stated rule; 46 and 29 are not reproducible under any
rule that also produces 17, and the doc states no rule for them. They should be corrected or the rule
stated. One more ambiguity: "patterns mentioning {string}: 29" — I count **28 distinct** patterns; 29
only holds if the duplicated pattern is counted per declaration, which the table does not say.

## The estimate

6.25 days: scanner 0.5, matcher 0.5, scoping 0.25, custom-command model 1.5, JS/TS vocabulary 1,
call-graph inference 1.5, tests 1, wiring 0 (paid). Scoping 0.25 is safe (the stem rule covers 5/5
stepdef files here — I verified the file set).

**Most likely wrong line: call-graph layer inference, 1.5 days, in the low direction.** The evidence
base for it is 11 commands in 4 files with exactly one level of helper indirection — the friendliest
call graph a Cypress suite can present. The doc itself establishes that layer is per-command, not
per-file, and that 28 of 44 bodies resolve only through helpers; real suites alias the cy import,
chain `.then()`, re-export helpers across modules, and mix `cy.` families in one command. The
underlying command-body model (1.5) shares the same exposure: it is priced off the same clean corpus.
Tests at 1 day is the second-worst exposure given this codebase's standard of byte-parity goldens,
but that is a stretch risk, not a misread. If T42-C is quoted on 6.25 days, I would quote 7.5-8 for
the same scope and say the corpus bonus is the risk being priced.

## Three sharpest concerns

1. **§5's two auxiliary match rates (46 of 76, 29 of 33) do not reproduce from the stored blobs.**
   The five headline numbers all confirm, but a document whose selling point is "counts, not
   estimates" carries two numbers nobody can derive. Fix the table (or state the rule) before T42-C
   is estimated from it.
2. **The ecosystem record is proven only on snapshots written after this ticket.** Every snapshot in
   the live store predates the seam, so `unsupported_spot`'s "reconstructable from the record alone"
   path has never executed against a stored snapshot; and the rebuild recomputes the ecosystem from
   blobs instead of reading the record, so the two could drift without any test noticing.
3. **§1's "76 steps (33 When, 33 Then, 10 And)" silently excludes the 6 Background Given steps** —
   the corpus has 87 step lines. The 76 denominator is right for what follows, but the table gives a
   reader no way to see that Backgrounds were dropped; same class of omission the ticket exists to
   prevent, in miniature.
