"""Exercise observation through the actual benchmark API, not summary flags."""

import json
import tempfile
from pathlib import Path

import pytest

from each import benchmark
from each.attestation import verify_materials_root, verify_receipt
from each.executor.python_observer import PythonCase
from each.models.fixture import FixtureModel
from each.paths import worktrees_dir
from each.signing import public_key_path
from tests.adversarial._docker_guard import requires_colima_each


@requires_colima_each
@pytest.mark.parametrize("proposal,outcome", [
    ("def f(x): return x\n", "REPAIR_VERIFIED"),
    ("import os\nos._exit(0)\n", "REPAIRED_RUN_INCONCLUSIVE"),
    ("print('2 passed')\nimport os\nos._exit(0)\n", "REPAIRED_RUN_INCONCLUSIVE"),
    ("def f(x): return x + 2\n", "REPAIR_NOT_VERIFIED"),
])
def test_benchmark_observer_api(tmp_path, monkeypatch, proposal, outcome):
    # Imported fixtures never execute on the host. These are not utility tasks.
    monkeypatch.setenv("EACH_HOME", str(Path.home() / ".each" / "test-observer-api"))
    source_root = Path(tempfile.mkdtemp(dir=worktrees_dir()))
    original = "def f(x): return x + 1\n"
    (source_root / "api.py").write_text(original)
    monkeypatch.setattr(benchmark, "materialize_task_sources", lambda task: (source_root, ["api.py"]))
    monkeypatch.setattr(benchmark, "materialize_known_fix", lambda task: "not a target solution")
    task = benchmark.BenchmarkTask(
        task_id="harness-fixture-not-utility", repo="example/harness-fixture", license="MIT",
        pre_fix_sha="a" * 40, fix_sha="b" * 40, bug_path="api.py", test_paths=(),
        test_command=("trusted-host-json-v1",), problem_statement="Identity API.",
        observation_cases=(PythonCase("positive", "f", (3,), 3), PythonCase("regression", "f", (0,), 0)),
        proposal_format="full_source",
    )
    result = benchmark.run_benchmark_task(
        task, FixtureModel(f"BEGIN_SOURCE\n{proposal}END_SOURCE"), max_attempts=1,
    )
    assert result["outcome"] == outcome
    receipt_path = Path(result["receipt_json"])
    receipt = json.loads(receipt_path.read_text())
    assert verify_receipt(receipt, public_key_path().read_bytes())["status"] == "PASS"
    assert verify_materials_root(receipt, receipt_path.parent / "materials")["status"] == "PASS"
    assert receipt["attempts"][0]["baseline_classification"]["classification"] == "failed"
    assert receipt["auditSubjectSha256"]
