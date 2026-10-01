"""Abstract interface for repair-proposal models.

EACH never substitutes its own (outer, cloud-assisted) inference for the
declared target model. Every model used to produce a candidate patch must
implement this interface and be invoked locally, with its identity recorded
in the run's provenance.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class RepairModel(ABC):
    """A model that proposes a unified-diff patch for a given repair context."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """A stable identifier recorded in provenance (e.g. name+revision+hash)."""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Return the raw model completion text for the given prompt."""
