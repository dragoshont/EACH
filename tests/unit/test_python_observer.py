import json

import pytest

from each.executor.base import ExecutionResult
from each.executor.container import ContainerExecutor
from each.executor.python_observer import PythonCase, observe_python


class RecordingExecutor:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def run(self, command, worktree, **kwargs):
        self.calls.append((command, kwargs))
        code, text = next(self.outputs)
        return ExecutionResult(tuple(command), code, text, "")


def source(tmp_path):
    (tmp_path / "api.py").write_text("def f(x): return x\n")
    return tmp_path


@pytest.mark.parametrize("code,text", [
    (0, ""), (0, "3 passed\n"), (0, "COMPLETE\n"),
    (0, '{"value":1}\n{"value":1}'), (1, '{"value":1}'),
    (0, '{"value":1,"passed":true}'), (0, 'null'),
    (0, '{"value":NaN}'),
])
def test_incomplete_cannot_pass(tmp_path, code, text):
    executor = RecordingExecutor([(code, text)])
    result = observe_python(executor, source(tmp_path), "api.py", (PythonCase("positive", "f", (1,), 1),))
    assert result.exit_code == 2
    assert json.loads(result.stdout)["completedCases"] == 0


def test_expected_completion_and_results_are_outside_candidate(tmp_path):
    cases = (PythonCase("positive", "f", (1,), 1234567), PythonCase("negative", "f", (-1,), error="ValueError"))
    executor = RecordingExecutor([(0, '{"value":1234567}'), (0, '{"error":"ValueError"}')])
    result = observe_python(executor, source(tmp_path), "api.py", cases)
    assert result.exit_code == 0
    assert json.loads(result.stdout)["completedCases"] == 2
    for command, kwargs in executor.calls:
        assert "1234567" not in " ".join(command)
        assert kwargs["read_only_worktree"] is True


@pytest.mark.parametrize("value", [2, True, "1"])
def test_real_failure_and_types(tmp_path, value):
    result = observe_python(RecordingExecutor([(0, json.dumps({"value": value}))]), source(tmp_path),
                            "api.py", (PythonCase("case", "f", (1,), 1),))
    assert result.exit_code == 1


def test_duplicate_cases_rejected(tmp_path):
    with pytest.raises(ValueError):
        observe_python(RecordingExecutor([]), source(tmp_path), "api.py",
                       (PythonCase("x", "f", ()), PythonCase("x", "f", ())))


def test_whole_worktree_readonly_command(tmp_path):
    command = ContainerExecutor().build_docker_command(
        ["python", "-I"], tmp_path, container_name="test", read_only_worktree=True,
    )
    assert f"{tmp_path.resolve()}:/work:ro" in command


def test_deep_candidate_json_is_incomplete_not_a_harness_recursion_crash(tmp_path):
    response = '{"value":' + '[' * 20000 + '0' + ']' * 20000 + '}'
    result = observe_python(
        RecordingExecutor([(0, response)]), source(tmp_path), "api.py",
        (PythonCase("deep", "f", (1,), 1),),
    )
    evidence = json.loads(result.stdout)
    assert result.exit_code == 2 and evidence["completedCases"] == 0
    assert evidence["apiReturnAuthenticated"] is False
