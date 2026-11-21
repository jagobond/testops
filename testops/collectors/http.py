"""Shared HTTP with retries. The only place that knows about urllib."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


class FetchError(RuntimeError):
    pass


def get_json(url: str, headers: dict[str, str], attempts: int = 4, timeout: int = 60):
    last = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode(errors="ignore")
            # 4xx other than rate limiting will not improve with another attempt
            if e.code < 500 and e.code != 429:
                raise FetchError(f"HTTP {e.code} for {url}: {body}") from e
            last = f"HTTP {e.code}: {body}"
        except Exception as e:  # network flake
            last = f"{type(e).__name__}: {e}"
        time.sleep(1.5 * (attempt + 1))
    raise FetchError(f"failed after {attempts} attempts: {last}")


def post_json(url: str, headers: dict[str, str], payload: dict, attempts: int = 4, timeout: int = 60):
    data = json.dumps(payload).encode()
    headers = {**headers, "Content-Type": "application/json"}
    last = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode(errors="ignore")
            if e.code < 500 and e.code != 429:
                raise FetchError(f"HTTP {e.code} for {url}: {body}") from e
            last = f"HTTP {e.code}: {body}"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(1.5 * (attempt + 1))
    raise FetchError(f"failed after {attempts} attempts: {last}")
