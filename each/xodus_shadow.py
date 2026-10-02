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
from each.executor.container import ContainerExecutor, ContainerExecutorError, derive_assurance_level
from each.models.base import ContextBudgetExceeded, RepairModel
from each.outcome import sanitize_outcome_class
from each.patch import PatchRejected, apply_patch, extract_patch_text, parse_patch
from each.paths import assert_no_symlink_escape, each_home, runs_dir, validate_private_root, validate_task_id
from each.receipt import Receipt
from each.spec import ApprovedSpec
from each.worktree import build_worktree, verify_unchanged
from each.xodus_policy import verify_xodus_shadow_binding

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

    ``allowed_path`` comes from an already hash-bound, durably approved
    spec (see :func:`each.xodus_policy.verify_xodus_shadow_binding`), but a
    write path is still independently contained here -- never simply
    trusted -- before any host filesystem write happens.
    """
    if allowed_path.startswith("/") or ".." in Path(allowed_path).parts:
        raise ValueError(f"refusing to write forbidden/traversal path: {allowed_path}")
    assert_no_symlink_escape(dest, label="shadow source destination")
    private_root = validate_private_root()
    dest_resolved = dest.resolve()
    if private_root not in dest_resolved.parents:
        raise ValueError("shadow source destination escapes the private root")
    if dest.exists():
        raise FileExistsError(f"refusing to reuse a shadow source destination: {dest}")
    target = (dest / allowed_path).resolve()
    if target != dest_resolved and dest_resolved not in target.parents:
        raise ValueError(f"resolved write target escapes destination root: {allowed_path}")
    if target.is_symlink():
        raise ValueError(f"refusing to write through symlink: {allowed_path}")
    dest.mkdir(parents=True, exist_ok=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(fetched_source, encoding="utf-8")
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
    verify_xodus_shadow_binding(approved)
    validate_private_root()
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
    validate_task_id(run_id)
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")

    # Host-side, pre-sealed-run materialization: fetch the exact pinned
    # public upstream file over the network (like M6's historical-task
    # fetch), never performed inside the no-network container.
    materialize_root = each_home() / "shadow" / "m8" / run_id / "source"
    assert_no_symlink_escape(materialize_root, label="shadow materialize root")
    if materialize_root.exists():
        raise FileExistsError(f"refusing to reuse a shadow source destination: {materialize_root}")
    fetched_source = fetch_file(packet.target_repo.split("github.com/")[-1], packet.target_ref, allowed_path)
    _assemble_source_root(fetched_source, allowed_path, materialize_root)
    include_paths = [allowed_path] + [f"examples/xodus-m8-sandbox-id/{name}" for name in HARNESS_FILES]

    executor = ContainerExecutor(image=NATIVE_IMAGE_DIGEST)
    probe_worktree, _probe_manifest = build_worktree(materialize_root, include_paths)
    isolation_result = executor.verify_isolation(probe_worktree)
    assurance_level = derive_assurance_level(executor, isolation_result)
    # Captured once, from the real pre-run probe only, and never itself
    # downgraded later -- see the identical fix/rationale in
    # each.clean_room.run_clean_room_build (F4).
    network_isolation_verified = assurance_level == "EACH-P2"
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
        "network_isolation_verified": network_isolation_verified,
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
    final_audit = common_fields["audit"]
    # The attempt whose patch/build/run fields are actually reported as the
    # receipt's top-level trajectory. Resolved to the real classified
    # attempt below -- never left to default to "whatever attempt happened
    # to run last", which can silently diverge from it (e.g. attempt 1
    # produces a classified-but-failing candidate, attempt 2 then retries
    # and is itself rejected before ever reaching a classified build/run:
    # the final patch/result must still be attempt 1's, not mixed with
    # attempt 2's prompt/completion). Every final_* field below is read
    # back OUT of this one selected attempt's own recorded dict (F6 fix),
    # never from a separate loop-scoped variable an unrelated later
    # iteration could leave stale.
    selected_attempt_record: dict[str, Any] | None = None

    for attempt_num in range(1, max_attempts + 1):
        worktree, manifest = build_worktree(materialize_root, include_paths)
        try:
            raw_completion = model.complete(prompt)
        except ContextBudgetExceeded as exc:
            # A policy/input-construction error, not a repair-attempt
            # failure: retrying would only make the prompt larger (the
            # retry suffix appends to base_prompt), so this is terminal
            # for the run rather than a consumable attempt -- the same
            # established fix as each.benchmark.run_benchmark (F6). Must
            # never propagate uncaught out of this function and discard
            # every attempt already recorded.
            outcome = f"BUILDER_CONTEXT_BUDGET_EXCEEDED: {exc}"
            attempts.append(
                {
                    "attempt": attempt_num,
                    "prompt": prompt,
                    "raw_completion": "",
                    "materials": manifest,
                    "baseline_result": final_baseline,
                    "patch_text": "",
                    "touched_paths": [],
                    "repaired_result": {},
                    "model_identity": model.identity(),
                    "materials_integrity": "UNAVAILABLE",
                    "outcome": outcome,
                }
            )
            final_outcome = outcome
            selected_attempt_record = attempts[-1]
            break
        rendered_prompt = getattr(model, "last_prompt", None)
        attempt_record: dict[str, Any] = {
            "attempt": attempt_num,
            "prompt": rendered_prompt if rendered_prompt is not None else prompt,
            "raw_completion": raw_completion,
            "materials": manifest,
            "baseline_result": final_baseline,
            "patch_text": "",
            "touched_paths": [],
            "build_result": None,
            "run_result": None,
            "repaired_result": {},
            "model_identity": model.identity(),
        }

        try:
            patch_text = extract_patch_text(raw_completion)
            patch = parse_patch(patch_text)
            touched = apply_patch(patch, worktree, {allowed_path})
        except PatchRejected as exc:
            attempt_record["outcome"] = f"PATCH_REJECTED: {exc}"
            attempts.append(attempt_record)
            prompt = base_prompt + _RETRY_SUFFIX.format(reason=str(exc))
            continue

        # Record the real applied patch immediately, before any
        # build/run/classification step that could itself raise: a later
        # EXECUTION_ERROR must never lose evidence of a patch that was, in
        # fact, successfully applied (F6).
        attempt_record["patch_text"] = patch_text
        attempt_record["touched_paths"] = touched

        # The harness's own scaffold files (everything in include_paths
        # except the one path the candidate is actually allowed to edit)
        # are mounted read-only for this execution (F4): the candidate's
        # build/run process cannot write through them even if it tries,
        # not merely have that attempt caught afterwards by re-hashing.
        harness_relative_paths = tuple(include_paths[1:])
        try:
            candidate_build = executor.run(build_command, worktree, protected_paths=harness_relative_paths)
        except ContainerExecutorError as exc:
            # A genuine container-launch/timeout failure during the build
            # step itself (not a classification of its result) is an infra
            # failure, not test feedback to retry against: the applied
            # patch is already recorded above, but the build step never
            # produced real pass/fail evidence at all. Finalize this
            # attempt with the real (absent) stage recorded honestly and
            # stop the bounded run -- this must never propagate out of the
            # whole function uncaught and discard every attempt already
            # recorded (F6). The private diagnostic text stays in this
            # attempt's own outcome field only; it never crosses into a
            # source-free export.
            attempt_record["materials_integrity"] = "UNAVAILABLE"
            attempt_record["outcome"] = f"EXECUTION_ERROR: {exc}"
            attempts.append(attempt_record)
            final_outcome = attempt_record["outcome"]
            selected_attempt_record = attempt_record
            break
        # Record the real build result immediately -- before the
        # acceptance run or classification -- so a build that genuinely
        # completed is never lost if a LATER step raises (F6). Both the
        # build and run command results are kept in their own distinct
        # fields; ``repaired_result`` (the final reported view) is only
        # ever reassigned once classification actually succeeds below.
        attempt_record["build_result"] = _result_to_dict(candidate_build)
        try:
            candidate_run = executor.run(acceptance_command, worktree, protected_paths=harness_relative_paths)
        except ContainerExecutorError as exc:
            # The build genuinely completed (already recorded above and
            # preserved as ``build_result``); the run step itself never
            # produced evidence. ``run_result`` stays an explicit None --
            # never a fabricated exit-code-0 result -- and the attempt is
            # finalized the same way as a build-step failure (F6).
            attempt_record["materials_integrity"] = "UNAVAILABLE"
            attempt_record["outcome"] = f"EXECUTION_ERROR: {exc}"
            attempts.append(attempt_record)
            final_outcome = attempt_record["outcome"]
            selected_attempt_record = attempt_record
            break
        attempt_record["run_result"] = _result_to_dict(candidate_run)
        attempt_record["repaired_result"] = attempt_record["run_result"]
        try:
            test_verdict = _interpret_native_run(candidate_build, candidate_run)
        except BenchmarkExecutionError as exc:
            attempt_record["outcome"] = f"EXECUTION_ERROR: {exc}"
            attempts.append(attempt_record)
            prompt = base_prompt + _RETRY_SUFFIX.format(reason="the previous patch could not be evaluated cleanly")
            continue

        # Candidate-authored C runs with full read/write access to the same
        # mount the harness scaffold files live in (see
        # examples/xodus-m8-sandbox-id/build_check.py's docstring): the
        # read-only mount above already prevents a candidate from WRITING
        # to them during execution; this re-verifies the actual retained
        # bytes immediately after execution as defense in depth (e.g.
        # against a host-side or mount-layering mistake), before any
        # outcome can be REPAIR_VERIFIED, and conservatively downgrades on
        # drift -- this is a narrow materials-integrity check, not a
        # redefinition of the shared container assurance level.
        materials_drift = verify_unchanged(worktree, manifest, harness_relative_paths)
        attempt_record["materials_integrity"] = (
            "PASS" if not materials_drift else f"FAIL: {len(materials_drift)} path(s) drifted"
        )

        # The classification-dependent choice of which raw result to report
        # (the run result normally, but the build result when the build
        # itself failed) is only finalized once classification has actually
        # succeeded; the unconditional assignment above already preserves
        # the real candidate_run result against a classification raise.
        attempt_record["repaired_result"] = (
            _result_to_dict(candidate_run) if test_verdict != "build_failed" else _result_to_dict(candidate_build)
        )
        if materials_drift:
            outcome = "REPAIR_NOT_VERIFIED"
        else:
            outcome = "REPAIR_VERIFIED" if test_verdict == "passed" else "REPAIR_NOT_VERIFIED"
        if test_verdict == "passed" and not materials_drift:
            # Terminal audit only after generation/validation ends; no
            # proprietary/forbidden-source corpus exists for this task (the
            # approved spec's forbidden_sources are enforced by never
            # fetching such material in the first place), so corpus-backed
            # checks honestly report UNAVAILABLE -- never a fabricated PASS.
            final_audit = run_audit(patch_text)
            if reject_on_audit_flag(final_audit):
                outcome = "REPAIR_REJECTED_AUDIT"

        if test_verdict == "build_failed":
            # The raw build-failure diagnostics (compiler stdout/stderr,
            # which routinely echoes verbatim fragments of the candidate's
            # own source around each error) are kept in their own private
            # field, never embedded in the outcome label itself -- this
            # label is a bounded class that crosses into
            # ``run_xodus_shadow_build``'s own documented source-free
            # return value and into ``summarize_receipt``.
            attempt_record["outcome"] = "BUILD_FAILED"
            attempt_record["build_failure_result"] = _result_to_dict(candidate_build)
        else:
            attempt_record["outcome"] = outcome
        attempts.append(attempt_record)
        final_outcome = attempt_record["outcome"]
        selected_attempt_record = attempt_record

        if outcome in {"REPAIR_VERIFIED", "REPAIR_REJECTED_AUDIT"}:
            break
        if materials_drift:
            reason = "patch applied but the validation harness scaffold was altered during execution"
        else:
            reason = "patch applied but did not compile" if test_verdict == "build_failed" else (
                "patch applied and compiled but did not fix the reported bug"
            )
        prompt = base_prompt + _RETRY_SUFFIX.format(reason=reason)

    if final_outcome is None:
        # Every attempt was exhausted on a PATCH_REJECTED/EXECUTION_ERROR
        # retry without ever reaching a classified candidate run: the honest
        # final outcome is that last attempt's own recorded outcome class
        # (e.g. "PATCH_REJECTED"), never a silent "REPAIR_NOT_VERIFIED" that
        # would misrepresent a never-applied patch as one that was applied,
        # built, run, and simply failed to verify. Sanitized through the
        # same bounded-class whitelist a source-free export uses, since
        # this value crosses into this function's own documented
        # source-free return value.
        final_outcome = sanitize_outcome_class(attempts[-1]["outcome"]) if attempts else "REPAIR_NOT_VERIFIED"

    # The trajectory fields (prompt/raw_completion/model_identity) must
    # describe the SAME attempt the patch/result fields above came from --
    # ``selected_attempt_record`` is that one classified attempt, not
    # whichever attempt merely happened to run last (a later retry can be
    # rejected before classification while an earlier attempt's real,
    # if failing, result remains the reported one).
    reported_attempt = selected_attempt_record or (attempts[-1] if attempts else None)
    if reported_attempt is not None:
        final_patch_text = reported_attempt["patch_text"]
        final_touched = reported_attempt["touched_paths"]
        final_materials = reported_attempt["materials"]
        final_baseline = reported_attempt["baseline_result"]
        final_repaired = reported_attempt["repaired_result"]
        common_fields["prompt"] = reported_attempt["prompt"]
        common_fields["raw_completion"] = reported_attempt["raw_completion"]
        # Refresh the receipt's top-level model identity from the actual
        # reported attempt's own post-inference snapshot: the identity
        # captured in common_fields above was taken before the first
        # model.complete() call, so its lastInputTokenCount is always null.
        common_fields["model_identity"] = reported_attempt["model_identity"]
        # See the identical rationale in each.clean_room.run_clean_room_build:
        # a selected attempt whose own validation scaffold drifted during
        # execution -- or never even reached the point the check runs at
        # all (e.g. every attempt was rejected before a candidate build
        # ever happened) -- must never still be reported under the
        # strongest assurance label, even though the raw network probe
        # genuinely passed (F4). An UNPERFORMED check defaults to
        # "UNAVAILABLE", never silently to "PASS": only an explicit "PASS"
        # keeps the configured assurance level, anything else (including a
        # missing key) downgrades it.
        if reported_attempt.get("materials_integrity", "UNAVAILABLE") != "PASS" and common_fields["assurance_level"] == "EACH-P2":
            common_fields["assurance_level"] = "EACH-P1"
    else:
        final_patch_text = ""
        final_touched = []
    common_fields["audit"] = final_audit
    common_fields["selected_attempt"] = reported_attempt["attempt"] if reported_attempt is not None else None
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
    # materialize_root is the pristine host-side source tree: never
    # mutated by apply_patch() (patches are applied only to a disposable
    # per-attempt worktree copy), so it is always the correct -- and
    # attempt-invariant -- source for the materials this receipt declared
    # BEFORE any attempt's patch was ever applied (F5).
    json_path, md_path = receipt.write(runs_dir() / run_id, materials_source=materialize_root)
    return {
        "outcome": sanitize_outcome_class(final_outcome),
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
        "outcome": sanitize_outcome_class(data["outcome"]),
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
        "attemptOutcomes": [sanitize_outcome_class(a.get("outcome", "")) for a in data.get("attempts", [])],
        "selectedAttempt": data.get("selectedAttempt"),
        "materialsManifest": data.get("materials", {}),
    }
