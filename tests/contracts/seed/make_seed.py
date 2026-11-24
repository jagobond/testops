"""Regenerate ``seed.json`` and ``seed/blobs/`` from a store, read-only (TESTOPS-53).

    python tests/contracts/seed/make_seed.py <path-to-testops.db>

The store is opened with ``mode=ro`` and nothing is written back. The seed is a *slice* of the
evidence the contract suite needs, not a copy of a deployment:

  * three restfulbooker runs - the newest (which raised five cases whose pages show the product
    line each verdict rests on, the evidence P6/P15..P19 walk), the run before the Java surface
    reader landed (four cases whose product arm was not assessable), and an earlier one that raised
    nothing (P1's no-findings run);
  * the reqoverflow duplication run, whose cases are settled ("Checked, but this repeats another
    test"). P4 needs a settled case to compare an uncertain one against; reqoverflow is a public
    sample project (reqnroll/Sample-ReqOverflow), so its rows are safe to pin;
  * the projects, services, snapshots, artefacts, observations and blob files those runs need.

reqoverflow's artefacts and blobs are deliberately not included: P4 only needs the case page's
verdict block, and a page that says the source content is not in this store is a real rendered
state, not a bug. That keeps the fixture at ~0.5 MB instead of ~2 MB.

The seeds are a fixture, not a second source of truth: no product code reads this file.
"""
from __future__ import annotations

import json
import pathlib
import re
import sqlite3
import sys

RUNS = (
    "restfulbooker-levels-20261124T123451",
    "restfulbooker-levels-20261123T132456",
    "restfulbooker-levels-20261122T204917",
    "reqoverflow-dup-20261122T205100",
)
PROJECTS = ("restfulbooker", "reqoverflow")
ARTEFACT_PROJECTS = ("restfulbooker",)   # the evidence pages P6/P15..P19 walk

SEED_DIR = pathlib.Path(__file__).resolve().parent
# A credential in a committed fixture would be the one thing worse than the fixture's size.
_CREDENTIAL = re.compile(r"(gh[pousr]_[A-Za-z0-9]{8,}|password\s*=\s*\S+|AKIA[0-9A-Z]{12,})")


def main(source: str) -> int:
    store = sqlite3.connect("file:%s?mode=ro" % pathlib.Path(source).as_posix(), uri=True)
    store.row_factory = sqlite3.Row

    def rows(sql: str, args=()) -> list[dict]:
        return [dict(row) for row in store.execute(sql, args)]

    marks = ", ".join("?" for _ in RUNS)
    runs = rows("SELECT * FROM run WHERE id IN (%s)" % marks, RUNS)
    missing = {run_id for run_id in RUNS} - {run["id"] for run in runs}
    if missing:
        raise SystemExit("the store does not hold these runs: %s" % sorted(missing))
    snapshots_ids = sorted({run["snapshot_id"] for run in runs})
    ship_marks = ", ".join("?" for _ in snapshots_ids)
    snapshots = rows("SELECT * FROM snapshot WHERE id IN (%s)" % ship_marks, snapshots_ids)
    projects = rows("SELECT * FROM project WHERE slug IN (%s)" % ", ".join("?" for _ in PROJECTS),
                    PROJECTS)
    services = rows("SELECT * FROM service WHERE project IN (%s)"
                    % ", ".join("?" for _ in PROJECTS), PROJECTS)

    artefacts, observations = [], []
    project_of_snapshot = {snapshot["id"]: snapshot["project"] for snapshot in snapshots}
    for artefact in rows("SELECT * FROM artefact WHERE snapshot_id IN (%s)" % ship_marks,
                         snapshots_ids):
        if project_of_snapshot.get(artefact["snapshot_id"]) not in ARTEFACT_PROJECTS:
            continue
        artefacts.append(artefact)
        observations += rows("SELECT * FROM observation WHERE artefact_id = ?", (artefact["id"],))

    claims = rows("SELECT * FROM claim WHERE run_id IN (%s)" % marks, RUNS)
    cases = rows("SELECT * FROM case_ WHERE run_id IN (%s)" % marks, RUNS)
    case_marks = ", ".join("?" for _ in cases) or "''"
    findings = rows("SELECT * FROM finding WHERE case_id IN (%s)" % case_marks,
                    [case["id"] for case in cases])
    states = rows("SELECT * FROM case_state WHERE case_id IN (%s)" % case_marks,
                  [case["id"] for case in cases])
    suppressions = rows("SELECT * FROM suppression WHERE fingerprint IN (SELECT fingerprint FROM "
                        "finding WHERE case_id IN (%s))" % case_marks,
                        [case["id"] for case in cases])
    # The analyzers' own records travel with the claims: since TESTOPS-83 the case page renders the
    # product surface's file, line and declaration from `detail["product"]`, and a seed without the
    # inference row would show a page no run could have produced.
    inferences = rows("SELECT * FROM inference WHERE claim_id IN (SELECT id FROM claim WHERE run_id "
                      "IN (%s))" % marks, RUNS)

    blobs = sorted({artefact["blob_sha"] for artefact in artefacts if artefact["blob_sha"]})
    # Keys are the schema's table names, so the builder in harness.py can insert row-for-row.
    seed = dict(project=projects, service=services, snapshot=snapshots, artefact=artefacts,
                observation=observations, run=runs, claim=claims, case_=cases,
                finding=findings, case_state=states, suppression=suppressions,
                inference=inferences, blobs=blobs)

    text = json.dumps(seed, ensure_ascii=False, indent=1, sort_keys=True)
    credential = _CREDENTIAL.search(text)
    if credential:
        raise SystemExit("refusing to write a credential-shaped value into the fixture: %r"
                         % credential.group(0)[:20])

    SEED_DIR.mkdir(parents=True, exist_ok=True)
    blob_dir = SEED_DIR / "blobs"
    blob_dir.mkdir(exist_ok=True)
    store_blobs = pathlib.Path(source).parent / "blobs"
    for sha in blobs:
        (blob_dir / sha).write_bytes((store_blobs / sha[:2] / sha[2:]).read_bytes())
    (SEED_DIR / "seed.json").write_text(text, encoding="utf-8")
    print("wrote %s (%d bytes) and %d blobs" % (SEED_DIR / "seed.json", len(text), len(blobs)))
    print({key: len(value) for key, value in seed.items()})
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    raise SystemExit(main(sys.argv[1]))
