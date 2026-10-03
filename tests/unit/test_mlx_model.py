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
    # Real complete() only imports mlx.core (to seed sampling) when a seed
    # was actually configured; stub it the same way as mlx_lm above so
    # these tests stay fast/hermetic and do not require the optional
    # 'models' extra's real mlx package to be installed.
    mlx_pkg = ModuleType("mlx")
    mlx_core = ModuleType("mlx.core")
    mlx_core.random = ModuleType("mlx.core.random")
    mlx_core.random.seed = lambda seed: None
    mlx_pkg.core = mlx_core
    monkeypatch.setitem(sys.modules, "mlx", mlx_pkg)
    monkeypatch.setitem(sys.modules, "mlx.core", mlx_core)
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


def test_lazy_load_refuses_a_shard_added_after_manifest_creation(tmp_path, monkeypatch):
    root = _snapshot(tmp_path, max_position_embeddings=8192)
    manifest = build_manifest_from_snapshot(
        root, repo_id="fixture/model", license="Apache-2.0",
        runtime_name="fixture", runtime_version="1", conversion_chain="fixture",
    )
    model = MLXRepairModel(root, manifest)
    (root / "extra.safetensors").write_bytes(b"unrecorded fixture weights")
    monkeypatch.setattr("mlx_lm.load", lambda *args: pytest.fail("backend load must not run"), raising=False)
    with pytest.raises(RuntimeError, match="unrecorded file"):
        model._ensure_loaded()


def test_runtime_model_configuration_is_applied_and_recorded(tmp_path, monkeypatch):
    root = _snapshot(tmp_path, max_position_embeddings=8192)
    manifest = build_manifest_from_snapshot(
        root, repo_id="fixture/model", license="Apache-2.0",
        runtime_name="fixture", runtime_version="1", conversion_chain="fixture",
    )
    observed = []
    monkeypatch.setattr(
        "mlx_lm.load",
        lambda path, **kwargs: observed.append(kwargs) or (_FakeModel(), _FakeTokenizer()),
        raising=False,
    )
    model = MLXRepairModel(root, manifest, model_config={"tie_word_embeddings": False})
    model._ensure_loaded()
    assert observed == [{"model_config": {"tie_word_embeddings": False}}]
    assert model.identity()["runtimeModelConfig"] == {"tie_word_embeddings": False}


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


def test_question_answer_format_records_exact_backend_input(monkeypatch, tmp_path):
    model = _model(tmp_path, max_position_embeddings=2048, max_tokens=5, monkeypatch=monkeypatch)
    model._prompt_format = "question-answer"
    received = []
    monkeypatch.setattr("mlx_lm.generate", lambda *a, **k: received.append(k["prompt"]) or "fixture")
    model.complete("raw diff instruction")
    assert received == ["Question: raw diff instruction\n\nAnswer:"]
    assert model.last_prompt == received[0]
    assert model.last_raw_prompt == "raw diff instruction"
    assert model.identity()["promptFormat"] == "question-answer"


@pytest.mark.parametrize("failure", ["context", "render", "tokenize", "backend"])
def test_failed_call_does_not_inherit_previous_prompt_or_tokens(monkeypatch, tmp_path, failure):
    model = _model(tmp_path, max_position_embeddings=10, max_tokens=5, monkeypatch=monkeypatch)
    calls = []

    def generate(*args, **kwargs):
        calls.append(kwargs["prompt"])
        if len(calls) == 2:
            raise RuntimeError("fixture backend failure")
        return "fixture response"

    monkeypatch.setattr("mlx_lm.generate", generate)
    model.complete("first request")
    assert model.last_input_token_count == 2
    request = "second request has eight words and exceeds budget" if failure == "context" else "different next request"

    def fail(*args, **kwargs):
        raise RuntimeError(f"fixture {failure} failure")

    if failure == "render":
        monkeypatch.setattr(model, "_render_prompt", fail)
    elif failure == "tokenize":
        monkeypatch.setattr(_FakeTokenizer, "encode", fail)
    with pytest.raises(RuntimeError):
        model.complete(request)
    assert model.last_raw_prompt == request
    assert model.last_generation_attempted is (failure == "backend")
    assert len(calls) == (2 if failure == "backend" else 1)
    assert model.last_prompt == (None if failure == "render" else f"[rendered]{request}")
    expected_tokens = None if failure in {"render", "tokenize"} else len(request.split())
    assert model.identity()["contextPolicy"]["lastInputTokenCount"] == expected_tokens


@pytest.mark.parametrize("failure", ["context", "render", "backend"])
def test_bakeoff_retry_failure_records_only_current_request(monkeypatch, tmp_path, failure):
    import json

    from each import bakeoff
    from each.attestation import verify_materials_root, verify_receipt
    from each.executor.base import ExecutionResult
    from each.executor.container import NETWORK_PROBE_DENIAL_MARKER
    from each.signing import public_key_path

    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))
    base_prompt = bakeoff._PROMPT_TEMPLATE.format(
        problem="greet() returns 'Hell, <name>' instead of 'Hello, <name>'.",
        allowed_paths=bakeoff.FIXTURE_ALLOWED_PATHS,
        path=bakeoff.FIXTURE_ALLOWED_PATHS[0],
        source=bakeoff._BUG_SOURCE,
    )
    model = _model(
        tmp_path, max_position_embeddings=len(base_prompt.split()) + 5 if failure == "context" else 2048,
        max_tokens=5, monkeypatch=monkeypatch,
    )
    calls = []

    def fail_render(prompt):
        raise RuntimeError("fixture render failure")

    def generate(*args, **kwargs):
        calls.append(kwargs["prompt"])
        if failure == "render":
            monkeypatch.setattr(model, "_render_prompt", fail_render)
        if len(calls) == 2:
            raise RuntimeError("fixture backend failure")
        return "not a patch"

    monkeypatch.setattr("mlx_lm.generate", generate)
    monkeypatch.setattr(
        bakeoff.ContainerExecutor, "verify_isolation",
        lambda *a, **k: ExecutionResult(("python",), 1, NETWORK_PROBE_DENIAL_MARKER, ""),
    )
    monkeypatch.setattr(
        bakeoff.ContainerExecutor, "run",
        lambda *a, **k: ExecutionResult(("python",), 1, "Ran 1 test in 0.01s\n\nFAILED (failures=1)\n", ""),
    )
    result = bakeoff.run_model_bakeoff(model, max_attempts=2)
    path = Path(result["receipt_json"])
    receipt = json.loads(path.read_text())
    first, failed = receipt["attempts"]
    assert len(calls) == (2 if failure == "backend" else 1)
    assert failed["prompt"] != first["prompt"]
    assert failed["raw_request"] != first["raw_request"]
    assert failed["prompt"] == ("" if failure == "render" else f"[rendered]{failed['raw_request']}")
    assert failed["rendered_prompt_available"] is (failure != "render")
    assert failed["generation_attempted"] is (failure == "backend")
    assert failed["failureStage"] == ("generation" if failure == "backend" else "generation_preflight")
    assert failed["failureClassification"] == (
        "backend_generation_failed" if failure == "backend" else "generation_not_started"
    )
    assert failed["errorType"] == ("ContextBudgetExceeded" if failure == "context" else "RuntimeError")
    assert failed["raw_completion"] == ""
    tokens = failed["model_identity"]["contextPolicy"]["lastInputTokenCount"]
    assert tokens == (None if failure == "render" else len(failed["prompt"].split()))
    assert tokens != first["model_identity"]["contextPolicy"]["lastInputTokenCount"]
    assert receipt["prompt"] == failed["prompt"]
    assert receipt["modelIdentity"] == failed["model_identity"]
    assert verify_receipt(receipt, public_key_path().read_bytes())["status"] == "PASS"
    assert verify_materials_root(receipt, path.parent / "materials")["status"] == "PASS"


def test_default_sampling_identity_is_unchanged_greedy(monkeypatch, tmp_path) -> None:
    """Without ever calling configure_sampling, identity() reports exactly
    the same deterministic greedy defaults as before this feature existed
    -- no behavior change for a caller that never opts in."""
    model = _model(tmp_path, max_position_embeddings=2048, max_tokens=5, monkeypatch=monkeypatch)
    monkeypatch.setattr("mlx_lm.generate", lambda *a, **k: "canned output")
    monkeypatch.setattr("mlx_lm.sample_utils.make_sampler", lambda **k: None)
    model.complete("one two three")
    params = model.identity()["generationParameters"]
    assert params == {"maxTokens": 5, "temperature": 0.0, "sampling": "greedy", "seed": None}


def test_configure_sampling_is_reflected_in_the_next_completions_identity(monkeypatch, tmp_path) -> None:
    """A later retry attempt that opts into sampling diversity must see its
    ACTUAL parameters recorded in identity(), not a stale static claim."""
    model = _model(tmp_path, max_position_embeddings=2048, max_tokens=5, monkeypatch=monkeypatch)
    captured_sampler_temps: list[float] = []
    monkeypatch.setattr("mlx_lm.generate", lambda *a, **k: "canned output")
    monkeypatch.setattr(
        "mlx_lm.sample_utils.make_sampler", lambda **k: captured_sampler_temps.append(k["temp"]) or None
    )
    model.configure_sampling(temperature=0.2, seed=7)
    model.complete("one two three")
    params = model.identity()["generationParameters"]
    assert params == {"maxTokens": 5, "temperature": 0.2, "sampling": "temperature", "seed": 7}
    assert captured_sampler_temps == [0.2]


def test_configure_sampling_rejects_a_negative_temperature(monkeypatch, tmp_path) -> None:
    model = _model(tmp_path, max_position_embeddings=2048, max_tokens=5, monkeypatch=monkeypatch)
    with pytest.raises(ValueError, match="temperature"):
        model.configure_sampling(temperature=-0.1)


def test_base_repair_model_configure_sampling_defaults_to_a_no_op() -> None:
    """A RepairModel backend that never overrides configure_sampling (the
    abstract base's default implementation) must not break -- callers may
    call it unconditionally without checking backend capability."""
    from each.models.base import RepairModel

    class _Stub(RepairModel):
        model_id = "stub"

        def complete(self, prompt: str) -> str:
            return "stub completion"

    stub = _Stub()
    stub.configure_sampling(temperature=0.5, seed=3)  # must not raise
