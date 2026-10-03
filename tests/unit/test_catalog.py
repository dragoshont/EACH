"""Regression tests for the M2 model catalog: unknown keys and the exact,
honest "unavailable" reasons must be real, not silently swallowed."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from each.hashing import sha256_file
from each.models import catalog
from each.models.catalog import UnavailableModelError, load_model


def test_load_model_unknown_key_raises_with_known_keys_listed() -> None:
    with pytest.raises(UnavailableModelError, match="unknown model key"):
        load_model("not-a-real-model")


# (F5) These three cases used to depend on whatever real, host-specific state
# happened to exist under this Mac's actual ~/.each/models cache (absent,
# partially downloaded, or fully downloaded with no shard missing) -- the
# test only passed because the then-current real download state on this one
# development machine happened to match one of the two branches it checked,
# and silently did not even cover the "weights not downloaded" (fully
# absent) case at all. Each case now uses a hermetic tmp_path models_dir,
# independent of any real downloaded weights, so this test is reproducible
# on a fresh clone/CI host and exercises all three real code paths.
def test_octocoder_reports_absent_weights_honestly(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("each.models.catalog.models_dir", lambda: tmp_path)
    with pytest.raises(UnavailableModelError, match="weights not downloaded"):
        catalog._octocoder_transformers_mps()


def test_octocoder_reports_incomplete_download_with_a_concrete_shard_count(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("each.models.catalog.models_dir", lambda: tmp_path)
    weights_dir = tmp_path / "bigcode--octocoder"
    weights_dir.mkdir(parents=True)
    index = {"weight_map": {"layer.0": "shard-00001.safetensors", "layer.1": "shard-00002.safetensors"}}
    (weights_dir / "model.safetensors.index.json").write_text(json.dumps(index), encoding="utf-8")
    # Only one of the two declared shards actually present on disk.
    (weights_dir / "shard-00001.safetensors").write_bytes(b"")
    with pytest.raises(UnavailableModelError, match=r"download incomplete: 1/2 safetensors shard\(s\) missing"):
        catalog._octocoder_transformers_mps()


def test_octocoder_reports_no_adapter_once_every_declared_shard_is_present(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("each.models.catalog.models_dir", lambda: tmp_path)
    weights_dir = tmp_path / "bigcode--octocoder"
    weights_dir.mkdir(parents=True)
    index = {"weight_map": {"layer.0": "shard-00001.safetensors", "layer.1": "shard-00002.safetensors"}}
    (weights_dir / "model.safetensors.index.json").write_text(json.dumps(index), encoding="utf-8")
    (weights_dir / "shard-00001.safetensors").write_bytes(b"")
    (weights_dir / "shard-00002.safetensors").write_bytes(b"")
    with pytest.raises(UnavailableModelError, match="no Transformers/MPS RepairModel adapter is implemented"):
        catalog._octocoder_transformers_mps()


def test_gguf_reports_no_verified_conversion_provenance() -> None:
    with pytest.raises(UnavailableModelError, match="no llama.cpp/GGUF conversion with recorded provenance"):
        catalog._granite_gguf_llamacpp()


def test_load_model_rejects_unsupported_kwarg_for_entries_without_tunable_params() -> None:
    # A keyword a builder does not accept must raise a normal TypeError, not
    # be silently swallowed as a no-op override.
    with pytest.raises(TypeError):
        catalog._granite_gguf_llamacpp(max_tokens=1024)


@pytest.mark.parametrize("key", [
    key for key in catalog._CATALOG if key not in {"starcoderbase-mlx", "octocoder-mlx"}
])
def test_catalog_blocks_unqualified_training_provenance_before_loading(key, monkeypatch) -> None:
    def must_not_load(**kwargs):
        pytest.fail("unqualified model builder was invoked")

    monkeypatch.setitem(catalog._CATALOG, key, must_not_load)
    with pytest.raises(UnavailableModelError, match="training-data provenance is not qualified"):
        load_model(key)


def test_qualified_base_still_requires_provisioned_artifact(monkeypatch, tmp_path):
    monkeypatch.setattr(catalog, "models_dir", lambda: tmp_path)
    with pytest.raises(UnavailableModelError, match="not provisioned"):
        load_model("starcoderbase-mlx")


def test_unrelated_conversion_cannot_enter_qualified_base(monkeypatch, tmp_path):
    monkeypatch.setattr(catalog, "models_dir", lambda: tmp_path)
    root = tmp_path / "qualified" / "starcoderbase-fp16" / catalog.STARCODERBASE_REVISION
    root.mkdir(parents=True)
    (root / "conversion.json").write_text(json.dumps({
        "sourceRepo": "Qwen/Qwen2.5-Coder-14B-Instruct",
        "sourceRevision": catalog.STARCODERBASE_REVISION,
        "operation": "pytorch-fp32-to-safetensors-fp16",
        "sourceFilesSha256": {"weights.bin": "a"},
        "outputFilesSha256": {"model.safetensors": "b"},
    }))
    with pytest.raises(UnavailableModelError, match="does not match"):
        load_model("starcoderbase-mlx")


@pytest.mark.parametrize("name", ["starcoderbase", "octocoder"])
def test_qualified_conversion_binds_lineage_and_rejects_output_drift(monkeypatch, tmp_path, name):
    """Synthetic artifact/adapter fixture, never a real model qualification."""
    monkeypatch.setattr(catalog, "models_dir", lambda: tmp_path)
    monkeypatch.setattr(catalog, "_mlx_runtime_version", lambda: "test-runtime")
    monkeypatch.setattr(
        "each.models.mlx_model.MLXRepairModel",
        lambda path, manifest, **kwargs: SimpleNamespace(manifest=manifest, options=kwargs),
    )
    profile = catalog.qualified_profile(name)
    root = tmp_path / "qualified" / f"{name}-fp16" / profile["revision"]
    root.mkdir(parents=True)
    for index in range(1, 8):
        (root / f"model-{index:05d}-of-00007.safetensors").write_bytes(b"synthetic-test-weights")
    (root / "config.json").write_text('{"n_positions":8192}')
    (root / "tokenizer.json").write_text("{}")
    weight_map = {f"tensor.{i}": f"model-{i:05d}-of-00007.safetensors" for i in range(1, 8)}
    (root / "model.safetensors.index.json").write_text(json.dumps({"weight_map": weight_map}))
    record = {
        "sourceRepo": profile["repo"],
        "sourceRevision": profile["revision"],
        "operation": profile["operation"],
        "sourceWeightsSha256": profile["weights"],
        "sourceFilesSha256": profile["weights"],
        "outputFilesSha256": {p.name: sha256_file(p) for p in root.iterdir()},
        "tensorRoundTripVerified": True,
        "sourceIndexVerified": True,
        "tensorCount": 7,
        "runtimeModelConfig": {"tie_word_embeddings": True},
        "trainingPerformed": False,
    }
    (root / "conversion.json").write_text(json.dumps(record))
    result = load_model(f"{name}-mlx")
    assert result.manifest.to_dict()["trainingDataProvenance"]["modelRevision"] == profile["revision"]
    assert result.manifest.max_position_embeddings == 8192
    assert result.options["model_config"] == {"tie_word_embeddings": name == "octocoder"}
    if name == "octocoder":
        assert result.options["prompt_format"] == "question-answer"
    (root / "extra.json").write_text("{}")
    with pytest.raises(UnavailableModelError, match="every output artifact"):
        load_model(f"{name}-mlx")
    (root / "extra.json").unlink()
    (root / "model-00001-of-00007.safetensors").write_bytes(b"changed")
    with pytest.raises(UnavailableModelError, match="changed"):
        load_model(f"{name}-mlx")


def test_octocoder_unknown_lineage_blocks_before_artifact_access(monkeypatch):
    monkeypatch.setitem(catalog.OCTOCODER_LINEAGE, "status", "UNKNOWN")
    monkeypatch.setattr(catalog, "models_dir", lambda: pytest.fail("must reject before disk or backend access"))
    with pytest.raises(UnavailableModelError, match="not qualified"):
        load_model("octocoder-mlx")


def test_octocoder_wrong_source_is_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(catalog, "models_dir", lambda: tmp_path)
    root = tmp_path / "qualified" / "octocoder-fp16" / catalog.OCTOCODER_REVISION
    root.mkdir(parents=True)
    (root / "conversion.json").write_text(json.dumps({
        "sourceRepo": "bigcode/starcoderbase",
        "sourceRevision": catalog.OCTOCODER_REVISION,
    }))
    with pytest.raises(UnavailableModelError, match="does not match"):
        load_model("octocoder-mlx")
