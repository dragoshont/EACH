"""Bounded, generic extraction of compiler/test diagnostics for a Builder
correction retry.

A bare "the patch did not pass" retry message gives a local model no
actionable information about *why*: a syntax error, a specific assertion,
and a wrong return value all look identical to it. Real pytest/compiler
output does carry that information -- but it also embeds literal source
lines from whatever file pytest prints context around, which may be the
hidden approved-test file's own body (never permitted Builder input).

This module extracts only a small, bounded, structurally-identified subset
of a real pytest run's own stdout/stderr: the "E "-prefixed exception/
assertion lines pytest's default long-form traceback already produces (the
actual failing assertion/exception, never the surrounding source-context
lines pytest prints without that prefix), plus the final one-line pytest
summary and any "FAILED <nodeid>" lines from the short test summary
section. It never includes a literal source-code context line, never
reads the hidden test file directly, and is capped to a small character
budget with an explicit, recorded truncation marker.
"""

from __future__ import annotations

import re

# pytest's default long verbose traceback prefixes the actual failing
# assertion/exception line (and continuation lines of a multi-line
# assertion message) with "E ", distinct from the unprefixed source-context
# lines surrounding it -- this is the one line class that carries
# diagnostic signal without being a verbatim source dump.
_E_LINE_RE = re.compile(r"^E +(.*)$", re.MULTILINE)
_FAILED_NODEID_RE = re.compile(r"^(?:FAILED|ERROR) +(\S+)", re.MULTILINE)
_SUMMARY_RE = re.compile(r"^=*\s*\d+ (?:failed|passed|error)[\w, ]* in [\d.]+s\s*=*\s*$", re.MULTILINE)

MAX_FEEDBACK_CHARS = 1500
MAX_E_LINES = 12
MAX_FAILED_NODEIDS = 6

TRUNCATION_MARKER = "...[truncated]"


def extract_bounded_test_feedback(stdout: str, stderr: str) -> str:
    """Return a small, bounded, structurally-filtered diagnostic string
    from a real pytest run's own output. Deterministic given the same
    input; never includes a verbatim source-context line or any content
    outside the three filtered line classes described above.
    """
    combined = stdout + "\n" + stderr
    e_lines = _E_LINE_RE.findall(combined)[:MAX_E_LINES]
    failed_nodeids = _FAILED_NODEID_RE.findall(combined)[:MAX_FAILED_NODEIDS]
    summary_match = _SUMMARY_RE.search(combined)

    parts: list[str] = []
    if failed_nodeids:
        parts.append("Failing test case(s): " + ", ".join(failed_nodeids))
    if e_lines:
        parts.append("Exception/assertion detail:\n" + "\n".join(f"  {line}" for line in e_lines))
    if summary_match:
        parts.append(summary_match.group(0).strip())

    if not parts:
        return ""

    feedback = "\n".join(parts)
    if len(feedback) > MAX_FEEDBACK_CHARS:
        feedback = feedback[:MAX_FEEDBACK_CHARS] + TRUNCATION_MARKER
    return feedback
