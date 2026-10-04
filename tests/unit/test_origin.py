"""Unit tests for each.origin: sensitive-spec origin rejection policy."""

from __future__ import annotations

import pytest

from each.origin import Origin, SensitiveOriginRejected, check_sensitive_origins


def test_non_sensitive_spec_allows_any_origin():
    origins = {"problem_statement": Origin.MODEL_INFERENCE, "allowed_paths": Origin.UNKNOWN}
    check_sensitive_origins(origins, sensitive=False)  # must not raise


@pytest.mark.parametrize("origin", [Origin.MODEL_INFERENCE, Origin.UNKNOWN, Origin.RESTRICTED])
def test_sensitive_spec_rejects_disallowed_origins(origin):
    origins = {"problem_statement": Origin.PUBLIC_ISSUE, "allowed_paths": origin}
    with pytest.raises(SensitiveOriginRejected, match="allowed_paths"):
        check_sensitive_origins(origins, sensitive=True)


@pytest.mark.parametrize(
    "origin",
    [
        Origin.PUBLIC_API_DOC,
        Origin.PUBLIC_HEADER,
        Origin.PUBLIC_OPEN_SOURCE,
        Origin.PUBLIC_ISSUE,
        Origin.BLACK_BOX_OBSERVATION,
        Origin.USER_ASSERTION,
    ],
)
def test_sensitive_spec_allows_trusted_origins(origin):
    origins = {"problem_statement": origin, "allowed_paths": Origin.USER_ASSERTION}
    check_sensitive_origins(origins, sensitive=True)  # must not raise
