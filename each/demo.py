"""The M1 deterministic hello-repair vertical slice.

local fixture issue -> approved immutable spec -> sanitized declared
materials -> FixtureModel -> scoped unified diff -> no-network container
executor -> deterministic failing/passing tests -> audit stub -> receipt.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from each.audit.stub import audit_stub
from each.executor.base import ExecutionResult
from each.executor.container import ContainerExecutor
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

FIXTURE_PATCH_RESPONSE = """BEGIN_PATCH
--- a/src/greet.py
+++ b/src/greet.py
@@ -1,2 +1,2 @@
 def greet(name: str) -> str:
-    return "Hell, " + name
+    return "Hello, " + name
END_PATCH
"""


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
    baseline = executor.run(ACCEPTANCE_COMMAND, worktree)

    model = FixtureModel(FIXTURE_PATCH_RESPONSE)
    prompt = f"Problem: {spec_packet.problem_statement}\nAllowed paths: {spec_packet.allowed_paths}"
    raw_completion = model.complete(prompt)

    try:
        patch_text = extract_patch_text(raw_completion)
        patch = parse_patch(patch_text)
        touched = apply_patch(patch, worktree, set(FIXTURE_ALLOWED_PATHS))
    except PatchRejected as exc:
        outcome = f"PATCH_REJECTED: {exc}"
        receipt = Receipt(
            run_id=run_id,
            spec=approved.to_dict()["packet"],
            spec_hash=approved.approved_hash,
            model_id=model.model_id,
            prompt=prompt,
            raw_completion=raw_completion,
            patch_text="",
            touched_paths=[],
            baseline_result=_result_to_dict(baseline),
            repaired_result={},
            audit=audit_stub(),
            assurance_level=executor.assurance_level,
            outcome=outcome,
        )
        json_path, md_path = receipt.write(runs_dir() / run_id)
        return {"outcome": outcome, "receipt_json": str(json_path), "receipt_md": str(md_path)}

    repaired = executor.run(ACCEPTANCE_COMMAND, worktree)

    baseline_failed = baseline.exit_code != 0
    repaired_passed = repaired.exit_code == 0
    outcome = "REPAIR_VERIFIED" if (baseline_failed and repaired_passed) else "REPAIR_NOT_VERIFIED"

    receipt = Receipt(
        run_id=run_id,
        spec=approved.to_dict()["packet"],
        spec_hash=approved.approved_hash,
        model_id=model.model_id,
        prompt=prompt,
        raw_completion=raw_completion,
        patch_text=patch_text,
        touched_paths=touched,
        baseline_result=_result_to_dict(baseline),
        repaired_result=_result_to_dict(repaired),
        audit=audit_stub(),
        assurance_level=executor.assurance_level,
        outcome=outcome,
    )
    json_path, md_path = receipt.write(runs_dir() / run_id)
    return {
        "outcome": outcome,
        "receipt_json": str(json_path),
        "receipt_md": str(md_path),
        "manifest": manifest,
    }
