"""F5 (MOST IMPORTANT) regression: ``attestation.verify_materials_root``
must perform REAL existence/sha256 verification of the actual retained
material files under a trusted local artifact root -- not just check that
a receipt's own JSON ``materials`` manifest is internally present, and not
just that some file happens to exist at all. A signature-only
``verify_receipt`` PASS proves the receipt's *declarations* were not
altered after signing; it says nothing about whether the files those
declarations describe still exist on disk with that content. This is the
strictly stronger, separate check.
"""

from __future__ import annotations

from pathlib import Path

from each.attestation import verify_materials_root
from each.hashing import sha256_text


def _receipt_with_material(rel_path: str, content: str) -> dict:
    return {"materials": {rel_path: sha256_text(content)}}


def test_full_artifact_verification_passes_for_genuine_retained_file(tmp_path: Path) -> None:
    content = "int main() {}\n"
    materials_root = tmp_path / "materials"
    (materials_root / "sub").mkdir(parents=True)
    (materials_root / "sub" / "a.c").write_text(content)
    receipt = _receipt_with_material("sub/a.c", content)
    result = verify_materials_root(receipt, materials_root)
    assert result["status"] == "PASS"


def test_full_artifact_verification_fails_on_actual_file_mutation(tmp_path: Path) -> None:
    """The real-world defect this check must catch: the declared hash was
    computed over one version of the file, but the actually-retained bytes
    were later mutated (e.g. a real changed source falsely declared as the
    original input). Deleting/editing the JSON manifest entry is NOT this
    bug -- only re-hashing the real retained bytes catches it."""
    original = "int main() {}\n"
    mutated = "int main() { return 1; }\n"
    materials_root = tmp_path / "materials"
    (materials_root / "sub").mkdir(parents=True)
    (materials_root / "sub" / "a.c").write_text(mutated)
    receipt = _receipt_with_material("sub/a.c", original)
    result = verify_materials_root(receipt, materials_root)
    assert result["status"] == "FAIL"
    assert "sub/a.c" in result["reason"]


def test_full_artifact_verification_fails_on_actual_file_deletion(tmp_path: Path) -> None:
    """Deleting the real retained file (not just removing its manifest
    entry) must FAIL, matching the exact scenario the prior weak test
    missed."""
    materials_root = tmp_path / "materials"
    materials_root.mkdir()
    receipt = _receipt_with_material("sub/a.c", "int main() {}\n")
    result = verify_materials_root(receipt, materials_root)
    assert result["status"] == "FAIL"
    assert "missing" in result["reason"]


def test_full_artifact_verification_is_unavailable_without_a_materials_root(tmp_path: Path) -> None:
    """A receipt written before this feature existed (or without a
    ``materials_source`` at all) is honestly declaration-only evidence for
    this specific check, not a fabricated PASS or a false FAIL."""
    receipt = _receipt_with_material("sub/a.c", "int main() {}\n")
    result = verify_materials_root(receipt, tmp_path / "does-not-exist")
    assert result["status"] == "UNAVAILABLE"


def test_full_artifact_verification_passes_when_no_materials_declared(tmp_path: Path) -> None:
    result = verify_materials_root({"materials": {}}, tmp_path / "does-not-exist")
    assert result["status"] == "PASS"


def test_full_artifact_verification_rejects_traversal_declared_path(tmp_path: Path) -> None:
    materials_root = tmp_path / "materials"
    materials_root.mkdir()
    receipt = _receipt_with_material("../outside.c", "x")
    result = verify_materials_root(receipt, materials_root)
    assert result["status"] == "FAIL"
    assert "traversal" in result["reason"]


def test_full_artifact_verification_fails_for_a_malformed_declared_hash(tmp_path: Path) -> None:
    """A manifest entry declaring an obviously-malformed/arbitrary hash value
    for a real, untouched file must FAIL -- the check always compares real
    bytes against the declaration; it never special-cases or trusts an
    unparseable/wrong-length declared value as if it were unverifiable."""
    content = "int main() {}\n"
    materials_root = tmp_path / "materials"
    (materials_root / "sub").mkdir(parents=True)
    (materials_root / "sub" / "a.c").write_text(content)
    receipt = {"materials": {"sub/a.c": "not-a-real-sha256-hash"}}
    result = verify_materials_root(receipt, materials_root)
    assert result["status"] == "FAIL"


def test_full_artifact_verification_rejects_symlink_escape(tmp_path: Path) -> None:
    materials_root = tmp_path / "materials"
    materials_root.mkdir()
    outside = tmp_path / "outside.c"
    outside.write_text("secret\n")
    (materials_root / "linked.c").symlink_to(outside)
    receipt = _receipt_with_material("linked.c", "secret\n")
    result = verify_materials_root(receipt, materials_root)
    assert result["status"] == "FAIL"
    assert "escapes" in result["reason"] or "symlink" in result["reason"]


def test_full_artifact_verification_rejects_in_root_symlink(tmp_path: Path) -> None:
    """F2 (public code review at 6c3e1f3): a symlink whose target resolves
    to somewhere INSIDE ``materials_root`` must still be rejected -- under
    the old "resolve() first, then is_symlink()" ordering it silently
    passed both the escape check (in-root) and the is_symlink() check
    (the resolved real file is not itself a symlink).
    """
    materials_root = tmp_path / "materials"
    materials_root.mkdir()
    real_file = materials_root / "real.c"
    real_file.write_text("x\n")
    (materials_root / "linked.c").symlink_to(real_file)
    receipt = _receipt_with_material("linked.c", sha256_text("x\n"))
    result = verify_materials_root(receipt, materials_root)
    assert result["status"] == "FAIL"
    assert "symlink" in result["reason"]
