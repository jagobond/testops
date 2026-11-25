# TESTOPS-93 build — the narrator as a Foundry agent, and the page says which route served it

2026-11-24 · `factory/testops-93-foundry-agent` · builder

## Verdict

Green. `tests/test_agent_foundry.py` and `tests/test_verdict_vocabulary.py`: 25 passed, 1 skipped.
Full suite, from the project `.venv` with `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV` and
`CONDA_PREFIX` stripped and `PYTHONNOUSERSITE=1`:

    env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
      C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q
    1409 passed, 3 skipped

That is `1412 tests collected`, with no failures and no errors. The Lead's run of the same tree
before this follow-up was `1402 passed, 3 skipped, 7 failed, 1 error`; the error was the repository
write guard's teardown, not a product test, and it is gone in a run with no commit landing
mid-flight.

## What changed

`testops/judgement/client.py`

- `agent_responses_url(endpoint_url, agent)`: the request URL is built, not assumed. A configured
  endpoint that carries a path is used verbatim (a gateway's own surface); an endpoint with no path
  — an origin, as the stub server and a project root are — has the agent's own surface appended:
  `/agents/{name}/endpoint/protocols/openai/responses?api-version=v1`.
- `complete_agent` posts to that URL. The body is still the one `input` string holding
  `{system, user}`, the header is still `api-key` from `TESTOPS_AGENT_TOKEN` only, and the reply is
  still read as `output[].content[].text` of type `output_text` with the trailing `USAGE` line.

`testops/judgement/agent.py`

- `failure_cause`: a `URLError` is `unreachable`; a bare `TimeoutError` raised while the response is
  being read is `timeout`. `HTTPError` stays `non_200` and is checked first.
- `Outcome.sentence`: for the foundry route, `not_configured` returns the configuration's own
  detail, so the page names the missing setting (the credential, or the endpoint) instead of the
  generic "nothing was added" sentence.
- `_explain_case`: the foundry route never reads the stored-explanation cache. The model route's
  cache is untouched; the agent route asks the agent on every foundry view, because the ledger's
  whole job here is to price the calls the agent actually served with its own `USAGE` counts.

`testops/web/app.py`

- `case_response`: when the foundry variant is rendered by a caller that did not open a view, the
  page opens one and closes it with what it carried. The `agent=on` path is untouched.

## The seven failures and their causes

1. `test_foundry_renders_the_same_block_and_names_its_route` — the page was right and the ledger was
   not: `case_response(..., variant=foundry)` with no `view_id` recorded a call but no `agent_view`
   row, so "the ledger records the route per explanation" had nothing to point at. The foundry
   variant now opens its own view when the caller did not, and closes it with `fresh`.
2. `test_the_agent_route_sends_the_ticket_shape_to_the_agent_endpoint` — the stub recorded the
   request at path `/`: the client posted to the configured endpoint verbatim, so an endpoint given
   as an origin never reached the agent's responses surface. Fixed by `agent_responses_url` above;
   the body, the api-key header and the inner `{system, user}` shape were already correct.
3. `test_every_agent_failure_is_a_kind_in_the_ledger...[unreachable]` — a refused connect to
   `127.0.0.1:1` with a 0.3s deadline surfaces on Windows as `URLError(reason=TimeoutError)`, and
   the classifier called it `timeout`. It is unreachable: nothing answered. The classification now
   keys on whether an answer arrived at all, which is the distinction AC3 asks the report to make.
4. `test_the_report_shows_the_routes_side_by_side...` — the second foundry view of the same case was
   served from the model route's cache, so it made no call and recorded no failure kind, and the
   report had no `non_200` to print. Fixed by taking the foundry route off that cache; both views
   now make a real call and the 502 is counted by its kind.
5. `test_no_fallback_unless_asked_and_the_fallback_is_said_out_loud` — two defects.
   (a) The test asked the stripped text for `agent-text`, which is a class name and is stripped with
   the rest of the markup; the block was present. The assertion now checks the raw bytes for
   `<div class="agent-text">`, the same marker the rest of this suite uses — a byte check rather
   than a prose check.
   (b) The expected route list was one short: both renders ask the agent, and the fallback view's
   failed agent call is in the ledger beside the model call that answered. The list now expects all
   three rows, so the test fails if a failed attempt is silently dropped.
6. `test_an_unconfigured_agent_route_says_so_and_never_calls_out` — the foundry outcome for "no
   credential" had no sentence of its own in `REFUSALS_FOUNDRY` (its cause is `not_configured`,
   which only the model route documented), so the page said the generic sentence and never named
   `TESTOPS_AGENT_TOKEN`. Fixed by returning the configuration's own detail; nothing is called, and
   the ledger still holds no call.
7. `test_the_comparison_reports_both_directions` (ERROR) — not a product defect. It passes alone and
   it passes in the clean full run. In the Lead's run and in my first full run the error was the
   repository write guard's teardown: a commit landed while the suite was running, so the guard
   could not attribute tracked files the run had not written. Nothing in the verdict vocabulary was
   touched by this ticket.

## Ledger and report

The ledger (`agent_call`) now holds, per view: the route that was asked (`model` / `foundry`), the
agent's own `USAGE` token counts rather than an estimate, its wall time, the outcome, and the
failure's kind — `unreachable`, `timeout`, `non_200`, `missing_text`, `malformed_reply` or
`rejected`. `/agent-report`'s "The routes, side by side" table is built from those rows, with votes
and failures counted by kind per route, so the cost of each route can be answered from the store.

A rejected reply is still never re-asked of the other route, and a transport failure falls back to
the model route only under `TESTOPS_AGENT_FALLBACK=model`; both attempts stay in the ledger and the
page names the route that failed as well as the one that answered.

## No weakening

- No credential test was touched. `TESTOPS_AGENT_TOKEN` remains the only source of the agent's
  api-key, and the substring test still scans the case page, `/agent-check`, `/agent-report` and the
  ledger.
- The 275-page byte-identical golden for `agent=off` and no parameter is untouched and passes.
- The ticket's acceptance assertions are unchanged except in two places, both of them stricter:
  `<div class="agent-text">` is now checked in raw bytes instead of the stripped text (the marker is
  markup; the old form could not pass and did not mean what it said it meant), and the fallback
  route list now demands three ledger rows instead of two, so a dropped failed attempt fails the
  test rather than passing it.
- No other test file, fixture or golden digest was modified.

## Residuals

- The migration widens `agent_view.variant` and `agent_flag.variant` by rebuilding both tables row
  for row (SQLite cannot alter a CHECK). Ids and values are preserved; no history is rewritten.
- `TESTOPS_AGENT_ROUTE_ENDPOINT` accepts either the agent's responses URL or an origin, which are
  two meanings in one variable. The client's rule (a path means "use it verbatim") is documented in
  `agent_responses_url`; if a gateway ever needs a bare path prefix, it will want its own variable.
- The live smoke test remains opt-in: it skips without `TESTOPS_AGENT_TOKEN` and
  `TESTOPS_AGENT_LIVE_SMOKE`, so CI never calls the deployed agent.
- Two builders worked this worktree at once today; commit `97a5546` carries both sets of edits. The
  tree is clean and the counts above are from a run with no concurrent writes.
