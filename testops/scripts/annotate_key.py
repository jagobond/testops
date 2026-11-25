"""Draft an interaction-based re-annotation of the demo-product-eval key.

Every row records what the repository actually says: which step files bind the scenario's steps, and
therefore which instrument runs. The verdict is derived from the claim and the instrument, not chosen.

Usage: python -m testops.scripts.annotate_key --key <path> --out <path>
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .. import blobs
from ..analysers import level_fitness as lf
from ..collectors import github
from ..config import load_env, project
from ..extract import csproj, gherkin, stepbindings

FLOOR = {"I1": "api", "I2": "api", "I3": "ui", "I4": "ui", "KP": "api", "U": "unknown"}
WIDER = {"api": 0, "controller": 0, "engine": 0, "ui": 1}


def collect(project_key: str):
    env = load_env()
    p = project(project_key)
    tr = github.collect(p.test, env["GITHUB_PAT"], role="test")
    texts = {k: blobs.text(v[0]) for k, v in tr.files.items()}
    excludes: list[str] = []
    for path, t in texts.items():
        if tr.files[path][1] == "build":
            excludes.extend(csproj.excluded_patterns(t))
    drivers = stepbindings.build_driver_map(texts)
    bindings = []
    for path, t in sorted(texts.items()):
        if tr.files[path][1] == "stepdef":
            bindings.extend(stepbindings.parse_file(path, t, drivers))
    scenarios = {}
    for path, t in sorted(texts.items()):
        if tr.files[path][1] != "feature" or not csproj.is_active(path, excludes):
            continue
        f = gherkin.parse(path, t)
        if not f:
            continue
        for sc in f.scenarios:
            scenarios[(Path(path).stem, sc.name)] = (path, sc)
    return bindings, scenarios, tr.commit


def evidence_for(sc, bindings, path):
    suite = stepbindings.suite_of(path)
    rows, suites, layers = [], Counter(), []
    for step in sc.steps:
        b = stepbindings.match_step(bindings, step.text, suite)
        rows.append({"keyword": step.keyword, "text": step.text,
                     "file": (b.path.split("/")[-1] if b else None),
                     "layer": (b.layer if b else "unbound")})
        if b:
            suites[b.path.split("/")[-1]] += 1
            layers.append(b.layer)
    instrument = stepbindings.highest(layers) if layers else "unknown"
    return rows, dict(suites), instrument


def claim_rows(sc, instrument, span):
    """One row per distinguishable assertion, in the v0.5 vocabulary."""
    uses_browser = "ui" in span
    text = sc.name + " " + " ".join(x.text for x in sc.steps)
    rows = []
    for interaction, why in lf.classify_claims(text):
        if interaction == "I3" and not uses_browser:
            interaction, why = "KP", "asserts served content without a user acting"
        needs = interaction in lf.NEEDS_BROWSER
        if instrument == "unknown" or interaction == "U":
            verdict = "unplaced"
        elif needs and not uses_browser:
            verdict = "gap"
        elif needs:
            verdict = "distinct"
        elif uses_browser:
            verdict = "review"
        else:
            verdict = "distinct"
        rows.append({"claim": interaction, "why": why, "needs_browser": needs,
                     "floor": "ui" if needs else "api", "verdict": verdict})
    return rows


def draft(key_path: str, out_path: str, project_key: str = "demo-product") -> dict:
    bindings, scenarios, commit = collect(project_key)
    key = json.loads(Path(key_path).read_text(encoding="utf-8"))
    rows = key["scenarios"] if isinstance(key, dict) else key

    out = []
    for k in rows:
        hit = scenarios.get((k["feature"], k["scenario"]))
        if not hit:
            out.append({**k, "claim": "?", "instrument": "not found in build", "verdict": "unplaced",
                        "evidence": {}, "status": "scenario not compiled"})
            continue
        path, sc = hit
        steps, suites, instrument = evidence_for(sc, bindings, path)

        span = sorted({x["layer"] for x in steps if x["layer"] != "unbound"})
        crows = claim_rows(sc, instrument, span)
        primary = crows[0]
        old = {"optimal": "distinct", "necessary": "distinct", "overbuilt": "review"}.get(k["verdict"])
        out.append({
            "feature": k["feature"], "scenario": k["scenario"],
            "claims": crows, "span": span,
            "instrument": instrument, "step_files": suites,
            "verdict": primary["verdict"], "key_verdict": k["verdict"],
            "status": "agree" if old == primary["verdict"] else "DISAGREE",
            "steps": steps,
        })

    doc = {"project": project_key, "commit": commit, "rows": out}
    Path(out_path).write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return doc


def to_markdown(doc: dict) -> str:
    lines = [f"# Re-annotation draft - {doc['project']} @ {doc['commit'][:10]}", "",
             "Claim = which interaction the scenario asserts. Instrument = what the code actually drives,",
             "taken from the step-definition files that bind its steps. Verdict follows from the two.", ""]
    for r in doc["rows"]:
        lines.append(f"## {r['scenario']}")
        lines.append(f"- feature: `{r['feature']}`")
        for c in r.get("claims", []):
            lines.append(f"- claim **{c['claim']}** — {c['why']}; needs `{c['floor']}`; "
                         f"verdict **{c['verdict']}**")
        lines.append(f"- instrument **{r.get('instrument')}** via {r.get('step_files')} "
                     f"(span: {', '.join(r.get('span') or [])})")
        lines.append(f"- key said `{r.get('key_verdict')}` -> {r.get('status')}")
        for s in r.get("steps", []):
            lines.append(f"  - {s['keyword']} {s['text'][:70]} -> {s['file']} [{s['layer']}]")
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--md", default=None)
    ap.add_argument("--project", default="demo-product")
    a = ap.parse_args(argv)
    doc = draft(a.key, a.out, a.project)
    if a.md:
        Path(a.md).write_text(to_markdown(doc), encoding="utf-8")
    rows = doc["rows"]
    print(f"rows {len(rows)}  agree {sum(r['status']=='agree' for r in rows)}  "
          f"disagree {sum(r['status']=='DISAGREE' for r in rows)}")
    for r in rows:
        print(f"  {r.get('status','?'):9} {r.get('claim','?'):3} inst={r.get('instrument','?'):8} "
              f"got={r.get('verdict','?'):9} key={r.get('key_verdict','?')}  {r['scenario'][:52]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
