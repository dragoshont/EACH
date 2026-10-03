from __future__ import annotations

import json
import subprocess
from pathlib import Path

import each.bakeoff as bakeoff_module
import each.receipt as receipt_module
from each.executor.base import ExecutionResult
from each.executor.container import NETWORK_PROBE_DENIAL_MARKER
from each.models.fixture import FixtureModel

PATCH = """BEGIN_PATCH
--- a/src/greet.py
+++ b/src/greet.py
@@ -1,2 +1,2 @@
 def greet(name: str) -> str:
-    return "Hell, " + name
+    return "Hello, " + name
END_PATCH
"""


class _FakeExecutor:
    def __init__(self, *args, **kwargs) -> None:
        self._calls = 0

    def identity(self) -> dict[str, str]:
        return {"executor": "fake-bakeoff"}

    def verify_isolation(self, worktree: Path) -> ExecutionResult:
        del worktree
        return ExecutionResult(("python",), 1, f"{NETWORK_PROBE_DENIAL_MARKER}\n", "")

    def run(self, command: list[str], worktree: Path) -> ExecutionResult:
        del command, worktree
        self._calls += 1
        if self._calls == 1:
            return ExecutionResult(("pytest",), 1, "1 failed in 0.01s\n", "")
        return ExecutionResult(("pytest",), 0, "1 passed in 0.01s\n", "")


def _fake_build_worktree_factory(tmp_path: Path):
    counter = {"value": 0}

    def _fake_build_worktree(source_root: Path, include_paths: list[str], dest: Path | None = None):
        counter["value"] += 1
        worktree = dest or (tmp_path / f"worktree-{counter['value']}")
        for rel in include_paths:
            src = source_root / rel
            target = worktree / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(src.read_bytes())
        return worktree, {rel: "hash" for rel in include_paths}

    return _fake_build_worktree


def _run_bakeoff(tmp_path: Path, monkeypatch) -> dict[str, object]:
    monkeypatch.setattr(bakeoff_module, "ContainerExecutor", _FakeExecutor)
    monkeypatch.setattr(bakeoff_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P2")
    monkeypatch.setattr(bakeoff_module, "build_worktree", _fake_build_worktree_factory(tmp_path))
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))
    return bakeoff_module.run_model_bakeoff(FixtureModel(PATCH), max_attempts=1, run_id="git-provenance-bakeoff")


def test_real_bakeoff_receipt_records_the_current_harness_commit_and_dirty_state(tmp_path, monkeypatch) -> None:
    result = _run_bakeoff(tmp_path, monkeypatch)
    receipt = json.loads(Path(result["receipt_json"]).read_text(encoding="utf-8"))
    expected_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=receipt_module.repo_root(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    expected_dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=receipt_module.repo_root(),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    assert receipt["producerCommit"] == expected_commit
    assert receipt["producerDirty"] == expected_dirty


def test_receipt_records_explicit_unknown_commit_when_git_metadata_is_unavailable(tmp_path, monkeypatch) -> None:
    real_run = receipt_module.subprocess.run

    def _raising_run(*args, **kwargs):
        if args and list(args[0])[:2] == ["git", "rev-parse"]:
            raise OSError("git unavailable")
        return real_run(*args, **kwargs)

    monkeypatch.setattr(receipt_module.subprocess, "run", _raising_run)
    result = _run_bakeoff(tmp_path, monkeypatch)
    receipt = json.loads(Path(result["receipt_json"]).read_text(encoding="utf-8"))
    assert receipt["producerCommit"] == "UNKNOWN"
    assert receipt["producerDirty"] == "UNKNOWN"
