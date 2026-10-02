"""M5 attestation tests: artifact hash manifest + signature binding, and
the four mandate-required tamper tests (patch mutation, spec mutation,
validation-output mutation, missing declared material)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from each import attestation, signing


@pytest.fixture(autouse=True)
def _isolated_each_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))


def _fake_receipt() -> dict[str, Any]:
    return {
        "runId": "test-run-1",
        "specHash": "a" * 64,
        "materials": {"src/greet.py": "b" * 64, "tests/test_greet.py": "c" * 64},
        "prompt": "fix the bug",
        "rawCompletion": "BEGIN_PATCH\n...\nEND_PATCH\n",
        "patchText": "--- a/src/greet.py\n+++ b/src/greet.py\n@@ -1,2 +1,2 @@\n-bad\n+good\n",
        "baselineResult": {"exit_code": 1, "stdout": "1 failed", "stderr": ""},
        "repairedResult": {"exit_code": 0, "stdout": "1 passed", "stderr": ""},
        "audit": {"checks": {"exact-substring": {"status": "UNAVAILABLE"}}},
    }


def _public_key_bytes() -> bytes:
    return signing.public_key_path().read_bytes()


def test_attest_receipt_produces_a_verifiable_signature() -> None:
    receipt = _fake_receipt()
    receipt["attestation"] = attestation.attest_receipt(receipt)
    result = attestation.verify_receipt(receipt, _public_key_bytes())
    assert result["status"] == "PASS"


def test_manifest_has_one_hash_per_attested_stage_no_single_score() -> None:
    manifest = attestation.build_manifest(_fake_receipt())
    assert set(manifest) == {"spec", "materials", "generation", "patch", "validation", "audit"}
    assert "score" not in manifest


def test_tamper_patch_after_receipt_fails_verification() -> None:
    receipt = _fake_receipt()
    receipt["attestation"] = attestation.attest_receipt(receipt)
    receipt["patchText"] = receipt["patchText"].replace("good", "evil")
    result = attestation.verify_receipt(receipt, _public_key_bytes())
    assert result["status"] == "FAIL"
    assert "patch" in result["reason"]


def test_tamper_spec_after_approval_fails_verification() -> None:
    receipt = _fake_receipt()
    receipt["attestation"] = attestation.attest_receipt(receipt)
    receipt["specHash"] = "f" * 64
    result = attestation.verify_receipt(receipt, _public_key_bytes())
    assert result["status"] == "FAIL"
    assert "spec" in result["reason"]


def test_tamper_validation_output_fails_verification() -> None:
    receipt = _fake_receipt()
    receipt["attestation"] = attestation.attest_receipt(receipt)
    receipt["repairedResult"]["exit_code"] = 1
    receipt["repairedResult"]["stdout"] = "1 failed"
    result = attestation.verify_receipt(receipt, _public_key_bytes())
    assert result["status"] == "FAIL"
    assert "validation" in result["reason"]


def test_remove_declared_material_fails_verification() -> None:
    receipt = _fake_receipt()
    receipt["attestation"] = attestation.attest_receipt(receipt)
    del receipt["materials"]["tests/test_greet.py"]
    result = attestation.verify_receipt(receipt, _public_key_bytes())
    assert result["status"] == "FAIL"
    assert "materials" in result["reason"]


def test_verification_is_deterministic_across_repeated_calls() -> None:
    receipt = _fake_receipt()
    receipt["attestation"] = attestation.attest_receipt(receipt)
    results = [attestation.verify_receipt(receipt, _public_key_bytes())["status"] for _ in range(5)]
    assert results == ["PASS"] * 5


def test_verify_rejects_an_unattested_receipt() -> None:
    signing.generate_or_load_signing_key()
    receipt = _fake_receipt()
    result = attestation.verify_receipt(receipt, _public_key_bytes())
    assert result["status"] == "FAIL"
    assert "attestation" in result["reason"]


def test_verify_rejects_a_forged_key_pairing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A third party who only has a *different* public key (e.g. an
    attacker's own, or simply the wrong one) must not be fooled even if
    every stage hash in the receipt is internally self-consistent."""
    receipt = _fake_receipt()
    receipt["attestation"] = attestation.attest_receipt(receipt)

    monkeypatch.setenv("EACH_HOME", str(tmp_path / "attacker-each-home"))
    signing.generate_or_load_signing_key()
    wrong_public_key_bytes = signing.public_key_path().read_bytes()

    result = attestation.verify_receipt(receipt, wrong_public_key_bytes)
    assert result["status"] == "FAIL"


def test_verify_handles_a_malformed_public_key_without_raising() -> None:
    receipt = _fake_receipt()
    receipt["attestation"] = attestation.attest_receipt(receipt)
    result = attestation.verify_receipt(receipt, b"not a real PEM")
    assert result["status"] == "FAIL"


def test_verify_rejects_a_non_ed25519_public_key_without_raising() -> None:
    """A wrong-algorithm but syntactically valid PEM (e.g. RSA) must be
    rejected cleanly, not crash with a TypeError deep inside .verify()."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    receipt = _fake_receipt()
    receipt["attestation"] = attestation.attest_receipt(receipt)
    rsa_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rsa_public_pem = rsa_private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    result = attestation.verify_receipt(receipt, rsa_public_pem)
    assert result["status"] == "FAIL"
    assert "Ed25519" in result["reason"]


def test_verify_states_result_is_not_legal_certification_via_receipt_fields() -> None:
    # The honest capability-boundary disclosure lives on the Receipt
    # dataclass itself (legalCertification/cleanroomCertification), not on
    # the attestation block -- confirm attest_receipt does not invent or
    # override those fields.
    receipt = _fake_receipt()
    attestation_block = attestation.attest_receipt(receipt)
    assert "legalCertification" not in attestation_block
    assert "cleanroomCertification" not in attestation_block
