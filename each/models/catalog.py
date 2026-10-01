"""A small, explicit catalog of local models evaluated for M2.

No plugin framework: a model is "available" only if its lawful weights are
already present on disk and its runtime can actually load them on this
Apple Silicon host, and "unavailable" is recorded with the concrete reason
(missing download, unverifiable conversion provenance, or no implemented
adapter) rather than silently omitted.
"""

from __future__ import annotations

from collections.abc import Callable

from each.model_manifest import build_manifest_from_snapshot
from each.models.base import RepairModel
from each.paths import models_dir

HF_CACHE_DIR = models_dir() / ".hf_cache"


class UnavailableModelError(RuntimeError):
    """Raised with the exact, honest reason a catalog entry cannot be used."""


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
        runtime_version="0.32.0",
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
        runtime_version="0.32.0",
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


_CATALOG: dict[str, Callable[[], RepairModel]] = {
    "granite-3b-code-base-mlx": _granite_3b_code_base_mlx,
    "granite-3b-code-instruct-mlx": _granite_3b_code_instruct_mlx,
    "octocoder-transformers-mps": _octocoder_transformers_mps,
    "granite-gguf-llamacpp": _granite_gguf_llamacpp,
}


def load_model(key: str) -> RepairModel:
    """Instantiate a catalog entry, raising UnavailableModelError with the
    exact reason if it cannot actually be used right now."""
    try:
        builder = _CATALOG[key]
    except KeyError as exc:
        raise UnavailableModelError(f"unknown model key: {key!r}; known keys: {sorted(_CATALOG)}") from exc
    return builder()
