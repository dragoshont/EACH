"""M5 attestation: artifact hash manifest + Ed25519 signature binding a
receipt's declared stages (intake/spec approval, materialization,
generation, validation, audit) so tampering any stage after the receipt
was written is independently detectable.

Deliberately NOT a full in-toto/DSSE envelope: the mandate allows that
"if it remains YAGNI-compatible"; a bespoke in-toto layer would be a
large spec to implement correctly for v0.1 with no demonstrated need over
a sorted hash manifest + mature-library signature, so that is recorded
here as a conscious, honest limitation rather than silently skipped.
"""

from __future__ import annotations

from typing import Any

from each.hashing import sha256_json, sha256_text
from each.signing import generate_or_load_signing_key, public_key_fingerprint, sign_manifest, verify_manifest

ALGORITHM = "ed25519"


def build_manifest(receipt: dict[str, Any]) -> dict[str, str]:
    """Hash each attested stage of a receipt dict (``Receipt.to_dict()``
    shape) independently, so a verifier can see which specific stage a
    tamper touched. The receipt root additionally binds the actual spec,
    model identity, full attempt history, assurance, and certification flags."""
    return {
        "receipt": sha256_json({key: value for key, value in receipt.items() if key != "attestation"}),
        "spec": receipt["specHash"],
        "materials": sha256_json(receipt["materials"]),
        "generation": sha256_json({"prompt": receipt["prompt"], "rawCompletion": receipt["rawCompletion"]}),
        "patch": sha256_text(receipt["patchText"]),
        "validation": sha256_json(
            {"baselineResult": receipt["baselineResult"], "repairedResult": receipt["repairedResult"]}
        ),
        "audit": sha256_json(receipt["audit"]),
    }


def attest_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Sign the receipt's stage manifest with the local EACH signing key
    (generated on first use; never committed -- see each.signing) and
    return the attestation block to embed under ``receipt["attestation"]``.
    """
    private_key = generate_or_load_signing_key()
    manifest = build_manifest(receipt)
    return {
        "algorithm": ALGORITHM,
        "manifest": manifest,
        "signature": sign_manifest(private_key, manifest),
        "keyFingerprint": public_key_fingerprint(private_key.public_key()),
    }


def verify_receipt(receipt: dict[str, Any], public_key_pem: bytes) -> dict[str, Any]:
    """Independently verify a receipt against an externally supplied public
    key (never the one embedded in the receipt itself -- an attacker who
    can modify the receipt could also forge an embedded key, so the
    verifying party must already possess the real public key out of band).

    Returns a result dict with ``status`` (``"PASS"`` or ``"FAIL"``) and a
    human ``reason``; never raises for a malformed/tampered receipt.
    """
    from each.signing import load_public_key

    attestation = receipt.get("attestation")
    if not isinstance(attestation, dict) or not attestation.get("signature") or not attestation.get("manifest"):
        return {"status": "FAIL", "reason": "receipt has no attestation block"}
    if attestation.get("algorithm") != ALGORITHM:
        return {"status": "FAIL", "reason": "unsupported attestation algorithm"}

    try:
        current_manifest = build_manifest(receipt)
    except KeyError as exc:
        return {"status": "FAIL", "reason": f"receipt is missing a required field: {exc}"}

    if current_manifest != attestation["manifest"]:
        changed = sorted(
            stage
            for stage in set(current_manifest) | set(attestation["manifest"])
            if current_manifest.get(stage) != attestation["manifest"].get(stage)
        )
        return {
            "status": "FAIL",
            "reason": f"recomputed stage hash manifest does not match the attested manifest (changed: {changed})",
        }

    try:
        public_key = load_public_key(public_key_pem)
    except ValueError as exc:
        return {"status": "FAIL", "reason": f"public key is not a valid Ed25519 PEM: {exc}"}

    if attestation.get("keyFingerprint") != public_key_fingerprint(public_key):
        return {"status": "FAIL", "reason": "attested key fingerprint does not match the supplied public key"}

    if not verify_manifest(public_key, current_manifest, attestation["signature"]):
        return {"status": "FAIL", "reason": "signature does not verify against the supplied public key"}

    return {"status": "PASS", "reason": "signature and every attested stage hash verify against the supplied public key"}
