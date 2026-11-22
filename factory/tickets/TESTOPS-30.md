---
id: TESTOPS-30
title: Two small defects the retention review found: --keep scope, and a stale case id
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-24
---

# TESTOPS-30 — Say what `--keep` counts, and answer a stale id instead of crashing

## Finding (TESTOPS-24 review)

**1. `--keep N` is per project.** The ticket said "the N most recent", which reads as global (the store's N most
recent snapshots). The implementation keeps N per project. Every deletion is still older than N globally, so it
deletes *fewer* than the letter allows — safe, but a reader invoking `--keep 2` expecting two snapshots total
gets one per project. The build report argued it; the Lead accepts the behaviour, and the wording must catch up.

**2. A stale case id crashes.** `case_page` returns `None` for a case whose snapshot was pruned, and the web
layer surfaces that as a `TypeError` rather than a 404-style page. Nobody has held a stale id yet; the first
person who does will see a crash.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The command's help text and the report say "keep N per project" wherever N appears, and the report prints the resulting per-project counts so a reader can see what N meant. No behaviour change. |
| AC2 | A request for a case whose snapshot no longer exists renders the "this case is no longer in the store" page with a 404 status, naming the case id and saying the evidence was pruned by retention — not a traceback, not a blank page. |
| AC3 | A test prunes a snapshot on a copy, then requests one of its case ids, and asserts status 404 and the explanatory page. A second test asserts a surviving case id still returns 200. |
| AC4 | No other page path changes; verdicts unchanged; suite green on both interpreters. |

## Notes

- Do not change `--keep` to global. It would delete more than the current rule and the difference buys nothing.
  Say what it does instead.
