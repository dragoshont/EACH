"""Container-based executor.

No network, a scrubbed environment, no host secrets or home-directory
mounts, a dropped capability set, and a bind-mounted worktree at /work.
Uses the `docker` CLI directly against the dedicated `colima-each` context
and a pinned base-image digest (never a mutable tag) so the execution
surface is reproducible.

This executor only supports the no-network, pinned-digest "strong
isolation" profile: a network-enabled or unpinned (mutable-tag) image is
rejected at construction time rather than silently claimed as isolated.
"""

from __future__ import annotations

import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from each.executor.base import ExecutionResult, Executor

# Resolved, recorded identity of python:3.12-slim at provisioning time (see
# docs/threat-model.md and the M1 milestone report for provenance).
DEFAULT_IMAGE_DIGEST = "python@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f"
DOCKER_CONTEXT = "colima-each"

# A pinned OCI reference: "<name>@sha256:<64 hex>", never a mutable tag.
_PINNED_IMAGE_PATTERN = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")

# Shared with tests/adversarial/test_container_isolation.py so the production
# isolation-probe evidence and the adversarial-test evidence are provably the
# same probe, not two diverging copies.
NETWORK_PROBE_SCRIPT = (
    "import errno, socket, sys\n"
    "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
    "s.settimeout(5)\n"
    "try:\n"
    "    s.connect(('1.1.1.1', 443))\n"
    "    sys.exit(0)\n"
    "except OSError as exc:\n"
    "    print(f'network probe errno: {exc.errno}')\n"
    "    sys.exit(1 if exc.errno == errno.ENETUNREACH else 2)\n"
)
NETWORK_PROBE_DENIAL_MARKER = "network probe errno: 101"


class ContainerExecutorError(RuntimeError):
    pass


@dataclass(frozen=True)
class ContainerExecutor(Executor):
    image: str = DEFAULT_IMAGE_DIGEST
    docker_context: str = DOCKER_CONTEXT
    network: str = "none"
    memory_limit: str = "512m"
    cpu_limit: str = "2"

    def __post_init__(self) -> None:
        # This class claims to provide no-network, reproducible-image
        # isolation; a config that cannot back that claim must be rejected
        # outright rather than silently reported as isolated.
        if self.network != "none":
            raise ContainerExecutorError(
                f"ContainerExecutor only supports network='none' (strong isolation); got {self.network!r}"
            )
        if not _PINNED_IMAGE_PATTERN.match(self.image):
            raise ContainerExecutorError(
                f"ContainerExecutor requires an image pinned by digest (name@sha256:...); got {self.image!r}"
            )

    def identity(self) -> dict[str, str | bool]:
        """Executor/environment identity recorded in every receipt."""
        return {
            "executor": "container",
            "dockerContext": self.docker_context,
            "image": self.image,
            "network": self.network,
            "readOnlyRootFilesystem": True,
            "memoryLimit": self.memory_limit,
            "cpuLimit": self.cpu_limit,
        }

    @property
    def assurance_level(self) -> str:
        # This property reflects only the *configuration*, not verified
        # per-run isolation evidence; honest receipts must additionally call
        # `derive_assurance_level` against this run's actual probe result
        # (see each/demo.py) rather than trusting this label alone.
        return "EACH-P2-configured"

    def build_docker_command(self, command: list[str], worktree: Path, *, container_name: str) -> list[str]:
        worktree = worktree.resolve()
        return [
            "docker",
            "--context",
            self.docker_context,
            "run",
            "--rm",
            "--read-only",
            "--name",
            container_name,
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

    def _cleanup_container(self, container_name: str) -> str | None:
        """Explicitly stop+remove the exact container this call started.

        `--rm` only triggers self-removal when the container's own process
        exits; a host-side `subprocess` timeout kills only the local
        `docker run` client, leaving the daemon-managed container running.
        Returns an error string if cleanup itself failed, else None. Never
        touches any container other than the one named here.
        """
        try:
            proc = subprocess.run(
                ["docker", "--context", self.docker_context, "rm", "--force", container_name],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return str(exc)
        if proc.returncode != 0 and "No such container" not in proc.stderr:
            return proc.stderr.strip()
        return None

    def run(
        self, command: list[str], worktree: Path, *, timeout: int = 120, container_name: str | None = None
    ) -> ExecutionResult:
        container_name = container_name or f"each-exec-{uuid.uuid4().hex}"
        docker_cmd = self.build_docker_command(command, worktree, container_name=container_name)
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            cleanup_error = self._cleanup_container(container_name)
            message = f"container execution timed out after {timeout}s (container {container_name})"
            if cleanup_error:
                message += f"; cleanup also failed: {cleanup_error}"
            raise ContainerExecutorError(message) from exc
        except FileNotFoundError as exc:
            raise ContainerExecutorError("docker CLI not found on host") from exc
        except BaseException:
            # The container may still be running after any other
            # unexpected failure (e.g. a signal); clean up before
            # propagating so a crashed harness never leaks a container.
            self._cleanup_container(container_name)
            raise
        return ExecutionResult(
            command=tuple(command),
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    def verify_isolation(self, worktree: Path, *, timeout: int = 30) -> ExecutionResult:
        """Run the real network-denial probe through this exact executor config.

        Evidence returned here is bound to this run's actual
        docker_context/image/network, not a historical or separately-run
        adversarial test pass.
        """
        return self.run(["python", "-I", "-c", NETWORK_PROBE_SCRIPT], worktree, timeout=timeout)


def derive_assurance_level(executor: ContainerExecutor, isolation_result: ExecutionResult) -> str:
    """Compute the honest assurance label for one run from its own evidence.

    EACH-P2 ("Isolated") is only claimed when this run's own isolation probe
    actually observed a denied outbound connection under this executor's
    exact configuration. Any other outcome (probe succeeded in reaching the
    network, or produced an unexpected result) downgrades to EACH-P1
    ("Recorded"): model/provider identified and trajectory recorded, but
    isolation is not verified for this run.
    """
    probe_denied = (
        isolation_result.exit_code == 1
        and isolation_result.stdout.strip() == NETWORK_PROBE_DENIAL_MARKER
    )
    if executor.network == "none" and _PINNED_IMAGE_PATTERN.match(executor.image) and probe_denied:
        return "EACH-P2"
    return "EACH-P1"
