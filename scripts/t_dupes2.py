from collections import Counter
from testops import blobs
from testops.collectors import github
from testops.config import load_env, project
from testops.extract import gherkin

env = load_env()
p = project("demo-service")
c = github.collect(p.product, env["GITHUB_PAT"], role="test")
feats = [pth for pth,(s,k) in c.files.items() if k == "feature"]
print("feature files:", len(feats))
for f in sorted(feats): print("  ", f)
tot = 0
for f in feats:
    feat = gherkin.parse(f, blobs.text(c.files[f][0]))
    n = len(feat.scenarios) if feat else 0
    tot += n
    print(f"   parsed {n:3} scenarios from {f}")
print("TOTAL scenarios:", tot)
