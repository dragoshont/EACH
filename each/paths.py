"""Private, ignored-by-git storage locations for EACH run evidence.

Nothing under :data:`EACH_HOME` is committed to the public repository. Model
weights, signing keys, GitHub tokens, and shadow patches must never leave
this tree without an explicit, deliberate publication step (see
``each/publish``, added in a later milestone).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_TASK_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def validate_task_id(task_id: str) -> str:
    """Reject a task id that could escape its intended cache/spec directory.

    Task ids ultimately become a filename component
    (``<task_id>.json``/``<task_id>/draft.json``). They may come from a
    user-supplied ``--task-id`` flag, not just the regex-derived GitHub
    owner/repo/number default, so they must be validated independently of
    that default's own safety.
    """
    if not task_id or "/" in task_id or ".." in task_id or not _TASK_ID_RE.match(task_id):
        raise ValueError(f"invalid task id: {task_id!r} (must match {_TASK_ID_RE.pattern} with no '..' component)")
    return task_id


def each_home() -> Path:
    """Return the root of the private EACH store, creating it if absent."""
    override = os.environ.get("EACH_HOME")
    home = Path(override).expanduser() if override else Path.home() / ".each"
    home.mkdir(parents=True, exist_ok=True)
    return home


def runs_dir() -> Path:
    path = each_home() / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    path = each_home() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def keys_dir() -> Path:
    path = each_home() / "keys"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = each_home() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def worktrees_dir() -> Path:
    """Private scratch space for sandboxed worktrees.

    Deliberately kept under ``each_home()`` (i.e. under ``$HOME``) rather
    than the OS temp directory: Colima's default guest only bind-mounts the
    host's ``$HOME``, so a container executor run through ``docker
    --context colima-each`` cannot see paths under ``/tmp`` or
    ``/var/folders``.
    """
    path = each_home() / "worktrees"
    path.mkdir(parents=True, exist_ok=True)
    return path


def repo_root() -> Path:
    """Return the EACH repository root (this file's grandparent directory)."""
    return Path(__file__).resolve().parent.parent


def assert_no_symlink_escape(path: Path, *, label: str = "private path") -> None:
    """Refuse ``path`` if it, or any existing ancestor directory between it
    and the filesystem root, is a symlink (F3).

    A plain ``path.mkdir(parents=True, exist_ok=True)`` silently follows a
    pre-planted symlink at ``path`` itself (treating the symlink's real
    target as if it were the intended private directory) and likewise
    follows a symlinked ANCESTOR even when the leaf component's own name
    looks fresh and legitimate -- e.g. a ``runs/<run-id>`` directory whose
    grandparent ``runs`` was itself replaced with a symlink after
    :func:`runs_dir` first created it. Resolving ``path`` and only then
    checking the resolved result against an expected root (the bug this
    function exists to close) is not sufficient: that check would use the
    already-escaped location as its own anchor of trust. This function
    must run BEFORE any ``mkdir``/copy happens at or under ``path``.
    """
    if path.is_symlink():
        raise ValueError(f"refusing to use {label} because it is a symlink: {path}")
    ancestor = path.parent
    while ancestor != ancestor.parent:
        if ancestor.is_symlink():
            raise ValueError(
                f"refusing to use {label} because an existing ancestor directory is a symlink: {ancestor}"
            )
        ancestor = ancestor.parent


def validate_private_root() -> Path:
    """Fail closed, BEFORE any fetch/materialize/write, if the private EACH
    store (:func:`each_home`) would resolve inside -- or around -- this
    repository's own working tree (e.g. an ``EACH_HOME`` override pointed
    at a path under the checkout).

    ``Receipt.write()`` independently refuses to write a receipt inside the
    repo tree, but that check only runs at the very end of a run, after
    real network fetches and host-side materialization of shadow/strict-run
    source have already happened. Strict-run pipelines call this first so a
    misconfigured private root is refused before any such side effect, not
    only at receipt-finalization time.
    """
    home_resolved = each_home().resolve()
    repo_resolved = repo_root().resolve()
    if home_resolved == repo_resolved or repo_resolved in home_resolved.parents:
        raise ValueError(
            f"refusing to use EACH_HOME={home_resolved} because it is inside the repository "
            f"working tree {repo_resolved}; set EACH_HOME to a private location outside any checkout"
        )
    return home_resolved
