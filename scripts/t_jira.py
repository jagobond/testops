from testops.collectors import jira
from testops.config import load_env
env = load_env()
for key in ("DEMO", "TOPS"):
    issues = jira.collect(env["JIRA_SITE"], env["JIRA_EMAIL"], env["JIRA_API_TOKEN"], key)
    print(f"{key}: {len(issues)} issues")
    for k in list(issues)[:3]:
        s = jira.summary_of(issues[k])
        print(f"   {s['key']}: {s['summary'][:60]} [{s['type']}/{s['status']}]")
