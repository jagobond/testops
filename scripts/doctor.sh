#!/usr/bin/env bash
# scripts/doctor.sh — why this checkout cannot push, test or be trusted, in one command.
#
# The dev container is the supported way to work on this repository, but it is not the only way and
# it is never the reason a push fails: git authentication belongs to the person, not to the image.
# This script separates the two questions a person actually has — "can I get my work to the remote?"
# and "would my test run mean anything?" — and answers both without guessing.
#
# Nothing here prints a credential, and the push check is a --dry-run: it sends no objects.
#
#   ./scripts/doctor.sh            # human-readable
#   ./scripts/doctor.sh --quiet    # one line per failure, for a hook or a wrapper
set -uo pipefail

QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1
FAILED=0
WARNED=0

say()  { [ "$QUIET" = 1 ] || printf '%s\n' "$*"; }
pass() { [ "$QUIET" = 1 ] || printf '  PASS  %s\n' "$1"; }
warn() { WARNED=$((WARNED+1)); printf '  WARN  %s\n      -> %s\n' "$1" "$2"; }
fail() { FAILED=$((FAILED+1)); printf '  FAIL  %s\n      -> %s\n' "$1" "$2"; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 2

say "doctor: $ROOT"
say ""

# --- 1. interpreter -------------------------------------------------------------------------
# The declared floor is 3.11. A 3.12 interpreter runs 3.12-only syntax happily and then dies in the
# process that serves the UI, so the version is a fact to report, not to assume.
PY=""
for candidate in ".venv/Scripts/python.exe" ".venv/bin/python" "python3" "python"; do
    if [ -x "$ROOT/$candidate" ]; then PY="$ROOT/$candidate"; break; fi
    if command -v "$candidate" >/dev/null 2>&1; then PY="$(command -v "$candidate")"; break; fi
done

if [ -z "$PY" ]; then
    fail "no python found" "create a venv: C:/Python311/python.exe -m venv .venv && pip install -e '.[dev]'"
else
    VER="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)"
    MAJ="$("$PY" -c 'import sys; print(sys.version_info[0])' 2>/dev/null)"
    MIN="$("$PY" -c 'import sys; print(sys.version_info[1])' 2>/dev/null)"
    case "$VER" in
        3.11|3.12) pass "interpreter $VER ($PY)" ;;
        2.*|"")    fail "interpreter unusable ($PY)" "install Python 3.11 or 3.12" ;;
        *)         warn "interpreter $VER ($PY)" "outside the 3.11-3.12 matrix CI proves; a local pass does not transfer" ;;
    esac
fi

# --- 2. the environment that makes a pass meaningful ----------------------------------------
# verify.sh strips these. Doctor reports them because a stray PYTHONPATH is the difference between
# testing this checkout and testing whatever was on the path first.
stray=""
for v in PYTHONPATH PYTHONHOME VIRTUAL_ENV CONDA_PREFIX; do
    [ -n "${!v:-}" ] && stray="$stray $v"
done
if [ -n "$stray" ]; then
    warn "inherited environment:$stray" "harmless if you use ./scripts/verify.sh, which strips them; never run bare pytest"
else
    pass "no inherited PYTHONPATH/VIRTUAL_ENV/CONDA_PREFIX"
fi

# --- 3. the identifier guard ----------------------------------------------------------------
if [ -n "$PY" ] && [ -f scripts/check_no_secrets.py ]; then
    if out="$(env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 "$PY" scripts/check_no_secrets.py 2>&1)"; then
        pass "identifier guard: ${out##*$'\n'}"
    else
        fail "identifier guard is red" "the tree carries an identifier; fix it before any commit (see SECURITY.md)"
    fi
else
    warn "identifier guard not run" "scripts/check_no_secrets.py missing or no python"
fi

# --- 4. repository identity -----------------------------------------------------------------
if git rev-parse --git-dir >/dev/null 2>&1; then
    pass "git repository, branch $(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
else
    fail "not a git repository" "clone the work repository, do not unpack an archive"
fi

REMOTE="$(git remote get-url origin 2>/dev/null || true)"
if [ -z "$REMOTE" ]; then
    fail "no origin remote" "git remote add origin <work-org-url>"
else
    pass "origin: $REMOTE"
fi

# --- 5. can this machine reach the remote at all? ------------------------------------------
# Separates "network/VPN" from "permission". ls-remote needs no write access.
if [ -n "$REMOTE" ] && timeout 25 git ls-remote --heads origin >/dev/null 2>&1; then
    pass "remote is reachable and readable"
else
    fail "remote unreachable or unreadable" "check VPN and the host name; a TLS error here is the corporate proxy (step 6)"
fi

# --- 6. corporate TLS inspection ------------------------------------------------------------
# The dev container carries the root CA; a bare laptop needs it in git's config. Without this the
# failure reads as an authentication problem but is a trust problem.
if [ -n "$PY" ] && [ -n "$REMOTE" ]; then
    host="$(printf '%s' "$REMOTE" | sed -E 's#^[a-z+]+://([^/]+).*#\1#')"
    case "$REMOTE" in
        *://*@*) host="$(printf '%s' "$REMOTE" | sed -E 's#^[a-z+]+://[^@]*@([^/]+).*#\1#')" ;;
    esac
    tls="$("$PY" - "$host" <<'PY' 2>&1
import socket, ssl, sys
host = sys.argv[1].split(":")[0]
try:
    ctx = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=15) as s:
        with ctx.wrap_socket(s, server_hostname=host):
            print("ok")
except ssl.SSLCertVerificationError as e:
    print("cert: " + (e.verify_message or str(e)))
except Exception as e:
    print("net: " + type(e).__name__)
PY
)"
    case "$tls" in
        ok) pass "TLS to $host verified against the system trust store" ;;
        cert:*) fail "TLS to $host fails certificate verification" "export the corporate root CA and set git config --global http.sslCAInfo <corp-root.pem>, then set SSL_CERT_FILE for pip" ;;
        *)      warn "TLS to $host not tested (${tls#*: })" "if pushes fail with a certificate error, it is the proxy, not your token" ;;
    esac
fi

# --- 7. can this account write? -------------------------------------------------------------
# A --dry-run sends no objects and still reports the refusal: protected branch, SSO, read-only.
if [ -n "$REMOTE" ]; then
    push="$(timeout 30 git push --dry-run --porcelain origin HEAD 2>&1 || true)"
    case "$push" in
        *"protected branch"*|*GH006*|*"required status"*|*"review required"*)
            warn "direct push to $(git rev-parse --abbrev-ref HEAD) is refused by branch protection" "that is the merge gate working: push a branch and open a PR" ;;
        *"Permission to"*|*"403"*|*"Authentication failed"*|*"could not read Username"*)
            fail "the remote refuses this account" "the token is missing SSO authorisation for the organisation, or lacks write scope: check 'gh auth status'" ;;
        *"SSL"*|*"certificate"*)
            fail "push fails at TLS, before authentication" "same fix as step 6: point git at the corporate root CA" ;;
        *"Everything up-to-date"*|*"would be updated"*|*"->"*|*"Done"*|"")
            pass "push permission is not the blocker" ;;
        *)
            warn "push dry-run unclear" "$(printf '%s' "$push" | tail -1)" ;;
    esac
fi

# --- 8. the store ---------------------------------------------------------------------------
DATA="${TESTOPS_DATA:-$ROOT/data}"
if [ -d "$DATA" ] && [ -w "$DATA" ]; then
    pass "store directory writable: $DATA"
else
    warn "store directory missing or not writable: $DATA" "the suite creates its own; a run without one uses the default under data/"
fi

# --- verdict --------------------------------------------------------------------------------
say ""
if [ "$FAILED" -gt 0 ]; then
    say "doctor: $FAILED blocking problem(s)$([ "$WARNED" -gt 0 ] && echo ", $WARNED warning(s)")."
    say "A local pass does not outrank CI: the suite job and the identifiers job are the authority."
    exit 1
fi
if [ "$WARNED" -gt 0 ]; then
    say "doctor: nothing blocking, $WARNED warning(s)."
else
    say "doctor: clean."
fi
say "A local pass does not outrank CI: the suite job and the identifiers job are the authority."
exit 0
