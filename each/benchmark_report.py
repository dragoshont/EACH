"""M6 benchmark-suite execution and sanitized report generation.

Runs a list of :class:`~each.benchmark.BenchmarkTask` through
:func:`~each.benchmark.run_benchmark_task` and aggregates the mandate's
required metrics (repair, provenance, isolation) into one private JSON
report plus a conservative sanitized Markdown summary suitable for public
publication (no source code, no patch text, no model-identifying
internals beyond the already-public model id, no known-fix content).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from each.benchmark import BenchmarkExecutionError, BenchmarkTask, run_benchmark_task
from each.models.base import RepairModel
from each.paths import each_home


def run_suite(
    tasks: list[BenchmarkTask], model: RepairModel, *, max_attempts: int = 3, report_id: str | None = None
) -> dict[str, Any]:
    """Run every task in ``tasks`` against ``model`` and return an aggregate report.

    A per-task materialization/network failure (dead link, rate limit) is
    recorded as a documented failure for that task, not a crash of the
    whole suite -- the mandate requires failures to be reported, not hidden.
    """
    report_id = report_id or f"benchmark-suite-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    task_results: list[dict[str, Any]] = []

    for task in tasks:
        try:
            result = run_benchmark_task(task, model, max_attempts=max_attempts, run_id=f"{report_id}-{task.task_id}")
            receipt = json.loads(Path(result["receipt_json"]).read_text(encoding="utf-8"))
            receipt_attempts = receipt.get("attempts") or []
            generation_call_count = sum(
                1 for attempt in receipt_attempts if attempt.get("generation_attempted")
            )
            task_results.append(
                {
                    "taskId": task.task_id,
                    "repo": task.repo,
                    "license": task.license,
                    "language": task.language,
                    "outcome": result["outcome"],
                    "attempts": result["attempts"],
                    # A preflight/complete() context-budget rejection consumes
                    # a loop iteration ("attempts") but never actually calls
                    # the model: counting it as a genuine generation attempt
                    # would misrepresent context-ineligible tasks as real
                    # repair-capability evidence. generationCallCount is the
                    # number of times model.complete() genuinely ran and
                    # returned for this task (0 for an eligibility rejection).
                    "generationCallCount": generation_call_count,
                    "generationEligible": generation_call_count > 0,
                    "patchSizeBytes": len(receipt.get("patchText", "")),
                    "assuranceLevel": receipt.get("assuranceLevel"),
                    "isolationNetworkProbe": receipt.get("isolationEvidence", {}).get("exit_code"),
                    "auditFlags": [
                        check
                        for check, outcome in (receipt.get("audit") or {}).get("checks", {}).items()
                        if isinstance(outcome, dict) and outcome.get("status") == "FLAG"
                    ],
                    "modelId": receipt.get("modelIdentity", {}).get("modelId"),
                    "receiptJson": result["receipt_json"],
                    "knownFixSha256": result.get("known_fix_sha256"),
                }
            )
        except BenchmarkExecutionError as exc:
            task_results.append(
                {
                    "taskId": task.task_id,
                    "repo": task.repo,
                    "license": task.license,
                    "language": task.language,
                    "outcome": f"TASK_MATERIALIZATION_FAILED: {exc}",
                    "attempts": 0,
                    "generationCallCount": 0,
                    "generationEligible": False,
                }
            )

    verified = sum(1 for r in task_results if r["outcome"] == "REPAIR_VERIFIED")
    eligible = sum(1 for r in task_results if r["generationEligible"])
    report = {
        "reportId": report_id,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "taskCount": len(tasks),
        "verifiedCount": verified,
        # Honest denominators: taskCount is overall catalog coverage;
        # eligibleCount is how many of those tasks ever reached a real
        # model.complete() call at all (the rest were rejected purely on
        # input-construction/context-budget grounds, before any generation
        # was attempted). verifiedCount / eligibleCount -- not
        # verifiedCount / taskCount -- is the repair-utility rate; reporting
        # only the latter would misleadingly fold context-ineligible tasks
        # into a repair-capability denominator they never actually tested.
        "eligibleCount": eligible,
        "tasks": task_results,
    }
    report_path = each_home() / "benchmarks" / f"{report_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"report": report, "report_path": str(report_path)}


def render_sanitized_markdown(report: dict[str, Any]) -> str:
    """A conservative public-safe summary: outcomes/metrics only, no source."""
    eligible = report.get("eligibleCount", sum(1 for t in report["tasks"] if t.get("generationEligible")))
    lines = [
        f"# EACH historical benchmark report: {report['reportId']}",
        "",
        f"- Tasks (overall catalog coverage): {report['taskCount']}",
        f"- Generation-eligible (fit the model's context budget for >=1 real attempt): {eligible} / {report['taskCount']}",
        f"- Verified repairs among generation-eligible tasks: {report['verifiedCount']} / {eligible if eligible else 0}",
        f"- Verified repairs over all catalog tasks: {report['verifiedCount']} / {report['taskCount']}",
        "",
        (
            "A task rejected before any model.complete() call (context-budget "
            "ineligible) is reported as 0 generation attempts, not 1 -- it never "
            "tested repair capability and must not be folded into a repair-utility "
            "denominator."
        ),
        "",
        "| Task | Repo | License | Outcome | Attempts | Generation calls | Assurance |",
        "|---|---|---|---|---|---|---|",
    ]
    for task in report["tasks"]:
        lines.append(
            f"| {task['taskId']} | {task['repo']} | {task['license']} | {task['outcome']} | "
            f"{task['attempts']} | {task.get('generationCallCount', 'n/a')} | {task.get('assuranceLevel', 'n/a')} |"
        )
    lines.append("")
    lines.append(
        "No patch text, model prompt/completion content, or known-fix source is included in this sanitized "
        "summary. Full private receipts (one per task) remain under ~/.each/runs."
    )
    return "\n".join(lines)
