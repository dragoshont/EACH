"""Adversarial/end-to-end evidence for M6's native-language (C/C++/Rust)
dispatch in run_benchmark_task: a real historical-style C repair is
materialized via the explicit-file-set path (never a whole-repo tarball),
compiled and validated through the real no-network
``each-benchmark-native-runtime`` container, and classified by exit code
(never pytest-summary-line parsing).

Network access is stubbed out (monkeypatched ``fetch_file``) so this test
is hermetic and fast; it still exercises the real container executor via
Colima, exactly like tests/adversarial/test_benchmark_task.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import each.benchmark as benchmark_module
from each.benchmark import BenchmarkTask, run_benchmark_task
from tests.adversarial._docker_guard import requires_colima_each

_BUGGY_CLAMP_C = (
    "int clamp(int value, int lo, int hi) {\n"
    "    if (value > hi) return hi;\n"
    "    return value;\n"
    "}\n"
)
_FIXED_CLAMP_C = (
    "int clamp(int value, int lo, int hi) {\n"
    "    if (value > hi) return hi;\n"
    "    if (value < lo) return lo;\n"
    "    return value;\n"
    "}\n"
)
_VALIDATOR_C = (
    "#include <stdio.h>\n"
    "int clamp(int value, int lo, int hi);\n"
    "int main(void) {\n"
    "    if (clamp(-5, 0, 10) != 0) { fprintf(stderr, \"lower bound not enforced\\n\"); return 1; }\n"
    "    return 0;\n"
    "}\n"
)
_CORRECT_PATCH = """BEGIN_PATCH
--- a/clamp.c
+++ b/clamp.c
@@ -1,4 +1,5 @@
 int clamp(int value, int lo, int hi) {
     if (value > hi) return hi;
+    if (value < lo) return lo;
     return value;
 }
END_PATCH
"""

_TASK = BenchmarkTask(
    task_id="synthetic-clamp-native-smoke",
    repo="example/clamp-native-lib",
    license="MIT",
    language="C",
    pre_fix_sha="deadbeef" * 5,
    fix_sha="cafebabe" * 5,
    bug_path="clamp.c",
    test_paths=(),
    test_command=("cc -std=c99 -Wall clamp.c validate.c -o validate && ./validate",),
    problem_statement="clamp() does not enforce its lower bound.",
    validator_files=(("validate.c", _VALIDATOR_C),),
)


def _stub_fetch_file(repo: str, sha: str, path: str, *, timeout: int = 20) -> str:
    del repo, timeout
    if path == _TASK.bug_path:
        return _FIXED_CLAMP_C if sha == _TASK.fix_sha else _BUGGY_CLAMP_C
    raise benchmark_module.BenchmarkExecutionError(f"no stub content for {path!r}")


class _StubRepairModel:
    model_id = "test/stub-repair-model"

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.seen_prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.seen_prompts.append(prompt)
        return self._replies[min(len(self.seen_prompts) - 1, len(self._replies) - 1)]

    def identity(self) -> dict[str, str]:
        return {"modelId": self.model_id, "implementationModule": __name__, "implementationSha256": ""}


@requires_colima_each
def test_a_real_historical_style_c_repair_is_verified_through_the_native_image(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(benchmark_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    model = _StubRepairModel([_CORRECT_PATCH])
    result = run_benchmark_task(_TASK, model, max_attempts=2)
    assert result["outcome"] == "REPAIR_VERIFIED"
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["assuranceLevel"] == "EACH-P2"
    assert receipt["attempts"][0]["outcome"] == "REPAIR_VERIFIED"
    # The native path must never invoke pytest-summary classification.
    assert "passed" not in json.dumps(receipt["attempts"][0]["repaired_result"])


@requires_colima_each
def test_an_unfixed_native_baseline_genuinely_fails_through_the_real_container(monkeypatch, tmp_path) -> None:
    """Regression: the native classifier must report the real baseline exit
    code (1, validator failure), not silently pass or misclassify a non-zero
    exit as inconclusive."""
    monkeypatch.setattr(benchmark_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    model = _StubRepairModel(["this completion has no patch markers at all"])
    result = run_benchmark_task(_TASK, model, max_attempts=1)
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    baseline = receipt["attempts"][0]["baseline_classification"]
    assert baseline["classification"] == "fail"
    assert baseline["exit_code"] == 1
