"""End-to-end adversarial evidence for the M1 hello-repair vertical slice:
the full pipeline running against the real no-network container executor,
plus a check that a malformed model completion is rejected rather than
silently producing a false "repaired" result.
"""

from __future__ import annotations

from pathlib import Path

import each.demo as demo_module
from tests.adversarial._docker_guard import requires_colima_each


@requires_colima_each
def test_hello_repair_full_pipeline_verifies_repair() -> None:
    result = demo_module.run_hello_repair()
    assert result["outcome"] == "REPAIR_VERIFIED"
    assert Path(result["receipt_json"]).exists()
    assert Path(result["receipt_md"]).exists()

    import json

    receipt = json.loads(Path(result["receipt_json"]).read_text())
    # Item 1: declared source/test materials (path -> sha256) from the
    # pre-execution worktree manifest must survive into the receipt.
    assert receipt["materials"] == result["manifest"]
    assert len(receipt["materials"]["src/greet.py"]) == 64  # sha256 hex digest
    assert "tests/test_greet.py" in receipt["materials"]
    # Item 2: the receipt is bound to concrete executor/model/isolation evidence.
    assert receipt["executorIdentity"]["network"] == "none"
    assert receipt["modelIdentity"]["modelId"]
    assert receipt["isolationEvidence"]["exit_code"] == 1
    assert receipt["legalCertification"] is False
    assert receipt["cleanroomCertification"] is False


@requires_colima_each
def test_hello_repair_rejected_patch_receipt_also_includes_materials(monkeypatch) -> None:
    """Item 1 regression: the PATCH_REJECTED branch must not discard materials."""
    import json

    class _BrokenModel:
        model_id = "broken/v1"

        def complete(self, _prompt: str) -> str:
            return "this is not a unified diff at all"

        def identity(self) -> dict[str, str]:
            return {"modelId": self.model_id, "implementationModule": __name__, "implementationSha256": ""}

    monkeypatch.setattr(demo_module, "FixtureModel", lambda *_a, **_k: _BrokenModel())
    result = demo_module.run_hello_repair()
    assert result["outcome"].startswith("PATCH_REJECTED")
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["materials"] == result["manifest"]
    assert "src/greet.py" in receipt["materials"]


@requires_colima_each
def test_hello_repair_rejects_malformed_model_completion(monkeypatch) -> None:
    class _BrokenModel:
        model_id = "broken/v1"

        def complete(self, _prompt: str) -> str:
            return "this is not a unified diff at all"

        def identity(self) -> dict[str, str]:
            return {"modelId": self.model_id, "implementationModule": __name__, "implementationSha256": ""}

    monkeypatch.setattr(demo_module, "FixtureModel", lambda *_a, **_k: _BrokenModel())
    result = demo_module.run_hello_repair()
    assert result["outcome"].startswith("PATCH_REJECTED")
