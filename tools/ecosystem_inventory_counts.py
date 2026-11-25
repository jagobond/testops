"""TESTOPS-50: recompute every counted table in docs/ecosystem-inventory-cucumber-js.md.

Read-only: the store is opened with ``mode=ro`` and nothing is written. The rules are printed
before the numbers, because a count without its rule is the defect this script exists to prevent.

The section-7 estimate table is deliberately not reproduced: its "estimate" column is engineering
judgement, not a count. The corpus facts its "counted" column cites are all printed here.

Usage:
    python tools/ecosystem_inventory_counts.py [--db PATH] [--blobs PATH]
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from collections import Counter
from pathlib import Path

SNAPSHOT = "demo-booking-20261122-262404a9"
ARM_PREFIX = ("github:m-pujic-levi9-com/cypress-cucumber-e2e-tests"
              "@262404a95784970315faeae6374ce8783ccbe598:")
PRODUCT_PREFIX = ("github:example-org/demo-booking-platform"
                  "@efe2deb8ce02db541adbf9d3a6604caf5fbdaae6:")


# ---------------------------------------------------------------- reading the store

def load_files(db: Path, blobs: Path) -> dict[str, str]:
    """path-within-arm -> text, from the store's distinct artefacts for the test arm."""
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "select distinct uri, blob_sha from artefact where snapshot_id=? and uri like ?"
            " order by uri",
            (SNAPSHOT, ARM_PREFIX + "%"),
        ).fetchall()
    finally:
        conn.close()
    files: dict[str, str] = {}
    for r in rows:
        rel = r["uri"][len(ARM_PREFIX):]
        sha = r["blob_sha"]
        files[rel] = (blobs / sha[:2] / sha[2:]).read_bytes().decode("utf-8-sig", errors="replace")
    return files


def count_product_files(db: Path) -> int:
    """Distinct product-arm artefacts whose path ends .js or .ts (the provenance line's 27)."""
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "select distinct uri from artefact where snapshot_id=? and uri like ?",
            (SNAPSHOT, PRODUCT_PREFIX + "%"),
        ).fetchall()
    finally:
        conn.close()
    return sum(1 for (uri,) in rows if uri.endswith((".js", ".ts")))


# ---------------------------------------------------------------- features

STEP_LINE = re.compile(r"^\s*(Given|When|Then|And|But)\s+(.*)$")
BLOCK_KEYWORD = re.compile(r"^\s*(Scenario Outline|Scenario|Background|Examples|Feature)\s*:")


def parse_features(files: dict[str, str]):
    """Scenarios (steps, tags), Background step lines, tag counts, feature count."""
    scenarios: list[dict] = []
    background: list[tuple[str, str]] = []
    tags: Counter[str] = Counter()
    feature_count = 0
    for path in sorted(files):
        if not path.endswith(".feature"):
            continue
        feature_count += 1
        section = "feature"
        current = None
        pending: list[str] = []
        for raw in files[path].splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("@"):
                pending.extend(t for t in line.split() if t.startswith("@"))
                continue
            m = BLOCK_KEYWORD.match(line)
            if m:
                word = m.group(1)
                if word == "Feature":
                    section, current, pending = "feature", None, []
                elif word == "Background":
                    section, current, pending = "background", None, []
                elif word in ("Scenario", "Scenario Outline"):
                    section = "scenario"
                    current = {"path": path, "outline": word == "Scenario Outline",
                               "steps": [], "tags": list(pending)}
                    scenarios.append(current)
                    for t in pending:
                        tags[t] += 1
                    pending = []
                elif word == "Examples":
                    section = "examples"
                    for t in pending:
                        tags[t] += 1
                    pending = []
                continue
            if section == "examples":
                continue
            sm = STEP_LINE.match(raw)
            if sm:
                verb, text = sm.group(1), sm.group(2).strip()
                if section == "background":
                    background.append((verb, text))
                elif section == "scenario" and current is not None:
                    current["steps"].append((verb, text))
    return {"feature_count": feature_count, "scenarios": scenarios,
            "background": background, "tag_counts": tags}


# ---------------------------------------------------------------- step definitions

DECLARATION = re.compile(
    r"^[ \t]*(?P<this>this\.)?(?P<verb>Given|When|Then|And|But)"
    r"[ \t]*\([ \t\r\n]*(?P<quote>['\"`/])", re.M)
STEP_FILE = re.compile(r"(stepdef|steps?/|\.cy\.[jt]s$|/steps/|_steps\.[jt]s$)", re.I)
CUCUMBER_IMPORT = re.compile(r"['\"][^'\"]*cucumber[^'\"]*['\"]", re.I)


def is_step_file(path: str, text: str) -> bool:
    return bool(STEP_FILE.search(path) or CUCUMBER_IMPORT.search(text))


def parse_declarations(files: dict[str, str]):
    """Declarations with their verb, pattern, file, quote style and layout."""
    out = []
    for path in sorted(files):
        if not path.endswith((".js", ".ts")) or path.endswith(".d.ts"):
            continue
        text = files[path]
        if not is_step_file(path, text):
            continue
        for m in DECLARATION.finditer(text):
            quote = m.group("quote")
            close = text.find("/", m.end()) if quote == "/" else _find_close(text, m.end(), quote)
            gap = text[text.index("(", m.start()) + 1:m.start("quote")]
            out.append({"verb": m.group("verb"), "pattern": text[m.end():close], "path": path,
                        "layout": "next-line" if "\n" in gap else "same-line", "quote": quote})
    return out


def _find_close(text: str, start: int, quote: str) -> int:
    i = start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == quote:
            return i
        i += 1
    raise ValueError("unterminated string literal")


# ---------------------------------------------------------------- custom commands

COMMAND = re.compile(r"Cypress\.Commands\.(?:add|overwrite|addAll)\s*\(\s*['\"`]([^'\"`]+)")


def strip_comments(text: str) -> str:
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))


def command_bodies(files: dict[str, str]):
    out = []
    for path in sorted(files):
        if not path.endswith(".js"):
            continue
        text = strip_comments(files[path])
        for m in COMMAND.finditer(text):
            out.append({"name": m.group(1), "path": path, "body": _balanced(text, m.end())})
    return out


def _balanced(text: str, pos: int) -> str:
    """Inner text of the first {...} block after ``pos`` (the arrow function's body)."""
    brace = text.find("{", pos)
    if brace < 0:
        return ""
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1:i]
    return ""


def declaration_body(text: str, pattern: str) -> str:
    idx = text.find(pattern)
    return "" if idx < 0 else _balanced(text, idx + len(pattern))


# ---------------------------------------------------------------- matching

BROWSER_CALL = re.compile(r"\bcy\.(?:get|contains|xpath|visit)\b|\.(?:click|type|select|trigger)\(")
HTTP_CALL = re.compile(r"\bcy\.request\b")


def permissive_regex(pattern: str) -> re.Pattern:
    """The repository's own rule (``stepbindings.pattern_to_regex``): every placeholder is a
    permissive group; everything else, parentheses included, is literal text; case-insensitive;
    anchored to the whole step."""
    p = re.escape(pattern)
    p = re.sub(r"\\\{[^}]+\\\}", "(.+?)", p)
    return re.compile("^" + p + "$", re.I)


def int_strict_regex(pattern: str) -> re.Pattern:
    """Variant: {int} is \\d+, every other placeholder is permissive."""
    p = re.escape(pattern)
    p = re.sub(r"\\\{int\\\}", r"\\d+", p)
    p = re.sub(r"\\\{[^}]+\\\}", "(.+?)", p)
    return re.compile("^" + p + "$", re.I)


def cucumber_regex(pattern: str, int_permissive: bool = False) -> re.Pattern:
    """Variant: cucumber-expression semantics - {string} a quoted string, {int} an integer,
    (text) optional, everything else literal. ``int_permissive`` widens {int} to (.+?)."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("{string}", i):
            out.append(r"""('.*?'|".*?")""")
            i += len("{string}")
        elif pattern.startswith("{int}", i):
            out.append("(.+?)" if int_permissive else r"-?\d+")
            i += len("{int}")
        elif pattern[i] == "(" and ")" in pattern[i:]:
            j = pattern.find(")", i)
            out.append("(?:" + re.escape(pattern[i + 1:j]) + ")?")
            i = j + 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$", re.I)


def matched(lines, patterns, builder) -> int:
    regs = [builder(p) for p in patterns]
    return sum(1 for text in lines if any(r.match(text) for r in regs))


# ---------------------------------------------------------------- report

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=Path("data/testops.db"))
    ap.add_argument("--blobs", type=Path, default=Path("data/blobs"))
    args = ap.parse_args()

    files = load_files(args.db, args.blobs)
    feats = parse_features(files)
    decls = parse_declarations(files)
    cmds = command_bodies(files)
    scenarios = feats["scenarios"]
    steps = [text for sc in scenarios for _, text in sc["steps"]]
    verbs = Counter(v for sc in scenarios for v, _ in sc["steps"])
    when_steps = [t for sc in scenarios for v, t in sc["steps"] if v == "When"]

    asserting: list[str] = []
    for sc in scenarios:
        after_then = False
        for v, text in sc["steps"]:
            if v == "Then":
                after_then = True
                asserting.append(text)
            elif v in ("And", "But") and after_then:
                asserting.append(text)
            else:
                after_then = False

    patterns = [d["pattern"] for d in decls]
    distinct = list(dict.fromkeys(patterns))
    duplicates = [p for p, n in Counter(patterns).items() if n > 1]
    strings = sum(1 for p in distinct if "{string}" in p)
    ints = sum(1 for p in distinct if "{int}" in p)
    none = sum(1 for p in distinct if "{" not in p)
    overlap = sum(1 for p in distinct if "{string}" in p and "{int}" in p)

    js_all = [p for p in files if p.endswith((".js", ".ts"))]
    stepdefs = [p for p in js_all if p.endswith(".stepdef.js")]
    config = [p for p in js_all if p not in stepdefs]

    print("=" * 78)
    print("TESTOPS-50 inventory recount  —  snapshot", SNAPSHOT)
    print("=" * 78)
    print()
    print("PROVENANCE")
    print(f"  test-arm artefacts read                         {len(files)}"
          f" ({feats['feature_count']} features, {len(js_all)} js/ts)")
    print(f"  product-arm .js/.ts artefacts in the snapshot    {count_product_files(args.db)}")
    print()
    print("RULES, stated before counting")
    print("  R1  One Scenario or Scenario Outline line is one scenario. Examples rows are data,")
    print("      not scenarios; a step line is counted once, not once per Examples row. Tags are")
    print("      counted on the lines attached to a Scenario, Scenario Outline or Examples block;")
    print("      tags above Feature: are feature tags and are not counted.")
    print("  R2  Step lines under Background are counted separately and excluded from every")
    print("      scenario-step denominator below. Only scenario bodies are matched in section 5.")
    print("  R3  A step matches a pattern when, after replacing every {name} placeholder with the")
    print("      permissive group (.+?) and escaping everything else (parentheses are literal),")
    print("      the pattern matches the whole step text, case-insensitively. This is exactly")
    print("      testops/extract/stepbindings.py::pattern_to_regex.")
    print("  R4  Pattern-level tables count distinct pattern texts. Matching uses the 44")
    print("      declarations, so a duplicated pattern is simply available twice; it changes no")
    print("      match count because the two declarations are identical.")
    print()
    print("SECTION 1 — the suite, in numbers")
    print(f"  feature files                                   {feats['feature_count']}")
    print(f"  scenarios                                       {len(scenarios)}")
    print(f"  steps (scenario bodies; Background excluded)    {len(steps)}"
          f" ({verbs['When']} When, {verbs['Then']} Then, {verbs['And']} And)")
    bg_verbs = Counter(v for v, _ in feats["background"])
    print(f"  Background step lines, excluded                 {len(feats['background'])}"
          f" ({bg_verbs['Given']} Given, {bg_verbs['And']} And)")
    print(f"  total step lines in the corpus                  {len(steps) + len(feats['background'])}")
    print(f"  asserting steps (Then + following And/But)      {len(asserting)}")
    print(f"  .js/.ts files in the test arm (incl. .d.ts)     {len(js_all)}")
    print(f"  — step-definition files (*.stepdef.js)          {len(stepdefs)}")
    print(f"  — support/config files (1 is index.d.ts)        {len(config)}")
    print(f"  scenario tags                                   {sum(feats['tag_counts'].values())}"
          f" ({', '.join(f'{t} {n}' for t, n in sorted(feats['tag_counts'].items()))})")
    print()
    print("SECTION 2 — binding declarations")
    print(f"  declarations                                    {len(decls)} in"
          f" {len({d['path'] for d in decls})} files")
    print("  keyword split                                   " +
          ", ".join(f"{v} {sum(1 for d in decls if d['verb'] == v)}"
                    for v in ("When", "Then", "Given", "And", "But")))
    for quote, label in (("'", "single-quoted string"), ('"', "double-quoted string"),
                         ("`", "template literal"), ("/", "regular expression")):
        print(f"  {label:<48}{sum(1 for d in decls if d['quote'] == quote)}")
    print(f"  same-line layout                                "
          f"{sum(1 for d in decls if d['layout'] == 'same-line')}")
    print(f"  pattern on the line after the parenthesis       "
          f"{sum(1 for d in decls if d['layout'] == 'next-line')}")
    print(f"  distinct patterns                               {len(distinct)} for"
          f" {len(patterns)} declarations")
    print(f"  duplicated pattern texts                        {len(duplicates)}"
          f" ({'; '.join(repr(p) + ' x' + str(Counter(patterns)[p]) for p in duplicates)})")
    print(f"  patterns mentioning {{string}} (distinct)         {strings}")
    print(f"  patterns mentioning {{string}} (declarations)     "
          f"{sum(1 for p in patterns if '{string}' in p)}")
    print(f"  {{string}} occurrences                           "
          f"{sum(p.count('{string}') for p in patterns)}")
    print(f"  patterns mentioning {{int}} (distinct)           {ints}")
    print(f"  {{int}} occurrences                              "
          f"{sum(p.count('{int}') for p in patterns)}")
    print(f"  patterns with no placeholder (distinct)         {none}")
    print(f"  patterns mentioning both {{string}} and {{int}}     {overlap}")
    print(f"  union check: {none} none + {strings} string + {ints} int - {overlap} overlap"
          f" = {none + strings + ints - overlap} distinct patterns")
    print()
    print("SECTION 3 — drivers and custom commands")
    raw = sum(len(COMMAND.findall(files[p])) for p in files if p.endswith(".js"))
    print(f"  Cypress.Commands.add|overwrite, raw regex       {raw}")
    print(f"  — of those, inside comments                     {raw - len(cmds)}")
    print(f"  real custom commands                            {len(cmds)}")
    print("  by file                                         " +
          ", ".join(f"{Path(k).name} {v}"
                    for k, v in Counter(c["path"] for c in cmds).items()))
    print(f"  commands containing cy.request in own body      "
          f"{sum(1 for c in cmds if HTTP_CALL.search(c['body']))}")
    print(f"  commands with only browser calls                "
          f"{sum(1 for c in cmds if BROWSER_CALL.search(c['body']) and not HTTP_CALL.search(c['body']))}")
    print(f"  commands that only call module-local helpers    "
          f"{sum(1 for c in cmds if not BROWSER_CALL.search(c['body']) and not HTTP_CALL.search(c['body']))}")
    print(f"  files ending *Driver.cs/.py/.ts                 "
          f"{sum(1 for p in files if re.search(r'Driver\\.(cs|py|ts)$', p))}")
    print()
    print("  the 11 commands, by the signal in their own body")
    print(f"    {'command':<24}{'file':<26}{'cy.request':>10}{'browser calls':>14}")
    for c in cmds:
        print(f"    {c['name']:<24}{Path(c['path']).name:<26}"
              f"{len(HTTP_CALL.findall(c['body'])):>10}{len(BROWSER_CALL.findall(c['body'])):>14}")
    print()
    print("  how the 44 declaration bodies reach their work")
    direct = sum(1 for d in decls
                 if BROWSER_CALL.search(declaration_body(files[d["path"]], d["pattern"])))
    http = sum(1 for d in decls
               if HTTP_CALL.search(declaration_body(files[d["path"]], d["pattern"])))
    print(f"    a browser command directly                   {direct}")
    print(f"    no browser command, no cy.request (helper)   {len(decls) - direct}")
    print(f"    cy.request directly in the step body         {http}")
    print()
    print("SECTION 4 — layer signals across the .js/.ts files")
    for label, rx in (
        ("cy.get(", r"cy\.get\("), ("cy.contains(", r"cy\.contains\("),
        ("cy.xpath(", r"cy\.xpath\("), ("cy.visit(", r"cy\.visit\("),
        (".click(", r"\.click\("), (".type(", r"\.type\("), (".select(", r"\.select\("),
        (".should(", r"\.should\("), ("cy.request(", r"cy\.request\("),
        ("cy.fixture(", r"cy\.fixture\("), ("cy.wrap(", r"cy\.wrap\("),
        (".as(", r"\.as\("), ("expect(", r"\bexpect\("),
        ("Cypress.Commands", r"Cypress\.Commands"),
        ("playwright", r"playwright"), ("supertest", r"supertest"), ("axios", r"axios"),
        ("fetch(", r"\bfetch\("), ("prisma|knex|mongoose", r"prisma|knex|mongoose"),
        ("localStorage", r"localStorage"),
    ):
        print(f"  {label:<26}{sum(len(re.findall(rx, files[p])) for p in js_all)}")
    print()
    print("SECTION 5 — the 43 distinct patterns applied to the 76 scenario steps")
    print("  R3 applies: every placeholder is a permissive group.")
    total = matched(steps, distinct, permissive_regex)
    when_n = matched(when_steps, distinct, permissive_regex)
    assert_n = matched(asserting, distinct, permissive_regex)
    print(f"  steps that match a declared pattern           {total} of {len(steps)}")
    print(f"  When steps that match                         {when_n} of {len(when_steps)}")
    print(f"  asserting steps that match                    {assert_n} of {len(asserting)}")
    print(f"  asserting steps that match nothing            {len(asserting) - assert_n} of {len(asserting)}")
    print()
    print("  Variants, printed so the sensitivity of the two auxiliary numbers is visible.")
    print("  They are not the document's rule; the asserting row is identical under all of them.")
    for label, builder in (
        ("{int} = \\d+, other placeholders permissive", int_strict_regex),
        ("cucumber-expression semantics ({string} quoted, (text) optional, {int} digits)",
         cucumber_regex),
        ("cucumber-expression semantics with {int} permissive",
         lambda p: cucumber_regex(p, int_permissive=True)),
    ):
        print(f"    {label}")
        print(f"      steps {matched(steps, distinct, builder)} of {len(steps)},"
              f" When {matched(when_steps, distinct, builder)} of {len(when_steps)},"
              f" asserting {matched(asserting, distinct, builder)} of {len(asserting)}")
    print()
    print("SECTION 7 — the estimate table is not reproducible from a corpus (it is judgement).")
    print("  The corpus facts its 'counted' column cites are the numbers above:")
    print(f"    44 declarations, {sum(1 for d in decls if d['layout'] == 'next-line')} multi-line,"
          f" 1 quote style; {len(distinct)} distinct patterns, 2 placeholder kinds;")
    print(f"    {len(stepdefs)} stepdef files, {feats['feature_count']} feature files;"
          f" {len(cmds)} commands, {len(decls) - direct} of 44 step bodies depend on them;")
    print(f"    {direct} of 44 resolvable in the body, {len(decls) - direct} one level down;"
          f" {feats['feature_count']} features, {len(scenarios)} scenarios, {len(asserting)} assertions.")
    print("  Not derivable here, and deliberately untouched (section 7 is out of this ticket's")
    print("  scope): the engineering-day figures 0.5/0.25/1.5/1/0/6.25, and the 142 .java files")
    print("  in section 7's notes - those were never fetched, so no blob can confirm them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
