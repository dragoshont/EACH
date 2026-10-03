import json
import subprocess

import pytest

from harness.architrave_runtime import RunStore, RuntimeFailure


def setup_store(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in [("init", "-q"), ("config", "user.email", "test@example.com"),
                 ("config", "user.name", "Test")]:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("test\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=repo, check=True, capture_output=True)
    store = RunStore(repo)
    state = store.create(goal="test", outcome="test", criteria=[{"id": "C", "description": "test"}],
                         run_id="old", autonomy_scope="approved-program",
                         policy_allow=[{"scope": "repository", "operations": ["edit"]}])
    path, _ = store.write_evidence_receipt(name="test", commit=state["baseline"]["commit"],
                                         payload={"status": "pass", "exitCode": 0, "command": ["test"],
                                                  "commit": state["baseline"]["commit"]})
    store._record_deterministic_result("old", artifact_id="evidence", path=path, evidence_refs=[])
    store.add_task("old", {"id": "T", "objective": "test", "acceptanceCriteria": ["C"],
                          "mutablePaths": ["each"]})
    return store, repo / path


def test_unavailable_old_artifact_does_not_block_without_active_lease(tmp_path):
    store, artifact = setup_store(tmp_path)
    artifact.unlink()
    with pytest.raises(RuntimeFailure, match="artifact"):
        store.load("old")
    assert store._cross_run_mutation_conflicts("new", ["each"]) == []


def test_active_lease_blocks_even_when_artifact_missing(tmp_path):
    store, artifact = setup_store(tmp_path)
    store.start_task("old", "T", worker_id="worker")
    artifact.unlink()
    assert store._cross_run_mutation_conflicts("new", ["each"]) == ["old:T"]


def test_unauthenticated_state_cannot_release_resource(tmp_path):
    store, _ = setup_store(tmp_path)
    store.start_task("old", "T", worker_id="worker")
    path = store.run_dir("old") / "run.json"
    state = json.loads(path.read_text())
    state["tasks"][0]["status"] = "COMPLETED"
    state["tasks"][0]["lease"] = None
    path.write_text(json.dumps(state))
    with pytest.raises(RuntimeFailure, match="cannot validate active resource"):
        store._cross_run_mutation_conflicts("new", ["each"])
