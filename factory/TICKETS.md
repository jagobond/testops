# TICKETS — TestOps

The board is the record of what exists. Ticket files live in `factory/tickets/<id>.md`; the queue
is read from `main`, so a ticket that exists only on a branch is invisible and will not run.

Status values: `ready` (buildable now) · `blocked` (waiting on a decision or a predecessor) ·
`in-progress` · `needs-human` (built, awaiting Lead/PO) · `done` · `killed`.

Only `ready` and `blocked` are meaningful to a coordinator; sequencing prose in the status field
makes a ticket invisible. `proposed` is a Lead placeholder: argued for, not yet written as a
ticket, because criteria encode what PRODUCT.md and ROLES.md decide.

| id | title | feature | status | note |
|----|-------|---------|--------|------|
| TESTOPS-1 | Factory scaffolding: git baseline, PRODUCT/ROLES/AGENTS, board | F0 | done | Lead work, no builder |
| TESTOPS-2 | Test harness baseline | F1 | done | 17 tests; PR #1 merged into feature/f1 as 5c008b7 after a PASS review |
| TESTOPS-3 | Claim schema v2 — one claim per assertion, with provenance and blind spots | F1 | done | 53 tests; PR #2 merged as 616d5d8 after a PASS review |
| TESTOPS-4 | One claim per assertion, said in words a developer can act on | F1 | done | 84 tests; PR #3 merged as 595894e after a PASS review |
| TESTOPS-5 | Sources are declared, not assumed — the capability registry | F1 | done | 162 tests; crux held end to end; PR #13 merged after a PASS review |
| TESTOPS-6 | The case page — an argument a developer can act on | F1 | done | 111 tests; PR #6 merged as fecfb6e after a PASS review |
| TESTOPS-7 | Page-contract suite from qa-author, never shown the implementation | F1 | done | Brief written (24 promises, 5 page types); blind qa-author writes the suite; aims at the live store |
| TESTOPS-8 | Packaging proof: install into a fresh venv and import through the distribution | F1 | done | Built: wheel installed in a fresh venv, served 4 pages; red run shown; CI runs the marked tests; 557 tests; PR #42 |
| TESTOPS-48 | The packaging coverage rule accepts a pattern that ships nothing | F1 | done | Wheel namelist is the authority; wrong-prefix declaration now fails; 3 red runs; PR #43 |
| TESTOPS-49 | The packaging coverage test passes when there is nothing to check | F1 | done | From the TESTOPS-48 review: empty enumeration yields a green test asserting nothing; add non-empty and minimum-count guards |
| TESTOPS-9 | Stale claim vocabulary — the schema and the docstrings describe verdicts that were abandoned | F1 | done | 514 tests; three places corrected, test bites both ways; PR #36 |
| TESTOPS-10 | Classification coverage — half the real corpus is unclassifiable | F1 | done | 48 → 0 unplaced, gaps unchanged; PR #4 merged after a PASS review |
| TESTOPS-11 | Restraint — a claim is not checked because one of its words is familiar | F1 | done | 90 distinct / 1 unplaced / 1 gap / 2 review; PR #5 merged as 1c1fca3 after a PASS review |
| TESTOPS-12 | Labels finish the job, and restraint stops being a be-verb pattern | F1 | done | Accumulated polish: eleven scenarios with mixed labels, be-verb restraint, every statement opening "This test", plus the TESTOPS-16 wording nit |
| TESTOPS-13 | The app cannot be imported by the interpreter that serves it | F1 | done | 118 pass on 3.12, 114 pass + 4 skip on 3.11; PR #7 merged after a PASS review |
| TESTOPS-14 | A level run cannot rebuild itself, and its claims carry no observations | F1 | done | 195 observations, 0 claims empty; verdicts unmoved; PR #8 merged as 28894a5 after a PASS review |
| TESTOPS-15 | Make the floor real — the suite runs on 3.11 in CI | F1 | done | Proven fail-capable (run 44962212770): 3.11 leg red, 3.12 green; PR #10 merged |
| TESTOPS-16 | Say which kind of nothing it is | F1 | done | 140 tests; PR #12 merged after a PASS review |
| TESTOPS-17 | A clean bill requires having looked | F1 | done | schema v3, 1005 old claims demoted to not-assessed; PR #14 merged after a PASS review |
| TESTOPS-18 | The response is not the store's mouthpiece | F1 | done | Restored from the ticket file |
| TESTOPS-19 | The case page opens with the answer, and shows the code | F1 | done | 210 tests; snippets verified against commit bytes; PR #16 merged after a PASS review |
| TESTOPS-21 | The duplication analyser still writes v1 claims, so its cases say nothing | F1 | done | 220 tests; 18 cases, 1 finding each, 18 distinct statements; PR #17 merged after a PASS review |
| TESTOPS-22 | A quiet run is not a resolved case | F1 | done | 228 tests; counts traced to stored rows; PR #18 merged after a PASS review |
| TESTOPS-23 | The page narrates the analyser instead of telling the reader one story | F1 | done | Restored from the ticket file |
| TESTOPS-24 | Retention — keep every run explainable without keeping every byte four times | F1 | done | 288 tests; blobs dedupe proven (0 bytes per re-run); PR #22 merged after a PASS review |
| TESTOPS-25 | The fixture is somebody else's MIT code, and we are not carrying its licence | F1 | done | 108 files verified against upstream blobs; PR #20 merged after a PASS review |
| TESTOPS-26 | The summary is there, but the reader has to dig it out of a paragraph | F1 | done | Three-part scan block; plain-English lint proven to bite; reviewed with T23 |
| TESTOPS-27 | The action line drops anything after a semicolon, and trusts that it was redundant | F1 | superseded | Reviewer finding on T23/26: a truncated action is the one thing a reader cannot detect |
| TESTOPS-28 | Stop classifying the tail; keep the whole action and fix redundancy at the source | F1 | done | Restored from the ticket file |
| TESTOPS-29 | The analyser's action strings repeat the argument, and the reader now sees it | F1 | done | Restored from the ticket file |
| TESTOPS-30 | Two small defects the retention review found: --keep scope, and a stale case id | F1 | done | A crash where a 404 belongs; a flag whose name promises more than it does |
| TESTOPS-31 | Duplication calls two scenarios the same when their tables differ | F1 | done | One pair resolved, no new duplicates; PR #25 |
| TESTOPS-32 | A duplicate claim never shows the copy it names | F1 | done | Counterpart shown before context; three lies tried, none rendered wrongly; PR #26 |
| TESTOPS-33 | The case list says "the suggestions list should be", which is not a case | F1 | done | Headlines; round 1 NEEDS-FIX (badge markup, inverted trim), round 2 PASS; PR #28 |
| TESTOPS-34 | A run with no findings is listed as an open case awaiting a decision | F1 | done | Rule moved into the list query; closed and quiet provably distinct; PR #29 |
| TESTOPS-35 | A reviewer's fixture case is sitting in Harry's live store | F1 | done | Scrub ran on the live store: case_ 168->167, 1 fixture removed; PR #27 |
| TESTOPS-36 | Two analysers, one step, two pages that never mention each other | F1 | done | Cross-reference both ways; four adversarial stores, no lie; PR #30 |
| TESTOPS-37 | Nothing proves a recorded decision stops the next run reporting the same thing | F1 | done | 417 tests; six user edits probed, gates proven by deletion; PR #31 |
| TESTOPS-38 | A project is a group of services, and a user sets it up without touching code | F2 | done | ADR-1 built; live store migrated v3→v4, 23 pages byte-identical; PR #34 |
| TESTOPS-39 | A second specimen of a different shape, to find out whether the analyses generalise | F2 | done | JS/Cypress+Cucumber tests against a Java multi-service platform — different ecosystem, different bindings, separate repos |
| TESTOPS-40 | Say what a decision covers, and stop a shifted twin from silencing one | F1 | done | Cover sentence + `@total` key; 11 goldens differ by the sentence alone; 540 tests; PR #39 |
| TESTOPS-41 | Files the collector cannot read are silently dropped, and the page then says they were read | F1 | done | 428 tests; three capability states; kind list is data; PR #33 |
| TESTOPS-42 | The tool reads one ecosystem, and says nothing when it does not | F2 | done | PO chose C (pluggable layer, cucumber-js first). Open question answered by T42A's inventory; full build stays blocked until it lands |
| TESTOPS-42A | The extractor seam, ecosystem detection, and a counted inventory of what cucumber-js needs | F2 | done | Seam + registry + per-repo ecosystem record; cucumber-js detected and refuses; 44/16/11/17 numbers independently confirmed; 579 tests; PR #44 |
| TESTOPS-42C | cucumber-js, built as a module with its own vocabulary and command model | F2 | done | Quote 7.5-8 days (review's judgement, not 6.25). 17 of 43 placed is the honest target; 26 unplaced for a true reason. Unblocks after T50 |
| TESTOPS-42C-1 | cucumber-js reads its own bindings: 44 declarations, both layouts, two placeholder kinds | F2 | done | Part 1 of 3: the parsing floor, no placement yet |
| TESTOPS-42C-2 | cucumber-js finds the layer where it happens: commands, helpers, call graph | F2 | done | Part 2 of 3: per-command layer, JS/TS vocabulary, one level of helpers |
| TESTOPS-42C-3 | cucumber-js places 17 of 43 assertions, and says why the other 26 are not placed | F2 | done | Part 3 of 3: placement, honest unplaced reasons, page voice, wrong-layer guard |
| TESTOPS-50 | Two numbers in the inventory cannot be reproduced | F2 | done | From the T42A review: 46/76 and 29/33 reproduce under no rule; 29 vs 28 `{string}` patterns. State the rule, recompute with a script |
| TESTOPS-43 | A sentence that hides its own partial reads | F1 | done | From the TESTOPS-41 review: aggregate totals hide a per-capability zero, a harmless skip renders nowhere, partial reads say "consulted" |
| TESTOPS-44 | The secret guard errs in both directions, and the store upgrades without saying so | F2 | done | From the TESTOPS-38 review: base64 key accepted because the guard exempts `/`, a real 32-char key refused, migration silent on open |
| TESTOPS-45 | The store will accept any verdict string, and 128 rows still carry retired names | F2 | done | Schema v5 vocabulary + triggers, `check-store`; 534 tests; PR #38 |
| TESTOPS-46 | A store can no longer be restored from its own history | F2 | done | Insert allows ever-emitted, update stays current-only; `add_claim` guard now actually called; 548 tests; PR #40 |
| TESTOPS-47 | Each analyser states the cover of its own decision, and states identity rather than promising an event | F2 | done | From the TESTOPS-40 review: one global sentence is wrong for duplication and over-promises on net-zero twin edits |
| TESTOPS-51 | `password=hunter2` was stored and echoed by `/config`; a project cannot be deleted | F1 | done | From T7: the screen exists per-field, so every field inherits the hole. One shared check, plus a project delete route |
| TESTOPS-52 | "Cannot assess" wears the alarm colour, and 32+ badges have malformed class attributes | F1 | done | From T7: the soft style exists in CSS and is applied to nothing; `class="badge class="hot""` makes `hot` inert |
| TESTOPS-53 | Running `pytest` writes to the live store | F2 | done | From T52's disclosure: `tests/contracts` defaults to the live server and POSTs a project. Give it its own temp server and store, and make it a CI gate |
| TESTOPS-54 | A case does not link to its run; `/config` is reachable from nowhere | F1 | done | From T7 P5: no dead ends, no page that only exists if you know the URL |
| TESTOPS-55 | The front page states no totals; the run page gives no per-kind read counts | F1 | ready | From T7 P7/P10: a reader cannot state what exists or what was read, and never sees an explicit zero |
| TESTOPS-56 | The screen refuses `token-bucket-limiter` and any value starting `AKIA`/`xoxb-` | F1 | ready | From the T51 review: qualify prefix rules by body shape, scope the short-identifier rule deliberately, pin a 25-value false-positive table |
| TESTOPS-57 | The 351 claims the tool could not place have no page of their own | F1 | ready | From the T52 review: `unplaced` never becomes a case, so the soft tone is rendered nowhere. A per-run section with anchors and the soft treatment |
| TESTOPS-58 | `TMPDIR` can move the root the disposable-store check trusts | F2 | done | From the T53 review: the refusal is structural but relative. Refuse an env temp root under the repo/home, pin the root, and state what is actually guaranteed |
| TESTOPS-59 | A token pasted inside a sentence is stored; `session-token` is wrongly refused | F1 | ready | From the T56 review: scan for credential shapes at any position (not just prefix), give every prefix a real body floor, and make the identifier boundary state itself |
| TESTOPS-60 | The unplaced section is a 93KB wall at 220 entries, and its anchors are positional | F1 | ready | From the T57 review: group by reason, disclose or cap with an honest count, state the reason once, and anchor on the claim id |

|----|-------|---------|--------|------|

Feature F1 = "a claim a developer can act on". F0 is scaffolding and carries no product outcome.

## Why the harness comes first

The factory's gate is a test run whose failure modes are distinguishable: pass, genuine failure,
and environment error. TestOps currently has **no tests** and `pytest` was installed only as a
side effect of this scaffolding. A reviewer asked to judge T3 against acceptance criteria with no
suite in the repo can only read the diff and take the builder's word for it — which is the
arrangement the factory exists to replace.
