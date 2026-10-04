"""Actual no-egress fault drills; only public self-authored harness fixtures."""

import errno
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from each.attestation import verify_materials_root, verify_receipt
from each.executor.container import ContainerExecutor, derive_assurance_level
from each.executor.python_observer import PythonCase, observe_python
from each.hashing import sha256_text
from each.paths import runs_dir, worktrees_dir
from each.signing import public_key_path
from tests.adversarial._docker_guard import requires_colima_each
from tests.unit.test_receipt_write_safety import _receipt

pytestmark = requires_colima_each


@pytest.fixture(autouse=True)
def private_owned_store(monkeypatch):
    # Colima only exports $HOME. Every drill uses a new named owned store and
    # TEMPORARY key. Keep its tiny private negative receipts for inspection.
    home = Path(tempfile.mkdtemp(prefix=".each-p3p4-runtime-", dir=Path.home()))
    monkeypatch.setenv("EACH_HOME", str(home))


def fixture_source(body):
    root = Path(tempfile.mkdtemp(prefix="owned-fixture-", dir=worktrees_dir()))
    (root / "api.py").write_text(body)
    return root


def assert_isolated(executor, root):
    probe = executor.verify_isolation(root)
    assert derive_assurance_level(executor, probe) == "EACH-P2"


def test_actual_observer_timeout_retains_honest_signed_fixture_evidence():
    body = "import time\ndef f(x):\n    time.sleep(60)\n    return x\n"
    root = fixture_source(body)
    executor = ContainerExecutor()
    assert_isolated(executor, root)
    result = observe_python(executor, root, "api.py", (PythonCase("timeout", "f", (1,), 1),), timeout=1)
    assert result.exit_code == 2
    assert json.loads(result.stdout)["completedCases"] == 0
    receipt = _receipt(
        run_id="synthetic-observer-timeout", raw_completion="public deterministic fixture, no inference",
        materials={"api.py": sha256_text(body)}, repaired_result={"exit_code": result.exit_code},
        outcome="REPAIRED_RUN_INCONCLUSIVE",
    )
    path, _ = receipt.write(runs_dir() / "timeout", materials_source=root)
    data = json.loads(path.read_text())
    assert verify_receipt(data, public_key_path().read_bytes())["status"] == "PASS"
    assert verify_materials_root(data, path.parent / "materials")["status"] == "PASS"


def test_actual_small_tmpfs_enospc_is_bounded_and_not_success():
    root = fixture_source("public synthetic disk exercise, not executed as source\n")

    class SmallMountExecutor(ContainerExecutor):
        def build_docker_command(self, *args, **kwargs):
            cmd = super().build_docker_command(*args, **kwargs)
            index = cmd.index(self.image)
            cmd[index:index] = ["--tmpfs", "/quota:size=1048576,mode=0700"]
            return cmd

    executor = SmallMountExecutor()
    assert_isolated(executor, root)
    script = (
        "import errno,json,os,sys\n"
        "try:\n"
        " with open('/quota/owned-test.bin','wb') as f:\n"
        "  f.write(b'x'*(2*1024*1024)); f.flush(); os.fsync(f.fileno())\n"
        "except OSError as e:\n"
        " print(json.dumps({'errno':e.errno,'limitBytes':1048576}));sys.exit(1)\n"
        "sys.exit(0)\n"
    )
    result = executor.run(["python", "-I", "-c", script], root, timeout=20, read_only_worktree=True)
    assert result.exit_code == 1
    assert json.loads(result.stdout) == {"errno": errno.ENOSPC, "limitBytes": 1048576}
    assert (root / "api.py").read_text() == "public synthetic disk exercise, not executed as source\n"


def test_concurrent_actual_observers_do_not_mix_subjects():
    executor = ContainerExecutor()
    roots = [fixture_source("def f(x): return x\n"), fixture_source("def f(x): return x + 1\n")]
    assert_isolated(executor, roots[0])

    def observe(index):
        return observe_python(executor, roots[index], "api.py", (PythonCase("case", "f", (3,), 3),))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(observe, range(2)))
    assert [r.exit_code for r in results] == [0, 1]
    assert len({json.loads(r.stdout)["subjectSha256"] for r in results}) == 2


@pytest.mark.parametrize("interruption", ["sigint", "container-kill"])
def test_exact_owned_executor_interrupt_cleanup(interruption):
    """SIGINT is sent to the exact child PID; container kill uses exact CID."""
    root = fixture_source("public interruption fixture, not imported on host\n")
    executor = ContainerExecutor()
    assert_isolated(executor, root)
    token = uuid.uuid4().hex
    cidfile = root / "owned.cid"
    name = "each-p3p4-" + token
    # Child uses the product executor. The only test seam records Docker's
    # actual CID and an ownership label before its sleep-only harness command.
    child_code = (
        "import sys\nfrom pathlib import Path\n"
        "from each.executor.container import ContainerExecutor\n"
        "class Owned(ContainerExecutor):\n"
        " def build_docker_command(self,*a,**k):\n"
        "  cmd=super().build_docker_command(*a,**k);i=cmd.index(self.image)\n"
        f"  cmd[i:i]=['--cidfile',{str(cidfile)!r},'--label','each.p3p4.owner={token}'];return cmd\n"
        "try:\n"
        f" r=Owned().run(['python','-I','-c','import time; time.sleep(60)'],Path({str(root)!r}),"
        f"timeout=30,container_name={name!r},read_only_worktree=True)\n"
        " print(r.exit_code)\n"
        "except KeyboardInterrupt:\n"
        " sys.exit(130)\n"
    )
    child = subprocess.Popen([sys.executable, "-c", child_code], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cid = None
    try:
        deadline = time.monotonic() + 20
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
            time.sleep(0.1)
        else:
            pytest.fail("owned container did not become ready")
        if interruption == "sigint":
            os.kill(child.pid, signal.SIGINT)
        else:
            killed = subprocess.run(
                ["docker", "--context", "colima-each", "kill", "--signal", "KILL", cid],
                capture_output=True, text=True, timeout=10, check=False,
            )
            assert killed.returncode == 0
        stdout, _stderr = child.communicate(timeout=40)
        if interruption == "sigint":
            assert child.returncode == 130
        else:
            assert child.returncode == 0 and stdout.strip() == b"137"
        gone = subprocess.run(
            ["docker", "--context", "colima-each", "inspect", cid],
            capture_output=True, timeout=10, check=False,
        )
        assert gone.returncode != 0
    finally:
        if child.poll() is None:
            os.kill(child.pid, signal.SIGKILL)
            child.communicate(timeout=10)
        if cid:
            # Exact owned CID only, never name filters or broad Docker prune.
            subprocess.run(
                ["docker", "--context", "colima-each", "rm", "--force", cid],
                capture_output=True, timeout=10, check=False,
            )
