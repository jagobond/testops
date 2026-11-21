"""Model adapter. Provider-agnostic, token-accounted, JSON-only.

Uses an AAD token against the Foundry project endpoint: no API key is stored, printed or committed.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass

AZ = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
ENDPOINT = "https://testops-resource.services.ai.azure.com/openai/v1/chat/completions"


@dataclass
class Completion:
    text: str
    model: str
    prompt_hash: str
    tokens_in: int
    tokens_out: int


def _token() -> str:
    r = subprocess.run([AZ, "account", "get-access-token", "--resource",
                        "https://cognitiveservices.azure.com", "--query", "accessToken", "-o", "tsv"],
                       capture_output=True, text=True, timeout=120)
    return next((l.strip() for l in r.stdout.splitlines() if l.strip().startswith("eyJ")), "")


def complete(system: str, user: str, model: str = "deepseek-flash", max_tokens: int = 900) -> Completion:
    prompt = f"{system}\n\n{user}"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_completion_tokens": max_tokens,
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={
        "Authorization": f"Bearer {_token()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read())
    usage = data.get("usage", {})
    return Completion(text=data["choices"][0]["message"].get("content") or "",
                      model=data.get("model", model), prompt_hash=prompt_hash,
                      tokens_in=usage.get("prompt_tokens", 0),
                      tokens_out=usage.get("completion_tokens", 0))


def extract_json(text: str) -> dict | None:
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = None
    return None
