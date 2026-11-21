"""Deploy the hello-world agent from source. No container registry involved.

Purpose is narrow: put a real hosted agent in the project so the idle-session billing question can be
answered by measurement. Everything here is the documented SDK path, nothing invented.
"""
from __future__ import annotations

import hashlib
import sys
import time
import zipfile
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import CodeConfiguration, HostedAgentDefinition, ProtocolVersionRecord
from azure.identity import AzureCliCredential

ROOT = Path(r"C:/Users/Chester/Projects/testops")
SRC = ROOT / "hello"
ZIP = ROOT / "hello.zip"
ENDPOINT = "https://testops-resource.services.ai.azure.com/api/projects/TestOps"
AGENT = "testops-hello"
MODEL_DEPLOYMENT = "deepseek-flash"


def build_zip() -> tuple[bytes, str]:
    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ("main.py", "requirements.txt"):
            z.write(SRC / name, arcname=name)  # flat: remote_build requires both at the root
    data = ZIP.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    print(f"zip {len(data)} bytes sha256 {digest[:16]}...")
    return data, digest


def main() -> int:
    data, digest = build_zip()
    project = AIProjectClient(endpoint=ENDPOINT, credential=AzureCliCredential())

    created = project.agents.create_version_from_code(
        agent_name=AGENT,
        definition=HostedAgentDefinition(
            cpu="1",
            memory="2Gi",
            code_configuration=CodeConfiguration(
                runtime="python_3_13",
                entry_point=["python", "main.py"],
                dependency_resolution="remote_build",
            ),
            protocol_versions=[ProtocolVersionRecord(protocol="responses", version="2.0.0")],
            environment_variables={
                "AZURE_AI_MODEL_DEPLOYMENT_NAME": MODEL_DEPLOYMENT,
                "PYTHONNOUSERSITE": "1",
            },
        ),
        code=(ZIP.name, data, "application/zip"),
        code_zip_sha256=digest,
        description="Minimal hello agent; exists to measure idle-session billing",
    )
    version = created.version
    print(f"created version {version}", flush=True)

    deadline = time.time() + 1200
    while time.time() < deadline:
        v = project.agents.get_version(agent_name=AGENT, agent_version=version)
        status = v["status"] if isinstance(v, dict) else getattr(v, "status", None)
        print(f"  status {status}", flush=True)
        if status == "active":
            print("ACTIVE")
            return 0
        if status in ("failed", "deleted"):
            err = v.get("error") if isinstance(v, dict) else getattr(v, "error", None)
            print(f"FAILED: {err}")
            return 1
        time.sleep(10)
    print("TIMEOUT waiting for active")
    return 2


if __name__ == "__main__":
    sys.exit(main())
