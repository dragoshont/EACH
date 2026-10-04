"""Unit tests for Receipt Markdown audit-section rendering, covering both
the M1 stub shape and the M4 real-engine shape (and confirming no per-check
status is ever collapsed into a single score in the rendered text)."""

from __future__ import annotations

from each.audit.run import run_audit
from each.audit.stub import audit_stub
from each.receipt import _audit_markdown_lines


def test_renders_m1_stub_shape() -> None:
    lines = _audit_markdown_lines(audit_stub())
    joined = "\n".join(lines)
    assert "Result: UNAVAILABLE" in joined
    assert "Reason:" in joined


def test_renders_m4_engine_shape_with_every_check_and_no_single_score() -> None:
    audit = run_audit("some candidate text")
    lines = _audit_markdown_lines(audit)
    joined = "\n".join(lines)
    for name in ("exact-substring", "ngram-similarity", "ast-similarity", "license-scan", "corpus-membership"):
        assert name in joined
    assert "score" not in joined.lower()
    assert "Tool versions" in joined
    assert "Corpus revision: none" in joined
