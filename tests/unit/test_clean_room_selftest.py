"""Harness self-test for the M7 clean-room Builder pipeline, using a
deterministic ``FixtureModel`` canned response -- never the real declared
local model -- purely to validate the worktree/patch/validate/audit/sign
wiring before spending real local-model inference time. This is explicitly
NOT the accepted M7 evidence; the accepted receipt must come from a real
``RepairModel`` run against the recorded local model (see
docs/EACH_BOOTSTRAP_MANDATE.md M7 and ``each.clean_room``'s own docstring).

Requires the real, dedicated ``docker --context colima-each`` daemon (the
same no-network executor every other milestone's real evidence uses); it is
skipped, not silently passed, when that daemon is unreachable.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import each.clean_room as clean_room_module
from each.benchmark import BenchmarkExecutionError
from each.clean_room import run_clean_room_build
from each.models.fixture import FixtureModel
from each.spec import ApprovedSpec, make_spec_packet
from tests.adversarial._docker_guard import requires_colima_each

# A hand-written, line-exact unified diff against the real stub file (built
# and independently verified to apply cleanly via each.patch.apply_patch and
# to pass all 9 real acceptance tests, outside any container, before being
# wired into this harness self-test) -- not the actual M7 Builder output.
_CORRECT_PATCH = (Path(__file__).parent / "data" / "clean_room_selftest_patch.txt").read_text()

# Applies cleanly (so the attempt is classifiable) but does not actually
# implement caching, so the repaired-test run still fails -- used only to
# exercise the F6 trajectory-consistency fix below.
_APPLIES_BUT_FAILS_PATCH = (
    Path(__file__).parent / "data" / "clean_room_selftest_patch_applies_but_fails_tests.txt"
).read_text()


def _approve_selftest_spec(task_id: str) -> ApprovedSpec:
    packet = make_spec_packet(
        task_id=task_id,
        target_repo="test/fixture",
        target_ref="local-fixture",
        problem_statement="Harness self-test stand-in for the real M7 spec problem statement.",
        allowed_paths=["shadow/m7/clean_room_lru_cache.py"],
        build_commands=[],
        acceptance_commands=[["pytest", "shadow/m7/test_clean_room_lru_cache.py", "-q"]],
        forbidden_sources=["network", "host-secrets", "host-home-mount"],
        approved_by="harness-selftest",
    )
    return ApprovedSpec.approve(packet)


@requires_colima_each
def test_fixture_model_candidate_is_verified_and_signed(tmp_path) -> None:
    approved = _approve_selftest_spec("test-clean-room-harness-selftest")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/clean-room-selftest-v1")

    result = run_clean_room_build(model, approved, max_attempts=1, run_id=f"selftest-{tmp_path.name}-{uuid.uuid4().hex[:8]}")

    assert result["outcome"] == "REPAIR_VERIFIED"
    assert result["attempts"] == 1
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["assuranceLevel"] == "EACH-P2"
    assert receipt["networkIsolationVerified"] is True
    assert receipt["attempts"][0]["outcome"] == "REPAIR_VERIFIED"
    assert set(receipt["audit"]["checks"]) == {
        "exact-substring",
        "ngram-similarity",
        "ast-similarity",
        "license-scan",
        "corpus-membership",
    }
    # F5: the real materials/ files are actually retained and verifiable,
    # not just declared in the receipt's own JSON.
    from each.attestation import verify_materials_root

    materials_root = Path(result["receipt_json"]).parent / "materials"
    full_result = verify_materials_root(receipt, materials_root)
    assert full_result["status"] == "PASS"


@requires_colima_each
def test_clean_room_fails_closed_when_isolation_cannot_be_verified(tmp_path, monkeypatch) -> None:
    """Same fail-closed branch each.bakeoff proves: the probe still runs for
    real, only the *derived* assurance level is forced non-P2, so no
    Builder call ever happens."""
    monkeypatch.setattr(clean_room_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P1")
    approved = _approve_selftest_spec("test-clean-room-isolation-fail-closed")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/clean-room-selftest-v1")

    result = run_clean_room_build(model, approved, max_attempts=3, run_id=f"selftest-iso-{tmp_path.name}-{uuid.uuid4().hex[:8]}")

    assert result["outcome"] == "ISOLATION_UNVERIFIED"
    assert result["attempts"] == 0
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["patchText"] == ""
    assert receipt["attempts"] == []


@requires_colima_each
def test_clean_room_audit_match_is_terminal_without_builder_feedback(tmp_path, monkeypatch) -> None:
    """Regression for the M4/994413b Auditor-is-terminal fix, replicated on
    this surface: a discovered audit match must end the run after exactly
    one Builder call, never triggering a second attempt or leaking the
    match hint back into a later prompt."""
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

    monkeypatch.setattr(clean_room_module, "run_audit", discovered_match)
    approved = _approve_selftest_spec("test-clean-room-audit-terminal")
    model = CapturingModel(_CORRECT_PATCH, model_id="fixture/clean-room-selftest-v1")

    result = run_clean_room_build(model, approved, max_attempts=3, run_id=f"selftest-audit-{tmp_path.name}-{uuid.uuid4().hex[:8]}")

    assert result["outcome"] == "REPAIR_REJECTED_AUDIT"
    assert result["attempts"] == len(calls) == 1
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["audit"]["result"] == "FAIL"
    assert all(forbidden_hint not in prompt for prompt in calls)


@requires_colima_each
def test_exhausting_all_attempts_on_a_rejected_patch_reports_that_real_outcome_not_a_false_repair_not_verified(
    tmp_path,
) -> None:
    """Regression for the same mislabeling bug each.benchmark already fixes:
    if every attempt is exhausted on a malformed/rejected completion (never
    reaching a classified repaired-test run), the receipt's final outcome
    must be the real last attempt's own outcome (e.g. "PATCH_REJECTED:
    ..."), not a sentinel "REPAIR_NOT_VERIFIED" that falsely implies a patch
    was applied and the repaired tests were run and failed."""
    approved = _approve_selftest_spec("test-clean-room-all-attempts-rejected")
    model = FixtureModel("this completion has no patch markers at all", model_id="fixture/clean-room-selftest-v1")

    result = run_clean_room_build(model, approved, max_attempts=2, run_id=f"selftest-rejected-{tmp_path.name}-{uuid.uuid4().hex[:8]}")

    assert result["outcome"].startswith("PATCH_REJECTED")
    assert result["outcome"] != "REPAIR_NOT_VERIFIED"
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["outcome"].startswith("PATCH_REJECTED")
    assert len(receipt["attempts"]) == 2
    assert all(a["outcome"].startswith("PATCH_REJECTED") for a in receipt["attempts"])
    # F4: no attempt ever reached the point the materials-integrity check
    # runs at all -- an UNPERFORMED required check must never be silently
    # treated as PASS.
    assert receipt["networkIsolationVerified"] is True
    assert receipt["assuranceLevel"] != "EACH-P2"


@requires_colima_each
def test_assurance_level_is_downgraded_to_p1_when_the_selected_attempts_materials_drift(tmp_path, monkeypatch) -> None:
    """F4: the raw network-isolation probe genuinely passes (recorded,
    unconditionally, as ``networkIsolationVerified``), but the broader
    authoring-assurance claim (``assuranceLevel``) must be conservatively
    downgraded when the actually-selected/reported attempt shows its own
    validation scaffold drifted during execution -- it must never still be
    reported under the strongest "EACH-P2" label just because the plain
    network fact alone passed."""
    monkeypatch.setattr(clean_room_module, "verify_unchanged", lambda *_a, **_k: ["shadow/m7/test_clean_room_lru_cache.py"])
    approved = _approve_selftest_spec("test-clean-room-assurance-downgrade")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/clean-room-selftest-v1")

    result = run_clean_room_build(
        model, approved, max_attempts=1, run_id=f"selftest-drift-{tmp_path.name}-{uuid.uuid4().hex[:8]}"
    )

    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["networkIsolationVerified"] is True
    assert receipt["assuranceLevel"] == "EACH-P1"
    assert receipt["outcome"] == "REPAIR_NOT_VERIFIED"


@requires_colima_each
def test_a_later_rejected_retry_never_overwrites_an_earlier_classified_attempts_trajectory(tmp_path) -> None:
    """F6 regression: attempt 1 applies cleanly and is classified
    (REPAIR_NOT_VERIFIED); attempt 2's completion has no patch markers at
    all and is PATCH_REJECTED. The receipt's top-level prompt/raw_completion
    /selectedAttempt must still describe attempt 1 -- the real classified
    attempt -- never silently shift to describe the later rejected retry
    just because it ran last."""

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

    model = SequenceModel(
        [_APPLIES_BUT_FAILS_PATCH, "this completion has no patch markers at all"],
        model_id="fixture/clean-room-selftest-sequence-v1",
    )
    approved = _approve_selftest_spec("test-clean-room-trajectory-consistency")

    result = run_clean_room_build(model, approved, max_attempts=2, run_id=f"selftest-traj-{tmp_path.name}-{uuid.uuid4().hex[:8]}")

    assert result["outcome"] == "REPAIR_NOT_VERIFIED"
    assert result["attempts"] == 2
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert len(receipt["attempts"]) == 2
    assert receipt["attempts"][0]["outcome"] == "REPAIR_NOT_VERIFIED"
    assert receipt["attempts"][1]["outcome"].startswith("PATCH_REJECTED")
    assert receipt["selectedAttempt"] == 1
    assert receipt["rawCompletion"] == _APPLIES_BUT_FAILS_PATCH
    assert "no patch markers at all" not in receipt["rawCompletion"]
    # F6: the final top-level materials/baseline/repaired fields must come
    # from attempt 1 (the selected/classified attempt), never silently
    # mixed with attempt 2's (the later PATCH_REJECTED retry, which never
    # even reached a build/run). Attempt 1's own recorded dict is the
    # source of truth for both.
    assert receipt["materials"] == receipt["attempts"][0]["materials"]
    assert receipt["baselineResult"] == receipt["attempts"][0]["baseline_result"]
    assert receipt["repairedResult"] == receipt["attempts"][0]["repaired_result"]
    # Every attempt's own build/repaired result is retained, not only the
    # selected one's.
    assert receipt["attempts"][0]["repaired_result"]
    assert receipt["attempts"][1]["patch_text"] == ""  # PATCH_REJECTED: never applied


@requires_colima_each
def test_an_ambiguous_repaired_run_still_preserves_the_applied_patch_and_real_run_result(tmp_path, monkeypatch) -> None:
    """F6 regression: a patch that genuinely applies and genuinely runs, but
    whose repaired-test run is ambiguous (e.g. a skip/collection-error
    pytest output ``_interpret_pytest_run`` refuses to classify), must
    never propagate that classification error uncaught and lose every
    attempt's evidence with no receipt ever written at all. The real
    applied patch and the real run's own exit code/output must be recorded
    on the attempt BEFORE classification -- not after -- so they survive a
    classification-time raise, and a truthful receipt must still exist at
    the end describing that inconclusive attempt honestly."""
    real_interpret = clean_room_module._interpret_pytest_run
    call_count = 0

    def _flaky_interpret(result, *, expected_tests):
        nonlocal call_count
        call_count += 1
        # Call 1 is the per-attempt BASELINE interpretation (must stay
        # real so expected_tests/baseline_verdict are genuine); call 2 is
        # the REPAIRED-run interpretation this test exercises.
        if call_count == 2:
            raise BenchmarkExecutionError("simulated ambiguous repaired-run output")
        return real_interpret(result, expected_tests=expected_tests)

    monkeypatch.setattr(clean_room_module, "_interpret_pytest_run", _flaky_interpret)
    approved = _approve_selftest_spec("test-clean-room-ambiguous-repaired-run")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/clean-room-selftest-v1")

    result = run_clean_room_build(
        model, approved, max_attempts=1, run_id=f"selftest-ambiguous-{tmp_path.name}-{uuid.uuid4().hex[:8]}"
    )

    assert result["outcome"].startswith("REPAIRED_RUN_INCONCLUSIVE")
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["outcome"].startswith("REPAIRED_RUN_INCONCLUSIVE")
    assert len(receipt["attempts"]) == 1
    attempt = receipt["attempts"][0]
    # The real applied patch must be recorded even though classification
    # itself raised -- not an empty default.
    assert attempt["patch_text"]
    assert attempt["patch_text"] != ""
    assert attempt["touched_paths"]
    # The real run's own exit code/output must be recorded too, not an
    # empty success-shaped default.
    assert attempt["repaired_result"]
    assert attempt["repaired_result"]["exit_code"] is not None


@requires_colima_each
def test_a_real_container_timeout_during_the_repaired_run_finalizes_a_truthful_partial_receipt(
    tmp_path, monkeypatch
) -> None:
    """F6 regression ("Likewise clean_room executor.run timeout must
    finalize attempt/partial receipt"): a patch that genuinely applies, but
    whose repaired acceptance-run ``executor.run`` call itself raises
    ``ContainerExecutorError`` (a real container-launch/timeout failure,
    not merely an ambiguous classification), must never propagate uncaught
    out of the whole function -- it must finalize a truthful, signed,
    partial receipt with the real applied patch preserved, no fabricated
    run result, a conservative EACH-P1 assurance level, and the private
    diagnostic text kept out of the source-free summary view.

    Call 1 is the real isolation probe, call 2 is this attempt's real
    baseline run; only call 3 (the repaired/candidate run) is forced to
    raise."""
    import each.executor.container as container_module

    original_run = container_module.ContainerExecutor.run
    call_count = 0

    def _flaky_run(self, command, worktree, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            raise container_module.ContainerExecutorError("simulated fixture container timeout")
        return original_run(self, command, worktree, **kwargs)

    monkeypatch.setattr(container_module.ContainerExecutor, "run", _flaky_run)
    approved = _approve_selftest_spec("test-clean-room-real-container-timeout")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/clean-room-selftest-v1")

    result = run_clean_room_build(
        model, approved, max_attempts=1, run_id=f"selftest-timeout-{tmp_path.name}-{uuid.uuid4().hex[:8]}"
    )

    assert call_count == 3
    assert result["outcome"].startswith("EXECUTION_ERROR")
    receipt_path = Path(result["receipt_json"])
    assert receipt_path.is_file()
    receipt = json.loads(receipt_path.read_text())
    assert receipt["outcome"].startswith("EXECUTION_ERROR")
    assert len(receipt["attempts"]) == 1
    attempt = receipt["attempts"][0]
    assert attempt["patch_text"]
    assert attempt["touched_paths"]
    assert attempt["baseline_result"]
    assert attempt["repaired_result"] == {}
    assert attempt["materials_integrity"] == "UNAVAILABLE"
    assert attempt["outcome"] == result["outcome"]
    assert receipt["networkIsolationVerified"] is True
    assert receipt["assuranceLevel"] == "EACH-P1"

    from each.cli import main as each_cli_main

    assert each_cli_main(["verify", str(receipt_path)]) == 0

    # The private diagnostic text must stay confined to this attempt's own
    # outcome string inside the private receipt, never leaking into any
    # outcome-independent top-level field (spec/materials/model identity).
    assert "simulated fixture container timeout" not in json.dumps(
        {k: v for k, v in receipt.items() if k not in ("outcome", "attempts")}
    )


