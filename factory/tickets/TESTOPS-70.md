---
id: TESTOPS-70
title: A Java product reader - Spring routes and what each one claims
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-41
---

# TESTOPS-70 - The reader that stops a Java product looking empty

## Why this exists

`surfaces/discover.py` parses Python only (`LANGUAGES = {".py": "Python"}`), so against a Java product it returns no
surfaces. TESTOPS-41 already made that an honest zero - `not_assessable` with the language and file count - but honest is
not the same as useful: on the public corpus (a Java/Spring product with 142 `.java` files) the tool can judge the tests'
shape and cannot compare them against the product they test.

This closes the first half: read a **Java product** and report what it exposes, and what each part claims to do. The test
side stays out of scope; a Java test suite will still be placed only if another reader claims it.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `.java` is in `LANGUAGES` and is genuinely **parsed**, not regex-scraped into noise: `.java` files are reported as parsed, and the "unread kinds" report no longer lists them as unsupported. |
| AC2 | Spring MVC annotations produce surfaces: `@GetMapping`, `@PostMapping`, `@PutMapping`, `@PatchMapping`, `@DeleteMapping`, and `@RequestMapping` with `value`/`path` and `method`. A **class-level** `@RequestMapping("/booking")` prefixes its methods' paths; joining is pinned (`/booking` + `/` , `/booking` + `/{id}` , no class prefix). |
| AC3 | A surface's `target` reads like the Python one: `GET /booking/{id}`. Layer is `api`. Ids are stable across runs for the same source, and two methods that map the same route are two surfaces, not one - a duplicate route is a fact worth showing. |
| AC4 | **Claims** come from what the code says it does, in this order of preference: an OpenAPI annotation summary (`@Operation(summary=...)`), else the first sentence of the method's Javadoc, else the humanised method name. A method with none of these still yields a surface, with an empty claim list - and the run page must not imply the absence is a finding. |
| AC5 | The three states stay distinct: `found` (routes parsed), `zero` (Java read, no routes), `not_assessable` (nothing this reader could parse, with language counts). A Java repository with routes must never print `not_assessable`; a mixed repository reports both languages and their counts. |
| AC6 | Fixtures in `tests/` are small synthetic Spring controllers covering: class prefix + method path, multi-path annotation (`{"/a", "/b"}`), `@RequestMapping(method = RequestMethod.GET)`, a Javadoc first sentence, an `@Operation(summary=...)`, a method with no annotation (not a surface), an interface, and a `.java` file with no annotations at all (parsed, no surfaces). No network access and no clone in tests. |
| AC7 | The corpus run is re-executed against restful-booker-platform and the report states: files parsed, surfaces found, and what the surfaces are for five named routes - proving this is real reading, not a count. |
| AC8 | Full suite green; contract suite green; page promises unchanged (a product repository that now yields surfaces must not change how a **test** repository is reported); no case-page golden changes except where a run's surface count legitimately changes, and each such change is listed and explained. |
