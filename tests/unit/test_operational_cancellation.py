"""Cancellation must stop retries and preserve the supported lane's evidence."""

import json

import pytest

from each import benchmark
from each.attestation import verify_materials_root, verify_receipt
from each.executor.base import ExecutionResult
from each.executor.container import NETWORK_PROBE_DENIAL_MARKER
from each.executor.python_observer import PythonCase
from each.models.fixture import FixtureModel
from each.signing import public_key_path


@pytest.mark.parametrize("phase", ["baseline", "generation", "validation"])
def test_benchmark_cancel_preserves_signed_partial_without_retry(tmp_path, monkeypatch, phase):
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "temporary-home"))
    source = tmp_path / "source"
    source.mkdir()
    (source / "api.py").write_text("def f(x): return x + 1\n")
    monkeypatch.setattr(benchmark, "materialize_task_sources", lambda task: (source, ["api.py"]))
    monkeypatch.setattr(benchmark, "materialize_known_fix", lambda task: "not supplied to Builder")

    class Executor:
        def __init__(self, **kwargs):
            pass

        def identity(self):
            return {"executor": "deterministic-cancellation-control"}

        def verify_isolation(self, root):
            return ExecutionResult(("probe",), 1, NETWORK_PROBE_DENIAL_MARKER, "")

    monkeypatch.setattr(benchmark, "ContainerExecutor", Executor)
    monkeypatch.setattr(benchmark, "derive_assurance_level", lambda *args: "EACH-P2")
    calls = []

    def observe(task, executor, worktree, protected_paths):
        calls.append("validation")
        if phase == "baseline" or (phase == "validation" and len(calls) == 2):
            raise KeyboardInterrupt()
        return ExecutionResult(("trusted-host-json-v1",), 1, json.dumps({
            "observer": "trusted-host-json-v1", "expectedCases": 1,
            "completedCases": 1, "cases": [{"caseId": "case", "status": "fail"}],
            "sourceUnchanged": True, "exitCode": 1,
        }), "")

    monkeypatch.setattr(benchmark, "_run_task_validation", observe)
    model = FixtureModel("BEGIN_SOURCE\ndef f(x): return x\nEND_SOURCE")
    completions = []
    original_complete = model.complete

    def complete(prompt):
        completions.append(1)
        if phase == "generation":
            raise KeyboardInterrupt()
        return original_complete(prompt)

    monkeypatch.setattr(model, "complete", complete)
    task = benchmark.BenchmarkTask(
        task_id="synthetic-cancel", repo="example/public-synthetic", license="Apache-2.0",
        pre_fix_sha="a" * 40, fix_sha="b" * 40, bug_path="api.py", test_paths=(),
        test_command=("trusted-host-json-v1",), problem_statement="Identity harness fixture.",
        observation_cases=(PythonCase("case", "f", (1,), 1),), proposal_format="full_source",
    )
    result = benchmark.run_benchmark_task(task, model, max_attempts=3)
    assert result["outcome"] == "EXECUTION_ERROR"
    assert result["attempts"] == 1
    assert len(completions) == (0 if phase == "baseline" else 1)
    path = __import__("pathlib").Path(result["receipt_json"])
    receipt = json.loads(path.read_text())
    assert receipt["outcome"] != "REPAIR_VERIFIED"
    assert receipt["attempts"][0]["errorType"] == "KeyboardInterrupt"
    assert receipt["attempts"][0]["failureStage"] == phase
    if phase == "validation":
        assert receipt["rawCompletion"] == "BEGIN_SOURCE\ndef f(x): return x\nEND_SOURCE"
        assert receipt["patchText"]
    assert verify_receipt(receipt, public_key_path().read_bytes())["status"] == "PASS"
    assert verify_materials_root(receipt, path.parent / "materials")["status"] == "PASS"
