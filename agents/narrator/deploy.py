"""Deploy the narrator source as a hosted agent. Requires: pip install azure-ai-projects azure-identity."""
import hashlib
import sys
import time
import zipfile
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (CodeConfiguration, HostedAgentDefinition,
                                      ProtocolVersionRecord)
from azure.identity import AzureCliCredential

ENDPOINT = "https://testops-resource.services.ai.azure.com/api/projects/testops"
NAME = "testops-narrator"
HERE = Path(__file__).resolve().parent


def build_zip() -> Path:
    out = HERE / "agent.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(HERE / "main.py", "main.py")
        z.write(HERE / "requirements.txt", "requirements.txt")
    return out


def main() -> int:
    bundle = build_zip()
    blob = bundle.read_bytes()
    project = AIProjectClient(endpoint=ENDPOINT, credential=AzureCliCredential())
    created = project.agents.create_version_from_code(
        agent_name=NAME,
        definition=HostedAgentDefinition(
            cpu="0.25", memory="0.5Gi",
            code_configuration=CodeConfiguration(runtime="python_3_13",
                                                 entry_point=["python", "main.py"],
                                                 dependency_resolution="remote_build"),
            protocol_versions=[ProtocolVersionRecord(protocol="responses", version="2.0.0")],
            environment_variables={"AZURE_AI_MODEL_DEPLOYMENT_NAME": "deepseek-flash",
                                   "PYTHONNOUSERSITE": "1"},
        ),
        code=(bundle.name, blob, "application/zip"),
        code_zip_sha256=hashlib.sha256(blob).hexdigest(),
        description="TestOps narrator: explains one stored case in plain English. Decides nothing.",
    )
    print("created version", created.version)
    for _ in range(40):
        v = project.agents.get_version(agent_name=NAME, agent_version=created.version)
        state = getattr(v.status, "name", str(v.status)).split(".")[-1].lower()
        print("status:", state)
        if state in ("active", "failed", "error"):
            return 0 if state == "active" else 1
        time.sleep(10)
    return 1


if __name__ == "__main__":
    sys.exit(main())
