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

import logging
import re
import subprocess
import sys
from collections import UserList
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, ClassVar, Mapping, Pattern, Sequence

import click
import toml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Linter:
    """A linter that is run from the command line."""

    executable: str
    options: Sequence[str] = field(default_factory=list)
    mutable: bool = False
    run: bool = True
    quiet: bool = False
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
        cmd += [file.as_posix() for file in files]
        subprocess.run(cmd, check=True, capture_output=self.quiet)

    def bootstrap(self) -> str:
        """Ensure the linter is available on the system."""
        ret = subprocess.run(
            ["type", self._executable.as_posix()], check=True, capture_output=True, text=True
        )
        return ret.stdout.strip()

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
                print(f"Caught {e!r}: Trying again...")
                continue
        print("Could not install pyright successfully after 3 attempts.")
        sys.exit(1)


DEFAULT_LINTERS = {
    "pyupgrade": Linter(executable="pyupgrade"),
    "black": Linter(executable="black", mutable=True),
    "isort": Linter(executable="isort", mutable=True),
    "flake8": Linter(executable="flake8"),
    "pyright": PyRightLinter(executable="pyright"),
    "prospector": Linter(executable="prospector"),
}


@dataclass
class LintConfiguration(UserList[Linter]):
    """Configuration for running all of the linters."""

    name: str
    include: Pattern[str]
    _config_file: ClassVar[Path] = Path("pyproject.toml")

    def __init__(self, name: str, linters: Sequence[Linter], include: Pattern[str]):
        super().__init__(linters)
        self.name = name
        self.include = include

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


class LinterExitNonZero(Exception):
    """Linter exited with non-zero status."""


@click.command()
@click.argument("files", nargs=-1, type=click.Path(path_type=Path))
@click.version_option()
def main(files: Sequence[Path]):
    try:
        config = LintConfiguration.get_config()
    except NoProjectFile as e:
        click.echo(
            f'No "{e.proj_filename}" file could be located in the search paths: {e.search_paths!s}'
        )
        sys.exit(1)

    for linter in config:
        click.echo(f"Bootstrapping {linter.executable} ... ")
        try:
            ret = linter.bootstrap()
            click.echo(ret)
        except subprocess.CalledProcessError as e:
            click.echo("Bootstrap failed. Echoing stdout and stderr...")
            click.echo(e.stdout)
            click.echo(e.stderr)
            raise e

    # Recursively search directories provided on the command line.
    found_files = [
        file_
        for part in files
        for file_ in part.rglob("*")
        if config.include.search(file_.as_posix())
    ]

    if len(found_files) == 0:
        click.echo("No files to lint. Bootstrap-mode only.")
        sys.exit(0)

    for linter in config:
        click.echo(f"Running {linter.executable} ...")
        linter.exec(*found_files)

    click.echo("Linting ran successfully")
