from collections import Counter
from testops import blobs
from testops.collectors import github
from testops.config import load_env, project
from testops.extract import gherkin, stepbindings
from testops.analysers import duplication

env = load_env()
p = project("demo-service")
c = github.collect(p.product, env["GITHUB_PAT"], role="test")

texts = {path: blobs.text(sha) for path, (sha, kind) in c.files.items()}
driver_map = stepbindings.build_driver_map(texts)
print("drivers mapped:", len(driver_map), Counter(driver_map.values()))

features, bindings = [], []
for path, text in sorted(texts.items()):
    kind = c.files[path][1]
    if kind == "feature":
        f = gherkin.parse(path, text)
        if f: features.append(f)
    elif kind == "stepdef":
        bindings.extend(stepbindings.parse_file(path, text, driver_map))

scenarios = sum(len(f.scenarios) for f in features)
print(f"features={len(features)} scenarios={scenarios} bindings={len(bindings)}")
print("binding layers:", dict(Counter(b.layer for b in bindings)))

def uri_for_path(path):
    return f"github:{p.product.slug}@{c.commit}:{path}"

claims = duplication.analyse(features, bindings, uri_for_path)
print(f"duplicate claims: {len(claims)}")
print("by layer:", dict(Counter(c.detail.get("layer") for c in claims)))
print("intra-level:", sum(1 for c in claims if c.detail.get("intra_level")))
groups = {c.detail.get("signature") for c in claims if not c.detail.get("intra_level")}
print("cross-level claim groups flagged:", len(groups))
