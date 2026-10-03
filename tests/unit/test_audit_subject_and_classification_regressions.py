from __future__ import annotations

import json
from pathlib import Path

import each.bakeoff as bakeoff_module
import each.benchmark as benchmark_module
from each.executor.base import ExecutionResult
from each.executor.container import NETWORK_PROBE_DENIAL_MARKER
from each.models.fixture import FixtureModel

_BAKEOFF_PATCH = """BEGIN_PATCH
--- a/src/greet.py
+++ b/src/greet.py
@@ -1,2 +1,2 @@
 def greet(name: str) -> str:
-    return "Hell, " + name
+    return "Hello, " + name
END_PATCH
"""

_BENCHMARK_PATCH = """BEGIN_PATCH
--- a/clamp.py
+++ b/clamp.py
@@ -1,4 +1,6 @@
 def clamp(value, lo, hi):
     if value > hi:
         return hi
+    if value < lo:
+        return lo
     return value
END_PATCH
"""

_BUGGY_CLAMP = "def clamp(value, lo, hi):\n    if value > hi:\n        return hi\n    return value\n"
_FIXED_CLAMP = (
    "def clamp(value, lo, hi):\n    if value > hi:\n        return hi\n    if value < lo:\n        return lo\n    return value\n"
)
_TEST_CLAMP = (
    "from clamp import clamp\n\n\ndef test_clamp_enforces_the_lower_bound():\n    assert clamp(-5, 0, 10) == 0\n"
)


class _BenchmarkModel:
    model_id = "test/stub-benchmark-model"

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls = 0

    def complete(self, prompt: str) -> str:
        del prompt
        reply = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        return reply

    def identity(self) -> dict[str, str]:
        return {"modelId": self.model_id, "implementationModule": __name__, "implementationSha256": ""}


def _copy_worktree_factory(tmp_path: Path):
    counter = {"value": 0}

    def _copy_worktree(source_root: Path, include_paths: list[str], dest: Path | None = None):
        counter["value"] += 1
        worktree = dest or (tmp_path / f"worktree-{counter['value']}")
        for rel in include_paths:
            src = source_root / rel
            target = worktree / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(src.read_bytes())
        return worktree, {rel: "hash" for rel in include_paths}

    return _copy_worktree


def _benchmark_source_root(tmp_path: Path) -> tuple[Path, list[str]]:
    source_root = tmp_path / "benchmark-source"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "clamp.py").write_text(_BUGGY_CLAMP, encoding="utf-8")
    (source_root / "test_clamp.py").write_text(_TEST_CLAMP, encoding="utf-8")
    return source_root, ["clamp.py", "test_clamp.py"]


def _benchmark_task() -> benchmark_module.BenchmarkTask:
    return benchmark_module.BenchmarkTask(
        task_id="synthetic-clamp-smoke",
        repo="example/clamp-lib",
        license="MIT",
        pre_fix_sha="deadbeef" * 5,
        fix_sha="cafebabe" * 5,
        bug_path="clamp.py",
        test_paths=("test_clamp.py",),
        test_command=("python", "-m", "pytest", "test_clamp.py", "-q"),
        problem_statement="clamp() does not enforce its lower bound.",
    )


def _stub_fetch_file(repo: str, sha: str, path: str, *, timeout: int = 20) -> str:
    del repo, sha, timeout
    if path == "clamp.py":
        return _BUGGY_CLAMP
    if path == "test_clamp.py":
        return _TEST_CLAMP
    raise AssertionError(path)


def test_bakeoff_audit_uses_precaptured_candidate_bytes_even_if_execution_mutates_the_worktree(tmp_path, monkeypatch) -> None:
    class _MutatingExecutor:
        def identity(self) -> dict[str, str]:
            return {"executor": "mutating-bakeoff"}

        def verify_isolation(self, worktree: Path) -> ExecutionResult:
            del worktree
            return ExecutionResult(("python",), 1, f"{NETWORK_PROBE_DENIAL_MARKER}\n", "")

        def run(self, command: list[str], worktree: Path, *, protected_paths: tuple[str, ...] = ()) -> ExecutionResult:
            del command
            if not hasattr(self, "_calls"):
                self._calls = 0
            self._calls += 1
            if self._calls == 1:
                return ExecutionResult(("python",), 1, "Ran 1 test in 0.001s\n\nFAILED (failures=1)\n", "")
            (worktree / "src" / "greet.py").write_text("MUTATED AFTER EXECUTION\n", encoding="utf-8")
            return ExecutionResult(("python",), 0, "Ran 1 test in 0.001s\n\nOK\n", "")

    observed: list[str] = []
    monkeypatch.setattr(bakeoff_module, "ContainerExecutor", _MutatingExecutor)
    monkeypatch.setattr(bakeoff_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P2")
    monkeypatch.setattr(bakeoff_module, "build_worktree", _copy_worktree_factory(tmp_path))
    monkeypatch.setattr(
        bakeoff_module,
        "run_audit",
        lambda source, **kwargs: observed.append(source) or {"checks": {}, "result": "PASS", "toolVersions": {}, "reason": "captured"},
    )
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))

    result = bakeoff_module.run_model_bakeoff(FixtureModel(_BAKEOFF_PATCH), max_attempts=1, run_id="bakeoff-precap")

    assert result["outcome"] == "REPAIR_VERIFIED"
    assert observed == ['def greet(name: str) -> str:\n    return "Hello, " + name\n']


def test_benchmark_audit_uses_precaptured_candidate_bytes_even_if_execution_mutates_the_worktree(tmp_path, monkeypatch) -> None:
    class _MutatingExecutor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def identity(self) -> dict[str, str]:
            return {"executor": "mutating-benchmark"}

        def verify_isolation(self, worktree: Path) -> ExecutionResult:
            del worktree
            return ExecutionResult(("python",), 1, f"{NETWORK_PROBE_DENIAL_MARKER}\n", "")

        def run(self, command: list[str], worktree: Path, *, protected_paths: tuple[str, ...] = ()) -> ExecutionResult:
            del command
            if not hasattr(self, "_calls"):
                self._calls = 0
            self._calls += 1
            if self._calls == 1:
                return ExecutionResult(("pytest",), 1, "1 failed in 0.01s\n", "")
            (worktree / "clamp.py").write_text("MUTATED AFTER EXECUTION\n", encoding="utf-8")
            return ExecutionResult(("pytest",), 0, "1 passed in 0.01s\n", "")

    observed: list[str] = []
    source_root, include_paths = _benchmark_source_root(tmp_path)
    monkeypatch.setattr(benchmark_module, "ContainerExecutor", _MutatingExecutor)
    monkeypatch.setattr(benchmark_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P2")
    monkeypatch.setattr(benchmark_module, "build_worktree", _copy_worktree_factory(tmp_path))
    monkeypatch.setattr(benchmark_module, "materialize_task_sources", lambda task: (source_root, include_paths))
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    monkeypatch.setattr(
        benchmark_module,
        "run_audit",
        lambda source, **kwargs: observed.append(source) or {"checks": {}, "result": "PASS", "toolVersions": {}, "reason": "captured"},
    )
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))

    result = benchmark_module.run_benchmark_task(
        _benchmark_task(), _BenchmarkModel([_BENCHMARK_PATCH]), max_attempts=1, run_id="benchmark-precap"
    )

    assert result["outcome"] == "REPAIR_VERIFIED"
    assert observed == [_FIXED_CLAMP]


def test_bakeoff_preserves_earlier_attempt_data_when_a_later_baseline_is_inconclusive(tmp_path, monkeypatch) -> None:
    class _InconclusiveBaselineExecutor:
        def identity(self) -> dict[str, str]:
            return {"executor": "inconclusive-bakeoff"}

        def verify_isolation(self, worktree: Path) -> ExecutionResult:
            del worktree
            return ExecutionResult(("python",), 1, f"{NETWORK_PROBE_DENIAL_MARKER}\n", "")

        def run(self, command: list[str], worktree: Path, *, protected_paths: tuple[str, ...] = ()) -> ExecutionResult:
            del command, worktree
            if not hasattr(self, "_calls"):
                self._calls = 0
            self._calls += 1
            if self._calls == 1:
                return ExecutionResult(("python",), 1, "Ran 1 test in 0.001s\n\nFAILED (failures=1)\n", "")
            if self._calls == 2:
                return ExecutionResult(("python",), 1, "Ran 1 test in 0.001s\n\nFAILED (failures=1)\n", "")
            return ExecutionResult(("python",), 0, "Ran 1 test in 0.001s\n\nFAILED (failures=1)\n", "")

    monkeypatch.setattr(bakeoff_module, "ContainerExecutor", _InconclusiveBaselineExecutor)
    monkeypatch.setattr(bakeoff_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P2")
    monkeypatch.setattr(bakeoff_module, "build_worktree", _copy_worktree_factory(tmp_path))
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))

    result = bakeoff_module.run_model_bakeoff(FixtureModel(_BAKEOFF_PATCH), max_attempts=2, run_id="bakeoff-inconclusive")
    receipt = json.loads(Path(result["receipt_json"]).read_text(encoding="utf-8"))

    assert result["outcome"] == "BASELINE_INCONCLUSIVE: contradictory_summary"
    assert len(receipt["attempts"]) == 2
    assert receipt["attempts"][0]["outcome"] == "REPAIR_NOT_VERIFIED"
    assert receipt["attempts"][0]["baseline_result"]["exit_code"] == 1
    assert receipt["attempts"][0]["repaired_result"]["exit_code"] == 1
    assert receipt["attempts"][1]["baseline_classification"] == {
        "classification": "inconclusive",
        "reason": "contradictory_summary",
    }
    assert receipt["attempts"][1]["repaired_result"] == {}


def test_benchmark_records_structured_baseline_inconclusive_results_instead_of_empty_dicts(tmp_path, monkeypatch) -> None:
    class _NoTestsExecutor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def identity(self) -> dict[str, str]:
            return {"executor": "no-tests-benchmark"}

        def verify_isolation(self, worktree: Path) -> ExecutionResult:
            del worktree
            return ExecutionResult(("python",), 1, f"{NETWORK_PROBE_DENIAL_MARKER}\n", "")

        def run(self, command: list[str], worktree: Path, *, protected_paths: tuple[str, ...] = ()) -> ExecutionResult:
            del command, worktree
            return ExecutionResult(("pytest",), 2, "no tests ran in 0.01s\n", "")

    source_root, include_paths = _benchmark_source_root(tmp_path)
    monkeypatch.setattr(benchmark_module, "ContainerExecutor", _NoTestsExecutor)
    monkeypatch.setattr(benchmark_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P2")
    monkeypatch.setattr(benchmark_module, "build_worktree", _copy_worktree_factory(tmp_path))
    monkeypatch.setattr(benchmark_module, "materialize_task_sources", lambda task: (source_root, include_paths))
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))

    result = benchmark_module.run_benchmark_task(
        _benchmark_task(), _BenchmarkModel([_BENCHMARK_PATCH]), max_attempts=1, run_id="benchmark-no-tests"
    )
    receipt = json.loads(Path(result["receipt_json"]).read_text(encoding="utf-8"))

    assert result["outcome"] == "BASELINE_INCONCLUSIVE"
    assert receipt["baselineResult"]["exit_code"] == 2
    assert receipt["attempts"][0]["baseline_classification"] == {
        "classification": "inconclusive",
        "reason": "no_tests_collected",
        "exit_code": 2,
    }


def test_benchmark_preserves_completed_repaired_execution_results_when_classification_is_inconclusive(tmp_path, monkeypatch) -> None:
    class _InconclusiveRepairedExecutor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def identity(self) -> dict[str, str]:
            return {"executor": "inconclusive-repaired-benchmark"}

        def verify_isolation(self, worktree: Path) -> ExecutionResult:
            del worktree
            return ExecutionResult(("python",), 1, f"{NETWORK_PROBE_DENIAL_MARKER}\n", "")

        def run(self, command: list[str], worktree: Path, *, protected_paths: tuple[str, ...] = ()) -> ExecutionResult:
            del command, worktree
            if not hasattr(self, "_calls"):
                self._calls = 0
            self._calls += 1
            if self._calls == 1:
                return ExecutionResult(("pytest",), 1, "1 failed in 0.01s\n", "")
            return ExecutionResult(("pytest",), 2, "2 passed, 1 failed in 0.01s\n", "")

    source_root, include_paths = _benchmark_source_root(tmp_path)
    monkeypatch.setattr(benchmark_module, "ContainerExecutor", _InconclusiveRepairedExecutor)
    monkeypatch.setattr(benchmark_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P2")
    monkeypatch.setattr(benchmark_module, "build_worktree", _copy_worktree_factory(tmp_path))
    monkeypatch.setattr(benchmark_module, "materialize_task_sources", lambda task: (source_root, include_paths))
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))

    result = benchmark_module.run_benchmark_task(
        _benchmark_task(), _BenchmarkModel([_BENCHMARK_PATCH]), max_attempts=1, run_id="benchmark-inconclusive-repaired"
    )
    receipt = json.loads(Path(result["receipt_json"]).read_text(encoding="utf-8"))

    assert result["outcome"] == "REPAIRED_RUN_INCONCLUSIVE"
    assert receipt["attempts"][0]["repaired_result"]["exit_code"] == 2
    assert receipt["attempts"][0]["repaired_classification"] == {
        "classification": "inconclusive",
        "reason": "unexpected_test_count",
        "exit_code": 2,
        "observedTests": 3,
        "expectedTests": 1,
    }
