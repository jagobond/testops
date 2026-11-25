# TESTOPS-92 build — a switch that ignores a value is a switch that lies

2026-11-24, worktree `C:/Users/<name>/Projects/testops-t92`, branch
`factory/testops-92-agent-flag`, implementation commit `d69cd27`.

Suite, from the project `.venv` with `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX` stripped
and `PYTHONNOUSERSITE=1`: **1389 passed, 2 skipped** (330 s), against 1357 passed / 2 skipped before
this build. `tests/contracts` ran inside that number and is green. No test reaches the network.

## The defect

`_agent_variant` compared the raw query value to the literal `on`:

    return agent.VARIANT_ON if (value or "").strip().lower() == "on" else agent.VARIANT_OFF

So `?agent=true` produced the agent-off page, silently. The page was byte-for-byte the plain page,
which is exactly what a reader is entitled to read as "the agent does nothing" — the trap Harry hit
on the demo URL.

## AC1 — eight accepted values, and the two defaults

`parse_agent_flag` (in `testops/web/app.py`) trims the value, lower-cases it, and reads it against
two pinned tuples:

    FLAG_SHOW = ("on", "true", "1", "yes")     -> the explanation is shown
    FLAG_HIDE = ("off", "false", "0", "no")    -> the agent-off page, as the default

An empty value and an absent parameter both mean off. `_agent_variant` keeps its old signature and
return value (it delegates to `parse_agent_flag(...).variant`), so every caller written before this
ticket still works and the existing pin `test_the_flag_parses_to_off_unless_it_says_on` passes
unchanged.

Pinned in `tests/test_agent_flag.py`:

- `test_the_show_values_mean_show` (8 params) and `test_the_hide_values_mean_hide` (8 params): the
  eight spellings, plus mixed case and surrounding whitespace (`" YES "`, `" True "`, `" No "`).
- `test_an_empty_value_and_an_absent_parameter_are_the_default_off` (2 params).
- `test_every_accepted_spelling_is_pinned_as_a_table`: the two tuples and that all eight are
  `understood`.

## AC2 — an unrecognised value is never silent

A value that is not one of the eight produces the agent-off page **plus one paragraph**, placed
directly under the case's badge (above the evidence, not buried below it):

> The explanation was not shown: the value `maybe` in `?agent=` was not understood. It accepts on,
> true, 1 or yes to show the explanation, and off, false, 0 or no to hide it; anything else leaves it
> hidden, as this page does.

It names all eight accepted spellings, so a reader who typed something wrong can fix it. Nothing is
added for an accepted value or for no parameter at all — `flag_note_block` returns `[]` for both.

Pinned by `test_an_unrecognised_value_adds_exactly_one_line_to_the_off_page` (params `maybe`, `2`,
`onn`): exactly one `agent-flag-note` paragraph, no explanation block, the typed value and the words
"not understood" present, all eight accepted spellings named, and — the strong form — removing that
one paragraph leaves the agent-off page byte for byte. `test_the_warning_line_appears_for_no_show_value_and_no_accepted_hide_value`
checks the whole table at the block level: `maybe`, `2`, `onn`, `o`, `tru`, `yes please`, `-1` all
warn; the eight accepted values, `None` and `""` do not.

## AC3 — off is untouched, over all 275 real pages

`test_off_and_no_parameter_are_the_same_bytes_on_all_275_real_pages` reads
`tests/fixtures/agent/off-golden.json` (digests captured from the pre-TESTOPS-88 build with the clock
pinned at 2026-11-24T12:00Z) and compares, for all **226 case pages + 49 run pages = 275**:

- no parameter (`app.case_page`) against `?agent=off` (`case_response(..., variant="off",
  flag=parse_agent_flag("off"))`) — equal to each other, and
- the sha256 of each against its golden digest.

All 275 match; the test asserts `compared == 275` and that no golden page is missing from the store,
so a quieter number cannot pass. The TESTOPS-88 AC1 gate itself
(`test_every_real_case_page_is_byte_identical_to_the_pre_change_build`) was not edited and still
passes.

## AC4 — `/agent-report` shows the flag values it saw

New table in `testops/store/schema.sql`, created on every open by `executescript` like the other
agent tables (additive; no schema-version bump, no stored row copied or rewritten):

    agent_flag(id, at, case_id, flag_value, variant, understood)

`agent.record_flag` writes one row per case-page request, with the value as typed (trimmed, capped at
50 chars), the page it produced, and whether it was one of the accepted spellings. `agent.flag_values`
groups by `(flag_value, variant, understood)` with a view count and last-seen time.

`/agent-report` gains a **"The flag values readers typed"** section: one row per value, columns
*Flag value · Page shown · Understood · Views · Last seen*. `''` reads as `(absent or empty)`. An
empty table says "No case page has recorded its flag yet, so this table is empty because nothing was
measured — not because every value was understood."

Pinned end to end by `test_the_handler_records_what_was_typed_and_the_report_shows_it`: a real
`Handler` on a socket serves `?agent=maybe`, `?agent=off` and the plain URL; the page for `maybe`
carries the warning; the ledger holds `maybe`/off/not-understood, `off`/off/understood and
`''`/off/understood; the report page shows the heading, the `maybe` row marked `no`, and the accepted
rows marked `yes`. `test_the_report_says_when_no_flag_has_been_recorded` pins the empty-state
sentence.

## AC5 — no weakening

- The citation check (`violations`, `citation_index`, the prompt) is untouched; `testops/judgement/agent.py`
  changes only by two additive ledger functions.
- `testops/judgement/client.py` untouched.
- All TESTOPS-88/89/90/91 agent pins still pass unmodified, including the four reviewer lies, the
  citation-id mask, and the repair round.
- Full suite and `tests/contracts`: **1389 passed, 2 skipped** — 32 new pins, zero weakened.

## Files

| file | change |
|---|---|
| `testops/web/app.py` | `FLAG_SHOW`/`FLAG_HIDE`/`FLAG_ACCEPTED`, `AgentFlag`, `parse_agent_flag`, `flag_note_block`; `_agent_variant` delegates; `case_response(flag=...)` adds the one line; handler parses and records the value; `flag_values_section` on `/agent-report` |
| `testops/judgement/agent.py` | `record_flag`, `flag_values` (ledger only) |
| `testops/store/schema.sql` | `agent_flag` table and its index, additive |
| `tests/test_agent_flag.py` | 32 pins for AC1–AC4 |

## Limitations, stated plainly

- An empty `?agent=` is dropped by `urllib.parse.parse_qs` before the app sees it, so it is
  indistinguishable from an absent parameter. Both mean off and neither warns; the report labels the
  shared row `(absent or empty)` rather than claiming which it was.
- The ledger keeps the first 50 characters of a typed value. A longer value still warns on the page
  in full and still counts as one unrecognised row, shortened.
- The agent-on path is unchanged and was not re-measured live: no model call was made by this build.
  `?agent=true` now reaches exactly the code path `?agent=on` already used, which is what AC1 asks.
