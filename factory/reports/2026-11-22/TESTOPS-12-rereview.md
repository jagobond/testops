# TESTOPS-12 re-review (after TESTOPS-18 fixes)

Corpus: run `cotw-levels-20261122T011316` (analyser level_fitness), 94 claims, 41 scenarios, 6 features, 47 surfaces. Suite: 198 passed, 16.4s, from the project `.venv` with PYTHONPATH and VIRTUAL_ENV stripped and PYTHONNOUSERSITE=1. Verdict counts in the run: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review — confirmed.

## Verdict — PASS

Both NEEDS-FIX findings are fixed exactly as specified, the tests catch both defects when I reintroduce them, and the corpus prose is the best this feature has produced.

## Your two findings

### 1. The multi-label pass note

Fixed. The note is now built from the interaction codes, not the labels. For the real two-label scenario in the run ("The audit counts what rests on a batch decision") the note reads:

> "This scenario carries 2 answers to one run: "settled by the response the server sends" for 1 assertion and "unclear what would settle it" for 1 assertion. The run is one: one is about a guarantee on the data as stored and one names nothing that could settle it, so the answers differ in what the assertions ask, not in which instrument read them."

That is grammatical English, no label interpolation, no doubled preposition. The no-code fallback withholds the explanation rather than guessing, which is the right failure mode. Fixed as specified.

### 2. The I1-over-api overclaim

Fixed, and it landed at the strength I asked for, not weaker. The statement now reads:

> "The run only reads the responses the server sends, and takes that answer as the report of what is stored, so the assertion is checked as far as that answer speaks for the store."

That is the exact wording I proposed: the answer is *taken as* the report of what is stored, and the sentence marks where that reading stops. It does not assert the response is the store. The KP sentence applies the same discipline ("as far as that answer speaks for the page") and the I2 sentence correctly keeps the stronger claim the response is the thing asked about. Not weaker than what I asked for.

## Can the defects come back?

I reintroduced both. Both caught.

1. I1 overclaim: I reinstated "that answer says what is stored" in `testops/analysers/level_fitness.py`. Two tests in `tests/test_level_fitness.py` fail — one asserts the inference phrase is present and the stop clause is present, one sweeps every claim in the corpus against a `STORE_AUTHORITY` regex (`says what is stored`, `the response is what is stored`). The corpus-wide sweep is the strong fence: a reworded regression anywhere in the corpus fails, not just at the exact spot.

2. Label interpolation: I replaced the `_asks(counts, codes)` call with the old label-interpolating fallback in `testops/queries.py`. Three tests in `tests/test_pass_labels.py` fail — the two-label and three-label cases assert the rendered clause text, and the leak test asserts the corpus contains no label-as-object anywhere. The three-label test also counts `one is about`/`one names` clauses, so a reworded fallback that still leaks fails the count as well as the substring.

One honest caveat: the tests pin the *exact* phrases ("takes that answer as the report of what is stored", "as far as that answer speaks for the store"). A legitimate paraphrase of the same meaning would fail the presence assertion. That is stricter than the ticket's "or wording of equivalent meaning", but it is a fence in the right direction — it makes the regression harder, not easier — and the corpus-wide regex covers the class of defect rather than one phrase. I would not loosen it.

## The prose

1. (I1, distinct) "The assertion is about the data as stored: each fact on the sheet is admitted through the admission gate. The run only reads the responses the server sends, and takes that answer as the report of what is stored, so the assertion is checked as far as that answer speaks for the store." — Names the inference, marks where it stops. This is the sentence the ticket existed to produce.

2. (I2, distinct) "The assertion is about the response itself: there is one sheet per entity. The run only reads the responses the server sends, which is exactly the answer the assertion asks about, so the assertion is checked." — Correctly stronger than I1: here the response is the thing asked about, and the sentence says so without borrowing the store's authority.

3. (KP, distinct) "The assertion is about the page as served: the sheet for "Keegan" shows every proposed fact for "Keegan". The run only reads the responses the server sends, and takes that answer as the page the server sends, so the assertion is checked as far as that answer speaks for the page." — Parallel to I1, correctly bounded. The parallelism is a strength: a reader can see the three kinds diverge at exactly the same clause.

4. (I4, gap) "The assertion is about what only a browser works out: each fact's citation is in an element reachable by an accessible name. Nothing short of a browser can decide it, and the run only reads the responses the server sends instead, so nothing checks it." — Blunt and honest about the gap. No hedging, no softening.

5. (U, unplaced) "The step reads "that count is correct for the store it was run against". Those words judge something right without saying what it is compared with, so nothing can be said about whether it is checked." — The unplaced verdict is explained by what the assertion fails to say, not by a missing label.

6. (KP, review) "The assertion is about the page as served: every rendered fact sits in an element carrying a data-fact-id. The page the server sends settles it, yet the run drives a browser, so it pays for a browser that decides nothing extra." — The review verdict is justified by a cost argument, not a complaint. This is the kind of sentence that makes the report worth reading.

## Three sharpest concerns

1. The tests pin exact phrases where the ticket allows equivalent wording. A future legitimate rewording of the I1 sentence will fail the presence assertion and look like a regression. The corpus-wide regex is the real fence; the exact-phrase assertion is belt-and-braces that will cost a future ticket to relax.

2. The `_ASKS` table is keyed by interaction code. A new code added without a `_ASKS` entry silently falls back to withholding the explanation — correct behaviour, but nothing warns the developer that their new code is invisible in the pass note. A test that enumerates codes against `_ASKS` keys would close that.

3. The store run I read from (`cotw-levels-20261122T011316`) was produced during this re-review, not by the builder's own run. The counts match the builder's snapshot, but the prose evidence here is from my run, not theirs. If the builder's snapshot differs in any wording, this report would not see it — worth a one-line note on the ticket that the re-review corpus is a fresh run, not a re-read of theirs.
