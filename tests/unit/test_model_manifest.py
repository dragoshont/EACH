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


def test_n_positions_fallback_for_gpt_bigcode_family_configs(tmp_path: Path) -> None:
    """Regression: granite-20b-code-instruct's own config.json declares its
    context window as "n_positions" (model_type="gpt_bigcode"), not
    "max_position_embeddings". Before this fix, the context-budget check
    was silently SKIPPED (not failed closed) for any such checkpoint,
    because the manifest recorded None -- the opposite of the mandate's
    "never silently let a prompt exceed the real supported context"
    requirement."""
    root = _snapshot(tmp_path)
    root.joinpath("config.json").write_text(
        json.dumps({"quantization": {}, "model_type": "gpt_bigcode", "n_positions": 8192})
    )
    manifest = _manifest(root)
    assert manifest.max_position_embeddings == 8192
    assert manifest.to_dict()["maxPositionEmbeddings"] == 8192


def test_max_position_embeddings_takes_priority_over_n_positions_when_both_present(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    root.joinpath("config.json").write_text(
        json.dumps({"quantization": {}, "max_position_embeddings": 4096, "n_positions": 8192})
    )
    manifest = _manifest(root)
    assert manifest.max_position_embeddings == 4096


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


def test_snapshot_rejects_an_extra_weight_shard_after_admission(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    manifest = _manifest(root)
    (root / "extra.safetensors").write_bytes(b"unrecorded fixture weights")
    assert verify_snapshot_matches(root, manifest) == ["extra.safetensors: unrecorded file"]


def test_snapshot_manifest_accepts_publisher_pytorch_shards(tmp_path: Path) -> None:
    root = tmp_path / "revision"
    root.mkdir()
    (root / "config.json").write_text('{"n_positions":2048}')
    (root / "tokenizer.json").write_text("{}")
    (root / "pytorch_model-00001-of-00001.bin").write_bytes(b"weights")
    manifest = build_manifest_from_snapshot(
        root,
        repo_id="publisher/model",
        license="Apache-2.0",
        runtime_name="transformers",
        runtime_version="test",
        conversion_chain="publisher bytes",
    )
    assert set(manifest.weights_sha256) == {"pytorch_model-00001-of-00001.bin"}
