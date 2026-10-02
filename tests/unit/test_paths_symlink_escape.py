"""F3 regression: :func:`each.paths.assert_no_symlink_escape` must reject a
symlinked leaf path and a symlinked existing ancestor directory, and must
accept an ordinary fresh (or pre-existing, non-symlinked) private path."""

from __future__ import annotations

from pathlib import Path

import pytest

from each.paths import assert_no_symlink_escape


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
