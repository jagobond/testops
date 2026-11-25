from testops import blobs
from testops.collectors import github
from testops.config import load_env, project
env = load_env(); p = project("demo-product")
c = github.collect(p.test, env["GITHUB_PAT"], role="test")
sd = [x for x in c.files if c.files[x][1] == "stepdef"]
print("stepdef files:", len(sd))
for x in sd[:3]: print("  ", x)
# show one
pick = sd[0]
print("="*25, pick)
print(blobs.text(c.files[pick][0])[:1200])
py = [x for x in c.files if x.endswith(".py")]
print("\npython files:", py[:10])
