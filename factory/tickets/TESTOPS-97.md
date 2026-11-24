---
id: TESTOPS-97
title: The proposal stage - an agent that may suggest, never decide
feature: F3
status: queued
autonomy: build
depends_on: TESTOPS-96
---

# TESTOPS-97 - Candidates, with provenance and no authority

## Shape

After the analysers write their findings, an evidence pack per claim (assertion, binding, product surface, neighbouring
claims) is sent to the hosted Foundry agent `testops-narrator` (or a sibling `testops-proposer`). The agent returns
candidates: `{kind, claim_id, pointer rows, one-sentence reason, confidence}`.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Candidates are stored in their own table with provenance: agent name and version, prompt hash, model deployment, tokens in/out, wall time, run id, and the raw reply (credential-screened). |
| AC2 | **No candidate can render as a finding.** A candidate has no page, no verdict and no case until a gate accepts it; a test proves a stored candidate alone produces no case. |
| AC3 | The proposal pass is explicitly opt-in per run (`--propose`), cannot run inside a page render, and cannot touch the verdict of any existing claim. |
| AC4 | The whole pass is replayable: given the stored candidates, the default run is unchanged; given the same prompt and model version, the pass records a diffable proposal set. |
| AC5 | Cost is recorded per candidate, not just per call, so T99 can price it. |
