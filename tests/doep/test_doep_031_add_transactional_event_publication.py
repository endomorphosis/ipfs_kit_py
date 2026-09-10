"""Independent current-tree checks for DOEP-031 event publication."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

IPFS_KIT_ROOT = Path(__file__).resolve().parents[2]
if str(IPFS_KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(IPFS_KIT_ROOT))

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (  # noqa: E402
    CANONICAL_EVENT_SCHEMA,
    EVENT_PUBLICATION_SCHEMA,
    DurableCoordinationStore,
)


OWNER_RELATIVE_OUTPUTS = (
    "ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py",
    "tests/doep/test_doep_031_add_transactional_event_publication.py",
    "artifacts/agent_supervisor_direct_objective_event_driven_planning/outputs/DOEP-031.json",
    "artifacts/agent_supervisor_direct_objective_event_driven_planning/receipts/DOEP-031.json",
)
OUTPUT_PATH = IPFS_KIT_ROOT / OWNER_RELATIVE_OUTPUTS[2]
RECEIPT_PATH = IPFS_KIT_ROOT / OWNER_RELATIVE_OUTPUTS[3]


def _event(**overrides: Any) -> dict[str, Any]:
    result = {
        "schema": CANONICAL_EVENT_SCHEMA,
        "event_id": "event:doep-031:1",
        "event_type": "task.validation.completed",
        "stream_id": "task:DOEP-031",
        "causal_parent_ids": ["event:doep-030:1"],
        "correlation_id": "correlation:DOEP-031",
        "causation_id": "causation:DOEP-030",
        "payload": {"outcome": "passed", "attempt": 1},
    }
    result.update(overrides)
    return result


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_declared_outputs_exist() -> None:
    assert all((IPFS_KIT_ROOT / path).is_file() for path in OWNER_RELATIVE_OUTPUTS)


def test_publish_is_locally_transactional_and_idempotent(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "coordination", clock_ms=lambda: 1_700_000_000_000) as store:
        published = store.publish_event(_event(), operation_id="event-publication:doep-031:1")
        assert published["status"] == "published"
        assert published["local_durable"] is True
        assert store.get(published["event_cid"]) == _event()
        publication = store.get(published["publication_cid"])
        assert publication["schema"] == EVENT_PUBLICATION_SCHEMA
        assert publication["event_cid"] == published["event_cid"]
        assert store.published_events() == [{
            "publication_cid": published["publication_cid"],
            "operation_id": "event-publication:doep-031:1",
            "event_cid": published["event_cid"],
            "event_id": "event:doep-031:1",
            "stream_id": "task:DOEP-031",
            "published_at_ms": 1_700_000_000_000,
        }]
        replay = store.publish_canonical_event(_event(), operation_id="event-publication:doep-031:1")
        assert replay["status"] == "unchanged"
        assert replay["publication_cid"] == published["publication_cid"]
        assert store.status()["counts"]["event_publications"] == 1


def test_rejected_reuse_does_not_add_a_second_publication(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "coordination") as store:
        first = store.publish_event(_event(), operation_id="event-publication:doep-031:1")
        operation_conflict = store.publish_event(
            _event(event_id="event:doep-031:2"), operation_id="event-publication:doep-031:1"
        )
        event_conflict = store.publish_event(
            _event(payload={"outcome": "failed"}), operation_id="event-publication:doep-031:2"
        )
        assert operation_conflict["reason_code"] == "operation_id_reused"
        assert event_conflict["reason_code"] == "event_id_reused"
        assert [row["publication_cid"] for row in store.published_events()] == [first["publication_cid"]]


def test_recovery_rebuilds_the_publication_index_from_immutable_evidence(tmp_path: Path) -> None:
    root = tmp_path / "coordination"
    with DurableCoordinationStore(root) as store:
        published = store.publish_event(_event(), operation_id="event-publication:doep-031:1")
    (root / "coordination.sqlite3").unlink()
    for sidecar in root.glob("coordination.sqlite3-*"):
        sidecar.unlink()
    with DurableCoordinationStore(root) as recovered:
        assert recovered.published_events()[0]["publication_cid"] == published["publication_cid"]
        assert recovered.get(published["event_cid"])["event_id"] == "event:doep-031:1"


def test_backend_observes_only_committed_publications(tmp_path: Path) -> None:
    class Backend:
        def __init__(self, database: Path) -> None:
            self.database = database
            self.calls: list[str] = []

        def store_block(self, cid: str, data: bytes, codec: str) -> None:
            assert codec == "dag-json"
            with sqlite3.connect(self.database) as connection:
                assert connection.execute("SELECT COUNT(*) FROM event_publications").fetchone()[0] == 1
            self.calls.append(cid)

        def load_block(self, cid: str) -> bytes:
            raise KeyError(cid)

    root = tmp_path / "coordination"
    backend = Backend(root / "coordination.sqlite3")
    with DurableCoordinationStore(root, backend=backend) as store:
        published = store.publish_event(_event(), operation_id="event-publication:doep-031:1")
        assert published["replicated"] is True
        assert backend.calls == [published["event_cid"], published["publication_cid"]]


def test_receipt_binds_exact_outputs_and_the_existing_authorities() -> None:
    manifest, receipt = _load(OUTPUT_PATH), _load(RECEIPT_PATH)
    assert manifest["task_id"] == receipt["task_id"] == "DOEP-031"
    assert manifest["declared_outputs"] == receipt["expected_outputs"] == list(OWNER_RELATIVE_OUTPUTS)
    assert manifest["canonical_event_schema"] == CANONICAL_EVENT_SCHEMA
    assert manifest["durable_storage"] == "DurableCoordinationStore"
    assert manifest["no_competing_subsystem_created"] is True
    assert receipt["no_competing_subsystem_created"] is True
    digests = {path: _sha256(IPFS_KIT_ROOT / path) for path in OWNER_RELATIVE_OUTPUTS[:-1]}
    assert receipt["path_digests"] == digests
    canonical = json.dumps(digests, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert receipt["required_evidence"]["changed_path_digest"] == "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
