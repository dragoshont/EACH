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


def _packet(
    task_id: str,
    *,
    target_repo: str = "test/fixture",
    target_ref: str = "deadbeef",
    allowed_paths: list[str] | None = None,
    build_commands: list[list[str]] | None = None,
    acceptance_commands: list[list[str]] | None = None,
    forbidden_sources: list[str] | None = None,
    sensitive: bool = False,
):
    return make_spec_packet(
        task_id=task_id,
        target_repo=target_repo,
        target_ref=target_ref,
        problem_statement="fixture",
        allowed_paths=allowed_paths if allowed_paths is not None else ["a.c"],
        build_commands=build_commands if build_commands is not None else [["true"]],
        acceptance_commands=acceptance_commands if acceptance_commands is not None else [["true"]],
        forbidden_sources=forbidden_sources if forbidden_sources is not None else [],
        approved_by="test",
        sensitive=sensitive,
    )


# The exact real, pinned M8 envelope for xodus-gaming/xgameruntime (see
# policies/xodus-shadow.yml's pinned_targets entry) -- fixtures that match
# this exactly are the only ones expected to pass the strict-run binding;
# anything else (a deadbeef target_ref, an arbitrary path/command, an empty
# forbidden_sources list) must be rejected (F2).
_REAL_TARGET_REF = "791710510d9ba0746bbd60754215eb321800e4f0"
_REAL_ALLOWED_PATHS = ["xsystem.c"]
_REAL_BUILD_COMMANDS = [["python3", "examples/xodus-m8-sandbox-id/build_check.py", "build", "xsystem.c"]]
_REAL_ACCEPTANCE_COMMANDS = [["python3", "examples/xodus-m8-sandbox-id/build_check.py", "run"]]
_REAL_FORBIDDEN_SOURCES = ["proprietary-implementation", "decompiler-output"]


def _real_envelope_packet(task_id: str, **overrides):
    kwargs = {
        "target_repo": "https://github.com/xodus-gaming/xgameruntime",
        "target_ref": _REAL_TARGET_REF,
        "allowed_paths": list(_REAL_ALLOWED_PATHS),
        "build_commands": [list(cmd) for cmd in _REAL_BUILD_COMMANDS],
        "acceptance_commands": [list(cmd) for cmd in _REAL_ACCEPTANCE_COMMANDS],
        "forbidden_sources": list(_REAL_FORBIDDEN_SOURCES),
        "sensitive": True,
    }
    kwargs.update(overrides)
    return _packet(task_id, **kwargs)


def _durably_approve(approved: ApprovedSpec) -> None:
    task_dir = specs_dir() / approved.packet.task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "approved.json").write_text(
        json.dumps(approved.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def test_unlisted_repository_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F2: an empty/missing/drifted ``strict_run_repositories`` entry for a
    repo must never silently fail OPEN -- every target this pipeline runs
    against is treated as strict by default and rejected if unlisted."""
    monkeypatch.setenv("EACH_HOME", str(tmp_path))
    approved = ApprovedSpec.approve(_packet("policy-unlisted-repo"))
    _durably_approve(approved)
    with pytest.raises(PolicyViolation, match="not a declared strict-run repository"):
        verify_xodus_shadow_binding(approved)


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


def test_strict_repo_with_exact_pinned_envelope_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path))
    approved = ApprovedSpec.approve(_real_envelope_packet("policy-strict-sensitive-ok"))
    _durably_approve(approved)
    verify_xodus_shadow_binding(approved)  # must not raise


@pytest.mark.parametrize("api", ["sandbox", "console"])
def test_named_ledger_envelope_only_allows_its_selected_api(tmp_path, monkeypatch, api):
    monkeypatch.setenv("EACH_HOME", str(tmp_path))
    task_id = f"each-two-model-ledger-{api}-v1"
    build = _REAL_BUILD_COMMANDS[0] + [api]
    run = _REAL_ACCEPTANCE_COMMANDS[0] + [api]
    approved = ApprovedSpec.approve(
        _real_envelope_packet(task_id, build_commands=[build], acceptance_commands=[run])
    )
    _durably_approve(approved)
    verify_xodus_shadow_binding(approved)
    wrong_api = "console" if api == "sandbox" else "sandbox"
    wrong = ApprovedSpec.approve(
        _real_envelope_packet(
            task_id,
            build_commands=[_REAL_BUILD_COMMANDS[0] + [wrong_api]],
            acceptance_commands=[_REAL_ACCEPTANCE_COMMANDS[0] + [wrong_api]],
        )
    )
    _durably_approve(wrong)
    with pytest.raises(PolicyViolation, match="build_commands"):
        verify_xodus_shadow_binding(wrong)


def test_strict_repo_with_deadbeef_target_ref_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path))
    approved = ApprovedSpec.approve(
        _real_envelope_packet("policy-strict-deadbeef-ref", target_ref="deadbeef")
    )
    _durably_approve(approved)
    with pytest.raises(PolicyViolation, match="target_ref"):
        verify_xodus_shadow_binding(approved)


def test_strict_repo_with_arbitrary_allowed_path_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path))
    approved = ApprovedSpec.approve(
        _real_envelope_packet("policy-strict-wrong-path", allowed_paths=["other_file.c"])
    )
    _durably_approve(approved)
    with pytest.raises(PolicyViolation, match="allowed_paths"):
        verify_xodus_shadow_binding(approved)


def test_strict_repo_with_arbitrary_commands_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path))
    approved = ApprovedSpec.approve(
        _real_envelope_packet("policy-strict-wrong-command", acceptance_commands=[["rm", "-rf", "/"]])
    )
    _durably_approve(approved)
    with pytest.raises(PolicyViolation, match="acceptance_commands"):
        verify_xodus_shadow_binding(approved)


def test_strict_repo_with_empty_forbidden_sources_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path))
    approved = ApprovedSpec.approve(
        _real_envelope_packet("policy-strict-empty-forbidden", forbidden_sources=[])
    )
    _durably_approve(approved)
    with pytest.raises(PolicyViolation, match="forbidden_sources"):
        verify_xodus_shadow_binding(approved)


def test_strict_repo_without_pinned_targets_entry_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A policy file that lists a repo as strict but never pins an exact
    envelope for it must reject, not silently trust the packet's own
    self-declared fields (F2)."""
    monkeypatch.setenv("EACH_HOME", str(tmp_path))
    approved = ApprovedSpec.approve(_real_envelope_packet("policy-strict-no-pin"))
    _durably_approve(approved)
    unpinned_policy = tmp_path / "unpinned-policy.yml"
    unpinned_policy.write_text(
        "strict_run_repositories:\n"
        "  - xodus-gaming/xgameruntime\n"
        "ai_source_upstream_promotion: false\n"
        "cloud_llm_candidate_review: false\n"
        "no_upstream_pr: true\n"
        "default_visibility: private\n"
        "terminal_audit: true\n"
        "information_origin_policy:\n"
        "  llm_driven_reverse_engineering: false\n"
    )
    with pytest.raises(PolicyViolation, match="no pinned_targets entry"):
        verify_xodus_shadow_binding(approved, policy_path=unpinned_policy)


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
