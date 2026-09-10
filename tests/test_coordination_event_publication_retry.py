"""Durable publication evidence survives a failed SQLite publication epoch."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    CANONICAL_EVENT_SCHEMA,
    EVENT_PUBLICATION_SCHEMA,
    ArtifactIntegrityError,
    DurableCoordinationStore,
    cid_for_artifact,
)


def _event(**changes):
    event = {
        "schema": CANONICAL_EVENT_SCHEMA,
        "event_id": "event:retry:1",
        "event_type": "task.validation.completed",
        "stream_id": "task:retry",
        "causal_parent_ids": [],
        "correlation_id": "correlation:retry",
        "causation_id": "causation:retry",
        "payload": {"outcome": "passed"},
    }
    return {**event, **changes}


@pytest.mark.parametrize("already_open_peer", [False, True])
@pytest.mark.parametrize("retry_kind", ["same", "operation_reused", "event_reused"])
def test_retry_reconciles_durable_unindexed_publication(
    tmp_path: Path, monkeypatch, already_open_peer, retry_kind
):
    root = tmp_path / "store"
    clock = {"ms": 1000}
    with DurableCoordinationStore(root, clock_ms=lambda: clock["ms"]) as first:
        # An already-open peer cannot rely on constructor recovery or a local
        # flag to discover another connection's interrupted publication.
        with DurableCoordinationStore(root, clock_ms=lambda: clock["ms"]) as peer:
            native_write = first._write_block
            durable = {}

            def interrupted_write(cid, data):
                native_write(cid, data)
                if json.loads(data)["schema"] == EVENT_PUBLICATION_SCHEMA:
                    durable.update(cid=cid, data=data)
                    raise OSError("publication durable, index not committed")

            monkeypatch.setattr(first, "_write_block", interrupted_write)
            with pytest.raises(OSError, match="publication durable"):
                first.publish_event(_event(), operation_id="publish:1")
            monkeypatch.setattr(first, "_write_block", native_write)
            assert first.published_events() == []
            before = dict(first._iter_local_blocks())
            clock["ms"] = 2000
            retry = peer if already_open_peer else first
            if retry_kind == "same":
                event, operation = _event(), "publish:1"
                status, reason = "unchanged", "idempotent_replay"
            elif retry_kind == "operation_reused":
                event, operation = _event(event_id="event:retry:2"), "publish:1"
                status, reason = "conflict", "operation_id_reused"
            else:
                event, operation = _event(payload={"outcome": "failed"}), "publish:2"
                status, reason = "conflict", "event_id_reused"
            result = retry.publish_event(event, operation_id=operation)
            assert (result["status"], result["reason_code"]) == (status, reason)
            assert result["publication_cid"] == durable["cid"]
            assert result["local_durable"] is True and result["replicated"] is False
            assert dict(first._iter_local_blocks()) == before
            [row] = retry.published_events()
            assert row["publication_cid"] == durable["cid"]
            assert row["published_at_ms"] == 1000
            assert retry.get(row["publication_cid"]) == json.loads(durable["data"])
    with DurableCoordinationStore(root) as reopened:
        assert reopened.published_events() == [row]
        assert dict(reopened._iter_local_blocks()) == before


def test_conflicting_immutable_publications_are_not_repaired_or_extended(tmp_path: Path):
    with DurableCoordinationStore(tmp_path / "store", clock_ms=lambda: 1000) as store:
        first = store.publish_event(_event(), operation_id="publish:1")
        duplicate = {**store.get(first["publication_cid"]), "published_at_ms": 2000}
        cid = cid_for_artifact(duplicate)
        data = json.dumps(duplicate, sort_keys=True, separators=(",", ":")).encode()
        store._write_block(cid, data)
        before = dict(store._iter_local_blocks())
        rows = store.published_events()
        with pytest.raises(ArtifactIntegrityError, match="duplicate event publication"):
            store.publish_event(_event(event_id="event:retry:3"), operation_id="publish:3")
        assert dict(store._iter_local_blocks()) == before
        assert store.published_events() == rows


def test_healthy_publication_does_not_rewrite_existing_indexes(tmp_path: Path):
    with DurableCoordinationStore(tmp_path / "store") as store:
        store.publish_event(_event(), operation_id="publish:1")
        statements = []
        store._connection.set_trace_callback(statements.append)
        store.publish_event(_event(), operation_id="publish:1")
        mutations = [sql for sql in statements if sql.split()[0].upper() in {"INSERT", "DELETE", "UPDATE"}]
        assert mutations == []
