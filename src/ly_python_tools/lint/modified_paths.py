from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator


class ModifiedPaths:
    """Async context manager to determine if files have been changed."""

    def __init__(self, paths: Iterable[Path]):
        self._paths = iter(paths)
        self._watch_paths = []
        self.modified_paths = []

    def __bool__(self) -> bool:
        return bool(self.modified_paths)

    def __iter__(self) -> Iterator[Path]:
        yield from self.modified_paths

    async def __aenter__(self):
        self._watch_paths = [_PathModified(path) for path in self._paths]
        self.modified_paths = []
        return self

    async def __aexit__(self, *_exc: Any) -> bool | None:
        self.modified_paths = [path.path for path in self._watch_paths if path.modified()]


@dataclass(frozen=True)
class _PathModified:
    """
    Keep track of when a file is modified.

    Uses the mtime and hash to determine if a file is changed.
    """

    path: Path
    _mtime: float = field(init=False, repr=False)
    _hash: str = field(init=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "_mtime", self._current_mtime())
        object.__setattr__(self, "_hash", self._current_hash())

    def _current_mtime(self) -> float:
        return self.path.stat().st_mtime

    def _current_hash(self) -> str:
        m = hashlib.md5()
        with self.path.open("rb") as f:
            chunk = f.read(8192)
            while chunk:
                m.update(chunk)
                chunk = f.read(8192)
        return m.hexdigest()

    def modified(self) -> bool:
        """Return if the file has been modified since initialization."""
        if self._current_mtime() != self._mtime:
            # Only check the hash if the modification time has changed.
            return self._current_hash() != self._hash
        return False
