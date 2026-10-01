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


@requires_colima_each
def test_hello_repair_rejects_malformed_model_completion(monkeypatch) -> None:
    class _BrokenModel:
        model_id = "broken/v1"

        def complete(self, _prompt: str) -> str:
            return "this is not a unified diff at all"

    monkeypatch.setattr(demo_module, "FixtureModel", lambda *_a, **_k: _BrokenModel())
    result = demo_module.run_hello_repair()
    assert result["outcome"].startswith("PATCH_REJECTED")
