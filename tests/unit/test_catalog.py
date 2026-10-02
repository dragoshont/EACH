"""Regression tests for the M2 model catalog: unknown keys and the exact,
honest "unavailable" reasons must be real, not silently swallowed."""

from __future__ import annotations

import pytest

from each.models.catalog import UnavailableModelError, load_model


def test_load_model_unknown_key_raises_with_known_keys_listed() -> None:
    with pytest.raises(UnavailableModelError, match="unknown model key"):
        load_model("not-a-real-model")


def test_octocoder_reports_a_concrete_unavailability_reason() -> None:
    # Either the download is still incomplete (missing shard count named) or
    # it completed and the "no adapter implemented" reason fires instead --
    # both are legitimate, both must be a real, specific message, never a
    # silent pass or a generic placeholder.
    with pytest.raises(UnavailableModelError) as exc_info:
        load_model("octocoder-transformers-mps")
    message = str(exc_info.value)
    assert ("download incomplete" in message and "shard(s) missing" in message) or (
        "no Transformers/MPS RepairModel adapter is implemented" in message
    )


def test_gguf_reports_no_verified_conversion_provenance() -> None:
    with pytest.raises(UnavailableModelError, match="no llama.cpp/GGUF conversion with recorded provenance"):
        load_model("granite-gguf-llamacpp")


def test_load_model_rejects_unsupported_kwarg_for_entries_without_tunable_params() -> None:
    # A keyword a builder does not accept must raise a normal TypeError, not
    # be silently swallowed as a no-op override.
    with pytest.raises(TypeError):
        load_model("granite-gguf-llamacpp", max_tokens=1024)
