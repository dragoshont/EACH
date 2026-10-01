"""Sanitized worktree creation.

Only the paths declared by the approved spec (plus any required test files)
are copied from the fixture/target source tree into an isolated temporary
directory, with a content manifest recorded, before any model-proposed
patch is parsed or applied.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from each.hashing import sha256_file
from each.paths import worktrees_dir


class WorktreeError(RuntimeError):
    pass


def build_worktree(
    source_root: Path, include_paths: list[str], dest: Path | None = None
) -> tuple[Path, dict[str, str]]:
    """Copy `include_paths` (relative to source_root) into a fresh worktree dir.

    Returns (worktree_path, manifest) where manifest maps relative path to
    the sha256 of the copied file, recorded before any patch is applied.

    The default worktree root lives under the private EACH store
    (``$HOME/.each/worktrees``) rather than the OS temp directory, since a
    container executor run through ``docker --context colima-each`` can
    only see paths Colima bind-mounts into its guest VM (``$HOME`` by
    default, not ``/tmp``).
    """
    worktree = dest or Path(tempfile.mkdtemp(prefix="each-worktree-", dir=worktrees_dir()))
    source_resolved = source_root.resolve()
    manifest: dict[str, str] = {}
    for rel in include_paths:
        if rel.startswith("/") or ".." in Path(rel).parts:
            raise WorktreeError(f"refusing to include forbidden/traversal path: {rel}")
        unresolved = source_root / rel
        if unresolved.is_symlink():
            raise WorktreeError(f"refusing to copy symlink source: {rel}")
        src = unresolved.resolve()
        if src != source_resolved and source_resolved not in src.parents:
            raise WorktreeError(f"source path escapes source root: {rel}")
        if not src.is_file():
            raise WorktreeError(f"declared path is not a regular file: {rel}")
        dst = worktree / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        manifest[rel] = sha256_file(dst)
    return worktree, manifest
