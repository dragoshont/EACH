"""Abstract interface for repair-proposal models.

EACH never substitutes its own (outer, cloud-assisted) inference for the
declared target model. Every model used to produce a candidate patch must
implement this interface and be invoked locally, with its identity recorded
in the run's provenance.
"""

from __future__ import annotations

import inspect
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from each.hashing import sha256_file

REAL_MODEL_ADAPTER_CLASS_PATHS = frozenset({
    "each.models.codegen25_model.CodeGen25RepairModel",
    "each.models.mlx_model.MLXRepairModel",
    "each.models.transformers_model.TransformersRepairModel",
})


class ContextBudgetExceeded(RuntimeError):
    """Raised by a RepairModel.complete() implementation when a rendered
    prompt plus its reserved output budget would exceed the checkpoint's
    declared supported context window -- checked BEFORE generation is
    attempted, never silently truncated or absorbed into a repair-failure
    outcome. Not every RepairModel backend declares/enforces a context
    limit (this is optional to raise), but any that does must use this
    exact type so callers can distinguish a policy/input-construction error
    from a genuine failed repair attempt.
    """


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

    def configure_sampling(self, *, temperature: float = 0.0, seed: int | None = None) -> None:
        """Optionally adjust this model's decoding parameters for the NEXT
        ``complete()`` call. The default implementation is a no-op: a
        ``RepairModel`` backend is not required to support sampling
        diversity, and a backend that ignores this call must keep behaving
        exactly as it always has (deterministic callers/tests are
        unaffected). A backend that does support it (e.g.
        :class:`each.models.mlx_model.MLXRepairModel`) must record the
        ACTUAL parameters it used for a given completion in its own
        ``identity()`` -- never a static claim that no longer matches what
        was really sampled.
        """

    def identity(self) -> dict[str, Any]:
        """Binds a receipt to the exact code that produced a completion.

        A free-text ``model_id`` alone is not trustworthy provenance evidence
        (anything could claim any label); this also records the concrete
        implementation module and its source hash.
        """
        module_path = Path(inspect.getfile(type(self)))
        return {
            "modelId": self.model_id,
            "adapterType": type(self).__name__,
            "adapterClassPath": f"{type(self).__module__}.{type(self).__name__}",
            "implementationModule": type(self).__module__,
            "implementationSha256": sha256_file(module_path),
        }


def validate_recorded_real_model_identity(model_identity: dict[str, Any]) -> tuple[str, str]:
    """Validate a recorded receipt model identity as a genuine local model.

    A free-form ``modelId`` label is never sufficient: the receipt must bind
    to one of the repository's actual non-fixture adapter classes, plus a
    structurally-real manifest and recorded generation parameters.
    """
    model_id = str(model_identity.get("modelId", "")).strip()
    adapter_class_path = str(model_identity.get("adapterClassPath", "")).strip()
    adapter_type = str(model_identity.get("adapterType", "")).strip()
    implementation_module = str(model_identity.get("implementationModule", "")).strip()
    implementation_sha256 = str(model_identity.get("implementationSha256", "")).strip()
    if adapter_class_path:
        if adapter_class_path not in REAL_MODEL_ADAPTER_CLASS_PATHS:
            raise ValueError("receipt does not declare an allowlisted real-model adapter")
        if adapter_type != adapter_class_path.rsplit(".", 1)[-1]:
            raise ValueError("receipt adapter type does not match its declared class path")
    else:
        # Legacy receipts (produced before ``RepairModel.identity()`` recorded
        # ``adapterClassPath``/``adapterType`` explicitly) only declared
        # ``implementationModule`` + ``implementationSha256``. Accept these
        # ONLY when the declared module uniquely and unambiguously identifies
        # one allowlisted real adapter class (never derived from a
        # caller-controlled ``modelId``/``adapterType`` string) and a genuine
        # implementation hash is present -- this is not a relaxation of the
        # allowlist, merely reading the same allowlisted fact through an
        # older, still-structurally-bound field name.
        if not implementation_module or not implementation_sha256:
            raise ValueError("receipt does not declare an allowlisted real-model adapter")
        matches = [
            class_path
            for class_path in REAL_MODEL_ADAPTER_CLASS_PATHS
            if class_path.rsplit(".", 1)[0] == implementation_module
        ]
        if len(matches) != 1:
            raise ValueError("receipt does not declare an allowlisted real-model adapter")
        adapter_class_path = matches[0]
    if not model_id:
        raise ValueError("receipt does not declare an allowlisted real-model adapter")

    manifest = model_identity.get("modelManifest")
    if not isinstance(manifest, dict):
        raise TypeError("receipt does not declare a structured model manifest")
    revision = str(manifest.get("revision", "")).strip()
    weights = manifest.get("weightsSha256")
    runtime = manifest.get("runtime")
    files = manifest.get("filesSha256")
    if (
        not revision
        or not isinstance(weights, dict)
        or not weights
        or not all(isinstance(path, str) and isinstance(digest, str) and digest for path, digest in weights.items())
        or not isinstance(runtime, dict)
        or not str(runtime.get("name", "")).strip()
        or not str(runtime.get("version", "")).strip()
        or not isinstance(files, dict)
        or not files
    ):
        raise ValueError("receipt manifest is missing required structural provenance fields")

    generation = model_identity.get("generationParameters")
    if (
        not isinstance(generation, dict)
        or not isinstance(generation.get("maxTokens"), int)
        or generation["maxTokens"] < 1
        or "temperature" not in generation
        or not str(generation.get("sampling", "")).strip()
    ):
        raise ValueError("receipt model identity is missing recorded generation parameters")
    if adapter_class_path == "each.models.transformers_model.TransformersRepairModel":
        runtime_environment = model_identity.get("runtimeEnvironment")
        if (
            implementation_module != adapter_class_path.rsplit(".", 1)[0]
            or not re.fullmatch(r"[0-9a-f]{64}", implementation_sha256)
            or not isinstance(runtime_environment, dict)
            or set(runtime_environment) != {"projectSha256", "lockSha256", "helperSha256", "versions"}
            or not all(
                isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                for key, value in runtime_environment.items()
                if key != "versions"
            )
            or not isinstance(runtime_environment.get("versions"), dict)
            or set(runtime_environment["versions"]) != {"python", "torch", "transformers"}
            or not all(
                isinstance(value, str) and value
                for value in runtime_environment["versions"].values()
            )
        ):
            raise ValueError("receipt Transformers runtime identity is missing or malformed")
    if adapter_class_path == "each.models.codegen25_model.CodeGen25RepairModel":
        tokenizer = model_identity.get("tokenizerProvenance")
        if (
            not isinstance(tokenizer, dict)
            or tokenizer.get("mode") != "reviewed-local-code"
            or not re.fullmatch(r"[0-9a-f]{64}", str(tokenizer.get("sha256", "")))
            or tokenizer.get("tiktokenVersion") != "0.4.0"
        ):
            raise ValueError("receipt CodeGen2.5 tokenizer identity is missing or malformed")
    return model_id, adapter_class_path
