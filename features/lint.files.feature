Feature: Lint python files
    In order to ensure consistent code quality,
    As a developer
    I want my code to meet the linter standards.

    Scenario: No files provided doesn't fail
        Given a new python project
        When I run lint with no arguments
        Then the exit code is 0

    Scenario: Missing project file
        Given there is no project file
        When I run lint with "src"
        Then the exit code is 1
        And the output contains the text
            """
            "pyproject.toml" could not be located
            """

    Scenario: Linted file should pass linting and remain unchanged
        Given a new python project
        And the example file "src/passes.py"
        When I run lint with "src"
        Then the exit code is 0
        And the output contains "- src/passes.py"
        And the file "src/passes.py" has not changed

    @fixture.dynamic_linter
    Scenario Outline: Lints are detected from <linter>
        Given a new python project
        And the example file "src/fails_<linter>.py"
        When I run lint with "src"
        Then the exit code is <trigger_exitcode>
        And the output contains "- src/fails_<linter>.py"
        And the output contains "<linter> found errors"

    @fixture.dynamic_linter
    Scenario Outline: <linter> can be disabled
        Given a new python project
        And the example file "src/fails_<linter>.py"
        And the linter <linter> is disabled
        When I run lint with "src"
        Then the exit code is 0
        And the output contains "- src/fails_<linter>.py"

    @fixture.dynamic_linter
    Scenario Outline: Changes are made with <linter>
        Given a new python project
        And the example file "src/fails_<linter>.py"
        When I run lint with "src"
        Then the exit code is <trigger_exitcode>
        Then the output contains "- src/fails_<linter>.py"
        And the file "src/fails_<linter>.py" has <changes>

    @fixture.dynamic_linter
    Scenario Outline: <linter> can be disabled
        Given a new python project
        And the example file "src/fails_<linter>.py"
        And the linter <linter> is disabled
        When I run lint with "src"
        Then the exit code is 0
        And the output contains "- src/fails_<linter>.py"
        And the file "src/fails_<linter>.py" has not changed

    Scenario: Linter can fail for multiple reasons on one file
        Given a new python project
        And the example file "src/fails_multiple.py"
        When I run lint with "src"
        Then the exit code is 1
        And the output contains "- src/fails_multiple.py"
        And the output contains "flake8 found errors"
        And the output contains "prospector found errors"
        And the output contains "pyright found errors"
        And the file "src/fails_multiple.py" has changed

    Scenario: Linter can fail for multiple reasons across many file
        Given a new python project
        And the example file "src/fails_black.py"
        And the example file "src/fails_flake8.py"
        And the example file "src/fails_isort.py"
        And the example file "src/fails_prospector.py"
        And the example file "src/fails_pyright.py"
        And the example file "src/fails_pyupgrade.py"
        When I run lint with "src"
        Then the exit code is 1
        And the output contains "- src/fails_black.py"
        And the output contains "- src/fails_flake8.py"
        And the output contains "- src/fails_isort.py"
        And the output contains "- src/fails_prospector.py"
        And the output contains "- src/fails_pyright.py"
        And the output contains "- src/fails_pyupgrade.py"
        And the output contains "flake8 found errors"
        And the output contains "prospector found errors"
        And the output contains "pyright found errors"
        And the file "src/fails_black.py" has changed
        And the file "src/fails_isort.py" has changed
        And the file "src/fails_pyupgrade.py" has changed
