"""M7 clean-room-style demonstration target: a from-scratch stand-in for
``functools.lru_cache``, built only from a black-box-observed spec (see
``docs/EACH_BOOTSTRAP_MANDATE.md`` M7 evidence and the private spec packet).

This stub deliberately raises ``NotImplementedError`` -- it is the baseline
EACH's Builder patches, not a hand-written reference implementation. No
EACH-authored (human or model) implementation code belongs in this file
before a sealed Builder run produces one; this file's only job is to define
the required public surface and guarantee the acceptance tests genuinely
fail before a patch is applied.
"""

from __future__ import annotations


def lru_cache_clean_room(maxsize: int | None = 128, typed: bool = False):
    """See the approved EACH M7 spec for the complete required behavior."""
    raise NotImplementedError("lru_cache_clean_room: not yet implemented (EACH M7 Builder target)")
