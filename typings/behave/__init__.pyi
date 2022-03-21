# pylint: disable=all
# flake8: noqa
from typing import Callable, Any

from behave.runner import Context

__all__ = ["given", "when", "then", "fixture", "use_fixture"]

_FixtureResult = Any
_FIXTURE = Callable[..., _FixtureResult]

def given(matcher: str) -> Callable[..., Any]: ...
def when(matcher: str) -> Callable[..., Any]: ...
def then(matcher: str) -> Callable[..., Any]: ...
def use_fixture(
    fixture: _FIXTURE, context: Context, *fixture_args: Any, **fixture_kwargs: Any
) -> _FixtureResult: ...

fixture: _FIXTURE | Callable[..., _FIXTURE]
