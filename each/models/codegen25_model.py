"""MLX adapter for CodeGen2.5 with a reviewed local tokenizer implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from each.model_manifest import ModelManifest, verify_snapshot_matches
from each.models.codegen25_tokenizer import CodeGen25Tokenizer
from each.models.mlx_model import MLXRepairModel
from each.paths import FileLock


class CodeGen25RepairModel(MLXRepairModel):
    """Load CodeGen2.5 without executing Hugging Face remote tokenizer code."""

    def __init__(
        self,
        snapshot_dir: Path,
        manifest: ModelManifest,
        *,
        max_tokens: int = 512,
        tokenizer_provenance: dict[str, Any],
    ) -> None:
        super().__init__(snapshot_dir, manifest, max_tokens=max_tokens)
        self._tokenizer_provenance = dict(tokenizer_provenance)

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        snapshot = Path(self._snapshot_dir)
        load_lock = snapshot.parent / f".{snapshot.name}.load.lock"
        with FileLock(load_lock):
            drift = verify_snapshot_matches(snapshot, self._manifest)
            if drift:
                raise RuntimeError(
                    "refusing to load: snapshot directory has drifted from its recorded "
                    f"manifest since provisioning ({'; '.join(drift)})"
                )
            from mlx_lm.tokenizer_utils import TokenizerWrapper
            from mlx_lm.utils import load_model

            model, _config = load_model(snapshot, lazy=True)
            tokenizer = TokenizerWrapper(CodeGen25Tokenizer())
            post_load_drift = verify_snapshot_matches(snapshot, self._manifest)
            if post_load_drift:
                raise RuntimeError(
                    "refusing loaded model: snapshot changed while the backend opened it "
                    f"({'; '.join(post_load_drift)})"
                )
            self._model, self._tokenizer = model, tokenizer

    def identity(self) -> dict[str, Any]:
        identity = super().identity()
        identity["tokenizerProvenance"] = dict(self._tokenizer_provenance)
        return identity
