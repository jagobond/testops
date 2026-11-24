# Programme: Model proposes, rules dispose

_Queued 24 November 2026, to start after the team presentation. Harry's words: "model proposes; rules dispose"._

## The claim we are testing

A language model is good at noticing that something *might* be wrong with a test, and bad at being trusted about it. The
rule engine is the opposite: it cannot notice a shape nobody wrote a rule for, but everything it publishes can be checked.

So: **the agent generates candidates, the rules decide what becomes a finding.** A proposal has no authority. It becomes a
case only by passing deterministic checks against stored evidence, and the case carries who proposed it and which rule
verified it.

## What "proving the value" means, in numbers

The programme is worth continuing only if it shows all four:

| measure | how it is measured | bar to clear |
|---|---|---|
| **Recall gain** | verified findings raised by proposals that the rules alone missed, over a fixed corpus | >= 10 genuinely new, adjudicated true |
| **Proposal precision** | accepted candidates / proposed candidates, per rule gate | >= 0.33 at the gate (two false proposals per true is tolerable when review is the bottleneck) |
| **Cost per verified finding** | tokens and wall time, from the ledger, divided by verified findings | cheaper than a human finding the same defect by reading the suite |
| **No regression in trust** | published findings still deterministic; `agent=on/off` byte-identical; every case cites rows | zero exception |

If proposal precision is hopeless (say < 0.1 with no gate beating it), the honest result is that the model is not yet useful
for recall on this corpus, and the programme stops with that written down. That is a real outcome, not a failure of nerve.

## Stages

1. **Measure the blind spot first (T95, T96).** Before building anything, find out how much we are missing. A blind gold set
   labelled by Harry and Bobby, plus a model-as-probe pass over cases the engine called `distinct`. No product change.
2. **Build the proposal stage (T97).** A Foundry agent reads an evidence pack and proposes candidates with pointers. Stored
   with full provenance; never rendered as a finding.
3. **Build the gate (T98).** Deterministic verification each candidate must pass. Rejections are recorded and counted,
   because the gate's own accuracy is the thing that makes the architecture trustworthy.
4. **Price it (T99).** Cost per verified finding, measured from the ledger, against a human baseline.
5. **Only then** decide whether proposals become part of the default run.

## Why this ordering

Measuring the blind spot first means the proposal stage has a target and a baseline. Building the proposal stage first
would produce an impressive demo and no way to say whether it helped.

## What the agent is not allowed to do

- Decide a verdict, set a case state, or suppress anything.
- Publish prose without citations (the guard from TESTOPS-88 applies to proposals too).
- Introduce a finding that no rule gate has passed.
