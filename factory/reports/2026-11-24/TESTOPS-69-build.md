# TESTOPS-69 build - the six small residuals, collected

Ticket: `factory/tickets/TESTOPS-69.md`. Branch: `factory/testops-69-residuals`, built in the linked
worktree `C:/Users/Chester/Projects/testops-t69`. The live store and port 8791 were never contacted:
every probe is a direct call to `testops.services` or to the guard in `tests/support.py`, plus a
disposable git repository under `tmp_path`.

Files touched: `testops/services.py`, `tests/support.py`, `tests/conftest.py` (docstring only),
`tests/test_guard_attribution.py` (one expected summary string) and the new
`tests/test_stated_residuals.py` (32 tests). No case-page golden, template, fixture or contract seed
changed.

## AC1 - the six, one by one, with the decision

| # | residual | decision | why |
|---|----------|----------|-----|
| 1 | a tab never licenses the line boundary | **fixed** | a tab-separated line *is* a settings row; the tab sat in the lookbehind's exclusion class by accident, not by argument |
| 2 | the inline-password floor is a one-line shape | **fixed** | encoded userinfo, whitespace-split userinfo and a password in the query string are the same statement about the same address |
| 3 | "0 unreadable files" can print when git was never readable | **fixed** | the field is now in every summary, pass or failure |
| 4 | committed build artefacts ride the ignored channel | **fixed** | the ignore policy is about *churn*, not names; a tracked path is content and is attributed like any other file |
| 5 | pruning is by name at any depth | **fixed** | same mechanism: the walk asks git what is tracked before it honours a name |
| 6 | a wrapped sentence whose next line begins `Key:` is read as configuration | **documented as a stated limit** | nothing in the string distinguishes a wrapped continuation from a second settings line - the line break is the only evidence there is |

## 1 and AC2 - the tab, decided on purpose

The lookbehind was `[^A-Za-z0-9_ \t]`: the tab was listed with the space, so `x\tkey = hunter2` was
prose and was stored. It is now `[^A-Za-z0-9_ ]`, so a newline, a separator and a **tab** are all line
boundaries. The decision is made, not inherited: a tab-separated line is a configuration row in every
tab-separated format settings are pasted from, and a tab between words is a cell separator rather than
the space that joins a sentence. A space stays the one horizontal character that does not license the
boundary, because a space is the one that occurs inside English prose. Pinned in both directions
(`x\tkey = hunter2` refused, `x key = hunter2` prose, both equal to the `key = hunter2` branch), and a
test reads the source and fails if the reasoning is edited away.

## 2 - the floor is more than one line shape

`_INLINE_PASSWORD` matched `://...:...@` on one line only. It now reads three spellings of the same
statement - plain userinfo, userinfo whose `:` is `%3A`, and userinfo split by whitespace around the
`:` and `@` - and a second pattern reads the query string: `?password=x`, `&pwd=...`, `?token=...`,
`?api_key=...`. The query form is the only member that reads a *name*, and the module comment now says
so instead of calling the whole floor word-free. Pinned: seven password-bearing addresses refused with
the reason naming the shape and never the value; five honest addresses (`postgres://app@db/qa`,
`...?sslmode=require`, a URL, `host:8200/path`, `localhost:8791`) still accepted; and a separate test
pins that `host:port` is not userinfo. Stated in the comment: a space *inside* a password is not read
(the value is no longer one address), and a percent-encoded whole URL is not decoded.

## AC3 (3) - `git readable: yes/no` in every run

`AttributionReport.git_readable` is set on every return of `attribute_differences` and printed at the
front of the summary line the guard already prints on pass and on failure:

    write guard: git readable: yes; 0 files changed by a commit ... 0 unreadable files, ...
    write guard: git readable: no; 0 files changed by a commit ... 0 unreadable files, ...

The second line is the residual: a run that read no git and saw no difference used to look like a
clean run, because the unreadable count is difference-driven. It is deliberately **not** a new failure
class: the field is the truth about what happened, the existing unreadable class is the failure when a
difference exists, and the docstring says which is which. Pinned for the empty pass, the empty
unreadable run, the failing git run and the corrupt-tree run (`readable` is `no` there too: the guard
could not read what it needed).

## AC4 (5) and 4 - a tracked path is never pruned, and a committed artefact is not churn

One mechanism answers both. `_walk` now takes the set of paths the checkout tracks (the index plus
`HEAD`'s tree, read by `tracked_paths`) and:

* never ignores a tracked path for a name - a committed `generated.pyc`, `build/gen.pyc` or
  `.venv/lib/vendored.py` goes into the attributed snapshot, so a write to it is a change that fails
  when no commit accounts for it, and a commit that adds it is reported as added by that commit;
* prunes `.venv/` only when nothing tracked lives under it (`.git/` is still never walked);
* leaves an *untracked* `*.pyc`, `build/`, `dist/`, `__pycache__/` or `.pytest_cache/` exactly where it
  was - report-only churn, which is what the policy was for.

`attribute_differences` also drops a path the index or a commit now tracks from `ignored_changed`, so a
file that becomes tracked mid-run is attributed once in the ordinary class and is not also counted as
ignore-policy churn. Pinned with a real committed `.pyc` at the root, a committed `.pyc` under
`build/`, and a committed file under `.venv/` (all three in the attributed snapshot, none in the
ignored one), with untracked churn beside them still report-only, and a rewrite of the tracked `.pyc`
failing as `unexplained` and named.

## 6 - the wrapped sentence, stated

Unchanged behaviour, now written at the pattern: because the rule is positional, "…in the vault\nKey:
it is in the vault" is read as configuration. The comment says the line break is the only evidence
there is and that the rule reads it loudly on purpose; a test pins the behaviour and a test fails if
the paragraph is deleted.

## AC5 - no weakening, nothing honest regressed

- Full suite: **1132 passed, 2 skipped**; the 32 pins in `tests/test_stated_residuals.py` are
  the difference.
- Contract suite `tests/contracts`: **37 passed, 2 skipped**, unchanged.
- Every rule changed here only *adds* refusals or *adds* attribution: the tab case, the three URL
  spellings and the query string were accepted before and are refused now; tracked paths were
  invisible or report-only and are now attributed. Nothing that was refused became accepted, and
  nothing that was failed became merely reported.
- T68's seams suite, T59's boundary table (104 values), T62/T63/T65's tables, the partition test and
  the alphabet test all pass unchanged; the only edited existing expectation is the summary string in
  `test_an_empty_report_has_nothing_to_say`, which now carries the new field.
- `git status` shows only the five files named at the top.

## Residual risk, named

1. **A wrapped sentence whose continuation line begins `Key:` is refused as configuration.** Stated
   above, at the rule, on purpose.
2. **A path that git tracks but the index and `HEAD` cannot describe** (a path only in a commit that
   is not `HEAD`, with git otherwise unreadable) is walked as untracked. The unreadable class reports
   it rather than the walk hiding it.
3. **A password inside a password** - a space in the secret itself - is not read, because the value is
   then not one address; stated at the pattern.
4. **A query parameter is read by name**, so `?token=` on a URL that is not a credential (a pagination
   token, a Slack callback) is refused. The loud direction, and the value is never printed.
