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
from pathlib import Path

import each.clean_room as clean_room_module
from each.clean_room import run_clean_room_build
from each.models.fixture import FixtureModel
from each.spec import ApprovedSpec, make_spec_packet
from tests.adversarial._docker_guard import requires_colima_each

# A hand-written, line-exact unified diff against the real stub file (built
# and independently verified to apply cleanly via each.patch.apply_patch and
# to pass all 9 real acceptance tests, outside any container, before being
# wired into this harness self-test) -- not the actual M7 Builder output.
_CORRECT_PATCH = (Path(__file__).parent / "data" / "clean_room_selftest_patch.txt").read_text()


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

    result = run_clean_room_build(model, approved, max_attempts=1, run_id=f"selftest-{tmp_path.name}")

    assert result["outcome"] == "REPAIR_VERIFIED"
    assert result["attempts"] == 1
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["assuranceLevel"] == "EACH-P2"
    assert receipt["attempts"][0]["outcome"] == "REPAIR_VERIFIED"
    assert set(receipt["audit"]["checks"]) == {
        "exact-substring",
        "ngram-similarity",
        "ast-similarity",
        "license-scan",
        "corpus-membership",
    }


@requires_colima_each
def test_clean_room_fails_closed_when_isolation_cannot_be_verified(tmp_path, monkeypatch) -> None:
    """Same fail-closed branch each.bakeoff proves: the probe still runs for
    real, only the *derived* assurance level is forced non-P2, so no
    Builder call ever happens."""
    monkeypatch.setattr(clean_room_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P1")
    approved = _approve_selftest_spec("test-clean-room-isolation-fail-closed")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/clean-room-selftest-v1")

    result = run_clean_room_build(model, approved, max_attempts=3, run_id=f"selftest-iso-{tmp_path.name}")

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

    result = run_clean_room_build(model, approved, max_attempts=3, run_id=f"selftest-audit-{tmp_path.name}")

    assert result["outcome"] == "REPAIR_REJECTED_AUDIT"
    assert result["attempts"] == len(calls) == 1
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["audit"]["result"] == "FAIL"
    assert all(forbidden_hint not in prompt for prompt in calls)

