"""F5 regression: ``each verify --full`` must wire real materials-root
artifact verification into the CLI, distinct from the pre-existing
signature-only check, and must fail the exit code on a real material
mutation (not merely report success because the signature itself is
untouched)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from each.cli import main
from each.hashing import sha256_text
from each.receipt import Receipt


@pytest.fixture(autouse=True)
def _isolated_each_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))


def _write_receipt_with_materials(run_dir: Path, source_dir: Path, content: str) -> Path:
    (source_dir / "sub").mkdir(parents=True)
    (source_dir / "sub" / "a.c").write_text(content)
    receipt = Receipt(
        run_id="full-verify-cli-test",
        spec={},
        spec_hash="deadbeef",
        model_identity={},
        prompt="p",
        raw_completion="r",
        patch_text="",
        touched_paths=[],
        materials={"sub/a.c": sha256_text(content)},
        executor_identity={},
        isolation_evidence={},
        baseline_result={},
        repaired_result={},
        audit={"result": "UNAVAILABLE", "checks": {}},
        assurance_level="EACH-P2",
        outcome="REPAIR_NOT_VERIFIED",
    )
    json_path, _md_path = receipt.write(run_dir, materials_source=source_dir)
    return json_path


def test_each_verify_full_passes_when_materials_are_genuinely_retained(tmp_path: Path) -> None:
    json_path = _write_receipt_with_materials(tmp_path / "run", tmp_path / "source", "int main() {}\n")
    assert main(["verify", str(json_path), "--full"]) == 0


def test_each_verify_full_fails_when_a_real_material_file_is_later_mutated(tmp_path: Path) -> None:
    json_path = _write_receipt_with_materials(tmp_path / "run", tmp_path / "source", "int main() {}\n")
    # Mutate the ACTUAL retained file, not the receipt's JSON manifest entry
    # (that distinction is exactly the F5 bug this flag exists to catch).
    materials_file = json_path.parent / "materials" / "sub" / "a.c"
    materials_file.write_text("int main() { return 1; }\n")
    assert main(["verify", str(json_path), "--full"]) == 1


def test_each_verify_full_fails_when_a_real_material_file_is_deleted(tmp_path: Path) -> None:
    json_path = _write_receipt_with_materials(tmp_path / "run", tmp_path / "source", "int main() {}\n")
    materials_file = json_path.parent / "materials" / "sub" / "a.c"
    materials_file.unlink()
    assert main(["verify", str(json_path), "--full"]) == 1


def test_each_verify_full_fails_when_the_entire_materials_directory_is_deleted(tmp_path: Path) -> None:
    json_path = _write_receipt_with_materials(tmp_path / "run", tmp_path / "source", "int main() {}\n")
    shutil.rmtree(json_path.parent / "materials")
    assert main(["verify", str(json_path), "--full"]) == 1
    # Signature-only (default, non-full) verification is unaffected.
    assert main(["verify", str(json_path)]) == 0


def test_each_verify_full_fails_for_a_malformed_declared_material_hash(tmp_path: Path) -> None:
    """A receipt whose own ``materials`` manifest declares a malformed/
    arbitrary hash value for a real, otherwise-untouched file must FAIL full
    verification -- the check compares real bytes against the declaration,
    it does not special-case or skip an obviously-wrong declared value."""
    run_dir = tmp_path / "run"
    source_dir = tmp_path / "source"
    (source_dir / "sub").mkdir(parents=True)
    (source_dir / "sub" / "a.c").write_text("int main() {}\n")
    receipt = Receipt(
        run_id="full-verify-cli-malformed-hash",
        spec={},
        spec_hash="deadbeef",
        model_identity={},
        prompt="p",
        raw_completion="r",
        patch_text="",
        touched_paths=[],
        materials={"sub/a.c": "not-a-real-sha256-hash"},
        executor_identity={},
        isolation_evidence={},
        baseline_result={},
        repaired_result={},
        audit={"result": "UNAVAILABLE", "checks": {}},
        assurance_level="EACH-P2",
        outcome="REPAIR_NOT_VERIFIED",
    )
    with pytest.raises(ValueError, match="does not match its declared hash"):
        receipt.write(run_dir, materials_source=source_dir)
