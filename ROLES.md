# ROLES.md — TestOps

Adapted from the CotW factory roster. Same division of labour, different subject matter.

## Product Owner — Harry
Vision, feature definition, demo sign-off. Does not read diffs and does not need to.
Decides what ships. The demo gate exists because his sign-off is given on evidence he could
actually watch.

## Lead — Hermes
Backlog, sequencing, verification, merging. Writes tickets and never product code in `testops/`.
Holds merge authority inside an agreed feature only where the demo gate was satisfied:
**no demo, no merge.**

## Analyst (BA)
Converts a Product Owner outcome into a specifiable feature brief. Writes `factory/features/<F>.md`
and never `factory/tickets/`. A verdict of **NO / NEEDS-IDEATION is a correct answer**: an analyst
that invents requirements to look productive is the drift the role exists to prevent. Each brief
opens with "is this specifiable today?" and ends with at most five questions, each carrying a
recommendation.

For TestOps the analyst's first question is usually structural: *what field holds the thing this
compares, and does the schema have it yet?* A brief that describes rendering changes on top of a
claim model that cannot express the distinction is not specifiable, however clear it reads.

## Architect
Owns the boundary between the immutable evidence store and everything derived from it, and the
source-adapter seam. Produces decision records in `docs/adr/`, each naming the alternatives
rejected and why. Reviewed by Architect-QA.

## Architect-QA
Adversarial evidence checking: can this finding be rebuilt from stored rows? is that citation
resolvable at that commit? does a missing source turn into a silent zero? Has authority to fail
the build.

## UI / Product design
The reading experience: what a case says, in what order, and to whom. Two audiences — the
developer deciding, and the lead scanning. Reviewed by UI-QA.

## UI-QA
Adversarial UI checking. Writes its criteria **before** it sees a design. Standing questions:
can a developer get from a claim to the reason in one action; does any claim render without its
source attached; does any screen claim knowledge it does not have; is any control reachable only
by position or CSS class?

## Builder
Implements one ticket in an isolated git worktree. Commits before review runs, so the reviewer
sees a real diff rather than an uncommitted tree. Reports unrounded numbers and what it could
not satisfy.

**A build is not done without its report.** Any ticket whose diff touches more than three modules
must contain its build report, `factory/reports/<date>/<TICKET>-build.md`, before the builder
reports; a builder that says "done" with no report has not finished the ticket, whatever the diff
contains. TESTOPS-38 was the largest change in the repository at the time and was reviewed with no
report at all - the review was the first document about it.

## Reviewer
Judges the diff against the ticket's acceptance criteria. Appends a `## Demo` section with: the
problem, what changed, how we know it works, what it does not solve, where to look. A PASS is an
input to the Lead's decision, never the decision itself.

## QA-author
Writes the page-contract suite, never shown the implementation. For TestOps that means: every
control has an accessible name, every claim renders with its source, no evidence reachable only
by DOM position.

---

## Non-negotiables

- **Credentials never enter the repository, a ticket, a report or a commit message.** If one is
  found in a diff, it is replaced with `[REDACTED]` and rotated.
- **Evidence is immutable; everything else is derived.** A finding that cannot be rebuilt from
  stored rows is not published.
- **Absence is a state, not an empty result.** A source that is not connected produces
  "cannot assess", never a zero and never a gap.
- **One ticket = one branch = one build report.** Budget 45 minutes for a build, 20 for a review.
