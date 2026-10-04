# TODO: PR to multiformats?
from abc import abstractmethod
from typing import Generic, TypeVar


Code = TypeVar("Code", bound=int)
"""IPLD codec code."""

Data = TypeVar("Data")


class BlockEncoder(Generic[Code, Data]):
    """
    IPLD encoder part of the codec.
    """

    name: str
    code: Code

    @abstractmethod
    def encode(self, data: Data) -> bytes:
        pass
