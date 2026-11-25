from testops import blobs
from testops.collectors import github
from testops.config import load_env, project
env = load_env()
c = github.collect(project("demo-service").product, env["GITHUB_PAT"], role="test")
for path in ("DemoService.Specs.Controller/Drivers/AskQuestionDriver.cs",
             "DemoService.Specs.API/Drivers/QuestionApiDriver.cs"):
    t = blobs.text(c.files[path][0])
    print("="*30, path)
    print(t[:700])
