# ly_python_tools

This package consists of two executables:

- autoupgrade: A tool that automatically upgrades developer dependencies for a poetry project.
- lint: A linter that bootstraps and runs other linters.

This is pre-alpha quality software. Use at your own risk.

## Autoupgrade

The `autoupgrade` tool will update dev-dependencies automatically. This replaces
the process of merging dependabot PRs one at a time. Instead, we would create a
PR where we had run `autoupgrade` and that single PR replaces the individual
dependabot PRs.

By default, it will upgrade everything to the latest available at the time of
running the tool, however additional constraints can be added. Extras for
packages can also be defined. We do not support autoupgrading package
dependencies to latest because that can lead to breakages in APIs.

For example, we can configure the dev-dependencies to ensure pytest is lower
than `7.1.0` and ensure that prospector is installed with all extra tools.

```toml
[tool.autoupgrade.constraints]
pytest = "<7.1.0"

[tool.autoupgrade.extras]
prospector = ["with_everything"]
```

## Lint

We have our own wrapper around python linters because we want to unify the
tooling we use across multiple projects. We want to favor consistency and
minimal configuration. These linters are the minimum version that we support.
Additionally, `pyright` downloads software via `npx` and we want to have more
control over when that download happens in CI and add additional retry logic
that is shared across many projects. The goal is to ensure that running the lint
step in CI can never fail due to being misconfigured or due to network failures.

See this project's `pyproject.toml` for an example of how to configure the
linter.

## Quickstart

Install the project.

```
poetry install -E all -E flake8
poetry run pre-commit install
```

Bootstrap the linter. This will ensure all of the expected linters are
available.

```
poetry run lint --bootstrap
```

Lint all of the python files in the `src` and `tests` directories.

```
poetry run lint src/ tests/
```

Run autoupgrade

```
poetry run autoupgrade
```

## Using in a project

With poetry, install all linters

```
poetry add --dev ly_python_tools@latest -E all
poetry run lint --bootstrap
```

Add configuration to your `pyproject.toml`. For example,

```toml
[tool.autoupgrade.constraints]
pytest = "<7.1.0"

[tool.lint]
include = '\.py$'
flake8 = { run=false }
pyupgrade = { options=["--py37-plus"] }
pyright = { options=["--pythonversion", "3.7"] }
```

## CI config

```yaml
run: |  # Install step can fail due to network failures.
  poetry install
  poetry run lint --bootstrap
run: |  # Step should only fail due to linting failures.
  poetry run lint src/
```
