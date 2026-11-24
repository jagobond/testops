"""TESTOPS-73: the top of a case page names what the case examined.

The band is the reader's first sight of a finding: one tag per source the case examined, linked at
the commit the evidence was read from, and a dimmed tag for a source the analysis needed and could
not consult. These tests build their own stores under ``tmp_path``; nothing reads the product's
``data/testops.db`` or the live server.

AC1  one tag per examined source, before the statement, naming source *and* kind
AC2  test repository links to the file at the claim's commit; product repository to the repo at its
     commit; linked issue / work item / pipeline run / requirements document to the item; an
     unlinked kind is not a tag, and one line says what an absent tag means
AC3  a needed source that could not be consulted is a dimmed "not consulted" tag with its reason
AC4  a case resting on test code alone says so in words, not as an empty space or a warning
AC5  tags are keyboard-reachable and their accessible names carry the kind
TESTOPS-80  the product-routes tag is answered by the snapshot's surface discovery state
     (found / zero / not_assessable), never by the test-ecosystem detector; its count is the one
     that reader read; a repeats-product verdict and a "not consulted" routes tag cannot coexist.
"""
from __future__ import annotations

import re

from testops.store import db
from testops.web import app

TS = "2020-01-01T00:00:00+00:00"
SNAP = "snap-band"
RUN = "run-band"
CASE = "case-band"
PROJECT = "team"
TEST_REPO = "owner/tests"
PRODUCT_REPO = "owner/product"
COMMIT = "a" * 40
PRODUCT_COMMIT = "b" * 40
PATH = "features/panel.feature"
LINE = 12


def _meta(*, product: bool = True, needs=("code", "test_code"), links: bool = False,
          surfaces: dict | None = None) -> dict:
    """A snapshot that records its arms the way the pipeline writes them."""
    meta = {
        "arms": ({"test": TEST_REPO} | ({"product": PRODUCT_REPO} if product else {})),
        "reads": ({"product": {"commit": PRODUCT_COMMIT}} if product else {}),
        "analysers": {"level_fitness": {"needs": list(needs),
                                        "consults": ["requirements"]}},
    }
    if surfaces is not None:
        meta["surfaces"] = surfaces
    if not product and needs:
        # What the pipeline records when the product service is configured but not readable.
        meta["service_states"] = [
            {"type": "git_repo", "role": "product", "name": f"{PRODUCT_REPO} (product)",
             "state": "absent", "reason": "no product git repository is configured for this project"},
            {"type": "git_repo", "role": "test", "name": f"{TEST_REPO} (test)",
             "state": "available", "reason": ""},
        ]
    return meta


def _case(tmp_path, *, meta: dict, links: list | None = None, analyser: str = "level_fitness",
          verdict: str = "distinct", product: dict | None = None, store: str = "band.db"):
    conn = db.connect(tmp_path / store)
    db.upsert_snapshot(conn, SNAP, PROJECT, TS, {TEST_REPO: COMMIT},
                       schema_version=2, meta=meta)
    db.start_run(conn, RUN, PROJECT, SNAP, analyser, TS)
    claim_id = db.add_claim(
        conn, RUN, analyser, "0.8.0", f"scenario:{PATH}#the panel is served",
        "The test asserts the step.", verdict, 0.5, [], schema_version=2,
        assertion_text="the panel is served", assertion_path=PATH, assertion_line=LINE,
        assertion_commit=COMMIT, interaction_label="needs a browser", interaction_code="I4",
        span=["ui"], sources_assessed=True, sources_missing=[], proposed_action="No change.")
    detail: dict = {"links": links or []}
    if product is not None:
        detail["product"] = product
    if links or product is not None:
        db.add_inference(conn, claim_id, "none", "none", "hash", [], detail)
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (CASE, RUN, PROJECT, analyser, SNAP, TS, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)",
                 (CASE, "The panel is served", "high", "f" * 32, db.j([claim_id])))
    conn.commit()
    page = app.case_page(conn, CASE).decode("utf-8")
    conn.close()
    return page


def _band(page: str) -> str:
    match = re.search(r'<section class="sources".*?</section>', page, re.S)
    assert match, "the case page has no source band"
    return match.group(0)


# --------------------------------------------------------------------------- AC1 / AC2

def test_the_band_opens_the_page_and_links_the_test_file_at_the_claims_commit(tmp_path):
    page = _case(tmp_path, meta=_meta())
    band = _band(page)

    # Before the statement, not after it.
    assert page.index('<section class="sources"') < page.index('<p class="wrong">')
    assert (f'https://github.com/{TEST_REPO}/blob/{COMMIT}/{PATH}#L{LINE}') in band, band
    assert "Test repository" in band
    assert TEST_REPO in band


def test_the_product_repository_links_to_the_repository_at_its_commit(tmp_path):
    band = _band(_case(tmp_path, meta=_meta()))
    assert f'https://github.com/{PRODUCT_REPO}/tree/{PRODUCT_COMMIT}' in band, band
    assert "Product repository" in band
    assert "consulted" in band


def test_a_kind_that_is_not_linked_is_not_a_tag_and_the_band_says_what_an_absence_means(tmp_path):
    band = _band(_case(tmp_path, meta=_meta()))
    for kind in ("Jira issue", "Azure DevOps work item", "Pipeline run", "Requirements document"):
        assert kind not in band, f"{kind} appeared although nothing linked it"
    assert "absent tag means it was not part of the evidence" in band


def test_linked_issues_work_items_runs_and_documents_are_tags_with_their_links(tmp_path):
    links = [
        {"kind": "jira_issue", "name": "TEAM-12",
         "url": "https://team.atlassian.net/browse/TEAM-12"},
        {"kind": "ado_work_item", "name": "Work item 88",
         "url": "https://dev.azure.com/team/workitems/88"},
        {"kind": "pipeline_run", "name": "Run 204",
         "url": "https://dev.azure.com/team/_build/results?buildId=204"},
        {"kind": "requirements_document", "name": "Panel requirements",
         "url": "https://example.test/panel-requirements"},
        # A link with no URL is not a link, so it is not a tag (AC2).
        {"kind": "requirements_document", "name": "Unlinked draft", "url": ""},
    ]
    band = _band(_case(tmp_path, meta=_meta(), links=links))
    for kind, name, url in (
            ("Jira issue", "TEAM-12", "https://team.atlassian.net/browse/TEAM-12"),
            ("Azure DevOps work item", "Work item 88", "https://dev.azure.com/team/workitems/88"),
            ("Pipeline run", "Run 204", "https://dev.azure.com/team/_build/results?buildId=204"),
            ("Requirements document", "Panel requirements",
             "https://example.test/panel-requirements")):
        assert kind in band, band
        assert name in band, band
        assert url in band, band
    assert "Unlinked draft" not in band


# --------------------------------------------------------------------------- AC3

def test_a_needed_source_that_could_not_be_consulted_is_dimmed_with_its_reason(tmp_path):
    band = _band(_case(tmp_path, meta=_meta(product=False)))
    assert 'class="tag unconsulted"' in band, band
    assert "not consulted" in band
    assert "no product git repository is configured for this project" in band
    assert 'tabindex="0"' in band


def test_a_source_the_analysis_did_not_need_is_not_named_as_a_blind_spot(tmp_path):
    """Duplication rests on test code; the product is not a missing source for it."""
    meta = _meta(product=False, needs=("test_code",))
    meta["analysers"] = {"duplication": {"needs": ["test_code"], "consults": ["requirements"]}}
    band = _band(_case(tmp_path, meta=meta, analyser="duplication"))
    assert 'class="tag unconsulted"' not in band, band
    # It still says what the case rests on (AC4); it does not invent a blind spot (AC3).
    assert "Assessed against test code only" in band


# --------------------------------------------------------------------------- AC4

def test_a_case_that_rests_on_test_code_alone_says_so_in_words(tmp_path):
    band = _band(_case(tmp_path, meta=_meta(product=False)))
    assert "Assessed against test code only: the product\u2019s routes could not be consulted" in band
    assert "no product git repository is configured for this project" in band
    # Not an empty space and not a warning banner.
    assert "warn" not in band and "alert" not in band


def test_a_case_with_a_product_does_not_claim_to_rest_on_test_code_alone(tmp_path):
    band = _band(_case(tmp_path, meta=_meta()))
    assert "test code only" not in band


# --------------------------------------------------------------------------- TESTOPS-80 AC1-AC3
# The routes tag answers "were the product's routes read" with the surface discovery state the
# snapshot recorded - never with the test-ecosystem detector, which answers whether a *test*
# suite could be parsed. The count is the one that reader read, not the snapshot's artefact total.

def _found() -> dict:
    """What the surface reader recorded for restfulbooker: 142 .java parsed, 25 routes."""
    return {"state": "found", "parsed": 142, "surfaces": 25, "reason": "",
            "languages": [{"suffix": ".java", "count": 142},
                          {"suffix": ".ts", "count": 23},
                          {"suffix": ".js", "count": 4}],
            "unread": [], "inherited_prefixes": []}


def _zero() -> dict:
    return {"state": "zero", "parsed": 142, "surfaces": 0, "reason": "",
            "languages": [{"suffix": ".java", "count": 142}],
            "unread": [], "inherited_prefixes": []}


def _not_assessable() -> dict:
    return {"state": "not_assessable", "parsed": 0, "surfaces": 0,
            "reason": ("the surface reader parses Java (.java) and Python (.py) only, and the "
                       "product repository holds no file it can read: 23 .ts, 4 .js"),
            "languages": [{"suffix": ".ts", "count": 23}, {"suffix": ".js", "count": 4}],
            "unread": [], "inherited_prefixes": []}


def _routes_item(band: str) -> str:
    """The one list item whose kind is Product routes, from the rendered band."""
    match = re.search(r'<span role="listitem">(?:(?!</span></span>).)*?Product routes'
                      r'(?:(?!</span></span>).)*</span></span>', band, re.S)
    assert match, band
    return match.group(0)


def test_the_routes_tag_reads_the_surface_reader_and_says_what_it_parsed(tmp_path):
    meta = _meta(surfaces=_found())
    # The test-ecosystem record still says no ecosystem was recognised in 169 files. It answers a
    # different question and must not reach the routes tag (AC1, AC4).
    meta["ecosystems"] = {"product": {
        "repository": PRODUCT_REPO, "ecosystem": "unknown", "evidence": [],
        "reason": ("none of the 3 ecosystems this build knows was recognised in the 169 files "
                   "read (reqnroll, python-bdd, cucumber-js)")}}
    band = _band(_case(tmp_path, meta=meta))
    item = _routes_item(band)
    assert "142 .java parsed, 25 routes" in item, band
    assert "consulted" in item
    assert "not consulted" not in item
    # AC3: the reader's count, not the snapshot's artefact total.
    assert "169" not in band
    assert "reqnroll" not in band


def test_a_reader_that_read_the_files_and_found_no_route_says_so(tmp_path):
    band = _band(_case(tmp_path, meta=_meta(surfaces=_zero())))
    item = _routes_item(band)
    assert "142 .java parsed, no routes found" in item, band
    assert "consulted" in item
    assert "not consulted" not in item


def test_a_product_the_surface_reader_could_not_read_keeps_the_readers_reason(tmp_path):
    band = _band(_case(tmp_path, meta=_meta(surfaces=_not_assessable())))
    item = _routes_item(band)
    assert 'class="tag unconsulted"' in item, band
    assert "not consulted" in item
    assert "the product repository holds no file it can read: 23 .ts, 4 .js" in item, band
    # Not the ecosystem detector's sentence: it never watched the product's files.
    assert "ecosystems this build knows" not in band
    assert "169" not in band


def test_a_snapshot_with_no_surface_record_invents_no_routes_tag(tmp_path):
    """Not recorded is not "not consulted": the same rule the band applies to every source."""
    band = _band(_case(tmp_path, meta=_meta()))
    assert "Product routes" not in band, band


# --------------------------------------------------------------------------- TESTOPS-80 AC2

def _repeats_product_page(tmp_path, surfaces: dict, *, store: str) -> str:
    product = {"state": "found", "route": "POST /", "word": "booking", "surfaces": 25}
    return _case(tmp_path, meta=_meta(surfaces=surfaces), store=store,
                 verdict="repeats_product", product=product)


def test_a_repeats_product_verdict_cannot_sit_beside_a_not_consulted_routes_tag(tmp_path):
    page = _repeats_product_page(tmp_path, _found(), store="a.db")
    item = _routes_item(_band(page))
    assert "already declares POST /" in page
    assert "not consulted" not in item, page
    assert "142 .java parsed, 25 routes" in item, page

    # Conversely: where the routes were not consulted, the page says no claim repeats them.
    page = _case(tmp_path, meta=_meta(surfaces=_not_assessable()), store="b.db",
                 verdict="review")
    assert "not consulted" in _routes_item(_band(page))
    assert "already declares" not in page
    assert "already exposes this" not in page


# --------------------------------------------------------------------------- AC5

def test_tags_are_keyboard_reachable_and_their_accessible_names_carry_the_kind(tmp_path):
    page = _case(tmp_path, meta=_meta(product=False))
    band = _band(page)
    # Consulted tags are links; the unconsulted tag is a focusable note.
    assert re.search(r'<a class="tag" href="[^"]+"[^>]*aria-label="Test repository:', band), band
    assert re.search(r'<span class="tag unconsulted" tabindex="0"[^>]*'
                     r'aria-label="Product repository:[^"]*not consulted', band), band
    # "Not consulted" is on the page as words, not only as a colour.
    plain = re.sub(r"<[^>]+>", " ", band)
    assert "not consulted" in plain.lower()
