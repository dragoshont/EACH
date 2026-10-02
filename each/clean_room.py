"""M7: a sealed, source-isolated Builder run for a bounded, black-box,
clean-room-style demonstration target.

Reuses the exact validated-before-audit / audit-terminal pipeline shape
already proven in :mod:`each.bakeoff` and hardened in :mod:`each.benchmark`
(the M4/M5 fixes): a candidate must pass real baseline-fails/repaired-passes
test validation before the terminal audit ever runs; an audit rejection
ends the run and is never fed back into another Builder attempt; only the
original approved spec -- never a discovered match or audit finding -- can
ever seed a later attempt.

Also reuses each.benchmark's own pinned ``each-benchmark-runtime`` image
(pytest pre-installed before any sealed run, never installed at execution
time -- see docker/benchmark-runtime/Dockerfile) rather than inventing a
second mechanism for running a pytest-based acceptance command.

The Builder prompt is built ONLY from the approved spec's own
``problem_statement`` (itself built entirely from public documentation and
recorded black-box observations -- see the spec's own material origins) and
the current (stub) contents of the one file the spec declares editable.
The terminal audit, by contrast, is explicitly permitted -- and expected --
to read the real reference implementation the Builder was never shown, to
check the candidate was not copied from it (that is the entire point of an
independent audit step).
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from each.audit.run import reject_on_audit_flag, run_audit
from each.benchmark import BENCHMARK_IMAGE_DIGEST, BenchmarkExecutionError, _interpret_pytest_run
from each.demo import _result_to_dict
from each.executor.container import ContainerExecutor, derive_assurance_level
from each.models.base import RepairModel
from each.outcome import sanitize_outcome_class
from each.patch import PatchRejected, apply_patch, extract_patch_text, parse_patch
from each.paths import runs_dir, validate_private_root, validate_task_id
from each.receipt import Receipt
from each.spec import ApprovedSpec
from each.worktree import build_worktree, verify_unchanged

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "examples" / "clean-room-lru-cache"

_PROMPT_TEMPLATE = """You are implementing a standalone Python module from a formal, hash-approved specification. You must implement this entirely yourself: do not import, read, invoke, or otherwise consult any third-party or standard-library implementation of the described behavior. The specification below is the ONLY permitted description of the required behavior.

{problem_statement}

Only this file may be changed: {path}

The file has exactly {line_count} lines. Its current contents, shown verbatim between the two marker lines below (the marker lines themselves are NOT part of the file and must NOT appear in your diff):
----- FILE CONTENT START -----
{numbered_source}
----- FILE CONTENT END -----

Here is a complete, fully worked example on an UNRELATED 2-line toy file -- it illustrates the exact wire format only; its content has nothing to do with the real task below.

Toy file "toy.py" (2 lines):
foo = 1
bar = 2

A correct diff changing those 2 lines to "foo = 10" and "bar = 20" looks exactly like this, with no other text:
BEGIN_PATCH
--- a/toy.py
+++ b/toy.py
@@ -1,2 +1,2 @@
-foo = 1
-bar = 2
+foo = 10
+bar = 20
END_PATCH

Now produce the REAL diff for {path} ({line_count} lines), replacing its entire content with your implementation, in the exact same wire format as the toy example above: reply with ONLY BEGIN_PATCH, the three diff header lines, one "-" line reproducing each of the {line_count} original lines verbatim character-for-character (in order, with no lines skipped or omitted), then one "+" line per line of your implementation, then END_PATCH. Do not use "..." or any other elision -- write out every single line literally, however many there are. Do not add markdown fences.

In the header, the number after "-1," must equal {line_count} -- that is the only number that is checked, and it must be an ordinary decimal integer computed by you from the {line_count}-line file shown above. The number after "+1," also must be an ordinary decimal integer digit sequence (it is not checked for correctness), but it must never be left as English text, angle brackets, or anything other than digits.
"""

_RETRY_SUFFIX = (
    "\n\nYour previous attempt was rejected: {reason}\n"
    "Try again, following the exact wire format shown in the toy example above: write out "
    "every one of the {line_count} original lines as its own \"-\" line, verbatim, with no "
    "elision and no lines skipped, then your replacement as \"+\" lines. Implement this "
    "yourself from the specification only; do not reference any external library's "
    "implementation."
)


def run_clean_room_build(
    model: RepairModel,
    approved: ApprovedSpec,
    *,
    audit_corpus: list[str] | None = None,
    corpus_revision: str = "none",
    max_attempts: int = 3,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run one sealed Builder attempt sequence for ``approved`` (an M7-style
    from-scratch, black-box clean-room spec), fully reusing the proven
    isolation / validation / terminal-audit / signed-receipt pipeline.

    ``audit_corpus`` is the real reference implementation's source, read
    only for the terminal audit comparison -- never shown to the Builder
    and never read by this function's own prompt-construction code path.
    """
    approved.verify()
    validate_private_root()
    packet = approved.packet
    if len(packet.allowed_paths) != 1 or len(packet.acceptance_commands) != 1:
        raise ValueError("run_clean_room_build currently supports exactly one allowed path and one acceptance command")
    allowed_path = packet.allowed_paths[0]
    acceptance_command = list(packet.acceptance_commands[0])
    test_path = next(arg for arg in acceptance_command if arg.endswith(".py"))

    run_id = run_id or f"clean-room-{uuid.uuid4().hex[:8]}"
    validate_task_id(run_id)
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")

    include_paths = [allowed_path, test_path]

    executor = ContainerExecutor(image=BENCHMARK_IMAGE_DIGEST)
    probe_worktree, _probe_manifest = build_worktree(FIXTURE_ROOT, include_paths)
    isolation_result = executor.verify_isolation(probe_worktree)
    assurance_level = derive_assurance_level(executor, isolation_result)
    # Captured once, from the real pre-run probe only, and never itself
    # downgraded later: this is the raw network-isolation fact. The
    # authoring-assurance claim (``assurance_level``) is a separate,
    # broader judgement that MAY be downgraded below if this run's own
    # selected attempt shows materials drift -- but that downgrade must
    # never be allowed to quietly erase or conflate the plain isolation
    # fact itself (F4).
    network_isolation_verified = assurance_level == "EACH-P2"
    isolation_evidence = _result_to_dict(isolation_result)

    stub_source = (FIXTURE_ROOT / allowed_path).read_text(encoding="utf-8")
    stub_lines = stub_source.splitlines()
    line_count = len(stub_lines)
    base_prompt = _PROMPT_TEMPLATE.format(
        problem_statement=packet.problem_statement,
        path=allowed_path,
        line_count=line_count,
        numbered_source=stub_source,
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

    expected_tests = 0  # resolved from the genuine baseline run's own pytest summary below.
    attempts: list[dict[str, Any]] = []
    prompt = base_prompt
    # No sentinel default: REPAIR_NOT_VERIFIED is only a valid final outcome
    # once a patch actually applied and the repaired-test run was classified.
    # If every attempt is exhausted on a PATCH_REJECTED retry (never reaching
    # that point), this stays None and is resolved from the real last
    # attempt's own outcome after the loop -- never silently mislabeled as a
    # verified-but-failing repair that never happened. Matches each.benchmark's
    # identical fix.
    final_outcome: str | None = None
    final_audit = common_fields["audit"]
    # Resolved to the real classified attempt below -- never left to
    # default to "whatever attempt happened to run last" (see the
    # identical fix in each.xodus_shadow for the exact failure mode this
    # guards against). Every final_* field reported below is read back OUT
    # of this one selected attempt's own recorded dict (F6 fix), never left
    # as a separate loop-scoped variable that an unrelated later iteration
    # (e.g. a retry that never even reaches the point that variable was
    # last assigned in) could leave stale or silently overwrite.
    selected_attempt_record: dict[str, Any] | None = None

    for attempt_num in range(1, max_attempts + 1):
        worktree, manifest = build_worktree(FIXTURE_ROOT, include_paths)
        baseline = executor.run(acceptance_command, worktree)
        if expected_tests == 0:
            combined = baseline.stdout + baseline.stderr
            failed_match = re.search(r"(\d+) failed", combined)
            if not failed_match:
                raise BenchmarkExecutionError(f"could not determine baseline failing test count: {combined!r}")
            expected_tests = int(failed_match.group(1))
        baseline_verdict = _interpret_pytest_run(baseline, expected_tests=expected_tests)
        baseline_dict = _result_to_dict(baseline)
        raw_completion = model.complete(prompt)
        rendered_prompt = getattr(model, "last_prompt", None)
        attempt_record: dict[str, Any] = {
            "attempt": attempt_num,
            "prompt": rendered_prompt if rendered_prompt is not None else prompt,
            "raw_completion": raw_completion,
            "materials": manifest,
            "baseline_result": baseline_dict,
            "patch_text": "",
            "touched_paths": [],
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
            prompt = base_prompt + _RETRY_SUFFIX.format(reason=str(exc), line_count=line_count)
            continue

        repaired = executor.run(acceptance_command, worktree)
        # A Docker-launch failure or an ambiguous (skip/error-containing)
        # run is not repair-failure evidence; let it propagate uncaught,
        # matching each.bakeoff's precedent exactly.
        repaired_verdict = _interpret_pytest_run(repaired, expected_tests=expected_tests)
        test_outcome = (
            "REPAIR_VERIFIED" if (baseline_verdict == "failed" and repaired_verdict == "passed") else "REPAIR_NOT_VERIFIED"
        )

        # The test file (``test_path``) is not Builder input -- it is part
        # of this harness's own validation scaffold. A candidate run that
        # altered it mid-execution must never be reported as a verified
        # repair (see the identical fix in each.xodus_shadow).
        materials_drift = verify_unchanged(worktree, manifest, [test_path])
        attempt_record["materials_integrity"] = (
            "PASS" if not materials_drift else f"FAIL: {len(materials_drift)} path(s) drifted"
        )

        attempt_record["patch_text"] = patch_text
        attempt_record["touched_paths"] = touched
        attempt_record["repaired_result"] = _result_to_dict(repaired)
        outcome = test_outcome if not materials_drift else "REPAIR_NOT_VERIFIED"
        if test_outcome == "REPAIR_VERIFIED" and not materials_drift:
            # Terminal audit only after generation/validation ends; this is
            # the one point where real reference material may be read, and
            # only for comparison -- never surfaced back to the Builder.
            final_candidate_source = "\n".join(
                (worktree / path).read_text(encoding="utf-8", errors="replace") for path in touched
            )
            final_audit = run_audit(final_candidate_source, corpus=audit_corpus, corpus_revision=corpus_revision)
            if reject_on_audit_flag(final_audit):
                outcome = "REPAIR_REJECTED_AUDIT"

        attempt_record["outcome"] = outcome
        attempts.append(attempt_record)
        final_outcome = outcome
        selected_attempt_record = attempt_record

        if outcome in {"REPAIR_VERIFIED", "REPAIR_REJECTED_AUDIT"}:
            break
        reason = (
            "patch applied but the validation harness scaffold was altered during execution"
            if materials_drift
            else "patch applied but did not make the failing tests pass"
        )
        prompt = base_prompt + _RETRY_SUFFIX.format(reason=reason, line_count=line_count)

    if final_outcome is None:
        # Every attempt was exhausted on a PATCH_REJECTED retry without ever
        # reaching a classified repaired-test run: the honest final outcome
        # is that last attempt's own recorded outcome class, never a silent
        # "REPAIR_NOT_VERIFIED" that would misrepresent a never-applied
        # patch as one that was applied, tested, and simply failed to
        # verify. Sanitized through the same bounded-class whitelist a
        # source-free export uses.
        final_outcome = sanitize_outcome_class(attempts[-1]["outcome"]) if attempts else "REPAIR_NOT_VERIFIED"

    # Every final_* field reported in this receipt is read back OUT of the
    # one selected attempt's own recorded dict (F6 fix) -- never from a
    # separate loop-scoped variable that an attempt which never even
    # reached that point (e.g. a PATCH_REJECTED retry) could leave stale.
    reported_attempt = selected_attempt_record or (attempts[-1] if attempts else None)
    if reported_attempt is not None:
        final_patch_text = reported_attempt["patch_text"]
        final_touched = reported_attempt["touched_paths"]
        final_materials = reported_attempt["materials"]
        final_baseline = reported_attempt["baseline_result"]
        final_repaired = reported_attempt["repaired_result"]
    else:
        final_patch_text = ""
        final_touched = []
        final_materials = {}
        final_baseline = {}
        final_repaired = {}
    if reported_attempt is not None:
        common_fields["prompt"] = reported_attempt["prompt"]
        common_fields["raw_completion"] = reported_attempt["raw_completion"]
        common_fields["model_identity"] = reported_attempt["model_identity"]
        # "EACH-P2" is a complete authoring-assurance claim, not just a
        # network-isolation fact: a selected attempt whose own validation
        # scaffold was found to have drifted during execution must never
        # still be reported under the strongest assurance label, even
        # though the raw network probe (``network_isolation_verified``
        # above) genuinely did pass (F4).
        if reported_attempt.get("materials_integrity", "PASS") != "PASS" and common_fields["assurance_level"] == "EACH-P2":
            common_fields["assurance_level"] = "EACH-P1"
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
    # The pristine fixture root is never mutated by apply_patch() (patches
    # are applied only to a disposable per-attempt worktree copy), so it is
    # always the correct -- and attempt-invariant -- source for the
    # materials this receipt declared BEFORE any attempt's patch was ever
    # applied. Passing a post-patch worktree here (the prior bug) copied
    # candidate-mutated bytes under a pre-patch declared hash (F5).
    json_path, md_path = receipt.write(runs_dir() / run_id, materials_source=FIXTURE_ROOT)
    return {
        "outcome": final_outcome,
        "receipt_json": str(json_path),
        "receipt_md": str(md_path),
        "attempts": len(attempts),
    }
