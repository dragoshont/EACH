"""Regression test for a real cache-contamination defect found during an
independent M6 semantic review: ``materialize_task_sources`` cached the
extracted repo tree keyed only by ``task.task_id``, with ``_extract_repo_tree``
skipping re-extraction whenever the destination directory already had any
content. If that directory ever held content extracted under a *different*
sha (e.g. from an earlier ad-hoc/debugging invocation), every later run would
silently keep serving that stale, wrongly-labeled tree forever -- with no
way to detect it short of manually diffing cached files against the repo.

This was not a hypothetical: the on-disk cache for one real M6 task was
found to contain the *fixed* version of the bug file under the pre-fix
cache directory, meaning the model was shown nearly-fixed code instead of
the real historical bug for that task's benchmark runs.

The fix binds the cache directory to ``task.pre_fix_sha`` as well as
``task.task_id``, so a different sha can never silently reuse another sha's
cached content. This test proves that binding holds without touching the
network (a real ``_extract_repo_tree`` is stubbed out, since the cache-path
construction itself -- not the network fetch -- is what is being verified).
"""

from __future__ import annotations

from pathlib import Path

import each.benchmark as benchmark_module
from each.benchmark import BenchmarkTask, materialize_task_sources

_TASK_TEMPLATE = {
    "task_id": "cache-binding-smoke",
    "repo": "example/some-lib",
    "license": "MIT",
    "bug_path": "pkg/module.py",
    "test_paths": ("tests/test_module.py",),
    "test_command": ("python", "-m", "pytest", "tests/test_module.py", "-q"),
    "problem_statement": "irrelevant for this cache-path test",
}


def test_a_different_pre_fix_sha_is_never_served_from_another_shas_cache(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(benchmark_module, "cache_dir", lambda: tmp_path)

    extracted_for: list[str] = []

    def _fake_extract_repo_tree(repo: str, sha: str, dest: Path, *, timeout: int = 60) -> Path:
        del repo, timeout
        extracted_for.append(sha)
        dest.mkdir(parents=True, exist_ok=True)
        # Content deliberately identifies which sha it was extracted for, so
        # a wrongly-reused cache entry would be directly observable.
        (dest / "pkg").mkdir(parents=True, exist_ok=True)
        (dest / "pkg" / "module.py").write_text(f"# extracted for sha {sha}\n", encoding="utf-8")
        return dest

    def _fake_fetch_file(repo: str, sha: str, path: str, *, timeout: int = 20) -> str:
        del repo, timeout
        return f"# test file for sha {sha} path {path}\n"

    monkeypatch.setattr(benchmark_module, "_extract_repo_tree", _fake_extract_repo_tree)
    monkeypatch.setattr(benchmark_module, "fetch_file", _fake_fetch_file)

    task_a = BenchmarkTask(pre_fix_sha="a" * 40, fix_sha="a-fix" + "0" * 35, **_TASK_TEMPLATE)
    task_b = BenchmarkTask(pre_fix_sha="b" * 40, fix_sha="b-fix" + "0" * 35, **_TASK_TEMPLATE)

    root_a, _ = materialize_task_sources(task_a)
    root_b, _ = materialize_task_sources(task_b)

    assert root_a != root_b, "two different pre_fix_sha values must never resolve to the same cache directory"
    assert (root_a / "pkg" / "module.py").read_text() == f"# extracted for sha {task_a.pre_fix_sha}\n"
    assert (root_b / "pkg" / "module.py").read_text() == f"# extracted for sha {task_b.pre_fix_sha}\n"

    # task_a's own cache path must itself be keyed by its own sha string
    # (not merely "some directory under task_id"), so content extracted
    # under one sha can never later be silently reused by a run that
    # actually asks for a different sha.
    assert task_a.pre_fix_sha in str(root_a)
    assert task_b.pre_fix_sha in str(root_b)
