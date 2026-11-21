from testops import blobs
from testops.collectors import github
from testops.config import load_env, project
env = load_env(); p = project("cotw")
c = github.collect(p.test, env["GITHUB_PAT"], role="test")
for path in c.files:
    if path.endswith(".csproj") or "reqnroll" in path.lower() or path.endswith(".json"):
        print("="*20, path)
        print(blobs.text(c.files[path][0])[:1200])
