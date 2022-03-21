Feature: Bootstrap linters
    In order to ensure CI has good uptime and is easy to debug
    As a CI developer
    I want to ensure that infrastructure failures do not interfere with linting failures

    Scenario: Bootstrap the linter in a project
        Given a new python project
        When I run lint with "--bootstrap"
        Then the exit code is 0

    Scenario: Bootstrap outside of a project
        Given there is no project file
        When I run lint with "--bootstrap"
        Then the exit code is 1
        And the output contains the text
            """
            "pyproject.toml" could not be located
            """

    @fixture.dynamic_linter
    Scenario Outline: <linter> is broken
        Given a new python project
        And the linter <linter> is broken
        When I run lint with "--bootstrap"
        Then the exit code is 1
        And the output contains "<linter> is broken"

    @fixture.dynamic_linter
    Scenario Outline: <linter> is missing
        Given a new python project
        And the linter <linter> is missing
        When I run lint with "--bootstrap"
        Then the exit code is 1
        And the output contains "<linter> is missing"
