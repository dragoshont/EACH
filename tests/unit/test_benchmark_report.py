"""Unit tests for each.benchmark_report's aggregation and sanitized rendering.

Uses hand-built fixture receipts (not real container runs) to exercise the
aggregation/sanitization logic in isolation -- the real end-to-end pipeline
is already covered by tests/adversarial/test_benchmark_task.py.
"""

from __future__ import annotations

import json

from each.benchmark import BenchmarkExecutionError, BenchmarkTask
from each.benchmark_report import render_sanitized_markdown, run_suite

_TASK_A = BenchmarkTask(
    task_id="task-a",
    repo="org/repo-a",
    license="MIT",
    pre_fix_sha="a" * 40,
    fix_sha="b" * 40,
    bug_path="a.py",
    test_paths=("test_a.py",),
    test_command=("python", "-m", "pytest", "test_a.py"),
    problem_statement="a is broken",
)
_TASK_B = BenchmarkTask(
    task_id="task-b",
    repo="org/repo-b",
    license="BSD-3-Clause",
    pre_fix_sha="c" * 40,
    fix_sha="d" * 40,
    bug_path="b.py",
    test_paths=("test_b.py",),
    test_command=("python", "-m", "pytest", "test_b.py"),
    problem_statement="b is broken",
)


def _fake_receipt_with_flagged_audit(tmp_path, run_id: str) -> str:
    receipt = {
        "patchText": "--- fake ---",
        "assuranceLevel": "EACH-P2",
        "isolationEvidence": {"exit_code": 101},
        "audit": {
            "checks": {
                "exact-substring": {"status": "FLAG", "detail": "matched corpus entry"},
                "license-scan": {"status": "PASS"},
            },
            "toolVersions": {},
            "corpusRevision": "none",
        },
        "modelIdentity": {"modelId": "test/stub"},
    }
    path = tmp_path / f"{run_id}.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return str(path)


def test_run_suite_surfaces_real_audit_flags_not_an_empty_list(monkeypatch, tmp_path):
    """Regression test: auditFlags must read receipt['audit']['checks'],
    not receipt['audit'] itself -- otherwise a genuine FLAG is silently
    dropped from the aggregate report."""

    def fake_run_benchmark_task(task, model, *, max_attempts, run_id):
        del model, max_attempts
        receipt_json = _fake_receipt_with_flagged_audit(tmp_path, run_id)
        return {"task_id": task.task_id, "outcome": "REPAIR_VERIFIED", "receipt_json": receipt_json, "attempts": 1}

    monkeypatch.setattr("each.benchmark_report.run_benchmark_task", fake_run_benchmark_task)
    monkeypatch.setattr("each.benchmark_report.each_home", lambda: tmp_path)

    outcome = run_suite([_TASK_A], model=object(), report_id="test-report")
    report = outcome["report"]
    assert report["tasks"][0]["auditFlags"] == ["exact-substring"]


def test_a_per_task_materialization_failure_is_recorded_not_a_suite_crash(monkeypatch, tmp_path):
    def fake_run_benchmark_task(task, model, *, max_attempts, run_id):
        del model, max_attempts, run_id
        if task.task_id == "task-a":
            raise BenchmarkExecutionError("could not fetch: HTTP 404")
        receipt_json = _fake_receipt_with_flagged_audit(tmp_path, "task-b-ok")
        return {"task_id": task.task_id, "outcome": "REPAIR_VERIFIED", "receipt_json": receipt_json, "attempts": 1}

    monkeypatch.setattr("each.benchmark_report.run_benchmark_task", fake_run_benchmark_task)
    monkeypatch.setattr("each.benchmark_report.each_home", lambda: tmp_path)

    outcome = run_suite([_TASK_A, _TASK_B], model=object(), report_id="test-report-2")
    report = outcome["report"]
    assert report["taskCount"] == 2
    assert report["verifiedCount"] == 1
    assert report["tasks"][0]["outcome"].startswith("TASK_MATERIALIZATION_FAILED")
    assert report["tasks"][1]["outcome"] == "REPAIR_VERIFIED"


def test_a_per_task_materialization_failure_never_leaks_the_raw_exception_text(monkeypatch, tmp_path):
    """F3 regression: a materialization failure's exception message (dead
    repo URL, HTTP reason, pip install stderr) can contain arbitrary,
    potentially sensitive detail -- the public/sanitized suite report must
    only ever record the bounded "TASK_MATERIALIZATION_FAILED" class, never
    that raw text verbatim."""
    _sensitive_sentinel = "SENTINEL-PRIVATE-DETAIL-should-never-be-exported-abc123"

    def fake_run_benchmark_task(task, model, *, max_attempts, run_id):
        del model, max_attempts, run_id
        raise BenchmarkExecutionError(f"could not fetch repo tarball: {_sensitive_sentinel}")

    monkeypatch.setattr("each.benchmark_report.run_benchmark_task", fake_run_benchmark_task)
    monkeypatch.setattr("each.benchmark_report.each_home", lambda: tmp_path)

    outcome = run_suite([_TASK_A], model=object(), report_id="test-report-leak-check")
    report = outcome["report"]
    assert report["tasks"][0]["outcome"] == "TASK_MATERIALIZATION_FAILED"
    assert _sensitive_sentinel not in json.dumps(report)
    assert _sensitive_sentinel not in render_sanitized_markdown(report)


def test_report_is_actually_written_to_disk_under_each_home(monkeypatch, tmp_path):
    def fake_run_benchmark_task(task, model, *, max_attempts, run_id):
        del task, model, max_attempts
        receipt_json = _fake_receipt_with_flagged_audit(tmp_path, run_id)
        return {"task_id": "task-a", "outcome": "REPAIR_VERIFIED", "receipt_json": receipt_json, "attempts": 1}

    monkeypatch.setattr("each.benchmark_report.run_benchmark_task", fake_run_benchmark_task)
    monkeypatch.setattr("each.benchmark_report.each_home", lambda: tmp_path)

    outcome = run_suite([_TASK_A], model=object(), report_id="test-report-3")
    report_path = outcome["report_path"]
    assert (tmp_path / "benchmarks" / "test-report-3.json").exists()
    on_disk = json.loads((tmp_path / "benchmarks" / "test-report-3.json").read_text())
    assert on_disk == outcome["report"]
    assert report_path.endswith("test-report-3.json")


def test_a_context_budget_rejection_is_reported_as_zero_generation_calls_not_one(monkeypatch, tmp_path):
    """Regression test for the user's explicit correction: a task rejected by
    the context-budget preflight before any model.complete() call must be
    reported as 0 real generation calls and generationEligible=False, not
    folded into the same denominator as a task that genuinely reached the
    model."""

    def _write_receipt(run_id: str, attempts: list[dict]) -> str:
        receipt = {
            "patchText": "",
            "assuranceLevel": "EACH-P0",
            "isolationEvidence": {"exit_code": 101},
            "audit": {"checks": {}, "toolVersions": {}, "corpusRevision": "none"},
            "modelIdentity": {"modelId": "test/stub"},
            "attempts": attempts,
        }
        path = tmp_path / f"{run_id}.json"
        path.write_text(json.dumps(receipt), encoding="utf-8")
        return str(path)

    def fake_run_benchmark_task(task, model, *, max_attempts, run_id):
        del model, max_attempts
        if task.task_id == "task-a":
            # Context-budget-ineligible: one loop iteration, zero real
            # model.complete() calls.
            receipt_json = _write_receipt(
                run_id,
                [{"attempt": 1, "outcome": "BUILDER_CONTEXT_BUDGET_EXCEEDED: too large", "generation_attempted": False}],
            )
            return {
                "task_id": task.task_id,
                "outcome": "BUILDER_CONTEXT_BUDGET_EXCEEDED: too large",
                "receipt_json": receipt_json,
                "attempts": 1,
            }
        # Genuinely eligible: reached generation at least once.
        receipt_json = _write_receipt(
            run_id, [{"attempt": 1, "outcome": "REPAIR_VERIFIED", "generation_attempted": True}]
        )
        return {"task_id": task.task_id, "outcome": "REPAIR_VERIFIED", "receipt_json": receipt_json, "attempts": 1}

    monkeypatch.setattr("each.benchmark_report.run_benchmark_task", fake_run_benchmark_task)
    monkeypatch.setattr("each.benchmark_report.each_home", lambda: tmp_path)

    outcome = run_suite([_TASK_A, _TASK_B], model=object(), report_id="test-report-eligibility")
    report = outcome["report"]
    task_a = next(t for t in report["tasks"] if t["taskId"] == "task-a")
    task_b = next(t for t in report["tasks"] if t["taskId"] == "task-b")

    assert task_a["generationCallCount"] == 0
    assert task_a["generationEligible"] is False
    assert task_b["generationCallCount"] == 1
    assert task_b["generationEligible"] is True
    # Overall catalog coverage is still 2, but only 1 task was ever
    # generation-eligible -- the honest repair-utility denominator.
    assert report["taskCount"] == 2
    assert report["eligibleCount"] == 1
    assert report["verifiedCount"] == 1

    markdown = render_sanitized_markdown(report)
    assert "Generation-eligible" in markdown
    assert "1 / 2" in markdown  # eligible / taskCount


def test_sanitized_markdown_contains_no_patch_or_audit_content():
    report = {
        "reportId": "r1",
        "taskCount": 1,
        "verifiedCount": 1,
        "tasks": [
            {
                "taskId": "task-a",
                "repo": "org/repo-a",
                "license": "MIT",
                "outcome": "REPAIR_VERIFIED",
                "attempts": 1,
                "assuranceLevel": "EACH-P2",
            }
        ],
    }
    markdown = render_sanitized_markdown(report)
    assert "task-a" in markdown
    assert "REPAIR_VERIFIED" in markdown
    assert "--- fake ---" not in markdown
    assert "patch" not in markdown.lower() or "No patch text" in markdown
    assert "No patch text, model prompt/completion content, or known-fix source" in markdown
