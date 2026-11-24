# TESTOPS-93 build — the narrator runs as a hosted Foundry agent

2026-11-24, worktree `C:/Users/Chester/Projects/testops-t93`, branch
`factory/testops-93-foundry-agent`.

## What the third variant is

`?agent=foundry` is a third variant beside `off` and `on`, not a sub-flag of `on`, because the
route is the experiment: the two explanations come from different places and the report must be
able to weigh a view of one against a view of the other. It renders the same case page and the
same explanation block as `?agent=on`, and adds one line naming the route that answered:

    served by: foundry-hosted-agent

The model route's block is untouched: neither the route line nor the substitution sentence is
emitted unless a foundry view or an explicitly-allowed fallback produced it.

## The route

`client.complete_agent` posts to

    POST {endpoint}/agents/testops-narrator/endpoint/protocols/openai/responses?api-version=v1
    header: api-key: <TESTOPS_AGENT_TOKEN>
    body:   {"input": json.dumps({"system": ..., "user": ...})}

The endpoint defaults to the project's hosted-agent surface and is overridable
(`TESTOPS_AGENT_ENDPOINT`, `TESTOPS_AGENT_NAME`). The reply is read from
`output[].content[].text` where `type` is `output_text`; the final `USAGE {...}` line is split off
and its `prompt_tokens` / `completion_tokens` are used as the ledger's counts — the agent's own
numbers, never an estimate. A reply without a readable text or USAGE line is a named failure
(`missing_text`, `malformed_reply`), not a zero.

The model route in `client.py` is unchanged; the agent route is added beside it.

## AC1 — same block, labelled, route named

`?agent=foundry` renders the identical explanation block, with the writer sentence naming the
Foundry hosted agent and the `served by: foundry-hosted-agent` line beneath it. The handler opens a
view for the foundry variant exactly as it does for `on`, so a foundry page counts a vote.

## AC2 — the citation guard is unchanged

The agent's prose passes through the same `parse_reply` and the same `violations` check as the
model route. A fabricated verb fed through the agent route is refused in the same state
(`failed_unavailable`), with the same sentence machinery. A test drives the stub's reply with a
wrong verb on a real route and asserts the page falls back and names the verb.

## AC3 — the ledger and the report

`agent_call` gains `route` (`model` | `foundry`); rows written before this ticket are `model`, and
the migration says so. Each call records the route, the agent's own token counts, its wall time,
and failures by kind: `unreachable`, `timeout`, `non_200`, `missing_text`, `malformed_reply`,
`rejected`. `/agent-report` gains a "The routes, side by side" table: per route, calls, total
tokens, wall time, explanations written, helped / did not help, and failures by kind. The per-variant
table also shows the route each variant asks. The foundry route deliberately does not read the
explanation cache: a cached page would price a call the agent never made.

## AC4 — honest failure

If the agent endpoint is unreachable or slow (>20 s), the page renders the honest failure sentence
and the ledger records the kind. The model route answers only when `TESTOPS_AGENT_FALLBACK=model`
is set; the page then says which route failed and that the substitution was allowed. A rejected
reply is never re-asked of the other route — a second opinion about the same record is not what
this feature claims. A test asserts no model call happens without the variable.

## AC5 — the 275 pages and the model route

`agent=off` and no parameter remain byte-identical over all 275 real pages (the TESTOPS-88 golden
test runs in this suite). `agent=on` behaviour is unchanged: the model route's code path and its
block are untouched. Suite: **see the verification section below.**

## AC6 — the credential

`TESTOPS_AGENT_TOKEN` is the only source of the agent's api-key; the agent route never falls back
to IMDS or the az CLI (the model route's token machinery is separate and still applies to it).
A test sets a distinctive token, drives a real agent call through the stub, and asserts no
substring of it appears on the case page, `/agent-check` or `/agent-report`.

## Tests

`tests/test_agent_foundry.py` (20 passed, 1 skipped). It never calls the live agent: a local
`ThreadingHTTPServer` stub answers with the ticket's quoted reply shape, and the parsing is pinned
against the real response body. The optional live smoke check skips without `TESTOPS_AGENT_TOKEN`.

## Verification

- `tests/test_agent_foundry.py`: 20 passed, 1 skipped.
- Full suite from the project `.venv` with `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV` and
  `CONDA_PREFIX` stripped and `PYTHONNOUSERSITE=1`: **1409 passed, 3 skipped** (476 s), against
  1389 passed / 2 skipped before this build. The 20 new tests are this ticket's; the third skip is
  the live smoke check, which needs a token. `tests/contracts` ran inside that number and is green.

## Notes for the reviewer

- The branch carries the Lead's earlier commit `9d06001` plus this build's follow-up commit; the
  branch has diverged from `origin/main` by two commits and does not merge it here.
- The migration rebuilds `agent_view` and `agent_flag` row for row to widen their `variant` CHECK
  (SQLite cannot alter a CHECK); ids and values are preserved and no history is rewritten.
