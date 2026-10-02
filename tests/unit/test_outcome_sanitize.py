"""F1 regression: a candidate-influenced diagnostic string must never cross
a documented source-free boundary unbounded -- only one of a fixed,
reviewed outcome-class label may ever be returned.
"""

from __future__ import annotations

from each.outcome import UNKNOWN_OUTCOME_CLASS, sanitize_outcome_class


def test_bare_known_label_passes_through() -> None:
    assert sanitize_outcome_class("REPAIR_VERIFIED") == "REPAIR_VERIFIED"


def test_known_label_with_free_text_suffix_is_bounded() -> None:
    assert sanitize_outcome_class("PATCH_REJECTED: malformed unified diff: ...") == "PATCH_REJECTED"


def test_sentinel_candidate_controlled_diagnostic_never_leaks() -> None:
    """Simulate exactly the F1 scenario: a compiler/model-controlled
    diagnostic string embedded ahead of or instead of a real outcome label.
    """
    sentinel = "SECRET-CANDIDATE-SOURCE-FRAGMENT-ABC123"
    leaked = f"BUILD_FAILED: {sentinel} xsystem.c:42: error: ..."
    result = sanitize_outcome_class(leaked)
    assert result == "BUILD_FAILED"
    assert sentinel not in result


def test_unrecognized_label_is_never_passed_through_raw() -> None:
    sentinel = "arbitrary-candidate-controlled-text"
    assert sanitize_outcome_class(sentinel) == UNKNOWN_OUTCOME_CLASS
    assert sentinel not in sanitize_outcome_class(sentinel)


def test_empty_outcome_is_unknown_not_blank() -> None:
    assert sanitize_outcome_class("") == UNKNOWN_OUTCOME_CLASS
