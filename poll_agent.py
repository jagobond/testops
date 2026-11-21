"""Poll an existing agent version until it is active. Creates nothing."""
import sys, time
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential

ENDPOINT = "https://testops-resource.services.ai.azure.com/api/projects/TestOps"
AGENT = "testops-hello"
version = sys.argv[1] if len(sys.argv) > 1 else "1"

def norm(v):
    s = v.get("status") if isinstance(v, dict) else getattr(v, "status", None)
    return getattr(s, "name", None) or (str(s).split(".")[-1] if s else "unknown")

project = AIProjectClient(endpoint=ENDPOINT, credential=AzureCliCredential())
deadline = time.time() + 900
while time.time() < deadline:
    v = project.agents.get_version(agent_name=AGENT, agent_version=version)
    st = norm(v).lower()
    print("status:", st, flush=True)
    if st == "active":
        print("ACTIVE"); sys.exit(0)
    if st in ("failed", "deleted"):
        err = v.get("error") if isinstance(v, dict) else getattr(v, "error", None)
        print("FAILED:", err); sys.exit(1)
    time.sleep(10)
print("TIMEOUT"); sys.exit(2)
