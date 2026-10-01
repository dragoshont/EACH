"""Unified-diff parsing, scope validation, and application.

Patch validation happens on the trusted harness side, before any sandboxed
execution: a model's raw completion is never executed directly, and never
applied without passing scope/path/symlink checks first.
"""

from __future__ import annotations

from pathlib import Path

from unidiff import PatchSet
from unidiff.errors import UnidiffParseError

PATCH_BEGIN = "BEGIN_PATCH"
PATCH_END = "END_PATCH"


class PatchRejected(RuntimeError):
    """Raised when a proposed patch fails validation or cannot be applied safely."""


def extract_patch_text(completion: str) -> str:
    """Pull the diff body out of BEGIN_PATCH/END_PATCH markers.

    Rejects completions that omit the markers or are empty between them,
    since raw model output is otherwise unconstrained free text.
    """
    if PATCH_BEGIN not in completion or PATCH_END not in completion:
        raise PatchRejected("completion missing BEGIN_PATCH/END_PATCH markers")
    body = completion.split(PATCH_BEGIN, 1)[1].split(PATCH_END, 1)[0]
    body = body.strip("\n")
    if not body.strip():
        raise PatchRejected("empty patch body")
    return body + "\n"


def parse_patch(patch_text: str) -> PatchSet:
    try:
        patch = PatchSet(patch_text)
    except UnidiffParseError as exc:
        raise PatchRejected(f"malformed unified diff: {exc}") from exc
    if len(patch) == 0:
        raise PatchRejected("diff parsed but contains no file changes")
    return patch


def _normalized_target(path_str: str) -> str:
    # Unified-diff paths are typically "a/<path>" / "b/<path>"; strip the prefix.
    parts = path_str.split("/", 1)
    if len(parts) == 2 and parts[0] in ("a", "b"):
        return parts[1]
    return path_str


def validate_patch_scope(patch: PatchSet, allowed_paths: set[str]) -> list[str]:
    """Return the sorted list of real target paths touched, or raise PatchRejected."""
    touched: list[str] = []
    for pf in patch:
        for raw in (pf.source_file, pf.target_file):
            target = _normalized_target(raw)
            if target == "/dev/null":
                continue
            if target.startswith("/") or ".." in Path(target).parts:
                raise PatchRejected(f"patch touches forbidden/traversal path: {target}")
            if target not in allowed_paths:
                raise PatchRejected(f"patch touches out-of-scope path: {target}")
            touched.append(target)
    if not touched:
        raise PatchRejected("patch touches no files")
    return sorted(set(touched))


def apply_patch(patch: PatchSet, worktree: Path, allowed_paths: set[str]) -> list[str]:
    """Apply a validated patch to files inside `worktree`. Returns touched paths."""
    touched = validate_patch_scope(patch, allowed_paths)
    worktree_resolved = worktree.resolve()
    for pf in patch:
        target_name = _normalized_target(pf.target_file)
        if target_name == "/dev/null":
            continue
        target_path = worktree / target_name
        if target_path.is_symlink():
            raise PatchRejected(f"refusing to patch through symlink: {target_path}")
        resolved = target_path.resolve()
        if resolved != worktree_resolved and worktree_resolved not in resolved.parents:
            raise PatchRejected(f"resolved patch target escapes worktree: {resolved}")

        original_lines = target_path.read_text().splitlines(keepends=True) if target_path.exists() else []
        new_lines = list(original_lines)
        # Apply hunks bottom-to-top so earlier line offsets stay valid.
        for hunk in sorted(pf, key=lambda h: h.source_start, reverse=True):
            start = max(hunk.source_start - 1, 0)
            length = hunk.source_length
            replacement = [line.value for line in hunk if not line.is_removed]
            new_lines[start : start + length] = replacement

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text("".join(new_lines))
    return touched
