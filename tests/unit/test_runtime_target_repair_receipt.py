"""Unit tests for RunStore._record_target_repair_receipt (reality-gate evidence
for M7/M8-style genuine local-model target-repair outcomes).

Real motivation (F1, GPT-6 Astra release review): the earlier implementation
accepted a caller-authored JSON summary that merely *asserted*
``"outcome": "REPAIR_VERIFIED"``/``"signatureVerification": "PASS"`` with no
binding whatsoever to any actual private receipt -- any caller could forge a
"PASS" by hand. This version instead takes a path to the REAL private receipt
under the private EACH runs store, independently re-runs the mature
``each verify --full`` signature + retained-materials verifier against it,
and derives every recorded fact directly from that re-verified receipt's own
content. These tests build genuine signed receipts (via ``each.receipt`` +
``each.attestation``) to prove the hardened path only accepts a receipt that
actually re-verifies, and rejects forged claims, tampering, FixtureModel
identities, non-verified outcomes, and private-store path escapes.
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


def _write_real_receipt(
    each_home: Path,
    run_id: str,
    *,
    outcome="REPAIR_VERIFIED",
    model_id=None,
    adapter_type="MLXRepairModel",
    network_isolation=True,
    spec_hash="2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
):
    """Build and sign a genuine receipt via the real each.receipt/each.attestation
    code paths, written under a private EACH_HOME/runs/<run_id>/ directory --
    exactly the shape _record_target_repair_receipt must independently re-verify."""
    import os

    os.environ["EACH_HOME"] = str(each_home)
    from each.receipt import Receipt

    receipt = Receipt(
        run_id=run_id,
        spec={"taskId": "each-m8-xsystem-sandboxid-opt"},
        spec_hash=spec_hash,
        model_identity={
            "modelId": model_id or "ibm-granite/granite-8b-code-instruct-128k@deadbeef#sha256:cafe",
            "adapterType": adapter_type,
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
        outcome=outcome,
        network_isolation_verified=network_isolation,
    )
    run_dir = each_home / "runs" / run_id
    json_path, _ = receipt.write(run_dir)
    return json_path


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

    run_store = art.RunStore(repository=repo)
    run_store.create(
        goal="test goal",
        outcome="test outcome",
        criteria=[{"id": "m8-repair", "description": "m8 repair", "verificationType": "reality", "surface": "runtime", "blocking": True}],
        autonomy_scope="approved-program",
        run_id="test-run",
    )
    return run_store, repo, each_home


def test_valid_real_receipt_registers_as_target_repair_artifact(harness):
    run_store, repo, each_home = harness
    receipt_path = _write_real_receipt(each_home, "m8-real-run")
    state = run_store._record_target_repair_receipt(
        "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
    )
    artifact = next(item for item in state["artifacts"] if item["id"] == "m8-evidence")
    assert artifact["kind"] == "target-repair-receipt"
    assert artifact["producer"] == "target-repair"
    summary_path = repo / artifact["path"]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["outcome"] == "REPAIR_VERIFIED"
    assert summary["signatureVerification"] == "PASS"
    assert summary["materialsVerification"] == "PASS"
    assert summary["targetRunId"] == "m8-real-run"
    assert "fixture" not in summary["modelId"].lower()


def test_can_satisfy_a_reality_gate_and_pass_criterion(harness):
    run_store, _repo, each_home = harness
    receipt_path = _write_real_receipt(each_home, "m8-real-run")
    run_store._record_target_repair_receipt(
        "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
    )
    run_store.record_gate(
        "test-run",
        gate_id="gate-m8",
        task_id=None,
        gate_type="reality",
        status="PASS",
        evidence_refs=["artifact:m8-evidence"],
        criteria=["m8-repair"],
    )
    result = run_store.set_criterion("test-run", "m8-repair", "PASS", ["gate:gate-m8"])
    criterion = next(item for item in result["acceptanceCriteria"] if item["id"] == "m8-repair")
    assert criterion["status"] == "PASS"


def test_rejects_a_hand_written_claim_file_that_is_not_a_real_receipt(harness):
    """The original F1 attack: a caller writes a JSON file that merely
    *asserts* PASS, with no real signature/materials/receipt behind it."""
    run_store, _repo, each_home = harness
    forged = each_home / "runs" / "forged-run"
    forged.mkdir(parents=True)
    forged_path = forged / "receipt.json"
    forged_path.write_text(
        json.dumps(
            {
                "specHash": "2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
                "runId": "forged-run",
                "outcome": "REPAIR_VERIFIED",
                "signatureVerification": "PASS",
                "materialsVerification": "PASS",
                "networkIsolationVerified": True,
                "modelIdentity": {"modelId": "ibm-granite/granite-8b-code-instruct-128k"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_repair_receipt(
            "test-run", artifact_id="m8-evidence", receipt_path=str(forged_path), evidence_refs=[]
        )


def test_rejects_a_tampered_receipt_whose_signature_no_longer_verifies(harness):
    run_store, _repo, each_home = harness
    receipt_path = _write_real_receipt(each_home, "m8-tampered-run")
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    data["outcome"] = "REPAIR_VERIFIED"
    data["baselineResult"] = {"exit_code": 0}  # tamper a non-attestation-exempt field
    receipt_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_repair_receipt(
            "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
        )


@pytest.mark.parametrize("outcome", ["PATCH_REJECTED: no acceptance exit", "REPAIRED_RUN_INCONCLUSIVE: ambiguous"])
def test_rejects_a_real_receipt_that_does_not_declare_a_verified_outcome(harness, outcome):
    run_store, _repo, each_home = harness
    receipt_path = _write_real_receipt(each_home, "m8-unverified-run", outcome=outcome)
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_repair_receipt(
            "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
        )


def test_rejects_a_real_receipt_without_network_isolation_verified(harness):
    run_store, _repo, each_home = harness
    receipt_path = _write_real_receipt(each_home, "m8-no-isolation-run", network_isolation=False)
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_repair_receipt(
            "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
        )


def test_rejects_a_fixturemodel_identity(harness):
    """No FixtureModel self-test substitution may ever satisfy a real target-repair criterion."""
    run_store, _repo, each_home = harness
    receipt_path = _write_real_receipt(each_home, "m8-fixture-run", model_id="FixtureModel/self-test")
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_repair_receipt(
            "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
        )


def test_rejects_a_receipt_that_records_fixturemodel_as_the_adapter_type(harness):
    run_store, _repo, each_home = harness
    receipt_path = _write_real_receipt(
        each_home,
        "m8-fixture-adapter-run",
        model_id="totally-real-model-not-fixture-i-promise",
        adapter_type="FixtureModel",
    )
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_repair_receipt(
            "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
        )


def test_rejects_a_receipt_path_outside_the_private_runs_store(harness):
    run_store, repo, each_home = harness
    receipt_path = _write_real_receipt(each_home, "m8-real-run")
    outside = repo / "receipt.json"
    outside.write_text(receipt_path.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_repair_receipt(
            "test-run", artifact_id="m8-evidence", receipt_path=str(outside), evidence_refs=[]
        )


def test_rejects_a_non_absolute_receipt_path(harness):
    run_store, _repo, each_home = harness
    _write_real_receipt(each_home, "m8-real-run")
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_repair_receipt(
            "test-run", artifact_id="m8-evidence", receipt_path="runs/m8-real-run/receipt.json", evidence_refs=[]
        )


def test_rejects_a_symlinked_receipt_path(harness):
    run_store, _repo, each_home = harness
    receipt_path = _write_real_receipt(each_home, "m8-real-run")
    symlink_path = each_home / "runs" / "m8-real-run" / "receipt-link.json"
    symlink_path.symlink_to(receipt_path)
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_repair_receipt(
            "test-run", artifact_id="m8-evidence", receipt_path=str(symlink_path), evidence_refs=[]
        )
