# TESTOPS-90 review — a citation id is not a statistic, and a rejection gets one repair

2026-11-24, worktree `C:/Users/Chester/Projects/testops-t90`, branch
`factory/testops-90-citation-id`, commit `515354d`. Store touched only read-only (`file:...?mode=ro`);
port 8791 never touched. Probes run from the project `.venv` with `PYTHONPATH`/`VIRTUAL_ENV`/
`CONDA_PREFIX` stripped and `PYTHONNOUSERSITE=1`.

## Verdict

**Accept.** AC1, AC2, AC3, AC5 are done and pinned, and the mask survives every attack I threw at
it. AC4's numbers are real and honestly caveated. But the measurement is not a feature result: the
malformed seam (3 of 10 replies have no `citations` array at all) is stochastic — my live rerun
flipped one of the three failures to accepted and, separately, flipped the ticket's own flagship
case to rejected — so 70% is a per-case coin with known bias, not a property of the feature. The
repair round that this ticket built was the natural place to catch that seam and was not pointed at
it. Merge, and open the malformed ticket the same day; do not present 70% to a team as a working
accept rate.

## The mask, attacked

Verified live with a probe against `violations` on a record whose claim id is 2405:

- The ticket's exact sentence ("...claim:2405 is the claim whose record that gap concerns") with
  citation `claim:2405` is now accepted — no violations. Pinned in
  `test_a_citation_id_written_in_the_prose_is_not_a_statistic` (tests/test_agent_case.py:480).
- "the number 7" beside the same valid citation still yields `['the number 7, which no cited fact
  holds']`. Pinned at tests/test_agent_case.py:505.
- Attack 1 — a real fabricated statistic smuggled in behind the id token: "claim:2405 is the claim,
  and 99 of 100 requests fail" → **caught**: `['the number 99...', 'the number 100...']`. The mask
  removes only the identifier, not its neighbours (agent.py:701 masks `_CITATION_ID` alone before
  `_numbers_written`). Verdict: the mask does not open a fabrication door.
- Attack 2 — the id written to look like a statistic: "the claim 2405 proves 7 repeats of the same
  behaviour" → **caught, both numbers**. The mask is colon-anchored (`\b(?:claim|reason):\d+\b`,
  agent.py:492), so a colon-less "claim 2405" is read as a statistic and rejected; likewise
  "reason:2405 is why, and the suite ran 2405 times" → the trailing 2405 is caught. Verdict: no
  false accept anywhere. The one nuance is safe-side: a model that drops the colon is rejected with
  a message ("the number 2405") that misnames its mistake, but it is rejected, never served.

## Naming the route

AC2 quote, from `SYSTEM_PROMPT` (testops/judgement/agent.py:112-114), under the first absolute rule:
"Every sentence must cite at least one identifier from the record. ... The identifiers belong in the
"citations" array and nowhere else: never write one in the explanation's prose. If a sentence is
about the claim whose id is 12, the prose says "the claim" and the citations array says "claim:12" -
the prose never says "claim:12"." `PROMPT_VERSION` is `explain-a-case/3` (agent.py:82), pinned with
a proof that the version is part of the cache key (tests/test_agent_case.py:515).

The rendered paragraph for case ...T123451-05, agent=on, from the stored measurement:

    "The assertion states that a new room of a given type, accessibility, name, price and features
    will be created. The rule found that this repeats the product, because the product already
    publishes the same behaviour at the route and its own claim for that route is to create a room.
    The reason given is that the product declares that route with that claim, and it shares the word
    "room" with the assertion, a word that appears in 6 of the product's 25 surfaces. The proposed
    action is to assert this at the API by calling the route and checking the response, rather than
    reading it through a UI run, while a browser is still needed for what only a person sees. The
    record does not contain any further detail about the assertion beyond what is stated here."

Judgement: this is a real loss, and it is the prompt's own doing, not just model timidity. The rule
says identifiers belong nowhere but the citations array — and `route:POST /` *is* an identifier —
so the model complied literally and wrote "the route" five times while naming it zero times. A
reader told to "assert this at the API by calling the route" cannot act: which route? The check
would not have punished naming it — a cited route row allows the method and path in prose (only a
wrong verb is rejected) — so the prompt traded precision for compliance. The rule should have been
scoped to what the bug actually was: `claim:`/`reason:` ids never in prose; routes and files may be
named and must match the record. As written, the fix that stopped punishing the model for citing
also taught it to stop telling the reader where to go.

## Repair

AC3 verified twice: in the pins, and live.

- Pins: `test_one_rejection_is_repaired_once_and_the_good_repair_is_served` (two calls, the repair
  prompt contains the exact violation `the verb PATCH` and "Change only the sentences those
  violations name", ledger rows `[rejected, ok]`, explanation stored, view `fresh`) and
  `test_a_second_rejection_falls_back_to_the_honest_sentence_with_state_rejected` (exactly two
  calls — no loop — both rows `rejected`, nothing stored, view `rejected`). The loop is bounded by
  `REPAIR_ROUNDS = 1` (agent.py:573) and re-checks the repair from scratch, so it cannot buy a
  pass.
- Live: my rerun of ...T123451-05 produced a first reply with violations, fired the one repair
  round (`repairs=1`), and the repair **also** failed (`the number one, which no cited fact holds`)
  — two calls, 3891 tokens in / 588 out for zero output. That is the mechanism working exactly as
  designed, and also the honest cost of it: one bad case paid double and still served nothing.
- Ledger: both calls are separate rows with their own tokens and wall time; the view's `call_id`
  points at the call that closed it, so the record shows which round was served. The unlinked first
  attempt is counted in the variant total and the `/agent-report` paragraph now names it
  (testops/web/app.py:3272-3277). One arithmetic test was updated for it — that change is
  legitimate, not a fudge: the previously-unattributable call is now attributable by design.

## The measurement

What I could verify cheaply, I did:

- `tes90-measurement.json` matches the report: 7/10 accepted, mean 1471.4 in / 253.3 out, total
  wall 31,839 ms (3.18 s mean), model `deepseek-flash`. The three failures (-01, -03, -04 of
  T123451) have their raw replies stored, and each is well-formed JSON with an `explanation` and
  **no `citations` array** — the report's claim that these are `malformed`, not the citation-id bug
  and not a rejection, is backed by the raw data.
- The burst re-run is real: `tes90-measurement-run2-burst.json` shows 2/10 accepted, 8
  `failed_unavailable`; `run1` shows a third sample (7/10 with a *different* failure set — two
  malformed plus one `http_429`). The 8-second spacing requirement is therefore not a footnote; it
  is a hard operational constraint on the only measurement that produced the headline number.
- Live rerun of 3 cases (8 s spacing): ...T123451-03, malformed in the build's run, came back
  **fresh**; ...T123451-05, served in the build's run, came back **rejected after a failed repair**;
  ...T114627-01 fresh again. Three cases is not a rate, but it settles the character of the seam:
  the 30% loss is stochastic, per case, and can land on any case — including one that worked
  yesterday.

Judgement for a team audience tomorrow: 70% with a 10-case sample has a 95% binomial interval of
roughly 35%-93%, and the failure mode is not "the explanation was weak" but "the page silently
served no explanation at all." With an 8-second spacing requirement stacked on top, presenting this
as "the feature accepts 70% of cases" would overstate what is known. What is honest to say: "in ten
real calls the feature served 7 explanations, 3 calls produced nothing the guard would accept, and
the cause in all 3 was the same known seam (no citations array), which is stochastic and unfixed."
The build report says exactly that, which is to its credit — the number itself is just not a
feature claim.

## No weakening

- Full suite from the clean-environment venv: **1338 passed, 2 skipped** in 268.8 s — matches the
  build report. The seven targeted tests (AC1 ×3, AC2, AC3 ×2, byte-identical) pass in isolation
  too.
- The four TESTOPS-88 lies and the uncited sentence are still pinned and still reject (the mask
  probe confirmed the scan is untouched outside the identifier).
- `agent=off` byte-identity is pinned by `test_every_real_case_page_is_byte_identical_to_the_pre_
  change_build` and passed inside the suite; the only `app.py` change is inside the agent-report
  paragraph, not the page template.
- `testops/judgement/client.py` untouched, as claimed — no TESTOPS-89 conflict. `git diff --stat`
  against the parent shows exactly the files the report lists, plus two extra measurement artefacts
  (`tes90-measurement-run1.json`, `...-run2-burst.json`) that the report's Files table omits — a
  bookkeeping nit, and the burst evidence they carry is worth having in git.

## Three sharpest concerns

1. **The malformed seam is a defect this ticket should have fixed, not reported.** The ticket built
   a repair round whose entire purpose is "the model's reply was almost usable — ask once, with the
   exact faults quoted." A reply with an explanation but no `citations` array is precisely that
   case: it is 90% of an answer, it is the single remaining cause of "the feature serves nothing,"
   and it appeared in 3 of 10 real calls during the very measurement this ticket ran. Whether the
   fix is a stricter prompt demand, or classifying explanation-without-citations as repairable
   ("you wrote the explanation but omitted the citations array — add it for each sentence"), the
   machinery was in reach of the file this ticket already rewrote. Reporting it as "worth a ticket
   of its own" leaves the feature serving a blank page 3 times in 10 and calls the repair round
   done.
2. **The prompt over-corrected, and the cost is paid by the reader.** "Identifiers belong in the
   citations array and nowhere else" swept route names out of the prose along with claim ids. The
   -05 paragraph says "the route" five times and never says `POST /`; its proposed action cannot be
   acted on. The check never demanded this — a cited route may be named in prose — so this was a
   prompt-authoring choice, and it should be re-scoped to `claim:`/`reason:` ids only.
3. **The repair round is proven against fakes but behaves badly against the real model.** My live
   observation: repair fired, doubled the token spend (3891 in / 588 out), and still failed. The
   build's own sample never exercised a violation, so nothing is known about the repair's live
   yield — not whether it fixes more than it costs. Before quoting any cost model, measure the
   repair round live on a violating case; if it is a 2x-spend coin flip, the one-round design may
   still be right, but that should be a measured decision, not a default.
