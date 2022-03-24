from __future__ import annotations

import os
from dataclasses import dataclass
import re
from typing import Pattern
from poetry.core.version.version import Version
import toml
import tokenize

maturity_levels = ["scratch", "snapshot", "release"]


class Trigger:
    def match(self, tag: str | None, branch: str | None) -> bool:
        return False


class AlwaysTrigger(Trigger):
    def match(self, tag: str | None, branch: str | None) -> bool:
        return True


@dataclass(frozen=True)
class OnTag(Trigger):
    tag_match: Pattern[str]

    def match(self, tag: str | None, branch: str | None) -> bool:
        return bool(self.tag_match.match(tag or ""))


@dataclass(frozen=True)
class OnBranch(Trigger):
    branch_match: Pattern[str]

    def match(self, tag: str | None, branch: str | None) -> bool:
        return bool(self.branch_match.match(branch or ""))


@dataclass
class Maturity:
    repo: str
    trigger: Trigger
    extra: str = ""

    def match(self, tag: str | None, branch: str | None) -> bool:
        return self.trigger.match(tag, branch)


maturity_levels = [
    Maturity(
        "${ARTIFACTORY_URL}/api/pypi/leapyear-pypi-release-local",
        trigger=OnTag(re.compile(r"^v.*")),
    ),
    Maturity(
        "${ARTIFACTORY_URL}/api/pypi/leapyear-pypi-snapshot-local",
        trigger=OnBranch(re.compile(r"^main$")),
        extra="a${CIRCLE_BUILD_NUM}+${CIRCLE_SHA1}",
    ),
    Maturity(
        "${ARTIFACTORY_URL}/api/pypi/leapyear-pypi-scratch-local",
        trigger=AlwaysTrigger(),
        extra=".dev${CIRCLE_BUILD_NUM}+${CIRCLE_SHA1}",
    ),
]

config = {"tag_env": "CIRCLE_TAG", "branch_env": "CIRCLE_BRANCH"}
pyproject = toml.load("pyproject.toml")

for maturity in maturity_levels:
    if maturity.match(tag=os.getenv(config["tag_env"]), branch=os.getenv(config["branch_env"])):
        level = maturity
        break
else:
    raise Exception("no match")

version = Version(pyproject["tool"]["poetry"]["version"])
print(os.path.expandvars(level.repo))
print(version.base_version + os.path.expandvars(level.extra))
final_version = version.base_version + os.path.expandvars(level.extra)


matcher = re.compile(r"^__version__ = \"[^\"]*\"$")
version_string = f'__version__ = "{final_version}"'

with open("src/ly_python_tools/__init__.py", "r", encoding="utf8") as fd:
    for token in tokenize.generate_tokens(fd.readline):
        if token.type == tokenize.NEWLINE:
            print(
                matcher.sub(version_string, token.line),
                end="",
            )
