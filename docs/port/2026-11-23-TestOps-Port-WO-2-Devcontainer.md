---
phase: 2
title: The devcontainer
prereqs: [WO-1 complete, Docker available and permitted]
deliverables: [.devcontainer/Dockerfile, .devcontainer/devcontainer.json]
gate: the suite passes inside the container as user vscode, and import testops succeeds
stop-if: Docker is not installed or not permitted; the base image cannot be pulled through the proxy
---

# WO-2 — The devcontainer

## Scope

Create the container image and its devcontainer definition, and prove the suite runs inside it as the user the editor will use. Nothing else.

## Preconditions — confirm by running

```bash
docker --version
docker run --rm hello-world
```

Both must succeed before you write a Dockerfile. If Docker is absent or blocked, stop: this work order cannot be faked, and a plan that pretends otherwise wastes a day.

## Do this

**1. `.devcontainer/Dockerfile`**

```dockerfile
FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

# TLS inspection: uncomment and add the root CA only if builds or outbound HTTPS fail
# with SSLCertVerificationError. Keep certs/ out of git.
# COPY certs/corp-root.crt /usr/local/share/ca-certificates/corp-root.crt
# RUN update-ca-certificates
# ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
#     SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
#     GIT_SSL_CAINFO=/etc/ssl/certs/ca-certificates.crt

RUN apt-get update && apt-get install -y --no-install-recommends \
      git sqlite3 jq curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir "pytest>=8" "setuptools>=68" wheel

ENV PYTHONNOUSERSITE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /workspaces/testops
```

Do not add an Azure CLI. The coordinator implements its token call with the standard library, and a 500 MB package that exists only to be unused is a maintenance cost with no return.

Do not `COPY` the source in. The workspace is mounted, which is what lets the same image serve the editor and a runner.

**2. `.devcontainer/devcontainer.json`**

```json
{
  "name": "testops",
  "build": { "dockerfile": "Dockerfile" },
  "remoteUser": "vscode",
  "postCreateCommand": "pip install -e '.[dev]'",
  "customizations": {
    "vscode": {
      "extensions": [
        "GitHub.copilot",
        "GitHub.copilot-chat",
        "GitHub.vscode-pull-request-github",
        "GitHub.vscode-github-actions"
      ]
    }
  }
}
```

**3. Build and verify as `vscode`, not as root.** The Dockerfile sets no `USER`, so a bare `docker run` is root, and root can succeed on permissions where the editor's user fails. Use `--mount` rather than `-v`: the `-v` form splits on `:` and a Windows drive letter or an MSYS path mangles it.

```bash
MSYS_NO_PATHCONV=1 docker build -t testops-dev .devcontainer/

MSYS_NO_PATHCONV=1 docker run --rm --user vscode \
  --mount type=bind,source="$(cygpath -w "$PWD" 2>/dev/null || echo "$PWD")",target=/workspaces/testops \
  -w /workspaces/testops testops-dev \
  bash -lc "pip install -e '.[dev]' && ./scripts/verify.sh"
```

On a Linux or WSL shell `cygpath` does not exist, the fallback prints `$PWD`, and `MSYS_NO_PATHCONV` is inert. Both paths are correct.

**4. Prove the package is importable**, not merely installed. These are different claims: the image installs no package, so only the editable install makes `import testops` work.

```bash
MSYS_NO_PATHCONV=1 docker run --rm --user vscode \
  --mount type=bind,source="$(cygpath -w "$PWD" 2>/dev/null || echo "$PWD")",target=/workspaces/testops \
  -w /workspaces/testops testops-dev \
  python -c "import testops, sys; print(testops.__file__, sys.version)"
```

**5. Run the render check**, which the suite does not cover:

```bash
... testops-dev python .github/ci/render_case_page.py
```

## Files you may create or edit

`.devcontainer/Dockerfile`, `.devcontainer/devcontainer.json`. Nothing else. If the container needs the CA block enabled, say which certificate you added and where it came from — do not commit a CA.

## Acceptance — paste the raw output of each

```bash
# suite inside the container, as vscode
... bash -lc "pip install -e '.[dev]' && ./scripts/verify.sh" | tail -3

# package importable
... python -c "import testops, sys; print(testops.__file__, sys.version)"

# render check
... python .github/ci/render_case_page.py

# nothing copied into the image
grep -iE '^(COPY|ADD)' .devcontainer/Dockerfile
```

Pass requires: the pass count matching WO-1's baseline, a printed `testops/__init__.py` path, a clean render, and no uncommented `COPY`/`ADD`.

## Stop list — do not work around

- Do not run `docker` with elevated permissions, do not add the user to a group, do not modify daemon configuration. If Docker needs privileges you do not have, stop and report it.
- Do not disable TLS verification to get past a proxy. The commented CA block is the fix; `--insecure` is not.
- Do not install product dependencies into the image that `pyproject.toml` does not declare.
- Do not edit tests or `tests/README.md` to make the container pass.

## When done

Append a row to `docs/port/PROGRESS.md` with the image size, the interpreter version inside the container, and the pass count. Then stop.
