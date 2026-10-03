"""A generic, format-tolerant alternative to diff-shaped model output.

``each.patch`` asks a declared local model to emit a unified diff directly,
including hand-computed hunk-header line counts. For a full-file-rewrite
task in particular, this asks the model to both (a) reproduce every
original line verbatim as a "-" line and (b) get the resulting header
arithmetic exactly right -- two independent, compounding ways to fail that
have nothing to do with whether the model's actual *implementation* is
correct.

This module offers a deterministic alternative: ask the model for the
complete NEW file content between ``BEGIN_SOURCE``/``END_SOURCE`` markers
only, and have the harness itself derive the unified diff with
``difflib.unified_diff`` against the exact known pre-image. The model never
computes a hunk header or reproduces old lines verbatim; the harness does
that arithmetic the same way every time, from source the harness already
possesses.

This is a generic proposal-format adapter, not a new agent framework: it
changes only how one candidate's raw text is turned into a unified diff
before the EXACT SAME ``each.patch`` scope/path/pre-image validation runs
on the result. It single-file-only (the only kind of task this project
already supports), rejects multiple files, prose, an unbounded/truncated
response, or an empty body -- it never fabricates a default patch when
parsing fails.
"""

from __future__ import annotations

import difflib

SOURCE_BEGIN = "BEGIN_SOURCE"
SOURCE_END = "END_SOURCE"


class RawProposalRejected(RuntimeError):
    """Raised when a full-source completion cannot be safely parsed."""


def extract_full_source(completion: str) -> str:
    """Pull the complete new file body out of BEGIN_SOURCE/END_SOURCE markers.

    Rejects a completion that is missing either marker, has more than one
    occurrence of either marker (ambiguous as to which body is intended),
    or whose extracted body is empty. Never falls back to a different
    extraction strategy or a default/placeholder body.
    """
    begin_count = completion.count(SOURCE_BEGIN)
    end_count = completion.count(SOURCE_END)
    if begin_count == 0 or end_count == 0:
        raise RawProposalRejected("completion is missing BEGIN_SOURCE/END_SOURCE markers")
    if begin_count > 1 or end_count > 1:
        raise RawProposalRejected("completion has more than one BEGIN_SOURCE/END_SOURCE marker pair")
    # (C1, GPT-6 Astra release review) ``str.split`` alone never checks marker
    # ORDER: if END_SOURCE happens to appear earlier in the text than
    # BEGIN_SOURCE, splitting on BEGIN_SOURCE first then searching for
    # END_SOURCE only in what follows it would silently find no END_SOURCE
    # there and fall back to treating the rest of the completion as the body
    # -- an unbounded, un-terminated extraction instead of a clear rejection.
    if completion.index(SOURCE_END) < completion.index(SOURCE_BEGIN):
        raise RawProposalRejected("END_SOURCE marker appears before BEGIN_SOURCE marker")
    body = completion.split(SOURCE_BEGIN, 1)[1].split(SOURCE_END, 1)[0]
    body = body.strip("\n")
    if not body.strip():
        raise RawProposalRejected("empty source body")
    return body + "\n"


def derive_unified_diff(*, path: str, original_text: str, proposed_text: str) -> str:
    """Deterministically derive a unified diff from two known, complete file
    bodies using the Python standard library's ``difflib`` -- never the
    model's own (unreliable) hunk-header arithmetic.

    Returns an empty string if the two texts are identical (a legitimate,
    honestly-reported "no change" outcome, not an error): callers must
    decide whether a no-op proposal counts as a rejected attempt.

    Fails closed (raises :class:`RawProposalRejected`) if either text does
    not end with a trailing newline. Python's ``difflib.unified_diff``
    does not emit a ``\\ No newline at end of file`` marker, so a line
    lacking ``\\n`` that is not the very last line ``"".join()``-ed into
    the output would be silently fused with the following diff record
    (its own prefix glued onto the previous line's text) rather than
    producing a readable or even a correctly-rejectable malformed diff.
    This project's declared/approved materials are expected to end with a
    trailing newline; this is a deliberate unsupported-input policy, not a
    silent correctness relaxation.
    """
    if original_text and not original_text.endswith("\n"):
        raise RawProposalRejected("original file does not end with a trailing newline; unsupported input")
    if proposed_text and not proposed_text.endswith("\n"):
        raise RawProposalRejected("proposed source does not end with a trailing newline; unsupported input")
    original_lines = original_text.splitlines(keepends=True)
    proposed_lines = proposed_text.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            original_lines,
            proposed_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
    if not diff_lines:
        return ""
    return "".join(diff_lines)
