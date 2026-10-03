"""The M6 historical-benchmark harness.

Runs the same approved-spec -> sanitized worktree -> model -> patch ->
no-network container -> audited/attested receipt pipeline as
:mod:`each.bakeoff`, generalized from the single hello-repair toy fixture
to arbitrary *real* historical bug-fix tasks drawn from permissively
licensed public repositories.

Materialization (fetching each task's pre-fix buggy source and the fix
commit's test file over the network) happens here, on the host, before any
sealed execution -- exactly like M2's model-weight download and M1's
spec/materials provisioning. The actual test *execution* -- both the
failing baseline run and the repaired run -- still goes through
:class:`~each.executor.container.ContainerExecutor` with ``network="none"``.
The model is never shown the known historical fix; it only ever receives
the pre-fix buggy source and a neutral problem statement. The known fix is
recorded in the benchmark *report* only after generation has completed, for
human review -- never fed back into a prompt or a retry.
"""

from __future__ import annotations

import ast
import dataclasses
import re
import shlex
import subprocess
import tarfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from each.audit.run import reject_on_audit_flag, run_audit
from each.demo import _DOCKER_LAUNCH_FAILURE_EXIT_CODES, _result_to_dict
from each.executor.base import ExecutionResult
from each.executor.container import ContainerExecutor, derive_assurance_level
from each.hashing import sha256_bytes
from each.models.base import ContextBudgetExceeded, RepairModel
from each.outcome import sanitize_outcome_class
from each.patch import PatchRejected, apply_patch, extract_patch_text, parse_patch
from each.paths import cache_dir, runs_dir
from each.receipt import Receipt
from each.spec import ApprovedSpec, make_spec_packet
from each.worktree import build_worktree

# The M1 default image (python:3.12-slim) has no test runner beyond
# stdlib unittest; historical repair tasks are run with pytest, which is
# pre-installed into this separately pinned image (see
# docker/benchmark-runtime/Dockerfile) before any sealed run -- never
# installed inside the no-network container at execution time.
BENCHMARK_IMAGE_DIGEST = (
    "each-benchmark-runtime@sha256:6150f4259b1dc7590817dd7d31021c2f56de367463a970d8ab04e1e9d371e4dc"
)

_PYTEST_PASSED_RE = re.compile(r"(\d+) passed")
_PYTEST_FAILED_RE = re.compile(r"(\d+) failed")
_PYTEST_SKIPPED_RE = re.compile(r"(\d+) skipped")
_PYTEST_ERROR_RE = re.compile(r"(\d+) error")


class BenchmarkExecutionError(RuntimeError):
    """Raised when a pytest run cannot be honestly classified as pass or fail."""


@dataclasses.dataclass(frozen=True)
class BenchmarkTask:
    """One real historical bug-fix task, verified by hand before inclusion.

    ``pre_fix_sha`` is the parent of the fix commit (the buggy revision);
    ``fix_sha`` is the commit that both fixes the bug and adds/strengthens
    the regression test proving it. ``problem_statement`` must never
    describe the actual code-level fix -- only the observable symptom.
    """

    task_id: str
    repo: str  # "org/repo"
    license: str
    pre_fix_sha: str
    fix_sha: str
    bug_path: str
    test_paths: tuple[str, ...]
    test_command: tuple[str, ...]
    problem_statement: str
    language: str = "python"
    expected_tests: int = 1
    # Real third-party runtime/test-only dependencies the task's own test
    # suite needs to import (e.g. the package's actual declared runtime
    # deps, or a test-only dependency like freezegun/hypothesis/pytest-mock
    # noted in curation). Installed at materialization time (host network),
    # never inside the sealed no-network container.
    extra_pip_packages: tuple[str, ...] = ()


def _raw_url(repo: str, sha: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"


def _tarball_url(repo: str, sha: str) -> str:
    return f"https://codeload.github.com/{repo}/tar.gz/{sha}"


def fetch_file(repo: str, sha: str, path: str, *, timeout: int = 20) -> str:
    """Fetch one file's content from a public GitHub repo at an exact commit.

    This is a materialization-time, host-network fetch (like M2's model
    download) -- never performed inside the sealed execution container.
    """
    url = _raw_url(repo, sha, path)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise BenchmarkExecutionError(f"could not fetch {url}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise BenchmarkExecutionError(f"could not fetch {url}: {exc.reason}") from exc


def _extract_repo_tree(repo: str, sha: str, dest: Path, *, timeout: int = 60) -> Path:
    """Download and extract a full repo snapshot at an exact commit.

    Many real historical tasks are single files within a larger importable
    package (internal cross-module imports); fetching only the bug file is
    not enough to actually import and run the real test suite. Uses
    GitHub's stable ``codeload`` tarball endpoint, which names its single
    top-level directory deterministically as ``<repo-name>-<full-sha>``.
    Cached: skipped if ``dest`` already has content.
    """
    if any(dest.iterdir()) if dest.exists() else False:
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    url = _tarball_url(repo, sha)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        raise BenchmarkExecutionError(f"could not fetch repo tarball {url}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise BenchmarkExecutionError(f"could not fetch repo tarball {url}: {exc.reason}") from exc

    tar_path = dest / ".download.tar.gz"
    tar_path.write_bytes(data)
    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            members = tar.getmembers()
            prefix = members[0].name.split("/", 1)[0] + "/" if members else ""
            for member in members:
                if not member.name.startswith(prefix):
                    continue
                relative = member.name[len(prefix) :]
                if not relative:
                    continue
                if member.isfile():
                    target = dest / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    extracted = tar.extractfile(member)
                    if extracted is not None:
                        target.write_bytes(extracted.read())
    finally:
        tar_path.unlink(missing_ok=True)
    return dest


def _package_root_dir(bug_path: str) -> str:
    """The top-level importable package directory containing ``bug_path``.

    E.g. ``"src/requests/utils.py"`` -> ``"src/requests"``;
    ``"click/core.py"`` -> ``"click"``.
    """
    parts = Path(bug_path).parts
    if parts[0] == "src" and len(parts) > 1:
        return str(Path(*parts[:2]))
    return parts[0]


def _list_files_relative(root: Path, subdir: str) -> list[str]:
    base = root / subdir
    if base.is_file():
        return [subdir]
    if base.is_dir():
        return sorted(str(p.relative_to(root)) for p in base.rglob("*") if p.is_file())
    return []


def materialize_task_sources(task: BenchmarkTask) -> tuple[Path, list[str]]:
    """Materialize a real, importable snapshot of this task's package.

    Returns ``(source_root, include_paths)`` suitable for ``build_worktree()``:
    - the whole package directory containing ``task.bug_path`` is extracted
      at ``task.pre_fix_sha`` (buggy) from a real repo tarball snapshot --
      not just the single bug file -- so the real test suite's internal
      cross-module imports actually resolve;
    - each of ``task.test_paths`` (and, best-effort, any sibling
      ``conftest.py``) is overlaid at ``task.fix_sha`` (the regression test
      the fix commit added/strengthened);
    - any declared ``extra_pip_packages`` (the task's real third-party
      runtime/test deps) are installed into ``<root>/.each-deps`` via
      ``uv pip install --target`` -- host network, never inside the sealed
      container.
    Re-extraction/re-fetch/re-install are all skipped once already cached.
    The cache directory is keyed by both ``task.task_id`` and
    ``task.pre_fix_sha`` (not task_id alone): a task_id-only cache key could
    silently keep serving a stale/mislabeled tree extracted under an earlier,
    different sha (e.g. from an earlier ad-hoc debugging session) forever,
    since ``_extract_repo_tree`` only checks "does this directory already
    have content", not "does this content actually match this exact sha".
    Binding the path to the sha means any content ever associated with a
    different sha lives under a different, unused directory.
    """
    root = cache_dir() / "benchmark" / task.task_id / task.pre_fix_sha / "source"
    _extract_repo_tree(task.repo, task.pre_fix_sha, root)

    for test_path in task.test_paths:
        test_dest = root / test_path
        test_dest.parent.mkdir(parents=True, exist_ok=True)
        test_dest.write_text(fetch_file(task.repo, task.fix_sha, test_path), encoding="utf-8")

    deps_dir = root / ".each-deps"
    if task.extra_pip_packages and not deps_dir.exists():
        deps_dir.mkdir(parents=True, exist_ok=True)
        # The deps are installed on the host (for network access) but RUN
        # inside the Linux container, which is a different platform than a
        # macOS host. Without pinning --python-platform, uv resolves/fetches
        # wheels for the host OS, which silently breaks any package with a
        # compiled native extension (observed for real: hypothesis's Rust
        # _native module) when it later runs inside the Linux container.
        proc = subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--target",
                str(deps_dir),
                "--python-platform",
                "aarch64-unknown-linux-gnu",
                "--python-version",
                "3.12",
                *task.extra_pip_packages,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0:
            raise BenchmarkExecutionError(f"could not install {task.extra_pip_packages}: {proc.stderr}")

    # Colima's container runtime cannot read files more restrictive than
    # the extracting process's umask allowed; make the whole materialized
    # tree world-readable/traversable so the (different-uid) container can
    # actually see it, regardless of the original repo's committed modes.
    for path in root.rglob("*"):
        path.chmod(path.stat().st_mode | 0o444 | (0o111 if path.is_dir() else 0))

    package_root = _package_root_dir(task.bug_path)
    test_root_dirs = {Path(p).parts[0] for p in task.test_paths}
    include_paths = sorted(
        set(_list_files_relative(root, package_root))
        | set(_list_files_relative(root, ".each-deps"))
        | {rel for test_root in test_root_dirs for rel in _list_files_relative(root, test_root)}
    )
    return root, include_paths


def pythonpath_for(task: BenchmarkTask) -> str:
    """The sys.path additions a worktree-relative test run needs: the repo
    root and ``src/`` (covers both historical layouts) plus any installed
    third-party deps -- never relying on the sealed container's own image
    having the target package or its deps pre-installed."""
    del task  # identical for every task; kept as a function for a clear single call site.
    return "/work:/work/src:/work/.each-deps"


def _wrapped_test_command(task: BenchmarkTask) -> list[str]:
    """Wrap ``task.test_command`` with the PYTHONPATH it needs to actually
    import the real historical package and its installed deps, without any
    change to ContainerExecutor's scrubbed-environment isolation guarantee
    (the env var is set by the invoked shell, not injected into docker)."""
    inner = shlex.join(task.test_command)
    return ["sh", "-c", f"PYTHONPATH={pythonpath_for(task)} {inner}"]


def materialize_known_fix(task: BenchmarkTask) -> str:
    """Fetch the historical fix's post-fix bug-source content for the report.

    Deliberately separate from :func:`materialize_task_sources` (which only
    ever feeds the model's worktree): callers must only invoke this *after*
    generation/audit has completed, to compare against -- never to build
    the prompt or a retry.
    """
    return fetch_file(task.repo, task.fix_sha, task.bug_path)


def _interpret_pytest_run(result: ExecutionResult, *, expected_tests: int) -> str:
    """Classify one pytest acceptance-command run as 'passed' or 'failed'.

    Mirrors each.demo._interpret_test_run's honesty discipline for
    pytest's summary line instead of unittest's: a Docker launch failure,
    any skip/error, or a test-count mismatch is never silently folded into
    a pass/fail verdict.
    """
    if result.exit_code in _DOCKER_LAUNCH_FAILURE_EXIT_CODES:
        raise BenchmarkExecutionError(
            f"container launch failed (exit {result.exit_code}); this is not test evidence: "
            f"{result.stderr or result.stdout}"
        )
    combined = result.stdout + result.stderr
    skipped_match = _PYTEST_SKIPPED_RE.search(combined)
    error_match = _PYTEST_ERROR_RE.search(combined)
    if (skipped_match and int(skipped_match.group(1)) > 0) or (error_match and int(error_match.group(1)) > 0):
        raise BenchmarkExecutionError(f"run included skipped tests or collection errors, not a clean pass/fail: {combined!r}")
    passed_match = _PYTEST_PASSED_RE.search(combined)
    failed_match = _PYTEST_FAILED_RE.search(combined)
    passed = int(passed_match.group(1)) if passed_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    if passed + failed != expected_tests:
        raise BenchmarkExecutionError(
            f"expected exactly {expected_tests} test(s) to run; could not confirm from output: {combined!r}"
        )
    if result.exit_code == 0 and failed == 0 and passed == expected_tests:
        return "passed"
    if result.exit_code != 0 and failed == expected_tests and passed == 0:
        return "failed"
    raise BenchmarkExecutionError(f"ambiguous pytest result, not a clean pass/fail: {combined!r}")


def _node_start_line(node: ast.AST) -> int:
    """A function/class's real first line, including its decorators (ast's
    own ``.lineno`` points at the ``def``/``class`` keyword, not any
    decorator line above it)."""
    decorators = getattr(node, "decorator_list", None) or []
    if decorators:
        return min(d.lineno for d in decorators)
    return node.lineno


def select_prompt_excerpt(bug_source: str, test_sources: list[str]) -> tuple[str, int, int]:
    """Deterministically select the smallest excerpt of ``bug_source`` that
    covers every top-level function/class the already-approved test
    file(s) reference by name (plus any top-level helper, or -- for a
    referenced class -- any class *method*, those referenced defs call
    locally within ``bug_source``).

    This selects by PUBLIC CONTRACT (names the test file actually imports
    and calls) -- it never looks at the known fix's diff or changed-line
    positions, and is computed purely from the pre-fix bug source and the
    pre-fix test source (both already part of the approved spec/materials),
    using only the Python stdlib ``ast`` module.

    Returns ``(excerpt_text, start_line, end_line)``: ``start_line``/
    ``end_line`` are the 1-based inclusive bounding range into the
    ORIGINAL ``bug_source`` that the excerpt was drawn from. For a large
    class where only some methods are actually referenced, unreferenced
    methods are elided from ``excerpt_text`` (replaced by a single
    "lines A-B omitted" comment) rather than included wholesale -- each
    remaining block is itself labeled with its own real absolute line
    range so a patch hunk written against any part of the excerpt can
    still use correct absolute line numbers for the real file (which
    remains on disk in full in the worktree; only the model-facing PROMPT
    is shortened).

    Falls back to the whole file (1, last_line) if the source does not
    parse, or if no top-level def/class name is referenced by any test
    file (e.g. a flat-script bug file with no functions/classes at all).
    """
    total_lines = len(bug_source.splitlines())
    try:
        bug_tree = ast.parse(bug_source)
    except SyntaxError:
        return bug_source, 1, total_lines

    referenced: set[str] = set()
    for test_source in test_sources:
        try:
            test_tree = ast.parse(test_source)
        except SyntaxError:
            continue
        for node in ast.walk(test_tree):
            if isinstance(node, ast.Name):
                referenced.add(node.id)
            elif isinstance(node, ast.Attribute):
                referenced.add(node.attr)

    top_level = [n for n in bug_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    by_name = {n.name: n for n in top_level}

    def _walk_targets_of(node: ast.AST) -> list[ast.AST]:
        # A plain function/async function is walked in full. A class is
        # only walked through the specific methods that will actually
        # survive into the rendered excerpt (per _class_needed_methods'
        # own scoped, class-local expansion) -- never the whole class
        # body -- so an unrelated sibling method's own helper calls can
        # never leak a top-level name into the excerpt purely because it
        # happens to share a class with a genuinely referenced method.
        # The one exception is the documented "no method referenced,
        # keep the whole class" fallback, where the whole class really
        # does end up in the excerpt and so really is a fair walk target.
        if not isinstance(node, ast.ClassDef):
            return [node]
        methods = _method_defs(node)
        needed = _class_needed_methods(node, referenced)
        return [methods[name] for name in needed] if needed else [node]

    selected: set[str] = {name for name in by_name if name in referenced}
    changed = True
    while changed:
        changed = False
        for name in list(selected):
            for target in _walk_targets_of(by_name[name]):
                for inner in ast.walk(target):
                    inner_name = getattr(inner, "id", None) or getattr(inner, "attr", None)
                    if inner_name and inner_name in by_name and inner_name not in selected:
                        selected.add(inner_name)
                        changed = True

    if not selected:
        return bug_source, 1, total_lines

    selected_nodes = [by_name[name] for name in selected]
    start_line = min(_node_start_line(n) for n in selected_nodes)
    end_line = max(getattr(n, "end_lineno", n.lineno) for n in selected_nodes)

    keep_ranges = _resolve_keep_ranges(selected_nodes, referenced)
    excerpt = _render_keep_ranges(bug_source, keep_ranges)
    return excerpt, start_line, end_line


def _method_defs(class_node: ast.ClassDef) -> dict[str, ast.AST]:
    return {
        n.name: n for n in class_node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _class_needed_methods(class_node: ast.ClassDef, referenced: set[str]) -> set[str]:
    """Which of ``class_node``'s own methods are genuinely needed: methods
    the test file references by name directly, plus their *intra-class*
    local call-graph expansion (a referenced method calling another method
    of the same class pulls that one in too). Scoped strictly to this one
    class's methods -- never expands into unrelated sibling methods or
    top-level names, so a method that happens to share a class with a
    referenced method is never pulled in merely by proximity."""
    methods = _method_defs(class_node)
    needed: set[str] = {name for name in methods if name in referenced}
    changed = True
    while changed:
        changed = False
        for name in list(needed):
            for inner in ast.walk(methods[name]):
                inner_name = getattr(inner, "id", None) or getattr(inner, "attr", None)
                if inner_name and inner_name in methods and inner_name not in needed:
                    needed.add(inner_name)
                    changed = True
    return needed


_DOCSTRING_LINE_CAP = 3


def _capped_function_ranges(node: ast.AST) -> list[tuple[int, int]]:
    """A function/method's own keep range(s): its leading docstring (if
    any) is capped to a fixed number of lines (prose/usage-example
    docstrings cost real budget with no repair-relevant benefit) -- a
    fixed constant applied identically regardless of the (unseen) fix, so
    it stays diff-blind and deterministic. Returns one range if the
    docstring fits under the cap (or there isn't one), two if it had to be
    split (the capped docstring head, then the body after it)."""
    start = _node_start_line(node)
    end = getattr(node, "end_lineno", node.lineno)
    body = getattr(node, "body", None) or []
    first_stmt = body[0] if body else None
    if not (isinstance(first_stmt, ast.Expr) and isinstance(getattr(first_stmt, "value", None), ast.Constant)):
        return [(start, end)]
    docstring_end = first_stmt.end_lineno
    if docstring_end - node.lineno <= _DOCSTRING_LINE_CAP:
        return [(start, end)]
    capped_end = node.lineno + _DOCSTRING_LINE_CAP
    body_start = docstring_end + 1
    if body_start > end:
        return [(start, capped_end)]
    return [(start, capped_end), (body_start, end)]


def _resolve_keep_ranges(selected_nodes: list[ast.AST], referenced: set[str]) -> list[tuple[int, int]]:
    """For each selected top-level node, decide exactly which of its own
    lines to literally keep: a plain function/async function keeps its
    whole span (docstring-capped); a class keeps its header (class line +
    capped leading docstring, if any) plus only the methods genuinely
    referenced/called (by the same name-matching + local
    call-graph-expansion discipline used at the top level, scoped to that
    one class, each also docstring-capped) -- any other method is elided."""
    ranges: list[tuple[int, int]] = []
    for node in selected_nodes:
        if not isinstance(node, ast.ClassDef):
            ranges.extend(_capped_function_ranges(node))
            continue

        methods = _method_defs(node)
        needed = _class_needed_methods(node, referenced)

        if not needed:
            # No specific method name was referenced (only the class name
            # itself was) -- keep the whole class rather than guess.
            ranges.append((_node_start_line(node), getattr(node, "end_lineno", node.lineno)))
            continue

        header_end = node.lineno
        first_stmt = node.body[0] if node.body else None
        if isinstance(first_stmt, ast.Expr) and isinstance(getattr(first_stmt, "value", None), ast.Constant):
            header_end = min(first_stmt.end_lineno, node.lineno + _DOCSTRING_LINE_CAP)
        ranges.append((_node_start_line(node), header_end))
        for name in needed:
            ranges.extend(_capped_function_ranges(methods[name]))
    return ranges


def _render_keep_ranges(source: str, keep_ranges: list[tuple[int, int]]) -> str:
    """Render only ``keep_ranges`` (1-based inclusive, merged/sorted) from
    ``source``, inserting a one-line ``# --- lines A-B omitted ---``
    marker for any gap and a real-line-number header before every kept
    block so the model always sees, immediately beside any code it might
    edit, the true absolute line number to use in a diff hunk header."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(keep_ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    lines = source.splitlines(keepends=True)
    pieces: list[str] = []
    prev_end = 0
    for start, end in merged:
        if prev_end and start > prev_end + 1:
            pieces.append(f"# --- lines {prev_end + 1}-{start - 1} omitted ---\n")
        pieces.append(f"# Lines {start}-{end} of the real file (use these exact absolute line numbers):\n")
        pieces.append("".join(lines[start - 1 : end]))
        prev_end = end
    return "".join(pieces)



_PROMPT_TEMPLATE = """You are repairing a real bug in an open-source Python project.

Problem: {problem}

Only this file may be changed: {allowed_paths}

Excerpt of {path} (NOT the whole file -- some parts may be omitted, marked
with a "lines A-B omitted" comment; each kept block below is labeled with
its own REAL absolute line numbers in the file -- preserve those EXACT
numbers in your diff hunk header for whichever block you edit, e.g.
"@@ -N,M +N,M @@" using that block's own starting line N):
```python
{source}
```

Reply with ONLY a unified diff of the required fix, wrapped exactly like
this (no other prose, no markdown fence around the markers):

BEGIN_PATCH
--- a/{path}
+++ b/{path}
@@ -N,M +N,M @@
 <context>
-<original line>
+<fixed line>
END_PATCH
"""

_RETRY_SUFFIX = "\n\nYour previous attempt was rejected: {reason}\nTry again, following the format exactly."


def run_benchmark_task(
    task: BenchmarkTask,
    model: RepairModel,
    *,
    max_attempts: int = 3,
    run_id: str | None = None,
    audit_corpus: list[str] | None = None,
) -> dict[str, Any]:
    """Run one real historical repair task end-to-end and write a receipt.

    Fails closed exactly like each.bakeoff.run_model_bakeoff: if this run's
    isolation probe does not verify no-egress execution, the outcome is
    ISOLATION_UNVERIFIED and no generation/test attempt is made. Network
    access only ever happens during materialize_task_sources (before this
    function's executor/model work begins), never during execution.
    """
    run_id = run_id or f"benchmark-{task.task_id}-{uuid.uuid4().hex[:8]}"
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")

    source_root, include_paths = materialize_task_sources(task)
    bug_source = (source_root / task.bug_path).read_text(encoding="utf-8")
    # Deterministic, diff-blind excerpt selection: uses only the pre-fix test
    # file(s)' own public references and the pre-fix bug file's local call
    # graph (never task.fix_sha/diff content) to shrink real multi-KB
    # whole-file sources down to what the declared model actually supports
    # (see select_prompt_excerpt). Test sources are fetched at pre_fix_sha,
    # not fix_sha, to keep selection independent of the known fix.
    pre_fix_test_sources = [fetch_file(task.repo, task.pre_fix_sha, test_path) for test_path in task.test_paths]
    excerpt_source, excerpt_start_line, excerpt_end_line = select_prompt_excerpt(bug_source, pre_fix_test_sources)
    excerpt_sha256 = sha256_bytes(excerpt_source.encode("utf-8"))
    excerpt_material_key = f"{task.bug_path}#prompt-excerpt:{excerpt_start_line}-{excerpt_end_line}"

    spec_packet = make_spec_packet(
        task_id=task.task_id,
        target_repo=task.repo,
        target_ref=task.pre_fix_sha,
        problem_statement=task.problem_statement,
        allowed_paths=[task.bug_path],
        build_commands=[],
        acceptance_commands=[list(task.test_command)],
        forbidden_sources=["network", "host-secrets", "host-home-mount", "known-fix-disclosure"],
        approved_by="local-benchmark-operator",
    )
    approved = ApprovedSpec.approve(spec_packet)
    approved.verify()

    executor = ContainerExecutor(image=BENCHMARK_IMAGE_DIGEST)
    probe_worktree, _probe_manifest = build_worktree(source_root, include_paths)
    isolation_result = executor.verify_isolation(probe_worktree)
    assurance_level = derive_assurance_level(executor, isolation_result)
    isolation_evidence = _result_to_dict(isolation_result)

    base_prompt = _PROMPT_TEMPLATE.format(
        problem=task.problem_statement,
        allowed_paths=[task.bug_path],
        path=task.bug_path,
        source=excerpt_source,
        start_line=excerpt_start_line,
        end_line=excerpt_end_line,
    )

    _no_audit_yet = {
        "checks": {},
        "result": "UNAVAILABLE",
        "reason": "no validated candidate exists; terminal audit has not run",
    }
    common_fields = {
        "run_id": run_id,
        "spec": approved.to_dict()["packet"],
        "spec_hash": approved.approved_hash,
        "model_identity": model.identity(),
        "prompt": base_prompt,
        "raw_completion": "",
        "executor_identity": executor.identity(),
        "isolation_evidence": isolation_evidence,
        "audit": _no_audit_yet,
        "assurance_level": assurance_level,
    }

    if assurance_level != "EACH-P2":
        outcome = "ISOLATION_UNVERIFIED"
        receipt = Receipt(
            patch_text="",
            touched_paths=[],
            materials={excerpt_material_key: excerpt_sha256},
            baseline_result={},
            repaired_result={},
            outcome=outcome,
            **common_fields,
        )
        json_path, md_path = receipt.write(runs_dir() / run_id)
        return {
            "task_id": task.task_id,
            "outcome": outcome,
            "receipt_json": str(json_path),
            "receipt_md": str(md_path),
            "attempts": 0,
        }

    attempts: list[dict[str, Any]] = []
    prompt = base_prompt
    # Every attempt dict below always carries the SAME complete set of
    # receipt-relevant keys (patch_text/touched_paths/materials/
    # baseline_result/repaired_result/audit), regardless of which branch
    # produced it -- not just "outcome" and "prompt". The receipt fields
    # are then read back out of exactly ONE selected attempt (the last one
    # appended) after the loop, never from separately loop-threaded
    # variables that an earlier successful-but-not-yet-verified attempt
    # could leave stale if a LATER attempt rejects early (e.g. attempt 2's
    # patch applies and tests run but REPAIR_NOT_VERIFIED, then attempt 3's
    # patch is rejected before parsing -- the old code would report
    # attempt 3's PATCH_REJECTED outcome/prompt alongside attempt 2's
    # stale patch_text/materials, a mixed receipt that never actually
    # happened as a whole). Matches the established selected-attempt
    # pattern in each.clean_room.run_clean_room_build.
    expected_tests = task.expected_tests

    for attempt_num in range(1, max_attempts + 1):
        # Preflight the context budget before spending a real container
        # baseline run on a prompt that cannot possibly reach generation:
        # not every RepairModel backend exposes this (it's an MLX-specific
        # extra, not part of the abstract RepairModel interface), so this
        # is a best-effort early exit, not a correctness requirement --
        # complete() below still enforces the budget authoritatively for
        # any backend that supports it.
        check_budget = getattr(model, "check_context_budget", None)
        if callable(check_budget):
            try:
                check_budget(prompt)
            except ContextBudgetExceeded as exc:
                attempts.append(
                    {
                        "attempt": attempt_num,
                        "prompt": prompt,
                        "raw_completion": "",
                        "materials": {},
                        "baseline_result": {},
                        "patch_text": "",
                        "touched_paths": [],
                        "repaired_result": {},
                        "audit": _no_audit_yet,
                        "outcome": f"BUILDER_CONTEXT_BUDGET_EXCEEDED: {exc}",
                        "generation_attempted": False,
                    }
                )
                break
        worktree, manifest = build_worktree(source_root, include_paths)
        try:
            baseline = executor.run(_wrapped_test_command(task), worktree)
            baseline_verdict = _interpret_pytest_run(baseline, expected_tests=expected_tests)
        except BenchmarkExecutionError as exc:
            attempts.append(
                {
                    "attempt": attempt_num,
                    "prompt": prompt,
                    "raw_completion": "",
                    "materials": {**manifest, excerpt_material_key: excerpt_sha256},
                    "baseline_result": {},
                    "patch_text": "",
                    "touched_paths": [],
                    "repaired_result": {},
                    "audit": _no_audit_yet,
                    "outcome": f"BASELINE_INCONCLUSIVE: {exc}",
                    "generation_attempted": False,
                }
            )
            break
        attempt_materials = {**manifest, excerpt_material_key: excerpt_sha256}
        attempt_baseline = _result_to_dict(baseline)
        try:
            raw_completion = model.complete(prompt)
        except ContextBudgetExceeded as exc:
            # Authoritative fallback for any backend complete() itself
            # enforces the budget for (the preflight above is only a
            # best-effort early exit for backends that expose it). A
            # policy/input-construction error, not a repair-attempt
            # failure: the excerpt (already the smallest diff-blind
            # selection we can make) still does not fit this checkpoint's
            # declared context budget. Retrying would only make the prompt
            # larger (the retry suffix appends to base_prompt), so this is
            # terminal for the task rather than consuming another attempt.
            attempts.append(
                {
                    "attempt": attempt_num,
                    "prompt": prompt,
                    "raw_completion": "",
                    "materials": attempt_materials,
                    "baseline_result": attempt_baseline,
                    "patch_text": "",
                    "touched_paths": [],
                    "repaired_result": {},
                    "audit": _no_audit_yet,
                    "outcome": f"BUILDER_CONTEXT_BUDGET_EXCEEDED: {exc}",
                    "generation_attempted": False,
                }
            )
            break
        rendered_prompt = getattr(model, "last_prompt", None)
        attempt_record: dict[str, Any] = {
            "attempt": attempt_num,
            "generation_attempted": True,
            "prompt": rendered_prompt if rendered_prompt is not None else prompt,
            "raw_completion": raw_completion,
            "materials": attempt_materials,
            "baseline_result": attempt_baseline,
            "patch_text": "",
            "touched_paths": [],
            "repaired_result": {},
            "audit": _no_audit_yet,
        }

        try:
            patch_text = extract_patch_text(raw_completion)
            patch = parse_patch(patch_text)
            touched = apply_patch(patch, worktree, {task.bug_path})
        except PatchRejected as exc:
            attempt_record["outcome"] = f"PATCH_REJECTED: {exc}"
            attempts.append(attempt_record)
            prompt = base_prompt + _RETRY_SUFFIX.format(reason=str(exc))
            continue

        # From here on this attempt's own patch_text/touched_paths are
        # recorded on THIS attempt_record -- never left to be reported
        # alongside a different, later attempt's outcome/prompt.
        attempt_record["patch_text"] = patch_text
        attempt_record["touched_paths"] = touched

        try:
            repaired = executor.run(_wrapped_test_command(task), worktree)
            repaired_verdict = _interpret_pytest_run(repaired, expected_tests=expected_tests)
        except BenchmarkExecutionError as exc:
            attempt_record["outcome"] = f"REPAIRED_RUN_INCONCLUSIVE: {exc}"
            attempts.append(attempt_record)
            prompt = base_prompt + _RETRY_SUFFIX.format(reason="the repaired test run could not be classified; try again")
            continue

        outcome = (
            "REPAIR_VERIFIED" if (baseline_verdict == "failed" and repaired_verdict == "passed") else "REPAIR_NOT_VERIFIED"
        )
        attempt_record["repaired_result"] = _result_to_dict(repaired)
        if outcome == "REPAIR_VERIFIED":
            # Audit the source only after generation/validation ends on a
            # genuinely validated candidate -- matches each.bakeoff's
            # terminal-boundary discipline (mandate section 126: the
            # Auditor is a terminal gate, never pre-generation feedback
            # that could steer or restart a later Builder attempt).
            repaired_source = "\n".join(
                (worktree / path).read_text(encoding="utf-8", errors="replace") for path in touched
            )
            attempt_record["audit"] = run_audit(repaired_source, corpus=audit_corpus)
            if reject_on_audit_flag(attempt_record["audit"]):
                outcome = "REPAIR_REJECTED_AUDIT"

        attempt_record["outcome"] = outcome
        attempts.append(attempt_record)

        if outcome in {"REPAIR_VERIFIED", "REPAIR_REJECTED_AUDIT"}:
            break
        prompt = base_prompt + _RETRY_SUFFIX.format(reason="patch applied but did not make the failing test pass")

    # Exactly one selected attempt -- the last one appended, whatever its
    # outcome -- supplies every receipt field below. max_attempts >= 1 is
    # enforced above, and every loop path above appends before breaking or
    # looping, so attempts is never empty here.
    selected = attempts[-1]
    final_outcome = selected["outcome"]

    common_fields["raw_completion"] = selected["raw_completion"]
    common_fields["prompt"] = selected["prompt"]
    common_fields["audit"] = selected["audit"]
    receipt = Receipt(
        patch_text=selected["patch_text"],
        touched_paths=selected["touched_paths"],
        materials=selected["materials"],
        baseline_result=selected["baseline_result"],
        repaired_result=selected["repaired_result"],
        outcome=final_outcome,
        attempts=attempts,
        **common_fields,
    )
    json_path, md_path = receipt.write(runs_dir() / run_id)
    try:
        known_fix_sha256: str | None = sha256_bytes(materialize_known_fix(task).encode("utf-8"))
    except BenchmarkExecutionError:
        # Purely a reporting convenience for the human benchmark report,
        # computed only after generation/audit have already completed and
        # the receipt has already been written -- never let its failure
        # discard a genuine completed repair result.
        known_fix_sha256 = None
    return {
        "task_id": task.task_id,
        # (F3) ``final_outcome`` may embed candidate-controlled or raw
        # pytest stdout/stderr detail after its leading label (e.g.
        # ``BASELINE_INCONCLUSIVE: <raw combined output>``) -- that full
        # detail is fine inside the already-written PRIVATE receipt above,
        # but this returned dict is consumed by each.benchmark_report's
        # public/sanitized suite report and Markdown export, so only the
        # bounded, reviewed outcome class ever crosses that boundary.
        "outcome": sanitize_outcome_class(final_outcome),
        "receipt_json": str(json_path),
        "receipt_md": str(md_path),
        "attempts": len(attempts),
        "known_fix_sha256": known_fix_sha256,
    }
