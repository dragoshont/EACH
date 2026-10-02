"""Pluggable training-corpus membership adapters (M4).

A real large-scale training-corpus membership service is out of scope for
v0.1 (no such service is wired up; EACH ships no model's training data).
The adapter interface exists so one can be plugged in later without
changing any check-calling code. The default adapter honestly reports
``UNAVAILABLE`` rather than fabricating a PASS.
"""

from __future__ import annotations

from typing import Protocol

from each.audit.checks import CheckResult, normalize_text
from each.hashing import sha256_text


class CorpusMembershipAdapter(Protocol):
    def check(self, candidate: str) -> CheckResult: ...


class NullCorpusAdapter:
    """Default adapter: no training-corpus membership service is configured."""

    def check(self, candidate: str) -> CheckResult:
        return CheckResult(status="UNAVAILABLE", detail="no training-corpus membership adapter configured")


class InMemoryCorpusAdapter:
    """A small, explicit, locally-declared "known member" set.

    This is a demonstration/test adapter, not a real training-corpus
    membership service — it proves the interface is pluggable and
    exercisable, not that EACH can answer "was this in some model's
    training data" in general.
    """

    def __init__(self, members: list[str]) -> None:
        self._normalized_members = [normalize_text(m) for m in members]

    def check(self, candidate: str) -> CheckResult:
        if not self._normalized_members:
            return CheckResult(status="UNAVAILABLE", detail="in-memory corpus-membership adapter has no members")
        normalized_candidate = normalize_text(candidate)
        for index, member in enumerate(self._normalized_members):
            if member and (member in normalized_candidate or normalized_candidate in member):
                return CheckResult(
                    status="FAIL",
                    detail="candidate matches a declared corpus-membership entry",
                    evidence={"memberIndex": index, "memberSha256": sha256_text(member)},
                )
        return CheckResult(status="PASS", detail="no declared corpus-membership entry matched")
