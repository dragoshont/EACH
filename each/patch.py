"""Unified-diff parsing, scope validation, and application.

Patch validation happens on the trusted harness side, before any sandboxed
execution: a model's raw completion is never executed directly, and never
applied without passing scope/path/symlink checks first.
"""

from __future__ import annotations

import re
from pathlib import Path

from unidiff import PatchSet
from unidiff.errors import UnidiffParseError

PATCH_BEGIN = "BEGIN_PATCH"
PATCH_END = "END_PATCH"

_FENCED_BLOCK_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_OPEN_FENCE_RE = re.compile(r"```[^\n]*\n(.*)", re.DOTALL)


class PatchRejected(RuntimeError):
    """Raised when a proposed patch fails validation or cannot be applied safely."""


def extract_patch_text(completion: str) -> str:
    """Pull the diff body out of BEGIN_PATCH/END_PATCH markers.

    Falls back, in order, to:

    1. the first *closed* markdown code fence that looks like a unified
       diff (contains both a ``--- `` and a ``+++ `` line);
    2. an unclosed trailing fence (the model opened a fence and emitted a
       diff but never emitted a closing ```` ``` ````, which real
       instruction-tuned models do even at generous output-token budgets --
       this is model phrasing style, not truncation, and is only used when
       the content after the single opening fence itself looks like a
       diff).

    This is a format-tolerance fallback, not a relaxation of validation:
    whichever text is extracted still goes through the same
    ``parse_patch``/``apply_patch`` scope and pre-image checks. Real
    instruction-tuned models frequently ignore a custom marker convention
    in favor of the much more common fenced-code-block convention even when
    explicitly told to use markers.

    Rejects completions that have neither the markers nor a recognizable
    fenced diff, since raw model output is otherwise unconstrained free
    text.
    """
    if PATCH_BEGIN in completion and PATCH_END in completion:
        body = completion.split(PATCH_BEGIN, 1)[1].split(PATCH_END, 1)[0]
    else:
        body = None
        for block in _FENCED_BLOCK_RE.findall(completion):
            if "--- " in block and "+++ " in block:
                body = block
                break
        if body is None:
            open_match = _OPEN_FENCE_RE.search(completion)
            if open_match and "--- " in open_match.group(1) and "+++ " in open_match.group(1):
                body = open_match.group(1)
        if body is None:
            raise PatchRejected("completion has neither BEGIN_PATCH/END_PATCH markers nor a fenced unified diff")
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
    for pf in patch:
        if len(pf) == 0:
            # A hunk header unidiff could not match (e.g. a non-numeric
            # line-count field) is silently dropped by unidiff rather than
            # raising -- the PatchedFile entry still exists (from the
            # ---/+++ file-name lines), but with zero hunks, which would
            # otherwise let apply_patch silently no-op (touch nothing,
            # change nothing) instead of failing loud.
            raise PatchRejected(
                f"diff for {pf.target_file} parsed with zero hunks (a malformed @@ header was likely dropped)"
            )
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


def _hunk_span(hunk) -> tuple[int, int]:
    """Return (start, length): the 0-based slice of the pre-image this hunk covers.

    For a pure insertion (source_length == 0), unified-diff numbers the hunk
    by the line *after which* it is inserted (0 means "before the first
    line"), and that number is already the correct 0-based insertion index
    -- unlike a modify/delete hunk, it must not be decremented by one.
    """
    if hunk.source_length == 0:
        return hunk.source_start, 0
    return hunk.source_start - 1, hunk.source_length


def apply_patch(patch: PatchSet, worktree: Path, allowed_paths: set[str]) -> list[str]:
    """Apply a validated patch to files inside `worktree`. Returns touched paths.

    Every hunk's pre-image (its context + removed lines) is compared against
    the file's actual current content before anything is written: a stale or
    fabricated pre-image is rejected rather than blindly overwritten.
    """
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

        spans: list[tuple[int, int, object]] = []
        prev_end = 0
        for hunk in sorted(pf, key=lambda h: h.source_start):
            start, length = _hunk_span(hunk)
            end = start + length
            if start < 0 or end > len(original_lines):
                raise PatchRejected(
                    f"hunk out of bounds for {target_name}: lines {start + 1}-{end} but file has "
                    f"{len(original_lines)} line(s)"
                )
            if start < prev_end:
                raise PatchRejected(f"overlapping hunks in {target_name}")
            preimage = [line.value for line in hunk if not line.is_added]
            actual = original_lines[start:end]
            if preimage != actual:
                raise PatchRejected(
                    f"patch does not apply cleanly to {target_name}: stale or mismatched "
                    f"context/removed lines starting at line {start + 1}"
                )
            spans.append((start, end, hunk))
            prev_end = end

        new_lines = list(original_lines)
        for start, end, hunk in sorted(spans, key=lambda item: item[0], reverse=True):
            replacement = [line.value for line in hunk if not line.is_removed]
            new_lines[start:end] = replacement

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text("".join(new_lines))
    return touched
