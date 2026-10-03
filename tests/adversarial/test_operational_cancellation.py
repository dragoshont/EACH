"""Actual benchmark API interruption, not a composed cleanup claim."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest

from each.attestation import verify_materials_root, verify_receipt
from tests.adversarial._docker_guard import requires_colima_each

pytestmark = requires_colima_each


def test_candidate_container_reads_exact_new_bytes_after_baseline(monkeypatch):
    from each import benchmark
    from each.executor.container import ContainerExecutor
    from each.executor.python_observer import PythonCase
    from each.hashing import sha256_file
    from each.models.fixture import FixtureModel

    root = Path(tempfile.mkdtemp(prefix=".each-p3p4-fidelity-", dir=Path.home()))
    monkeypatch.setenv("EACH_HOME", str(root / "store"))
    source = root / "source"
    source.mkdir()
    (source / "api.py").write_text("def f(x): return x + 1\n")
    monkeypatch.setattr(benchmark, "materialize_task_sources", lambda task: (source, ["api.py"]))
    monkeypatch.setattr(benchmark, "materialize_known_fix", lambda task: "not supplied to Builder")
    observed_roots = []

    class FidelityExecutor(ContainerExecutor):
        def run(self, command, worktree, **kwargs):
            if "/work/api.py" in command:
                probe = super().run(
                    ["python", "-I", "-c",
                     "import pathlib,hashlib;print(hashlib.sha256(pathlib.Path('/work/api.py').read_bytes()).hexdigest())"],
                    worktree, read_only_worktree=True,
                )
                assert probe.exit_code == 0 and probe.stdout.strip() == sha256_file(worktree / "api.py")
                observed_roots.append(worktree)
            return super().run(command, worktree, **kwargs)

    monkeypatch.setattr(benchmark, "ContainerExecutor", FidelityExecutor)
    task = benchmark.BenchmarkTask(
        task_id="synthetic-fidelity", repo="example/public-synthetic", license="Apache-2.0",
        pre_fix_sha="a" * 40, fix_sha="b" * 40, bug_path="api.py", test_paths=(),
        test_command=("trusted-host-json-v1",), problem_statement="Identity harness fixture.",
        observation_cases=(PythonCase("case", "f", (1,), 1),), proposal_format="full_source",
    )
    result = benchmark.run_benchmark_task(
        task, FixtureModel("BEGIN_SOURCE\ndef f(x):\n    return x\nEND_SOURCE"), max_attempts=1,
    )
    assert result["outcome"] == "REPAIR_VERIFIED"  # Canned fixture, not utility.
    assert len(observed_roots) == 2 and observed_roots[0] != observed_roots[1]


@pytest.mark.parametrize("method", ["sigint", "container-kill"])
def test_actual_benchmark_interruption_keeps_trajectory_and_partial_receipt(method):
    root = Path(tempfile.mkdtemp(prefix=".each-p3p4-cancellation-", dir=Path.home()))
    root.chmod(0o700)
    token = uuid.uuid4().hex
    cidfile = root / "owned-candidate.cid"
    # Only this PUBLIC synthetic fixture enters Docker. No local-model loading
    # or private firstslice content; this is not a utility repair attempt.
    code = f"""
import json
from pathlib import Path
from each import benchmark
from each.executor.container import ContainerExecutor
from each.executor.python_observer import PythonCase
from each.models.fixture import FixtureModel
root=Path({str(root)!r})
source=root/'source';source.mkdir()
(source/'api.py').write_text('def f(x): return x + 1\\n')
benchmark.materialize_task_sources=lambda task:(source,['api.py'])
benchmark.materialize_known_fix=lambda task:'not a target solution'
class Owned(ContainerExecutor):
 def build_docker_command(self,command,worktree,**kwargs):
  cmd=super().build_docker_command(command,worktree,**kwargs)
  if (worktree/'api.py').is_file() and 'sleep' in (worktree/'api.py').read_text():
   i=cmd.index(self.image)
   cmd[i:i]=['--cidfile',{str(cidfile)!r},'--label','each.p3p4.owner={token}']
  return cmd
 def run(self,*args,**kwargs):
  result=super().run(*args,**kwargs)
  with (root/'executor-status.jsonl').open('a') as handle:
   handle.write(json.dumps({{'exitCode':result.exit_code,'stderrSha256':__import__('hashlib').sha256(result.stderr.encode()).hexdigest(),'stderrKinds':[kind for kind in ('already exists','permission denied','invalid','unknown flag','read-only') if kind in result.stderr.lower()],'errorTypes':[line.split(':',1)[0] for line in result.stderr.splitlines() if line.split(':',1)[0] in ('SyntaxError','NameError','FileNotFoundError','ImportError','IndentationError','PermissionError')]}})+'\\n')
  return result
benchmark.ContainerExecutor=Owned
task=benchmark.BenchmarkTask(
 task_id='synthetic-cancel',repo='example/public-synthetic',license='Apache-2.0',
 pre_fix_sha='a'*40,fix_sha='b'*40,bug_path='api.py',test_paths=(),
 test_command=('trusted-host-json-v1',),problem_statement='Identity harness fixture.',
 observation_cases=(PythonCase('case','f',(1,),1),),proposal_format='full_source')
model=FixtureModel('BEGIN_SOURCE\\nimport time\\ndef f(x):\\n    time.sleep(60)\\n    return x\\nEND_SOURCE')
result=benchmark.run_benchmark_task(task,model,max_attempts=1,run_id='actual-cancel')
(root/'result.json').write_text(json.dumps(result))
"""
    env = os.environ.copy()
    env["EACH_HOME"] = str(root / "store")
    child = subprocess.Popen(
        [sys.executable, "-c", code], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    cid = None
    try:
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if cidfile.exists() and cidfile.read_text().strip():
                cid = cidfile.read_text().strip()
                inspected = subprocess.run(
                    ["docker", "--context", "colima-each", "inspect", cid],
                    capture_output=True, text=True, timeout=10, check=False,
                )
                if inspected.returncode == 0 and json.loads(inspected.stdout)[0]["State"]["Running"]:
                    info = json.loads(inspected.stdout)[0]
                    assert info["Config"]["Labels"]["each.p3p4.owner"] == token
                    assert info["HostConfig"]["NetworkMode"] == "none"
                    break
            if child.poll() is not None:
                _, error = child.communicate(timeout=5)
                error_type = error.decode("utf-8", "replace").splitlines()[-1].split(":", 1)[0] if error else "none"
                result_path = root / "result.json"
                outcome = json.loads(result_path.read_text())["outcome"] if result_path.exists() else "no-result"
                statuses_path = root / "executor-status.jsonl"
                statuses = statuses_path.read_text() if statuses_path.exists() else "no-executor-status"
                pytest.fail(f"fixture ended before interruption: exit={child.returncode}, type={error_type}, {outcome}; {statuses}")
            time.sleep(0.1)
        else:
            pytest.fail("owned candidate container never became ready")
        if method == "sigint":
            os.kill(child.pid, signal.SIGINT)
        else:
            assert subprocess.run(
                ["docker", "--context", "colima-each", "kill", "--signal", "KILL", cid],
                capture_output=True, timeout=10, check=False,
            ).returncode == 0
        child.communicate(timeout=45)
        assert child.returncode == 0, "interruption escaped without a signed partial receipt"
        result = json.loads((root / "result.json").read_text())
        assert result["outcome"] in {"EXECUTION_ERROR", "REPAIRED_RUN_INCONCLUSIVE"}
        path = Path(result["receipt_json"])
        receipt = json.loads(path.read_text())
        public = (root / "store/keys/each-signing-ed25519-public.pem").read_bytes()
        assert receipt["selectedAttempt"] == 1
        assert len(receipt["attempts"]) == 1
        assert receipt["rawCompletion"] == (
            "BEGIN_SOURCE\nimport time\ndef f(x):\n    time.sleep(60)\n    return x\nEND_SOURCE"
        )
        assert receipt["patchText"]
        assert verify_receipt(receipt, public)["status"] == "PASS"
        assert verify_materials_root(receipt, path.parent / "materials")["status"] == "PASS"
        assert subprocess.run(
            ["docker", "--context", "colima-each", "inspect", cid],
            capture_output=True, timeout=10, check=False,
        ).returncode != 0
    finally:
        if child.poll() is None:
            os.kill(child.pid, signal.SIGKILL)
            child.communicate(timeout=10)
        if cid:
            subprocess.run(
                ["docker", "--context", "colima-each", "rm", "--force", cid],
                capture_output=True, timeout=10, check=False,
            )
