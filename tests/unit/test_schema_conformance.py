"""F6 regression: real standards-conformant JSON Schema validation of the
durable architrave.run.v2 state.

``harness/schemas/run-v2.schema.json`` declares ``additionalProperties:
false`` at every object level, which previously omitted several fields that
the runtime genuinely emits during ordinary operation: artifact/gate
``sourceCommit`` (F2/F7), external checkpoint ``challengeReissuedAt``/
``challengeReissueCount`` (M7 recovery), task ``retryNotBefore`` (bounded
retry backoff), and the ``target-repair`` artifact producer (M7/M8 reality
evidence). A schema this strict that does not actually match the real
runtime's own output is not a conformance proof -- it silently could never
have validated a real Run at all. This drives one Run through enough of its
real lifecycle to emit every one of those fields, then validates the whole
resulting state against the actual schema with a real JSON Schema engine
(not the runtime's own hand-rolled ``validate_run`` checks, which this is
deliberately independent of).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "harness"))
import architrave_runtime as art

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[2] / "harness" / "schemas" / "run-v2.schema.json").read_text(encoding="utf-8")
)


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
            {"id": "C1", "description": "c1", "verificationType": "deterministic", "blocking": True, "risk": "R1"},
            {"id": "C2", "description": "c2", "verificationType": "external", "blocking": True, "risk": "R3"},
            {
                "id": "C3",
                "description": "reality criterion",
                "verificationType": "reality",
                "blocking": True,
                "risk": "R3",
                "surface": "runtime",
                "targetEvidence": {
                    "kind": "target-repair-receipt",
                    "purpose": "target-repair-verified",
                    "targetSpecHash": "schema-test-spec-hash",
                },
            },
        ],
        autonomy_scope="approved-program",
        run_id="test-run",
    )
    return store, repo


def test_a_freshly_created_run_conforms_to_run_v2_schema(store_with_run):
    store, _repo = store_with_run
    jsonschema.validate(instance=store.load("test-run"), schema=SCHEMA)


def test_a_run_exercising_retryNotBefore_target_repair_and_checkpoint_reissue_fields_conforms(store_with_run):
    store, repo = store_with_run

    # retryNotBefore: add a task, make it attempt and fail with a retryable
    # backoff so retryNotBefore is populated with a real timestamp.
    store.add_task(
        "test-run",
        {
            "id": "T1",
            "title": "T1",
            "objective": "flaky",
            "acceptanceCriteria": ["C1"],
            "risk": "R1",
            "maxAttempts": 3,
            "backoffSeconds": 1,
            "retryable": ["TRANSIENT"],
        },
    )
    store.fail_task("test-run", task_id="T1", reason="TRANSIENT")
    state = store.load("test-run")
    task = next(item for item in state["tasks"] if item["id"] == "T1")
    assert task["retryNotBefore"] is not None
    jsonschema.validate(instance=state, schema=SCHEMA)

    # target-repair producer + artifact/gate sourceCommit: register a
    # target-repair receipt artifact and bind a reality gate to it.
    evidence_dir = repo / ".architrave" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    summary_path = evidence_dir / "m7-target-repair.target-repair-summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "purpose": "target-repair-verified",
                "specHash": "schema-test-spec-hash",
                "outcome": "REPAIR_VERIFIED",
            }
        ),
        encoding="utf-8",
    )
    store._record_artifact(
        "test-run",
        artifact_id="m7-target-repair",
        kind="target-repair-receipt",
        producer="target-repair",
        actor="coordinator",
        path=str(summary_path.relative_to(repo)),
        evidence_refs=[],
    )
    store.record_gate(
        "test-run",
        gate_id="gate-reality-1",
        task_id=None,
        gate_type="reality",
        status="PASS",
        evidence_refs=["artifact:m7-target-repair"],
        criteria=["C3"],
        surface="runtime",
    )
    state = store.load("test-run")
    artifact = next(item for item in state["artifacts"] if item["id"] == "m7-target-repair")
    assert artifact["producer"] == "target-repair"
    assert artifact["sourceCommit"]
    gate = next(item for item in state["gateResults"] if item["id"] == "gate-reality-1")
    assert gate["sourceCommit"]
    jsonschema.validate(instance=state, schema=SCHEMA)

    # challengeReissuedAt/challengeReissueCount: a second task waits
    # externally, then its challenge is reissued against a registered proof.
    store.add_task(
        "test-run",
        {"id": "T2", "title": "T2", "objective": "needs approval", "acceptanceCriteria": ["C2"], "risk": "R3"},
    )
    store.wait_external(
        "test-run",
        checkpoint_id="cp1",
        task_id="T2",
        checkpoint_type="HUMAN_JUDGMENT_REQUIRED",
        principal="alice",
        provider="test-provider",
        reason="needs a human decision",
    )
    proof_path = repo / "proof.json"
    proof_path.write_text(
        json.dumps({"checkpointId": "cp1", "principal": "alice", "provider": "test-provider"}),
        encoding="utf-8",
    )
    store._record_external_proof("test-run", artifact_id="proof1", path="proof.json", evidence_refs=[])
    store.reissue_challenge("test-run", checkpoint_id="cp1", proof_ref="artifact:proof1", actor="coordinator")

    state = store.load("test-run")
    checkpoint = next(item for item in state["externalCheckpoints"] if item["id"] == "cp1")
    assert checkpoint["challengeReissuedAt"]
    assert checkpoint["challengeReissueCount"] == 1
    jsonschema.validate(instance=state, schema=SCHEMA)
