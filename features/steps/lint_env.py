"""Runners for click applications."""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from behave.runner import Context
from click.testing import CliRunner, Result

from ly_python_tools.lint import main


@contextmanager
def set_directory(path: Path):
    """Sets the cwd within the context."""
    origin = Path().absolute()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(origin)


@dataclass
class LintEnvironment:
    _path: Path
    verbose: bool = False
    project_files: dict[str, str] = field(default_factory=dict)
    _runner: CliRunner = field(init=False)
    broken_linters: list[str] = field(default_factory=list)
    missing_linters: list[str] = field(default_factory=list)

    @property
    def _project_dir(self) -> Path:
        return self._path / "project"

    def __post_init__(self):
        pyright_env_dir = (self._path / "pyright").resolve()
        self._runner = CliRunner(env={"PYRIGHT_PYTHON_ENV_DIR": pyright_env_dir.as_posix()})

    def _setup_environment(self):
        self._project_dir.mkdir(parents=True)
        for rel_path, contents in self.project_files.items():
            (self._project_dir / rel_path).parent.mkdir(parents=True, exist_ok=True)
            (self._project_dir / rel_path).write_text(contents)
        if self.broken_linters:
            bin_dir = self._path / "bin"
            bin_dir.mkdir()
            new_path = f'{bin_dir.resolve().as_posix()}:{os.getenv("PATH")}'
            self._runner.env = {"PATH": new_path, **self._runner.env}
            for linter in self.broken_linters:
                linter_exe = bin_dir / linter
                linter_exe.write_text("#!/usr/bin/env python\nimport sys\nsys.exit(1)")
                linter_exe.chmod(0o555)
        if self.missing_linters:
            search_paths = os.getenv("PATH", "").split(":")
            replace_paths = [
                search_path
                for search_path in search_paths
                for linter in self.missing_linters
                if not (Path(search_path) / linter).exists()
            ]
            self._runner.env = {"PATH": ":".join(replace_paths), **self._runner.env}

    def unchanged(self, rel_path: Path | str) -> bool:
        path = self._project_dir / rel_path
        return path.read_text() == self.project_files[str(rel_path)]

    def run(self, *args: str) -> Result:
        if not self._project_dir.exists():
            self._setup_environment()
        invoke_args = list(args)
        if self.verbose:
            invoke_args.append("--verbose")
        with set_directory(self._project_dir):
            return self._runner.invoke(main, invoke_args)  # type: ignore


class LintContext(Context):
    lint: LintEnvironment
    result: Result | None
