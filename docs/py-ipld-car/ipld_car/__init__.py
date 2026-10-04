import dag_cbor
from dag_cbor import IPLDKind
from multiformats import CID, varint
from typing import Final, Tuple, Union

BytesLike = Union[bytes, bytearray, memoryview]
""" Type alias for bytes-like objects. """

byteslike: Final = (bytes, bytearray, memoryview)
""" Tuple of bytes-like objects types (for use with :obj:`isinstance` checks). """

Block = Tuple[CID, BytesLike]
""" Represents an IPLD block (including its CID). """


def encode(roots: list[CID], blocks: list[Block]) -> memoryview:
    """
    Encode a CAR v1 file from a list of root CIDs and blocks.
    """
    buffer = bytearray()

    header_bytes = dag_cbor.encode({"version": 1, "roots": list[IPLDKind](roots)})
    header_len = varint.encode(len(header_bytes))
    buffer += header_len
    buffer += header_bytes

    for b in blocks:
        cid = b[0]
        if not isinstance(cid, CID):
            raise TypeError("block CID is not an instance of CID")
        cid_bytes = bytes(cid)

        block_bytes = b[1]
        if not isinstance(block_bytes, byteslike):
            raise TypeError("block bytes is not an instance of BytesLike")

        block_len = varint.encode(len(cid_bytes) + len(block_bytes))
        buffer += block_len
        buffer += cid_bytes
        buffer += block_bytes

    return memoryview(buffer)


def decode(buffer: BytesLike) -> tuple[list[CID], list[Block]]:
    """
    Decode a CAR v1 file into a list of root CIDs and blocks.
    """
    header_len, n, _ = varint.decode_raw(buffer)
    header = dag_cbor.decode(bytes(buffer[n : n + header_len]))

    if not isinstance(header, dict):
        raise TypeError("unexpected header type")

    if header.get("version") != 1:
        raise Exception("unexpected CAR version")

    raw_roots = header.get("roots")
    if not isinstance(raw_roots, list):
        raise TypeError("unexpected roots type")

    roots: list[CID] = []
    for r in raw_roots:
        if not isinstance(r, CID):
            raise TypeError("unexpected root type")
        roots.append(r)

    blocks: list[Block] = []
    index = n + header_len
    while True:
        if index >= len(buffer):
            break

        block_len, n, _ = varint.decode_raw(buffer[index:])
        index += n
        cid_start = index
        version, n, _ = varint.decode_raw(buffer[index:])
        index += n

        cid = None
        if version == 1:
            codec_code, n, _ = varint.decode_raw(buffer[index:])
            index += n
            hash_code, n, _ = varint.decode_raw(buffer[index:])
            index += n
            digest_size, n, _ = varint.decode_raw(buffer[index:])
            index += n
            digest = buffer[index : index + digest_size]
            index += digest_size
            cid = CID("base32", 1, codec_code, (hash_code, digest))
        elif version == 0x12:  # If version is the sha2-256 codec, then assume CIDv0
            digest = buffer[index : index + 32]
            index += 32
            cid = CID("base58btc", 0, "dag-pb", ("sha2-256", digest))
        else:
            raise Exception("invalid CID version")

        bytes_len = block_len - (index - cid_start)
        blocks.append((cid, buffer[index : index + bytes_len]))
        index += bytes_len

    return roots, blocks
