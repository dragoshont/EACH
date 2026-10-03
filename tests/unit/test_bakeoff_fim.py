from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from each import bakeoff
from each.attestation import verify_materials_root, verify_receipt
from each.executor.base import ExecutionResult
from each.models.fixture import FixtureModel
from each.signing import public_key_path
from tests.adversarial._docker_guard import requires_colima_each


class CapturingFixture(FixtureModel):
    def complete(self, prompt: str) -> str:
        self.prompt = prompt
        return super().complete(prompt)


@pytest.fixture
def container_home(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="each-fim-tests-", dir=Path.home()) as directory:
        monkeypatch.setenv("EACH_HOME", directory)
        yield Path(directory)


def test_unknown_bakeoff_format_is_rejected():
    with pytest.raises(ValueError, match="proposal_format"):
        bakeoff.run_model_bakeoff(FixtureModel("unused"), proposal_format="unknown")


def test_missing_fixture_test_module_is_not_a_genuine_failing_test():
    result = ExecutionResult(
        ("python",), 1, "",
        "test_greet (unittest.loader._FailedTest.test_greet) ... ERROR\nRan 1 test\nFAILED (errors=1)",
    )
    verdict, classification = bakeoff._classify_fixture_run(result, expected_tests=1)
    assert verdict is None
    assert classification["reason"] == "test_collection_failed"


@requires_colima_each
def test_fim_uses_the_declared_prefix_and_retains_original_inputs(container_home, monkeypatch):
    calls = []
    original_run = bakeoff.ContainerExecutor.run

    def observed_run(self, command, worktree, **kwargs):
        calls.append((worktree, kwargs.get("protected_paths")))
        return original_run(self, command, worktree, **kwargs)

    monkeypatch.setattr(bakeoff.ContainerExecutor, "run", observed_run)
    completion = '    return "Hello, " + name\n'
    model = CapturingFixture(completion)
    result = bakeoff.run_model_bakeoff(model, max_attempts=1, proposal_format="fim")
    receipt_path = Path(result["receipt_json"])
    receipt = json.loads(receipt_path.read_text())
    assert result["outcome"] == "REPAIR_VERIFIED"
    assert model.prompt.startswith("<fim_prefix># ")
    assert model.prompt.endswith("def greet(name: str) -> str:\n<fim_suffix><fim_middle>")
    assert receipt["rawCompletion"] == completion
    assert receipt["attempts"][0]["proposal_format"] == "fim"
    assert receipt["attempts"][0]["completion_call_seconds"] >= 0
    validation_calls = [(path, protected) for path, protected in calls if protected]
    assert len(validation_calls) == 2
    assert validation_calls[0][0] != validation_calls[1][0]
    assert all(protected == tuple(bakeoff.FIXTURE_TEST_PATHS) for _, protected in validation_calls)
    assert verify_receipt(receipt, public_key_path().read_bytes())["status"] == "PASS"
    assert verify_materials_root(receipt, receipt_path.parent / "materials")["status"] == "PASS"


@requires_colima_each
@pytest.mark.parametrize("completion", ["", "<fim_prefix>unexpected"])
def test_invalid_fim_completion_is_not_a_patch(container_home, completion):
    result = bakeoff.run_model_bakeoff(FixtureModel(completion), max_attempts=1, proposal_format="fim")
    receipt_path = Path(result["receipt_json"])
    receipt = json.loads(receipt_path.read_text())
    assert result["outcome"].startswith("PATCH_REJECTED")
    assert receipt["rawCompletion"] == completion
    assert receipt["repairedResult"] == {}
    assert verify_materials_root(receipt, receipt_path.parent / "materials")["status"] == "PASS"


@requires_colima_each
def test_fim_backend_failure_preserves_a_signed_partial_receipt(container_home, monkeypatch):
    model = FixtureModel("unused")

    def failed(prompt):
        raise RuntimeError("private backend detail")

    monkeypatch.setattr(model, "complete", failed)
    result = bakeoff.run_model_bakeoff(model, max_attempts=1, proposal_format="fim")
    path = Path(result["receipt_json"])
    receipt = json.loads(path.read_text())
    assert result["outcome"] == "EXECUTION_ERROR"
    assert receipt["attempts"][0]["failureStage"] == "generation"
    assert receipt["attempts"][0]["generation_error_detail"] == "private backend detail"
    assert verify_receipt(receipt, public_key_path().read_bytes())["status"] == "PASS"
    assert verify_materials_root(receipt, path.parent / "materials")["status"] == "PASS"
