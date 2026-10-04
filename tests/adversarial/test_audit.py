"""M4 adversarial audit tests.

Exercises the five required fixture categories (exact copy, renamed copy,
common boilerplate, independently-written semantic equivalent, corpus
membership) and proves the terminal-boundary requirement: the Auditor
never returns matched source/implementation text to a caller — only
metadata (hashes, lengths, similarity ratios) — so a retry loop built on
top of it structurally cannot feed matched content back into Builder.
"""

from __future__ import annotations

import pytest

from each.audit.checks import ast_similarity_check, exact_substring_check, ngram_similarity_check
from each.audit.corpus import InMemoryCorpusAdapter, NullCorpusAdapter
from each.audit.run import reject_on_audit_flag, run_audit

_CORPUS_SNIPPET = """def add(a, b):
    return a + b"""

_EXACT_COPY = """def add(a, b):
    return a + b"""

_RENAMED_COPY = """def sum_two(x, y):
    return x + y"""

_COMMON_BOILERPLATE = """if __name__ == "__main__":
    main()"""

_SEMANTIC_EQUIVALENT = """def combine(numbers):
    total = 0
    for n in numbers:
        total += n
    return total"""


def test_exact_copy_is_detected() -> None:
    result = exact_substring_check(_EXACT_COPY, [_CORPUS_SNIPPET])
    assert result.status == "FAIL"


def test_ngram_check_on_exact_copy_is_fail() -> None:
    result = ngram_similarity_check(_EXACT_COPY, [_CORPUS_SNIPPET])
    assert result.status == "FAIL"


def test_renamed_copy_evades_exact_and_ngram_checks() -> None:
    # Honest limitation: lexical checks cannot see past identifier renames.
    assert exact_substring_check(_RENAMED_COPY, [_CORPUS_SNIPPET]).status == "PASS"
    assert ngram_similarity_check(_RENAMED_COPY, [_CORPUS_SNIPPET]).status == "PASS"


def test_renamed_copy_is_caught_by_ast_similarity() -> None:
    pytest.importorskip("tree_sitter")
    result = ast_similarity_check(_RENAMED_COPY, [_CORPUS_SNIPPET])
    assert result.status == "FAIL"


def test_common_boilerplate_is_not_flagged() -> None:
    pytest.importorskip("tree_sitter")
    result = run_audit(_COMMON_BOILERPLATE, corpus=[_CORPUS_SNIPPET])
    for name, check in result["checks"].items():
        assert check["status"] in {"PASS", "UNAVAILABLE"}, (name, check)


def test_independently_written_semantic_equivalent_is_not_flagged() -> None:
    # Honest limitation, not a false PASS pretending to be proof of
    # originality: structural/lexical comparators cannot detect true
    # semantic equivalence when the implementation is substantially
    # rewritten. This fixture documents that, it does not hide it.
    pytest.importorskip("tree_sitter")
    result = run_audit(_SEMANTIC_EQUIVALENT, corpus=[_CORPUS_SNIPPET])
    for name, check in result["checks"].items():
        assert check["status"] in {"PASS", "UNAVAILABLE"}, (name, check)


def test_corpus_membership_adapter_is_pluggable_and_detects_a_known_member() -> None:
    adapter = InMemoryCorpusAdapter(members=[_CORPUS_SNIPPET])
    result = run_audit(_EXACT_COPY, corpus_adapter=adapter)
    assert result["checks"]["corpus-membership"]["status"] == "FAIL"


def test_default_corpus_membership_adapter_is_honestly_unavailable() -> None:
    result = run_audit(_EXACT_COPY, corpus_adapter=NullCorpusAdapter())
    assert result["checks"]["corpus-membership"]["status"] == "UNAVAILABLE"


def test_unconfigured_checks_are_unavailable_not_a_fabricated_pass() -> None:
    result = run_audit("any candidate text")
    for name, check in result["checks"].items():
        assert check["status"] == "UNAVAILABLE", (name, check)


def test_license_scan_is_honestly_unavailable_in_v0_1() -> None:
    result = run_audit("any candidate text")
    assert result["checks"]["license-scan"]["status"] == "UNAVAILABLE"


def test_tool_versions_are_recorded() -> None:
    result = run_audit("any candidate text")
    assert "treeSitter" in result["toolVersions"]
    assert "treeSitterPython" in result["toolVersions"]
    assert result["corpusRevision"] == "none"


def test_reject_on_audit_flag_true_when_any_check_fails() -> None:
    result = run_audit(_EXACT_COPY, corpus=[_CORPUS_SNIPPET])
    assert reject_on_audit_flag(result) is True


def test_reject_on_audit_flag_false_when_nothing_fails() -> None:
    result = run_audit("completely unrelated text with no matches at all")
    assert reject_on_audit_flag(result) is False


def test_no_check_evidence_ever_contains_the_literal_matched_source_text() -> None:
    """Terminal-boundary proof: every evidence dict across every check is
    metadata-only (hashes, indices, ratios, lengths) -- never the literal
    corpus snippet or candidate text itself. A caller cannot accidentally
    build a new model prompt from "what matched" because the Auditor never
    hands that text back, by construction."""
    result = run_audit(_EXACT_COPY, corpus=[_CORPUS_SNIPPET], corpus_adapter=InMemoryCorpusAdapter([_CORPUS_SNIPPET]))
    for name, check in result["checks"].items():
        evidence_values = list(check["evidence"].values())
        for value in evidence_values:
            if isinstance(value, str):
                assert _CORPUS_SNIPPET not in value, f"{name} evidence leaked corpus source text: {value!r}"
                assert _EXACT_COPY not in value, f"{name} evidence leaked candidate source text: {value!r}"


def test_run_audit_does_not_collapse_into_a_single_score() -> None:
    result = run_audit(_EXACT_COPY, corpus=[_CORPUS_SNIPPET])
    assert "score" not in result
    assert set(result["checks"]) == {
        "exact-substring",
        "ngram-similarity",
        "ast-similarity",
        "license-scan",
        "corpus-membership",
    }
