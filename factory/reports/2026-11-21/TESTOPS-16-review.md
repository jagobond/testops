# TESTOPS-16 review — Empty evidence, two meanings

Reviewed 2026-11-21, branch `factory/testops-16-two-nothings`, diff `feature/f1..HEAD`.
Suite: `env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 .venv/Scripts/python.exe -m pytest -q` → **140 passed in 12.47s**.

## Verdict — PASS

All five criteria hold: the three empties are now three distinct, truthful sentences; the tests build real stores; no verdict or schema moved.

## Criteria

| id | judgement |
|----|-----------|
| AC1 | HOLDS — a zero-observation run renders "This run recorded no observations; it predates observation recording...", checked from a real store (`test_a_run_that_recorded_no_observations_says_so`, and the artefacts-without-observations variant that proves a snapshot alone is not evidence). |
| AC2 | HOLDS — state (b) renders "Nothing in this run bears on this claim... The run recorded N observations in total; none of them is at these coordinates." Singular/plural handled (`1 observation`, not `1 observations`). The count is computed over the claim's own run's snapshot (`observations_in_snapshot`, `testops/queries.py:101`), which is the right scope — another run's looking says nothing about this one. |
| AC3 | HOLDS — v1 keeps its own wording ("Evidence for this claim was not recorded: it was recorded before provenance was captured..."). Note: the v1 sentence on `feature/f1` was exactly "Evidence for this claim was not recorded."; the new text is that sentence extended with provenance reasoning, not a verbatim keep. I judge this an improvement and within the criterion's intent (the three states never share wording — verified by the cross-product assertion), but a strict reading of "keeps its existing text" fails; flagging for the Lead's awareness. |
| AC4 | HOLDS — `tests/test_empty_evidence_states.py` builds genuine snapshots, runs, artefacts, observations, cases and findings through `db.*` on real SQLite files in `tmp_path` and renders through `app.case_page`. No mocking anywhere; the docstring even states why (a mocked dict asserts the sentence, not the fact). |
| AC5 | HOLDS — `claim_view` and the verdict path are untouched; `test_the_verdict_is_unchanged_and_the_schema_is_untouched` asserts `verdict == "gap"`, that `observations_recorded` is not a `claim` column, and that `schema_meta` is intact. The diff touches only wording in `section_does` plus the read-model fields. |

## The three sentences

Read aloud, sceptically:

1. **(a)** "This run recorded no observations; it predates observation recording. Nobody was looking when this claim was made, so the source link above is the only evidence there is — and the emptiness here is not a sign the claim is clean."
   Truthful and at-a-glance distinct. The last clause is the best part: it pre-empts the reader's lazy inference "empty evidence = clean". One nit: "it predates observation recording" asserts *why* the run recorded nothing, which a zero count cannot strictly prove (a run could postdate recording and still record nothing) — the artefacts-without-observations test covers that store shape and renders (a)'s sentence anyway, so the *why* is an attribution, not a fact. Acceptable; a tester could quibble.

2. **(b)** "Nothing in this run bears on this claim, so the source link above is the only evidence there is. The run recorded 3 observations in total; none of them is at these coordinates."
   Exactly right: the count is the reader's instrument for judging the emptiness, and "none of them is at these coordinates" says *where* the emptiness lives. Clean pass.

3. **(c)** "Evidence for this claim was not recorded: it was recorded before provenance was captured, so there is no run to look in and no coordinates to look at."
   Correct in kind — it declines to invent a run ("saying 'this run recorded none' would invent a run that never existed" is the comment's own rule, and the code honours it). The colon construction is slightly breathless aloud, but every claim it makes is checkable against the store, and none is checkable in the other two. Distinct.

## Three sharpest concerns

1. **State (b) does not exist in the shipped corpus.** I queried `data/testops.db`: of 282 v2 claims, 188 have support and 94 are empty on zero-observation runs — zero claims in state (b). I reached (b) in the UI only by building a store myself (probe through `app.case_page`; the sentence with count rendered correctly) and the tests do the same. So the only thing a reader of the corpus can actually see is state (a) and (c); (b) is a state the product can say but nobody has yet seen it say. Not a defect in this ticket — but the corpus should eventually produce a (b).
2. **The (a) "why" is inferred from a count.** "It predates observation recording" is a claim about history, derived from `observations_recorded == 0`. A run that postdates recording but failed to write observations would be misdescribed. A snapshot-level `records_observations` flag would remove the inference; that would be a schema change, so it is out of scope here — but it is the crack the next ticket should look at.
3. **AC3's letter vs its spirit.** The v1 sentence was rewritten, not kept. It now says strictly more and shares no words with the others, so the criterion's real test (never share wording) passes — but "keeps its existing ... text" is not literally satisfied, and the Lead should know the ticket was read as "keeps its distinct meaning".

## Demo

**The problem.** `None` and `[]` collapsed into one page sentence, so "nobody was looking" and "we looked and none of it was here" were indistinguishable — different trusts rendered as the same words.

**What changed.** `queries.py` gained `_attach_evidence`, which attaches the evidence list and the observation count of the claim's own run *together*, because they only mean something as a pair; `app.section_does` now picks among three sentences — (a) zero observations, (b) positive count with none at the coordinates, (c) v1 with no run to look in. A fourth guard covers the rare "cannot say" (count is None) without stating a count.

**How we know it works.** 140 tests pass. The six new tests build real SQLite stores and render real pages. I additionally built an independent store by hand and asked the UI for state (b): the page answered "Nothing in this run bears on this claim, so the source link above is the only evidence there is. The run recorded 2 observations in total; none of them is at these coordinates." — with neither of the other sentences anywhere on the page.

**What it does not solve.** State (b) is unreachable from the current corpus (0 of 282 v2 claims); the (a) attribution "predates observation recording" is still inferred from a count; v1 wording was extended, not verbatim kept.

**Where to look.** `testops/queries.py:91` (`_attach_evidence`, `observations_in_snapshot`), `testops/web/app.py:290-316` (the three sentences), `tests/test_empty_evidence_states.py` (all six tests).
