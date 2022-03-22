from __future__ import annotations

import asyncio
import logging
import shutil
from asyncio.subprocess import PIPE, Process
from dataclasses import dataclass, field, replace
from pathlib import Path
from textwrap import indent
from typing import Any, ClassVar, Mapping, Sequence

from .environ import pyright_env
from .modified_paths import ModifiedPaths

logger = logging.getLogger(__name__)

__all__ = ["DEFAULT_LINTERS", "Linter", "LintBootstrapResult", "LintExecResult"]


@dataclass
class Linter:
    """A linter."""

    executable: str
    options: Sequence[str] = field(default_factory=list)
    mutable: bool = False
    run: bool = True
    quiet: bool = False
    pass_filenames: bool = True
    additional_options: Sequence[str] = field(default_factory=list, repr=False)
    _executable: Path = field(init=False, repr=False)

    def __post_init__(self):
        self._executable = Path(self.executable)

    async def bootstrap(self) -> LintBootstrapResult:
        """Ensure the linter is available on the system."""
        which = shutil.which(self._executable.as_posix())
        if not which:
            return LintBootstrapResult(self.executable)
        proc = await run_proc(which, "--help")
        return LintBootstrapResult(
            linter=self.executable,
            which=Path(which),
            stdout=(await proc.stdout.read()).decode("utf8") if proc.stdout else None,
            stderr=(await proc.stderr.read()).decode("utf8") if proc.stderr else None,
            returncode=proc.returncode,
        )

    async def exec(self, lock: asyncio.Lock, files: Sequence[Path]) -> LintExecResult:
        """
        Run the linter and return the result.

        Returns None if the linter is not configured to run.
        """
        assert self.run, f"{self.executable} is not configured to run"
        cmd = [self._executable.as_posix()] + list(self.additional_options) + list(self.options)
        cmd += [file.as_posix() for file in files if self.pass_filenames]
        async with lock:
            # Looking for modified files means we need to lock the process.
            async with ModifiedPaths(files) as modified_files:
                proc = await run_proc(*cmd)
            stdout = (await proc.stdout.read()).decode("utf8") if proc.stdout else None
            stderr = (await proc.stderr.read()).decode("utf8") if proc.stderr else None
            modified = list(modified_files)
            assert (
                not modified
            ) or self.mutable, f"{self.executable} was not expected to change files."
        return LintExecResult(
            linter=self.executable,
            stdout=stdout,
            stderr=stderr,
            returncode=proc.returncode,
            modified_files=modified,
        )

    def update(self, config: Mapping[str, Any]) -> Linter:
        """Update the linter options."""
        new_linter = replace(self, **config)
        new_linter.__post_init__()
        return new_linter


@dataclass(frozen=True)
class ResultBase:
    """Result that can be pretty printed."""

    linter: str
    stdout: str | None = None
    stderr: str | None = None
    returncode: int | None = None

    def pretty_output(self) -> str:
        ret: list[str] = []
        symbols = ["¹", "²"]
        for symbol, out in zip(symbols, [self.stdout, self.stderr]):
            if out:
                ret += [indent(out, f"{self.linter}{symbol}: ", predicate=lambda _: True)]
        return "\n".join(ret)


@dataclass(frozen=True)
class LintBootstrapResult(ResultBase):
    """Result of bootstrapping a linter."""

    which: Path | None = None


@dataclass(frozen=True)
class LintExecResult(ResultBase):
    """Result of running a linter."""

    modified_files: Sequence[Path] = field(default_factory=list)


@dataclass
class PyRightLinter(Linter):
    """
    A linter for pyright.

    Running pyright will download additional node software. We want to retry a few times in case of
    flaky network availability.
    """

    _retries: ClassVar[int] = 3

    @pyright_env
    async def bootstrap(self) -> LintBootstrapResult:
        """Ensure the linter is available on the system."""
        bootstrap = await super().bootstrap()
        retry = self._retries
        while retry and bootstrap.returncode:
            logger.debug(bootstrap.stdout)
            logger.debug(bootstrap.stderr)
            logger.debug("Error: Trying again...")
            bootstrap = await super().bootstrap()
            retry -= 1
        return bootstrap

    @pyright_env
    async def exec(self, lock: asyncio.Lock, files: Sequence[Path]) -> LintExecResult | None:
        return await super().exec(lock=lock, files=files)


DEFAULT_LINTERS = {
    "pyupgrade": Linter(
        executable="pyupgrade",
        mutable=True,
        additional_options=["--py37-plus", "--exit-zero-even-if-changed"],
    ),
    "black": Linter(executable="black", mutable=True, additional_options=["-t", "py37"]),
    "isort": Linter(executable="isort", mutable=True, additional_options=["--py", "37"]),
    "flake8": Linter(executable="flake8"),
    "pyright": PyRightLinter(executable="pyright", pass_filenames=False),
    "prospector": Linter(executable="prospector"),
}


async def run_proc(program: str, *args: str) -> Process:
    """Run a process and wait for it to finish."""
    proc = await asyncio.create_subprocess_exec(program, *args, stdout=PIPE, stderr=PIPE)
    await proc.wait()
    return proc
