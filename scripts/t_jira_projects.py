import base64, json, urllib.request
from testops.config import load_env
env = load_env()
site = env["JIRA_SITE"]; site = site if site.startswith("http") else "https://"+site
auth = base64.b64encode(f'{env["JIRA_EMAIL"]}:{env["JIRA_API_TOKEN"]}'.encode()).decode()
h = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
with urllib.request.urlopen(urllib.request.Request(site.rstrip("/")+"/rest/api/3/project/search?maxResults=50", headers=h), timeout=40) as r:
    d = json.loads(r.read())
for p in d.get("values", []):
    print(f'{p["key"]:8} {p["name"]}')
