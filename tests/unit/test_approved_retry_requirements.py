from each.clean_room import _retry_suffix_for_mode


def test_retry_focuses_only_on_unchanged_approved_requirement():
    approved = "1. First approved behavior.\n\n6. Unusual approved behavior.\n\n7. Other behavior.\n"
    feedback = "Reported failed approved specification items: 6"
    suffix = _retry_suffix_for_mode(
        "full_source", reason="failed", line_count=2,
        test_feedback=feedback, previous_candidate="fixture previous source",
        approved_problem_statement=approved,
    )
    assert "6. Unusual approved behavior." in suffix
    assert "1. First approved behavior." not in suffix
    assert "7. Other behavior." not in suffix
    assert suffix.index("END_OWN_PREVIOUS_CANDIDATE") < suffix.index("BEGIN_FAILED_APPROVED_REQUIREMENTS")
    assert "unchanged approved specification" in suffix


def test_feedback_for_an_absent_item_cannot_invent_requirement_text():
    suffix = _retry_suffix_for_mode(
        "full_source", reason="failed", line_count=2,
        test_feedback="Reported failed approved specification items: 9",
        approved_problem_statement="6. Approved behavior.\n",
    )
    assert "BEGIN_FAILED_APPROVED_REQUIREMENTS" not in suffix
    assert "6. Approved behavior." not in suffix
