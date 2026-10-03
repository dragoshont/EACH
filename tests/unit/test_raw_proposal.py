from __future__ import annotations

import pytest

from each.patch import parse_patch
from each.raw_proposal import RawProposalRejected, derive_unified_diff, extract_full_source


def test_extract_full_source_happy_path() -> None:
    completion = "preamble text\nBEGIN_SOURCE\ndef f():\n    return 1\nEND_SOURCE\ntrailer text"
    assert extract_full_source(completion) == "def f():\n    return 1\n"


def test_extract_full_source_rejects_missing_begin_marker() -> None:
    with pytest.raises(RawProposalRejected, match="missing"):
        extract_full_source("def f():\n    return 1\nEND_SOURCE")


def test_extract_full_source_rejects_missing_end_marker() -> None:
    with pytest.raises(RawProposalRejected, match="missing"):
        extract_full_source("BEGIN_SOURCE\ndef f():\n    return 1\n")


def test_extract_full_source_rejects_duplicate_begin_marker() -> None:
    completion = "BEGIN_SOURCE\nfoo\nEND_SOURCE\nBEGIN_SOURCE\nbar\nEND_SOURCE"
    with pytest.raises(RawProposalRejected, match="more than one"):
        extract_full_source(completion)


def test_extract_full_source_rejects_duplicate_end_marker() -> None:
    completion = "BEGIN_SOURCE\nfoo\nEND_SOURCE\nEND_SOURCE"
    with pytest.raises(RawProposalRejected, match="more than one"):
        extract_full_source(completion)


def test_extract_full_source_rejects_empty_body() -> None:
    with pytest.raises(RawProposalRejected, match="empty"):
        extract_full_source("BEGIN_SOURCE\n\n   \n\nEND_SOURCE")


def test_extract_full_source_rejects_end_marker_before_begin_marker() -> None:
    # (C1) An END_SOURCE marker that appears before BEGIN_SOURCE in the raw
    # completion must be rejected explicitly, not silently treated as "no
    # END_SOURCE found after BEGIN_SOURCE" and fall back to an unbounded body.
    completion = "noise END_SOURCE more noise BEGIN_SOURCE\ndef f():\n    return 1\n"
    with pytest.raises(RawProposalRejected, match="before BEGIN_SOURCE"):
        extract_full_source(completion)


def test_extract_full_source_rejects_whitespace_only_body() -> None:
    with pytest.raises(RawProposalRejected, match="empty"):
        extract_full_source("BEGIN_SOURCE\nEND_SOURCE")


def test_derive_unified_diff_identical_texts_returns_empty() -> None:
    text = "a\nb\nc\n"
    assert derive_unified_diff(path="x.py", original_text=text, proposed_text=text) == ""


def test_derive_unified_diff_produces_parseable_patch() -> None:
    original = "def greet(name):\n    return \"Hell, \" + name\n"
    proposed = "def greet(name):\n    return \"Hello, \" + name\n"
    diff_text = derive_unified_diff(path="src/greet.py", original_text=original, proposed_text=proposed)
    assert diff_text
    patch = parse_patch(diff_text)
    assert len(patch) == 1
    assert patch[0].target_file.endswith("src/greet.py")


def test_derive_unified_diff_is_deterministic() -> None:
    original = "one\ntwo\nthree\n"
    proposed = "one\ntwo-changed\nthree\nfour\n"
    first = derive_unified_diff(path="f.py", original_text=original, proposed_text=proposed)
    second = derive_unified_diff(path="f.py", original_text=original, proposed_text=proposed)
    assert first == second


def test_derive_unified_diff_handles_multiline_insertion_and_deletion() -> None:
    original = "alpha\nbeta\ngamma\ndelta\n"
    proposed = "alpha\nBETA\nGAMMA\ndelta\nepsilon\n"
    diff_text = derive_unified_diff(path="f.py", original_text=original, proposed_text=proposed)
    patch = parse_patch(diff_text)
    assert len(patch) == 1


# F1 (Claude-family public code review at 6c3e1f3): a no-trailing-newline
# input line is NOT the last line difflib joins into the output whenever a
# changed/context line appears before a later hunk or trailing context --
# "".join() would then fuse that line's text directly onto the following
# diff record with no separating newline, corrupting the parseable diff.
# Fail closed instead of ever emitting that corrupted text.


def test_derive_unified_diff_rejects_original_without_trailing_newline() -> None:
    original = "alpha\nbeta\ngamma"  # no trailing newline
    proposed = "alpha\nBETA\ngamma\n"
    with pytest.raises(RawProposalRejected, match="trailing newline"):
        derive_unified_diff(path="f.py", original_text=original, proposed_text=proposed)


def test_derive_unified_diff_rejects_proposed_without_trailing_newline() -> None:
    original = "alpha\nbeta\ngamma\n"
    proposed = "alpha\nBETA\ngamma"  # no trailing newline
    with pytest.raises(RawProposalRejected, match="trailing newline"):
        derive_unified_diff(path="f.py", original_text=original, proposed_text=proposed)


def test_derive_unified_diff_rejects_eof_case_even_with_multiple_hunks() -> None:
    """Regression for the exact fusion scenario: two widely-separated
    changes force difflib to emit two separate hunks, and the file's last
    line (lacking a trailing newline) is NOT the final line of the second
    hunk's output -- demonstrating the fail-closed policy applies even when
    a naive "only check the very last character of the whole diff" guard
    would have missed it.
    """
    original = "\n".join([f"line{i}" for i in range(1, 11)]) + "\n"  # line1..line10, trailing newline
    lines = original.splitlines()
    lines[1] = "CHANGED_NEAR_TOP"
    lines[-1] = lines[-1] + "_CHANGED"
    proposed = "\n".join(lines)  # no trailing newline on the reconstructed text
    with pytest.raises(RawProposalRejected, match="trailing newline"):
        derive_unified_diff(path="f.py", original_text=original, proposed_text=proposed)
