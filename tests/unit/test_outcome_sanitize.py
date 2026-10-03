"""F1 regression: a candidate-influenced diagnostic string must never cross
a documented source-free boundary unbounded -- only one of a fixed,
reviewed outcome-class label may ever be returned.
"""

from __future__ import annotations

from each.outcome import (
    UNKNOWN_OUTCOME_CLASS,
    UNKNOWN_PROPOSAL_FORMAT_CLASS,
    sanitize_outcome_class,
    sanitize_proposal_format,
)


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


# F3: a source-free export's proposalFormat field must be a bounded enum,
# never an arbitrary attempt-controlled string.


def test_known_proposal_format_passes_through() -> None:
    assert sanitize_proposal_format("diff") == "diff"
    assert sanitize_proposal_format("full_source") == "full_source"
    assert sanitize_proposal_format("source_edit") == "source_edit"


def test_unrecognized_proposal_format_is_never_passed_through_raw() -> None:
    sentinel = "arbitrary-candidate-controlled-format-string"
    result = sanitize_proposal_format(sentinel)
    assert result == UNKNOWN_PROPOSAL_FORMAT_CLASS
    assert sentinel not in result


def test_missing_proposal_format_is_unknown_not_none() -> None:
    assert sanitize_proposal_format(None) == UNKNOWN_PROPOSAL_FORMAT_CLASS
