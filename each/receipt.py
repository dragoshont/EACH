"""Receipt construction: the durable, private JSON (+ human Markdown) record
of a single repair-run trajectory, including every supplied input.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Receipt:
    run_id: str
    spec: dict[str, Any]
    spec_hash: str
    model_id: str
    prompt: str
    raw_completion: str
    patch_text: str
    touched_paths: list[str]
    baseline_result: dict[str, Any]
    repaired_result: dict[str, Any]
    audit: dict[str, Any]
    assurance_level: str
    outcome: str
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "runId": self.run_id,
            "createdAt": self.created_at,
            "spec": self.spec,
            "specHash": self.spec_hash,
            "modelId": self.model_id,
            "prompt": self.prompt,
            "rawCompletion": self.raw_completion,
            "patchText": self.patch_text,
            "touchedPaths": self.touched_paths,
            "baselineResult": self.baseline_result,
            "repairedResult": self.repaired_result,
            "audit": self.audit,
            "assuranceLevel": self.assurance_level,
            "outcome": self.outcome,
        }

    def write(self, directory: Path) -> tuple[Path, Path]:
        directory.mkdir(parents=True, exist_ok=True)
        json_path = directory / "receipt.json"
        md_path = directory / "receipt.md"
        json_path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")
        md_path.write_text(self._to_markdown())
        return json_path, md_path

    def _to_markdown(self) -> str:
        lines = [
            f"# EACH repair receipt — {self.run_id}",
            "",
            f"- Created: {self.created_at}",
            f"- Outcome: **{self.outcome}**",
            f"- Assurance level: {self.assurance_level}",
            f"- Model: `{self.model_id}`",
            f"- Spec hash: `{self.spec_hash}`",
            f"- Touched paths: {', '.join(self.touched_paths) or '(none)'}",
            "",
            "## Baseline (pre-patch) result",
            "```",
            f"exit={self.baseline_result.get('exit_code')}",
            str(self.baseline_result.get("stdout", "")),
            "```",
            "",
            "## Repaired (post-patch) result",
            "```",
            f"exit={self.repaired_result.get('exit_code')}",
            str(self.repaired_result.get("stdout", "")),
            "```",
            "",
            "## Audit",
            f"- Result: {self.audit.get('result')}",
            f"- Reason: {self.audit.get('reason', '')}",
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
