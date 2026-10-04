"""Subprocess-isolated adapter for pinned Hugging Face custom architectures."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from each.hashing import sha256_file
from each.model_manifest import ModelManifest, verify_snapshot_matches
from each.models.base import ContextBudgetExceeded, RepairModel


class TransformersRepairModel(RepairModel):
    """Run an exact local checkpoint through a pinned Transformers runtime."""

    def __init__(
        self,
        snapshot_dir: Path,
        manifest: ModelManifest,
        *,
        max_tokens: int = 512,
        device: str = "mps",
        runtime_project: Path | None = None,
        runtime_files_sha256: dict[str, str] | None = None,
        runtime_versions: dict[str, str] | None = None,
        timeout_seconds: int = 300,
        sandbox_executable: Path = Path("/usr/bin/sandbox-exec"),
    ) -> None:
        if max_tokens < 1:
            raise ValueError("max_tokens must be at least 1")
        if device not in {"mps", "cpu"}:
            raise ValueError("device must be 'mps' or 'cpu'")
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be at least 1")
        self._snapshot_dir = str(snapshot_dir)
        self._manifest = manifest
        self._max_tokens = max_tokens
        self._device = device
        self._runtime_project = runtime_project or (
            Path(__file__).resolve().parents[2] / "runtimes" / "crystal"
        )
        self._runtime_helper = Path(__file__).with_name("crystal_runtime.py")
        runtime_launcher = self._runtime_project / ".venv" / "bin" / "python"
        self._runtime_python = runtime_launcher.resolve()
        site_packages = sorted((self._runtime_project / ".venv" / "lib").glob("python*/site-packages"))
        if len(site_packages) != 1:
            raise RuntimeError("qualified Transformers runtime must have exactly one site-packages directory")
        self._runtime_site_packages = site_packages[0]
        self._runtime_files = {
            "pyproject.toml": self._runtime_project / "pyproject.toml",
            "uv.lock": self._runtime_project / "uv.lock",
            "crystal_runtime.py": self._runtime_helper,
        }
        for required in (*self._runtime_files.values(), runtime_launcher, self._runtime_python):
            if not required.is_file():
                raise RuntimeError(f"qualified Transformers runtime file is missing: {required}")
        self._runtime_files_sha256 = dict(runtime_files_sha256 or {})
        if set(self._runtime_files_sha256) != set(self._runtime_files):
            raise ValueError("runtime_files_sha256 must bind the project, lock and helper")
        self._runtime_versions = dict(runtime_versions or {})
        if set(self._runtime_versions) != {"python", "torch", "transformers"}:
            raise ValueError("runtime_versions must bind Python, Torch and Transformers")
        self._timeout_seconds = timeout_seconds
        self._sandbox_executable = sandbox_executable
        self._temperature = 0.0
        self._seed: int | None = None
        self.last_raw_prompt: str | None = None
        self.last_input_token_count: int | None = None
        self.last_generation_attempted = False
        self.last_isolation_evidence: dict[str, Any] | None = None

    @property
    def model_id(self) -> str:
        return self._manifest.model_id

    @property
    def manifest(self) -> ModelManifest:
        return self._manifest

    def _verify_snapshot(self) -> None:
        snapshot = Path(self._snapshot_dir)
        drift = verify_snapshot_matches(snapshot, self._manifest)
        if drift:
            raise RuntimeError(
                "refusing to load: snapshot directory has drifted from its recorded "
                f"manifest ({'; '.join(drift)})"
            )

    def _verify_runtime(self) -> None:
        drift = [
            f"{name}: hash mismatch"
            for name, path in self._runtime_files.items()
            if sha256_file(path) != self._runtime_files_sha256[name]
        ]
        if drift:
            raise RuntimeError(
                "refusing to run: qualified Transformers runtime has drifted "
                f"({'; '.join(drift)})"
            )

    def configure_sampling(self, *, temperature: float = 0.0, seed: int | None = None) -> None:
        if temperature < 0.0:
            raise ValueError(f"temperature must be >= 0.0, got {temperature}")
        self._temperature = temperature
        self._seed = seed

    def identity(self) -> dict[str, Any]:
        identity = super().identity()
        identity["modelManifest"] = self._manifest.to_dict()
        identity["generationParameters"] = {
            "maxTokens": self._max_tokens,
            "temperature": self._temperature,
            "sampling": "greedy" if self._temperature == 0.0 else "temperature",
            "seed": self._seed,
        }
        identity["contextPolicy"] = {
            "maxPositionEmbeddings": self._manifest.max_position_embeddings,
            "reservedOutputTokens": self._max_tokens,
            "lastInputTokenCount": self.last_input_token_count,
        }
        identity["executionDevice"] = self._device
        identity["runtimeEnvironment"] = {
            "projectSha256": self._runtime_files_sha256["pyproject.toml"],
            "lockSha256": self._runtime_files_sha256["uv.lock"],
            "helperSha256": self._runtime_files_sha256["crystal_runtime.py"],
            "versions": dict(self._runtime_versions),
        }
        identity["isolationEvidence"] = self.last_isolation_evidence
        identity["generationAttempted"] = self.last_generation_attempted
        return identity

    @staticmethod
    def _sandbox_literal(path: Path) -> str:
        return str(path.resolve()).replace("\\", "\\\\").replace('"', '\\"')

    def _sandbox_profile(self, work_dir: Path, denied_probe: Path) -> str:
        home = Path.home()
        sensitive_paths = [
            denied_probe,
            home / ".ssh",
            home / ".aws",
            home / ".gnupg",
            home / ".kube",
            home / ".docker" / "config.json",
            home / ".config" / "gh",
            home / ".netrc",
            home / ".npmrc",
            home / ".pypirc",
            home / ".gitconfig",
            home / ".each" / "runtime.key",
            home / "Library" / "Keychains",
            home / ".each" / "runs",
            home / ".each" / "shadow",
            home / ".each" / "oracle",
            Path(__file__).resolve().parents[2] / ".git",
            Path(__file__).resolve().parents[2] / ".architrave",
            Path(__file__).resolve().parents[2] / "docs",
            Path(__file__).resolve().parents[2] / "tests",
            Path(__file__).resolve().parents[2] / "examples",
        ]
        deny_rules = "\n".join(
            f'(deny file-read* (subpath "{self._sandbox_literal(path)}"))'
            for path in sensitive_paths
        )
        return (
            "(version 1)\n"
            "(allow default)\n"
            "(deny network*)\n"
            "(deny file-write*)\n"
            f'(allow file-write* (subpath "{self._sandbox_literal(work_dir)}"))\n'
            f"{deny_rules}\n"
        )

    def _run_subprocess(
        self,
        command: list[str],
        *,
        prompt: str,
        environment: dict[str, str],
        cwd: Path,
    ) -> tuple[int, str, str]:
        stdout_path = cwd / "stdout.json"
        stderr_path = cwd / "stderr.log"

        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=stdout,
                stderr=stderr,
                cwd=cwd,
                env=environment,
                start_new_session=True,
            )
            assert process.stdin is not None
            process.stdin.write(prompt.encode())
            process.stdin.close()
            deadline = time.monotonic() + self._timeout_seconds
            while process.poll() is None:
                if stdout_path.stat().st_size > 8 * 1024 * 1024 or stderr_path.stat().st_size > 8 * 1024 * 1024:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise RuntimeError("qualified Transformers runtime exceeded its output limit")
                if time.monotonic() >= deadline:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise RuntimeError(
                        f"qualified Transformers runtime exceeded {self._timeout_seconds} seconds"
                    )
                time.sleep(0.05)
            if process.returncode is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise RuntimeError(
                    "qualified Transformers runtime did not report a process result"
                )
        if stdout_path.stat().st_size > 8 * 1024 * 1024 or stderr_path.stat().st_size > 8 * 1024 * 1024:
            raise RuntimeError("qualified Transformers runtime exceeded its output limit")
        return (
            process.returncode,
            stdout_path.read_text(errors="replace"),
            stderr_path.read_text(errors="replace"),
        )

    def complete(self, prompt: str) -> str:
        self.last_raw_prompt = prompt
        self.last_prompt = None
        self.last_input_token_count = None
        self.last_generation_attempted = False
        self.last_isolation_evidence = None
        if len(prompt.encode()) > 32 * 1024:
            raise ContextBudgetExceeded("raw prompt exceeds the 32 KiB subprocess input limit")
        self._verify_snapshot()
        self._verify_runtime()
        if not self._sandbox_executable.is_file():
            raise RuntimeError("qualified Transformers runtime requires /usr/bin/sandbox-exec")
        with tempfile.TemporaryDirectory(prefix="each-crystal-runtime-") as private:
            work_dir = Path(private)
            denied_probe = work_dir.parent / f".{work_dir.name}-denied"
            denied_probe.write_text("private isolation probe", encoding="utf-8")
            denied_paths = [denied_probe]
            for candidate in (
                Path.home() / ".each" / "runtime.key",
                Path.home() / ".ssh" / "known_hosts",
                Path(__file__).resolve().parents[2] / "docs" / "EACH_BOOTSTRAP_MANDATE.md",
            ):
                if candidate.is_file():
                    denied_paths.append(candidate)
            write_probe = work_dir.parent / f".{work_dir.name}-write-denied"
            profile = self._sandbox_profile(work_dir, denied_probe)
            command = [
                str(self._sandbox_executable),
                "-p",
                profile,
                str(self._runtime_python),
                "-I",
                str(self._runtime_helper),
                "--snapshot",
                self._snapshot_dir,
                "--max-tokens",
                str(self._max_tokens),
                "--max-position-embeddings",
                str(self._manifest.max_position_embeddings or 0),
                "--device",
                self._device,
                "--temperature",
                str(self._temperature),
                "--site-packages",
                str(self._runtime_site_packages),
                "--probe-write-path",
                str(write_probe),
                "--stage-path",
                str(work_dir / "stage.json"),
            ]
            for denied_path in denied_paths:
                command.extend(["--probe-denied-path", str(denied_path)])
            if self._seed is not None:
                command.extend(["--seed", str(self._seed)])
            environment = {
                "HOME": str(work_dir),
                "TMPDIR": str(work_dir),
                "XDG_CACHE_HOME": str(work_dir / "cache"),
                "HF_HOME": str(work_dir / "huggingface"),
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_HUB_DISABLE_PROGRESS_BARS": "1",
                "TOKENIZERS_PARALLELISM": "false",
                "PYTHONNOUSERSITE": "1",
                "PATH": "/usr/bin:/bin",
            }
            try:
                returncode, stdout, stderr = self._run_subprocess(
                    command, prompt=prompt, environment=environment, cwd=work_dir,
                )
                stage_path = work_dir / "stage.json"
                if stage_path.is_file():
                    stage = json.loads(stage_path.read_text())
                    self.last_generation_attempted = stage.get("generationAttempted") is True
            finally:
                denied_probe.unlink(missing_ok=True)
                write_probe.unlink(missing_ok=True)
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"qualified Transformers runtime failed without structured output "
                f"(exit {returncode}): {stderr.strip()}"
            ) from exc
        if not isinstance(result, dict) or result.get("schemaVersion") != "1":
            raise RuntimeError("qualified Transformers runtime returned an invalid result schema")
        self.last_input_token_count = result.get("inputTokenCount")
        self.last_generation_attempted = result.get("generationAttempted") is True
        isolation = result.get("isolation")
        if (
            not isinstance(isolation, dict)
            or isolation.get("networkDenied") is not True
            or isolation.get("privateFilesDenied") != len(denied_paths)
            or isolation.get("outsideWriteDenied") is not True
        ):
            raise RuntimeError("qualified Transformers runtime isolation probe did not pass")
        self.last_isolation_evidence = isolation
        runtime = result.get("runtime")
        if runtime != self._runtime_versions:
            raise RuntimeError(
                f"qualified Transformers runtime version mismatch: expected "
                f"{self._runtime_versions}, got {runtime}"
            )
        if result.get("status") == "CONTEXT_BUDGET_EXCEEDED":
            raise ContextBudgetExceeded(str(result["detail"]))
        if returncode != 0 or result.get("status") != "OK":
            raise RuntimeError(
                f"qualified Transformers runtime failed (exit {returncode}): "
                f"{result.get('detail') or stderr.strip()}"
            )
        self._verify_snapshot()
        self._verify_runtime()
        return str(result["completion"])
