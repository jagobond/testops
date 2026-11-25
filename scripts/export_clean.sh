#!/usr/bin/env bash
# Build a copy of this repository that is safe to push to somebody else's organisation.
#
# Why a copy and not a history rewrite: this repository's 460 commits contain identifiers that were
# correct at the time (a subscription id in a cost probe, resource names in deploy notes). Rewriting
# them in place would change commits other worktrees are based on, and would leave the private
# repository's own history as the thing that still leaks. A single-commit import is honest about
# what it is - "this is the code as of today" - and leaves nothing behind for `git log -S` to find.
#
# Usage:  scripts/export_clean.sh [output-dir]
#         scripts/export_clean.sh ../testops-for-quilter
set -euo pipefail

OUT="${1:-../testops-export}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== guard: the tracked tree must carry no identifiers"
py=""
for candidate in ".venv/Scripts/python.exe" ".venv/bin/python" "python" "python3"; do
    if command -v "$ROOT/$candidate" >/dev/null 2>&1 || [ -x "$ROOT/$candidate" ]; then py="$ROOT/$candidate"; break; fi
    if command -v "$candidate" >/dev/null 2>&1; then py="$candidate"; break; fi
done
[ -n "$py" ] || { echo "no python found; set one up in .venv first" >&2; exit 1; }
env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 "$py" scripts/check_no_secrets.py

echo "== guard: no credential-shaped file is tracked"
bad=$(git ls-files | grep -E '(^|/)\.env$|\.pem$|\.key$|\.pfx$|\.p12$' || true)
[ -z "$bad" ] || { echo "refusing: tracked credential files:" >&2; echo "$bad" >&2; exit 1; }

echo "== staging $OUT from the commit $(git rev-parse --short HEAD)"
rm -rf "$OUT"
mkdir -p "$OUT"
git archive --format=tar HEAD | tar -x -C "$OUT"

# The rename map is a one-time tool and it necessarily contains the names it removed, so it does not
# travel: a copy that shipped it would leak exactly what TESTOPS-103 took out.
rm -f "$OUT/scripts/rename_corpus.py"

# The ticket that ordered the rename quotes the mapping table for the same reason. Replace the table
# with a pointer, keeping the acceptance criteria that say what was promised.
python - "$OUT/factory/tickets/TESTOPS-103.md" <<'PY'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
if p.exists():
    text = p.read_text(encoding="utf-8")
    text = re.sub(r"## The rename map.*?(?=## Acceptance criteria)",
                  "## The rename map\n\nWithheld from this copy: the table names the identifiers it removed, and shipping it "
                  "would undo the ticket. The mapping is recorded in the private repository the copy came from.\n\n",
                  text, flags=re.S)
    p.write_text(text, encoding="utf-8")
PY

cd "$OUT"
git init -q -b main
git config user.name "TestOps"
git config user.email "testops@example.invalid"
git add -A
git -c commit.gpgsign=false commit -q -m "TestOps: initial import

Imported from a private working repository. Configuration and deployment identifiers are read
from the environment; docs/DEPLOYING.md lists every variable. scripts/check_no_secrets.py is the
guard against a new one being committed, and CI runs it."

echo "== what was produced"
git log --oneline
echo "files: $(git ls-files | wc -l)   size: $(du -sh . | cut -f1)   commits: $(git rev-list --count HEAD)"
echo
echo "next:"
echo "  git -C $OUT remote add origin <the-new-repository-url>"
echo "  git -C $OUT push -u origin main"
