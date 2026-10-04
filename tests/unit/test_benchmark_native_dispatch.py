"""Unit tests for the native-language (C/C++/Rust) dispatch helpers added to
``each.benchmark`` to close the section 128 "mix of C/C++/Rust/Python"
historical-benchmark requirement, plus the materials-recovery helper used
to genuinely re-verify a receipt that predates materials retention.

These are pure-function/filesystem tests (no model, no container) --
container-exercised end-to-end coverage lives in
tests/adversarial/test_benchmark_native_task.py.
"""

from __future__ import annotations

import each.benchmark as benchmark_module
from each.benchmark import (
    BENCHMARK_IMAGE_DIGEST,
    BENCHMARK_NATIVE_IMAGE_DIGEST,
    BenchmarkTask,
    _benchmark_image_for,
    _classify_execution,
    _classify_native_execution,
    _wrapped_test_command,
    retain_task_materials,
)
from each.executor.base import ExecutionResult

_PYTHON_TASK = BenchmarkTask(
    task_id="python-smoke",
    repo="example/some-lib",
    license="MIT",
    pre_fix_sha="a" * 40,
    fix_sha="b" * 40,
    bug_path="pkg/module.py",
    test_paths=("tests/test_module.py",),
    test_command=("python", "-m", "pytest", "tests/test_module.py", "-q"),
    problem_statement="irrelevant",
)

_NATIVE_TASK = BenchmarkTask(
    task_id="c-smoke",
    repo="example/some-c-lib",
    license="MIT",
    language="C",
    pre_fix_sha="c" * 40,
    fix_sha="d" * 40,
    bug_path="lib.c",
    test_paths=(),
    test_command=("cc -std=c99 lib.c validate.c -o validate && ./validate",),
    problem_statement="irrelevant",
    validator_files=(("validate.c", "int main(void) { return 0; }\n"),),
)


def _result(exit_code: int) -> ExecutionResult:
    return ExecutionResult(command=("validate",), exit_code=exit_code, stdout="", stderr="")


def test_benchmark_image_for_dispatches_by_language() -> None:
    assert _benchmark_image_for(_PYTHON_TASK) == BENCHMARK_IMAGE_DIGEST
    assert _benchmark_image_for(_NATIVE_TASK) == BENCHMARK_NATIVE_IMAGE_DIGEST


def test_classify_native_execution_exit_zero_is_pass() -> None:
    verdict, classification = _classify_native_execution(_result(0))
    assert verdict == "passed"
    assert classification == {"classification": "pass", "reason": "validator_exit_zero", "exit_code": 0}


def test_classify_native_execution_exit_one_is_fail() -> None:
    verdict, classification = _classify_native_execution(_result(1))
    assert verdict == "failed"
    assert classification["classification"] == "fail"


def test_classify_native_execution_other_exit_code_is_inconclusive_not_silently_passed() -> None:
    verdict, classification = _classify_native_execution(_result(2))
    assert verdict is None
    assert classification["classification"] == "inconclusive"
    assert classification["exit_code"] == 2


def test_classify_execution_dispatches_to_native_for_non_python_language() -> None:
    verdict, classification = _classify_execution(_NATIVE_TASK, _result(0), expected_tests=0)
    assert verdict == "passed"
    assert classification["reason"] == "validator_exit_zero"


def test_wrapped_test_command_native_single_string_is_passed_unmodified_to_sh_c() -> None:
    wrapped = _wrapped_test_command(_NATIVE_TASK)
    assert wrapped == ["sh", "-c", "cc -std=c99 lib.c validate.c -o validate && ./validate"]
    # Regression: shlex.join-ing this string would mis-quote the "&&" as a
    # literal argument token, breaking the compile-then-run pipeline.
    assert "'&&'" not in " ".join(wrapped)


def test_wrapped_test_command_python_still_sets_pythonpath_and_shlex_joins() -> None:
    wrapped = _wrapped_test_command(_PYTHON_TASK)
    assert wrapped[:2] == ["sh", "-c"]
    assert "PYTHONPATH=" in wrapped[2]
    assert "pytest" in wrapped[2]


def test_retain_task_materials_recovers_exact_bytes_and_excerpt_pseudo_path(monkeypatch, tmp_path) -> None:
    source_cache = tmp_path / "cache"
    monkeypatch.setattr(benchmark_module, "cache_dir", lambda: source_cache)

    def _stub_fetch_file(repo: str, sha: str, path: str, *, timeout: int = 20) -> str:
        del repo, timeout
        assert sha == _NATIVE_TASK.pre_fix_sha, "materials recovery must only ever read the pinned pre_fix_sha"
        return "int lib(void) { return 1; }\n"

    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)

    materials_root = tmp_path / "materials"
    written = retain_task_materials(_NATIVE_TASK, materials_root)

    assert (materials_root / "lib.c").read_text() == "int lib(void) { return 1; }\n"
    assert (materials_root / "validate.c").read_text() == "int main(void) { return 0; }\n"
    assert "lib.c" in written
    assert "validate.c" in written
    excerpt_keys = [k for k in written if "#prompt-excerpt:" in k]
    assert len(excerpt_keys) == 1
    assert (materials_root / excerpt_keys[0]).exists()
