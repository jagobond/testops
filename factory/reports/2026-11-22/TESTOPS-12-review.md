# TESTOPS-12 review — 2026-11-22

Corpus: run `demo-product-levels-20261122T005529` (analyser level_fitness, snapshot demo-product-levels-20261122-a3f19853-r4), 94 claims, 41 scenarios. Suite: 190 passed, 15.9s, from the project `.venv` with PYTHONPATH and VIRTUAL_ENV stripped and PYTHONNOUSERSITE=1.

## Verdict

NEEDS-FIX — the corpus holds its counts and most of its prose is the best this feature has produced, but the pass note on the two multi-label scenarios leaks a raw label into the sentence ("one is about settled by the response the server sends"), and the I1-over-api sentence upgrades the response into the store. Both are wording fixes in product code, so they need a ticket, not a merge.

## Criteria

- AC1 HOLDS. Counted on the corpus: 41 scenarios, 39 carry one label per verification pass, 2 carry two (`The audit counts what rests on a batch decision`, `The character page is server-rendered with stable fact anchors`) and both carry a pass note produced from the stored rows. Every scenario has one label, or the page says why not.
- AC2 HOLDS. A compound sentence places by its checkable half; the tested shape "the stored hash is correct and the response returns 200" places I2, and the meta half places nothing.
- AC3 HOLDS. "that number comes out right" is unplaced, as are "the report checks out" and "is correct"; the corpus holds exactly 1 unplaced, inside the ≤3 budget.
- AC4 HOLDS. Zero statements in the run begin "This test" (counted: 0). Openers now say what the assertion is about, and no statement repeats its own subject.
- AC5 HOLDS. 94 claims: 90 distinct, 1 unplaced, 1 gap, 2 review — exact. The test diffs tighten rather than weaken: assertions still check content, plus new ones for the pass note, the compound shape and the AC-b reason ban.
- AC6 HOLDS. Suite green under the clean-venv invocation; CI runs 3.11 and 3.12 plus a 3.11 render check; the zero-observation page states the count and never invents a reason ("predates observation recording" appears nowhere in the corpus).

## The prose

Six statements, verbatim, from run `demo-product-levels-20261122T005529`.

1. (distinct, settled by the response the server sends) "The assertion is about the data as stored: it reports how many admitted facts rest on a batch decision. The run only reads the responses the server sends, and that answer says what is stored, so the assertion is checked."
   The sharpest sentence in the corpus and the most problematic. "That answer says what is stored" is the open question — see below.

2. (unplaced, unclear what would settle it) "The step reads \"that count is correct for the store it was run against\". Those words judge something right without saying what it is compared with, so nothing can be said about whether it is checked."
   Reads well. Honest restraint, and quoting keeps the reader holding the actual words.

3. (gap, needs a browser) "The assertion is about what only a browser works out: each fact's citation is in an element reachable by an accessible name. Nothing short of a browser can decide it, and the run only reads the responses the server sends instead, so nothing checks it."
   Reads well. "Nothing checks it" is the right blunt register.

4. (review, settled by the page the server sends) "The assertion is about the page as served: every rendered fact sits in an element carrying a data-fact-id. The page the server sends settles it, yet the run drives a browser, so it pays for a browser that decides nothing extra."
   Reads human. "Pays for a browser that decides nothing extra" states the cost, not the blame.

5. (distinct, settled by the engine's own answer about the stored data) "The assertion is about the data as stored: the pass fails. The run only talks to the engine, whose own answer about the stored data settles it, so the assertion is checked."
   The one that reads like machine output. The colon introduces a bare three-word verdict, and the join is a stutter. A careful reader would also ask why "the pass fails" is data as stored at all — it is the engine's answer, which the second sentence does say, but the opener points the wrong way.

6. (distinct, needs a browser) "The assertion is about what only a browser works out: every interactive control exposes an accessible name. The run drives a browser, which is what decides it, so the assertion is checked."
   Reads well. Clean subject split between the two sentences.

Which read well: 2, 3, 4, 6. Machine output: 5, and the pass note (below). A careful reader challenges: 1 (the inference), 5 (opener pointing at the store for an engine answer), and the pass note.

## The open question

An I1 claim about data as stored, judged `distinct` because an HTTP response reports it. The sentence: "The run only reads the responses the server sends, and that answer says what is stored, so the assertion is checked."

Ruling: the disclosure is necessary but not sufficient. "That answer says what is stored" does exactly the upgrade the question names — it grants the response authority over the store. A handler can return cached state, computed values, or nothing that touches the store; "the API reports X" is a fact about the wire, and the sentence converts it into a fact about the disk while using "says" as if the response were the store's mouthpiece. The label is honest — "settled by the response the server sends" claims only the wire — but the statement quietly contradicts the label's modesty in the same breath.

Disclosure is the right instinct, and a paying reader can reconstruct the inference. But a disclosure the reader must undo is not a disclosure; it is the claim wearing its caveat as a footnote inside the same sentence.

There is also direct evidence the builder knows the better answer: run `demo-product-levels-20261121T230858` carried the label "settled by the data as stored, read through the response the server sends" for exactly these claims, and the final run dropped it for the blunter one. The honest form existed in the codebase's history and was removed.

The wording I would use:

  "The run only reads the responses the server sends, and takes that answer as the report of what is stored, so the assertion is checked as far as the response speaks for the store."

That keeps the I1 framing, keeps the check, and stops the response from being promoted into the store. It names the inference as an inference instead of asserting the thing the inference is only evidence for.

## Three sharpest concerns

1. "That answer says what is stored" — the upgrade, ruled on above. It is not one sentence; it is the pattern on all 72 response-labelled I1 claims in the run, and the label that disclosed it properly was dropped between runs.
2. The pass note on the multi-label scenarios renders the raw label as prose: "The run is one - one is about settled by the response the server sends; one is about needs a browser - so the answers differ..." The `_ASKS` lookup falls through to a fallback that prefixes "one is about" onto a label that already begins "settled by the", producing a sentence no reader would write.
3. "The assertion is about the data as stored: the pass fails." — the colon construction breaks down on subjectless verdict clauses; it reads like a template hiccup, which is the defect AC4 was meant to kill.

## Demo

The problem: one verification pass read as two or three stories — different label wordings for one run answering one way, restraint that only caught be-verbs, and every claim opening "This test asserts…".

What changed: the label now answers "what settles it" from the suite, not the assertion's subject; what the assertion is about moved into the statement opener; restraint recognises judgement verbs by meaning, not by a be-verb pattern; compound assertions are placed by their checkable half; the two scenarios that still carry two labels get a pass note read from the stored rows; AC-b removed the "predates observation recording" attribution the count cannot prove.

How we know it works: 190 tests pass from the clean-venv invocation; the corpus shows 90 distinct / 1 unplaced / 1 gap / 2 review over 94 claims, unchanged; "that number comes out right" is unplaced; the compound sentence places I2; both multi-label scenarios carry a pass note; zero statements begin "This test"; the reason-ban phrase appears nowhere.

What it does not solve: the response-as-store upgrade in every I1-over-api statement (ruled on above, disclosed but not reworded); the pass-note fallback leaking the raw label; the colon hiccup on bare verdict clauses.

Where to look: `testops/analysers/level_fitness.py` (`_label`, `_second`, `META_PROPERTY`), `testops/queries.py` (`pass_note_from_rows`, `_ASKS`), `testops/web/app.py` (the zero-observations paragraph, the pass-note paragraph), corpus at run `demo-product-levels-20261122T005529`, and run `demo-product-levels-20261121T230858` for the dropped label.
