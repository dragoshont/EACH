from __future__ import annotations

import json
from pathlib import Path

import pytest

from each.hashing import sha256_file
from each.model_manifest import ModelManifest, build_manifest_from_snapshot, verify_snapshot_matches


def _snapshot(tmp_path: Path) -> Path:
    root = tmp_path.joinpath("a" * 40)
    root.mkdir()
    root.joinpath("model.safetensors").write_bytes(b"fixture weights")
    root.joinpath("tokenizer.json").write_text("{}")
    root.joinpath("tokenizer_config.json").write_text('{"chat_template": "original"}')
    root.joinpath("config.json").write_text('{"quantization": {"bits": 4}}')
    return root


def _manifest(root: Path) -> ModelManifest:
    return build_manifest_from_snapshot(
        root, repo_id="fixture/model", license="Apache-2.0", runtime_name="fixture",
        runtime_version="1", conversion_chain="fixture",
    )


def test_manifest_binds_config_and_auxiliary_tokenizer_files(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    manifest = _manifest(root)
    recorded = manifest.to_dict()
    assert recorded["configSha256"] == sha256_file(root.joinpath("config.json"))
    assert recorded["filesSha256"]["tokenizer_config.json"] == sha256_file(
        root.joinpath("tokenizer_config.json")
    )
    assert recorded["schemaVersion"] == "0.1"


@pytest.mark.parametrize("filename", ["config.json", "tokenizer_config.json"])
def test_config_or_template_mutation_changes_model_identity(tmp_path: Path, filename: str) -> None:
    root = _snapshot(tmp_path)
    before = _manifest(root)
    root.joinpath(filename).write_text(json.dumps({"changed": True}))
    after = _manifest(root)
    assert before.weights_sha256 == after.weights_sha256
    assert before.model_id != after.model_id


def test_missing_config_is_not_a_successful_manifest(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    root.joinpath("config.json").unlink()
    with pytest.raises(ValueError, match="no config.json"):
        _manifest(root)


def test_max_position_embeddings_is_recorded_from_config(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    root.joinpath("config.json").write_text(json.dumps({"quantization": {"bits": 4}, "max_position_embeddings": 2048}))
    manifest = _manifest(root)
    assert manifest.max_position_embeddings == 2048
    assert manifest.to_dict()["maxPositionEmbeddings"] == 2048


def test_missing_max_position_embeddings_is_recorded_honestly_as_none(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    manifest = _manifest(root)
    assert manifest.max_position_embeddings is None
    assert manifest.to_dict()["maxPositionEmbeddings"] is None


def test_verify_snapshot_matches_reports_no_drift_for_untouched_snapshot(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    manifest = _manifest(root)
    assert verify_snapshot_matches(root, manifest) == []


def test_verify_snapshot_matches_detects_weight_file_mutation(tmp_path: Path) -> None:
    """F6: a provisioning root must be treated as read-only -- a snapshot
    whose weight bytes changed after the manifest was built must never be
    silently loaded as if it still matched that manifest."""
    root = _snapshot(tmp_path)
    manifest = _manifest(root)
    root.joinpath("model.safetensors").write_bytes(b"mutated weights")
    drift = verify_snapshot_matches(root, manifest)
    assert any("model.safetensors" in entry and "hash mismatch" in entry for entry in drift)


def test_verify_snapshot_matches_detects_missing_file(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    manifest = _manifest(root)
    root.joinpath("tokenizer.json").unlink()
    drift = verify_snapshot_matches(root, manifest)
    assert any("tokenizer.json" in entry and "missing" in entry for entry in drift)
