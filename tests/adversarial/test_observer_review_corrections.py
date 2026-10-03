"""Actual public synthetic forgery/recursion controls; no target generation."""

import json
import tempfile
from pathlib import Path

import pytest

from each import benchmark
from each.attestation import verify_materials_root, verify_receipt
from each.executor.container import ContainerExecutor
from each.executor.python_observer import PythonCase, observe_python
from each.models.fixture import FixtureModel
from each.paths import worktrees_dir
from each.signing import public_key_path
from tests.adversarial._docker_guard import requires_colima_each

pytestmark = requires_colima_each

# Public self-authored harness attack fixtures, not private target patches.
PROPOSALS = {
    "valid-json-early-exit": "import os\nprint('{\"value\":1}', flush=True)\nos._exit(0)\n",
    "serializer-substitution": (
        "import json\njson.dumps = lambda *args, **kwargs: '{\"value\":1}'\n"
        "def f(x):\n    return 999\n"
    ),
    "deep-json": (
        "import os\nprint('{\"value\":' + '[' * 20000 + '0' + ']' * 20000 + '}', flush=True)\n"
        "os._exit(0)\n"
    ),
    "ordinary-return": "def f(x):\n    return x\n",
}


@pytest.fixture(autouse=True)
def owned_store(monkeypatch):
    root = Path(tempfile.mkdtemp(prefix=".each-observer-review-", dir=Path.home()))
    root.chmod(0o700)
    monkeypatch.setenv("EACH_HOME", str(root))


@pytest.mark.parametrize("kind", list(PROPOSALS))
def test_actual_response_evidence_cannot_authenticate_api_return(kind):
    root = Path(tempfile.mkdtemp(prefix="observer-review-", dir=worktrees_dir()))
    (root / "api.py").write_text(PROPOSALS[kind])
    result = observe_python(
        ContainerExecutor(), root, "api.py", (PythonCase("case", "f", (1,), 1),),
    )
    evidence = json.loads(result.stdout)
    assert evidence["observationScope"] == "sandboxed-process-response"
    assert evidence["apiReturnAuthenticated"] is False
    assert result.exit_code == (2 if kind == "deep-json" else 0)
    assert evidence["completedCases"] == (0 if kind == "deep-json" else 1)


@pytest.mark.parametrize("kind", list(PROPOSALS))
def test_actual_benchmark_never_verifies_api_from_response_only(monkeypatch, kind):
    root = Path(tempfile.mkdtemp(prefix="benchmark-review-", dir=worktrees_dir()))
    (root / "api.py").write_text("def f(x): return x + 1\n")
    monkeypatch.setattr(benchmark, "materialize_task_sources", lambda task: (root, ["api.py"]))
    monkeypatch.setattr(benchmark, "materialize_known_fix", lambda task: "not Builder input")
    task = benchmark.BenchmarkTask(
        task_id="public-review-control", repo="example/public-harness", license="Apache-2.0",
        pre_fix_sha="a" * 40, fix_sha="b" * 40, bug_path="api.py", test_paths=(),
        test_command=("sandboxed-process-response-v1",), problem_statement="Identity API contract.",
        observation_cases=(PythonCase("case", "f", (1,), 1),), proposal_format="full_source",
    )
    result = benchmark.run_benchmark_task(
        task, FixtureModel("BEGIN_SOURCE\n" + PROPOSALS[kind] + "END_SOURCE"), max_attempts=1,
    )
    assert result["outcome"] == "REPAIRED_RUN_INCONCLUSIVE"
    path = Path(result["receipt_json"])
    receipt = json.loads(path.read_text())
    assert receipt["selectedAttempt"] == 1
    assert receipt["rawCompletion"] == "BEGIN_SOURCE\n" + PROPOSALS[kind] + "END_SOURCE"
    assert receipt["patchText"]
    classification = receipt["attempts"][0]["repaired_classification"]
    assert classification["apiReturnAuthenticated"] is False
    if kind == "deep-json":
        assert classification["evidence"]["completedCases"] == 0
    else:
        assert classification["reason"] == "api_return_authentication_unavailable"
    assert verify_receipt(receipt, public_key_path().read_bytes())["status"] == "PASS"
    assert verify_materials_root(receipt, path.parent / "materials")["status"] == "PASS"
