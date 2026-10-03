"""M4 provenance-audit checks: real, independent, non-collapsed comparators.

Each check returns one of PASS / FLAG / FAIL / UNAVAILABLE plus evidence
that is deliberately metadata-only (hashes, lengths, indices, similarity
ratios) — never the literal matched source text. This is a structural,
test-provable enforcement of the mandate's terminal-boundary requirement:
"Auditor results must never feed matching source or implementation
details back into Builder." A caller cannot accidentally leak matched
source into a retry prompt if the Auditor never hands it any.

Multiple independent checks are returned side by side; nothing here
collapses them into a single "cleanliness score" (mandate section 126).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from each.hashing import sha256_text

_MIN_EXACT_MATCH_LEN = 20
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+")

STATUSES = ("PASS", "FLAG", "FAIL", "UNAVAILABLE")


@dataclass(frozen=True)
class CheckResult:
    status: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"invalid check status: {self.status!r} (must be one of {STATUSES})")

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "detail": self.detail, "evidence": self.evidence}


def normalize_text(text: str) -> str:
    """Collapse whitespace so cosmetic reformatting doesn't defeat matching."""
    return " ".join(text.split())


def _tokenize(text: str) -> list[str]:
    return [tok.lower() for tok in _TOKEN_RE.findall(text)]


def exact_substring_check(candidate: str, corpus: list[str]) -> CheckResult:
    """Catches a verbatim (or whitespace-reformatted) copy."""
    if not corpus:
        return CheckResult(status="UNAVAILABLE", detail="no corpus snippets configured for exact/substring matching")
    normalized_candidate = normalize_text(candidate)
    eligible_snippet_count = 0
    for index, snippet in enumerate(corpus):
        normalized_snippet = normalize_text(snippet)
        if len(normalized_snippet) < _MIN_EXACT_MATCH_LEN:
            continue
        eligible_snippet_count += 1
        if normalized_snippet in normalized_candidate or normalized_candidate in normalized_snippet:
            return CheckResult(
                status="FAIL",
                detail="candidate contains (or is contained in) a corpus snippet verbatim",
                evidence={
                    "corpusIndex": index,
                    "corpusSnippetSha256": sha256_text(normalized_snippet),
                    "matchedLength": min(len(normalized_snippet), len(normalized_candidate)),
                },
            )
    if eligible_snippet_count == 0:
        return CheckResult(
            status="UNAVAILABLE",
            detail="no corpus snippets met the minimum comparison length for exact/substring matching",
        )
    return CheckResult(status="PASS", detail="no verbatim/whitespace-reformatted corpus match found")


def ngram_similarity_check(
    candidate: str, corpus: list[str], *, n: int = 3, flag_threshold: float = 0.5, fail_threshold: float = 0.8
) -> CheckResult:
    """Normalized token n-gram Jaccard similarity: catches near-verbatim
    copies with minor edits, but — unlike the AST check — is defeated by
    identifier renaming (each renamed token changes every n-gram it's in)."""
    if not corpus:
        return CheckResult(status="UNAVAILABLE", detail="no corpus snippets configured for n-gram similarity")
    candidate_tokens = _tokenize(candidate)
    candidate_grams = _ngrams(candidate_tokens, n)
    best_ratio = 0.0
    best_index = None
    for index, snippet in enumerate(corpus):
        snippet_grams = _ngrams(_tokenize(snippet), n)
        ratio = _jaccard(candidate_grams, snippet_grams)
        if ratio > best_ratio:
            best_ratio, best_index = ratio, index
    status = "FAIL" if best_ratio >= fail_threshold else "FLAG" if best_ratio >= flag_threshold else "PASS"
    return CheckResult(
        status=status,
        detail=f"best n-gram Jaccard similarity against corpus = {best_ratio:.3f}",
        evidence={"bestCorpusIndex": best_index, "bestRatio": round(best_ratio, 3), "n": n},
    )


def _ngrams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    if len(tokens) < n:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def ast_similarity_check(
    candidate: str, corpus: list[str], *, flag_threshold: float = 0.6, fail_threshold: float = 0.85
) -> CheckResult:
    """Tree-sitter AST-normalized comparator: compares the preorder sequence
    of node *types* (never identifier/literal text), so it catches a
    structurally-identical copy that was merely renamed — the case the
    n-gram check above is blind to."""
    if not corpus:
        return CheckResult(status="UNAVAILABLE", detail="no corpus snippets configured for AST similarity")
    try:
        import tree_sitter_python as _tspython
        from tree_sitter import Language, Parser
    except ImportError:
        return CheckResult(
            status="UNAVAILABLE",
            detail="tree-sitter is not installed; install the optional 'audit' extra (uv sync --extra audit)",
        )
    parser = Parser(Language(_tspython.language()))
    candidate_seq = _ast_type_sequence(parser, candidate)
    best_ratio = 0.0
    best_index = None
    for index, snippet in enumerate(corpus):
        snippet_seq = _ast_type_sequence(parser, snippet)
        ratio = SequenceMatcher(None, candidate_seq, snippet_seq).ratio()
        if ratio > best_ratio:
            best_ratio, best_index = ratio, index
    status = "FAIL" if best_ratio >= fail_threshold else "FLAG" if best_ratio >= flag_threshold else "PASS"
    return CheckResult(
        status=status,
        detail=f"best AST (node-type sequence) similarity against corpus = {best_ratio:.3f}",
        evidence={"bestCorpusIndex": best_index, "bestRatio": round(best_ratio, 3)},
    )


def _ast_type_sequence(parser: Any, source: str) -> list[str]:
    tree = parser.parse(source.encode("utf-8"))
    sequence: list[str] = []

    def walk(node: Any) -> None:
        sequence.append(node.type)
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return sequence


def license_scan_check(paths: list[str] | None = None) -> CheckResult:
    """Mature license-scanner integration (e.g. scancode-toolkit) is out of
    scope for v0.1: it is a large dependency with no demonstrated need yet
    (YAGNI). Honestly UNAVAILABLE rather than a shallow regex pretending to
    be a real scanner. License compatibility is instead a human-reviewed
    declaration on the approved spec (SpecPacket.forbidden_sources)."""
    return CheckResult(
        status="UNAVAILABLE",
        detail="mature license-scanner integration not implemented in v0.1 (YAGNI); see SpecPacket.forbidden_sources",
    )
