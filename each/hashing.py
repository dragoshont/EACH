"""Deterministic hashing helpers used for spec, manifest, and artifact integrity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_text_file_lf(path: Path) -> str:
    """Hash UTF-8 text after normalizing Git's CRLF/LF checkout difference."""
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def canonical_json(obj: Any) -> str:
    """Stable JSON serialization used for hashing (sorted keys, no extra whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(obj: Any) -> str:
    return sha256_text(canonical_json(obj))
