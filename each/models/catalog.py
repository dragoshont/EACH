"""A small, explicit catalog of local models evaluated for M2.

No plugin framework: a model is "available" only if its lawful weights are
already present on disk and its runtime can actually load them on this
Apple Silicon host, and "unavailable" is recorded with the concrete reason
(missing download, unverifiable conversion provenance, or no implemented
adapter) rather than silently omitted.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from importlib.metadata import PackageNotFoundError, version

from each.model_manifest import build_manifest_from_snapshot
from each.models.base import RepairModel
from each.paths import assert_no_symlink_escape, models_dir

HF_CACHE_DIR = models_dir() / ".hf_cache"
STARCODERBASE_REVISION = "88ec5781ad071a9d9e925cd28f327dea22eb5188"
STARCODERBASE_SOURCE_WEIGHTS = {
    "pytorch_model-00001-of-00007.bin": "dfde5c06da1a9b64727a04b1dd6b2414ead32b8513cef9b54eb12c6ba82b6c86",
    "pytorch_model-00002-of-00007.bin": "437479f655b31775554991fdabec6472244d334354ee03aea3a4c20b5d0b819b",
    "pytorch_model-00003-of-00007.bin": "a27c41541d9584e63f8bf5da6d493c053157b75e69d10928dff5ded809b16604",
    "pytorch_model-00004-of-00007.bin": "f4c16714179039c91190a9bec5935d7c25f7053d0423e3173257163fce16346f",
    "pytorch_model-00005-of-00007.bin": "fdaf103942e2a0757e576c2d64811b7a9f9c093f77bbfb7635235eeca7ece52b",
    "pytorch_model-00006-of-00007.bin": "aa2f8410b362aad53a0dea6511fac7460fd2e64a3c0bbe2c142324ed15587f1a",
    "pytorch_model-00007-of-00007.bin": "a0a6a38cfae8b0418e8b79ec30b6e14a0dfdd24a8237c238e98c80da6f3f5d1c",
}
STARCODERBASE_LINEAGE = {
    "status": "ELIGIBLE",
    "scope": "documented-inspectable-training-dataset-lineage",
    "modelRepo": "bigcode/starcoderbase",
    "modelRevision": STARCODERBASE_REVISION,
    "datasetRepo": "bigcode/starcoderdata",
    "datasetRevision": "9fc30b578cedaec69e47302df72cf00feed7c8c4",
    "releaseDatasetRevision": "771a4a11d98f975ff1a8d5f29206f4ef57fd25d3",
    "datasetManifestSha256": "3636743c1f4356db564aa82f6379e0e9b59fed59f0e53faf9edac6c1fece7a34",
    "inspectionEvidenceSha256": "45e9fee3103c406069c0d2f752082c5d7b0fce102b904eae0a745c417a004cbd",
    "postTraining": "NONE_FOR_SELECTED_BASE_RELEASE",
    "postTrainingEvidence": "https://arxiv.org/html/2305.06161v2",
    "dossier": "docs/model-qualifications/starcoderbase.md",
    "limitations": [
        "Dataset lineage, not exhaustive per-record original-source attribution.",
        "Processed issue/commit records omit separate repository/license columns.",
        "No legal, originality, memorization or repair-correctness guarantee.",
    ],
}


class UnavailableModelError(RuntimeError):
    """Raised with the exact, honest reason a catalog entry cannot be used."""


def _mlx_runtime_version() -> str:
    try:
        return version("mlx-lm")
    except PackageNotFoundError as exc:
        raise UnavailableModelError("MLX-LM is not installed; run uv sync --extra models") from exc


def _starcoderbase_mlx(*, max_tokens: int = 512) -> RepairModel:
    snapshot_dir = models_dir() / "qualified" / "starcoderbase-fp16" / STARCODERBASE_REVISION
    assert_no_symlink_escape(snapshot_dir, label="qualified model artifact")
    conversion_path = snapshot_dir / "conversion.json"
    if not conversion_path.is_file():
        raise UnavailableModelError("qualified StarCoderBase artifact is not provisioned; conversion provenance required")
    import json

    try:
        conversion = json.loads(conversion_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UnavailableModelError("StarCoderBase conversion record is unreadable") from exc
    if (
        not isinstance(conversion, dict)
        or conversion.get("sourceRepo") != "bigcode/starcoderbase"
        or conversion.get("sourceRevision") != STARCODERBASE_REVISION
        or conversion.get("operation") != "pytorch-fp32-to-safetensors-fp16"
        or conversion.get("sourceWeightsSha256") != STARCODERBASE_SOURCE_WEIGHTS
        or not isinstance(conversion.get("outputFilesSha256"), dict)
        or conversion.get("tensorRoundTripVerified") is not True
        or conversion.get("trainingPerformed") is not False
    ):
        raise UnavailableModelError("StarCoderBase conversion does not match its qualified source artifact")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="bigcode/starcoderbase",
        license="bigcode-openrail-m",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        conversion_chain="original publisher FP32 PyTorch -> local FP16 safetensors; retained conversion.json",
    )
    for name, expected in conversion["outputFilesSha256"].items():
        if manifest.files_sha256.get(name) != expected:
            raise UnavailableModelError("qualified StarCoderBase converted artifact has changed")
    if set(manifest.files_sha256) - {"conversion.json"} != set(conversion["outputFilesSha256"]):
        raise UnavailableModelError("qualified StarCoderBase conversion does not cover every output artifact")
    expected_weights = {
        f"model-{index:05d}-of-00007.safetensors"
        for index in range(1, 8)
    }
    if set(manifest.weights_sha256) != expected_weights or not expected_weights.issubset(conversion["outputFilesSha256"]):
        raise UnavailableModelError("qualified StarCoderBase conversion must bind all seven output weight shards")
    manifest = replace(manifest, training_data_provenance=dict(STARCODERBASE_LINEAGE))
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(
        snapshot_dir, manifest, max_tokens=max_tokens,
        model_config={"tie_word_embeddings": False},
    )


def _granite_3b_code_base_mlx() -> RepairModel:
    snapshot_dir = (
        HF_CACHE_DIR
        / "hub"
        / "models--mlx-community--granite-3b-code-base-4bit"
        / "snapshots"
        / "f55bfe8cccff2ac0285f3d5ad45ab63495a0896e"
    )
    if not snapshot_dir.exists():
        raise UnavailableModelError(f"snapshot not downloaded: {snapshot_dir}")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="mlx-community/granite-3b-code-base-4bit",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        # Verbatim provenance statement from the model card at this exact
        # snapshot (README.md in snapshot_dir), not an assumed chain: "The
        # Model mlx-community/granite-3b-code-base-4bit was converted to
        # MLX format from ibm-granite/granite-3b-code-base using mlx-lm
        # version 0.12.0."
        conversion_chain=(
            "ibm-granite/granite-3b-code-base -> mlx-community/granite-3b-code-base-4bit "
            "via mlx_lm.convert (4-bit, group_size=64), per the model card's own "
            "conversion statement (mlx-lm 0.12.0)"
        ),
    )
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest)


def _granite_3_3_8b_instruct_mlx(*, max_tokens: int = 2048) -> RepairModel:
    snapshot_dir = (
        HF_CACHE_DIR
        / "models--ibm-granite--granite-3.3-8b-instruct"
        / "snapshots"
        / "51dd4bc2ade4059a6bd87649d68aa11e4fb2529b"
    )
    if not snapshot_dir.exists():
        raise UnavailableModelError(f"snapshot not downloaded: {snapshot_dir}")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="ibm-granite/granite-3.3-8b-instruct",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        # ORIGINAL publisher weights (ibm-granite's own repo, bf16
        # safetensors), not a third-party community re-conversion: no
        # conversion chain applies. config.json declares
        # architectures=["GraniteForCausalLM"]/model_type="granite" (a
        # modern, non-deprecated Granite generation, distinct from the
        # gpt_bigcode-family 8B/20B/34B code-instruct checkpoints already
        # catalogued); mlx_lm.utils._get_classes(config) was verified to
        # resolve this to mlx_lm.models.granite.{Model,ModelArgs} before
        # this snapshot was loaded.
        conversion_chain="none; original ibm-granite publisher bf16 safetensors loaded directly via mlx_lm",
    )
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest, max_tokens=max_tokens)


def _qwen2_5_coder_14b_instruct_mlx(*, max_tokens: int = 2048) -> RepairModel:
    snapshot_dir = (
        HF_CACHE_DIR
        / "models--Qwen--Qwen2.5-Coder-14B-Instruct"
        / "snapshots"
        / "aedcc2d42b622764e023cf882b6652e646b95671"
    )
    if not snapshot_dir.exists():
        raise UnavailableModelError(f"snapshot not downloaded: {snapshot_dir}")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="Qwen/Qwen2.5-Coder-14B-Instruct",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        # ORIGINAL Qwen publisher weights (Qwen/Qwen2.5-Coder-14B-Instruct's
        # own repo, bf16 safetensors, LICENSE file present in the snapshot),
        # not a third-party community re-conversion: no conversion chain
        # applies. config.json declares model_type="qwen2"; verified
        # mlx_lm.utils._get_classes(config) resolves this to
        # mlx_lm.models.qwen2.{Model,ModelArgs} before this snapshot was
        # loaded. A pragmatic fallback candidate (not a pure-capacity
        # escalation) justified only after the newer, non-deprecated
        # granite-3.3-8b-instruct also failed to produce a verified repair.
        conversion_chain="none; original Qwen publisher bf16 safetensors loaded directly via mlx_lm",
    )
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest, max_tokens=max_tokens)


def _granite_8b_code_instruct_128k_mlx(*, max_tokens: int = 512) -> RepairModel:
    snapshot_dir = (
        HF_CACHE_DIR
        / "models--ibm-granite--granite-8b-code-instruct-128k"
        / "snapshots"
        / "bed93d8de15bb9bb55cb1da10ae860e2883f4254"
    )
    if not snapshot_dir.exists():
        raise UnavailableModelError(f"snapshot not downloaded: {snapshot_dir}")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="ibm-granite/granite-8b-code-instruct-128k",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        # These are the ORIGINAL publisher weights (ibm-granite's own repo,
        # bf16 safetensors), not a third-party community re-conversion: no
        # conversion chain applies. mlx_lm.utils._get_classes(config) was
        # verified to resolve this config's declared
        # architectures=["LlamaForCausalLM"]/model_type="llama" to
        # mlx_lm.models.llama.{Model,ModelArgs} before this snapshot was
        # loaded, and mlx_lm.load() loads the original safetensors directly
        # (mlx_lm's Llama-family loader sanitizes/accepts the standard HF
        # safetensors key layout; no separate mlx-community conversion
        # artifact was produced or required).
        conversion_chain="none; original ibm-granite publisher bf16 safetensors loaded directly via mlx_lm",
    )
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest, max_tokens=max_tokens)


def _granite_20b_code_instruct_mlx(*, max_tokens: int = 2048) -> RepairModel:
    snapshot_dir = (
        HF_CACHE_DIR
        / "models--ibm-granite--granite-20b-code-instruct"
        / "snapshots"
        / "03d2f3664ed0059eac4d35797b43fb52d551bb5b"
    )
    if not snapshot_dir.exists():
        raise UnavailableModelError(f"snapshot not downloaded: {snapshot_dir}")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="ibm-granite/granite-20b-code-instruct",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        # ORIGINAL publisher weights (ibm-granite's own repo, bf16
        # safetensors), not a third-party community re-conversion: no
        # conversion chain applies. config.json declares
        # architectures=["GPTBigCodeForCausalLM"]/model_type="gpt_bigcode";
        # mlx_lm.utils._get_classes(config) was verified to resolve this to
        # mlx_lm.models.gpt_bigcode.{Model,ModelArgs} before this snapshot
        # was loaded.
        conversion_chain="none; original ibm-granite publisher bf16 safetensors loaded directly via mlx_lm",
    )
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest, max_tokens=max_tokens)


def _granite_34b_code_instruct_mlx(*, max_tokens: int = 2048) -> RepairModel:
    snapshot_dir = (
        HF_CACHE_DIR
        / "models--ibm-granite--granite-34b-code-instruct"
        / "snapshots"
        / "4bdfb589ebd261be0942a00dd239175d9d65bc47"
    )
    if not snapshot_dir.exists():
        raise UnavailableModelError(f"snapshot not downloaded: {snapshot_dir}")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="ibm-granite/granite-34b-code-instruct",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        # ORIGINAL publisher weights (ibm-granite's own repo, bf16
        # safetensors), not a third-party community re-conversion: no
        # conversion chain applies. config.json declares
        # architectures=["GPTBigCodeForCausalLM"]/model_type="gpt_bigcode"
        # (same family as the 20B sibling); mlx_lm.utils._get_classes(config)
        # was verified to resolve this to mlx_lm.models.gpt_bigcode.{Model,
        # ModelArgs} before this snapshot was loaded.
        conversion_chain="none; original ibm-granite publisher bf16 safetensors loaded directly via mlx_lm",
    )
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest, max_tokens=max_tokens)


def _granite_3b_code_instruct_mlx() -> RepairModel:
    snapshot_dir = (
        HF_CACHE_DIR
        / "hub"
        / "models--mlx-community--granite-3b-code-instruct-4bit"
        / "snapshots"
        / "1fe6b1a221a5a79606e7a94604bb1ea5cc512ff0"
    )
    if not snapshot_dir.exists():
        raise UnavailableModelError(f"snapshot not downloaded: {snapshot_dir}")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="mlx-community/granite-3b-code-instruct-4bit",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        conversion_chain=(
            "ibm-granite/granite-3b-code-instruct -> mlx-community/granite-3b-code-instruct-4bit "
            "via mlx_lm.convert (4-bit, group_size=64), per the model card's own "
            "conversion statement (mlx-lm 0.12.0)"
        ),
    )
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest)


def _octocoder_transformers_mps() -> RepairModel:
    weights_dir = models_dir() / "bigcode--octocoder"
    index_path = weights_dir / "model.safetensors.index.json"
    if not index_path.exists():
        raise UnavailableModelError(f"weights not downloaded: {weights_dir}")
    import json

    shard_names = sorted(set(json.loads(index_path.read_text())["weight_map"].values()))
    missing = [name for name in shard_names if not (weights_dir / name).exists()]
    if missing:
        raise UnavailableModelError(
            f"download incomplete: {len(missing)}/{len(shard_names)} safetensors shard(s) missing "
            f"({', '.join(missing)}); resume with huggingface_hub.snapshot_download"
        )
    raise UnavailableModelError(
        "no Transformers/MPS RepairModel adapter is implemented yet for OctoCoder "
        "(15.5B dense StarCoder-family); MLX-LM was selected as the initial M2 "
        "Builder backend instead (see docs/EACH_BOOTSTRAP_MANDATE.md M2 evidence)"
    )


def _granite_gguf_llamacpp() -> RepairModel:
    raise UnavailableModelError(
        "no llama.cpp/GGUF conversion with recorded provenance exists for any M2 "
        "candidate model; the mandate requires a recorded conversion chain before "
        "using a converted GGUF artifact, and none was produced or verified"
    )


_CATALOG: dict[str, Callable[..., RepairModel]] = {
    "starcoderbase-mlx": _starcoderbase_mlx,
    "granite-3b-code-base-mlx": _granite_3b_code_base_mlx,
    "granite-3b-code-instruct-mlx": _granite_3b_code_instruct_mlx,
    "granite-8b-code-instruct-128k-mlx": _granite_8b_code_instruct_128k_mlx,
    "granite-3.3-8b-instruct-mlx": _granite_3_3_8b_instruct_mlx,
    "qwen2.5-coder-14b-instruct-mlx": _qwen2_5_coder_14b_instruct_mlx,
    "granite-20b-code-instruct-mlx": _granite_20b_code_instruct_mlx,
    "granite-34b-code-instruct-mlx": _granite_34b_code_instruct_mlx,
    "octocoder-transformers-mps": _octocoder_transformers_mps,
    "granite-gguf-llamacpp": _granite_gguf_llamacpp,
}


def load_model(key: str, **kwargs) -> RepairModel:
    """Load only an explicitly qualified model; all other entries fail closed.

    Historical builders remain for adapter tests and receipt interpretation;
    their availability is not permission to use them for new target generation.
    """
    if key not in _CATALOG:
        raise UnavailableModelError(f"unknown model key: {key!r}; known keys: {sorted(_CATALOG)}")
    if key == "starcoderbase-mlx":
        return _CATALOG[key](**kwargs)
    raise UnavailableModelError(
        f"training-data provenance is not qualified for {key!r}; "
        "public weights, artifact hashes and a model license are insufficient. "
        "EACH requires reviewed base-training and post-training dataset lineage "
        "before target generation. This catalog entry has no such qualification."
    )
