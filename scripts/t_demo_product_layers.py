from collections import Counter
from testops import blobs
from testops.collectors import github
from testops.config import load_env, project
from testops.extract import gherkin, stepbindings
env = load_env(); p = project("demo-product")
c = github.collect(p.test, env["GITHUB_PAT"], role="test")
texts = {path: blobs.text(sha) for path, (sha, k) in c.files.items()}
dm = stepbindings.build_driver_map(texts)
print("driver map:", dict(Counter(dm.values())), "classes:", len(dm))
feats = [gherkin.parse(path, t) for path, t in texts.items() if c.files[path][1] == "feature"]
feats = [f for f in feats if f]
bindings = []
for path, t in texts.items():
    if c.files[path][1] == "stepdef":
        bindings.extend(stepbindings.parse_file(path, t, dm))
print("bindings by layer:", dict(Counter(b.layer for b in bindings)))
layers, unmatched = Counter(), 0
for f in feats:
    for sc in f.scenarios:
        ls = []
        for st in sc.steps:
            b = stepbindings.match_step(bindings, st.text)
            if b: ls.append(b.layer)
            else: unmatched += 1
        layers[stepbindings.highest(ls) if ls else "unmatched"] += 1
print("scenario layers:", dict(layers), "| unmatched steps:", unmatched)
print("scenarios:", sum(len(f.scenarios) for f in feats), "features:", len(feats))
