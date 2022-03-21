# pylint: disable=all
# flake8: noqa
from __future__ import annotations

__all__ = ["Feature", "Tag", "Scenario", "Background", "Examples", "Table", "Row"]

class Feature:
    filename: str
    line: int
    keyword: str | None
    name: str
    tags: list[Tag] | None
    description: str | None
    scenarios: list[Scenario] | None
    background: Background | None
    language: str | None

class Tag:
    pass

class Scenario:
    filename: str
    line: int
    keyword: str | None
    tags: list[Tag] | None

class ScenarioOutline(Scenario):
    examples: list[Examples] | None

class Background:
    pass

class Examples:
    filename: str
    line: int
    keyword: str | None
    name: str | None
    table: Table | None

    def __init__(
        self,
        filename: str,
        line: int,
        keyword: str | None,
        name: str | None,
        tags: list[Tag] | None = ...,
        table: Table | None = ...,
    ) -> None: ...

class Table:
    rows: list[Row] | None
    headings: list[Row]

    def __init__(self, headings: list[str], rows: list[Row]) -> None: ...

class Row:
    headings: list[str]
    cells: list[str]
    line: int | None
    comments: list[str] | None

    def __init__(
        self,
        headings: list[str],
        cells: list[str],
        line: int | None = ...,
        comments: list[str] | None = ...,
    ) -> None: ...
