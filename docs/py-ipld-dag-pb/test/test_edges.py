import pytest
from ipld_dag_pb.node import PBNode, RawPBLink, RawPBNode
from ipld_dag_pb.util import as_link
from ipld_dag_pb.encode import encode_node
from ipld_dag_pb.decode import decode_node

a_cid_bytes = bytearray([1, 85, 0, 5, 0, 1, 2, 3, 4])


def test_fail_to_encode_large_int():
    # sanity check maximum forms

    pbn = RawPBNode()
    pbl = RawPBLink()
    pbl.hash = a_cid_bytes
    pbl.t_size = 9007199254740991 - 1
    pbn.links = [pbl]
    form = pbn
    expected = "12140a0901550005000102030418feffffffffffff0f"
    assert encode_node(form).hex() == expected
    assert decode_node(bytes.fromhex(expected)) == form

    pbn = RawPBNode()
    pbl = RawPBLink()
    pbl.hash = a_cid_bytes
    pbl.t_size = 9007199254740991
    pbn.links = [pbl]
    form = pbn
    expected = '12140a0901550005000102030418ffffffffffffff0f'
    assert encode_node(form).hex() == expected
    assert decode_node(bytes.fromhex(expected)) == form

    # NOTE: python doesn't have the `MAX_SAFE_INTEGER` in js, so this test case is
    # expected pass and not fail like the js-dag-pb/tests/test-edges.spec.js test
    # case where the tests in this module are mirrored
    pbn = RawPBNode()
    pbl = RawPBLink()
    pbl.hash = a_cid_bytes
    pbl.t_size = 9007199254740991 + 1
    pbn.links = [pbl]
    form = pbn
    expected = '12140a09015500050001020304188080808080808010'
# encoding and decoding should work without failure
    assert encode_node(form).hex() == expected
    assert decode_node(bytes.fromhex(expected)) == form


def test_fail_to_encode_negative_large():
    pbn = RawPBNode()
    pbl = RawPBLink()

    pbn.data = bytearray(0)
    pbn.links = [pbl]

    pbl.name = "yoik"
    pbl.hash = a_cid_bytes
    pbl.t_size = -1

    with pytest.raises(TypeError, match=r"negative$"):
        encode_node(pbn)


def test_encode_awkward_tsize_negative_large():
    # testing len64() to make sure we can properly calculate the encoded length of
    # various awkward values
    cases = [
        6779297111, 5368709120, 4831838208, 4294967296, 3758096384, 3221225472,
        2813203579, 2147483648, 1932735283, 1610612736, 1073741824
    ]
    for t_size in cases:
        pbn = RawPBNode()
        pbn.data = bytearray([8, 1])

        pbl = RawPBLink()
        pbl.hash = a_cid_bytes
        pbl.name = "big.bin"
        pbl.t_size = t_size
        pbn.links = [pbl]

        encoded = encode_node(pbn)
        assert decode_node(encoded) == pbn
