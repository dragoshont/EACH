from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from each.attestation import attest_receipt
from each.executor.base import ExecutionResult
from each.hashing import sha256_bytes
from each.receipt import Receipt

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "harness"))
import architrave_runtime as art

_M7_SPEC_HASH = "8499cf22255d11c15f1f446c19d504bec21ac03dfbe524439b2af377c65e39b8"
_M8_SPEC_HASH = "2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78"
_PATCH = """--- a/xsystem.c
+++ b/xsystem.c
@@ -1,2 +1,2 @@
-int sandbox_id(void) { return 0; }
+int sandbox_id(void) { return 1; }
 int keep(void) { return 7; }
"""
_ORIGINAL_SOURCE = "int sandbox_id(void) { return 0; }\nint keep(void) { return 7; }\n"
_REPAIRED_SOURCE = "int sandbox_id(void) { return 1; }\nint keep(void) { return 7; }\n"
# A genuinely classified-negative candidate: the patch touches the file but
# never fixes the actual bug (sandbox_id still returns 0), so the fake
# replay executor's acceptance command still fails after the patch -- the
# same decisive, non-contradictory negative the original honestly recorded.
_NEGATIVE_PATCH = """--- a/xsystem.c
+++ b/xsystem.c
@@ -1,2 +1,2 @@
 int sandbox_id(void) { return 0; }
-int keep(void) { return 7; }
+int keep(void) { return 8; }
"""
_NEGATIVE_REPAIRED_SOURCE = "int sandbox_id(void) { return 0; }\nint keep(void) { return 8; }\n"



def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _real_model_identity() -> dict[str, object]:
    return {
        "modelId": "ibm-granite/granite-8b-code-instruct-128k@deadbeef#sha256:cafe",
        "adapterType": "MLXRepairModel",
        "adapterClassPath": "each.models.mlx_model.MLXRepairModel",
        "modelManifest": {
            "schemaVersion": "0.1",
            "repoId": "ibm-granite/granite-8b-code-instruct-128k",
            "revision": "deadbeefcafebabe",
            "license": "apache-2.0",
            "runtime": {"name": "mlx-lm", "version": "0.0-test"},
            "quantization": {"groupSize": 128},
            "weightsSha256": {"model.safetensors": "cafe"},
            "tokenizerSha256": "face",
            "configSha256": "bead",
            "filesSha256": {"config.json": "bead", "model.safetensors": "cafe", "tokenizer.json": "face"},
            "conversionChain": "none",
            "maxPositionEmbeddings": 8192,
        },
        "generationParameters": {"maxTokens": 256, "temperature": 0.0, "sampling": "greedy", "seed": None},
    }


def _candidate_subject_sha() -> str:
    return sha256_bytes(_REPAIRED_SOURCE.encode("utf-8"))


def _rewrite_signed_receipt(receipt_path: Path, mutate) -> None:
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload = mutate(payload)
    payload["attestation"] = attest_receipt({key: value for key, value in payload.items() if key != "attestation"})
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_original_receipt(
    each_home: Path,
    run_id: str,
    *,
    spec_hash: str = _M8_SPEC_HASH,
    outcome: str = "REPAIR_VERIFIED",
    patch_text: str = _PATCH,
    repaired_source: str = _REPAIRED_SOURCE,
) -> Path:
    import os

    from each.spec import ApprovedSpec, make_spec_packet

    os.environ["EACH_HOME"] = str(each_home)
    source_root = each_home / "sources" / run_id
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "xsystem.c").write_text(_ORIGINAL_SOURCE, encoding="utf-8")
    # Regression requirement: the real production spec contract -- never a
    # handmade camelCase JSON object -- so the replay path's snake_case
    # build_commands/acceptance_commands decoding is exercised against the
    # actual canonical shape SpecPacket.content() emits.
    approved_spec = ApprovedSpec.approve(
        make_spec_packet(
            task_id="each-m8-xsystem-sandboxid-opt",
            target_repo="local-fixture",
            target_ref="HEAD",
            problem_statement="repair sandbox_id",
            allowed_paths=["xsystem.c"],
            build_commands=[["python", "-c", "print('build')"]],
            acceptance_commands=[["python", "-c", "print('test')"]],
            forbidden_sources=[],
            approved_by="test-human",
        )
    )
    receipt = Receipt(
        run_id=run_id,
        spec=approved_spec.to_dict()["packet"],
        spec_hash=spec_hash,
        model_identity=_real_model_identity(),
        prompt="repair this function",
        raw_completion=patch_text,
        patch_text=patch_text,
        touched_paths=["xsystem.c"],
        materials={"xsystem.c": sha256_bytes(_ORIGINAL_SOURCE.encode("utf-8"))},
        executor_identity={
            "executor": "container",
            "dockerContext": "colima-each",
            "image": "python@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f",
            "network": "none",
            "memoryLimit": "512m",
            "cpuLimit": "2",
        },
        isolation_evidence={"command": ["docker", "run", "--network", "none"], "exit_code": 1, "stdout": ""},
        baseline_result={"exit_code": 1},
        repaired_result={"exit_code": 0 if outcome == "REPAIR_VERIFIED" else 1},
        audit={
            "checks": {"exact-substring": {"status": "UNAVAILABLE", "detail": "no corpus"}},
            "toolVersions": {"each-audit": "v0.1-mvp"},
            "corpusRevision": "none",
        },
        assurance_level="EACH-P2",
        outcome=outcome,
        network_isolation_verified=True,
        attempts=[{"attempt": 1, "proposal_format": "diff", "outcome": outcome}],
        selected_attempt=1,
        audit_subject_sha256=sha256_bytes(repaired_source.encode("utf-8")),
    )
    run_dir = each_home / "runs" / run_id
    json_path, _ = receipt.write(run_dir, materials_source=source_root)
    return json_path


def _write_replay_request(each_home: Path, name: str, payload: dict[str, object]) -> Path:
    run_dir = each_home / "runs" / name
    run_dir.mkdir(parents=True, exist_ok=True)
    replay_path = run_dir / "replay.json"
    replay_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return replay_path


def _expected_original_fields(receipt_path: Path) -> dict[str, object]:
    from each.outcome import sanitize_outcome_class

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    return {
        "specHash": receipt["specHash"],
        "patchHash": receipt["patchHash"],
        "trajectoryHash": receipt["trajectoryHash"],
        "modelId": receipt["modelIdentity"]["modelId"],
        "adapterClassPath": receipt["modelIdentity"]["adapterClassPath"],
        "selectedAttempt": receipt["selectedAttempt"],
        "outcome": sanitize_outcome_class(str(receipt["outcome"])),
        "targetRunId": receipt["runId"],
        "auditSubjectSha256": receipt["auditSubjectSha256"],
        "producerCommit": receipt["producerCommit"],
    }


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
                "targetEvidence": {
                    "kind": "target-repair-receipt",
                    "purpose": "target-repair-verified",
                    "targetSpecHash": _M7_SPEC_HASH,
                },
                "blocking": True,
                "risk": "R3",
            },
            {
                "id": "m8-target-repair-verified",
                "description": "m8 reality",
                "verificationType": "reality",
                "surface": "runtime",
                "targetEvidence": {
                    "kind": "target-repair-receipt",
                    "purpose": "target-repair-verified",
                    "targetSpecHash": _M8_SPEC_HASH,
                },
                "blocking": True,
                "risk": "R3",
            },
            {
                "id": "arbitrary-replay-proof",
                "description": "arbitrary reality criterion",
                "verificationType": "reality",
                "surface": "runtime",
                "targetEvidence": {
                    "kind": "target-repair-receipt",
                    "purpose": "target-repair-verified",
                    "targetSpecHash": _M8_SPEC_HASH,
                },
                "blocking": True,
                "risk": "R3",
            },
            {
                "id": "generic-runtime-criterion",
                "description": "generic runtime criterion",
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


def test_m8_target_repair_evidence_cannot_satisfy_an_m7_target_repair_criterion(harness):
    store, _repo, each_home = harness
    receipt_path = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    store._record_target_repair_receipt("test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[])

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
    assert excinfo.value.code == "EVIDENCE_KIND_MISMATCH" or excinfo.value.code == "EVIDENCE_SPEC_MISMATCH"


def test_target_evidence_owning_criterion_rejects_non_target_repair_producer_evidence(harness):
    """A *-target-repair-verified criterion must never be satisfiable by a
    DIFFERENT reality-gate producer (external-proof/mutation/legibility) just
    because that producer is independently trusted for OTHER reality
    purposes and happens to also report surface "runtime". Before this fix,
    the entire targetEvidence kind/purpose/specHash validation block was
    gated on `"target-repair" in producers`, so binding ONLY an
    external-proof artifact (no target-repair producer at all) to
    m8-target-repair-verified skipped validation entirely and the gate
    registered PASS with zero ownership checking."""
    store, repo, _each_home = harness
    evidence_dir = repo / ".architrave" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = evidence_dir / "bogus-external-proof.json"
    artifact_path.write_text(json.dumps({"note": "stub reality evidence, not a target-repair receipt"}), encoding="utf-8")
    store._record_artifact(
        "test-run",
        artifact_id="bogus-external-proof",
        kind="external-proof",
        producer="external-proof",
        actor="external-checkpoint",
        path=str(artifact_path.relative_to(repo)),
        evidence_refs=[],
    )

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.record_gate(
            "test-run",
            gate_id="gate-bypass-attempt",
            task_id=None,
            gate_type="reality",
            status="PASS",
            evidence_refs=["artifact:bogus-external-proof"],
            criteria=["m8-target-repair-verified"],
            surface="runtime",
        )
    assert excinfo.value.code == "EVIDENCE_KIND_MISMATCH"


def test_same_milestone_target_repair_binding_still_works(harness):
    store, _repo, each_home = harness
    receipt_path = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    store._record_target_repair_receipt("test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[])

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


def test_arbitrarily_named_target_repair_criterion_requires_explicit_ownership_data(tmp_path, monkeypatch):
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
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.create(
            goal="test goal",
            outcome="test outcome",
            criteria=[
                {
                    "id": "arbitrary-repair-proof",
                    "description": "arbitrary target-evidence criterion",
                    "verificationType": "reality",
                    "surface": "runtime",
                    "targetEvidence": {"kind": "target-repair-receipt"},
                    "blocking": True,
                    "risk": "R3",
                }
            ],
            autonomy_scope="approved-program",
            run_id="bad-run",
        )
    assert excinfo.value.code == "INVALID_CRITERION"


def test_arbitrarily_named_target_repair_criterion_uses_criterion_owned_spec_and_purpose_not_its_name(harness):
    store, _repo, each_home = harness
    receipt_path = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    store._record_target_repair_receipt("test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[])

    state = store.record_gate(
        "test-run",
        gate_id="gate-arbitrary",
        task_id=None,
        gate_type="reality",
        status="PASS",
        evidence_refs=["artifact:m8-evidence"],
        criteria=["arbitrary-replay-proof"],
        surface="runtime",
    )
    assert next(g for g in state["gateResults"] if g["id"] == "gate-arbitrary")["status"] == "PASS"

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.record_gate(
            "test-run",
            gate_id="gate-generic",
            task_id=None,
            gate_type="reality",
            status="PASS",
            evidence_refs=["artifact:m8-evidence"],
            criteria=["generic-runtime-criterion"],
            surface="runtime",
        )
    assert excinfo.value.code == "EVIDENCE_BINDING_REQUIRED"


class _FakeReplayExecutor:
    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs

    def run(self, command: list[str], worktree: Path, *, protected_paths: tuple[str, ...] = ()) -> ExecutionResult:
        del protected_paths
        if any("build" in part for part in command):
            # The fake build step always succeeds; only acceptance is
            # driven by the (candidate-controlled) source content below.
            return ExecutionResult(tuple(command), 0, "build ok\n", "")
        source = (worktree / "xsystem.c").read_text(encoding="utf-8")
        if "return 1" in source:
            return ExecutionResult(("python",), 0, "1 passed in 0.01s\n", "")
        return ExecutionResult(("python",), 1, "1 failed in 0.01s\n", "")



def _replay_payload(store: art.RunStore, receipt_path: Path) -> dict[str, object]:
    return {
        "purpose": "replay-validation",
        "originalReceiptPath": str(receipt_path),
        "original": _expected_original_fields(receipt_path),
        "executionCommit": store.repository_identity()["commit"],
    }


def test_record_target_replay_receipt_happy_path(harness, monkeypatch):
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, repo, each_home = harness
    original_receipt = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    replay_path = _write_replay_request(each_home, "m8-replay", _replay_payload(store, original_receipt))

    state = store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    artifact = next(item for item in state["artifacts"] if item["id"] == "m8-replay")
    summary = json.loads((repo / artifact["path"]).read_text(encoding="utf-8"))
    assert artifact["kind"] == "target-replay-receipt"
    assert summary["purpose"] == "replay-validation"
    assert summary["specHash"] == _M8_SPEC_HASH
    assert "originalReceiptPath" not in summary
    assert summary["currentAuditorCheckStatuses"]
    assert summary["baselineExecution"]["acceptance"][0]["exitCode"] == 1
    assert summary["replayExecution"]["acceptance"][0]["exitCode"] == 0


def test_record_target_replay_receipt_rejects_malformed_original_receipt(harness, monkeypatch):
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, _repo, each_home = harness
    original_path = each_home / "runs" / "bad-original" / "receipt.json"
    original_path.parent.mkdir(parents=True)
    original_path.write_text("{not json}\n", encoding="utf-8")
    replay_path = _write_replay_request(
        each_home,
        "m8-replay",
        {
            "purpose": "replay-validation",
            "originalReceiptPath": str(original_path),
            "original": {},
            "executionCommit": store.repository_identity()["commit"],
        },
    )
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"


def test_record_target_replay_receipt_rejects_missing_materials(harness, monkeypatch):
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, _repo, each_home = harness
    original_receipt = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    materials_root = original_receipt.parent / "materials"
    for path in materials_root.rglob("*"):
        if path.is_file():
            path.unlink()
    replay_path = _write_replay_request(each_home, "m8-replay", _replay_payload(store, original_receipt))
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"


def test_record_target_replay_receipt_rejects_wrong_original_commit(harness, monkeypatch):
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, _repo, each_home = harness
    original_receipt = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    payload = _replay_payload(store, original_receipt)
    payload["original"] = {**payload["original"], "producerCommit": "0" * 40}
    replay_path = _write_replay_request(each_home, "m8-replay", payload)
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"


def test_record_target_replay_receipt_rejects_wrong_candidate_hash_claim(harness, monkeypatch):
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, _repo, each_home = harness
    original_receipt = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    payload = _replay_payload(store, original_receipt)
    payload["original"] = {**payload["original"], "patchHash": "not-the-real-hash"}
    replay_path = _write_replay_request(each_home, "m8-replay", payload)
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"


def test_record_target_replay_receipt_rejects_wrong_execution_sha(harness, monkeypatch):
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, _repo, each_home = harness
    original_receipt = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    payload = _replay_payload(store, original_receipt)
    payload["executionCommit"] = "f" * 40
    replay_path = _write_replay_request(each_home, "m8-replay", payload)
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"


def test_record_target_replay_receipt_rejects_bad_signature_original(harness, monkeypatch):
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, _repo, each_home = harness
    original_receipt = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    tampered = json.loads(original_receipt.read_text(encoding="utf-8"))
    tampered["patchText"] = tampered["patchText"].replace("return 1", "return 9")
    original_receipt.write_text(json.dumps(tampered, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    replay_path = _write_replay_request(each_home, "m8-replay", _replay_payload(store, original_receipt))
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"


def test_record_target_replay_receipt_detects_audit_subject_mutation(harness, monkeypatch):
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, _repo, each_home = harness
    original_receipt = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    _rewrite_signed_receipt(original_receipt, lambda payload: {**payload, "auditSubjectSha256": "0" * 64})
    replay_path = _write_replay_request(each_home, "m8-replay", _replay_payload(store, original_receipt))
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"


def test_m7_experiment_summary_sanitizes_outcome_and_proposal_format(harness):
    store, repo, each_home = harness
    receipt_path = _write_original_receipt(each_home, "m7-experiment", spec_hash=_M7_SPEC_HASH)
    _rewrite_signed_receipt(
        receipt_path,
        lambda payload: {
            **payload,
            "outcome": "REPAIR_NOT_VERIFIED: /private/secret detail",
            "legalCertification": False,
            "cleanroomCertification": False,
            "audit": {
                "checks": {
                    "exact-substring": {"status": "PASS"},
                    "ngram-similarity": {"status": "PASS"},
                    "ast-similarity": {"status": "PASS"},
                    "license-scan": {"status": "PASS"},
                    "corpus-membership": {"status": "UNAVAILABLE"},
                }
            },
            "attempts": [{"attempt": 1, "proposal_format": "/private/weird-format", "outcome": payload["outcome"]}],
        },
    )
    state = store._record_m7_experiment_receipt(
        "test-run", artifact_id="m7-experiment", receipt_path=str(receipt_path), evidence_refs=[]
    )
    artifact = next(item for item in state["artifacts"] if item["id"] == "m7-experiment")
    summary = json.loads((repo / artifact["path"]).read_text(encoding="utf-8"))
    assert summary["outcome"] == "REPAIR_NOT_VERIFIED"
    assert summary["attemptProposalFormats"] == ["UNKNOWN_PROPOSAL_FORMAT_CLASS"]
    assert "/private/" not in json.dumps(summary, sort_keys=True)


def test_target_replay_summary_and_rejection_paths_do_not_leak_private_details(harness, monkeypatch):
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, repo, each_home = harness
    original_receipt = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    replay_path = _write_replay_request(each_home, "m8-replay", _replay_payload(store, original_receipt))

    state = store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    artifact = next(item for item in state["artifacts"] if item["id"] == "m8-replay")
    summary = json.loads((repo / artifact["path"]).read_text(encoding="utf-8"))
    encoded = json.dumps(summary, sort_keys=True)
    assert "originalReceiptPath" not in summary
    assert "toolVersions" not in summary
    assert "/private/" not in encoded

    _rewrite_signed_receipt(
        original_receipt,
        lambda payload: {**payload, "outcome": "REPAIR_NOT_VERIFIED: /private/raw-detail"},
    )
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt("test-run", artifact_id="m8-reject", receipt_path=str(replay_path), evidence_refs=[])
    assert "/private/raw-detail" not in str(excinfo.value)


def test_record_target_replay_receipt_rejects_dirty_checkout(harness, monkeypatch):
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, repo, each_home = harness
    original_receipt = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    replay_path = _write_replay_request(each_home, "m8-replay", _replay_payload(store, original_receipt))
    # A real, tracked-file modification (not the Run's own private
    # .architrave/ bookkeeping) makes the checkout genuinely dirty.
    (repo / "README.md").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"
    assert "dirty" in str(excinfo.value)


def test_record_target_replay_receipt_rejects_execution_commit_mismatching_run_baseline(harness, monkeypatch):
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, repo, each_home = harness
    original_receipt = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    replay_path = _write_replay_request(each_home, "m8-replay", _replay_payload(store, original_receipt))
    _git(repo, "commit", "--allow-empty", "-q", "-m", "second")
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"
    assert "baseline" in str(excinfo.value)


def test_record_target_replay_receipt_rejects_malformed_spec_commands(harness, monkeypatch):
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, _repo, each_home = harness
    original_receipt = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    _rewrite_signed_receipt(
        original_receipt,
        lambda payload: {**payload, "spec": {**payload["spec"], "acceptance_commands": [["python", ""]]}},
    )
    replay_path = _write_replay_request(each_home, "m8-replay", _replay_payload(store, original_receipt))
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"
    assert "malformed" in str(excinfo.value)


def test_record_target_replay_receipt_rejects_non_dict_model_manifest(harness, monkeypatch):
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, _repo, each_home = harness
    original_receipt = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    _rewrite_signed_receipt(
        original_receipt,
        lambda payload: {
            **payload,
            "modelIdentity": {**payload["modelIdentity"], "modelManifest": "not-a-dict"},
        },
    )
    replay_path = _write_replay_request(each_home, "m8-replay", _replay_payload(store, original_receipt))
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"
    assert "not-a-dict" not in str(excinfo.value)


def test_record_target_replay_receipt_accepts_classified_negative_original(harness, monkeypatch):
    """A genuinely classified REPAIR_NOT_VERIFIED original is replayable:
    the candidate replays decisively and still fails, exactly matching the
    historical negative -- never contradicting it with an unexpected pass."""
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, repo, each_home = harness
    original_receipt = _write_original_receipt(
        each_home,
        "m8-negative-run",
        spec_hash=_M8_SPEC_HASH,
        outcome="REPAIR_NOT_VERIFIED",
        patch_text=_NEGATIVE_PATCH,
        repaired_source=_NEGATIVE_REPAIRED_SOURCE,
    )
    replay_path = _write_replay_request(each_home, "m8-negative-replay", _replay_payload(store, original_receipt))
    state = store._record_target_replay_receipt(
        "test-run", artifact_id="m8-negative-replay", receipt_path=str(replay_path), evidence_refs=[]
    )
    artifact = next(item for item in state["artifacts"] if item["id"] == "m8-negative-replay")
    summary = json.loads((repo / artifact["path"]).read_text(encoding="utf-8"))
    assert summary["originalOutcome"] == "REPAIR_NOT_VERIFIED"
    assert summary["candidatePassed"] is False
    assert summary["baselineExecution"]["acceptance"][0]["exitCode"] == 1
    assert summary["replayExecution"]["acceptance"][0]["exitCode"] == 1


def test_record_target_replay_receipt_rejects_contradictory_negative_replay(harness, monkeypatch):
    """A classified-negative original whose candidate now genuinely passes
    on replay must never be silently accepted as negative evidence --
    registering it would contradict the historical claim it is replaying."""
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, _repo, each_home = harness
    original_receipt = _write_original_receipt(
        each_home,
        "m8-negative-run",
        spec_hash=_M8_SPEC_HASH,
        outcome="REPAIR_NOT_VERIFIED",
        patch_text=_PATCH,
        repaired_source=_REPAIRED_SOURCE,
    )
    replay_path = _write_replay_request(each_home, "m8-negative-replay", _replay_payload(store, original_receipt))
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt(
            "test-run", artifact_id="m8-negative-replay", receipt_path=str(replay_path), evidence_refs=[]
        )
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"
    assert "contradictory" in str(excinfo.value)


def test_record_target_replay_receipt_rejects_non_decisive_original_outcome(harness, monkeypatch):
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, _repo, each_home = harness
    original_receipt = _write_original_receipt(
        each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH, outcome="BASELINE_INCONCLUSIVE"
    )
    replay_path = _write_replay_request(each_home, "m8-replay", _replay_payload(store, original_receipt))
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    assert excinfo.value.code == "TARGET_REPLAY_RECEIPT"


def test_record_target_replay_receipt_allows_legacy_unknown_producer_and_subject(harness, monkeypatch):
    """A genuinely legacy signed original that never recorded a producer
    commit or audit subject hash (exported source tree, no git metadata at
    write time) is still honestly replayable -- UNKNOWN is labelled, not
    hard-rejected -- as long as the CURRENT execution is a clean, fully
    attributable checkout and the candidate still reconstructs/replays."""
    monkeypatch.setattr("each.executor.container.ContainerExecutor", _FakeReplayExecutor)
    store, _repo, each_home = harness
    original_receipt = _write_original_receipt(each_home, "m8-real-run", spec_hash=_M8_SPEC_HASH)
    _rewrite_signed_receipt(
        original_receipt,
        lambda payload: {**payload, "producerCommit": "UNKNOWN", "producerDirty": "UNKNOWN", "auditSubjectSha256": None},
    )
    payload = _replay_payload(store, original_receipt)
    payload["original"] = {**payload["original"], "producerCommit": "UNKNOWN", "auditSubjectSha256": None}
    replay_path = _write_replay_request(each_home, "m8-replay", payload)
    state = store._record_target_replay_receipt("test-run", artifact_id="m8-replay", receipt_path=str(replay_path), evidence_refs=[])
    artifact = next(item for item in state["artifacts"] if item["id"] == "m8-replay")
    assert artifact["kind"] == "target-replay-receipt"

