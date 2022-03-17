#!/usr/bin/env python
"""
Upgrade repo tooling.

Dependabot creates multiple PRs that can only be merged sequentially. It is easier and cheaper
to combine all PRs into one and merge that one. This is a burden that many people have raised:

* https://github.com/dependabot/dependabot-core/issues/1190
* https://www.hrvey.com/blog/combine-dependabot-prs

This script facilitates upgrading all of the dev-dependencies in a single command. The library
dependencies will to continue to be manually upgraded because we do not want to lose backwards
compatibility in the major releases.

To run, use `poetry run autoupgrade`. If there are failures in upgrading or in testing, you may
be required to add additional constraints to the `tool.autoupgrade.constraints` section of
pyproject.toml.
"""
from __future__ import annotations

import pathlib
import subprocess
from collections import defaultdict
from typing import Iterable, Mapping, NewType, Sequence

import toml

Package = NewType("Package", str)


def upgrade_packages(
    packages: Iterable[Package],
    constraints: Mapping[Package, str],
    optionals: frozenset[Package],
    extras: Mapping[Package, Sequence[str]],
    *,
    dev: bool = False,
):
    """Upgrade python packages."""
    default_constraints: defaultdict[Package, str] = defaultdict(lambda: "@latest")
    default_constraints.update(constraints)

    default_extras: defaultdict[Package, str] = defaultdict(str)
    default_extras.update({key: f"[{','.join(extra)}]" for key, extra in extras.items()})

    cmd = ["poetry", "add"]
    if dev:
        cmd.append("--dev")

    optional_packages = [
        f"{name}{default_extras[name]}{default_constraints[name]}"
        for name in packages
        if name in optionals
    ]
    required_packages = [
        f"{name}{default_extras[name]}{default_constraints[name]}"
        for name in packages
        if name not in optionals
    ]
    if len(optional_packages) > 0:
        cmd1 = cmd + ["--optional"] + optional_packages
        subprocess.run(cmd1, check=True)
    cmd2 = cmd + required_packages
    subprocess.run(cmd2, check=True)


def main():
    """Run the executable."""
    # Read configuration from pyproject.toml
    path = pathlib.Path.cwd() / "pyproject.toml"
    tool_root = toml.load(path)["tool"]
    constraints = tool_root.get("autoupgrade", {}).get("constraints", {})
    extras = tool_root.get("autoupgrade", {}).get("extras", {})
    optionals = frozenset(
        extra
        for extra_group in tool_root.get("poetry", {}).get("extras", {}).values()
        for extra in extra_group
    )
    dev_dependencies = tool_root.get("poetry", {}).get("dev-dependencies", {})

    upgrade_packages(
        packages=dev_dependencies.keys(),
        constraints=constraints,
        optionals=optionals,
        extras=extras,
        dev=True,
    )
