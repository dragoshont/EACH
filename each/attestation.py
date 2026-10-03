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

from pathlib import Path
from typing import Any

from each.hashing import sha256_file, sha256_json, sha256_text
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


def verify_materials_root(receipt: dict[str, Any], materials_root: Path) -> dict[str, Any]:
    """Verify the REAL retained material files under ``materials_root``
    actually exist and match their declared ``receipt["materials"]`` hash.

    This is a strictly stronger, separate check from :func:`verify_receipt`:
    a passing signature only proves the receipt JSON's own *declarations*
    were not altered after signing -- it says nothing about whether the
    external files those declarations describe still exist, were ever
    retained, or genuinely have that content. A receipt can have a
    perfectly valid signature while declaring a false material (e.g. an
    input whose recorded hash does not match what was actually used, or a
    file that was later deleted/mutated); this function is what actually
    checks that, not declaration-only trust.

    Returns ``status: "UNAVAILABLE"`` (not ``"FAIL"``) when
    ``materials_root`` itself does not exist at all -- this is the honest
    state for every receipt written before this check existed, or any
    receipt written without a ``materials_source`` (declaration-only
    evidence for this specific check, not proof of tampering).
    """
    materials = receipt.get("materials", {})
    if not materials:
        return {"status": "PASS", "reason": "receipt declares no materials to verify"}
    if not materials_root.is_dir():
        return {
            "status": "UNAVAILABLE",
            "reason": (
                f"no retained materials directory at {materials_root}; this receipt is "
                "declaration-only evidence for full artifact verification"
            ),
        }
    materials_root_resolved = materials_root.resolve()
    problems: list[str] = []
    for rel_path, expected_hash in sorted(materials.items()):
        if rel_path.startswith("/") or ".." in Path(rel_path).parts:
            problems.append(f"{rel_path}: forbidden/traversal path")
            continue
        # (F2, public review at 6c3e1f3) same unresolved-first symlink
        # check as ``Receipt.write``: resolve() already follows a symlink
        # to its real target, so checking is_symlink() only afterward
        # silently misses a symlink anywhere along ``rel_path`` -- even
        # one whose target happens to resolve back inside this root.
        candidate_unresolved = materials_root / rel_path
        if candidate_unresolved.is_symlink():
            problems.append(f"{rel_path}: is a symlink")
            continue
        candidate = candidate_unresolved.resolve()
        if candidate != materials_root_resolved and materials_root_resolved not in candidate.parents:
            problems.append(f"{rel_path}: escapes materials root")
            continue
        if not candidate.is_file():
            problems.append(f"{rel_path}: missing")
            continue
        actual_hash = sha256_file(candidate)
        if actual_hash != expected_hash:
            problems.append(f"{rel_path}: hash mismatch")
    if problems:
        return {
            "status": "FAIL",
            "reason": f"{len(problems)} declared material path(s) failed verification: {problems}",
        }
    return {
        "status": "PASS",
        "reason": f"all {len(materials)} declared material path(s) exist and match their declared hash",
    }
