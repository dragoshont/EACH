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
    # Real external-checkpoint pause/resume cycle: T1 genuinely starts its one
    # declared attempt, is interrupted mid-run by a real external checkpoint
    # (F7: this is what makes the checkpoint an eligible "interruption" --
    # recorded as such only because the task is actually RUNNING when the
    # checkpoint is created), a real resolution proof closes it, and the
    # single resumed attempt still fails (a real execution failure,
    # independent of the checkpoint) -- exhausting the declared attempt
    # budget while leaving a real RESOLVED checkpoint bound to T1's exact
    # interrupted attempt that a grant can legitimately point at.
    store.start_task("test-run", "T1", worker_id="w1")
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


def test_grant_attempt_refuses_a_replayed_checkpoint_after_the_task_fails_again(store_with_exhausted_task):
    """F7: a single genuinely-resolved checkpoint must back exactly one
    recovery grant -- not an unbounded number of them. Once T1 is granted,
    runs, fails again, and re-exhausts its (now-raised) budget, the SAME
    ``cp-t1`` resolution can no longer justify a second grant; that would let
    one real human decision be replayed indefinitely to keep reopening a
    task that keeps genuinely failing on its own.
    """
    store, _repo = store_with_exhausted_task
    store.grant_task_attempt("test-run", "T1", reason="first genuine operational gap", actor="coordinator", checkpoint_id="cp-t1")
    store.start_task("test-run", "T1", worker_id="w2")
    store.fail_task("test-run", "T1", "fails again on its own, independent of any checkpoint")

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.grant_task_attempt(
            "test-run", "T1", reason="trying to reuse the same checkpoint", actor="coordinator", checkpoint_id="cp-t1"
        )
    assert excinfo.value.code == "RECOVERY_GRANT_ALREADY_CONSUMED"


@pytest.fixture()
def store_for_interruption_ownership(tmp_path, monkeypatch):
    """A fresh Run with T1 (maxAttempts=2) exercised through a full, genuine
    lifecycle -- real external checkpoints created at several different
    points -- for the F7 "interrupted-attempt ownership" regression below.
    T2 carries its own independent retryable failure/backoff so a T1 grant
    can be checked to never touch it.
    """
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
            "objective": "spans several real external checkpoints across two attempts",
            "acceptanceCriteria": ["C1"],
            "risk": "R3",
            "maxAttempts": 2,
            "backoffSeconds": 0,
        },
    )
    store.add_task(
        "test-run",
        {
            "id": "T2",
            "title": "T2",
            "objective": "independently retries with its own backoff window",
            "acceptanceCriteria": ["C1"],
            "risk": "R1",
            "maxAttempts": 3,
            "backoffSeconds": 600,
        },
    )
    return store, repo


def test_a_checkpoint_created_before_the_task_ever_started_cannot_back_a_grant(store_for_interruption_ownership):
    """F7: a checkpoint resolved while T1 was never actually RUNNING records
    no eligible interrupted attempt. Exhausting T1's budget afterwards via
    ordinary execution does not retroactively make that old checkpoint a
    valid recovery event.
    """
    store, repo = store_for_interruption_ownership

    # Checkpoint created while T1 is still READY (never started).
    _state, challenge = store.wait_external(
        "test-run",
        checkpoint_id="cp-before-start",
        task_id="T1",
        checkpoint_type="HUMAN_JUDGMENT_REQUIRED",
        principal="alice",
        provider="test-provider",
        reason="an approval requested before any attempt ever ran",
    )
    _resolve_checkpoint(store, repo, checkpoint_id="cp-before-start", task_id="T1", challenge=challenge)

    # T1 now genuinely executes and exhausts its real attempt budget, with no
    # further relationship to the stale pre-start checkpoint.
    store.start_task("test-run", "T1", worker_id="w1")
    store.fail_task("test-run", "T1", "ordinary first failure")
    store.start_task("test-run", "T1", worker_id="w1b")
    store.fail_task("test-run", "T1", "ordinary second failure, budget now exhausted")

    task = next(item for item in store.load("test-run")["tasks"] if item["id"] == "T1")
    assert task["status"] == "FAILED"
    assert task["attempts"] == 2

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.grant_task_attempt(
            "test-run", "T1", reason="trying to reuse the pre-start checkpoint", actor="coordinator",
            checkpoint_id="cp-before-start",
        )
    assert excinfo.value.code == "RECOVERY_CHECKPOINT_NOT_AN_INTERRUPTION"


def test_a_checkpoint_from_an_earlier_attempt_cannot_back_a_grant_after_a_later_unrelated_failure(
    store_for_interruption_ownership,
):
    """F7: a checkpoint that genuinely interrupted attempt 1 records
    ``interruptedAttempt=1``. If T1 is later resumed, runs a real attempt 2,
    and fails again on its own (unrelated to the original interruption),
    ``task["attempts"]`` has moved past 1 -- the old checkpoint no longer
    describes T1's current situation and must not justify a grant for the
    new failure.
    """
    store, repo = store_for_interruption_ownership

    store.start_task("test-run", "T1", worker_id="w1")
    _state, challenge = store.wait_external(
        "test-run",
        checkpoint_id="cp-attempt-1",
        task_id="T1",
        checkpoint_type="HUMAN_JUDGMENT_REQUIRED",
        principal="alice",
        provider="test-provider",
        reason="a genuine interruption of the first real attempt",
    )
    _resolve_checkpoint(store, repo, checkpoint_id="cp-attempt-1", task_id="T1", challenge=challenge)

    task = next(item for item in store.load("test-run")["tasks"] if item["id"] == "T1")
    checkpoint = next(item for item in store.load("test-run")["externalCheckpoints"] if item["id"] == "cp-attempt-1")
    assert task["attempts"] == 1
    assert checkpoint["interruptedAttempt"] == 1

    # T1 resumes normally (no grant used) and runs a real, unrelated second
    # attempt that fails on its own, exhausting the declared budget.
    store.start_task("test-run", "T1", worker_id="w2")
    store.fail_task("test-run", "T1", "ordinary second failure, unrelated to the first interruption")

    task = next(item for item in store.load("test-run")["tasks"] if item["id"] == "T1")
    assert task["status"] == "FAILED"
    assert task["attempts"] == 2

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.grant_task_attempt(
            "test-run", "T1", reason="trying to reuse the stale attempt-1 checkpoint", actor="coordinator",
            checkpoint_id="cp-attempt-1",
        )
    assert excinfo.value.code == "RECOVERY_CHECKPOINT_STALE"


def test_a_genuine_interruption_grants_exactly_once_and_leaves_unrelated_backoff_untouched(
    store_for_interruption_ownership,
):
    """The full required F7 lifecycle in one place: start -> wait_external
    DURING RUNNING -> resolve a genuine proof -> the budget is exhausted as
    designed -> grant PASSES exactly once; replaying the same checkpoint is
    DENIED; and an unrelated task's own retry backoff is never touched by
    T1's grant.
    """
    store, repo = store_for_interruption_ownership

    # T2 fails once on its own first, genuinely entering its declared backoff
    # window -- this must stay untouched by anything that happens to T1.
    store.start_task("test-run", "T2", worker_id="w-t2")
    store.fail_task("test-run", "T2", "ordinary T2 failure, enters its own backoff")
    t2_before = next(item for item in store.load("test-run")["tasks"] if item["id"] == "T2")
    assert t2_before["status"] == "NOT_READY" or t2_before["retryNotBefore"]
    retry_not_before_t2 = t2_before["retryNotBefore"]
    assert retry_not_before_t2

    # T1's real second (final) attempt is genuinely interrupted mid-run by an
    # external checkpoint, then resolved, then fails on its own -- exhausting
    # its budget exactly as the real M7 incident did.
    store.start_task("test-run", "T1", worker_id="w1")
    store.fail_task("test-run", "T1", "ordinary first failure")
    store.start_task("test-run", "T1", worker_id="w1b")
    _state, challenge = store.wait_external(
        "test-run",
        checkpoint_id="cp-real-interruption",
        task_id="T1",
        checkpoint_type="HUMAN_JUDGMENT_REQUIRED",
        principal="alice",
        provider="test-provider",
        reason="a genuine interruption of the final real attempt",
    )
    _resolve_checkpoint(store, repo, checkpoint_id="cp-real-interruption", task_id="T1", challenge=challenge)
    store.fail_task("test-run", "T1", "the resumed final attempt still fails on its own")

    task = next(item for item in store.load("test-run")["tasks"] if item["id"] == "T1")
    assert task["status"] == "FAILED"
    assert task["attempts"] == 2
    checkpoint = next(
        item for item in store.load("test-run")["externalCheckpoints"] if item["id"] == "cp-real-interruption"
    )
    assert checkpoint["interruptedAttempt"] == 2

    # The genuine interruption grants exactly once.
    store.grant_task_attempt(
        "test-run", "T1", reason="genuine interruption of the final attempt", actor="coordinator",
        checkpoint_id="cp-real-interruption",
    )
    task = next(item for item in store.load("test-run")["tasks"] if item["id"] == "T1")
    assert task["retryPolicy"]["maxAttempts"] == 3
    assert task["attempts"] == 2
    assert task["status"] == "READY"

    # Replaying the same resolved checkpoint a second time, after the task
    # genuinely runs again and re-exhausts its (now-raised) budget on its
    # own, is still denied -- the same real recovery event cannot be
    # replayed indefinitely.
    store.start_task("test-run", "T1", worker_id="w1c")
    store.fail_task("test-run", "T1", "the newly granted attempt also fails on its own")
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.grant_task_attempt(
            "test-run", "T1", reason="trying to reuse the same proof", actor="coordinator",
            checkpoint_id="cp-real-interruption",
        )
    assert excinfo.value.code == "RECOVERY_GRANT_ALREADY_CONSUMED"

    # T2's independent backoff window is wholly unaffected by T1's grant.
    t2_after = next(item for item in store.load("test-run")["tasks"] if item["id"] == "T2")
    assert t2_after["retryNotBefore"] == retry_not_before_t2
