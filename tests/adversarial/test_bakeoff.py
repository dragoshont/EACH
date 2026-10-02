"""Adversarial/end-to-end evidence for the M2 bake-off orchestrator:
isolation fail-closed, bounded-attempt trajectory recording, and real patch
rejection/retry against the real no-network container executor.

Uses a tiny stub RepairModel (never FixtureModel) so FixtureModel's own
CI-safety/determinism claim is not entangled with this real-model-shaped
code path.
"""

from __future__ import annotations

import json
from pathlib import Path

import each.bakeoff as bakeoff_module
from tests.adversarial._docker_guard import requires_colima_each

_CORRECT_PATCH = """BEGIN_PATCH
--- a/src/greet.py
+++ b/src/greet.py
@@ -1,2 +1,2 @@
 def greet(name: str) -> str:
-    return "Hell, " + name
+    return "Hello, " + name
END_PATCH
"""


class _StubRepairModel:
    """Minimal RepairModel stand-in: not FixtureModel, not a real local
    model -- just enough to drive the bake-off orchestrator deterministically
    for test purposes."""

    model_id = "test/stub-repair-model"

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls = 0

    def complete(self, _prompt: str) -> str:
        reply = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        return reply

    def identity(self) -> dict[str, str]:
        return {
            "modelId": self.model_id,
            "implementationModule": __name__,
            "implementationSha256": "",
        }


@requires_colima_each
def test_bakeoff_verifies_repair_and_records_single_attempt() -> None:
    model = _StubRepairModel([_CORRECT_PATCH])
    result = bakeoff_module.run_model_bakeoff(model, max_attempts=3)
    assert result["outcome"] == "REPAIR_VERIFIED"
    assert result["attempts"] == 1
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["attempts"][0]["outcome"] == "REPAIR_VERIFIED"
    assert receipt["modelIdentity"]["modelId"] == model.model_id
    assert receipt["assuranceLevel"] == "EACH-P2"
    assert set(receipt["audit"]["checks"]) == {
        "exact-substring",
        "ngram-similarity",
        "ast-similarity",
        "license-scan",
        "corpus-membership",
    }
    assert "score" not in receipt["audit"]


@requires_colima_each
def test_bakeoff_records_full_trajectory_across_bounded_retries() -> None:
    model = _StubRepairModel(["not a diff at all", _CORRECT_PATCH])
    result = bakeoff_module.run_model_bakeoff(model, max_attempts=3)
    assert result["outcome"] == "REPAIR_VERIFIED"
    assert result["attempts"] == 2
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert len(receipt["attempts"]) == 2
    assert receipt["attempts"][0]["outcome"].startswith("PATCH_REJECTED")
    assert receipt["attempts"][1]["outcome"] == "REPAIR_VERIFIED"
    # Every attempt's own prompt/raw_completion must be recorded, not just
    # the final one.
    assert receipt["attempts"][0]["raw_completion"] == "not a diff at all"
    assert receipt["attempts"][1]["raw_completion"] == _CORRECT_PATCH


@requires_colima_each
def test_bakeoff_bounds_attempts_and_reports_last_rejection() -> None:
    model = _StubRepairModel(["still not a diff"])
    result = bakeoff_module.run_model_bakeoff(model, max_attempts=2)
    assert result["attempts"] == 2
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert len(receipt["attempts"]) == 2
    assert all(a["outcome"].startswith("PATCH_REJECTED") for a in receipt["attempts"])
    assert set(receipt["materials"]) == {"src/greet.py", "tests/test_greet.py"}
    assert receipt["baselineResult"]["exit_code"] == 1
    assert all(a["materials"] == receipt["materials"] for a in receipt["attempts"])
    # No patch ever applied: nothing to leak into touched_paths/materials.
    assert receipt["touchedPaths"] == []


@requires_colima_each
def test_bakeoff_rejects_a_candidate_that_matches_the_audit_corpus() -> None:
    """End-to-end proof that M4 wiring actually audits the real repaired
    source (not the raw diff text): a corpus entry equal to the genuine
    post-patch file content must cause REPAIR_REJECTED_AUDIT, not
    REPAIR_VERIFIED, even though the patch applies cleanly and the fixture
    test suite passes."""
    repaired_source = 'def greet(name: str) -> str:\n    return "Hello, " + name\n'
    model = _StubRepairModel([_CORRECT_PATCH])
    result = bakeoff_module.run_model_bakeoff(model, max_attempts=3, audit_corpus=[repaired_source])
    assert result["outcome"] == "REPAIR_REJECTED_AUDIT"
    assert result["attempts"] == model.calls == 1
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["attempts"][0]["outcome"] == "REPAIR_REJECTED_AUDIT"
    assert receipt["audit"]["checks"]["exact-substring"]["status"] == "FAIL"
    # Terminal boundary: the rejection is visible, but no matched source
    # text leaked into the receipt's audit evidence.
    for check in receipt["audit"]["checks"].values():
        for value in check["evidence"].values():
            if isinstance(value, str):
                assert repaired_source not in value


@requires_colima_each
def test_bakeoff_accepts_a_candidate_with_no_audit_corpus_configured() -> None:
    # Unconfigured corpus must never silently become a rejection: the
    # checks honestly report UNAVAILABLE, and an unavailable check must
    # never be treated as a FAIL by reject_on_audit_flag.
    model = _StubRepairModel([_CORRECT_PATCH])
    result = bakeoff_module.run_model_bakeoff(model, max_attempts=1)
    assert result["outcome"] == "REPAIR_VERIFIED"
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["audit"]["checks"]["exact-substring"]["status"] == "UNAVAILABLE"


@requires_colima_each
def test_bakeoff_fails_closed_when_isolation_cannot_be_verified(monkeypatch) -> None:
    """The probe still runs for real (needs colima); only the *derived*
    assurance level is forced non-P2, to check the fail-closed branch
    without depending on ever observing a real denial."""

    monkeypatch.setattr(bakeoff_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P1")

    model = _StubRepairModel([_CORRECT_PATCH])
    result = bakeoff_module.run_model_bakeoff(model, max_attempts=3)
    assert result["outcome"] == "ISOLATION_UNVERIFIED"
    assert result["attempts"] == 0
    assert model.calls == 0
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["patchText"] == ""
    assert receipt["attempts"] == []


def test_bakeoff_rejects_max_attempts_below_one() -> None:
    """Regression: a zero/negative max_attempts must not silently produce a
    receipt indistinguishable from a genuine classified repair failure."""
    model = _StubRepairModel([_CORRECT_PATCH])
    for bad_value in (0, -1):
        try:
            bakeoff_module.run_model_bakeoff(model, max_attempts=bad_value)
        except ValueError as exc:
            assert "max_attempts" in str(exc)
        else:
            raise AssertionError(f"expected ValueError for max_attempts={bad_value}")
    assert model.calls == 0


@requires_colima_each
def test_bakeoff_does_not_mask_execution_classification_failures(monkeypatch) -> None:
    """Regression: a FixtureExecutionError (container launch failure, skipped
    tests, unrecognized output -- i.e. "not test evidence") must propagate
    uncaught rather than being folded into the same REPAIR_NOT_VERIFIED
    bucket a genuinely-tested failing repair would also produce, matching
    each.demo.run_hello_repair's fail-loud precedent."""
    from each.demo import FixtureExecutionError

    def _raise(*_a, **_k):
        raise FixtureExecutionError("container launch failed (exit 125): simulated infra failure")

    monkeypatch.setattr(bakeoff_module, "_interpret_test_run", _raise)

    model = _StubRepairModel([_CORRECT_PATCH])
    try:
        bakeoff_module.run_model_bakeoff(model, max_attempts=1)
    except FixtureExecutionError as exc:
        assert "container launch failed" in str(exc)
    else:
        raise AssertionError("expected FixtureExecutionError to propagate uncaught")
    assert model.calls == 0


@requires_colima_each
def test_bakeoff_records_the_model_rendered_prompt() -> None:
    class RenderedModel(_StubRepairModel):
        last_prompt: str | None = None

        def complete(self, prompt: str) -> str:
            self.last_prompt = f"[user]{prompt}[assistant]"
            return super().complete(prompt)

    model = RenderedModel([_CORRECT_PATCH])
    result = bakeoff_module.run_model_bakeoff(model, max_attempts=1)
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["attempts"][0]["prompt"] == model.last_prompt
    assert receipt["prompt"] == model.last_prompt


@requires_colima_each
def test_audit_match_is_terminal_without_builder_feedback(monkeypatch) -> None:
    forbidden_hint = "FORBIDDEN_POST_GENERATION_SOURCE_MATCH"

    class CapturingModel(_StubRepairModel):
        def __init__(self) -> None:
            super().__init__([_CORRECT_PATCH])
            self.prompts: list[str] = []

        def complete(self, prompt: str) -> str:
            self.prompts.append(prompt)
            return super().complete(prompt)

    model = CapturingModel()
    audited: list[str] = []

    def discovered_match(source: str, *, corpus: list[str] | None = None) -> dict[str, object]:
        assert model.calls == 1
        assert source
        audited.append(source)
        return {
            "checks": {"exact-substring": {"status": "FAIL", "sourceHint": forbidden_hint}},
            "result": "FAIL",
        }

    monkeypatch.setattr(bakeoff_module, "run_audit", discovered_match)
    result = bakeoff_module.run_model_bakeoff(model, max_attempts=3)
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert len(audited) == model.calls == 1
    assert receipt["audit"]["result"] == "FAIL"
    assert all(forbidden_hint not in prompt for prompt in model.prompts)
