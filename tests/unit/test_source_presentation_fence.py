import pytest

from each.raw_proposal import RawProposalRejected, extract_full_source


@pytest.mark.parametrize("language", ["", "python", "c++", "rust"])
def test_one_closed_source_presentation_fence(language):
    assert extract_full_source(f"BEGIN_SOURCE\n```{language}\ndef f(x): return x\n```\nEND_SOURCE") == (
        "def f(x): return x\n"
    )


@pytest.mark.parametrize("body", [
    "```python\ndef f(x): return x", "```python\nx\n```\nprose",
    "```python\nx\n```\n```python\ny\n```", "```python\n\n```",
])
def test_incomplete_ambiguous_or_empty_source_fence_rejected(body):
    with pytest.raises(RawProposalRejected):
        extract_full_source(f"BEGIN_SOURCE\n{body}\nEND_SOURCE")
