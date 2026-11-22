# TESTOPS-19 review — 2026-11-22

## Verdict — PASS

The page opens with the stored finding and action verbatim, shows both code excerpts read from the
claim's own commit, degrades honestly on every missing-content path, and moves no verdict.

## Criteria

- AC1 HOLDS. On the -03 specimen the summary section is the first content after the `<h1>`; the
  badge follows it; it contains no decision control. Both sentences compare byte-for-byte equal to
  `claim.statement.strip()` and `claim.proposed_action.strip()`. The build report's reading of
  "first content" as "first block after the page heading" is reasonable — a title above the answer
  is chrome, not an argument.
- AC2 HOLDS, structural branch, and the branch is declared as AC requires. No browser in the suite,
  so the test asserts first-block plus exactly two labelled statements. I judged fit independently:
  I rendered all 43 corpus cases with no exceptions, and the tallest summary wraps to about six
  lines (~150 px at body size) — the whole block plus heading and badges sits far under 800 px at
  1280×800. The build report's three caveats about this reading are fair, not evasions.
- AC3 HOLDS. `summary_of` returns `action=None` when none is recorded; the page prints "No proposed
  action was recorded for this claim." and the finding still leads. Test at
  `tests/test_case_summary_and_code.py:210`.
- AC4 HOLDS. Over-budget statements cut at a sentence boundary with a pointer to section 4.
- AC5 HOLDS. Verified against the real commit (below), not just the page.
- AC6 HOLDS. `Steps/BrowserSteps.cs:94-99`, attribute line 94 marked, captioned as the step that is
  asserted.
- AC7 HOLDS (see "The snippets").
- AC8 HOLDS (see "The snippets"); the full page also renders with the blob file removed — no
  exception, no empty `<pre>`.
- AC9 HOLDS. Both excerpts come from `blobs.text(sha)`; the AC9 socket test passes; the page I
  rendered with a blob physically missing still completed.
- AC10 HOLDS. Snapshot `cotw-levels-20261122-a3f19853-r6`: 94 claims — 90 distinct, 1 gap, 1
  unplaced, 2 review. Suite: 210 passed, clean invocation, 18.4s.

## The snippets

Spot check 1 — assertion excerpt. Claim of `case-cotw-levels-20261122T011316-03`,
`features/review_panel.feature`, commit `a3f19853`. I rendered the page, then ran `git show
a3f19853:features/review_panel.feature` in the real `cotw-bdd` repo and compared. The excerpt is
lines 30–34, asserted line 32 marked, and every rendered line matches the commit's bytes at its
printed line number — no off-by-one. The stored blob and the repo agree.

Spot check 2 — step definition. Same claim, `Steps/BrowserSteps.cs` lines 94–99, line 94 marked;
`git show` at the same commit matches all six lines exactly. The excerpt stops at the body's closing
line, not at an arbitrary count.

What I did to break them. (1) Hostile unit fixture through `snippet_block`: `<script>alert(...)`,
`&amp;`, single and double quotes, a 340-character line, a `<script>` in the repository link's URL.
Result: no raw `<script>` in the output, ampersand double-escaped (`&amp;amp;`), both quote styles
escaped, the link attribute escaped, the 340-character line kept whole — and `pre.snippet` has
`overflow-x:auto`, so a long line scrolls rather than overflowing the page. (2) Hostile content in a
real corpus page: the rendered `<pre>` blocks contain no unescaped entity and no stray tag beyond the
renderer's own `span`/`mark` scaffolding. (3) Missing blob: I renamed the real blob file
`data/blobs/50/…` out of the store, re-read the claim and re-rendered the whole case page. Both
snippets flipped to honest states (assertion `not_stored` renders the recorded-but-not-stored
sentence; step definition fell to `ok` via a different artefact), no exception was raised anywhere,
and I restored the blob afterwards.

## The first screen

At 1280×800 the reader sees: the case title, then "What this is" — the finding's own words, whole
("The assertion is about the page as served: each fact's data-fact-id is the same on both loads…")
— then "What to do" — the stored action ("Rewrite the step … to call the HTTP client instead of the
browser…"). That is a real decision: it names the finding, the wasted browser, and the fix, in about
five seconds, with no decision control riding on it. A reader can stop there or scroll to the
evidence with an informed reason. The point of the ticket is met.

## Three sharpest concerns

1. The summary is the lead claim's only. A multi-claim case gets further summaries buried inside
   later arguments, so the top block can understate a case with two independent findings. The build
   report admits this; nothing in the criteria catches it.
2. The step-definition excerpt trims at the first blank line, so a step body with an internal blank
   line is cut early and looks complete. Cosmetic risk of a mis-read, not a wrong line number.
3. The claim text now appears four times on the -03 page (summary, section 1 quote, section 4
   statement, section 6 action). TESTOPS-23 must collapse this or the "scan in five seconds" win is
   spent re-reading the same words down the page.

## Demo

**The problem.** The case page opened with a verdict badge and six sections; evidence was links, so
deciding whether a case was worth reading meant leaving the tool and assembling the argument
yourself.

**What changed.** Every case page now opens with a two-label summary — the claim's own statement and
proposed action, read from the store and never re-worded — placed before the badges and section 1.
For a v2 claim it also shows the asserted feature lines (±2, numbered, asserted line marked) and the
step definition that runs them, both from content-addressed blobs at the claim's own commit, each
with a repository link for context only.

**How we know it works.** Suite green, clean environment, 210 passed. Verdicts unchanged: 94 / 90
distinct / 1 unplaced / 1 gap / 2 review. Both excerpts verified against `git show` at commit
`a3f19853` — line numbers and marked lines exact. Hostile markup, quotes, a 340-char line and a
deleted blob file all render or degrade correctly; all 43 corpus cases render without exception.

**What it does not solve.** AC2 is a structural assertion, not a pixel measurement (no browser in
the suite — declared, and my own line-count estimate agrees with the intent). The multi-claim
summary gap and the four-fold repetition of the claim text remain open, owned by TESTOPS-23.

**Where to look.** `testops/queries.py` (`summary_of`, `source_snippets`), `testops/web/app.py`
(`summary_block`, `snippet_block`), `tests/test_case_summary_and_code.py`; the -03 case page and the
`cotw-bdd` repo at `a3f19853`.
