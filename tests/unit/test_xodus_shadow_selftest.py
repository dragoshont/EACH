"""Harness self-test for the M8 real-source shadow-demonstration Builder
pipeline, using a deterministic ``FixtureModel`` canned response -- never
the real declared local model -- purely to validate the fetch/merge/
worktree/patch/validate/audit/sign wiring before spending real local-model
inference time. This is explicitly NOT the accepted M8 evidence; the
accepted receipt must come from a real ``RepairModel`` run against the
recorded local model (see docs/EACH_BOOTSTRAP_MANDATE.md M8 and
``each.xodus_shadow``'s own docstring).

The cached source fixture (``tests/unit/data/xsystem_selftest_source.c``)
is a byte-identical copy of the real, pinned, public
``xodus-gaming/xgameruntime`` file at the exact approved-spec commit --
fetched once, here cached for deterministic/offline tests, never altered.
``each.benchmark.fetch_file`` is monkeypatched to return it instead of
making a real network call during this self-test.

Requires the real, dedicated ``docker --context colima-each`` daemon AND
the locally pre-built ``each-m8-native-runtime`` image (see
``docker/m8-native-runtime/Dockerfile``); skipped, not silently passed,
when either is unavailable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

import each.xodus_shadow as xodus_shadow_module
from each.models.fixture import FixtureModel
from each.spec import ApprovedSpec, make_spec_packet
from each.spec_workflow import specs_dir
from each.xodus_shadow import run_xodus_shadow_build, summarize_receipt
from tests.adversarial._docker_guard import requires_colima_each

_CORRECT_PATCH = (Path(__file__).parent / "data" / "xodus_shadow_selftest_patch.txt").read_text()
_CACHED_SOURCE = (Path(__file__).parent / "data" / "xsystem_selftest_source.c").read_text()
# Applies cleanly and compiles (so the attempt is classifiable) but only
# fixes one of the two bugged lines, so the repaired acceptance run still
# fails -- used only to exercise the F6 trajectory-consistency fix below.
_APPLIES_BUT_LEAVES_BUG_PATCH = (
    Path(__file__).parent / "data" / "xodus_shadow_selftest_patch_applies_but_leaves_bug.txt"
).read_text()


def _native_image_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        proc = subprocess.run(
            ["docker", "--context", "colima-each", "image", "inspect", xodus_shadow_module.NATIVE_IMAGE_DIGEST],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


requires_m8_native_image = pytest.mark.skipif(
    not _native_image_available(),
    reason="each-m8-native-runtime image not built locally (see docker/m8-native-runtime/Dockerfile)",
)


def _approve_selftest_spec(task_id: str) -> ApprovedSpec:
    """Build and approve a self-test spec, durably recording its approval
    at the exact path :func:`each.xodus_policy.verify_xodus_shadow_binding`
    reads (``~/.each/specs/<task_id>/approved.json``) -- a plain in-memory
    ``ApprovedSpec.approve(...)`` is no longer sufficient to run the real
    pipeline, by design (F2): it must be a genuine, durably recorded
    approval, not a caller-constructed object nothing else ever sees.
    ``sensitive=True`` is required because this self-test's own
    ``target_repo`` is one of ``policies/xodus-shadow.yml``'s declared
    strict-run repositories.
    """
    packet = make_spec_packet(
        task_id=task_id,
        target_repo="https://github.com/xodus-gaming/xgameruntime",
        target_ref="791710510d9ba0746bbd60754215eb321800e4f0",
        problem_statement="Harness self-test stand-in for the real M8 spec problem statement.",
        allowed_paths=["xsystem.c"],
        build_commands=[["python3", "examples/xodus-m8-sandbox-id/build_check.py", "build", "xsystem.c"]],
        acceptance_commands=[["python3", "examples/xodus-m8-sandbox-id/build_check.py", "run"]],
        forbidden_sources=["proprietary-implementation", "decompiler-output", "disassembly", "unauthorized-runtime-trace"],
        approved_by="harness-selftest",
        sensitive=True,
    )
    approved = ApprovedSpec.approve(packet)
    task_dir = specs_dir() / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    approved_path = task_dir / "approved.json"
    approved_path.write_text(json.dumps(approved.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return approved


@requires_colima_each
@requires_m8_native_image
def test_fixture_model_candidate_is_verified_and_signed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    approved = _approve_selftest_spec("test-xodus-shadow-harness-selftest")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(model, approved, max_attempts=1, run_id=f"selftest-{tmp_path.name}-{uuid.uuid4().hex[:8]}")

    assert result["outcome"] == "REPAIR_VERIFIED"
    assert result["attempts"] == 1
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["assuranceLevel"] == "EACH-P2"
    assert receipt["networkIsolationVerified"] is True
    assert receipt["attempts"][0]["outcome"] == "REPAIR_VERIFIED"
    assert receipt["baselineResult"]["exit_code"] == 1
    assert receipt["repairedResult"]["exit_code"] == 0
    assert set(receipt["audit"]["checks"]) == {
        "exact-substring",
        "ngram-similarity",
        "ast-similarity",
        "license-scan",
        "corpus-membership",
    }
    # F5: the real materials/ files are actually retained and verifiable,
    # not just declared in the receipt's own JSON (and not a post-patch
    # candidate-mutated copy falsely declared under the pre-patch hash).
    from each.attestation import verify_materials_root

    materials_root = Path(result["receipt_json"]).parent / "materials"
    full_result = verify_materials_root(receipt, materials_root)
    assert full_result["status"] == "PASS"
    # F6: the top-level materials/baseline/repaired fields must come from
    # the one selected/classified attempt's own recorded dict.
    assert receipt["materials"] == receipt["attempts"][0]["materials"]
    assert receipt["baselineResult"] == receipt["attempts"][0]["baseline_result"]
    assert receipt["repairedResult"] == receipt["attempts"][0]["repaired_result"]

    summary = summarize_receipt(result["receipt_json"])
    assert summary["outcome"] == "REPAIR_VERIFIED"
    assert "prompt" not in summary
    assert "rawCompletion" not in summary
    assert "patchText" not in summary


@requires_colima_each
@requires_m8_native_image
def test_xodus_shadow_assurance_level_is_downgraded_to_p1_when_the_selected_attempts_materials_drift(
    tmp_path, monkeypatch
) -> None:
    """F4: the raw network-isolation probe genuinely passes, but the
    broader authoring-assurance claim must be conservatively downgraded
    when the selected attempt's own validation scaffold drifted during
    execution."""
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    monkeypatch.setattr(
        xodus_shadow_module,
        "verify_unchanged",
        lambda *_a, **_k: ["examples/xodus-m8-sandbox-id/build_check.py"],
    )
    approved = _approve_selftest_spec("test-xodus-shadow-assurance-downgrade")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(
        model, approved, max_attempts=1, run_id=f"selftest-drift-{tmp_path.name}-{uuid.uuid4().hex[:8]}"
    )

    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["networkIsolationVerified"] is True
    assert receipt["assuranceLevel"] == "EACH-P1"
    assert receipt["outcome"] == "REPAIR_NOT_VERIFIED"


@requires_colima_each
@requires_m8_native_image
def test_xodus_shadow_fails_closed_when_isolation_cannot_be_verified(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    monkeypatch.setattr(xodus_shadow_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P1")
    approved = _approve_selftest_spec("test-xodus-shadow-isolation-fail-closed")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(model, approved, max_attempts=3, run_id=f"selftest-iso-{tmp_path.name}-{uuid.uuid4().hex[:8]}")

    assert result["outcome"] == "ISOLATION_UNVERIFIED"
    assert result["attempts"] == 0
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["patchText"] == ""
    assert receipt["attempts"] == []


@requires_colima_each
@requires_m8_native_image
def test_xodus_shadow_audit_match_is_terminal_without_builder_feedback(tmp_path, monkeypatch) -> None:
    """Regression for the M4/994413b Auditor-is-terminal fix, replicated on
    this surface: a discovered audit match must end the run after exactly
    one Builder call, never triggering a second attempt or leaking the
    match hint back into a later prompt."""
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    forbidden_hint = "FORBIDDEN_POST_GENERATION_SOURCE_MATCH"

    calls: list[str] = []

    class CapturingModel(FixtureModel):
        def complete(self, prompt: str) -> str:
            calls.append(prompt)
            return super().complete(prompt)

    def discovered_match(source: str, *, corpus=None, corpus_revision="none"):
        assert len(calls) == 1
        assert source
        return {
            "checks": {"exact-substring": {"status": "FAIL", "sourceHint": forbidden_hint}},
            "result": "FAIL",
            "corpusRevision": corpus_revision,
        }

    monkeypatch.setattr(xodus_shadow_module, "run_audit", discovered_match)
    approved = _approve_selftest_spec("test-xodus-shadow-audit-terminal")
    model = CapturingModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(model, approved, max_attempts=3, run_id=f"selftest-audit-{tmp_path.name}-{uuid.uuid4().hex[:8]}")

    assert result["outcome"] == "REPAIR_REJECTED_AUDIT"
    assert result["attempts"] == len(calls) == 1
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["audit"]["result"] == "FAIL"
    assert all(forbidden_hint not in prompt for prompt in calls)


_ALREADY_FIXED_SOURCE = _CACHED_SOURCE.replace(
    "if (!sandboxId || !sandboxIdUsed)", "if (!sandboxId)"
).replace(
    "*sandboxIdUsed = strlen( Id ) + 1;", "if (sandboxIdUsed) *sandboxIdUsed = strlen( Id ) + 1;"
)


@requires_colima_each
@requires_m8_native_image
def test_xodus_shadow_baseline_must_genuinely_reproduce_the_bug(tmp_path, monkeypatch) -> None:
    """If the fetched 'buggy' source is actually already fixed, this harness
    must raise rather than silently accept a vacuous (never-failing)
    baseline -- proving this is a real regression check, not a fake one."""
    assert _ALREADY_FIXED_SOURCE != _CACHED_SOURCE
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _ALREADY_FIXED_SOURCE)
    approved = _approve_selftest_spec("test-xodus-shadow-baseline-honesty")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    from each.benchmark import BenchmarkExecutionError

    with pytest.raises(BenchmarkExecutionError):
        run_xodus_shadow_build(model, approved, max_attempts=1, run_id=f"selftest-baseline-{tmp_path.name}-{uuid.uuid4().hex[:8]}")


@requires_colima_each
@requires_m8_native_image
def test_exhausting_all_attempts_on_a_rejected_patch_reports_that_real_outcome_not_a_false_repair_not_verified(
    tmp_path,
) -> None:
    """Regression for the same mislabeling bug each.benchmark/each.clean_room
    already fix: if every attempt is exhausted on a malformed/rejected
    completion (never reaching a classified build/run), the receipt's final
    outcome must be the real last attempt's own outcome (e.g.
    "PATCH_REJECTED: ..."), not a sentinel "REPAIR_NOT_VERIFIED" that
    falsely implies a patch was applied, built, run, and simply failed."""
    approved = _approve_selftest_spec("test-xodus-shadow-all-attempts-rejected")
    model = FixtureModel("this completion has no patch markers at all", model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(model, approved, max_attempts=2, run_id=f"selftest-rejected-{tmp_path.name}-{uuid.uuid4().hex[:8]}")

    assert result["outcome"].startswith("PATCH_REJECTED")
    assert result["outcome"] != "REPAIR_NOT_VERIFIED"
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["outcome"].startswith("PATCH_REJECTED")
    assert len(receipt["attempts"]) == 2
    assert all(a["outcome"].startswith("PATCH_REJECTED") for a in receipt["attempts"])
    # F4: no attempt ever reached the point the materials-integrity check
    # runs at all (every attempt was rejected before any candidate
    # build/run) -- an UNPERFORMED required check must never be silently
    # treated as PASS, so the receipt must never claim the strongest
    # EACH-P2 authoring-assurance label here even though the raw network
    # probe genuinely passed.
    assert receipt["networkIsolationVerified"] is True
    assert receipt["assuranceLevel"] != "EACH-P2"


@requires_colima_each
@requires_m8_native_image
def test_an_execution_error_still_preserves_the_applied_patch_and_real_build_run_results(tmp_path, monkeypatch) -> None:
    """F6 regression: a patch that genuinely applies, builds, and runs, but
    whose (build, run) pair ``_interpret_native_run`` cannot classify, must
    never lose that real applied patch / real build / real run evidence --
    both must be recorded on the attempt BEFORE classification runs, so
    they survive a classification-time raise rather than being left at
    their initial empty defaults."""
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    real_interpret = xodus_shadow_module._interpret_native_run
    call_count = 0

    def _flaky_interpret(build_result, run_result):
        nonlocal call_count
        call_count += 1
        # Call 1 is the pre-loop BASELINE classification (must stay real);
        # call 2 is the per-attempt candidate classification this test
        # exercises.
        if call_count == 2:
            raise xodus_shadow_module.BenchmarkExecutionError("simulated ambiguous native build/run output")
        return real_interpret(build_result, run_result)

    monkeypatch.setattr(xodus_shadow_module, "_interpret_native_run", _flaky_interpret)
    approved = _approve_selftest_spec("test-xodus-shadow-execution-error-preserves-evidence")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(
        model, approved, max_attempts=1, run_id=f"selftest-execerr-{tmp_path.name}-{uuid.uuid4().hex[:8]}"
    )

    assert result["outcome"].startswith("EXECUTION_ERROR")
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["outcome"].startswith("EXECUTION_ERROR")
    assert len(receipt["attempts"]) == 1
    attempt = receipt["attempts"][0]
    assert attempt["patch_text"]
    assert attempt["touched_paths"]
    assert attempt["repaired_result"]
    assert attempt["repaired_result"]["exit_code"] is not None
    assert real_interpret is not None  # the genuine function, unused here, confirms monkeypatch replaced it


@requires_colima_each
@requires_m8_native_image
def test_a_real_container_timeout_during_the_acceptance_run_preserves_the_build_result_and_finalizes_a_partial_receipt(
    tmp_path, monkeypatch
) -> None:
    """F6 regression: a patch that genuinely applies and builds, but whose
    acceptance-run ``executor.run`` call itself raises ``ContainerExecutorError``
    (a real container-launch/timeout failure, not merely an ambiguous
    classification), must never propagate uncaught out of the whole
    function -- it must finalize a truthful, signed, partial receipt with
    the real build result preserved, the run result explicitly absent (no
    fabricated exit code), a conservative EACH-P1 assurance level, and the
    private diagnostic text kept out of the source-free summary view.

    Calls 1-4 (the isolation probe, the real baseline build, the real
    baseline run, and this attempt's real candidate build) are allowed to
    execute for real against the dedicated colima-each executor; only call
    5 (this attempt's acceptance run) is forced to raise."""
    import each.executor.container as container_module

    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    original_run = container_module.ContainerExecutor.run
    call_count = 0

    def _flaky_run(self, command, worktree, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 5:
            raise container_module.ContainerExecutorError("simulated fixture container timeout")
        return original_run(self, command, worktree, **kwargs)

    monkeypatch.setattr(container_module.ContainerExecutor, "run", _flaky_run)
    approved = _approve_selftest_spec("test-xodus-shadow-real-container-timeout")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(
        model, approved, max_attempts=1, run_id=f"selftest-timeout-{tmp_path.name}-{uuid.uuid4().hex[:8]}"
    )

    assert call_count == 5
    assert result["outcome"].startswith("EXECUTION_ERROR")
    receipt_path = Path(result["receipt_json"])
    assert receipt_path.is_file()
    receipt = json.loads(receipt_path.read_text())
    assert receipt["outcome"].startswith("EXECUTION_ERROR")
    assert len(receipt["attempts"]) == 1
    attempt = receipt["attempts"][0]
    assert attempt["patch_text"]
    assert attempt["touched_paths"]
    assert attempt["build_result"] is not None
    assert attempt["build_result"]["exit_code"] == 0
    assert attempt["run_result"] is None
    assert attempt["materials_integrity"] == "UNAVAILABLE"
    assert result["outcome"] == "EXECUTION_ERROR"
    assert "simulated fixture container timeout" not in json.dumps(result)
    assert receipt["repairedResult"] == {}
    # A genuine network-isolation PROBE pass stays recorded as a plain fact,
    # but the broader authoring-assurance claim must still be conservatively
    # downgraded: an unperformed materials-integrity check is never "PASS".
    assert receipt["networkIsolationVerified"] is True
    assert receipt["assuranceLevel"] == "EACH-P1"

    # Signature-only verification must still PASS for this honest, signed
    # partial receipt.
    from each.cli import main as each_cli_main

    assert each_cli_main(["verify", str(receipt_path)]) == 0

    # The private diagnostic text ("simulated fixture container timeout")
    # must never cross into the source-free summary view.
    summary = summarize_receipt(result["receipt_json"])
    summary_text = json.dumps(summary)
    assert "simulated fixture container timeout" not in summary_text
    assert summary["outcome"] == "EXECUTION_ERROR"
    assert summary["repairedExitCode"] is None


@requires_colima_each
@requires_m8_native_image
def test_an_earlier_completed_attempt_is_preserved_when_a_later_attempt_hits_a_real_container_error(
    tmp_path, monkeypatch
) -> None:
    """F6 regression: attempt 1 applies cleanly but does not fix the bug
    (REPAIR_NOT_VERIFIED, a real classified attempt); attempt 2's
    acceptance run hits a real ``ContainerExecutorError``. The receipt must
    retain BOTH attempts (never silently drop attempt 1's real evidence),
    and the top-level/selected-attempt fields must consistently describe
    whichever attempt is actually reported as final -- never a mix of the
    two."""
    import each.executor.container as container_module

    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    # A patch that applies and compiles cleanly but only fixes one of the
    # two bugged lines, so case1 of the real acceptance driver still fails
    # (hr stays E_POINTER) -- a genuine, cleanly classified REPAIR_NOT_VERIFIED,
    # not a PatchRejected/crash/ambiguous outcome -- before attempt 2 starts.
    wrong_patch = _APPLIES_BUT_LEAVES_BUG_PATCH

    original_run = container_module.ContainerExecutor.run
    call_count = 0
    # Calls: 1 probe, 2 baseline build, 3 baseline run, 4 attempt-1 build,
    # 5 attempt-1 run (real, classified REPAIR_NOT_VERIFIED), 6 attempt-2
    # build (real), 7 attempt-2 run -> forced ContainerExecutorError.
    FAIL_ON_CALL = 7

    def _flaky_run(self, command, worktree, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == FAIL_ON_CALL:
            raise container_module.ContainerExecutorError("simulated fixture container timeout (attempt 2)")
        return original_run(self, command, worktree, **kwargs)

    monkeypatch.setattr(container_module.ContainerExecutor, "run", _flaky_run)
    approved = _approve_selftest_spec("test-xodus-shadow-later-attempt-container-error")

    class SequenceModel(FixtureModel):
        def __init__(self, responses: list[str], model_id: str) -> None:
            super().__init__(responses[0], model_id=model_id)
            self._responses = responses
            self._call_count = 0

        def complete(self, prompt: str) -> str:
            response = self._responses[self._call_count]
            self._call_count += 1
            self.last_prompt = prompt
            return response

    model = SequenceModel([wrong_patch, _CORRECT_PATCH], model_id="fixture/xodus-shadow-selftest-sequence-v1")

    result = run_xodus_shadow_build(
        model, approved, max_attempts=2, run_id=f"selftest-later-timeout-{tmp_path.name}-{uuid.uuid4().hex[:8]}"
    )

    assert call_count == FAIL_ON_CALL
    assert result["outcome"].startswith("EXECUTION_ERROR")
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert len(receipt["attempts"]) == 2
    assert receipt["attempts"][0]["outcome"] == "REPAIR_NOT_VERIFIED"
    assert receipt["attempts"][0]["build_result"] is not None
    assert receipt["attempts"][0]["run_result"] is not None
    assert receipt["attempts"][1]["outcome"].startswith("EXECUTION_ERROR")
    assert receipt["attempts"][1]["build_result"] is not None
    assert receipt["attempts"][1]["run_result"] is None
    # The reported top-level/selected fields must describe attempt 2 (the
    # real final attempt), never a stale mix with attempt 1's.
    assert receipt["selectedAttempt"] == 2
    assert receipt["outcome"] == receipt["attempts"][1]["outcome"]
