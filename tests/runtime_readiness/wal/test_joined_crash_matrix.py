"""Crash-boundary coverage for legacy adapters joined to the canonical WAL.

The matrix intentionally uses a process-like crash exception: no exception
handler in the transaction runner is allowed to turn that exception into a
normal abort.  A fresh coordinator must therefore decide from durable records
whether to replay a committed intent or compensate a pre-commit effect.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ipfs_kit_py.core.wal.coordinator import (
    WALTransactionCoordinator,
    WALTransactionCrash,
    WALTransactionError,
)
from ipfs_kit_py.filesystem_journal import FilesystemJournal
from ipfs_kit_py.storage_wal import StorageWriteAheadLog


_EXECUTE_BOUNDARIES = (
    "before_begin",
    "after_begin",
    "before_intent",
    "after_intent",
    "before_effect",
    "after_effect",
    "before_commit",
    "after_commit",
)


@pytest.mark.parametrize("boundary", _EXECUTE_BOUNDARIES)
def test_execute_crash_matrix_has_no_lost_or_duplicate_effects(
    tmp_path: Path, boundary: str
) -> None:
    """Every execute boundary converges to a committed or compensated state."""
    transaction_id = f"transaction-{boundary}"
    effect_id = f"effect-{boundary}"
    visible_effects: set[str] = set()

    def inject(name: str, received_transaction_id: str) -> None:
        if name == boundary:
            assert received_transaction_id == transaction_id
            raise WALTransactionCrash(name)

    coordinator = WALTransactionCoordinator(tmp_path, crash_injector=inject)
    try:
        with pytest.raises(WALTransactionCrash):
            coordinator.execute(
                {"object": "joined-adapter", "boundary": boundary},
                lambda: visible_effects.add(effect_id),
                lambda: visible_effects.discard(effect_id),
                transaction_id=transaction_id,
                effect_id=effect_id,
            )
    finally:
        coordinator.close()

    decisions = [
        json.loads(line)
        for line in (tmp_path / "transaction-decisions.jsonl").read_text().splitlines()
    ] if (tmp_path / "transaction-decisions.jsonl").exists() else []
    assert {entry["transaction_id"] for entry in decisions} <= {transaction_id}

    recovered = WALTransactionCoordinator(tmp_path)
    try:
        first = recovered.recover(
            replay_effect=lambda _intent, received_effect_id: visible_effects.add(
                received_effect_id
            ),
            rollback_effect=lambda _intent, received_effect_id: visible_effects.discard(
                received_effect_id
            ),
        )
        second = recovered.recover(
            replay_effect=lambda _intent, received_effect_id: visible_effects.add(
                received_effect_id
            ),
            rollback_effect=lambda _intent, received_effect_id: visible_effects.discard(
                received_effect_id
            ),
        )
    finally:
        recovered.close()

    # A durable commit is retained; every other interrupted execution is
    # compensated.  Idempotency ledger entries make a second replay a no-op.
    if boundary == "after_commit":
        assert visible_effects == {effect_id}
        assert first == {"replayed": 1, "rolled_back": 0}
    else:
        assert visible_effects == set()
        assert first["replayed"] == 0
    assert second == {"replayed": 0, "rolled_back": 0}


@pytest.mark.parametrize("boundary", ("before_abort", "after_abort"))
def test_abort_crash_matrix_performs_real_compensation(
    tmp_path: Path, boundary: str
) -> None:
    """Abort never writes its marker before undoing the performed effect."""
    transaction_id = f"abort-{boundary}"
    effect_id = f"effect-{boundary}"
    visible_effects: set[str] = set()

    def inject(name: str, _transaction_id: str) -> None:
        if name == boundary:
            raise WALTransactionCrash(name)

    coordinator = WALTransactionCoordinator(tmp_path, crash_injector=inject)
    try:
        transaction = coordinator.begin(transaction_id)
        coordinator.perform(
            transaction,
            {"object": "joined-adapter"},
            lambda: visible_effects.add(effect_id),
            lambda: visible_effects.discard(effect_id),
            effect_id=effect_id,
        )
        with pytest.raises(WALTransactionCrash):
            coordinator.abort(transaction)
    finally:
        coordinator.close()

    recovered = WALTransactionCoordinator(tmp_path)
    try:
        first = recovered.recover(
            rollback_effect=lambda _intent, received_effect_id: visible_effects.discard(
                received_effect_id
            )
        )
        second = recovered.recover(
            rollback_effect=lambda _intent, received_effect_id: visible_effects.discard(
                received_effect_id
            )
        )
    finally:
        recovered.close()

    assert visible_effects == set()
    assert first["replayed"] == 0
    assert second == {"replayed": 0, "rolled_back": 0}


def test_commit_failure_compensates_and_cannot_be_reported_as_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    coordinator = WALTransactionCoordinator(tmp_path)
    visible_effects: set[str] = set()
    original_marker = coordinator._marker

    def fail_commit(kind: object, transaction_id: str, *, effect_id: str = "") -> None:
        if getattr(kind, "value", kind) == "commit":
            raise WALTransactionError("injected durable commit failure")
        original_marker(kind, transaction_id, effect_id=effect_id)

    monkeypatch.setattr(coordinator, "_marker", fail_commit)
    try:
        with pytest.raises(WALTransactionError, match="commit failure"):
            coordinator.execute(
                {"object": "commit-failure"},
                lambda: visible_effects.add("effect"),
                lambda: visible_effects.discard("effect"),
                transaction_id="commit-failure",
                effect_id="effect",
            )
    finally:
        coordinator.close()

    assert visible_effects == set()


def test_filesystem_markers_use_one_transaction_id_and_abort_is_not_metadata_only(
    tmp_path: Path,
) -> None:
    journal = FilesystemJournal(
        base_path=str(tmp_path / "journal"), sync_interval=3600, auto_recovery=False
    )
    visible_effects: set[str] = set()
    try:
        transaction_id = journal.begin_transaction()
        journal.add_journal_entry("write", "/joined")
        visible_effects.add("write:/joined")
        journal.register_compensation(lambda: visible_effects.discard("write:/joined"))
        assert journal.rollback_transaction()
        markers = [
            entry for entry in journal.journal_entries
            if entry.get("metadata", {}).get("marker") in {"begin", "abort"}
        ]
    finally:
        journal.close()

    assert visible_effects == set()
    assert [marker["metadata"]["marker"] for marker in markers] == ["begin", "abort"]
    assert {marker["transaction_id"] for marker in markers} == {transaction_id}
    assert {marker["data"]["transaction_id"] for marker in markers} == {transaction_id}


def test_failed_storage_append_is_not_accepted_or_queued(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wal = StorageWriteAheadLog(base_path=str(tmp_path / "storage"))
    monkeypatch.setattr(wal, "_store_operation", lambda _operation: False)
    try:
        result = wal.add_operation("add", "ipfs", {"cid": "pending"})
        assert not result["success"]
        assert result["error_type"] == "wal_append_failed"
        assert wal._processing_queue.empty()
    finally:
        wal.close()
