# Contract suite seed

`seed.json` and `blobs/` are the rows the contract suite's **disposable** store is built from, in a
temp directory, every time the suite runs (TESTOPS-53). They are fixture input, not a deployment:
nothing in `testops/` reads them, and no test opens `data/`.

Contents:

| table | rows | why |
|---|---|---|
| `runs` | 4 | `restfulbooker-levels-20261124T123451` (newest; five cases with evidence, including the product line each verdict rests on), `restfulbooker-levels-20261123T132456` (four cases whose product arm was not assessable), `restfulbooker-levels-20261122T204917` (a run that raised nothing, for P1), `reqoverflow-dup-20261122T205100` (settled cases, for P4's comparison) |
| `snapshots` | 4 | one per run, with the recorded registry the page's "what could not be checked" section reads |
| `artefacts` / `observations` | 286 / 187 | the feature files, bindings and product source behind the restfulbooker cases (P6, P15–P19) |
| `claims` | 146 | the restfulbooker verdicts (distinct / review / unplaced / repeats product) and the reqoverflow duplicates |
| `inference` | 129 | the analysers' product record each case page reads to resolve the product line (TESTOPS-83) |
| `cases` / `findings` | 26 / 26 | five restfulbooker cases that repeat the product, four older ones ("Cannot assess" on the page) and seventeen reqoverflow duplicates ("Checked, but this repeats another test") |
| `projects` / `services` | 2 / 4 | the config page's projects-and-services listing (P21) |
| `blobs` | 187 | the feature, step-definition and product-source content the restfulbooker pages quote |

Regenerate with the generator, from a store the product has written, **read-only**:

```
python tests/contracts/seed/make_seed.py C:/Users/Chester/Projects/testops/data/testops.db
```

The generator opens the store with `mode=ro`, takes only the rows named in `RUNS`/`PROJECTS`, and
refuses to write anything credential-shaped. Treated as a slice of public evidence: restfulbooker
is `mwinteringham/restful-booker-platform` and reqoverflow is `reqnroll/Sample-ReqOverflow`.

Deliberately absent: reqoverflow's artefacts and blobs (P4 needs only the verdict block; a page
that says the source content is not in this store is a real rendered state). Inference rows for the
shipped claims **are** included: they carry the product surface and word the case page resolves the
product line from, and a page built without them would show a state no run produced.

**P20 and the soft badge class.** `app.verdict_badge` gives an `unplaced` verdict the dashed
`badge verdict soft` class, but an unplaced claim never becomes a case (no finding is raised for
it), so no case page and no case-list row can witness that class from a store alone. The seed does
contain 18 `unplaced` claims; they are reachable only as run-page placement counts ("N matched no
step binding"). Making the class observable needs a product change (a case for an unplaced claim,
or the placement summary carrying the badge); it is not something a fixture can add without
writing a case the analyser never raised.
