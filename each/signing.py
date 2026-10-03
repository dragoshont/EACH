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
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from each.hashing import canonical_json, sha256_bytes
from each.paths import FileLock, assert_no_symlink_escape, each_home, keys_dir

PRIVATE_KEY_FILENAME = "each-signing-ed25519.pem"
PUBLIC_KEY_FILENAME = "each-signing-ed25519-public.pem"
_LOCK_FILENAME = "each-signing-ed25519.lock"


def private_key_path() -> Path:
    return keys_dir() / PRIVATE_KEY_FILENAME


def public_key_path() -> Path:
    return keys_dir() / PUBLIC_KEY_FILENAME


def _write_bytes_atomically(path: Path, data: bytes, *, mode: int) -> None:
    temp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    fd = os.open(str(temp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        os.chmod(path, mode)
    except BaseException:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise


def _load_private_key_from_disk(key_path: Path) -> Ed25519PrivateKey:
    try:
        return serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    except ValueError as exc:
        raise ValueError(f"private signing key at {key_path} is corrupt or incomplete") from exc


def _write_public_key_from_private(private_key: Ed25519PrivateKey) -> None:
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    _write_bytes_atomically(public_key_path(), public_pem, mode=0o644)


def _ensure_public_key_matches(private_key: Ed25519PrivateKey) -> None:
    public_path = public_key_path()
    expected_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if not public_path.exists():
        _write_public_key_from_private(private_key)
        return
    try:
        existing_public = load_public_key(public_path.read_bytes())
    except (OSError, ValueError):
        _write_public_key_from_private(private_key)
        return
    if existing_public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ) != expected_pem:
        _write_public_key_from_private(private_key)


def generate_or_load_signing_key() -> Ed25519PrivateKey:
    """Return the EACH signing key, generating and persisting a new Ed25519
    keypair on first use. Never regenerates an existing key (that would
    silently invalidate every previously issued attestation).

    Every reader takes the same exclusive file lock as the writer: a
    concurrent process must never observe a partially-written private key
    PEM during first-use creation or public-key recovery.
    """
    key_path = private_key_path()
    lock_path = keys_dir() / _LOCK_FILENAME
    for path in (key_path, public_key_path(), lock_path):
        assert_no_symlink_escape(path, label="signing key or lock")
    with FileLock(lock_path):
        for path in (key_path, public_key_path()):
            assert_no_symlink_escape(path, label="signing key")
        if key_path.exists():
            private_key = _load_private_key_from_disk(key_path)
            os.chmod(key_path, 0o600)
            _ensure_public_key_matches(private_key)
            return private_key

        # Missing is not first-use when a public identity or historical receipt
        # survives. Never silently rotate away from the old signing identity.
        retained_runs = each_home() / "runs"
        assert_no_symlink_escape(retained_runs, label="retained runs")
        if public_key_path().exists() or (
            retained_runs.exists() and any(retained_runs.glob("*/receipt.json"))
        ):
            raise ValueError("signing key is missing; restore the original key from a trusted private backup")
        private_key = Ed25519PrivateKey.generate()
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        _write_bytes_atomically(key_path, pem, mode=0o600)
        _write_public_key_from_private(private_key)
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
