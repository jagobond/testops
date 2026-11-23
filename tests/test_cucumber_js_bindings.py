"""TESTOPS-42C-1: the cucumber-js parsing floor.

The ticket's acceptance criteria, in tests:

  * AC1 - 44 declarations from 5 ``*.stepdef.js`` files: 26 When, 13 Then, 5 Given; each with verb,
    pattern text, file path, 1-based declaration line and suite.
  * AC2 - both layouts parse (28 same-line, 16 on the next line) and the scanner crosses the
    newline rather than scanning line by line.
  * AC3 - single quotes, double quotes and backticks parse; a regex literal is refused explicitly
    rather than silently dropped.
  * AC4 - ``pattern_to_regex``: ``{int}`` is ``\\d+``, ``{string}`` stays permissive, literal text
    stays literal, anchored and case-insensitive.
  * AC5 - the duplicate pattern resolves per-suite first and falls back only when the scenario's
    suite matches neither.
  * AC6 - six features, five step-definition files, and every feature resolves to its own suite.

The corpus tests read the build store read-only and skip when it is absent, as the other corpus
tests do.
"""
from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path

import pytest

from testops.extract import stepbindings
from testops.extract.ecosystems import cucumber_js, UnsupportedEcosystem

ROOT = Path(__file__).resolve().parents[1]
STORED = ROOT / "data" / "testops.db"
BLOB_DIR = ROOT / "data" / "blobs"

CYPRESS_SNAPSHOT = "restfulbooker-20261122-262404a9"
CYPRESS_TEST_REPO = ("m-pujic-levi9-com/cypress-cucumber-e2e-tests",
                     "262404a95784970315faeae6374ce8783ccbe598")
DUPLICATE = "Visitor will get validation/mandatory error message: {string}"


# --------------------------------------------------------------------------- AC4: the matcher

def test_int_placeholder_is_one_or_more_digits():
    regex = stepbindings.pattern_to_regex("phone with value length of {int} characters")

    assert regex.match("phone with value length of 10 characters")
    assert not regex.match("phone with value length of 4.5 characters")
    assert not regex.match("phone with value length of ten characters")


def test_string_placeholder_stays_permissive():
    regex = stepbindings.pattern_to_regex("Visitor {string} books room {string}")

    assert regex.match("Visitor Ada Lovelace books room Presidential Suite")
    assert regex.match("Visitor '' books room 101")


def test_literal_text_stays_literal():
    regex = stepbindings.pattern_to_regex("Visitor with an (invalid )email a.b")

    assert regex.match("Visitor with an (invalid )email a.b")
    # The parentheses are text, not a group; the dot is a full stop, not a wildcard.
    assert not regex.match("Visitor with an invalid email a.b")
    assert not regex.match("Visitor with an (invalid )email axb")


def test_pattern_is_anchored_and_case_insensitive():
    regex = stepbindings.pattern_to_regex("User is Logged In")

    assert regex.match("user is logged in")
    assert not regex.match("prefix user is logged in")
    assert not regex.match("user is logged in suffix")


# --------------------------------------------------------------------------- AC2/AC3: layouts

SYNTHETIC = {
    "cypress/e2e/front/booking/booking.stepdef.js": (
        "const { Given, When, Then } = require('@badeball/cypress-cucumber-preprocessor');\n"
        "Given('a same-line single-quoted step', () => {});\n"
        "When(\n"
        "  'a next-line single-quoted step',\n"
        "  () => {}\n"
        ");\n"
        "Then(\"a double-quoted step\", () => {});\n"
        "Then(`a template-literal step`, () => {});\n"
        "this.And('a World-style step', () => {});\n"
        "But('a step with \"double quotes\" inside', () => {});\n"
    )
}


def test_both_layouts_and_all_three_quoting_styles_parse():
    declarations = cucumber_js.parse_declarations(SYNTHETIC)

    assert Counter(d.layout for d in declarations) == {"same-line": 5, "next-line": 1}
    assert Counter(d.quote for d in declarations) == {"'": 4, '"': 1, "`": 1}
    assert not any(d.regex for d in declarations)
    by_verb = {(d.verb, d.pattern): d for d in declarations}
    assert ("Given", "a same-line single-quoted step") in by_verb
    assert by_verb[("When", "a next-line single-quoted step")].layout == "next-line"
    assert ("Then", "a double-quoted step") in by_verb
    assert ("Then", "a template-literal step") in by_verb
    assert ("And", "a World-style step") in by_verb
    assert by_verb[("And", "a World-style step")].world_style is True
    assert ("But", 'a step with "double quotes" inside') in by_verb


def test_declaration_lines_are_one_based_and_point_at_the_keyword():
    declarations = cucumber_js.parse_declarations(SYNTHETIC)
    lines = {d.pattern: d.line for d in declarations}

    assert lines["a same-line single-quoted step"] == 2
    assert lines["a next-line single-quoted step"] == 3
    assert lines["a double-quoted step"] == 7


def test_a_regex_literal_is_reported_unsupported_not_skipped():
    files = {"cypress/e2e/front/booking/booking.stepdef.js":
             "Given(/^a (\\d+) user is logged in$/, () => {});\n"}

    ecosystem = cucumber_js.ECOSYSTEM.detect(files)
    assert ecosystem is not None
    assert any("1 regex-literal declarations" in line and "unsupported" in line
               for line in ecosystem.evidence)
    with pytest.raises(UnsupportedEcosystem) as caught:
        cucumber_js.ECOSYSTEM.bindings(files)
    assert "regex literal" in str(caught.value)
    assert "booking.stepdef.js:1" in str(caught.value)


# --------------------------------------------------------------------------- the corpus

def _corpus() -> dict[str, str]:
    conn = sqlite3.connect(f"file:{STORED.as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "select distinct uri, blob_sha from artefact"
            " where snapshot_id = ? and uri like ? order by uri",
            (CYPRESS_SNAPSHOT, f"github:{CYPRESS_TEST_REPO[0]}@{CYPRESS_TEST_REPO[1]}:%"),
        ).fetchall()
    finally:
        conn.close()
    prefix = f"github:{CYPRESS_TEST_REPO[0]}@{CYPRESS_TEST_REPO[1]}:"
    return {uri[len(prefix):]: (BLOB_DIR / sha[:2] / sha[2:]).read_bytes()
            .decode("utf-8-sig", errors="replace")
            for uri, sha in rows}


requires_store = pytest.mark.skipif(not STORED.exists(),
                                    reason="the product store is a build artefact")


@requires_store
def test_ac1_the_corpus_yields_44_bindings_in_five_files():
    files = _corpus()
    bindings = cucumber_js.ECOSYSTEM.bindings(files)

    assert len(bindings) == 44
    assert Counter(binding.verb for binding in bindings) == {"When": 26, "Then": 13, "Given": 5}
    assert len({binding.path for binding in bindings}) == 5
    assert all(binding.path.endswith(".stepdef.js") for binding in bindings)
    assert all(binding.pattern for binding in bindings)
    assert all(binding.line >= 1 for binding in bindings)
    assert all(binding.suite for binding in bindings)
    assert all(binding.layer == "unknown" for binding in bindings), \
        "T42C-1 adds no layer vocabulary; a guessed layer would be a claim"

    for binding in bindings:
        source = files[binding.path].splitlines()
        assert binding.verb in source[binding.line - 1]
        assert binding.pattern in "\n".join(source[binding.line - 1:])


@requires_store
def test_ac2_the_corpus_has_28_same_line_and_16_next_line_declarations():
    declarations = cucumber_js.parse_declarations(_corpus())

    assert len(declarations) == 44
    assert Counter(declaration.layout for declaration in declarations) == {
        "same-line": 28, "next-line": 16}
    assert Counter(declaration.quote for declaration in declarations) == {"'": 44}


@requires_store
def test_ac3_the_corpus_is_single_quoted_and_has_no_regex_literals():
    declarations = cucumber_js.parse_declarations(_corpus())

    assert not any(declaration.regex for declaration in declarations)
    assert not any(declaration.quote != "'" for declaration in declarations)


@requires_store
def test_ac5_the_duplicate_pattern_resolves_per_suite_both_directions():
    files = _corpus()
    bindings = cucumber_js.ECOSYSTEM.bindings(files)
    duplicates = [binding for binding in bindings if binding.pattern == DUPLICATE]

    assert len(duplicates) == 2
    assert {binding.suite for binding in duplicates} == {"booking", "contact"}

    text = "Visitor will get validation/mandatory error message: 'Some message'"
    booking = stepbindings.match_step(bindings, text, "booking")
    contact = stepbindings.match_step(bindings, text, "contact")
    fallback = stepbindings.match_step(bindings, text, "login")

    assert booking is not None and booking.path.endswith("/booking.stepdef.js")
    assert contact is not None and contact.path.endswith("/contact.stepdef.js")
    # Neither booking nor contact: the any-suite fallback answers, and it is still the same text.
    assert fallback is not None and fallback.pattern == DUPLICATE
    assert fallback.suite in {"booking", "contact"}


@requires_store
def test_ac6_six_features_and_five_stepdef_files_resolve_to_their_own_suites():
    files = _corpus()
    bindings = cucumber_js.ECOSYSTEM.bindings(files)

    features = sorted(path for path in files if path.endswith(".feature"))
    stepdefs = sorted(path for path in files if path.endswith(".stepdef.js"))
    assert len(features) == 6
    assert len(stepdefs) == 5

    binding_suites = {binding.suite for binding in bindings}
    assert binding_suites == {"login", "management", "booking", "contact", "support"}
    assert len({cucumber_js.suite_of_path(path) for path in stepdefs}) == 5

    # Every feature resolves to the suite it sits in, and that suite has bindings.
    resolved = {path: cucumber_js.suite_of_path(path) for path in features}
    assert len(set(resolved.values())) == 4  # booking and contact each hold two features
    for path, suite in resolved.items():
        assert suite in binding_suites, path
        assert any(binding.suite == suite for binding in bindings), path

    # The shared background file owns no feature directory; it is reached by the fallback.
    assert resolved["cypress/e2e/features/front-page/booking/book-a-room.feature"] == "booking"
    assert "support" not in set(resolved.values())


@requires_store
def test_ac7_the_ecosystem_is_still_unsupported_so_no_claim_can_be_placed():
    ecosystem = cucumber_js.ECOSYSTEM.detect(_corpus())

    assert ecosystem is not None
    assert ecosystem.supported is False
    assert ecosystem.reason
    with pytest.raises(UnsupportedEcosystem):
        cucumber_js.ECOSYSTEM.drivers(_corpus())
