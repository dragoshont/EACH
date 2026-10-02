"""M5 signing primitive tests: real Ed25519 key generation/persistence via
the mature ``cryptography`` library (no custom crypto), isolated to a
temporary EACH_HOME so tests never touch the user's real signing key."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization

from each import signing


@pytest.fixture(autouse=True)
def _isolated_each_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))


def test_generate_or_load_signing_key_persists_outside_any_repo_path(tmp_path: Path) -> None:
    key = signing.generate_or_load_signing_key()
    assert signing.private_key_path().is_file()
    assert signing.public_key_path().is_file()
    # Never inside the EACH repository checkout itself.
    assert "src/EACH" not in str(signing.private_key_path()) or str(tmp_path) in str(signing.private_key_path())
    assert key is not None


def test_generate_or_load_signing_key_is_stable_across_calls() -> None:
    first = signing.generate_or_load_signing_key()
    second = signing.generate_or_load_signing_key()
    manifest = {"a": "b"}
    sig1 = signing.sign_manifest(first, manifest)
    sig2 = signing.sign_manifest(second, manifest)
    # Same persisted key -> same deterministic Ed25519 signature.
    assert sig1 == sig2


def test_private_key_file_has_owner_only_permissions() -> None:
    signing.generate_or_load_signing_key()
    mode = signing.private_key_path().stat().st_mode & 0o777
    assert mode == 0o600


def test_sign_and_verify_round_trip_with_only_the_exported_public_key_bytes() -> None:
    """Proves genuine asymmetric verification: a party holding only the
    exported public key PEM bytes (not the private key, not even the same
    in-process object) can verify a signature produced by the private key.
    """
    private_key = signing.generate_or_load_signing_key()
    manifest = {"stage": "deadbeef"}
    signature = signing.sign_manifest(private_key, manifest)

    public_pem_bytes = signing.public_key_path().read_bytes()
    independently_loaded_public_key = signing.load_public_key(public_pem_bytes)

    assert signing.verify_manifest(independently_loaded_public_key, manifest, signature) is True


def test_verify_fails_with_a_different_keypairs_public_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = signing.generate_or_load_signing_key()
    manifest = {"stage": "deadbeef"}
    signature = signing.sign_manifest(private_key, manifest)

    # A second, unrelated keypair under a different EACH_HOME.
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "other-each-home"))
    other_private_key = signing.generate_or_load_signing_key()
    other_public_pem = signing.public_key_path().read_bytes()
    other_public_key = signing.load_public_key(other_public_pem)
    assert other_private_key.private_bytes_raw() != private_key.private_bytes_raw()

    assert signing.verify_manifest(other_public_key, manifest, signature) is False


def test_verify_fails_if_the_manifest_content_changed() -> None:
    private_key = signing.generate_or_load_signing_key()
    signature = signing.sign_manifest(private_key, {"stage": "original"})
    public_key = signing.load_public_key(signing.public_key_path().read_bytes())
    assert signing.verify_manifest(public_key, {"stage": "tampered"}, signature) is False


def test_verify_rejects_a_corrupted_base64_signature_without_raising() -> None:
    private_key = signing.generate_or_load_signing_key()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_key = signing.load_public_key(public_pem)
    assert signing.verify_manifest(public_key, {"a": "b"}, "not valid base64 !!!") is False
