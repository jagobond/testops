from collections import defaultdict
from testops import blobs
from testops.collectors import github
from testops.config import load_env, project
from testops.extract import gherkin, stepbindings

env = load_env()
p = project("reqoverflow")
c = github.collect(p.product, env["GITHUB_PAT"], role="test")
texts = {path: blobs.text(sha) for path, (sha, kind) in c.files.items()}
dm = stepbindings.build_driver_map(texts)
feats = []
for path, t in texts.items():
    if c.files[path][1] == "feature":
        f = gherkin.parse(path, t)
        if f: feats.append(f)
groups = defaultdict(list)
for f in feats:
    suite = f.path.split("/")[0].split(".")[-1]
    for sc in f.scenarios:
        groups[sc.signature].append((suite, sc.name))
multi = {k: v for k, v in groups.items() if len(v) > 1}
print("scenarios:", sum(len(f.scenarios) for f in feats), "signatures:", len(groups), "multi-groups:", len(multi))
for sig, members in list(multi.items())[:5]:
    print("---", len(members))
    for suite, name in members: print(f"    {suite:10} {name[:60]}")
    print("    sig:", sig[:120])
