import base64
from testops.collectors.github import _headers, API, head_commit
from testops.collectors.http import get_json
from testops.config import load_env, project
env = load_env(); p = project("demo-product")
sha = head_commit(p.test, env["GITHUB_PAT"])
tree = get_json(f"{API}/repos/{p.test.slug}/git/trees/{sha}?recursive=1", _headers(env["GITHUB_PAT"]))
node = next(n for n in tree["tree"] if n["path"] == "DemoProductTests.csproj")
blob = get_json(f"{API}/repos/{p.test.slug}/git/blobs/{node['sha']}", _headers(env["GITHUB_PAT"]))
print(base64.b64decode(blob["content"]).decode("utf-8", "replace")[1200:3000])
