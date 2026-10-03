from __future__ import annotations

from pathlib import Path

import pytest

from each.executor.base import ExecutionResult
from each.executor.container import (
    DEFAULT_IMAGE_DIGEST,
    NETWORK_PROBE_DENIAL_MARKER,
    ContainerExecutor,
    ContainerExecutorError,
    derive_assurance_level,
)
from tests.adversarial._docker_guard import requires_colima_each


def test_rejects_network_enabled_profile() -> None:
    with pytest.raises(ContainerExecutorError, match="network='none'"):
        ContainerExecutor(network="bridge")


def test_rejects_unpinned_mutable_tag_image() -> None:
    with pytest.raises(ContainerExecutorError, match="pinned by digest"):
        ContainerExecutor(image="python:latest")


def test_accepts_default_pinned_no_network_config() -> None:
    executor = ContainerExecutor()
    assert executor.image == DEFAULT_IMAGE_DIGEST
    assert executor.network == "none"


def test_strong_profile_uses_read_only_root_filesystem(tmp_path: Path) -> None:
    executor = ContainerExecutor()
    command = executor.build_docker_command(["python", "--version"], tmp_path, container_name="probe")
    assert "--read-only" in command
    assert executor.identity()["readOnlyRootFilesystem"] is True


def test_derive_assurance_level_is_p2_when_probe_actually_denied() -> None:
    executor = ContainerExecutor()
    denied = ExecutionResult(
        command=("python", "-c", "probe"),
        exit_code=1,
        stdout=f"{NETWORK_PROBE_DENIAL_MARKER}\n",
        stderr="",
    )
    assert derive_assurance_level(executor, denied) == "EACH-P2"


def test_derive_assurance_level_downgrades_when_probe_did_not_deny() -> None:
    executor = ContainerExecutor()
    reached = ExecutionResult(command=("python", "-c", "probe"), exit_code=0, stdout="", stderr="")
    assert derive_assurance_level(executor, reached) == "EACH-P1"


def test_derive_assurance_level_downgrades_on_unexpected_probe_output() -> None:
    executor = ContainerExecutor()
    weird = ExecutionResult(command=("python", "-c", "probe"), exit_code=1, stdout="", stderr="oops")
    assert derive_assurance_level(executor, weird) == "EACH-P1"


@pytest.mark.parametrize(
    ("exit_code", "stdout"),
    [
        (2, "network probe errno: None\n"),
        (2, "network probe errno: 111\n"),
        (1, "connection denied as expected: timed out\n"),
        (1, "connection denied as expected: [Errno 111] Connection refused\n"),
        (2, f"{NETWORK_PROBE_DENIAL_MARKER}\n"),
    ],
)
def test_ambiguous_socket_failures_do_not_verify_isolation(exit_code: int, stdout: str) -> None:
    result = ExecutionResult(
        command=("python", "-I", "-c", "probe"), exit_code=exit_code, stdout=stdout, stderr=""
    )
    assert derive_assurance_level(ContainerExecutor(), result) == "EACH-P1"


def test_protected_paths_are_mounted_read_only_over_the_writable_worktree(tmp_path: Path) -> None:
    """F4: the harness's own validation scaffold files must be re-mounted
    individually read-only, not merely trusted to remain unmodified because
    a post-execution hash check happens to run afterwards."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x(): pass\n")
    executor = ContainerExecutor()
    command = executor.build_docker_command(
        ["pytest", "tests/test_x.py"],
        tmp_path,
        container_name="probe",
        protected_paths=("tests/test_x.py",),
    )
    expected_host = str((tmp_path / "tests" / "test_x.py").resolve())
    assert f"{expected_host}:/work/tests/test_x.py:ro" in command
    # The protected mount is additive, on top of (not instead of) the
    # writable worktree mount the candidate's OWN editable file still
    # needs.
    assert f"{tmp_path.resolve()}:/work:rw" in command


def test_protected_paths_reject_traversal(tmp_path: Path) -> None:
    executor = ContainerExecutor()
    with pytest.raises(ContainerExecutorError, match="traversal"):
        executor.build_docker_command(
            ["pytest"], tmp_path, container_name="probe", protected_paths=("../outside.py",)
        )


def test_protected_paths_reject_absolute_path(tmp_path: Path) -> None:
    executor = ContainerExecutor()
    with pytest.raises(ContainerExecutorError, match="traversal"):
        executor.build_docker_command(
            ["pytest"], tmp_path, container_name="probe", protected_paths=("/etc/passwd",)
        )


@requires_colima_each
def test_protected_paths_are_actually_read_only_inside_the_real_container(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    protected = tmp_path / "tests" / "test_x.py"
    protected.write_text("original\n", encoding="utf-8")

    executor = ContainerExecutor()
    result = executor.run(
        ["sh", "-c", "echo changed > tests/test_x.py"],
        tmp_path,
        protected_paths=("tests/test_x.py",),
    )

    assert result.exit_code != 0
    assert protected.read_text(encoding="utf-8") == "original\n"
