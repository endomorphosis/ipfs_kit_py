#!/usr/bin/env python3
"""Focused metadata-index contract tests for ipfs_datasets integration in ipfs_kit submodule."""

import sys
import json
import os
import multiprocessing
import time
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from ipfs_kit_py.ipfs_datasets_integration import IPFSDatasetsManager


def _concurrent_index_writer(home_dir: str, dataset_path: str, idx: int) -> None:
    os.environ["HOME"] = home_dir
    manager = IPFSDatasetsManager(enable=False)
    manager.refresh_metadata_index(
        path=dataset_path,
        operation="write",
        metadata={"worker": idx},
    )


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

    operation_id = "op-lineage-123"
    manager = IPFSDatasetsManager(enable=False)
    result = manager.record_ipfs_operation(
        {
            "operation": "write",
            "path": str(dataset),
            "dataset_summary": "updated from vfs",
            "operation_id": operation_id,
            "source_operation_id": "op-parent-42",
            "source_cid": "cidv1-source-abc",
        }
    )
    assert result["success"] is True

    listed = manager.list()
    assert listed["count"] >= 1
    entry = next(item for item in listed["items"] if item["path"] == str(dataset))
    assert entry["operation"] == "write"
    assert entry["operation_id"] == operation_id
    assert entry["source_operation_id"] == "op-parent-42"
    assert entry["source_cid"] == "cidv1-source-abc"
    assert entry["lineage"]["operation_id"] == operation_id
    assert entry["lineage"]["source_cid"] == "cidv1-source-abc"
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


def test_datasets_accelerate_embedding_cache_reuses_vectors(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    call_counter = {"create_embedding": 0}

    class FakeAccelerate:
        @staticmethod
        def discover_embedding_models():
            return ["mini-embed"]

        @staticmethod
        def create_embedding(text):
            call_counter["create_embedding"] += 1
            return [0.1, 0.2, 0.3]

    manager = IPFSDatasetsManager(enable=False)
    manager._accelerate_module = FakeAccelerate()
    manager._accelerate_checked = True

    dataset = tmp_path / "cache.csv"
    dataset.write_text("x,y\n1,2\n", encoding="utf-8")

    first = manager.refresh_metadata_index(
        path=dataset,
        operation="write",
        metadata={"dataset_summary": "same-summary"},
    )
    second = manager.refresh_metadata_index(
        path=dataset,
        operation="write",
        metadata={"dataset_summary": "same-summary"},
    )

    assert first["success"] is True
    assert second["success"] is True
    assert call_counter["create_embedding"] == 1
    assert manager.metadata_index_snapshot()["metrics"]["accelerate_cache_hits"] >= 1


def test_metadata_index_concurrent_process_writes_preserve_all_entries(tmp_path, monkeypatch):
    home_dir = str(tmp_path / "home")
    monkeypatch.setenv("HOME", home_dir)

    worker_count = 6
    dataset_paths = []
    for idx in range(worker_count):
        dataset = tmp_path / f"concurrent_{idx}.jsonl"
        dataset.write_text('{"id": %d}\n' % idx, encoding="utf-8")
        dataset_paths.append(str(dataset))

    processes = []
    for idx, dataset_path in enumerate(dataset_paths):
        proc = multiprocessing.Process(
            target=_concurrent_index_writer,
            args=(home_dir, dataset_path, idx),
        )
        proc.start()
        processes.append(proc)

    for proc in processes:
        proc.join(timeout=15)
        assert proc.exitcode == 0

    manager = IPFSDatasetsManager(enable=False)
    listed = manager.list_metadata_index()
    assert listed["success"] is True

    recorded_paths = {item.get("path") for item in listed["items"]}
    for dataset_path in dataset_paths:
        assert dataset_path in recorded_paths


def test_remove_from_metadata_index_returns_removed_lineage(tmp_path):
    dataset = tmp_path / "lineage_remove.csv"
    dataset.write_text("a,b\n1,2\n", encoding="utf-8")

    manager = IPFSDatasetsManager(enable=False)
    refresh = manager.refresh_metadata_index(
        path=dataset,
        operation="write",
        metadata={"operation_id": "op-remove-55"},
    )
    assert refresh["success"] is True

    removed = manager.remove(str(dataset))
    assert removed["success"] is True
    assert removed["removed"] is True
    assert removed["removed_operation_id"] == "op-remove-55"
    assert isinstance(removed.get("removed_entry"), dict)
    assert removed["removed_entry"].get("operation_id") == "op-remove-55"


def test_datasets_timeout_helper_returns_within_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    manager = IPFSDatasetsManager(enable=False)

    original_timeout = manager._accelerate_timeout_sec
    manager._accelerate_timeout_sec = 0.05

    try:
        start = time.perf_counter()
        timed_out, value = manager._call_with_timeout(lambda: (time.sleep(0.25), "done")[1])
        elapsed = time.perf_counter() - start

        assert timed_out is True
        assert value is None
        assert elapsed < 0.20
    finally:
        manager._accelerate_timeout_sec = original_timeout
