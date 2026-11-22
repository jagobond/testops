# TESTOPS-6 review — 2026-11-21

## Verdict

PASS — the page is a readable argument in the ticket's six-section order, the permalink and
evidence lookups are coordinate-exact and tested, and every AC I could check against the real
store holds; the one soft spot (section 3's evidence empty state on every real specimen) is a
data-collection gap outside this ticket's scope, not a rendering defect.

## Criteria

- **AC1 HOLDS.** Live render of `case-cotw-levels-20261121T215534-01` and `-02` (server on 127.0.0.1:8793)
  shows all six numbered sections in order, no `<script`, no fetch, HTML only. `test_every_v2_case_
  renders_all_six_sections_in_order` and `test_the_page_is_server_rendered_with_no_javascript_and_no_
  network` enforce it.
- **AC2 HOLDS.** The rendered permalink is
  `https://github.com/jagobond/cotw-bdd/blob/a3f19853ebfab.../features/canon_query_api.feature#L59`,
  and the store row for claim 768 carries exactly that commit and path. `blob_permalink` takes the
  commit as a parameter and returns None without one; tests prove an older-commit claim never links
  to the snapshot tip, HEAD or main.
- **AC3 HOLDS.** `evidence_for_claim` matches uri commit and path character-for-character within the
  claim's own run's snapshot; `evidence_for_subject` (the `LIKE %feature%` path) is deleted outright
  and a test asserts it can never come back. The cross-path/cross-snapshot impostor test passes.
- **AC4 HOLDS.** Section 2 reads "It is the test author's name for the scenario, not a requirement:
  nothing here was checked against one." No page implies a requirement source exists.
- **AC5 HOLDS.** Every evidence item renders `<where> — <shows>.`; `_shows` writes a real sentence
  ("the scenario "…" begins at line 14, 6 steps"). Tested; a bare link list would fail it.
- **AC6 HOLDS.** Primary text is code-free; `I4`/`KP` appear only in the footnote, explicitly
  labelled "Debugging shorthand, not part of the finding".
- **AC7 HOLDS.** "It drives the HTTP API.", "It is settled by the page the server sends.", "It needs
  a browser." — no JSON, no list reprs.
- **AC8 HOLDS.** "1 finding rides on this decision, and it applies to this case only"; the reopen
  form and copy say reopening deletes the suppression and the case reports again.
- **AC9 HOLDS.** Rendered `case-reqoverflow-dup-20261120T153431` (18 v1 claims) and
  `case-cotw-levels-20261120T195330` (41 v1 claims): every claim renders "recorded before provenance
  was captured", plus honest "not recorded" sentences for span/evidence/label/rule/action. No
  exception, no blanks.
- **AC10 HOLDS.** The 0-finding duplication case renders "This case is resolved: the analysis raised
  nothing to act on… not a claim that the code is clean"; the home page leads with "Last analysed
  38 minutes ago at cotw-bdd@a3f19853, cotw-continuity@b901ea4d".
- **AC11 HOLDS.** The home list carries full claim statements; nothing is cut mid-sentence, and
  `finding.title` is no longer read by any screen.

## The page as a reader sees it

Quoted render of `case-cotw-levels-20261121T215534-01` (verbatim, tags stripped):

> cotw · Level fitness — Open — Analysed 37 minutes ago at cotw-bdd@a3f19853, cotw-continuity@b901ea4d
> **Never actually proved**
> **1. What is asserted** — "each fact's citation is in an element reachable by an accessible name" —
> Test source: features/canon_query_api.feature:59 at commit a3f19853 — the commit this claim was read at.
> **2. Where the name came from** — This name comes from the test's own scenario title: "The character
> page is server-rendered with stable fact anchors". It is the test author's name for the scenario,
> not a requirement: nothing here was checked against one.
> **3. What the test actually does** — It drives the HTTP API. — This run recorded no observations at
> these coordinates, so the source link above is the only evidence there is.
> **4. Why that does or does not establish it** — This test asserts that each fact's citation is in an
> element reachable by an accessible name. Only a browser works that out, and this test only reads the
> responses the server sends instead, so nothing checks it. — What settles it. It needs a browser. —
> Why it was classified this way: asserts an accessibility property the browser computes.
> **5. What could not be checked** — Not connected when this claim was checked: Jira and Azure DevOps.
> They were never consulted, so nothing here says they were clean — only that this claim was never
> checked against them.
> **6. Proposed action and decision** — Move the step "each fact's citation is in an element reachable
> by an accessible name" into a test that drives a browser, or delete it; at this level nothing
> establishes what it asserts. — Decide this case — 1 finding rides on this decision, and it applies
> to this case only. [Needs a fix / Resolved / Not a real finding] — reopening deletes the suppression…
> Footnote: Debugging shorthand, not part of the finding: interaction I4; verdict gap.

Blunt judgement: this is decidable in one read. Someone who has never heard of TestOps learns what
the step says, where it lives, what the test touched, why that is not enough, what was never
consulted, and what to do — in that order, with no riddles. The one paragraph a reader will keep
tripping over is section 3's second sentence (see below).

## Three sharpest concerns

1. **Section 3's evidence sentence is true but nearly always the only thing it can say on real data.**
   In the specimen's snapshot, all 45 artefacts are `cotw-continuity` source files, every one with
   zero observations, and no artefact exists at the claim's own coordinates
   (`cotw-bdd@a3f19853:features/canon_query_api.feature`). The lookup is exact, so it correctly finds
   nothing — but the levels collector recorded no per-file observations at all, so every v2 case page
   will render the same "no observations at these coordinates" line. **Ruling: honest limitation of
   this ticket, not a gap in what the page claims.** The page asserts only what the store holds and
   says so; the gap is that the collector does not yet populate observations the page was built to
   show. That belongs in a collector ticket, and until one exists the evidence section of the
   argument is exercised only by tests, never by reality.
2. **`_repo_for_coordinates` uses a `LIKE` as a pre-filter.** It is safe (exact match completed in
   Python) but the naming invites a future reader to assume the old bug is back. A comment exists;
   keep it.
3. **`show` sentences depend on observation `key` vocabulary.** `_shows` handles `scenario:*` and
   falls back to "an observation of {key}"; the first non-scenario key type to appear will read
   awkwardly. Cosmetic, worth a line in a later ticket.

## Demo

**The problem.** The old case page opened with a bare claim heading, a template sentence, and a pile
of links whose provenance nobody could judge; the Product Owner could not tell what the claim was
alleging, where it came from, or why the links were there. Evidence resolution used
`LIKE %feature%`, so a claim in `a/x.feature` collected links from `b/x.y.feature` and from other
snapshots, and permalinks could point wherever the repo's HEAD happens to be.

**What changed.** `testops/web/app.py` renders the case as six ordered sections: verbatim assertion
with a permalink at the claim's own commit, the scenario title labelled as the test's own name, the
span and instrument in words, the classification rule in the reader's words, sources that were never
connected, and the action plus a per-case decision form that says how many findings ride on it.
`testops/queries.py` builds the permalink from the claim's own `assertion_commit` and resolves
evidence only from artefacts whose uri carries the claim's exact commit and path within the claim's
own run's snapshot — the `LIKE %feature%` resolver is deleted. `testops/links.py` gains
`blob_permalink`, which returns None rather than a branch URL when coordinates are missing. Every
absent field renders as a stated absence, never a blank and never an exception, including v1 claims.

**How we know it works.** 111 tests pass from a stripped environment (`env -u PYTHONPATH …
PYTHONNOUSERSITE=1 .venv/Scripts/python.exe -m pytest -q`). I also started the server on
127.0.0.1:8793 against the real store and read the rendered HTML: the specimen v2 case
(`case-cotw-levels-20261121T215534-01`), the review case `-02`, an 18-claim v1 duplication case and a
41-claim v1 levels case all render their sections; the permalink's commit in the href equals the
claim row's `assertion_commit`; the store holds no artefact at the specimen's coordinates, matching
the honest empty-evidence sentence.

**What it does not solve.** The collectors still record (near-)zero observations, so the evidence
section is currently proven by tests rather than fed by runs; nothing on the page verifies the
linked commit actually contains the quoted line; the reqoverflow v1 claims render honest "not
recorded" sentences but remain essentially undecidable — that needs a provenance backfill, not a
page change.

**Where to look.** `testops/web/app.py` (`claim_sections`, `section_does`, `decision_form`),
`testops/queries.py` (`evidence_for_claim`, `_repo_for_coordinates`, `case_statement`),
`testops/links.py` (`blob_permalink`), `tests/test_case_page.py`.
