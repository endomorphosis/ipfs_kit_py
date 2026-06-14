from pathlib import Path

from ipfs_kit_py.vfs_manager import VFSManager


class MockIndexer:
    def __init__(self):
        self.calls = []
        self.enabled = False

    def enable_graphrag_indexing(self, **kwargs):
        self.enabled = True
        self.calls.append(("enable", kwargs))
        return {"enabled": True, "mock": True}

    def index_path(self, **kwargs):
        self.calls.append(("index_path", kwargs))
        return {"indexed": 1, "path": str(kwargs["path"]), "mock": True}

    def index_namespace(self, **kwargs):
        self.calls.append(("index_namespace", kwargs))
        return {"indexed": 2, "namespace": kwargs["namespace"], "mock": True}

    def search(self, **kwargs):
        self.calls.append(("search", kwargs))
        return {"query": kwargs["query"], "results": [{"record_id": "mock"}], "mock": True}

    def export_index(self, **kwargs):
        self.calls.append(("export_index", kwargs))
        return {"records": [], "mock": True}

    def import_index(self, **kwargs):
        self.calls.append(("import_index", kwargs))
        return {"imported": 1, "mock": True}

    def get_index_status(self):
        self.calls.append(("get_index_status", {}))
        return {"ready": True, "mock": True}


def test_vfs_manager_exposes_graphrag_lifecycle_and_search_with_local_index(tmp_path):
    document = tmp_path / "notes.md"
    document.write_text("# Research\nIPFS GraphRAG indexing notes.", encoding="utf-8")

    manager = VFSManager(storage_path=tmp_path)
    enabled = manager.enable_graphrag_indexing_sync(index_path=tmp_path / "index", namespace="research")
    indexed = manager.index_path_sync(document, namespace="research", backend="local", tags=["docs"])
    results = manager.search_sync("GraphRAG", namespaces=["research"], backends=["local"], top_k=5)
    exported = manager.export_index_sync(tmp_path / "export.json")
    status = manager.get_index_status_sync()

    assert enabled["success"] is True
    assert indexed["success"] is True
    assert indexed["indexed"] == 1
    assert indexed["records"][0]["mime_type"] == "text/markdown"
    assert results["success"] is True
    assert results["total"] == 1
    assert results["results"][0]["record"]["path"] == str(document)
    assert exported["success"] is True
    assert Path(exported["export"]["path"]).exists()
    assert status["index_status"]["graphrag"]["enabled"] is True
    assert status["index_status"]["graphrag"]["stats"]["counts"]["objects"] == 1
    assert status["index_status"]["graphrag"]["stats"]["counts"]["chunks"] >= 1
    assert status["index_status"]["graphrag"]["stats"]["counts"]["entities"] >= 1


def test_vfs_manager_imports_exported_graphrag_index(tmp_path):
    source_file = tmp_path / "source.txt"
    source_file.write_text("portable metadata", encoding="utf-8")

    first = VFSManager(storage_path=tmp_path / "first")
    first.enable_graphrag_indexing_sync(index_path=tmp_path / "first-index", namespace="docs")
    first.index_path_sync(source_file, namespace="docs", backend="local")
    bundle = first.export_index_sync()["export"]

    second = VFSManager(storage_path=tmp_path / "second")
    second.enable_graphrag_indexing_sync(index_path=tmp_path / "second-index", namespace="docs")
    imported = second.import_index_sync(bundle)
    results = second.search_sync("source.txt", namespaces=["docs"])

    assert imported["success"] is True
    assert imported["imported"] >= 1
    assert results["total"] == 1
    assert results["results"][0]["record"]["path"] == str(source_file)


def test_vfs_manager_delegates_to_mocked_indexer(tmp_path):
    mock = MockIndexer()
    manager = VFSManager(storage_path=tmp_path)

    assert manager.enable_graphrag_indexing_sync(indexer=mock, namespace="mock")["mock"] is True
    assert manager.index_path_sync("/mock/path.txt")["path"] == "/mock/path.txt"
    assert manager.index_namespace_sync("mock")["indexed"] == 2
    assert manager.search_sync("query")["results"] == [{"record_id": "mock"}]
    assert manager.export_index_sync()["mock"] is True
    assert manager.import_index_sync({"records": {}})["imported"] == 1

    status = manager.get_index_status_sync()
    assert status["index_status"]["graphrag"]["enabled"] is True
    assert status["index_status"]["graphrag"]["indexer_status"]["ready"] is True
    assert [name for name, _ in mock.calls] == [
        "enable",
        "index_path",
        "index_namespace",
        "search",
        "export_index",
        "import_index",
        "get_index_status",
    ]
