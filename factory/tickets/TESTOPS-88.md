---
id: TESTOPS-88
title: A Foundry agent that explains a case, measured against the same case without it
feature: F2
status: done
autonomy: build
depends_on: TESTOPS-85
---

# TESTOPS-88 - The agent, and the honest way to tell whether it earns its cost

## Why this exists

`testops/judgement/client.py` and `testops/judgement/prompts/level_fitness.md` were the baseline design: a model that
*decided* whether a test was overbuilt. The factory replaced that decision with deterministic rules, because a verdict has to
be rebuildable from stored rows. The adapter was left in the tree with no callers, and the architecture Harry thought he had
stopped being true without anyone saying so.

Harry's decision (2026-11-24): the deterministic verdicts stay, **and** a Foundry agent is added where a model genuinely
helps - turning a stored finding into plain English - **with an A/B test**, so the value can be weighed against the cost
rather than asserted.

## The rule this must not break

The verdict is evidence. The explanation is commentary. A reader must be able to tell which is which without reading a
changelog, and switching the agent off must leave the page's verdict-bearing content byte-identical to today's output.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `agent=on` / `agent=off` on a case page selects the variant, default **off**, and the choice is recorded with every page view. Off renders exactly today's page - the golden for each real case must be unchanged byte for byte when the flag is off. |
| AC2 | With the agent on, the page gains one labelled block: an explanation of **this case**, written from the stored record only - assertion text, verdict, matched word, product file/line, near-miss reason, and nothing the store does not contain. It is labelled as model-written with the model name, and the deterministic verdict above it is untouched. |
| AC3 | The prompt forbids inventing facts, numbers, filenames or routes. A reply that introduces a route, file or count absent from the record is **discarded**, the page falls back to the agent-off rendering plus one sentence saying the explanation was rejected and why. Pinned with a fake model returning a fabricated route. |
| AC4 | A cost ledger records every call: case id, variant, model, prompt hash, tokens in, tokens out, cached yes/no, wall time. A `/agent-report` page shows, per variant: views, explanations served, cache hits, total tokens, mean tokens per explanation, and the same for feedback. |
| AC5 | Caching: the explanation for a (case, prompt hash, model) is stored and reused, so a second view of the same case costs nothing. The page says when it is showing a cached explanation. |
| AC6 | Feedback without JavaScript or cookies: two links per explanation ("this helped" / "this did not"), recording variant + case + verdict into the same ledger, and the report page counts them per variant. One vote per case per variant per browser session is enough; identity is not wanted. |
| AC7 | Failure is honest: model unreachable, non-200, rate-limited, empty or malformed reply - the page renders the agent-off content plus one sentence saying so, never a blank block and never a fabricated explanation. Each failure is recorded in the ledger with its cause. |
| AC8 | No credential is stored, printed or committed. The token comes from a managed identity inside Azure and from the `az` CLI locally; `client.py` must stop hard-coding a host path to `az.cmd`. Endpoint and model are configuration, defaulting to the Foundry project `<foundry-account>` and `deepseek-flash`. |
| AC9 | Determinism guard: the analysis suites and contract suites are unchanged and green; the agent path is tested against a fake model (no network in tests); the ledger arithmetic is tested. |
| AC10 | The report states the cost model it uses and marks any price as an **assumption** with its source; it does not invent a per-token price as fact. |

## Notes for the builder

- The agent never runs during analysis, only at render time, and only when asked.
- Keep the whole path optional: with `TESTOPS_AGENT_TOKEN` absent and no managed identity, the site must serve agent-off pages with a single line saying the agent is not configured - it must not fail to start.
- The 41 existing run pages and the real cases are the test corpus for "off is unchanged".
