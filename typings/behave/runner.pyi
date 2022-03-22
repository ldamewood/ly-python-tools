# pylint: disable=all
# flake8: noqa
from __future__ import annotations
from typing import Any, Callable

_CLEANUP_FUNC = Callable[..., Any]

__all__ = ["Context"]

class Context:
    BEHAVE: str
    USER: str
    FAIL_ON_CLEANUP_ERRORS: bool

    feature: Any
    text: str
    table: Any
    stdout_capture: Any
    stderr_capture: Any
    log_capture: Any
    fail_on_cleanup_errors: bool

    @staticmethod
    def ignore_cleanup_error(
        context: Context, cleanup_func: _CLEANUP_FUNC, exception: Exception
    ) -> None: ...
    @staticmethod
    def print_cleanup_error(
        context: Context, cleanup_func: _CLEANUP_FUNC, exception: Exception
    ) -> None: ...
    def use_with_user_mode(self) -> None: ...
    def user_mode(self) -> None: ...
    def __getattr__(self, attr: str) -> Any: ...
    def __setattr__(self, attr: str, value: Any) -> None: ...
    def __delattr__(self, attr: str) -> None: ...
    def __contains__(self, attr: str) -> bool: ...
    def execute_steps(self, steps_text: str) -> bool: ...
    def add_cleanup(self, cleanup_func: _CLEANUP_FUNC, *args: Any, **kwargs: Any) -> None: ...
