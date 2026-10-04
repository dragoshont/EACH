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
def store_with_run(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "initial")

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()

    store = art.RunStore(repository=repo)
    store.create(
        goal="test goal",
        outcome="test outcome",
        criteria=[
            {
                "id": "security-policy-review-r4",
                "description": "requires both security and policy review",
                "verificationType": "deterministic",
                "blocking": True,
                "risk": "R4",
            }
        ],
        autonomy_scope="approved-program",
        run_id="test-run",
    )
    return store, repo


def _write_receipt(repo: Path, name: str, payload: dict) -> Path:
    evidence_dir = repo / ".architrave" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_security_gate_rejects_fail_or_revise_verdict_content_even_when_commit_matches(store_with_run):
    store, repo = store_with_run
    commit = store.load("test-run")["baseline"]["commit"]
    receipt_path = _write_receipt(
        repo,
        "security-fail",
        {"commit": commit, "status": "FAIL", "criteria": ["security-policy-review-r4"]},
    )
    store._record_security_verdict("test-run", artifact_id="security-fail", path=str(receipt_path.relative_to(repo)), evidence_refs=[])

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.record_gate(
            "test-run",
            gate_id="security-gate",
            task_id=None,
            gate_type="security",
            status="PASS",
            family="security",
            evidence_refs=["artifact:security-fail"],
            criteria=["security-policy-review-r4"],
        )
    assert excinfo.value.code == "SECURITY_RECEIPT"


def test_policy_gate_rejects_mismatched_criteria(store_with_run):
    store, repo = store_with_run
    commit = store.load("test-run")["baseline"]["commit"]
    receipt_path = _write_receipt(
        repo,
        "policy-mismatch",
        {"commit": commit, "status": "PASS", "criteria": ["different-criterion"]},
    )
    store._record_policy_decision("test-run", artifact_id="policy-mismatch", path=str(receipt_path.relative_to(repo)), evidence_refs=[])

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.record_gate(
            "test-run",
            gate_id="policy-gate",
            task_id=None,
            gate_type="policy",
            status="PASS",
            evidence_refs=["artifact:policy-mismatch"],
            criteria=["security-policy-review-r4"],
        )
    assert excinfo.value.code == "POLICY_RECEIPT"


def test_matching_security_and_policy_pass_verdicts_are_accepted(store_with_run):
    store, repo = store_with_run
    commit = store.load("test-run")["baseline"]["commit"]
    security_path = _write_receipt(
        repo,
        "security-pass",
        {"commit": commit, "status": "PASS", "criteria": ["security-policy-review-r4"]},
    )
    policy_path = _write_receipt(
        repo,
        "policy-pass",
        {"commit": commit, "status": "PASS", "criteria": ["security-policy-review-r4"]},
    )
    store._record_security_verdict("test-run", artifact_id="security-pass", path=str(security_path.relative_to(repo)), evidence_refs=[])
    store._record_policy_decision("test-run", artifact_id="policy-pass", path=str(policy_path.relative_to(repo)), evidence_refs=[])

    security_state = store.record_gate(
        "test-run",
        gate_id="security-gate",
        task_id=None,
        gate_type="security",
        status="PASS",
        family="security",
        evidence_refs=["artifact:security-pass"],
        criteria=["security-policy-review-r4"],
    )
    policy_state = store.record_gate(
        "test-run",
        gate_id="policy-gate",
        task_id=None,
        gate_type="policy",
        status="PASS",
        evidence_refs=["artifact:policy-pass"],
        criteria=["security-policy-review-r4"],
    )

    assert next(g for g in security_state["gateResults"] if g["id"] == "security-gate")["status"] == "PASS"
    assert next(g for g in policy_state["gateResults"] if g["id"] == "policy-gate")["status"] == "PASS"


def test_security_pass_cannot_substitute_for_a_policy_revise_requirement(store_with_run):
    store, repo = store_with_run
    commit = store.load("test-run")["baseline"]["commit"]
    security_path = _write_receipt(
        repo,
        "security-pass",
        {"commit": commit, "status": "PASS", "criteria": ["security-policy-review-r4"]},
    )
    policy_path = _write_receipt(
        repo,
        "policy-revise",
        {"commit": commit, "status": "REVISE", "criteria": ["security-policy-review-r4"]},
    )
    store._record_security_verdict("test-run", artifact_id="security-pass", path=str(security_path.relative_to(repo)), evidence_refs=[])
    store._record_policy_decision("test-run", artifact_id="policy-revise", path=str(policy_path.relative_to(repo)), evidence_refs=[])
    store.record_gate(
        "test-run",
        gate_id="security-gate",
        task_id=None,
        gate_type="security",
        status="PASS",
        family="security",
        evidence_refs=["artifact:security-pass"],
        criteria=["security-policy-review-r4"],
    )

    with pytest.raises(art.RuntimeFailure):
        store.record_gate(
            "test-run",
            gate_id="policy-gate",
            task_id=None,
            gate_type="policy",
            status="PASS",
            evidence_refs=["artifact:policy-revise"],
            criteria=["security-policy-review-r4"],
        )

    state = store.load("test-run")
    missing = art.missing_gate_requirements(state, state["acceptanceCriteria"])
    assert "security-policy-review-r4:policy" in missing
    assert "security-policy-review-r4:security" not in missing
