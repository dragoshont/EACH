from __future__ import annotations

from each.audit.checks import exact_substring_check


def test_exact_substring_check_is_unavailable_when_every_corpus_snippet_is_too_short() -> None:
    result = exact_substring_check("candidate source that is definitely long enough", ["tiny", "short"])
    assert result.status == "UNAVAILABLE"
    assert "minimum comparison length" in result.detail


def test_exact_substring_check_still_compares_against_eligible_snippets() -> None:
    fail_result = exact_substring_check(
        "alpha beta gamma delta epsilon",
        ["short", "beta gamma delta epsilon"],
    )
    assert fail_result.status == "FAIL"

    pass_result = exact_substring_check(
        "alpha beta gamma delta epsilon",
        ["short", "this eligible corpus snippet is different"],
    )
    assert pass_result.status == "PASS"
