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
def harness(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "initial")

    each_home = tmp_path / "home" / ".each"
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("EACH_HOME", str(each_home))

    store = art.RunStore(repository=repo)
    store.create(
        goal="test goal",
        outcome="test outcome",
        criteria=[
            {
                "id": "m7-target-repair-verified",
                "description": "m7 reality",
                "verificationType": "reality",
                "surface": "runtime",
                "blocking": True,
                "risk": "R3",
            },
            {
                "id": "m8-target-repair-verified",
                "description": "m8 reality",
                "verificationType": "reality",
                "surface": "runtime",
                "blocking": True,
                "risk": "R3",
            },
            {
                "id": "base-target-repair-verified",
                "description": "non-milestone reality",
                "verificationType": "reality",
                "surface": "runtime",
                "blocking": True,
                "risk": "R3",
            },
        ],
        autonomy_scope="approved-program",
        run_id="test-run",
    )
    return store, repo, each_home


def _write_real_receipt(each_home: Path, run_id: str, *, spec_hash: str) -> Path:
    import os

    os.environ["EACH_HOME"] = str(each_home)
    from each.receipt import Receipt

    receipt = Receipt(
        run_id=run_id,
        spec={"taskId": "each-m8-xsystem-sandboxid-opt"},
        spec_hash=spec_hash,
        model_identity={
            "modelId": "ibm-granite/granite-8b-code-instruct-128k@deadbeef#sha256:cafe",
            "adapterType": "MLXRepairModel",
            "modelManifest": {"modelId": "ibm-granite/granite-8b-code-instruct-128k@deadbeef#sha256:cafe"},
        },
        prompt="repair this function",
        raw_completion="def f(): ...",
        patch_text="--- a\n+++ b\n",
        touched_paths=["xsystem.c"],
        materials={},
        executor_identity={"engine": "colima-each"},
        isolation_evidence={"command": ["docker", "run", "--network", "none"], "exit_code": 1, "stdout": ""},
        baseline_result={"exit_code": 1},
        repaired_result={"exit_code": 0},
        audit={"result": "UNAVAILABLE", "checks": {}},
        assurance_level="EACH-P1",
        outcome="REPAIR_VERIFIED",
        network_isolation_verified=True,
    )
    run_dir = each_home / "runs" / run_id
    json_path, _ = receipt.write(run_dir)
    return json_path


def _write_replay(each_home: Path, name: str, payload: dict) -> Path:
    run_dir = each_home / "runs" / name
    run_dir.mkdir(parents=True, exist_ok=True)
    replay_path = run_dir / "replay.json"
    replay_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return replay_path


def test_m8_target_repair_evidence_cannot_satisfy_an_m7_target_repair_criterion(harness):
    store, _repo, each_home = harness
    receipt_path = _write_real_receipt(
        each_home,
        "m8-real-run",
        spec_hash="2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
    )
    store._record_target_repair_receipt(
        "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
    )

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.record_gate(
            "test-run",
            gate_id="gate-m7",
            task_id=None,
            gate_type="reality",
            status="PASS",
            evidence_refs=["artifact:m8-evidence"],
            criteria=["m7-target-repair-verified"],
            surface="runtime",
        )
    assert excinfo.value.code == "EVIDENCE_SPEC_MISMATCH"


def test_same_milestone_target_repair_binding_still_works(harness):
    store, _repo, each_home = harness
    receipt_path = _write_real_receipt(
        each_home,
        "m8-real-run",
        spec_hash="2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
    )
    store._record_target_repair_receipt(
        "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
    )

    state = store.record_gate(
        "test-run",
        gate_id="gate-m8",
        task_id=None,
        gate_type="reality",
        status="PASS",
        evidence_refs=["artifact:m8-evidence"],
        criteria=["m8-target-repair-verified"],
        surface="runtime",
    )
    assert next(g for g in state["gateResults"] if g["id"] == "gate-m8")["status"] == "PASS"


def test_unknown_prefix_target_repair_criterion_is_unaffected(harness):
    store, _repo, each_home = harness
    receipt_path = _write_real_receipt(
        each_home,
        "m8-real-run",
        spec_hash="2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
    )
    store._record_target_repair_receipt(
        "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
    )

    state = store.record_gate(
        "test-run",
        gate_id="gate-base",
        task_id=None,
        gate_type="reality",
        status="PASS",
        evidence_refs=["artifact:m8-evidence"],
        criteria=["base-target-repair-verified"],
        surface="runtime",
    )
    assert next(g for g in state["gateResults"] if g["id"] == "gate-base")["status"] == "PASS"


def test_record_target_replay_receipt_happy_path(harness):
    store, repo, each_home = harness
    original_receipt = _write_real_receipt(
        each_home,
        "m8-real-run",
        spec_hash="2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
    )
    replay_path = _write_replay(
        each_home,
        "m8-replay",
        {
            "replay_of_original_receipt": str(original_receipt),
            "original_spec_hash": "2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
            "original_patch_hash": "patch-hash",
            "original_trajectory_hash": "trajectory-hash",
            "original_outcome": "REPAIR_VERIFIED",
            "fidelity_checks": "PASS: replay matched all retained hashes",
            "current_auditor_result": {"exact-substring": "UNAVAILABLE"},
            "current_auditor_rejected": False,
            "current_auditor_tool_versions": {"each-audit": "v0.1"},
        },
    )

    state = store._record_target_replay_receipt(
        "test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[]
    )
    artifact = next(item for item in state["artifacts"] if item["id"] == "m8-replay")
    summary = json.loads((repo / artifact["path"]).read_text(encoding="utf-8"))
    assert artifact["kind"] == "target-replay-receipt"
    assert summary["originalReceiptSha256"]
    assert summary["replayReceiptSha256"]
    assert summary["originalPatchHash"] == "patch-hash"


@pytest.mark.parametrize(
    "payload,expected_code",
    [
        (
            {
                "replay_of_original_receipt": "/does/not/matter.json",
                "original_spec_hash": "spec",
                "original_patch_hash": "patch",
                "original_trajectory_hash": "trajectory",
                "fidelity_checks": "FAIL",
                "current_auditor_result": {"exact-substring": "UNAVAILABLE"},
            },
            "TARGET_REPLAY_RECEIPT",
        ),
        (
            {
                "replay_of_original_receipt": "/does/not/matter.json",
                "original_spec_hash": "spec",
                "fidelity_checks": "PASS",
                "current_auditor_result": {"exact-substring": "UNAVAILABLE"},
            },
            "TARGET_REPLAY_RECEIPT",
        ),
    ],
)
def test_record_target_replay_receipt_rejects_missing_fidelity_or_original_hashes(harness, payload, expected_code):
    store, _repo, each_home = harness
    original_receipt = _write_real_receipt(
        each_home,
        "m8-real-run",
        spec_hash="2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
    )
    payload = {**payload, "replay_of_original_receipt": str(original_receipt)}
    replay_path = _write_replay(each_home, "m8-bad-replay", payload)

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt(
            "test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[]
        )
    assert excinfo.value.code == expected_code


def test_record_target_replay_receipt_rejects_a_path_outside_private_runs(harness):
    store, repo, _each_home = harness
    replay_path = repo / "outside-replay.json"
    replay_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt(
            "test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[]
        )
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"


def test_record_target_replay_receipt_rejects_a_symlinked_path(harness):
    store, _repo, each_home = harness
    original_receipt = _write_real_receipt(
        each_home,
        "m8-real-run",
        spec_hash="2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
    )
    replay_path = _write_replay(
        each_home,
        "m8-replay",
        {
            "replay_of_original_receipt": str(original_receipt),
            "original_spec_hash": "spec",
            "original_patch_hash": "patch",
            "original_trajectory_hash": "trajectory",
            "fidelity_checks": "PASS",
            "current_auditor_result": {"exact-substring": "UNAVAILABLE"},
        },
    )
    symlink_path = replay_path.parent / "replay-link.json"
    symlink_path.symlink_to(replay_path)

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt(
            "test-run", artifact_id="m8-replay", receipt_path=str(symlink_path), evidence_refs=[]
        )
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"
