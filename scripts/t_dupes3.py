from testops import blobs
from testops.collectors import github
from testops.config import load_env, project
env = load_env()
p = project("reqoverflow")
c = github.collect(p.product, env["GITHUB_PAT"], role="test")
path = "ReqOverflow.Specs.Controller/Features/Home.feature"
raw = blobs.get(c.files[path][0])
print("bytes:", len(raw), "first bytes:", raw[:8])
print("--- decoded utf-8 ---")
print(raw.decode("utf-8", "replace")[:500])
