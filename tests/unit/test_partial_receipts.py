from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

import each.bakeoff as bakeoff_module
import each.benchmark as benchmark_module
from each.benchmark import BenchmarkTask
from each.executor.base import ExecutionResult
from each.executor.container import NETWORK_PROBE_DENIAL_MARKER, ContainerExecutorError
from each.models.fixture import FixtureModel

PATCH = """BEGIN_PATCH
--- a/src/greet.py
+++ b/src/greet.py
@@ -1,2 +1,2 @@
 def greet(name: str) -> str:
-    return \"Hell, \" + name
+    return \"Hello, \" + name
END_PATCH
"""


@pytest.fixture(autouse=True)
def _isolated_each_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))


class _FakeBakeoffExecutor:
    def __init__(self, *args, **kwargs) -> None:
        self._calls = 0

    def identity(self) -> dict[str, str]:
        return {"executor": "fake-bakeoff"}

    def verify_isolation(self, worktree: Path) -> ExecutionResult:
        return ExecutionResult(("python",), 1, f"{NETWORK_PROBE_DENIAL_MARKER}\n", "")

    def run(self, command: list[str], worktree: Path, *, protected_paths: tuple[str, ...] = ()) -> ExecutionResult:
        self._calls += 1
        if self._calls == 1:
            return ExecutionResult(
                tuple(command),
                1,
                "test_greet (tests.test_greet.GreetTests.test_greet) ... FAIL\n\nRan 1 test in 0.001s\n\nFAILED (failures=1)\n",
                "",
            )
        raise ContainerExecutorError("simulated repaired-run timeout")


class _FakeBenchmarkExecutor:
    def __init__(self, *args, **kwargs) -> None:
        self._calls = 0

    def identity(self) -> dict[str, str]:
        return {"executor": "fake-benchmark"}

    def verify_isolation(self, worktree: Path) -> ExecutionResult:
        return ExecutionResult(("python",), 1, f"{NETWORK_PROBE_DENIAL_MARKER}\n", "")

    def run(self, command: list[str], worktree: Path, *, protected_paths: tuple[str, ...] = ()) -> ExecutionResult:
        self._calls += 1
        if self._calls == 1:
            return ExecutionResult(tuple(command), 1, "1 failed in 0.01s\n", "")
        raise ContainerExecutorError("simulated repaired-run timeout")


def _fake_build_worktree(source_root: Path, include_paths: list[str], dest: Path | None = None):
    # Deliberately never derived from `source_root` itself: `source_root` here
    # is the real, repo-tracked `FIXTURE_ROOT` fixture directory
    # (`examples/hello-repair`), not an isolated copy -- `source_root.parent /
    # "wt-..."` would write real files straight into the tracked `examples/`
    # tree. Always materialize under the OS temp directory instead.
    worktree = dest or Path(tempfile.mkdtemp(prefix=f"wt-{source_root.name}-"))
    for rel in include_paths:
        src = source_root / rel
        target = worktree / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(src.read_bytes())
    return worktree, {rel: "hash" for rel in include_paths}


def test_bakeoff_preserves_generation_data_in_a_partial_receipt_after_a_repaired_run_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(bakeoff_module, "ContainerExecutor", _FakeBakeoffExecutor)
    monkeypatch.setattr(bakeoff_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P2")
    monkeypatch.setattr(bakeoff_module, "build_worktree", _fake_build_worktree)
    model = FixtureModel(PATCH, model_id="fixture/bakeoff-partial-v1")

    result = bakeoff_module.run_model_bakeoff(model, max_attempts=1, run_id="bakeoff-partial")

    assert result["outcome"].startswith("EXECUTION_ERROR")
    receipt = json.loads(Path(result["receipt_json"]).read_text(encoding="utf-8"))
    assert receipt["selectedAttempt"] == 1
    assert receipt["attempts"][0]["raw_completion"] == PATCH
    assert receipt["attempts"][0]["patch_text"]
    assert receipt["attempts"][0]["model_identity"]["adapterType"] == "FixtureModel"
    assert receipt["attempts"][0]["outcome"].startswith("EXECUTION_ERROR")


def test_benchmark_preserves_generation_data_in_a_partial_receipt_after_a_repaired_run_timeout(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    (source_root / "pkg").mkdir(parents=True)
    (source_root / "tests").mkdir(parents=True)
    (source_root / "pkg" / "module.py").write_text('def greet(name: str) -> str:\n    return "Hell, " + name\n', encoding='utf-8')
    (source_root / "tests" / "test_module.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    monkeypatch.setattr(benchmark_module, "ContainerExecutor", _FakeBenchmarkExecutor)
    monkeypatch.setattr(benchmark_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P2")
    monkeypatch.setattr(benchmark_module, "build_worktree", _fake_build_worktree)
    monkeypatch.setattr(benchmark_module, "materialize_task_sources", lambda task: (source_root, [task.bug_path, *task.test_paths]))
    monkeypatch.setattr(benchmark_module, "fetch_file", lambda *args, **kwargs: "def test_ok():\n    assert True\n")
    monkeypatch.setattr(benchmark_module, "select_prompt_excerpt", lambda source, tests: (source, 1, len(source.splitlines())))
    monkeypatch.setattr(benchmark_module, "materialize_known_fix", lambda task: "known fix")
    model = FixtureModel(
        """BEGIN_PATCH
--- a/pkg/module.py
+++ b/pkg/module.py
@@ -1,2 +1,2 @@
 def greet(name: str) -> str:
-    return \"Hell, \" + name
+    return \"Hello, \" + name
END_PATCH
""",
        model_id="fixture/benchmark-partial-v1",
    )
    task = BenchmarkTask(
        task_id="partial-benchmark",
        repo="example/repo",
        license="MIT",
        pre_fix_sha="a" * 40,
        fix_sha="b" * 40,
        bug_path="pkg/module.py",
        test_paths=("tests/test_module.py",),
        test_command=("pytest", "tests/test_module.py", "-q"),
        problem_statement="greet() returns Hell instead of Hello",
    )

    result = benchmark_module.run_benchmark_task(task, model, max_attempts=1, run_id="benchmark-partial")

    assert result["outcome"] == "EXECUTION_ERROR"
    receipt = json.loads(Path(result["receipt_json"]).read_text(encoding="utf-8"))
    assert receipt["selectedAttempt"] == 1
    assert receipt["attempts"][0]["raw_completion"]
    assert receipt["attempts"][0]["patch_text"]
    assert receipt["attempts"][0]["model_identity"]["adapterType"] == "FixtureModel"
    assert receipt["attempts"][0]["outcome"].startswith("EXECUTION_ERROR")
