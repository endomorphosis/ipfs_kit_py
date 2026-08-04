"""Regression coverage for the canonical VFS legacy compatibility bridge."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import anyio

from ipfs_kit_py.core.vfs.adapters import LegacyVFSAdapter
from ipfs_kit_py.mcp.ipfs_kit.vfs import VFSManager as MCPVFSManager
from ipfs_kit_py.vfs_manager import VFSManager as LegacyVFSManager


class RecordingJournal:
    """Journal double that makes obsolete API calls fail the test immediately."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []
        self.get_entries_limits: list[int] = []

    def record_operation(
        self,
        operation_type: str,
        path: str,
        details: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        self.entries.append(
            {
                "operation_type": operation_type,
                "path": path,
                "details": details or {},
                "metadata": metadata or {},
            }
        )
        return f"journal-{len(self.entries)}"

    def get_entries(self, *, limit: int = 100) -> list[dict[str, Any]]:
        self.get_entries_limits.append(limit)
        return self.entries[:limit]

    def log_operation(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        raise AssertionError("legacy log_operation must not be called")

    def get_recent_entries(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        raise AssertionError("legacy get_recent_entries must not be called")


class DatasetStore:
    def __init__(self) -> None:
        self.available = True
        self.result: dict[str, Any] = {"success": True, "cid": "bafy-test"}
        self.stored_payloads: list[list[dict[str, Any]]] = []

    def is_available(self) -> bool:
        return self.available

    def store(self, path: str | Path, metadata: dict[str, Any]) -> dict[str, Any]:
        del metadata
        contents = Path(path).read_text(encoding="utf-8")
        if contents.lstrip().startswith("["):
            self.stored_payloads.append(json.loads(contents))
        else:
            self.stored_payloads.append(
                [json.loads(line) for line in contents.splitlines() if line]
            )
        return dict(self.result)


class CentralVFS:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result

    async def execute_vfs_operation(self, operation: str, **kwargs: Any) -> dict[str, Any]:
        del operation, kwargs
        return dict(self.result)


def _legacy_manager(journal: RecordingJournal, dataset: DatasetStore) -> LegacyVFSManager:
    """Construct the narrow state needed to test publication ordering."""
    manager = object.__new__(LegacyVFSManager)
    manager.filesystem_journal = journal
    manager._legacy_vfs_adapter = LegacyVFSAdapter(journal=journal)
    manager.enable_dataset_storage = True
    manager.dataset_batch_size = 10
    manager.dataset_manager = dataset
    manager._operation_buffer = []
    manager._operation_buffer_lock = threading.Lock()
    return manager


def _mcp_manager(central: CentralVFS, dataset: DatasetStore) -> MCPVFSManager:
    manager = object.__new__(MCPVFSManager)
    manager.vfs_manager = central
    manager.enable_dataset_storage = True
    manager.dataset_batch_size = 10
    manager.dataset_manager = dataset
    manager._operation_buffer = []
    manager._buffer_lock = threading.Lock()
    return manager


def test_adapter_is_closed_and_does_not_promote_failed_canonical_operation() -> None:
    adapter = LegacyVFSAdapter()

    unsupported = anyio.run(lambda: adapter.execute("provider_only_operation", path="x"))
    assert unsupported["success"] is False
    assert unsupported["code"] == "unsupported_legacy_operation"

    missing = anyio.run(lambda: adapter.execute("rm", path="does-not-exist"))
    assert missing["success"] is False
    assert missing["result"]["success"] is False


def test_legacy_manager_publishes_journal_only_after_committed_mutation() -> None:
    journal = RecordingJournal()
    manager = _legacy_manager(journal, DatasetStore())

    failed = anyio.run(lambda: manager.delete_item("does-not-exist"))
    assert failed["success"] is False
    assert journal.entries == []
    assert manager._operation_buffer == []

    created = anyio.run(lambda: manager.create_folder("/", "docs"))
    assert created["success"] is True
    assert journal.entries[0]["operation_type"] == "mkdir"
    assert journal.entries[0]["path"] == "docs"

    entries = anyio.run(lambda: manager.get_vfs_journal(limit=7))
    assert entries == journal.entries
    assert journal.get_entries_limits == [7]


def test_legacy_dataset_flush_retains_buffer_until_store_commits() -> None:
    journal = RecordingJournal()
    dataset = DatasetStore()
    manager = _legacy_manager(journal, dataset)
    manager._track_vfs_operation("mkdir", "one")
    manager._track_vfs_operation("mkdir", "two")
    original_ids = {entry["operation_id"] for entry in manager._operation_buffer}

    dataset.available = False
    assert manager._flush_operation_buffer() is False
    assert {entry["operation_id"] for entry in manager._operation_buffer} == original_ids

    dataset.available = True
    dataset.result = {"success": False, "error": "dataset unavailable"}
    assert manager._flush_operation_buffer() is False
    assert {entry["operation_id"] for entry in manager._operation_buffer} == original_ids

    dataset.result = {"success": True, "cid": "bafy-committed"}
    assert manager._flush_operation_buffer() is True
    assert manager._operation_buffer == []
    assert len(dataset.stored_payloads) == 2


def test_mcp_rejects_underlying_failure_and_preserves_retryable_dataset_records() -> None:
    dataset = DatasetStore()
    central = CentralVFS({"success": False, "error": "mutation rejected"})
    manager = _mcp_manager(central, dataset)

    failed = anyio.run(lambda: manager.execute_vfs_operation("mkdir", path="docs"))
    assert failed["success"] is False
    assert manager._operation_buffer == []

    central.result = {
        "success": True,
        "result": {"success": False, "error": "inner mutation rejected"},
    }
    contradictory = anyio.run(lambda: manager.execute_vfs_operation("mkdir", path="docs"))
    assert contradictory["success"] is False
    assert manager._operation_buffer == []

    central.result = {"success": True, "result": {"success": True}}
    committed = anyio.run(lambda: manager.execute_vfs_operation("mkdir", path="docs"))
    assert committed["success"] is True
    manager._store_operation_to_dataset({"operation": "mkdir", "path": "other"})
    buffered_ids = {
        entry["dataset_operation_id"] for entry in manager._operation_buffer
    }
    assert len(buffered_ids) == 2

    dataset.available = False
    assert manager.flush_to_dataset() is False
    assert {
        entry["dataset_operation_id"] for entry in manager._operation_buffer
    } == buffered_ids

    dataset.available = True
    dataset.result = {"success": False, "error": "write rejected"}
    assert manager.flush_to_dataset() is False
    assert {
        entry["dataset_operation_id"] for entry in manager._operation_buffer
    } == buffered_ids

    dataset.result = {"success": True, "cid": "bafy-committed"}
    assert manager.flush_to_dataset() is True
    assert manager._operation_buffer == []
