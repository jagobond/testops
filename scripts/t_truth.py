import base64, json
from testops.collectors.github import _headers, API, head_commit
from testops.collectors.http import get_json
from testops.config import load_env, project
env = load_env(); p = project("cotw")

sha = head_commit(p.test, env["GITHUB_PAT"])
tree = get_json(f"{API}/repos/{p.test.slug}/git/trees/{sha}?recursive=1", _headers(env["GITHUB_PAT"]))
node = next(n for n in tree["tree"] if n["path"] == "CotwBdd.csproj")
blob = get_json(f"{API}/repos/{p.test.slug}/git/blobs/{node['sha']}", _headers(env["GITHUB_PAT"]))
print("=== CotwBdd.csproj ===")
print(base64.b64decode(blob["content"]).decode("utf-8", "replace")[:1500])

# ADO: most recent build's test run count
pat = env["AZURE_DEVOPS_PAT"]
h = {"Authorization": "Basic " + base64.b64encode(f":{pat}".encode()).decode(), "Accept": "application/json"}
org, proj = p.ado_org, p.ado_project
runs = get_json(f"https://dev.azure.com/{org}/{proj}/_apis/test/runs?api-version=7.1&$top=3", h)
print("\n=== latest ADO test runs ===")
for r in runs.get("value", [])[:3]:
    print(f"  run {r['id']}: total={r.get('totalTests')} passed={r.get('passedTests')} failed={r.get('failedTests')} notApplicable={r.get('notApplicableTests')} | {r.get('name','')[:60]}")
