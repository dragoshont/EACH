from __future__ import annotations

import json
from pathlib import Path

import pytest

import each.clean_room as clean_room_module
from each.hashing import sha256_bytes, sha256_text
from each.receipt import Receipt

_SPEC_HASH = "seed-spec-hash"


@pytest.fixture(autouse=True)
def _isolated_each_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))


def _real_model_identity(*, model_id: str = "ibm-granite/granite-8b-code-instruct-128k@seed") -> dict[str, object]:
    return {
        "modelId": model_id,
        "adapterType": "MLXRepairModel",
        "adapterClassPath": "each.models.mlx_model.MLXRepairModel",
        "modelManifest": {
            "schemaVersion": "0.1",
            "repoId": "ibm-granite/granite-8b-code-instruct-128k",
            "revision": "seed-revision",
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


def _patch_from(before: str, after: str) -> str:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    return (
        "--- a/candidate.py\n"
        "+++ b/candidate.py\n"
        f"@@ -1,{len(before_lines)} +1,{len(after_lines)} @@\n"
        + "\n".join(f"-{line}" for line in before_lines)
        + "\n"
        + "\n".join(f"+{line}" for line in after_lines)
        + "\n"
    )


def _write_seed_receipt(
    tmp_path: Path,
    *,
    run_id: str,
    before: str,
    after: str,
    spec_hash: str = _SPEC_HASH,
    model_identity: dict[str, object] | None = None,
    outcome: str = "REPAIR_VERIFIED",
    parent_receipt_path: Path | None = None,
    parent_seed_source: str | None = None,
) -> Path:
    source_root = tmp_path / f"{run_id}-source"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "candidate.py").write_text(before, encoding="utf-8")
    receipt = Receipt(
        run_id=run_id,
        spec={"taskId": "seed-task"},
        spec_hash=spec_hash,
        model_identity=model_identity or _real_model_identity(),
        prompt="seed prompt",
        raw_completion="seed completion",
        patch_text=_patch_from(before, after),
        touched_paths=["candidate.py"],
        materials={"candidate.py": sha256_bytes(before.encode("utf-8"))},
        executor_identity={},
        isolation_evidence={"command": ["docker", "run", "--network", "none"], "exit_code": 1, "stdout": ""},
        baseline_result={"exit_code": 1},
        repaired_result={"exit_code": 0},
        audit={"result": "UNAVAILABLE", "checks": {}},
        assurance_level="EACH-P2",
        outcome=outcome,
        attempts=[
            {
                "attempt": 1,
                "proposal_format": "diff",
                "correction_candidate_hash": sha256_text(after),
                "outcome": outcome,
            }
        ],
        selected_attempt=1,
        audit_subject_sha256=sha256_bytes(after.encode("utf-8")),
        seed_provenance=(
            {
                "type": "seed-source-provenance",
                "seedSha256": sha256_text(parent_seed_source or ""),
                "sourceReceiptPath": str(parent_receipt_path),
                "sourceRunId": parent_receipt_path.parent.name if parent_receipt_path is not None else None,
            }
            if parent_receipt_path is not None
            else None
        ),
    )
    run_dir = tmp_path / run_id
    json_path, _ = receipt.write(run_dir, materials_source=source_root)
    return json_path


def test_verify_seed_source_provenance_accepts_a_verified_matching_receipt(tmp_path: Path) -> None:
    seed_source = "def f():\n    return 1\n"
    receipt_path = _write_seed_receipt(tmp_path, run_id="seed-run", before="def f():\n    return 0\n", after=seed_source)

    provenance = clean_room_module._verify_seed_source_provenance(
        seed_source=seed_source,
        seed_receipt_path=receipt_path,
        expected_spec_hash=_SPEC_HASH,
        current_model_identity=_real_model_identity(),
    )

    assert provenance["seedSha256"] == sha256_text(seed_source)
    assert provenance["sourceRunId"] == "seed-run"
    assert provenance["sourceAttempt"] == 1
    assert provenance["sourceReceiptPath"] == str(receipt_path.resolve())


def test_verify_seed_source_provenance_rejects_a_tampered_seed_source(tmp_path: Path) -> None:
    receipt_path = _write_seed_receipt(
        tmp_path,
        run_id="seed-run",
        before="def f():\n    return 0\n",
        after="def f():\n    return 1\n",
    )

    with pytest.raises(ValueError, match="do not match the reconstructed selected candidate"):
        clean_room_module._verify_seed_source_provenance(
            seed_source="def f():\n    return 2\n",
            seed_receipt_path=receipt_path,
            expected_spec_hash=_SPEC_HASH,
            current_model_identity=_real_model_identity(),
        )


def test_verify_seed_source_provenance_rejects_a_missing_receipt(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        clean_room_module._verify_seed_source_provenance(
            seed_source="def f():\n    return 1\n",
            seed_receipt_path=tmp_path / "missing.json",
            expected_spec_hash=_SPEC_HASH,
            current_model_identity=_real_model_identity(),
        )


def test_verify_seed_source_provenance_accepts_legitimate_two_hop_and_three_hop_chains(tmp_path: Path) -> None:
    source1 = "def f():\n    return 1\n"
    source2 = "def f():\n    return 2\n"
    source3 = "def f():\n    return 3\n"
    receipt1 = _write_seed_receipt(tmp_path, run_id="seed-1", before="def f():\n    return 0\n", after=source1)
    receipt2 = _write_seed_receipt(
        tmp_path,
        run_id="seed-2",
        before=source1,
        after=source2,
        parent_receipt_path=receipt1,
        parent_seed_source=source1,
    )
    receipt3 = _write_seed_receipt(
        tmp_path,
        run_id="seed-3",
        before=source2,
        after=source3,
        parent_receipt_path=receipt2,
        parent_seed_source=source2,
    )

    provenance2 = clean_room_module._verify_seed_source_provenance(
        seed_source=source2,
        seed_receipt_path=receipt2,
        expected_spec_hash=_SPEC_HASH,
        current_model_identity=_real_model_identity(),
    )
    assert provenance2["ancestry"][0]["sourceRunId"] == "seed-1"

    provenance3 = clean_room_module._verify_seed_source_provenance(
        seed_source=source3,
        seed_receipt_path=receipt3,
        expected_spec_hash=_SPEC_HASH,
        current_model_identity=_real_model_identity(),
    )
    assert provenance3["ancestry"][0]["sourceRunId"] == "seed-2"
    assert provenance3["ancestry"][0]["ancestry"][0]["sourceRunId"] == "seed-1"


def test_verify_seed_source_provenance_rejects_cycles(tmp_path: Path) -> None:
    source1 = "def f():\n    return 1\n"
    source2 = "def f():\n    return 2\n"
    receipt1 = _write_seed_receipt(tmp_path, run_id="seed-1", before="def f():\n    return 0\n", after=source1)
    receipt2 = _write_seed_receipt(
        tmp_path,
        run_id="seed-2",
        before=source1,
        after=source2,
        parent_receipt_path=receipt1,
        parent_seed_source=source1,
    )

    data1 = json.loads(receipt1.read_text(encoding="utf-8"))
    data1["seedProvenance"] = {
        "type": "seed-source-provenance",
        "seedSha256": sha256_text(source2),
        "sourceReceiptPath": str(receipt2),
        "sourceRunId": "seed-2",
    }
    data1["attestation"] = receipt_module_attestation(data1)
    receipt1.write_text(json.dumps(data1, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="cycle"):
        clean_room_module._verify_seed_source_provenance(
            seed_source=source2,
            seed_receipt_path=receipt2,
            expected_spec_hash=_SPEC_HASH,
            current_model_identity=_real_model_identity(),
        )


def receipt_module_attestation(payload: dict[str, object]) -> dict[str, object]:
    from each.attestation import attest_receipt

    return attest_receipt({key: value for key, value in payload.items() if key != "attestation"})


def test_verify_seed_source_provenance_rejects_audit_rejected_or_terminal_receipts(tmp_path: Path) -> None:
    receipt_path = _write_seed_receipt(
        tmp_path,
        run_id="seed-run",
        before="def f():\n    return 0\n",
        after="def f():\n    return 1\n",
        outcome="REPAIR_REJECTED_AUDIT",
    )
    with pytest.raises(ValueError, match="eligible verified repair"):
        clean_room_module._verify_seed_source_provenance(
            seed_source="def f():\n    return 1\n",
            seed_receipt_path=receipt_path,
            expected_spec_hash=_SPEC_HASH,
            current_model_identity=_real_model_identity(),
        )


def test_verify_seed_source_provenance_rejects_current_spec_or_model_mismatch(tmp_path: Path) -> None:
    seed_source = "def f():\n    return 1\n"
    receipt_path = _write_seed_receipt(tmp_path, run_id="seed-run", before="def f():\n    return 0\n", after=seed_source)

    with pytest.raises(ValueError, match="spec hash"):
        clean_room_module._verify_seed_source_provenance(
            seed_source=seed_source,
            seed_receipt_path=receipt_path,
            expected_spec_hash="different-spec-hash",
            current_model_identity=_real_model_identity(),
        )

    with pytest.raises(ValueError, match="model identity"):
        clean_room_module._verify_seed_source_provenance(
            seed_source=seed_source,
            seed_receipt_path=receipt_path,
            expected_spec_hash=_SPEC_HASH,
            current_model_identity=_real_model_identity(model_id="other-model@revision"),
        )


def test_verify_seed_source_provenance_rejects_fixture_or_unknown_authoring(tmp_path: Path) -> None:
    seed_source = "def f():\n    return 1\n"
    fixture_identity = {
        "modelId": "fixture/deterministic-v1",
        "adapterType": "FixtureModel",
        "adapterClassPath": "each.models.fixture.FixtureModel",
        "modelManifest": {"revision": "fixture", "weightsSha256": {"none": "none"}, "runtime": {"name": "fixture", "version": "1"}, "filesSha256": {"config.json": "x"}},
        "generationParameters": {"maxTokens": 1, "temperature": 0.0, "sampling": "greedy"},
    }
    receipt_path = _write_seed_receipt(
        tmp_path,
        run_id="fixture-seed",
        before="def f():\n    return 0\n",
        after=seed_source,
        model_identity=fixture_identity,
    )
    with pytest.raises(ValueError, match="allowlisted real-model adapter"):
        clean_room_module._verify_seed_source_provenance(
            seed_source=seed_source,
            seed_receipt_path=receipt_path,
            expected_spec_hash=_SPEC_HASH,
            current_model_identity=_real_model_identity(),
        )
