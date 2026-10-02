"""Regression tests for RunStore.grant_task_attempt (M7 operational recovery).

Real incident: M7's task was created with the default ``maxAttempts=1``, but
its genuine work spans an external-checkpoint pause/resume cycle (start ->
wait on a real human approval -> resume). The single declared attempt was
legitimately consumed by that cycle, leaving the task's retry budget
exhausted even though no actual execution failure ever occurred -- blocking
``M8`` (which depends on ``M7`` reaching ``COMPLETED``), with no existing
runtime API to recover other than hand-editing canonical Run state (which is
forbidden).

``grant_task_attempt`` is the narrow, auditable recovery path: a trusted
coordinator/human actor only, it raises ``maxAttempts`` by exactly one (never
resets ``attempts``, never touches any other task/criterion/gate state), it
refuses a task that is still ``RUNNING`` or already terminal, and every grant
is its own typed, reasoned event -- never a silent retry-policy rewrite.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "harness"))
import architrave_runtime as art


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture()
def store_with_exhausted_task(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "initial")

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()

    store = art.RunStore(repository=repo)
    store.create(
        goal="test goal",
        outcome="test outcome",
        criteria=[{"id": "C1", "description": "c1", "verificationType": "external", "blocking": True}],
        autonomy_scope="approved-program",
        run_id="test-run",
    )
    store.add_task(
        "test-run",
        {
            "id": "T1",
            "title": "T1",
            "objective": "spans an external checkpoint",
            "acceptanceCriteria": ["C1"],
            "risk": "R3",
        },
    )
    # A second, untouched task keeps the overall Run non-terminal while T1 is
    # independently exhausted/recovered below -- mirroring the real situation
    # (most milestone tasks already COMPLETED/READY) rather than the
    # unrelated edge case of the *whole Run* going terminal.
    store.add_task(
        "test-run",
        {
            "id": "T2",
            "title": "T2",
            "objective": "unrelated, stays READY",
            "acceptanceCriteria": ["C1"],
            "risk": "R1",
        },
    )
    # Consume the sole declared attempt exactly like a real checkpoint pause: start,
    # then let the task return to READY (simulating a resume after a long wait) with
    # its attempts counter already at the max.
    store.start_task("test-run", "T1", worker_id="w1")
    store.fail_task("test-run", "T1", "parked at external checkpoint, never resumed in this attempt")
    return store, repo


def test_grant_attempt_raises_max_attempts_by_exactly_one(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task
    before = store.load("test-run")
    task_before = next(item for item in before["tasks"] if item["id"] == "T1")
    assert task_before["attempts"] >= task_before["retryPolicy"]["maxAttempts"]

    store.grant_task_attempt("test-run", "T1", reason="checkpoint pause consumed the only attempt", actor="coordinator")

    after = store.load("test-run")
    task_after = next(item for item in after["tasks"] if item["id"] == "T1")
    assert task_after["retryPolicy"]["maxAttempts"] == task_before["retryPolicy"]["maxAttempts"] + 1
    assert task_after["attempts"] == task_before["attempts"]


def test_grant_attempt_moves_a_failed_task_back_to_ready(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task
    task = next(item for item in store.load("test-run")["tasks"] if item["id"] == "T1")
    assert task["status"] == "FAILED"

    store.grant_task_attempt("test-run", "T1", reason="genuine operational gap", actor="coordinator")

    task = next(item for item in store.load("test-run")["tasks"] if item["id"] == "T1")
    assert task["status"] == "READY"


def test_grant_attempt_then_allows_a_real_start_task_call(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task
    store.grant_task_attempt("test-run", "T1", reason="genuine operational gap", actor="coordinator")

    state = store.start_task("test-run", "T1", worker_id="w2")
    task = next(item for item in state["tasks"] if item["id"] == "T1")
    assert task["status"] == "RUNNING"
    assert task["attempts"] == 2


def test_grant_attempt_rejects_a_task_that_has_not_exhausted_its_budget(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "initial")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()

    store = art.RunStore(repository=repo)
    store.create(
        goal="g",
        outcome="o",
        criteria=[{"id": "C1", "description": "c1", "verificationType": "external", "blocking": True}],
        autonomy_scope="approved-program",
        run_id="test-run",
    )
    store.add_task(
        "test-run",
        {"id": "T1", "title": "T1", "objective": "o", "acceptanceCriteria": ["C1"], "risk": "R3"},
    )

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.grant_task_attempt("test-run", "T1", reason="not actually exhausted", actor="coordinator")
    assert excinfo.value.code == "ATTEMPT_NOT_EXHAUSTED"


def test_grant_attempt_rejects_a_running_task(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task
    store.grant_task_attempt("test-run", "T1", reason="genuine operational gap", actor="coordinator")
    store.start_task("test-run", "T1", worker_id="w2")

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.grant_task_attempt("test-run", "T1", reason="again while running", actor="coordinator")
    assert excinfo.value.code == "TASK_NOT_GRANTABLE"


def test_grant_attempt_requires_a_trusted_coordinator_or_human_actor(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.grant_task_attempt("test-run", "T1", reason="reason", actor="worker:some-worker")
    assert excinfo.value.code == "UNTRUSTED_RESOLUTION"


def test_grant_attempt_requires_a_non_empty_reason(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.grant_task_attempt("test-run", "T1", reason="   ", actor="coordinator")
    assert excinfo.value.code == "INVALID_REASON"


def test_grant_attempt_is_recorded_as_a_genuine_hash_chained_event(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task
    before = store.events("test-run")

    store.grant_task_attempt("test-run", "T1", reason="genuine operational gap", actor="coordinator")

    after = store.events("test-run")
    assert len(after) == len(before) + 1
    new_event = after[-1]
    assert new_event["type"] == "task.attempt_granted"
    assert new_event["taskId"] == "T1"
    state = store.load("test-run")
    assert state["eventCursor"]["lastHash"] == new_event["hash"]
    art.validate_run(state)
