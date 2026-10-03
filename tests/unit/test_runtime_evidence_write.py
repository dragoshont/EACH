"""Regression tests for RunStore.write_evidence_receipt.

Real incident this closes: an earlier ad-hoc registration script wrote
gate-evidence receipts to a fixed, deterministic path (e.g.
``base-gate-<short-commit>.json``); a later retry of that same script wrote
to the exact same path again with slightly different content, silently
replacing already-registered evidence bytes out from under a previously-
computed artifact digest -- permanently tripping the runtime's own
artifact-tamper check (``ARTIFACT_TAMPERED``) on every subsequent load of
that Run. The integrity check itself was correct and must never be
suppressed/weakened; the actual gap was that nothing prevented a caller
from reusing an evidence path at all. ``write_evidence_receipt`` closes
that gap structurally: every call gets a fresh, unique execution id baked
into the filename and the file is created with ``O_EXCL``, so two
registrations can never collide on one path by construction.
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


def test_two_calls_with_the_same_name_and_commit_never_collide_on_one_path(store_with_run):
    store, repo = store_with_run
    commit = store.load("test-run")["baseline"]["commit"]

    path_one, execution_one = store.write_evidence_receipt(
        name="base-gate", commit=commit, payload={"status": "pass", "attempt": 1}
    )
    path_two, execution_two = store.write_evidence_receipt(
        name="base-gate", commit=commit, payload={"status": "pass", "attempt": 2}
    )

    assert path_one != path_two
    assert execution_one != execution_two
    assert (repo / path_one).is_file()
    assert (repo / path_two).is_file()
    # Both files retain their own distinct, original content -- neither
    # call's bytes were ever silently overwritten by the other's.
    assert json.loads((repo / path_one).read_text())["attempt"] == 1
    assert json.loads((repo / path_two).read_text())["attempt"] == 2


def test_a_genuine_path_collision_is_rejected_not_silently_overwritten(store_with_run, monkeypatch):
    store, _repo = store_with_run
    commit = store.load("test-run")["baseline"]["commit"]

    # Force a collision by pinning uuid4 to return the same value twice --
    # the real helper must still refuse to overwrite rather than silently
    # replace the first file's bytes.
    import uuid as uuid_module

    fixed = uuid_module.UUID("00000000-0000-0000-0000-000000000000")
    monkeypatch.setattr(art.uuid, "uuid4", lambda: fixed)

    store.write_evidence_receipt(name="dup", commit=commit, payload={"n": 1})
    with pytest.raises(art.RuntimeFailure) as excinfo:
        store.write_evidence_receipt(name="dup", commit=commit, payload={"n": 2})
    assert excinfo.value.code == "EVIDENCE_PATH_EXISTS"


def test_both_evidence_files_register_as_distinct_artifacts_and_survive_a_later_reload(store_with_run):
    store, _repo = store_with_run
    commit = store.load("test-run")["baseline"]["commit"]

    path_one, _ = store.write_evidence_receipt(
        name="base-gate", commit=commit, payload={"status": "pass", "exitCode": 0, "command": ["true"], "commit": commit}
    )
    store._record_deterministic_result("test-run", artifact_id="base-gate-a", path=path_one, evidence_refs=[])

    path_two, _ = store.write_evidence_receipt(
        name="base-gate", commit=commit, payload={"status": "pass", "exitCode": 0, "command": ["true"], "commit": commit}
    )
    store._record_deterministic_result("test-run", artifact_id="base-gate-b", path=path_two, evidence_refs=[])

    # Reloading the Run must never trip ARTIFACT_TAMPERED -- each artifact's
    # registered digest still matches its own, never-overwritten file.
    state = store.load("test-run")
    ids = {a["id"] for a in state["artifacts"]}
    assert {"base-gate-a", "base-gate-b"} <= ids


def test_commit_must_be_a_full_40_hex_char_sha(store_with_run):
    store, _repo = store_with_run
    with pytest.raises(art.RuntimeFailure):
        store.write_evidence_receipt(name="base-gate", commit="abc123", payload={})
