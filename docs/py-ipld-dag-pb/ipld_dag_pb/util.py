from functools import cmp_to_key
from typing import Any, Optional, Union
from multiformats import CID
from .node import BytesLike, PBLink, PBNode, byteslike

pb_node_properties = ["data", "links"]
pb_link_properties = ["hash", "name", "t_size"]


def link_comparator(a: PBLink, b: PBLink) -> int:
    if a == b:
        return 0

    abuf = a.name.encode("utf-8") if isinstance(a.name, str) else bytes()
    bbuf = b.name.encode("utf-8") if isinstance(b.name, str) else bytes()

    x = len(abuf)
    y = len(bbuf)

    for i in range(0, min(x, y)):
        if abuf[i] != bbuf[i]:
            x = abuf[i]
            y = bbuf[i]
            break

    return -1 if x < y else 1 if y < x else 0


def has_only_attrs(node: Any, attrs: list[str]) -> bool:
    for attr in vars(node).keys():
        found = False
        for only_attr in attrs:
            if attr == only_attr:
                found = True
                break
        if not found:
            return False
    return True


def as_link(link: Union[CID, str, dict]) -> PBLink:  # type: ignore[type-arg]
    """
    Converts a CID, a string encoded CID, or a PBLink-like dict to a PBLink
    """
    if isinstance(link, CID) or isinstance(link, str):
        link = {"hash": link}

    if not isinstance(link, dict):
        raise TypeError("Invalid DAG-PB form")

    hash = link.get("hash", None)
    if hash is not None:
        if isinstance(hash, str) or isinstance(hash, byteslike):
            hash = CID.decode(hash)
    if not isinstance(hash, CID):
        raise Exception("Invalid DAG-PB form (hash is not a CID)")

    pbl = PBLink(hash)

    name = link.get("name", None)
    if name is not None:
        if isinstance(name, str):
            pbl.name = name
        else:
            raise TypeError("Invalid DAG-PB form (name is not a string)")

    size = link.get("t_size", None)
    if size is not None:
        if isinstance(size, int):
            if size < 0:
                raise TypeError("Invalid DAG-PB form (t_size cannot be negative)")
            pbl.t_size = size
        else:
            raise TypeError("Invalid DAG-PB form (t_size not an integer)")

    return pbl


def prepare(node: Union[BytesLike, str, dict]) -> PBNode:  # type: ignore[type-arg]
    """
    Converts bytes, a string, or a PBNode-like dict to a PBNode
    """
    if isinstance(node, byteslike) or isinstance(node, str):
        node = {"data": node}

    if not isinstance(node, dict):
        raise TypeError("Invalid DAG-PB form")

    pbn = PBNode()
    data = node.get("data", None)
    if data is not None:
        if isinstance(data, str):
            pbn.data = data.encode("utf-8")
        elif isinstance(data, byteslike):
            pbn.data = data
        else:
            raise TypeError("Invalid DAG-PB form (data is not a string or bytes)")

    links = node.get("links", None)
    if links is not None:
        if isinstance(links, list):
            pbn.links = []
            for l in links:
                if isinstance(l, PBLink):
                    pbn.links.append(l)
                else:
                    pbn.links.append(as_link(l))
            pbn.links.sort(key=cmp_to_key(link_comparator))
        else:
            raise TypeError("Invalid DAG-PB form (links are not a list)")

    return pbn


def validate(node: PBNode) -> None:
    if not has_only_attrs(node, pb_node_properties):
        raise TypeError("Invalid DAG-PB form (extraneous properties)")

    if (node.data is not None) and (not isinstance(node.data, byteslike)):
        raise TypeError("Invalid DAG-PB form (data must be bytes)")

    if not isinstance(node.links, list):
        raise TypeError("Invalid DAG-PB form (links must be a list)")

    for i in range(0, len(node.links)):
        link = node.links[i]

        if not has_only_attrs(link, pb_link_properties):
            raise TypeError("Invalid DAG-PB form (extraneous properties on link)")

        if (link.hash is not None) and (not isinstance(link.hash, CID)):
            raise TypeError("Invalid DAG-PB form (link must have a hash)")

        if (link.name is not None) and (not isinstance(link.name, str)):
            raise TypeError("Invalid DAG-PB form (link Name must be a string)")

        if link.t_size is not None:
            if not type(link.t_size) is int:
                raise TypeError("Invalid DAG-PB form (link t_size must be an integer)")
            if link.t_size < 0:
                raise TypeError("Invalid DAG-PB form (link t_size cannot be negative)")

        if i > 0 and link_comparator(link, node.links[i - 1]) == -1:
            raise TypeError("Invalid DAG-PB form (links must be sorted by name bytes)")


def create_node(data: Optional[BytesLike], links: list[PBLink] = []) -> PBNode:
    return prepare({"data": data, "links": links})


def create_link(
    hash: CID, name: Optional[str] = None, size: Optional[int] = None
) -> PBLink:
    return as_link({"hash": hash, "name": name, "t_size": size})
