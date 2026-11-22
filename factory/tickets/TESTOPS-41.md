---
id: TESTOPS-41
title: Files the collector cannot read are silently dropped, and the page then says they were read
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-39
---

# TESTOPS-41 — Skipped is not consulted

## Finding (TESTOPS-39, second specimen)

`collectors/github.py:19-27` holds a fixed list of file kinds. `.java` is not in it. Against a Java product with
**142 `.java` files**, the collector fetched none of them and said nothing. The run then wrote a source record whose
capability `code` was marked *observed*, and the page's sentence for those claims is:

> "Assessed: code and test code were consulted and returned 48 items."

48 is the total of what *was* collected — 6 features and 42 JavaScript files, 27 of them front-end assets — counted
once for a source serving both capabilities. **No product code file was read.** The sentence is false, and it is the
same class of fault as every honesty rule in this project: a zero produced by a reader that could not read is being
reported like a zero produced by a reader that read and found nothing.

The same shape hides elsewhere: `surfaces/discover.py:45` parses Python only and returns `[]` for a Java product,
and the run prints `"surfaces": 0` with no reason attached.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The collector records, per run, **which files it skipped and why** — unsupported kind, size cap, ignore pattern — with counts per kind. A file it could not read is never counted as consulted. |
| AC2 | The source record distinguishes three states for a capability: *read and returned items*, *read and returned nothing*, *not readable in this repository* — and the page's sentence differs for each. The `code` capability must not read as observed when zero product-code files were fetched. |
| AC3 | A surface reader that cannot parse a language returns `not_assessable` with the reason (the language and the file count), not `[]`. The run's stats distinguish "0 surfaces found" from "0 surfaces findable". |
| AC4 | Both are proven on the TESTOPS-39 corpus: re-running `restfulbooker` renders a sentence naming the 142 skipped `.java` files, and says the product code was not read, rather than the current false sentence. |
| AC5 | CotW and ReqOverflow are unaffected: verdict counts 94/90/1/1/2 and 17/17, and their pages byte-identical. |
| AC6 | The fix is not a longer kind list alone. Whatever list exists must be data (configuration), and the code must report what fell outside it — a list that silently grows is the same bug with more entries. |

## Notes

- This is a correctness bug, not an ecosystem gap. It would mislead today on any repository with a language nobody
  anticipated, and it is the reason the TESTOPS-39 assessment reads as harshly as it does.
- Do not fix the cucumber-js binding gap here; that is a separate decision (TESTOPS-42, pending).
