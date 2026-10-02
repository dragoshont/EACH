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
from pathlib import Path

import pytest

import each.xodus_shadow as xodus_shadow_module
from each.models.fixture import FixtureModel
from each.spec import ApprovedSpec, make_spec_packet
from each.xodus_shadow import run_xodus_shadow_build, summarize_receipt
from tests.adversarial._docker_guard import requires_colima_each

_CORRECT_PATCH = (Path(__file__).parent / "data" / "xodus_shadow_selftest_patch.txt").read_text()
_CACHED_SOURCE = (Path(__file__).parent / "data" / "xsystem_selftest_source.c").read_text()


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
    )
    return ApprovedSpec.approve(packet)


@requires_colima_each
@requires_m8_native_image
def test_fixture_model_candidate_is_verified_and_signed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    approved = _approve_selftest_spec("test-xodus-shadow-harness-selftest")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(model, approved, max_attempts=1, run_id=f"selftest-{tmp_path.name}")

    assert result["outcome"] == "REPAIR_VERIFIED"
    assert result["attempts"] == 1
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["assuranceLevel"] == "EACH-P2"
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

    summary = summarize_receipt(result["receipt_json"])
    assert summary["outcome"] == "REPAIR_VERIFIED"
    assert "prompt" not in summary
    assert "rawCompletion" not in summary
    assert "patchText" not in summary


@requires_colima_each
@requires_m8_native_image
def test_xodus_shadow_fails_closed_when_isolation_cannot_be_verified(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    monkeypatch.setattr(xodus_shadow_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P1")
    approved = _approve_selftest_spec("test-xodus-shadow-isolation-fail-closed")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(model, approved, max_attempts=3, run_id=f"selftest-iso-{tmp_path.name}")

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

    result = run_xodus_shadow_build(model, approved, max_attempts=3, run_id=f"selftest-audit-{tmp_path.name}")

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
        run_xodus_shadow_build(model, approved, max_attempts=1, run_id=f"selftest-baseline-{tmp_path.name}")


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

    result = run_xodus_shadow_build(model, approved, max_attempts=2, run_id=f"selftest-rejected-{tmp_path.name}")

    assert result["outcome"].startswith("PATCH_REJECTED")
    assert result["outcome"] != "REPAIR_NOT_VERIFIED"
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["outcome"].startswith("PATCH_REJECTED")
    assert len(receipt["attempts"]) == 2
    assert all(a["outcome"].startswith("PATCH_REJECTED") for a in receipt["attempts"])
