from dataclasses import dataclass
from typing import Optional, Sequence
from ipld_unixfs.file.chunker.api import Chunk
from ipld_unixfs.file.layout.api import (
    Branch,
    CloseResult,
    LayoutEngine,
    Leaf,
    WriteResult,
)
from ipld_unixfs.unixfs import Metadata

EMPTY = ()


class Balanced:
    """
    Type representing a state of the balanced tree. First row hold leaves coming
    into a builder, once number of leaves in the stack reaches `maxChildren`
    they are moved into `RootNode` instance which is pushed into the next row of
    nodes. If next row now contains `maxChildren` nodes from there are again
    moved into a new `RootNode` and pushed into next row etc...

    For illustration let's assume we have `maxChildren: 3`, after 3 leafs were
    added tree will have following layout

    ```
    #           (root1)
    #              |
    #    ----------------------
    #    |         |          |
    #  (leaf1)   (leaf2)    (leaf3)
    ```

    Which in our model before flushing is represented as follows:

    ```
    {
      width: 3
      leaf_index: [leaf1, leaf2, leaf3]
      node_index: []
      nodes: []
    }
    ```

    After flushing 3 leaves (which is width) are moved into a `RootNode` that
    is added to `nodes` array (and returned so that caller can create a block).
    Additionally position of the added node is captured in the `index` at an
    appropriate depth `0` (that is because we don't count leaves into depth).

    ```
    {
      width: 3
      leaf_index: []
      node_index: [[0]]
      nodes: [RootNode([leaf1, leaf2, leaf3])]
    }
    ```

    Increasing number of leaves to 10 would produce following tree layout

    ```
    #                                                          (root7)
    #                                                            |
    #                                    ------------------------------------------
    #                                    |                                        |
    #                                  (root4)                                  (root6)
    #                                    |                                        |
    #            -------------------------------------------------                |
    #            |                       |                       |                |
    #          (root1)                 (root2)                 (root3)          (root5)
    #            |                       |                       |                |
    #    --------|--------       --------|--------       --------|--------        |
    #    |       |       |       |       |       |       |       |       |        |
    #  (leaf1) (leaf2) (leaf3) (leaf4) (leaf5) (leaf6) (leaf7) (leaf8) (leaf9) (leaf10)
    ```

    Which in our model will look as follows (note we do not have root5 - root7
    in model because they are build once width is reached or once builder is
    closed)

    ```
    {
      width: 3
      leaf_index: [leaf10]
      node_index: [
        [0, 1, 2], // [r1, r2, r3]
        [3]        // [r4]
      ]
      nodes: [
        Node([leaf1, leaf2, leaf3]), // r1
        Node([leaf4, leaf5, leaf6]), // r2
        Node([leaf7, leaf8, leaf9]), // r3
        Node([ // r4
            Node([leaf1, leaf2, leaf3]), // r1
            Node([leaf4, leaf5, leaf6]), // r2
            Node([leaf7, leaf8, leaf9]), // r3
        ])
      ]
    }
    ```
    """

    width: int
    head: Optional[Chunk]
    leaf_index: Sequence[int]
    node_index: Sequence[Sequence[int]]
    last_id: int

    def __init__(
        self,
        width: int,
        head: Optional[Chunk] = None,
        leaf_index: Sequence[int] = [],
        node_index: Sequence[Sequence[int]] = [],
        last_id: int = 0,
    ):
        self.width = width
        self.head = head
        self.leaf_index = leaf_index
        self.node_index = node_index
        self.last_id = last_id


class BalancedLayout(LayoutEngine[Balanced]):
    width: int

    def __init__(self, width: int):
        self.width = width

    def open(self) -> Balanced:
        return open(self.width)

    def write(self, layout: Balanced, chunks: Sequence[Chunk]) -> WriteResult[Balanced]:
        return write(layout, chunks)

    def close(
        self, layout: Balanced, metadata: Optional[Metadata] = None
    ) -> CloseResult:
        return close(layout, metadata)


def with_width(width: int) -> LayoutEngine[Balanced]:
    return BalancedLayout(width)


@dataclass(frozen=True)
class Options:
    width: int


defaults = Options(174)


def open(width: int = defaults.width) -> Balanced:
    return Balanced(width)


def write(layout: Balanced, chunks: Sequence[Chunk]) -> WriteResult[Balanced]:
    if len(chunks) == 0:
        return WriteResult(layout, EMPTY, EMPTY)

    last_id = layout.last_id

    # We need to hold on to the first chunk until we either get a second chunk
    # (at which point we know our layout will have branches) or until we close
    # (at which point our layout will be single leaf or node depneding on
    # metadata)
    head: Optional[Chunk] = None
    slices: list[Chunk] = []

    if layout.head is not None:
        # If we had a head we have more then two chunks (we already checked
        # chunks weren't empty) so we process head along with other chunks.
        slices.append(layout.head)
        slices.extend(chunks)
    elif len(chunks) == 1 and len(layout.leaf_index) == 0:
        # If we have no head no leaves and got only one chunk we have to save it
        # until we can decide what to do with it.
        head = chunks[0]
    else:
        # Otherwise we have no head but got enough chunks to know we'll have a
        # node.
        slices.extend(chunks)

    if len(slices) == 0:
        return WriteResult(
            Balanced(
                layout.width,
                head,
                layout.leaf_index,
                layout.node_index,
                layout.last_id,
            ),
            EMPTY,
            EMPTY,
        )

    leaf_index: list[int] = []
    leaf_index.extend(layout.leaf_index)
    leaves = []

    for chunk in slices:
        last_id += 1
        leaf = Leaf(last_id, chunk, None)
        leaves.append(leaf)
        leaf_index.append(leaf.id)

    if len(leaf_index) > layout.width:
        return flush(
            Balanced(layout.width, head, leaf_index, layout.node_index, last_id),
            leaves,
        )

    return WriteResult(
        Balanced(layout.width, head, leaf_index, layout.node_index, last_id),
        EMPTY,
        leaves,
    )


def _grow(index: list[list[int]], length: int) -> None:
    while len(index) < length:
        index.append([])


def flush(
    state: Balanced,
    leaves: Sequence[Leaf] = [],
    nodes: Sequence[Branch] = [],
    close: bool = False,
) -> WriteResult[Balanced]:
    last_id = state.last_id
    node_index: list[list[int]] = []
    for row in state.node_index:
        node_index.append(list(row))
    leaf_index = list(state.leaf_index)
    width = state.width
    nodes = list(nodes)

    # Move leaves into nodes
    while len(leaf_index) > width or (len(leaf_index) > 0 and close):
        _grow(node_index, 1)
        last_id += 1
        node = Branch(last_id, leaf_index[0:width], None)
        leaf_index = leaf_index[width:]
        node_index[0].append(node.id)
        nodes.append(node)

    depth = 0
    while depth < len(node_index):
        row = node_index[depth]
        depth += 1

        while len(row) > width or (len(row) > 0 and depth < len(node_index)):
            last_id += 1
            node = Branch(last_id, row[0:width], None)
            row = row[width:]
            _grow(node_index, depth + 1)
            nodes.append(node)

    return WriteResult(
        Balanced(state.width, state.head, leaf_index, node_index, last_id),
        nodes,
        leaves,
    )


def close(layout: Balanced, metadata: Optional[Metadata] = None) -> CloseResult:
    if layout.head is not None:
        return CloseResult(Leaf(1, layout.head, metadata), EMPTY, EMPTY)

    if len(layout.leaf_index) == 0:
        return CloseResult(Leaf(1, None, metadata), EMPTY, EMPTY)

    # Flush with width 1 so all the items will be propagate up the tree
    # and height of `depth-1` so we propagate nodes all but from the top
    # most level.
    result = flush(layout, EMPTY, EMPTY, True)
    nodes = result.nodes
    node_index = result.layout.node_index
    height = len(node_index) - 1
    top = node_index[height]

    if len(top) == 1:
        root = nodes[len(nodes) - 1]
        nodes = nodes[0:-1]
        return CloseResult(root, nodes, EMPTY)

    root = Branch(result.layout.last_id + 1, top, metadata)
    return CloseResult(root, nodes, EMPTY)
