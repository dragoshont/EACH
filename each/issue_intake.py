"""GitHub issue intake: fetch, hash, and cache a public issue's raw metadata.

Key invariant (M3): the cached issue is *intake*, not a Builder input. Its
title/body are untrusted, attacker-influenced text. Nothing here parses that
text as commands, paths, or policy — it is only ever stored verbatim and,
later, embedded as inert quoted data in a spec's ``problem_statement`` by a
human-driven ``each spec build`` step (see each/spec_workflow.py).
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from each.hashing import sha256_json
from each.paths import each_home, validate_task_id

_ISSUE_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/issues/(?P<number>\d+)/?$"
)


class IssueIntakeError(RuntimeError):
    """Raised when an issue URL is invalid or cannot be fetched."""


@dataclass(frozen=True)
class CachedIssue:
    url: str
    owner: str
    repo: str
    number: int
    title: str
    body: str
    html_url: str
    retrieved_at: str
    content_sha256: str
    cache_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "owner": self.owner,
            "repo": self.repo,
            "number": self.number,
            "title": self.title,
            "body": self.body,
            "htmlUrl": self.html_url,
            "retrievedAt": self.retrieved_at,
            "contentSha256": self.content_sha256,
            "cachePath": self.cache_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CachedIssue:
        return cls(
            url=data["url"],
            owner=data["owner"],
            repo=data["repo"],
            number=data["number"],
            title=data["title"],
            body=data["body"],
            html_url=data["htmlUrl"],
            retrieved_at=data["retrievedAt"],
            content_sha256=data["contentSha256"],
            cache_path=data["cachePath"],
        )


def parse_issue_url(url: str) -> tuple[str, str, int]:
    match = _ISSUE_URL_RE.match(url.strip())
    if not match:
        raise IssueIntakeError(
            f"not a well-formed public GitHub issue URL: {url!r} "
            "(expected https://github.com/<owner>/<repo>/issues/<number>)"
        )
    return match.group("owner"), match.group("repo"), int(match.group("number"))


def issue_cache_dir() -> Path:
    path = each_home() / "issue_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_task_id(owner: str, repo: str, number: int) -> str:
    return f"{owner}-{repo}-{number}"


def fetch_issue(url: str, *, task_id: str | None = None) -> CachedIssue:
    """Fetch a single public GitHub issue via the unauthenticated REST API.

    Only the exact ``owner/repo/issues/number`` host/path shape is accepted
    (no redirects followed, no other host reachable) to avoid SSRF-style
    URL confusion. The response is cached verbatim, content-addressed by a
    hash of the retrieved fields, alongside its retrieval timestamp.
    """
    owner, repo, number = parse_issue_url(url)
    task_id = task_id or default_task_id(owner, repo, number)
    try:
        validate_task_id(task_id)
    except ValueError as exc:
        raise IssueIntakeError(str(exc)) from exc
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
    request = urllib.request.Request(
        api_url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "EACH-issue-intake"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise IssueIntakeError(f"failed to fetch {api_url}: {exc}") from exc
    if "pull_request" in raw:
        raise IssueIntakeError(f"{url} is a pull request, not an issue; issue intake only accepts issues")

    title = str(raw.get("title") or "")
    body = str(raw.get("body") or "")
    html_url = str(raw.get("html_url") or url)
    retrieved_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    content_sha256 = sha256_json(
        {"owner": owner, "repo": repo, "number": number, "title": title, "body": body, "htmlUrl": html_url}
    )
    cache_path = issue_cache_dir() / f"{task_id}.json"
    cached = CachedIssue(
        url=url,
        owner=owner,
        repo=repo,
        number=number,
        title=title,
        body=body,
        html_url=html_url,
        retrieved_at=retrieved_at,
        content_sha256=content_sha256,
        cache_path=str(cache_path),
    )
    cache_path.write_text(json.dumps(cached.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return cached


def load_cached_issue(task_id: str) -> CachedIssue:
    try:
        validate_task_id(task_id)
    except ValueError as exc:
        raise IssueIntakeError(str(exc)) from exc
    cache_path = issue_cache_dir() / f"{task_id}.json"
    if not cache_path.exists():
        raise IssueIntakeError(f"no cached issue for task {task_id!r}; run `each issue import <url>` first")
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    cached = CachedIssue.from_dict(data)
    expected = sha256_json(
        {
            "owner": cached.owner,
            "repo": cached.repo,
            "number": cached.number,
            "title": cached.title,
            "body": cached.body,
            "htmlUrl": cached.html_url,
        }
    )
    if expected != cached.content_sha256:
        raise IssueIntakeError(f"cached issue for task {task_id!r} failed its own content hash check (tampered cache)")
    return cached
