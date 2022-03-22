from pathlib import Path
from textwrap import dedent

from behave import given, then, when

from features.steps.lint_env import LintContext

here = Path(__file__).parent


@given("a new python project")
def step_new_project(context: LintContext):
    context.lint.project_files["pyproject.toml"] = (here / "data" / "pyproject.toml").read_text()


@given("there is no project file")
def step_no_project(_context: LintContext):
    pass


@given('the example file "{rel_path}"')
def step_example_file(context: LintContext, rel_path: str):
    src = here / "data" / rel_path
    context.lint.project_files[rel_path] = src.read_text()


@when('I run lint with "{args}"')
def step_run_lint(context: LintContext, args: str):
    context.result = context.lint.run(*args.split())


@when("I run lint with no arguments")
def step_run_lint_no_args(context: LintContext):
    context.result = context.lint.run()


@then("the exit code is {exit_code}")
def step_exit_code(context: LintContext, exit_code: str):
    assert context.result
    assert context.result.exit_code == int(exit_code), context.result.stdout


@then("the output contains the text")
def step_output_contains_text(context: LintContext):
    assert context.result
    assert context.text.strip() in context.result.output, context.result.output


@given("the linter {linter} is broken")
def step_linter_broken(context: LintContext, linter: str):
    context.lint.broken_linters.append(linter)


@given("the linter {linter} is missing")
def step_linter_missing(context: LintContext, linter: str):
    context.lint.missing_linters.append(linter)


@then('the output contains "{message}"')
def step_output_contains_message(context: LintContext, message: str):
    assert context.result
    assert message in context.result.output, context.result.output


@then('the file "{filename}" has not changed')
def step_file_has_not_changed(context: LintContext, filename: str):
    assert context.lint.unchanged(filename)


@then('the file "{filename}" has changed')
def step_file_has_changed(context: LintContext, filename: str):
    assert not context.lint.unchanged(filename)


@given("the linter {linter} is disabled")
def step_linter_is_disabled(context: LintContext, linter: str):
    disable_toml = dedent(
        f"""
        [tool.lint]
        {linter} = {{ run=false }}
        """
    ).strip()
    context.lint.project_files["pyproject.toml"] += disable_toml
