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
