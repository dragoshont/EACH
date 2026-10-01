"""Immutable, hash-verified repair-task spec packets.

A spec packet is the single source of truth a repair run is permitted to
act on: the target, the allowed edit scope, the build/acceptance commands,
and the declared forbidden sources. Once approved, the packet is bound to
its content hash; any later mutation is detectable via `ApprovedSpec.verify`.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

from each.hashing import sha256_json

SCHEMA_VERSION = "each.spec/v1"


class SpecIntegrityError(RuntimeError):
    """Raised when a spec packet's recorded hash does not match its content."""


@dataclass(frozen=True)
class SpecPacket:
    task_id: str
    target_repo: str
    target_ref: str
    problem_statement: str
    allowed_paths: tuple[str, ...]
    build_commands: tuple[tuple[str, ...], ...]
    acceptance_commands: tuple[tuple[str, ...], ...]
    forbidden_sources: tuple[str, ...]
    approved_by: str
    approved_at: str
    schema_version: str = SCHEMA_VERSION

    def content(self) -> dict[str, Any]:
        """The hashed payload: everything that defines the task's scope."""
        return asdict(self)

    def sha256(self) -> str:
        return sha256_json(self.content())


@dataclass(frozen=True)
class ApprovedSpec:
    """A spec packet bound to its approval-time content hash."""

    packet: SpecPacket
    approved_hash: str

    @classmethod
    def approve(cls, packet: SpecPacket) -> ApprovedSpec:
        return cls(packet=packet, approved_hash=packet.sha256())

    def verify(self) -> None:
        """Raise SpecIntegrityError if the packet content has drifted since approval."""
        current = self.packet.sha256()
        if current != self.approved_hash:
            raise SpecIntegrityError(
                f"spec hash mismatch: approved={self.approved_hash} current={current}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {"packet": self.packet.content(), "approvedHash": self.approved_hash}


def make_spec_packet(
    *,
    task_id: str,
    target_repo: str,
    target_ref: str,
    problem_statement: str,
    allowed_paths: list[str],
    build_commands: list[list[str]],
    acceptance_commands: list[list[str]],
    forbidden_sources: list[str],
    approved_by: str,
) -> SpecPacket:
    return SpecPacket(
        task_id=task_id,
        target_repo=target_repo,
        target_ref=target_ref,
        problem_statement=problem_statement,
        allowed_paths=tuple(allowed_paths),
        build_commands=tuple(tuple(c) for c in build_commands),
        acceptance_commands=tuple(tuple(c) for c in acceptance_commands),
        forbidden_sources=tuple(forbidden_sources),
        approved_by=approved_by,
        approved_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
