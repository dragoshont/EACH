"""A small, explicit catalog of local models evaluated for M2.

No plugin framework: a model is "available" only if its lawful weights are
already present on disk and its runtime can actually load them on this
Apple Silicon host, and "unavailable" is recorded with the concrete reason
(missing download, unverifiable conversion provenance, or no implemented
adapter) rather than silently omitted.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version

from each.model_manifest import build_manifest_from_snapshot
from each.models.base import RepairModel
from each.paths import models_dir

HF_CACHE_DIR = models_dir() / ".hf_cache"


class UnavailableModelError(RuntimeError):
    """Raised with the exact, honest reason a catalog entry cannot be used."""


def _mlx_runtime_version() -> str:
    try:
        return version("mlx-lm")
    except PackageNotFoundError as exc:
        raise UnavailableModelError("MLX-LM is not installed; run uv sync --extra models") from exc


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
    "granite-3b-code-base-mlx": _granite_3b_code_base_mlx,
    "granite-3b-code-instruct-mlx": _granite_3b_code_instruct_mlx,
    "granite-8b-code-instruct-128k-mlx": _granite_8b_code_instruct_128k_mlx,
    "granite-3.3-8b-instruct-mlx": _granite_3_3_8b_instruct_mlx,
    "granite-20b-code-instruct-mlx": _granite_20b_code_instruct_mlx,
    "granite-34b-code-instruct-mlx": _granite_34b_code_instruct_mlx,
    "octocoder-transformers-mps": _octocoder_transformers_mps,
    "granite-gguf-llamacpp": _granite_gguf_llamacpp,
}


def load_model(key: str, **kwargs) -> RepairModel:
    """Instantiate a catalog entry, raising UnavailableModelError with the
    exact reason if it cannot actually be used right now.

    ``kwargs`` (e.g. ``max_tokens``) are forwarded to the catalog entry's
    builder; entries that do not accept a given keyword raise a normal
    ``TypeError``, not a silently-ignored override.
    """
    try:
        builder = _CATALOG[key]
    except KeyError as exc:
        raise UnavailableModelError(f"unknown model key: {key!r}; known keys: {sorted(_CATALOG)}") from exc
    return builder(**kwargs)
