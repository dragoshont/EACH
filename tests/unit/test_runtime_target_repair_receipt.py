"""Unit tests for RunStore._record_target_repair_receipt (reality-gate evidence
for M7/M8-style genuine local-model target-repair outcomes).

Real motivation: M7/M8's actual receipts (prompts, completions, patch text,
target source) must stay private under ``runs_dir()`` and are never copied
into the public-repo-adjacent Run evidence store. This validator enforces
that only a sanitized, source-free summary -- outcome classification,
independently re-checked signature/materials verification, spec hash, and
network-isolation status -- can ever satisfy a "reality" acceptance
criterion for a target repair, and that the summary can never smuggle in
raw private material under a differently-named key.
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
def store(tmp_path, monkeypatch):
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

    run_store = art.RunStore(repository=repo)
    run_store.create(
        goal="test goal",
        outcome="test outcome",
        criteria=[{"id": "m8-repair", "description": "m8 repair", "verificationType": "reality", "surface": "runtime", "blocking": True}],
        autonomy_scope="approved-program",
        run_id="test-run",
    )
    return run_store, repo


def _write_summary(repo: Path, name: str, **overrides) -> str:
    summary = {
        "specId": "each-m8-xsystem-sandboxid-opt",
        "specHash": "2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
        "targetRunId": "m8-xsystem-sandboxid-opt-fullsource-20261003",
        "outcome": "REPAIR_VERIFIED",
        "signatureVerification": "PASS",
        "materialsVerification": "PASS",
        "networkIsolationVerified": True,
    }
    summary.update(overrides)
    path = repo / name
    path.write_text(json.dumps(summary), encoding="utf-8")
    return name


def test_valid_summary_registers_as_target_repair_artifact(store):
    run_store, repo = store
    path = _write_summary(repo, "summary.json")
    state = run_store._record_target_repair_receipt(
        "test-run", artifact_id="m8-evidence", path=path, evidence_refs=[]
    )
    artifact = next(item for item in state["artifacts"] if item["id"] == "m8-evidence")
    assert artifact["kind"] == "target-repair-receipt"
    assert artifact["producer"] == "target-repair"


def test_can_satisfy_a_reality_gate_and_pass_criterion(store):
    run_store, repo = store
    path = _write_summary(repo, "summary.json")
    run_store._record_target_repair_receipt("test-run", artifact_id="m8-evidence", path=path, evidence_refs=[])
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


@pytest.mark.parametrize(
    "overrides",
    [
        {"outcome": "PATCH_REJECTED: no acceptance exit"},
        {"outcome": "REPAIRED_RUN_INCONCLUSIVE: ambiguous"},
        {"signatureVerification": "FAIL"},
        {"materialsVerification": "UNAVAILABLE"},
        {"networkIsolationVerified": False},
    ],
)
def test_rejects_summary_that_does_not_show_a_genuine_verified_repair(store, overrides):
    run_store, repo = store
    path = _write_summary(repo, "summary.json", **overrides)
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_repair_receipt("test-run", artifact_id="m8-evidence", path=path, evidence_refs=[])


def test_rejects_summary_missing_required_fields(store):
    run_store, repo = store
    path = repo / "summary.json"
    path.write_text(json.dumps({"specId": "x"}), encoding="utf-8")
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_repair_receipt("test-run", artifact_id="m8-evidence", path="summary.json", evidence_refs=[])


@pytest.mark.parametrize("leaked_key", ["prompt", "rawCompletion", "patchText", "numberedSource", "diff"])
def test_rejects_summary_carrying_raw_private_material(store, leaked_key):
    run_store, repo = store
    path = _write_summary(repo, "summary.json", **{leaked_key: "should never be here"})
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_repair_receipt("test-run", artifact_id="m8-evidence", path=path, evidence_refs=[])
