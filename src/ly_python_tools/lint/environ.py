from __future__ import annotations

import functools
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable


@contextmanager
def environ(**env: str):
    """Temporarily set environment variables inside the context manager."""
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
