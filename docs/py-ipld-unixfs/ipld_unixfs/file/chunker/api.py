from abc import abstractmethod
from typing import Generic, Literal, Optional, Protocol, Sequence, TypeVar, Union


T = TypeVar("T")


class Chunk(Protocol):
    byte_length: int
    byte_offset: int

    def copy_to(self, target: memoryview, offset: int) -> memoryview: ...


class ChunkerBase(Generic[T]):
    """
    Chunker API can be used to slice up the file content according
    to specific logic. It is designed with following properties in mind:

    1. **Stateless** - Chunker does not retain any state across the calls. This
       implies that calling `cut` function on the same bytes would produce same
       array of sizes. Do note however, that when chunker is used to chunk
       stream of data it will be **callers responsibility** to carry remaining
       bytes in subsequent calls.

    2. **No side effects** - Chunker does not read from the underlying source
       and MUST not mutate given buffer nor any other outside references
       (including passed arguments). If your chunker is unable to operate
       optimally without interal state changes consider using `StatefulChunker`
       instead.

    3. **Does not manage resources** - Chunker does not manage any resources,
       all the data is passed in and managed by the caller, which allows it to
       control amount of memory to be used.
    """

    name: str

    context: T
    """
    Context used by the chunker. It usually represents chunker configuration
    like max, min chunk size etc. Usually chunker implementation library will
    provide utility function to initalize a context.
    """

    @abstractmethod
    def cut(self, context: T, buffer: Chunk, end: bool = False) -> Sequence[int]:
        """
        Chunker takes a `context: T` object, `buffer` containing bytes to be
        chunked. Chunker is expected to return a list of chunk byte lengths
        (from the start of the buffer). If returned list is empty that signifies
        that the buffer contains no valid chunks.

        **Note:** Consumer of the chunker is responsible for dealing with the
        remaining bytes in the buffer, that is unless `end` is true signalling
        to the chunker that the end of the stream is reached.
        """
        pass


class StatefulChunker(ChunkerBase[T]):
    """
    Stateful chunker is just like regular `Chunker` execpt it also carries
    **mutable** `state` that it is free to update as needed. It is advised to
    use the regular `Chunker` and only resort to this when chunking logic may
    depend on previously seen bytes.
    """

    type: Literal["Stateful"]


class StatelessChunker(ChunkerBase[T]):
    type: Literal["Stateless"]


Chunker = Union[StatefulChunker[T], StatelessChunker[T]]
