from collections import Counter
from testops import blobs
from testops.collectors import github
from testops.config import load_env, project
from testops.extract import gherkin
env = load_env(); p = project("demo-product")
c = github.collect(p.test, env["GITHUB_PAT"], role="test")
texts = {path: blobs.text(sha) for path, (sha, k) in c.files.items()}
live, draft = Counter(), Counter()
for path, (sha, kind) in c.files.items():
    if kind != "feature": continue
    f = gherkin.parse(path, texts[path])
    n = len(f.scenarios) if f else 0
    (draft if ".lead-draft" in path else live)[path] = n
print("LIVE features:", len(live), "scenarios:", sum(live.values()))
for k, v in sorted(live.items()): print(f"   {v:3}  {k}")
print("\nDRAFT features:", len(draft), "scenarios:", sum(draft.values()))
for k, v in sorted(draft.items())[:6]: print(f"   {v:3}  {k}")
