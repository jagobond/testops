---
id: TESTOPS-80
title: The source band says the product's routes were not consulted while the verdict is resting on them
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-73, TESTOPS-72
---

# TESTOPS-80 - The band contradicts the verdict on the same page

## Why this exists

On `case-restfulbooker-levels-20261124T114627-05` the page reads, at the top:

    Product repository  mwinteringham/restful-booker-platform at commit efe2deb8   consulted
    Product routes      mwinteringham/restful-booker-platform                       not consulted
                        none of the 3 ecosystems this build knows was recognised in the 169 files read
                        (reqnroll, python-bdd, cucumber-js)

and then, in the verdict, *"the product already declares `POST /`"*. Both cannot be true. The reasons:

1. "Product routes" is judged by the **test-ecosystem** detector (`reqnroll`, `python-bdd`, `cucumber-js`) - a list of ways
   to read *test* suites - rather than by the surface discovery result that actually produced 25 routes. A kind is being
   answered by the wrong question.
2. The count is wrong for the same reason: 169 files were read for test ecosystems; 142 `.java` files were parsed for
   routes, and 25 surfaces were found.
3. The sentence "a kind that is not tagged here was not linked to this case" still stands on the page while nothing can
   write a link, which is TESTOPS-76's absence line and must not ship twice with the same fault.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Whether the product's routes were consulted is answered by the **surface discovery state** for that snapshot - `found`, `zero` or `not_assessable` - never by the test-ecosystem detector. `found` renders the surface count and the languages read ("142 .java parsed, 25 routes"); `not_assessable` renders the reason the reader gives. Pinned per state. |
| AC2 | The page cannot contradict itself: a test asserts that when a claim's verdict is `repeats product`, the product-routes tag on the same case page is not `not consulted`; and conversely. |
| AC3 | The file count on that line is the count of files the *reader of that kind* read, not the total artefacts in the snapshot. 142 for Java, not 169. |
| AC4 | One place computes the band's facts, and the test-ecosystem line is used only for the ecosystems it can answer (whether the test suite's steps could be read). |
| AC5 | Full suite green; contract suite green; goldens regenerated deliberately and listed; a page test pins the exact sentence for each of the three states. |
