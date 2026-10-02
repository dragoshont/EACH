"""M5 attestation signing primitives.

Uses the mature ``cryptography`` library's Ed25519 implementation -- no
custom cryptography. The private signing key lives outside the repository
under ``each.paths.keys_dir()`` (``~/.each/keys`` by default, the same
private, gitignored store used for model weights and GitHub tokens -- see
``each/paths.py``) and is never committed.

Honest limitation (documented, not hidden): the private key file is an
unencrypted PEM for v0.1 -- there is no passphrase/HSM/keychain integration
yet. Its confidentiality currently depends entirely on filesystem
permissions (0600) and the key directory being outside the repo and
gitignored. This is noted as a known limitation, not a certified secure
key-management solution.
"""

from __future__ import annotations

import base64
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from each.hashing import canonical_json, sha256_bytes
from each.paths import keys_dir

PRIVATE_KEY_FILENAME = "each-signing-ed25519.pem"
PUBLIC_KEY_FILENAME = "each-signing-ed25519-public.pem"


def private_key_path() -> Path:
    return keys_dir() / PRIVATE_KEY_FILENAME


def public_key_path() -> Path:
    return keys_dir() / PUBLIC_KEY_FILENAME


def generate_or_load_signing_key() -> Ed25519PrivateKey:
    """Return the EACH signing key, generating and persisting a new Ed25519
    keypair on first use. Never regenerates an existing key (that would
    silently invalidate every previously issued attestation)."""
    key_path = private_key_path()
    if key_path.exists():
        return serialization.load_pem_private_key(key_path.read_bytes(), password=None)

    private_key = Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_path.write_bytes(pem)
    key_path.chmod(0o600)

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_key_path().write_bytes(public_pem)
    return private_key


def load_public_key(pem_bytes: bytes) -> Ed25519PublicKey:
    """Load a public key PEM, rejecting any non-Ed25519 key type.

    ``cryptography``'s ``load_pem_public_key`` happily loads RSA/EC/etc. keys
    too, whose ``.verify()`` signature differs and would otherwise raise an
    unhandled ``TypeError`` deep inside verification instead of a clean FAIL.
    """
    public_key = serialization.load_pem_public_key(pem_bytes)
    if not isinstance(public_key, Ed25519PublicKey):
        # Intentionally ValueError (not TypeError) to match load_pem_public_key's
        # own error type for malformed PEM input, so callers can catch one type.
        raise ValueError("public key is not an Ed25519 key")  # noqa: TRY004
    return public_key


def public_key_fingerprint(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    return sha256_bytes(raw)


def sign_manifest(private_key: Ed25519PrivateKey, manifest: dict[str, str]) -> str:
    signature = private_key.sign(canonical_json(manifest).encode("utf-8"))
    return base64.b64encode(signature).decode("ascii")


def verify_manifest(public_key: Ed25519PublicKey, manifest: dict[str, str], signature_b64: str) -> bool:
    try:
        signature = base64.b64decode(signature_b64)
    except (ValueError, TypeError):
        return False
    try:
        public_key.verify(signature, canonical_json(manifest).encode("utf-8"))
        return True
    except InvalidSignature:
        return False
