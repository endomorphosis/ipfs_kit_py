from math import inf
from multiformats import CID
from typing import Any

import pytest

from ipld_dag_pb import encode
from ipld_dag_pb.node import PBLink, PBNode
from ipld_dag_pb.util import as_link, validate

a_cid = CID.decode("bafkqabiaaebagba")

def test_validate_good_forms():
    def doesnt_throw(good: PBNode) -> None:
        validate(good)
        byts = encode(good)
        assert isinstance(byts, memoryview)

    doesnt_throw(PBNode(links=[]))

    doesnt_throw(PBNode(data=bytearray([1, 2, 3]), links=[]))

    doesnt_throw(
        PBNode(
            links=[
                as_link({"hash": a_cid}),
                as_link({"hash": a_cid, "name": "bar"}),
                as_link({"hash": a_cid, "name": "foo"}),
            ]
        )
    )

    doesnt_throw(
        PBNode(
            links=[
                as_link({"hash": a_cid}),
                as_link({"hash": a_cid, "name": "a"}),
                as_link({"hash": a_cid, "name": "a"}),
            ]
        )
    )

    l = {"hash": a_cid, "name": "a"}
    doesnt_throw(PBNode(links=[as_link(l), as_link(l)]))


def test_validate_fails_bad_forms():
    def throws(bad: Any) -> None:
        with pytest.raises(TypeError):
            validate(bad)

        with pytest.raises(TypeError):
            encode(bad)


    bads = [
        True,
        False,
        None,
        0,
        101,
        -101,
        'blip',
        [],
        inf,
        object(),
        bytearray([1, 2, 3])
    ]
    for bad in bads:
        throws(bad)

    throws({})
    throws(PBNode(data=None, links=None))  # type: ignore[type-arg]
    throws(PBNode(data={}, links=[]))  # type: ignore[type-arg]
    throws(PBNode(links=None))  # type: ignore[type-arg]

    # empty link
    throws(PBNode(links=[{}]))  # type: ignore[type-arg]

    # bad data forms
    bads = [True, False, 0, 101, -101, 'blip', inf, object, []]
    for bad in bads:
        throws(PBNode(data=bad, links=[]))

    # bad link array forms
    bads = [True, False, 0, 101, -101, 'blip', inf, object, bytearray([1, 2, 3])]
    for bad in bads:
        throws(PBNode(links=bad))

    # bad link forms
    bads = [True, False, 0, 101, -101, 'blip', inf, object, bytearray([1, 2, 3])]
    for bad in bads:
        throws(PBNode(links=bad))

    # bad link.hash forms
    bads = [True, False, 0, 101, -101, [], {}, inf, object, bytearray([1, 2, 3])]
    for bad in bads:
        throws(PBNode(links=[PBLink(hash=bad)]))

    # bad link.name forms
    bads = [True, False, 0, 101, -101, [], {}, inf, object, bytearray([1, 2, 3])]
    for bad in bads:
        throws(PBNode(links=[PBLink(hash=a_cid, name=bad)]))

    # bad link.t_size forms
    bads = [True, False, [], 'blip', {}, object, bytearray([1, 2, 3])]
    for bad in bads:
        throws(PBNode(links=[PBLink(hash=a_cid, size=bad)]))

    # bad sort
    throws(
        PBNode(
            links=[
                PBLink(hash=a_cid),
                PBLink(hash=a_cid, name="foo"),
                PBLink(hash=a_cid, name="bar")
            ]
        )
    )
    throws(
        PBNode(
            links=[
                PBLink(hash=a_cid),
                PBLink(hash=a_cid, name="aa"),
                PBLink(hash=a_cid, name="a")
            ]
        )
    )
