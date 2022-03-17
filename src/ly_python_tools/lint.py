"""
Lint files with a variety of linters.

* black
* flake8
* isort
* prospector
* pyright
* pyupgrade
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class Linter:
    executable: str
    options: Sequence[str] = field(default_factory=list)
    pass_filenames: bool = False
    mutable: bool = False
    _executable: Path = field(init=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "_executable", Path(self.executable))

    def run(self, *files: Path):
        cmd = [self._executable.as_posix()] + list(self.options)
        cmd += [file.as_posix() for file in files]
        print(cmd)
        subprocess.run(cmd, check=True)

    def setup(self):
        subprocess.run([self._executable.as_posix(), "--version"], check=True)


@dataclass(frozen=True)
class PyRightLinter(Linter):
    def setup(self):
        for _ in range(3):
            try:
                super().setup()
                break
            except subprocess.CalledProcessError:
                continue
        else:
            print(
                "Could not install pyright successfully after 3 attempts. Please check the logs."
            )
            sys.exit(1)


LINTERS = {
    "pyupgrade": Linter(executable="pyupgrade", options=["--py37-plus"], pass_filenames=True),
    "black": Linter(executable="black", pass_filenames=True, mutable=True),
    "isort": Linter(executable="isort", pass_filenames=True, mutable=True),
    "flake8": Linter(executable="flake8"),
    "pyright": PyRightLinter(executable="pyright"),
    "prospector": Linter(executable="prospector"),
}


@dataclass(frozen=True)
class LintConfiguration:
    name: str
    linters: Sequence[Linter]
    files: Sequence[Path]

    def setup(self):
        for linter in self.linters:
            print(f"Setting up {linter.executable}...")
            try:
                linter.setup()
            except subprocess.CalledProcessError:
                print("Unknown version")

    def run(self):
        for linter in self.linters:
            print(f"Running {linter.executable} on {self.name}", end="")
            print(" (This may change files)" if linter.mutable else "")
            if linter.pass_filenames:
                linter.run(*self.files)
            else:
                linter.run()


def setup() -> LintConfiguration:
    this_dir = Path(__file__).parent
    config = LintConfiguration(
        "ly_python_tools", list(LINTERS.values()), list(this_dir.glob("*.py"))
    )
    config.setup()
    return config


def main():
    setup().run()
