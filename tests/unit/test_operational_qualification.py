"""Real filesystem/Ed25519 exercises with a TEMPORARY key, never the user key."""

import errno
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from each import signing
from each.attestation import verify_materials_root, verify_receipt
from each.hashing import sha256_text
from each.paths import FileLock, each_home, runs_dir
from tests.unit.test_receipt_write_safety import _receipt


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "private-test-store"))


def test_missing_private_key_does_not_replace_retained_public_identity():
    signing.generate_or_load_signing_key()
    public = signing.public_key_path().read_bytes()
    signing.private_key_path().unlink()
    with pytest.raises(ValueError, match="restore"):
        signing.generate_or_load_signing_key()
    assert signing.public_key_path().read_bytes() == public
    assert not signing.private_key_path().exists()


def test_loss_of_both_keys_with_retained_receipts_requires_restore():
    directory = runs_dir() / "old"
    _receipt().write(directory)
    signing.private_key_path().unlink()
    signing.public_key_path().unlink()
    before = (directory / "receipt.json").read_bytes()
    with pytest.raises(ValueError, match="restore"):
        signing.generate_or_load_signing_key()
    assert (directory / "receipt.json").read_bytes() == before


def test_corrupt_private_key_is_never_replaced():
    signing.generate_or_load_signing_key()
    signing.private_key_path().write_bytes(b"corrupt temporary test key")
    with pytest.raises(ValueError, match="corrupt"):
        signing.generate_or_load_signing_key()
    assert signing.private_key_path().read_bytes() == b"corrupt temporary test key"


@pytest.mark.parametrize("leaf", ["private", "public", "lock"])
def test_key_and_lock_symlinks_are_rejected(tmp_path, leaf):
    signing.generate_or_load_signing_key()
    target = tmp_path / "outside-test-file"
    path = (
        signing.private_key_path() if leaf == "private"
        else signing.public_key_path() if leaf == "public"
        else signing.private_key_path().parent / signing._LOCK_FILENAME
    )
    original = path.read_bytes()
    path.unlink()
    target.write_bytes(original)
    path.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        signing.generate_or_load_signing_key()
    assert target.read_bytes() == original


def test_file_lock_does_not_follow_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.write_bytes(b"unchanged")
    link = tmp_path / "lock"
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"), FileLock(link):
        pass
    assert outside.read_bytes() == b"unchanged"


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions support row only")
def test_private_store_and_receipt_permissions(tmp_path):
    home = each_home()
    directory = runs_dir() / "permissions"
    source = tmp_path / "input"
    source.mkdir()
    (source / "fixture.txt").write_text("public synthetic input")
    _receipt(materials={"fixture.txt": sha256_text("public synthetic input")}).write(
        directory, materials_source=source,
    )
    for p in (home, runs_dir(), signing.private_key_path().parent, directory, directory / "materials"):
        assert p.stat().st_mode & 0o777 == 0o700
    for p in (directory / "receipt.json", directory / "receipt.md", directory / "materials/fixture.txt"):
        assert p.stat().st_mode & 0o777 == 0o600


def test_same_run_concurrent_writers_cannot_overwrite(tmp_path):
    directory = tmp_path / "same-run"

    def write(index):
        try:
            _receipt(raw_completion=f"public synthetic completion {index}").write(directory)
            return True
        except FileExistsError:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(write, range(4))) == 1
    data = json.loads((directory / "receipt.json").read_text())
    assert verify_receipt(data, signing.public_key_path().read_bytes())["status"] == "PASS"


def test_distinct_concurrent_runs_share_one_stable_key():
    def write(index):
        directory = runs_dir() / f"concurrent-{index}"
        _receipt(run_id=f"synthetic-{index}").write(directory)
        return json.loads((directory / "receipt.json").read_text())

    with ThreadPoolExecutor(max_workers=6) as pool:
        receipts = list(pool.map(write, range(12)))
    public = signing.public_key_path().read_bytes()
    assert all(verify_receipt(r, public)["status"] == "PASS" for r in receipts)
    assert len({r["attestation"]["keyFingerprint"] for r in receipts}) == 1


def test_concurrent_process_key_initialization_has_one_identity():
    code = (
        "from each.signing import generate_or_load_signing_key,public_key_fingerprint;"
        "print(public_key_fingerprint(generate_or_load_signing_key().public_key()))"
    )
    children = [subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                for _ in range(6)]
    fingerprints = []
    for child in children:
        stdout, stderr = child.communicate(timeout=30)
        assert child.returncode == 0, stderr.decode()
        fingerprints.append(stdout.strip())
    assert len(set(fingerprints)) == 1


def test_temporary_key_and_retained_input_backup_restore(tmp_path, monkeypatch, capsys):
    source = tmp_path / "input"
    source.mkdir()
    (source / "fixture.txt").write_text("public synthetic retained input")
    directory = runs_dir() / "backup-fixture"
    _receipt(materials={"fixture.txt": sha256_text("public synthetic retained input")}).write(
        directory, materials_source=source,
    )
    original_public = signing.public_key_path().read_bytes()
    original_key = signing.private_key_path().read_bytes()
    receipt_bytes = (directory / "receipt.json").read_bytes()
    backup = tmp_path / "backup"
    shutil.copytree(each_home(), backup)
    restored = tmp_path / "restored"
    shutil.copytree(backup, restored)
    monkeypatch.setenv("EACH_HOME", str(restored))
    signing.generate_or_load_signing_key()
    assert signing.public_key_path().read_bytes() == original_public
    assert signing.private_key_path().read_bytes() == original_key
    recovered = runs_dir() / "backup-fixture"
    assert (recovered / "receipt.json").read_bytes() == receipt_bytes
    receipt = json.loads(receipt_bytes)
    assert verify_receipt(receipt, original_public)["status"] == "PASS"
    assert verify_materials_root(receipt, recovered / "materials")["status"] == "PASS"
    from each.cli import main

    assert main(["verify", str(recovered / "receipt.json"), "--full",
                 "--public-key", str(signing.public_key_path()),
                 "--artifact-root", str(recovered / "materials")]) == 0
    output = capsys.readouterr().out
    assert "signature verification: PASS" in output and "materials verification (--full): PASS" in output
    assert "public synthetic retained input" not in output


@pytest.mark.parametrize("damage", ["missing", "corrupt", "symlink"])
def test_retained_artifact_damage_fails_full_verification(tmp_path, damage):
    source = tmp_path / "input"
    source.mkdir()
    (source / "fixture.txt").write_text("synthetic artifact")
    directory = runs_dir() / "damaged"
    _receipt(materials={"fixture.txt": sha256_text("synthetic artifact")}).write(
        directory, materials_source=source,
    )
    receipt = json.loads((directory / "receipt.json").read_text())
    retained = directory / "materials/fixture.txt"
    retained.unlink()
    if damage == "corrupt":
        retained.write_text("wrong")
    elif damage == "symlink":
        retained.symlink_to(source / "fixture.txt")
    assert verify_materials_root(receipt, directory / "materials")["status"] == "FAIL"


def test_receipt_tamper_fails_under_original_key():
    directory = runs_dir() / "tamper"
    _receipt().write(directory)
    data = json.loads((directory / "receipt.json").read_text())
    data["outcome"] = "REPAIR_VERIFIED"
    assert verify_receipt(data, signing.public_key_path().read_bytes())["status"] == "FAIL"


def test_simulated_enospc_preserves_unsigned_trajectory_and_old_receipt(tmp_path, monkeypatch):
    old = runs_dir() / "original"
    _receipt().write(old)
    immutable = (old / "receipt.json").read_bytes()
    source = tmp_path / "input"
    source.mkdir()
    (source / "fixture.txt").write_text("public fixture")

    def no_space(*args, **kwargs):
        raise OSError(errno.ENOSPC, "bounded simulated quota exhaustion")

    monkeypatch.setattr(shutil, "copyfile", no_space)
    failed = runs_dir() / "disk-failure"
    receipt = _receipt(
        prompt="synthetic declared prompt", raw_completion="synthetic complete trajectory",
        materials={"fixture.txt": sha256_text("public fixture")},
    )
    with pytest.raises(OSError) as exc:
        receipt.write(failed, materials_source=source)
    assert exc.value.errno == errno.ENOSPC
    assert not (failed / "receipt.json").exists()
    pending = json.loads((failed / "receipt.pending.json").read_text())
    assert pending["rawCompletion"] == "synthetic complete trajectory"
    assert pending["outcome"] != "REPAIR_VERIFIED"
    assert "attestation" not in pending
    assert (old / "receipt.json").read_bytes() == immutable


def test_low_space_preflight_stops_before_signing_or_material_copy(tmp_path, monkeypatch):
    from collections import namedtuple

    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda path: usage(100, 99, 1))
    with pytest.raises(OSError) as exc:
        _receipt().write(tmp_path / "quota-stopped")
    assert exc.value.errno == errno.ENOSPC
    assert not signing.private_key_path().exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission failure drill")
def test_unreadable_material_retains_draft_and_never_becomes_success(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    artifact = source / "unreadable.txt"
    artifact.write_text("synthetic private-permission fixture")
    artifact.chmod(0)
    directory = runs_dir() / "permission-failed"
    try:
        with pytest.raises(PermissionError):
            _receipt(materials={"unreadable.txt": sha256_text("synthetic private-permission fixture")}).write(
                directory, materials_source=source,
            )
        assert not (directory / "receipt.json").exists()
        pending = json.loads((directory / "receipt.pending.json").read_text())
        assert pending["rawCompletion"] == "r" and "attestation" not in pending
    finally:
        artifact.chmod(0o600)
