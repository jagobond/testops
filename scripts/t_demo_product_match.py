from testops import blobs
from testops.collectors import github
from testops.config import load_env, project
from testops.extract import gherkin, stepbindings
env = load_env(); p = project("demo-product")
c = github.collect(p.test, env["GITHUB_PAT"], role="test")
texts = {path: blobs.text(sha) for path, (sha, k) in c.files.items()}
bindings = []
for path, t in texts.items():
    if c.files[path][1] == "stepdef":
        bindings.extend(stepbindings.parse_file(path, t, {}))
print("binding patterns sample:")
for b in bindings[:6]: print("   ", b.verb, "|", b.pattern[:70], "| layer", b.layer)
feat = [x for x in c.files if c.files[x][1] == "feature"][0]
f = gherkin.parse(feat, texts[feat])
print("\nfeature:", feat, "scenarios:", len(f.scenarios))
for sc in f.scenarios[:2]:
    print("scenario:", sc.name)
    for st in sc.steps[:6]:
        m = stepbindings.match_step(bindings, st.text)
        print(f"   [{'MATCH' if m else 'MISS '}] {st.text[:70]}")
