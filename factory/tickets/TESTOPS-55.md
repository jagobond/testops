---
id: TESTOPS-55
title: Counts that say what they count - front-page totals and per-kind reads
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-54
---

# TESTOPS-55 - Counts that say what they count

## Why this exists

Two failures from the blind author, both about a reader being unable to state what exists or what was read. The front
page lists projects but never says how many, and never uses the word "projects". The run page says "5 files" and "the 27
files read" per repository, and lists **skipped** files by kind - but never gives read counts per kind, and never an
explicit zero ("0 product files"), so a reader cannot tell an unread side from a side that produced nothing.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The front page states totals for projects, runs and cases, each labelled with what it counts, in a sentence or line a newcomer can act on. A test asserts three labelled counts are present and that they match the store's actual counts at render time. |
| AC2 | A run page gives **per-repository, per-kind read counts, including explicit zeroes** - "read 148 .cs files and 0 .js files", not "5 files". The kinds listed are those the analyser knows about, so a zero is informative rather than absent. |
| AC3 | Read counts and skipped counts are visibly distinct (a reader must not confuse "read 0" with "skipped 142"), and the existing skipped-by-kind list is unchanged in meaning. |
| AC4 | The numbers are derived, never hardcoded: a test renders a page whose store copy has a known zero of a known kind and asserts the zero appears; and a test with a partially-read capability asserts both the read count and the skip count. |
| AC5 | Contract suite **P07** and **P10** pass, nothing regresses; the .NET and Python analyser output is unchanged (CotW 94/90/1/1/2, ReqOverflow 17/17); goldens regenerated only for the intended text, with diffs shown. |
