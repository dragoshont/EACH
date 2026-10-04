"""The exhausted/unqualified API development command cannot load a model."""

import json
import sys

import pytest

from each import production_development


@pytest.mark.parametrize("task", ["negative-size", "one-byte-float", "yotta-rollover"])
def test_command_is_blocked_before_any_model_or_target_operation(monkeypatch, capsys, task):
    monkeypatch.setattr(sys, "argv", ["production-development", "--task", task])
    assert production_development.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "API_RETURN_AUTHENTICATION_UNAVAILABLE"
    assert result["actualModelCalls"] == 0
    assert result["utilityCap"] == "EXHAUSTED"
    assert result["originalProductionGoalMet"] is False
