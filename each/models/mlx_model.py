"""A real, local, Apple-Silicon-native repair model backed by MLX-LM.

This adapter performs genuine on-device inference -- no network calls, no
outer/cloud substitution for the declared target model. Its ``model_id`` is
derived from a :class:`~each.model_manifest.ModelManifest`, so every patch
attempt's provenance is traceable to exact weight/tokenizer bytes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from each.model_manifest import ModelManifest, verify_snapshot_matches
from each.models.base import ContextBudgetExceeded, RepairModel

__all__ = ["ContextBudgetExceeded", "MLXRepairModel"]


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
        model_config: dict[str, Any] | None = None,
    ) -> None:
        if max_tokens < 1:
            raise ValueError("max_tokens must be at least 1")
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
        self._model_config = dict(model_config) if model_config is not None else {}
        self._model = None
        self._tokenizer = None
        # last_prompt (inherited from RepairModel) is set to the exact
        # backend-encoded string after chat-template rendering -- that is
        # what callers (each.benchmark/each.bakeoff) record as a receipt's
        # "prompt" field, because that is what the model actually received.
        # last_raw_prompt keeps the pre-render controller request distinct,
        # so replaying a saved receipt's (already-rendered) prompt through
        # complete() is never silently double-wrapped by a second
        # chat-template application -- feed last_raw_prompt back, not the
        # receipt's rendered prompt field, when reproducing an attempt.
        self.last_raw_prompt: str | None = None
        self.last_input_token_count: int | None = None
        self._temperature = 0.0
        self._seed: int | None = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            drift = verify_snapshot_matches(Path(self._snapshot_dir), self._manifest)
            if drift:
                raise RuntimeError(
                    "refusing to load: snapshot directory has drifted from its recorded "
                    f"manifest since provisioning ({'; '.join(drift)})"
                )
            import mlx_lm

            self._model, self._tokenizer = mlx_lm.load(
                self._snapshot_dir, **({"model_config": self._model_config} if self._model_config else {})
            )

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
        identity["generationParameters"] = {
            "maxTokens": self._max_tokens,
            "temperature": self._temperature,
            "sampling": "greedy" if self._temperature == 0.0 else "temperature",
            "seed": self._seed,
        }
        identity["contextPolicy"] = {
            "maxPositionEmbeddings": self._manifest.max_position_embeddings,
            "reservedOutputTokens": self._max_tokens,
            "lastInputTokenCount": self.last_input_token_count,
        }
        if self._model_config:
            identity["runtimeModelConfig"] = dict(self._model_config)
        return identity

    def _render_prompt(self, prompt: str) -> str:
        self._ensure_loaded()
        chat_template = getattr(self._tokenizer, "chat_template", None)
        if chat_template:
            # Instruction-tuned checkpoints (e.g. granite-*-instruct) expect
            # their own chat-template wrapping; a bare completion prompt is
            # otherwise read as code to continue, not an instruction to
            # follow. Base (non-instruct) tokenizers have no chat_template,
            # so this is a no-op for them.
            return self._tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True
            )
        return prompt

    def check_context_budget(self, prompt: str) -> tuple[str, int]:
        """Render ``prompt`` and verify it fits this checkpoint's declared
        context window before any generation is attempted.

        Returns ``(rendered_prompt, input_token_count)`` on success. Raises
        :class:`ContextBudgetExceeded` if ``input_token_count +
        reserved_output_tokens`` would exceed ``max_position_embeddings`` --
        never silently truncates the prompt or shrinks the output budget.
        If the checkpoint does not declare a limit, the check is skipped
        (recorded as ``None``, not assumed unlimited by a magic default).
        """
        rendered = self._render_prompt(prompt)
        self._ensure_loaded()
        input_token_count = len(self._tokenizer.encode(rendered))
        limit = self._manifest.max_position_embeddings
        if limit is not None and input_token_count + self._max_tokens > limit:
            raise ContextBudgetExceeded(
                f"rendered prompt ({input_token_count} tokens) + reserved output "
                f"({self._max_tokens} tokens) = {input_token_count + self._max_tokens} tokens "
                f"exceeds this checkpoint's declared max_position_embeddings ({limit})"
            )
        return rendered, input_token_count

    def configure_sampling(self, *, temperature: float = 0.0, seed: int | None = None) -> None:
        """Record the decoding parameters the NEXT ``complete()`` call should
        use (reported verbatim in ``identity()`` so a receipt's per-attempt
        provenance always matches what was actually sampled). A bounded
        retry loop passing a small nonzero temperature with a distinct
        recorded seed on later attempts gives genuine exploratory value to
        its attempt budget -- pure temp=0.0 greedy decoding reproduces
        nearly the same completion regardless of a short trailing retry
        instruction, since the much larger shared prompt prefix dominates
        the argmax choice at every step.
        """
        if temperature < 0.0:
            raise ValueError(f"temperature must be >= 0.0, got {temperature}")
        self._temperature = temperature
        self._seed = seed

    def complete(self, prompt: str) -> str:
        rendered, input_token_count = self.check_context_budget(prompt)
        import mlx_lm
        from mlx_lm.sample_utils import make_sampler

        self.last_raw_prompt = prompt
        self.last_prompt = rendered
        self.last_input_token_count = input_token_count
        if self._seed is not None:
            import mlx.core as mx

            mx.random.seed(self._seed)
        return mlx_lm.generate(
            self._model,
            self._tokenizer,
            prompt=rendered,
            max_tokens=self._max_tokens,
            sampler=make_sampler(temp=self._temperature),
            verbose=False,
        )
