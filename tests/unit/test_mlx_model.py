"""Unit coverage for MLXRepairModel's pre-generation context-budget policy.

Uses a real ModelManifest (hashed from a small synthetic snapshot directory,
same fixture pattern as tests/unit/test_model_manifest.py) but stubs
mlx_lm.load/generate with a tiny deterministic fake tokenizer/model, so these
tests run fast and hermetically without downloading real weights. The real
end-to-end inference path is already covered by the Colima-gated adversarial
bake-off/benchmark tests, which load actual local model weights.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from each.model_manifest import build_manifest_from_snapshot
from each.models.mlx_model import ContextBudgetExceeded, MLXRepairModel


@pytest.fixture(autouse=True)
def _stub_optional_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = ModuleType("mlx_lm")
    backend.generate = lambda *args, **kwargs: "fixture output"
    sampling = ModuleType("mlx_lm.sample_utils")
    sampling.make_sampler = lambda **kwargs: None
    backend.sample_utils = sampling
    monkeypatch.setitem(sys.modules, "mlx_lm", backend)
    monkeypatch.setitem(sys.modules, "mlx_lm.sample_utils", sampling)


def _snapshot(tmp_path: Path, *, max_position_embeddings: int | None) -> Path:
    root = tmp_path.joinpath("a" * 40)
    root.mkdir()
    root.joinpath("model.safetensors").write_bytes(b"fixture weights")
    root.joinpath("tokenizer.json").write_text("{}")
    config = {"quantization": {"bits": 4}}
    if max_position_embeddings is not None:
        config["max_position_embeddings"] = max_position_embeddings
    root.joinpath("config.json").write_text(__import__("json").dumps(config))
    return root


class _FakeTokenizer:
    """One token per whitespace-separated word -- deterministic and exact
    enough to test the budget arithmetic without a real tokenizer."""

    chat_template = "{{ messages }}"

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        del tokenize, add_generation_prompt
        return f"[rendered]{messages[0]['content']}"

    def encode(self, text: str) -> list[int]:
        return text.split()


class _FakeModel:
    pass


def _model(tmp_path: Path, *, max_position_embeddings: int | None, max_tokens: int = 10, monkeypatch) -> MLXRepairModel:
    root = _snapshot(tmp_path, max_position_embeddings=max_position_embeddings)
    manifest = build_manifest_from_snapshot(
        root, repo_id="fixture/model", license="Apache-2.0", runtime_name="fixture", runtime_version="1",
        conversion_chain="fixture",
    )
    model = MLXRepairModel(root, manifest, max_tokens=max_tokens)
    monkeypatch.setattr(model, "_ensure_loaded", lambda: setattr(model, "_tokenizer", _FakeTokenizer()))
    return model


def test_context_budget_passes_when_prompt_and_output_fit(monkeypatch, tmp_path) -> None:
    model = _model(tmp_path, max_position_embeddings=20, max_tokens=5, monkeypatch=monkeypatch)
    rendered, count = model.check_context_budget("one two three")
    assert rendered == "[rendered]one two three"
    assert count == len(rendered.split())  # 4 words -> 4 tokens via the fake tokenizer


def test_context_budget_rejects_before_any_generation_call(monkeypatch, tmp_path) -> None:
    model = _model(tmp_path, max_position_embeddings=10, max_tokens=5, monkeypatch=monkeypatch)
    # 8 words after rendering + 5 reserved output = 13 > 10 declared limit.
    long_prompt = " ".join(f"word{i}" for i in range(7))
    generate_calls = []
    monkeypatch.setattr("mlx_lm.generate", lambda *a, **k: generate_calls.append(1) or "unused")
    with pytest.raises(ContextBudgetExceeded, match="exceeds this checkpoint's declared max_position_embeddings"):
        model.complete(long_prompt)
    assert generate_calls == []  # generation must never be attempted


def test_context_budget_is_skipped_honestly_when_limit_is_undeclared(monkeypatch, tmp_path) -> None:
    model = _model(tmp_path, max_position_embeddings=None, max_tokens=5, monkeypatch=monkeypatch)
    long_prompt = " ".join(f"word{i}" for i in range(500))
    # No exception: an undeclared limit is recorded as None, never assumed
    # to be some default cap.
    _rendered, count = model.check_context_budget(long_prompt)
    assert count == 500


def test_identity_records_actual_token_counts_and_policy(monkeypatch, tmp_path) -> None:
    model = _model(tmp_path, max_position_embeddings=2048, max_tokens=5, monkeypatch=monkeypatch)
    monkeypatch.setattr("mlx_lm.generate", lambda *a, **k: "canned output")
    monkeypatch.setattr("mlx_lm.sample_utils.make_sampler", lambda **k: None)
    model.complete("one two three")
    identity = model.identity()
    assert identity["contextPolicy"]["maxPositionEmbeddings"] == 2048
    assert identity["contextPolicy"]["reservedOutputTokens"] == 5
    assert identity["contextPolicy"]["lastInputTokenCount"] == 3


def test_raw_and_rendered_prompts_are_recorded_distinctly(monkeypatch, tmp_path) -> None:
    model = _model(tmp_path, max_position_embeddings=2048, max_tokens=5, monkeypatch=monkeypatch)
    monkeypatch.setattr("mlx_lm.generate", lambda *a, **k: "canned output")
    monkeypatch.setattr("mlx_lm.sample_utils.make_sampler", lambda **k: None)
    model.complete("raw request")
    assert model.last_raw_prompt == "raw request"
    assert model.last_prompt == "[rendered]raw request"
    assert model.last_raw_prompt != model.last_prompt
