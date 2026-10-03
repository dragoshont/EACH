from __future__ import annotations

import json
from pathlib import Path

import pytest

import each.clean_room as clean_room_module
from each.hashing import sha256_text
from each.receipt import Receipt


@pytest.fixture(autouse=True)
def _isolated_each_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))


def _write_seed_receipt(tmp_path: Path, *, source: str) -> Path:
    receipt = Receipt(
        run_id="seed-run",
        spec={"taskId": "seed-task"},
        spec_hash="seed-spec-hash",
        model_identity={
            "modelId": "ibm-granite/granite-8b-code-instruct-128k@seed",
            "adapterType": "MLXRepairModel",
            "modelManifest": {"modelId": "ibm-granite/granite-8b-code-instruct-128k@seed"},
        },
        prompt="seed prompt",
        raw_completion="seed completion",
        patch_text="--- a/seed\n+++ b/seed\n",
        touched_paths=["candidate.py"],
        materials={},
        executor_identity={},
        isolation_evidence={},
        baseline_result={"exit_code": 1},
        repaired_result={"exit_code": 0},
        audit={"result": "UNAVAILABLE", "checks": {}},
        assurance_level="EACH-P2",
        outcome="REPAIR_VERIFIED",
        attempts=[
            {
                "attempt": 1,
                "proposal_format": "diff",
                "correction_candidate_hash": sha256_text(source),
                "outcome": "REPAIR_VERIFIED",
            }
        ],
        selected_attempt=1,
    )
    receipt_path, _ = receipt.write(tmp_path / "seed-run")
    return receipt_path


def test_verify_seed_source_provenance_accepts_a_verified_matching_receipt(tmp_path: Path) -> None:
    seed_source = "def f():\n    return 1\n"
    receipt_path = _write_seed_receipt(tmp_path, source=seed_source)

    provenance = clean_room_module._verify_seed_source_provenance(
        seed_source=seed_source,
        seed_receipt_path=receipt_path,
    )

    assert provenance["seedSha256"] == sha256_text(seed_source)
    assert provenance["sourceRunId"] == "seed-run"
    assert provenance["sourceAttempt"] == 1


def test_verify_seed_source_provenance_rejects_a_tampered_seed_source(tmp_path: Path) -> None:
    receipt_path = _write_seed_receipt(tmp_path, source="def f():\n    return 1\n")

    with pytest.raises(ValueError, match="does not match any candidate"):
        clean_room_module._verify_seed_source_provenance(
            seed_source="def f():\n    return 2\n",
            seed_receipt_path=receipt_path,
        )


def test_verify_seed_source_provenance_rejects_a_missing_receipt(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        clean_room_module._verify_seed_source_provenance(
            seed_source="def f():\n    return 1\n",
            seed_receipt_path=tmp_path / "missing.json",
        )


def test_verify_seed_source_provenance_rejects_an_invalid_signed_receipt(tmp_path: Path) -> None:
    receipt_path = _write_seed_receipt(tmp_path, source="def f():\n    return 1\n")
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    data["outcome"] = "REPAIR_NOT_VERIFIED"
    receipt_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="failed signature verification"):
        clean_room_module._verify_seed_source_provenance(
            seed_source="def f():\n    return 1\n",
            seed_receipt_path=receipt_path,
        )
