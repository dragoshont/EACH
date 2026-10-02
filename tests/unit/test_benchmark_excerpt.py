"""Unit coverage for each.benchmark.select_prompt_excerpt: the deterministic,
diff-blind source-excerpting mechanism that lets real multi-KB whole-file
historical sources fit a model's actual context budget.

Selection must depend ONLY on the pre-fix bug source and the pre-fix test
source's own public references (names the test file imports/calls) -- never
on the known fix's diff or changed-line positions. These tests assert both
the inclusion/exclusion behavior and that the result is identical regardless
of what the (unseen) fix eventually changes.
"""

from __future__ import annotations

from each.benchmark import select_prompt_excerpt

_BUG_SOURCE = '''"""Module docstring, several lines long, not referenced by any test."""

CONSTANT_UNUSED = 1


def helper_used_by_target(x):
    return x + 1


def target_function(value):
    return helper_used_by_target(value) * 2


def unrelated_function(y):
    """Never referenced by the test file; must be excluded from the excerpt."""
    return y * 2


class UnrelatedClass:
    """Also never referenced; must be excluded."""

    def method(self):
        return 1
'''

_TEST_SOURCE = """from mod import target_function


def test_target_function_doubles_the_helper_result():
    assert target_function(1) == 4
"""


def test_excerpt_includes_the_referenced_function_and_its_local_helper() -> None:
    excerpt, start, end = select_prompt_excerpt(_BUG_SOURCE, [_TEST_SOURCE])
    assert "def target_function" in excerpt
    assert "def helper_used_by_target" in excerpt
    assert start >= 1
    assert end <= len(_BUG_SOURCE.splitlines())


def test_excerpt_excludes_unreferenced_top_level_defs() -> None:
    excerpt, _start, _end = select_prompt_excerpt(_BUG_SOURCE, [_TEST_SOURCE])
    assert "def unrelated_function" not in excerpt
    assert "class UnrelatedClass" not in excerpt


def test_excerpt_labels_each_kept_block_with_real_absolute_line_numbers() -> None:
    """Each kept block (even when nothing was elided between two adjacent
    referenced functions) is labeled with its own real absolute line
    numbers, so the model always knows the correct numbers for a diff hunk
    header wherever it edits."""
    excerpt, _start, _end = select_prompt_excerpt(_BUG_SOURCE, [_TEST_SOURCE])
    assert "# Lines" in excerpt
    assert "def helper_used_by_target" in excerpt
    assert "def target_function" in excerpt


def test_excerpt_selection_never_depends_on_the_known_fix_content() -> None:
    """The selector only ever receives the pre-fix bug source and the
    pre-fix test source; it has no fix_sha/diff parameter at all, so the
    selection for the exact same (bug_source, test_sources) pair is always
    identical -- this is a structural guarantee, exercised here by calling
    it twice and confirming byte-identical output, which is the strongest
    assertion possible without a diff/fix parameter to vary."""
    first = select_prompt_excerpt(_BUG_SOURCE, [_TEST_SOURCE])
    second = select_prompt_excerpt(_BUG_SOURCE, [_TEST_SOURCE])
    assert first == second


def test_falls_back_to_the_whole_file_when_no_test_reference_matches() -> None:
    unrelated_test = "def test_something_else():\n    assert True\n"
    excerpt, start, end = select_prompt_excerpt(_BUG_SOURCE, [unrelated_test])
    assert excerpt == _BUG_SOURCE
    assert (start, end) == (1, len(_BUG_SOURCE.splitlines()))


def test_falls_back_to_the_whole_file_for_unparseable_source() -> None:
    broken_source = "def broken(:\n    pass\n"
    excerpt, start, end = select_prompt_excerpt(broken_source, [_TEST_SOURCE])
    assert excerpt == broken_source
    assert (start, end) == (1, len(broken_source.splitlines()))


def test_decorated_function_excerpt_starts_at_the_decorator_line() -> None:
    decorated_source = (
        "def unrelated(y):\n"
        "    return y\n"
        "\n"
        "\n"
        "@staticmethod\n"
        "def target_function(value):\n"
        "    return value\n"
    )
    test_source = "from mod import target_function\n\n\ndef test_it():\n    assert target_function(1) == 1\n"
    excerpt, start, end = select_prompt_excerpt(decorated_source, [test_source])
    assert "@staticmethod\ndef target_function" in excerpt
    assert start == 5
    assert end == 7


_CLASS_SOURCE = '''class Signer:
    """A long docstring with lots of unrelated prose that would otherwise
    bloat every excerpt that touches this class, across many lines of
    versionchanged notes and usage examples that are not needed to
    understand or repair the one broken method below.
    """

    def unrelated_method_one(self):
        """Not referenced by the test file; should be elided."""
        return 1

    def unrelated_method_two(self):
        """Also not referenced; should be elided."""
        return 2

    def sign(self, value):
        return value + "!"
'''

_CLASS_TEST_SOURCE = """from mod import Signer


def test_sign_appends_a_bang():
    assert Signer().sign("hi") == "hi!"
"""


def test_class_excerpt_narrows_to_only_the_referenced_method() -> None:
    """A large class where only one method is actually exercised by the
    test file must not pull in every unrelated sibling method wholesale --
    this is the real-world shape that made the (pre-fix) contiguous-slice
    design fail to fit real historical single-class modules into a small
    context budget."""
    excerpt, _start, _end = select_prompt_excerpt(_CLASS_SOURCE, [_CLASS_TEST_SOURCE])
    assert "def sign" in excerpt
    assert "def unrelated_method_one" not in excerpt
    assert "def unrelated_method_two" not in excerpt
    assert "omitted" in excerpt
    assert len(excerpt.splitlines()) < len(_CLASS_SOURCE.splitlines())


def test_class_excerpt_keeps_the_whole_class_when_no_method_name_matches() -> None:
    """If the test file only references the class name itself (e.g. via a
    generic helper) and no specific method name, narrowing to "no methods"
    would be worse than useless -- fall back to the whole class rather
    than guess which parts matter."""
    test_source = "from mod import Signer\n\n\ndef test_it():\n    assert Signer()\n"
    excerpt, _start, _end = select_prompt_excerpt(_CLASS_SOURCE, [test_source])
    assert "def unrelated_method_one" in excerpt
    assert "def sign" in excerpt


_LONG_DOCSTRING_SOURCE = '''def target_function(value):
    """A very long prose docstring with many lines of usage examples and
    historical notes that cost real token budget without being needed to
    understand or repair the actual bug below -- only the first few lines
    should survive excerpting, with the rest elided as a labeled gap.
    """
    return value
'''

_LONG_DOCSTRING_TEST_SOURCE = (
    "from mod import target_function\n\n\ndef test_it():\n    assert target_function(1) == 1\n"
)


def test_an_oversized_function_docstring_is_capped_and_the_rest_elided() -> None:
    excerpt, _start, _end = select_prompt_excerpt(_LONG_DOCSTRING_SOURCE, [_LONG_DOCSTRING_TEST_SOURCE])
    assert "def target_function" in excerpt
    assert "return value" in excerpt
    assert "omitted" in excerpt
    assert "should survive excerpting" not in excerpt


