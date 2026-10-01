"""Private, ignored-by-git storage locations for EACH run evidence.

Nothing under :data:`EACH_HOME` is committed to the public repository. Model
weights, signing keys, GitHub tokens, and shadow patches must never leave
this tree without an explicit, deliberate publication step (see
``each/publish``, added in a later milestone).
"""

from __future__ import annotations

import os
from pathlib import Path


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
