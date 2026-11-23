# What the pages promise a reader

_Written for TESTOPS-7. This is the whole brief. If you read the application's source, its templates, its goldens or its
existing page tests, this suite stops being independent evidence — so don't._

## Who reads these pages

Two people, neither of whom wrote the tool:

- **A developer** who has been told "your tests are testing at the wrong level" and wants to know whether to believe it,
  what the evidence is, and what to do next.
- **A lead or manager** who wants to know what was analysed, what could not be, and whether the tool is guessing.

Neither will read the source of the tool. Neither will be told what a badge means. Everything they need must be on the
page, in words they already know.

## Promises that hold on every page

1. **Nothing is silent.** If a page has nothing to show, it says why: no runs yet, no findings in this run, a store that
   could not be opened. A blank page, an empty section or a solitary "0" with no explanation is a broken promise.
2. **A number always says what it counts.** "17" alone is not acceptable; "17 of 43 assertions placed" is. If a count is
   of files, it says files; if of cases, cases.
3. **Unread is never dressed as read.** Wherever the tool depends on files it could not open, the page must say so with a
   count and the kind of file — on that page, not on a separate one, and not only when it changes the verdict.
4. **Certainty and uncertainty look different.** A conclusion the tool is sure of and a conclusion it could not reach
   must be visibly distinguishable without reading a legend. "Cannot tell" must never be styled as settled.
5. **Every page is reachable and every page leads somewhere.** From the front page a reader can reach a run, from a run
   its cases, and from a case back to its run. No dead ends, no page that only exists if you already know its URL.
6. **A URL is stable enough to cite.** A reader can paste a case or run URL into a ticket and the recipient sees the same
   thing.

## The front page

7. A reader arriving for the first time can tell **what this tool analyses** and **what exists right now** — how many
   projects, runs, cases — without being taught any vocabulary.

## The runs index

8. Each run is distinguishable at a glance: which project, which repositories and commits, when it ran, and how much it
   found. Two runs of the same project at different commits must be tellable apart.
9. A run that found nothing and a run that failed are **different things** and must not look the same.

## A run page

10. It says **what was read**: per repository, how many files of each kind were read, including explicit zeroes. "Read 48
    test files and 0 product files" is a promise; "code and tests were consulted" is not.
11. It says **what each repository was read as** — which language/framework family the tool recognised — and says plainly
    when it recognised none, rather than implying the repository was empty or irrelevant.
12. It says **what was skipped**, by kind and count, whenever files were not read for any reason.
13. It says **what it placed and what it could not**, and for anything unplaced, why — in a sentence a reader can act on.
14. It never awards a repository credit for analysis it did not perform. **Observable form:** a repository that
    contributed no evidence must not be presented as supporting the conclusion - if a verdict's supporting evidence comes
    only from one repository, the other must not be described as though it confirmed anything. _(Amended after T7: the
    first phrasing named an internal attribution no page exposes, so a blind author could not test it.)_

## A case page

15. The **claim** is stated in one sentence a developer can act on, in the developer's own words rather than the tool's
    internal vocabulary.
16. The **verdict** is one word plus enough context to know what it means: what the tool believes, and what evidence
    would change its mind.
17. The **evidence** is traceable: which repository and commit, which file and which line the reader would open to check
    it themselves.
18. It says whether **everything needed was readable**. A conclusion drawn from a partial read must say so on the page.
19. There is a way to **record a decision** about the claim, and the page states what that decision will and will not
    cover on later runs.
20. A claim that could not be placed must look **less settled** than one that could — visibly, without a legend.

## The config page

21. A reader can see which projects exist and which resources belong to each one.
22. Adding a project or a resource does not require a code change or a restart, and the page says what it needs.
23. It **refuses to store anything that looks like a credential** (a token, a key, a password) and says why, in words
    that do not blame the reader.
24. Existing data survives an edit: changing one thing does not silently blank another.

## Out of scope

Do not test colour, spacing, fonts, layout at specific widths, exact wording, or speed. Testing those would pin things
the reader does not depend on and would fail for the wrong reasons.

## How the result is judged

Every failure is one of two things, and both are useful:

- **the page breaks a promise** a reader relies on, or
- **this brief promised more than any page could deliver**, in which case the brief is wrong and gets corrected.

Report the first run as it comes out. A suite that has been adjusted until it is green has told us nothing.
