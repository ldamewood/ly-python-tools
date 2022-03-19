import os

from ly_python_tools.environ import environ


def test_environ():
    """Test that context manager environ works as expected."""
    key = "__TEST_VAR__"
    value = "__TEST_VAR_VALUE__"

    assert key not in os.environ
    with environ(**{key: value}):
        assert os.environ[key] == value
    assert key not in os.environ
