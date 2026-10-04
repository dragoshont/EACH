"""Regression tests for the M2 model catalog: unknown keys and the exact,
honest "unavailable" reasons must be real, not silently swallowed."""

from __future__ import annotations

import json
from pathlib import Path
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
    key for key in catalog._CATALOG
    if key not in {
        "starcoderbase-mlx",
        "octocoder-mlx",
        "crystalcoder-transformers",
        "k2-65b-mlx",
        "codegen25-7b-multi-mlx",
    }
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


def test_qualified_crystal_binds_exact_artifact_and_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(catalog, "models_dir", lambda: tmp_path)
    monkeypatch.setattr(catalog, "_transformers_runtime_version", lambda: "4.44.2")
    monkeypatch.setattr(catalog, "verify_snapshot_matches", lambda path, manifest: [])
    monkeypatch.setattr(
        "each.models.transformers_model.TransformersRepairModel",
        lambda path, manifest, **kwargs: SimpleNamespace(path=path, manifest=manifest, options=kwargs),
    )
    root = tmp_path / f"crystal-{catalog.CRYSTAL_REVISION}" / "original"
    root.mkdir(parents=True)
    (root / "config.json").write_text(
        '{"model_type":"crystalcoder","n_positions":2048,"torch_dtype":"bfloat16"}'
    )
    model = load_model("crystalcoder-transformers", max_tokens=256)
    assert model.manifest.model_id == catalog.CRYSTAL_MODEL_ID
    assert model.manifest.weights_sha256 == catalog.CRYSTAL_SOURCE_WEIGHTS
    assert model.manifest.training_data_provenance["status"] == "ELIGIBLE"
    assert model.options["max_tokens"] == 256
    assert model.options["runtime_files_sha256"] == catalog.CRYSTAL_RUNTIME_FILES
    assert model.options["runtime_versions"] == catalog.CRYSTAL_RUNTIME_VERSIONS


def test_qualified_crystal_rejects_artifact_drift(monkeypatch, tmp_path):
    monkeypatch.setattr(catalog, "models_dir", lambda: tmp_path)
    monkeypatch.setattr(catalog, "_transformers_runtime_version", lambda: "4.44.2")
    monkeypatch.setattr(catalog, "verify_snapshot_matches", lambda path, manifest: ["config.json: missing"])
    with pytest.raises(UnavailableModelError, match="absent or has changed"):
        load_model("crystalcoder-transformers")


def test_qualified_crystal_rejects_unknown_lineage_before_artifact_access(monkeypatch):
    lineage = dict(catalog.CRYSTAL_LINEAGE)
    lineage["status"] = "UNKNOWN"
    monkeypatch.setattr(catalog, "CRYSTAL_LINEAGE", lineage)
    monkeypatch.setattr(
        catalog,
        "verify_snapshot_matches",
        lambda *args: pytest.fail("artifact was accessed before lineage eligibility"),
    )
    with pytest.raises(UnavailableModelError, match="provenance is not qualified"):
        load_model("crystalcoder-transformers")


def test_qualified_crystal_rejects_runtime_drift_before_artifact_access(monkeypatch):
    monkeypatch.setattr(
        catalog,
        "sha256_file",
        lambda path: "0" * 64 if path.name == "uv.lock" else catalog.CRYSTAL_RUNTIME_FILES[
            "crystal_runtime.py" if path.name == "crystal_runtime.py" else "pyproject.toml"
        ],
    )
    monkeypatch.setattr(
        catalog,
        "verify_snapshot_matches",
        lambda *args: pytest.fail("artifact was accessed before runtime verification"),
    )
    with pytest.raises(UnavailableModelError, match="runtime is absent or has changed"):
        load_model("crystalcoder-transformers")


def test_qualified_k2_requires_the_exact_provisioned_artifact(monkeypatch, tmp_path):
    monkeypatch.setattr(catalog, "models_dir", lambda: tmp_path)
    with pytest.raises(UnavailableModelError, match="not provisioned"):
        load_model("k2-65b-mlx")


def test_qualified_k2_profile_binds_lineage_and_quantization() -> None:
    profile = json.loads((Path(catalog.__file__).with_name("k2_profile.json")).read_text())
    assert catalog.K2_LINEAGE["status"] == "ELIGIBLE"
    assert profile["sourceRevision"] == catalog.K2_REVISION
    assert profile["lineageEvidence"]["datasetRevision"] == catalog.K2_LINEAGE["datasetRevision"]
    assert profile["quantization"] == {
        "mode": "affine",
        "bits": 8,
        "groupSize": 64,
        "effectiveBitsPerWeightReported": 8.5,
    }
    assert len(profile["sourceWeightsSha256"]) == 27
    assert len(profile["outputWeightsSha256"]) == 14


def test_qualified_k2_rejects_converted_artifact_drift(monkeypatch, tmp_path):
    monkeypatch.setattr(catalog, "models_dir", lambda: tmp_path)
    monkeypatch.setattr(catalog, "_mlx_runtime_version", lambda: "test-runtime")
    root = tmp_path / "qualified" / "k2-int8" / catalog.K2_REVISION
    root.mkdir(parents=True)
    profile_path = Path(catalog.__file__).with_name("k2_profile.json")
    (root / "conversion.json").write_bytes(profile_path.read_bytes())
    monkeypatch.setattr(
        catalog,
        "build_manifest_from_snapshot",
        lambda *args, **kwargs: SimpleNamespace(
            files_sha256={},
            weights_sha256={},
            quantization={},
            max_position_embeddings=None,
        ),
    )
    with pytest.raises(UnavailableModelError, match="converted artifact has changed"):
        load_model("k2-65b-mlx")


def test_qualified_codegen25_requires_the_exact_provisioned_artifact(monkeypatch, tmp_path):
    monkeypatch.setattr(catalog, "models_dir", lambda: tmp_path)
    with pytest.raises(UnavailableModelError, match="not provisioned"):
        load_model("codegen25-7b-multi-mlx")


def test_qualified_codegen25_profile_binds_lineage_and_tokenizer_patch() -> None:
    profile = json.loads((Path(catalog.__file__).with_name("codegen25_profile.json")).read_text())
    assert catalog.CODEGEN25_LINEAGE["status"] == "ELIGIBLE"
    assert profile["sourceRevision"] == catalog.CODEGEN25_REVISION
    assert profile["lineageEvidence"]["datasetRevision"] == catalog.CODEGEN25_LINEAGE["datasetRevision"]
    assert profile["tokenizerCompatibilityPatch"]["outputSha256"] == (
        "8a6718384a609bcdda49504fb1fa38568940f27a2f96ac99badb945234f2171f"
    )
    assert profile["runtime"]["tiktoken"] == "0.4.0"
    assert len(profile["sourceWeightsSha256"]) == 3
    assert len(profile["outputWeightsSha256"]) == 2


def test_qualified_codegen25_rejects_runtime_version_drift(monkeypatch, tmp_path):
    monkeypatch.setattr(catalog, "models_dir", lambda: tmp_path)
    root = tmp_path / "qualified" / "codegen25-multi-int8" / catalog.CODEGEN25_REVISION
    root.mkdir(parents=True)
    profile_path = Path(catalog.__file__).with_name("codegen25_profile.json")
    (root / "conversion.json").write_bytes(profile_path.read_bytes())
    expected = {
        "mlx": "0.32.3",
        "mlx-lm": "0.32.0",
        "transformers": "5.18.0",
        "tiktoken": "0.4.0",
        "torch": "2.14.1",
        "safetensors": "0.8.0",
    }
    monkeypatch.setattr(
        catalog,
        "version",
        lambda package: "9.9.9" if package == "transformers" else expected[package],
    )
    with pytest.raises(UnavailableModelError, match="runtime drift: transformers"):
        load_model("codegen25-7b-multi-mlx")


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
    synthetic_profile = {
        **profile,
        "conversion_sha256": sha256_file(root / "conversion.json"),
        "output_files": record["outputFilesSha256"],
    }
    synthetic_profile["model_id"] = catalog.build_manifest_from_snapshot(
        root,
        repo_id=profile["repo"],
        license="bigcode-openrail-m",
        runtime_name="test-runtime",
        runtime_version="test-runtime",
        conversion_chain="synthetic",
    ).model_id
    monkeypatch.setattr(catalog, "qualified_profile", lambda requested: synthetic_profile if requested == name else profile)
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


@pytest.mark.parametrize("name", ["starcoderbase", "octocoder"])
def test_qualified_conversion_rejects_coordinated_artifact_and_manifest_replacement(monkeypatch, tmp_path, name):
    """Updating conversion.json alongside replaced bytes cannot redefine an authorized artifact."""
    monkeypatch.setattr(catalog, "models_dir", lambda: tmp_path)
    profile = catalog.qualified_profile(name)
    root = tmp_path / "qualified" / f"{name}-fp16" / profile["revision"]
    root.mkdir(parents=True)
    for filename, digest in profile["output_files"].items():
        (root / filename).write_bytes(f"placeholder-for-{digest}".encode())
    conversion = {
        "sourceRepo": profile["repo"],
        "sourceRevision": profile["revision"],
        "operation": profile["operation"],
        "sourceWeightsSha256": profile["weights"],
        "outputFilesSha256": {
            filename: sha256_file(root / filename)
            for filename in profile["output_files"]
        },
        "tensorRoundTripVerified": True,
        "trainingPerformed": False,
    }
    (root / "conversion.json").write_text(json.dumps(conversion))
    with pytest.raises(UnavailableModelError, match="qualified source artifact"):
        load_model(f"{name}-mlx")


@pytest.mark.parametrize("name", ["starcoderbase", "octocoder"])
def test_qualified_conversion_rejects_untrusted_output_map_before_manifest(monkeypatch, tmp_path, name):
    monkeypatch.setattr(catalog, "models_dir", lambda: tmp_path)
    profile = catalog.qualified_profile(name)
    root = tmp_path / "qualified" / f"{name}-fp16" / profile["revision"]
    root.mkdir(parents=True)
    forged_outputs = {"model.safetensors": "0" * 64}
    conversion = {
        "sourceRepo": profile["repo"],
        "sourceRevision": profile["revision"],
        "operation": profile["operation"],
        "sourceWeightsSha256": profile["weights"],
        "outputFilesSha256": forged_outputs,
        "tensorRoundTripVerified": True,
        "trainingPerformed": False,
    }
    (root / "conversion.json").write_text(json.dumps(conversion))
    forged_profile = {
        **profile,
        "conversion_sha256": sha256_file(root / "conversion.json"),
    }
    monkeypatch.setattr(catalog, "qualified_profile", lambda requested: forged_profile if requested == name else profile)
    monkeypatch.setattr(
        catalog,
        "build_manifest_from_snapshot",
        lambda *_a, **_k: pytest.fail("untrusted output map must fail before manifest construction"),
    )
    with pytest.raises(UnavailableModelError, match="qualified source artifact"):
        load_model(f"{name}-mlx")


@pytest.mark.parametrize("name", ["starcoderbase", "octocoder"])
def test_qualified_conversion_detects_replacement_before_manifest_capture(monkeypatch, tmp_path, name):
    monkeypatch.setattr(catalog, "models_dir", lambda: tmp_path)
    monkeypatch.setattr(catalog, "_mlx_runtime_version", lambda: "test-runtime")
    profile = catalog.qualified_profile(name)
    root = tmp_path / "qualified" / f"{name}-fp16" / profile["revision"]
    root.mkdir(parents=True)
    for index in range(1, 8):
        (root / f"model-{index:05d}-of-00007.safetensors").write_bytes(b"synthetic-test-weights")
    (root / "config.json").write_text('{"n_positions":8192}')
    (root / "tokenizer.json").write_text("{}")
    weight_map = {f"tensor.{i}": f"model-{i:05d}-of-00007.safetensors" for i in range(1, 8)}
    (root / "model.safetensors.index.json").write_text(json.dumps({"weight_map": weight_map}))
    output_files = {path.name: sha256_file(path) for path in root.iterdir()}
    conversion = {
        "sourceRepo": profile["repo"],
        "sourceRevision": profile["revision"],
        "operation": profile["operation"],
        "sourceWeightsSha256": profile["weights"],
        "outputFilesSha256": output_files,
        "tensorRoundTripVerified": True,
        "trainingPerformed": False,
    }
    (root / "conversion.json").write_text(json.dumps(conversion))
    trusted_profile = {
        **profile,
        "conversion_sha256": sha256_file(root / "conversion.json"),
        "output_files": output_files,
    }
    monkeypatch.setattr(catalog, "qualified_profile", lambda requested: trusted_profile if requested == name else profile)
    real_builder = catalog.build_manifest_from_snapshot

    def replace_then_build(*args, **kwargs):
        (root / "conversion.json").write_text(json.dumps({**conversion, "trainingPerformed": True}))
        return real_builder(*args, **kwargs)

    monkeypatch.setattr(catalog, "build_manifest_from_snapshot", replace_then_build)
    with pytest.raises(UnavailableModelError, match="changed during verification"):
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
