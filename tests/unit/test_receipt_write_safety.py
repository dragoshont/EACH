"""F3/F5 regression: ``Receipt.write`` must never write inside the
repository working tree, must never silently overwrite an already-written
receipt, and (F5) must be able to copy the exact declared material files
alongside the receipt with full traversal/escape containment.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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
    (source / "sub" / "a.c").write_text("int main() {}\n")
    receipt = _receipt(materials={"sub/a.c": "irrelevant-for-this-test"})
    _json_path, _md_path = receipt.write(tmp_path / "run-3", materials_source=source)
    copied = tmp_path / "run-3" / "materials" / "sub" / "a.c"
    assert copied.read_text() == "int main() {}\n"


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
