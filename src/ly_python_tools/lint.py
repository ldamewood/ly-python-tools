#!/usr/bin/env python
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

import asyncio
import logging
import re
import shutil
import sys
from asyncio.subprocess import PIPE, Process
from dataclasses import dataclass, field, replace
from pathlib import Path
from textwrap import indent
from typing import Any, ClassVar, Mapping, Pattern, Sequence

import click
import toml

from .environ import pyright_env

logger = logging.getLogger(__name__)


async def run_proc(program: str, *args: str, verbose: bool = False) -> Process:
    proc = await asyncio.create_subprocess_exec(program, *args, stdout=PIPE, stderr=PIPE)
    await proc.wait()
    if verbose and proc.returncode != 0:
        for out in (proc.stdout, proc.stderr):
            if out:
                logger.debug((await out.read()).decode("utf8"))
    return proc


@dataclass(frozen=True)
class Linter:
    """A linter that is run from the command line."""

    executable: str
    options: Sequence[str] = field(default_factory=list)
    mutable: bool = False
    run: bool = True
    quiet: bool = False
    pass_filenames: bool = True
    _executable: Path = field(init=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "_executable", Path(self.executable))

    async def bootstrap(self) -> str:
        """Ensure the linter is available on the system."""
        which = shutil.which(self._executable.as_posix())
        if not which:
            raise LinterBootstrapFailure(f"{self._executable.as_posix()} is missing")
        proc = await run_proc(which, "--help")
        if proc.returncode != 0:
            raise LinterBootstrapFailure(f"{self._executable.as_posix()} is broken")
        return which

    async def exec(self, *files: Path) -> Process | None:
        """
        Run the linter.

        If this linter fails, the program exits.
        """
        if not self.run:
            return
        cmd = [self._executable.as_posix()] + list(self.options)
        cmd += [file.as_posix() for file in files if self.pass_filenames]
        async with asyncio.Lock():
            # Multiple mutable linters can be running, so we ensure they are in lock-step
            proc = await run_proc(*cmd)
        if proc.returncode != 0:
            stdout = (await proc.stdout.read()).decode("utf8") if proc.stdout else None
            stderr = (await proc.stderr.read()).decode("utf8") if proc.stderr else None
            raise LinterExitNonZero(
                linter=self._executable.as_posix(),
                stdout=stdout,
                stderr=stderr,
            )
        return proc

    def update(self, config: Mapping[str, Any]) -> Linter:
        """Update the linter options."""
        new_linter = replace(self, **config)
        new_linter.__post_init__()
        return new_linter


@dataclass(frozen=True)
class PyRightLinter(Linter):
    """
    A linter for pyright.

    Running pyright will download additional node software. We want to retry a few times in case of
    flaky network availability.
    """

    _retries: ClassVar[int] = 3

    @pyright_env
    async def bootstrap(self) -> str:
        """Ensure the linter is available on the system."""
        ret = await super().bootstrap()
        for i in range(self._retries):
            proc = await run_proc(self._executable.as_posix(), "--help")
            if proc.returncode == 0:
                return ret
            if i < self._retries - 1:
                logger.debug(proc.stdout)
                logger.debug(proc.stderr)
                logger.debug("Error: Trying again...")
        raise LinterBootstrapFailure(
            f"Could not install pyright successfully after {self._retries} attempts."
        )

    @pyright_env
    async def exec(self, *files: Path):
        return await super().exec(*files)


DEFAULT_LINTERS = {
    "pyupgrade": Linter(executable="pyupgrade", mutable=True),
    "black": Linter(executable="black", mutable=True),
    "isort": Linter(executable="isort", mutable=True),
    "flake8": Linter(executable="flake8"),
    "pyright": PyRightLinter(executable="pyright", pass_filenames=False),
    "prospector": Linter(executable="prospector"),
}


@dataclass
class LintConfiguration:
    """Configuration for running all of the linters."""

    name: str
    linters: Sequence[Linter]
    include: Pattern[str]
    _config_file: ClassVar[Path] = Path("pyproject.toml")

    @classmethod
    def get_config(cls) -> LintConfiguration:
        pyproject = cls.get_configfile()
        lint_config: Mapping[str, Any] = toml.load(pyproject).get("tool", {}).get("lint", {})
        include = re.compile(lint_config.get("include", r"\.py$"))
        linters = [
            linter.update(lint_config.get(linter_name, {}))
            for linter_name, linter in DEFAULT_LINTERS.items()
        ]
        return LintConfiguration(linters=linters, name=pyproject.parent.name, include=include)

    @classmethod
    def get_configfile(cls) -> Path:
        cwd = Path.cwd().absolute()
        paths = [cwd] + list(cwd.parents)
        for path in paths:
            pyproject = path / cls._config_file
            if pyproject.exists() and pyproject.is_file():
                break
        else:
            raise NoProjectFile(cls._config_file, search_paths=paths)
        return pyproject


class NoProjectFile(Exception):
    """No project file could be found."""

    def __init__(self, proj_filename: Path, search_paths: Sequence[Path]):
        self.proj_filename = proj_filename.as_posix()
        self.search_paths = [path.as_posix() for path in search_paths]


class LinterBootstrapFailure(Exception):
    """Linter failed during bootstrap."""


class LinterExitNonZero(Exception):
    """Linter exited with non-zero status."""

    def __init__(self, linter: str, stdout: str | None, stderr: str | None):
        self.linter = linter
        self.stdout = stdout
        self.stderr = stderr

    def pretty(self) -> str:
        ret: list[str] = []
        symbols = ["¹", "²"]
        for symbol, out in zip(symbols, [self.stdout, self.stderr]):
            if out:
                ret += [indent(out, f"{self.linter}{symbol}: ", predicate=lambda _: True)]
        return "\n".join(ret)


class LinterMultipleExceptions(Exception):
    """Multiple exceptions."""


async def _bootstrap_linters(config: LintConfiguration):
    returns = await asyncio.gather(
        *[_bootstrap_linter(linter) for linter in config.linters], return_exceptions=True
    )
    exceptions = [ret for ret in returns if isinstance(ret, Exception)]
    if exceptions:
        click.echo(f"Multiple exceptions raised: {exceptions!r}")
        raise LinterMultipleExceptions(exceptions)


async def _bootstrap_linter(linter: Linter):
    click.echo(f"Bootstrapping {linter.executable} ... ")
    found = await linter.bootstrap()
    logger.debug(f"{linter.executable} is {found}")


async def _exec_linters(linters: Sequence[Linter], files: Sequence[Path]):
    returns = await asyncio.gather(
        *[_exec_linter(linter, files) for linter in linters], return_exceptions=True
    )
    exceptions = [ret for ret in returns if isinstance(ret, Exception)]
    for exception in exceptions:
        if isinstance(exception, LinterExitNonZero):
            click.echo(f"{exception.linter} found errors")
            click.echo(exception.pretty())
    if exceptions:
        click.echo(f"Multiple exceptions raised: {exceptions!r}")
        raise LinterMultipleExceptions(exceptions)


async def _exec_linter(linter: Linter, files: Sequence[Path]):
    if not linter.run:
        return
    click.echo(f"Running {linter.executable} ...")
    return await linter.exec(*files)


def _resolve_files(config: LintConfiguration, *files: Path) -> Sequence[Path]:
    # Recursively search directories provided on the command line.
    found_files = [
        file_
        for part in files
        for file_ in (part.rglob("*") if part.is_dir() else [part])
        if config.include.search(file_.as_posix()) and file_.is_file()
    ]

    if len(found_files) == 0:
        click.echo("No files to lint.")
        sys.exit(0)
    else:
        click.echo("Linting the following files:")
        for file_ in found_files:
            click.echo(f"- {file_}")

    return found_files


@click.command()
@click.option("--bootstrap", is_flag=True, default=False, help="Bootstrap all of the linters")
@click.option("--verbose", is_flag=True, default=False)
@click.argument("files", nargs=-1, type=click.Path(path_type=Path))
@click.version_option()
def main(verbose: bool, bootstrap: bool, files: Sequence[Path]):
    if verbose:
        logging.basicConfig()
        logger.setLevel(logging.DEBUG)

    try:
        config = LintConfiguration.get_config()
    except NoProjectFile as e:
        click.echo(
            f'"{e.proj_filename}" could not be located in the search paths: {e.search_paths!s}'
        )
        sys.exit(1)

    if bootstrap:
        asyncio.run(_bootstrap_linters(config))
        click.echo("Bootstrapping finished successfully.")

    found_files = _resolve_files(config, *files)
    asyncio.run(_exec_linters(config.linters, found_files))
    click.echo("Linting ran successfully")
