from typing import Tuple, Union
from .node import BytesLike, RawPBLink, RawPBNode


def decode_varint(buf: BytesLike, offset: int) -> Tuple[int, int]:
    v = 0
    shift = 0
    while True:
        if shift >= 64:
            raise OverflowError("protobuf: varint overflow")
        if offset >= len(buf):
            raise EOFError("protobuf: unexpected end of data")

        b = buf[offset]
        offset += 1
        v += (b & 0x7F) << shift if shift < 28 else (b & 0x7F) * (2**shift)

        if b < 0x80:
            break
        shift += 7

    return (v, offset)


def decode_bytes(buf: BytesLike, offset: int) -> Tuple[BytesLike, int]:
    byte_len, offset = decode_varint(buf, offset)
    post_offset = offset + byte_len

    if byte_len < 0 or post_offset < 0:
        raise ValueError("protobuf: invalid length")
    if post_offset > len(buf):
        raise EOFError("protobuf: unexpected end of data")

    return (buf[offset:post_offset], post_offset)


def decode_key(buf: BytesLike, index: int) -> Tuple[int, int, int]:
    wire, index = decode_varint(buf, index)
    # (wire_type, field_num, new_index)
    return (wire & 0x7, wire >> 3, index)


def decode_link(buf: BytesLike) -> RawPBLink:
    link = RawPBLink()
    l = len(buf)
    index = 0

    while index < l:
        wire_type, field_num, index = decode_key(buf, index)

        if field_num == 1:
            if hasattr(link, "hash"):
                raise Exception("protobuf: (PBLink) duplicate Hash section")
            if wire_type != 2:
                raise ValueError(
                    "protobuf: (PBLink) wrong wire type ("
                    + str(wire_type)
                    + ") for Hash"
                )
            if hasattr(link, "name"):
                raise Exception(
                    "protobuf: (PBLink) invalid order, found Name before Hash"
                )
            if hasattr(link, "t_size"):
                raise Exception(
                    "protobuf: (PBLink) invalid order, found Tsize before Hash"
                )

            link.hash, index = decode_bytes(buf, index)
        elif field_num == 2:
            if hasattr(link, "name"):
                raise Exception("protobuf: (PBLink) duplicate Name section")
            if wire_type != 2:
                raise ValueError(
                    "protobuf: (PBLink) wrong wire type ("
                    + str(wire_type)
                    + ") for Name"
                )
            if hasattr(link, "t_size"):
                raise Exception(
                    "protobuf: (PBLink) invalid order, found Tsize before Name"
                )

            byts, index = decode_bytes(buf, index)
            link.name = str(byts, "utf-8")
        elif field_num == 3:
            if hasattr(link, "t_size"):
                raise Exception("protobuf: (PBLink) duplicate Tsize section")
            if wire_type != 0:
                raise ValueError(
                    "protobuf: (PBLink) wrong wire type ("
                    + str(wire_type)
                    + ") for Tsize"
                )

            link.t_size, index = decode_varint(buf, index)
        else:
            raise Exception(
                "protobuf: (PBLink) invalid field number, expected 1, 2 or 3, got "
                + str(field_num)
            )

    if index > l:
        raise EOFError("protobuf: (PBLink) unexpected end of data")

    return link


def decode_node(buf: BytesLike) -> RawPBNode:
    l = len(buf)
    index = 0
    links: Union[list[RawPBLink], None] = None
    links_before_data = False
    data: Union[BytesLike, None] = None

    while index < l:
        wire_type, field_num, index = decode_key(buf, index)

        if wire_type != 2:
            raise Exception(
                "protobuf: (PBNode) invalid wire type, expected 2, got "
                + str(wire_type)
            )

        if field_num == 1:
            if data != None:
                raise Exception("protobuf: (PBNode) duplicate Data section")

            data, index = decode_bytes(buf, index)
            if links is not None:  # Set flag if links exist before data
                links_before_data = True
        elif field_num == 2:
            if links_before_data:  # interleaved Links/Data/Links
                raise Exception("protobuf: (PBNode) duplicate Links section")
            elif links is None:
                links = []

            byts, index = decode_bytes(buf, index)
            links.append(decode_link(byts))
        else:
            raise Exception(
                "protobuf: (PBNode) invalid fieldNumber, expected 1 or 2, got "
                + str(field_num)
            )

    if index > l:
        raise EOFError("protobuf: (PBNode) unexpected end of data")

    node = RawPBNode()
    if data != None:
        node.data = data
    if links != None:
        node.links = links
    else:
        node.links = []  # Ensure links is never None in output, matching JS

    return node
