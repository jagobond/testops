# TESTOPS-26 addendum build report — 2026-11-22

Branch `factory/testops-23-copy`, addendum committed at 44c4158. Two typographic defects seen in
the rendered build of `case-cotw-levels-20261122T011316-03`. Nothing else changed: the page's
structure, the recast copy and the verdicts are untouched.

## AC10 — the detached comma

**The markup was never wrong.** The page already emitted `…both loads</code>, but…` with no space
between the span and the comma; a search of all 101 stored case pages found no `</code> ,` anywhere.
The gap was painted: `code.ident` carried `padding:.05em .25em` and no margin, so the span's own
right padding stood between the last glyph and the comma. Measured with `Range.getBoundingClientRect`
on the real page: the whitespace between the `s` of "loads" and the comma was **3.81px**; it is now
**0.00px**.

The fix is in `testops/web/app.py`: `code.ident` keeps its tint and radius, and the horizontal
padding is cancelled by an equal negative margin (`margin:0 -.25em`), so the span ends where its
identifier ends.

Three tests, because the defect had two halves:

- `test_punctuation_follows_a_code_span_with_no_space_between` — no `</code> ,` and no
  `</code> .` in the rendered page, and `lint.detached_punctuation(html) == []`;
- `test_the_punctuation_check_catches_a_detached_comma` — the check rejects a space it is given, so
  it cannot pass vacuously;
- `test_the_code_span_paints_no_space_between_it_and_that_punctuation` — `code.ident`'s horizontal
  padding equals its negative margin, so nobody can delete the margin and reintroduce the gap that
  the markup check cannot see.

`lint.detached_punctuation` is part of `lint()`, so the existing corpus test now runs it over every
page of the stored 94-claim run, and over every page of the fixture pipeline run.

## AC11 — the "What to do" box

The defect was real in the CSS and could not be fixed by equal padding: the font's ascent is longer
than its descent, so with `.6rem` top and bottom the ink sat low in the box. Measured on the
screenshot, before:

```
box rows 352–395   ink rows 368–383   space above 16px   space below 12px
```

`.6rem .8rem` became `.51rem .8rem .69rem` — the same total height, with the half-leading paid at
the bottom, which is where the descender competes for it. After:

```
box rows 352–395   ink rows 366–381   space above 14px   space below 14px
```

The two lines in the CSS that carry these decisions are commented with the reason, because the
asymmetry looks like a mistake to anyone who has not measured it.

## Verification

- Verdicts: `scripts/replay_levels.py --acceptance` — **94 claims, 90 distinct, 1 unplaced, 1 gap,
  2 review — PASS**, 41 scenarios.
- Suite, clean invocation (`env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX
  PYTHONNOUSERSITE=1`):
  - Python 3.12.5 (`.venv`): **273 passed**, 32.7s (270 before, 3 added).
  - Python 3.11.15 (`uv run --no-project --python 3.11 --with pytest --with-editable . pytest`):
    **269 passed, 4 skipped**, 31.3s. The four skips are the pre-existing pre-3.12 checks.
- The CSS test was confirmed to fail on the old rule (negative margin removed) before the fix was
  restored, so it is a guard and not a description.

## Screenshots

Served from `testops.web.app`, screenshotted with headless Chrome at 1100px:

```
C:\Users\Chester\Pictures\testops-screenshots\TESTOPS-26-case-cotw-levels-20261122T011316-03.png
C:\Users\Chester\Pictures\testops-screenshots\TESTOPS-26-case-cotw-levels-20261122T011316-03-scan-block-2x.png
```

The second is the scan block at 2x, where the comma and the box's padding can be read directly.

## What it does not solve

- **The gap was invisible to the markup checks.** Anything that only reads HTML cannot see a
  padding defect; AC10 is pinned twice for that reason, once in the markup and once in the rule.
- **The padding numbers are font-dependent.** `.51rem/.69rem` balances the block's ink in Segoe UI
  and the other sans-serif fallbacks at 16px. A face with very different metrics would move it by a
  pixel or two; it would not become wrong, only less exact.
