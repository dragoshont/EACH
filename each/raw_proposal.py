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
import json
import re

SOURCE_BEGIN = "BEGIN_SOURCE"
SOURCE_END = "END_SOURCE"

# (edit-proposal mode) A still-smaller-surface alternative to both
# diff-shaped and full-source-shaped output: when a candidate is already
# mostly correct (e.g. a prior bounded correction chain converged on a
# generally-working file that still fails one approved requirement), asking
# the model to regenerate or re-diff the ENTIRE file gives it maximal
# surface area to silently reintroduce an already-fixed defect while fixing
# another. Asking for the smallest possible find-and-replace edit to its own
# previously-captured candidate bounds the blast radius of each individual
# correction attempt to exactly the text it names.
_EDIT_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*)\n```$", re.DOTALL)
EDIT_MAX_RESPONSE_CHARS = 20_000
EDIT_MAX_FIELD_CHARS = 10_000


class RawProposalRejected(RuntimeError):
    """Raised when a full-source or edit-proposal completion cannot be safely parsed."""


def extract_source_edit(completion: str) -> dict[str, str]:
    """Parse a strict, minimal JSON edit object: ``{"old": "...", "new": "..."}``.

    The harness performs the actual substitution itself (see
    :func:`apply_source_edit`) once ``old`` is confirmed to occur exactly
    once in the model's own previously-captured candidate source, then
    still derives the final unified diff with ``difflib`` against the
    original known pre-image -- exactly as :func:`extract_full_source`/
    :func:`derive_unified_diff` already do for full-file proposals. Only
    how one candidate's raw text becomes two known-good strings changes.

    Rejects: a non-JSON-object completion, missing/extra top-level keys,
    non-string values, an empty ``old``, ``old == new`` (a no-op
    masquerading as an edit), and an oversized response or field (a
    bounded sanity limit, never a content-based judgement). Tolerates one
    optional, fully-closed enclosing markdown code fence (some
    instruction-tuned models wrap JSON output in one regardless of
    instructions) but never a second fence or unfenced prose around the
    object.
    """
    text = completion.strip()
    if len(text) > EDIT_MAX_RESPONSE_CHARS:
        raise RawProposalRejected(f"edit-proposal response exceeds the bounded size limit ({len(text)} chars)")
    fence_match = _EDIT_FENCE_RE.match(text)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RawProposalRejected(f"edit-proposal response is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RawProposalRejected("edit-proposal response must be a JSON object")
    if set(payload.keys()) != {"old", "new"}:
        raise RawProposalRejected(
            f"edit-proposal response must have exactly the keys 'old' and 'new', got {sorted(payload.keys())!r}"
        )
    old, new = payload["old"], payload["new"]
    if not isinstance(old, str) or not isinstance(new, str):
        raise RawProposalRejected("edit-proposal 'old' and 'new' must both be JSON strings")
    if len(old) > EDIT_MAX_FIELD_CHARS or len(new) > EDIT_MAX_FIELD_CHARS:
        raise RawProposalRejected("edit-proposal 'old'/'new' field exceeds the bounded size limit")
    if not old:
        raise RawProposalRejected("edit-proposal 'old' must be non-empty")
    if old == new:
        raise RawProposalRejected("edit-proposal 'old' and 'new' are identical; not an edit")
    return {"old": old, "new": new}


def apply_source_edit(*, previous_source: str, edit: dict[str, str]) -> str:
    """Apply a validated ``{"old", "new"}`` edit to ``previous_source`` via a
    single, deterministic ``str.replace`` -- never a partial, fuzzy, or
    first/last-occurrence match. Requires ``old`` to occur in
    ``previous_source`` EXACTLY once: an absent or ambiguous (multiple
    equally-valid) occurrence is rejected rather than silently guessed at.
    """
    old, new = edit["old"], edit["new"]
    occurrences = previous_source.count(old)
    if occurrences == 0:
        raise RawProposalRejected("edit-proposal 'old' text does not occur in the previous candidate source")
    if occurrences > 1:
        raise RawProposalRejected(
            f"edit-proposal 'old' text occurs {occurrences} times in the previous candidate source; must be unique"
        )
    return previous_source.replace(old, new, 1)


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
