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

(F7, Astra REVISE batch) A grant must now also name an actual, already-
RESOLVED external checkpoint genuinely bound to the exact same task
(``resumeTask == task_id``), with its own recorded resolution proof --
not just a free-text ``reason`` string an arbitrary trusted caller could
attach to any exhausted/failed task. The fixture below exercises the real
``wait_external``/``resolve_external`` recovery cycle (not a stub) so the
checkpoint used to justify the grant is the same kind of real recovery event
the production M7 incident actually was.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "harness"))
import architrave_runtime as art


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _resolve_checkpoint(store: art.RunStore, repo: Path, *, checkpoint_id: str, task_id: str, challenge: str) -> None:
    """Resolve a PENDING checkpoint with a real, matching external-proof artifact."""
    proof_path = repo / f"{checkpoint_id}-proof.json"
    proof_path.write_text(
        json.dumps({"checkpointId": checkpoint_id, "principal": "alice", "provider": "test-provider"}),
        encoding="utf-8",
    )
    store._record_external_proof(
        "test-run",
        artifact_id=f"{checkpoint_id}-proof",
        path=f"{checkpoint_id}-proof.json",
        evidence_refs=[],
    )
    store.resolve_external(
        "test-run",
        checkpoint_id=checkpoint_id,
        resolution_ref=f"artifact:{checkpoint_id}-proof",
        challenge=challenge,
        actor="human:alice",
    )


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
    # Real external-checkpoint pause/resume cycle: T1 genuinely waits, a real
    # resolution proof closes it, then the single resumed attempt still fails
    # (a real execution failure, independent of the checkpoint) -- exhausting
    # the declared attempt budget while leaving a real RESOLVED checkpoint
    # bound to T1 that a grant can legitimately point at.
    _state, challenge = store.wait_external(
        "test-run",
        checkpoint_id="cp-t1",
        task_id="T1",
        checkpoint_type="HUMAN_JUDGMENT_REQUIRED",
        principal="alice",
        provider="test-provider",
        reason="needs a human decision before T1 can proceed",
    )
    _resolve_checkpoint(store, repo, checkpoint_id="cp-t1", task_id="T1", challenge=challenge)
    store.start_task("test-run", "T1", worker_id="w1")
    store.fail_task("test-run", "T1", "parked at external checkpoint, never resumed in this attempt")
    return store, repo


def test_grant_attempt_raises_max_attempts_by_exactly_one(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task
    before = store.load("test-run")
    task_before = next(item for item in before["tasks"] if item["id"] == "T1")
    assert task_before["attempts"] >= task_before["retryPolicy"]["maxAttempts"]

    store.grant_task_attempt("test-run", "T1", reason="checkpoint pause consumed the only attempt", actor="coordinator", checkpoint_id="cp-t1")

    after = store.load("test-run")
    task_after = next(item for item in after["tasks"] if item["id"] == "T1")
    assert task_after["retryPolicy"]["maxAttempts"] == task_before["retryPolicy"]["maxAttempts"] + 1
    assert task_after["attempts"] == task_before["attempts"]


def test_grant_attempt_moves_a_failed_task_back_to_ready(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task
    task = next(item for item in store.load("test-run")["tasks"] if item["id"] == "T1")
    assert task["status"] == "FAILED"

    store.grant_task_attempt("test-run", "T1", reason="genuine operational gap", actor="coordinator", checkpoint_id="cp-t1")

    task = next(item for item in store.load("test-run")["tasks"] if item["id"] == "T1")
    assert task["status"] == "READY"


def test_grant_attempt_then_allows_a_real_start_task_call(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task
    store.grant_task_attempt("test-run", "T1", reason="genuine operational gap", actor="coordinator", checkpoint_id="cp-t1")

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
        store.grant_task_attempt("test-run", "T1", reason="not actually exhausted", actor="coordinator", checkpoint_id="unused")
    assert excinfo.value.code == "ATTEMPT_NOT_EXHAUSTED"


def test_grant_attempt_rejects_a_running_task(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task
    store.grant_task_attempt("test-run", "T1", reason="genuine operational gap", actor="coordinator", checkpoint_id="cp-t1")
    store.start_task("test-run", "T1", worker_id="w2")

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.grant_task_attempt("test-run", "T1", reason="again while running", actor="coordinator", checkpoint_id="cp-t1")
    assert excinfo.value.code == "TASK_NOT_GRANTABLE"


def test_grant_attempt_requires_a_trusted_coordinator_or_human_actor(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.grant_task_attempt("test-run", "T1", reason="reason", actor="worker:some-worker", checkpoint_id="cp-t1")
    assert excinfo.value.code == "UNTRUSTED_RESOLUTION"


def test_grant_attempt_requires_a_non_empty_reason(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.grant_task_attempt("test-run", "T1", reason="   ", actor="coordinator", checkpoint_id="cp-t1")
    assert excinfo.value.code == "INVALID_REASON"


def test_grant_attempt_rejects_an_unknown_checkpoint_id(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.grant_task_attempt(
            "test-run", "T1", reason="genuine operational gap", actor="coordinator", checkpoint_id="does-not-exist"
        )
    assert excinfo.value.code == "EXTERNAL_CHECKPOINT_NOT_FOUND"


def test_grant_attempt_rejects_a_checkpoint_bound_to_a_different_task(store_with_exhausted_task, tmp_path, monkeypatch):
    store, repo = store_with_exhausted_task
    # A real checkpoint exists and is genuinely RESOLVED, but it was never
    # bound to T1 (resumeTask == "T2") -- it must not justify granting T1.
    _state, challenge = store.wait_external(
        "test-run",
        checkpoint_id="cp-t2",
        task_id="T2",
        checkpoint_type="HUMAN_JUDGMENT_REQUIRED",
        principal="alice",
        provider="test-provider",
        reason="an unrelated checkpoint for T2",
    )
    _resolve_checkpoint(store, repo, checkpoint_id="cp-t2", task_id="T2", challenge=challenge)

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.grant_task_attempt(
            "test-run", "T1", reason="genuine operational gap", actor="coordinator", checkpoint_id="cp-t2"
        )
    assert excinfo.value.code == "RECOVERY_CHECKPOINT_MISMATCH"


def test_grant_attempt_rejects_a_pending_unresolved_checkpoint(tmp_path, monkeypatch):
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
    # Mirror the real incident exactly: the sole declared attempt is consumed
    # by start_task, and the task is then genuinely parked WAITING_EXTERNAL
    # mid-attempt -- its retry budget is exhausted, but cp-t1 (bound to T1)
    # is still genuinely PENDING, with no real resolution proof yet.
    store.start_task("test-run", "T1", worker_id="w1")
    store.wait_external(
        "test-run",
        checkpoint_id="cp-t1",
        task_id="T1",
        checkpoint_type="HUMAN_JUDGMENT_REQUIRED",
        principal="alice",
        provider="test-provider",
        reason="still awaiting a real human decision",
    )

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.grant_task_attempt(
            "test-run", "T1", reason="premature", actor="coordinator", checkpoint_id="cp-t1"
        )
    assert excinfo.value.code == "RECOVERY_CHECKPOINT_UNRESOLVED"


def test_grant_attempt_is_recorded_as_a_genuine_hash_chained_event(store_with_exhausted_task):
    store, _repo = store_with_exhausted_task
    before = store.events("test-run")

    store.grant_task_attempt("test-run", "T1", reason="genuine operational gap", actor="coordinator", checkpoint_id="cp-t1")

    after = store.events("test-run")
    assert len(after) == len(before) + 1
    new_event = after[-1]
    assert new_event["type"] == "task.attempt_granted"
    assert new_event["taskId"] == "T1"
    state = store.load("test-run")
    assert state["eventCursor"]["lastHash"] == new_event["hash"]
    art.validate_run(state)
