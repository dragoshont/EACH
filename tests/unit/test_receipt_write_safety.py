"""F3/F5 regression: ``Receipt.write`` must never write inside the
repository working tree, must never silently overwrite an already-written
receipt, and (F5) must be able to copy the exact declared material files
alongside the receipt with full traversal/escape containment.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from each.hashing import sha256_text
from each.paths import repo_root
from each.receipt import Receipt


def _receipt(**overrides) -> Receipt:
    base = {
        "run_id": "fixture-run",
        "spec": {},
        "spec_hash": "deadbeef",
        "model_identity": {},
        "prompt": "p",
        "raw_completion": "r",
        "patch_text": "",
        "touched_paths": [],
        "materials": {},
        "executor_identity": {},
        "isolation_evidence": {},
        "baseline_result": {},
        "repaired_result": {},
        "audit": {"result": "UNAVAILABLE", "checks": {}},
        "assurance_level": "EACH-P2",
        "outcome": "REPAIR_NOT_VERIFIED",
    }
    base.update(overrides)
    return Receipt(**base)


def test_refuses_to_write_inside_repository_working_tree(tmp_path: Path) -> None:
    receipt = _receipt()
    with pytest.raises(ValueError, match="repository working tree"):
        receipt.write(repo_root() / "a-receipt-must-never-land-here")


def test_refuses_to_overwrite_an_already_written_receipt(tmp_path: Path) -> None:
    receipt = _receipt()
    directory = tmp_path / "run-1"
    receipt.write(directory)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        receipt.write(directory)


def test_writes_cleanly_to_a_fresh_private_directory(tmp_path: Path) -> None:
    receipt = _receipt()
    json_path, md_path = receipt.write(tmp_path / "run-2")
    assert json_path.exists()
    assert md_path.exists()


def test_materials_source_copies_declared_files(tmp_path: Path) -> None:
    source = tmp_path / "worktree"
    (source / "sub").mkdir(parents=True)
    content = "int main() {}\n"
    (source / "sub" / "a.c").write_text(content)
    receipt = _receipt(materials={"sub/a.c": sha256_text(content)})
    _json_path, _md_path = receipt.write(tmp_path / "run-3", materials_source=source)
    copied = tmp_path / "run-3" / "materials" / "sub" / "a.c"
    assert copied.read_text() == content


def test_materials_source_rejects_hash_mismatch(tmp_path: Path) -> None:
    """F5 (MOST IMPORTANT): a declared material whose real bytes do not
    match the declared hash (e.g. because a post-patch worktree was passed
    as ``materials_source`` for a pre-patch declared hash) must never be
    silently signed as if the declaration were true."""
    source = tmp_path / "worktree"
    (source / "sub").mkdir(parents=True)
    (source / "sub" / "a.c").write_text("int main() { return 1; }\n")  # does NOT match the declared hash below
    receipt = _receipt(materials={"sub/a.c": sha256_text("int main() {}\n")})
    with pytest.raises(ValueError, match="does not match its declared hash"):
        receipt.write(tmp_path / "run-3-mismatch", materials_source=source)
    assert not (tmp_path / "run-3-mismatch" / "receipt.json").exists()


def test_materials_source_rejects_destination_symlink_collision(tmp_path: Path) -> None:
    """F3: the materials destination side must be containment-checked too,
    not only the source side -- a symlink planted at the destination path
    must never be followed/written through."""
    source = tmp_path / "worktree"
    (source / "sub").mkdir(parents=True)
    content = "int main() {}\n"
    (source / "sub" / "a.c").write_text(content)
    receipt = _receipt(materials={"sub/a.c": sha256_text(content)})
    directory = tmp_path / "run-3-dst-symlink"
    materials_root = directory / "materials"
    (materials_root / "sub").mkdir(parents=True)
    outside = tmp_path / "outside-dst.c"
    outside.write_text("tampered\n")
    (materials_root / "sub" / "a.c").symlink_to(outside)
    with pytest.raises(ValueError, match="materials destination path escapes materials root|existing materials destination or symlink"):
        receipt.write(directory, materials_source=source)


def test_materials_source_rejects_preexisting_destination_file(tmp_path: Path) -> None:
    """F3: a non-symlink pre-existing file at the exact materials
    destination path (e.g. a leftover/collided run) must also be rejected,
    not silently overwritten."""
    source = tmp_path / "worktree"
    (source / "sub").mkdir(parents=True)
    content = "int main() {}\n"
    (source / "sub" / "a.c").write_text(content)
    receipt = _receipt(materials={"sub/a.c": sha256_text(content)})
    directory = tmp_path / "run-3-dst-exists"
    materials_root = directory / "materials"
    (materials_root / "sub").mkdir(parents=True)
    (materials_root / "sub" / "a.c").write_text("pre-existing\n")
    with pytest.raises(ValueError, match="existing materials destination or symlink"):
        receipt.write(directory, materials_source=source)


def test_materials_source_rejects_traversal_declared_path(tmp_path: Path) -> None:
    source = tmp_path / "worktree"
    source.mkdir()
    receipt = _receipt(materials={"../outside.c": "x"})
    with pytest.raises(ValueError, match="traversal"):
        receipt.write(tmp_path / "run-4", materials_source=source)


def test_materials_source_rejects_escape_via_symlink(tmp_path: Path) -> None:
    source = tmp_path / "worktree"
    source.mkdir()
    outside = tmp_path / "outside.c"
    outside.write_text("secret\n")
    (source / "linked.c").symlink_to(outside)
    receipt = _receipt(materials={"linked.c": "x"})
    with pytest.raises(ValueError, match="escapes its root"):
        receipt.write(tmp_path / "run-5", materials_source=source)


def test_refuses_a_symlinked_receipt_directory(tmp_path: Path) -> None:
    """F3: a symlink planted at the exact receipt-directory name must be
    rejected outright, never followed by ``mkdir(..., exist_ok=True)`` to
    silently write the receipt through it into an unrelated location."""
    outside = tmp_path / "outside-run-dir"
    outside.mkdir()
    receipt = _receipt()
    linked_directory = tmp_path / "run-symlinked"
    linked_directory.symlink_to(outside)
    with pytest.raises(ValueError, match="receipt directory"):
        receipt.write(linked_directory)
    assert not (outside / "receipt.json").exists()


def test_refuses_a_symlinked_materials_root(tmp_path: Path) -> None:
    """F3: if ``<directory>/materials`` is itself a symlink, the anchor
    used for every subsequent destination-containment check must not be
    derived from resolving that symlink (which would trivially make every
    write "inside" its own already-escaped target); the symlink must be
    rejected before any anchor is even computed."""
    source = tmp_path / "worktree"
    (source / "sub").mkdir(parents=True)
    content = "int main() {}\n"
    (source / "sub" / "a.c").write_text(content)
    receipt = _receipt(materials={"sub/a.c": sha256_text(content)})
    directory = tmp_path / "run-materials-symlinked"
    directory.mkdir()
    outside_materials = tmp_path / "outside-materials"
    outside_materials.mkdir()
    (directory / "materials").symlink_to(outside_materials)
    with pytest.raises(ValueError, match="materials destination root"):
        receipt.write(directory, materials_source=source)
    assert list(outside_materials.iterdir()) == []
