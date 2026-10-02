"""M8 strict-run policy enforcement (F2 fix).

``run_xodus_shadow_build`` previously trusted any caller-supplied in-memory
``ApprovedSpec`` object: nothing bound it to the genuine, durably recorded
human approval in ``~/.each/specs/<task_id>/approved.json``, and nothing
ever loaded or enforced ``policies/xodus-shadow.yml``'s machine-readable
clauses (``ai_source_upstream_promotion: false``, ``default_visibility:
private``, etc.) -- that policy existed purely as documentation. A caller
could in principle construct and self-approve a spoofed ``ApprovedSpec``
and the pipeline would still run it.

:func:`verify_xodus_shadow_binding` closes both gaps, reusing the existing
M3 spec-approval store (never inventing a second approval mechanism) and
the existing policy YAML (never inventing a generic policy framework).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from each.paths import repo_root
from each.spec import ApprovedSpec
from each.spec_workflow import SpecWorkflowError, load_approved_spec

POLICY_PATH = repo_root() / "policies" / "xodus-shadow.yml"

# Clauses a strict-run (one touching a declared ``strict_run_repositories``
# target) must have pinned to these exact values before any side effect.
_REQUIRED_BOOL_CLAUSES: dict[str, bool] = {
    "ai_source_upstream_promotion": False,
    "cloud_llm_candidate_review": False,
    "no_upstream_pr": True,
}


class PolicyViolation(RuntimeError):
    """Raised when a strict-run spec/policy binding check fails."""


def load_xodus_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PolicyViolation(f"policy file {path} did not parse to a mapping")
    return data


def _normalize_repo(target_repo: str) -> str:
    return target_repo.rstrip("/").split("github.com/")[-1]


def verify_xodus_shadow_binding(approved: ApprovedSpec, *, policy_path: Path = POLICY_PATH) -> None:
    """Reject a spoofed/self-approved spec, or a policy-noncompliant strict
    run, before any network fetch, container execution, or disk write.

    1. ``approved`` must be identical to the genuine, durably recorded
       approval for its own ``task_id`` (re-read from
       ``~/.each/specs/<task_id>/approved.json`` via the same
       ``load_approved_spec`` the M3 CLI approval workflow itself uses).
       ``approved.verify()`` alone only checks internal self-consistency
       (the packet still matches its own claimed hash); it does not prove a
       real human ever approved it. Reusing ``load_approved_spec`` here is
       what actually binds this run to that genuine decision -- the real
       approval the user gave for M8 on 2026-10-02 (draft
       ``f6f5b61f...``, approved ``2c5eca88...``), not a new one.
    2. If the packet's target repository is a declared strict-run
       repository, the packet must be marked ``sensitive`` and
       ``policies/xodus-shadow.yml``'s own required clauses must all still
       hold -- a drifted or edited policy file fails closed, it is never
       silently ignored.
    """
    packet = approved.packet
    try:
        durable = load_approved_spec(packet.task_id)
    except SpecWorkflowError as exc:
        raise PolicyViolation(
            f"no genuine durable spec approval exists for task {packet.task_id!r}: {exc}"
        ) from exc
    # Compare by content hash, not by the in-memory ``content()`` dict
    # directly: a packet reloaded from its JSON-serialized durable record
    # has plain lists where the original in-memory packet has tuples (an
    # encoding artifact, not a real content difference), and
    # ``approved_hash``/``sha256()`` already normalize through the same
    # JSON hashing both objects' own integrity checks rely on.
    if durable.approved_hash != approved.approved_hash or durable.packet.sha256() != packet.sha256():
        raise PolicyViolation(
            f"supplied ApprovedSpec for task {packet.task_id!r} does not match the genuine, "
            "durably recorded approval; refusing to run against a spoofed/self-approved spec"
        )

    policy = load_xodus_policy(policy_path)
    strict_repos = {_normalize_repo(repo) for repo in policy.get("strict_run_repositories", [])}
    if _normalize_repo(packet.target_repo) not in strict_repos:
        return

    if not packet.sensitive:
        raise PolicyViolation(
            f"target repository {packet.target_repo!r} is a declared strict-run repository; "
            "its approved spec must be marked sensitive=True"
        )
    for key, required_value in _REQUIRED_BOOL_CLAUSES.items():
        if policy.get(key) is not required_value:
            raise PolicyViolation(
                f"policy {policy_path} must declare {key}: {str(required_value).lower()} for a strict run"
            )
    if policy.get("default_visibility") != "private":
        raise PolicyViolation(f"policy {policy_path} must declare default_visibility: private for a strict run")
