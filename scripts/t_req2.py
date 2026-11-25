from testops import blobs
from testops.collectors import github
from testops.config import load_env, project
env = load_env()
c = github.collect(project("demo-service").product, env["GITHUB_PAT"], role="test")
web = [p for p in c.files if "WebUI" in p and p.endswith(".cs")]
api = [p for p in c.files if "Specs.API" in p and p.endswith(".cs")]
print("web cs files:", len(web), "api cs files:", len(api))
print("--- sample web ui step def ---")
sd = [p for p in web if "StepDefinitions" in p][:1] or web[:1]
for p in sd:
    print("FILE", p); print(blobs.text(c.files[p][0])[:900])
print("--- sample api step def ---")
sd = [p for p in api if "StepDefinitions" in p][:1] or api[:1]
for p in sd:
    print("FILE", p); print(blobs.text(c.files[p][0])[:900])
