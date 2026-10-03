"""Regression tests for the M2 model catalog: unknown keys and the exact,
honest "unavailable" reasons must be real, not silently swallowed."""

from __future__ import annotations

import json

import pytest

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
        load_model("octocoder-transformers-mps")


def test_octocoder_reports_incomplete_download_with_a_concrete_shard_count(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("each.models.catalog.models_dir", lambda: tmp_path)
    weights_dir = tmp_path / "bigcode--octocoder"
    weights_dir.mkdir(parents=True)
    index = {"weight_map": {"layer.0": "shard-00001.safetensors", "layer.1": "shard-00002.safetensors"}}
    (weights_dir / "model.safetensors.index.json").write_text(json.dumps(index), encoding="utf-8")
    # Only one of the two declared shards actually present on disk.
    (weights_dir / "shard-00001.safetensors").write_bytes(b"")
    with pytest.raises(UnavailableModelError, match=r"download incomplete: 1/2 safetensors shard\(s\) missing"):
        load_model("octocoder-transformers-mps")


def test_octocoder_reports_no_adapter_once_every_declared_shard_is_present(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("each.models.catalog.models_dir", lambda: tmp_path)
    weights_dir = tmp_path / "bigcode--octocoder"
    weights_dir.mkdir(parents=True)
    index = {"weight_map": {"layer.0": "shard-00001.safetensors", "layer.1": "shard-00002.safetensors"}}
    (weights_dir / "model.safetensors.index.json").write_text(json.dumps(index), encoding="utf-8")
    (weights_dir / "shard-00001.safetensors").write_bytes(b"")
    (weights_dir / "shard-00002.safetensors").write_bytes(b"")
    with pytest.raises(UnavailableModelError, match="no Transformers/MPS RepairModel adapter is implemented"):
        load_model("octocoder-transformers-mps")


def test_gguf_reports_no_verified_conversion_provenance() -> None:
    with pytest.raises(UnavailableModelError, match="no llama.cpp/GGUF conversion with recorded provenance"):
        load_model("granite-gguf-llamacpp")


def test_load_model_rejects_unsupported_kwarg_for_entries_without_tunable_params() -> None:
    # A keyword a builder does not accept must raise a normal TypeError, not
    # be silently swallowed as a no-op override.
    with pytest.raises(TypeError):
        load_model("granite-gguf-llamacpp", max_tokens=1024)
