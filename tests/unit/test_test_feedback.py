"""Unit tests for each.test_feedback.extract_bounded_test_feedback: only
synthetic/artificial pytest-shaped output, never real private test content.
"""

from __future__ import annotations

from each.test_feedback import MAX_FEEDBACK_CHARS, TRUNCATION_MARKER, extract_bounded_test_feedback


def test_extracts_assertion_detail_and_failing_nodeid() -> None:
    stdout = (
        "FAILED shadow/m7/test_fixture.py::test_basic - assert 3 == 2\n"
        "========================= 1 failed, 2 passed in 0.12s ===========================\n"
    )
    feedback = extract_bounded_test_feedback(stdout, "")
    assert "test_basic" in feedback
    assert "1 failed, 2 passed" in feedback


def test_extracts_e_prefixed_exception_lines_only() -> None:
    stdout = (
        "    def test_basic():\n"
        "        calls = []\n"
        ">       assert f(1) == 2\n"
        "E       assert 3 == 2\n"
        "E        +  where 3 = f(1)\n"
        "shadow/m7/test_fixture.py:15: AssertionError\n"
    )
    feedback = extract_bounded_test_feedback(stdout, "")
    assert "assert 3 == 2" in feedback
    assert "where 3 = f(1)" in feedback
    # unprefixed source-context lines must never be surfaced
    assert "calls = []" not in feedback
    assert "def test_basic" not in feedback


def test_extracts_indentation_error_from_own_candidate_file() -> None:
    stdout = (
        "E     File \"/work/src/candidate.py\", line 3\n"
        "E       bad_indent = 2\n"
        "E                     ^\n"
        "E   IndentationError: unindent does not match any outer indentation level\n"
        "1 error in 0.04s\n"
    )
    feedback = extract_bounded_test_feedback(stdout, "")
    assert "IndentationError" in feedback
    assert "1 error in 0.04s" in feedback


def test_no_matching_lines_returns_empty_string() -> None:
    assert extract_bounded_test_feedback("nothing structured here\n", "") == ""


def test_feedback_is_bounded_in_length() -> None:
    many_lines = "\n".join(f"E   assertion detail line {i} " + "x" * 50 for i in range(500))
    feedback = extract_bounded_test_feedback(many_lines, "")
    assert len(feedback) <= MAX_FEEDBACK_CHARS + len(TRUNCATION_MARKER)


def test_feedback_is_deterministic() -> None:
    stdout = "E   ValueError: bad value\n1 failed in 0.1s\n"
    assert extract_bounded_test_feedback(stdout, "") == extract_bounded_test_feedback(stdout, "")


def test_stdout_and_stderr_are_both_considered() -> None:
    feedback = extract_bounded_test_feedback("", "E   RuntimeError: boom\n1 error in 0.1s\n")
    assert "RuntimeError" in feedback
