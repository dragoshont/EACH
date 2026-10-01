"""Exact model-artifact identity: the provenance manifest for a local model
used to propose a repair.

EACH must record *which exact bytes* produced a patch, not merely a
human-readable model name. This module hashes the real on-disk weight and
tokenizer files (not Hugging Face cache "blob" filenames, which are only a
content hash for LFS-tracked files and a git SHA-1 for everything else --
verified empirically against both file kinds before writing this code).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ModelManifest:
    """The exact, recorded identity of a local model artifact."""

    repo_id: str
    revision: str
    license: str
    runtime_name: str
    runtime_version: str
    quantization: dict[str, Any]
    weights_sha256: dict[str, str]
    tokenizer_sha256: str
    conversion_chain: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "repoId": self.repo_id,
            "revision": self.revision,
            "license": self.license,
            "runtime": {"name": self.runtime_name, "version": self.runtime_version},
            "quantization": self.quantization,
            "weightsSha256": self.weights_sha256,
            "tokenizerSha256": self.tokenizer_sha256,
            "conversionChain": self.conversion_chain,
        }

    @property
    def model_id(self) -> str:
        """A stable provenance identifier: ``repo@revision#sha256:<digest>``
        where ``<digest>`` folds in every weight-file hash (order-independent),
        so two snapshots with identical bytes always yield the identical id
        and any single changed byte changes it.
        """
        combined = "".join(sorted(self.weights_sha256.values()))
        folded = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]
        return f"{self.repo_id}@{self.revision}#sha256:{folded}"


def build_manifest_from_snapshot(
    snapshot_dir: Path,
    *,
    repo_id: str,
    license: str,
    runtime_name: str,
    runtime_version: str,
    conversion_chain: str,
) -> ModelManifest:
    """Build a manifest from a real local Hugging Face snapshot directory.

    ``snapshot_dir`` must be the ``snapshots/<revision>/`` directory produced
    by ``huggingface_hub.snapshot_download``; its name is the exact resolved
    git commit revision of the downloaded repo.
    """
    snapshot_dir = snapshot_dir.resolve()
    revision = snapshot_dir.name

    weights: dict[str, str] = {}
    tokenizer_sha256 = ""
    for entry in sorted(snapshot_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix == ".safetensors":
            weights[entry.name] = _sha256_file(entry)
        elif entry.name == "tokenizer.json":
            tokenizer_sha256 = _sha256_file(entry)

    if not weights:
        raise ValueError(f"no .safetensors weight files found under {snapshot_dir}")
    if not tokenizer_sha256:
        raise ValueError(f"no tokenizer.json found under {snapshot_dir}")

    quantization: dict[str, Any] = {}
    config_path = snapshot_dir / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        quantization = config.get("quantization", {})

    return ModelManifest(
        repo_id=repo_id,
        revision=revision,
        license=license,
        runtime_name=runtime_name,
        runtime_version=runtime_version,
        quantization=quantization,
        weights_sha256=weights,
        tokenizer_sha256=tokenizer_sha256,
        conversion_chain=conversion_chain,
    )
