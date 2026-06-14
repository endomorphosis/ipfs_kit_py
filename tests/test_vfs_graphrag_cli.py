import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import anyio

from ipfs_kit_py.cli import FastCLI
from ipfs_kit_py.mcp.controllers.vfs_graphrag_controller import VFSGraphRAGController
from ipfs_kit_py.vfs_graphrag_schema import VFSObjectRecord


def _run_cli(monkeypatch, capsys, argv):
    monkeypatch.setattr(sys, "argv", ["ipfs-kit", *argv])
    anyio.run(FastCLI().run)
    return json.loads(capsys.readouterr().out)


def test_vfs_graphrag_cli_index_search_status_export_and_import(tmp_path, monkeypatch, capsys):
    index_root = tmp_path / "index"
    imported_root = tmp_path / "imported"
    bundle = tmp_path / "bundle"

    indexed = _run_cli(
        monkeypatch,
        capsys,
        [
            "vfs",
            "index",
            "--index-root",
            str(index_root),
            "--namespace",
            "research",
            "--path",
            "/docs/readme.md",
            "--content-id",
            "bafy-readme",
            "--backend",
            "ipfs",
            "--metadata-json",
            '{"project": "atlas"}',
            "--tag",
            "docs",
        ],
    )

    assert indexed["success"] is True
    assert indexed["indexed"] == 1
    assert indexed["status"]["counts"]["objects"] == 1

    search = _run_cli(
        monkeypatch,
        capsys,
        [
            "vfs",
            "search",
            "--index-root",
            str(index_root),
            "--filters-json",
            '{"metadata.project": "atlas"}',
            "readme",
        ],
    )

    assert search["success"] is True
    assert search["total"] == 1
    assert search["results"][0]["path"] == "/docs/readme.md"

    status = _run_cli(
        monkeypatch,
        capsys,
        ["vfs", "graphrag-status", "--index-root", str(index_root), "--namespace", "research"],
    )

    assert status["success"] is True
    assert status["counts"]["objects"] == 1

    exported = _run_cli(
        monkeypatch,
        capsys,
        ["vfs", "export-index", "--index-root", str(index_root), "--output", str(bundle)],
    )

    assert exported["success"] is True
    assert exported["manifest"]["counts"]["metadata"] == 1
    assert (bundle / "manifest.json").exists()

    imported = _run_cli(
        monkeypatch,
        capsys,
        [
            "vfs",
            "import-index",
            "--index-root",
            str(imported_root),
            "--input",
            str(bundle),
            "--mode",
            "metadata-plus-indexes",
        ],
    )

    assert imported["success"] is True
    assert imported["imported_counts"]["metadata"] == 1
    assert imported["status"]["counts"]["objects"] == 1


def test_vfs_graphrag_cli_indexes_records_file(tmp_path, monkeypatch, capsys):
    record = VFSObjectRecord(
        namespace="research",
        backend="s3",
        protocol="s3",
        path="/papers/graph.md",
        content_id="s3://bucket/graph.md",
        metadata={"project": "atlas"},
    )
    records_path = tmp_path / "records.jsonl"
    records_path.write_text(record.to_json() + "\n", encoding="utf-8")

    result = _run_cli(
        monkeypatch,
        capsys,
        [
            "vfs",
            "index",
            "--index-root",
            str(tmp_path / "index"),
            "--records",
            str(records_path),
        ],
    )

    assert result["success"] is True
    assert result["records"][0]["record_id"] == record.record_id


def test_vfs_graphrag_mcp_controller_delegates_to_mocked_service():
    service = SimpleNamespace(
        index_records=AsyncMock(return_value={"success": True, "indexed": 2}),
        search=AsyncMock(return_value={"success": True, "results": [{"path": "/x"}]}),
        status=AsyncMock(return_value={"success": True, "counts": {"objects": 2}}),
        export_index=AsyncMock(return_value={"success": True, "manifest": {"counts": {"metadata": 2}}}),
        import_index=AsyncMock(return_value={"success": True, "imported_counts": {"metadata": 2}}),
    )
    controller = VFSGraphRAGController(service=service)

    assert anyio.run(controller.index, {"records": []}) == {"success": True, "indexed": 2}
    assert anyio.run(controller.search, {"query": "atlas"})["results"] == [{"path": "/x"}]
    assert anyio.run(controller.status, {})["counts"] == {"objects": 2}
    assert anyio.run(controller.export_index, {"output_path": "bundle"})["manifest"]["counts"]["metadata"] == 2
    assert anyio.run(controller.import_index, {"input_path": "bundle"})["imported_counts"]["metadata"] == 2
