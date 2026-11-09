from typing import Generic, Sequence, TypeVar
from .api import Chunk, Chunker, ChunkerBase, StatefulChunker, StatelessChunker
from .buffer import BufferView

T = TypeVar("T")


class State(Generic[T]):
    chunker: Chunker[T]
    buffer: BufferView
    chunks: Sequence[Chunk]

    def __init__(
        self, chunker: Chunker[T], buffer: BufferView, chunks: Sequence[Chunk]
    ) -> None:
        self.buffer = buffer
        self.chunker = chunker
        self.chunks = chunks


def open(chunker: Chunker[T]) -> State[T]:
    return State(chunker, BufferView(), [])


def write(state: State[T], buf: memoryview) -> State[T]:
    if len(buf) > 0:
        return split(state.chunker, state.buffer, False)
    else:
        return State(state.chunker, state.buffer, [])


def close(state: State[T]) -> State[T]:
    return split(state.chunker, state.buffer, True)


def split(chunker: Chunker[T], buffer: BufferView, end: bool) -> State[T]:
    chunks: list[Chunk] = []

    offset = 0
    for size in chunker.cut(chunker.context, buffer, end):
        # We may be splitting empty buffer in which case there will be no chunks
        # in it so we make sure that we do not emit empty buffer.
        if size > 0:
            chunk = buffer[offset : offset + size]
            chunks.append(chunk)
            offset += size

    return State(chunker, buffer[offset:], chunks)
