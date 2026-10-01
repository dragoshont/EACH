from __future__ import annotations

from pathlib import Path

import pytest

from each.patch import (
    PatchRejected,
    apply_patch,
    extract_patch_text,
    parse_patch,
    validate_patch_scope,
)

VALID_PATCH = """BEGIN_PATCH
--- a/src/greet.py
+++ b/src/greet.py
@@ -1,2 +1,2 @@
 def greet(name: str) -> str:
-    return "Hell, " + name
+    return "Hello, " + name
END_PATCH
"""


def test_extract_patch_text_requires_markers() -> None:
    with pytest.raises(PatchRejected, match="BEGIN_PATCH/END_PATCH"):
        extract_patch_text("not a patch at all")


def test_extract_patch_text_rejects_empty_body() -> None:
    with pytest.raises(PatchRejected, match="empty patch body"):
        extract_patch_text("BEGIN_PATCH\n\nEND_PATCH")


def test_parse_patch_rejects_malformed_diff() -> None:
    malformed = "--- a/x\n+++ b/x\n@@ -1,1 +1,1 @@\n*not a valid diff line prefix\n"
    with pytest.raises(PatchRejected, match="malformed unified diff"):
        parse_patch(malformed)


def test_parse_patch_rejects_diff_with_no_file_changes() -> None:
    with pytest.raises(PatchRejected, match="no file changes"):
        parse_patch("this is not --- +++ @@ a valid\ndiff at all\n")


def test_validate_patch_scope_accepts_in_scope_path() -> None:
    patch = parse_patch(extract_patch_text(VALID_PATCH))
    touched = validate_patch_scope(patch, {"src/greet.py"})
    assert touched == ["src/greet.py"]


def test_validate_patch_scope_rejects_out_of_scope_path() -> None:
    patch = parse_patch(extract_patch_text(VALID_PATCH))
    with pytest.raises(PatchRejected, match="out-of-scope"):
        validate_patch_scope(patch, {"src/other.py"})


def test_validate_patch_scope_rejects_path_traversal() -> None:
    traversal_patch_text = (
        "--- a/../../etc/passwd\n"
        "+++ b/../../etc/passwd\n"
        "@@ -1 +1 @@\n"
        "-root:x:0:0:root:/root:/bin/bash\n"
        "+pwned:x:0:0:root:/root:/bin/bash\n"
    )
    patch = parse_patch(traversal_patch_text)
    with pytest.raises(PatchRejected, match="forbidden/traversal"):
        validate_patch_scope(patch, {"../../etc/passwd"})


def test_apply_patch_rejects_symlink_target(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    (worktree / "src").mkdir(parents=True)
    outside = tmp_path / "outside.py"
    outside.write_text("def greet(name):\n    return 'Hell, ' + name\n")
    symlink_path = worktree / "src" / "greet.py"
    symlink_path.symlink_to(outside)

    patch = parse_patch(extract_patch_text(VALID_PATCH))
    with pytest.raises(PatchRejected, match="symlink"):
        apply_patch(patch, worktree, {"src/greet.py"})
    assert outside.read_text() == "def greet(name):\n    return 'Hell, ' + name\n"


def test_apply_patch_updates_file_in_scope(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    (worktree / "src").mkdir(parents=True)
    (worktree / "src" / "greet.py").write_text('def greet(name: str) -> str:\n    return "Hell, " + name\n')

    patch = parse_patch(extract_patch_text(VALID_PATCH))
    touched = apply_patch(patch, worktree, {"src/greet.py"})
    assert touched == ["src/greet.py"]
    assert "Hello, " in (worktree / "src" / "greet.py").read_text()


def test_apply_patch_rejects_stale_preimage(tmp_path: Path) -> None:
    """The removed/context line must actually be present; a fabricated or
    stale preimage (file content already differs from what the diff claims
    to be removing) must be rejected, never silently applied."""
    worktree = tmp_path / "wt"
    (worktree / "src").mkdir(parents=True)
    # Actual file content no longer matches the patch's claimed "Hell, " preimage.
    (worktree / "src" / "greet.py").write_text('def greet(name: str) -> str:\n    return "Howdy, " + name\n')

    patch = parse_patch(extract_patch_text(VALID_PATCH))
    with pytest.raises(PatchRejected, match="stale or mismatched"):
        apply_patch(patch, worktree, {"src/greet.py"})
    # The file must be left untouched.
    assert "Howdy, " in (worktree / "src" / "greet.py").read_text()


def test_apply_patch_inserts_at_correct_offset(tmp_path: Path) -> None:
    """A pure insertion hunk (@@ -1,0 +2,1 @@) must insert *after* line 1,
    not at offset zero."""
    worktree = tmp_path / "wt"
    worktree.mkdir(parents=True)
    (worktree / "f.txt").write_text("alpha\nbeta\n")

    insertion_patch = parse_patch("--- a/f.txt\n+++ b/f.txt\n@@ -1,0 +2,1 @@\n+inserted\n")
    apply_patch(insertion_patch, worktree, {"f.txt"})
    assert (worktree / "f.txt").read_text() == "alpha\ninserted\nbeta\n"


def test_apply_patch_rejects_out_of_bounds_hunk(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir(parents=True)
    (worktree / "f.txt").write_text("only one line\n")

    # Claims to replace 2 lines starting at line 5, but the file has only 1 line.
    out_of_bounds_patch = parse_patch(
        "--- a/f.txt\n+++ b/f.txt\n@@ -5,2 +5,1 @@\n-missing line a\n-missing line b\n+replacement\n"
    )
    with pytest.raises(PatchRejected, match="out of bounds"):
        apply_patch(out_of_bounds_patch, worktree, {"f.txt"})
