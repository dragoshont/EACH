"""Canonical, bounded outcome classification shared by every Builder pipeline.

A pipeline's internal, per-attempt diagnostic text (a diff-parser error
message, a raw compiler/test stdout+stderr dict) can contain fragments of
candidate-controlled content -- including, for a native compile, literal
source-line snippets GCC prints alongside each diagnostic. That text is
fine inside a receipt's own private fields (``attempts``, a dedicated
``*_result`` field), but it must never be embedded in a field that a
source-free export (e.g. ``each.xodus_shadow.summarize_receipt``) or a
pipeline's own public-facing return value treats as safe to surface.

``sanitize_outcome_class`` is the one function such a boundary may call on
a possibly candidate-influenced outcome string: it returns only one of a
fixed, reviewed label, never free text.
"""

from __future__ import annotations

# Every top-level/attempt outcome label every Builder pipeline
# (each.demo/bakeoff/benchmark/clean_room/xodus_shadow) currently
# constructs. Adding a new label here is a deliberate, reviewed decision,
# not an incidental side effect of a new f-string prefix.
OUTCOME_CLASSES = frozenset(
    {
        "REPAIR_VERIFIED",
        "REPAIR_NOT_VERIFIED",
        "REPAIR_REJECTED_AUDIT",
        "PATCH_REJECTED",
        "EXECUTION_ERROR",
        "BUILD_FAILED",
        "ISOLATION_UNVERIFIED",
        "BUILDER_CONTEXT_BUDGET_EXCEEDED",
        "BASELINE_INCONCLUSIVE",
        "REPAIRED_RUN_INCONCLUSIVE",
        # each.benchmark_report: a per-task materialization failure (dead
        # repo/tarball link, rate limit, pip install failure) before any
        # benchmark attempt loop ever started.
        "TASK_MATERIALIZATION_FAILED",
    }
)

UNKNOWN_OUTCOME_CLASS = "UNKNOWN_OUTCOME_CLASS"


def sanitize_outcome_class(outcome: str) -> str:
    """Return the leading, whitelisted class of ``outcome``, discarding any
    free-text detail after it (and discarding the entire value if even its
    leading label is not recognized). Never returns anything other than one
    of :data:`OUTCOME_CLASSES` or :data:`UNKNOWN_OUTCOME_CLASS`.
    """
    head = outcome.split(":", 1)[0].strip()
    return head if head in OUTCOME_CLASSES else UNKNOWN_OUTCOME_CLASS


# Every ``proposal_format`` value every Builder pipeline's attempt record
# currently declares. A source-free export must never surface an arbitrary
# model/attempt-controlled string through this field -- only one of these
# reviewed labels.
PROPOSAL_FORMAT_CLASSES = frozenset({"diff", "full_source", "source_edit", "fim"})

UNKNOWN_PROPOSAL_FORMAT_CLASS = "UNKNOWN_PROPOSAL_FORMAT_CLASS"


def sanitize_proposal_format(proposal_format: object) -> str:
    """Return ``proposal_format`` unchanged only if it is one of the fixed,
    reviewed :data:`PROPOSAL_FORMAT_CLASSES` labels; otherwise returns
    :data:`UNKNOWN_PROPOSAL_FORMAT_CLASS`. Never returns an arbitrary
    attempt-controlled string.
    """
    return proposal_format if proposal_format in PROPOSAL_FORMAT_CLASSES else UNKNOWN_PROPOSAL_FORMAT_CLASS
