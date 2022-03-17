# ly_python_tools

- Auto-upgrade development dependencies in poetry
- Run a variety of linters

This is pre-alpha quality software. Use at your own risk.

## Quickstart

Install the project.

```
poetry install -E all -E flake8
poetry run pre-commit install
```

Bootstrap the linter. This will ensure all of the expected linters are
available.

```
poetry run lint
```

Lint all of the python files in the `src` directory.

```
poetry run lint src
```

Run autoupgrade

```
poetry run autoupgrade
```
