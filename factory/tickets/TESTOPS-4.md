---
id: TESTOPS-4
title: One claim per assertion, said in words a developer can act on
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-3
---

# TESTOPS-4 — One claim per assertion, said in words a developer can act on

## Why

This is the ticket that fixes the Product Owner's complaint. Today a claim is one row per scenario,
classified from `scenario name + every step concatenated`, and its statement is a template with codes
in it:

> "I4 claim needs a browser to be established; the suite asserts it over api, so the claim is not
> actually established"

A developer reading that cannot tell what is asserted, where, or why it matters — and neither could
the Product Owner. Worse, classification is **title-driven**: a scenario titled "…with stable fact
anchors" whose third step asserts an accessibility property gets classified by whatever words the
title happens to contain.

The ruling being implemented: a claim is per assertion; the case presents it with its evidence and
what it could not check; the shorthand never appears in text a reader sees.

## What this ticket must produce

1. **One claim per asserting step.** An asserting step is a `Then`, or an `And`/`But` following a
   `Then`. `Given`/`When` steps establish context; they do not make claims.
2. **Classification reads the assertion.** The step's own text decides. The scenario title may be
   passed as context, but it must not create a claim the step does not assert. If the title and the
   step disagree, the step wins.
3. **Plain statement, no codes.** The statement says what is asserted, what establishing it needs,
   and what the test actually did. `I1`..`I4` and `KP` appear only in `interaction_code`.
4. **A proposed action.** What the team could do about it, in one sentence. This is the field the
   reviewer of a case acts on.
5. **Blind spots recorded.** Every claim carries `sources_missing`, supplied by the caller, so a
   claim can never look as though it consulted a source that was never connected.
6. **A case per claim.** A run raising N actionable claims creates N cases, each with at most one
   finding. A claim whose verdict is `distinct` raises no case and no finding.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A scenario with three asserting steps produces three claims, each with `assertion_text` equal to that step's verbatim text and `assertion_line` equal to that step's line. |
| AC2 | `Given` and `When` steps produce no claim. A `But`/`And` following a `Then` does. |
| AC3 | Classification follows the step text, not the title: a scenario whose title mentions anchors but whose step asserts an accessible name is classified by the accessibility step, and the reverse also holds. Prove both directions. |
| AC4 | No `statement`, `interaction_label` or `proposed_action` contains `I1`, `I2`, `I3`, `I4` or `KP` as a token. The code lives in `interaction_code` only. |
| AC5 | Every claim has a non-empty `proposed_action`, and the action differs by verdict — a `gap` proposes a different action from a `review`, and it names the specific thing to change. |
| AC6 | Every claim records `sources_missing` as passed by the caller; a caller that passes nothing still yields an explicit empty list, never NULL. |
| AC7 | A run of N actionable claims produces N cases, one finding each; `distinct` claims produce no case and no finding. |
| AC8 | Running the analyser twice over the same snapshot produces identical claims — same order, same statements, no timestamps or run ids inside statement text. |
| AC9 | The suite still passes and `web/` is untouched. `analysers/level_fitness.py` and `pipeline.py` are the product files this ticket changes. |

## Verification

```
cd C:/Users/Chester/Projects/testops
env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
  .venv/Scripts/python.exe -m pytest -q
```

## Notes for the builder

- A worked example of the target reading, for the CotW specimen: today's statement is unreadable
  shorthand; the replacement should read like
  *"This test asserts that each fact's citation is in an element an assistive technology can name.
  Only a browser works that out, and this test reads the server's response instead, so nothing checks
  it."* — followed by a proposed action naming the step to move.
- `classify_claims(text)` currently returns `[(interaction, why)]`. It will need to take the step
  and the scenario context separately; keep it a pure function so it stays testable without a
  repository.
- `interaction_label` is the reader's phrase ("needs a browser", "settled by the response body");
  it is not the code and it is not the statement.
- Do not change the verdict vocabulary beyond what ACs require, and do not touch the UI: the page is
  TESTOPS-6 and it will read the fields you produce.
- Existing v1 claims in the store must keep working — this ticket changes what new runs write, not
  what old rows mean.
