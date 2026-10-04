# ipld-unixfs

An implementation of the [UnixFS spec][] in Python.

## Overview

This library provides functionality similar to [ipfs-unixfs-importer][], but it had been designed around different set of use cases:

1. Writing into Content Addressable Archives ([CAR][]).

   In order to allow encoding file(s) into arbitrary number of CARs, the library makes no assumbtions about how blocks will be consumed by returning a stream of blocks and leaving it up to caller to handle the rest.

1. Incremental and resumable writes

   Instead of passing a stream of files, user creates files, writes into them and when finished gets a `CID` for it. This removes need for mapping files back to their CIDs streamed on the other end.

1. Complete control of memory and concurrency

   By using writer style API users can choose how many files to write concurrently and change that decision based on other tasks application performs. User can also specify buffer size to be able to tweak read/write coordination.

1. No indirect configuration

   Library removes indirection by taking approach similar to the [multiformats][] library. Instead of passing chunker and layout config options, you pass chunker / layout / encoder interface implementations.

## Install

```sh
pip install ipld-unixfs
```

## Usage

```py
import ipld_unixfs
from multiformats import multihash, CID

```

## Contributing

All welcome! storacha.network is open-source.

## License

Dual-licensed under [Apache-2.0 OR MIT](LICENSE.md)


[ipfs-unixfs-importer]: https://www.npmjs.com/package/ipfs-unixfs-importer
[car]: https://ipld.io/specs/transport/car/carv1/
[unixfs spec]: https://github.com/ipfs/specs/blob/master/UNIXFS.md
[multiformats]: https://github.com/multiformats/js-multiformats
