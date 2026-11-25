# TESTOPS-88 review, round 2 — the citation scheme, and what honesty costs

2026-11-24, worktree `C:/Users/<name>/Projects/testops-t88`, amendment `8916a14`, branch
`factory/testops-88-agent-ab`. Everything below was reproduced in this worktree only; the live
store and port 8791 were never touched. The only file I wrote is this one. The real store
(`data/testops.db`) was opened read-only (`mode=ro`) for every render and probe; the state
accounting probes ran against a throwaway store in a temp directory.

## Verdict

**Accept.** All four of round 1's lies are now rejected, each with a sentence that names the
disagreement; the A/B ledger counts what each view actually was; AC1 is unchanged and independently
reproduced (275 of 275 byte-identical); the suite is green from the clean environment (1332 passed,
2 skipped in 245 s — the build's own number). The two new lies I aimed at the citation scheme's
seams both land, but they land in the irreducible remainder of citation-based checking, not in a
regression of anything the amendment promised: the check verifies *form* (the citation exists, the
sentence carries one, structured facts agree with their row), and it cannot verify that a
shapeless sentence is true of the row it cites. That is the honest boundary of this design, and the
ticket's amendment says so. The cost side is real and is my first concern below, but it is a
quality cost the A/B can measure, not a gate that fails to hold. Return nothing to the builder.

## The four lies, re-run

Each was run through `agent.violations` as a parsed `Reply` whose citations are ones the record
really offers (asserted against `agent.citation_index` before each run), against the review's
record shape: `GET /rooms`, `features/panel_api.feature:17`, counts findings 6 / claims 6 /
sources 2.

1. **Wrong verb on a real route.** "The product declares PATCH /rooms, …", citing
   `route:GET /rooms`. → `['the verb PATCH, where the record says GET /rooms']`. *Rejected.*
2. **Wrong line before a full stop.** "The assertion lives in features/panel_api.feature,
   line 99.", citing `file:features/panel_api.feature:17`. → `['the line 99, where the record
   says 17']`. The full stop no longer saves the lie: the line check reads the sentence, not a
   lookahead-gated digit. *Rejected.*
3. **"Four findings" against 6.** Citing `count:findings:6`. → `['the number four, where the
   record says 6 findings']`. The word is read as 4 and held against the cited row. *Rejected.*
4. **The uncited product claim.** "The product validates the token before the handler runs.",
   citing nothing. → `['the sentence 1, which cites nothing']`. Coverage catches it. *Rejected.*

Each rejection sentence names the model's own word against the record's, and the end-to-end tests
pin the page rendering it (`test_a_wrong_verb_on_a_real_route_reaches_the_page_and_is_rejected`).

## Two new lies

Both aimed at the gap the amendment does not claim to close: whether a citation actually supports
what the sentence says.

1. **A real claim id carrying behaviour the claim does not state.** "This repeats POST /room,
   which validates the token", citing `claim:1`. This *exact* sentence is rejected — but not by
   the citation scheme: `POST /room` is a route shape the claim's row does not name, so it falls to
   the route lookup (`['the route /room, which no cited fact names']`). Strip the route shape and
   the lie survives: "This repeats the existing check, which validates the token before the handler
   runs", citing `claim:1`, → `[]` on the synthetic record *and* on a real record from the store
   (case `case-demo-product-levels-20261120T194425`, citing `claim:19`). **Survives.** A claim citation is
   a pointer, not a proof; anything the check cannot recognise as a shape rides in behind a real id.
2. **A real route with a meaning-changing qualifier.** "The product already deletes the room, so
   this test only checks the response", citing `route:GET /rooms`. → `[]`. **Survives.** Lowercase
   "deletes" is not `DELETE`, the sentence holds no route path, and no rule reads what "already"
   does to the meaning. Even "The product already DELETEs the room, …" survives — `_METHOD` finds
   the verb, but the sentence names no path, and the verb is only checked when a path is present.

So both survive in their honest forms. The check now holds every lie that has structure, and no
lie that does not. That is the design working as amended, not failing — but it means AC3 protects
against fabrication of *facts with identifiers*, and against nothing else.

## What honesty costs

The cost of this design is that a sentence with no citation is discarded, whatever it says. I wrote
the four sentences a good technical writer would actually produce about a real case, and ran them
through `agent.violations` twice — once uncited (how prose is written before the citation game),
once citing a real claim id — both on the synthetic record and on a real store record:

- **Opinion:** "This test is written at the wrong level for what it is trying to learn."
- **Recommendation:** "Move this assertion to the API suite, where it can run without a browser."
- **Causal:** "Because the run drives a browser, a small change to the page layout breaks the test."
- **Summary:** "In short, the test is slower and more fragile than the behaviour it guards."

**Uncited: 4 of 4 rejected** (`the sentence 1, which cites nothing`). **Cited: 4 of 4 accepted** —
on the real record too. Nothing in the checker compares the sentence to what the cited claim says;
the citation is a tollbooth, not a witness. So the answer to "does an opinion have to cite a fact
to survive?" is yes by construction, and the citation is not verified to support the opinion.

Judged honestly, this makes the feature *not useless but strange*: the honest writer's prose is not
thrown away by the product — it is thrown away by the model if the model fails to decorate each
sentence with an identifier, and it sails through if the model decorates mechanically. The real
tax lands twice: on models that under-cite (the whole reply dies for one uncited sentence), and on
honest numbers — "move this assertion to the API suite, where 30 similar assertions already run in
seconds" is rejected even while citing a real claim, because 30 is in no row
(`['the number 30, which no cited fact holds']`). The prompt forbids exactly that, so a compliant
model loses little; but the gate enforces citation discipline, not truthfulness, and the A/B's
value figure will include explanations whose every sentence was licensed by a citation that was
never checked for agreement. That is measurable in the A/B and should be watched, not blocked.

## States

Confirmed from the ledger arithmetic (`agent.report`, per-state SQL joining calls through
`agent_view.call_id` and votes through `agent_feedback.view_id`), with a fake completer against a
temp store, one fresh view, one cached view, one off view:

- **A cached view is never counted as an explanation written.** `explanations_written` counts only
  fresh `ok` calls: fresh 1, cached 0. Cached tokens are 0 and its cache hit is counted
  (`cache_hits=1`). Two caveats stated plainly: the report marks the cached state
  `value=True` and includes it in `explanation_views` (2 for fresh+cached) — defensible under the
  build's own definition ("an explanation a reader saw") but a reader summing "value" counts a
  page that cost nothing the same as one that cost 180 tokens; the token columns are what keep
  that honest.
- **A failed render is never counted as a loss of explanation.** `failed_unavailable` and
  `failed_unconfigured` carry `value=False` and zero votes; `failed_unconfigured` records zero
  calls. `failed_unavailable` is marked `cost=True` — that is the build's word for money spent, not
  value lost, and with an unreachable model its token figure is 0.
- **The five states are separated.** `report()` returns `states` keyed by all of fresh, cached,
  rejected, failed_unavailable, failed_unconfigured (plus no_finding, off, pending), each with
  views/calls/tokens/cache hits/votes/value/cost, and `unlinked_calls` keeps the variant total
  equal to the whole ledger. Pinned by
  `test_the_report_separates_every_state_so_value_and_loss_are_not_confused`, which I re-ran green.

**Vote attacks, all refused or correctly attributed:**

- **Vote on a cached view:** accepted (`200`, "Recorded"), and the report counts it in the cached
  state — cached `helped=1`, fresh `helped=0`. That is the right state: it is a vote about the page
  the reader actually saw.
- **Vote twice on the same view:** the second returns `200` "Already recorded",
  `agent_feedback` still holds exactly one row.
- **Vote for a view id from another case:** `400`, "did not show an explanation of this case" —
  `feedback_page` checks `row["case_id"] != case_id` before recording, and no row was written.
- **Vote on an off view:** `400`, no row written.

## No weakening

- **AC1 unchanged, independently reproduced.** I re-hashed every golden page myself (own script,
  read-only store, clock pinned at 2026-11-24T12:00Z): **275 of 275 byte-identical** (226 case +
  49 run), 0 absent, 0 mismatched, against `tests/fixtures/agent/off-golden.json`.
- **Suite:** **1332 passed, 2 skipped in 245 s** from `C:/Users/<name>/Projects/testops/.venv`
  with `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV`, `CONDA_PREFIX` stripped and
  `PYTHONNOUSERSITE=1`. The contracts suite (`tests/contracts/`) is inside that number; the
  42 `tests/test_agent_case.py` tests are all green, including the four-lies parametrisation, the
  honest-prose survival, the unknown-citation rejection, the end-to-end verb rejection and both
  per-state report tests.
- The agent-off path is untouched by the amendment: the check, the state vocabulary and the report
  all sit downstream of the off render, which the 275 digests prove byte for byte.

## Three sharpest concerns

1. **Over-refusal is the design's standing cost, and its true shape is worse than "honest prose is
   thrown away": the citation requirement taxes honesty while buying less than it appears to.**
   Every uncited sentence is discarded — 4 of 4 of a good writer's natural sentences died uncited,
   and a sentence with an honest number the cited rows do not hold dies even when it cites — yet a
   sentence that cites a real id passes *regardless of whether the id supports it*: the shapeless
   product-behaviour lie and the meaning-changing route qualifier both survive on real records. So
   the gate's guaranteed yield is citation discipline, not truth, and its guaranteed cost is that
   the explanation's quality now depends on the model playing a formatting game under prompt
   pressure. The A/B should track the rejected-state rate per model explicitly; a model that
   under-cites will look "safe" while delivering nothing.
2. **The value/cost vocabulary blurs two things the state table otherwise separates.** The cached
   state is marked `value=True` and folded into `explanation_views` beside fresh, so the headline
   "explanation views" counts pages that cost nothing the same as pages that cost a call; and
   `failed_unavailable` is marked `cost=True` even when its token figure is 0 (unreachable), while
   the paid-for-rejected tokens are correctly visible in the rejected state. The arithmetic is
   honest everywhere; the labels invite a reader of `/agent-report` to over-count value. One
   sentence of labelling on the page ("cached: served from the store, zero tokens") would close it.
3. **The semantic remainder is now the whole attack surface, and it is unmeasured.** Both new lies
   survive by having no structure, and the injection finding from round 1 stands unchanged: text
   inside the record is still trusted absolutely, and a claim citation launders any prose. Nothing
   in the ledger or the report can show how often explanations assert things their citations do
   not state — that failure mode is invisible by construction. If the A/B is meant to measure
   whether the agent helps, it currently measures whether the agent formats; whether it *tells the
   truth* is known only by reading the explanations, and nothing surfaces a sample for reading.
