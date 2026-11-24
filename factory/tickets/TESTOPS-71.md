---
id: TESTOPS-71
title: The guard goes quiet when git is down, and the URL rule cannot read a placeholder
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-69
---

# TESTOPS-71 - Three findings from the residuals review

## Why this exists

TESTOPS-69 fixed five residuals and documented a sixth. Its review then found that one of the fixes has a hole in exactly
the direction it was meant to close, and that the URL rule cannot tell a placeholder from a secret.

1. **When git is unavailable at walk time at both ends of a run, the tracked-path guard goes quiet.** `tracked_paths`
   returns an empty set, so the walk falls back to pruning `.venv` and ignoring `*.pyc` **by name** — and a rewrite of a
   commit-tracked `.pyc` becomes report-only churn, which is the thing AC4 was written to make impossible. The function's
   own docstring says an empty set is "a smaller promise, never a licence to prune nothing". The code contradicts it.
2. **`git readable: yes` can print when git was unreadable at snapshot time**, because the field reflects the state reads
   and commit trees but not the walk. The run still fails as `not_comparable`, so nothing is hidden — but a field that can
   say yes when the answer is no is the same class of lie the guard exists to prevent.
3. **The pair rule fires before the reference check.** `?token=${TOKEN}` and `?page_token=abc` are refused by the pair
   branch, which does not consult `_is_reference` for strong words, so a slot reference is refused while `?api_key=*** is refused because
   `YOUR_KEY_HERE` is not recognised as a placeholder. A filter that refuses a placeholder trains people to paste the real
   value instead.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | When the repository is unreadable at walk time, the guard treats every walked path as **content** (loud) or fails the run - it never silently falls back to name-based pruning. Pinned by a test with git unavailable at baseline and comparison. |
| AC2 | `git readable` is true only when **every** read the guard performed succeeded, including the walk's tracked-path lookup. Pinned in the unreadable-walk case. |
| AC3 | A slot reference is accepted wherever a value is read, including the pair branch: `?token=${TOKEN}`, `page_token=${TOKEN}`, `api_key=os.environ["X"]`, `key = from-env`. The pair branch consults `_is_reference` for strong words too, or states why it must not. |
| AC4 | Placeholder values are recognised as placeholders, not secrets: `YOUR_KEY_HERE`, `YOUR_API_KEY`, `<your-key>`, `changeme`, `xxxx`, `***`, `REDACTED`, `TODO`, `example`. Pinned as accepted in both a pair and a query string, while `hunter2`, a 36-character base62 body and an `AKIA`-shaped value stay refused. |
| AC5 | The tab decision's false-positive family is recorded beside the wrapped-sentence limit: `notes\tkey: in the vault` is refused as configuration and that is stated with the other stated limits rather than discovered later. |
| AC6 | No detection weakened: the 33-row bill, the twenty collisions and the T59/T62/T63/T65/T68 probe sets keep their verdicts; contract suite green; full suite green; no case-page golden changes. |
