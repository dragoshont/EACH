"""Abstract interface for repair-proposal models.

EACH never substitutes its own (outer, cloud-assisted) inference for the
declared target model. Every model used to produce a candidate patch must
implement this interface and be invoked locally, with its identity recorded
in the run's provenance.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from each.hashing import sha256_file


class RepairModel(ABC):
    """A model that proposes a unified-diff patch for a given repair context."""

    last_prompt: str | None = None

    @property
    @abstractmethod
    def model_id(self) -> str:
        """A stable identifier recorded in provenance (e.g. name+revision+hash)."""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Return the raw model completion text for the given prompt."""

    def identity(self) -> dict[str, Any]:
        """Binds a receipt to the exact code that produced a completion.

        A free-text ``model_id`` alone is not trustworthy provenance evidence
        (anything could claim any label); this also records the concrete
        implementation module and its source hash.
        """
        module_path = Path(inspect.getfile(type(self)))
        return {
            "modelId": self.model_id,
            "implementationModule": type(self).__module__,
            "implementationSha256": sha256_file(module_path),
        }
