# pylint: disable=all
# flake8: noqa
import logging
import collections
from typing import DefaultDict

foo: DefaultDict[str, str] = collections.defaultdict()
logging.info(foo)
