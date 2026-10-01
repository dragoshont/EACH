from __future__ import annotations

import pytest

from each.executor.base import ExecutionResult
from each.executor.container import (
    DEFAULT_IMAGE_DIGEST,
    ContainerExecutor,
    ContainerExecutorError,
    derive_assurance_level,
)


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


def test_derive_assurance_level_is_p2_when_probe_actually_denied() -> None:
    executor = ContainerExecutor()
    denied = ExecutionResult(
        command=("python", "-c", "probe"),
        exit_code=1,
        stdout="connection denied as expected: [Errno 101] Network is unreachable\n",
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
