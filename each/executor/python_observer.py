"""Trusted-host black-box comparison for standalone, JSON-shaped Python APIs.

Only the invocation and input enter the candidate container. Expected answers,
case accounting and classification stay in this process. The entire worktree
is read-only; each case gets a fresh no-egress container. This is not a pytest
plugin, a TEE, or support for arbitrary Python projects. A candidate controls
its outputs, not the independent comparison of those outputs.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from each.executor.base import ExecutionResult
from each.executor.container import ContainerExecutor, ContainerExecutorError
from each.hashing import sha256_file, sha256_text
from each.paths import assert_no_symlink_escape

_WORKER = """
import importlib.util, json, sys
path, function, payload = sys.argv[1:]
spec = importlib.util.spec_from_file_location("observed_target", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
args = json.loads(payload)
try:
    result = getattr(module, function)(*args)
except Exception as exc:
    response = {"error": type(exc).__name__}
else:
    response = {"value": result}
print(json.dumps(response, allow_nan=False, sort_keys=True))
"""


@dataclass(frozen=True)
class PythonCase:
    case_id: str
    function: str
    args: tuple[Any, ...]
    expected: Any = None
    error: str | None = None


def observe_python(
    executor: ContainerExecutor,
    worktree: Path,
    source_path: str,
    cases: tuple[PythonCase, ...],
    *,
    timeout: int = 15,
) -> ExecutionResult:
    """Return only host-computed case counts/status, never candidate test text.

    Exit 0: every declared case returned the exact expected JSON observation.
    Exit 1: complete observations include a genuine behavioral mismatch.
    Exit 2: incomplete/invalid observation, timeout, source drift or launch error.
    Equality is canonical JSON, so True does not masquerade as numeric 1.
    """
    if not cases or len({c.case_id for c in cases}) != len(cases):
        raise ValueError("nonempty cases with unique identifiers required")
    if source_path.startswith("/") or ".." in Path(source_path).parts:
        raise ValueError("source path must be worktree-relative")
    source = worktree / source_path
    assert_no_symlink_escape(source, label="observed source")
    subject = sha256_file(source)
    contract = sha256_text(json.dumps([asdict(c) for c in cases], sort_keys=True, allow_nan=False))
    observations = []
    for case in cases:
        if not case.function.isidentifier() or not case.case_id:
            raise ValueError("named cases and simple exported functions required")
        try:
            result = executor.run(
                ["python", "-I", "-c", _WORKER, f"/work/{source_path}", case.function,
                 json.dumps(case.args, allow_nan=False)],
                worktree, timeout=timeout, read_only_worktree=True,
            )
            response = json.loads(result.stdout)
            expected = {"error": case.error} if case.error else {"value": case.expected}
            complete = result.exit_code == 0 and isinstance(response, dict) and (
                set(response) in ({"value"}, {"error"})
            )
            matched = complete and json.dumps(response, sort_keys=True, allow_nan=False) == json.dumps(
                expected, sort_keys=True, allow_nan=False
            )
            status = "pass" if matched else "fail" if complete else "incomplete"
        except (ContainerExecutorError, ValueError, TypeError):
            status = "incomplete"
        observations.append({"caseId": case.case_id, "status": status})
    unchanged = sha256_file(source) == subject
    incomplete = not unchanged or any(o["status"] == "incomplete" for o in observations)
    exit_code = 2 if incomplete else 1 if any(o["status"] == "fail" for o in observations) else 0
    evidence = {
        "observer": "trusted-host-json-v1",
        "observerSha256": sha256_file(Path(__file__)),
        "workerSha256": sha256_text(_WORKER),
        "contractSha256": contract,
        "subjectSha256": subject,
        "sourceUnchanged": unchanged,
        "expectedCases": len(cases),
        "completedCases": sum(o["status"] != "incomplete" for o in observations),
        "cases": observations,
        "exitCode": exit_code,
    }
    return ExecutionResult(
        command=("trusted-host-json-v1", source_path, contract),
        exit_code=exit_code, stdout=json.dumps(evidence, sort_keys=True), stderr="",
    )
