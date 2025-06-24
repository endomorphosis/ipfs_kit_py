import pytest
from multiformats import CID, multihash
from ipld_dag_pb import decode, encode, prepare, PBNode, code
from ipld_dag_pb.util import as_link, create_link, create_node


class TestBasics:
    def test_prepare_encode_an_empty_node(self) -> None:
        prepared = prepare({})
        assert prepared == PBNode()

        result = encode(prepared)
        assert result == bytes()

        node = decode(result)
        assert node.data is None


    def test_prepare_encode_node_with_data(self) -> None:
        data = bytes([0, 1, 2, 3, 4])
        prepared = prepare(data)
        assert prepared == PBNode(data)

        result = encode(prepared)
        assert isinstance(result, memoryview)

        node = decode(result)
        assert node.data == data


    def test_prepare_encode_node_with_string_data(self) -> None:
        data = "some bytes"
        prepared = prepare({"data": data})
        assert prepared == PBNode(data.encode("utf-8"))

        result = encode(prepared)
        assert isinstance(result, memoryview)

        node = decode(result)
        assert bytes(node.data).decode("utf-8") == data


    def test_prepare_encode_node_with_bare_string(self) -> None:
        data = "some bytes"
        prepared = prepare(data)
        assert prepared == PBNode(data.encode("utf-8"))

        result = encode(prepared)
        assert isinstance(result, memoryview)

        node = decode(result)
        assert bytes(node.data).decode("utf-8") == data


    def test_prepare_encode_node_with_links(self) -> None:
        links = [CID.decode("QmWDtUQj38YLW8v3q4A6LwPn4vYKEbuKWpgSm6bjKW6Xfe")]
        prepared = prepare({"links": links})
        assert prepared.links[0].hash == links[0]

        result = encode(prepared)
        assert isinstance(result, memoryview)

        node = decode(result)
        assert len(links) == len(node.links)

        for i in range(len(links)):
            assert links[i] == node.links[i].hash
            assert node.links[i].name is None
            assert node.links[i].t_size is None


    def test_ignore_invalid_properties_when_preparing(self) -> None:
        prepared = prepare({"foo": "bar"})
        assert prepared == PBNode()

        result = encode(prepared)
        assert result == bytes()


    def test_prepare_encode_node_with_links_and_sorting(self) -> None:
        orig_links = [
            {
                "name": "some other link",
                "hash": CID.decode("QmXg9Pp2ytZ14xgmQjYEiHjVjMFXzCVVEcRTWJBmLgR39V"),
                "t_size": 8,
            },
            {
                "name": "some link",
                "hash": CID.decode("QmXg9Pp2ytZ14xgmQjYEiHjVjMFXzCVVEcRTWJBmLgR39U"),
                "t_size": 100000000,
            },
        ]
        some_data = "some data".encode("utf-8")
        node = {"data": some_data, "links": orig_links}

        prepared = prepare(node)
        assert list(map(lambda l: l.name, prepared.links)) == [
            "some link",
            "some other link",
        ]
        byts = encode(prepared)
        expected_bytes = (
            "12340a2212208ab7a6c5e74737878ac73863cb76739d15d4666de44e5756bf55a2f9e9ab5f"
            "431209736f6d65206c696e6b1880c2d72f12370a2212208ab7a6c5e74737878ac73863cb76"
            "739d15d4666de44e5756bf55a2f9e9ab5f44120f736f6d65206f74686572206c696e6b1808"
            "0a09736f6d652064617461"
        )
        assert expected_bytes == bytes(byts).hex()

        reconstituted = decode(byts)

        # check sorting
        assert list(map(lambda l: l.name, reconstituted.links)) == [
            "some link",
            "some other link",
        ]


    def test_create_node_with_stable_sorted_links(self):
        links = [
            {
              "name": '',
              "hash": CID.decode('QmUGhP2X8xo9dsj45vqx1H6i5WqPqLqmLQsHTTxd3ke8mp'),
              "t_size": 262158
            },
            {
              "name": '',
              "hash": CID.decode('QmP7SrR76KHK9A916RbHG1ufy2TzNABZgiE23PjZDMzZXy'),
              "t_size": 262158
            },
            {
              "name": '',
              "hash": CID.decode('QmQg1v4o9xdT3Q14wh4S7dxZkDjyZ9ssFzFzyep1YrVJBY'),
              "t_size": 262158
            },
            {
              "name": '',
              "hash": CID.decode('QmdP6fartWRrydZCUjHgrJ4XpxSE4SAoRsWJZ1zJ4MWiuf'),
              "t_size": 262158
            },
            {
              "name": '',
              "hash": CID.decode('QmNNjUStxtMC1WaSZYiDW6CmAUrvd5Q2e17qnxPgVdwrwW'),
              "t_size": 262158
            },
            {
              "name": '',
              "hash": CID.decode('QmWJwqZBJWerHsN1b7g4pRDYmzGNnaMYuD3KSbnpaxsB2h'),
              "t_size": 262158
            },
            {
              "name": '',
              "hash": CID.decode('QmRXPSdysBS3dbUXe6w8oXevZWHdPQWaR2d3fggNsjvieL'),
              "t_size": 262158
            },
            {
              "name": '',
              "hash": CID.decode('QmTUZAXfws6zrhEksnMqLxsbhXZBQs4FNiarjXSYQqVrjC'),
              "t_size": 262158
            },
            {
              "name": '',
              "hash": CID.decode('QmNNk7dTdh8UofwgqLNauq6N78DPc6LKK2yBs1MFdx7Mbg'),
              "t_size": 262158
            },
            {
              "name": '',
              "hash": CID.decode('QmW5mrJfyqh7B4ywSvraZgnWjS3q9CLiYURiJpCX3aro5i'),
              "t_size": 262158
            },
            {
              "name": '',
              "hash": CID.decode('QmTFHZL5CkgNz19MdPnSuyLAi6AVq9fFp81zmPpaL2amED'),
              "t_size": 262158
            }
        ]

        some_data = "some data".encode("utf-8")
        node = PBNode(
            data=some_data, links=[as_link(link) for link in links]
        )

        prepared = prepare({"data": some_data, "links": links})
        assert prepared == node
        reconstituted = decode(encode(node))

        # sorting
        assert list(map(lambda l: l.hash, reconstituted.links)) == list(
            map(lambda l: l["hash"], links)
        )


    def test_prepare_create_link_with_empty_link_name(self):
        node = {
            "data": "hello".encode(),
            "links": [
                CID.decode("QmXg9Pp2ytZ14xgmQjYEiHjVjMFXzCVVEcRTWJBmLgR39U")
            ]
        }
        expected = PBNode(
            data=node["data"],
            links=[as_link({"hash": node["links"][0]})]
        )
        prepared = prepare(node)
        assert prepared == expected


    def test_prepare_create_link_with_undefined_name(self):
        node = {
            "data": "hello".encode(),
            "links": [
                {
                    "t_size": 10,
                    "hash": CID.decode("QmXg9Pp2ytZ14xgmQjYEiHjVjMFXzCVVEcRTWJBmLgR39U")
                }
            ]
        }
        expected = PBNode(
            data=node["data"],
            links=[as_link(node["links"][0])]
        )
        prepared = prepare(node)
        assert prepared == expected

        reconstituted = decode(encode(prepared))
        assert reconstituted == expected


    def test_create_node_with_bytes_only(self):
        node = "hello".encode()
        reconstituted = decode(encode(prepare(node)))
        assert reconstituted == PBNode(data=node, links=[])


    def test_prepare_create_empty_node(self):
        node = bytes()
        prepared = prepare(node)
        assert prepared == PBNode(data=node, links=[])
        reconstituted = decode(encode(prepared))
        assert reconstituted == PBNode(data=node, links=[])


    def test_prepare_create_empty_node_from_object(self):
        prepared = prepare({})
        assert prepared == PBNode(links=[])
        reconstituted = decode(encode(prepared))
        assert reconstituted == PBNode(links=[])


    def test_fail_prepare_create_node_with_other_data_types(self):
        invalids = [[], True, 100, lambda: {}, object()]

        for invalid in invalids:
            with pytest.raises(TypeError):
                encode(prepare(invalid))


    def test_fail_prepare_create_link_with_other_data_types(self):
        invalids = [[], True, 100, lambda: {}, object(), {"asCID": {}}]
        for invalid in invalids:
            with pytest.raises(Exception):
                encode(prepare({"links": [invalid]}))
                if not type(list):
                    # test invalids without list enclosure, but not the invalid "empty list"
                    # value itself because that won't raise an error
                    encode(prepare({"links": invalid}))


    def test_fail_create_link_with_bad_cid_hash(self):
        with pytest.raises(ValueError):
            prepare({"links": [{"hash": bytearray([0xf0, 1, 2, 3, 4])}]})


    def test_deserialize_go_ipfs_block_with_unnamed_links(self):
        test_block_unnamed_links = bytes.fromhex(
            "122b0a2212203f29086b59b9e046b362b4b19c9371e834a9f5a80597af83be6d8b7d1a5ad33b120"
            "018aed4e015122b0a221220ae1a5afd7c770507dddf17f92bba7a326974af8ae5277c198cf132063"
            "73f7263120018aed4e015122b0a22122022ab2ebf9c3523077bd6a171d516ea0e1be1beb132d8537"
            "78bcc62cd208e77f1120018aed4e015122b0a22122040a77fe7bc69bbef2491f7633b7c462d0bce9"
            "68868f88e2cbcaae9d0996997e8120018aed4e015122b0a2212206ae1979b14dd43966b0241ebe80"
            "ac2a04ad48959078dc5affa12860648356ef6120018aed4e015122b0a221220a957d1f89eb9a8615"
            "93bfcd19e0637b5c957699417e2b7f23c88653a240836c4120018aed4e015122b0a221220345f9c2"
            "137a2cd76d7b876af4bfecd01f80b7dd125f375cb0d56f8a2f96de2c31200189bfec10f0a2b080218"
            "cbc1819201208080e015208080e015208080e015208080e015208080e015208080e01520cbc1c10f"
        )

        expected_links = [
            {
                "name": '',
                "hash": CID.decode('QmSbCgdsX12C4KDw3PDmpBN9iCzS87a5DjgSCoW9esqzXk'),
                "t_size": 45623854
            },
            {
                "name": '',
                "hash": CID.decode('Qma4GxWNhywSvWFzPKtEswPGqeZ9mLs2Kt76JuBq9g3fi2'),
                "t_size": 45623854
            },
            {
                "name": '',
                "hash": CID.decode('QmQfyxyys7a1e3mpz9XsntSsTGc8VgpjPj5BF1a1CGdGNc'),
                "t_size": 45623854
            },
            {
                "name": '',
                "hash": CID.decode('QmSh2wTTZT4N8fuSeCFw7wterzdqbE93j1XDhfN3vQHzDV'),
                "t_size": 45623854
            },
            {
                "name": '',
                "hash": CID.decode('QmVXsSVjwxMsCwKRCUxEkGb4f4B98gXVy3ih3v4otvcURK'),
                "t_size": 45623854
            },
            {
                "name": '',
                "hash": CID.decode('QmZjhH97MEYwQXzCqSQbdjGDhXWuwW4RyikR24pNqytWLj'),
                "t_size": 45623854
            },
            {
                "name": '',
                "hash": CID.decode('QmRs6U5YirCqC7taTynz3x2GNaHJZ3jDvMVAzaiXppwmNJ'),
                "t_size": 32538395
            }
        ]
        node = decode(test_block_unnamed_links)
        assert node.links == [as_link(link) for link in expected_links]

        hash = multihash.digest(data=test_block_unnamed_links, hashfun="sha2-256")
        cid = CID(base="base58btc", version=0, codec=code, digest=hash)
        assert str(cid) == 'QmQqy2SiEkKgr2cw5UbQ93TtLKEMsD8TdcWggR8q9JabjX'


    def test_deserialize_go_ipfs_block_with_named_links(self):
        test_block_named_links = bytes.fromhex(
            "12390a221220b4397c02da5513563d33eef894bf68f2ccdf1bdfc14a976956ab3d1c72f735a012"
            "0e617564696f5f6f6e6c792e6d346118cda88f0b12310a221220025c13fcd1a885df444f64a4a8"
            "2a26aea867b1148c68cb671e83589f971149321208636861742e74787418e40712340a2212205d"
            "44a305b9b328ab80451d0daa72a12a7bf2763c5f8bbe327597a31ee40d1e48120c706c61796261"
            "636b2e6d3375187412360a2212202539ed6e85f2a6f9097db9d76cffd49bf3042eb2e3e8e9af4a"
            "3ce842d49dea22120a7a6f6f6d5f302e6d70341897fb8592010a020801"
        )

        expected_links = [
            {
              "name": 'audio_only.m4a',
              "hash": CID.decode('QmaUAwAQJNtvUdJB42qNbTTgDpzPYD1qdsKNtctM5i7DGB'),
              "t_size": 23319629
            },
            {
              "name": 'chat.txt',
              "hash": CID.decode('QmNVrxbB25cKTRuKg2DuhUmBVEK9NmCwWEHtsHPV6YutHw'),
              "t_size": 996
            },
            {
              "name": 'playback.m3u',
              "hash": CID.decode('QmUcjKzDLXBPmB6BKHeKSh6ZoFZjss4XDhMRdLYRVuvVfu'),
              "t_size": 116
            },
            {
              "name": 'zoom_0.mp4',
              "hash": CID.decode('QmQqy2SiEkKgr2cw5UbQ93TtLKEMsD8TdcWggR8q9JabjX'),
              "t_size": 306281879
            }
        ]

        node = decode(test_block_named_links)
        assert node.links == [as_link(link) for link in expected_links]

        hash = multihash.digest(test_block_named_links, "sha2-256")
        cid = CID(base="base58btc", version=0, codec=code, digest=hash)
        assert str(cid) == "QmbSAC58x1tsuPBAoarwGuTQAgghKvdbKSBC8yp5gKCj5M"


# Ref: https://github.com/ipld/specs/pull/360
# Ref: https://github.com/ipld/go-codec-dagpb/pull/26
    def test_deserialize_ancient_ipfs_block_with_data_before_links(self):
        out_of_order_node_hex = (
            "0a040802180612240a221220cf92fdefcdc34cac009c8b05eb662be0618db9de55ecd42785e9ec"
            "6712f8df6512240a221220cf92fdefcdc34cac009c8b05eb662be0618db9de55ecd42785e9ec67"
            "12f8df65"
        )
        out_of_order_node = bytes.fromhex(out_of_order_node_hex)
        node = decode(out_of_order_node)
        reencoded = encode(node)
        # we only care that it's different, i.e. this won't round-trip
        assert reencoded.hex() != out_of_order_node_hex


# this condition is introduced due to the laxity of the above case
    def test_node_with_data_between_links(self):
        double_links_node = bytes.fromhex(
            "12240a221220cf92fdefcdc34cac009c8b05eb662be0618db9de55ecd42785e9ec6712f8df"
            "650a040802180612240a221220cf92fdefcdc34cac009c8b05eb662be0618db9de55ecd427"
            "85e9ec6712f8df65"
        )
        with pytest.raises(Exception):
            decode(double_links_node)


    def test_prepare_create_with_multihash_bytes(self):
        link_hash = bytes.fromhex(
            '12208ab7a6c5e74737878ac73863cb76739d15d4666de44e5756bf55a2f9e9ab5f43'
        )
        link = {"name": "hello", "t_szie": 3, "hash": link_hash}

        node = {"data": b"some data", "links": [link]}
        prepared = prepare(node)
        assert str(prepared.links[0].hash) == "QmXg9Pp2ytZ14xgmQjYEiHjVjMFXzCVVEcRTWJBmLgR39U"

        reconstituted = decode(encode(prepared))
        assert str(
            reconstituted.links[0].hash
        ) == "QmXg9Pp2ytZ14xgmQjYEiHjVjMFXzCVVEcRTWJBmLgR39U"


    def test_prepare_and_create_with_cid_string(self):
        link_string = "QmXg9Pp2ytZ14xgmQjYEiHjVjMFXzCVVEcRTWJBmLgR39U"
        link = {"name": "hello", "t_size": 3, "hash": link_string}

        node = {"data": b"some data", "links": [link]}
        prepared = prepare(node)
        assert str(prepared.links[0].hash) == link_string

        reconstituted = decode(encode(prepared))
        assert str(reconstituted.links[0].hash == link_string)


    def test_fail_to_create_without_hash(self):
        node = {"data": b"some data", "links": [{"name": "hello", "t_size": 3}]}
        with pytest.raises(Exception):
            prepare(node)


class TestCreateUtilityFunctions:
    data = bytearray([0, 1, 2, 3, 4])
    a_cid = CID.decode('QmWDtUQj38YLW8v3q4A6LwPn4vYKEbuKWpgSm6bjKW6Xfe')
    links = [
        {
            "name": 'foo',
            "hash": CID.decode('QmUGhP2X8xo9dsj45vqx1H6i5WqPqLqmLQsHTTxd3ke8mp'),
            "t_size": 262158
        },
        {
            "name": 'boo',
            "hash": CID.decode('QmP7SrR76KHK9A916RbHG1ufy2TzNABZgiE23PjZDMzZXy'),
            "t_size": 262158
        },
        {
            "name": 'yep',
            "hash": CID.decode('QmQg1v4o9xdT3Q14wh4S7dxZkDjyZ9ssFzFzyep1YrVJBY'),
            "t_size": 262158
        }
    ]

    links_sorted = [links[1], links[0], links[2]]

    def test_create_node(self):
        assert create_node(self.data) == PBNode(self.data, [])
        assert create_node(self.data, []) == PBNode(self.data, [])
        assert create_node(
            self.data, [as_link(self.links[0])]
        ) == PBNode(self.data, [as_link(self.links[0])])
        assert create_node(
            self.data, [as_link(link) for link in self.links]
        ) == PBNode(self.data, [as_link(link) for link in self.links_sorted])
        assert create_node(data=None) == PBNode(links=[])


    def test_create_node_errors(self):
        invalids = [[], True, 100, lambda: {}, object()]
        for invalid in invalids:
            with pytest.raises(TypeError):
                create_node(invalid)


    def test_create_link(self):
        assert create_link(name="foo", size=100, hash=self.a_cid)
        for l in self.links:
            create_link(name=l["name"], size=l["t_size"], hash=l["hash"])
        # t_size isn't mandatory
        assert create_link(name='foo', size=None, hash=self.a_cid)
        # neither is "name"
        assert create_link(name=None, size=None, hash=self.a_cid)
        # but that's not really what this API is for ...


    def test_create_link_errors(self):
        invalids = [[], True, 100, lambda: {}, object()]
        for invalid1 in invalids:
            for invalid2 in invalids:
                for invalid3 in invalids:
                    with pytest.raises(Exception):
                        create_link(name=invalid1, size=invalid2, hash=invalid3)


def test_create_node_with_data_and_links():
    """Test creating a node with data and links"""
    data = bytes([0, 1, 2, 3, 4])
    cid1 = CID.decode("QmWDtUQj38YLW8v3q4A6LwPn4vYKEbuKWpgSm6bjKW6Xfe")
    cid2 = CID.decode("bafyreifepiu23okq5zuyvyhsoiazv2icw2van3s7ko6d3ixl5jx2yj2yhu")

    links = [
        create_link(cid1, "link1", 100),
        create_link(cid2, "link2", 200)
    ]

    node = create_node(data, links)
    result = encode(node)
    decoded = decode(result)

    assert decoded.data == data
    assert len(decoded.links) == 2
    assert decoded.links[0].hash == cid1
    assert decoded.links[0].name == "link1"
    assert decoded.links[0].t_size == 100
    assert decoded.links[1].hash == cid2
    assert decoded.links[1].name == "link2"
    assert decoded.links[1].t_size == 200


def test_create_link():
    """Test creating a link"""
    cid = CID.decode("QmWDtUQj38YLW8v3q4A6LwPn4vYKEbuKWpgSm6bjKW6Xfe")
    link = create_link(cid, "test-link", 1234)

    assert link.hash == cid
    assert link.name == "test-link"
    assert link.t_size == 1234


def test_bad_forms():
    """Test validation failure with bad forms"""
    # Missing hash
    with pytest.raises(Exception):
        encode(prepare({"links": [{"name": "missing-hash"}]}))

    # Invalid data type
    with pytest.raises(Exception):
        encode(prepare({"data": 123}))  # not bytes-like

    # Links not a list
    with pytest.raises(Exception):
        encode(prepare({"links": "not a list"}))

    # Link is not a dict
    with pytest.raises(Exception):
        encode(prepare({"links": ["not a dict"]}))
