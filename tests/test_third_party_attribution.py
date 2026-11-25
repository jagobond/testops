"""TESTOPS-25: the copied fixture carries its upstream MIT notice and its provenance.

`tests/fixtures/demo-service/` is a verbatim subset of `reqnroll/Sample-ReqOverflow` (MIT, Copyright
(c) 2013-2024 Reqnroll and Gaspar Nagy). MIT only permits redistribution with the copyright and
permission notice, so these files are part of the fixture's contract, not tidy-up material: if a
future change deletes them, this suite goes red.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "demo-service"
LICENSE = FIXTURE / "LICENSE"
PROVENANCE = FIXTURE / "PROVENANCE.md"
NOTICES = ROOT / "THIRD-PARTY-NOTICES.md"

UPSTREAM_COMMIT = "78153818b81d7c9a324af81b4e95f65aead705b4"
UPSTREAM_COPYRIGHT = ("Copyright (c) 2013-2024 Reqnroll and Gaspar Nagy, "
                      "https://www.specsolutions.eu")

# SHA-256 of the upstream MIT notice, newline-normalised. Pinning the whole text is deliberate: a
# verbatim notice is the licence condition, and a change to it (new copyright years, say) should be a
# deliberate edit here rather than something that slips through.
UPSTREAM_LICENSE_SHA256 = "97b3daee1fb482163923337773a46a904e97b57e8f500da0146ffae409ea693a"


def test_the_upstream_mit_notice_travels_with_the_copy():
    assert LICENSE.is_file(), "the fixture is MIT code with no licence file"

    text = LICENSE.read_text(encoding="utf-8")
    assert text.startswith("MIT License\n")
    assert UPSTREAM_COPYRIGHT in text, "upstream's copyright line was altered or removed"
    assert "Permission is hereby granted, free of charge" in text
    assert "The above copyright notice and this permission notice shall be included" in text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in text
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == UPSTREAM_LICENSE_SHA256, (
        "the MIT notice is no longer verbatim")


def test_provenance_names_the_upstream_commit_and_what_travelled():
    assert PROVENANCE.is_file(), "the fixture's provenance is not recorded"

    text = PROVENANCE.read_text(encoding="utf-8")
    assert "reqnroll/Sample-ReqOverflow" in text
    assert "78153818" in text

    # The exact commit, as a hash a reader can paste into GitHub, not just a nickname.
    hashes = re.findall(r"\b[0-9a-f]{40}\b", text)
    assert UPSTREAM_COMMIT in hashes, f"PROVENANCE.md names no full upstream commit (found {hashes})"

    # Which projects came across, and which were left out - so "the fixture" is not a vague claim.
    for copied in ("ReqOverflow.Specs.API", "ReqOverflow.Specs.Controller", "ReqOverflow.Specs.WebUI"):
        assert copied in text, f"PROVENANCE.md does not say {copied} was copied"
    assert "ReqOverflow.Web" in text, "PROVENANCE.md does not say what was left out"
    assert "Modifications" in text, "PROVENANCE.md does not state whether anything was modified"
    assert "MIT" in text and "2013-2024 Reqnroll and Gaspar Nagy" in text


def test_the_repository_root_makes_the_obligation_visible():
    assert NOTICES.is_file(), "the third-party obligation is hidden inside a test directory"

    text = NOTICES.read_text(encoding="utf-8")
    assert "tests/fixtures/demo-service" in text
    assert "MIT" in text
    assert "Reqnroll and Gaspar Nagy" in text
    assert "LICENSE" in text and "PROVENANCE.md" in text


def test_the_fixture_stays_data_and_the_notices_stay_out_of_the_corpus():
    # AC5: no .NET build targets in the fixture, so CI never tries to build somebody else's sample.
    assert list(FIXTURE.rglob("*.csproj")) == []
    assert list(FIXTURE.rglob("*.slnx")) == []

    import demo_service_fixtures as corpus

    texts = corpus.texts()
    assert len(texts) == 108, "the analyser no longer sees the 108 files the run collected"
    assert sum(path.endswith(".feature") for path in texts) == 18
    assert "LICENSE" not in texts and "PROVENANCE.md" not in texts, (
        "the licence and provenance files must not be analysed as test code")
