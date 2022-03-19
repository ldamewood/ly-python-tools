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

import functools
import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, ClassVar, Mapping, Pattern, Sequence

import click
import toml

from .environ import environ

logger = logging.getLogger(__name__)


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

    def exec(self, *files: Path):
        """
        Run the linter.

        If this linter fails, the program exits.
        """
        if not self.run:
            return
        cmd = [self._executable.as_posix()] + list(self.options)
        cmd += [file.as_posix() for file in files if self.pass_filenames]
        subprocess.run(cmd, check=True, capture_output=self.quiet)

    def bootstrap(self) -> str:
        """Ensure the linter is available on the system."""
        which = shutil.which(self._executable.as_posix())
        if not which:
            raise LinterBootstrapFailure(f"Could not find {self._executable.as_posix()}")
        return which

    def update(self, config: Mapping[str, Any]) -> Linter:
        """Update the linter options."""
        new_linter = replace(self, **config)
        new_linter.__post_init__()
        return new_linter


def pyright_env(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorate a function to set the pyright environment."""

    @functools.wraps(func)
    def wrap_pyright_env(*args: Any, **kwargs: Any):
        default_env_dir = (
            Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "pyright"
        )
        env_dir = Path(os.getenv("PYRIGHT_PYTHON_ENV_DIR", default_env_dir)).resolve()
        with environ(PYRIGHT_PYTHON_ENV_DIR=env_dir.as_posix()):
            logger.debug(f'PYRIGHT_PYTHON_ENV_DIR is {os.environ["PYRIGHT_PYTHON_ENV_DIR"]}')
            return func(*args, **kwargs)

    return wrap_pyright_env


@dataclass(frozen=True)
class PyRightLinter(Linter):
    """
    A linter for pyright.

    Running pyright will download additional node software. We want to retry a few times in case of
    flaky network availability.
    """

    _retries: ClassVar[int] = 3

    @pyright_env
    def bootstrap(self) -> str:
        """Ensure the linter is available on the system."""
        ret = super().bootstrap()
        for i in range(self._retries):
            try:
                subprocess.run(
                    [self._executable.as_posix(), "--version"], check=True, capture_output=True
                )
                return ret
            except subprocess.CalledProcessError as e:
                if i == self._retries - 1:
                    raise
                logger.debug(f"Caught {e!r}: Trying again...")
                continue
        raise LinterBootstrapFailure(
            f"Could not install pyright successfully after {self._retries} attempts."
        )

    @pyright_env
    def exec(self, *files: Path):
        super().exec(*files)


DEFAULT_LINTERS = {
    "pyupgrade": Linter(executable="pyupgrade"),
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
            f'No "{e.proj_filename}" file could be located in the search paths: {e.search_paths!s}'
        )
        sys.exit(1)

    if bootstrap:
        for linter in config.linters:
            click.echo(f"Bootstrapping {linter.executable} ... ")
            found = linter.bootstrap()
            logger.debug(f"{linter.executable} is {found}")
        click.echo("Bootstrapping finished successfully.")

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

    runnable_linters = [linter for linter in config.linters if linter.run]

    for linter in runnable_linters:
        click.echo(f"Running {linter.executable} ...")
        linter.exec(*found_files)

    if any(linter.mutable for linter in runnable_linters):
        click.echo("Files may have been modified")

    click.echo("Linting ran successfully")
