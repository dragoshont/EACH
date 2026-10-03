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
from typing import Self

_TASK_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class FileLock:
    """A small, cross-platform exclusive file lock using only the standard
    library (``fcntl`` on POSIX, ``msvcrt`` on Windows) -- mirrors the
    equivalent helper already used by ``harness/architrave_runtime.py``, so
    first-use races on private, process-shared files (such as the signing
    keypair) are serialized instead of silently overwriting each other.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: object | None = None

    def __enter__(self) -> Self:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self.handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.handle is None:
            return
        if os.name == "nt":
            import msvcrt

            self.handle.seek(0)
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()


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
    return validate_private_root()


def runs_dir() -> Path:
    path = each_home() / "runs"
    assert_no_symlink_escape(path, label="runs directory")
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    path = each_home() / "models"
    assert_no_symlink_escape(path, label="models directory")
    path.mkdir(parents=True, exist_ok=True)
    return path


def keys_dir() -> Path:
    path = each_home() / "keys"
    assert_no_symlink_escape(path, label="keys directory")
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = each_home() / "cache"
    assert_no_symlink_escape(path, label="cache directory")
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
    assert_no_symlink_escape(path, label="worktrees directory")
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
    override = os.environ.get("EACH_HOME")
    home = Path(override).expanduser() if override else Path.home() / ".each"
    assert_no_symlink_escape(home, label="private EACH root")
    home_resolved = home.resolve()
    repo_resolved = repo_root().resolve()
    if home_resolved == repo_resolved or repo_resolved in home_resolved.parents:
        raise ValueError(
            f"refusing to use EACH_HOME={home_resolved} because it is inside the repository "
            f"working tree {repo_resolved}; set EACH_HOME to a private location outside any checkout"
        )
    home.mkdir(parents=True, exist_ok=True)
    return home_resolved
