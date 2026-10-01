from __future__ import annotations

from pathlib import Path

import pytest

from each.worktree import WorktreeError, build_worktree


def test_build_worktree_rejects_traversal(tmp_path: Path) -> None:
    source = tmp_path / "src-root"
    source.mkdir()
    with pytest.raises(WorktreeError, match="traversal"):
        build_worktree(source, ["../outside.py"], dest=tmp_path / "wt")


def test_build_worktree_rejects_symlink_source(tmp_path: Path) -> None:
    source = tmp_path / "src-root"
    source.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("x = 1\n")
    link = source / "linked.py"
    link.symlink_to(outside)
    with pytest.raises(WorktreeError, match="symlink"):
        build_worktree(source, ["linked.py"], dest=tmp_path / "wt")


def test_build_worktree_copies_declared_files(tmp_path: Path) -> None:
    source = tmp_path / "src-root"
    (source / "src").mkdir(parents=True)
    (source / "src" / "a.py").write_text("x = 1\n")
    worktree, manifest = build_worktree(source, ["src/a.py"], dest=tmp_path / "wt")
    assert (worktree / "src" / "a.py").read_text() == "x = 1\n"
    assert "src/a.py" in manifest
