"""Jira collector: issues as raw documents.

Nothing is interpreted here. The raw issue JSON is stored as a blob and parsed by an extractor, so a change
in how acceptance criteria are read never requires a re-fetch.
"""
from __future__ import annotations

import base64
import json

from .. import blobs
from .http import FetchError, get_json, post_json

FIELDS = ["summary", "description", "status", "issuetype", "labels", "parent", "created", "updated", "resolution"]


def _headers(site: str, email: str, token: str) -> dict[str, str]:
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    return {"Authorization": f"Basic {auth}", "Accept": "application/json"}


def collect(site: str, email: str, token: str, jira_key: str, page_size: int = 100) -> dict[str, str]:
    """Return {issue_key: blob_sha} for every issue in the project."""
    if not site.startswith("http"):
        site = "https://" + site
    site = site.rstrip("/")
    headers = _headers(site, email, token)
    jql = f'project = "{jira_key}" ORDER BY key ASC'

    out: dict[str, str] = {}
    token_next = None
    while True:
        body = {"jql": jql, "maxResults": page_size, "fields": FIELDS}
        if token_next:
            body["nextPageToken"] = token_next
        try:
            data = post_json(f"{site}/rest/api/3/search/jql", headers, body)
        except FetchError:
            # Older tenants only expose the classic search endpoint.
            q = f"{site}/rest/api/3/search?jql={jql}&maxResults={page_size}&fields={','.join(FIELDS)}"
            data = get_json(q, headers)
            for issue in data.get("issues", []):
                out[issue["key"]] = blobs.put(json.dumps(issue, ensure_ascii=False).encode())
            break
        for issue in data.get("issues", []):
            out[issue["key"]] = blobs.put(json.dumps(issue, ensure_ascii=False).encode())
        token_next = data.get("nextPageToken")
        if not token_next or not data.get("issues"):
            break
    return out


def summary_of(blob_sha: str) -> dict:
    issue = json.loads(blobs.get(blob_sha).decode("utf-8"))
    f = issue.get("fields", {})
    return {
        "key": issue["key"],
        "summary": f.get("summary", ""),
        "type": (f.get("issuetype") or {}).get("name", ""),
        "status": (f.get("status") or {}).get("name", ""),
        "labels": f.get("labels", []),
    }
