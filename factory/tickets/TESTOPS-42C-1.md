---
id: TESTOPS-42C-1
title: cucumber-js reads its own bindings - 44 declarations, both layouts, two placeholder kinds
feature: F2
status: done
autonomy: build
depends_on: TESTOPS-42A, TESTOPS-50
---

# TESTOPS-42C-1 — The parsing floor

Part 1 of 3 of TESTOPS-42C (green-lit by Harry, 23 Nov, quoted 7.5–8 days total). This part is the scanner and the
matcher: 44 declarations in 5 files, 16 of them multi-line, `{string}` and `{int}`, one duplicate across two files.
Everything downstream is inference, so this must be exact first.

Reference: `docs/ecosystem-inventory-cucumber-js.md` §1–§2 and `tools/ecosystem_inventory_counts.py` — the corpus facts and
the tool that proves them. Corpus: snapshot `demo-booking-20261122-262404a9`, test arm
`m-pujic-levi9-com/cypress-cucumber-e2e-tests@262404a95`, blobs in the store.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `cucumber_js.bindings()` returns 44 bindings from the 5 `*.stepdef.js` files: 26 When, 13 Then, 5 Given. Each carries verb, pattern text, file path, 1-based line of the declaration, and its suite. |
| AC2 | Both layouts parse: 28 declarations with the pattern on the same line, 16 with the parenthesis at end of line and the pattern on the following line. A line-oriented regex must not be the implementation - the inventory records that v1 of the detector missed exactly those 16. |
| AC3 | Both quoting styles parse (single quote in this corpus; double quote and backtick must work if present), and a regex-literal form `Given(/^...$/)` is either supported or **explicitly reported as unsupported in the record** - never silently skipped. |
| AC4 | `pattern_to_regex` gains `{int}` → `\d+` and keeps `{string}` → permissive; literal text stays literal; anchored and case-insensitive. Unit tests pin all three. |
| AC5 | The duplicate pattern (`Visitor will get validation/mandatory error message: {string}`, declared in `booking.stepdef.js` and `contact.stepdef.js`) resolves per-suite first, and falls back to any-suite only when the scenario's suite matches neither. Test both directions. |
| AC6 | Suite scoping matches the corpus: 6 features, 5 stepdef files, and each feature resolves to its own suite (the existing stem rule works on 5 of 5 - prove it, do not assume it). |
| AC7 | No claim is placed by this ticket: `analysers` receive the bindings and the run still reports what it reported before for this corpus (which is `not_assessable` until T42C-3 wires placement). Do not half-wire. |
| AC8 | .NET and Python unchanged: Demo Product 94/90/1/1/2, DemoService 17/17, case-page goldens byte-identical, suite green (583+). |

## Notes

- Count with `tools/ecosystem_inventory_counts.py`, not by eye. If your parser gives 43 or 45, the parser is wrong, not the
  corpus - the count was independently verified twice.
- Keep this a module-level change under `testops/extract/ecosystems/cucumber_js.py` plus the shared matcher; do not touch
  the analysers.
