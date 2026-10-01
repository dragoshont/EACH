from __future__ import annotations

import pytest

from each.demo import EXPECTED_TEST_COUNT, FixtureExecutionError, _interpret_test_run
from each.executor.base import ExecutionResult


def _result(exit_code: int, stdout: str = "", stderr: str = "") -> ExecutionResult:
    return ExecutionResult(command=("python", "-m", "unittest"), exit_code=exit_code, stdout=stdout, stderr=stderr)


def test_interpret_test_run_passed() -> None:
    result = _result(0, stderr="test_greet (tests.test_greet.GreetTest) ... ok\n\nRan 1 test in 0.000s\n\nOK\n")
    assert _interpret_test_run(result, expected_tests=EXPECTED_TEST_COUNT) == "passed"


def test_interpret_test_run_failed() -> None:
    result = _result(
        1,
        stderr=(
            "test_greet (tests.test_greet.GreetTest) ... FAIL\n\n"
            "Ran 1 test in 0.000s\n\nFAILED (failures=1)\n"
        ),
    )
    assert _interpret_test_run(result, expected_tests=EXPECTED_TEST_COUNT) == "failed"


@pytest.mark.parametrize("exit_code", [125, 126, 127])
def test_interpret_test_run_rejects_docker_launch_failure(exit_code: int) -> None:
    result = _result(exit_code, stderr="docker: Error response from daemon")
    with pytest.raises(FixtureExecutionError, match="container launch failed"):
        _interpret_test_run(result, expected_tests=EXPECTED_TEST_COUNT)


def test_interpret_test_run_rejects_skip_masquerading_as_pass() -> None:
    result = _result(0, stderr="Ran 1 test in 0.000s\n\nOK (skipped=1)\n")
    with pytest.raises(FixtureExecutionError, match="not a clean 'OK'"):
        _interpret_test_run(result, expected_tests=EXPECTED_TEST_COUNT)


def test_interpret_test_run_rejects_wrong_test_count() -> None:
    result = _result(0, stderr="Ran 2 tests in 0.000s\n\nOK\n")
    with pytest.raises(FixtureExecutionError, match="expected exactly"):
        _interpret_test_run(result, expected_tests=EXPECTED_TEST_COUNT)


def test_interpret_test_run_rejects_unrecognizable_nonzero_output() -> None:
    result = _result(2, stderr="Ran 1 test in 0.000s\n\nsomething weird happened\n")
    with pytest.raises(FixtureExecutionError, match="FAILED summary"):
        _interpret_test_run(result, expected_tests=EXPECTED_TEST_COUNT)
