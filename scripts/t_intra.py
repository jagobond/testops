from collections import defaultdict
from testops import blobs
from testops.collectors import github
from testops.config import load_env, project
from testops.extract import gherkin, stepbindings

env = load_env(); p = project("reqoverflow")
c = github.collect(p.product, env["GITHUB_PAT"], role="test")
texts = {path: blobs.text(sha) for path, (sha, k) in c.files.items()}
feats = [gherkin.parse(path, t) for path, t in texts.items() if c.files[path][1] == "feature"]
feats = [f for f in feats if f]
by_name = defaultdict(list)
for f in feats:
    for sc in f.scenarios:
        by_name[sc.name].append((f.path, sc))
print("names appearing more than once (any suite):")
for name, occ in by_name.items():
    if len(occ) > 1 and "Controller" in "".join(p for p, _ in occ):
        suites = [p.split("/")[0].split(".")[-1] for p, _ in occ]
        sigs = {sc.signature for _, sc in occ}
        print(f"  {name[:58]:58} suites={suites} distinct_signatures={len(sigs)}")
