"""Daily spend by service for the Foundry subscription, over the last N days.

Uses the Cost Management query API directly: `az consumption` returns null costs on this subscription.
"""
import json, subprocess, sys, datetime as dt

AZ = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
SUB = "965a76e1-8fe3-405e-b484-4820aca954b1"
days = int(sys.argv[1]) if len(sys.argv) > 1 else 3
end = dt.date.today()
start = end - dt.timedelta(days=days)

body = {
    "type": "ActualCost",
    "timeframe": "Custom",
    "timePeriod": {"from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"},
    "dataset": {
        "granularity": "Daily",
        "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
        "grouping": [{"type": "Dimension", "name": "ServiceName"}],
    },
}
r = subprocess.run([AZ, "rest", "--method", "post", "--url",
                    f"https://management.azure.com/subscriptions/{SUB}/providers/Microsoft.CostManagement/query?api-version=2023-11-01",
                    "--body", json.dumps(body), "--headers", "Content-Type=application/json", "-o", "json"],
                   capture_output=True, text=True, timeout=180)
if r.returncode != 0:
    print("cost query failed:", (r.stderr or "")[-400:]); sys.exit(1)
out = r.stdout
i = out.find("{")
data = json.loads(out[i:])
cols = [c["name"] for c in data["properties"]["columns"]]
rows = data["properties"]["rows"]
if not rows:
    print(f"No cost rows for {start}..{end} (spend may lag by up to 24h)."); sys.exit(0)
print(f"Cost {start}..{end} (columns: {cols})")
ic, iday, isvc = (cols.index("Cost"), cols.index("UsageDate"), cols.index("ServiceName") if "ServiceName" in cols else None)
agg = {}
for row in rows:
    day = str(row[iday])
    svc = row[isvc] if isvc is not None else "all"
    agg[(day, svc)] = agg.get((day, svc), 0) + float(row[ic])
for (day, svc), cost in sorted(agg.items()):
    print(f"  {day}  {svc[:38]:38}  {cost:8.4f}")
print(f"  TOTAL {sum(agg.values()):.4f}")
