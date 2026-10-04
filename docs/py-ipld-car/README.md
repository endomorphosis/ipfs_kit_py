# ipld-car

Content Addressable aRchive format reader and writer.

## Install

```sh
pip install ipld-car
```

## Usage

```py
import ipld_car
from multiformats import multihash, CID

data = bytes([1, 2, 3])
digest = multihash.digest(data, "sha2-256")
cid = CID("base32", 1, "raw", digest)
block = (cid, data)

# encode a CAR file
car = ipld_car.encode([block[0]], [block])
print("CAR: ")
print("  " + str(car.tobytes()))

# decode a CAR file
roots, blocks = ipld_car.decode(car)

print("===")
print("Roots:")
for r in roots:
    print("  " + r.encode("base32"))

print("Blocks:")
for b in blocks:
    print("  CID: " + b[0].encode("base32"))
    print("  Bytes: " + str(b[1].tobytes()))

# Output:
#
# CAR: 
#   b":\xa2eroots\x81\xd8*X%\x00\x01U\x12 \x03\x90X\xc6\xf2\xc0\xcbI,S;\nM\x14\xefw\xcc\x0fx\xab\xcc\xce\xd5(}\x84\xa1\xa2\x01\x1c\xfb\x81gversion\x01'\x01U\x12 \x03\x90X\xc6\xf2\xc0\xcbI,S;\nM\x14\xefw\xcc\x0fx\xab\xcc\xce\xd5(}\x84\xa1\xa2\x01\x1c\xfb\x81\x01\x02\x03"
# ===
# Roots:
#   bafkreiadsbmmn4waznesyuz3bjgrj33xzqhxrk6mz3ksq7meugrachh3qe
# Blocks:
#   CID: bafkreiadsbmmn4waznesyuz3bjgrj33xzqhxrk6mz3ksq7meugrachh3qe
#   Bytes: b'\x01\x02\x03'
```

## Contributing

All welcome! storacha.network is open-source.

## License

Dual-licensed under [Apache-2.0 OR MIT](LICENSE.md)
