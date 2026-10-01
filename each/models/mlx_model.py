"""A real, local, Apple-Silicon-native repair model backed by MLX-LM.

This adapter performs genuine on-device inference -- no network calls, no
outer/cloud substitution for the declared target model. Its ``model_id`` is
derived from a :class:`~each.model_manifest.ModelManifest`, so every patch
attempt's provenance is traceable to exact weight/tokenizer bytes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from each.model_manifest import ModelManifest
from each.models.base import RepairModel


class MLXRepairModel(RepairModel):
    """Wraps ``mlx_lm.load``/``generate`` for a locally downloaded model.

    Requires the optional ``models`` dependency group
    (``uv sync --extra models``); importing ``mlx_lm`` is deferred to
    ``__init__`` so the base install (and CI) never needs it.
    """

    def __init__(
        self,
        snapshot_dir: Path,
        manifest: ModelManifest,
        *,
        max_tokens: int = 512,
    ) -> None:
        try:
            import mlx_lm  # noqa: F401
        except ImportError as exc:  # pragma: no cover - exercised only with extras
            raise RuntimeError(
                "MLXRepairModel requires the optional 'models' dependency group: "
                "uv sync --extra models"
            ) from exc

        self._manifest = manifest
        self._max_tokens = max_tokens
        self._snapshot_dir = str(snapshot_dir)
        self._model = None
        self._tokenizer = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            import mlx_lm

            self._model, self._tokenizer = mlx_lm.load(self._snapshot_dir)

    @property
    def model_id(self) -> str:
        return self._manifest.model_id

    @property
    def manifest(self) -> ModelManifest:
        return self._manifest

    def identity(self) -> dict[str, Any]:
        """Includes the exact weight/tokenizer-hash manifest, not just the
        wrapper module's own source hash: the thing that actually determines
        a completion is the loaded weights, not just the adapter code.
        """
        identity = super().identity()
        identity["modelManifest"] = self._manifest.to_dict()
        return identity

    def complete(self, prompt: str) -> str:
        self._ensure_loaded()
        import mlx_lm

        final_prompt = prompt
        chat_template = getattr(self._tokenizer, "chat_template", None)
        if chat_template:
            # Instruction-tuned checkpoints (e.g. granite-*-instruct) expect
            # their own chat-template wrapping; a bare completion prompt is
            # otherwise read as code to continue, not an instruction to
            # follow. Base (non-instruct) tokenizers have no chat_template,
            # so this is a no-op for them.
            final_prompt = self._tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True
            )

        return mlx_lm.generate(
            self._model,
            self._tokenizer,
            prompt=final_prompt,
            max_tokens=self._max_tokens,
            verbose=False,
        )
