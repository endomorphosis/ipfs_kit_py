import pytest
from ipld_unixfs.file.chunker import Chunk
from ipld_unixfs.file.chunker.fixed import FixedSizeChunker, FixedSizeContext


class _TestChunk(Chunk):
    buffer: bytes

    def __init__(self, buf: bytes) -> None:
        self.buffer = buf
        self.byte_length = len(buf)
        self.byte_offset = 0

    def copy_to(self, target: memoryview, offset: int) -> memoryview:
        slice = self.buffer[offset:]
        target[0 : len(slice)] = slice
        return target


def test_api() -> None:
    chunker = FixedSizeChunker(1024)
    assert chunker.name == "fixed"
    assert chunker.type == "Stateless"
    assert isinstance(chunker.context, FixedSizeContext)
    assert chunker.context.max_chunk_size == 1024
    assert callable(chunker.cut)


def test_cut() -> None:
    chunker = FixedSizeChunker(2)
    chunk_bytes = bytes([0, 1, 2, 3, 4, 5, 6])
    chunk = _TestChunk(chunk_bytes)
    cuts = chunker.cut(chunker.context, chunk)
    assert cuts == [2, 2, 2]


def test_cut_end() -> None:
    chunker = FixedSizeChunker(2)
    chunk_bytes = bytes([0, 1, 2, 3, 4, 5, 6])
    chunk = _TestChunk(chunk_bytes)
    cuts = chunker.cut(chunker.context, chunk, True)
    assert cuts == [2, 2, 2, 1]


def test_copy_to() -> None:
    chunk_bytes = bytes([0, 1, 2, 3, 4, 5, 6])
    chunk = _TestChunk(chunk_bytes)
    out = chunk.copy_to(memoryview(bytearray(len(chunk_bytes))), 0)
    assert bytes(out) == chunk_bytes


def test_copy_to_non_zero_offset() -> None:
    chunk_bytes = bytes([0, 1, 2, 3, 4, 5, 6])
    chunk = _TestChunk(chunk_bytes)
    out = chunk.copy_to(memoryview(bytearray(2)), 5)
    assert bytes(out) == bytes([5, 6])
