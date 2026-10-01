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
