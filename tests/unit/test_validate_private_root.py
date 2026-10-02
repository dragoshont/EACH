"""F3 regression: ``validate_private_root`` must fail closed, BEFORE any
fetch/materialize/write, if the private EACH store would resolve inside
this repository's own working tree -- not only at receipt-finalization
time (``Receipt.write``'s own, separate, end-of-pipeline check)."""

from __future__ import annotations

import pytest

from each.paths import repo_root, validate_private_root


def test_validate_private_root_passes_for_a_genuinely_private_location(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))
    resolved = validate_private_root()
    assert resolved == (tmp_path / "each-home").resolve()


def test_validate_private_root_rejects_each_home_inside_the_repo_checkout(monkeypatch) -> None:
    nested = repo_root() / "a-should-never-exist-dir"
    monkeypatch.setenv("EACH_HOME", str(nested))
    try:
        with pytest.raises(ValueError, match="inside the repository working tree"):
            validate_private_root()
    finally:
        if nested.is_dir():
            nested.rmdir()


def test_validate_private_root_rejects_each_home_equal_to_the_repo_checkout(monkeypatch) -> None:
    monkeypatch.setenv("EACH_HOME", str(repo_root()))
    with pytest.raises(ValueError, match="inside the repository working tree"):
        validate_private_root()
