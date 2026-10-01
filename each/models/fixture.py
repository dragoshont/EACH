"""A deterministic, canned-response model used only for the M1 hello-repair
vertical slice and harness self-tests.

FixtureModel performs no inference whatsoever and must never be used as a
stand-in for a declared target model in a real repair run (see M2 for real
local-model evaluation).
"""

from __future__ import annotations

from each.models.base import RepairModel


class FixtureModel(RepairModel):
    def __init__(self, response: str, model_id: str = "fixture/deterministic-v1") -> None:
        self._response = response
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response
