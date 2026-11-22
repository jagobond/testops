# TESTOPS-33 review — a headline a reader would click

Reviewed 2026-11-22 from worktree `C:/Users/Chester/Projects/testops-t33` on `factory/testops-33-headline`
(HEAD `a92a6ec`), diff `origin/feature/f1..HEAD`. Suite: 363 passed, 7 skipped, from
`C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe` with `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV`,
`CONDA_PREFIX` stripped and `PYTHONNOUSERSITE=1`; `PYTHONPATH=.`, and `testops.__file__` confirmed as
`C:\Users\Chester\Projects\testops-t33\testops\__init__.py`. The live store was read read-only
(`file:...?mode=ro` + `PRAGMA query_only`), never through `db.connect` (see concern 3).

## Verdict — NEEDS-FIX

Every acceptance criterion and the headline builder's hostile-subject behaviour hold, but the diff rewrites the
row-markup line and still ships `<span class="badge class="hot"">` — malformed, still rendered live, fixed
nowhere and deferred nowhere, so the rule that it must not ship twice-broken fails.

## Criteria

- **AC1 HOLDS.** Over the live store every listed row reads `<judgement> — <subject>` from the ticket's
  vocabulary; legacy verdict words (`necessary` ×25, `optimal` ×36, `overbuilt` ×67 in the store) get the
  judgement their old word made via `LEGACY_JUDGEMENT`; the normalised step is the fallback subject only when no
  scenario was recorded. Verdict and scenario come from the same claim as the assertion (`case_lead`),
  so a judgement is never stated beside a subject from another claim.
- **AC2 WEAK.** No headline ends on a preposition or stopword — verified over all 168 live cases and every
  hostile subject below. But the mechanism that refuses the tail silently strips a trailing negation, which can
  invert meaning (see the constructed cases under Hostile subjects); the ticket's letter is met, the
  trim-never-lies requirement is not.
- **AC3 HOLDS.** 90-character ceiling, whole-word trim, ellipsis, never mid-word. A 200-character unbroken
  subject degrades to the judgement alone rather than a mid-word cut.
- **AC4 HOLDS.** The case page is untouched by the diff; the live page for
  `case-reqoverflow-dup-20261122T090439-18` still carries the full assertion text and TESTOPS-23's six-section
  structure including "3. The copy this claim names". Tests pin it.
- **AC5 HOLDS.** Rows grouped under one `<h2 class="section">` per project; the verdict badge sits beside the
  case state, dashed for `unplaced`/legacy; `Cannot tell` cannot be mistaken for `Checked`.
- **AC6 HOLDS.** The test renders a run the real pipeline wrote and refuses raw fragments. Independently
  re-verified against the live store: **168 cases**, all listed rows and every case render **zero** headline
  problems, and **zero** rows whose subject is still the bare assertion fragment. The defect row
  ("the suggestions list should be") no longer appears as link text anywhere.

Hostile-subject escaping: the builder returns raw text by design, but the render site escapes —
`<p class="claimtext">{esc(row_headline(r))}</p>`. Fed a `<script>`/`&`/quotes subject through the real page
path, the output was `Not proved — &lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;q&quot;`. No escaping
failure.

## Hostile subjects

`case_headline("Not proved", <subject>)` — output and length:

| subject in | headline out | len |
|---|---|---|
| `word` | `Not proved — word` | 17 |
| `x` × 200 (no spaces) | `Not proved` | 10 |
| `!!! ??? ... ---` (punctuation only) | `Not proved` | 10 |
| `🚀 🧪 ✨ done 🚀` (emoji) | `Not proved — 🚀 🧪 ✨ done 🚀` | 25 |
| `the suggestions list should be` | `Not proved — the suggestions list` | 33 |
| `Not proved` (verdict word) | `Not proved — Not proved` | 23 |
| `Checked` (verdict word) | `Not proved — Checked` | 20 |
| `<script>alert('xss')</script>` | raw from builder; page renders escaped (`&lt;script&gt;…`) | 42 raw |
| `a & b "quoted" <tag>` | raw from builder; page renders escaped (`&amp;`, `&quot;`) | 33 raw |
| `The panel does not verify the token` | `Not proved — The panel does not verify the token` | 48 |
| `no evidence found for the token` | `Not proved — no evidence found for the token` | 44 |
| `check the no` | `Not proved — check` | 18 |
| `verify the` | `Not proved — verify` | 19 |
| `` (empty) / `   ` | `Not proved` | 10 |

Trim-never-lies check — constructed subjects where the trim cuts a trailing negation:

- `the row is skipped if not` → `Not proved — the row is skipped` — the negation is gone; the subject now
  asserts the opposite condition.
- `the value is set no` → `Not proved — the value is set` — inverted.
- `The claim holds because the step is missing not` → `…the step is missing` — inverted.
- Subjects whose negation is mid-sentence (`The corpus is not available when the`) trim correctly.

The AC's letter — never end on a dangling word — holds in every case above; the lie lives in what the trim
silently removes. `headline_problems` cannot see it because the surviving headline is grammatical.

## Three sharpest concerns

1. **The badge markup ships twice-broken.** The old row rendered `<span class="badge{hot}">` with
   `hot = ' class="hot"'` → `<span class="badge class="hot"">`. The diff rewrites that exact line
   (`app.py:874`, and the same pattern at `app.py:1359` on the case page) and keeps it; the live index render
   confirms three such spans. The browser resolves `class="badge class="` so the `Open`/`Needs a fix` badge
   never wears `.hot`. No ticket defers it — TESTOPS-34/35/36 are about cases, fixtures and cross-references —
   and neither the commit message nor a build report records a deferral. This is the one blocking item.
2. **A trailing negation is trimmed into a lie.** `DANGLING` contains `not`, `no`, `never`, `cannot`, so the
   tail-trim strips them silently. The fix is small: a negation removed by the trim should be refused by
   `headline_problems` (or the builder should drop the whole subject rather than invert it), and the test that
   pins the tail should include a `… if not` subject.
3. **Silent loss, both directions.** An unbroken 200-character subject renders as the bare judgement with no
   ellipsis to say a subject existed and was dropped; and `db.connect` eagerly creates an empty store wherever
   it is pointed — during this review a stray call created an empty `data/testops.db` in the worktree (since
   removed). That is the fault class TESTOPS-35 AC3 targets; the guard cannot come too soon.

On the "No findings" badge question: TESTOPS-33 does not add a badge reading "No findings" — it prints
`No findings` as the *headline* of a case with no claim, which is a placeholder TESTOPS-34 (already ticketed,
depends on this one) deletes along with the empty cases themselves. The ordering is right and this ticket did
not pre-empt TESTOPS-34's decision; no concern.

One note on the claim the build makes: "no row in the live store now has a problem" is true as measured —
168 cases, zero `headline_problems`, zero bare-fragment subjects — but the list shows only the newest case per
analyser (4 rows, 164 older); the per-case check I ran covers all 168 via the same builder, so the claim holds
beyond what the list itself displays.
