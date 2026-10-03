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

import time
import uuid
from typing import Any

from each.audit.run import reject_on_audit_flag, run_audit
from each.demo import (
    ACCEPTANCE_COMMAND,
    EXPECTED_TEST_COUNT,
    FIXTURE_ALLOWED_PATHS,
    FIXTURE_ROOT,
    FIXTURE_TEST_PATHS,
    FixtureExecutionError,
    _interpret_test_run,
    _result_to_dict,
)
from each.executor.container import ContainerExecutor, ContainerExecutorError, derive_assurance_level
from each.hashing import sha256_bytes
from each.models.base import ContextBudgetExceeded, RepairModel
from each.outcome import sanitize_outcome_class
from each.patch import PatchRejected, apply_patch, extract_patch_text, parse_patch
from each.paths import runs_dir
from each.raw_proposal import RawProposalRejected, derive_unified_diff
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


def _read_candidate_bytes_for_audit(worktree, touched: list[str]) -> bytes:
    return b"\n".join((worktree / path).read_bytes() for path in touched)


def _classify_fixture_run(result, *, expected_tests: int) -> tuple[str | None, dict[str, str]]:
    if "unittest.loader._FailedTest" in result.stdout + result.stderr:
        return None, {"classification": "inconclusive", "reason": "test_collection_failed"}
    try:
        verdict = _interpret_test_run(result, expected_tests=expected_tests)
    except FixtureExecutionError as exc:
        reason = "ambiguous_output"
        message = str(exc)
        if result.exit_code in {125, 126, 127} or "container launch failed" in message:
            reason = "container_launch_failed"
        elif "expected exactly" in message:
            reason = "unexpected_test_count"
        elif "clean 'OK'" in message:
            reason = "contradictory_summary"
        elif "recognizable FAILED summary" in message:
            reason = "nonzero_unexpected_exit"
        return None, {"classification": "inconclusive", "reason": reason}
    return (
        verdict,
        {"classification": "pass" if verdict == "passed" else "fail", "reason": verdict},
    )


def run_model_bakeoff(
    model: RepairModel, *, max_attempts: int = 3, run_id: str | None = None,
    audit_corpus: list[str] | None = None, proposal_format: str = "diff",
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
    if proposal_format not in {"diff", "fim"}:
        raise ValueError("proposal_format must be diff or fim")
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
    probe_worktree, probe_manifest = build_worktree(FIXTURE_ROOT, FIXTURE_ALLOWED_PATHS + FIXTURE_TEST_PATHS)
    try:
        isolation_result = executor.verify_isolation(probe_worktree)
    except ContainerExecutorError as exc:
        assurance_level = "EACH-P1"
        isolation_evidence = {"errorType": type(exc).__name__, "errorDetail": str(exc)}
    else:
        assurance_level = derive_assurance_level(executor, isolation_result)
        isolation_evidence = _result_to_dict(isolation_result)

    base_prompt = _PROMPT_TEMPLATE.format(
        problem=spec_packet.problem_statement,
        allowed_paths=spec_packet.allowed_paths,
        path=FIXTURE_ALLOWED_PATHS[0],
        source=_BUG_SOURCE,
    )
    source_prefix = _BUG_SOURCE.partition("\n")[0] + "\n"
    if proposal_format == "fim":
        base_prompt = (
            "<fim_prefix># " + spec_packet.problem_statement + "\n"
            + source_prefix + "<fim_suffix><fim_middle>"
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
        "network_isolation_verified": assurance_level == "EACH-P2",
    }

    if assurance_level != "EACH-P2":
        outcome = "ISOLATION_UNVERIFIED"
        isolation_evidence.update({
            "status": "failed",
            "failureStage": "isolation",
            "generation_attempted": False,
            "validation_attempted": False,
        })
        common_fields["prompt"] = ""
        receipt = Receipt(
            patch_text="",
            touched_paths=[],
            materials=probe_manifest,
            baseline_result={},
            repaired_result={},
            outcome=outcome,
            **common_fields,
        )
        json_path, md_path = receipt.write(runs_dir() / run_id, materials_source=FIXTURE_ROOT)
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
            baseline = executor.run(
                ACCEPTANCE_COMMAND, worktree,
                protected_paths=tuple(FIXTURE_TEST_PATHS),
            )
        except ContainerExecutorError as exc:
            attempts.append(
                {
                    "attempt": attempt_num,
                    "proposal_format": proposal_format,
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
        attempt_baseline = _result_to_dict(baseline)
        baseline_verdict, baseline_classification = _classify_fixture_run(
            baseline, expected_tests=EXPECTED_TEST_COUNT
        )
        if baseline_verdict is None:
            attempts.append(
                {
                    "attempt": attempt_num,
                    "prompt": prompt,
                    "raw_completion": "",
                    "materials": manifest,
                    "baseline_result": attempt_baseline,
                    "baseline_classification": baseline_classification,
                    "patch_text": "",
                    "touched_paths": [],
                    "repaired_result": {},
                    "repaired_classification": {"classification": "unavailable", "reason": "not_run"},
                    "outcome": f"BASELINE_INCONCLUSIVE: {baseline_classification['reason']}",
                    "audit": common_fields["audit"],
                }
            )
            break
        completion_started = time.perf_counter()
        model.last_prompt = None
        try:
            raw_completion = model.complete(prompt)
        except (RuntimeError, OSError, ValueError, TypeError, ImportError, MemoryError, KeyboardInterrupt) as exc:
            generation_attempted = (
                False if isinstance(exc, ContextBudgetExceeded)
                else getattr(model, "last_generation_attempted", None)
            )
            attempts.append({
                "attempt": attempt_num,
                "proposal_format": proposal_format,
                "raw_request": prompt,
                "prompt": getattr(model, "last_prompt", None) or "",
                "rendered_prompt_available": model.last_prompt is not None,
                "generation_attempted": generation_attempted,
                "raw_completion": "",
                "materials": manifest,
                "baseline_result": attempt_baseline,
                "baseline_classification": baseline_classification,
                "patch_text": "", "touched_paths": [], "repaired_result": {},
                "repaired_classification": {"classification": "unavailable", "reason": "not_run"},
                "audit": common_fields["audit"],
                "outcome": "EXECUTION_ERROR",
                "failureStage": "generation_preflight" if generation_attempted is False else "generation",
                "failureClassification": (
                    "generation_not_started" if generation_attempted is False
                    else "backend_generation_failed" if generation_attempted is True
                    else "generation_stage_unknown"
                ),
                "errorType": type(exc).__name__,
                "generation_error_detail": str(exc),
                "completion_call_seconds": time.perf_counter() - completion_started,
                "model_identity": model.identity(),
            })
            break
        rendered_prompt = getattr(model, "last_prompt", None)
        attempt_record: dict[str, Any] = {
            "attempt": attempt_num,
            "proposal_format": proposal_format,
            "completion_call_seconds": time.perf_counter() - completion_started,
            "raw_request": prompt,
            "prompt": rendered_prompt if rendered_prompt is not None else prompt,
            "rendered_prompt_available": rendered_prompt is not None,
            "generation_attempted": True,
            "raw_completion": raw_completion,
            "materials": manifest,
            "baseline_result": attempt_baseline,
            "baseline_classification": baseline_classification,
            "patch_text": "",
            "touched_paths": [],
            "repaired_result": {},
            "repaired_classification": {"classification": "unavailable", "reason": "not_run"},
            "model_identity": model.identity(),
            "audit": common_fields["audit"],
        }

        try:
            if proposal_format == "fim":
                if not raw_completion.strip() or "<fim_" in raw_completion or "<|endoftext|>" in raw_completion:
                    raise RawProposalRejected("FIM completion is empty or contains unexpected control tokens")
                proposed_source = source_prefix + raw_completion
                if not proposed_source.endswith("\n"):
                    proposed_source += "\n"
                patch_text = derive_unified_diff(
                    path=FIXTURE_ALLOWED_PATHS[0], original_text=_BUG_SOURCE, proposed_text=proposed_source,
                )
                if not patch_text:
                    raise RawProposalRejected("FIM completion did not change the source")
                attempt_record["infillPrefixSha256"] = sha256_bytes(source_prefix.encode())
                attempt_record["infillSuffixSha256"] = sha256_bytes(b"")
            else:
                patch_text = extract_patch_text(raw_completion)
            worktree, candidate_manifest = build_worktree(
                FIXTURE_ROOT, FIXTURE_ALLOWED_PATHS + FIXTURE_TEST_PATHS
            )
            if candidate_manifest != manifest:
                raise RawProposalRejected("Candidate preimage differs from the validated baseline")
            patch = parse_patch(patch_text)
            touched = apply_patch(patch, worktree, set(FIXTURE_ALLOWED_PATHS))
        except (PatchRejected, RawProposalRejected) as exc:
            attempt_record["outcome"] = f"PATCH_REJECTED: {exc}"
            attempts.append(attempt_record)
            prompt = base_prompt if proposal_format == "fim" else base_prompt + _RETRY_SUFFIX.format(reason=str(exc))
            continue

        # From here on this attempt's own patch_text/touched_paths are
        # recorded on THIS attempt_record -- never left to be reported
        # alongside a different, later attempt's outcome/prompt.
        attempt_record["patch_text"] = patch_text
        attempt_record["touched_paths"] = touched
        candidate_source_bytes = _read_candidate_bytes_for_audit(worktree, touched)
        attempt_record["audit_subject_sha256"] = sha256_bytes(candidate_source_bytes)

        try:
            repaired = executor.run(
                ACCEPTANCE_COMMAND, worktree,
                protected_paths=tuple(FIXTURE_TEST_PATHS),
            )
        except ContainerExecutorError as exc:
            attempt_record["outcome"] = f"EXECUTION_ERROR: {exc}"
            attempts.append(attempt_record)
            break
        outcome = (
            "REPAIR_VERIFIED" if baseline_verdict == "failed" else "REPAIR_NOT_VERIFIED"
        )
        attempt_record["repaired_result"] = _result_to_dict(repaired)
        repaired_verdict, repaired_classification = _classify_fixture_run(
            repaired, expected_tests=EXPECTED_TEST_COUNT
        )
        attempt_record["repaired_classification"] = repaired_classification
        if repaired_verdict is None:
            attempt_record["outcome"] = f"REPAIRED_RUN_INCONCLUSIVE: {repaired_classification['reason']}"
            attempts.append(attempt_record)
            prompt = base_prompt if proposal_format == "fim" else base_prompt + _RETRY_SUFFIX.format(
                reason="the repaired test run could not be classified; try again"
            )
            continue
        outcome = (
            "REPAIR_VERIFIED" if (baseline_verdict == "failed" and repaired_verdict == "passed") else "REPAIR_NOT_VERIFIED"
        )
        if outcome == "REPAIR_VERIFIED":
            repaired_source = candidate_source_bytes.decode("utf-8", errors="replace")
            attempt_record["audit"] = run_audit(repaired_source, corpus=audit_corpus)
            if reject_on_audit_flag(attempt_record["audit"]):
                outcome = "REPAIR_REJECTED_AUDIT"

        attempt_record["outcome"] = outcome
        attempts.append(attempt_record)

        if outcome in {"REPAIR_VERIFIED", "REPAIR_REJECTED_AUDIT"}:
            break
        prompt = base_prompt if proposal_format == "fim" else base_prompt + _RETRY_SUFFIX.format(
            reason="patch applied but did not make the failing test pass"
        )

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
        audit_subject_sha256=selected.get("audit_subject_sha256"),
        **common_fields,
    )
    json_path, md_path = receipt.write(
        runs_dir() / run_id, materials_source=FIXTURE_ROOT
    )
    return {
        "outcome": sanitize_outcome_class(final_outcome),
        "receipt_json": str(json_path),
        "receipt_md": str(md_path),
        "attempts": len(attempts),
    }
