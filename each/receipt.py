"""Receipt construction: the durable, private JSON (+ human Markdown) record
of a single repair-run trajectory, including every supplied input.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from each.hashing import sha256_file, sha256_text
from each.paths import assert_no_symlink_escape, repo_root


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
    # The raw network-isolation probe result, captured once before any
    # attempt and never itself downgraded: kept deliberately separate from
    # ``assurance_level`` (a broader authoring-assurance judgement that MAY
    # be conservatively downgraded, e.g. on detected materials drift) so a
    # downgrade can never silently erase or conflate the plain isolation
    # fact with the bigger claim (F4). ``None`` for receipts written before
    # this field existed.
    network_isolation_verified: bool | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)
    # Which attempt's own prompt/raw_completion/model_identity the
    # top-level fields above actually came from (F6 fix): a later retry
    # can be rejected before classification while an earlier attempt's
    # real, if failing, patch/result remains the one reported -- this
    # makes that binding explicit and checkable instead of leaving a
    # reader to assume it is always the last attempt in ``attempts``.
    selected_attempt: int | None = None

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
            "networkIsolationVerified": self.network_isolation_verified,
            "outcome": self.outcome,
            "legalCertification": self.legal_certification,
            "cleanroomCertification": self.cleanroom_certification,
            "attempts": self.attempts,
            "selectedAttempt": self.selected_attempt,
        }

    def write(self, directory: Path, *, materials_source: Path | None = None) -> tuple[Path, Path]:
        """Write ``receipt.json``/``receipt.md`` under ``directory``.

        ``directory`` must not resolve inside this repository's own working
        tree (:func:`each.paths.repo_root`) -- a receipt is always private
        evidence and must never land somewhere a later ``git add`` could
        accidentally publish it -- and must not already hold a receipt (a
        receipt is immutable once written; a run that needs to retry gets a
        new ``run_id``/directory, never an in-place overwrite of registered
        evidence).

        If ``materials_source`` is given, every path this receipt declares
        under ``materials`` is additionally copied, byte-for-byte, from
        ``materials_source`` into a new ``materials/`` subdirectory next to
        the receipt, so a later verifier can check the real referenced
        files still exist and still match their declared hash -- not just
        that the receipt's own JSON is internally self-consistent (see
        :func:`each.attestation.verify_materials_root`). Each source file's
        actual sha256 is checked against its declared ``materials`` hash
        BEFORE it is copied, and before this receipt is signed: a caller
        that passes a post-patch worktree as ``materials_source`` for a
        path whose declared hash was recorded pre-patch (a real defect
        this check exists to catch) gets a loud ``ValueError``, never a
        silently-signed receipt whose declared input does not match the
        bytes actually retained.
        """
        assert_no_symlink_escape(directory, label="receipt directory")
        repo_root_resolved = repo_root().resolve()
        directory_resolved = directory.resolve()
        if directory_resolved == repo_root_resolved or repo_root_resolved in directory_resolved.parents:
            raise ValueError(f"refusing to write a receipt inside the repository working tree: {directory}")
        json_path = directory / "receipt.json"
        md_path = directory / "receipt.md"
        if any(path.exists() or path.is_symlink() for path in (json_path, md_path)):
            raise FileExistsError(f"refusing to overwrite an already-written receipt at {directory}")
        directory.mkdir(parents=True, exist_ok=True)
        from each.attestation import attest_receipt

        if materials_source is not None:
            materials_root = directory / "materials"
            # (F3) Anchor the trusted materials root to the ALREADY
            # validated ``directory_resolved`` rather than to
            # ``materials_root.resolve()``: if ``materials_root`` were
            # itself a symlink, resolving it first and using THAT as the
            # anchor would make every subsequent "does this escape the
            # root?" check trivially pass against the already-escaped
            # location. ``assert_no_symlink_escape`` rejects that symlink
            # outright, before any anchor is even computed.
            assert_no_symlink_escape(materials_root, label="materials destination root")
            materials_root_resolved = directory_resolved / "materials"
            source_resolved = materials_source.resolve()
            for rel_path in sorted(self.materials):
                if rel_path.startswith("/") or ".." in Path(rel_path).parts:
                    raise ValueError(f"refusing to copy forbidden/traversal materials path: {rel_path}")
                src = (materials_source / rel_path).resolve()
                if src != source_resolved and source_resolved not in src.parents:
                    raise ValueError(f"materials source path escapes its root: {rel_path}")
                if src.is_symlink():
                    raise ValueError(f"refusing to copy materials source through a symlink: {rel_path}")
                if not src.is_file():
                    raise ValueError(f"declared materials path is not a regular file: {rel_path}")
                actual_hash = sha256_file(src)
                expected_hash = self.materials[rel_path]
                if actual_hash != expected_hash:
                    raise ValueError(
                        f"materials source file {rel_path!r} does not match its declared hash "
                        f"(expected {expected_hash}, got {actual_hash}); refusing to sign a receipt "
                        "whose declared input does not match the real retained bytes"
                    )
                dst = materials_root / rel_path
                assert_no_symlink_escape(dst.parent, label="materials destination ancestor")
                dst_resolved = dst.resolve()
                if dst_resolved != materials_root_resolved and materials_root_resolved not in dst_resolved.parents:
                    raise ValueError(f"materials destination path escapes materials root: {rel_path}")
                if dst.exists() or dst.is_symlink():
                    raise ValueError(
                        f"refusing to write through an existing materials destination or symlink: {rel_path}"
                    )
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)

        receipt_dict = self.to_dict()
        receipt_dict["attestation"] = attest_receipt(receipt_dict)
        with json_path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt_dict, indent=2, sort_keys=True) + "\n")
        with md_path.open("x", encoding="utf-8") as handle:
            handle.write(self._to_markdown(receipt_dict["attestation"]))
        return json_path, md_path

    def _to_markdown(self, attestation: dict[str, Any]) -> str:
        materials_lines = [f"- `{path}`: `{digest}`" for path, digest in sorted(self.materials.items())]
        lines = [
            f"# EACH repair receipt — {self.run_id}",
            "",
            f"- Created: {self.created_at}",
            f"- Outcome: **{self.outcome}**",
            f"- Assurance level: {self.assurance_level}",
            f"- Network isolation verified: {self.network_isolation_verified}",
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
            "",
            "## Attestation",
            f"- Algorithm: {attestation.get('algorithm')}",
            f"- Key fingerprint: `{attestation.get('keyFingerprint')}`",
            "- Verify with: `each verify <this receipt.json> --public-key <path to the published EACH signing public key>`",
            "- This signature proves artifact integrity (nothing in this receipt was altered after signing); it is NOT legal clean-room certification.",
        ]
        return "\n".join(lines) + "\n"
