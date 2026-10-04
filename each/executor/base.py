"""Executor interface: run a command against a worktree under an isolation
policy, returning a structured, deterministic result.

Raw model- or target-controlled output is never trusted directly; only the
structured result of a command actually executed under the declared
isolation policy is recorded in a receipt.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExecutionResult:
    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str


class Executor(ABC):
    @property
    @abstractmethod
    def assurance_level(self) -> str:
        """e.g. EACH-P1 (native) ... EACH-P3 (sandboxed container, no network)."""

    @abstractmethod
    def run(self, command: list[str], worktree: Path, *, timeout: int = 120) -> ExecutionResult: ...
