---
id: TESTOPS-43
title: A sentence that hides its own partial reads
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-41
---

# TESTOPS-43 — Partial is not whole

## Finding (TESTOPS-41 review)

TESTOPS-41 fixed the big lie. Three smaller ones remain, all in the sentence rather than the record:

1. **The aggregate sentence hides a per-capability zero.** With one real item of test code and zero product code, the
   page reads *"code and test code were consulted and returned 2 items"* — true as a total, silent about the fact that
   touching code returned nothing. A reader cannot tell a 2-and-0 from a 1-and-1.
2. **A skip that does not break a capability renders nowhere.** `_skip_reason` (`pipeline.py:83`) names only the
   largest skipped kind, and the *Files this run could not read* list appears only when an unread capability needs
   explaining. A run that skips 500 `.sql` files but reads its code fine shows the reader nothing.
3. **Partial reads are invisible.** Skip four of five kinds and the sentence still says *"consulted"*, which is true
   and misleading: a repository 80% unreadable looks fully read.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The sentence separates capabilities: a reader can tell which capability supplied which count, including when one supplied zero. It stays one readable sentence — no tables, no lists-in-prose. |
| AC2 | When a capability is read but **partially** skipped, the sentence says so with the counts: how many files were read and how many kinds were skipped. "Consulted" alone is not enough. |
| AC3 | Skips are always visible somewhere on the run page, even when no capability failed: a line under the source record stating kinds and counts, with the detail list reachable. A skip is never recorded in the store and absent from the page. |
| AC4 | The Demo Product and DemoService sentences do not change — both have zero skips, so neither gains noise. Pinned by test. |
| AC5 | Sentence construction stays in `sources.py` with the rest; no page template builds its own wording. |
| AC6 | Prose lint applies: no repetition with the surrounding page, no vocabulary the reader must learn. |

## Notes

- Prefer a short parenthetical over a second sentence: *"code returned 12 items (142 `.java` files and 3 other kinds
  unreadable); test code returned 48."*
- Do not start until the product decision on TESTOPS-42 is known only if the answer changes the vocabulary; the
  wording work here is ecosystem-neutral.
