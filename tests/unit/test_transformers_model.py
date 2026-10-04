from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from each.hashing import sha256_text_file_lf
from each.model_manifest import ModelManifest
from each.models.base import ContextBudgetExceeded
from each.models.transformers_model import TransformersRepairModel


def _model(tmp_path: Path) -> TransformersRepairModel:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "pyproject.toml").write_text("[project]\nname='test'\nversion='0'\n")
    (runtime / "uv.lock").write_text("version = 1\n")
    runtime_python = runtime / ".venv" / "bin" / "python"
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_text("fixture")
    (runtime / ".venv" / "lib" / "python3.12" / "site-packages").mkdir(parents=True)
    sandbox = tmp_path / "sandbox-exec"
    sandbox.write_text("fixture")
    helper = Path(__file__).parents[2] / "each" / "models" / "crystal_runtime.py"
    runtime_hashes = {
        "pyproject.toml": sha256_text_file_lf(runtime / "pyproject.toml"),
        "uv.lock": sha256_text_file_lf(runtime / "uv.lock"),
        "crystal_runtime.py": sha256_text_file_lf(helper),
    }
    manifest = ModelManifest(
        repo_id="publisher/model",
        revision="revision",
        license="Apache-2.0",
        runtime_name="transformers",
        runtime_version="4.44.2",
        quantization={},
        weights_sha256={"pytorch_model.bin": "weights"},
        tokenizer_sha256="tokenizer",
        conversion_chain="publisher bytes",
        files_sha256={"config.json": "config", "tokenizer.json": "tokenizer"},
        max_position_embeddings=2048,
    )
    return TransformersRepairModel(
        snapshot,
        manifest,
        max_tokens=128,
        device="cpu",
        runtime_project=runtime,
        runtime_files_sha256=runtime_hashes,
        runtime_versions={"python": "3.12.14", "torch": "2.14.1", "transformers": "4.44.2"},
        sandbox_executable=sandbox,
    )


def test_transformers_adapter_uses_locked_offline_subprocess(monkeypatch, tmp_path: Path) -> None:
    model = _model(tmp_path)
    monkeypatch.setattr("each.models.transformers_model.verify_snapshot_matches", lambda path, manifest: [])
    captured = {}

    def run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        probe_count = command.count("--probe-denied-path")
        return (
            0,
            json.dumps({
                "schemaVersion": "1",
                "status": "OK",
                "generationAttempted": True,
                "isolation": {
                    "networkDenied": True,
                    "privateFilesDenied": probe_count,
                    "outsideWriteDenied": True,
                },
                "runtime": {"python": "3.12.14", "torch": "2.14.1", "transformers": "4.44.2"},
                "inputTokenCount": 17,
                "completion": "body",
            }),
            "",
        )

    monkeypatch.setattr(model, "_run_subprocess", run)
    assert model.complete("prompt") == "body"
    assert str(model._runtime_python) in captured["command"]
    assert captured["kwargs"]["prompt"] == "prompt"
    assert captured["kwargs"]["environment"]["HF_HUB_OFFLINE"] == "1"
    assert "GITHUB_TOKEN" not in captured["kwargs"]["environment"]
    assert model.last_input_token_count == 17
    assert model.last_generation_attempted is True


def test_runtime_text_hash_is_checkout_line_ending_independent(tmp_path: Path) -> None:
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    lf.write_bytes(b"one\ntwo\n")
    crlf.write_bytes(b"one\r\ntwo\r\n")
    assert sha256_text_file_lf(lf) == sha256_text_file_lf(crlf)


def test_transformers_adapter_reports_pre_generation_context_rejection(
    monkeypatch, tmp_path: Path,
) -> None:
    model = _model(tmp_path)
    monkeypatch.setattr("each.models.transformers_model.verify_snapshot_matches", lambda path, manifest: [])
    def context_rejected(command, **kwargs):
        return (
            2,
            json.dumps({
                "schemaVersion": "1",
                "status": "CONTEXT_BUDGET_EXCEEDED",
                "generationAttempted": False,
                "isolation": {
                    "networkDenied": True,
                    "privateFilesDenied": command.count("--probe-denied-path"),
                    "outsideWriteDenied": True,
                },
                "runtime": {"python": "3.12.14", "torch": "2.14.1", "transformers": "4.44.2"},
                "inputTokenCount": 2000,
                "detail": "too large",
            }),
            "",
        )

    monkeypatch.setattr(model, "_run_subprocess", context_rejected)
    with pytest.raises(ContextBudgetExceeded, match="too large"):
        model.complete("prompt")
    assert model.last_input_token_count == 2000
    assert model.last_generation_attempted is False


def test_transformers_adapter_rejects_runtime_drift_before_launch(
    monkeypatch, tmp_path: Path,
) -> None:
    model = _model(tmp_path)
    monkeypatch.setattr("each.models.transformers_model.verify_snapshot_matches", lambda path, manifest: [])
    (model._runtime_project / "uv.lock").write_text("changed")
    monkeypatch.setattr(
        model,
        "_run_subprocess",
        lambda *args, **kwargs: pytest.fail("drifted runtime was launched"),
    )
    with pytest.raises(RuntimeError, match="runtime has drifted"):
        model.complete("prompt")


def test_transformers_adapter_rejects_malformed_child_schema(
    monkeypatch, tmp_path: Path,
) -> None:
    model = _model(tmp_path)
    monkeypatch.setattr("each.models.transformers_model.verify_snapshot_matches", lambda path, manifest: [])
    monkeypatch.setattr(
        model,
        "_run_subprocess",
        lambda *args, **kwargs: (0, json.dumps({"status": "OK", "completion": "body"}), ""),
    )
    with pytest.raises(RuntimeError, match="invalid result schema"):
        model.complete("prompt")


def test_transformers_adapter_rejects_runtime_version_mismatch(
    monkeypatch, tmp_path: Path,
) -> None:
    model = _model(tmp_path)
    monkeypatch.setattr("each.models.transformers_model.verify_snapshot_matches", lambda path, manifest: [])
    def wrong_runtime(command, **kwargs):
        return (
            0,
            json.dumps({
                "schemaVersion": "1",
                "status": "OK",
                "generationAttempted": True,
                "isolation": {
                    "networkDenied": True,
                    "privateFilesDenied": command.count("--probe-denied-path"),
                    "outsideWriteDenied": True,
                },
                "runtime": {"python": "3.12.14", "torch": "2.14.1", "transformers": "9.9.9"},
                "inputTokenCount": 1,
                "completion": "body",
            }),
            "",
        )

    monkeypatch.setattr(model, "_run_subprocess", wrong_runtime)
    with pytest.raises(RuntimeError, match="version mismatch"):
        model.complete("prompt")


def test_transformers_sandbox_profile_denies_network_and_sensitive_reads(tmp_path: Path) -> None:
    model = _model(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    denied = tmp_path / "secret"
    denied.write_text("secret")
    profile = model._sandbox_profile(work, denied)
    assert "(deny network*)" in profile
    assert "(deny file-write*)" in profile
    assert str(Path.home() / ".each" / "runs") in profile
    assert str(denied.resolve()) in profile


def test_transformers_adapter_rejects_oversized_raw_prompt(tmp_path: Path) -> None:
    model = _model(tmp_path)
    with pytest.raises(ContextBudgetExceeded, match="32 KiB"):
        model.complete("x" * (32 * 1024 + 1))


def test_transformers_adapter_requires_sandbox_binary(monkeypatch, tmp_path: Path) -> None:
    model = _model(tmp_path)
    monkeypatch.setattr("each.models.transformers_model.verify_snapshot_matches", lambda path, manifest: [])
    model._sandbox_executable = tmp_path / "missing"
    with pytest.raises(RuntimeError, match="requires /usr/bin/sandbox-exec"):
        model.complete("prompt")


@pytest.mark.skipif(os.name != "posix", reason="process-group enforcement is POSIX-only")
def test_transformers_subprocess_timeout_kills_process_group(tmp_path: Path) -> None:
    model = _model(tmp_path)
    model._timeout_seconds = 1
    work = tmp_path / "timeout"
    work.mkdir()
    with pytest.raises(RuntimeError, match="exceeded 1 seconds"):
        model._run_subprocess(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            prompt="",
            environment=dict(os.environ),
            cwd=work,
        )


@pytest.mark.skipif(os.name != "posix", reason="process-group enforcement is POSIX-only")
def test_transformers_subprocess_output_limit_kills_process_group(tmp_path: Path) -> None:
    model = _model(tmp_path)
    work = tmp_path / "output"
    work.mkdir()
    with pytest.raises(RuntimeError, match="output limit"):
        model._run_subprocess(
            [
                sys.executable,
                "-c",
                "import os,time; os.write(1, b'x' * (9 * 1024 * 1024)); time.sleep(1)",
            ],
            prompt="",
            environment=dict(os.environ),
            cwd=work,
        )
