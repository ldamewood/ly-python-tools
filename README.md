# ly_python_tools

* Auto-upgrade development dependencies in poetry
* Run a variety of linters

This is pre-alpha quality software. Use at your own risk.

## Quickstart

Install the project.
```
poetry install -E all -E flake8
poetry run pre-commit install
```

Run the linter
```
poetry run lint
```

Run autoupgrade
```
poetry run autoupgrade
```
