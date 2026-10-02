"""M4 real provenance-audit combinator.

Runs every independent check and returns their results side by side (no
single "cleanliness score" — mandate section 126). Records audit tool
versions/config so a receipt's audit section states exactly what ran, not
just a verdict.
"""

from __future__ import annotations

from typing import Any

from each.audit.checks import (
    ast_similarity_check,
    exact_substring_check,
    license_scan_check,
    ngram_similarity_check,
)
from each.audit.corpus import CorpusMembershipAdapter, NullCorpusAdapter


def _tool_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {"each-audit": "v0.1-mvp"}
    try:
        import tree_sitter

        versions["treeSitter"] = getattr(tree_sitter, "__version__", "unknown")
    except ImportError:
        versions["treeSitter"] = None
    try:
        import tree_sitter_python

        versions["treeSitterPython"] = getattr(tree_sitter_python, "__version__", "unknown")
    except ImportError:
        versions["treeSitterPython"] = None
    return versions


def run_audit(
    candidate: str,
    *,
    corpus: list[str] | None = None,
    corpus_adapter: CorpusMembershipAdapter | None = None,
    license_paths: list[str] | None = None,
    corpus_revision: str = "none",
) -> dict[str, Any]:
    """Run every M4 check against ``candidate``.

    ``corpus`` is the small, explicitly-declared set of known snippets to
    compare against for exact/n-gram/AST matching (empty by default, which
    honestly reports those checks UNAVAILABLE rather than a fabricated
    PASS — there is no configured comparison corpus in that case).
    """
    corpus = corpus or []
    adapter = corpus_adapter or NullCorpusAdapter()
    checks = {
        "exact-substring": exact_substring_check(candidate, corpus),
        "ngram-similarity": ngram_similarity_check(candidate, corpus),
        "ast-similarity": ast_similarity_check(candidate, corpus),
        "license-scan": license_scan_check(license_paths),
        "corpus-membership": adapter.check(candidate),
    }
    return {
        "checks": {name: result.to_dict() for name, result in checks.items()},
        "toolVersions": _tool_versions(),
        "corpusRevision": corpus_revision,
    }


def any_status(audit_result: dict[str, Any], status: str) -> bool:
    """True if any check in an audit result carries the given status."""
    return any(check["status"] == status for check in audit_result["checks"].values())


def reject_on_audit_flag(audit_result: dict[str, Any], *, reject_statuses: tuple[str, ...] = ("FAIL",)) -> bool:
    """The terminal-boundary decision point: should this candidate be rejected?

    Deliberately takes only the audit *result* (metadata-only evidence, no
    matched source text — see each.audit.checks) and returns a bare bool.
    There is no code path here, or anywhere in each.audit, that returns
    matched corpus/source content to a caller: a retry that honors this
    decision can only restart from the original approved spec, because
    nothing else is available to build a new prompt from.
    """
    return any(audit_result["checks"][name]["status"] in reject_statuses for name in audit_result["checks"])
