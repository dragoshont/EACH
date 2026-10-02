"""F3 regression: :func:`each.paths.assert_no_symlink_escape` must reject a
symlinked leaf path and a symlinked existing ancestor directory, and must
accept an ordinary fresh (or pre-existing, non-symlinked) private path."""

from __future__ import annotations

from pathlib import Path

import pytest

from each.paths import assert_no_symlink_escape, cache_dir, keys_dir, models_dir, runs_dir, worktrees_dir


def test_accepts_a_fresh_nonexistent_path(tmp_path: Path) -> None:
    assert_no_symlink_escape(tmp_path / "fresh" / "leaf")


def test_accepts_an_existing_plain_directory(tmp_path: Path) -> None:
    existing = tmp_path / "real"
    existing.mkdir()
    assert_no_symlink_escape(existing / "leaf")


def test_rejects_a_symlinked_leaf(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    leaf = tmp_path / "leaf"
    leaf.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        assert_no_symlink_escape(leaf)


def test_rejects_a_symlinked_ancestor(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    ancestor_link = tmp_path / "ancestor-link"
    ancestor_link.symlink_to(outside)
    with pytest.raises(ValueError, match="ancestor"):
        assert_no_symlink_escape(ancestor_link / "child" / "leaf")


@pytest.mark.parametrize(
    ("name", "directory"),
    [("runs", runs_dir), ("worktrees", worktrees_dir), ("cache", cache_dir),
     ("models", models_dir), ("keys", keys_dir)],
)
def test_private_child_symlink_cannot_create_external_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, directory
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (home / name).symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("EACH_HOME", str(home))
    with pytest.raises(ValueError, match="symlink"):
        directory()
    assert list(outside.iterdir()) == []


def test_shadow_source_collision_rejected_before_descendant_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from each.xodus_shadow import _assemble_source_root

    home = tmp_path / "home"
    destination = home / "shadow" / "m8" / "run" / "source"
    destination.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (destination / "examples").symlink_to(outside, target_is_directory=True)
    (destination / "xsystem.c").write_text("sentinel")
    monkeypatch.setenv("EACH_HOME", str(home))
    with pytest.raises(FileExistsError, match="reuse"):
        _assemble_source_root("fixture", "xsystem.c", destination)
    assert (destination / "xsystem.c").read_text() == "sentinel"
    assert list(outside.iterdir()) == []


def test_shadow_source_outside_private_root_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from each.xodus_shadow import _assemble_source_root

    monkeypatch.setenv("EACH_HOME", str(tmp_path / "home"))
    destination = tmp_path / "outside" / "source"
    with pytest.raises(ValueError, match="private root"):
        _assemble_source_root("fixture", "xsystem.c", destination)
    assert not destination.parent.exists()
