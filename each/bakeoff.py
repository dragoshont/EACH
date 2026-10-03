"""The M2 local-model bake-off: runs the same hello-repair fixture through a
real, locally-executed :class:`~each.models.base.RepairModel` instead of the
deterministic ``FixtureModel``.

Reuses the exact M1 pipeline primitives (spec approval, worktree
sanitization, isolation verification/fail-closed, patch validation, test-run
classification, receipt construction) from :mod:`each.demo` rather than
re-implementing them, so a real model is evaluated under the same
corrected isolation and verdict-classification guarantees as the
deterministic slice -- no separate "configured-only" shortcut.

Zero cloud inference: the model named in the resulting receipt's
``modelIdentity`` is the only model that ever sees the repair prompt.
Note on isolation scope: the container executor's no-egress isolation
probe covers the baseline/repaired *test* executions, not the model's own
``complete()`` call -- local inference backends such as MLX-LM require
native host GPU/Metal access and cannot run inside the Linux container.
"Zero cloud inference" here is a property of which backend is wired in
(a local weights path, never a network API), not something the isolation
probe itself measures for the inference step.
"""

from __future__ import annotations

import uuid
from typing import Any

from each.audit.run import reject_on_audit_flag, run_audit
from each.demo import (
    ACCEPTANCE_COMMAND,
    EXPECTED_TEST_COUNT,
    FIXTURE_ALLOWED_PATHS,
    FIXTURE_ROOT,
    FIXTURE_TEST_PATHS,
    _interpret_test_run,
    _result_to_dict,
)
from each.executor.container import ContainerExecutor, ContainerExecutorError, derive_assurance_level
from each.models.base import RepairModel
from each.patch import PatchRejected, apply_patch, extract_patch_text, parse_patch
from each.paths import runs_dir
from each.receipt import Receipt
from each.spec import ApprovedSpec, make_spec_packet
from each.worktree import build_worktree

_BUG_SOURCE = (FIXTURE_ROOT / "src" / "greet.py").read_text()

_PROMPT_TEMPLATE = """You are repairing a small, scoped Python bug.

Problem: {problem}

Only this file may be changed: {allowed_paths}

Current contents of {path}:
```python
{source}
```

Reply with ONLY a unified diff of the required fix, wrapped exactly like
this (no other prose, no markdown fence around the markers):

BEGIN_PATCH
--- a/{path}
+++ b/{path}
@@ -1,2 +1,2 @@
 def greet(name: str) -> str:
-    <original line>
+    <fixed line>
END_PATCH
"""

_RETRY_SUFFIX = "\n\nYour previous attempt was rejected: {reason}\nTry again, following the format exactly."


def run_model_bakeoff(
    model: RepairModel, *, max_attempts: int = 3, run_id: str | None = None, audit_corpus: list[str] | None = None
) -> dict[str, Any]:
    """Run the hello-repair fixture against a real local model, bounded to
    ``max_attempts`` tries, recording the full prompt/response trajectory.

    Fails closed exactly like ``each.demo.run_hello_repair``: if this run's
    own isolation probe does not verify no-egress execution, the outcome is
    ``ISOLATION_UNVERIFIED`` and no generation/test attempt is made.

    ``audit_corpus`` is the declared set of known snippets the M4 audit
    checks compare the repaired source against (default none, which honestly
    reports those checks UNAVAILABLE rather than a fabricated PASS -- there
    is no production corpus wired in yet).
    """
    run_id = run_id or f"bakeoff-{uuid.uuid4().hex[:8]}"
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")

    spec_packet = make_spec_packet(
        task_id="m2-bakeoff-hello-repair",
        target_repo="examples/hello-repair",
        target_ref="local-fixture",
        problem_statement="greet() returns 'Hell, <name>' instead of 'Hello, <name>'.",
        allowed_paths=FIXTURE_ALLOWED_PATHS,
        build_commands=[],
        acceptance_commands=[ACCEPTANCE_COMMAND],
        forbidden_sources=["network", "host-secrets", "host-home-mount"],
        approved_by="local-demo-operator",
    )
    approved = ApprovedSpec.approve(spec_packet)
    approved.verify()

    executor = ContainerExecutor()
    probe_worktree, _probe_manifest = build_worktree(FIXTURE_ROOT, FIXTURE_ALLOWED_PATHS + FIXTURE_TEST_PATHS)
    isolation_result = executor.verify_isolation(probe_worktree)
    assurance_level = derive_assurance_level(executor, isolation_result)
    isolation_evidence = _result_to_dict(isolation_result)

    base_prompt = _PROMPT_TEMPLATE.format(
        problem=spec_packet.problem_statement,
        allowed_paths=spec_packet.allowed_paths,
        path=FIXTURE_ALLOWED_PATHS[0],
        source=_BUG_SOURCE,
    )

    common_fields = {
        "run_id": run_id,
        "spec": approved.to_dict()["packet"],
        "spec_hash": approved.approved_hash,
        "model_identity": model.identity(),
        "prompt": base_prompt,
        "raw_completion": "",
        "executor_identity": executor.identity(),
        "isolation_evidence": isolation_evidence,
        "audit": {
            "checks": {},
            "result": "UNAVAILABLE",
            "reason": "no validated candidate exists; terminal audit has not run",
        },
        "assurance_level": assurance_level,
    }

    if assurance_level != "EACH-P2":
        outcome = "ISOLATION_UNVERIFIED"
        receipt = Receipt(
            patch_text="",
            touched_paths=[],
            materials={},
            baseline_result={},
            repaired_result={},
            outcome=outcome,
            **common_fields,
        )
        json_path, md_path = receipt.write(runs_dir() / run_id)
        return {"outcome": outcome, "receipt_json": str(json_path), "receipt_md": str(md_path), "attempts": 0}

    attempts: list[dict[str, Any]] = []
    prompt = base_prompt
    # Every attempt dict below always carries the SAME complete set of
    # receipt-relevant keys (patch_text/touched_paths/materials/
    # baseline_result/repaired_result/audit) regardless of which branch
    # produced it. The receipt fields are read back out of exactly ONE
    # selected attempt (the last one appended) after the loop -- never
    # from separately loop-threaded variables defaulted to
    # "REPAIR_NOT_VERIFIED", which would misreport an all-rejected run
    # (every attempt's patch failed to even apply) as if a real patch had
    # been applied, tested, and simply failed to verify. Matches the
    # established selected-attempt pattern in
    # each.clean_room.run_clean_room_build / each.benchmark.run_benchmark_task.

    for attempt_num in range(1, max_attempts + 1):
        worktree, manifest = build_worktree(FIXTURE_ROOT, FIXTURE_ALLOWED_PATHS + FIXTURE_TEST_PATHS)
        try:
            baseline = executor.run(ACCEPTANCE_COMMAND, worktree)
        except ContainerExecutorError as exc:
            attempts.append(
                {
                    "attempt": attempt_num,
                    "prompt": prompt,
                    "raw_completion": "",
                    "materials": manifest,
                    "baseline_result": {},
                    "patch_text": "",
                    "touched_paths": [],
                    "repaired_result": {},
                    "outcome": f"EXECUTION_ERROR: {exc}",
                    "audit": common_fields["audit"],
                }
            )
            break
        baseline_verdict = _interpret_test_run(baseline, expected_tests=EXPECTED_TEST_COUNT)
        attempt_baseline = _result_to_dict(baseline)
        raw_completion = model.complete(prompt)
        rendered_prompt = getattr(model, "last_prompt", None)
        attempt_record: dict[str, Any] = {
            "attempt": attempt_num,
            "prompt": rendered_prompt if rendered_prompt is not None else prompt,
            "raw_completion": raw_completion,
            "materials": manifest,
            "baseline_result": attempt_baseline,
            "patch_text": "",
            "touched_paths": [],
            "repaired_result": {},
            "model_identity": model.identity(),
            "audit": common_fields["audit"],
        }

        try:
            patch_text = extract_patch_text(raw_completion)
            patch = parse_patch(patch_text)
            touched = apply_patch(patch, worktree, set(FIXTURE_ALLOWED_PATHS))
        except PatchRejected as exc:
            attempt_record["outcome"] = f"PATCH_REJECTED: {exc}"
            attempts.append(attempt_record)
            prompt = base_prompt + _RETRY_SUFFIX.format(reason=str(exc))
            continue

        # From here on this attempt's own patch_text/touched_paths are
        # recorded on THIS attempt_record -- never left to be reported
        # alongside a different, later attempt's outcome/prompt.
        attempt_record["patch_text"] = patch_text
        attempt_record["touched_paths"] = touched

        try:
            repaired = executor.run(ACCEPTANCE_COMMAND, worktree)
        except ContainerExecutorError as exc:
            attempt_record["outcome"] = f"EXECUTION_ERROR: {exc}"
            attempts.append(attempt_record)
            break
        # Matches each.demo.run_hello_repair's fail-loud precedent: a
        # FixtureExecutionError means the test run could not be classified
        # as a genuine pass/fail (container launch failure, skipped tests,
        # unrecognized output) -- that is not evidence the repair failed,
        # so it must not be folded into the same REPAIR_NOT_VERIFIED bucket
        # a real failing test would produce. Let it propagate uncaught.
        repaired_verdict = _interpret_test_run(repaired, expected_tests=EXPECTED_TEST_COUNT)
        outcome = (
            "REPAIR_VERIFIED" if (baseline_verdict == "failed" and repaired_verdict == "passed") else "REPAIR_NOT_VERIFIED"
        )

        attempt_record["repaired_result"] = _result_to_dict(repaired)
        if outcome == "REPAIR_VERIFIED":
            # Audit the source only after generation/validation ends.
            repaired_source = "\n".join(
                (worktree / path).read_text(encoding="utf-8", errors="replace") for path in touched
            )
            attempt_record["audit"] = run_audit(repaired_source, corpus=audit_corpus)
            if reject_on_audit_flag(attempt_record["audit"]):
                outcome = "REPAIR_REJECTED_AUDIT"

        attempt_record["outcome"] = outcome
        attempts.append(attempt_record)

        if outcome in {"REPAIR_VERIFIED", "REPAIR_REJECTED_AUDIT"}:
            break
        prompt = base_prompt + _RETRY_SUFFIX.format(reason="patch applied but did not make the failing test pass")

    # Exactly one selected attempt -- the last one appended, whatever its
    # outcome -- supplies every receipt field below. max_attempts >= 1 is
    # enforced above, and every loop iteration appends before looping or
    # breaking, so attempts is never empty here.
    selected = attempts[-1]
    final_outcome = selected["outcome"]

    common_fields["raw_completion"] = selected["raw_completion"]
    common_fields["prompt"] = selected["prompt"]
    common_fields["audit"] = selected["audit"]
    common_fields["model_identity"] = selected.get("model_identity", common_fields["model_identity"])
    receipt = Receipt(
        patch_text=selected["patch_text"],
        touched_paths=selected["touched_paths"],
        materials=selected["materials"],
        baseline_result=selected["baseline_result"],
        repaired_result=selected["repaired_result"],
        outcome=final_outcome,
        attempts=attempts,
        selected_attempt=selected["attempt"],
        **common_fields,
    )
    json_path, md_path = receipt.write(runs_dir() / run_id)
    return {
        "outcome": final_outcome,
        "receipt_json": str(json_path),
        "receipt_md": str(md_path),
        "attempts": len(attempts),
    }
