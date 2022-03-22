"""Runners for click applications."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable

from behave import fixture, use_fixture
from behave.model import Examples, Feature, Row, Scenario, ScenarioOutline, Table

from features.steps.lint_env import LintContext, LintEnvironment


@fixture
def lint_environment(context: LintContext) -> Iterable[LintEnvironment]:
    with TemporaryDirectory() as tmp_dir:
        lint = LintEnvironment(_path=Path(tmp_dir), verbose=False, project_files={})
        context.lint = lint
        yield lint


def add_dynamic_linter(feature: Feature):
    headings = ["linter", "changes", "trigger_exitcode"]
    mutable_linters = ["black", "isort", "pyupgrade"]
    linters = mutable_linters + ["flake8", "prospector", "pyright"]

    def _mk_row(linter: str) -> Row:
        return Row(
            headings=headings,
            cells=[
                linter,
                "changed" if linter in mutable_linters else "not changed",
                str(int(linter not in mutable_linters)),
            ],
        )

    if feature.scenarios is None:
        return
    for scenario in feature.scenarios:
        if scenario.tags is None:
            continue
        if "fixture.dynamic_linter" in scenario.tags and isinstance(scenario, ScenarioOutline):
            rows = [_mk_row(linter) for linter in linters]
            table = Table(
                headings=headings,
                rows=rows,
            )
            example = Examples(
                filename=scenario.filename,
                line=scenario.line,
                keyword=scenario.keyword,
                name="Linters",
                table=table,
            )
            if scenario.examples:
                scenario.examples.append(example)
            else:
                scenario.examples = [example]


def before_scenario(context: LintContext, _scenario: Scenario):
    use_fixture(lint_environment, context)


def before_feature(_context: LintContext, feature: Feature):
    add_dynamic_linter(feature)
