"""Shared guard for adversarial tests that need a real `docker --context
colima-each` daemon. Tests are skipped (not silently passed) when the
dedicated profile isn't reachable in this environment.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest


def colima_each_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        proc = subprocess.run(
            ["docker", "--context", "colima-each", "info"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


requires_colima_each = pytest.mark.skipif(
    not colima_each_available(),
    reason="docker --context colima-each not reachable in this environment",
)
