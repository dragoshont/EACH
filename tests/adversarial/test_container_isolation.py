"""Real (non-mocked) adversarial evidence for the M1 no-network container
executor: outbound network denial, host-secret non-inheritance, and
explicit cleanup of a container that outlives its host-side timeout.

These tests invoke the actual ``docker --context colima-each`` CLI against
a running container. They self-skip (not silently pass) when Docker or the
dedicated ``colima-each`` context is unreachable, e.g. on a CI runner
without Colima -- consistent with ``each doctor``'s optional-check model.
"""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from pathlib import Path

from each.executor.container import (
    NETWORK_PROBE_DENIAL_MARKER,
    NETWORK_PROBE_SCRIPT,
    ContainerExecutor,
    ContainerExecutorError,
)
from each.paths import worktrees_dir
from tests.adversarial._docker_guard import requires_colima_each


def _empty_worktree() -> Path:
    return Path(tempfile.mkdtemp(prefix="each-adversarial-", dir=worktrees_dir()))


@requires_colima_each
def test_real_outbound_network_connection_is_denied() -> None:
    """A genuine socket connection attempt from inside the executor must fail.

    This is a real probe (no mocking of subprocess/docker): it actually
    launches a container with ``--network none`` and attempts to reach
    1.1.1.1:443 from inside it. Uses the exact same probe script the
    production code binds into every receipt's isolation evidence
    (`each.executor.container.NETWORK_PROBE_SCRIPT`), so this test and the
    production evidence can never silently diverge.
    """
    executor = ContainerExecutor()
    result = executor.run(["python", "-c", NETWORK_PROBE_SCRIPT], _empty_worktree(), timeout=30)
    assert result.exit_code == 1, (
        "expected outbound connection to 1.1.1.1:443 to be denied by the "
        f"--network none executor; got exit={result.exit_code} "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert NETWORK_PROBE_DENIAL_MARKER in result.stdout


@requires_colima_each
def test_host_secret_env_vars_are_not_inherited(monkeypatch) -> None:
    """A secret set in the host process environment must not reach the container."""
    monkeypatch.setenv("EACH_TEST_SECRET_TOKEN", "should-never-be-visible-in-container")
    executor = ContainerExecutor()
    result = executor.run(
        ["python", "-c", "import os; print(repr(os.environ.get('EACH_TEST_SECRET_TOKEN')))"],
        _empty_worktree(),
        timeout=30,
    )
    assert result.exit_code == 0
    assert "should-never-be-visible-in-container" not in result.stdout
    assert "None" in result.stdout


def _container_exists(executor: ContainerExecutor, name: str) -> bool:
    proc = subprocess.run(
        ["docker", "--context", executor.docker_context, "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return name in proc.stdout.split()


@requires_colima_each
def test_timed_out_container_is_actually_stopped_and_removed() -> None:
    """A real sleeping container that outlives its host-side timeout must be
    explicitly stopped/removed, not merely abandoned.

    `--rm` only removes a container when its own process exits; killing the
    local `docker run` client on a Python-side timeout does not stop a
    daemon-managed container. This exercises the genuine failure mode (no
    mocking of subprocess or docker) and asserts the executor's explicit
    cleanup actually removed the named container.
    """
    executor = ContainerExecutor()
    container_name = f"each-test-timeout-{uuid.uuid4().hex}"
    try:
        executor.run(
            ["sleep", "30"],
            _empty_worktree(),
            timeout=2,
            container_name=container_name,
        )
        raise AssertionError("expected ContainerExecutorError on timeout")
    except ContainerExecutorError as exc:
        assert "timed out" in str(exc)

    assert not _container_exists(executor, container_name), (
        f"container {container_name} was still present after executor cleanup"
    )

