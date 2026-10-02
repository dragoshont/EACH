"""Receipt construction: the durable, private JSON (+ human Markdown) record
of a single repair-run trajectory, including every supplied input.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from each.hashing import sha256_text


def _audit_markdown_lines(audit: dict[str, Any]) -> list[str]:
    """Render either audit shape: the M1 stub (flat name -> status string,
    plus top-level result/reason) or the M4 engine (name -> CheckResult dict,
    plus toolVersions/corpusRevision). Never collapses per-check statuses
    into a single score -- only reformats what is already there."""
    if "result" in audit:
        return [f"- Result: {audit.get('result')}", f"- Reason: {audit.get('reason', '')}"]
    lines = []
    for name, check in audit.get("checks", {}).items():
        status = check["status"] if isinstance(check, dict) else check
        detail = check.get("detail", "") if isinstance(check, dict) else ""
        lines.append(f"- {name}: {status}" + (f" ({detail})" if detail else ""))
    tool_versions = audit.get("toolVersions")
    if tool_versions:
        lines.append(f"- Tool versions: {tool_versions}")
    corpus_revision = audit.get("corpusRevision")
    if corpus_revision is not None:
        lines.append(f"- Corpus revision: {corpus_revision}")
    return lines or ["- (no audit data)"]


@dataclass
class Receipt:
    run_id: str
    spec: dict[str, Any]
    spec_hash: str
    model_identity: dict[str, Any]
    prompt: str
    raw_completion: str
    patch_text: str
    touched_paths: list[str]
    materials: dict[str, str]
    executor_identity: dict[str, Any]
    isolation_evidence: dict[str, Any]
    baseline_result: dict[str, Any]
    repaired_result: dict[str, Any]
    audit: dict[str, Any]
    assurance_level: str
    outcome: str
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    legal_certification: bool = False
    cleanroom_certification: bool = False
    attempts: list[dict[str, Any]] = field(default_factory=list)

    @property
    def patch_hash(self) -> str:
        return sha256_text(self.patch_text)

    @property
    def trajectory_hash(self) -> str:
        """Hash binding together everything the model saw and produced."""
        return sha256_text(self.prompt + "\x00" + self.raw_completion)

    def to_dict(self) -> dict[str, Any]:
        return {
            "runId": self.run_id,
            "createdAt": self.created_at,
            "spec": self.spec,
            "specHash": self.spec_hash,
            "modelIdentity": self.model_identity,
            "prompt": self.prompt,
            "rawCompletion": self.raw_completion,
            "patchText": self.patch_text,
            "patchHash": self.patch_hash,
            "trajectoryHash": self.trajectory_hash,
            "touchedPaths": self.touched_paths,
            "materials": self.materials,
            "executorIdentity": self.executor_identity,
            "isolationEvidence": self.isolation_evidence,
            "baselineResult": self.baseline_result,
            "repairedResult": self.repaired_result,
            "audit": self.audit,
            "assuranceLevel": self.assurance_level,
            "outcome": self.outcome,
            "legalCertification": self.legal_certification,
            "cleanroomCertification": self.cleanroom_certification,
            "attempts": self.attempts,
        }

    def write(self, directory: Path) -> tuple[Path, Path]:
        directory.mkdir(parents=True, exist_ok=True)
        json_path = directory / "receipt.json"
        md_path = directory / "receipt.md"
        json_path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")
        md_path.write_text(self._to_markdown())
        return json_path, md_path

    def _to_markdown(self) -> str:
        materials_lines = [f"- `{path}`: `{digest}`" for path, digest in sorted(self.materials.items())]
        lines = [
            f"# EACH repair receipt — {self.run_id}",
            "",
            f"- Created: {self.created_at}",
            f"- Outcome: **{self.outcome}**",
            f"- Assurance level: {self.assurance_level}",
            "- Legal certification: false",
            "- Cleanroom certification: false",
            (
                f"- Model: `{self.model_identity.get('modelId')}` "
                f"(`{self.model_identity.get('implementationModule')}`, "
                f"sha256 `{self.model_identity.get('implementationSha256')}`)"
            ),
            f"- Executor: {self.executor_identity}",
            f"- Spec hash: `{self.spec_hash}`",
            f"- Patch hash: `{self.patch_hash}`",
            f"- Trajectory hash: `{self.trajectory_hash}`",
            f"- Touched paths: {', '.join(self.touched_paths) or '(none)'}",
            f"- Attempts recorded: {len(self.attempts)}",
            "",
            "## Declared materials (sanitized worktree manifest)",
            *(materials_lines or ["(none)"]),
            "",
            "## Isolation evidence",
            f"- Command: `{' '.join(self.isolation_evidence.get('command', []))}`",
            f"- Exit code: {self.isolation_evidence.get('exit_code')}",
            f"- Stdout: {self.isolation_evidence.get('stdout', '').strip()!r}",
            "",
            "## Baseline (pre-patch) result",
            "```",
            f"exit={self.baseline_result.get('exit_code')}",
            str(self.baseline_result.get("stdout", "")),
            str(self.baseline_result.get("stderr", "")),
            "```",
            "",
            "## Repaired (post-patch) result",
            "```",
            f"exit={self.repaired_result.get('exit_code')}",
            str(self.repaired_result.get("stdout", "")),
            str(self.repaired_result.get("stderr", "")),
            "```",
            "",
            "## Audit",
            *_audit_markdown_lines(self.audit),
            "",
            "## Raw model completion",
            "```",
            self.raw_completion,
            "```",
            "",
            "## Applied patch",
            "```diff",
            self.patch_text,
            "```",
        ]
        return "\n".join(lines) + "\n"
