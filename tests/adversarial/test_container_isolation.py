"""Real (non-mocked) adversarial evidence for the M1 no-network container
executor: outbound network denial and host-secret non-inheritance.

These tests invoke the actual ``docker --context colima-each`` CLI against
a running container. They self-skip (not silently pass) when Docker or the
dedicated ``colima-each`` context is unreachable, e.g. on a CI runner
without Colima -- consistent with ``each doctor``'s optional-check model.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from each.executor.container import ContainerExecutor
from each.paths import worktrees_dir
from tests.adversarial._docker_guard import requires_colima_each


def _empty_worktree() -> Path:
    return Path(tempfile.mkdtemp(prefix="each-adversarial-", dir=worktrees_dir()))


@requires_colima_each
def test_real_outbound_network_connection_is_denied() -> None:
    """A genuine socket connection attempt from inside the executor must fail.

    This is a real probe (no mocking of subprocess/docker): it actually
    launches a container with ``--network none`` and attempts to reach
    1.1.1.1:443 from inside it.
    """
    executor = ContainerExecutor()
    probe = (
        "import socket, sys\n"
        "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "s.settimeout(5)\n"
        "try:\n"
        "    s.connect(('1.1.1.1', 443))\n"
        "    sys.exit(0)\n"
        "except OSError as exc:\n"
        "    print(f'connection denied as expected: {exc}')\n"
        "    sys.exit(1)\n"
    )
    result = executor.run(["python", "-c", probe], _empty_worktree(), timeout=30)
    assert result.exit_code == 1, (
        "expected outbound connection to 1.1.1.1:443 to be denied by the "
        f"--network none executor; got exit={result.exit_code} "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "connection denied as expected" in result.stdout


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
