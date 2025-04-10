import pytest
from ipld_unixfs.file.chunker.buffer import BufferView


def test_concat_two_bytes() -> None:
    buffer = BufferView().extend(bytes([1] * 12)).extend(bytes([2] * 8))
    assert buffer.byte_length == 20
    assert buffer[0] == 1
    assert buffer[1] == 1
    assert buffer[12] == 2
    assert buffer[19] == 2
    with pytest.raises(IndexError):
        buffer[20]


def test_slice() -> None:
    buffer = BufferView().extend(bytes([1] * 12)).extend(bytes([2] * 8)).extend(bytes())

    expect = bytearray([1] * 12)
    expect.extend(bytes([2] * 8))

    s0 = buffer[0:0]
    assert s0.byte_length == 0

    assert bytes(buffer[-1:4]) == expect[-1:4]
    assert bytes(buffer[-1:-4]) == expect[-1:-4]
    assert bytes(buffer[8:100]) == expect[8:100]

    s1 = buffer[0:3]
    assert s1.byte_length == 3
    assert [*s1] == [1, 1, 1]

    s2 = buffer[3:13]
    assert s2.byte_length == 10
    assert [*s2] == [1, 1, 1, 1, 1, 1, 1, 1, 1, 2]

    s3 = bytearray([1] * 12)
    s3.extend(bytes([2] * 8))
    s3 = s3[3:13]

    assert [*s3] == [*s2]


def test_create() -> None:
    buffer = BufferView.create([bytes([1] * 12), bytes([2] * 8)])
    assert buffer.byte_length == 20
    assert buffer[0] == 1
    assert buffer[1] == 1
    assert buffer[12] == 2
    assert buffer[19] == 2
    with pytest.raises(IndexError):
        buffer[20]
