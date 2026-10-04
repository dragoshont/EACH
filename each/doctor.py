"""``each doctor``: report environment health without hiding missing pieces.

Every check is explicit. Required checks that fail make ``each doctor`` exit
non-zero. Optional checks (needed only for later milestones, such as a
container runtime for the strong executor or a local model backend) are
reported as ``WARN`` and do not fail the command. This lets CI and a fresh
clone pass M0 acceptance even before Docker/Colima or a local model are
provisioned.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from each.paths import each_home

MIN_PYTHON = (3, 12)


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # "OK" | "WARN" | "FAIL"
    detail: str
    required: bool


def _check_python() -> Check:
    version = sys.version_info[:2]
    if version >= MIN_PYTHON:
        return Check("python", "OK", f"Python {platform.python_version()}", required=True)
    return Check(
        "python",
        "FAIL",
        f"Python {platform.python_version()} < required {'.'.join(map(str, MIN_PYTHON))}",
        required=True,
    )


def _check_tool(name: str, *, required: bool, version_args: tuple[str, ...] = ("--version",)) -> Check:
    path = shutil.which(name)
    if path is None:
        status = "FAIL" if required else "WARN"
        return Check(name, status, f"{name} not found on PATH", required=required)
    try:
        result = subprocess.run(
            [path, *version_args], capture_output=True, text=True, timeout=5, check=False
        )
        version_line = (result.stdout or result.stderr).strip().splitlines()[0] if (result.stdout or result.stderr) else "present"
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - defensive, tool-dependent
        version_line = f"present ({exc})"
    return Check(name, "OK", version_line, required=required)


def _check_docker_context() -> Check:
    path = shutil.which("docker")
    if path is None:
        return Check("docker", "WARN", "docker CLI not found (needed for the M1 strong executor)", required=False)
    try:
        result = subprocess.run(
            [path, "--context", "colima-each", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
        return Check("docker:colima-each", "WARN", f"could not query colima-each context: {exc}", required=False)
    if result.returncode == 0 and result.stdout.strip():
        return Check(
            "docker:colima-each",
            "OK",
            f"colima-each daemon reachable (server {result.stdout.strip()})",
            required=False,
        )
    return Check(
        "docker:colima-each",
        "WARN",
        "colima-each context not reachable yet (needed for the M1 strong executor)",
        required=False,
    )


def _check_each_home() -> Check:
    try:
        home = each_home()
        probe = home / ".doctor-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return Check("each-home", "FAIL", f"{Path.home() / '.each'} not writable: {exc}", required=True)
    return Check("each-home", "OK", f"private store writable at {home}", required=True)


def _check_platform() -> Check:
    machine = platform.machine()
    system = platform.system()
    detail = f"{system}/{machine}"
    if system == "Darwin" and machine == "arm64":
        detail += " (Apple Silicon)"
    return Check("platform", "OK", detail, required=False)


def run_checks() -> list[Check]:
    return [
        _check_python(),
        _check_platform(),
        _check_tool("git", required=True),
        _check_tool("uv", required=False),
        _check_docker_context(),
        _check_each_home(),
    ]


def doctor_passed(checks: list[Check]) -> bool:
    return all(check.status != "FAIL" for check in checks if check.required)
