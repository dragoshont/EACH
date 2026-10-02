"""F2 regression: ``verify_xodus_shadow_binding`` must reject a spoofed/
self-approved spec and a policy-noncompliant strict run before any side
effect, while accepting a genuine, durably recorded approval unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from each.spec import ApprovedSpec, make_spec_packet
from each.spec_workflow import specs_dir
from each.xodus_policy import PolicyViolation, verify_xodus_shadow_binding


def _packet(task_id: str, *, target_repo: str = "test/fixture", sensitive: bool = False):
    return make_spec_packet(
        task_id=task_id,
        target_repo=target_repo,
        target_ref="deadbeef",
        problem_statement="fixture",
        allowed_paths=["a.c"],
        build_commands=[["true"]],
        acceptance_commands=[["true"]],
        forbidden_sources=[],
        approved_by="test",
        sensitive=sensitive,
    )


def _durably_approve(approved: ApprovedSpec) -> None:
    task_dir = specs_dir() / approved.packet.task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "approved.json").write_text(
        json.dumps(approved.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def test_genuine_durable_non_strict_approval_is_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path))
    approved = ApprovedSpec.approve(_packet("policy-ok-non-strict"))
    _durably_approve(approved)
    verify_xodus_shadow_binding(approved)  # must not raise


def test_in_memory_only_spec_is_rejected_as_unapproved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact spoofing scenario: a caller constructs and self-approves
    an ``ApprovedSpec`` in memory without ever going through the real
    ``each spec approve`` workflow."""
    monkeypatch.setenv("EACH_HOME", str(tmp_path))
    approved = ApprovedSpec.approve(_packet("policy-never-durably-approved"))
    with pytest.raises(PolicyViolation, match="no genuine durable spec approval"):
        verify_xodus_shadow_binding(approved)


def test_durable_approval_mismatch_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller presents an ``ApprovedSpec`` whose content differs from
    what is actually durably recorded for that same task id (e.g. an
    edited target_repo)."""
    monkeypatch.setenv("EACH_HOME", str(tmp_path))
    real = ApprovedSpec.approve(_packet("policy-mismatch-task"))
    _durably_approve(real)
    spoofed = ApprovedSpec.approve(_packet("policy-mismatch-task", target_repo="test/fixture-different"))
    with pytest.raises(PolicyViolation, match="does not match the genuine"):
        verify_xodus_shadow_binding(spoofed)


def test_strict_repo_without_sensitive_flag_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path))
    approved = ApprovedSpec.approve(
        _packet(
            "policy-strict-not-sensitive",
            target_repo="https://github.com/xodus-gaming/xgameruntime",
            sensitive=False,
        )
    )
    _durably_approve(approved)
    with pytest.raises(PolicyViolation, match="sensitive=True"):
        verify_xodus_shadow_binding(approved)


def test_strict_repo_with_sensitive_flag_and_matching_policy_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path))
    approved = ApprovedSpec.approve(
        _packet(
            "policy-strict-sensitive-ok",
            target_repo="https://github.com/xodus-gaming/xgameruntime",
            sensitive=True,
        )
    )
    _durably_approve(approved)
    verify_xodus_shadow_binding(approved)  # must not raise


def test_drifted_policy_file_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path))
    approved = ApprovedSpec.approve(
        _packet("policy-drifted", target_repo="https://github.com/xodus-gaming/xgameruntime", sensitive=True)
    )
    _durably_approve(approved)
    bad_policy = tmp_path / "bad-policy.yml"
    bad_policy.write_text(
        "strict_run_repositories:\n"
        "  - xodus-gaming/xgameruntime\n"
        "ai_source_upstream_promotion: true\n"  # drifted: should be false
        "cloud_llm_candidate_review: false\n"
        "no_upstream_pr: true\n"
        "default_visibility: private\n"
    )
    with pytest.raises(PolicyViolation, match="ai_source_upstream_promotion"):
        verify_xodus_shadow_binding(approved, policy_path=bad_policy)
