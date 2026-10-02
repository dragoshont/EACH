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


def test_extract_patch_text_falls_back_to_fenced_diff_block() -> None:
    """Real instruction-tuned models frequently ignore a custom marker
    convention and use a plain markdown code fence instead, even when
    explicitly told to use BEGIN_PATCH/END_PATCH -- this is a format
    tolerance, not a validation relaxation (the extracted text still goes
    through the same parse/apply checks)."""
    completion = (
        "Here is the fix:\n\n"
        "```diff\n"
        "--- a/src/greet.py\n"
        "+++ b/src/greet.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def greet(name: str) -> str:\n"
        '-    return "Hell, " + name\n'
        '+    return "Hello, " + name\n'
        "```\n"
    )
    body = extract_patch_text(completion)
    assert "--- a/src/greet.py" in body
    assert "+++ b/src/greet.py" in body
    patch = parse_patch(body)
    assert len(patch) == 1


def test_extract_patch_text_falls_back_to_unclosed_trailing_fence() -> None:
    """Real completions sometimes open a fence, emit a genuine diff, and
    simply stop (EOS) without ever emitting the closing ```` ``` ````, even
    at a generous output-token budget -- this is model phrasing style, not
    truncation, and must still be recoverable."""
    completion = (
        "```diff\n"
        "--- a/src/greet.py\n"
        "+++ b/src/greet.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def greet(name: str) -> str:\n"
        '-    return "Hell, " + name\n'
        '+    return "Hello, " + name\n'
    )
    body = extract_patch_text(completion)
    assert "--- a/src/greet.py" in body
    assert "+++ b/src/greet.py" in body
    patch = parse_patch(body)
    assert len(patch) == 1


def test_extract_patch_text_prefers_literal_markers_over_fence() -> None:
    # If both are present, the literal markers still win (no ambiguity
    # about which content is authoritative).
    completion = "```diff\nnot the real patch\n```\n" + VALID_PATCH
    body = extract_patch_text(completion)
    assert "not the real patch" not in body


def test_extract_patch_text_rejects_fence_without_diff_markers() -> None:
    with pytest.raises(PatchRejected, match="BEGIN_PATCH/END_PATCH"):
        extract_patch_text("```python\nprint('hello')\n```\n")


def test_extract_patch_text_restores_a_genuinely_blank_context_line() -> None:
    """Real local models frequently emit a true empty line (not a single
    space) for a blank context line inside a hunk -- a common
    trailing-whitespace-stripping habit. A strict parser then miscounts the
    hunk's remaining body lines and rejects the whole diff over one missing
    space character. extract_patch_text must mechanically restore it (never
    inventing/altering any other line) so the diff parses and applies.
    """
    completion = (
        "BEGIN_PATCH\n"
        "--- a/src/greet.py\n"
        "+++ b/src/greet.py\n"
        "@@ -1,3 +1,3 @@\n"
        " def greet(name: str) -> str:\n"
        "\n"
        "-    return \"Hell, \" + name\n"
        "+    return \"Hello, \" + name\n"
        "END_PATCH\n"
    )
    body = extract_patch_text(completion)
    lines = body.splitlines()
    assert lines[4] == " "  # restored, not still an empty string
    patch = parse_patch(body)
    assert len(patch) == 1


def test_extract_patch_text_does_not_touch_blank_lines_outside_a_hunk() -> None:
    """A blank line between file-header lines (not yet inside a hunk) is
    left alone -- there is nothing inside a hunk yet to restore. (Leading/
    trailing blank lines around the whole body are already separately
    trimmed by ``.strip("\\n")``, so this exercises a blank line placed
    between the two file-header lines instead.)"""
    completion = "BEGIN_PATCH\n--- a/src/greet.py\n\n+++ b/src/greet.py\n@@ -1,1 +1,1 @@\n-x\n+y\nEND_PATCH\n"
    body = extract_patch_text(completion)
    assert body.splitlines()[1] == ""


def test_parse_patch_rejects_malformed_diff() -> None:
    malformed = "--- a/x\n+++ b/x\n@@ -1,1 +1,1 @@\n*not a valid diff line prefix\n"
    with pytest.raises(PatchRejected, match="malformed unified diff"):
        parse_patch(malformed)


def test_parse_patch_rejects_a_hunk_header_unidiff_silently_drops() -> None:
    """Regression: a non-numeric field in a @@ header (e.g. a model that
    literally echoes a placeholder like "<your new line count>" instead of
    computing a real number) is silently dropped by unidiff -- the
    PatchedFile entry still exists (from the ---/+++ lines) but with zero
    hunks, which must never be treated as a no-op "successful" patch that
    silently changes nothing."""
    malformed = "--- a/x\n+++ b/x\n@@ -1,1 +1,<not a number> @@\n-old\n+new\n"
    with pytest.raises(PatchRejected, match="zero hunks"):
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
