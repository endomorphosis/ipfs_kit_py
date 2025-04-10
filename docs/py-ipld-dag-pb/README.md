# ipld-dag-pb

An implementation of the DAG-PB spec for Python.

## Install

```sh
pip install ipld-dag-pb
```

## Usage

```py
from ipld_dag_pb import PBNode, encode, decode, code
from multiformats import multihash, CID

node = PBNode("Some data as a string".encode("utf-8"))
encoded_bytes = encode(node)

# Alternatively:
# from ipld_dag_pb import prepare
# encoded_bytes = encode(prepare("Some data as a string"))

digest = multihash.digest(encoded_bytes, "sha2-256")
cid = CID("base32", 1, code, digest)

print(str(cid) + " => " + encoded_bytes.hex())
# bafybeibweq2akodv3uezac2g225qvjynh7lv3xv4wp5c4uxfppogtwt3fe => 0a15536f6d652064617461206173206120737472696e67

decoded_bytes = decode(encoded_bytes)
print(decoded_bytes)
print("decoded 'Data': " + bytes(decoded_bytes.data).decode("utf-8"))
# decoded 'Data': Some data as a string
```

### `prepare()`

The DAG-PB encoding is very strict about the Data Model forms that are passed in. The objects *must* exactly resemble what they would if they were to undergo a round-trip of encode & decode. Therefore, extraneous or mistyped properties are not acceptable and will be rejected. See the [DAG-PB spec](https://github.com/ipld/specs/blob/master/block-layer/codecs/dag-pb.md) for full details of the acceptable schema and additional constraints.

Due to this strictness, a `prepare()` function is made available which simplifies construction and allows for more flexible input forms. Prior to encoding objects, call `prepare()` to receive a new object that strictly conforms to the schema.

```py
from ipld_dag_pb import prepare
from multiformats import CID

print(vars(prepare("Some data as a string")))
# -> {'data': b'Some data as a string', 'links': []}
print(vars(prepare({"links": [CID.decode("bafkqabiaaebagba")]})))
# -> {'data': None, 'links': [<ipld_dag_pb.node.PBLink object at 0x102c1b0e0>]}
```

## Contributing

All welcome! storacha.network is open-source.

## License

Dual-licensed under [Apache-2.0 OR MIT](LICENSE.md)
