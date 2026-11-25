from testops.collectors import github
from testops.config import load_env, project
env = load_env()
p = project("demo-product")
c = github.collect(p.product, env["GITHUB_PAT"], role="product")
kinds = {}
for _p, (_s, k) in c.files.items():
    kinds[k] = kinds.get(k, 0) + 1
print(f"{p.product.slug} @ {c.commit[:8]}: {len(c.files)} files {kinds}")
