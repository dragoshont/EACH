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


def _subprocess_first_use_fingerprint(each_home: str) -> str:
    """Run in a real child process: first-use key generation under a
    shared, not-yet-populated EACH_HOME, returning the resulting public-key
    fingerprint. Used to exercise the actual first-use race, not just
    simulate it in-process."""
    import os

    os.environ["EACH_HOME"] = each_home
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    from each import signing as signing_module

    key = signing_module.generate_or_load_signing_key()
    public_key = key.public_key()
    assert isinstance(public_key, Ed25519PublicKey)
    return signing_module.public_key_fingerprint(public_key)


def test_concurrent_first_use_does_not_overwrite_the_winning_keypair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real regression test for the first-use race: multiple processes
    racing ``generate_or_load_signing_key`` against a shared, empty
    EACH_HOME must all converge on the SAME persisted keypair (serialized
    by the exclusive file lock), never each generating and overwriting a
    distinct key."""
    import multiprocessing

    each_home = str(tmp_path / "shared-each-home")
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=8) as pool:
        fingerprints = pool.map(_subprocess_first_use_fingerprint, [each_home] * 8)

    assert len(set(fingerprints)) == 1, "concurrent first use produced more than one distinct keypair"

    # The key persisted on disk must match what every process actually used
    # -- not a key regenerated afterward by whichever process ran last.
    monkeypatch.setenv("EACH_HOME", each_home)
    key = signing.generate_or_load_signing_key()
    assert signing.public_key_fingerprint(key.public_key()) == fingerprints[0]


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
