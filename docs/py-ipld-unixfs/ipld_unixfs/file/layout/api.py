from dataclasses import dataclass
from typing import Generic, Literal, Optional, Protocol, Sequence, TypeVar, Union
from ipld_unixfs.multiformats.codecs.api import BlockEncoder
from ipld_unixfs.file.chunker.api import Chunk
from ipld_unixfs.unixfs import Metadata, File

Layout = TypeVar("Layout")

NodeID = int


@dataclass
class Branch:
    id: NodeID
    children: Sequence[NodeID]
    metadata: Optional[Metadata]


@dataclass
class Leaf:
    id: NodeID
    content: Optional[Chunk]
    metadata: Optional[Metadata]


Node = Union[Leaf, Branch]


@dataclass
class WriteResult(Generic[Layout]):
    layout: Layout
    nodes: Sequence[Branch]
    leaves: Sequence[Leaf]


@dataclass
class CloseResult:
    root: Node
    nodes: Sequence[Branch]
    leaves: Sequence[Leaf]


PB = Literal[0x70]
RAW = Literal[0x55]

FileChunkEncoder = Union[BlockEncoder[PB, bytes], BlockEncoder[RAW, bytes]]


class FileEncoder(Protocol):
    code: PB

    def encode(self, file: File) -> bytes: ...


class LayoutEngine(Protocol, Generic[Layout]):
    def open(self) -> Layout:
        """
        When new file is imported importer will call file builders `open`
        function. Here layout implementation can initialize implementation
        specific state.

        Please note it is important that builder does not mutate any state
        outside of returned state object as order of calls is non deterministic.
        """
        ...

    def write(self, layout: Layout, chunks: Sequence[Chunk]) -> WriteResult[Layout]:
        """
        Importer takes care reading file content chunking it. Afet it produces
        some chunks it will pass those via `write` call along with current
        layout a state (which was returned by `open` or previous `write` calls).

        Layout engine implementation is responsible for returning new layout
        along with all the leaf and branch nodes it created as a result.

        Note: Layout engine should not hold reference to chunks or nodes to
        avoid unecessary memory use.
        """
        ...

    def close(self, layout: Layout, metadata: Optional[Metadata] = None) -> CloseResult:
        """
        After importer wrote all the chunks through `write` calls it will call
        `close` so that layout engine can produce all the remaining nodes along
        with a root.
        """
        ...
