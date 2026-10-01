"""Container-based executor.

No network, a scrubbed environment, no host secrets or home-directory
mounts, a dropped capability set, and a bind-mounted worktree at /work.
Uses the `docker` CLI directly against the dedicated `colima-each` context
and a pinned base-image digest (never a mutable tag) so the execution
surface is reproducible.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from each.executor.base import ExecutionResult, Executor

# Resolved, recorded identity of python:3.12-slim at provisioning time (see
# docs/threat-model.md and the M1 milestone report for provenance).
DEFAULT_IMAGE_DIGEST = "python@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f"
DOCKER_CONTEXT = "colima-each"


class ContainerExecutorError(RuntimeError):
    pass


@dataclass(frozen=True)
class ContainerExecutor(Executor):
    image: str = DEFAULT_IMAGE_DIGEST
    docker_context: str = DOCKER_CONTEXT
    network: str = "none"
    memory_limit: str = "512m"
    cpu_limit: str = "2"

    @property
    def assurance_level(self) -> str:
        # EACH-P2 ("Isolated"), not P3: P3 additionally requires executed
        # corpus/source similarity checks and documented model training
        # provenance, neither of which exist yet (the M1 audit step is an
        # explicit UNAVAILABLE stub; see docs/threat-model.md).
        return "EACH-P2"

    def build_docker_command(self, command: list[str], worktree: Path) -> list[str]:
        worktree = worktree.resolve()
        return [
            "docker",
            "--context",
            self.docker_context,
            "run",
            "--rm",
            "--network",
            self.network,
            "--tmpfs",
            "/tmp",
            "--memory",
            self.memory_limit,
            "--cpus",
            self.cpu_limit,
            "--pids-limit",
            "256",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "--env-file",
            "/dev/null",
            "-v",
            f"{worktree}:/work:rw",
            "-w",
            "/work",
            self.image,
            *command,
        ]

    def run(self, command: list[str], worktree: Path, *, timeout: int = 120) -> ExecutionResult:
        docker_cmd = self.build_docker_command(command, worktree)
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ContainerExecutorError(f"container execution timed out after {timeout}s") from exc
        except FileNotFoundError as exc:
            raise ContainerExecutorError("docker CLI not found on host") from exc
        return ExecutionResult(
            command=tuple(command),
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
