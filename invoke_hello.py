"""Call the deployed agent once through the project's OpenAI-compatible surface."""
import sys
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential

ENDPOINT = "https://testops-resource.services.ai.azure.com/api/projects/TestOps"
project = AIProjectClient(endpoint=ENDPOINT, credential=AzureCliCredential())
client = project.get_openai_client(agent_name="testops-hello")
resp = client.responses.create(input="Reply with exactly: HOSTED AGENT OK")
print("output:", (resp.output_text or "").strip()[:300])
