"""Unit tests for each.issue_intake: URL validation, content-hash caching,
and tamper detection on load. Network calls are stubbed; no real GitHub API
traffic is required for this unit-level coverage (a real fetch is exercised
separately as the M3 live demonstration, not in CI)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Self

import pytest

from each import issue_intake
from each.issue_intake import IssueIntakeError, fetch_issue, load_cached_issue, parse_issue_url


@pytest.fixture(autouse=True)
def _private_each_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))


def test_parse_issue_url_accepts_well_formed_url() -> None:
    owner, repo, number = parse_issue_url("https://github.com/octocat/Hello-World/issues/42")
    assert (owner, repo, number) == ("octocat", "Hello-World", 42)


@pytest.mark.parametrize(
    "bad_url",
    [
        "https://evil.example.com/octocat/Hello-World/issues/42",
        "http://github.com/octocat/Hello-World/issues/42",  # not https
        "https://github.com/octocat/Hello-World/pull/42",
        "https://github.com/octocat/Hello-World/issues/not-a-number",
        "not a url at all",
    ],
)
def test_parse_issue_url_rejects_malformed_or_wrong_host_urls(bad_url: str) -> None:
    with pytest.raises(IssueIntakeError):
        parse_issue_url(bad_url)


class _StubResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_fetch_issue_caches_content_and_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"title": "Test Issue", "body": "a real body", "html_url": "https://github.com/octocat/Hello-World/issues/1"}
    monkeypatch.setattr(issue_intake.urllib.request, "urlopen", lambda *a, **k: _StubResponse(payload))

    cached = fetch_issue("https://github.com/octocat/Hello-World/issues/1")

    assert cached.title == "Test Issue"
    assert cached.body == "a real body"
    assert Path(cached.cache_path).exists()
    reloaded = load_cached_issue("octocat-Hello-World-1")
    assert reloaded.content_sha256 == cached.content_sha256


def test_fetch_issue_rejects_pull_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"title": "x", "body": "y", "pull_request": {"url": "..."}}
    monkeypatch.setattr(issue_intake.urllib.request, "urlopen", lambda *a, **k: _StubResponse(payload))
    with pytest.raises(IssueIntakeError, match="pull request"):
        fetch_issue("https://github.com/octocat/Hello-World/issues/1")


def test_load_cached_issue_missing_task_raises() -> None:
    with pytest.raises(IssueIntakeError, match="no cached issue"):
        load_cached_issue("never-imported")


def test_load_cached_issue_detects_tampered_cache_file(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"title": "Test Issue", "body": "a real body", "html_url": "https://github.com/octocat/Hello-World/issues/1"}
    monkeypatch.setattr(issue_intake.urllib.request, "urlopen", lambda *a, **k: _StubResponse(payload))
    cached = fetch_issue("https://github.com/octocat/Hello-World/issues/1")

    # Simulate tampering: rewrite the cached body without updating its hash.
    data = json.loads(Path(cached.cache_path).read_text(encoding="utf-8"))
    data["body"] = "attacker-modified body, including a prompt-injection payload"
    Path(cached.cache_path).write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(IssueIntakeError, match="tampered"):
        load_cached_issue("octocat-Hello-World-1")


@pytest.mark.parametrize(
    "evil_task_id",
    [
        "../../../../../../tmp/each_poc_victim",
        "../escape",
        "a/b",
        "a/../b",
    ],
)
def test_fetch_issue_rejects_path_traversal_task_ids(monkeypatch: pytest.MonkeyPatch, evil_task_id: str) -> None:
    payload = {"title": "x", "body": "y", "html_url": "https://github.com/octocat/Hello-World/issues/1"}
    monkeypatch.setattr(issue_intake.urllib.request, "urlopen", lambda *a, **k: _StubResponse(payload))
    with pytest.raises(IssueIntakeError, match="invalid task id"):
        fetch_issue("https://github.com/octocat/Hello-World/issues/1", task_id=evil_task_id)


def test_load_cached_issue_rejects_path_traversal_task_id() -> None:
    with pytest.raises(IssueIntakeError, match="invalid task id"):
        load_cached_issue("../../../../../../tmp/each_poc_victim")
