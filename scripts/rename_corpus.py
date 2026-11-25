#!/usr/bin/env python3
"""TESTOPS-103. Rename the demonstration corpus to neutral names, from one reviewable table.

The repository is going to an organisation that has its own repository pairs. A fixture corpus that
names a friend's book series, a band's website and a public demo project tells a reader where the
tool came from and what it was pointed at - two things a clone should not disclose. This script is
the whole rename: the table below is the ticket's map, applied to every tracked file, every path
segment, the page fixtures' SQLite store and the content-addressed seed.

Stages, in this order (``--apply`` runs all of them):

1. text      - rewrite the tracked text files. Python is handled with :mod:`tokenize`, because the
               same word is a *slug* inside a string (``"cotw"`` -> ``"demo-product"``) and an
               *identifier* outside it (``cotw = ...`` -> ``demo_product = ...``); a blind replace
               would produce a module that does not parse.
2. paths     - rename the tracked paths the table touches (``git mv``), so the fixture directory and
               the helper module it holds stop naming the thing too. A ``.py`` segment takes the
               underscored form, because a module name cannot carry a hyphen.
3. store     - rewrite the text columns of the page fixture's store (``before_v3.db``). It is
               binary, so it is not a text file, but its rows are rendered into the goldens.
4. blobs     - the evidence store (``data/``) is content-addressed as well; rewrite its blobs and
               repoint every artefact, so a page that quotes the source does not print the old name
               over a row that says the new one. ``--store`` chooses the store.
5. seed      - the contract seed is content-addressed: after a blob's text changes its filename no
               longer equals the SHA-256 of its contents. Rewrite the blob, recompute the hash,
               rename the file and repoint ``seed.json`` (and every ``blob_sha`` reference in it).
6. goldens   - re-render ``tests/fixtures/projects_services/*.html`` through the same path the tests
               use: ``app.age`` frozen to ``"a fixed time ago"``, exactly as the baseline was made.
7. digests   - re-take ``tests/fixtures/agent/off-golden.json``, the sha256 of every real case and
               run page, with the same pinned clock the gate pins.

``--check`` prints what is left of the names in the tracked tree (the attribution documents and this
script are the only permitted carriers, and are listed explicitly).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------- the map, as data
#
# Ordered: a longer name before the shorter name inside it, or the short one mangles it
# (`cotw-continuity` before `cotw`, `restful-booker` before `restfulbooker`, `CotwBdd` before
# `CotW`). Case is carried by the row, not by a rule: the upper-case tag prefix becomes the
# upper-case tag, the slug stays a slug, the display name stays a display name.
#
# Two rows are not spelled exactly as the ticket's table spells them, and both are the same
# decision - the *identifier* form of a display name. `RuckoldtAndRylander` is a repository owner
# and an ADO organisation, and an owner cannot carry spaces, so the PascalCase spelling takes the
# PascalCase target (`ExampleAndCo`) while `Ruckoldt & Rylander` takes the display form exactly as
# the table gives it. `Sample-ReqOverflow` is the upstream sample's repository name as it is used
# *as a fixture coordinate* (the repo slug the fixture corpus is stored under); the real upstream
# name survives where attribution requires it (THIRD-PARTY-NOTICES.md, PROVENANCE.md), which the
# protected spans at the bottom of this file keep intact.
TABLE: tuple[tuple[str, str], ...] = (
    ("Sample-ReqOverflow", "demo-service"),
    ("Children of the Old War", "Demo Product"),
    ("Ruckoldt & Rylander", "Example and Co"),
    ("RuckoldtAndRylander", "ExampleAndCo"),
    ("CotwBdd", "DemoProductTests"),
    ("cotw-continuity", "demo-product"),
    ("cotw-bdd", "demo-product-tests"),
    ("ReqOverflow", "DemoService"),
    ("REQOVERFLOW", "DEMO_SERVICE"),
    ("reqoverflow", "demo-service"),
    ("Restful-booker", "Demo-booking"),
    ("restful-booker", "demo-booking"),
    ("RESTFULBOOKER", "DEMO_BOOKING"),
    ("restfulbooker", "demo-booking"),
    ("COTW", "DEMO"),
    ("CotW", "Demo Product"),
    ("Cotw", "DemoProduct"),
    ("cotw", "demo-product"),
    ("mwtestconsultancy.co.uk", "example.com"),
    ("mwinteringham", "example-org"),
    ("jagobond", "example-org"),
)

# Text files whose subject is the *upstream* of a copied fixture. The MIT notice obliges
# attribution, so the real names have to survive there; everything else in the file (the local
# path of the copy, the run ids quoted from this repository) is renamed like anywhere else. Each
# span is lifted out before the map is applied and put back afterwards.
PROTECTED: dict[str, tuple[str, ...]] = {
    "THIRD-PARTY-NOTICES.md": ("reqnroll/Sample-ReqOverflow",),
    "tests/fixtures/reqoverflow/PROVENANCE.md": (
        "reqnroll/Sample-ReqOverflow",
        "ReqOverflow.Specs.API",
        "ReqOverflow.Specs.Controller",
        "ReqOverflow.Specs.WebUI",
        "ReqOverflow.Tests",
        "ReqOverflow.Web",
    ),
    "tests/test_third_party_attribution.py": (
        "reqnroll/Sample-ReqOverflow",
        "ReqOverflow.Specs.API",
        "ReqOverflow.Specs.Controller",
        "ReqOverflow.Specs.WebUI",
        "ReqOverflow.Web",
    ),
}

# The files that may still carry a name after the rename, and why. Two kinds only: the documents
# that owe upstream attribution, and the ticket and the script that *define* the map - a document
# that cannot state which names it removes cannot be reviewed.
CARRIERS = (
    "factory/tickets/TESTOPS-103.md",
    "THIRD-PARTY-NOTICES.md",
    "tests/fixtures/demo-service/PROVENANCE.md",
    "tests/test_third_party_attribution.py",
    "scripts/rename_corpus.py",
)

# The ticket is not text to rewrite: its table is the map. Every other file, including the other
# tickets and reports, is renamed like the code.
SKIP_FILES = {"factory/tickets/TESTOPS-103.md"}

BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".pdf", ".woff", ".woff2", ".db"}

# The store the page goldens are rendered from, and the goldens themselves.
FIXTURE_STORE = "tests/fixtures/projects_services/before_v3.db"
GOLDEN_DIR = "tests/fixtures/projects_services"

SEED_DIR = Path("tests/contracts/seed")


# --------------------------------------------------------------------------- text engine

def rules() -> list[tuple[str, str]]:
    return list(TABLE)


def apply_table(text: str, style: str = "text") -> str:
    """Apply the map to one string. ``style`` picks the identifier spelling for Python names."""
    for was, becomes in rules():
        target = becomes
        if style == "ident":
            target = becomes.replace("-", "_").replace(" ", "_")
        text = text.replace(was, target)
    return text


def _protect(text: str, spans: tuple[str, ...]) -> tuple[str, dict[str, str]]:
    saved: dict[str, str] = {}
    for index, span in enumerate(spans):
        if span not in text:
            continue
        token = "%%PROTECTED%d%%" % index
        saved[token] = span
        text = text.replace(span, token)
    return text, saved


def _restore(text: str, saved: dict[str, str]) -> str:
    for token, span in saved.items():
        text = text.replace(token, span)
    return text


def rewrite_python(text: str) -> str:
    """Rewrite strings and comments with the text spelling, names with the identifier spelling.

    ``tokenize`` gives exact positions, so everything that is not a string, a comment or a name is
    copied through untouched. An f-string's replacement fields are expressions and are left alone;
    only the literal text around them is rewritten.
    """
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))

    def absolute(position: tuple[int, int]) -> int:
        row, column = position
        return offsets[row - 1] + column

    edits: list[tuple[int, int, str]] = []
    # Python 3.12 tokenizes an f-string's literal text as FSTRING_MIDDLE, not as one STRING; the
    # fields between them are ordinary tokens, so their names take the identifier spelling.
    fstring_middle = getattr(tokenize, "FSTRING_MIDDLE", -1)
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        literal = False
        if token.type == tokenize.NAME:
            style = "ident"
        elif token.type in (tokenize.STRING, tokenize.COMMENT):
            style, literal = "text", token.type == tokenize.STRING
        elif token.type == fstring_middle:
            style = "text"
        else:
            continue
        if not any(was in token.string for was, _ in TABLE):
            continue
        piece = token.string
        if style == "text" and literal:
            piece = _rewrite_string_literal(piece)
        else:
            piece = apply_table(piece, style)
        if piece == token.string:
            continue
        edits.append((absolute(token.start), absolute(token.end), piece))

    for start, end, piece in reversed(edits):
        text = text[:start] + piece + text[end:]
    return text


_FSTRING = re.compile(r"(?i)^[rubf]*f[rubf]*['\"]")


def _rewrite_string_literal(literal: str) -> str:
    """Rewrite a string literal's text, but not the expressions inside an f-string's braces."""
    if not _FSTRING.match(literal) or "{" not in literal:
        return apply_table(literal)
    protected: list[str] = []

    def hold(match: re.Match) -> str:
        protected.append(match.group(0))
        return "%%FIELD%d%%" % (len(protected) - 1)

    held = re.sub(r"\{\{[^{}]*\}\}|\{[^{}]*\}", hold, literal)
    held = apply_table(held)
    for index, field in enumerate(protected):
        held = held.replace("%%FIELD%d%%" % index, field)
    return held


def protection(relative: str) -> tuple[str, ...]:
    """The protected spans for a tracked path, whichever side of the rename it is named from."""
    for key, spans in PROTECTED.items():
        if relative in (key, renamed_path(key)):
            return spans
    return ()


def rewrite_text(path: Path, relative: str, apply: bool = True) -> bool:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    protected, saved = _protect(text, protection(relative))
    if path.suffix == ".py":
        rewritten = rewrite_python(protected)
    else:
        rewritten = apply_table(protected)
    rewritten = _restore(rewritten, saved)
    if rewritten == text:
        return False
    if apply:
        path.write_bytes(rewritten.encode("utf-8"))
    return True


# --------------------------------------------------------------------------- stage 1: text

def tracked_files() -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    return [name for name in result.stdout.decode("utf-8", "replace").split("\0") if name]


def stage_text(apply: bool) -> int:
    changed = 0
    for relative in tracked_files():
        path = ROOT / relative
        if path.suffix.lower() in BINARY_SUFFIXES or relative in SKIP_FILES:
            continue
        if not path.is_file():
            continue
        if rewrite_text(path, relative, apply):
            changed += 1
    return changed


# --------------------------------------------------------------------------- stage 2: paths

def renamed_path(relative: str) -> str:
    parts = []
    for segment in Path(relative).parts:
        new = apply_table(segment)
        if new.endswith(".py"):
            new = new.replace("-", "_")
        parts.append(new)
    return "/".join(parts)


def stage_paths(apply: bool) -> int:
    moves = [(relative, renamed_path(relative)) for relative in tracked_files()
             if renamed_path(relative) != relative]
    if apply:
        for old, new in moves:
            target = ROOT / new
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "mv", "--", old, new], cwd=ROOT, check=True)
    return len(moves)


# --------------------------------------------------------------------------- stage 3: the store

def stage_store(apply: bool, path: Path | None = None) -> int:
    path = path or (ROOT / FIXTURE_STORE)
    if not path.is_file():
        return 0
    conn = sqlite3.connect(str(path))
    changed = 0
    try:
        conn.row_factory = sqlite3.Row
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
        for table in tables:
            columns = [row[1] for row in conn.execute('PRAGMA table_info("%s")' % table)]
            rows = [dict(row) for row in conn.execute('SELECT rowid AS _rowid, * FROM "%s"' % table)]
            for row in rows:
                updates = {}
                for column in columns:
                    value = row[column]
                    if not isinstance(value, str):
                        continue
                    new = apply_table(value)
                    if new != value:
                        updates[column] = new
                if not updates:
                    continue
                changed += 1
                if apply:
                    assignments = ", ".join('"%s" = ?' % column for column in updates)
                    conn.execute('UPDATE "%s" SET %s WHERE rowid = ?' % (table, assignments),
                                 list(updates.values()) + [row["_rowid"]])
        if apply:
            conn.commit()
            # The schema's own text is stored verbatim in `sqlite_master`, comments included, and
            # this fixture was created when those comments named the corpus. Rewriting them is the
            # only way the file stops carrying the names; `writable_schema` is how sqlite allows a
            # change to that table, and `integrity_check` is what proves it survived.
            stored = [(name, apply_table(sql)) for name, sql in conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL")]
            schema_changes = [(sql, name) for name, sql in stored
                              if conn.execute("SELECT sql FROM sqlite_master WHERE name = ?",
                                              (name,)).fetchone()[0] != sql]
            if schema_changes:
                conn.execute("PRAGMA writable_schema = ON")
                for sql, name in schema_changes:
                    conn.execute("UPDATE sqlite_master SET sql = ? WHERE name = ?", (sql, name))
                conn.execute("PRAGMA writable_schema = OFF")
                conn.commit()
            # VACUUM, not tidiness: a rewritten row leaves its old text in a free page, and the
            # guard reads this file's bytes. Compacting is what makes the store stop carrying names.
            conn.execute("VACUUM")
            verdict = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if verdict != "ok":
                raise SystemExit("the store did not survive the rewrite: %s" % verdict)
    finally:
        conn.close()
    return changed


# --------------------------------------------------------------------------- stage 4: the seed

def stage_seed(apply: bool) -> int:
    seed_path = ROOT / SEED_DIR / "seed.json"
    blob_dir = ROOT / SEED_DIR / "blobs"
    if not seed_path.is_file():
        return 0
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    replaced: dict[str, str] = {}
    renamed = 0
    for sha in seed.get("blobs") or []:
        source = blob_dir / sha
        if not source.is_file():
            raise SystemExit("seed names a blob that is not there: %s" % sha)
        raw = source.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        rewritten = apply_table(text)
        digest = hashlib.sha256(rewritten.encode("utf-8")).hexdigest()
        if digest == sha:
            continue
        renamed += 1
        replaced[sha] = digest
        if apply:
            (blob_dir / digest).write_bytes(rewritten.encode("utf-8"))
            source.unlink()
    if not apply:
        return renamed

    # Every 64-hex string in the seed is a blob reference; the ones whose contents changed take
    # their new name, the rest are left exactly as they are.
    def repoint(match: re.Match) -> str:
        key = match.group(0) or ""
        return replaced.get(key, key)

    # The same JSON make_seed.py writes: indent=1, sorted keys, no trailing newline.
    text = json.dumps(seed, ensure_ascii=False, indent=1, sort_keys=True)
    text = re.sub(r"[0-9a-f]{64}", repoint, text)
    # The map applies to the seed too: project slugs, run ids, artefact URIs, quoted statements.
    # The upstream sample's coordinate is a fixture fact, not a home-grown name, and is left alone.
    rewritten, saved = _protect(text, ("reqnroll/Sample-ReqOverflow",))
    rewritten = _restore(apply_table(rewritten), saved)
    seed_path.write_text(rewritten, encoding="utf-8")
    return renamed


# --------------------------------------------------------------------------- stage 5: the store's blobs

# A blob is quoted source, and the spelling a name takes depends on what the file is. Python is
# parsed with the same tokenizer the tree pass uses: `from cotw.citation import ...` is a module
# name, and a module name cannot carry a hyphen, so it takes `demo_product` while the docstring
# above it takes `Demo Product`. Every other language in this corpus names the project in strings
# and comments only, where the slug spelling is the one a reader expects.
PYTHON = ".py"


def blob_text(text: str, suffix: str) -> str:
    return rewrite_python(text) if suffix == PYTHON else apply_table(text)


def stage_blobs(apply: bool, store: Path | None = None) -> int:
    """Rewrite the evidence store's own blobs, and repoint every artefact at its new hash.

    The store is content-addressed too: ``artefact.blob_sha`` is the name of a file under
    ``data/blobs/<xx>/<rest>``. A page renders the quoted source straight out of that file, so a
    blob still holding the old names would print them on the page even though the row beside it says
    ``demo-product``. Rewriting the text without re-hashing would break the store's addressing, so
    the two moves go together, exactly as they do for the contract seed.
    """
    store = store or (ROOT / "data" / "testops.db")
    if not store.is_file():
        return 0
    blob_dir = store.parent / "blobs"
    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    renamed = 0
    try:
        # A blob may be quoted by several artefacts; the suffix that decides the spelling is the
        # last one to claim it, and they agree, because a blob's bytes are its identity.
        suffix = {}
        for row in conn.execute("SELECT uri, blob_sha FROM artefact WHERE blob_sha IS NOT NULL"):
            suffix[row["blob_sha"]] = Path(row["uri"].rsplit(":", 1)[-1]).suffix
        for sha, one in sorted(suffix.items()):
            source = blob_dir / sha[:2] / sha[2:]
            if not source.is_file():
                continue
            try:
                text = source.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                continue
            rewritten = blob_text(text, one)
            digest = hashlib.sha256(rewritten.encode("utf-8")).hexdigest()
            if digest == sha:
                continue
            renamed += 1
            if apply:
                target = blob_dir / digest[:2] / digest[2:]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(rewritten.encode("utf-8"))
                source.unlink()
                conn.execute("UPDATE artefact SET blob_sha = ? WHERE blob_sha = ?", (digest, sha))
        if apply:
            conn.commit()
    finally:
        conn.close()
    return renamed


# --------------------------------------------------------------------------- stage 6: goldens

def stage_goldens(apply: bool) -> int:
    sys.path.insert(0, str(ROOT))
    from testops import config  # noqa: F401  (the migration reads it)
    from testops.store import db
    from testops.web import app

    fixtures = ROOT / GOLDEN_DIR
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as scratch:
        store = Path(scratch) / "store.db"
        shutil.copyfile(fixtures / manifest["store"], store)
        db.connect(store).close()          # the tests copy the store and migrate it the same way
        app.age = lambda iso: "a fixed time ago"
        conn = db.connect(store)
        try:
            pages = {"index.html": app.index(conn), "runs.html": app.runs_index(conn)}
            for case_id in manifest["cases"]:
                pages["%s.html" % case_id] = app.case_page(conn, case_id)
        finally:
            conn.close()
    if apply:
        for name, rendered in pages.items():
            (fixtures / name).write_bytes(rendered)
    return len(pages)


# --------------------------------------------------------------------------- stage 6: page digests

AGENT_GOLDEN = "tests/fixtures/agent/off-golden.json"
PINNED_NOW = "2026-11-24T12:00:00+00:00"


def stage_digests(apply: bool) -> int:
    """Re-take the agent-off page digests, with the clock pinned the way the gate pins it.

    ``tests/test_agent_case.py`` and its two siblings compare the *bytes* of every real case and run
    page with a sha256 taken at 2026-11-24T12:00Z. The rename changes those bytes on purpose (the
    page carries the project slug, the run id and the tag prefix), so the digests are re-taken here,
    through the same render path and the same pinned clock, rather than being declared stale.
    """
    sys.path.insert(0, str(ROOT))
    import datetime as dt
    import hashlib
    import os

    from testops.web import app

    class Fixed(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 11, 24, 12, 0, 0, tzinfo=dt.timezone.utc)

    class Shim:
        datetime = Fixed
        timezone = dt.timezone
        timedelta = dt.timedelta
        date = dt.date

    golden_path = ROOT / AGENT_GOLDEN
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    store = ROOT / "data" / "testops.db"
    if not store.is_file():
        return 0
    previous = (app.dt, os.getcwd())
    app.dt = Shim
    os.chdir(ROOT)
    conn = sqlite3.connect("file:%s?mode=ro" % store.as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    changed = 0
    try:
        for case_id in sorted(golden["cases"]):
            if conn.execute("SELECT 1 FROM case_ WHERE id = ?", (case_id,)).fetchone() is None:
                continue
            digest = hashlib.sha256(app.case_page(conn, case_id)).hexdigest()
            if digest != golden["cases"][case_id]:
                golden["cases"][case_id] = digest
                changed += 1
        for run_id in sorted(golden["runs"]):
            if conn.execute("SELECT 1 FROM run WHERE id = ?", (run_id,)).fetchone() is None:
                continue
            digest = hashlib.sha256(app.run_page(conn, run_id)).hexdigest()
            if digest != golden["runs"][run_id]:
                golden["runs"][run_id] = digest
                changed += 1
    finally:
        conn.close()
        app.dt, cwd = previous
        os.chdir(cwd)
    if apply and changed:
        golden["pinned_now"] = PINNED_NOW
        golden_path.write_text(json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True)
                               + "\n", encoding="utf-8")
    return changed


# --------------------------------------------------------------------------- --check

def forbidden_pattern() -> re.Pattern:
    names = sorted({was for was, _ in TABLE}, key=len, reverse=True)
    return re.compile(r"(?i)(%s)" % "|".join(re.escape(name) for name in names))


def stage_check() -> int:
    pattern = forbidden_pattern()
    carriers = {name for key in CARRIERS for name in (key, renamed_path(key))}
    hits = 0
    for relative in tracked_files():
        path = ROOT / relative
        if path.suffix.lower() in BINARY_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        found = sorted({match.group(1).lower() for match in pattern.finditer(text)})
        if not found:
            continue
        marker = "carrier" if relative in carriers else "UNEXPECTED"
        print("%-48s %-11s %s" % (relative, marker, ", ".join(found)))
        if relative not in carriers:
            hits += 1
    print("%d unexpected carrier(s)" % hits)
    return 1 if hits else 0


# --------------------------------------------------------------------------- main

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write the changes")
    parser.add_argument("--check", action="store_true", help="report names left in the tree")
    parser.add_argument("--only", default="", help="run one stage: text, paths, store, seed, goldens")
    parser.add_argument("--store", default="",
                        help="rewrite this store's text columns (default: the page fixture store)")
    args = parser.parse_args(argv)

    if args.check:
        return stage_check()

    stages = {
        "text": stage_text,
        "paths": stage_paths,
        "store": lambda apply: stage_store(apply, Path(args.store) if args.store else None),
        "blobs": lambda apply: stage_blobs(apply, Path(args.store) if args.store else None),
        "seed": stage_seed,
        "goldens": stage_goldens,
        "digests": stage_digests,
    }
    chosen = [args.only] if args.only else list(stages)
    if not args.apply:
        print("dry run (pass --apply to write)")
    for name in chosen:
        count = stages[name](args.apply)
        print("%-8s %5d %s" % (name, count, "changed" if args.apply else "would change"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())