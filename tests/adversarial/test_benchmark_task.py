"""Adversarial/end-to-end evidence for M6's run_benchmark_task:

- the real pytest-enabled pinned container actually verifies a genuine
  repair end-to-end (not just the M1 unittest-based toy fixture);
- the hidden-fix discipline structurally holds: the known historical fix
  (fetched only at ``fix_sha``) never leaks into the prompt, any attempt's
  raw_completion, or the receipt before the receipt has already been
  written -- it is only used, after the fact, to compute a hash for the
  human report.

Network access to GitHub is stubbed out (monkeypatched ``fetch_file``) so
this test is hermetic and fast; it still exercises the real no-network
container executor via Colima, exactly like tests/adversarial/test_bakeoff.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import each.benchmark as benchmark_module
from each.benchmark import BenchmarkTask, run_benchmark_task
from tests.adversarial._docker_guard import requires_colima_each

_BUGGY_SOURCE = 'def clamp(value, lo, hi):\n    if value > hi:\n        return hi\n    return value\n'
_FIXED_SOURCE = (
    'def clamp(value, lo, hi):\n    if value > hi:\n        return hi\n    if value < lo:\n        return lo\n    return value\n'
)
_TEST_SOURCE = (
    "from clamp import clamp\n\n\ndef test_clamp_enforces_the_lower_bound():\n    assert clamp(-5, 0, 10) == 0\n"
)
_CORRECT_PATCH = """BEGIN_PATCH
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

_TASK = BenchmarkTask(
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
    del repo, timeout
    if path == _TASK.bug_path:
        return _FIXED_SOURCE if sha == _TASK.fix_sha else _BUGGY_SOURCE
    if path in _TASK.test_paths:
        return _TEST_SOURCE
    raise benchmark_module.BenchmarkExecutionError(f"no stub content for {path!r}")


def _stub_extract_repo_tree(repo: str, sha: str, dest, *, timeout: int = 60):
    del repo, sha, timeout
    dest.mkdir(parents=True, exist_ok=True)
    (dest / _TASK.bug_path).write_text(_BUGGY_SOURCE, encoding="utf-8")
    return dest


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
def test_a_real_historical_style_repair_is_verified_through_the_pytest_image(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(benchmark_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    monkeypatch.setattr(benchmark_module, "_extract_repo_tree", _stub_extract_repo_tree)
    model = _StubRepairModel([_CORRECT_PATCH])
    result = run_benchmark_task(_TASK, model, max_attempts=2)
    assert result["outcome"] == "REPAIR_VERIFIED"
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["assuranceLevel"] == "EACH-P2"
    assert receipt["attempts"][0]["outcome"] == "REPAIR_VERIFIED"


@requires_colima_each
def test_exhausting_all_attempts_on_a_rejected_patch_reports_that_real_outcome_not_a_false_repair_not_verified(
    monkeypatch, tmp_path
) -> None:
    """Regression test: if every attempt is exhausted on a malformed/rejected
    completion (never reaching a classified repaired-test run), the receipt's
    final outcome must be the real last attempt's own outcome (e.g.
    "PATCH_REJECTED: ..."), not a sentinel "REPAIR_NOT_VERIFIED" that falsely
    implies a patch was applied and the repaired tests were run and failed."""
    monkeypatch.setattr(benchmark_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    monkeypatch.setattr(benchmark_module, "_extract_repo_tree", _stub_extract_repo_tree)
    model = _StubRepairModel(["this completion has no patch markers at all"])
    result = run_benchmark_task(_TASK, model, max_attempts=2)
    assert result["outcome"].startswith("PATCH_REJECTED")
    assert result["outcome"] != "REPAIR_NOT_VERIFIED"
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["outcome"].startswith("PATCH_REJECTED")
    assert len(receipt["attempts"]) == 2
    assert all(a["outcome"].startswith("PATCH_REJECTED") for a in receipt["attempts"])
    # The baseline test run is a real container execution for each attempt
    # that got this far (preflight budget check passed); confirm that
    # evidence is preserved even though no patch ever applied.
    assert receipt["baselineResult"]


@requires_colima_each
def test_does_not_mix_an_earlier_attempts_patch_with_a_later_rejection(monkeypatch, tmp_path) -> None:
    """F4 regression: if an EARLIER attempt applies a patch and runs the
    repaired tests (but does not verify, so the loop retries) and a LATER
    attempt is rejected before even parsing a patch, the final receipt must
    report that LATER attempt's own outcome/prompt/raw_completion together
    with ITS OWN (empty) patch_text/touched_paths/repaired_result -- never
    a receipt mixing the newest rejection's outcome with an earlier
    attempt's stale applied-but-unverified patch."""
    monkeypatch.setattr(benchmark_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    monkeypatch.setattr(benchmark_module, "_extract_repo_tree", _stub_extract_repo_tree)
    _applies_but_does_not_fix = """BEGIN_PATCH
--- a/clamp.py
+++ b/clamp.py
@@ -1,4 +1,5 @@
 def clamp(value, lo, hi):
     if value > hi:
         return hi
+    # not fixing the lower bound here
     return value
END_PATCH
"""
    model = _StubRepairModel([_applies_but_does_not_fix, "this completion has no patch markers at all"])
    result = run_benchmark_task(_TASK, model, max_attempts=2)
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["attempts"][0]["outcome"] == "REPAIR_NOT_VERIFIED"
    assert receipt["attempts"][1]["outcome"].startswith("PATCH_REJECTED")

    assert result["outcome"].startswith("PATCH_REJECTED")
    assert receipt["outcome"].startswith("PATCH_REJECTED")
    assert receipt["rawCompletion"] == "this completion has no patch markers at all"
    assert receipt["patchText"] == ""
    assert receipt["touchedPaths"] == []
    assert receipt["repairedResult"] == {}


@requires_colima_each
def test_the_known_fix_content_never_leaks_into_the_prompt_or_any_attempt(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(benchmark_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    monkeypatch.setattr(benchmark_module, "_extract_repo_tree", _stub_extract_repo_tree)
    model = _StubRepairModel([_CORRECT_PATCH])
    result = run_benchmark_task(_TASK, model, max_attempts=2)

    # The fix content differs from the buggy content only by the inserted
    # lower-bound branch; assert that exact inserted line never appears in
    # what the model was shown (only the pre-fix buggy source should).
    fix_only_fingerprint = "if value < lo:"
    for prompt in model.seen_prompts:
        assert fix_only_fingerprint not in prompt, "known fix leaked into the model's prompt before generation"

    receipt = json.loads(Path(result["receipt_json"]).read_text())
    # The model's own correct patch legitimately reintroduces this line in
    # its *completion* (that's the fix it produced) and in the final patch
    # text -- that is not a leak. What must never happen is the known fix
    # appearing in the *source shown to the model*, i.e. embedded in the
    # prompt field recorded for any attempt.
    for attempt in receipt["attempts"]:
        assert fix_only_fingerprint not in attempt["prompt"]

    # known_fix_sha256 is a reporting-only, post-hoc value: assert it's
    # present and distinct from a hash of the buggy source (proving it
    # really was computed from fix_sha content, not just echoing the bug).
    import hashlib

    assert result["known_fix_sha256"] == hashlib.sha256(_FIXED_SOURCE.encode("utf-8")).hexdigest()
    assert result["known_fix_sha256"] != hashlib.sha256(_BUGGY_SOURCE.encode("utf-8")).hexdigest()


@requires_colima_each
def test_materialize_known_fix_is_only_ever_called_after_the_receipt_is_written(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(benchmark_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    monkeypatch.setattr(benchmark_module, "_extract_repo_tree", _stub_extract_repo_tree)
    calls: list[str] = []
    real_write = benchmark_module.Receipt.write

    def _tracking_write(self, *args, **kwargs):
        calls.append("receipt.write")
        return real_write(self, *args, **kwargs)

    real_materialize_known_fix = benchmark_module.materialize_known_fix

    def _tracking_materialize_known_fix(task):
        calls.append("materialize_known_fix")
        return real_materialize_known_fix(task)

    monkeypatch.setattr(benchmark_module.Receipt, "write", _tracking_write)
    monkeypatch.setattr(benchmark_module, "materialize_known_fix", _tracking_materialize_known_fix)

    model = _StubRepairModel([_CORRECT_PATCH])
    run_benchmark_task(_TASK, model, max_attempts=2)

    assert "materialize_known_fix" in calls
    assert calls.index("receipt.write") < calls.index("materialize_known_fix")


@requires_colima_each
def test_audit_rejection_is_terminal_and_runs_only_once_against_a_validated_candidate(monkeypatch, tmp_path) -> None:
    """Regression for the coordinator-identified M4 wiring gap: run_audit
    must be called exactly once (only after a REPAIR_VERIFIED candidate
    exists), and a FAIL verdict must end the run as REPAIR_REJECTED_AUDIT
    without any further Builder call, even though max_attempts allows more.
    Mirrors tests/adversarial/test_bakeoff.py::test_audit_match_is_terminal_without_builder_feedback.
    """
    monkeypatch.setattr(benchmark_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    monkeypatch.setattr(benchmark_module, "_extract_repo_tree", _stub_extract_repo_tree)

    forbidden_hint = "FORBIDDEN_POST_GENERATION_SOURCE_MATCH"
    model = _StubRepairModel([_CORRECT_PATCH, _CORRECT_PATCH, _CORRECT_PATCH])
    audited: list[str] = []

    def discovered_match(source: str, *, corpus: list[str] | None = None) -> dict[str, object]:
        assert source  # only ever called with the real repaired source, never ""
        audited.append(source)
        return {
            "checks": {"exact-substring": {"status": "FAIL", "sourceHint": forbidden_hint}},
            "toolVersions": {},
            "corpusRevision": "test",
        }

    monkeypatch.setattr(benchmark_module, "run_audit", discovered_match)
    result = run_benchmark_task(_TASK, model, max_attempts=3)

    assert result["outcome"] == "REPAIR_REJECTED_AUDIT"
    # Exactly one Builder call: audit is terminal, not pre-generation
    # feedback that could trigger a second attempt.
    assert len(model.seen_prompts) == 1
    assert len(audited) == 1

    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["attempts"][0]["outcome"] == "REPAIR_REJECTED_AUDIT"
    assert receipt["audit"]["checks"]["exact-substring"]["status"] == "FAIL"
    assert all(forbidden_hint not in prompt for prompt in model.seen_prompts)


@requires_colima_each
def test_audit_is_never_invoked_before_a_candidate_passes_tests(monkeypatch, tmp_path) -> None:
    """Regression: a patch that is syntactically valid but does not make the
    failing test pass must never trigger an audit call at all -- audit is a
    terminal gate only on a REPAIR_VERIFIED candidate, never pre-generation
    feedback for a still-failing one."""
    monkeypatch.setattr(benchmark_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    monkeypatch.setattr(benchmark_module, "_extract_repo_tree", _stub_extract_repo_tree)

    # A no-op patch: applies cleanly, but leaves the bug unfixed, so the
    # test still fails after "repair" -> REPAIR_NOT_VERIFIED, never audited.
    noop_patch = """BEGIN_PATCH
--- a/clamp.py
+++ b/clamp.py
@@ -1,4 +1,4 @@
-def clamp(value, lo, hi):
+def clamp(value, lo, hi):  # unchanged
     if value > hi:
         return hi
     return value
END_PATCH
"""
    model = _StubRepairModel([noop_patch])
    audit_calls = []
    real_run_audit = benchmark_module.run_audit

    def _tracking_run_audit(*args, **kwargs):
        audit_calls.append((args, kwargs))
        return real_run_audit(*args, **kwargs)

    monkeypatch.setattr(benchmark_module, "run_audit", _tracking_run_audit)
    result = run_benchmark_task(_TASK, model, max_attempts=1)

    assert result["outcome"] == "REPAIR_NOT_VERIFIED"
    assert audit_calls == []
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["audit"]["result"] == "UNAVAILABLE"


@requires_colima_each
def test_context_budget_preflight_skips_the_real_baseline_container_run(monkeypatch, tmp_path) -> None:
    """When the model exposes an MLX-style ``check_context_budget`` preflight
    (not part of the abstract RepairModel interface, but duck-typed for any
    backend that has it), run_benchmark_task must consult it BEFORE spending
    a real container baseline execution -- not merely before model.complete()
    -- so a task that can never reach generation doesn't waste a real
    executor run, and so an unrelated container/infrastructure hiccup on
    that wasted run can never masquerade as the true, more fundamental
    BUILDER_CONTEXT_BUDGET_EXCEEDED reason (regression for a gap found by
    independent adversarial review: the budget check previously only ran
    after the baseline container execution had already happened).
    """
    monkeypatch.setattr(benchmark_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    monkeypatch.setattr(benchmark_module, "_extract_repo_tree", _stub_extract_repo_tree)

    executor_run_calls = []
    real_executor_run = benchmark_module.ContainerExecutor.run

    def _tracking_run(self, *args, **kwargs):
        executor_run_calls.append((args, kwargs))
        return real_executor_run(self, *args, **kwargs)

    monkeypatch.setattr(benchmark_module.ContainerExecutor, "run", _tracking_run)

    class _PreflightOverBudgetModel:
        model_id = "test/preflight-over-budget-model"

        def check_context_budget(self, prompt: str) -> tuple[str, int]:
            del prompt
            raise benchmark_module.ContextBudgetExceeded(
                "rendered prompt (5000 tokens) + reserved output (512) exceeds max_position_embeddings (2048)"
            )

        def complete(self, prompt: str) -> str:
            raise AssertionError("complete() must never be called once the preflight check rejects the prompt")

        def identity(self) -> dict[str, str]:
            return {"modelId": self.model_id, "implementationModule": __name__, "implementationSha256": ""}

    model = _PreflightOverBudgetModel()
    result = run_benchmark_task(_TASK, model, max_attempts=3)

    assert result["outcome"].startswith("BUILDER_CONTEXT_BUDGET_EXCEEDED")
    assert result["attempts"] == 1
    # verify_isolation() legitimately uses executor.run() once per task (the
    # real no-egress network probe, unrelated to the budget decision); what
    # must never happen is the baseline *test-command* run this preflight
    # exists to avoid wasting.
    baseline_run_calls = [
        call for call in executor_run_calls if "pytest" in " ".join(call[0][0])
    ]
    assert baseline_run_calls == []

    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["outcome"].startswith("BUILDER_CONTEXT_BUDGET_EXCEEDED")
    assert receipt["baselineResult"] == {}
    assert receipt["audit"]["result"] == "UNAVAILABLE"



    """Regression for the measured M6 context-overflow defect: when the
    model's own context-budget policy rejects the (already smallest,
    diff-blind) excerpt before generation, run_benchmark_task must record a
    distinct BUILDER_CONTEXT_BUDGET_EXCEEDED outcome -- never silently fold
    it into REPAIR_NOT_VERIFIED -- and must not retry (a retry only grows
    the prompt via _RETRY_SUFFIX, which cannot help an already-oversized
    excerpt fit), proving the rejection happens before any real generate.
    """
    monkeypatch.setattr(benchmark_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(benchmark_module, "fetch_file", _stub_fetch_file)
    monkeypatch.setattr(benchmark_module, "_extract_repo_tree", _stub_extract_repo_tree)

    class _OverBudgetModel:
        model_id = "test/over-budget-model"

        def __init__(self) -> None:
            self.generate_calls = 0

        def complete(self, prompt: str) -> str:
            # Simulates a real RepairModel backend's own pre-generation
            # budget check (see each.models.mlx_model.check_context_budget)
            # rejecting before ever invoking the real backend generate().
            del prompt
            raise benchmark_module.ContextBudgetExceeded(
                "rendered prompt (5000 tokens) + reserved output (512) exceeds max_position_embeddings (2048)"
            )

        def identity(self) -> dict[str, str]:
            return {"modelId": self.model_id, "implementationModule": __name__, "implementationSha256": ""}

    model = _OverBudgetModel()
    result = run_benchmark_task(_TASK, model, max_attempts=3)

    assert result["outcome"].startswith("BUILDER_CONTEXT_BUDGET_EXCEEDED")
    assert result["attempts"] == 1  # terminal on the first attempt; never retried

    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["outcome"].startswith("BUILDER_CONTEXT_BUDGET_EXCEEDED")
    assert len(receipt["attempts"]) == 1
    assert receipt["attempts"][0]["raw_completion"] == ""
    assert receipt["audit"]["result"] == "UNAVAILABLE"


