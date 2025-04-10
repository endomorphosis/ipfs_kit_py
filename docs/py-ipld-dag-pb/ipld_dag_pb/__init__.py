from typing import Final
from multiformats import CID
from .node import BytesLike, PBLink, PBNode, RawPBLink, RawPBNode
from .encode import encode_node
from .decode import decode_node
from .util import validate, prepare

name: Final = "dag-pb"
code: Final = 0x70


def encode(node: PBNode) -> memoryview:
    validate(node)
    pbn = RawPBNode()

    links: list[RawPBLink] = []
    for l in node.links:
        link = RawPBLink()
        link.hash = bytes(l.hash)
        if l.name is not None:
            link.name = l.name
        if l.t_size is not None:
            link.t_size = l.t_size
        links.append(link)
    if len(links) > 0:
        pbn.links = links

    if node.data is not None:
        pbn.data = node.data

    return encode_node(pbn)


def decode(buf: BytesLike) -> PBNode:
    pbn = decode_node(buf)
    data = None
    if hasattr(pbn, "data"):
        data = pbn.data
    node = PBNode(data)

    if hasattr(pbn, "links"):
        links: list[PBLink] = []
        for l in pbn.links:
            if not hasattr(l, "hash"):
                raise TypeError("Invalid Hash field found in link, expected CID")
            link = PBLink(CID.decode(l.hash))

            if hasattr(l, "name"):
                link.name = l.name
            if hasattr(l, "t_size"):
                link.t_size = l.t_size

            links.append(link)
        node.links = links

    return node
