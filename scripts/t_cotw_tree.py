from testops.collectors.github import _headers, API, head_commit
from testops.collectors.http import get_json
from testops.config import load_env, project
env = load_env(); p = project("cotw")
sha = head_commit(p.test, env["GITHUB_PAT"])
tree = get_json(f"{API}/repos/{p.test.slug}/git/trees/{sha}?recursive=1", _headers(env["GITHUB_PAT"]))
paths = [n["path"] for n in tree["tree"] if n["type"] == "blob"]
print("total files:", len(paths), "| commit", sha[:8])
for pat in (".csproj", "reqnroll", ".runsettings", ".json", ".feature"):
    hits = [x for x in paths if x.endswith(pat) or pat in x]
    print(f"{pat}: {len(hits)}")
    for h in hits[:8]: print("    ", h)
