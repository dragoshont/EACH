"""Acceptance tests for EACH's M7 clean-room-style ``lru_cache_clean_room``
demonstration target.

Every assertion here traces directly to one of the 9 numbered, black-box
OBSERVED behaviors in the approved spec
(``~/.each/specs/each-m7-clean-room-lru-cache/approved.json``), not to
``functools.lru_cache``'s own implementation source (never opened while
writing this spec or these tests). This file is public, source-free, and
written before any Builder attempt -- it is the acceptance bar a candidate
implementation must clear, derived only from approved, previously-recorded
observations.
"""

from __future__ import annotations

import unittest

from clean_room_lru_cache import lru_cache_clean_room


class TestLruCacheCleanRoom(unittest.TestCase):
    def test_spec_item_1_second_call_is_a_cache_hit_not_a_recompute(self) -> None:
        calls = []

        @lru_cache_clean_room()
        def counted(x):
            calls.append(x)
            return x * 2

        self.assertEqual(counted(3), 6)
        self.assertEqual(counted(3), 6)
        self.assertEqual(len(calls), 1)

    def test_spec_item_2_cache_info_has_four_ordered_attributes(self) -> None:
        @lru_cache_clean_room(maxsize=4)
        def f(x):
            return x

        f(1)
        f(1)
        f(2)
        info = f.cache_info()
        self.assertEqual((info.hits, info.misses, info.maxsize, info.currsize), (1, 2, 4, 2))

    def test_spec_item_3_cache_clear_resets_everything(self) -> None:
        @lru_cache_clean_room()
        def f(x):
            return x

        f(1)
        f(1)
        f.cache_clear()
        info = f.cache_info()
        self.assertEqual((info.hits, info.misses, info.currsize), (0, 0, 0))

    def test_spec_item_4_bounded_maxsize_evicts_least_recently_used(self) -> None:
        calls = []

        @lru_cache_clean_room(maxsize=2)
        def f(x):
            calls.append(x)
            return x

        f(1)
        f(2)
        f(3)  # evicts 1 (least recently used), currsize stays at 2
        self.assertEqual(f.cache_info().currsize, 2)
        f(1)  # must be a genuine recompute (fresh miss), not a cache hit
        self.assertEqual(calls, [1, 2, 3, 1])

    def test_spec_item_5_unbounded_maxsize_none_never_evicts(self) -> None:
        @lru_cache_clean_room(maxsize=None)
        def f(x):
            return x

        for value in range(5):
            f(value)
        info = f.cache_info()
        self.assertEqual(info.currsize, 5)
        self.assertIsNone(info.maxsize)

    def test_spec_item_6_typed_false_still_distinguishes_int_and_float(self) -> None:
        results = []

        @lru_cache_clean_room()
        def f(x):
            results.append(type(x).__name__)
            return x

        f(3)
        f(3.0)
        self.assertEqual(f.cache_info().currsize, 2)
        self.assertEqual(results, ["int", "float"])

    def test_spec_item_7_positional_vs_keyword_are_different_cache_keys(self) -> None:
        @lru_cache_clean_room()
        def k(x, y=1):
            return x + y

        k(1)
        k(1, y=1)
        self.assertEqual(k.cache_info().currsize, 2)

    def test_spec_item_8_unhashable_argument_raises_type_error(self) -> None:
        @lru_cache_clean_room()
        def f(x):
            return x

        with self.assertRaises(TypeError):
            f([1, 2, 3])

    def test_spec_item_9_wrapped_name_and_doc_are_preserved(self) -> None:
        @lru_cache_clean_room()
        def documented(x):
            """A docstring."""
            return x

        self.assertTrue(callable(documented.__wrapped__))
        self.assertEqual(documented.__wrapped__.__name__, "documented")
        self.assertEqual(documented.__name__, "documented")
        self.assertEqual(documented.__doc__, "A docstring.")
        # __wrapped__ must be the real undecorated function, not the
        # decorated wrapper itself.
        self.assertIsNot(documented.__wrapped__, documented)


if __name__ == "__main__":
    unittest.main()
