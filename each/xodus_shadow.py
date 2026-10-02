"""M8: a sealed, source-isolated Builder run against a real, pinned, public
upstream file (``xodus-gaming/xgameruntime``'s ``xsystem.c``), reusing the
exact validated-before-audit / audit-terminal pipeline shape already proven
in :mod:`each.bakeoff` and :mod:`each.clean_room` (M4/M5 fixes): a candidate
must pass a real baseline-fails/repaired-passes acceptance run before the
terminal audit ever runs; an audit rejection ends the run and is never fed
back into another Builder attempt; only the original approved spec -- never
a discovered match or audit finding -- can ever seed a later attempt.

Unlike M7 (a from-scratch, black-box clean-room synthesis task), M8 is a
real, scoped bug-fix task: the Builder is shown the complete current public
``xsystem.c`` (the one file the approved spec's ``allowed_paths`` permits
editing) plus the approved spec's own ``problem_statement`` (built entirely
from the public GitHub issue text -- see the spec's own material origins).
It is never shown any proprietary implementation, decompiled/disassembled
material, or any human-authored fix -- only the real public source it is
allowed to edit and the public issue describing the bug.

The acceptance pipeline is two mechanical host-tool steps (compile, then
run a tiny isolated C test binary -- see
``examples/xodus-m8-sandbox-id/build_check.py``), not pytest: outcomes are
plain process exit codes, classified honestly (a Docker-launch failure is
never read as pass/fail evidence).
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from each.audit.run import reject_on_audit_flag, run_audit
from each.benchmark import BenchmarkExecutionError, fetch_file
from each.demo import _DOCKER_LAUNCH_FAILURE_EXIT_CODES, _result_to_dict
from each.executor.container import ContainerExecutor, derive_assurance_level
from each.models.base import RepairModel
from each.patch import PatchRejected, apply_patch, extract_patch_text, parse_patch
from each.paths import each_home, runs_dir
from each.receipt import Receipt
from each.spec import ApprovedSpec
from each.worktree import build_worktree

HARNESS_ROOT = Path(__file__).resolve().parent.parent / "examples" / "xodus-m8-sandbox-id"
HARNESS_FILES = ("build_check.py", "winstubs.h")

# Built from docker/m8-native-runtime/Dockerfile (python:3.12-slim + gcc +
# libc6-dev only), pinned by digest before this sealed run -- "provision
# dependencies before sealed run where possible" (mandate section 128),
# matching the exact precedent of each.benchmark.BENCHMARK_IMAGE_DIGEST.
NATIVE_IMAGE_DIGEST = (
    "each-m8-native-runtime@sha256:5e3fd3be8e066385dfa7eaf5bf7ef2a14a5e2090a6a8ba3227de5e9aeffb6baf"
)

_PROMPT_TEMPLATE = """You are repairing exactly one bug in a real, existing C source file, described below by its own public issue report. You must fix ONLY the behavior the issue describes, using ONLY the file content shown below and the issue text -- do not invent, assume, or reference any other implementation, patch, or fix you may have seen elsewhere for this exact bug.

{problem_statement}

Only this file may be changed: {path}

The file has exactly {line_count} lines. Its current contents, shown verbatim between the two marker lines below (the marker lines themselves are NOT part of the file and must NOT appear in your diff):
----- FILE CONTENT START -----
{numbered_source}
----- FILE CONTENT END -----

Here is a complete, fully worked example on an UNRELATED 2-line toy file -- it illustrates the exact wire format only; its content has nothing to do with the real task below.

Toy file "toy.c" (2 lines):
int foo = 1;
int bar = 2;

A correct diff changing those 2 lines to "int foo = 10;" and "int bar = 20;" looks exactly like this, with no other text:
BEGIN_PATCH
--- a/toy.c
+++ b/toy.c
@@ -1,2 +1,2 @@
-int foo = 1;
-int bar = 2;
+int foo = 10;
+int bar = 20;
END_PATCH

Now produce the REAL diff for {path} ({line_count} lines), making the smallest change that fixes the described bug, in the exact same wire format as the toy example above: reply with ONLY BEGIN_PATCH, the three diff header lines, a unified-diff hunk (or hunks) covering only the lines you actually change -- each unchanged context line as a " " (space-prefixed) line, each removed line as a "-" line, each added line as a "+" line -- then END_PATCH. Do not use "..." or any other elision. Do not add markdown fences.

The number after "-N," in each hunk header must equal the number of context+removed lines in that hunk, and the number after "+N," must equal the number of context+added lines in that hunk -- both ordinary decimal integers computed by you from the hunk you write, not left as English text or anything other than digits.
"""

_RETRY_SUFFIX = (
    "\n\nYour previous attempt was rejected: {reason}\n"
    "Try again, following the exact wire format shown in the toy example above: a unified-diff "
    "hunk with correct line counts in its header, context (\" \"), removed (\"-\"), and added "
    "(\"+\") lines. Fix only the behavior the issue describes; do not reference any external "
    "patch or implementation."
)


def _assemble_source_root(fetched_source: str, allowed_path: str, dest: Path) -> None:
    """Materialize one merged source tree: the fetched real target file plus
    this repo's own (never-Builder-input) validation harness scaffold, at
    the exact relative layout the approved spec's build/acceptance commands
    expect. This is a host-side, pre-sealed-run materialization step (like
    M6's historical-task fetch), never performed inside the container.
    """
    (dest / allowed_path).parent.mkdir(parents=True, exist_ok=True)
    (dest / allowed_path).write_text(fetched_source, encoding="utf-8")
    harness_dest = dest / "examples" / "xodus-m8-sandbox-id"
    harness_dest.mkdir(parents=True, exist_ok=True)
    for name in HARNESS_FILES:
        shutil.copyfile(HARNESS_ROOT / name, harness_dest / name)


def _interpret_native_run(build_result, run_result) -> str:
    """Classify one (build, run) command pair as 'passed' or 'failed'.

    Raises BenchmarkExecutionError for anything that is not genuine
    pass/fail evidence (a Docker-launch failure on either step).
    """
    if build_result.exit_code in _DOCKER_LAUNCH_FAILURE_EXIT_CODES:
        raise BenchmarkExecutionError(
            f"container launch failed during build (exit {build_result.exit_code}); "
            f"this is not build evidence: {build_result.stderr or build_result.stdout}"
        )
    if build_result.exit_code != 0:
        return "build_failed"
    if run_result.exit_code in _DOCKER_LAUNCH_FAILURE_EXIT_CODES:
        raise BenchmarkExecutionError(
            f"container launch failed during run (exit {run_result.exit_code}); "
            f"this is not test evidence: {run_result.stderr or run_result.stdout}"
        )
    return "passed" if run_result.exit_code == 0 else "failed"


def run_xodus_shadow_build(
    model: RepairModel,
    approved: ApprovedSpec,
    *,
    max_attempts: int = 3,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run one sealed Builder attempt sequence for ``approved`` (an M8-style
    real, pinned, public-source bug-fix spec), reusing the proven isolation
    / validation / terminal-audit / signed-receipt pipeline.

    The candidate module is authored exclusively by ``model`` -- never by
    this harness or any outer conductor. All strict candidate
    source/prompt/completion/patch data is written only to the private
    receipt under ``runs_dir()``; this function's return value is
    deliberately source-free (outcome label + file paths only).
    """
    approved.verify()
    packet = approved.packet
    if len(packet.allowed_paths) != 1 or len(packet.build_commands) != 1 or len(packet.acceptance_commands) != 1:
        raise ValueError(
            "run_xodus_shadow_build currently supports exactly one allowed path, "
            "one build command, and one acceptance command"
        )
    allowed_path = packet.allowed_paths[0]
    build_command = list(packet.build_commands[0])
    acceptance_command = list(packet.acceptance_commands[0])

    run_id = run_id or f"xodus-shadow-{uuid.uuid4().hex[:8]}"
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")

    # Host-side, pre-sealed-run materialization: fetch the exact pinned
    # public upstream file over the network (like M6's historical-task
    # fetch), never performed inside the no-network container.
    fetched_source = fetch_file(packet.target_repo.split("github.com/")[-1], packet.target_ref, allowed_path)
    materialize_root = each_home() / "shadow" / "m8" / run_id / "source"
    materialize_root.mkdir(parents=True, exist_ok=True)
    _assemble_source_root(fetched_source, allowed_path, materialize_root)
    include_paths = [allowed_path] + [f"examples/xodus-m8-sandbox-id/{name}" for name in HARNESS_FILES]

    executor = ContainerExecutor(image=NATIVE_IMAGE_DIGEST)
    probe_worktree, _probe_manifest = build_worktree(materialize_root, include_paths)
    isolation_result = executor.verify_isolation(probe_worktree)
    assurance_level = derive_assurance_level(executor, isolation_result)
    isolation_evidence = _result_to_dict(isolation_result)

    source_lines = fetched_source.splitlines()
    line_count = len(source_lines)
    base_prompt = _PROMPT_TEMPLATE.format(
        problem_statement=packet.problem_statement,
        path=allowed_path,
        line_count=line_count,
        numbered_source=fetched_source,
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
        "legal_certification": False,
        "cleanroom_certification": False,
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

    # Baseline: the real, unmodified public source must build but genuinely
    # fail the acceptance run (proving this harness actually exercises the
    # reported bug, not a vacuous always-pass check).
    baseline_worktree, baseline_manifest = build_worktree(materialize_root, include_paths)
    baseline_build = executor.run(build_command, baseline_worktree)
    baseline_run = executor.run(acceptance_command, baseline_worktree)
    baseline_verdict = _interpret_native_run(baseline_build, baseline_run)
    if baseline_verdict != "failed":
        raise BenchmarkExecutionError(
            f"baseline (unmodified public source) did not genuinely fail acceptance "
            f"(verdict={baseline_verdict!r}); this harness does not exercise the reported bug"
        )
    final_baseline = _result_to_dict(baseline_run)
    final_materials = baseline_manifest

    attempts: list[dict[str, Any]] = []
    prompt = base_prompt
    # No sentinel default: REPAIR_NOT_VERIFIED is only a valid final outcome
    # once a patch actually applied and the candidate build/run was
    # classified. If every attempt is exhausted on a PATCH_REJECTED retry
    # (never reaching that point), this stays None and is resolved from the
    # real last attempt's own outcome after the loop -- never silently
    # mislabeled as a verified-but-failing repair that never happened.
    # Matches each.benchmark's and the fixed each.clean_room's identical rule.
    final_outcome: str | None = None
    final_patch_text = ""
    final_touched: list[str] = []
    final_repaired: dict[str, Any] = {}
    final_raw_completion = ""
    final_audit = common_fields["audit"]

    for attempt_num in range(1, max_attempts + 1):
        worktree, manifest = build_worktree(materialize_root, include_paths)
        final_materials = manifest
        raw_completion = model.complete(prompt)
        rendered_prompt = getattr(model, "last_prompt", None)
        attempt_record: dict[str, Any] = {
            "attempt": attempt_num,
            "prompt": rendered_prompt if rendered_prompt is not None else prompt,
            "raw_completion": raw_completion,
            "materials": manifest,
            "baseline_result": final_baseline,
        }
        final_raw_completion = raw_completion

        try:
            patch_text = extract_patch_text(raw_completion)
            patch = parse_patch(patch_text)
            touched = apply_patch(patch, worktree, {allowed_path})
        except PatchRejected as exc:
            attempt_record["outcome"] = f"PATCH_REJECTED: {exc}"
            attempts.append(attempt_record)
            prompt = base_prompt + _RETRY_SUFFIX.format(reason=str(exc))
            continue

        candidate_build = executor.run(build_command, worktree)
        candidate_run = executor.run(acceptance_command, worktree)
        try:
            test_verdict = _interpret_native_run(candidate_build, candidate_run)
        except BenchmarkExecutionError as exc:
            attempt_record["outcome"] = f"EXECUTION_ERROR: {exc}"
            attempts.append(attempt_record)
            prompt = base_prompt + _RETRY_SUFFIX.format(reason="the previous patch could not be evaluated cleanly")
            continue

        final_patch_text = patch_text
        final_touched = touched
        final_repaired = _result_to_dict(candidate_run) if test_verdict != "build_failed" else _result_to_dict(
            candidate_build
        )
        outcome = "REPAIR_VERIFIED" if test_verdict == "passed" else "REPAIR_NOT_VERIFIED"
        if test_verdict == "passed":
            # Terminal audit only after generation/validation ends; no
            # proprietary/forbidden-source corpus exists for this task (the
            # approved spec's forbidden_sources are enforced by never
            # fetching such material in the first place), so corpus-backed
            # checks honestly report UNAVAILABLE -- never a fabricated PASS.
            final_audit = run_audit(final_patch_text)
            if reject_on_audit_flag(final_audit):
                outcome = "REPAIR_REJECTED_AUDIT"

        attempt_record["outcome"] = (
            outcome if test_verdict != "build_failed" else f"BUILD_FAILED: {_result_to_dict(candidate_build)}"
        )
        attempts.append(attempt_record)
        final_outcome = outcome

        if outcome in {"REPAIR_VERIFIED", "REPAIR_REJECTED_AUDIT"}:
            break
        reason = "patch applied but did not compile" if test_verdict == "build_failed" else (
            "patch applied and compiled but did not fix the reported bug"
        )
        prompt = base_prompt + _RETRY_SUFFIX.format(reason=reason)

    if final_outcome is None:
        # Every attempt was exhausted on a PATCH_REJECTED/EXECUTION_ERROR
        # retry without ever reaching a classified candidate run: the honest
        # final outcome is that last attempt's own recorded outcome (e.g.
        # "PATCH_REJECTED: ..."), never a silent "REPAIR_NOT_VERIFIED" that
        # would misrepresent a never-applied patch as one that was applied,
        # built, run, and simply failed to verify.
        final_outcome = attempts[-1]["outcome"] if attempts else "REPAIR_NOT_VERIFIED"

    common_fields["raw_completion"] = final_raw_completion
    if attempts:
        common_fields["prompt"] = attempts[-1]["prompt"]
    common_fields["audit"] = final_audit
    receipt = Receipt(
        patch_text=final_patch_text,
        touched_paths=final_touched,
        materials=final_materials,
        baseline_result=final_baseline,
        repaired_result=final_repaired,
        outcome=final_outcome,
        attempts=attempts,
        **common_fields,
    )
    json_path, md_path = receipt.write(runs_dir() / run_id)
    return {
        "outcome": final_outcome,
        "receipt_json": str(json_path),
        "receipt_md": str(md_path),
        "attempts": len(attempts),
    }


def summarize_receipt(receipt_json_path: str | Path) -> dict[str, Any]:
    """Read a private receipt and return ONLY source-free, hash/outcome/
    exit-code-level fields -- never the prompt, raw completion, or patch
    text. This is the one permitted way M8 (and future shadow-only) receipt
    content may be surfaced to an outer/cloud caller: strict candidate
    source must never be read or reviewed here, only this sanitized view.
    """
    import json

    data = json.loads(Path(receipt_json_path).read_text(encoding="utf-8"))
    return {
        "runId": data["runId"],
        "createdAt": data["createdAt"],
        "outcome": data["outcome"],
        "assuranceLevel": data["assuranceLevel"],
        "specHash": data["specHash"],
        "patchHash": data["patchHash"],
        "trajectoryHash": data["trajectoryHash"],
        "touchedPaths": data["touchedPaths"],
        "legalCertification": data["legalCertification"],
        "cleanroomCertification": data["cleanroomCertification"],
        "modelIdentity": {
            "modelId": data["modelIdentity"].get("modelId"),
            "implementationModule": data["modelIdentity"].get("implementationModule"),
            "implementationSha256": data["modelIdentity"].get("implementationSha256"),
            "generationParameters": data["modelIdentity"].get("generationParameters"),
            "contextPolicy": data["modelIdentity"].get("contextPolicy"),
        },
        "executorIdentity": data["executorIdentity"],
        "isolationEvidence": {
            "command": data["isolationEvidence"].get("command"),
            "exit_code": data["isolationEvidence"].get("exit_code"),
            "stdout": data["isolationEvidence"].get("stdout", "").strip(),
        },
        "baselineExitCode": data["baselineResult"].get("exit_code"),
        "repairedExitCode": data["repairedResult"].get("exit_code"),
        "audit": {
            "result": data["audit"].get("result"),
            "checks": {
                name: (check.get("status") if isinstance(check, dict) else check)
                for name, check in data["audit"].get("checks", {}).items()
            },
        },
        "attemptCount": len(data.get("attempts", [])),
        "attemptOutcomes": [a.get("outcome", "").split(":")[0] for a in data.get("attempts", [])],
        "materialsManifest": data.get("materials", {}),
    }
