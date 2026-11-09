from typing import TypedDict, Union
import json

from multiformats import CID
import pytest

from ipld_dag_pb import  encode, decode
from ipld_dag_pb.decode import decode_node
from ipld_dag_pb.encode import encode_node
from ipld_dag_pb.node import PBNode, RawPBLink, RawPBNode
from ipld_dag_pb.util import as_link


# tests mirrored in https://github.com/ipld/js-dag-pb/blob/master/test/test-compat.spec.js

# Hash is raw+identity 0x0001020304 CID(bafkqabiaaebagba)
a_cid = CID.decode(bytearray([1, 85, 0, 5, 0, 1, 2, 3, 4]))


class Case(TypedDict):
    node: Union[RawPBNode, PBNode]
    expected_bytes: str
    expected_form: str


def serialize_node_to_json(node: Union[RawPBNode, PBNode]):
    if isinstance(node, RawPBNode):
        serialized_links = []
        serializable_obj = {}

        for link in node.links:
            link_dict = {}
            if getattr(link, "hash", None) is not None:
                link_dict["hash"] = link.hash.hex()
            if getattr(link, "name", None) is not None:
                link_dict["name"] = link.name
            if getattr(link, "t_size", None) is not None:
                link_dict["t_size"] = link.t_size
            serialized_links.append(link_dict)
        # data should come before links
        if getattr(node, "data", None) is not None:
            serializable_obj["data"] = node.data.hex()
        serializable_obj["links"] = serialized_links
        return serializable_obj
    elif isinstance(node, PBNode):
        serialized_links = []
        serializable_obj = {}

        for link in node.links:
            link_dict = {}
            link_dict["hash"] = bytes(link.hash).hex()
            if link.name is not None:
                link_dict["name"] = link.name
            if link.t_size is not None:
                link_dict["t_size"] = link.t_size
            serialized_links.append(link_dict)

        # data should come before links
        if node.data is not None:
            # if zero bytes, serialize to empty string instead
            serializable_obj["data"] = node.data if node.data != bytes(0) else ""
        serializable_obj["links"] = serialized_links
        return serializable_obj


def verify_round_trip(test_case: Case, bypass: bool):
    actual_bytes = (
        encode_node(test_case['node']) if bypass else encode(test_case['node'])  # type: ignore[type-arg]
    )
    assert actual_bytes.hex() == test_case['expected_bytes']
    round_trip_node = decode_node(actual_bytes) if bypass else decode(actual_bytes)
    if getattr(round_trip_node, "data", None):
        # this can't be a string, but we're making it so for ease of test
        round_trip_node.data = round_trip_node.data.hex()  # type: ignore[assignment]

    if round_trip_node.links:
        for link in round_trip_node.links:
            if getattr(round_trip_node, "hash", None):
                # this can't be a string, but we're making it so for ease of test
                link.hash = link.hash if bypass else bytes(link.hash)  # type: ignore[assignment]

    actual_form = json.dumps(round_trip_node, default=serialize_node_to_json)
    assert actual_form == test_case["expected_form"]


def test_empty():
    verify_round_trip(
        {
            "node": PBNode(links=[]),
            "expected_bytes": "",
            "expected_form": r'{"links": []}',
        },
        bypass=False
    )


def test_data_zero():
    verify_round_trip(
        {
            "node": PBNode(data=bytes(0)),
            "expected_bytes": '0a00',
            "expected_form": r'{"data": "", "links": []}',
        },
        bypass=False
    )


def test_data_some():
    verify_round_trip(
        {
            "node": PBNode(data=bytearray([0, 1, 2, 3, 4])),
            "expected_bytes": '0a050001020304',
            "expected_form": r'{"data": "0001020304", "links": []}',
        },
        bypass=False
    )


def test_link_zero():
    verify_round_trip(
        {
            "node": PBNode(links=[]),
            "expected_bytes": '',
            "expected_form": r'{"links": []}'
        },
        bypass=False
    )


def test_data_some_links_zero():
    test_case: Case = {
        "node": PBNode(data=bytearray([0, 1, 2, 3, 4]), links=[]),
        "expected_bytes": "0a050001020304",
        "expected_form": r'{"data": "0001020304", "links": []}'
    }
    verify_round_trip(test_case, False)


def test_links_empty():
    with pytest.raises(Exception):
        verify_round_trip(
            {
                "node": PBNode(links=[as_link({})]),
                "expected_bytes": "1200",
                "expected_form": r'{"links": [{}]}'
            },
            False
        )
    pbn = RawPBNode()
    pbl = RawPBLink()
    pbn.links = [pbl]
    # bypass straight to encode and it should verify the bytes
    verify_round_trip(
        {
            "node": pbn,
            "expected_bytes": "1200",
            "expected_form": r'{"links": [{}]}'
        },
        True
    )


def test_data_some_links_empty():
    pbn = RawPBNode()
    pbl = RawPBLink()

    pbn.data = bytearray([0, 1, 2, 3, 4])
    pbn.links = [pbl]
    test_case: Case = {
        "node": pbn,
        "expected_bytes": "12000a050001020304",
        "expected_form": r'{"data": "0001020304", "links": [{}]}'
    }
    with pytest.raises(Exception):
        # bypass straight to encode and it should verify the bytes
        verify_round_trip(test_case, True)


# this is excluded from the spec, it must be a CID bytes
def test_links_hash_zero():
    with pytest.raises(Exception):
        # NOTE: eager validation that raises "invalid hash error" prevents
        # round-tripping from happening. And this is specific to the python
        # implementation alone. This behaviour is prevalent in all the other
        # tests where there is an invalid/absent link hash
        verify_round_trip(
            {
                "node": PBNode(links=[as_link({"hash": bytes(0)})]),  # eager decoding detects that hash bytes has len(varint) < 1 and raises exception before round-trip occurs
                "expected_bytes": "12020a00",
                "expected_form": r'{"links": [{"hash": ""}]}'
            },
            False
        )

    pbn = RawPBNode()
    pbl = RawPBLink()
    pbl.hash = bytes(0)
    pbn.links = [pbl]
    test_case: Case = {
        "node": pbn,
        "expected_bytes": "12020a00",
        "expected_form": r'{"links": [{"hash": ""}]}',
    }
    # bypass straight to encode and decode and it should verify the bytes,
    # the failure is on the way in _and_ out, so we have to bypass encode & decode
    verify_round_trip(test_case, True)
    # don't bypass decode and check the bad CID test there
    with pytest.raises(Exception):
        decode(bytes.fromhex(test_case["expected_bytes"]))


def test_links_hash_some():
    verify_round_trip(
        {
            "node": PBNode(links=[as_link({"hash": a_cid})]),
            "expected_bytes": "120b0a09015500050001020304",
            "expected_form": r'{"links": [{"hash": "015500050001020304"}]}'
        },
        False
    )


def test_links_name_zero():
    with pytest.raises(Exception):
        verify_round_trip(
            {
                "node": PBNode(links=[as_link({"name": ""})]),  # eager validation detects absence of link's hash and raises exception before round-trip occurs
                "expected_bytes": "12021200",
                "expected_form": r'{"links": [{"name": ""}]}'
            },
            False
        )
    pbn = RawPBNode()
    pbl = RawPBLink()
    pbl.name = ""
    pbn.links = [pbl]
    verify_round_trip(
        {
            "node": pbn,
            "expected_bytes": "12021200",
            "expected_form": r'{"links": [{"name": ""}]}',
        },
        True
    )


def test_links_hash_name_zero():
    verify_round_trip(
        {
            "node": PBNode(links=[as_link({"hash": a_cid, "name": ""})]),
            "expected_bytes": "120d0a090155000500010203041200",
            "expected_form": r'{"links": [{"hash": "015500050001020304", "name": ""}]}',
        },
        False
    )


def test_links_name_some():
    with pytest.raises(Exception):
        verify_round_trip(
            {
                "node": PBNode(links=[as_link({"name": "some name"})]),  # eager validation detects absence of link's hash and raises exception before round-trip occurs
                "expected_bytes": "120b1209736f6d65206e616d65",
                "expected_form": r'{"links": [{"name": "some name"}]}'
            },
            False
        )

    pbn = RawPBNode()
    pbl = RawPBLink()

    pbl.name = "some name"
    pbn.links = [pbl]
    verify_round_trip(
        {
            "node": pbn,
            "expected_bytes": "120b1209736f6d65206e616d65",
            "expected_form": r'{"links": [{"name": "some name"}]}'
        },
        True
    )


# same as above but with a hash
def test_links_hash_some_name_some():
    verify_round_trip(
        {
            "node": PBNode(links=[as_link({"hash": a_cid, "name": "some name"})]),
            "expected_bytes": "12160a090155000500010203041209736f6d65206e616d65",
            "expected_form": r'{"links": [{"hash": "015500050001020304", "name": "some name"}]}'
        },
        False
    )


def test_links_tsize_zero():
    with pytest.raises(Exception):
        verify_round_trip(
            {
                "node": PBNode(links=[as_link({"t_size": 0})]),  # eager validation detects absence of link's hash and raises exception before round-trip occurs
                "expected_bytes": "12021800",
                "expected_form": r'{"links": [{"t_size": 0}]}'
            },
            False
        )

    pbn = RawPBNode()
    pbl = RawPBLink()
    pbl.t_size = 0
    pbn.links = [pbl]
    # bypass straight to encode and it should verify the bytes
    verify_round_trip(
        {
            "node": pbn,
            "expected_bytes": "12021800",
            "expected_form": r'{"links": [{"t_size": 0}]}'
        },
        True
    )


def test_links_hash_some_tsize_zero():
    verify_round_trip(
        {
            "node": PBNode(links=[as_link({"hash": a_cid, "t_size": 0})]),
            "expected_bytes": "120d0a090155000500010203041800",
            "expected_form": r'{"links": [{"hash": "015500050001020304", "t_size": 0}]}',
        },
        False
    )


def test_links_tsize_some():
    with pytest.raises(Exception):
        verify_round_trip(
            {
                "node": PBNode(links=[as_link({"t_size": 1010})]),  # eager validation detects absence of link's hash and raises exception before round-trip occurs
                "expected_bytes": "120318f207",
                "expected_form": r'{"links": [{"t_size": 1010}]}',
            },
            False
        )

    pbn = RawPBNode()
    pbl = RawPBLink()
    pbl.t_size = 1010
    pbn.links = [pbl]
    # bypass straight to encode and it should verify the bytes
    verify_round_trip(
        {
            "node": pbn,
            "expected_bytes": "120318f207",
            "expected_form": r'{"links": [{"t_size": 1010}]}'
        },
        True
    )


def test_links_hash_some_tsize_some():
    verify_round_trip(
        {
            "node": PBNode(links=[as_link({"hash": a_cid, "t_size": 9007199254740991})]),
            "expected_bytes": "12140a0901550005000102030418ffffffffffffff0f",
            "expected_form": r'{"links": [{"hash": "015500050001020304", "t_size": 9007199254740991}]}'
            },
        False
    )
