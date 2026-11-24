# TESTOPS-88 build — the agent, and the honest way to tell whether it earns its cost

2026-11-24, branch `factory/testops-88-agent-ab`, worktree
`C:/Users/Chester/Projects/testops-t88`.

Suite, from the project `.venv` with `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX`
stripped and `PYTHONNOUSERSITE=1`: **1321 passed, 2 skipped** (239.9 s). The new file
`tests/test_agent_case.py` is 31 tests. No network is reached by any test: every model call in the
suite is a fake, and no test writes to the product's store.

## What the page shows with `?agent=on`

The verdict-bearing page is untouched. One block is added, after the claim and before the decision:

- heading `Explanation of this case` (deliberately **unnumbered** - numbering it would renumber the
  argument's own sections, which is a change to the page the agent is not allowed to make);
- a label naming the model that wrote it, e.g. `deepseek-flash`, and one sentence saying it is
  commentary, not evidence, and that the finding above is what the analysis decided;
- four to six sentences of plain English, written from the stored record only;
- when the explanation came from the store: "This is the explanation stored from an earlier view of
  this case, so showing it cost nothing."
- two plain links, `This helped` / `This did not`, each carrying `?view=<id>&vote=…`;
- links to the agent-off view of the same case and to `/agent-report`.

Everything the agent does is downstream of the claim. `agent=off` is the default, and every caller
written before this ticket gets it.

## AC1 is the gate, and it is proved over the real corpus

`tests/fixtures/agent/off-golden.json` holds a sha256 for **226 case pages and 49 run pages**, taken
from the real store (`data/testops.db`) rendered by the **unmodified** build at the branch point,
with the clock pinned at 2026-11-24T12:00Z so relative ages ("3 days ago") are stable and the
comparison measures the render rather than the day. `test_every_real_case_page_is_byte_identical_to_
the_pre_change_build` re-renders all 275 and compares: **0 mismatched, 0 of the 226 cases absent**.
A second test asserts that the default and an explicit `=off` agree, and that neither carries any
agent markup.

Zero is the number that matters here, and it is a number, not a claim: 226 + 49 digests compared.

## How a fabricated fact is caught (AC3)

`agent.violations(text, record)` reads four kinds of fact out of the reply and looks each up in the
record the prompt was built from:

| kind | pattern | example that is discarded |
|---|---|---|
| route | an absolute path fragment | `GET /api/orders` |
| file | a name with a source-file extension | `CheckoutController.cs` |
| count | any digit run | `3 copies` when the record says 1 |
| entity | CamelCase identifier | `CheckoutService` |

A short file name that suffixes a path the record holds (`login.feature` for
`cypress/e2e/…/login.feature`) is treated as an abbreviation, not an invention. Anything else is a
violation, the reply is **discarded before it is stored**, and the page renders the agent-off body
plus one sentence naming the invented fact: "The model-written explanation was rejected because it
named the route /api/orders, which is not in this case's record. Nothing it wrote was added to this
page." Pinned by `test_a_fabricated_route_is_discarded_and_the_page_falls_back` (asserting the
ledger row `outcome=rejected`, `cause='rejected: the route /api/orders'`, and that
`agent_explanation` stays empty) and by a unit test over all four kinds.

## The ledger

Three tables, additive in `schema.sql` (no version bump: no stored row is copied or rewritten, and an
older build ignores tables it does not know).

| table | row | fields |
|---|---|---|
| `agent_view` | one per page view, on and off | `case_id`, `variant`, `at`, `served` (`off` / `explanation` / `cached` / `rejected` / `error` / `not_configured` / `pending`), `detail`, `call_id` |
| `agent_call` | one per model call **or cache hit** | `case_id`, `variant`, `model`, `prompt_hash`, `tokens_in`, `tokens_out`, `cached`, `wall_ms`, `outcome`, `cause` |
| `agent_explanation` | the cache | `(case_id, prompt_hash, model)`, `text`, `created_at`, `tokens_in`, `tokens_out` |
| `agent_feedback` | one vote | `case_id`, `variant`, `verdict` (`helped` / `did_not_help`), `at`, `view_id`, unique per `(view_id, case, variant)` |

`/agent-report` prints, per variant: views, explanations shown, rejected, failed, calls, cache hits,
total tokens, mean tokens per explanation, helped / did not. Every figure is a count or a sum over
those rows. `null` mean prints as `—` and the page says no explanation has been written yet, because
a 0 there would read as a measurement.

Feedback is two `GET` links and nothing else: no script, no form, no cookie, no identity. The view id
is the session - one page counts one vote per variant, and a second click says "Already recorded". A
vote for a view that never served an explanation under that case is refused (400) rather than
counted.

The prompt hash covers the prompt version, both messages and the model, so a changed record or a
different model is a new key, never a stale hit. A second view costs nothing and says so.

## Failure is one sentence (AC7)

Unconfigured (no `TESTOPS_AGENT_TOKEN`, no managed identity, no `az`), unreachable, `http_429`,
any other non-200, empty reply, malformed reply (including a JSON-only reply), and a case with no
finding: each renders the agent-off page plus **one** sentence and is recorded with its cause. Six
parametrised tests assert `outcome=error` with the exact cause, that no explanation block appears,
that exactly one note paragraph is present, and that the page is byte-for-byte the off page plus
that sentence. The site starts and serves agent-off pages without a token - it does not fail to
start.

## Cost model (AC10)

The tool measures **tokens**, not money, and the report page prints no currency symbol. Cost per
explanation is, by definition:

    cost = tokens_in x price_in + tokens_out x price_out

where `tokens_in`/`tokens_out` are the provider's own `usage` figures, summed per variant by
`/agent-report`. One explanation is paid for **once per (case, prompt_hash, model)**: every later
view is a cache hit at zero tokens.

**No price is asserted here.** The price per token depends on the Foundry deployment, the model's
SKU and the customer's agreement, none of which this build reads or records. If a reader wants a
money figure, it must be entered from the provider's own price list - for Azure Foundry models that
is the Azure pricing page for the model deployed in `testops-resource`
(`https://azure.microsoft.com/en-us/pricing/details/`) - and any figure quoted in a later report is
an **assumption with that source and the date it was read**, not a fact this tool measured.

Worked example, with the two prices explicitly marked as **assumptions**:

    ASSUMPTION: price_in  = $0.14 per 1M input tokens   (unverified; enter from Azure's price list)
    ASSUMPTION: price_out = $0.28 per 1M output tokens  (unverified; enter from Azure's price list)
    a 1,050-token call (900 in + 150 out) -> $0.000126 + $0.000042 = $0.00017 per explanation

Both figures are placeholders whose only purpose is to show the arithmetic; they are not read from
the deployed model's rate card and must not be quoted as its price. The ledger holds what is real:
the token counts, the wall time and the cache hits.

## Criterion by criterion

| id | what was done, and the evidence |
|----|--------------------------------|
| AC1 | `case_response(conn, case_id, *, variant=off, view_id=None, agent_config=None, completer=None)`; `?agent=on` is the only value that turns it on (`_agent_variant`). Every view is a row in `agent_view` with its variant. Off is byte-identical for all 226 real cases and 49 run pages against digests captured from the pre-change build. |
| AC2 | One labelled block, placed after the claims and before the decision; `test_on_is_the_off_page_plus_one_labelled_block` strips exactly one block and asserts the remainder equals the off page byte for byte, and that the verdict text precedes the block. The prompt asserts the record is the whole world; `test_the_explanation_is_written_from_the_record_and_nothing_else` checks the assertion text, route, matched word, reason, path and line are all in the prompt, and `test_the_record_is_read_from_the_store_not_written_by_the_agent` checks the record is unchanged by a render. A case with dozens of findings quotes the first `PROMPT_FINDING_LIMIT` (6) and the prompt says the rest are not summarised; the check on the reply still reads the whole record, so a fact from a finding the prompt did not quote is not called a fabrication. |
| AC3 | `agent.violations` (four kinds) + discard-before-store; page falls back to the off body plus one sentence naming the fact. Pinned with a fake model returning a fabricated route. |
| AC4 | `agent_call` per call/hit, `agent_view` per view; `/agent-report` per variant. `test_the_report_arithmetic_is_the_ledger` checks views, served, cache hits, calls, total and mean tokens and the vote counts against the rows. |
| AC5 | `agent_explanation` keyed `(case, prompt_hash, model)`; the page says when it is showing a stored one. `test_a_second_view_is_served_from_the_store_and_says_so` proves the second view makes no model call, and `test_the_cache_key_is_case_prompt_hash_and_model` proves the model is in the key. |
| AC6 | Two links on the explanation, no JS, no form, no cookie; one vote per view; `/agent-report` counts per variant. Three tests, including the refusal of a vote for an off view. |
| AC7 | Six parametrised failure tests + unconfigured + no-finding, each the off page plus exactly one sentence and a cause in the ledger. |
| AC8 | `client.py` resolves `az` with `shutil.which` (no host path, asserted), takes a token from `TESTOPS_AGENT_TOKEN` → managed identity (IMDS, `Metadata: true`, optional `TESTOPS_AGENT_CLIENT_ID`) → `az`; never stores, prints or returns a token. Endpoint and model default to `testops-resource` and `deepseek-flash`, overridable by `TESTOPS_AGENT_PROJECT`/`TESTOPS_AGENT_ENDPOINT`/`TESTOPS_AGENT_MODEL`. `test_no_credential_reaches_the_page_or_the_ledger` renders with a token and asserts it appears in neither. |
| AC9 | Full suite **1321 passed, 2 skipped**; the analysis and contract suites unchanged; no test reaches the network. |
| AC10 | Above; the report page prints tokens and no currency, and this report marks every price as an assumption with its source. |

## Files changed

| file | change |
|---|---|
| `testops/judgement/agent.py` | new. Config, record assembly, prompt + hash, `violations`, cache, ledger, `report`/`recent_calls`. |
| `testops/judgement/client.py` | transport only: `shutil.which("az")`, token chain (env → IMDS → `az`), configurable endpoint/model, no module-level token. `complete` keeps its name and grows injectable `endpoint_url`/`access_token`. `extract_json` kept and documented as the retired prompt's helper. |
| `testops/judgement/prompts/level_fitness.md` | unchanged. It is the baseline judge's prompt; no code reads it now, and it stays as the record of the design that was replaced rather than deleted quietly. |
| `testops/store/schema.sql` | four additive tables (`agent_view`, `agent_call`, `agent_explanation`, `agent_feedback`) and three indexes; no version bump. |
| `testops/web/app.py` | `_agent_variant`, `_explanation_block`, `_agent_note`; `case_response` gains `variant`/`view_id`/`agent_config`/`completer` and closes the view with what the page carried; `agent_report`, `feedback_page`, `self_back`; `do_GET` gains `/agent-report`, `/case/<id>/feedback`, and the `agent` parameter. |
| `tests/test_agent_case.py` | new, 31 tests. |
| `tests/fixtures/agent/off-golden.json` | new, 226 case + 49 run page digests, captured from the pre-change build. |

## Amendment, 2026-11-24 - the review's block on AC3, and concern 1

This section supersedes "How a fabricated fact is caught (AC3)" above and the AC3/AC4 rows of the
criterion table. It answers `factory/reports/2026-11-24/TESTOPS-88-review.md`, section
**"Fabrication, both ways"** and **concern 1**. Everything else in this report still stands: the
review confirmed AC1 to the letter, the ledger arithmetic, the cache, the failure sentences and the
token path, and nothing else was reworked.

The reviewer reproduced four ordinary lies that the old four-regex deny-list let through: a wrong
verb on a real route (`PATCH /rooms` where the record says `GET /rooms`), a real filename with a
wrong line number when the digit is followed by a full stop (the old `_COUNT` lookahead refused to
match `99.`), a count written as a word ("four findings" where the record holds 6), and a confident
product claim citing nothing. The old check scanned prose for shapes, so a shape it did not
recognise, or a sentence with no shape at all, was invisible.

### The reply is now structured evidence, not prose to be scanned

The model answers with one JSON object:

```json
{"explanation": "sentence one. sentence two.",
 "citations": [{"sentence": 1, "facts": ["claim:12", "route:GET /rooms"]},
               {"sentence": 2, "facts": ["file:features/panel_api.feature:17"]}]}
```

The citation vocabulary is derived from the record (`agent.citation_index`) and printed in the
prompt under `CITATIONS`, one identifier per fact, so the model can only copy what it was given:

| citation | names | agreement the prose must keep |
|---|---|---|
| `claim:<claim id>` | a claim row | the claim's own fields |
| `route:<METHOD> <path>` | a product route as recorded | any HTTP verb in the sentence must equal the route's method |
| `file:<path>:<line>` | the assertion file and its recorded line | any line number must equal the recorded line |
| `count:<name>:<value>` | a count the record holds | any count of that noun must equal the value |
| `reason:<claim id>` | the near-miss reason on a claim | the reason's own text |

### The validation order (`agent.violations`)

1. **Existence.** Every citation must name a fact in the record; an unknown one rejects the reply
   and the page names the identifier (`the citation route:/api/orders`).
2. **Coverage.** Every sentence must carry at least one citation. A sentence with none rejects the
   reply, which is what catches a confident claim that cites nothing.
3. **Agreement.** What the sentence says must match the row it cites: the verb against the route's
   recorded method, a line number against the recorded line, a count against the recorded count, a
   file name against the cited path, a named class or service against the cited row's text.
4. **Numbers.** Every numeral and every number word in a sentence must be present in the rows that
   sentence cites. `four` is read as 4 before this test, so a count written as a word is caught in
   the same place a digit is.

Any violation discards the reply before it is stored (`outcome=rejected`, `agent_explanation` stays
empty) and the page renders the agent-off body plus one sentence: *"The model-written explanation
was rejected: the verb PATCH, where the record says GET /rooms. Nothing it wrote was added to this
page."* A reply that is not the agreed JSON is `malformed`, recorded with its cause, never guessed
at. `PROMPT_VERSION` is `explain-a-case/2`, so an old explanation cannot be served as this one.

**Pinned by tests** (`tests/test_agent_case.py`): all four of the review's lies, parametrised, each
with the assertion that the citation it uses (or fails to use) is one the record really offers -
`test_each_of_the_reviewers_four_lies_is_rejected`; the wrong verb end to end through the page
(`test_a_wrong_verb_on_a_real_route_reaches_the_page_and_is_rejected`); an unknown citation
(`test_a_citation_the_record_does_not_offer_is_rejected`); and the honest prose that must survive -
a re-quoted route, file and line, count and claim served both directly
(`test_honest_prose_that_requotes_the_record_survives`) and through the page
(`test_an_honest_reply_that_requotes_the_record_is_served`).

### The A/B no longer compares states with each other (concern 1)

Each view now records which state it was in: `fresh`, `cached`, `rejected`, `failed_unavailable`,
`failed_unconfigured` - plus `no_finding`, `off` and `pending`, so a page that asked for nothing and
a render that died are not folded into a failure. Rows written before this vocabulary are read as
what they meant (`explanation` -> `fresh`, `error` -> `failed_unavailable`, `not_configured` ->
`failed_unconfigured`) and never rewritten.

`agent.report` returns the variant totals *and* `states`, and every figure in a state is counted
through the view it belongs to: calls and tokens join on `agent_view.call_id`, votes join on
`agent_feedback.view_id`. So a cached page's tokens are zero and its vote is counted in the cached
state, a rejected reply's tokens appear as cost rather than disappearing, and a failed render is not
a loss. A call no view closed is counted in the variant total as `unlinked_calls` so the breakdown
and the total still agree. `/agent-report` prints the state table under the variant table, with
value and cost labelled.

**Pinned by** `test_the_report_separates_every_state_so_value_and_loss_are_not_confused` (one view
in each of the five states, one off view: views, tokens, cache hits and votes asserted per state,
and the totals asserted to be the sum of the states) and
`test_the_report_page_breaks_the_numbers_down_by_state`, plus the existing arithmetic test, extended
to assert the fresh and cached states.

### Nothing was weakened

- **AC1 still holds over the real corpus**: the golden test compares all **275** pages (226 case +
  49 run) and reports **0 mismatched**, **2 skipped** for the whole suite as before.
- Suite: **1332 passed, 2 skipped** (241.0 s) from the project `.venv` with `PYTHONPATH`,
  `PYTHONHOME`, `VIRTUAL_ENV`, `CONDA_PREFIX` stripped and `PYTHONNOUSERSITE=1`. The 11 new tests
  are all in `tests/test_agent_case.py` (42 there now).
- Contracts and analysis suites unchanged and green; the goldens listed in
  `tests/fixtures/agent/off-golden.json` are untouched.
- The agent-off page is not touched by any of this: the check, the state vocabulary and the report
  all sit downstream of it.

### Files changed by this amendment

| file | change |
|---|---|
| `testops/judgement/agent.py` | `citation_index`, `Reply`/`parse_reply`, rewritten `violations` (four ordered questions), `parse_reply` in `explain_case`, state vocabulary, `report` per state with `unlinked_calls`. |
| `testops/web/app.py` | `/agent-report` gains the per-state table and the unlinked-call line; `feedback_page` accepts the canonical states. |
| `testops/store/schema.sql` | comment only: `agent_view.served` names the new states. No structural change. |
| `tests/test_agent_case.py` | 42 tests: the four lies, the honest prose, per-state report arithmetic and the page. |

## What this does not do

- The agent runs only at render time, only when asked. It never runs during analysis.
- Both price figures in the worked example are placeholders. Before any money claim reaches a
  reader, the rate card for the deployed model must be read and quoted with its date.
- `agent=on` is not linked from the off page (AC1 forbids changing it), so the way in is the query
  string a reader is given, or the `/agent-report` link on an explanation block.