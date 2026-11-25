#!/usr/bin/env python3
"""TESTOPS-102. The tracked tree must carry no personal identifiers.

A repository pushed to a colleague's organisation must not name Harry's subscription, his
machines, his network or his home directory. This check is the gate for that: it reads every
tracked file (``git ls-files``), looks for five shapes, prints ``file:line`` and the shape for
each hit, and exits 1 if there are any.

The shapes:

* a GUID - a subscription, a tenant or a client id is always one, and none belongs in source;
* an absolute home directory - ``C:\\Users\\<name>``, ``/home/<name>``, ``/Users/<name>``;
* an Azure host name - ``*.services.ai.azure.com`` or ``*.azurecontainerapps.io``;
* a tailnet address - anything in ``100.64.0.0/10``;
* a credential - every quoted string and every code-shaped token on a line is asked of
  :func:`testops.services.credential_reason`, the screen the store boundary already applies.
  There is one vocabulary for credentials in this repository, and this is it.

Placeholders are not identifiers: ``<account>.services.ai.azure.com``, ``C:\\Users\\<name>`` and
``TESTOPS_AGENT_TOKEN=<token>`` are the documentation's way of saying "put yours here", and the
shapes above require a real name, so a bracketed placeholder does not match. The credential
screen has its own placeholder rule (TESTOPS-71).

Text files are read as UTF-8 with errors replaced; a binary file (a PNG, the icon) is counted as
read and not searched, because an identifier in a compiled artefact is not a string a reader meets.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from testops.services import credential_reason  # noqa: E402  (after the path is set)

# The shapes, each with the name the report prints. The order decides which name a line gets when
# two shapes overlap, so the most specific comes first.
GUID = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
                  r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}(?![0-9A-Fa-f])")
HOME_PATH = re.compile(r"(?i)(?:\b[A-Z]:\\Users\\|\b[A-Z]:/Users/|(?<![\w.-])/home/|(?<![\w.-])/Users/)"
                       r"(?P<name>[A-Za-z0-9._-]+)")
AZURE_HOST = re.compile(r"(?i)\b[A-Za-z0-9][A-Za-z0-9-]*\."
                        r"(?:services\.ai\.azure\.com|azurecontainerapps\.io)\b")
TAILNET = re.compile(r"(?<![\d.])100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}(?![\d.])")

QUOTED = re.compile(r"""(?P<quote>['"])(?P<body>(?:\\.|(?!\1).)*)(?P=quote)""")
# A token that could be a credential on its own: no spaces, at least eight characters, and not a
# word alone. Paths and URLs are excluded here because they are configuration (a host, a coordinate)
# and are judged by the shapes above.
TOKEN = re.compile(r"[^\s'\"`,;()\[\]{}]+")

# The screen's reasons that name a credential *format* - a shape whose vocabulary nobody has to
# have thought of. The screen's entropy and naming rules are deliberately not used here: a
# repository is full of SHA-256 digests and of tests that write `key=hunter2` to prove the screen
# refuses it, and a check that flagged those would be a check that forbids its own regression
# tests. The tree check asks a narrower question than the store boundary - "is a real credential
# format written into source?" - and it asks it of the same screen, so there is still one
# vocabulary rather than two.
FORMAT_REASONS = ("PEM", "JSON Web Token", "authorization header", "known credential", "embeds a password")

# A GUID in a verbatim third-party fixture. ``tests/contracts/seed/blobs/`` holds files copied from
# an upstream repository and addressed by their content hash, so a UUID v5 namespace inside one is
# not this repository's to rewrite. It is the only place a GUID literal is allowed, and it is a path
# rather than a filename so a regenerated seed stays covered.
THIRD_PARTY_BLOBS = "tests/contracts/seed/blobs/"

# The account label a documentation example or a test may use. ``example-account`` is what the
# ticket calls a fake account name: a host derived from it is a fake too, not somebody's tenant.
EXAMPLE_LABELS = ("example", "account", "your-account")

# An authorization header written into source or a report: a scheme and one unbroken value.
AUTH_HEADER = re.compile(r"(?i)\b(?:bearer|basic|digest|token)\s+(?P<body>[A-Za-z0-9._~+/=-]{12,})\b")

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".pdf", ".woff", ".woff2"}


def tracked_files() -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    return [name for name in result.stdout.decode("utf-8", "replace").split("\0") if name]


def shapes_in(line: str, name: str = "") -> list[tuple[str, str]]:
    """Every ``(shape, detail)`` the line carries, in the order the shapes are listed above.

    ``name`` is the tracked path, used for the two exemptions the ticket states: a GUID inside a
    verbatim third-party blob, and - for credentials - a test, which has to contain the shapes it
    proves the store refuses. Identifier shapes apply to tests unchanged: a test may use
    ``example-account``, and a GUID it genuinely needs is written down as a non-GUID value.
    """
    found: list[tuple[str, str]] = []

    if not name.startswith(THIRD_PARTY_BLOBS):
        match = GUID.search(line)
        if match:
            found.append(("guid", match.group(0)))

    match = HOME_PATH.search(line)
    if match:
        found.append(("home path", match.group(0)))

    for host in AZURE_HOST.finditer(line):
        label = host.group(0).split(".")[0].lower()
        if label in EXAMPLE_LABELS or label.startswith(("example-", "example.")):
            continue
        found.append(("azure host", host.group(0)))

    for address in TAILNET.finditer(line):
        # ``100.64.0.0/10`` is how the shape is written down; a CIDR range is not an address in use.
        if line[address.end():address.end() + 1] in ("/",):
            continue
        found.append(("tailnet address", address.group(0)))
        break

    if name.startswith("tests/"):
        return found

    header = AUTH_HEADER.search(line)
    if header and not _is_template(header.group(0)):
        found.append(("credential", "an authorization header with a value written into the file"))

    seen: set[str] = set()
    for literal in QUOTED.finditer(line):
        body = literal.group("body").strip()
        if len(body) < 8 or body in seen or _is_template(body):
            continue
        seen.add(body)
        reason = credential_reason(body)
        if reason and any(marker in reason for marker in FORMAT_REASONS):
            found.append(("credential", f"{body[:12]}… - {reason}"))
    for token in TOKEN.finditer(line):
        value = token.group(0).strip()
        if len(value) < 16 or value in seen or _is_template(value):
            continue
        if value.startswith(("http://", "https://", "./", "testops/")):
            continue
        if "/" in value or "\\" in value or not re.search(r"[0-9A-Z]", value):
            continue
        seen.add(value)
        reason = credential_reason(value)
        if reason and any(marker in reason for marker in FORMAT_REASONS):
            found.append(("credential", f"{value[:12]}… - {reason}"))
    return found


def _is_template(value: str) -> bool:
    """A value with an interpolation slot is a template: ``Bearer {token}`` is not a token."""
    return any(marker in value for marker in ("{", "}", "<", ">"))


def main() -> int:
    files = tracked_files()
    hits = 0
    for name in files:
        path = ROOT / name
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            text = path.read_bytes().decode("utf-8", "replace")
        except OSError as exc:
            print(f"{name}: unreadable ({type(exc).__name__})")
            hits += 1
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for shape, detail in shapes_in(line, name):
                print(f"{name}:{number}: {shape}: {detail}")
                hits += 1
    if hits:
        print(f"\n{hits} identifier(s) in {len(files)} tracked files. "
              f"Deployment identifiers are configuration, never source (TESTOPS-102).")
        return 1
    print(f"read {len(files)} files, no identifiers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
