"""Python file with good format and syntax."""

import abc
import dataclasses
import logging


@dataclasses.dataclass
class Foo(abc.ABC):
    logger = logging.getLogger(__name__)

    @abc.abstractmethod
    def run(self) -> int:
        raise NotImplementedError("run is not implemented")
