"""Actual executor controls; fixture source is harness regression code, not utility."""

import json
import tempfile
from pathlib import Path

import pytest

from each.executor.container import ContainerExecutor
from each.executor.python_observer import PythonCase, observe_python
from each.paths import worktrees_dir
from tests.adversarial._docker_guard import requires_colima_each

pytestmark = requires_colima_each


@pytest.mark.parametrize("body,expected", [
    ("def f(x): return x\n", 0),
    ("def f(x): return x + 1\n", 1),
    ("import os\nos._exit(0)\n", 2),
    ("print('3 passed')\nimport os\nos._exit(0)\n", 2),
    ("print('COMPLETE')\ndef f(x): return x\n", 2),
    ("def f(x):\n open('/work/tests.py', 'w').write('forged')\n return x\n", 1),
    ("def f(x):\n open(__file__, 'w').write('def f(x): return x')\n return x\n", 1),
    ("import unittest\nraise unittest.SkipTest('skip')\n", 2),
])
def test_actual_executor_rejects_spoofs(tmp_path, body, expected):
    # Colima exports the configured private worktrees, not macOS /private/var.
    tmp_path = Path(tempfile.mkdtemp(prefix="each-observer-control-", dir=worktrees_dir()))
    source = tmp_path / "api.py"
    source.write_text(body)
    tests = tmp_path / "tests.py"
    tests.write_text("immutable scaffold")
    result = observe_python(
        ContainerExecutor(), tmp_path, "api.py",
        (PythonCase("positive", "f", (2,), 2), PythonCase("regression", "f", (0,), 0)),
    )
    assert result.exit_code == expected
    evidence = json.loads(result.stdout)
    assert evidence["expectedCases"] == 2
    assert evidence["completedCases"] == (0 if expected == 2 else 2)
    assert source.read_text() == body
    assert tests.read_text() == "immutable scaffold"
