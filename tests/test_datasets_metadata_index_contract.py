#!/usr/bin/env python3
"""Focused metadata-index contract tests for ipfs_datasets integration in ipfs_kit submodule."""

import sys
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
