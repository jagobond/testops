"""TESTOPS-102. The no-identifiers scan fires, and does not fire on a placeholder.

A gate nobody tests is a gate that can quietly stop gating. Each shape is assembled from parts here
rather than written down, because this file is itself inside the tree the scan reads: the test proves
the pattern without putting an identifier in the repository, which is the same rule the ticket
applies to a test that needs a GUID.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_no_secrets.py"


@pytest.fixture(scope="module")
def scan():
    spec = importlib.util.spec_from_file_location("check_no_secrets", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Assembled, so no identifier literal is in this file.
SAMPLE_GUID = "-".join(("965a76e1", "8fe3", "405e", "b484", "4820aca954b1"))
SAMPLE_HOME = "C:" + "/Users" + "/alice/Projects/x"
SAMPLE_HOST = "acct" + ".services" + ".ai.azure.com"
SAMPLE_APP = "app" + ".azurecontainerapps" + ".io"
SAMPLE_TAILNET = "100." + "121.128.21"


@pytest.mark.parametrize("line, shape", [
    (f'x = "{SAMPLE_GUID}"', "guid"),
    (f'p = "{SAMPLE_HOME}"', "home path"),
    (f'p = "/home/{"bob"}/src"', "home path"),
    (f"p = '/Users/{'carol'}/src'", "home path"),
    (f'u = "https://{SAMPLE_HOST}/openai"', "azure host"),
    (f'u = "{SAMPLE_APP}"', "azure host"),
    (f'h = "{SAMPLE_TAILNET}"', "tailnet address"),
])
def test_every_shape_is_caught(scan, line, shape):
    assert shape in [name for name, _ in scan.shapes_in(line, "testops/module.py")]


def test_a_credential_format_is_caught(scan):
    """A real-shaped key, built here: the tree carries none, and the scan still recognises one."""
    line = 'key = "%s"' % ("AKIA" + "A" * 16)
    shapes = [name for name, _ in scan.shapes_in(line, "testops/module.py")]
    assert "credential" in shapes
    assert scan.shapes_in(line, "tests/test_something.py") == [], (
        "a test has to be able to contain the shape it proves the store refuses")


@pytest.mark.parametrize("line", [
    'u = "https://<account>.services.ai.azure.com/openai"',   # a placeholder, not a host
    'p = "C:/Users/<name>/Projects/x"',
    'h = {"Authorization": f"Bearer {token}"}',                 # a template, not a token
    "anything in 100.64.0.0/10",                               # the shape written down, not an address
    'u = "https://example-account.services.ai.azure.com/x"',   # the fake account a test may use
    'key = "<your-key-here>"',
])
def test_a_placeholder_is_not_an_identifier(scan, line):
    assert scan.shapes_in(line, "docs/DEPLOYING.md") == []


def test_the_tracked_tree_is_clean(scan):
    """The gate's own verdict on this repository, so a reintroduced identifier fails the suite too."""
    assert scan.main() == 0
