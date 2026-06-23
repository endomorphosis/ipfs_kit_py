import fsspec

from ipfs_kit_py.vfs_graphrag_fsspec import IndexedVFSFileSystem, VFSIndexingEvent
from ipfs_kit_py.vfs_graphrag_index import VFSGraphRAGIndex


class EventQueue:
    def __init__(self):
        self.events = []

    def enqueue(self, event):
        self.events.append(event)


def memory_fs():
    return fsspec.filesystem("memory", skip_instance_cache=True)


def test_write_delete_move_and_listing_operations_enqueue_events():
    queue = EventQueue()
    fs = IndexedVFSFileSystem(memory_fs(), indexer=queue, namespace="research", backend="memory")

    fs.pipe_file("/docs/a.txt", b"alpha")
    fs.put_file(__file__, "/docs/source.py")
    fs.mv("/docs/a.txt", "/docs/b.txt")
    listing = fs.ls("/docs", detail=True)
    info = fs.info("/docs/b.txt")
    fs.rm("/docs/b.txt")

    operations = [event.operation for event in queue.events]
    assert operations == ["write", "write", "move", "list", "info", "delete"]
    assert queue.events[0].path == "/docs/a.txt"
    assert queue.events[0].content == b"alpha"
    assert queue.events[2].destination_path == "/docs/b.txt"
    assert queue.events[3].namespace == "research"
    assert queue.events[3].backend == "memory"
    assert any(entry["name"].endswith("source.py") for entry in listing)
    assert info["name"].endswith("/docs/b.txt")
    assert fs.drain_events() == queue.events
    assert fs.events == []


def test_open_write_hook_emits_after_handle_closes():
    queue = EventQueue()
    fs = IndexedVFSFileSystem(memory_fs(), indexer=queue)

    with fs.open("/notes/open.txt", "wb") as handle:
        handle.write(b"from open")
        assert queue.events == []

    assert fs.cat_file("/notes/open.txt") == b"from open"
    assert [event.operation for event in queue.events] == ["write"]
    assert queue.events[0].metadata["method"] == "open"


def test_synchronous_indexing_persists_canonical_records_and_enriches_listing(tmp_path):
    index = VFSGraphRAGIndex(tmp_path, namespace="research")
    fs = IndexedVFSFileSystem(
        memory_fs(),
        indexer=index,
        namespace="research",
        backend="memory",
        synchronous_indexing=True,
    )

    fs.pipe_file("/docs/indexed.md", b"# Indexed")
    records = index.query_objects(namespace="research", backend="memory", path="/docs/indexed.md")
    listing = fs.ls("/docs", detail=True)

    assert len(records) == 1
    assert records[0].mime_type == "text/markdown"
    assert records[0].size_bytes == len(b"# Indexed")
    assert records[0].metadata["event"] == "write"
    indexed_entry = next(entry for entry in listing if entry["name"].endswith("/docs/indexed.md"))
    assert indexed_entry["graphrag_index"]["record_id"] == records[0].record_id


def test_delete_and_move_can_be_synchronously_indexed_as_metadata_events(tmp_path):
    index = VFSGraphRAGIndex(tmp_path)
    fs = IndexedVFSFileSystem(memory_fs(), indexer=index, backend="memory", synchronous_indexing=True)

    fs.pipe_file("/move/source.txt", b"content")
    fs.mv("/move/source.txt", "/move/dest.txt")
    fs.rm("/move/dest.txt")

    paths = {record.path: record for record in index.query_objects(backend="memory")}
    assert paths["/move/dest.txt"].metadata["event"] == "delete"
    assert paths["/move/dest.txt"].object_type == "tombstone"
    assert paths["/move/source.txt"].metadata["event"] == "delete"
    assert paths["/move/source.txt"].metadata["destination_path"] == "/move/dest.txt"


def test_optional_read_through_cat_file_enqueues_read_event():
    queue = EventQueue()
    fs = IndexedVFSFileSystem(memory_fs(), indexer=queue, index_read_through=True)

    fs.pipe_file("/read/data.txt", b"read me")
    content = fs.cat_file("/read/data.txt")

    assert content == b"read me"
    assert [event.operation for event in queue.events] == ["write", "read"]
    assert queue.events[-1].content == b"read me"
    assert isinstance(queue.events[-1], VFSIndexingEvent)
