from typing import Any, Generator, Protocol, overload
from typing_extensions import Self


class BufferSlice(Protocol):
    segments: list[memoryview]
    byte_offset: int
    byte_length: int


class BufferView:
    segments: list[memoryview]
    byte_offset: int
    byte_length: int

    def __init__(self) -> None:
        self.segments = []
        self.byte_offset = 0
        self.byte_length = 0

    @classmethod
    def create(cls, segments: list[memoryview], byte_offset: int = 0) -> Self:
        """
        Create a new BufferView from the passed segments.
        """
        self = cls()
        self.segments = segments
        self.byte_offset = byte_offset
        self.byte_length = total_byte_length(segments)
        return self

    @classmethod
    def _create(
        cls,
        segments: list[memoryview],
        byte_offset: int,
        byte_length: int,
    ) -> Self:
        self = cls()
        self.segments = segments
        self.byte_offset = byte_offset
        self.byte_length = byte_length
        return self

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        for i in range(len(self)):
            if self[i] != other[i]:
                return False
        return True

    @overload
    def __getitem__(self, index: int) -> int: ...
    @overload
    def __getitem__(self, index: slice) -> Self: ...
    def __getitem__(self, index: Any) -> Any:
        if isinstance(index, slice):
            if index.step is not None:
                raise NotImplementedError("slice step not implemented in BufferView")
            return slice_(self, index)
        if isinstance(index, int):
            return get(self, index)
        raise TypeError("unsupported buffer slice arguments")

    def __iter__(self) -> Generator[int, None, None]:
        for segment in self.segments:
            yield from segment

    def __len__(self) -> int:
        return total_byte_length(self.segments)

    def copy_to(self, target: memoryview, offset: int = 0) -> memoryview:
        """
        Copy from the buffer at the passed offset to the target.
        """
        return copy_to(self, target, offset)

    def extend(self, bytes: memoryview) -> Self:
        """
        Add the specified bytes to the end of the buffer.
        """
        view = extend(self, bytes)
        if not isinstance(view, type(self)):
            raise Exception("extended buffer view is not an instance of buffer view")
        return view


def copy_to(buffer: BufferView, target: memoryview, offset: int = 0) -> memoryview:
    for segment in buffer.segments:
        for i in range(len(segment)):
            target[offset + i] = segment[i]
        offset += len(segment)

    return target


def get(buffer: BufferSlice, index: int) -> int:
    if index >= buffer.byte_length or index <= -buffer.byte_length:
        raise IndexError("index out of range")
    if index < 0:
        index = buffer.byte_length + index

    offset = 0
    for segment in buffer.segments:
        if index < offset + len(segment):
            return segment[index - offset]
        offset += len(segment)

    raise Exception("did not find index in segments")


def extend(buffer: BufferSlice, bytes: memoryview) -> BufferView:
    """
    Zero copy extend - adds the specified bytes to the end of the buffer
    returning a new buffer.
    """
    if len(bytes) == 0:
        return (
            buffer
            if isinstance(buffer, BufferView)
            else BufferView._create(
                buffer.segments, buffer.byte_offset, buffer.byte_length
            )
        )
    view = BufferView._create(
        list(buffer.segments), buffer.byte_offset, buffer.byte_length + len(bytes)
    )
    view.segments.append(bytes)
    return view


def slice_(buffer: BufferSlice, bounds: slice) -> BufferView:
    """
    Zero copy slice of a buffer. Creates a new BufferView referencing the shared
    segments.
    """
    segments: list[memoryview] = []
    start_offset = bounds.start if bounds.start is not None else 0
    end_offset = bounds.stop if bounds.stop is not None else buffer.byte_length
    start = start_offset if start_offset >= 0 else buffer.byte_length - start_offset
    end = end_offset if end_offset >= 0 else buffer.byte_length - end_offset

    # If start at 0 offset and end is past buffer range it is effectively
    # as same buffer.
    if start == 0 and end >= buffer.byte_length:
        return (
            buffer
            if isinstance(buffer, BufferView)
            else BufferView._create(
                buffer.segments, buffer.byte_offset, buffer.byte_length
            )
        )

    # If range is not within the current buffer just create an empty slice.
    if start > end or start > buffer.byte_length or end <= 0:
        return BufferView()

    byte_length = 0
    offset = 0
    for segment in buffer.segments:
        next_offset = offset + len(segment)
        # Have not found a start yet
        if byte_length == 0:
            # If end offset is within the current segment we know start is also,
            # because it preceeds the end & we had not found start yet.
            # In such case we create a view with only single segment of bytes
            # in the range.
            if end <= next_offset:
                range_ = segment[start - offset : end - offset]
                segments.append(range_)
                byte_length = len(range_)
                break

            # If start offeset falls with in current range (but not the end)
            # we save matching buffer slice and update byteLength.
            elif start < next_offset:
                range_ = segment if start == offset else segment[start - offset :]
                segments.append(range_)
                byte_length = len(range_)

        # Otherwise we already started collecting matching segments and are
        # looking for the end of the slice. If it is with in the current range
        # capture the segment and create a view.
        elif end <= next_offset:
            range = segment if end == next_offset else segment[0 : end - offset]
            segments.append(range)
            byte_length += len(range)
            break

        # If end is past current range we just save the segment and continue.
        else:
            segments.append(segment)
            byte_length += len(segment)

        offset = next_offset

    return BufferView._create(segments, buffer.byte_offset + start, byte_length)


def total_byte_length(segments: list[memoryview]) -> int:
    byte_length = 0
    for segment in segments:
        byte_length += len(segment)
    return byte_length
