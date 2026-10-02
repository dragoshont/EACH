"""F7 regression: a gate recorded as PASS against an earlier source commit
must not keep satisfying a requirement once the Run's baseline has moved to
a different commit (``resume(accept_commit=True)``) -- a gate's own proof
is tied to the exact source it verified, not a standing credential.
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
    receipt_path.write_text(
        json.dumps({"status": "pass", "exitCode": 0, "command": ["true"]}), encoding="utf-8"
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
    stale_receipt.write_text(json.dumps({"status": "pass", "exitCode": 0, "command": ["true"]}), encoding="utf-8")
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

    # A freshly-recorded artifact (produced after the baseline moved) is fine.
    _record_passing_deterministic_gate(store, repo, gate_id="fresh-gate")
    state = store.load("test-run")
    assert "C1:deterministic" not in art.missing_gate_requirements(state, state["acceptanceCriteria"])
