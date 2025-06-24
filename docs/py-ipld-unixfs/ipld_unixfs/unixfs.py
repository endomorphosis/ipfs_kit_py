from enum import Enum
from typing import Literal, Optional, Protocol, Sequence, Union

from multiformats import CID


class NodeType(Enum):
    Raw = 0
    Directory = 1
    File = 2
    Metadata = 3
    Symlink = 4
    HAMTShard = 5


Mode = int
"""
The mode is for persisting the file permissions in [numeric notation].
If unspecified this defaults to
- `0755` for directories/HAMT shards
- `0644` for all other types where applicable

The nine least significant bits represent `ugo-rwx`
The next three least significant bits represent setuid, setgid and the sticky bit.
The remaining 20 bits are reserved for future use, and are subject to change.

Spec implementations MUST handle bits they do not expect as follows:
- For future-proofing the (de)serialization layer must preserve the entire
  `uint32` value during clone/copy operations, modifying only bit values that
  have a well defined meaning:
  `clonedValue = ( modifiedBits & 07777 ) | ( originalValue & 0xFFFFF000 )`
- Implementations of this spec MUST proactively mask off bits without a
  defined meaning in the implemented version of the spec:
  `interpretedValue = originalValue & 07777`

[numeric notation]:https://en.wikipedia.org/wiki/File-system_permissions#Numeric_notation

@see https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/sys_stat.h.html
"""


class MTime:
    """
    Representing the modification time in seconds relative to the unix epoch
    1970-01-01T00:00:00Z.
    """

    secs: int
    nsecs: Optional[int]


class Metadata:
    mode: Optional[Mode]
    mtime: Optional[MTime]


class SimpleFile:
    """
    Logical representation of a file that fits a single block. Note this is only
    semantically different from a `FileChunk` and your interpretation SHOULD
    vary depending on where you encounter the node (In root of the DAG or not).
    """

    metadata: Optional[Metadata]
    type: Literal[NodeType.File]
    layout: Literal["simple"]
    content: bytes


class FileChunk:
    """
    Logical representation of a file chunk (a leaf node of the file DAG layout).

    When a large file is added to IPFS it gets chunked into smaller pieces
    (according to the `--chunker` specified) and each chunk is encoded into this
    representation (and linked from file DAG). Please note that in practice
    there are many other representations for file chunks (leaf nodes) like `Raw`
    nodes (deprecated in favor of this representation) and raw binary nodes
    (That is 0x55 multicodec) which are on a way to surpass this representation.

    Please note that in protobuf representation there is only one `file` node
    type with many optional fields, however different combination of fields
    corresponds to a different semntaics and we represent each via different
    type.

    Also note that some file nodes may also have `mode` and `mtime` fields,
    which we represent via `SimpleFile` type, however in practice the two are
    indistinguishable & how to interpret will only depend on whether the node is
    encountered in DAG root position or not. That is because one could take two
    `SimpleFile` nodes and represent their concatination via `AdvancedFile`
    simply by linking to them. In such scenario consumer SHOULD treat leaves as
    `FileChunk`s and ignoring their `mode` and `mtime` fileds. However if those
    leaves are encountered on their own consumer SHOULD treat them as
    `SimpleFile`s and take `mode` and `mtime` fields into account.
    """

    metadata: Optional[Metadata]
    type: Literal[NodeType.File]
    layout: Literal["simple"]
    content: bytes


class DAGLink:
    cid: CID
    """*C*ontent *Id*entifier of the target DAG."""

    dagByteLength: int
    """
    Cumulative number of bytes in the target DAG, that is number of bytes in the
    block and all the blocks it links to.
    """


class ContentDAGLink(DAGLink):
    contentByteLength: int
    """Total number of bytes in the file."""


FileLink = ContentDAGLink


class FileShard:
    """
    Logical representation of a file shard. When large files are chunked,
    slices that span multiple blocks may be represented as file shards in
    certain DAG layouts (e.g. balanced & trickle DAGs).

    Please note in protobuf representation there is only one `file` node type
    with many optional fields. Different combinations of those fields
    correspond to a different semantics. The combination of fields in this type
    represent branch nodes in the file DAGs in which nodes beside leaves and
    root exist.

    Also note that you may encounter `FileShard`s with `mode` and `mtime` fields
    which, according to our definition would be `AdvancedFile`. However just as
    with `FileChunk` / `SimpleFile`, here as well, you should treat node as
    `AdvancedFile` if you encounter it in the root position (that is to say
    regard `mode`, `mtime` field) and treat it as `FileShard` node if
    encountered in any other position (that is ignore `mode`, `mtime` fileds).
    """

    type: Literal[NodeType.File]
    layout: Literal["advanced"]
    parts: Sequence[FileLink]


class AdvancedFile:
    """
    Logical represenatation of a file that consists of multiple blocks. Note it
    is only semantically different from a `FileShard` and your interpretation
    SHOULD vary depending on where you encounter the node (In root of the DAG
    or not).
    """

    metadata: Optional[Metadata]
    type: Literal[NodeType.File]
    layout: Literal["advanced"]
    parts: Sequence[FileLink]


File = Union[SimpleFile, AdvancedFile]
