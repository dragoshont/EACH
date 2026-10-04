"""Unit tests for each.benchmark._interpret_pytest_run's honesty discipline.

Mirrors tests/unit/test_demo_classifier.py's coverage for
each.demo._interpret_test_run, but for pytest's summary-line format.
"""

from __future__ import annotations

import pytest

from each.benchmark import BenchmarkExecutionError, _interpret_pytest_run
from each.executor.base import ExecutionResult


def _result(exit_code: int, stdout: str, stderr: str = "") -> ExecutionResult:
    return ExecutionResult(command=("pytest",), exit_code=exit_code, stdout=stdout, stderr=stderr)


def test_a_clean_single_passing_test_is_classified_as_passed():
    result = _result(0, "collected 1 item\n\ntest_x.py .  [100%]\n\n1 passed in 0.01s\n")
    assert _interpret_pytest_run(result, expected_tests=1) == "passed"


def test_a_clean_single_failing_test_is_classified_as_failed():
    result = _result(1, "collected 1 item\n\ntest_x.py F  [100%]\n\n1 failed in 0.01s\n")
    assert _interpret_pytest_run(result, expected_tests=1) == "failed"


def test_partial_progress_is_a_real_failure_not_an_inconclusive_run():
    result = _result(1, "1 failed, 8 passed in 0.02s\n")
    assert _interpret_pytest_run(result, expected_tests=9) == "failed"


@pytest.mark.parametrize("exit_code", [2, 3, 4, 5, 137])
def test_non_test_failure_exit_cannot_be_classified_as_a_failing_test(exit_code):
    result = _result(exit_code, "1 failed, 8 passed in 0.02s\n")
    with pytest.raises(BenchmarkExecutionError, match="ambiguous"):
        _interpret_pytest_run(result, expected_tests=9)


def test_a_docker_launch_failure_exit_code_is_never_test_evidence():
    result = _result(125, "", "docker: Error response from daemon")
    with pytest.raises(BenchmarkExecutionError, match="container launch failed"):
        _interpret_pytest_run(result, expected_tests=1)


def test_any_skipped_test_is_rejected_even_if_the_target_test_passed():
    result = _result(0, "1 passed, 1 skipped in 0.02s\n")
    with pytest.raises(BenchmarkExecutionError, match="skipped"):
        _interpret_pytest_run(result, expected_tests=1)


def test_a_collection_error_is_rejected_not_folded_into_a_verdict():
    result = _result(2, "1 error in 0.01s\n")
    with pytest.raises(BenchmarkExecutionError, match="skipped"):
        _interpret_pytest_run(result, expected_tests=1)


def test_a_test_count_mismatch_is_rejected():
    result = _result(0, "2 passed in 0.02s\n")
    with pytest.raises(BenchmarkExecutionError, match="expected exactly 1"):
        _interpret_pytest_run(result, expected_tests=1)


def test_an_ambiguous_mixed_result_is_rejected_not_silently_passed():
    # exit 0 but failed > 0 is internally inconsistent pytest output; never
    # silently treated as a pass.
    result = _result(0, "1 passed, 1 failed in 0.02s\n")
    with pytest.raises(BenchmarkExecutionError, match="ambiguous"):
        _interpret_pytest_run(result, expected_tests=2)


def test_zero_tests_run_with_no_output_is_rejected_not_treated_as_passed():
    result = _result(0, "no tests ran\n")
    with pytest.raises(BenchmarkExecutionError, match="expected exactly 1"):
        _interpret_pytest_run(result, expected_tests=1)
