from __future__ import annotations

import asyncio
import functools
import hashlib
import os
from asyncio.subprocess import PIPE, Process
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator


@dataclass(frozen=True)
class _PathModified:
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
        return self._current_mtime() != self._mtime or self._current_hash() != self._hash


class ModifiedPaths:
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


class AsyncNullContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc: Any):
        return


@contextmanager
def environ(**env: str):
    """Temporarily set environment variables inside the context manager and
    fully restore previous environment afterwards
    """
    original_env = {key: os.getenv(key) for key in env}
    os.environ.update(env)
    try:
        yield
    finally:
        for key, value in original_env.items():
            if value is None:
                del os.environ[key]
            else:
                os.environ[key] = value


def pyright_env(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorate a function to set the pyright environment."""

    @functools.wraps(func)
    async def wrap_pyright_env(*args: Any, **kwargs: Any):
        default_env_dir = (
            Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "pyright"
        )
        env_dir = Path(os.getenv("PYRIGHT_PYTHON_ENV_DIR", default_env_dir)).resolve()
        with environ(PYRIGHT_PYTHON_ENV_DIR=env_dir.as_posix(), PYRIGHT_PYTHON_GLOBAL_NODE="off"):
            return await func(*args, **kwargs)

    return wrap_pyright_env


async def run_proc(program: str, *args: str) -> Process:
    proc = await asyncio.create_subprocess_exec(program, *args, stdout=PIPE, stderr=PIPE)
    await proc.wait()
    return proc
