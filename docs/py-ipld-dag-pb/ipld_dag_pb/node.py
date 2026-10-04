from typing import Any, Final, Optional, Union
from multiformats import CID

BytesLike = Union[bytes, bytearray, memoryview]
""" Type alias for bytes-like objects. """

byteslike: Final = (bytes, bytearray, memoryview)
""" Tuple of bytes-like objects types (for use with :obj:`isinstance` checks). """

"""
PBNode and PBLink match the DAG-PB logical format, as described at:
https://github.com/ipld/specs/blob/master/block-layer/codecs/dag-pb.md#logical-format
"""


class PBLink:
    name: Optional[str]
    t_size: Optional[int]
    hash: CID

    def __init__(
        self, hash: CID, name: Optional[str] = None, size: Optional[int] = None
    ) -> None:
        self.hash = hash
        self.name = name
        self.t_size = size

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, PBLink):
            return NotImplemented
        return (
            self.hash == other.hash
            and self.name == other.name
            and self.t_size == other.t_size
        )


class PBNode:
    data: Optional[BytesLike]
    links: list[PBLink]

    def __init__(
        self, data: Optional[BytesLike] = None, links: list[PBLink] = []
    ) -> None:
        self.data = data
        self.links = links

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, PBNode):
            return NotImplemented
        if self.data != other.data:
            return False
        return self.links == other.links


"""
Raw versions of PBNode and PBLink used internally to deal with the underlying
encode/decode byte interface.
A future iteration could make encode.py and decode.py aware of PBNode and PBLink
specifics (including CID and optionals).
"""


class RawPBLink:
    name: str
    t_size: int
    hash: BytesLike


    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True

        if not isinstance(other, RawPBLink):
            return NotImplemented

        if getattr(self, "name", None) != getattr(other, "name", None):
            return False

        if getattr(self, "t_size", None) != getattr(other, "t_size", None):
            return False

        if bytes(self.hash) != bytes(other.hash):
            return False

        return True


class RawPBNode:
    data: BytesLike
    links: list[RawPBLink]

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True

        if not isinstance(other, RawPBNode):
            return NotImplemented

        if getattr(self, "data", None) != getattr(other, "data", None):
            return False

        if len(self.links) != len(other.links):
            return False

        return self.links == other.links
