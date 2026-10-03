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

from each.hashing import sha256_json


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
    files_sha256: dict[str, str]
    max_position_embeddings: int | None
    training_data_provenance: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "schemaVersion": "0.1",
            "repoId": self.repo_id,
            "revision": self.revision,
            "license": self.license,
            "runtime": {"name": self.runtime_name, "version": self.runtime_version},
            "quantization": self.quantization,
            "weightsSha256": self.weights_sha256,
            "tokenizerSha256": self.tokenizer_sha256,
            "configSha256": self.files_sha256["config.json"],
            "filesSha256": self.files_sha256,
            "conversionChain": self.conversion_chain,
            "maxPositionEmbeddings": self.max_position_embeddings,
        }
        if self.training_data_provenance is not None:
            result["trainingDataProvenance"] = self.training_data_provenance
        return result

    @property
    def model_id(self) -> str:
        """A stable provenance identifier: ``repo@revision#sha256:<digest>``
        where ``<digest>`` folds in all artifact filenames and hashes,
        so any changed artifact changes the fingerprint. Repository and
        revision remain separate declared source identifiers.
        """
        folded = sha256_json(self.files_sha256)[:16]
        return f"{self.repo_id}@{self.revision}#sha256:{folded}"


def verify_snapshot_matches(snapshot_dir: Path, manifest: ModelManifest) -> list[str]:
    """Re-hash every file ``manifest.files_sha256`` declares and compare
    against ``snapshot_dir``'s real, current on-disk bytes.

    Returns the empty list if every declared file still exists with its
    originally recorded hash. Otherwise returns a sorted list of
    ``"<relative path>: <reason>"`` drift descriptions (missing file or hash
    mismatch) -- never raises itself, so a caller can log/record the exact
    drift before refusing to load. This closes the gap where a lazily
    loaded backend (e.g. ``MLXRepairModel._ensure_loaded``) would otherwise
    trust whatever bytes happen to be on disk at load time, never
    re-checking them against the manifest hashes a receipt actually claims.
    """
    snapshot_dir = snapshot_dir.resolve()
    drift: list[str] = []
    current_files = {
        path.relative_to(snapshot_dir).as_posix()
        for path in snapshot_dir.rglob("*")
        if path.is_file()
    }
    for relative_path in sorted(current_files - set(manifest.files_sha256)):
        drift.append(f"{relative_path}: unrecorded file")
    for relative_path, expected_hash in sorted(manifest.files_sha256.items()):
        candidate = snapshot_dir / relative_path
        if not candidate.is_file():
            drift.append(f"{relative_path}: missing")
            continue
        actual_hash = _sha256_file(candidate)
        if actual_hash != expected_hash:
            drift.append(f"{relative_path}: hash mismatch (expected {expected_hash}, got {actual_hash})")
    return drift


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
    files: dict[str, str] = {}
    for entry in sorted(snapshot_dir.rglob("*")):
        if not entry.is_file():
            continue
        relative_path = entry.relative_to(snapshot_dir).as_posix()
        files[relative_path] = _sha256_file(entry)
        if entry.suffix == ".safetensors":
            weights[relative_path] = files[relative_path]
        elif relative_path == "tokenizer.json":
            tokenizer_sha256 = files[relative_path]

    if not weights:
        raise ValueError(f"no .safetensors weight files found under {snapshot_dir}")
    if not tokenizer_sha256:
        raise ValueError(f"no tokenizer.json found under {snapshot_dir}")

    config_path = snapshot_dir / "config.json"
    if "config.json" not in files:
        raise ValueError(f"no config.json found under {snapshot_dir}")
    config = json.loads(config_path.read_text())
    quantization: dict[str, Any] = config.get("quantization", {})
    # The declared supported context window (mandate: never let a prompt
    # silently exceed what the checkpoint actually supports). Most HF
    # architectures declare this as "max_position_embeddings", but the
    # GPT-2/GPT-BigCode family (e.g. granite-20b-code-instruct's own
    # config.json: model_type="gpt_bigcode") uses "n_positions" for the
    # identical concept instead -- falling back to it here is reading the
    # same declared value under its real field name for that architecture,
    # not guessing a default. Honestly recorded as None only if the config
    # declares neither field.
    max_position_embeddings = config.get("max_position_embeddings")
    if max_position_embeddings is None:
        max_position_embeddings = config.get("n_positions")

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
        files_sha256=files,
        max_position_embeddings=max_position_embeddings,
    )
