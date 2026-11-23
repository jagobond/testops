"""TESTOPS-42C-2: the inference - commands, helpers, and the layer where it happens.

The ticket's acceptance criteria, in tests:

  * AC1 - ``drivers()`` returns the 11 real ``Cypress.Commands.add`` registrations (15 raw less 4
    inside comments) with file, name and body, and the four commented ones are excluded **by
    parsing**: the same exclusion works when a comment and a live registration sit in one file.
  * AC2 - a JS/TS signal table exists separate from ``SIGNALS``, holds the required tokens, and
    ``LAYER_ORDER`` is still the shared one.
  * AC3 - step body -> custom command -> one level of module-local helper -> ``cy.*``; where
    nothing resolves the answer is ``unknown`` **with the reason recorded**.
  * AC4 - the layer is per command: ``loginViaApi``/``loginViaUI`` and
    ``createRoom``/``createRoomViaApi`` resolve differently inside one file each.
  * AC5 - the .NET signals that fire on JS by accident are closed: ``\\bRepository\\b`` is not
    storage in JS, and the "Playwright" signal is not JS Playwright support.
  * AC6 - still no placement: the ecosystem is unsupported, so nothing is claimed.

Plus the two carried-over items from the T42C-1 review:

  * a pattern split across a string concatenation is refused, never returned truncated;
  * (the second is the inventory document's stem-rule correction, which is a document fix).

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

COMMENTED_OUT = {"login", "drag", "dismiss", "visit"}
REAL_COMMANDS = {
    "loginViaApi", "loginViaUI",
    "createRoom", "createRoomViaApi", "deleteBookingViaApi", "deleteAllBookingsViaApi",
    "deleteRoomViaApi", "deleteAllRoomsViaApi",
    "bookRoom", "bookRoomWithNoDates", "sendMessage",
}


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


def _bindings(files: dict[str, str]) -> dict[str, stepbindings.Binding]:
    return {binding.pattern: binding for binding in cucumber_js.ECOSYSTEM.bindings(files)}


def _commands(files: dict[str, str]) -> dict[str, cucumber_js.CustomCommand]:
    """``drivers()`` typed for the tests: the protocol return is deliberately open (a .NET driver
    map is name -> layer, a command map is name -> record)."""
    out: dict[str, cucumber_js.CustomCommand] = {}
    for name, command in cucumber_js.ECOSYSTEM.drivers(files).items():
        assert isinstance(command, cucumber_js.CustomCommand), name
        out[name] = command
    return out


# --------------------------------------------------------------------------- AC1: the commands

def test_ac1_the_corpus_yields_the_11_real_commands_with_file_and_body():
    commands = _commands(_corpus())

    assert set(commands) == REAL_COMMANDS
    assert set(commands) & COMMENTED_OUT == set()
    for command in commands.values():
        assert isinstance(command, cucumber_js.CustomCommand)
        assert command.path.endswith(".js")
        assert "/custom-commands/" in command.path
        assert command.line >= 1
        assert command.body.strip(), command.name
        # The body is the registration's own body, not the rest of the file.
        assert len(command.body.splitlines()) <= 25, command.name
    # 6 of the 11 make an HTTP request in their own body; 1 is browser-only and 4 reach cy.*
    # through helpers - the inventory's §3 split, now measured from the parsed bodies.
    assert sum(1 for c in commands.values() if "cy.request(" in c.body) == 6
    assert sum(1 for c in commands.values() if c.layer == "ui") == 5
    assert sum(1 for c in commands.values() if c.layer == "api") == 6


@requires_store
def test_ac1_15_raw_occurrences_less_the_4_in_comments():
    files = _corpus()
    raw = sum(len(cucumber_js.CUSTOM_COMMAND.findall(text))
              for path, text in files.items() if path.endswith(".js"))
    commands = _commands(files)

    assert raw == 15
    assert len(commands) == 11
    assert raw - len(commands) == 4


def test_ac1_a_commented_registration_is_excluded_by_parsing_not_by_file():
    # Both registrations are in the SAME file: nothing here can be excused by "that file is the
    # sample header". Only the position inside a comment excludes the first one.
    files = {"cypress/support/mixed.js": (
        "// Cypress.Commands.add('ghost', () => { cy.visit('/'); })\n"
        "/* Cypress.Commands.add('phantom', () => { cy.request('/x'); })\n"
        "   Cypress.Commands.overwrite('visit', () => {})\n"
        "   Cypress.Commands.add('phantomTwo', () => {}) */\n"
        "Cypress.Commands.add('real', () => { cy.get('#a').click(); })\n"
    )}

    commands = _commands(files)

    assert list(commands) == ["real"]
    assert commands["real"].layer == "ui"
    # ... and the raw regex still sees all five, which is why the corpus count was 15 and not 11.
    assert len(cucumber_js.CUSTOM_COMMAND.findall(list(files.values())[0])) == 5


def test_ac1_a_command_declaring_prevsubject_options_is_read_past_the_options_object():
    files = {"cypress/support/child.js": (
        "Cypress.Commands.add('dismiss', { prevSubject: 'optional' }, (subject) => {\n"
        "  cy.get('#close').click();\n"
        "});\n")}

    command = _commands(files)["dismiss"]

    assert command.body.strip() == "cy.get('#close').click();"
    assert command.layer == "ui"


# --------------------------------------------------------------------------- AC2: the vocabulary

def test_ac2_the_js_table_is_separate_from_signals_and_holds_the_required_tokens():
    assert cucumber_js.JS_SIGNALS is not stepbindings.SIGNALS
    assert set(cucumber_js.JS_SIGNALS["ui"]) == {
        "cy.get", "cy.contains", "cy.xpath", "cy.visit", ".click", ".type", ".select", ".should"}
    assert set(cucumber_js.JS_SIGNALS["api"]) == {"cy.request", "supertest", "axios", "fetch("}
    assert set(cucumber_js.JS_SIGNALS["storage"]) == {"prisma", "knex", "mongoose"}
    # The layer names and their order stay shared: they are the vocabulary the verdicts use.
    assert cucumber_js.LAYER_ORDER is stepbindings.LAYER_ORDER


def test_ac2_every_required_token_is_a_pattern_on_the_real_call_form():
    cases = {
        "cy.get('#room').should('be.visible');": "ui",
        "cy.contains('Room #');": "ui",
        "cy.xpath('//button').click();": "ui",
        "cy.visit('/#/admin');": "ui",
        "$('#a').type('x');": "ui",
        "$('#a').select('Single');": "ui",
        "cy.request({ method: 'POST', url: '/room/' });": "api",
        "const s = supertest(app);": "api",
        "axios.get(url);": "api",
        "const r = await fetch(url);": "api",
        "prisma.room.findMany();": "storage",
        "const db = knex({ client: 'pg' });": "storage",
        "mongoose.model('Room');": "storage",
    }
    for text, expected in cases.items():
        assert cucumber_js.infer_layer_from_body(text) == expected, text


# --------------------------------------------------------------------------- AC3: the chain

CHAIN = {
    "cypress/support/custom-commands/login.js": (
        "const enterUserName = (username) => {\n"
        "  cy.get('#username').type(username);\n"
        "};\n"
        "Cypress.Commands.add('loginViaUI', (username, password) => {\n"
        "  enterUserName(username);\n"
        "});\n"
        "Cypress.Commands.add('loginViaApi', (username, password) => {\n"
        "  cy.request({ method: 'POST', url: '/auth/login' });\n"
        "});\n"
    ),
    "cypress/e2e/features/admin-panel/login/login.stepdef.js": (
        "const { Given, When } = require('@badeball/cypress-cucumber-preprocessor');\n"
        "Given('a user is logged in', () => {\n"
        "  cy.loginViaApi('admin', 'password');\n"
        "});\n"
        "When('the admin logs in', () => {\n"
        "  cy.loginViaUI('admin', 'password');\n"
        "});\n"
    ),
}


def test_ac3_a_step_resolves_through_a_command_and_one_helper():
    rows = _bindings(CHAIN)

    api = rows["a user is logged in"]
    ui = rows["the admin logs in"]

    assert api.layer == "api"
    assert "cy.loginViaApi()" in api.layer_via
    assert "cy.loginViaApi() -> cy.request" in api.layer_via
    assert api.layer_reason == ""

    assert ui.layer == "ui"
    assert "cy.loginViaUI()" in ui.layer_via
    assert "cy.loginViaUI() -> enterUserName()" in ui.layer_via
    assert "cy.loginViaUI() -> cy.get" in ui.layer_via


def test_ac3_one_level_of_helper_only_a_second_hop_is_not_followed():
    files = {"cypress/e2e/x/step.stepdef.js": (
        "const inner = () => {\n  cy.get('#x').click();\n};\n"
        "const outer = () => {\n  inner();\n};\n"
        "Cypress.Commands.add('deep', () => {\n  outer();\n});\n"
        "When('the deep way', () => {\n  cy.deep();\n});\n")}

    rows = _bindings(files)
    binding = rows["the deep way"]

    # `outer` is one level down and reaches no signal; `inner` is two levels down and is not
    # followed. The answer is an honest unknown, not a guess that arrives by searching further.
    assert binding.layer == "unknown"
    assert "outer()" in binding.layer_reason


def test_ac3_an_unresolvable_body_is_unknown_with_its_reason_recorded():
    files = {"cypress/e2e/x/step.stepdef.js": (
        "When('a step that only asserts a value', () => {\n  expect(1).to.eq(1);\n});\n"
        "When('a step that calls an unknown command', () => {\n  cy.noSuchCommand();\n});\n"
        "When('a step that does nothing', () => {});\n"
    )}

    rows = _bindings(files)

    assert rows["a step that only asserts a value"].layer == "unknown"
    assert "no cy.* command" in rows["a step that only asserts a value"].layer_reason
    assert rows["a step that calls an unknown command"].layer == "unknown"
    assert "cy.noSuchCommand()" in rows["a step that calls an unknown command"].layer_reason
    assert rows["a step that does nothing"].layer == "unknown"
    assert rows["a step that does nothing"].layer_reason
    for binding in rows.values():
        assert binding.layer_reason, "an unknown without a reason is the dead end this refuses"
        assert binding.layer_via == ()


def test_ac3_a_step_delegation_says_so_instead_of_inheriting_a_layer():
    files = {"cypress/e2e/x/step.stepdef.js": (
        "const { When, Step } = require('@badeball/cypress-cucumber-preprocessor');\n"
        "When('a bookable room exists', () => {\n"
        "  Step(this, `a ${'room'} exists`);\n"
        "});\n")}

    binding = _bindings(files)["a bookable room exists"]

    assert binding.layer == "unknown"
    assert "Step(this" in binding.layer_reason


# --------------------------------------------------------------------------- AC4: per command

@requires_store
def test_ac4_two_commands_in_one_file_resolve_to_different_layers():
    commands = _commands(_corpus())

    login = commands["loginViaUI"], commands["loginViaApi"]
    room = commands["createRoom"], commands["createRoomViaApi"]

    assert login[0].path == login[1].path, "the test is only meaningful inside one file"
    assert login[0].layer == "ui" and login[1].layer == "api"
    assert room[0].path == room[1].path
    assert room[0].layer == "ui" and room[1].layer == "api"
    # The API command reaches HTTP through plumbing, not through a single obvious call: its body
    # also holds `cy.get('@roomIds')`, an alias retrieval that must not read as a browser command.
    assert "cy.request" in room[1].via


@requires_store
def test_ac4_two_bindings_resolve_to_different_layers_by_the_command_they_call():
    rows = _bindings(_corpus())

    ui = rows["User creates new {string} type {string} room {string} priced at {string} GBP with "
              "{string}"]
    api = rows["User has created {string} type {string} room {string} priced at {string} GBP "
               "with {string}"]

    assert ui.layer == "ui" and api.layer == "api"
    assert ui.suite == "management" and api.suite == "support"


@requires_store
def test_ac4_the_corpus_layer_split_is_31_ui_2_api_and_11_unknown():
    bindings = cucumber_js.ECOSYSTEM.bindings(_corpus())

    assert Counter(binding.layer for binding in bindings) == {
        "ui": 31, "api": 2, "unknown": 11}
    # All 11 unknowns are Step(this, ...) delegation - a fact a reader can act on.
    unknown = [binding for binding in bindings if binding.layer == "unknown"]
    assert all("re-invokes another step" in binding.layer_reason for binding in unknown)
    # No JS file is classified as storage or controller: the vocabulary has neither for JS.
    assert not any(binding.layer in {"storage", "controller", "engine"} for binding in bindings)


# --------------------------------------------------------------------------- AC5: .NET signals

def test_ac5_repository_does_not_classify_javascript_as_storage():
    text = ("class Repository {\n  constructor() { this.items = []; }\n}\n"
            "const repo = new Repository();\n")

    # The .NET table fires on this text - that is the accident being closed ...
    assert stepbindings.infer_layer_from_body(text) == "storage"
    # ... and the JS table must not.
    assert cucumber_js.infer_layer_from_body(text) == "unknown"
    assert "storage" not in {layer for layer, _token in cucumber_js.signals_in(text)}


def test_ac5_the_playwright_signal_is_not_js_playwright_support():
    net_spellings = "page.GetByRole('button').ClickAsync();\n"

    # `\bPlaywright\b` matches this text in the .NET table because of GetByRole/ClickAsync, which
    # are .NET spellings. JavaScript Playwright writes getByRole(/click(, so this is not evidence.
    assert stepbindings.infer_layer_from_body(net_spellings) == "ui"
    assert cucumber_js.infer_layer_from_body(net_spellings) == "unknown"
    assert "Playwright" in " ".join(cucumber_js.DOTNET_ONLY_SIGNALS["ui"])


def test_ac5_the_module_states_which_signals_are_dotnet_only_and_the_tables_are_disjoint():
    net = {pattern for patterns in cucumber_js.DOTNET_ONLY_SIGNALS.values() for pattern in patterns}
    js = {pattern for tokens in cucumber_js.JS_SIGNALS.values() for pattern in tokens.values()}

    assert net & js == set()
    assert r"\bRepository\b" in cucumber_js.DOTNET_ONLY_SIGNALS["storage"]
    assert r"\bPlaywright\b" in cucumber_js.DOTNET_ONLY_SIGNALS["ui"]
    assert r"\bGetByRole\b" in cucumber_js.DOTNET_ONLY_SIGNALS["ui"]
    assert r"\bClickAsync\b" in cucumber_js.DOTNET_ONLY_SIGNALS["ui"]
    # The module's own guard is the same check, run at import.
    cucumber_js._guard_tables_are_disjoint()


# ------------------------------------------------------- the carried-over concatenation defect

def test_a_pattern_split_across_a_concatenation_is_refused_never_truncated():
    files = {"cypress/e2e/front/booking/booking.stepdef.js": (
        "When('Visitor will get validation/' +\n"
        "     'mandatory error message: {string}', (message) => {\n"
        "  cy.get('div.alert');\n"
        "});\n")}

    declarations = cucumber_js.parse_declarations(files)
    assert len(declarations) == 1
    assert declarations[0].concatenated is True, "the truncation must be recorded at parse time"

    with pytest.raises(UnsupportedEcosystem) as caught:
        cucumber_js.ECOSYSTEM.bindings(files)
    message = str(caught.value)
    assert "concatenation" in message
    assert "booking.stepdef.js:1" in message
    # The refusal names the half that was readable, so a reader can find the line.
    assert "Visitor will get validation/" in message

    ecosystem = cucumber_js.ECOSYSTEM.detect(files)
    assert ecosystem is not None
    assert any("string concatenation" in line for line in ecosystem.evidence)


def test_a_concatenation_that_is_not_at_a_declaration_is_untouched():
    files = {"cypress/e2e/x/step.stepdef.js": (
        "When('a normal step', () => {\n  cy.visit('/a' + '/b');\n});\n")}

    bindings = cucumber_js.ECOSYSTEM.bindings(files)

    assert [binding.pattern for binding in bindings] == ["a normal step"]
    assert bindings[0].layer == "ui"


# --------------------------------------------------------------------------- AC6: no placement

@requires_store
def test_ac6_the_ecosystem_is_still_unsupported_so_the_layers_claim_nothing():
    ecosystem = cucumber_js.ECOSYSTEM.detect(_corpus())

    assert ecosystem is not None
    assert ecosystem.supported is False
    assert any("11 Cypress custom commands (6 api, 5 ui)" == line for line in ecosystem.evidence)
