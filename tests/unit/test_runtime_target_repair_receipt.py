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

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "harness"))
import architrave_runtime as art


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _patch_official_identity(monkeypatch, receipt_path: Path) -> dict:
    identity = json.loads(receipt_path.read_text())["modelIdentity"]
    official = copy.deepcopy(identity)
    official["generationParameters"]["maxTokens"] = 1
    official["contextPolicy"]["reservedOutputTokens"] = 1
    official["generationAttempted"] = False
    monkeypatch.setattr(
        "each.models.catalog.load_model",
        lambda *_a, **_k: type("M", (), {"identity": lambda self: official})(),
    )
    return identity


def test_recorded_implementation_is_bound_to_clean_producer_commit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    module = repo / "each" / "models" / "mlx_model.py"
    module.parent.mkdir(parents=True)
    module.write_text("fixture implementation\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture implementation")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    run_store = art.RunStore(repository=repo)
    identity = {
        "implementationModule": "each.models.mlx_model",
        "implementationSha256": hashlib.sha256(module.read_bytes()).hexdigest(),
    }
    receipt = {"producerCommit": commit, "producerDirty": False}
    run_store._validate_recorded_model_implementation(
        receipt,
        identity,
        error_code="TARGET_EXPERIMENT_RECEIPT",
    )
    identity["implementationSha256"] = "0" * 64
    with pytest.raises(art.RuntimeFailure, match="does not match"):
        run_store._validate_recorded_model_implementation(
            receipt,
            identity,
            error_code="TARGET_EXPERIMENT_RECEIPT",
        )
    receipt["producerDirty"] = True
    with pytest.raises(art.RuntimeFailure, match="identity is invalid"):
        run_store._validate_recorded_model_implementation(
            receipt,
            identity,
            error_code="TARGET_EXPERIMENT_RECEIPT",
        )


def _write_real_receipt(
    each_home: Path,
    run_id: str,
    *,
    outcome="REPAIR_VERIFIED",
    model_id=None,
    adapter_type="MLXRepairModel",
    network_isolation=True,
    spec_hash="2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
    repaired_result=None,
    repo_id="bigcode/starcoderbase",
    revision="88ec5781ad071a9d9e925cd28f327dea22eb5188",
    raw_completion="def f(): ...",
    selected_attempt=1,
    assurance_level="EACH-P1",
    legal_certification=False,
    cleanroom_certification=False,
    attempt_number=1,
    attempt_model_identity=None,
    type_confused_attempt_identity=False,
    top_level_raw_completion=None,
    retain_materials=True,
    generation_attempted=True,
    materials_override=None,
    audit_value=None,
):
    """Build and sign a genuine receipt via the real each.receipt/each.attestation
    code paths, written under a private EACH_HOME/runs/<run_id>/ directory --
    exactly the shape _record_target_repair_receipt must independently re-verify."""
    import os

    os.environ["EACH_HOME"] = str(each_home)
    from each.receipt import Receipt

    model_identity = {
        "modelId": model_id or f"{repo_id}@{revision}#sha256:cafe",
        "adapterType": adapter_type,
        "adapterClassPath": f"each.models.mlx_model.{adapter_type}",
        "implementationModule": "each.models.mlx_model",
        "implementationSha256": "implementation-test-sha",
        "runtimeModelConfig": {"tie_word_embeddings": False},
        "modelManifest": {
            "schemaVersion": "0.1",
            "repoId": repo_id,
            "revision": revision,
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
        "contextPolicy": {"maxPositionEmbeddings": 8192, "reservedOutputTokens": 256},
        "generationAttempted": generation_attempted,
    }

    selected_model_identity = model_identity if attempt_model_identity is None else attempt_model_identity
    if type_confused_attempt_identity:
        selected_model_identity = copy.deepcopy(model_identity)
        selected_model_identity["generationAttempted"] = 1
        selected_model_identity["generationParameters"]["maxTokens"] = 256.0
        selected_model_identity["runtimeModelConfig"]["tie_word_embeddings"] = 0

    receipt = Receipt(
        run_id=run_id,
        spec={"taskId": "each-m8-xsystem-sandboxid-opt"},
        spec_hash=spec_hash,
        model_identity=model_identity,
        prompt="repair this function",
        raw_completion=raw_completion if top_level_raw_completion is None else top_level_raw_completion,
        patch_text="--- a\n+++ b\n",
        touched_paths=["xsystem.c"],
        materials={},
        executor_identity={"engine": "colima-each"},
        isolation_evidence={"command": ["docker", "run", "--network", "none"], "exit_code": 1, "stdout": ""},
        baseline_result={"exit_code": 1},
        repaired_result={"exit_code": 0} if repaired_result is None else repaired_result,
        audit={"result": "UNAVAILABLE", "checks": {}} if audit_value is None else audit_value,
        assurance_level=assurance_level,
        legal_certification=legal_certification,
        cleanroom_certification=cleanroom_certification,
        outcome=outcome,
        network_isolation_verified=network_isolation,
        attempts=[
            {
                "attempt": attempt_number,
                "proposal_format": "full_source",
                "outcome": outcome,
                "raw_completion": raw_completion,
                "model_identity": selected_model_identity,
            }
        ],
        selected_attempt=selected_attempt,
        audit_subject_sha256="subject-sha",
    )
    run_dir = each_home / "runs" / run_id
    materials_source = each_home / "receipt-inputs" / run_id
    if retain_materials:
        materials_source.mkdir(parents=True)
        material = materials_source / "input.txt"
        material.write_text("retained input\n", encoding="utf-8")
        receipt.materials = {"input.txt": hashlib.sha256(material.read_bytes()).hexdigest()}
    if materials_override is not None:
        receipt.materials = materials_override
    json_path, _ = receipt.write(
        run_dir,
        materials_source=materials_source if retain_materials else None,
    )
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
    monkeypatch.setattr(run_store, "_validate_recorded_model_implementation", lambda *_a, **_k: None)
    run_store.create(
        goal="test goal",
        outcome="test outcome",
        criteria=[
            {
                "id": "m8-repair",
                "description": "m8 repair",
                "verificationType": "reality",
                "surface": "runtime",
                "blocking": True,
                "targetEvidence": {
                    "kind": "target-repair-receipt",
                    "purpose": "target-repair-verified",
                    "targetSpecHash": "2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
                },
            },
        ],
        autonomy_scope="approved-program",
        run_id="test-run",
    )
    return run_store, repo, each_home


@pytest.fixture()
def experiment_harness(tmp_path, monkeypatch):
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
    monkeypatch.setattr(run_store, "_validate_recorded_model_implementation", lambda *_a, **_k: None)
    run_store.create(
        goal="test goal",
        outcome="test outcome",
        criteria=[
            {
                "id": "qualified-local-evaluation",
                "description": "real local model completed a target evaluation",
                "verificationType": "reality",
                "surface": "runtime",
                "blocking": True,
                "targetEvidence": {
                    "kind": "target-experiment-receipt",
                    "purpose": "target-experiment-complete",
                    "targetSpecHash": "2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
                },
            },
            {
                "id": "unrelated-runtime",
                "description": "unrelated runtime truth",
                "verificationType": "reality",
                "surface": "runtime",
                "blocking": False,
            },
            {
                "id": "verified-repair",
                "description": "a genuinely verified repair",
                "verificationType": "reality",
                "surface": "runtime",
                "blocking": False,
                "targetEvidence": {
                    "kind": "target-repair-receipt",
                    "purpose": "target-repair-verified",
                    "targetSpecHash": "2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
                },
            },
        ],
        autonomy_scope="approved-program",
        run_id="test-experiment-run",
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


def test_negative_real_target_experiment_can_satisfy_local_evaluation_criterion(experiment_harness, monkeypatch):
    run_store, repo, each_home = experiment_harness
    receipt_path = _write_real_receipt(
        each_home,
        "negative-target-run",
        outcome="PATCH_REJECTED: no change",
        repaired_result={},
    )
    _patch_official_identity(monkeypatch, receipt_path)
    state = run_store._record_target_experiment_receipt(
        "test-experiment-run",
        artifact_id="negative-target-evidence",
        receipt_path=str(receipt_path),
        evidence_refs=[],
    )
    artifact = next(item for item in state["artifacts"] if item["id"] == "negative-target-evidence")
    assert artifact["kind"] == "target-experiment-receipt"
    assert artifact["producer"] == "target-experiment"
    summary = json.loads((repo / artifact["path"]).read_text())
    assert summary["outcome"] == "PATCH_REJECTED"
    assert summary["candidateValidationRecorded"] is False
    assert summary["terminalAuditRecorded"] is False
    run_store.record_gate(
        "test-experiment-run",
        gate_id="gate-negative-target",
        task_id=None,
        gate_type="reality",
        status="PASS",
        evidence_refs=["artifact:negative-target-evidence"],
        criteria=["qualified-local-evaluation"],
    )
    result = run_store.set_criterion(
        "test-experiment-run",
        "qualified-local-evaluation",
        "PASS",
        ["gate:gate-negative-target"],
    )
    criterion = next(
        item for item in result["acceptanceCriteria"] if item["id"] == "qualified-local-evaluation"
    )
    assert criterion["status"] == "PASS"


def test_target_experiment_rejects_fixture_identity_and_unknown_outcome(experiment_harness, monkeypatch):
    run_store, _repo, each_home = experiment_harness
    fixture_receipt = _write_real_receipt(
        each_home,
        "fixture-target-run",
        outcome="PATCH_REJECTED",
        model_id="fixture/not-a-qualified-model",
        adapter_type="FixtureModel",
        repaired_result={},
    )
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_experiment_receipt(
            "test-experiment-run",
            artifact_id="fixture-target-evidence",
            receipt_path=str(fixture_receipt),
            evidence_refs=[],
        )
    unknown_receipt = _write_real_receipt(
        each_home,
        "unknown-target-run",
        outcome="PRIVATE_UNKNOWN_RESULT",
        repaired_result={},
    )
    _patch_official_identity(monkeypatch, unknown_receipt)
    with pytest.raises(art.RuntimeFailure, match="qualified target generation"):
        run_store._record_target_experiment_receipt(
            "test-experiment-run",
            artifact_id="unknown-target-evidence",
            receipt_path=str(unknown_receipt),
            evidence_refs=[],
        )


def test_target_experiment_rejects_unqualified_model_and_unowned_criterion(experiment_harness, monkeypatch):
    run_store, _repo, each_home = experiment_harness
    receipt_path = _write_real_receipt(
        each_home,
        "unqualified-target-run",
        outcome="PATCH_REJECTED",
        repo_id="ibm-granite/granite-8b-code-instruct-128k",
        revision="deadbeefcafebabe",
        repaired_result={},
    )
    with pytest.raises(art.RuntimeFailure, match="exact qualified checkpoint"):
        run_store._record_target_experiment_receipt(
            "test-experiment-run",
            artifact_id="unqualified-target-evidence",
            receipt_path=str(receipt_path),
            evidence_refs=[],
        )

    qualified_receipt = _write_real_receipt(
        each_home,
        "owned-target-run",
        outcome="PATCH_REJECTED",
        repaired_result={},
    )
    _patch_official_identity(monkeypatch, qualified_receipt)
    run_store._record_target_experiment_receipt(
        "test-experiment-run",
        artifact_id="owned-target-evidence",
        receipt_path=str(qualified_receipt),
        evidence_refs=[],
    )
    with pytest.raises(art.RuntimeFailure, match="targetEvidence"):
        run_store.record_gate(
            "test-experiment-run",
            gate_id="laundered-gate",
            task_id=None,
            gate_type="reality",
            status="PASS",
            evidence_refs=["artifact:owned-target-evidence"],
            criteria=["unrelated-runtime"],
        )
    with pytest.raises(art.RuntimeFailure, match="kind"):
        run_store.record_gate(
            "test-experiment-run",
            gate_id="repair-laundered-gate",
            task_id=None,
            gate_type="reality",
            status="PASS",
            evidence_refs=["artifact:owned-target-evidence"],
            criteria=["verified-repair"],
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"network_isolation": False}, "network isolation"),
        ({"assurance_level": "UNBOUNDED"}, "assuranceLevel"),
        ({"assurance_level": "EACH-P3"}, "exceeds this neural"),
        ({"assurance_level": "EACH-P4"}, "exceeds this neural"),
        ({"spec_hash": "not-a-hash"}, "specHash"),
        ({"raw_completion": "", "selected_attempt": None}, "bind one selected"),
        ({"legal_certification": True}, "legal certification"),
        ({"retain_materials": False}, "no retained materials"),
    ],
)
def test_target_experiment_rejects_invalid_runtime_evidence(experiment_harness, monkeypatch, kwargs, message):
    run_store, _repo, each_home = experiment_harness
    receipt_path = _write_real_receipt(
        each_home,
        "invalid-target-" + str(abs(hash(message))),
        outcome="PATCH_REJECTED",
        repaired_result={},
        **kwargs,
    )
    _patch_official_identity(monkeypatch, receipt_path)
    with pytest.raises(art.RuntimeFailure, match=message):
        run_store._record_target_experiment_receipt(
            "test-experiment-run",
            artifact_id="invalid-target-evidence-" + str(abs(hash(message))),
            receipt_path=str(receipt_path),
            evidence_refs=[],
        )


def test_target_experiment_verifies_the_captured_receipt_payload(experiment_harness, monkeypatch):
    run_store, _repo, each_home = experiment_harness
    receipt_path = _write_real_receipt(
        each_home,
        "raced-target-run",
        outcome="PATCH_REJECTED",
        repaired_result={},
    )
    _patch_official_identity(monkeypatch, receipt_path)
    original_bytes = receipt_path.read_bytes()
    original_sha256 = hashlib.sha256(original_bytes).hexdigest()
    from each.attestation import verify_receipt as original_verify

    def replace_path_during_verify(receipt, public_key):
        result = original_verify(receipt, public_key)
        receipt_path.write_bytes(receipt_path.read_bytes() + b"\n")
        return result

    monkeypatch.setattr("each.attestation.verify_receipt", replace_path_during_verify)
    state = run_store._record_target_experiment_receipt(
        "test-experiment-run",
        artifact_id="captured-target-evidence",
        receipt_path=str(receipt_path),
        evidence_refs=[],
    )
    artifact = next(item for item in state["artifacts"] if item["id"] == "captured-target-evidence")
    summary = json.loads((_repo / artifact["path"]).read_text())
    assert summary["receiptSha256"] == original_sha256
    assert hashlib.sha256(receipt_path.read_bytes()).hexdigest() != original_sha256


@pytest.mark.parametrize(
    "kwargs",
    [
        {"attempt_number": 2, "selected_attempt": 1},
        {"attempt_number": True, "selected_attempt": 1},
        {"attempt_number": 1.0, "selected_attempt": 1},
        {"selected_attempt": True},
        {"generation_attempted": False},
        {"raw_completion": "   "},
        {"raw_completion": "", "top_level_raw_completion": "top-level fallback is forbidden"},
        {
            "attempt_model_identity": {
                "modelId": "fixture/unqualified",
                "adapterClassPath": "each.models.fixture.FixtureModel",
                "modelManifest": {},
            }
        },
        {"type_confused_attempt_identity": True},
    ],
)
def test_target_experiment_binds_selected_attempt_to_qualified_identity(
    experiment_harness, monkeypatch, kwargs,
):
    run_store, _repo, each_home = experiment_harness
    receipt_path = _write_real_receipt(
        each_home,
        "attempt-binding-" + str(abs(hash(json.dumps(kwargs, sort_keys=True)))),
        outcome="PATCH_REJECTED",
        repaired_result={},
        **kwargs,
    )
    _patch_official_identity(monkeypatch, receipt_path)
    with pytest.raises(art.RuntimeFailure, match="bind one selected"):
        run_store._record_target_experiment_receipt(
            "test-experiment-run",
            artifact_id="attempt-binding-evidence-" + str(abs(hash(json.dumps(kwargs, sort_keys=True)))),
            receipt_path=str(receipt_path),
            evidence_refs=[],
        )


@pytest.mark.parametrize("mismatch", ["runtime-config-type", "manifest"])
def test_target_experiment_rejects_mismatched_official_identity(experiment_harness, monkeypatch, mismatch):
    run_store, _repo, each_home = experiment_harness
    receipt_path = _write_real_receipt(
        each_home,
        "official-identity-mismatch-" + mismatch,
        outcome="PATCH_REJECTED",
        repaired_result={},
    )
    identity = json.loads(receipt_path.read_text())["modelIdentity"]
    official = copy.deepcopy(identity)
    official["generationParameters"]["maxTokens"] = 1
    official["contextPolicy"]["reservedOutputTokens"] = 1
    official["generationAttempted"] = False
    if mismatch == "runtime-config-type":
        official["runtimeModelConfig"]["tie_word_embeddings"] = 0
    else:
        official["modelManifest"]["configSha256"] = "different-config"
    monkeypatch.setattr(
        "each.models.catalog.load_model",
        lambda *_a, **_k: type("M", (), {"identity": lambda self: official})(),
    )
    with pytest.raises(art.RuntimeFailure, match="official qualified local artifact"):
        run_store._record_target_experiment_receipt(
            "test-experiment-run",
            artifact_id="official-identity-mismatch-" + mismatch,
            receipt_path=str(receipt_path),
            evidence_refs=[],
        )


def test_target_experiment_normalizes_receipt_read_and_catalog_failures(experiment_harness, monkeypatch):
    run_store, _repo, each_home = experiment_harness
    missing = each_home / "runs" / "missing" / "receipt.json"
    original_resolver = run_store._resolve_private_each_run_file
    monkeypatch.setattr(run_store, "_resolve_private_each_run_file", lambda *_a, **_k: missing)
    with pytest.raises(art.RuntimeFailure, match="could not be read"):
        run_store._record_target_experiment_receipt(
            "test-experiment-run",
            artifact_id="missing-receipt-evidence",
            receipt_path=str(missing),
            evidence_refs=[],
        )

    monkeypatch.setattr(run_store, "_resolve_private_each_run_file", original_resolver)
    receipt_path = _write_real_receipt(
        each_home,
        "catalog-runtime-failure",
        outcome="PATCH_REJECTED",
        repaired_result={},
    )
    monkeypatch.setattr(
        "each.models.catalog.load_model",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("optional runtime failure")),
    )
    with pytest.raises(art.RuntimeFailure, match="unavailable or changed"):
        run_store._record_target_experiment_receipt(
            "test-experiment-run",
            artifact_id="catalog-runtime-failure-evidence",
            receipt_path=str(receipt_path),
            evidence_refs=[],
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("materials", "invalid", "no retained materials"),
        ("audit", "invalid", "audit must be an object"),
    ],
)
def test_target_experiment_rejects_signed_malformed_mapping_shapes(
    experiment_harness, field, value, message,
):
    from each.attestation import attest_receipt

    run_store, _repo, each_home = experiment_harness
    receipt_path = _write_real_receipt(
        each_home,
        "malformed-shape-" + field,
        outcome="PATCH_REJECTED",
        repaired_result={},
    )
    receipt = json.loads(receipt_path.read_text())
    receipt[field] = value
    receipt.pop("attestation", None)
    receipt["attestation"] = attest_receipt(receipt)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(art.RuntimeFailure, match=message):
        run_store._record_target_experiment_receipt(
            "test-experiment-run",
            artifact_id="malformed-shape-evidence-" + field,
            receipt_path=str(receipt_path),
        evidence_refs=[],
    )


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


def test_negative_repair_rejection_does_not_export_private_outcome_details(harness):
    run_store, _repo, each_home = harness
    sentinel = "PRIVATE_TARGET_SOURCE_SENTINEL"
    receipt_path = _write_real_receipt(
        each_home, "m8-private-negative-outcome", outcome=f"REPAIR_NOT_VERIFIED: {sentinel}"
    )
    with pytest.raises(art.RuntimeFailure) as caught:
        run_store._record_target_repair_receipt(
            "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
        )
    error = caught.value
    cli_payload = {
        "status": "failed",
        "error": {"code": error.code, "message": error.message, "details": art.redact(error.details)},
    }
    assert error.code == "TARGET_REPAIR_RECEIPT"
    assert sentinel not in json.dumps(cli_payload)


def test_rejects_a_real_receipt_without_network_isolation_verified(harness):
    run_store, _repo, each_home = harness
    receipt_path = _write_real_receipt(each_home, "m8-no-isolation-run", network_isolation=False)
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_repair_receipt(
            "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
        )


def test_does_not_reject_a_real_adapter_solely_because_model_id_mentions_fixture(harness):
    """Caller-controlled model_id text is not identity; adapter class path and manifest are."""
    run_store, _repo, each_home = harness
    receipt_path = _write_real_receipt(each_home, "m8-fixture-run", model_id="FixtureModel/self-test")
    state = run_store._record_target_repair_receipt(
        "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
    )
    assert any(item["id"] == "m8-evidence" for item in state["artifacts"])


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


def test_rejects_a_fixturemodel_subclass_with_a_misleading_non_fixture_name_and_manifest(harness):
    run_store, _repo, each_home = harness
    receipt_path = _write_real_receipt(
        each_home,
        "m8-fixture-subclass-run",
        model_id="totally-real-local-model",
        adapter_type="DefinitelyRealLocalModel",
    )
    with pytest.raises(art.RuntimeFailure):
        run_store._record_target_repair_receipt(
            "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
        )


def _write_legacy_real_receipt(each_home: Path, run_id: str, *, implementation_module: str) -> Path:
    """Build a receipt whose modelIdentity uses the PRE-this-session field
    shape: only implementationModule/implementationSha256/modelId/modelManifest/
    generationParameters -- no adapterClassPath/adapterType at all. This is
    exactly the shape every M7/M8 receipt genuinely signed before this
    session's RepairModel.identity() hardening actually has on disk; the
    validator must accept it ONLY when implementation_module uniquely
    resolves to an allowlisted real adapter class, never via the caller's
    modelId/adapterType strings (which this legacy shape doesn't even carry)."""
    import os

    os.environ["EACH_HOME"] = str(each_home)
    from each.receipt import Receipt

    model_identity = {
        "modelId": "ibm-granite/granite-8b-code-instruct-128k@deadbeef#sha256:cafe",
        "implementationModule": implementation_module,
        "implementationSha256": "a" * 64,
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
    receipt = Receipt(
        run_id=run_id,
        spec={"taskId": "each-m8-xsystem-sandboxid-opt"},
        spec_hash="2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78",
        model_identity=model_identity,
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
        attempts=[{"attempt": 1, "proposal_format": "full_source", "outcome": "REPAIR_VERIFIED"}],
        selected_attempt=1,
        audit_subject_sha256="subject-sha",
    )
    run_dir = each_home / "runs" / run_id
    json_path, _ = receipt.write(run_dir)
    return json_path


def test_accepts_a_legacy_real_receipt_declaring_only_implementation_module(harness):
    """Genuine M7/M8 receipts signed before this session's adapterClassPath
    field existed must still be accepted -- they bind to the real allowlisted
    adapter module just as strongly, only via an older field name."""
    run_store, _repo, each_home = harness
    receipt_path = _write_legacy_real_receipt(each_home, "m8-legacy-run", implementation_module="each.models.mlx_model")
    state = run_store._record_target_repair_receipt(
        "test-run", artifact_id="m8-evidence", receipt_path=str(receipt_path), evidence_refs=[]
    )
    assert any(item["id"] == "m8-evidence" for item in state["artifacts"])


def test_rejects_a_legacy_fixture_receipt_declaring_the_fixture_implementation_module(harness):
    """The legacy-shape compatibility path must never accept the fixture
    adapter's own real module path -- it only recognizes the one genuine,
    non-fixture allowlisted adapter module."""
    run_store, _repo, each_home = harness
    receipt_path = _write_legacy_real_receipt(each_home, "m8-legacy-fixture-run", implementation_module="each.models.fixture")
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
