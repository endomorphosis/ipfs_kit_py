import pytest
from multiformats import multihash, CID
import ipld_car
from ipld_car import Block


def new_block(data: bytes) -> Block:
    digest = multihash.digest(data, "sha2-256")
    cid = CID("base32", 1, "raw", digest)
    return (cid, data)


def test_roundtrip() -> None:
    root = new_block(bytes([1, 2, 3]))
    leaf = new_block(bytes([4, 5, 6]))

    car = ipld_car.encode([root[0]], [root, leaf])
    print(car)

    roots, blocks = ipld_car.decode(car.tobytes())

    assert len(roots) == 1
    assert roots[0].encode("base32") == root[0].encode()

    assert len(blocks) == 2
    assert blocks[0][0].encode() == root[0].encode()
    assert blocks[0][1].hex() == root[1].hex()
    assert blocks[1][0].encode() == leaf[0].encode()
    assert blocks[1][1].hex() == leaf[1].hex()
