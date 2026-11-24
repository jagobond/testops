---
id: TESTOPS-77
title: The Java reader refuses for the right reason - two false reasons left
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-74
---

# TESTOPS-77 - A refusal is only honest if its reason is true

## Why this exists

TESTOPS-74 stopped the reader inventing routes: everything it cannot compute is now refused. Its second review found that
two of those refusals tell the reader something untrue - which is the same defect one layer quieter, and the reason is
what a person acts on.

1. **String literals in an unlexable file are harvested as type declarations.** `_declared_type_names` strips comments but
   not string literals, so a file containing `"class BaseController ..."` in a string makes the refusal say the repository
   *holds* that type. It does not. (The mapping is refused either way - only the reason is false.)
2. **An interface-borne refusal names a superclass that does not exist.** `REASON_PREFIX_NOT_READ` reads "class prefix is
   inherited and its superclass was not read", and every interface case - including the both-at-once case where nothing is
   missing at all - carries that wording.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Type names are read from an unlexable file only in **code position**: string and char literals and comments are consumed before the declaration is recognised, or the declaration is matched in the lexer's token stream. A `class X` inside a string or a comment is not a declaration. Pinned by a fixture whose only mention of the type is in a literal and one where it is a real declaration. |
| AC2 | Every refusal names the thing that is actually missing, with the right noun: a **superclass**, an **interface**, or an **ambiguous** name held more than once. The both-at-once case names both, or names neither as missing. Pinned for all four shapes. |
| AC3 | The reason strings contain no ticket ids or AC numbers (same rule as TESTOPS-75 AC1) - a stranger reading a page can act on them without our backlog. |
| AC4 | Corpus: 142 parsed / 25 surfaces / 0 unread unchanged, since no corpus file exercises these paths; the fixtures do. State it. |
| AC5 | Full suite green; contract suite green; no case-page golden changes; stored run pages byte-identical. |
