import base64
from testops.collectors.http import get_json
from testops.config import load_env, project
env = load_env(); p = project("demo-product")
h = {"Authorization": "Basic " + base64.b64encode(f":{env['AZURE_DEVOPS_PAT']}".encode()).decode(),
     "Accept": "application/json"}
base = f"https://dev.azure.com/{p.ado_org}/{p.ado_project}"
runs = get_json(f"{base}/_apis/test/runs?api-version=7.1&$top=200", h).get("value", [])
runs = [r for r in runs if r.get("totalTests")]
runs.sort(key=lambda r: r["id"])
print("runs with results:", len(runs))
for r in runs[-8:]:
    print(f"  run {r['id']:3} total={r['totalTests']:3} passed={r.get('passedTests')} failed={r.get('failedTests')} "
          f"| {r.get('name','')[:52]} | {str(r.get('completedDate'))[:19]}")
