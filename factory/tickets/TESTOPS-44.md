---
id: TESTOPS-44
title: The secret guard errs in both directions, and the store upgrades without saying so
feature: F2
status: done
autonomy: build
depends_on: TESTOPS-38
---

# TESTOPS-44 — The guard misses base64 and refuses real keys

## Finding (TESTOPS-38 review)

`services._looks_like_secret` exempts any value containing `/`. Base64 — the most common credential encoding — always
contains `/`, so a complete AWS key posted to a free-text settings field was **accepted and stored** (row 15 in the
reviewer's scratch store). In the shipped form only `repo` is free-text and its `owner/name` regex constrains it, so
today's exposure is a hand-crafted POST or a future settings field — which is exactly how this becomes a leak.

It also refuses the innocent: `DEMO-PROJ-KEY-0123456789-ABCDEFG`, a plausible 32-character project key, was rejected as
high-entropy. A guard that blocks real configuration teaches people to disable it.

Two smaller findings from the same review:

2. **The store upgrades itself on open.** `db.connect()` migrates any store it touches, so running a command in the repo
   directory upgrades the live store with no prompt and no notice. Forward-only refusal protects *older builds*, and
   nothing protects the person who did not intend to migrate.
3. **The largest change so far was built with no report.** The review was the first document about it. A ticket this
   size going unreported is the failure mode the factory exists to catch.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Base64 is detected as base64 **before** the `/` exemption applies: a value whose charset and length look like base64 is refused even though it contains `/`. Prove with the reviewer's AWS key and with a random 40-byte base64 string. |
| AC2 | A legitimate structured key is accepted: `DEMO-PROJ-KEY-0123456789-ABCDEFG`, `owner/repo`, `https://jira.example.com`, `PROJ`, a UUID, and a 12-char word. Pin every one of these as a test so tightening the guard cannot silently break configuration. |
| AC3 | The guard never echoes a rejected value: assert the response body and the log contain the field name and the reason, never the value. |
| AC4 | Opening a store that needs migration prints one line naming the version change (`migrated store v3 -> v4`) and, on a store whose version is newer than the build supports, refuses with the versions named. A migrated-in-this-request store is distinguishable from one opened for reading. |
| AC5 | No behaviour change elsewhere: 439+ tests, Demo Product 94/90/1/1/2, DemoService 17/17, pages unchanged. |
| AC6 | Process: any ticket whose diff touches more than three modules must contain its build report, and the builder must not report "done" without one. State this in the builder prompt, not just the ticket. |

## Notes

- AC2 matters more than AC1: a guard that refuses real configuration will be worked around, and then it protects
  nothing.
