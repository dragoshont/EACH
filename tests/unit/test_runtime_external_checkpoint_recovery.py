"""Regression tests for RunStore.reissue_challenge (M7 operational recovery).

Real incident: ``wait_external`` deliberately persists only a one-time
challenge's SHA-256 hash in canonical Run state, never the secret itself --
the secret is returned once to the caller and must be relayed to
``resolve_external`` out of band. During the M7 checkpoint for this project,
that one-time return value was only ever printed into a temporary shell-output
file, which was lost across a host/session transition before the checkpoint
could be resolved -- leaving a genuinely-approved spec with no way to close
its checkpoint, short of fabricating a new challenge or hand-editing Run
state (both explicitly forbidden).

``reissue_challenge`` is the narrow, auditable recovery path: it requires a
trusted coordinator/human actor and an ALREADY-REGISTERED, unconsumed
external-proof artifact that genuinely matches the checkpoint's id/principal/
provider (the exact same binding ``resolve_external`` itself enforces), so it
can never manufacture approval that was not already real -- it only ever
re-opens the door for evidence that already exists.
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


@pytest.fixture()
def store_with_pending_checkpoint(tmp_path, monkeypatch):
    """A real Run, in a real (throwaway) git repo, with one task genuinely
    parked at a PENDING external checkpoint -- mirroring the exact M7 shape.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "initial")

    # Runtime keys/state live outside the repo by default; keep them isolated per test.
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
            "objective": "needs human approval",
            "acceptanceCriteria": ["C1"],
            "risk": "R3",
        },
    )
    state, challenge = store.wait_external(
        "test-run",
        checkpoint_id="cp1",
        task_id="T1",
        checkpoint_type="HUMAN_JUDGMENT_REQUIRED",
        principal="alice",
        provider="test-provider",
        reason="needs a human decision",
    )
    assert state["status"] == "WAITING_EXTERNAL"
    return store, repo, challenge


def _register_proof(store: art.RunStore, repo: Path, *, checkpoint_id="cp1", principal="alice", provider="test-provider", artifact_id="proof1") -> str:
    proof_path = repo / "proof.json"
    proof_path.write_text(
        json.dumps({"checkpointId": checkpoint_id, "principal": principal, "provider": provider, "userMessage": "i approve"}),
        encoding="utf-8",
    )
    store._record_external_proof(
        "test-run",
        artifact_id=artifact_id,
        path="proof.json",
        evidence_refs=[],
    )
    return f"artifact:{artifact_id}"


def test_reissue_with_a_matching_registered_proof_lets_resolve_succeed(store_with_pending_checkpoint):
    store, repo, _lost_challenge = store_with_pending_checkpoint
    proof_ref = _register_proof(store, repo)

    state, new_challenge = store.reissue_challenge(
        "test-run",
        checkpoint_id="cp1",
        proof_ref=proof_ref,
        actor="coordinator",
    )
    assert state["status"] == "WAITING_EXTERNAL"

    resolved = store.resolve_external(
        "test-run",
        checkpoint_id="cp1",
        resolution_ref=proof_ref,
        challenge=new_challenge,
        actor="human:alice",
    )
    checkpoint = next(item for item in resolved["externalCheckpoints"] if item["id"] == "cp1")
    assert checkpoint["status"] == "RESOLVED"
    task = next(item for item in resolved["tasks"] if item["id"] == "T1")
    assert task["status"] == "READY"


def test_reissue_rejects_a_proof_with_the_wrong_principal(store_with_pending_checkpoint):
    store, repo, _lost_challenge = store_with_pending_checkpoint
    # _record_external_proof itself already refuses to register a proof that
    # does not match the checkpoint's principal/provider; reconstruct a
    # mismatched artifact through the lower-level primitive directly, so that
    # reissue_challenge's OWN (defense-in-depth) binding check is what is
    # actually under test here, not registration-time validation.
    (repo / "mismatched-proof.json").write_text(
        json.dumps({"checkpointId": "cp1", "principal": "mallory", "provider": "test-provider"}),
        encoding="utf-8",
    )
    store._record_artifact(
        "test-run",
        artifact_id="mismatched-proof",
        kind="external-proof",
        path="mismatched-proof.json",
        evidence_refs=[],
        actor="external-checkpoint",
        producer="external-proof",
    )

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.reissue_challenge(
            "test-run",
            checkpoint_id="cp1",
            proof_ref="artifact:mismatched-proof",
            actor="coordinator",
        )
    assert excinfo.value.code == "EXTERNAL_PROOF_MISMATCH"


def test_reissue_rejects_evidence_from_an_untrusted_producer(store_with_pending_checkpoint):
    store, repo, _lost_challenge = store_with_pending_checkpoint
    # record_artifact uses producer="coordinator", not "external-proof" -- an
    # ordinary artifact must never be usable to reissue a checkpoint challenge.
    (repo / "not-a-proof.json").write_text("{}", encoding="utf-8")
    store.record_artifact(
        "test-run",
        artifact_id="not-a-proof",
        kind="external-proof",
        path="not-a-proof.json",
        evidence_refs=[],
    )

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.reissue_challenge(
            "test-run",
            checkpoint_id="cp1",
            proof_ref="artifact:not-a-proof",
            actor="coordinator",
        )
    assert excinfo.value.code == "UNTRUSTED_RESOLUTION"


def test_reissue_rejects_an_already_resolved_checkpoint(store_with_pending_checkpoint):
    store, repo, original_challenge = store_with_pending_checkpoint
    # Register BOTH proofs while the checkpoint is still genuinely PENDING --
    # _record_external_proof itself refuses registration once resolved.
    proof_ref = _register_proof(store, repo)
    proof_ref_2 = _register_proof(store, repo, artifact_id="proof2")
    store.resolve_external(
        "test-run",
        checkpoint_id="cp1",
        resolution_ref=proof_ref,
        challenge=original_challenge,
        actor="human:alice",
    )

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.reissue_challenge(
            "test-run",
            checkpoint_id="cp1",
            proof_ref=proof_ref_2,
            actor="coordinator",
        )
    assert excinfo.value.code == "EXTERNAL_CHECKPOINT_TERMINAL"


def test_the_original_lost_challenge_is_invalidated_once_reissued(store_with_pending_checkpoint):
    store, repo, original_challenge = store_with_pending_checkpoint
    proof_ref = _register_proof(store, repo)
    store.reissue_challenge(
        "test-run",
        checkpoint_id="cp1",
        proof_ref=proof_ref,
        actor="coordinator",
    )

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.resolve_external(
            "test-run",
            checkpoint_id="cp1",
            resolution_ref=proof_ref,
            challenge=original_challenge,
            actor="human:alice",
        )
    assert "invalid" in excinfo.value.message.lower()


def test_reissue_requires_a_trusted_coordinator_or_human_actor(store_with_pending_checkpoint):
    store, repo, _lost_challenge = store_with_pending_checkpoint
    proof_ref = _register_proof(store, repo)

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.reissue_challenge(
            "test-run",
            checkpoint_id="cp1",
            proof_ref=proof_ref,
            actor="worker:some-worker",
        )
    assert excinfo.value.code == "UNTRUSTED_RESOLUTION"


def test_reissue_is_recorded_as_a_genuine_hash_chained_event(store_with_pending_checkpoint):
    store, repo, _lost_challenge = store_with_pending_checkpoint
    proof_ref = _register_proof(store, repo)
    before = store.events("test-run")

    store.reissue_challenge(
        "test-run",
        checkpoint_id="cp1",
        proof_ref=proof_ref,
        actor="coordinator",
    )

    after = store.events("test-run")
    assert len(after) == len(before) + 1
    new_event = after[-1]
    assert new_event["type"] == "external.challenge_reissued"
    assert new_event["evidenceRefs"] == [proof_ref]
    # The hash chain must still validate end to end after the reissue event.
    state = store.load("test-run")
    assert state["eventCursor"]["lastHash"] == new_event["hash"]
    art.validate_run(state)
