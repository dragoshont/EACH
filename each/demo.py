"""The M1 deterministic hello-repair vertical slice.

local fixture issue -> approved immutable spec -> sanitized declared
materials -> FixtureModel -> scoped unified diff -> no-network container
executor -> deterministic failing/passing tests -> audit stub -> receipt.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from each.audit.stub import audit_stub
from each.executor.base import ExecutionResult
from each.executor.container import ContainerExecutor, derive_assurance_level
from each.models.fixture import FixtureModel
from each.patch import PatchRejected, apply_patch, extract_patch_text, parse_patch
from each.paths import runs_dir
from each.receipt import Receipt
from each.spec import ApprovedSpec, make_spec_packet
from each.worktree import build_worktree

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "examples" / "hello-repair"
FIXTURE_ALLOWED_PATHS = ["src/greet.py"]
FIXTURE_TEST_PATHS = ["tests/test_greet.py"]
ACCEPTANCE_COMMAND = ["python", "-m", "unittest", "tests.test_greet", "-v"]
EXPECTED_TEST_COUNT = 1

FIXTURE_PATCH_RESPONSE = """BEGIN_PATCH
--- a/src/greet.py
+++ b/src/greet.py
@@ -1,2 +1,2 @@
 def greet(name: str) -> str:
-    return "Hell, " + name
+    return "Hello, " + name
END_PATCH
"""

# Docker/daemon launch failures: these codes mean the test never genuinely
# ran, so they must never be read as either a pass or a fail signal.
_DOCKER_LAUNCH_FAILURE_EXIT_CODES = {125, 126, 127}
_RAN_TESTS_RE = re.compile(r"Ran (\d+) tests? in")
_CLEAN_OK_RE = re.compile(r"^OK$", re.MULTILINE)
_CLEAN_FAILED_RE = re.compile(r"^FAILED \((?:failures|errors)=\d+\)$", re.MULTILINE)


class FixtureExecutionError(RuntimeError):
    """Raised when a test run cannot be honestly classified as pass or fail."""


def _interpret_test_run(result: ExecutionResult, *, expected_tests: int) -> str:
    """Classify one acceptance-command run as 'passed' or 'failed'.

    Raises FixtureExecutionError for anything that is not genuine pass/fail
    evidence: a Docker launch failure, a skipped test masquerading as a
    pass, a test count mismatch, or output that doesn't match either
    unittest's exact clean-pass or clean-fail summary line.
    """
    if result.exit_code in _DOCKER_LAUNCH_FAILURE_EXIT_CODES:
        raise FixtureExecutionError(
            f"container launch failed (exit {result.exit_code}); this is not test evidence: "
            f"{result.stderr or result.stdout}"
        )
    combined = result.stdout + result.stderr
    ran_match = _RAN_TESTS_RE.search(combined)
    if not ran_match or int(ran_match.group(1)) != expected_tests:
        raise FixtureExecutionError(
            f"expected exactly {expected_tests} test(s) to run; could not confirm from output: {combined!r}"
        )
    if result.exit_code == 0:
        if _CLEAN_OK_RE.search(combined):
            return "passed"
        raise FixtureExecutionError(
            f"exit 0 but output was not a clean 'OK' (possible skip/error masked as pass): {combined!r}"
        )
    if _CLEAN_FAILED_RE.search(combined):
        return "failed"
    raise FixtureExecutionError(f"nonzero exit without a recognizable FAILED summary: {combined!r}")


def _result_to_dict(result: ExecutionResult) -> dict[str, Any]:
    return {
        "command": list(result.command),
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_hello_repair(*, run_id: str | None = None) -> dict[str, Any]:
    """Run the full hello-repair pipeline and write a private receipt.

    Returns a small dict with the outcome and the receipt paths for
    callers (CLI, tests, milestone evidence collection).
    """
    run_id = run_id or f"hello-repair-{uuid.uuid4().hex[:12]}"

    spec_packet = make_spec_packet(
        task_id="hello-repair",
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

    worktree, manifest = build_worktree(FIXTURE_ROOT, FIXTURE_ALLOWED_PATHS + FIXTURE_TEST_PATHS)

    executor = ContainerExecutor()
    isolation_result = executor.verify_isolation(worktree)
    assurance_level = derive_assurance_level(executor, isolation_result)
    isolation_evidence = _result_to_dict(isolation_result)

    baseline = executor.run(ACCEPTANCE_COMMAND, worktree)

    model = FixtureModel(FIXTURE_PATCH_RESPONSE)
    prompt = f"Problem: {spec_packet.problem_statement}\nAllowed paths: {spec_packet.allowed_paths}"
    raw_completion = model.complete(prompt)

    common_fields = {
        "run_id": run_id,
        "spec": approved.to_dict()["packet"],
        "spec_hash": approved.approved_hash,
        "model_identity": model.identity(),
        "prompt": prompt,
        "raw_completion": raw_completion,
        "materials": manifest,
        "executor_identity": executor.identity(),
        "isolation_evidence": isolation_evidence,
        "audit": audit_stub(),
        "assurance_level": assurance_level,
    }

    try:
        patch_text = extract_patch_text(raw_completion)
        patch = parse_patch(patch_text)
        touched = apply_patch(patch, worktree, set(FIXTURE_ALLOWED_PATHS))
    except PatchRejected as exc:
        outcome = f"PATCH_REJECTED: {exc}"
        receipt = Receipt(
            patch_text="",
            touched_paths=[],
            baseline_result=_result_to_dict(baseline),
            repaired_result={},
            outcome=outcome,
            **common_fields,
        )
        json_path, md_path = receipt.write(runs_dir() / run_id)
        return {
            "outcome": outcome,
            "receipt_json": str(json_path),
            "receipt_md": str(md_path),
            "manifest": manifest,
        }

    repaired = executor.run(ACCEPTANCE_COMMAND, worktree)

    baseline_verdict = _interpret_test_run(baseline, expected_tests=EXPECTED_TEST_COUNT)
    repaired_verdict = _interpret_test_run(repaired, expected_tests=EXPECTED_TEST_COUNT)
    outcome = (
        "REPAIR_VERIFIED"
        if (baseline_verdict == "failed" and repaired_verdict == "passed")
        else "REPAIR_NOT_VERIFIED"
    )

    receipt = Receipt(
        patch_text=patch_text,
        touched_paths=touched,
        baseline_result=_result_to_dict(baseline),
        repaired_result=_result_to_dict(repaired),
        outcome=outcome,
        **common_fields,
    )
    json_path, md_path = receipt.write(runs_dir() / run_id)
    return {
        "outcome": outcome,
        "receipt_json": str(json_path),
        "receipt_md": str(md_path),
        "manifest": manifest,
    }
