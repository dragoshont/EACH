#!/usr/bin/env python3
"""Architrave durable Run v2 runtime.

The runtime deliberately uses only the Python standard library. Repository-local
JSON is canonical state; JSONL is a hash-chained audit log. Human-readable run
artifacts are projections and never drive state transitions.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from types import TracebackType
from typing import Any, Self

ZERO_HASH = "0" * 64
SCHEMA = "architrave.run.v2"
RUN_STATUSES = {
    "CREATED",
    "PLANNING",
    "RUNNING",
    "WAITING_EXTERNAL",
    "WAITING_RESOURCE",
    "WAITING_WORKER",
    "PAUSED",
    "RECOVERING",
    "VERIFYING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
}
TASK_STATUSES = {
    "NOT_READY",
    "READY",
    "RUNNING",
    "WAITING_EXTERNAL",
    "WAITING_RESOURCE",
    "COMPLETED",
    "FAILED",
    "SKIPPED",
    "CANCELLED",
}
TERMINAL_TASK_STATUSES = {"COMPLETED", "FAILED", "SKIPPED", "CANCELLED"}
CRITERION_STATUSES = {"UNTESTED", "PASS", "FAIL", "BLOCKED_EXTERNAL", "NOT_APPLICABLE"}
RISK_CLASSES = {"R0", "R1", "R2", "R3", "R4"}
EXTERNAL_TYPES = {
    "AUTH_REQUIRED",
    "MFA_REQUIRED",
    "CONSENT_REQUIRED",
    "SAFE_WRITE_TARGET_REQUIRED",
    "SIGNING_REQUIRED",
    "HUMAN_JUDGMENT_REQUIRED",
}
EVENT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_.-]+$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SENSITIVE_KEY_RE = re.compile(
    r"(?:authorization|cookie|password|passwd|secret|token|api[_-]?key|private[_-]?key|session)",
    re.IGNORECASE,
)
SENSITIVE_VALUE_RES = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"\b(?:gh[pousr]_|github_pat_|sk-|cfut_)[A-Za-z0-9._-]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
ARTIFACT_PRODUCERS = {
    "coordinator",
    "deterministic",
    "invariant",
    "workspace",
    "worker",
    "legibility",
    "mutation",
    "reconciliation",
    "semantic-judge",
    "security-review",
    "policy-engine",
    "external-proof",
    "target-repair",
    "target-experiment",
}
GATE_EVIDENCE_PRODUCERS = {
    "deterministic": {"deterministic", "invariant"},
    "e2e": {"legibility"},
    "reality": {"legibility", "mutation", "external-proof", "target-repair", "target-experiment"},
    "semantic": {"semantic-judge"},
    "policy": {"policy-engine"},
    "security": {"security-review"},
}
PRODUCER_ARTIFACT_KINDS = {
    "deterministic": {"deterministic-result"},
    "invariant": {"invariant-result"},
    "workspace": {"candidate-patch", "workspace-status"},
    "worker": {"worker-result"},
    "mutation": {"mutation-receipt"},
    "reconciliation": {"reconciliation-receipt"},
    "semantic-judge": {"semantic-verdict"},
    "security-review": {"security-verdict"},
    "policy-engine": {"policy-decision"},
    "external-proof": {"external-proof"},
    "target-repair": {"target-repair-receipt", "clean-room-experiment-receipt", "target-replay-receipt"},
    "target-experiment": {"target-experiment-receipt"},
}
TARGET_EVIDENCE_KINDS = {
    "target-repair-receipt",
    "clean-room-experiment-receipt",
    "target-replay-receipt",
    "target-experiment-receipt",
}
TARGET_EVIDENCE_PURPOSES = {
    "target-repair-receipt": "target-repair-verified",
    "clean-room-experiment-receipt": "clean-room-experiment-complete",
    "target-replay-receipt": "replay-validation",
    "target-experiment-receipt": "target-experiment-complete",
}
# Acceptance criteria declare a `verificationType`; this reconciles it with which gate `type`s
# may legitimately satisfy it (e2e and reality are treated as mutually satisfying, mirroring the
# "e2e-or-reality" bucket already used by DEFAULT_RISK_GATES) so a criterion cannot be marked PASS
# on the strength of a gate that never ran the kind of verification it claims.
CRITERION_GATE_TYPES = {
    "deterministic": {"deterministic"},
    "e2e": {"e2e", "reality"},
    "reality": {"e2e", "reality"},
    "semantic": {"semantic"},
}
# A reality/e2e criterion must own the exact product surface it verifies so a gate can never
# borrow one surface's evidence to satisfy a different surface's criterion. "deployment" and
# "runtime" cover the non-legibility reality producers (mutation, external-proof) below.
SURFACE_VALUES = {"web", "electron", "ios", "deployment", "runtime"}
SURFACE_VERIFICATION_TYPES = {"reality", "e2e"}


def outcome_class(outcome: object) -> str:
    return str(outcome).split(":", 1)[0].strip()


def verdict_status_allows_pass(status: object) -> bool:
    return str(status).upper() in {"PASS", "APPROVED"}


def sanitize_seed_provenance_summary(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    ancestry = value.get("ancestry")
    ancestry_depth = len(ancestry) if isinstance(ancestry, list) else 0
    sanitized: dict[str, Any] = {
        key: value.get(key)
        for key in (
            "type",
            "seedSha256",
            "sourceRunId",
            "sourceAttempt",
            "sourceReceiptSha256",
            "sourceSpecHash",
            "sourceOutcome",
            "sourcePatchHash",
            "sourceTrajectoryHash",
            "sourceAuditSubjectSha256",
        )
        if value.get(key) not in (None, "")
    }
    if isinstance(value.get("sourceModel"), dict):
        model = value["sourceModel"]
        sanitized["sourceModel"] = {
            "modelId": model.get("modelId"),
            "adapterClassPath": model.get("adapterClassPath"),
        }
    sanitized["ancestryDepth"] = ancestry_depth
    return sanitized


def normalize_target_evidence(
    value: object,
    *,
    criterion_id: str,
    verification_type: str,
    surface: str | None,
) -> dict[str, str] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, dict):
        raise RuntimeFailure("INVALID_CRITERION", f"criterion {criterion_id} targetEvidence must be an object")
    kind = str(value.get("kind") or "").strip()
    purpose = str(value.get("purpose") or "").strip()
    target_spec_hash = str(value.get("targetSpecHash") or "").strip()
    if kind not in TARGET_EVIDENCE_KINDS:
        raise RuntimeFailure("INVALID_CRITERION", f"criterion {criterion_id} has invalid targetEvidence kind")
    if verification_type not in SURFACE_VERIFICATION_TYPES or surface != "runtime":
        raise RuntimeFailure(
            "INVALID_CRITERION",
            f"criterion {criterion_id} targetEvidence requires a runtime reality/e2e criterion",
        )
    if not purpose or not target_spec_hash:
        raise RuntimeFailure(
            "INVALID_CRITERION",
            f"criterion {criterion_id} targetEvidence must declare both purpose and targetSpecHash",
        )
    if not re.fullmatch(r"[0-9a-f]{64}", target_spec_hash):
        raise RuntimeFailure(
            "INVALID_CRITERION",
            f"criterion {criterion_id} targetEvidence targetSpecHash must be 64 lowercase hex characters",
        )
    expected_purpose = TARGET_EVIDENCE_PURPOSES[kind]
    if purpose != expected_purpose:
        raise RuntimeFailure(
            "INVALID_CRITERION",
            f"criterion {criterion_id} targetEvidence purpose must be {expected_purpose!r} for kind {kind!r}",
        )
    return {"kind": kind, "purpose": purpose, "targetSpecHash": target_spec_hash}


class RuntimeFailure(Exception):
    """A bounded runtime error suitable for structured CLI output."""

    def __init__(self, code: str, message: str, *, details: Any = None, exit_code: int = 1):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.exit_code = exit_code


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def redact(value: Any, key: str = "") -> Any:
    if key and SENSITIVE_KEY_RE.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): redact(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        redacted = value
        for pattern in SENSITIVE_VALUE_RES:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted
    return value


def require_id(value: str, label: str) -> str:
    if not ID_RE.fullmatch(value):
        raise RuntimeFailure("INVALID_ID", f"{label} must match {ID_RE.pattern}")
    return value


def safe_relative_path(value: str, label: str = "path") -> str:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise RuntimeFailure("PATH_ESCAPE", f"{label} must be a non-escaping repository-relative path")
    normalized = path.as_posix()
    if normalized in {".", ""}:
        raise RuntimeFailure("PATH_ESCAPE", f"{label} must identify a path below the repository root")
    return normalized


def run_command(args: Sequence[str], cwd: Path) -> str:
    try:
        completed = subprocess.run(
            list(args),
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeFailure("REPOSITORY_IDENTITY", f"failed to inspect repository: {' '.join(args)}") from exc
    return completed.stdout.strip()


class FileLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle: Any = None

    def __enter__(self) -> Self:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        if self.handle.tell() == 0:
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self.handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.handle is None:
            return
        self.handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()


class RunStore:
    def __init__(self, repository: Path | str):
        self.repository = Path(repository).resolve()
        self.runs_root = self.repository / ".architrave" / "runs"
        self.key_path = self.repository / ".architrave" / "runtime.key"

    def _runtime_key(self, *, create: bool = False) -> bytes:
        if create and not self.key_path.exists():
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                descriptor = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(secrets.token_bytes(32))
                    handle.flush()
                    os.fsync(handle.fileno())
        try:
            key_stat = self.key_path.lstat()
            if not stat.S_ISREG(key_stat.st_mode) or self.key_path.is_symlink():
                raise RuntimeFailure("RUNTIME_KEY_INVALID", "durable Run authentication key must be a regular file")
            if os.name != "nt" and ((key_stat.st_mode & 0o077) != 0 or key_stat.st_uid != os.getuid()):
                raise RuntimeFailure("RUNTIME_KEY_PERMISSIONS", "durable Run authentication key permissions or owner are unsafe")
            key = self.key_path.read_bytes()
        except OSError as exc:
            raise RuntimeFailure("RUNTIME_KEY_MISSING", "durable Run authentication key is unavailable") from exc
        if len(key) != 32:
            raise RuntimeFailure("RUNTIME_KEY_INVALID", "durable Run authentication key is invalid")
        return key

    def _state_hash(self, state: dict[str, Any]) -> str:
        semantic = {
            key: value
            for key, value in state.items()
            if key not in {"eventCursor", "pendingEvent"}
        }
        return hmac.new(self._runtime_key(), canonical_json(semantic).encode("utf-8"), hashlib.sha256).hexdigest()

    def _artifact_attestation(self, artifact: dict[str, Any]) -> str:
        unsigned = {key: value for key, value in artifact.items() if key != "attestation"}
        return hmac.new(self._runtime_key(), canonical_json(unsigned).encode("utf-8"), hashlib.sha256).hexdigest()

    def _verify_artifacts(self, state: dict[str, Any]) -> None:
        for artifact in state["artifacts"]:
            if artifact.get("producer") not in ARTIFACT_PRODUCERS:
                raise RuntimeFailure("ARTIFACT_TAMPERED", f"artifact producer is invalid: {artifact.get('id')}")
            if not hmac.compare_digest(str(artifact.get("attestation", "")), self._artifact_attestation(artifact)):
                raise RuntimeFailure("ARTIFACT_TAMPERED", f"artifact attestation failed: {artifact.get('id')}")
            relative = safe_relative_path(str(artifact.get("path", "")), "artifact path")
            path = (self.repository / relative).resolve()
            try:
                path.relative_to(self.repository)
            except ValueError as exc:
                raise RuntimeFailure("ARTIFACT_TAMPERED", "artifact path escapes repository") from exc
            if not path.is_file() or sha256_file(path) != artifact.get("sha256"):
                raise RuntimeFailure("ARTIFACT_TAMPERED", f"artifact content digest failed: {artifact.get('id')}")
            if artifact["producer"] == "legibility":
                receipt = self._read_json_receipt(artifact["path"], "legibility")
                for result in receipt.get("results") or []:
                    for source in result.get("artifacts") or []:
                        source_path = (self.repository / safe_relative_path(str(source.get("path", "")), "legibility source path")).resolve()
                        if not source_path.is_file() or sha256_file(source_path) != source.get("sha256"):
                            raise RuntimeFailure("ARTIFACT_TAMPERED", "legibility source artifact digest failed")

    def repository_identity(self) -> dict[str, Any]:
        root = Path(run_command(["git", "rev-parse", "--show-toplevel"], self.repository)).resolve()
        if root != self.repository:
            raise RuntimeFailure(
                "REPOSITORY_IDENTITY",
                "runtime must be invoked at the repository root",
                details={"expected": str(self.repository), "actual": str(root)},
            )
        commit = run_command(["git", "rev-parse", "HEAD"], self.repository)
        branch = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], self.repository)
        return {
            "repository": str(root),
            "commit": commit,
            "branch": branch,
            "deployment": None,
        }

    def _assert_repository_baseline(self, state: dict[str, Any]) -> None:
        identity = self.repository_identity()
        drift = {
            key: {"expected": state["baseline"].get(key), "actual": identity.get(key)}
            for key in ("repository", "commit", "branch")
            if state["baseline"].get(key) != identity.get(key)
        }
        if drift:
            raise RuntimeFailure("STALE_REPOSITORY", "repository baseline drift requires resume reconciliation", details=drift)

    def run_dir(self, run_id: str) -> Path:
        require_id(run_id, "run id")
        path = (self.runs_root / run_id).resolve()
        if path.parent != self.runs_root.resolve():
            raise RuntimeFailure("PATH_ESCAPE", "run id escapes the run root")
        return path

    def latest_run_id(self) -> str:
        if not self.runs_root.is_dir():
            raise RuntimeFailure("RUN_NOT_FOUND", "no durable runs exist", exit_code=2)
        candidates = [path for path in self.runs_root.iterdir() if path.is_dir() and (path / "run.json").is_file()]
        if not candidates:
            raise RuntimeFailure("RUN_NOT_FOUND", "no durable runs exist", exit_code=2)
        return max(candidates, key=lambda path: path.stat().st_mtime).name

    def _resolve_run_id(self, run_id: str | None) -> str:
        return run_id or self.latest_run_id()

    def _atomic_write(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(value, handle, indent=2, sort_keys=False, ensure_ascii=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
            if os.name != "nt":
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temp_name)

    def _write_snapshot(self, run_dir: Path, state: dict[str, Any]) -> None:
        snapshot_dir = run_dir / "snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._atomic_write(snapshot_dir / f"{state['revision']:012d}.json", state)

    def _restore_snapshot(
        self,
        run_dir: Path,
        run_id: str,
        events: Sequence[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not events:
            return None
        expected_hash = events[-1]["payload"].get("stateHash")
        snapshot_dir = run_dir / "snapshots"
        for path in sorted(snapshot_dir.glob("*.json"), reverse=True) if snapshot_dir.is_dir() else []:
            try:
                candidate = json.loads(path.read_text(encoding="utf-8"))
                validate_run(candidate)
            except (OSError, json.JSONDecodeError, RuntimeFailure):
                continue
            if candidate.get("runId") != run_id:
                continue
            if candidate.get("eventCursor") != {"sequence": len(events), "lastHash": events[-1]["hash"]}:
                continue
            if self._state_hash(candidate) != expected_hash:
                continue
            self._atomic_write(run_dir / "run.json", candidate)
            return candidate
        return None

    def _read_state(self, run_dir: Path) -> dict[str, Any]:
        path = run_dir / "run.json"
        try:
            with path.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
        except FileNotFoundError as exc:
            raise RuntimeFailure("RUN_NOT_FOUND", f"run state not found: {path}", exit_code=2) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeFailure("RUN_CORRUPT", f"run state is unreadable: {path}") from exc
        if not isinstance(state, dict):
            raise RuntimeFailure("RUN_CORRUPT", "run state must be a JSON object")
        return state

    def _event_hash(self, event: dict[str, Any]) -> str:
        unsigned = {key: value for key, value in event.items() if key != "hash"}
        return hmac.new(self._runtime_key(), canonical_json(unsigned).encode("utf-8"), hashlib.sha256).hexdigest()

    def _read_events(self, run_dir: Path) -> list[dict[str, Any]]:
        path = run_dir / "events.jsonl"
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if len(line) > 1024 * 1024:
                        raise RuntimeFailure("EVENT_LOG_CORRUPT", f"event line {line_number} exceeds 1 MiB")
                    if not line.strip():
                        raise RuntimeFailure("EVENT_LOG_CORRUPT", f"event line {line_number} is empty")
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise RuntimeFailure("EVENT_LOG_CORRUPT", f"event line {line_number} is not an object")
                    events.append(event)
        except json.JSONDecodeError as exc:
            raise RuntimeFailure("EVENT_LOG_CORRUPT", f"invalid JSONL event at line {exc.lineno}") from exc
        except OSError as exc:
            raise RuntimeFailure("EVENT_LOG_CORRUPT", f"cannot read event log: {path}") from exc
        return events

    def _verify_events(
        self,
        run_id: str,
        events: Sequence[dict[str, Any]],
        expected_cursor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        previous_hash = ZERO_HASH
        for sequence, event in enumerate(events, start=1):
            required = {
                "eventId",
                "runId",
                "taskId",
                "timestamp",
                "type",
                "actor",
                "payload",
                "evidenceRefs",
                "sequence",
                "previousHash",
                "hash",
            }
            if set(event) != required:
                raise RuntimeFailure("EVENT_LOG_TAMPERED", f"event {sequence} has an invalid shape")
            if event["runId"] != run_id or event["sequence"] != sequence:
                raise RuntimeFailure("EVENT_LOG_TAMPERED", f"event {sequence} identity or sequence mismatch")
            if event["previousHash"] != previous_hash or event["hash"] != self._event_hash(event):
                raise RuntimeFailure("EVENT_LOG_TAMPERED", f"event {sequence} hash chain mismatch")
            if not isinstance(event["type"], str) or not EVENT_TYPE_RE.fullmatch(event["type"]):
                raise RuntimeFailure("EVENT_LOG_TAMPERED", f"event {sequence} type is invalid")
            previous_hash = event["hash"]
        cursor = {"sequence": len(events), "lastHash": previous_hash}
        if expected_cursor is not None and cursor != expected_cursor:
            raise RuntimeFailure(
                "EVENT_LOG_TAMPERED",
                "event log does not match the Run cursor",
                details={"expected": expected_cursor, "actual": cursor},
            )
        return cursor

    def _append_event(self, run_dir: Path, event: dict[str, Any]) -> None:
        path = run_dir / "events.jsonl"
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(event))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _recover_pending(self, run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
        pending = state.get("pendingEvent")
        events = self._read_events(run_dir)
        cursor = self._verify_events(state.get("runId", ""), events)
        if pending is None:
            self._verify_events(state.get("runId", ""), events, state.get("eventCursor"))
            return state

        expected_previous = state.get("eventCursor")
        if not isinstance(expected_previous, dict):
            raise RuntimeFailure("RUN_CORRUPT", "pending event has no prior event cursor")
        if pending.get("sequence") != expected_previous.get("sequence", -1) + 1:
            raise RuntimeFailure("RUN_CORRUPT", "pending event sequence is invalid")
        if pending.get("previousHash") != expected_previous.get("lastHash"):
            raise RuntimeFailure("RUN_CORRUPT", "pending event previous hash is invalid")
        if pending.get("hash") != self._event_hash(pending):
            raise RuntimeFailure("RUN_CORRUPT", "pending event hash is invalid")

        pending_cursor = {"sequence": pending["sequence"], "lastHash": pending["hash"]}
        if cursor == expected_previous:
            self._append_event(run_dir, pending)
        elif cursor != pending_cursor:
            raise RuntimeFailure("EVENT_LOG_TAMPERED", "event log diverged while a transition was pending")

        state["eventCursor"] = pending_cursor
        state["pendingEvent"] = None
        self._atomic_write(run_dir / "run.json", state)
        self._verify_events(state["runId"], self._read_events(run_dir), pending_cursor)
        return state

    def _load_locked(self, run_id: str, *, verify_artifacts: bool = True) -> tuple[Path, dict[str, Any]]:
        run_dir = self.run_dir(run_id)
        state = self._recover_pending(run_dir, self._read_state(run_dir))
        validate_run(state)
        if verify_artifacts:
            self._verify_artifacts(state)
        events = self._read_events(run_dir)
        self._verify_events(run_id, events, state["eventCursor"])
        if events and events[-1]["payload"].get("stateHash") != self._state_hash(state):
            recovered = self._restore_snapshot(run_dir, run_id, events)
            if recovered is not None:
                raise RuntimeFailure("RUN_STATE_TAMPERED_RECOVERED", "canonical Run state was restored from its latest valid snapshot")
            raise RuntimeFailure("RUN_STATE_TAMPERED", "canonical Run state does not match the latest event")
        return run_dir, state

    def load(self, run_id: str | None = None) -> dict[str, Any]:
        resolved = self._resolve_run_id(run_id)
        run_dir = self.run_dir(resolved)
        with FileLock(run_dir / ".run.lock"):
            _, state = self._load_locked(resolved)
            return copy.deepcopy(state)

    def events(self, run_id: str | None = None) -> list[dict[str, Any]]:
        resolved = self._resolve_run_id(run_id)
        run_dir = self.run_dir(resolved)
        with FileLock(run_dir / ".run.lock"):
            _, state = self._load_locked(resolved)
            events = self._read_events(run_dir)
            self._verify_events(resolved, events, state["eventCursor"])
            return events

    def _new_event(
        self,
        state: dict[str, Any],
        event_type: str,
        actor: str,
        task_id: str | None,
        payload: dict[str, Any] | None,
        evidence_refs: Sequence[str],
    ) -> dict[str, Any]:
        if not EVENT_TYPE_RE.fullmatch(event_type):
            raise RuntimeFailure("INVALID_EVENT", f"invalid event type: {event_type}")
        cursor = state["eventCursor"]
        event = {
            "eventId": f"evt-{uuid.uuid4().hex}",
            "runId": state["runId"],
            "taskId": task_id,
            "timestamp": utc_now(),
            "type": event_type,
            "actor": actor,
            "payload": redact(
                {
                    **(payload or {}),
                    "stateRevision": state["revision"],
                    "stateHash": self._state_hash(state),
                }
            ),
            "evidenceRefs": list(dict.fromkeys(evidence_refs)),
            "sequence": cursor["sequence"] + 1,
            "previousHash": cursor["lastHash"],
        }
        event["hash"] = self._event_hash(event)
        return event

    def _commit_locked(
        self,
        run_dir: Path,
        state: dict[str, Any],
        *,
        event_type: str,
        actor: str,
        task_id: str | None = None,
        payload: dict[str, Any] | None = None,
        evidence_refs: Sequence[str] = (),
    ) -> dict[str, Any]:
        sanitized = redact(state)
        state.clear()
        state.update(sanitized)
        state["revision"] += 1
        state["updatedAt"] = utc_now()
        event = self._new_event(state, event_type, actor, task_id, payload, evidence_refs)
        state["pendingEvent"] = event
        validate_run(state)
        self._atomic_write(run_dir / "run.json", state)
        self._append_event(run_dir, event)
        state["eventCursor"] = {"sequence": event["sequence"], "lastHash": event["hash"]}
        state["pendingEvent"] = None
        self._atomic_write(run_dir / "run.json", state)
        self._write_snapshot(run_dir, state)
        self._project(run_dir, state)
        return copy.deepcopy(state)

    def _transaction(
        self,
        run_id: str,
        mutate: Callable[[dict[str, Any]], dict[str, Any] | None],
        *,
        event_type: str,
        actor: str = "coordinator",
        task_id: str | None = None,
        evidence_refs: Sequence[str] = (),
    ) -> dict[str, Any]:
        run_dir = self.run_dir(run_id)
        with FileLock(run_dir / ".run.lock"):
            _, state = self._load_locked(run_id)
            before_policy = copy.deepcopy(state["policy"])
            payload = mutate(state) or {}
            if actor.startswith("worker:") and state["policy"] != before_policy:
                raise RuntimeFailure("POLICY_ESCALATION", "workers cannot modify Run policy")
            return self._commit_locked(
                run_dir,
                state,
                event_type=event_type,
                actor=actor,
                task_id=task_id,
                payload=payload,
                evidence_refs=evidence_refs,
            )

    def create(
        self,
        *,
        goal: str,
        outcome: str,
        criteria: Sequence[dict[str, Any]],
        autonomy_scope: str | None = None,
        policy_allow: Sequence[dict[str, Any]] | None = None,
        confirmation_required: Sequence[str] | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        # Explicit arguments always win; an omitted (None) argument falls back to the
        # repository's configured `autonomy` defaults, and only then to the built-in default.
        configured_autonomy = repository_config(str(self.repository)).get("autonomy") or {}
        configured_policy = configured_autonomy.get("mutationPolicy") or {}
        if autonomy_scope is None:
            autonomy_scope = configured_autonomy.get("scope") or "current-task"
        if policy_allow is None:
            policy_allow = configured_policy.get("allow") or []
        if confirmation_required is None:
            confirmation_required = configured_policy.get("confirmationRequired") or []
        if autonomy_scope not in {"current-task", "approved-program", "advisory-only"}:
            raise RuntimeFailure("INVALID_AUTONOMY", f"invalid autonomy scope: {autonomy_scope}")
        if not goal.strip() or not outcome.strip():
            raise RuntimeFailure("INVALID_RUN", "goal and outcome are required")
        run_id = run_id or f"run-{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        require_id(run_id, "run id")
        run_dir = self.run_dir(run_id)
        with FileLock(run_dir / ".run.lock"):
            if (run_dir / "run.json").exists():
                raise RuntimeFailure("RUN_EXISTS", f"run already exists: {run_id}")
            run_dir.mkdir(parents=True, exist_ok=True)
            self._runtime_key(create=True)
            normalized_criteria = normalize_criteria(criteria, outcome)
            now = utc_now()
            state: dict[str, Any] = {
                "schema": SCHEMA,
                "revision": -1,
                "runId": run_id,
                "createdAt": now,
                "updatedAt": now,
                "goal": goal.strip(),
                "status": "CREATED",
                "autonomy": {"scope": autonomy_scope},
                "policy": {
                    "default": "deny",
                    "allow": normalize_policy_allow(policy_allow),
                    "confirmationRequired": list(dict.fromkeys(confirmation_required)),
                },
                "outcome": {
                    "description": outcome.strip(),
                    "requiredCriteria": [
                        {
                            "id": criterion["id"],
                            "description": criterion["description"],
                            "verification": criterion["verificationType"],
                            "required": criterion["blocking"],
                        }
                        for criterion in normalized_criteria
                    ],
                },
                "acceptanceCriteria": normalized_criteria,
                "baseline": self.repository_identity(),
                "tasks": [],
                "checkpoints": [],
                "externalCheckpoints": [],
                "artifacts": [],
                "workers": [],
                "gateResults": [],
                "eventLog": f".architrave/runs/{run_id}/events.jsonl",
                "eventCursor": {"sequence": 0, "lastHash": ZERO_HASH},
                "pendingEvent": None,
            }
            self._create_human_artifacts(run_dir, state)
            return self._commit_locked(
                run_dir,
                state,
                event_type="run.created",
                actor="coordinator",
                payload={"goal": goal.strip(), "autonomyScope": autonomy_scope},
            )

    def _create_human_artifacts(self, run_dir: Path, state: dict[str, Any]) -> None:
        templates = {
            "intake.md": "# Intake\n\n## Understanding\n\n## Acceptance Criteria\n\n## Grounding Sources\n\n## Assumptions\n\n## Blocking Questions\n",
            "tournament.md": "# Tournament of Options\n\n## Decision Matrix\n\n## Winner\n",
            "recommended-plan.md": "# Recommended Plan\n\n## Implementation Sequence\n\n## Test Strategy\n\n## Rollback / Recovery\n",
            "deterministic-gates.md": "# Deterministic Gates\n\n",
            "judge-pre.md": "# Judge Gate 1\n\n## Verdict\n\n## Findings\n",
            "judge-post.md": "# Judge Gate 2\n\n## Verdict\n\n## Findings\n",
            "runtime-observer.md": "# Runtime Observer\n\n## Sources Used\n\n## Observed State\n\n## Mismatches\n",
        }
        for name, content in templates.items():
            path = run_dir / name
            if not path.exists():
                path.write_text(content, encoding="utf-8")

    def _project(self, run_dir: Path, state: dict[str, Any]) -> None:
        rows = [
            "# Phase Ledger",
            "",
            "> Projection of `run.json`; phase labels are observational and do not authorize or block work.",
            "",
            "| Phase | Name | Status | Scope | Gate | Result |",
            "|---:|---|---|---|---|---|",
        ]
        status_map = {
            "NOT_READY": "not-started",
            "READY": "not-started",
            "RUNNING": "in-progress",
            "WAITING_EXTERNAL": "blocked",
            "WAITING_RESOURCE": "blocked",
            "COMPLETED": "completed",
            "FAILED": "blocked",
            "SKIPPED": "skipped",
            "CANCELLED": "skipped",
        }
        for index, task in enumerate(state["tasks"], start=1):
            result = "pass" if task["status"] == "COMPLETED" else "pending"
            if task["status"] == "FAILED":
                result = "fail"
            values = [
                str(index),
                task["title"],
                status_map[task["status"]],
                task["objective"],
                task.get("gate") or "runtime task gate",
                result,
            ]
            escaped = [value.replace("|", "\\|").replace("\n", " ") for value in values]
            rows.append("| " + " | ".join(escaped) + " |")
        if not state["tasks"]:
            rows.append("| 0 | Planning | in-progress | Build the TaskGraph. | TaskGraph accepted | pending |")
        rows.extend(["", "## Phase Transition Log", "", f"Last projected from Run revision {state['revision']}.", ""])
        (run_dir / "phase-ledger.md").write_text("\n".join(rows), encoding="utf-8")

        required = [criterion for criterion in state["acceptanceCriteria"] if criterion["blocking"]]
        summary = {
            "schema": SCHEMA,
            "runId": state["runId"],
            "status": state["status"],
            "updatedAt": state["updatedAt"],
            "canonicalState": f".architrave/runs/{state['runId']}/run.json",
            "eventLog": state["eventLog"],
            "outcome": state["outcome"]["description"],
            "acceptance": {
                "required": len(required),
                "passed": sum(item["status"] in {"PASS", "NOT_APPLICABLE"} for item in required),
                "failed": sum(item["status"] == "FAIL" for item in required),
                "blockedExternal": sum(item["status"] == "BLOCKED_EXTERNAL" for item in required),
            },
            "readyTasks": [task["id"] for task in state["tasks"] if task["status"] == "READY"],
            "pendingExternalCheckpoints": [
                checkpoint["id"]
                for checkpoint in state["externalCheckpoints"]
                if checkpoint["status"] == "PENDING"
            ],
        }
        self._atomic_write(run_dir / "summary.json", summary)

    def add_task(self, run_id: str, task: dict[str, Any], actor: str = "coordinator") -> dict[str, Any]:
        task_id = require_id(str(task.get("id", "")), "task id")

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            if state["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                raise RuntimeFailure("RUN_TERMINAL", "cannot add a task to a terminal Run")
            if any(existing["id"] == task_id for existing in state["tasks"]):
                raise RuntimeFailure("TASK_EXISTS", f"task already exists: {task_id}")
            criterion_ids = {criterion["id"] for criterion in state["acceptanceCriteria"]}
            acceptance = list(dict.fromkeys(task.get("acceptanceCriteria") or []))
            if not acceptance or not set(acceptance).issubset(criterion_ids):
                raise RuntimeFailure("INVALID_TASK", "task must reference existing acceptance criteria")
            dependencies = list(dict.fromkeys(task.get("dependencies") or []))
            existing_ids = {existing["id"] for existing in state["tasks"]}
            if not set(dependencies).issubset(existing_ids):
                raise RuntimeFailure("INVALID_TASK", "task dependencies must already exist")
            mutable_paths = [safe_relative_path(path, "mutable path") for path in task.get("mutablePaths", [])]
            side_effect = task.get("sideEffect")
            if side_effect is not None:
                side_effect = {
                    "operation": str(side_effect["operation"]),
                    "target": str(side_effect["target"]),
                    "state": "NONE",
                    "reconciliation": None,
                }
            config = repository_config(str(self.repository))
            workers_config = config.get("workers") or {}
            evaluation_block = config.get("evaluation") or {}
            worker_profile = str(task.get("workerProfile") or workers_config.get("defaultAdapter") or "shell")
            enabled_adapters = workers_config.get("enabledAdapters")
            if enabled_adapters and worker_profile not in enabled_adapters:
                raise RuntimeFailure(
                    "INVALID_TASK",
                    f"worker adapter is not enabled for this repository: {worker_profile}",
                    details={"enabledAdapters": list(enabled_adapters)},
                )
            risk = str(task.get("risk") or evaluation_block.get("defaultRisk") or "R1")
            if risk not in RISK_CLASSES:
                raise RuntimeFailure("INVALID_TASK", f"invalid risk: {risk}")
            normalized = {
                "id": task_id,
                "title": str(task.get("title") or task_id),
                "objective": str(task.get("objective") or "").strip(),
                "status": "NOT_READY" if dependencies else "READY",
                "dependencies": dependencies,
                "workerProfile": worker_profile,
                "workspace": task.get("workspace"),
                "mutablePaths": mutable_paths,
                "tools": list(dict.fromkeys(task.get("tools") or [])),
                "risk": risk,
                "acceptanceCriteria": acceptance,
                "requiredArtifacts": list(dict.fromkeys(task.get("requiredArtifacts") or [])),
                "gate": task.get("gate"),
                "retryPolicy": {
                    "maxAttempts": int(task.get("maxAttempts", 1)),
                    "backoffSeconds": float(task.get("backoffSeconds", 0)),
                    "retryable": list(dict.fromkeys(task.get("retryable") or [])),
                },
                "checkpointPolicy": {
                    "beforeSideEffect": bool(task.get("beforeSideEffect", side_effect is not None)),
                    "afterCompletion": bool(task.get("afterCompletion", True)),
                },
                "attempts": 0,
                "lease": None,
                "retryNotBefore": None,
                "workPacket": normalize_work_packet(task.get("workPacket"), task_id, normalized_defaults={
                    "objective": str(task.get("objective") or "").strip(),
                    "acceptanceCriteria": acceptance,
                    "repoScope": str(self.repository),
                    "mutablePaths": mutable_paths,
                    "tools": list(dict.fromkeys(task.get("tools") or [])),
                    "worker": worker_profile,
                    "risk": risk,
                    "expectedArtifacts": list(dict.fromkeys(task.get("requiredArtifacts") or [])),
                }),
                "sideEffect": side_effect,
            }
            if not normalized["objective"]:
                raise RuntimeFailure("INVALID_TASK", "task objective is required")
            state["tasks"].append(normalized)
            validate_task_graph(state["tasks"])
            state["status"] = "PLANNING" if state["status"] == "CREATED" else state["status"]
            return {"taskId": task_id, "status": normalized["status"]}

        return self._transaction(run_id, mutate, event_type="task.created", actor=actor, task_id=task_id)

    def ready_tasks(self, run_id: str | None = None) -> list[dict[str, Any]]:
        state = self.load(run_id)
        return [copy.deepcopy(task) for task in state["tasks"] if task["status"] == "READY"]

    def assign_workspace(
        self,
        run_id: str,
        task_id: str,
        workspace: str,
        *,
        actor: str = "coordinator",
    ) -> dict[str, Any]:
        workspace_path = Path(workspace).resolve()

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            self._assert_repository_baseline(state)
            task = find_task(state, task_id)
            if task["status"] not in {"NOT_READY", "READY"}:
                raise RuntimeFailure("WORKSPACE_LATE_ASSIGNMENT", "workspace must be assigned before task start")
            if any(
                other["id"] != task_id
                and other.get("workspace")
                and Path(other["workspace"]).resolve() == workspace_path
                and task["mutablePaths"]
                and other["mutablePaths"]
                and other["status"] not in TERMINAL_TASK_STATUSES
                for other in state["tasks"]
            ):
                raise RuntimeFailure("WORKSPACE_COLLISION", "workspace is already assigned to another active task")
            task["workspace"] = str(workspace_path)
            task["workPacket"]["repoScope"] = str(workspace_path)
            return {"taskId": task_id, "workspace": str(workspace_path)}

        return self._transaction(
            run_id,
            mutate,
            event_type="workspace.created",
            actor=actor,
            task_id=task_id,
        )

    def record_artifact(
        self,
        run_id: str,
        *,
        artifact_id: str,
        kind: str,
        path: str,
        evidence_refs: Sequence[str] = (),
        actor: str = "coordinator",
    ) -> dict[str, Any]:
        return self._record_artifact(
            run_id,
            artifact_id=artifact_id,
            kind=kind,
            path=path,
            evidence_refs=evidence_refs,
            actor=actor,
            producer="coordinator",
        )

    def write_evidence_receipt(self, *, name: str, commit: str, payload: dict[str, Any]) -> tuple[str, str]:
        """Write one evidence receipt file EXCLUSIVELY, under a name that embeds
        both the exact execution commit and a fresh, unique execution id.

        Real incident this closes: an earlier ad-hoc registration script wrote
        gate-evidence receipts to a fixed, deterministic path (e.g.
        ``base-gate-<short-commit>.json``); a later retry of that SAME script
        (after an unrelated subprocess-environment bug) wrote to the exact same
        path again with slightly different content, silently replacing already-
        registered evidence bytes out from under a previously-computed artifact
        digest -- permanently tripping the runtime's own artifact-tamper check
        on every subsequent load. That check was working correctly; the gap was
        that nothing prevented a caller from reusing a path at all.

        This helper is the fix: every call gets its own fresh ``uuid4`` execution
        id baked into the filename, and the file is created with ``O_EXCL`` (so a
        genuine uuid collision -- vanishingly unlikely -- fails loudly instead of
        silently overwriting). No caller can ever cause two registrations to
        share one evidence path again, by construction, not by convention.
        Returns ``(relative_path, execution_id)``; the caller still registers the
        artifact itself (via ``_record_deterministic_result``/``_record_artifact``
        etc.) exactly as before.
        """
        require_id(name, "evidence receipt name")
        if not commit or not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
            raise RuntimeFailure("EVIDENCE_RECEIPT", "write_evidence_receipt requires a full 40-hex-char commit")
        execution_id = uuid.uuid4().hex[:12]
        evidence_dir = self.repository / ".architrave" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        relative = Path(".architrave") / "evidence" / f"{commit[:12]}-{execution_id}-{name}.json"
        absolute = self.repository / relative
        content = json.dumps(payload, indent=2).encode("utf-8")
        try:
            descriptor = os.open(absolute, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError as exc:
            raise RuntimeFailure(
                "EVIDENCE_PATH_EXISTS",
                f"evidence path already exists and must never be overwritten: {relative}",
            ) from exc
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
        except BaseException:
            with contextlib.suppress(OSError):
                absolute.unlink()
            raise
        return str(relative), execution_id

    def _record_artifact(
        self,
        run_id: str,
        *,
        artifact_id: str,
        kind: str,
        path: str,
        evidence_refs: Sequence[str],
        actor: str,
        producer: str,
        declared_commit: str | None = None,
    ) -> dict[str, Any]:
        require_id(artifact_id, "artifact id")
        relative = safe_relative_path(path, "artifact path")
        absolute = (self.repository / relative).resolve()
        try:
            absolute.relative_to(self.repository)
        except ValueError as exc:
            raise RuntimeFailure("PATH_ESCAPE", "artifact path escapes repository") from exc
        if not absolute.is_file():
            raise RuntimeFailure("ARTIFACT_NOT_FOUND", f"artifact not found: {relative}")
        if producer not in ARTIFACT_PRODUCERS:
            raise RuntimeFailure("ARTIFACT_PRODUCER", f"invalid artifact producer: {producer}")
        allowed_kinds = PRODUCER_ARTIFACT_KINDS.get(producer)
        if producer == "legibility":
            if not kind.endswith("-legibility"):
                raise RuntimeFailure("ARTIFACT_KIND", "legibility artifact kind must end in -legibility")
        elif allowed_kinds is not None and kind not in allowed_kinds:
            raise RuntimeFailure("ARTIFACT_KIND", f"artifact kind {kind} is invalid for {producer}")
        if absolute.stat().st_size <= 2 * 1024 * 1024:
            content = absolute.read_bytes()
            if b"\x00" not in content:
                text = content.decode("utf-8", "replace")
                if redact(text) != text:
                    raise RuntimeFailure("ARTIFACT_SENSITIVE", "artifact appears to contain secret material")

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            if any(item["id"] == artifact_id for item in state["artifacts"]):
                raise RuntimeFailure("ARTIFACT_EXISTS", f"artifact already exists: {artifact_id}")
            # (F7) ``sourceCommit`` below only stamps "whatever the baseline reads
            # right now" -- that alone proves nothing about when the receipt FILE
            # was actually produced, so replaying a stale-but-unregistered receipt
            # after the baseline has moved on would otherwise launder it as fresh
            # evidence. Producers that require freshness (e.g. deterministic gate
            # receipts) must have the executor stamp their OWN execution commit
            # into the receipt content, and that declared commit must match the
            # current baseline before the artifact is ever recorded.
            if declared_commit is not None and declared_commit != state["baseline"].get("commit"):
                raise RuntimeFailure(
                    "EVIDENCE_STALE_COMMIT",
                    "producer receipt declares a different execution commit than the current baseline",
                    details={"declaredCommit": declared_commit, "baselineCommit": state["baseline"].get("commit")},
                )
            content_sha256 = sha256_file(absolute)
            if producer in {"mutation", "reconciliation"} and any(
                item["producer"] in {"mutation", "reconciliation"}
                and item["sha256"] == content_sha256
                for item in state["artifacts"]
            ):
                raise RuntimeFailure("EVIDENCE_REPLAY", "mutation reconciliation receipt content is already registered")
            artifact = {
                "id": artifact_id,
                "kind": kind,
                "producer": producer,
                "path": relative,
                "createdAt": utc_now(),
                "sha256": content_sha256,
                # (F7) The exact baseline commit this artifact was recorded against. An
                # artifact is never rewritten once recorded, so this is a frozen, honest
                # fact about when it was actually produced -- it is what lets
                # ``record_gate`` refuse to launder an artifact recorded under an older
                # baseline into evidence for a gate registered after the baseline moved
                # (``resume(accept_commit=True)``), instead of trusting only the new
                # gate's own self-reported stamp.
                "sourceCommit": state["baseline"].get("commit"),
                "evidenceRefs": list(dict.fromkeys(evidence_refs)),
                "consumedByTask": None,
            }
            artifact["attestation"] = self._artifact_attestation(artifact)
            state["artifacts"].append(artifact)
            return {"artifactId": artifact_id, "kind": kind, "path": relative}

        return self._transaction(
            run_id,
            mutate,
            event_type="artifact.recorded",
            actor=actor,
            evidence_refs=evidence_refs,
        )

    def _record_deterministic_result(self, run_id: str, **kwargs: Any) -> dict[str, Any]:
        receipt = self._read_json_receipt(kwargs["path"], "deterministic")
        if receipt.get("status") != "pass" or receipt.get("exitCode") != 0 or not receipt.get("command"):
            raise RuntimeFailure("DETERMINISTIC_RECEIPT", "deterministic receipt does not prove a passing command")
        declared_commit = receipt.get("commit")
        if not declared_commit or not isinstance(declared_commit, str):
            # (F7) A deterministic gate receipt that doesn't declare the exact
            # commit it was actually executed against cannot be trusted as fresh
            # evidence -- it would otherwise only ever be judged by "what the
            # baseline happens to read right now", which is exactly the
            # laundering gap a stale, replayed receipt file could exploit.
            raise RuntimeFailure("DETERMINISTIC_RECEIPT", "deterministic receipt does not declare its execution commit")
        return self._record_artifact(
            run_id,
            kind="deterministic-result",
            actor="deterministic-executor",
            producer="deterministic",
            declared_commit=declared_commit,
            **kwargs,
        )

    def _record_invariant_result(self, run_id: str, **kwargs: Any) -> dict[str, Any]:
        path = (self.repository / safe_relative_path(str(kwargs["path"]), "invariant result path")).resolve()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeFailure("INVARIANT_RECEIPT", "invariant result is unreadable") from exc
        from invariant_engine import evaluate, load_config

        expected = evaluate(self.repository, load_config(self.repository))
        if payload != expected:
            raise RuntimeFailure("INVARIANT_RECEIPT", "invariant result does not match a fresh engine evaluation")
        return self._record_artifact(run_id, kind="invariant-result", actor="invariant-engine", producer="invariant", **kwargs)

    def _record_legibility_result(self, run_id: str, *, kind: str, **kwargs: Any) -> dict[str, Any]:
        receipt = self._read_json_receipt(kwargs["path"], "legibility")
        surface = kind.removesuffix("-legibility")
        required_names = {
            "web": {"runtime.health", "web.e2e"},
            "electron": {"electron.launch", "electron.health", "electron.screenshot"},
            "ios": {"ios.build", "ios.install", "ios.launch", "ios.screenshot", "ios.blank-screen"},
        }.get(surface)
        results = receipt.get("results") or []
        result_names = {item.get("name") for item in results if isinstance(item, dict) and item.get("status") == "pass"}
        if (
            required_names is None
            or receipt.get("surface") != surface
            or receipt.get("status") != "pass"
            or receipt.get("failed") != []
            or not required_names.issubset(result_names)
        ):
            raise RuntimeFailure("LEGIBILITY_RECEIPT", "legibility receipt does not prove the required surface checks")
        return self._record_artifact(run_id, kind=kind, actor="legibility-runner", producer="legibility", **kwargs)

    def _record_mutation_receipt(self, run_id: str, **kwargs: Any) -> dict[str, Any]:
        path = (self.repository / safe_relative_path(str(kwargs["path"]), "mutation receipt path")).resolve()
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeFailure("MUTATION_RECEIPT", "mutation receipt is unreadable") from exc
        result = receipt.get("result") or {}
        verification = receipt.get("verification") or {}
        expected = receipt.get("expected") or {}
        task_id = receipt.get("taskId")
        operation = receipt.get("operation")
        target = receipt.get("target")
        if not task_id or not operation or not target:
            raise RuntimeFailure("MUTATION_RECEIPT", "mutation receipt lacks task, operation, or target binding")
        if (result.get("apply") or {}).get("status") != "pass":
            raise RuntimeFailure("MUTATION_RECEIPT", "mutation receipt does not prove the apply occurred")
        if not (verification.get("version") or {}).get("stdout") or not (verification.get("digest") or {}).get("stdout"):
            raise RuntimeFailure("MUTATION_RECEIPT", "mutation receipt lacks version or digest evidence")
        if not expected.get("version") or not expected.get("digest"):
            raise RuntimeFailure("MUTATION_RECEIPT", "mutation receipt lacks intended version or digest")
        if (verification.get("health") or {}).get("status") != "pass":
            raise RuntimeFailure("MUTATION_RECEIPT", "mutation receipt health verification did not pass")
        if (verification.get("version") or {}).get("stdout", "").strip() != expected["version"]:
            raise RuntimeFailure("MUTATION_RECEIPT", "mutation receipt observed version does not match intended version")
        if (verification.get("digest") or {}).get("stdout", "").strip() != expected["digest"]:
            raise RuntimeFailure("MUTATION_RECEIPT", "mutation receipt observed digest does not match intended digest")
        state = self.load(run_id)
        task = find_task(state, task_id)
        side_effect = task.get("sideEffect")
        if side_effect is None or side_effect["operation"] != operation or side_effect["target"] != target:
            raise RuntimeFailure("MUTATION_RECEIPT", "mutation receipt does not match the bound task side effect")
        return self._record_artifact(run_id, kind="mutation-receipt", actor="mutation-runner", producer="mutation", **kwargs)

    def _record_reconciliation_receipt(self, run_id: str, **kwargs: Any) -> dict[str, Any]:
        receipt = self._read_json_receipt(kwargs["path"], "reconciliation")
        required = ("taskId", "operation", "target")
        if any(not receipt.get(field) for field in required) or receipt.get("outcome") != "not-applied":
            raise RuntimeFailure("RECONCILIATION_RECEIPT", "not-applied receipt lacks task/operation/target/outcome")
        if not receipt.get("observation") or not receipt.get("observedAt"):
            raise RuntimeFailure("RECONCILIATION_RECEIPT", "not-applied receipt lacks observation evidence")
        state = self.load(run_id)
        task = find_task(state, receipt["taskId"])
        side_effect = task.get("sideEffect")
        if side_effect is None or side_effect["operation"] != receipt["operation"] or side_effect["target"] != receipt["target"]:
            raise RuntimeFailure("RECONCILIATION_RECEIPT", "not-applied receipt does not match task side effect")
        return self._record_artifact(
            run_id,
            kind="reconciliation-receipt",
            actor="reconciliation-runner",
            producer="reconciliation",
            **kwargs,
        )

    def _record_workspace_artifact(self, run_id: str, *, kind: str, **kwargs: Any) -> dict[str, Any]:
        return self._record_artifact(run_id, kind=kind, actor="workspace-manager", producer="workspace", **kwargs)

    def _record_worker_result(self, run_id: str, **kwargs: Any) -> dict[str, Any]:
        return self._record_artifact(run_id, kind="worker-result", actor="worker-adapter", producer="worker", **kwargs)

    def _record_semantic_verdict(self, run_id: str, **kwargs: Any) -> dict[str, Any]:
        verdict = self._read_json_receipt(kwargs["path"], "semantic")
        if verdict.get("verdict") != "PASS" or verdict.get("family") not in {"gpt", "claude"} or not verdict.get("criteria"):
            raise RuntimeFailure("SEMANTIC_RECEIPT", "semantic verdict receipt is invalid")
        declared_commit = verdict.get("commit")
        if not declared_commit or not isinstance(declared_commit, str):
            # (F2) A semantic review verdict that doesn't declare the exact
            # commit it actually reviewed cannot be trusted as fresh evidence
            # once the baseline has moved on -- without this, an old verdict
            # file could be registered as a brand-new artifact any time after
            # resume(accept_commit=True) and pass the gate-binding freshness
            # check purely because `sourceCommit` is stamped at registration
            # time, never because the review itself actually covered the
            # current code.
            raise RuntimeFailure("SEMANTIC_RECEIPT", "semantic verdict receipt does not declare its reviewed commit")
        return self._record_artifact(
            run_id,
            kind="semantic-verdict",
            actor="semantic-review",
            producer="semantic-judge",
            declared_commit=declared_commit,
            **kwargs,
        )

    def _record_security_verdict(self, run_id: str, **kwargs: Any) -> dict[str, Any]:
        verdict = self._read_json_receipt(kwargs["path"], "security")
        declared_commit = verdict.get("commit")
        if not declared_commit or not isinstance(declared_commit, str):
            # (F2) Same rationale as _record_semantic_verdict: a security
            # review verdict must declare the exact commit it actually
            # reviewed, not merely get stamped fresh at registration time.
            raise RuntimeFailure("SECURITY_RECEIPT", "security verdict receipt does not declare its reviewed commit")
        return self._record_artifact(
            run_id,
            kind="security-verdict",
            actor="security-review",
            producer="security-review",
            declared_commit=declared_commit,
            **kwargs,
        )

    def _record_policy_decision(self, run_id: str, **kwargs: Any) -> dict[str, Any]:
        decision = self._read_json_receipt(kwargs["path"], "policy")
        declared_commit = decision.get("commit")
        if not declared_commit or not isinstance(declared_commit, str):
            # (F2) Same rationale: a policy decision must declare the exact
            # commit it was actually evaluated against.
            raise RuntimeFailure("POLICY_RECEIPT", "policy decision receipt does not declare its evaluated commit")
        return self._record_artifact(
            run_id,
            kind="policy-decision",
            actor="policy-engine",
            producer="policy-engine",
            declared_commit=declared_commit,
            **kwargs,
        )

    def _record_external_proof(self, run_id: str, **kwargs: Any) -> dict[str, Any]:
        proof = self._read_json_receipt(kwargs["path"], "external")
        state = self.load(run_id)
        checkpoint = next((item for item in state["externalCheckpoints"] if item["id"] == proof.get("checkpointId")), None)
        if (
            checkpoint is None
            or checkpoint["status"] != "PENDING"
            or proof.get("principal") != checkpoint["principal"]
            or proof.get("provider") != checkpoint["provider"]
        ):
            raise RuntimeFailure("EXTERNAL_PROOF", "external proof does not match a pending checkpoint")
        return self._record_artifact(run_id, kind="external-proof", actor="external-checkpoint", producer="external-proof", **kwargs)

    def _resolve_private_each_run_file(self, path_value: str, *, code: str) -> Path:
        receipt_file = Path(path_value).expanduser()
        if not receipt_file.is_absolute():
            raise RuntimeFailure(code, "receipt path must be an absolute path to the private receipt store")
        if receipt_file.is_symlink():
            raise RuntimeFailure(code, "receipt path must not itself be a symlink")
        each_home = Path(os.environ.get("EACH_HOME", str(Path.home() / ".each"))).expanduser()
        private_runs_root = (each_home / "runs").resolve()
        resolved = receipt_file.resolve()
        try:
            resolved.relative_to(private_runs_root)
        except ValueError as exc:
            raise RuntimeFailure(
                code,
                "receipt path must live under the private EACH runs directory, not anywhere else",
            ) from exc
        if not resolved.is_file():
            raise RuntimeFailure(code, "private receipt file does not exist")
        return resolved

    def _extract_original_producer_sha(self, receipt: dict[str, Any]) -> str:
        for key in ("producerCommit", "sourceCommit", "commit"):
            value = receipt.get(key)
            if isinstance(value, str) and value:
                return value
        return "UNKNOWN"

    def _validated_real_model_identity(self, receipt: dict[str, Any], *, error_code: str) -> tuple[str, str]:
        from each.models.base import validate_recorded_real_model_identity

        model_identity = receipt.get("modelIdentity") or {}
        if not isinstance(model_identity, dict):
            raise RuntimeFailure(error_code, "private receipt does not declare a structured model identity")
        try:
            model_id, adapter_class_path = validate_recorded_real_model_identity(model_identity)
        except (TypeError, ValueError) as exc:
            # (B-series fix) ``validate_recorded_real_model_identity`` raises
            # TypeError (not ValueError) when ``modelManifest`` itself is not
            # a dict -- a non-dict manifest is an INPUT shape error from an
            # untrusted private receipt, not a programming bug in this
            # runtime module, and must be rejected the same honest,
            # source-free way as every other malformed-identity case rather
            # than propagating an unguarded TypeError out of this boundary.
            raise RuntimeFailure(
                error_code,
                "private receipt does not declare an allowlisted real local-model identity with full provenance",
            ) from exc
        if not isinstance(receipt.get("attempts"), list) or not receipt["attempts"]:
            raise RuntimeFailure(error_code, "private receipt is missing recorded attempts")
        if not isinstance(receipt.get("isolationEvidence"), dict) or "command" not in receipt["isolationEvidence"]:
            raise RuntimeFailure(error_code, "private receipt is missing recorded isolation evidence")
        if not isinstance(receipt.get("baselineResult"), dict) or not isinstance(receipt.get("repairedResult"), dict):
            raise RuntimeFailure(error_code, "private receipt is missing recorded validation evidence")
        return model_id, adapter_class_path

    def _record_target_repair_receipt(
        self,
        run_id: str,
        *,
        artifact_id: str,
        receipt_path: str,
        evidence_refs: Sequence[str] = (),
        actor: str = "coordinator",
    ) -> dict[str, Any]:
        """Register honest, reality-gate evidence that a declared local model produced a
        genuinely verified target repair (M7/M8-style).

        ``receipt_path`` must be an absolute path to the REAL private receipt
        (prompts, completions, patch text, target source) under the private
        ``~/.each/runs`` store -- never a repo-relative, caller-authored summary
        file. This function independently re-runs the EXISTING, mature
        ``each verify --full`` signature + retained-materials verifier against
        that real receipt itself (never trusting a caller-supplied
        "signatureVerification": "PASS"-style claim string), and derives every
        fact this records -- outcome, spec hash, model identity, network
        isolation -- directly from the re-verified receipt's own declared
        content. A hand-written JSON summary that merely *asserts* a PASS can
        therefore never satisfy a reality criterion; only a genuinely signed,
        materially-retained, REPAIR_VERIFIED receipt for a real (non-Fixture)
        model can. The private receipt content itself is still never copied
        into the artifact this writes -- only the independently re-derived,
        source-free summary fields are.
        """
        resolved = self._resolve_private_each_run_file(receipt_path, code="TARGET_REPAIR_RECEIPT")

        try:
            receipt = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeFailure("TARGET_REPAIR_RECEIPT", "private receipt is unreadable") from exc
        if not isinstance(receipt, dict):
            raise RuntimeFailure("TARGET_REPAIR_RECEIPT", "private receipt must be a JSON object")

        # Independently re-run the EXISTING `each verify --full` CLI (mature
        # Ed25519 signature + retained-materials-bytes verifier) against the
        # real receipt file. Invoked as a subprocess, not imported, so this
        # stdlib-only runtime module stays free of a hard dependency on the
        # `each` package/its own dependencies (e.g. `cryptography`).
        result = subprocess.run(
            [sys.executable, "-m", "each.cli", "verify", "--full", str(resolved)],
            cwd=str(self.repository),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeFailure(
                "TARGET_REPAIR_RECEIPT",
                "independent `each verify --full` re-check of the private receipt did not PASS",
                details={"returncode": result.returncode},
            )

        outcome = str(receipt.get("outcome", ""))
        if outcome_class(outcome) != "REPAIR_VERIFIED":
            raise RuntimeFailure(
                "TARGET_REPAIR_RECEIPT",
                "private receipt does not itself declare a verified repair outcome",
            )
        if receipt.get("networkIsolationVerified") is not True:
            raise RuntimeFailure("TARGET_REPAIR_RECEIPT", "private receipt does not show network isolation verified")
        from each.outcome import sanitize_proposal_format

        model_id, adapter_class_path = self._validated_real_model_identity(
            receipt, error_code="TARGET_REPAIR_RECEIPT"
        )
        spec_hash = receipt.get("specHash")
        target_run_id = receipt.get("runId")
        if not spec_hash or not target_run_id:
            raise RuntimeFailure("TARGET_REPAIR_RECEIPT", "private receipt is missing specHash or runId")

        # The artifact this records is built ENTIRELY from the independently
        # re-verified receipt above -- never from caller-supplied claim
        # fields -- and written to a private, gitignored evidence scratch
        # file inside the repo so `_record_artifact` (which requires a
        # repo-relative path) can register it. Uses the exclusive-create
        # evidence helper (never a fixed/reusable path) so a retried call
        # can never silently overwrite an already-registered receipt's bytes.
        sanitized_summary = {
            "purpose": "target-repair-verified",
            "specHash": spec_hash,
            "targetRunId": target_run_id,
            "outcome": "REPAIR_VERIFIED",
            "signatureVerification": "PASS",
            "materialsVerification": "PASS",
            "networkIsolationVerified": True,
            "modelId": model_id,
            "adapterClassPath": adapter_class_path,
            "adapterType": adapter_class_path.rsplit(".", 1)[-1],
            "originalProducerSha": self._extract_original_producer_sha(receipt),
            "selectedAttempt": receipt.get("selectedAttempt"),
            "auditSubjectSha256": receipt.get("auditSubjectSha256"),
            "attemptProposalFormats": [
                sanitize_proposal_format(attempt.get("proposal_format") if isinstance(attempt, dict) else None)
                for attempt in receipt.get("attempts") or []
            ],
            "seedProvenance": sanitize_seed_provenance_summary(receipt.get("seedProvenance")),
            "receiptSha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
        }
        current_commit = self.load(run_id)["baseline"]["commit"]
        relative_path, _execution_id = self.write_evidence_receipt(
            name=f"{artifact_id}.target-repair-summary", commit=current_commit, payload=sanitized_summary
        )

        return self._record_artifact(
            run_id,
            artifact_id=artifact_id,
            kind="target-repair-receipt",
            path=relative_path,
            evidence_refs=evidence_refs,
            actor=actor,
            producer="target-repair",
        )

    def _record_target_experiment_receipt(
        self,
        run_id: str,
        *,
        artifact_id: str,
        receipt_path: str,
        evidence_refs: Sequence[str] = (),
        actor: str = "coordinator",
    ) -> dict[str, Any]:
        """Register a complete real-model target experiment without claiming repair success.

        This is the reality-evidence counterpart to
        :meth:`_record_target_repair_receipt` for a criterion that requires an
        actual qualified local evaluation, not a verified repair. It independently
        re-verifies the private signed receipt and retained materials, requires a
        real allowlisted local-model identity and verified network isolation, and
        exports only a bounded outcome class plus hashes/stage-presence facts.
        """
        from each.models.catalog import UnavailableModelError, load_model, qualified_profile
        from each.outcome import UNKNOWN_OUTCOME_CLASS, sanitize_outcome_class, sanitize_proposal_format

        resolved = self._resolve_private_each_run_file(receipt_path, code="TARGET_EXPERIMENT_RECEIPT")
        try:
            before_bytes = resolved.read_bytes()
        except OSError as exc:
            raise RuntimeFailure("TARGET_EXPERIMENT_RECEIPT", "private receipt could not be read") from exc
        before_sha256 = hashlib.sha256(before_bytes).hexdigest()
        try:
            receipt = json.loads(before_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeFailure("TARGET_EXPERIMENT_RECEIPT", "private receipt is unreadable") from exc
        if not isinstance(receipt, dict):
            raise RuntimeFailure("TARGET_EXPERIMENT_RECEIPT", "private receipt must be a JSON object")
        if not isinstance(receipt.get("materials"), dict) or not receipt["materials"]:
            raise RuntimeFailure("TARGET_EXPERIMENT_RECEIPT", "private receipt has no retained materials")
        if not isinstance(receipt.get("audit"), dict):
            raise RuntimeFailure("TARGET_EXPERIMENT_RECEIPT", "private receipt audit must be an object")
        from each.attestation import verify_materials_root, verify_receipt
        from each.signing import public_key_path

        try:
            signature_result = verify_receipt(receipt, public_key_path().read_bytes())
            materials_result = verify_materials_root(receipt, resolved.parent / "materials")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise RuntimeFailure(
                "TARGET_EXPERIMENT_RECEIPT",
                "independent receipt verification could not execute",
            ) from exc
        if signature_result.get("status") != "PASS" or materials_result.get("status") != "PASS":
            raise RuntimeFailure(
                "TARGET_EXPERIMENT_RECEIPT",
                "independent signature and retained-material verification did not PASS",
            )
        outcome = sanitize_outcome_class(str(receipt.get("outcome", "")))
        eligible_outcomes = {
            "PATCH_REJECTED",
            "BUILD_FAILED",
            "REPAIR_NOT_VERIFIED",
            "REPAIR_VERIFIED",
            "REPAIR_REJECTED_AUDIT",
            "EXECUTION_ERROR",
        }
        if outcome == UNKNOWN_OUTCOME_CLASS or outcome not in eligible_outcomes:
            raise RuntimeFailure(
                "TARGET_EXPERIMENT_RECEIPT",
                "private receipt outcome does not prove that qualified target generation occurred",
            )
        if receipt.get("networkIsolationVerified") is not True:
            raise RuntimeFailure("TARGET_EXPERIMENT_RECEIPT", "private receipt does not show network isolation verified")
        if receipt.get("legalCertification") is not False or receipt.get("cleanroomCertification") is not False:
            raise RuntimeFailure("TARGET_EXPERIMENT_RECEIPT", "private receipt must not claim legal certification")
        _model_id, adapter_class_path = self._validated_real_model_identity(
            receipt, error_code="TARGET_EXPERIMENT_RECEIPT"
        )
        model_identity = receipt.get("modelIdentity") or {}
        manifest = model_identity.get("modelManifest") or {}
        repo_id = str(manifest.get("repoId") or "")
        revision = str(manifest.get("revision") or "")
        matched_name = next(
            (
                name for name in ("starcoderbase", "octocoder")
                if qualified_profile(name)["repo"] == repo_id
                and qualified_profile(name)["revision"] == revision
            ),
            None,
        )
        if matched_name is None:
            raise RuntimeFailure("TARGET_EXPERIMENT_RECEIPT", "private receipt model is not an exact qualified checkpoint")
        catalog_key = f"{matched_name}-mlx"
        try:
            official_identity = load_model(catalog_key, max_tokens=1).identity()
        except (
            UnavailableModelError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        ) as exc:
            raise RuntimeFailure(
                "TARGET_EXPERIMENT_RECEIPT",
                "exact qualified local artifact is unavailable or changed",
            ) from exc
        immutable_identity_fields = (
            "adapterClassPath",
            "adapterType",
            "implementationModule",
            "implementationSha256",
            "modelId",
            "modelManifest",
            "runtimeModelConfig",
        )
        def exact_json_equal(left: Any, right: Any) -> bool:
            try:
                return json.dumps(
                    left, sort_keys=True, separators=(",", ":"), allow_nan=False
                ) == json.dumps(
                    right, sort_keys=True, separators=(",", ":"), allow_nan=False
                )
            except (TypeError, ValueError):
                return False

        if any(
            not exact_json_equal(official_identity.get(key), model_identity.get(key))
            for key in immutable_identity_fields
        ):
            raise RuntimeFailure(
                "TARGET_EXPERIMENT_RECEIPT",
                "private receipt identity does not match the official qualified local artifact",
            )
        spec_hash = str(receipt.get("specHash") or "")
        target_run_id = str(receipt.get("runId") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", spec_hash):
            raise RuntimeFailure("TARGET_EXPERIMENT_RECEIPT", "private receipt specHash is invalid")
        try:
            require_id(target_run_id, "target run id")
        except RuntimeFailure as exc:
            raise RuntimeFailure("TARGET_EXPERIMENT_RECEIPT", "private receipt runId is invalid") from exc
        assurance_level = str(receipt.get("assuranceLevel") or "")
        if assurance_level not in {"EACH-P1", "EACH-P2"}:
            raise RuntimeFailure(
                "TARGET_EXPERIMENT_RECEIPT",
                "private receipt assuranceLevel exceeds this neural target-experiment evidence scope",
            )
        attempts = receipt.get("attempts") or []
        selected_attempt = receipt.get("selectedAttempt")
        selected_records = (
            [
                attempt for attempt in attempts
                if (
                    isinstance(attempt, dict)
                    and type(attempt.get("attempt")) is int
                    and attempt.get("attempt") == selected_attempt
                )
            ]
            if type(selected_attempt) is int
            else []
        )
        selected_completion = selected_records[0].get("raw_completion") if len(selected_records) == 1 else None
        if (
            type(selected_attempt) is not int
            or selected_attempt < 1
            or len(selected_records) != 1
            or not isinstance(selected_completion, str)
            or not selected_completion.strip()
            or not exact_json_equal(selected_records[0].get("model_identity"), model_identity)
            or model_identity.get("generationAttempted") is not True
        ):
            raise RuntimeFailure(
                "TARGET_EXPERIMENT_RECEIPT",
                "private receipt does not bind one selected target-generation attempt to the qualified artifact",
            )
        audit = receipt.get("audit") or {}
        sanitized_summary = {
            "purpose": "target-experiment-complete",
            "specHash": spec_hash,
            "targetRunId": target_run_id,
            "outcome": outcome,
            "signatureVerification": "PASS",
            "materialsVerification": "PASS",
            "materialCount": len(receipt.get("materials") or {}),
            "networkIsolationVerified": True,
            "assuranceLevel": assurance_level,
            "modelId": official_identity["modelId"],
            "adapterClassPath": official_identity["adapterClassPath"],
            "adapterType": adapter_class_path.rsplit(".", 1)[-1],
            "baselineValidationRecorded": bool(receipt.get("baselineResult")),
            "candidateValidationRecorded": bool(receipt.get("repairedResult")),
            "terminalAuditRecorded": bool(audit.get("checks") or {}),
            "selectedAttempt": selected_attempt,
            "attemptProposalFormats": [
                sanitize_proposal_format(attempt.get("proposal_format") if isinstance(attempt, dict) else None)
                for attempt in receipt.get("attempts") or []
            ],
            "receiptSha256": before_sha256,
            "legalCertification": False,
            "cleanroomCertification": False,
        }
        current_commit = self.load(run_id)["baseline"]["commit"]
        relative_path, _ = self.write_evidence_receipt(
            name=f"{artifact_id}.target-experiment-summary",
            commit=current_commit,
            payload=sanitized_summary,
        )
        return self._record_artifact(
            run_id,
            artifact_id=artifact_id,
            kind="target-experiment-receipt",
            path=relative_path,
            evidence_refs=evidence_refs,
            actor=actor,
            producer="target-experiment",
        )

    def _record_m7_experiment_receipt(
        self,
        run_id: str,
        *,
        artifact_id: str,
        receipt_path: str,
        evidence_refs: Sequence[str] = (),
        actor: str = "coordinator",
    ) -> dict[str, Any]:
        """Register honest reality-gate evidence for mandate section 129's M7
        clean-room-style demonstration acceptance, which is DELIBERATELY NOT
        the same bar as ``_record_target_repair_receipt``'s: section 129's own
        stated acceptance is "complete receipt; information firewall
        demonstrably enforced; candidate remains shadow-only" -- it never
        requires the candidate's validation to have actually passed. This
        exists specifically so an honestly-failed repair (``REPAIR_NOT_VERIFIED``,
        or any other non-``REPAIR_VERIFIED`` outcome reached via a real attempt)
        can still satisfy its OWN, narrower, mandate-grounded criterion without
        ever touching the separate, stricter ``m7-target-repair-verified``
        criterion a prior Run registered -- that criterion keeps meaning
        exactly what it always meant (a genuinely verified repair) and stays
        FAIL here; this method can never flip it.

        Like ``_record_target_repair_receipt``, every fact recorded is
        independently re-derived from the real, signature+materials-verified
        private receipt file itself -- never trusted from a caller-supplied
        claim string -- and the private receipt content (prompts, completions,
        patch, target source) is never copied into the public artifact.
        """
        resolved = self._resolve_private_each_run_file(receipt_path, code="M7_EXPERIMENT_RECEIPT")

        try:
            receipt = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeFailure("M7_EXPERIMENT_RECEIPT", "private receipt is unreadable") from exc
        if not isinstance(receipt, dict):
            raise RuntimeFailure("M7_EXPERIMENT_RECEIPT", "private receipt must be a JSON object")

        # Independently re-run the EXISTING `each verify --full` CLI against
        # the real receipt file -- a complete receipt's signature and
        # retained materials must genuinely verify regardless of outcome.
        result = subprocess.run(
            [sys.executable, "-m", "each.cli", "verify", "--full", str(resolved)],
            cwd=str(self.repository),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeFailure(
                "M7_EXPERIMENT_RECEIPT",
                "independent `each verify --full` re-check of the private receipt did not PASS",
                details={"returncode": result.returncode},
            )

        outcome = str(receipt.get("outcome", ""))
        if not outcome:
            raise RuntimeFailure("M7_EXPERIMENT_RECEIPT", "private receipt does not declare an outcome")
        if receipt.get("legalCertification") is not False or receipt.get("cleanroomCertification") is not False:
            raise RuntimeFailure(
                "M7_EXPERIMENT_RECEIPT",
                "private receipt must explicitly declare legal/clean-room certification false (section 129 never certifies)",
            )
        # (adversarial review finding) Section 129 requires the information
        # firewall to be DEMONSTRABLY ENFORCED, not merely mentioned -- a
        # receipt that never actually verified network isolation cannot
        # satisfy that bar just because some other field happens to be
        # truthy. This must be a hard requirement, not an optionally-true
        # recorded fact.
        if receipt.get("networkIsolationVerified") is not True:
            raise RuntimeFailure(
                "M7_EXPERIMENT_RECEIPT",
                "private receipt does not show the information firewall (network isolation) was verified",
            )
        audit = receipt.get("audit") or {}
        audit_checks = audit.get("checks") or {}
        # (adversarial review finding) A merely non-empty `checks` mapping
        # does not prove the REAL terminal auditor (each.audit.run.run_audit)
        # executed -- a receipt could fabricate an unrelated non-empty dict.
        # The real auditor always evaluates exactly this fixed check set
        # (each/audit/run.py); require an exact match so only a genuine
        # terminal-audit invocation (not a stub, and not a partial/forged
        # mapping) can satisfy this criterion. This module intentionally has
        # no import dependency on the `each` package, so the check names are
        # duplicated here as a stable, independently-verifiable constant.
        real_auditor_check_names = {
            "exact-substring",
            "ngram-similarity",
            "ast-similarity",
            "license-scan",
            "corpus-membership",
        }
        if set(audit_checks.keys()) != real_auditor_check_names:
            raise RuntimeFailure(
                "M7_EXPERIMENT_RECEIPT",
                "private receipt's audit.checks do not match the real terminal auditor's exact check set "
                "(section 129 requires the Auditor to have actually run, not a stub or a forged mapping)",
                details={"declared": sorted(audit_checks.keys()), "expected": sorted(real_auditor_check_names)},
            )
        from each.outcome import sanitize_outcome_class, sanitize_proposal_format

        model_id, adapter_class_path = self._validated_real_model_identity(
            receipt, error_code="M7_EXPERIMENT_RECEIPT"
        )
        spec_hash = receipt.get("specHash")
        target_run_id = receipt.get("runId")
        if not spec_hash or not target_run_id:
            raise RuntimeFailure("M7_EXPERIMENT_RECEIPT", "private receipt is missing specHash or runId")

        if "shadowOnly" in receipt:
            shadow_only = bool(receipt.get("shadowOnly"))
        elif "publicationPolicy" in receipt:
            shadow_only = str(receipt.get("publicationPolicy")).lower() == "shadow-only"
        else:
            # Section 129's project-wide default remains shadow-only unless a
            # receipt explicitly recorded a narrower/different publication fact.
            shadow_only = True

        sanitized_summary = {
            "purpose": "clean-room-experiment-complete",
            "specHash": spec_hash,
            "targetRunId": target_run_id,
            "outcome": sanitize_outcome_class(outcome),
            "signatureVerification": "PASS",
            "materialsVerification": "PASS",
            "networkIsolationVerified": bool(receipt.get("networkIsolationVerified")),
            "modelId": model_id,
            "adapterClassPath": adapter_class_path,
            "adapterType": adapter_class_path.rsplit(".", 1)[-1],
            "auditChecksRun": sorted(audit_checks.keys()),
            "auditResultStatuses": sorted(
                {
                    str(v.get("status"))
                    for v in audit_checks.values()
                    if isinstance(v, dict) and str(v.get("status")) in {"PASS", "FLAG", "FAIL", "UNAVAILABLE"}
                }
            ),
            "legalCertification": False,
            "cleanroomCertification": False,
            "shadowOnly": shadow_only,
            "originalProducerSha": self._extract_original_producer_sha(receipt),
            "selectedAttempt": receipt.get("selectedAttempt"),
            "auditSubjectSha256": receipt.get("auditSubjectSha256"),
            "attemptProposalFormats": [
                sanitize_proposal_format(attempt.get("proposal_format") if isinstance(attempt, dict) else None)
                for attempt in receipt.get("attempts") or []
            ],
            "seedProvenance": sanitize_seed_provenance_summary(receipt.get("seedProvenance")),
            "receiptSha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
        }
        current_commit = self.load(run_id)["baseline"]["commit"]
        relative_path, _execution_id = self.write_evidence_receipt(
            name=f"{artifact_id}.m7-experiment-summary", commit=current_commit, payload=sanitized_summary
        )

        return self._record_artifact(
            run_id,
            artifact_id=artifact_id,
            kind="clean-room-experiment-receipt",
            path=relative_path,
            evidence_refs=evidence_refs,
            actor=actor,
            producer="target-repair",
        )

    def _verify_clean_current_execution_identity(self, run_id: str) -> str:
        """Prove the CURRENT process is genuinely executing a clean checkout
        of the exact commit this Run's own canonical baseline records --
        not merely that ``git rev-parse HEAD`` happens to print a matching
        string while the working tree is dirty, or while some OTHER
        (stale/foreign) copy of the ``each`` package was already imported
        into this process from a different location on disk.

        Returns the verified commit sha. Only enforces the loaded-module
        origin check when ``self.repository`` is itself a checkout that
        declares an ``each`` package (the real EACH release checkout) --
        a synthetic target-repair fixture repository used by tests for a
        DIFFERENT repaired target naturally has no ``each/__init__.py`` and
        is unaffected.
        """
        state = self.load(run_id)
        identity = self.repository_identity()
        baseline_commit = state.get("baseline", {}).get("commit")
        if not baseline_commit or identity["commit"] != baseline_commit:
            raise RuntimeFailure(
                "TARGET_REPLAY_RECEIPT",
                "current repository HEAD does not match this Run's own recorded baseline commit",
            )
        # Exclude the Run's own private, gitignored `.architrave/` state
        # directory: durable Run bookkeeping writes there as a normal part
        # of EVERY run and is not a foreign/untracked source modification
        # that would make a replay non-reproducible.
        status = run_command(["git", "status", "--porcelain", "--", ".", ":(exclude).architrave"], self.repository)
        if status.strip():
            raise RuntimeFailure(
                "TARGET_REPLAY_RECEIPT",
                "current checkout is dirty; replay against an unclean working tree is not reproducible evidence",
            )
        each_pkg_init = self.repository / "each" / "__init__.py"
        if each_pkg_init.is_file():
            import each as _each_module

            package_root = each_pkg_init.parent.resolve()
            for name, module in list(sys.modules.items()):
                if name != "each" and not name.startswith("each."):
                    continue
                filename = getattr(module, "__file__", None)
                if not filename:
                    raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "loaded EACH module has no verifiable source origin")
                expected = self.repository.joinpath(*name.split("."))
                expected = expected / "__init__.py" if hasattr(module, "__path__") else expected.with_suffix(".py")
                if Path(filename).resolve() != expected.resolve():
                    raise RuntimeFailure(
                        "TARGET_REPLAY_RECEIPT",
                        "loaded EACH implementation is not the current repository checkout",
                    )
                for search_path in getattr(module, "__path__", ()):
                    if Path(search_path).resolve() != expected.parent.resolve():
                        raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "loaded EACH package has a foreign module search path")
            if Path(_each_module.__file__).resolve() != package_root / "__init__.py":
                raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "loaded EACH package origin does not match the checkout")
        return identity["commit"]

    # Decisive original outcomes eligible for current replay validation: a
    # genuinely verified repair, or a genuinely classified negative (patch
    # applied, build/test ran to a decisive answer, candidate did not
    # verify). Non-decisive outcomes (patch rejected before execution, an
    # execution/infra error, context budget exhaustion, or an inconclusive
    # baseline/repaired run that never reached a decisive pass/fail) are
    # never eligible -- there is no decisive historical claim to replay.
    _REPLAY_ELIGIBLE_OUTCOMES = frozenset({"REPAIR_VERIFIED", "REPAIR_NOT_VERIFIED"})

    def _record_target_replay_receipt(
        self,
        run_id: str,
        *,
        artifact_id: str,
        receipt_path: str,
        evidence_refs: Sequence[str] = (),
        actor: str = "coordinator",
    ) -> dict[str, Any]:
        from each.attestation import verify_materials_root, verify_receipt
        from each.audit.checks import STATUSES as AUDIT_STATUSES
        from each.audit.run import reject_on_audit_flag, run_audit
        from each.executor.container import ContainerExecutor, ContainerExecutorError
        from each.hashing import canonical_json, sha256_bytes
        from each.models.base import validate_recorded_real_model_identity
        from each.outcome import sanitize_outcome_class
        from each.patch import PatchRejected, apply_patch, parse_patch
        from each.signing import public_key_path
        from each.worktree import build_worktree, verify_unchanged

        resolved = self._resolve_private_each_run_file(receipt_path, code="TARGET_REPLAY_RECEIPT")
        try:
            replay = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "private replay receipt is unreadable") from exc
        if not isinstance(replay, dict):
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "private replay receipt must be a JSON object")
        if replay.get("purpose") != "replay-validation":
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "replay receipt must declare purpose replay-validation")

        expected_original = replay.get("original")
        if not isinstance(expected_original, dict):
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "replay receipt must declare original lineage fields")
        original_receipt_path = replay.get("originalReceiptPath") or replay.get("replayOfOriginalReceipt")
        if not isinstance(original_receipt_path, str) or not original_receipt_path:
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "replay receipt must identify the original receipt path")
        original_resolved = self._resolve_private_each_run_file(original_receipt_path, code="TARGET_REPLAY_RECEIPT")
        try:
            original = json.loads(original_resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "original receipt is unreadable") from exc
        if not isinstance(original, dict):
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "original receipt must be a JSON object")

        try:
            public_key_pem = public_key_path().read_bytes()
        except OSError as exc:
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "public signing key is unavailable") from exc
        signature_result = verify_receipt(original, public_key_pem)
        if signature_result.get("status") != "PASS":
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "original receipt signature verification failed")
        materials_root = original_resolved.parent / "materials"
        materials_result = verify_materials_root(original, materials_root)
        if materials_result.get("status") != "PASS":
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "original retained materials failed verification")

        # Item 7b: a genuinely classified negative is also eligible for
        # replay, not just a verified positive -- but its own terminal
        # audit (for a claimed-verified original) must not itself have
        # been rejected, and the raw (possibly candidate-influenced) text
        # is never retained past this sanitized classification.
        original_outcome_class = sanitize_outcome_class(str(original.get("outcome", "")))
        if original_outcome_class not in self._REPLAY_ELIGIBLE_OUTCOMES:
            raise RuntimeFailure(
                "TARGET_REPLAY_RECEIPT", "original receipt is not a decisively classified repair outcome eligible for replay"
            )
        if original_outcome_class == "REPAIR_VERIFIED" and reject_on_audit_flag(original.get("audit") or {}):
            raise RuntimeFailure(
                "TARGET_REPLAY_RECEIPT", "original receipt claims a verified repair but its own terminal audit was rejected"
            )
        try:
            model_id, adapter_class_path = validate_recorded_real_model_identity(original.get("modelIdentity") or {})
        except (TypeError, ValueError) as exc:
            # A non-dict modelManifest on an untrusted private receipt is
            # an input-shape error, not a programming bug -- it must reach
            # this boundary the same way any other malformed identity does.
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "original receipt does not declare a replayable real-model identity") from exc
        selected_attempt = original.get("selectedAttempt")
        if not isinstance(selected_attempt, int):
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "original receipt is missing selectedAttempt")
        # Item 2/3: a genuinely legacy signed original may honestly have
        # never recorded a producer commit (exported source tree, no git
        # metadata at write time) -- this is labelled UNKNOWN, not
        # hard-rejected. What IS always required, below, is that the
        # CURRENT replay execution itself is clean and fully attributable.
        original_producer_sha = self._extract_original_producer_sha(original)
        # Item 3: likewise a genuinely legacy original may never have
        # recorded auditSubjectSha256 at all. When present it must still
        # be a non-empty string; when absent, the CURRENT reconstructed
        # subject hash (computed below) stands on its own as the current
        # proof and is never backfilled onto the historic field.
        recorded_subject_sha = original.get("auditSubjectSha256")
        if recorded_subject_sha is not None and (not isinstance(recorded_subject_sha, str) or not recorded_subject_sha):
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "original receipt declares a malformed auditSubjectSha256")
        expected_map = {
            "specHash": original.get("specHash"),
            "patchHash": original.get("patchHash"),
            "trajectoryHash": original.get("trajectoryHash"),
            "modelId": model_id,
            "adapterClassPath": adapter_class_path,
            "selectedAttempt": selected_attempt,
            "outcome": original_outcome_class,
            "targetRunId": original.get("runId"),
            "auditSubjectSha256": recorded_subject_sha,
            "producerCommit": original_producer_sha,
        }
        for key, actual_value in expected_map.items():
            if expected_original.get(key) != actual_value:
                raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "replay receipt original lineage does not match the signed original")

        # Item 2: the claimed execution commit must match BOTH the current
        # actual git HEAD and this Run's own recorded baseline -- on a
        # clean checkout, with the loaded `each` package itself originating
        # from this same checkout (never a stale/foreign import).
        actual_execution_commit = self._verify_clean_current_execution_identity(run_id)
        execution_commit = replay.get("executionCommit")
        if execution_commit != actual_execution_commit:
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "replay execution commit does not match the current repository baseline")

        executor_identity = original.get("executorIdentity") or {}
        if executor_identity.get("executor") != "container":
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "original receipt does not declare a replayable container executor")
        executor = ContainerExecutor(
            image=str(executor_identity.get("image") or ""),
            docker_context=str(executor_identity.get("dockerContext") or "colima-each"),
            network=str(executor_identity.get("network") or "none"),
            memory_limit=str(executor_identity.get("memoryLimit") or "512m"),
            cpu_limit=str(executor_identity.get("cpuLimit") or "2"),
        )

        include_paths = sorted((original.get("materials") or {}).keys())
        if not include_paths:
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "original receipt declares no retained materials")

        # Item 1: the production spec contract (each.spec.SpecPacket.content())
        # always serializes snake_case build_commands/acceptance_commands --
        # never camelCase. A malformed command entry is strictly rejected,
        # never silently filtered away.
        def _validated_commands(value: Any, *, label: str) -> list[list[str]]:
            if value is None:
                return []
            if not isinstance(value, list):
                raise RuntimeFailure("TARGET_REPLAY_RECEIPT", f"original spec declares a malformed {label} list")
            validated: list[list[str]] = []
            for command in value:
                if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
                    raise RuntimeFailure("TARGET_REPLAY_RECEIPT", f"original spec declares a malformed {label} entry")
                validated.append(command)
            return validated

        spec = original.get("spec") or {}
        build_commands = _validated_commands(spec.get("build_commands"), label="build command")
        acceptance_commands = _validated_commands(spec.get("acceptance_commands"), label="acceptance command")
        if not acceptance_commands:
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "original receipt does not declare acceptance commands")

        def replay_results_for(
            worktree: Path, manifest: dict[str, str], protected_paths: tuple[str, ...]
        ) -> dict[str, list[dict[str, Any]]]:
            build_results: list[dict[str, Any]] = []
            acceptance_results: list[dict[str, Any]] = []
            try:
                for command in build_commands:
                    result = executor.run(list(command), worktree, protected_paths=protected_paths)
                    build_results.append(
                        {
                            "exitCode": result.exit_code,
                            "stdoutSha256": sha256_bytes(result.stdout.encode("utf-8")),
                            "stderrSha256": sha256_bytes(result.stderr.encode("utf-8")),
                        }
                    )
                for command in acceptance_commands:
                    result = executor.run(list(command), worktree, protected_paths=protected_paths)
                    acceptance_results.append(
                        {
                            "exitCode": result.exit_code,
                            "stdoutSha256": sha256_bytes(result.stdout.encode("utf-8")),
                            "stderrSha256": sha256_bytes(result.stderr.encode("utf-8")),
                        }
                    )
            except ContainerExecutorError as exc:
                raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "replay execution failed to produce a trusted execution record") from exc
            # Item 4: re-hash the protected (never-editable) retained inputs
            # immediately after every build/acceptance call -- a candidate
            # run that mutated harness/validator scaffold mid-execution must
            # never be reported as a trusted replay result.
            drift = verify_unchanged(worktree, manifest, list(protected_paths))
            if drift:
                raise RuntimeFailure(
                    "TARGET_REPLAY_RECEIPT", "protected retained inputs drifted during replay execution", details={"paths": drift}
                )
            return {"build": build_results, "acceptance": acceptance_results}

        def _decisive_exit_codes(results: list[dict[str, Any]], *, label: str) -> list[int]:
            codes = [int(entry["exitCode"]) for entry in results]
            if any(code not in (0, 1) for code in codes):
                raise RuntimeFailure("TARGET_REPLAY_RECEIPT", f"{label} produced an ambiguous, non-decisive exit code")
            return codes

        # Baseline must never be touched at all -- every retained path is
        # protected for the baseline execution.
        baseline_worktree, baseline_manifest = build_worktree(materials_root, include_paths)
        baseline_results = replay_results_for(baseline_worktree, baseline_manifest, tuple(include_paths))
        if baseline_results["build"] and any(entry["exitCode"] != 0 for entry in baseline_results["build"]):
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "baseline build failed during replay; not a usable replay artifact")
        baseline_codes = _decisive_exit_codes(baseline_results["acceptance"], label="baseline acceptance")
        if all(code == 0 for code in baseline_codes):
            raise RuntimeFailure(
                "TARGET_REPLAY_RECEIPT", "baseline unexpectedly passed acceptance during replay; original bug did not reproduce"
            )

        touched_paths = original.get("touchedPaths") or []
        patch_text = str(original.get("patchText") or "")
        if not touched_paths or not patch_text:
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "original receipt is missing its selected patch or touched paths")
        candidate_worktree, candidate_manifest = build_worktree(materials_root, include_paths)
        try:
            patch = parse_patch(patch_text)
            apply_patch(patch, candidate_worktree, set(touched_paths))
        except PatchRejected as exc:
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "original selected patch does not replay against retained materials") from exc
        # Capture the candidate bytes BEFORE any build/run -- the same
        # bytes are hashed for the current reconstructed subject proof and
        # decoded for the terminal audit below, never a post-exec reread.
        candidate_bytes = b"\n".join((candidate_worktree / path).read_bytes() for path in touched_paths)
        candidate_sha = sha256_bytes(candidate_bytes)
        if recorded_subject_sha is not None and candidate_sha != recorded_subject_sha:
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "reconstructed candidate does not match the original trusted audit subject")
        touched_set = set(touched_paths)
        protected_candidate_paths = tuple(p for p in include_paths if p not in touched_set)
        replay_results = replay_results_for(candidate_worktree, candidate_manifest, protected_candidate_paths)
        if replay_results["build"] and any(entry["exitCode"] != 0 for entry in replay_results["build"]):
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "candidate build failed during replay; not a usable replay artifact")
        candidate_codes = _decisive_exit_codes(replay_results["acceptance"], label="candidate acceptance")
        candidate_passed = all(code == 0 for code in candidate_codes)

        try:
            candidate_text = candidate_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeFailure("TARGET_REPLAY_RECEIPT", "reconstructed candidate source is not valid UTF-8") from exc
        # Terminal audit runs only against this trusted, already-validated
        # candidate capture -- never fed back to a Builder, never used to
        # pick a different attempt.
        audit_result = run_audit(candidate_text, corpus_revision=str((original.get("audit") or {}).get("corpusRevision") or "none"))
        current_audit_rejected = reject_on_audit_flag(audit_result)
        audit_statuses = {
            name: (
                check.get("status")
                if isinstance(check, dict) and str(check.get("status")) in AUDIT_STATUSES
                else "UNAVAILABLE"
            )
            for name, check in (audit_result.get("checks") or {}).items()
        }

        if original_outcome_class == "REPAIR_VERIFIED":
            if not candidate_passed:
                raise RuntimeFailure(
                    "TARGET_REPLAY_RECEIPT", "replay candidate failed to reproduce the originally verified repair"
                )
            if current_audit_rejected:
                raise RuntimeFailure(
                    "TARGET_REPLAY_RECEIPT", "current terminal audit rejected the replayed candidate; refusing positive registration"
                )
        else:  # REPAIR_NOT_VERIFIED
            if candidate_passed:
                raise RuntimeFailure(
                    "TARGET_REPLAY_RECEIPT",
                    "replay candidate unexpectedly passed acceptance for a classified-negative original; refusing contradictory registration",
                )

        sanitized_summary = {
            "purpose": "replay-validation",
            "originalRunId": original.get("runId"),
            "specHash": original.get("specHash"),
            "originalSpecHash": original.get("specHash"),
            "originalPatchHash": original.get("patchHash"),
            "originalTrajectoryHash": original.get("trajectoryHash"),
            "originalProducerSha": original_producer_sha,
            "originalOutcome": original_outcome_class,
            "originalModelId": model_id,
            "originalAdapterClassPath": adapter_class_path,
            "selectedAttempt": selected_attempt,
            "auditSubjectSha256": candidate_sha,
            "replayExecutionCommit": actual_execution_commit,
            "baselineExecution": baseline_results,
            "replayExecution": replay_results,
            "candidatePassed": candidate_passed,
            "currentAuditorRejected": current_audit_rejected,
            "currentAuditorCheckStatuses": audit_statuses,
            "currentAuditorToolVersionKeys": sorted((audit_result.get("toolVersions") or {}).keys()),
            "currentAuditorToolVersionsSha256": sha256_bytes(
                canonical_json(audit_result.get("toolVersions") or {}).encode("utf-8")
            ),
            "replayReceiptSha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
            "originalReceiptSha256": hashlib.sha256(original_resolved.read_bytes()).hexdigest(),
        }
        current_commit = self.load(run_id)["baseline"]["commit"]
        relative_path, _execution_id = self.write_evidence_receipt(
            name=f"{artifact_id}.target-replay-summary", commit=current_commit, payload=sanitized_summary
        )
        return self._record_artifact(
            run_id,
            artifact_id=artifact_id,
            kind="target-replay-receipt",
            path=relative_path,
            evidence_refs=evidence_refs,
            actor=actor,
            producer="target-repair",
        )

    def _read_json_receipt(self, path_value: str, label: str) -> dict[str, Any]:
        path = (self.repository / safe_relative_path(str(path_value), f"{label} receipt path")).resolve()
        try: 
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeFailure("EVIDENCE_RECEIPT", f"{label} receipt is unreadable") from exc
        if not isinstance(payload, dict):
            raise RuntimeFailure("EVIDENCE_RECEIPT", f"{label} receipt must be an object")
        return payload

    def start_task(
        self,
        run_id: str,
        task_id: str,
        *,
        worker_id: str,
        lease_seconds: int = 3600,
        confirmed: bool = False,
        actor: str = "coordinator",
    ) -> dict[str, Any]:
        require_id(worker_id, "worker id")

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            self._assert_repository_baseline(state)
            if state["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                raise RuntimeFailure("RUN_TERMINAL", "cannot start a task on a terminal Run")
            if state["status"] == "PAUSED":
                raise RuntimeFailure(
                    "RUN_PAUSED",
                    "cannot start a task while the Run is paused; call resume() explicitly first",
                )
            task = find_task(state, task_id)
            if task["status"] != "READY":
                raise RuntimeFailure("TASK_NOT_READY", f"task {task_id} is {task['status']}")
            if task["attempts"] >= task["retryPolicy"]["maxAttempts"]:
                raise RuntimeFailure("RETRY_EXHAUSTED", f"task {task_id} exhausted its retry policy")
            if task.get("retryNotBefore") and parse_iso(task["retryNotBefore"]) > dt.datetime.now(dt.UTC):
                raise RuntimeFailure(
                    "RETRY_BACKOFF",
                    f"task {task_id} is within its declared retry backoff window",
                    details={"retryNotBefore": task["retryNotBefore"]},
                )
            max_parallel = (repository_config(str(self.repository)).get("workers") or {}).get("maxParallel")
            if max_parallel is not None:
                running = sum(1 for other in state["tasks"] if other["id"] != task_id and other["status"] == "RUNNING")
                if running >= int(max_parallel):
                    raise RuntimeFailure(
                        "PARALLELISM_EXCEEDED",
                        f"configured workers.maxParallel={max_parallel} concurrent task limit reached",
                    )
            if task["mutablePaths"]:
                active_mutating = [
                    other
                    for other in state["tasks"]
                    if other["id"] != task_id and other["status"] == "RUNNING" and other["mutablePaths"]
                ]
                if active_mutating and not task.get("workspace"):
                    raise RuntimeFailure(
                        "WORKSPACE_ISOLATION_REQUIRED",
                        "concurrent mutating tasks require isolated assigned workspaces",
                    )
                conflicting = [
                    other["id"]
                    for other in active_mutating
                    if mutable_scopes_overlap(task["mutablePaths"], other["mutablePaths"])
                ]
                if conflicting:
                    raise RuntimeFailure(
                        "RESOURCE_CONFLICT",
                        "concurrent mutating tasks have overlapping mutable paths",
                        details={"tasks": conflicting},
                    )
                cross_run_conflicts = self._cross_run_mutation_conflicts(state["runId"], task["mutablePaths"])
                if cross_run_conflicts:
                    raise RuntimeFailure(
                        "RESOURCE_CONFLICT",
                        "another Run has an active overlapping mutable scope",
                        details={"tasks": cross_run_conflicts},
                    )
                if task.get("workspace") and any(
                    other.get("workspace")
                    and Path(other["workspace"]).resolve() == Path(task["workspace"]).resolve()
                    for other in active_mutating
                ):
                    raise RuntimeFailure("WORKSPACE_COLLISION", "concurrent mutating tasks cannot share a workspace")
            if task["mutablePaths"]:
                require_mutation_allowed(state, "repository", "edit", confirmed=confirmed)
            if task["sideEffect"] is not None:
                require_mutation_allowed(
                    state,
                    task["sideEffect"]["target"],
                    task["sideEffect"]["operation"],
                    confirmed=confirmed,
                )
                task["sideEffect"]["state"] = "PENDING"
            if task["checkpointPolicy"]["beforeSideEffect"]:
                append_checkpoint(state, task_id, "TASK_START")
            acquired = dt.datetime.now(dt.UTC)
            expires = acquired + dt.timedelta(seconds=max(1, lease_seconds))
            task["lease"] = {
                "owner": worker_id,
                "acquiredAt": acquired.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "expiresAt": expires.isoformat(timespec="seconds").replace("+00:00", "Z"),
            }
            task["attempts"] += 1
            task["status"] = "RUNNING"
            worker = next((item for item in state["workers"] if item["id"] == worker_id), None)
            if worker is None:
                adapter = task["workerProfile"] if task["workerProfile"] in {"copilot", "claude", "codex", "shell"} else "shell"
                state["workers"].append(
                    {
                        "id": worker_id,
                        "adapter": adapter,
                        "status": "RUNNING",
                        "workspace": task["workspace"],
                        "mutablePaths": task["mutablePaths"],
                    }
                )
            else:
                if worker["status"] == "RUNNING":
                    raise RuntimeFailure("WORKER_BUSY", f"worker is already running: {worker_id}")
                worker["status"] = "RUNNING"
                worker["workspace"] = task["workspace"]
                worker["mutablePaths"] = task["mutablePaths"]
            state["status"] = "RUNNING"
            return {"taskId": task_id, "workerId": worker_id, "attempt": task["attempts"]}

        with FileLock(self.repository / ".architrave" / "resources.lock"):
            return self._transaction(run_id, mutate, event_type="task.started", actor=actor, task_id=task_id)

    def grant_task_attempt(
        self,
        run_id: str,
        task_id: str,
        *,
        reason: str,
        actor: str,
        checkpoint_id: str,
    ) -> dict[str, Any]:
        """Grant one additional bounded attempt to a task that exhausted its retry policy.

        A task whose declared work genuinely spans an external-checkpoint pause/resume
        cycle (e.g. a milestone task that starts, then waits on a genuine human approval,
        then resumes) can legitimately need more attempts than a tight `maxAttempts` bound
        anticipated -- this is an operational gap in the original task's declared budget,
        not a reason to retry speculative or already-failed work. This is deliberately
        narrow: a trusted coordinator/human actor only, it raises `maxAttempts` by exactly
        one (never resets `attempts` or any other state), it refuses a task that is still
        RUNNING or already terminal (COMPLETED/CANCELLED), and every grant is recorded as
        its own typed, reasoned event -- never a silent retry-policy rewrite.

        ``checkpoint_id`` (F7 fix) must name an actual, already-RESOLVED external
        checkpoint bound to exactly this task (``resumeTask == task_id``), with its own
        recorded resolution proof -- not just a free-text ``reason`` string. A caller
        can no longer reopen an arbitrary exhausted/failed task on its own say-so; the
        grant must point at the specific real recovery event (the genuine approval/
        resolution) that justifies retrying this exact task, reusing the existing
        external-checkpoint resolution record rather than inventing a second proof
        mechanism.
        """
        if actor != "coordinator" and not actor.startswith("human:"):
            raise RuntimeFailure("UNTRUSTED_RESOLUTION", "attempt grant requires a human or coordinator actor")
        # NOTE (F7, documentation-only): this is a plain string-prefix check with no
        # cryptographic or external proof binding the caller to the claimed identity --
        # this runtime's security boundary is "the local CLI/caller invoking it is already
        # the single trusted operator", the same boundary every other local mutation in this
        # module relies on. It is not, and is not intended to be, protection against an
        # untrusted multi-tenant caller forging an `actor` string. If this runtime is ever
        # exposed to a caller that is not already fully trusted, this check (and every other
        # `actor=` parameter in this file) needs real authentication, not a bigger version of
        # this same string check.
        if not reason.strip():
            raise RuntimeFailure("INVALID_REASON", "attempt grant requires a non-empty reason")
        require_id(checkpoint_id, "recovery checkpoint id")

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            task = find_task(state, task_id)
            if task["status"] in {"RUNNING", "COMPLETED", "CANCELLED"}:
                raise RuntimeFailure("TASK_NOT_GRANTABLE", f"task {task_id} is {task['status']}")
            if task["attempts"] < task["retryPolicy"]["maxAttempts"]:
                raise RuntimeFailure("ATTEMPT_NOT_EXHAUSTED", f"task {task_id} has not exhausted its current attempt budget")
            checkpoint = next(
                (item for item in state["externalCheckpoints"] if item["id"] == checkpoint_id),
                None,
            )
            if checkpoint is None:
                raise RuntimeFailure("EXTERNAL_CHECKPOINT_NOT_FOUND", f"checkpoint not found: {checkpoint_id}")
            if checkpoint.get("resumeTask") != task_id:
                raise RuntimeFailure(
                    "RECOVERY_CHECKPOINT_MISMATCH",
                    f"checkpoint {checkpoint_id} is not bound to task {task_id}",
                )
            if checkpoint["status"] != "RESOLVED" or not checkpoint.get("resolutionRef"):
                raise RuntimeFailure(
                    "RECOVERY_CHECKPOINT_UNRESOLVED",
                    f"checkpoint {checkpoint_id} has no recorded resolution proof; unresolved side effects stay denied",
                )
            # (F7) The checkpoint must represent a genuine interruption of an
            # in-flight attempt, not merely a resolved approval created at an
            # arbitrary point (e.g. before the task ever started). A checkpoint
            # created while the task was not actually RUNNING recorded no
            # interrupted attempt and can never justify a recovery grant.
            interrupted_attempt = checkpoint.get("interruptedAttempt")
            if interrupted_attempt is None:
                raise RuntimeFailure(
                    "RECOVERY_CHECKPOINT_NOT_AN_INTERRUPTION",
                    f"checkpoint {checkpoint_id} was not created while task {task_id} was actually running; "
                    "there is no eligible interrupted attempt to recover",
                )
            if checkpoint.get("recoveryGrantConsumed"):
                # (F7) A stale/replayed grant: this exact resolved checkpoint
                # already backed one attempt grant. Reusing it a second time
                # would let one genuine recovery event justify an unbounded
                # number of extra attempts; a NEW exhaustion needs its own NEW
                # checkpoint/resolution, not a replay of an old one. Checked
                # before staleness below, since an already-consumed checkpoint
                # is invalid for this reason regardless of current attempts.
                raise RuntimeFailure(
                    "RECOVERY_GRANT_ALREADY_CONSUMED",
                    f"checkpoint {checkpoint_id} already granted a recovery attempt and cannot be reused",
                )
            # And the task must not have executed any FURTHER attempt since
            # that interruption: if it has (e.g. it resumed normally and
            # later failed again on its own retry policy, unrelated to the
            # original interruption), this checkpoint no longer describes
            # the task's current situation and must not be replayed to
            # excuse that separate, ordinary failure.
            if task["attempts"] != interrupted_attempt:
                raise RuntimeFailure(
                    "RECOVERY_CHECKPOINT_STALE",
                    f"task {task_id} has executed further attempts since checkpoint {checkpoint_id}'s "
                    f"interruption (interrupted at attempt {interrupted_attempt}, now at attempt "
                    f"{task['attempts']}); this checkpoint cannot justify a recovery grant for that attempt",
                )
            checkpoint["recoveryGrantConsumed"] = True
            task["retryPolicy"]["maxAttempts"] += 1
            if task["status"] == "FAILED":
                task["status"] = "READY" if dependencies_completed(state, task) else "NOT_READY"
            task["retryNotBefore"] = None
            refresh_task_readiness(state)
            state["status"] = derive_run_status(state)
            return {
                "taskId": task_id,
                "maxAttempts": task["retryPolicy"]["maxAttempts"],
                "reason": reason,
                "checkpointId": checkpoint_id,
            }

        return self._transaction(
            run_id,
            mutate,
            event_type="task.attempt_granted",
            actor=actor,
            task_id=task_id,
        )

    def grant_resume_attempt(
        self, run_id: str, task_id: str, *, reason: str, actor: str = "coordinator",
    ) -> dict[str, Any]:
        """Recover exactly one genuine resume-requeued attempt, without consent fiction.

        A supported resume requeues RUNNING tasks and consumes their original
        attempt. That is not an external approval interruption. Bind a bounded
        grant to the authenticated resume event; it cannot recover ordinary
        failed tasks, uncertain side effects, or replay the same interruption.
        """
        if actor != "coordinator" or not reason.strip():
            raise RuntimeFailure("UNTRUSTED_RESOLUTION", "resume recovery requires coordinator and reason")

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            self._assert_repository_baseline(state)
            task = find_task(state, task_id)
            if task["status"] != "READY" or task["attempts"] != task["retryPolicy"]["maxAttempts"]:
                raise RuntimeFailure("TASK_NOT_GRANTABLE", "only an exhausted READY task can recover a resume")
            if task.get("sideEffect") and task["sideEffect"]["state"] in {"PENDING", "UNCERTAIN"}:
                raise RuntimeFailure("RECONCILIATION_REQUIRED", "uncertain side effects cannot recover by retry")
            events = self._read_events(self.run_dir(run_id))
            resumes = [
                event for event in events if event["type"] == "run.resumed"
                and task_id in event["payload"].get("recoveredTasks", [])
            ]
            if not resumes:
                raise RuntimeFailure("RESUME_RECOVERY_REQUIRED", "no authenticated task interruption by resume")
            resume = resumes[-1]
            later = [event for event in events if event["sequence"] > resume["sequence"]]
            if any(
                event.get("taskId") == task_id
                and event["type"] in {"task.started", "task.resume_attempt_granted", "task.failed"}
                for event in later
            ):
                raise RuntimeFailure("RESUME_RECOVERY_CONSUMED", "resume interruption is stale or already consumed")
            task["retryPolicy"]["maxAttempts"] += 1
            return {"taskId": task_id, "maxAttempts": task["retryPolicy"]["maxAttempts"],
                    "resumeSequence": resume["sequence"], "reason": reason}

        return self._transaction(
            run_id, mutate, event_type="task.resume_attempt_granted", actor=actor, task_id=task_id,
        )

    def _cross_run_mutation_conflicts(self, current_run_id: str, mutable_paths: Sequence[str]) -> list[str]:
        conflicts: list[str] = []
        if not self.runs_root.is_dir():
            return conflicts
        for run_dir in self.runs_root.iterdir():
            if run_dir.name == current_run_id or not (run_dir / "run.json").is_file():
                continue
            try:
                # Resource ownership is authenticated canonical state, not
                # historical artifact availability. Missing old gate files
                # must not globally deadlock new development. Still validate
                # schema, event HMAC chain and stateHash; never trust raw JSON.
                with FileLock(run_dir / ".run.lock"):
                    _, other = self._load_locked(run_dir.name, verify_artifacts=False)
            except RuntimeFailure as exc:
                raise RuntimeFailure(
                    "RESOURCE_STATE_UNREADABLE",
                    f"cannot validate active resource leases for Run {run_dir.name}",
                    details={"cause": exc.code},
                ) from exc
            for task in other["tasks"]:
                if task["status"] == "RUNNING" and task["mutablePaths"] and mutable_scopes_overlap(mutable_paths, task["mutablePaths"]):
                    conflicts.append(f"{run_dir.name}:{task['id']}")
        return conflicts

    def _apply_task_retry_or_terminate(self, state: dict[str, Any], task: dict[str, Any], reason: str) -> None:
        """Honor a task's declared retryPolicy on failure instead of always terminating it.

        A failure is retried (task returns to READY/NOT_READY, subject to backoffSeconds) only
        when attempts remain and the reason is retryable (an empty `retryable` list means every
        reason is retryable, matching the permissive default already produced by add_task).
        Otherwise the task becomes terminally FAILED, exactly as before this fix.
        """
        policy = task["retryPolicy"]
        retryable = not policy["retryable"] or reason in policy["retryable"]
        if retryable and task["attempts"] < policy["maxAttempts"]:
            task["status"] = "READY" if dependencies_completed(state, task) else "NOT_READY"
            backoff = max(0.0, float(policy["backoffSeconds"]))
            if backoff:
                retry_at = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=backoff)
                # isoformat(timespec="seconds") truncates sub-second precision, which could
                # round the persisted deadline *down* to a moment at or before "now" and let
                # start_task's RETRY_BACKOFF check pass immediately -- bypassing the declared
                # backoff window. Ceil to the next whole second instead, so the stored
                # retryNotBefore is never earlier than the true intended deadline.
                if retry_at.microsecond:
                    retry_at = (retry_at + dt.timedelta(seconds=1)).replace(microsecond=0)
                task["retryNotBefore"] = retry_at.isoformat(timespec="seconds").replace("+00:00", "Z")
            else:
                task["retryNotBefore"] = None
        else:
            task["status"] = "FAILED"
            task["retryNotBefore"] = None

    def finish_worker(
        self,
        run_id: str,
        task_id: str,
        *,
        worker_id: str,
        status: str,
        artifact_refs: Sequence[str] = (),
    ) -> dict[str, Any]:
        if status not in {"FINISHED", "FAILED"}:
            raise RuntimeFailure("INVALID_WORKER_RESULT", "worker status must be FINISHED or FAILED")

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            self._assert_repository_baseline(state)
            task = find_task(state, task_id)
            if task["status"] != "RUNNING" or not task["lease"] or task["lease"]["owner"] != worker_id:
                raise RuntimeFailure("WORKER_OWNERSHIP", "worker does not own the running task")
            if parse_iso(task["lease"]["expiresAt"]) <= dt.datetime.now(dt.UTC):
                raise RuntimeFailure(
                    "WORKER_LEASE_EXPIRED",
                    "worker completion reported after its lease expired",
                    details={"taskId": task_id, "workerId": worker_id},
                )
            worker = next((item for item in state["workers"] if item["id"] == worker_id), None)
            if worker is None:
                raise RuntimeFailure("WORKER_OWNERSHIP", "worker is not registered")
            worker["status"] = status
            task["lease"] = None
            if status == "FAILED":
                if task["sideEffect"] and task["sideEffect"]["state"] == "PENDING":
                    task["sideEffect"]["state"] = "UNCERTAIN"
                    task["status"] = "WAITING_RESOURCE"
                    append_checkpoint(state, task_id, "SIDE_EFFECT_AMBIGUITY")
                else:
                    self._apply_task_retry_or_terminate(state, task, "WORKER_FAILURE")
            else:
                task["status"] = "WAITING_RESOURCE"
                append_checkpoint(state, task_id, "WORKER_COMPLETION")
            state["status"] = derive_run_status(state)
            return {
                "taskId": task_id,
                "workerId": worker_id,
                "candidateStatus": status,
                "taskStatus": task["status"],
            }

        return self._transaction(
            run_id,
            mutate,
            event_type="worker.finished",
            actor=f"worker:{worker_id}",
            task_id=task_id,
            evidence_refs=artifact_refs,
        )

    def complete_task(
        self,
        run_id: str,
        task_id: str,
        *,
        evidence_refs: Sequence[str],
        actor: str = "coordinator",
    ) -> dict[str, Any]:
        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            self._assert_repository_baseline(state)
            task = find_task(state, task_id)
            # A task may only be completed once its owning worker has actually reported
            # finishing (finish_worker transitions it to WAITING_RESOURCE and releases the
            # lease) or it has otherwise reached that same legal waiting state through
            # reconciliation. Accepting completion while still RUNNING would let anyone with
            # runtime access -- including the worker itself, e.g. via the CLI -- complete a
            # task out from under its own in-flight execution, bypassing every post-execution
            # validation execute_work_packet performs.
            if task["status"] != "WAITING_RESOURCE":
                raise RuntimeFailure("TASK_NOT_COMPLETABLE", f"task {task_id} is {task['status']}")
            if task["sideEffect"] is not None and task["sideEffect"]["state"] != "CONFIRMED":
                raise RuntimeFailure("RECONCILIATION_REQUIRED", "task side effect must be confirmed before completion")
            if any(result["taskId"] == task_id and result["status"] == "FAIL" for result in state["gateResults"]):
                raise RuntimeFailure("DETERMINISTIC_FAILURE", "a failed gate blocks task completion")
            referenced_gates = [
                result
                for result in state["gateResults"]
                if f"gate:{result['id']}" in evidence_refs
            ]
            if not referenced_gates or any(
                result["status"] != "PASS"
                or result["taskId"] != task_id
                or not set(task["acceptanceCriteria"]).intersection(result["criteria"])
                for result in referenced_gates
            ):
                raise RuntimeFailure("GATE_REQUIRED", "task completion requires a task-bound PASS gate reference")
            missing_artifacts = [
                requirement
                for requirement in task["requiredArtifacts"]
                if not any(
                    (artifact["id"] == requirement or artifact["kind"] == requirement)
                    and f"task:{task_id}" in artifact["evidenceRefs"]
                    for artifact in state["artifacts"]
                )
            ]
            if missing_artifacts:
                raise RuntimeFailure(
                    "ARTIFACT_REQUIRED",
                    "task required artifacts are missing",
                    details={"requirements": missing_artifacts},
                )
            task["status"] = "COMPLETED"
            task["lease"] = None
            if task["checkpointPolicy"]["afterCompletion"]:
                append_checkpoint(state, task_id, "TASK_COMPLETION")
            newly_ready = refresh_task_readiness(state)
            if state["autonomy"]["scope"] == "current-task" and newly_ready:
                state["status"] = "PAUSED"
            else:
                state["status"] = derive_run_status(state)
            return {
                "taskId": task_id,
                "newlyReady": newly_ready,
                "automaticTransition": state["autonomy"]["scope"] == "approved-program",
            }

        return self._transaction(
            run_id,
            mutate,
            event_type="task.completed",
            actor=actor,
            task_id=task_id,
            evidence_refs=evidence_refs,
        )

    def fail_task(self, run_id: str, task_id: str, reason: str, actor: str = "coordinator") -> dict[str, Any]:
        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            self._assert_repository_baseline(state)
            task = find_task(state, task_id)
            if task["status"] in TERMINAL_TASK_STATUSES:
                raise RuntimeFailure("TASK_TERMINAL", f"task {task_id} is already terminal")
            task["lease"] = None
            if task["sideEffect"] and task["sideEffect"]["state"] == "PENDING":
                task["sideEffect"]["state"] = "UNCERTAIN"
                task["status"] = "WAITING_RESOURCE"
                append_checkpoint(state, task_id, "SIDE_EFFECT_AMBIGUITY")
            else:
                self._apply_task_retry_or_terminate(state, task, reason)
            state["status"] = derive_run_status(state)
            return {"taskId": task_id, "reason": reason, "taskStatus": task["status"]}

        return self._transaction(run_id, mutate, event_type="task.failed", actor=actor, task_id=task_id)

    def record_gate(
        self,
        run_id: str,
        *,
        gate_id: str,
        task_id: str | None,
        gate_type: str,
        status: str,
        evidence_refs: Sequence[str],
        family: str | None = None,
        criteria: Sequence[str] | None = None,
        surface: str | None = None,
        actor: str = "coordinator",
    ) -> dict[str, Any]:
        require_id(gate_id, "gate id")
        if gate_type not in {"deterministic", "e2e", "semantic", "reality", "policy", "security"}:
            raise RuntimeFailure("INVALID_GATE", f"invalid gate type: {gate_type}")
        if family not in {None, "gpt", "claude", "security"}:
            raise RuntimeFailure("INVALID_GATE", f"invalid gate family: {family}")
        if gate_type == "semantic" and family not in {"gpt", "claude"}:
            raise RuntimeFailure("INVALID_GATE", "semantic gates require gpt or claude family")
        if gate_type == "security" and family not in {None, "security"}:
            raise RuntimeFailure("INVALID_GATE", "security gate family must be security")
        if status not in {"PASS", "FAIL", "BLOCKED", "SKIPPED"}:
            raise RuntimeFailure("INVALID_GATE", f"invalid gate status: {status}")

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            if any(result["id"] == gate_id for result in state["gateResults"]):
                raise RuntimeFailure("GATE_EXISTS", f"gate result already exists: {gate_id}")
            if task_id is not None:
                task = find_task(state, task_id)
                bound_criteria = list(criteria or task["acceptanceCriteria"])
            else:
                blocking_criteria = [item["id"] for item in state["acceptanceCriteria"] if item["blocking"]]
                # A taskless reality/e2e gate has no task to inherit its acceptance criteria
                # from. Defaulting to "every currently blocking criterion" is only unambiguous
                # when there is a single blocking criterion; with more than one, it silently let
                # one surface's legibility run stand in as proof for criteria it never
                # exercised. Require the caller to name exactly which criteria this gate proves
                # whenever that default would otherwise be ambiguous.
                if gate_type in {"reality", "e2e"} and not criteria and len(blocking_criteria) > 1:
                    raise RuntimeFailure(
                        "GATE_BINDING_REQUIRED",
                        "a taskless reality/e2e gate must explicitly bind to specific acceptance "
                        "criteria when more than one blocking criterion exists",
                    )
                bound_criteria = list(criteria or blocking_criteria)
            known_criteria = {item["id"] for item in state["acceptanceCriteria"]}
            if not bound_criteria or not set(bound_criteria).issubset(known_criteria):
                raise RuntimeFailure("INVALID_GATE", "gate must bind to known acceptance criteria")
            criteria_by_id = {criterion["id"]: criterion for criterion in state["acceptanceCriteria"]}
            if status == "PASS":
                require_evidence_refs(state, evidence_refs, allowed={"artifact", "external"})
                artifact_ids = [reference.split(":", 1)[1] for reference in evidence_refs if reference.startswith("artifact:")]
                if task_id is not None and any(
                    f"task:{task_id}" not in artifact["evidenceRefs"]
                    for artifact in state["artifacts"]
                    if artifact["id"] in artifact_ids
                ):
                    raise RuntimeFailure("EVIDENCE_REPLAY", "PASS gate artifact is not bound to this task")
                producers = {
                    artifact["producer"]
                    for artifact in state["artifacts"]
                    if artifact["id"] in artifact_ids
                }
                if not producers or not producers.issubset(GATE_EVIDENCE_PRODUCERS[gate_type]):
                    raise RuntimeFailure(
                        "EVIDENCE_PROVENANCE",
                        "PASS gate evidence has an untrusted producer",
                        details={"gateType": gate_type, "producers": sorted(producers)},
                    )
                # (F2/F7) A PASS gate's own "sourceCommit" stamp (below) records only
                # what commit was current WHEN THIS GATE was registered -- it proves
                # nothing about whether the referenced artifact was actually produced
                # against that same source. Without this check, ANY producer's
                # artifact recorded under an earlier baseline (not just a
                # deterministic test-suite receipt, but a semantic/security/policy
                # review verdict or a reality target-repair receipt too) could be
                # replayed as evidence for a brand-new gate registered after
                # `resume(accept_commit=True)` moved the baseline, stamping stale
                # evidence as fresh proof for the new commit. Require every
                # referenced artifact -- for every gate type -- to independently
                # declare the CURRENT baseline commit as its own recorded source, not
                # merely be referenced here. This governs gate EVIDENCE artifacts
                # only; it is unrelated to -- and never invalidates -- an
                # already-granted human spec approval, which has its own
                # commit-independent signature/hash scheme.
                current_commit = state["baseline"].get("commit")
                stale = sorted(
                    artifact["id"]
                    for artifact in state["artifacts"]
                    if artifact["id"] in artifact_ids and artifact.get("sourceCommit") != current_commit
                )
                if stale:
                    raise RuntimeFailure(
                        "EVIDENCE_STALE_COMMIT",
                        f"{gate_type} PASS gate evidence was not produced against the current baseline commit",
                        details={"artifacts": stale, "baseline": current_commit},
                    )
                if gate_type == "semantic":
                    for artifact in state["artifacts"]:
                        if artifact["id"] not in artifact_ids:
                            continue
                        verdict = self._read_json_receipt(artifact["path"], "semantic")
                        if verdict.get("family") != family or not set(bound_criteria).issubset(set(verdict.get("criteria") or [])):
                            raise RuntimeFailure("SEMANTIC_RECEIPT", "semantic gate does not match verdict family/criteria")
                if gate_type in {"security", "policy"}:
                    label = "security" if gate_type == "security" else "policy"
                    failure_code = "SECURITY_RECEIPT" if gate_type == "security" else "POLICY_RECEIPT"
                    for artifact in state["artifacts"]:
                        if artifact["id"] not in artifact_ids:
                            continue
                        verdict = self._read_json_receipt(artifact["path"], label)
                        if not verdict_status_allows_pass(verdict.get("status")):
                            raise RuntimeFailure(
                                failure_code,
                                f"{gate_type} gate does not match a PASS/APPROVED verdict",
                                details={"artifact": artifact["id"], "status": verdict.get("status")},
                            )
                        if not set(bound_criteria).issubset(set(verdict.get("criteria") or [])):
                            raise RuntimeFailure(
                                failure_code,
                                f"{gate_type} gate does not match verdict criteria",
                                details={"artifact": artifact["id"], "criteria": verdict.get("criteria")},
                            )
                # This block must trigger whenever EITHER a target-repair producer
                # artifact is bound OR any bound criterion itself declares targetEvidence
                # ownership -- not only the former. A criterion that owns targetEvidence
                # but is satisfied solely by a different reality-gate producer (e.g.
                # "external-proof", "mutation", or "legibility" -- all independently
                # trusted for OTHER reality/e2e purposes) must still be rejected here,
                # never silently skipped because no target-repair artifact happened to
                # be present. Gating this solely on `"target-repair" in producers` would
                # let a *-target-repair-verified criterion be satisfied by untyped
                # external-proof evidence that was never validated against the
                # criterion's own kind/purpose/specHash at all.
                any_criterion_owns_target_evidence = any(
                    criteria_by_id[cid].get("targetEvidence") is not None for cid in bound_criteria
                )
                if gate_type in {"reality", "e2e"} and (
                    producers.intersection({"target-repair", "target-experiment"})
                    or any_criterion_owns_target_evidence
                ):
                    target_declarations = {
                        cid: criteria_by_id[cid].get("targetEvidence")
                        for cid in bound_criteria
                    }
                    if any(declaration is None for declaration in target_declarations.values()):
                        raise RuntimeFailure(
                            "EVIDENCE_BINDING_REQUIRED",
                            "criteria bound to target-repair evidence must declare targetEvidence ownership explicitly",
                        )
                    target_producers = {"target-repair", "target-experiment"}
                    artifact_summaries = {
                        artifact["id"]: self._read_json_receipt(artifact["path"], "target-repair evidence")
                        for artifact in state["artifacts"]
                        if artifact["id"] in artifact_ids and artifact["producer"] in target_producers
                    }
                    for artifact in state["artifacts"]:
                        if artifact["id"] not in artifact_ids or artifact["producer"] not in target_producers:
                            continue
                        summary = artifact_summaries[artifact["id"]]
                        summary_purpose = summary.get("purpose")
                        for declaration in target_declarations.values():
                            if declaration is None:
                                continue
                            if artifact["kind"] != declaration["kind"]:
                                continue
                            if summary_purpose != declaration["purpose"]:
                                continue
                            if summary.get("specHash") != declaration["targetSpecHash"]:
                                raise RuntimeFailure(
                                    "EVIDENCE_SPEC_MISMATCH",
                                    "target-repair evidence specHash does not match the criterion-owned target spec",
                                )
                    for declaration in target_declarations.values():
                        if declaration is None:
                            continue
                        if not any(
                            artifact["kind"] == declaration["kind"]
                            and artifact_summaries[artifact["id"]].get("purpose") == declaration["purpose"]
                            and artifact_summaries[artifact["id"]].get("specHash") == declaration["targetSpecHash"]
                            for artifact in state["artifacts"]
                            if artifact["id"] in artifact_ids and artifact["producer"] in target_producers
                        ):
                            raise RuntimeFailure(
                                "EVIDENCE_KIND_MISMATCH",
                                "target-repair evidence kind/purpose/spec does not match the bound criterion",
                            )
                if gate_type in {"reality", "e2e"}:
                    # A reality/e2e PASS gate proves exactly one verification surface (web,
                    # electron, ios, deployment, runtime). Evidence spanning zero or more than
                    # one surface is ambiguous about what was actually verified and must be
                    # rejected rather than silently accepted as proof for whichever criteria the
                    # caller named. `producers` is already validated above to be a subset of
                    # GATE_EVIDENCE_PRODUCERS[gate_type], so every producer here is trusted.
                    def evidence_surface_of(artifact: dict[str, Any]) -> str | None:
                        producer = artifact["producer"]
                        if producer == "legibility":
                            return self._read_json_receipt(artifact["path"], "legibility").get("surface")
                        if producer == "mutation":
                            return "deployment"
                        if producer == "external-proof":
                            return "runtime"
                        if producer == "target-repair":
                            return "runtime"
                        if producer == "target-experiment":
                            return "runtime"
                        return None

                    evidence_surfaces = {
                        evidence_surface_of(artifact)
                        for artifact in state["artifacts"]
                        if artifact["id"] in artifact_ids
                    }
                    if len(evidence_surfaces) != 1 or None in evidence_surfaces:
                        raise RuntimeFailure(
                            "EVIDENCE_SURFACE_AMBIGUOUS",
                            "reality/e2e PASS gate must be backed by evidence for exactly one verification surface",
                        )
                    (evidence_surface,) = evidence_surfaces
                    if surface is not None and surface != evidence_surface:
                        raise RuntimeFailure(
                            "EVIDENCE_SURFACE_MISMATCH",
                            "declared verification surface does not match the evidence",
                            details={"declared": surface, "evidence": evidence_surface},
                        )
                    # The criterion -- not the caller, and not the producer type -- is the
                    # authoritative source of the expected surface here: a caller can simply
                    # omit `surface` to dodge the declared-vs-evidence check above, and a
                    # mutation/external-proof producer is just as capable of being bound to the
                    # wrong criterion as a legibility one. Every derived reality/e2e evidence
                    # surface (web/electron/ios via legibility, deployment via mutation, runtime
                    # via external-proof) must match whatever surface every bound reality/e2e
                    # criterion owns, regardless of which producer backed it.
                    owned_surfaces = {
                        criterion.get("surface")
                        for criterion in state["acceptanceCriteria"]
                        if criterion["id"] in bound_criteria
                        and criterion["verificationType"] in SURFACE_VERIFICATION_TYPES
                        and criterion.get("surface")
                    }
                    if len(owned_surfaces) > 1:
                        raise RuntimeFailure(
                            "EVIDENCE_SURFACE_MISMATCH",
                            "gate is bound to criteria that expect conflicting verification surfaces",
                            details={"surfaces": sorted(owned_surfaces)},
                        )
                    if owned_surfaces:
                        (owned_surface,) = owned_surfaces
                        if owned_surface != evidence_surface:
                            raise RuntimeFailure(
                                "EVIDENCE_SURFACE_MISMATCH",
                                "evidence surface does not match the criterion-owned verification surface",
                                details={"criterion": owned_surface, "evidence": evidence_surface},
                            )
                elif surface is not None:
                    raise RuntimeFailure(
                        "EVIDENCE_SURFACE_MISMATCH",
                        "a verification surface was declared but no matching reality/e2e evidence was supplied",
                    )
                if "mutation" in producers:
                    for artifact in state["artifacts"]:
                        if artifact["id"] not in artifact_ids or artifact["producer"] != "mutation":
                            continue
                        receipt = self._read_json_receipt(artifact["path"], "mutation")
                        if task_id is None or receipt.get("taskId") != task_id or artifact.get("consumedByTask") != task_id:
                            raise RuntimeFailure("EVIDENCE_REPLAY", "mutation PASS gate receipt is not consumed by this task")
                        if receipt.get("result", {}).get("status") != "pass" or receipt.get("result", {}).get("mismatches") != []:
                            raise RuntimeFailure("MUTATION_RECEIPT", "mutation PASS gate requires a fully matching receipt")
            now = utc_now()
            state["gateResults"].append(
                {
                    "id": gate_id,
                    "taskId": task_id,
                    "criteria": list(dict.fromkeys(bound_criteria)),
                    "type": gate_type,
                    "family": family,
                    "status": status,
                    "startedAt": now,
                    "finishedAt": now,
                    "evidenceRefs": list(dict.fromkeys(evidence_refs)),
                    # The exact source snapshot this gate's evidence was
                    # produced against. A later source-changing commit
                    # (``resume(accept_commit=True)``) must not let an
                    # earlier gate recorded against a now-superseded
                    # commit keep being read as current proof -- see the
                    # matching filter in ``missing_gate_requirements``.
                    "sourceCommit": state["baseline"].get("commit"),
                }
            )
            append_checkpoint(state, task_id, "GATE_COMPLETION")
            if status == "FAIL" and gate_type in {"deterministic", "e2e", "reality", "policy", "security"}:
                state["status"] = "FAILED"
            return {"gateId": gate_id, "gateType": gate_type, "family": family, "status": status}

        return self._transaction(
            run_id,
            mutate,
            event_type="gate.passed" if status == "PASS" else "gate.failed" if status == "FAIL" else "gate.recorded",
            actor=actor,
            task_id=task_id,
            evidence_refs=evidence_refs,
        )

    def set_criterion(
        self,
        run_id: str,
        criterion_id: str,
        status: str,
        evidence_refs: Sequence[str],
        actor: str = "coordinator",
    ) -> dict[str, Any]:
        if status not in CRITERION_STATUSES:
            raise RuntimeFailure("INVALID_CRITERION", f"invalid criterion status: {status}")
        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            criterion = next((item for item in state["acceptanceCriteria"] if item["id"] == criterion_id), None)
            if criterion is None:
                raise RuntimeFailure("CRITERION_NOT_FOUND", f"criterion not found: {criterion_id}")
            if status in {"PASS", "NOT_APPLICABLE"}:
                require_evidence_refs(state, evidence_refs, allowed={"gate", "external"})
                for reference in evidence_refs:
                    kind, identifier = reference.split(":", 1)
                    if kind == "gate":
                        gate = next(item for item in state["gateResults"] if item["id"] == identifier)
                        if criterion_id not in gate["criteria"]:
                            raise RuntimeFailure(
                                "EVIDENCE_INVALID",
                                "gate evidence is not bound to this criterion",
                                details={"criterionId": criterion_id, "gateId": identifier},
                            )
                        allowed_gate_types = CRITERION_GATE_TYPES.get(criterion["verificationType"], set())
                        if gate["type"] not in allowed_gate_types:
                            raise RuntimeFailure(
                                "VERIFICATION_TYPE_MISMATCH",
                                "gate type does not satisfy the criterion's declared verificationType",
                                details={
                                    "criterionId": criterion_id,
                                    "verificationType": criterion["verificationType"],
                                    "gateType": gate["type"],
                                },
                            )
                    elif kind == "external":
                        if criterion["verificationType"] != "external":
                            raise RuntimeFailure(
                                "VERIFICATION_TYPE_MISMATCH",
                                "external evidence requires a criterion with verificationType 'external'",
                                details={"criterionId": criterion_id, "verificationType": criterion["verificationType"]},
                            )
                        checkpoint = next(item for item in state["externalCheckpoints"] if item["id"] == identifier)
                        bound_task = find_task(state, checkpoint["taskId"])
                        if criterion_id not in bound_task["acceptanceCriteria"]:
                            raise RuntimeFailure(
                                "EVIDENCE_INVALID",
                                "external checkpoint evidence is not bound to this criterion",
                                details={"criterionId": criterion_id, "checkpointId": identifier},
                            )
            criterion["status"] = status
            criterion["evidenceRefs"] = list(dict.fromkeys(evidence_refs))
            state["status"] = derive_run_status(state)
            return {"criterionId": criterion_id, "status": status}

        return self._transaction(
            run_id,
            mutate,
            event_type="acceptance.updated",
            actor=actor,
            evidence_refs=evidence_refs,
        )

    def wait_external(
        self,
        run_id: str,
        *,
        checkpoint_id: str,
        task_id: str,
        checkpoint_type: str,
        principal: str,
        provider: str,
        reason: str,
        actor: str = "coordinator",
    ) -> tuple[dict[str, Any], str]:
        require_id(checkpoint_id, "external checkpoint id")
        if checkpoint_type not in EXTERNAL_TYPES:
            raise RuntimeFailure("INVALID_EXTERNAL_CHECKPOINT", f"invalid external checkpoint type: {checkpoint_type}")
        challenge = secrets.token_urlsafe(32)
        challenge_hash = hashlib.sha256(challenge.encode("utf-8")).hexdigest()

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            task = find_task(state, task_id)
            if task["status"] in TERMINAL_TASK_STATUSES:
                raise RuntimeFailure("TASK_TERMINAL", "terminal tasks cannot wait externally")
            if any(item["id"] == checkpoint_id for item in state["externalCheckpoints"]):
                raise RuntimeFailure("EXTERNAL_CHECKPOINT_EXISTS", f"checkpoint already exists: {checkpoint_id}")
            # (F7) Record whether this checkpoint actually interrupts a
            # RUNNING attempt, and if so, exactly which one. A checkpoint
            # created while the task was not actually running (e.g. it was
            # PENDING/READY/NOT_READY, or had already failed) is real
            # history but is not an eligible "interruption" a later
            # grant_task_attempt call can recover from -- there was no
            # in-flight attempt it cut short. ``grant_task_attempt`` below
            # refuses a checkpoint with no recorded interrupted attempt.
            interrupted_attempt = task["attempts"] if task["status"] == "RUNNING" else None
            lease = task.get("lease")
            if lease:
                worker = next((item for item in state["workers"] if item["id"] == lease["owner"]), None)
                if worker is not None:
                    worker["status"] = "FINISHED"
            task["status"] = "WAITING_EXTERNAL"
            task["lease"] = None
            state["externalCheckpoints"].append(
                {
                    "id": checkpoint_id,
                    "taskId": task_id,
                    "type": checkpoint_type,
                    "principal": principal,
                    "provider": provider,
                    "reason": reason,
                    "createdAt": utc_now(),
                    "status": "PENDING",
                    "resumeTask": task_id,
                    "challengeHash": challenge_hash,
                    "resolutionRef": None,
                    # (F7) Set exactly once, the first time this checkpoint's
                    # resolution is actually spent to grant a bounded extra task
                    # attempt -- a resolved checkpoint stays RESOLVED forever (it
                    # is real history), but it must not be replayable to justify
                    # an unbounded number of attempt grants.
                    "recoveryGrantConsumed": False,
                    "interruptedAttempt": interrupted_attempt,
                }
            )
            append_checkpoint(state, task_id, "EXTERNAL_WAIT")
            state["status"] = derive_run_status(state)
            return {
                "checkpointId": checkpoint_id,
                "type": checkpoint_type,
                "principal": principal,
                "provider": provider,
            }

        state = self._transaction(
            run_id,
            mutate,
            event_type="external.wait_started",
            actor=actor,
            task_id=task_id,
        )
        return state, challenge

    def reissue_challenge(
        self,
        run_id: str,
        *,
        checkpoint_id: str,
        proof_ref: str,
        actor: str,
    ) -> tuple[dict[str, Any], str]:
        """Reissue a pending external checkpoint's one-time resolution challenge.

        ``wait_external`` deliberately persists only the challenge's hash, never
        the secret itself -- so if the process holding the original challenge is
        lost (e.g. a host/session transition before ``resolve_external`` ran),
        the checkpoint can never be resolved again, even though a genuine
        external-proof artifact already exists. This is the designed recovery
        path for exactly that situation.

        It is deliberately narrow: it requires a trusted coordinator/human actor
        and an ALREADY-REGISTERED, unconsumed external-proof artifact that
        genuinely matches this checkpoint's id/principal/provider -- the same
        binding ``resolve_external`` itself requires -- so it can never manufacture
        approval that was not already real; it only ever re-opens the door for
        evidence that already exists. It never reads or needs the lost token.
        """
        if actor != "coordinator" and not actor.startswith("human:"):
            raise RuntimeFailure("UNTRUSTED_RESOLUTION", "challenge reissue requires a human or coordinator actor")
        require_id(checkpoint_id, "external checkpoint id")
        challenge = secrets.token_urlsafe(32)
        challenge_hash = hashlib.sha256(challenge.encode("utf-8")).hexdigest()

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            checkpoint = next(
                (item for item in state["externalCheckpoints"] if item["id"] == checkpoint_id),
                None,
            )
            if checkpoint is None:
                raise RuntimeFailure("EXTERNAL_CHECKPOINT_NOT_FOUND", f"checkpoint not found: {checkpoint_id}")
            if checkpoint["status"] != "PENDING":
                raise RuntimeFailure("EXTERNAL_CHECKPOINT_TERMINAL", "checkpoint is not pending")
            require_evidence_refs(state, [proof_ref], allowed={"artifact"})
            proof_id = proof_ref.split(":", 1)[1]
            proof_artifact = next(item for item in state["artifacts"] if item["id"] == proof_id)
            if proof_artifact["producer"] != "external-proof":
                raise RuntimeFailure("UNTRUSTED_RESOLUTION", "challenge reissue evidence is not externally attested")
            if proof_artifact.get("consumedByTask") is not None:
                raise RuntimeFailure("EVIDENCE_REPLAY", "external proof was already consumed")
            proof = self._read_json_receipt(proof_artifact["path"], "external")
            if (
                proof.get("checkpointId") != checkpoint_id
                or proof.get("principal") != checkpoint["principal"]
                or proof.get("provider") != checkpoint["provider"]
            ):
                raise RuntimeFailure(
                    "EXTERNAL_PROOF_MISMATCH",
                    "challenge reissue evidence does not bind to this checkpoint's id, principal, and provider",
                )
            checkpoint["challengeHash"] = challenge_hash
            checkpoint["challengeReissuedAt"] = utc_now()
            checkpoint["challengeReissueCount"] = checkpoint.get("challengeReissueCount", 0) + 1
            state["status"] = derive_run_status(state)
            return {"checkpointId": checkpoint_id}

        state = self._transaction(
            run_id,
            mutate,
            event_type="external.challenge_reissued",
            actor=actor,
            evidence_refs=[proof_ref],
        )
        return state, challenge

    def resolve_external(
        self,
        run_id: str,
        *,
        checkpoint_id: str,
        resolution_ref: str,
        challenge: str,
        actor: str,
    ) -> dict[str, Any]:
        if actor != "coordinator" and not actor.startswith("human:"):
            raise RuntimeFailure("UNTRUSTED_RESOLUTION", "external checkpoints require a human or coordinator actor")
        if redact(resolution_ref) != resolution_ref:
            raise RuntimeFailure("SENSITIVE_RESOLUTION", "resolution reference appears to contain secret material")

        task_holder: dict[str, str] = {}

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            checkpoint = next(
                (item for item in state["externalCheckpoints"] if item["id"] == checkpoint_id),
                None,
            )
            if checkpoint is None:
                raise RuntimeFailure("EXTERNAL_CHECKPOINT_NOT_FOUND", f"checkpoint not found: {checkpoint_id}")
            if checkpoint["status"] != "PENDING":
                raise RuntimeFailure("EXTERNAL_CHECKPOINT_TERMINAL", "checkpoint is not pending")
            supplied_hash = hashlib.sha256(challenge.encode("utf-8")).hexdigest()
            if not hmac.compare_digest(checkpoint["challengeHash"], supplied_hash):
                raise RuntimeFailure("UNTRUSTED_RESOLUTION", "external checkpoint challenge is invalid")
            require_evidence_refs(state, [resolution_ref], allowed={"artifact"})
            resolution_id = resolution_ref.split(":", 1)[1]
            resolution_artifact = next(item for item in state["artifacts"] if item["id"] == resolution_id)
            if resolution_artifact["producer"] != "external-proof":
                raise RuntimeFailure("UNTRUSTED_RESOLUTION", "external checkpoint evidence is not externally attested")
            if resolution_artifact.get("consumedByTask") is not None:
                raise RuntimeFailure("EVIDENCE_REPLAY", "external proof was already consumed")
            proof = self._read_json_receipt(resolution_artifact["path"], "external")
            if (
                proof.get("checkpointId") != checkpoint_id
                or proof.get("principal") != checkpoint["principal"]
                or proof.get("provider") != checkpoint["provider"]
            ):
                raise RuntimeFailure(
                    "EXTERNAL_PROOF_MISMATCH",
                    "external proof does not bind to this checkpoint's id, principal, and provider",
                )
            checkpoint["status"] = "RESOLVED"
            checkpoint["resolvedAt"] = utc_now()
            checkpoint["resolvedBy"] = actor
            checkpoint["resolutionRef"] = resolution_ref
            resolution_artifact["consumedByTask"] = checkpoint["resumeTask"]
            resolution_artifact["attestation"] = self._artifact_attestation(resolution_artifact)
            task = find_task(state, checkpoint["resumeTask"])
            outstanding = any(
                other["resumeTask"] == checkpoint["resumeTask"] and other["status"] == "PENDING"
                for other in state["externalCheckpoints"]
                if other["id"] != checkpoint_id
            )
            if not outstanding:
                task["status"] = "READY" if dependencies_completed(state, task) else "NOT_READY"
            task_holder["id"] = task["id"]
            state["status"] = derive_run_status(state)
            return {"checkpointId": checkpoint_id, "resumeTask": task["id"]}

        state = self._transaction(
            run_id,
            mutate,
            event_type="external.wait_resolved",
            actor=actor,
            evidence_refs=[resolution_ref],
        )
        return state

    def reconcile_side_effect(
        self,
        run_id: str,
        task_id: str,
        *,
        result: str,
        evidence_ref: str,
        actor: str = "coordinator",
    ) -> dict[str, Any]:
        if result not in {"applied", "not-applied"}:
            raise RuntimeFailure("INVALID_RECONCILIATION", "result must be applied or not-applied")

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            task = find_task(state, task_id)
            side_effect = task["sideEffect"]
            if side_effect is None or side_effect["state"] != "UNCERTAIN":
                raise RuntimeFailure("RECONCILIATION_NOT_REQUIRED", "task has no uncertain side effect")
            require_evidence_refs(state, [evidence_ref], allowed={"artifact"})
            evidence_id = evidence_ref.split(":", 1)[1]
            artifact = next(item for item in state["artifacts"] if item["id"] == evidence_id)
            expected_producers = (
                {"reconciliation"}
                if result == "not-applied"
                else {"mutation"} if side_effect["operation"] != "edit" else {"workspace"}
            )
            if artifact["producer"] not in expected_producers:
                raise RuntimeFailure("EVIDENCE_PROVENANCE", "side-effect reconciliation evidence has the wrong producer")
            if artifact.get("consumedByTask") is not None:
                raise RuntimeFailure("EVIDENCE_REPLAY", "side-effect receipt was already consumed")
            if artifact["producer"] == "mutation":
                receipt = self._read_json_receipt(artifact["path"], "mutation")
                if (
                    receipt.get("taskId") != task_id
                    or receipt.get("operation") != side_effect["operation"]
                    or receipt.get("target") != side_effect["target"]
                ):
                    raise RuntimeFailure("EVIDENCE_REPLAY", "mutation receipt does not bind to this task side effect")
                if result != "applied":
                    raise RuntimeFailure("RECONCILIATION_CONTRADICTION", "applied mutation receipt cannot prove not-applied")
            elif artifact["producer"] == "reconciliation":
                receipt = self._read_json_receipt(artifact["path"], "reconciliation")
                if (
                    receipt.get("taskId") != task_id
                    or receipt.get("operation") != side_effect["operation"]
                    or receipt.get("target") != side_effect["target"]
                    or receipt.get("outcome") != "not-applied"
                ):
                    raise RuntimeFailure("EVIDENCE_REPLAY", "reconciliation receipt does not bind to this task/outcome")
            elif f"task:{task_id}" not in artifact["evidenceRefs"]:
                raise RuntimeFailure("EVIDENCE_REPLAY", "workspace receipt does not bind to this task")
            elif result != "applied":
                raise RuntimeFailure("RECONCILIATION_CONTRADICTION", "applied workspace receipt cannot prove not-applied")
            artifact["consumedByTask"] = task_id
            artifact["attestation"] = self._artifact_attestation(artifact)
            side_effect["state"] = "CONFIRMED" if result == "applied" else "NONE"
            side_effect["reconciliation"] = evidence_ref
            task["status"] = "WAITING_RESOURCE" if result == "applied" else "READY"
            state["status"] = derive_run_status(state)
            return {"taskId": task_id, "result": result}

        return self._transaction(
            run_id,
            mutate,
            event_type="mutation.reconciled",
            actor=actor,
            task_id=task_id,
            evidence_refs=[evidence_ref],
        )

    def prepare_side_effect(
        self,
        run_id: str,
        task_id: str,
        *,
        operation: str,
        target: str,
        confirmed: bool = False,
        actor: str = "coordinator",
    ) -> dict[str, Any]:
        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            self._assert_repository_baseline(state)
            task = find_task(state, task_id)
            if task["status"] not in {"RUNNING", "WAITING_RESOURCE"}:
                raise RuntimeFailure("SIDE_EFFECT_NOT_READY", "side effect task must be running or awaiting coordinator validation")
            require_mutation_allowed(state, target, operation, confirmed=confirmed)
            side_effect = task.get("sideEffect")
            if side_effect is None:
                side_effect = {
                    "operation": operation,
                    "target": target,
                    "state": "NONE",
                    "reconciliation": None,
                }
                task["sideEffect"] = side_effect
            if side_effect["operation"] != operation or side_effect["target"] != target:
                raise RuntimeFailure("SIDE_EFFECT_SCOPE", "side effect differs from the task's authorized operation/target")
            if side_effect["state"] not in {"NONE", "PENDING"}:
                raise RuntimeFailure("RECONCILIATION_REQUIRED", "side effect is already uncertain or confirmed")
            side_effect["state"] = "UNCERTAIN"
            append_checkpoint(state, task_id, "SIDE_EFFECT_AMBIGUITY")
            return {"taskId": task_id, "operation": operation, "target": target}

        return self._transaction(
            run_id,
            mutate,
            event_type="mutation.started",
            actor=actor,
            task_id=task_id,
        )

    def policy_check(
        self,
        run_id: str,
        scope: str,
        operation: str,
        *,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        state = self.load(run_id)
        decision = mutation_decision(state, scope, operation, confirmed=confirmed)
        event_type = "mutation.allowed" if decision["status"] == "allowed" else "mutation.denied"

        def no_mutation(run: dict[str, Any]) -> dict[str, Any]:
            return decision

        self._transaction(run_id, no_mutation, event_type=event_type, actor="coordinator")
        return decision

    def resume(self, run_id: str, *, accept_commit: bool = False, actor: str = "coordinator") -> dict[str, Any]:
        identity = self.repository_identity()

        current = self.load(run_id)
        drift = {
            key: {"expected": current["baseline"].get(key), "actual": identity.get(key)}
            for key in ("commit", "branch")
            if current["baseline"].get(key) != identity.get(key)
        }
        if drift and not accept_commit:
            def pause(state: dict[str, Any]) -> dict[str, Any]:
                state["status"] = "PAUSED"
                return {"reason": "stale-repository", "drift": drift}

            self._transaction(run_id, pause, event_type="run.paused", actor=actor)
            raise RuntimeFailure("STALE_REPOSITORY", "repository baseline drift requires reconciliation", details=drift)

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            if Path(state["baseline"]["repository"]).resolve() != self.repository:
                raise RuntimeFailure("STALE_REPOSITORY", "Run belongs to a different repository")
            if drift:
                state["baseline"]["commit"] = identity["commit"]
                state["baseline"]["branch"] = identity["branch"]
            recovered: list[str] = []
            uncertain: list[str] = []
            for task in state["tasks"]:
                if task["status"] != "RUNNING":
                    continue
                lease = task.get("lease")
                if lease:
                    worker = next((item for item in state["workers"] if item["id"] == lease["owner"]), None)
                    if worker is not None:
                        worker["status"] = "FAILED"
                task["lease"] = None
                if task["sideEffect"] and task["sideEffect"]["state"] in {"PENDING", "UNCERTAIN"}:
                    task["sideEffect"]["state"] = "UNCERTAIN"
                    task["status"] = "WAITING_RESOURCE"
                    append_checkpoint(state, task["id"], "SIDE_EFFECT_AMBIGUITY")
                    uncertain.append(task["id"])
                else:
                    task["status"] = "READY" if dependencies_completed(state, task) else "NOT_READY"
                    recovered.append(task["id"])
            refresh_task_readiness(state)
            state["status"] = derive_run_status(state)
            if state["status"] == "PAUSED" and state["autonomy"]["scope"] == "current-task":
                state["status"] = "RUNNING" if any(task["status"] == "READY" for task in state["tasks"]) else state["status"]
            return {"recoveredTasks": recovered, "uncertainSideEffects": uncertain, "baselineDriftAccepted": bool(drift)}

        return self._transaction(run_id, mutate, event_type="run.resumed", actor=actor)

    def verify(self, run_id: str, actor: str = "coordinator") -> tuple[dict[str, Any], bool]:
        outcome: dict[str, Any] = {}

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            required = [criterion for criterion in state["acceptanceCriteria"] if criterion["blocking"]]
            deterministic_failures = [
                gate["id"]
                for gate in state["gateResults"]
                if gate["status"] == "FAIL" and gate["type"] in {"deterministic", "e2e", "reality", "policy", "security"}
            ]
            failed = [criterion["id"] for criterion in required if criterion["status"] == "FAIL"]
            untested = [criterion["id"] for criterion in required if criterion["status"] == "UNTESTED"]
            blocked = [criterion["id"] for criterion in required if criterion["status"] == "BLOCKED_EXTERNAL"]
            missing_evidence = [
                criterion["id"]
                for criterion in required
                if criterion["status"] in {"PASS", "NOT_APPLICABLE"}
                and (
                    not criterion["evidenceRefs"]
                    or any(evidence_ref_kind(state, reference) is None for reference in criterion["evidenceRefs"])
                )
            ]
            incomplete_tasks = [
                task["id"] for task in state["tasks"] if task["status"] not in {"COMPLETED", "SKIPPED"}
            ]
            pending_external = [
                checkpoint["id"]
                for checkpoint in state["externalCheckpoints"]
                if checkpoint["status"] == "PENDING"
            ]
            high_risk = [criterion for criterion in required if criterion["risk"] in {"R3", "R4"}]
            passed_real_gates = {
                gate["type"]
                for gate in state["gateResults"]
                if gate["status"] == "PASS" and gate["type"] in {"e2e", "reality"}
            }
            missing_reality = bool(high_risk and not passed_real_gates)
            missing_risk_gates = missing_gate_requirements(state, required)

            if deterministic_failures or failed or missing_evidence:
                state["status"] = "FAILED"
            elif blocked or pending_external:
                state["status"] = "WAITING_EXTERNAL"
            elif untested or incomplete_tasks or missing_reality or missing_risk_gates:
                state["status"] = "VERIFYING"
            else:
                state["status"] = "COMPLETED"
            outcome.update(
                {
                    "status": state["status"],
                    "deterministicFailures": deterministic_failures,
                    "failedCriteria": failed,
                    "untestedCriteria": untested,
                    "blockedExternalCriteria": blocked,
                    "missingEvidence": missing_evidence,
                    "incompleteTasks": incomplete_tasks,
                    "pendingExternalCheckpoints": pending_external,
                    "missingRealityGate": missing_reality,
                    "missingRiskGates": missing_risk_gates,
                }
            )
            return outcome

        state = self._transaction(
            run_id,
            mutate,
            event_type="run.verifying",
            actor=actor,
        )
        completed = state["status"] == "COMPLETED"
        if completed:
            state = self._transaction(
                run_id,
                lambda _: {"outcome": "satisfied"},
                event_type="run.completed",
                actor=actor,
            )
        return state, completed

    def migrate_v1(self, summary_path: Path, *, run_id: str | None = None) -> dict[str, Any]:
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeFailure("V1_INVALID", f"cannot read v1 summary: {summary_path}") from exc
        if summary.get("schema") != "architrave.run.v1":
            raise RuntimeFailure("V1_INVALID", "input is not an architrave.run.v1 summary")
        migrated_id = run_id or f"{summary.get('runId', 'run')}-v2"
        self.create(
            goal=f"Migrated v1 Run {summary.get('runId', 'unknown')}",
            outcome="Preserve the legacy Run as durable v2 state without claiming new verification.",
            criteria=[
                {
                    "id": "MIGRATION-001",
                    "description": "Legacy phases are represented in Run v2.",
                    "scope": "migration",
                    "risk": "R0",
                    "verificationType": "deterministic",
                    "status": "UNTESTED",
                    "evidenceRefs": [],
                    "blocking": True,
                }
            ],
            autonomy_scope="advisory-only",
            run_id=migrated_id,
        )
        previous_task: str | None = None
        legacy_statuses: dict[str, str] = {}
        for index, phase in enumerate(summary.get("phases") or [], start=1):
            task_id = f"legacy-{index}"
            self.add_task(
                migrated_id,
                {
                    "id": task_id,
                    "title": str(phase.get("name") or f"Legacy phase {index}"),
                    "objective": str(phase.get("scope") or "Preserve legacy phase state."),
                    "dependencies": [previous_task] if previous_task else [],
                    "workerProfile": "shell",
                    "risk": "R0",
                    "acceptanceCriteria": ["MIGRATION-001"],
                    "requiredArtifacts": [],
                    "gate": str(phase.get("gate") or "legacy projection"),
                },
            )
            legacy_statuses[task_id] = str(phase.get("status") or "not-started")
            previous_task = task_id

        status_map = {
            "not-started": "NOT_READY",
            "in-progress": "READY",
            "blocked": "WAITING_RESOURCE",
            "completed": "COMPLETED",
            "skipped": "SKIPPED",
        }

        def preserve_statuses(run: dict[str, Any]) -> dict[str, Any]:
            for task in run["tasks"]:
                task["status"] = status_map.get(legacy_statuses[task["id"]], "NOT_READY")
            run["status"] = derive_run_status(run)
            return {"sourceSchema": "architrave.run.v1", "phaseStatuses": legacy_statuses}

        return self._transaction(
            migrated_id,
            preserve_statuses,
            event_type="run.migrated",
            actor="coordinator",
        )


def normalize_policy_allow(entries: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for entry in entries:
        scope = str(entry.get("scope") or "").strip()
        operations = tuple(dict.fromkeys(str(item).strip() for item in entry.get("operations", []) if str(item).strip()))
        if not scope or not operations:
            raise RuntimeFailure("INVALID_POLICY", "policy allows require scope and operations")
        key = (scope, operations)
        if key not in seen:
            result.append({"scope": scope, "operations": list(operations)})
            seen.add(key)
    return result


def normalize_criteria(criteria: Sequence[dict[str, Any]], outcome: str) -> list[dict[str, Any]]:
    if not criteria:
        criteria = [
            {
                "id": "OUTCOME-001",
                "description": outcome.strip(),
                "scope": "program",
                "risk": "R1",
                "verificationType": "deterministic",
                "status": "UNTESTED",
                "evidenceRefs": [],
                "blocking": True,
            }
        ]
    normalized: list[dict[str, Any]] = []
    ids: set[str] = set()
    for raw in criteria:
        criterion_id = require_id(str(raw.get("id") or ""), "criterion id")
        if criterion_id in ids:
            raise RuntimeFailure("INVALID_CRITERION", f"duplicate criterion id: {criterion_id}")
        risk = str(raw.get("risk") or "R1")
        if risk not in RISK_CLASSES:
            raise RuntimeFailure("INVALID_CRITERION", f"invalid risk: {risk}")
        verification = str(raw.get("verificationType") or "deterministic")
        if verification not in {"deterministic", "e2e", "semantic", "reality", "external"}:
            raise RuntimeFailure("INVALID_CRITERION", f"invalid verification type: {verification}")
        surface_raw = raw.get("surface")
        surface = str(surface_raw) if surface_raw not in (None, "") else None
        if verification in SURFACE_VERIFICATION_TYPES:
            if surface is None:
                raise RuntimeFailure(
                    "INVALID_CRITERION",
                    f"criterion {criterion_id} has verificationType '{verification}' and must "
                    "declare the product surface it verifies",
                )
            if surface not in SURFACE_VALUES:
                raise RuntimeFailure("INVALID_CRITERION", f"invalid verification surface: {surface}")
        elif surface is not None:
            raise RuntimeFailure(
                "INVALID_CRITERION",
                f"criterion {criterion_id} has verificationType '{verification}' and must not "
                "declare a verification surface",
            )
        target_evidence = normalize_target_evidence(
            raw.get("targetEvidence"),
            criterion_id=criterion_id,
            verification_type=verification,
            surface=surface,
        )
        normalized.append(
            {
                "id": criterion_id,
                "description": str(raw.get("description") or "").strip(),
                "scope": str(raw.get("scope") or "program"),
                "risk": risk,
                "verificationType": verification,
                "surface": surface,
                "targetEvidence": target_evidence,
                "status": str(raw.get("status") or "UNTESTED"),
                "evidenceRefs": list(dict.fromkeys(raw.get("evidenceRefs") or [])),
                "blocking": bool(raw.get("blocking", True)),
            }
        )
        ids.add(criterion_id)
    return normalized


def normalize_work_packet(
    value: dict[str, Any] | None,
    task_id: str,
    *,
    normalized_defaults: dict[str, Any],
) -> dict[str, Any]:
    value = value or {}
    packet_id = require_id(str(value.get("workPacketId") or f"wp-{task_id}"), "work packet id")
    return {
        "workPacketId": packet_id,
        "taskId": task_id,
        "objective": str(value.get("objective") or normalized_defaults["objective"]),
        "acceptanceCriteria": list(value.get("acceptanceCriteria") or normalized_defaults["acceptanceCriteria"]),
        "contextBundle": [safe_relative_path(path, "context path") for path in value.get("contextBundle", [])],
        "repoScope": str(value.get("repoScope") or normalized_defaults["repoScope"]),
        "mutablePaths": [safe_relative_path(path, "mutable path") for path in value.get("mutablePaths", normalized_defaults["mutablePaths"])],
        "tools": list(dict.fromkeys(value.get("tools") or normalized_defaults["tools"])),
        "worker": str(value.get("worker") or normalized_defaults["worker"]),
        "model": value.get("model"),
        "risk": str(value.get("risk") or normalized_defaults["risk"]),
        "expectedArtifacts": list(value.get("expectedArtifacts") or normalized_defaults["expectedArtifacts"]),
        "budget": {
            "timeoutSeconds": int((value.get("budget") or {}).get("timeoutSeconds", 3600)),
            "maxOutputBytes": int((value.get("budget") or {}).get("maxOutputBytes", 1024 * 1024)),
        },
        "execution": normalize_execution(value.get("execution")),
    }


def normalize_execution(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    command = value.get("command") or []
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        raise RuntimeFailure("INVALID_EXECUTION", "execution command must be a non-empty argv array")
    cwd = value.get("cwd")
    if cwd is not None:
        cwd = safe_relative_path(str(cwd), "execution cwd")
    environment = list(dict.fromkeys(value.get("environment") or []))
    if any(not re.fullmatch(r"[A-Z_][A-Z0-9_]*", str(name)) for name in environment):
        raise RuntimeFailure("INVALID_EXECUTION", "execution environment contains an invalid variable name")
    return {"command": list(command), "cwd": cwd, "environment": environment}


def validate_run(state: dict[str, Any]) -> None:
    required = {
        "schema",
        "revision",
        "runId",
        "createdAt",
        "updatedAt",
        "goal",
        "status",
        "autonomy",
        "policy",
        "outcome",
        "acceptanceCriteria",
        "baseline",
        "tasks",
        "checkpoints",
        "externalCheckpoints",
        "artifacts",
        "workers",
        "gateResults",
        "eventLog",
        "eventCursor",
        "pendingEvent",
    }
    if set(state) != required:
        raise RuntimeFailure("RUN_INVALID", "Run has missing or unknown top-level fields")
    if state["schema"] != SCHEMA or state["status"] not in RUN_STATUSES:
        raise RuntimeFailure("RUN_INVALID", "Run schema or status is invalid")
    require_id(str(state["runId"]), "run id")
    if not isinstance(state["revision"], int) or state["revision"] < -1:
        raise RuntimeFailure("RUN_INVALID", "Run revision is invalid")
    if state["autonomy"].get("scope") not in {"current-task", "approved-program", "advisory-only"}:
        raise RuntimeFailure("RUN_INVALID", "Run autonomy scope is invalid")
    if state["policy"].get("default") != "deny":
        raise RuntimeFailure("RUN_INVALID", "mutation policy must default to deny")
    normalize_policy_allow(state["policy"].get("allow") or [])
    criteria_ids: set[str] = set()
    for criterion in state["acceptanceCriteria"]:
        criterion_id = require_id(str(criterion.get("id") or ""), "criterion id")
        if criterion_id in criteria_ids or criterion.get("risk") not in RISK_CLASSES:
            raise RuntimeFailure("RUN_INVALID", "acceptance criteria are invalid")
        if criterion.get("status") not in CRITERION_STATUSES:
            raise RuntimeFailure("RUN_INVALID", "acceptance criterion status is invalid")
        surface = criterion.get("surface")
        if surface is not None and surface not in SURFACE_VALUES:
            raise RuntimeFailure("RUN_INVALID", "acceptance criterion surface is invalid")
        normalize_target_evidence(
            criterion.get("targetEvidence"),
            criterion_id=criterion_id,
            verification_type=str(criterion.get("verificationType") or ""),
            surface=surface,
        )
        criteria_ids.add(criterion_id)
    outcome_ids = {item.get("id") for item in state["outcome"].get("requiredCriteria", [])}
    if not outcome_ids or not outcome_ids.issubset(criteria_ids):
        raise RuntimeFailure("RUN_INVALID", "Outcome references unknown acceptance criteria")
    validate_task_graph(state["tasks"])
    for task in state["tasks"]:
        if task["risk"] not in RISK_CLASSES or task["status"] not in TASK_STATUSES:
            raise RuntimeFailure("RUN_INVALID", f"task {task['id']} risk or status is invalid")
        if not set(task["acceptanceCriteria"]).issubset(criteria_ids):
            raise RuntimeFailure("RUN_INVALID", f"task {task['id']} references unknown criteria")
        for path in task["mutablePaths"]:
            safe_relative_path(path, "mutable path")
        for path in task["workPacket"]["contextBundle"]:
            safe_relative_path(path, "context path")
    checkpoint_ids = [item.get("id") for item in state["checkpoints"]]
    external_ids = [item.get("id") for item in state["externalCheckpoints"]]
    if len(checkpoint_ids) != len(set(checkpoint_ids)) or len(external_ids) != len(set(external_ids)):
        raise RuntimeFailure("RUN_INVALID", "checkpoint ids must be unique")
    for checkpoint in state["externalCheckpoints"]:
        if not re.fullmatch(r"[0-9a-f]{64}", str(checkpoint.get("challengeHash", ""))):
            raise RuntimeFailure("RUN_INVALID", "external checkpoint challenge hash is invalid")
    gate_ids: set[str] = set()
    for gate in state["gateResults"]:
        gate_id = require_id(str(gate.get("id") or ""), "gate id")
        if gate_id in gate_ids or not gate.get("criteria") or not set(gate["criteria"]).issubset(criteria_ids):
            raise RuntimeFailure("RUN_INVALID", "gate ids and criterion bindings must be valid")
        gate_ids.add(gate_id)
    cursor = state["eventCursor"]
    if not isinstance(cursor.get("sequence"), int) or cursor["sequence"] < 0:
        raise RuntimeFailure("RUN_INVALID", "event cursor sequence is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", str(cursor.get("lastHash", ""))):
        raise RuntimeFailure("RUN_INVALID", "event cursor hash is invalid")


def validate_task_graph(tasks: Sequence[dict[str, Any]]) -> None:
    task_ids = [require_id(str(task.get("id") or ""), "task id") for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise RuntimeFailure("TASK_GRAPH_INVALID", "task ids must be unique")
    known = set(task_ids)
    graph: dict[str, list[str]] = {}
    for task in tasks:
        dependencies = list(task.get("dependencies") or [])
        if task["id"] in dependencies or not set(dependencies).issubset(known):
            raise RuntimeFailure("TASK_GRAPH_INVALID", f"task {task['id']} has invalid dependencies")
        graph[task["id"]] = dependencies

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise RuntimeFailure("TASK_GRAPH_CYCLE", f"task graph cycle includes {task_id}")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in graph[task_id]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in task_ids:
        visit(task_id)


def find_task(state: dict[str, Any], task_id: str) -> dict[str, Any]:
    require_id(task_id, "task id")
    task = next((item for item in state["tasks"] if item["id"] == task_id), None)
    if task is None:
        raise RuntimeFailure("TASK_NOT_FOUND", f"task not found: {task_id}")
    return task


def dependencies_completed(state: dict[str, Any], task: dict[str, Any]) -> bool:
    statuses = {item["id"]: item["status"] for item in state["tasks"]}
    return all(statuses.get(dependency) in {"COMPLETED", "SKIPPED"} for dependency in task["dependencies"])


def mutable_scopes_overlap(left: Sequence[str], right: Sequence[str]) -> bool:
    def prefix(pattern: str) -> str:
        wildcard = min(
            [position for token in "*?[" if (position := pattern.find(token)) >= 0]
            or [len(pattern)]
        )
        return pattern[:wildcard].rstrip("/")

    for left_pattern in left:
        for right_pattern in right:
            if left_pattern == right_pattern:
                return True
            left_prefix = prefix(left_pattern)
            right_prefix = prefix(right_pattern)
            if not left_prefix or not right_prefix:
                return True
            if (
                left_prefix == right_prefix
                or left_prefix.startswith(right_prefix + "/")
                or right_prefix.startswith(left_prefix + "/")
            ):
                return True
    return False


def refresh_task_readiness(state: dict[str, Any]) -> list[str]:
    newly_ready: list[str] = []
    for task in state["tasks"]:
        if task["status"] == "NOT_READY" and dependencies_completed(state, task):
            task["status"] = "READY"
            newly_ready.append(task["id"])
    return newly_ready


def derive_run_status(state: dict[str, Any]) -> str:
    if state["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
        return state["status"]
    statuses = {task["status"] for task in state["tasks"]}
    if "RUNNING" in statuses:
        return "RUNNING"
    if "READY" in statuses:
        return "RUNNING"
    pending_external = any(item["status"] == "PENDING" for item in state["externalCheckpoints"])
    if pending_external or "WAITING_EXTERNAL" in statuses:
        return "WAITING_EXTERNAL"
    if "WAITING_RESOURCE" in statuses:
        return "WAITING_RESOURCE"
    if statuses and statuses.issubset({"COMPLETED", "SKIPPED"}):
        return "VERIFYING"
    if "FAILED" in statuses:
        return "FAILED"
    return "PLANNING" if state["tasks"] else "CREATED"


def append_checkpoint(state: dict[str, Any], task_id: str | None, kind: str) -> None:
    snapshot = copy.deepcopy(state)
    snapshot["pendingEvent"] = None
    checkpoint = {
        "id": f"cp-{uuid.uuid4().hex}",
        "taskId": task_id,
        "kind": kind,
        "createdAt": utc_now(),
        "revision": state["revision"],
        "stateHash": sha256_value(snapshot),
    }
    state["checkpoints"].append(checkpoint)


def evidence_ref_kind(state: dict[str, Any], reference: str) -> str | None:
    if ":" not in reference:
        return None
    kind, identifier = reference.split(":", 1)
    if kind == "artifact" and any(item["id"] == identifier for item in state["artifacts"]):
        return kind
    if kind == "gate" and any(item["id"] == identifier and item["status"] == "PASS" for item in state["gateResults"]):
        return kind
    if kind == "external" and any(item["id"] == identifier and item["status"] == "RESOLVED" for item in state["externalCheckpoints"]):
        return kind
    return None


def require_evidence_refs(state: dict[str, Any], references: Sequence[str], *, allowed: set[str]) -> None:
    if not references:
        raise RuntimeFailure("EVIDENCE_REQUIRED", "registered evidence is required")
    invalid = [
        reference
        for reference in references
        if evidence_ref_kind(state, reference) not in allowed
    ]
    if invalid:
        raise RuntimeFailure(
            "EVIDENCE_INVALID",
            "evidence references must resolve to registered Run evidence",
            details={"references": invalid, "allowed": sorted(allowed)},
        )


DEFAULT_RISK_GATES = {
    "R0": ["deterministic"],
    "R1": ["deterministic"],
    "R2": ["deterministic", "semantic-any"],
    "R3": ["deterministic", "e2e-or-reality", "semantic-gpt", "semantic-claude"],
    "R4": ["deterministic", "e2e-or-reality", "semantic-gpt", "semantic-claude", "security", "policy"],
}


def evaluation_config(repository: str) -> dict[str, Any]:
    path = Path(repository) / "architrave.config.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value.get("evaluation") or {} if isinstance(value, dict) else {}


def repository_config(repository: str) -> dict[str, Any]:
    path = Path(repository) / "architrave.config.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def missing_gate_requirements(state: dict[str, Any], criteria: Sequence[dict[str, Any]]) -> list[str]:
    repo_config = repository_config(state["baseline"]["repository"])
    configured = repo_config.get("evaluation") or {}
    risk_policy = configured.get("riskPolicy") or {}
    missing: list[str] = []
    for criterion in criteria:
        requirements = list(
            dict.fromkeys(
                [
                    *DEFAULT_RISK_GATES[criterion["risk"]],
                    *(risk_policy.get(criterion["risk"]) or []),
                ]
            )
        )
        if configured.get("realityGate") and criterion["risk"] in {"R2", "R3", "R4"}:
            requirements = [*requirements, "reality"]
        if repo_config.get("invariants"):
            requirements = [*requirements, "invariant"]
        passed = [
            gate
            for gate in state["gateResults"]
            if gate["status"] == "PASS"
            and criterion["id"] in gate["criteria"]
            # A gate recorded against an earlier source commit is stale
            # proof once the baseline has moved on (``resume(accept_commit=
            # True)``): it must not keep satisfying a requirement for the
            # current, different source snapshot. Gates recorded before
            # this field existed have no ``sourceCommit`` and are treated
            # as already-stale (never silently trusted as current).
            and gate.get("sourceCommit") == state["baseline"].get("commit")
        ]
        capabilities: set[str] = {gate["type"] for gate in passed}
        if any(gate["type"] == "semantic" for gate in passed):
            capabilities.add("semantic-any")
        if any(gate["type"] == "semantic" and gate.get("family") == "gpt" for gate in passed):
            capabilities.add("semantic-gpt")
        if any(gate["type"] == "semantic" and gate.get("family") == "claude" for gate in passed):
            capabilities.add("semantic-claude")
        if any(gate["type"] in {"e2e", "reality"} for gate in passed):
            capabilities.add("e2e-or-reality")
        if any(
            gate["type"] == "deterministic"
            and gate["id"].startswith("invariants-")
            and any(
                artifact["producer"] == "invariant"
                and f"artifact:{artifact['id']}" in gate["evidenceRefs"]
                for artifact in state["artifacts"]
            )
            for gate in passed
        ):
            capabilities.add("invariant")
        missing.extend(
            f"{criterion['id']}:{requirement}"
            for requirement in requirements
            if requirement not in capabilities
        )
    return sorted(set(missing))


def mutation_decision(state: dict[str, Any], scope: str, operation: str, *, confirmed: bool) -> dict[str, Any]:
    if state["autonomy"]["scope"] == "advisory-only":
        return {"status": "denied", "reason": "advisory-only", "scope": scope, "operation": operation}
    allowed = any(
        (entry["scope"] == scope or entry["scope"] == "*")
        and (operation in entry["operations"] or "*" in entry["operations"])
        for entry in state["policy"]["allow"]
    )
    if not allowed:
        return {"status": "denied", "reason": "default-deny", "scope": scope, "operation": operation}
    if operation in state["policy"]["confirmationRequired"] and not confirmed:
        return {
            "status": "confirmation-required",
            "reason": "operation-requires-confirmation",
            "scope": scope,
            "operation": operation,
        }
    return {"status": "allowed", "reason": "scoped-policy", "scope": scope, "operation": operation}


def require_mutation_allowed(state: dict[str, Any], scope: str, operation: str, *, confirmed: bool) -> None:
    decision = mutation_decision(state, scope, operation, confirmed=confirmed)
    if decision["status"] != "allowed":
        raise RuntimeFailure(
            "MUTATION_DENIED",
            f"mutation {scope}:{operation} is {decision['status']} ({decision['reason']})",
            details=decision,
        )


def parse_criterion(value: str) -> dict[str, Any]:
    parts = value.split("|", 5)
    if len(parts) not in (5, 6):
        raise RuntimeFailure(
            "INVALID_ARGUMENT",
            "criterion must be ID|description|scope|R0-R4|deterministic|e2e|semantic|reality|external"
            "[|web|electron|ios|deployment|runtime] (surface is required for reality/e2e)",
            exit_code=2,
        )
    criterion_id, description, scope, risk, verification, *rest = parts
    surface = rest[0] if rest and rest[0] else None
    return {
        "id": criterion_id,
        "description": description,
        "scope": scope,
        "risk": risk,
        "verificationType": verification,
        "surface": surface,
        "status": "UNTESTED",
        "evidenceRefs": [],
        "blocking": True,
    }


def parse_policy_allow(value: str) -> dict[str, Any]:
    if ":" not in value:
        raise RuntimeFailure("INVALID_ARGUMENT", "allow must be SCOPE:operation[,operation]", exit_code=2)
    scope, operations = value.rsplit(":", 1)
    return {"scope": scope, "operations": [item for item in operations.split(",") if item]}


def split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def state_summary(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "runId": state["runId"],
        "status": state["status"],
        "revision": state["revision"],
        "autonomy": state["autonomy"]["scope"],
        "readyTasks": [task["id"] for task in state["tasks"] if task["status"] == "READY"],
        "runningTasks": [task["id"] for task in state["tasks"] if task["status"] == "RUNNING"],
        "pendingExternal": [
            checkpoint["id"] for checkpoint in state["externalCheckpoints"] if checkpoint["status"] == "PENDING"
        ],
        "acceptance": {criterion["id"]: criterion["status"] for criterion in state["acceptanceCriteria"]},
        "eventCursor": state["eventCursor"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Architrave durable Run v2 control plane")
    parser.add_argument("--repo", default=".", help="repository root (default: current directory)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("run", aliases=["create"], help="create a durable Run")
    create.add_argument("--goal", required=True)
    create.add_argument("--outcome", required=True)
    create.add_argument("--criterion", action="append", default=[])
    create.add_argument("--autonomy", choices=["current-task", "approved-program", "advisory-only"], default="current-task")
    create.add_argument("--allow", action="append", default=[])
    create.add_argument("--confirmation-required", action="append", default=[])
    create.add_argument("--run-id")

    for command in ("status", "inspect", "events", "ready", "resume", "verify"):
        current = subparsers.add_parser(command)
        current.add_argument("run_id", nargs="?")
        if command == "resume":
            current.add_argument("--accept-commit", action="store_true")

    task_add = subparsers.add_parser("task-add")
    task_add.add_argument("run_id")
    task_add.add_argument("--id", required=True)
    task_add.add_argument("--title", required=True)
    task_add.add_argument("--objective", required=True)
    task_add.add_argument("--depends-on")
    task_add.add_argument("--worker", choices=["copilot", "claude", "codex", "shell"], default="shell")
    task_add.add_argument("--workspace")
    task_add.add_argument("--mutable-path", action="append", default=[])
    task_add.add_argument("--tool", action="append", default=[])
    task_add.add_argument("--risk", choices=sorted(RISK_CLASSES), default="R1")
    task_add.add_argument("--criteria", required=True)
    task_add.add_argument("--artifact", action="append", default=[])
    task_add.add_argument("--gate")
    task_add.add_argument("--max-attempts", type=int, default=1)
    task_add.add_argument("--side-effect", help="OPERATION@TARGET")
    task_add.add_argument(
        "--command", dest="task_command", nargs=argparse.REMAINDER, help="deterministic shell argv (must be last)"
    )

    task_start = subparsers.add_parser("task-start")
    task_start.add_argument("run_id")
    task_start.add_argument("task_id")
    task_start.add_argument("--worker-id", required=True)
    task_start.add_argument("--lease-seconds", type=int, default=3600)
    task_start.add_argument("--confirmed", action="store_true")

    worker_finish = subparsers.add_parser("worker-finish")
    worker_finish.add_argument("run_id")
    worker_finish.add_argument("task_id")
    worker_finish.add_argument("--worker-id", required=True)
    worker_finish.add_argument("--status", choices=["FINISHED", "FAILED"], required=True)
    worker_finish.add_argument("--evidence", action="append", default=[])

    task_complete = subparsers.add_parser("task-complete")
    task_complete.add_argument("run_id")
    task_complete.add_argument("task_id")
    task_complete.add_argument("--evidence", action="append", required=True)

    task_fail = subparsers.add_parser("task-fail")
    task_fail.add_argument("run_id")
    task_fail.add_argument("task_id")
    task_fail.add_argument("--reason", required=True)

    grant_attempt = subparsers.add_parser(
        "task-grant-attempt",
        help="grant one additional bounded attempt to a task that exhausted its declared retry policy "
        "(e.g. a milestone task whose work genuinely spans an external-checkpoint pause/resume cycle)",
    )
    grant_attempt.add_argument("run_id")
    grant_attempt.add_argument("task_id")
    grant_attempt.add_argument("--reason", required=True)
    grant_attempt.add_argument("--actor", required=True, help="human:<name> or coordinator")
    grant_attempt.add_argument(
        "--checkpoint-id",
        required=True,
        help="id of an already-RESOLVED external checkpoint bound to this task (resumeTask == task_id) "
        "with a recorded resolution proof; the grant is denied without a real matching recovery event",
    )

    gate = subparsers.add_parser("gate-record")
    gate.add_argument("run_id")
    gate.add_argument("--id", required=True)
    gate.add_argument("--task-id")
    gate.add_argument("--type", choices=["deterministic", "e2e", "semantic", "reality", "policy", "security"], required=True)
    gate.add_argument("--family", choices=["gpt", "claude", "security"])
    gate.add_argument("--criteria", help="comma-separated acceptance criterion ids")
    gate.add_argument("--surface", help="verification surface this reality/e2e gate proves (e.g. web, ios, electron)")
    gate.add_argument("--status", choices=["PASS", "FAIL", "BLOCKED", "SKIPPED"], required=True)
    gate.add_argument("--evidence", action="append", default=[])

    criterion = subparsers.add_parser("criterion-set")
    criterion.add_argument("run_id")
    criterion.add_argument("criterion_id")
    criterion.add_argument("--status", choices=sorted(CRITERION_STATUSES), required=True)
    criterion.add_argument("--evidence", action="append", default=[])

    wait = subparsers.add_parser("external-wait")
    wait.add_argument("run_id")
    wait.add_argument("--id", required=True)
    wait.add_argument("--task-id", required=True)
    wait.add_argument("--type", choices=sorted(EXTERNAL_TYPES), required=True)
    wait.add_argument("--principal", required=True)
    wait.add_argument("--provider", required=True)
    wait.add_argument("--reason", required=True)

    resolve = subparsers.add_parser("external-resolve")
    resolve.add_argument("run_id")
    resolve.add_argument("checkpoint_id")
    resolve.add_argument("--resolution-ref", required=True)
    resolve.add_argument("--challenge", required=True)
    resolve.add_argument("--actor", required=True, help="human:<name> or coordinator")

    reissue = subparsers.add_parser(
        "external-reissue-challenge",
        help="reissue a pending external checkpoint's lost one-time challenge, bound to an already-registered external-proof artifact",
    )
    reissue.add_argument("run_id")
    reissue.add_argument("checkpoint_id")
    reissue.add_argument("--proof-ref", required=True, help="artifact:<id> of an already-registered matching external-proof")
    reissue.add_argument("--actor", required=True, help="human:<name> or coordinator")

    reconcile = subparsers.add_parser("reconcile-side-effect")
    reconcile.add_argument("run_id")
    reconcile.add_argument("task_id")
    reconcile.add_argument("--result", choices=["applied", "not-applied"], required=True)
    reconcile.add_argument("--evidence", required=True)

    policy = subparsers.add_parser("policy-check")
    policy.add_argument("run_id")
    policy.add_argument("--scope", required=True)
    policy.add_argument("--operation", required=True)
    policy.add_argument("--confirmed", action="store_true")

    migrate = subparsers.add_parser("migrate-v1")
    migrate.add_argument("summary")
    migrate.add_argument("--run-id")
    return parser


def cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = RunStore(args.repo)
    try:
        command = args.command
        if command in {"run", "create"}:
            state = store.create(
                goal=args.goal,
                outcome=args.outcome,
                criteria=[parse_criterion(item) for item in args.criterion],
                autonomy_scope=args.autonomy,
                policy_allow=[parse_policy_allow(item) for item in args.allow],
                confirmation_required=args.confirmation_required,
                run_id=args.run_id,
            )
            output = state_summary(state)
        elif command == "status":
            output = state_summary(store.load(args.run_id))
        elif command == "inspect":
            output = store.load(args.run_id)
        elif command == "events":
            output = store.events(args.run_id)
        elif command == "ready":
            output = {"tasks": store.ready_tasks(args.run_id)}
        elif command == "resume":
            run_id = args.run_id or store.latest_run_id()
            output = state_summary(store.resume(run_id, accept_commit=args.accept_commit))
        elif command == "verify":
            run_id = args.run_id or store.latest_run_id()
            state, completed = store.verify(run_id)
            output = state_summary(state)
            if not completed:
                print(json.dumps({"status": "incomplete", "result": output}, indent=2))
                return 1
        elif command == "task-add":
            side_effect = None
            if args.side_effect:
                if "@" not in args.side_effect:
                    raise RuntimeFailure("INVALID_ARGUMENT", "side-effect must be OPERATION@TARGET", exit_code=2)
                operation, target = args.side_effect.split("@", 1)
                side_effect = {"operation": operation, "target": target}
            state = store.add_task(
                args.run_id,
                {
                    "id": args.id,
                    "title": args.title,
                    "objective": args.objective,
                    "dependencies": split_csv(args.depends_on),
                    "workerProfile": args.worker,
                    "workspace": args.workspace,
                    "mutablePaths": args.mutable_path,
                    "tools": args.tool,
                    "risk": args.risk,
                    "acceptanceCriteria": split_csv(args.criteria),
                    "requiredArtifacts": args.artifact,
                    "gate": args.gate,
                    "maxAttempts": args.max_attempts,
                    "sideEffect": side_effect,
                    "workPacket": {
                        "execution": {
                            "command": args.task_command,
                            "cwd": None,
                            "environment": [],
                        }
                    } if args.task_command else None,
                },
            )
            output = state_summary(state)
        elif command == "task-start":
            output = state_summary(
                store.start_task(
                    args.run_id,
                    args.task_id,
                    worker_id=args.worker_id,
                    lease_seconds=args.lease_seconds,
                    confirmed=args.confirmed,
                )
            )
        elif command == "worker-finish":
            output = state_summary(
                store.finish_worker(
                    args.run_id,
                    args.task_id,
                    worker_id=args.worker_id,
                    status=args.status,
                    artifact_refs=args.evidence,
                )
            )
        elif command == "task-complete":
            output = state_summary(store.complete_task(args.run_id, args.task_id, evidence_refs=args.evidence))
        elif command == "task-fail":
            output = state_summary(store.fail_task(args.run_id, args.task_id, args.reason))
        elif command == "task-grant-attempt":
            output = state_summary(
                store.grant_task_attempt(
                    args.run_id,
                    args.task_id,
                    reason=args.reason,
                    actor=args.actor,
                    checkpoint_id=args.checkpoint_id,
                )
            )
        elif command == "gate-record":
            output = state_summary(
                store.record_gate(
                    args.run_id,
                    gate_id=args.id,
                    task_id=args.task_id,
                    gate_type=args.type,
                    status=args.status,
                    evidence_refs=args.evidence,
                    family=args.family,
                    criteria=split_csv(args.criteria) if args.criteria else None,
                    surface=args.surface,
                )
            )
        elif command == "criterion-set":
            output = state_summary(
                store.set_criterion(args.run_id, args.criterion_id, args.status, args.evidence)
            )
        elif command == "external-wait":
            state, challenge = store.wait_external(
                args.run_id,
                checkpoint_id=args.id,
                task_id=args.task_id,
                checkpoint_type=args.type,
                principal=args.principal,
                provider=args.provider,
                reason=args.reason,
            )
            output = {**state_summary(state), "resolutionChallenge": challenge}
        elif command == "external-resolve":
            output = state_summary(
                store.resolve_external(
                    args.run_id,
                    checkpoint_id=args.checkpoint_id,
                    resolution_ref=args.resolution_ref,
                    challenge=args.challenge,
                    actor=args.actor,
                )
            )
        elif command == "external-reissue-challenge":
            state, challenge = store.reissue_challenge(
                args.run_id,
                checkpoint_id=args.checkpoint_id,
                proof_ref=args.proof_ref,
                actor=args.actor,
            )
            output = {**state_summary(state), "resolutionChallenge": challenge}
        elif command == "reconcile-side-effect":
            output = state_summary(
                store.reconcile_side_effect(
                    args.run_id,
                    args.task_id,
                    result=args.result,
                    evidence_ref=args.evidence,
                )
            )
        elif command == "policy-check":
            output = store.policy_check(
                args.run_id,
                args.scope,
                args.operation,
                confirmed=args.confirmed,
            )
            if output["status"] != "allowed":
                print(json.dumps({"status": "denied", "result": output}, indent=2))
                return 3
        elif command == "migrate-v1":
            output = state_summary(store.migrate_v1(Path(args.summary), run_id=args.run_id))
        else:
            parser.error(f"unsupported command: {command}")
            return 2
        print(json.dumps({"status": "ok", "result": output}, indent=2))
        return 0
    except RuntimeFailure as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": {"code": exc.code, "message": exc.message, "details": redact(exc.details)},
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(cli())