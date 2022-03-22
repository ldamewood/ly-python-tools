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
import sys
from pathlib import Path
from typing import Iterable, Iterator, Sequence, TypeVar

import click

from .config import LintConfiguration, NoProjectFile
from .linter import LintBootstrapResult, Linter, LintExecResult

logger = logging.getLogger(__name__)

__all__ = ["main"]


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
        _bootstrap(config)

    _run_linters(config, files)


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


def _bootstrap(config: LintConfiguration):
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


def _resolve_files(config: LintConfiguration, files: Sequence[Path]) -> Sequence[Path]:
    # Recursively search directories provided on the command line.
    found_files = [
        file_
        for part in files
        for file_ in (part.rglob("*") if part.is_dir() else [part])
        if config.include.search(file_.as_posix()) and file_.is_file()
    ]
    if not found_files:
        click.echo("No files to lint.")
        sys.exit(0)
    else:
        click.echo("Linting the following files:")
        for file_ in found_files:
            click.echo(f"- {file_}")
    return found_files


def _run_linters(config: LintConfiguration, files: Sequence[Path]):
    found_files = _resolve_files(config, files)
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


class MultipleExceptions(Exception):
    """Multiple exceptions."""

    def __init__(self, exceptions: Sequence[Exception]):
        self.exceptions = exceptions


def iter_returns(items: Iterable[ReturnType | Exception | None]) -> Iterator[ReturnType]:
    """Handle asyncio.gather(return_exceptions=True) results."""
    exceptions: list[Exception] = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, Exception):
            exceptions.append(item)
            continue
        yield item
    if exceptions:
        raise MultipleExceptions(exceptions)
