from testops import blobs
from testops.collectors import github
from testops.config import load_env, project

env = load_env()
tok = env["GITHUB_PAT"]
for name, role_key in (("demo-product", "test"), ("demo-product", "product")):
    proj = project(name)
    repo = proj.test if role_key == "test" else proj.product
    c = github.collect(repo, tok, role=role_key)
    kinds = {}
    for _p, (_s, k) in c.files.items():
        kinds[k] = kinds.get(k, 0) + 1
    print(f"{repo.slug} @ {c.commit[:8]}: {len(c.files)} files {kinds}")
    samples = [p for p in c.files if p.endswith('.feature')][:3]
    for s in samples:
        sha, _ = c.files[s]
        body = blobs.text(sha)
        print(f"   {s} ({len(body)} chars) first line: {body.splitlines()[0][:70]}")
