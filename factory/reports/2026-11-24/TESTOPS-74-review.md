# TESTOPS-74 review — the Java reader stops guessing

2026-11-24, worktree `C:/Users/<name>/Projects/testops-t74`, branch
`factory/testops-74-java-honesty`. Store: the worktree's own `data/` only; the live store and
port 8791 were never opened. Note: the stated prior review
(`factory/reports/2026-11-24/TESTOPS-70-review.md`) does not exist at that path; the two concerns
were taken from the ticket itself, which quotes them.

## Verdict

**FAIL — two silently wrong routes still get through, both in the class of defect this ticket
exists to close.** The build's own claims are otherwise honest: the suite numbers check out
(1159 passed, 2 skipped; contract 37 passed, 2 skipped, both reproduced here from the project
`.venv` with the environment stripped), AC3, AC4, AC5 and AC6 hold under independent
reproduction, and every constant-shape case I threw at it was refused with the expression named.
But an inherited prefix read through an **interface** is dropped, and a superclass whose own
prefix is a **constant** makes the child emit the unprefixed route. Both produce a route that
does not exist, presented as one that does — the exact failure mode the ticket names. One-level
inheritance is the right promise; the refusals that bound it are not airtight.

## Getting a wrong route through

| case | result | verdict |
|---|---|---|
| superclass name held by two files in different packages | unread: `BaseController, which this repository holds more than once` | correct |
| superclass file that does not compile (unbalanced brace, `read` returns `None`) | unread: `BaseController, which this repository does not hold` | correct route, but the **reason is wrong** — see concerns |
| class extending a generic base `BaseController<Booking>` | resolved: `GET /base/{id}`, recorded in `inherited_prefixes` | correct (the `extends` reader stops at `<`) |
| prefix on an INTERFACE the class implements (`implements BookingApi`) | **`GET /{id}` emitted, no prefix, no unread, no reason** | **silently wrong — FAIL** |
| `@RequestMapping` on a nested static class used by two controllers | both controllers unread, naming `Holders.NestedController` | correct (refused, not invented) |
| subclass overriding the prefix in its own annotation | `GET /child/{id}`; the superclass is not consulted | correct |

The interface case is not hypothetical: Spring honours `@RequestMapping` on an interface a
controller implements, so `GET /{id}` is a route that does not exist. It is AC1's defect wearing
`implements` instead of `extends`, and the build's resolution loop
(`testops/surfaces/discover.py:189`) only fires when `reading.superclass` is set — `_extends`
reads `extends` and never `implements` (`java.py:292`), so an interface prefix is indistinguishable
from no prefix at all.

## Constants

All four constant shapes were refused with the expression named and no surface emitted:

- positional constant `@GetMapping(Paths.BOOKING)` → unread, detail `Paths.BOOKING`
- `value = Paths.BOOKING` → unread, detail `Paths.BOOKING`
- class-level constant prefix `@RequestMapping(Paths.CATALOGUE)` → unread, reason `class prefix is a constant`, every mapping under it refused
- mixed literal + constant `@GetMapping(Paths.PREFIX + "/{id}")` → unread, detail names `Paths.PREFIX`
- mixed array `@GetMapping({"/a", Paths.B})` → unread, detail `{ "/a" , Paths.B }` (the whole expression, not just the constant — right call)

**No branch anywhere can emit `/` as a fallback — read and confirmed.** The only `/`-producing
code is `_join` (`java.py:549`), and it returns `/` only when both prefix and path are empty; a
path is empty only when the annotation names **no path argument at all**, which is Spring's own
semantics (the mapping sits at the class prefix, and `/` is what the code says). Every
unresolvable path exits through the `Unread` return at `_path_argument`/`_routes`
(`java.py:288`, `java.py:519`) before `_join` is ever reached. There is no fallback assignment
anywhere in `java.py` or `discover.py` that substitutes `/` or `""` for an expression.

## Found-but-unplaced

Reproduced with an independent probe (not the checked-in test):

- 3 readable routes + 2 constant-path mappings → state `found`, record says `surfaces: 3` and
  `unread: 2`, and `could_not_read_lines` renders `2 mappings unread: path is a constant`, the
  two expressions (`Paths.X0`, `Paths.X1`), and the sentence that none is counted as a surface.
  Count and section cannot disagree because both come from the same record.
- only unread mappings → state **`found`**, `surfaces: 0`, the unread section renders, and
  nothing on the page reads as "found nothing": `zero` is reserved for parsed-and-empty
  (`discover.py:247`), and this record is not that. The page does not read as *nothing to see*.

## Two wordings

The noun is stored per run (`count_unit: "file"` written by `pipeline.py` beside the registry it
describes) and the sentence renders it: `returned 3 files`. Confirmed:

- a fresh run's page says `files` and the word `items` is nowhere on it (the checked-in test
  pins this; I re-verified the mechanism: `sources.py:79` records the unit, the render branches
  on the snapshot, not on today's code);
- old snapshots keep `items`: the checked-in golden `case-page-09.html` still embeds
  `returned 48 items`, and the stored-snapshot pins (95 items, 158 items) pass untouched.

**Judgement: honest, and the right call.** Two wordings in one store is only confusing if a
reader takes a sentence as a promise about every snapshot; each sentence records what *that*
snapshot was rendered with, which is the same rule every derived-from-record sentence in this
product follows. Retro-fitting would rewrite stored pages — the one thing a store that is
someone's memory must not do. The residual cost is that a reader comparing a November page and a
December page sees different nouns; a reader who checks either against its own artefact list is
not misled.

## Inheritance depth, judged

**One level is the right promise — and it must stay a promise the reader can check.** A reader of
a route list believes every listed route exists as printed. Walking the chain until it runs out
would satisfy that belief on more real projects, but it turns the reader into a project-wide type
resolver wearing a reader's clothes: generics, interfaces, diamond ambiguity, and classpath
semantics arrive one by one, each silently wrong until handled. One level, with every refusal
naming the superclass and saying "this reader reads one level", keeps the promise small enough to
be true — the route list never contains a route the reader did not compute. The build's failure
is not the depth; it is that two resolutions it *could* make under its own promise (implements,
constant parent) fall through a "no prefix to drop" branch that assumes absence-of-prefix means
absence-of-unknown. Fix the branch, not the depth.

## Corpus

**Reproduced: state `found`, 142 parsed, 25 surfaces, 0 unread, 0 inherited, 14 distinct
targets — identical to the build's numbers.** One deviation to state plainly: the build's scratch
copy of the pinned run's blob store (`data74copy`) has been pruned, and the pinned run's blobs
live in a store I was barred from, so I re-ran discovery over the corpus at source: the
`restful-booker-platform` checkout in the scratch cache is at commit `efe2deb` (verified with
`git log`) and holds exactly 142 `.java` files. Same corpus, same pinned commit, no live store
touched. No surface silently disappeared, and the reason the count does not move is as the build
says: no controller in the corpus extends anything that declares a mapping, and every mapping
path is a literal — the strict reader and the lenient one agree on this corpus because the corpus
happens to be simple. (`GET /` in the list is real: no-path mappings at class prefixes — not the
fabrication AC2 closed.)

## Three sharpest concerns

1. **An interface-borne prefix is dropped — a silently wrong route, FAIL.** Spring serves
   `@RequestMapping` declared on an interface the controller implements; this reader emits
   `GET /{id}` where the product serves `GET /booking/{id}`. Fix in the same class as AC1: read
   `implements` in `_extends`, name the interface in the resolution loop, and refuse (or resolve,
   one level, same rule) — never drop.
2. **A superclass whose own prefix is a constant makes the child silently unprefixed.**
   `BaseController` carrying `@RequestMapping(Paths.BASE)`: the child's parent has
   `own_prefix is None`, `parent.superclass` is `None`, so `discover.py:212` treats it as "no
   prefix to drop" and emits `GET /{id}`. The parent's `class_problem` is knowable at that point
   and is not consulted — the child must be unread with the parent's reason (or the same reason
   naming the parent). Same defect, different trigger.
3. **A refusal that misstates the fact.** A superclass file that exists but does not lex is
   reported as `BaseController, which this repository does not hold`. The repository *holds* it;
   this reader could not read it. Not a wrong route, but the reason is what a reader checks the
   route against, and this one sends them looking for a file that is there. One extra branch:
   `read(...) is None` for the parent file deserves its own wording.
