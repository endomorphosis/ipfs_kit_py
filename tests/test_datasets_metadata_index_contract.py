#!/usr/bin/env python3
"""Focused metadata-index contract tests for ipfs_datasets integration in ipfs_kit submodule."""

import sys
import json
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from ipfs_kit_py.ipfs_datasets_integration import IPFSDatasetsManager


def test_store_and_list_updates_real_metadata_index(tmp_path):
    dataset = tmp_path / "sample.csv"
    dataset.write_text("id,value\n1,alpha\n2,beta\n", encoding="utf-8")

    manager = IPFSDatasetsManager(enable=False)
    store_result = manager.store(dataset, metadata={"description": "sample dataset"})
    assert store_result["success"] is True

    listed = manager.list()
    assert listed["success"] is True
    assert listed["count"] >= 1

    entry = next(item for item in listed["items"] if item["path"] == str(dataset))
    assert entry["schema"]["source"] == "csv_header"
    assert "id" in entry["schema"]["fields"]
    assert "value" in entry["schema"]["fields"]


def test_load_and_remove_update_metadata_index(tmp_path):
    dataset = tmp_path / "train.jsonl"
    dataset.write_text('{"text":"hello","label":"x"}\n', encoding="utf-8")

    manager = IPFSDatasetsManager(enable=False)
    manager.store(dataset)

    load_result = manager.load(str(dataset))
    assert load_result["success"] is True

    snapshot = manager.metadata_index_snapshot()
    assert snapshot["metrics"]["index_refresh"] >= 2  # store + load

    remove_result = manager.remove(str(dataset))
    assert remove_result["success"] is True

    listed = manager.list()
    remaining_paths = [item.get("path") for item in listed["items"]]
    assert str(dataset) not in remaining_paths


def test_record_ipfs_operation_refreshes_index(tmp_path):
    dataset = tmp_path / "test.csv"
    dataset.write_text("a,b\n1,2\n", encoding="utf-8")

    manager = IPFSDatasetsManager(enable=False)
    result = manager.record_ipfs_operation(
        {
            "operation": "write",
            "path": str(dataset),
            "dataset_summary": "updated from vfs",
        }
    )
    assert result["success"] is True

    listed = manager.list()
    assert listed["count"] >= 1
    entry = next(item for item in listed["items"] if item["path"] == str(dataset))
    assert entry["operation"] == "write"
    assert entry["metadata"].get("dataset_summary") == "updated from vfs"


def test_metadata_index_file_is_valid_json_after_refresh(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    dataset = tmp_path / "indexable.csv"
    dataset.write_text("a,b\n1,2\n", encoding="utf-8")

    manager = IPFSDatasetsManager(enable=False)
    refresh = manager.refresh_metadata_index(path=dataset, operation="store", metadata={"source": "test"})
    assert refresh["success"] is True

    assert manager.metadata_index_path.exists()
    persisted = manager.metadata_index_path.read_text(encoding="utf-8")
    loaded = json.loads(persisted)
    assert isinstance(loaded, dict)
    assert refresh["entry"]["id"] in loaded


def test_corrupt_metadata_index_recovers_to_empty_and_continues(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    manager = IPFSDatasetsManager(enable=False)
    manager.metadata_index_path.parent.mkdir(parents=True, exist_ok=True)
    manager.metadata_index_path.write_text("{not-valid-json", encoding="utf-8")

    reloaded = IPFSDatasetsManager(enable=False)
    snapshot = reloaded.metadata_index_snapshot()
    assert snapshot["count"] == 0

    dataset = tmp_path / "after_corruption.jsonl"
    dataset.write_text('{"x":1}\n', encoding="utf-8")
    refresh = reloaded.refresh_metadata_index(path=dataset, operation="store")
    assert refresh["success"] is True
    assert reloaded.metadata_index_snapshot()["count"] == 1


def test_datasets_accelerate_enrichment_timeout_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    manager = IPFSDatasetsManager(enable=False)

    class FakeAccelerate:
        @staticmethod
        def discover_embedding_models():
            return ["ok"]

    manager._accelerate_module = FakeAccelerate()
    manager._accelerate_checked = True
    monkeypatch.setattr(manager, "_call_with_timeout", lambda func, *args: (True, None))

    result = manager.refresh_metadata_index(
        path=tmp_path / "timeout.csv",
        operation="write",
        metadata={"dataset_summary": "timeout path"},
    )

    assert result["success"] is True
    accelerate = result["entry"].get("accelerate_status")
    assert isinstance(accelerate, dict)
    assert accelerate.get("reason") == "accelerate_timeout"
