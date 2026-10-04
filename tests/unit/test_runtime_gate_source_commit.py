"""F7 regression: a gate recorded as PASS against an earlier source commit
must not keep satisfying a requirement once the Run's baseline has moved to
a different commit (``resume(accept_commit=True)``) -- a gate's own proof
is tied to the exact source it verified, not a standing credential.

F2 regression (below): the F7 staleness guard originally only applied to
``gate_type == "deterministic"``. An old semantic/security/policy/reality
artifact could still be referenced by a brand-new gate id registered after
the baseline moved on, and would be silently stamped with that NEW gate's
own ``sourceCommit`` -- a producer-type-specific laundering gap. The fix
generalizes the staleness check in ``record_gate`` to every gate type, and
additionally requires semantic/security/policy receipts (mirroring the
deterministic receipt's own ``commit`` field) to declare the exact commit
they were actually produced against at REGISTRATION time, not just at
gate-binding time.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "harness"))
import architrave_runtime as art


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture()
def store_with_run(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "initial")

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()

    store = art.RunStore(repository=repo)
    store.create(
        goal="test goal",
        outcome="test outcome",
        criteria=[{"id": "C1", "description": "c1", "verificationType": "deterministic", "blocking": True, "risk": "R1"}],
        autonomy_scope="approved-program",
        run_id="test-run",
    )
    return store, repo


def _record_passing_deterministic_gate(store: art.RunStore, repo: Path, *, gate_id: str) -> None:
    evidence_dir = repo / ".architrave" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = evidence_dir / f"{gate_id}.json"
    current_commit = store.load("test-run")["baseline"]["commit"]
    receipt_path.write_text(
        json.dumps({"status": "pass", "exitCode": 0, "command": ["true"], "commit": current_commit}),
        encoding="utf-8",
    )
    store._record_deterministic_result(
        "test-run",
        artifact_id=gate_id,
        path=str(receipt_path.relative_to(repo)),
        evidence_refs=[],
    )
    store.record_gate(
        "test-run",
        gate_id=gate_id,
        task_id=None,
        gate_type="deterministic",
        status="PASS",
        evidence_refs=[f"artifact:{gate_id}"],
        criteria=["C1"],
    )


def test_gate_recorded_against_current_commit_satisfies_the_requirement(store_with_run):
    store, repo = store_with_run
    _record_passing_deterministic_gate(store, repo, gate_id="gate-1")

    state = store.load("test-run")
    missing = art.missing_gate_requirements(state, state["acceptanceCriteria"])
    assert "C1:deterministic" not in missing


def test_gate_becomes_stale_after_baseline_commit_changes(store_with_run):
    """The exact F7 scenario: a gate recorded as PASS, then the repository
    (and the Run's own recorded baseline) moves to a new commit -- the old
    gate must no longer silently count as current proof."""
    store, repo = store_with_run
    _record_passing_deterministic_gate(store, repo, gate_id="gate-1")

    state = store.load("test-run")
    assert "C1:deterministic" not in art.missing_gate_requirements(state, state["acceptanceCriteria"])

    (repo / "README.md").write_text("v2\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "second commit")
    store.resume("test-run", accept_commit=True)

    state = store.load("test-run")
    assert "C1:deterministic" in art.missing_gate_requirements(state, state["acceptanceCriteria"])


def test_new_gate_recorded_after_commit_change_is_stamped_with_the_new_commit(store_with_run):
    store, repo = store_with_run
    (repo / "README.md").write_text("v2\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "second commit")
    store.resume("test-run", accept_commit=True)

    _record_passing_deterministic_gate(store, repo, gate_id="gate-after")

    state = store.load("test-run")
    gate = next(g for g in state["gateResults"] if g["id"] == "gate-after")
    assert gate["sourceCommit"] == state["baseline"]["commit"]
    assert "C1:deterministic" not in art.missing_gate_requirements(state, state["acceptanceCriteria"])


def test_an_artifact_recorded_under_an_old_baseline_cannot_back_a_new_gate_after_resume(store_with_run):
    """The exact F7 laundering gap: a gate's own ``sourceCommit`` stamp only
    records what the baseline was WHEN THE GATE was registered -- it proves
    nothing about whether the referenced artifact was actually produced
    against that source. A caller must not be able to register a brand-new
    gate id that simply references an artifact recorded under an EARLIER
    baseline and have it come out stamped (and trusted) as current proof.
    """
    store, repo = store_with_run
    evidence_dir = repo / ".architrave" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    stale_receipt = evidence_dir / "stale-artifact.json"
    initial_commit = store.load("test-run")["baseline"]["commit"]
    stale_receipt.write_text(
        json.dumps({"status": "pass", "exitCode": 0, "command": ["true"], "commit": initial_commit}),
        encoding="utf-8",
    )
    store._record_deterministic_result(
        "test-run",
        artifact_id="stale-artifact",
        path=str(stale_receipt.relative_to(repo)),
        evidence_refs=[],
    )

    (repo / "README.md").write_text("v2\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "second commit")
    store.resume("test-run", accept_commit=True)

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.record_gate(
            "test-run",
            gate_id="laundered-gate",
            task_id=None,
            gate_type="deterministic",
            status="PASS",
            evidence_refs=["artifact:stale-artifact"],
            criteria=["C1"],
        )
    assert excinfo.value.code == "EVIDENCE_STALE_COMMIT"


def test_a_receipt_replayed_after_baseline_moves_is_denied_at_registration(store_with_run):
    """F7: the deeper laundering gap is not just at ``record_gate`` time -- a
    stale receipt FILE that was never registered while its commit was current
    must not be allowed to masquerade as fresh evidence simply by calling
    ``_record_deterministic_result`` again after the baseline has already
    moved on. The receipt's own declared ``commit`` must match the CURRENT
    baseline at registration time, not just get stamped with whatever "now"
    happens to be.
    """
    store, repo = store_with_run
    evidence_dir = repo / ".architrave" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    old_commit = store.load("test-run")["baseline"]["commit"]

    (repo / "README.md").write_text("v2\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "second commit")
    store.resume("test-run", accept_commit=True)

    # A receipt declaring the now-OLD commit, registered only AFTER the
    # baseline moved, must be denied outright -- not silently stamped fresh.
    replayed_receipt = evidence_dir / "replayed-artifact.json"
    replayed_receipt.write_text(
        json.dumps({"status": "pass", "exitCode": 0, "command": ["true"], "commit": old_commit}),
        encoding="utf-8",
    )
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_deterministic_result(
            "test-run",
            artifact_id="replayed-artifact",
            path=str(replayed_receipt.relative_to(repo)),
            evidence_refs=[],
        )
    assert excinfo.value.code == "EVIDENCE_STALE_COMMIT"

    # A receipt that fails to declare any execution commit at all is rejected too.
    undeclared_receipt = evidence_dir / "undeclared-artifact.json"
    undeclared_receipt.write_text(
        json.dumps({"status": "pass", "exitCode": 0, "command": ["true"]}), encoding="utf-8"
    )
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store._record_deterministic_result(
            "test-run",
            artifact_id="undeclared-artifact",
            path=str(undeclared_receipt.relative_to(repo)),
            evidence_refs=[],
        )
    assert excinfo.value.code == "DETERMINISTIC_RECEIPT"

    # A genuinely fresh receipt (declaring the current, new commit) is fine.
    _record_passing_deterministic_gate(store, repo, gate_id="genuinely-fresh-gate")
    state = store.load("test-run")
    assert "C1:deterministic" not in art.missing_gate_requirements(state, state["acceptanceCriteria"])

    # A freshly-recorded artifact (produced after the baseline moved) is fine.
    _record_passing_deterministic_gate(store, repo, gate_id="fresh-gate")
    state = store.load("test-run")
    assert "C1:deterministic" not in art.missing_gate_requirements(state, state["acceptanceCriteria"])


def _write_receipt(repo: Path, name: str, payload: dict) -> Path:
    evidence_dir = repo / ".architrave" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / f"{name}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "recorder_name,path_kind",
    [
        ("_record_semantic_verdict", "semantic"),
        ("_record_security_verdict", "security"),
        ("_record_policy_decision", "policy"),
    ],
)
def test_f2_receipt_missing_its_declared_commit_is_rejected_at_registration(store_with_run, recorder_name, path_kind):
    store, repo = store_with_run
    current_commit = store.load("test-run")["baseline"]["commit"]
    payload = (
        {"verdict": "PASS", "family": "gpt", "criteria": ["C1"]}
        if path_kind == "semantic"
        else {"status": "PASS", "criteria": ["C1"]}
    )
    # Deliberately omit "commit".
    receipt_path = _write_receipt(repo, f"{path_kind}-no-commit", payload)
    recorder = getattr(store, recorder_name)
    with pytest.raises(art.RuntimeFailure) as excinfo:
        recorder(
            "test-run",
            artifact_id=f"{path_kind}-no-commit",
            path=str(receipt_path.relative_to(repo)),
            evidence_refs=[],
        )
    assert "commit" in excinfo.value.message.lower()
    del current_commit


@pytest.mark.parametrize(
    "recorder_name,path_kind,gate_type,family",
    [
        ("_record_semantic_verdict", "semantic", "semantic", "gpt"),
        ("_record_security_verdict", "security", "security", "security"),
        ("_record_policy_decision", "policy", "policy", None),
    ],
)
def test_f2_old_artifact_cannot_back_a_new_semantic_security_or_policy_gate_after_baseline_moves(
    store_with_run, recorder_name, path_kind, gate_type, family
):
    """The F2 scenario: an old semantic/security/policy verdict, genuinely
    produced and registered while it was still current, must not keep
    counting as proof once the Run's baseline has moved to a new commit --
    even though its own ``sourceCommit`` stamp (from when it was first
    registered) is immutable history, a NEW gate id must not be allowed to
    reference it as if it were fresh."""
    store, repo = store_with_run
    old_commit = store.load("test-run")["baseline"]["commit"]
    payload = (
        {"verdict": "PASS", "family": "gpt", "criteria": ["C1"], "commit": old_commit}
        if path_kind == "semantic"
        else {"status": "PASS", "criteria": ["C1"], "commit": old_commit}
    )
    receipt_path = _write_receipt(repo, f"{path_kind}-old", payload)
    recorder = getattr(store, recorder_name)
    recorder("test-run", artifact_id=f"{path_kind}-old", path=str(receipt_path.relative_to(repo)), evidence_refs=[])

    # Genuinely fresh while the baseline still matches: binding a gate now works.
    store.record_gate(
        "test-run",
        gate_id=f"gate-{path_kind}-while-fresh",
        task_id=None,
        gate_type=gate_type,
        status="PASS",
        evidence_refs=[f"artifact:{path_kind}-old"],
        family=family,
        criteria=["C1"],
    )

    (repo / "README.md").write_text("v2\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "second commit")
    store.resume("test-run", accept_commit=True)

    # The SAME old artifact must now be denied for a brand-new gate id.
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.record_gate(
            "test-run",
            gate_id=f"gate-{path_kind}-laundered",
            task_id=None,
            gate_type=gate_type,
            status="PASS",
            evidence_refs=[f"artifact:{path_kind}-old"],
            family=family,
            criteria=["C1"],
        )
    assert excinfo.value.code == "EVIDENCE_STALE_COMMIT"

    # A genuinely fresh receipt (declaring the NEW current commit) is fine.
    new_commit = store.load("test-run")["baseline"]["commit"]
    fresh_payload = (
        {"verdict": "PASS", "family": "gpt", "criteria": ["C1"], "commit": new_commit}
        if path_kind == "semantic"
        else {"status": "PASS", "criteria": ["C1"], "commit": new_commit}
    )
    fresh_path = _write_receipt(repo, f"{path_kind}-fresh", fresh_payload)
    recorder("test-run", artifact_id=f"{path_kind}-fresh", path=str(fresh_path.relative_to(repo)), evidence_refs=[])
    store.record_gate(
        "test-run",
        gate_id=f"gate-{path_kind}-fresh",
        task_id=None,
        gate_type=gate_type,
        status="PASS",
        evidence_refs=[f"artifact:{path_kind}-fresh"],
        family=family,
        criteria=["C1"],
    )
    state = store.load("test-run")
    gate = next(g for g in state["gateResults"] if g["id"] == f"gate-{path_kind}-fresh")
    assert gate["status"] == "PASS"


def test_f2_old_target_repair_artifact_cannot_back_a_new_reality_gate_after_baseline_moves(store_with_run):
    """Same F2 scenario, but for the "reality" gate type / target-repair
    producer -- the staleness check must not be special-cased to only
    deterministic/semantic/security/policy producers."""
    store, repo = store_with_run
    old_commit = store.load("test-run")["baseline"]["commit"]
    evidence_dir = repo / ".architrave" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = evidence_dir / "reality-old.json"
    artifact_path.write_text(json.dumps({"note": "stub reality evidence"}), encoding="utf-8")
    # A reality artifact is registered generically (there is no dedicated
    # recorder exercised here beyond _record_artifact itself, matching how
    # legibility/mutation/external-proof producers are recorded).
    store._record_artifact(
        "test-run",
        artifact_id="reality-old",
        kind="external-proof",
        producer="external-proof",
        actor="external-checkpoint",
        path=str(artifact_path.relative_to(repo)),
        evidence_refs=[],
    )
    del old_commit

    store.record_gate(
        "test-run",
        gate_id="gate-reality-while-fresh",
        task_id=None,
        gate_type="reality",
        status="PASS",
        evidence_refs=["artifact:reality-old"],
        criteria=["C1"],
        surface="runtime",
    )

    (repo / "README.md").write_text("v2\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "second commit")
    store.resume("test-run", accept_commit=True)

    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.record_gate(
            "test-run",
            gate_id="gate-reality-laundered",
            task_id=None,
            gate_type="reality",
            status="PASS",
            evidence_refs=["artifact:reality-old"],
            criteria=["C1"],
            surface="runtime",
        )
    assert excinfo.value.code == "EVIDENCE_STALE_COMMIT"
