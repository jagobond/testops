---
id: TESTOPS-52
title: Uncertainty does not wear certainty's clothes, and badges carry valid markup
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-7
---

# TESTOPS-52 - Uncertainty does not wear certainty's clothes

## Why this exists

The blind author found `Cannot assess` rendered as `<strong class="verdict hot">`, styled by
`p.judgement strong.verdict.hot { color: var(--bad) }` - the same alarm red as
`Checked, but this repeats another test`. Only the words differ, which is exactly "reading a legend". Worse, the
design already exists: the served CSS has `.badge.verdict.soft { border-style: dashed; border-color: var(--dim) }` with
a comment explaining it is for exactly this - and **nothing renders with it**.

While looking, it also found `<span class="badge class="hot">` served 32+ times: a quote inside the class attribute, so
the `hot` class is inert and the emphasis styling silently does nothing.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Every verdict carries a **deliberate tone**, declared in one place and mapped explicitly - never by a default that catches whatever is left. At minimum: a verdict that says the tool could not conclude wears the **soft** (dashed) treatment; a verdict that asserts a problem wears the alarm treatment; a verdict that asserts nothing is wrong must **not** wear the alarm colour. |
| AC2 | The mapping is exhaustive: a test iterates the verdict vocabulary (current and retired) and fails if any verdict has no declared tone, so a new verdict cannot appear untinted. |
| AC3 | `Cannot assess` on a real case page no longer shares a class or colour with a settled verdict, and a test asserts the two differ **structurally** (class attribute), not by wording. |
| AC4 | **No malformed markup**: no element anywhere in served pages has a literal `class="` inside its class attribute. A test parses every rendered page (front, runs, run, case, config) with `html.parser` and asserts every `class` attribute is a single well-formed token list - and that the badges' intended tone class is actually present. This must catch the current 32+ instances, so run it against the old templates first to prove it fails. |
| AC5 | The contract suite's **P4** test passes and no other contract test regresses; the suite is not edited by this ticket. |
| AC6 | Goldens regenerated only for the intended change; the diff is shown to be tone classes and markup only - no wording, no layout, no numbers. .NET and Python analyser output unchanged (CotW 94/90/1/1/2, ReqOverflow 17/17). |
