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


def test_each_verify_without_full_still_passes_on_signature_alone_for_a_missing_materials_dir(
    tmp_path: Path,
) -> None:
    """Signature-only verification (the pre-existing, default behavior)
    must keep working unchanged for a receipt with no retained materials/
    directory at all -- the new check is additive, opt-in via --full."""
    json_path = _write_receipt_with_materials(tmp_path / "run", tmp_path / "source", "int main() {}\n")
    shutil.rmtree(json_path.parent / "materials")
    assert main(["verify", str(json_path)]) == 0
    # --full on the SAME receipt now honestly reports UNAVAILABLE (not a
    # fabricated PASS or a false FAIL) since the materials/ directory is gone.
    assert main(["verify", str(json_path), "--full"]) == 0
