from testops import blobs
from testops.collectors import github
from testops.config import load_env, project
env = load_env()
c = github.collect(project("demo-service").product, env["GITHUB_PAT"], role="test")
p = "DemoService.Specs.WebUI/StepDefinitions/AuthStepDefinitions.cs"
sha, kind = c.files[p]
data = blobs.get(sha)
print("path:", p, "blob_sha:", sha[:12], "bytes:", len(data), "kind:", kind)
print("---HEAD---")
print(data.decode("utf-8", "replace")[:800])
