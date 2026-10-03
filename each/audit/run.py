"""M4 real provenance-audit combinator.

Runs every independent check and returns their results side by side (no
single "cleanliness score" — mandate section 126). Records audit tool
versions/config so a receipt's audit section states exactly what ran, not
just a verdict.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from each.audit.checks import (
    ast_similarity_check,
    exact_substring_check,
    license_scan_check,
    ngram_similarity_check,
)
from each.audit.corpus import CorpusMembershipAdapter, NullCorpusAdapter

CHECK_NAMES = frozenset({
    "exact-substring", "ngram-similarity", "ast-similarity", "license-scan", "corpus-membership",
})


def _tool_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {"each-audit": "v0.1-mvp"}
    for field, package in (("treeSitter", "tree-sitter"), ("treeSitterPython", "tree-sitter-python")):
        try:
            versions[field] = version(package)
        except PackageNotFoundError:
            versions[field] = None
    return versions


def run_audit(
    candidate: str,
    *,
    corpus: list[str] | None = None,
    corpus_adapter: CorpusMembershipAdapter | None = None,
    license_paths: list[str] | None = None,
    corpus_revision: str = "none",
    required_checks: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Run every M4 check against ``candidate``.

    ``corpus`` is the small, explicitly-declared set of known snippets to
    compare against for exact/n-gram/AST matching (empty by default, which
    honestly reports those checks UNAVAILABLE rather than a fabricated
    PASS — there is no configured comparison corpus in that case).
    """
    _validate_required_checks(required_checks)
    corpus = corpus or []
    adapter = corpus_adapter or NullCorpusAdapter()
    checks = {
        "exact-substring": exact_substring_check(candidate, corpus),
        "ngram-similarity": ngram_similarity_check(candidate, corpus),
        "ast-similarity": ast_similarity_check(candidate, corpus),
        "license-scan": license_scan_check(license_paths),
        "corpus-membership": adapter.check(candidate),
    }
    result = {
        "checks": {name: result.to_dict() for name, result in checks.items()},
        "toolVersions": _tool_versions(),
        "corpusRevision": corpus_revision,
        "configuration": {
            "exactMinimumReferenceLength": 20,
            "ngram": {"n": 3, "flagThreshold": 0.5, "failThreshold": 0.8},
            "ast": {"language": "python", "flagThreshold": 0.6, "failThreshold": 0.85},
        },
    }
    unavailable = [name for name, check in checks.items() if check.status == "UNAVAILABLE"]
    result["policy"] = {
        "requiredChecks": list(required_checks),
        "missingRequiredChecks": [name for name in required_checks if name in unavailable],
        "optionalUnavailableChecks": [name for name in unavailable if name not in required_checks],
        "qualifiedForDeclaredChecks": bool(required_checks) and not reject_on_audit_flag(
            result, required_checks=required_checks,
        ),
        "coverageCeiling": "declared-reference-only" if corpus else "unavailable",
    }
    return result


def any_status(audit_result: dict[str, Any], status: str) -> bool:
    """True if any check in an audit result carries the given status."""
    return any(check["status"] == status for check in audit_result["checks"].values())


def _validate_required_checks(required_checks: tuple[str, ...]) -> None:
    if set(required_checks) - CHECK_NAMES:
        raise ValueError("unknown required audit check")


def reject_on_audit_flag(
    audit_result: dict[str, Any], *,
    reject_statuses: tuple[str, ...] = ("FAIL",),
    required_checks: tuple[str, ...] = (),
) -> bool:
    """The terminal-boundary decision point: should this candidate be rejected?

    Deliberately takes only the audit *result* (metadata-only evidence, no
    matched source text — see each.audit.checks) and returns a bare bool.
    There is no code path here, or anywhere in each.audit, that returns
    matched corpus/source content to a caller: a retry that honors this
    decision can only restart from the original approved spec, because
    nothing else is available to build a new prompt from.
    """
    _validate_required_checks(required_checks)
    checks = audit_result.get("checks", {})
    if any(checks.get(name, {}).get("status") not in {"PASS", "FLAG", "FAIL"} for name in required_checks):
        return True
    return any(check.get("status") in reject_statuses for check in checks.values())
