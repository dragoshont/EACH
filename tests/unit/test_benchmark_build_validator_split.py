"""Regressions for item 5/6 of the a3bf1f4-successor defect contract:

- a non-Python task's ``build_command`` compile phase is a structurally
  separate executor call from its ``test_command`` validator phase, so an
  ordinary compiler error (exit 1) is never misclassified as the validator
  binary's own ``validator_exit_one`` "declared behavior does not hold"
  result (``each.benchmark._classify_native_execution``'s historical bug);
- every baseline/candidate executor call during ``run_benchmark_task`` is
  passed ``protected_paths`` covering the task's declared immutable
  materials (test/validator/support files), not just the one editable
  ``bug_path``.
"""

from __future__ import annotations

import json
from pathlib import Path

import each.benchmark as benchmark_module
from each.executor.base import ExecutionResult
from each.executor.container import NETWORK_PROBE_DENIAL_MARKER
from each.models.fixture import FixtureModel

_GOOD_PATCH = """BEGIN_PATCH
--- a/validate.c
+++ b/validate.c
@@ -1,3 +1,3 @@
 int main(void) {
-    return 1;
+    return 0;
 }
END_PATCH
"""

_BROKEN_PATCH = """BEGIN_PATCH
--- a/validate.c
+++ b/validate.c
@@ -1,3 +1,3 @@
 int main(void) {
-    return 1;
+    return 0  // missing semicolon: a genuine compiler syntax error
 }
END_PATCH
"""

_VALIDATE_C_FAILING = "int main(void) {\n    return 1;\n}\n"


def _native_task() -> benchmark_module.BenchmarkTask:
    return benchmark_module.BenchmarkTask(
        task_id="synthetic-native-build-split",
        repo="example/native-lib",
        license="MIT",
        pre_fix_sha="deadbeef" * 5,
        fix_sha="cafebabe" * 5,
        bug_path="validate.c",
        test_paths=("validate.c",),
        test_command=("./validate",),
        build_command=("cc -std=c99 validate.c -o validate",),
        problem_statement="The validator reports the bug is still present.",
        language="c",
    )


def _native_source_root(tmp_path: Path) -> tuple[Path, list[str]]:
    source_root = tmp_path / "native-source"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "validate.c").write_text(_VALIDATE_C_FAILING, encoding="utf-8")
    (source_root / "SUPPORT_NOTES.txt").write_text("immutable supporting material\n", encoding="utf-8")
    return source_root, ["validate.c", "SUPPORT_NOTES.txt"]


def _stub_fetch_file(repo: str, sha: str, path: str, *, timeout: int = 20) -> str:
    del repo, sha, timeout
    if path == "validate.c":
        return _VALIDATE_C_FAILING
    raise AssertionError(path)


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


class _RecordingNativeExecutor:
    """Fake ``ContainerExecutor`` distinguishing a real compile step from
    the validator run step by literal command content, and recording every
    ``protected_paths`` it was called with for later assertion."""

    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs
        self.calls: list[tuple[list[str], tuple[str, ...]]] = []
        self._baseline_build_done = False
        self._candidate_build_attempt = 0

    def identity(self) -> dict[str, str]:
        return {"executor": "recording-native"}

    def verify_isolation(self, worktree: Path) -> ExecutionResult:
        del worktree
        return ExecutionResult(("cc",), 1, f"{NETWORK_PROBE_DENIAL_MARKER}\n", "")

    def run(self, command: list[str], worktree: Path, *, protected_paths: tuple[str, ...] = ()) -> ExecutionResult:
        del worktree
        self.calls.append((command, protected_paths))
        joined = " ".join(command)
        is_build = "cc " in joined or "cc -" in joined
        if is_build:
            if not self._baseline_build_done:
                self._baseline_build_done = True
                return ExecutionResult(tuple(command), 0, "", "")
            self._candidate_build_attempt += 1
            if "0  // missing semicolon" in joined or self._candidate_build_attempt == 1:
                # First candidate attempt: simulate a genuine compiler
                # syntax error (never a validator result).
                return ExecutionResult(tuple(command), 1, "", "validate.c:2: error: expected ';'\n")
            return ExecutionResult(tuple(command), 0, "", "")
        # Validator run step: baseline always observes the bug (exit 1);
        # the only candidate build that ever reaches this point is the
        # one that compiled cleanly (the fixed patch), which validates 0.
        return ExecutionResult(tuple(command), 1, "", "")


def test_native_compile_error_is_build_failed_never_validator_exit_one(tmp_path, monkeypatch) -> None:
    source_root, include_paths = _native_source_root(tmp_path)
    monkeypatch.setattr(benchmark_module, "ContainerExecutor", _RecordingNativeExecutor)
    monkeypatch.setattr(benchmark_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P2")
    monkeypatch.setattr(benchmark_module, "build_worktree", _copy_worktree_factory(tmp_path))
    monkeypatch.setattr(benchmark_module, "materialize_task_sources", lambda task: (source_root, include_paths))
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))

    result = benchmark_module.run_benchmark_task(
        _native_task(), FixtureModel(_BROKEN_PATCH), max_attempts=1, run_id="native-build-split"
    )
    receipt = json.loads(Path(result["receipt_json"]).read_text(encoding="utf-8"))

    attempt = receipt["attempts"][0]
    assert attempt["repaired_classification"]["classification"] == "build_failed"
    assert attempt["repaired_classification"]["reason"] == "compile_failed"
    assert attempt["outcome"].startswith("BUILD_FAILED: candidate compile failed")
    assert "validator_exit_one" not in attempt["outcome"]
    assert attempt["repaired_classification"]["classification"] != "validator_exit_one"


def test_native_executor_calls_all_carry_protected_paths_for_support_files(tmp_path, monkeypatch) -> None:
    source_root, include_paths = _native_source_root(tmp_path)
    executor_holder: dict[str, _RecordingNativeExecutor] = {}

    def _factory(*args, **kwargs):
        instance = _RecordingNativeExecutor(*args, **kwargs)
        executor_holder["executor"] = instance
        return instance

    monkeypatch.setattr(benchmark_module, "ContainerExecutor", _factory)
    monkeypatch.setattr(benchmark_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P2")
    monkeypatch.setattr(benchmark_module, "build_worktree", _copy_worktree_factory(tmp_path))
    monkeypatch.setattr(benchmark_module, "materialize_task_sources", lambda task: (source_root, include_paths))
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))

    benchmark_module.run_benchmark_task(
        _native_task(), FixtureModel(_GOOD_PATCH), max_attempts=1, run_id="native-protected-paths"
    )

    executor = executor_holder["executor"]
    assert len(executor.calls) >= 2
    for command, protected_paths in executor.calls:
        del command
        # SUPPORT_NOTES.txt is never the editable bug_path -- it must stay
        # protected on every single baseline/candidate executor call.
        assert "SUPPORT_NOTES.txt" in protected_paths
