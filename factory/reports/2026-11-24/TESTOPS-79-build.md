# TESTOPS-79 build — display copy is not the subject of the claim

2026-11-24, branch `factory/testops-79-quoted-copy`, worktree
`C:/Users/<name>/Projects/testops-t79`. `level_fitness` 0.12 → **0.13**. No store schema change.
Eight verdicts moved, all of them the wrong repeats this ticket was written to refuse; nothing else
moved.

Suite, from the project `.venv` with `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX` stripped
and `PYTHONNOUSERSITE=1`: **1248 passed, 2 skipped** (181.1 s). Contract suite alone
(`pytest tests/contracts`): **37 passed, 2 skipped** (12.8 s). `tests/test_product_evidence.py` is
now 27 tests (was 22); five are new and two existing tests were rewritten for AC7. Goldens:
**14 pages, all byte-identical** — `index.html`, `runs.html`, `case-page-01.html` …
`case-page-12.html`. No golden file changed on disk.

## The rule

The first real corpus run proposed nine `repeats product`; eight shared the word `message` between
an assertion about a **banner** and the message service's `GET /{id}` *get message*. The fix is a
reading rule, not a stop-list of nouns:

> a word is **display copy** when every occurrence of it in the assertion lies in text the
> assertion reproduces — a quoted run, or a banner phrase — and display copy can be neither a
> candidate shared word nor the assertion's intent.

The typography that identifies copy, from the assertion alone:

- **quoted runs** (`"…"`, `'…'`, curly forms) are copy; a quoted **placeholder** (`'<room_name>'`,
  `'{room}'`) is a *slot*, not a literal, and its words stay candidates;
- **banner phrases**: a capitalised phrase introduced by a display verb (`get`, `see`, `show`,
  `display`, `render`) — the mid-sentence capital is the mark of a title or banner — running to the
  next connective, determiner, auxiliary, quote or the end of the sentence. `Booking Successful!
  message` and `Thanks for getting in touch message` are both such phrases.

A capitalised domain noun with no display phrase in front of it (`New Booking is created`) stays a
candidate, which is why the rule does not refuse the room-creation assertion. The detector can only
*withhold* a candidate; it can never manufacture one, so a misread banner can turn a repeat into a
near miss but can never turn a claim into an accusation.

## What changed

| file | change |
|---|---|
| `testops/analysers/level_fitness.py` | `_display_copy()` / `_display_runs()` — quoted runs (slots excluded) and banner phrases; `_product_meaningful` and `_assertion_intent` take a `skip` set so display copy is neither a candidate word nor an intent; `product_match` ranks visible words first and returns the nearest refused surface with `display_copy` / `display_text` only when nothing visible matches; `_product_record` records `near_miss_kind: "display_copy"` with the word and the copy in its reason, and assesses `KP` claims where the run drove a browser (AC7). Version 0.13. |
| `testops/queries.py` | `product_evidence` counts `near_miss_display_copy` separately from `verb differs` / `no intent`, never folded into repeats or unconsulted. |
| `testops/web/app.py` | `near_miss_sentence` has a display-copy sentence naming the word and quoting the copy; `product_block`'s refusal line reads `verb differs N / no intent N / display copy N`. |
| `tests/test_product_evidence.py` | Four new tests (AC1/AC2/AC3/AC6) and the KP product-record test rewritten (AC7). |
| `tests/test_skipped_is_not_consulted.py` | The stored-corpus test now pins `restfulbooker-levels-20261123T132456` instead of "the newest run": the copied store now also holds a later run whose `.java` **was** read (TESTOPS-72), and that run is not the subject of that criterion. Store-driven test selection, not a verdict. |

## Criterion by criterion

| id | what was done, and the evidence |
|----|--------------------------------|
| AC1 | `test_a_word_that_occurs_only_in_display_copy_is_not_a_candidate_shared_word`: `Visitor will get Booking Successful! message` against a six-surface corpus containing `GET /{id:[0-9]*}` *get message* → verdict `distinct`, state `zero`, `near_miss: true`, `near_miss_kind: "display_copy"`, route `GET /{id:[0-9]*}`, word `message`, `display_text: "Booking Successful! message"`. The contact sibling is pinned in the same test. |
| AC2 | The same test pins the defensible case on the **same corpus**: `New '<room_type>' … room '<room_name>' … will be created` → `repeats_product`, `POST /room`, word `room`, `display_copy: false`. `test_a_quoted_placeholder_is_a_slot_not_display_copy` pins that `'<room_name>'` is a slot and that an assertion whose only occurrence of `room` is inside the slot still repeats. Refusing everything cannot pass both. |
| AC3 | The reason reads, verbatim: *"the product declares GET /{id:[0-9]*}, whose own claim is "get message", and the only word the two share is "message", which appears only inside the assertion's display copy "Booking Successful! message" - text a person is shown rather than the subject of the check - so it is not counted as a repeat. Name the thing the assertion checks rather than the copy it is shown in, or check this one by hand"*. `test_the_refusal_names_the_word_and_the_copy_it_sits_in` asserts the word, the phrase and "display copy" in the record and in `app.near_miss_sentence`. |
| AC4 | Rebuilt offline from this worktree's own store: `scripts/replay_levels.py --snapshot restfulbooker-levels-20261124-fe8537db` (no network, no live store, no port 8791). **43 claims: 1 `repeats_product` (was 9), 12 near misses (8 display copy / 4 no intent / 0 verb differs), 26 unplaced, 12 distinct, 4 review.** The three strongest: **(1)** `POST /` from `room/src/…/RoomController.createRoom`, word `room`, surface claim *"create room"* — the repeat; **(2)** `GET /{id:[0-9]*}` from `message/src/…/MessageController.getMessage`, word `message`, surface claim *"get message"*, refused on display copy *"Booking Successful! message"*; **(3)** the same route and word, refused on display copy *"Thanks for getting in touch message"*. |
| AC5 | **One of the previous nine survives.** The room-creation claim is unchanged in verdict, route, word and surface claim. It is defensible: `room` is not quoted copy and not a slot value — it is the noun the assertion says is created, and the room service declares `POST /` whose own claim is "create room", so the browser run re-verifies the developer's act. The eight `message` claims are near misses: the word occurs only in the banner the visitor is shown, so the product's `get message` route is a different service's entity, and the old advice ("call `GET /{id}` and check the response") would have failed. Exactly 8 verdicts moved, all `repeats_product → distinct`; every other claim's verdict is identical. |
| AC6 | `test_quoted_copy_is_not_the_assertions_intent`: `Visitor sees the booking with "Booking created"` records `assertion_verb: "see"` and matches `GET /booking/{id}`; with only a `POST /booking` surface it is a near miss with `assertion_verb: "see"` and `verb_agrees: false`. The test also asserts that reading the sentence without the rule would yield `create` (the old fault), so the pin measures the difference. |
| AC7 | Decision: **KP claims in a browser run are assessed, not exempt.** `the page is served with the room list` is still `KP` (verdict `review`), and now records state `zero` with the product's surface count and reason instead of "the product is not evidence about it"; on the corpus the four KP claims record `no_intent` near misses naming `GET /` *get rooms* and `POST /login`. Where no browser ran, the record says *"…the run did not drive a browser, so no browser was spent and the product's routes are not evidence about it"*. Both pinned (`test_a_claim_the_product_is_not_evidence_about_says_so`, `test_a_kp_claim_with_no_browser_says_why_the_product_is_not_evidence`). A KP claim is never `repeats_product`: `review` (a browser spent on what the server's page settles) is the stronger, already-correct finding. |
| AC8 | Full suite **1248 passed, 2 skipped**; contracts **37 passed, 2 skipped**; **14 goldens byte-identical**; no golden file changed. |

## The corpus, before and after

| | before | after |
|---|---|---|
| `repeats_product` | 9 | **1** |
| near misses | 0 | **12** (display copy 8, no intent 4) |
| `distinct` | 4 | 12 |
| `review` | 4 | 4 |
| `unplaced` | 26 | 26 |

The four `no intent` near misses are the KP claims AC7 now assesses; they are not new repeats and
not new findings — they are the same `review` claims, with a recorded product answer where there
was silence.

## What this does not do

- **The banner detector is typographic.** The stored assertions write `Booking Successful! message`
  and `Thanks for getting in touch message` with no quote marks; the rule reads them as banners from
  the mid-sentence capital and the display verb in front of them. A banner written in lower case
  with no punctuation (`visitor will get booking successful message`) would still be read as a
  shared noun and counted. The ticket's premise that the word sits "inside quoted literals" is not
  what the corpus contains; this build names the shape the corpus actually has, and the limitation
  is stated rather than hidden.
- **A capitalised phrase after a display verb is treated as display copy**, so a claim such as
  `the page shows Booking Summary` cannot count `booking` as the shared subject. This direction only
  ever refuses a repeat; the true positive the ticket protects is pinned by name.
- **A near miss still raises no finding.** The eight are reachable on the run page
  ("What the product refused") and on their scenarios' case pages through the TESTOPS-78 read model,
  but they raise no case of their own, as before.
- **The stored run page is unchanged.** `data/testops.db` still holds the 11:46 run produced by
  v0.11 with its nine repeats; this worktree re-derived the claims for the report but did not
  overwrite the artefact. A new run is what puts the new counts on a page.
