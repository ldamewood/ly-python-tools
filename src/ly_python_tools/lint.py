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
from dataclasses import dataclass, field, replace
from pathlib import Path
from textwrap import indent
from typing import Any, ClassVar, Iterable, Iterator, Mapping, Pattern, Sequence, TypeVar

import click
import toml

from .environ import ModifiedPaths, pyright_env, run_proc

logger = logging.getLogger(__name__)


@dataclass
class Linter:
    """A linter that is run from the command line."""

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

    async def exec(self, lock: asyncio.Lock, files: Sequence[Path]) -> LintExecResult | None:
        """
        Run the linter.

        If this linter fails, the program exits.
        """
        if not self.run:
            return
        cmd = [self._executable.as_posix()] + list(self.additional_options) + list(self.options)
        cmd += [file.as_posix() for file in files if self.pass_filenames]
        async with lock:
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
            modified_files=list(modified_files),
        )

    def update(self, config: Mapping[str, Any]) -> Linter:
        """Update the linter options."""
        new_linter = replace(self, **config)
        new_linter.__post_init__()
        return new_linter


@dataclass(frozen=True)
class PrettyResult:
    linter: str
    stdout: str | None = None
    stderr: str | None = None

    def pretty_output(self) -> str:
        ret: list[str] = []
        symbols = ["¹", "²"]
        for symbol, out in zip(symbols, [self.stdout, self.stderr]):
            if out:
                ret += [indent(out, f"{self.linter}{symbol}: ", predicate=lambda _: True)]
        return "\n".join(ret)


@dataclass(frozen=True)
class LintBootstrapResult(PrettyResult):
    returncode: int | None = None
    which: Path | None = None


@dataclass(frozen=True)
class LintExecResult(PrettyResult):
    returncode: int | None = None
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


class LinterMultipleExceptions(Exception):
    """Multiple exceptions."""


async def _bootstrap_linters(
    config: LintConfiguration,
) -> Sequence[LintBootstrapResult | Exception | None]:
    async def _bootstrap_linter(linter: Linter) -> LintBootstrapResult | None:
        if not linter.run:
            return
        click.echo(f"Bootstrapping {linter.executable} ... ")
        return await linter.bootstrap()

    return await asyncio.gather(
        *[_bootstrap_linter(linter) for linter in config.linters], return_exceptions=True
    )


async def _exec_linter(
    linter: Linter, files: Sequence[Path], lock: asyncio.Lock
) -> LintExecResult | None:
    if not linter.run:
        return
    click.echo(f"Running {linter.executable} ...")
    return await linter.exec(lock=lock, files=files)


async def _exec_linters(
    linters: Sequence[Linter], files: Sequence[Path]
) -> Sequence[LintExecResult | Exception | None]:

    lock = asyncio.Lock()
    return await asyncio.gather(
        *[_exec_linter(linter, files, lock=lock) for linter in linters], return_exceptions=True
    )


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
        _exit = 0
        for ret in iter_returns(asyncio.run(_bootstrap_linters(config), debug=True)):
            if ret.returncode:
                click.echo(f"{ret.linter} is broken and exited {ret.returncode}")
                click.echo(ret.pretty_output())
                _exit = 1
            if ret.which is None:
                click.echo(f"{ret.linter} is missing")
                click.echo(ret.pretty_output())
                _exit = 1
        if _exit:
            click.echo("Linting bootstrap failed.")
            sys.exit(1)
        click.echo("Bootstrapping finished successfully.")

    found_files = _resolve_files(config, *files)

    _exit = 0
    for ret in iter_returns(asyncio.run(_exec_linters(config.linters, found_files), debug=True)):
        if ret.modified_files:
            click.echo(f"{ret.linter} found errors and modified files:")
            for modified_path in ret.modified_files:
                click.echo(f"- {ret.linter} modified {modified_path}")
            _exit = 1
        if ret.returncode:
            click.echo(f"{ret.linter} found errors and exited {ret.returncode}")
            click.echo(ret.pretty_output())
            _exit = 1
    if _exit:
        click.echo("Linting failed.")
        sys.exit(1)
    click.echo("Linting ran successfully")


ReturnType = TypeVar("ReturnType")


def iter_returns(items: Iterable[ReturnType | Exception | None]) -> Iterator[ReturnType]:
    exceptions: list[Exception] = []
    for item in iter(items):
        if item is None:
            continue
        if isinstance(item, Exception):
            logger.error(item)
            exceptions.append(item)
            continue
        yield item
    if exceptions:
        raise LinterMultipleExceptions(exceptions)
