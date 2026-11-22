# TESTOPS-33 review, second round — the fix

Reviewed 2026-11-22 from worktree `C:/Users/Chester/Projects/testops-t33` on `factory/testops-33-headline`
(HEAD `616237b`, fix commit `bb2d57f`, diff `a92a6ec..bb2d57f`: `testops/web/app.py` +134/−26,
`tests/test_claim_headline.py` +115). Suite: **371 passed, 7 skipped** in 48.4 s from
`C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe` with `PYTHONPATH`, `PYTHONHOME`,
`VIRTUAL_ENV`, `CONDA_PREFIX` stripped and `PYTHONNOUSERSITE=1` (8 tests more than the first review's
363 — the new guard and trim tests). Worktree clean, no stray store file (the `data/testops.db` the
first review created is gone).

## Verdict — PASS

Both defects are fixed at the root — one class attribute built from a list and joined once, a trim that
keeps meaning words and never drops a subject silently — and the guard that refuses duplicate `class=`
attributes demonstrably fails when the old markup is reintroduced.

## Your six inputs — output after the fix

`case_headline("Not proved", <subject>)`:

| subject in | headline out | len | meaning |
|---|---|---|---|
| `the row is skipped if not` | `Not proved — the row is skipped if not` | 38 | kept |
| `the value is set no` | `Not proved — the value is set no` | 32 | kept |
| `The claim holds because the step is missing not` | `…the step is missing not` | 60 | kept |
| `x` × 200 (no spaces) | `Not proved — xxx…x …` (77 x's + ellipsis) | 89 | shown cut short, ellipsis present |
| `!!! ??? ... ---` | `Not proved — !!! ???` | 20 | shown (was bare judgement) |
| `🚀 🧪 ✨ done 🚀` | `Not proved — 🚀 🧪 ✨ done 🚀` | 25 | kept |

All six now carry a subject; none inverts its claim; all `headline_problems` empty; all ≤ 90 chars.
The three once-inverted headlines are exactly the ones the fix's tests pin, and they now read the
subject whole.

## New attacks — each construction, output, meaning survived?

Negation vocabulary beyond the fix's word list (MEANING covers `not no never none without unless except
only cannot isn't doesn't won't` — my probes use words *not* in it, which end on ordinary words the
trim would normally keep, so the risk is the boundary, not the word list):

| construction | output | meaning survived? |
|---|---|---|
| `the job fails to run the migration` | kept whole (47) | yes — "fails to" never touched |
| `the service lacks a retry path` | kept whole (43) | yes |
| `the endpoint declines the request when unauthenticated` | kept whole (67) | yes |
| `the parser refuses the empty payload` | kept whole (49) | yes |
| `the check not only times out but also hangs` | kept whole (56) | yes — ends on "hangs", no trim needed |
| `the cron job no longer sends the report` | kept whole (52) | yes |
| `the value is set no longer` | kept whole (39) | yes — "no longer" kept whole |

Subject whose 90th character falls inside a URL:

| construction | output | meaning survived? |
|---|---|---|
| 99-char URL (char 90 inside `?query=1&other=2`) | `Not proved — https://…/forever/segm …` (89) | mostly — cut at a word boundary with an ellipsis, but a URL cut mid-segment is not clickable; cosmetic, not a lie |
| long path + ` tail token after the url` | `Not proved — https://example.com/aaa… … token after the url` (89) | yes — middle ellipsis keeps both ends; the tail words survive |

500-word subjects:

| construction | output | meaning survived? |
|---|---|---|
| `word0 … word499` (500 words, 3 889 chars) | `Not proved — word0 … word11…` (87) | yes — whole-word prefix + ellipsis, never mid-word |
| `not ` × 500 (2 000 chars) | `Not proved — not not … not not…` (89) | yes — all-negation subject trimmed at a word boundary; no inversion possible, the negations are still there |

Single-emoji subjects:

| construction | output | meaning survived? |
|---|---|---|
| `🚀` | `Not proved — 🚀` (14) | yes |
| `🚀🚀🚀` (no spaces) | `Not proved — 🚀🚀🚀` (16) | yes — short enough, no trim |
| `👨‍👩‍👧‍👦` (ZWJ family, 7 code points, 1 grapheme) | `Not proved — 👨‍👩‍👧‍👦` (20) | yes — length counted in code points, grapheme intact |

Edge shapes re-checked: no judgement (`None`/`""`) → the bare subject; blank subject → `Not proved`
(judgement alone is correct when there is no subject at all). Every output ≤ 90, `headline_problems`
empty everywhere. No attack broke the trim; nothing inverted, nothing vanished.

## The guard — did it fail when you reintroduced the markup?

Yes. I copied the fixed `testops` package to a shadow tree, replaced both `badge_classes(...)` call
sites with the original broken string form, and ran `tests/test_claim_headline.py` against the shadow
(the venv's editable-install finder was neutralised via a startup plugin so the shadow package won
import resolution — the shadow `app.py` was confirmed as the imported module). Result:

```
FAILED test_no_tag_carries_its_class_attribute_twice
  assert ['<span class...lass="hot"">'] == []
  Left contains one more item: '<span class="badge class="hot"">'
1 failed, 17 passed
```

The rendered index carried `<span class="badge class="hot"">Open</span>` and the guard named the exact
tag. The teeth are real: the same test passes (18/18) against the unmodified fix.

## Verdicts unchanged and bytes elsewhere

Rendered the same seeded store through both `a92a6ec` (pre-fix) and `bb2d57f` (post-fix) `app.py` and
diffed the bytes. The index and the case page each differ in exactly one span:
`<span class="badge class="hot"">Open</span>` → `<span class="badge hot">Open</span>`. Everything else
— headline text `Not proved — The same word is in different fields`, the verdict badge
`<span class="badge verdict">Not proved</span>`, all six sections of the case page, the decision form —
is byte-identical. Judgement vocabulary and `LEGACY_JUDGEMENT` are untouched by the diff. No other page
is affected; the diff touches no rendering path beyond the two badge spans.

## Residual risk

1. **A trailing punctuation-only tail is printed.** `!!! ??? ... ---` renders as `… — !!! ???`: three
   punctuation marks end the headline and `headline_problems` accepts them (they are not words, so
   "no trailing punctuation fragment" is met only by the letter of AC2's word list). Harmless, honest,
   and rare — worth a line in a future ticket at most, not a blocker.
2. **URLs are cut mid-segment** when a URL alone exceeds the budget; the ellipsis keeps it honest but
   the fragment is not a link a reader could paste. Same class of issue, cosmetic.
3. **MEANING is a word list, and English negation is not.** "fails to", "lacks", "declines", "refuses"
   survive today only because they end on ordinary words that `_dangling_word` would keep anyway; a
   sentence engineered to *end* on such a word (e.g. `… the run fails to` ) would be kept — correct —
   but a future tightening of DANGLING that adds those verbs without adding them to MEANING would
   reintroduce inversion. The pinning tests cover `not`/`no` endings only; the class is guarded by
   structure (MEANING is checked before DANGLING), not by vocabulary.
