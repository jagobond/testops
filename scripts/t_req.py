from testops import blobs
from testops.collectors import github
from testops.config import load_env, project
env = load_env()
p = project("reqoverflow")
c = github.collect(p.product, env["GITHUB_PAT"], role="test")
print("commit", c.commit[:8], "files", len(c.files))
for path in sorted(c.files):
    print("  ", path)
