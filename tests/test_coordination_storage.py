from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    DurableCoordinationStore,
    RetentionPolicy,
    cid_for_artifact,
)
from ipfs_kit_py.mcp_server.mcplusplus.event_dag import EventDAGStore


REPO_ROOT = Path(__file__).resolve().parents[1]


def _profile_g_vectors_path() -> Path:
    """Resolve Profile G vectors without requiring a monorepo sibling checkout.

    Hermetic seal materialization unpacks this repository alone, so
    ``REPO_ROOT.parent.parent / "Mcp-Plus-Plus"`` is not available. Prefer an
    explicit override, then the vendored fixture, then the monorepo sibling path.
    """

    override = os.environ.get("MCP_PLUS_PLUS_PROFILE_G_VECTORS", "").strip()
    if override:
        return Path(override)
    vendored = (
        REPO_ROOT
        / "tests"
        / "fixtures"
        / "mcp_plus_plus"
        / "profile_g_artifacts_valid.json"
    )
    if vendored.is_file():
        return vendored
    return (
        REPO_ROOT.parent.parent
        / "Mcp-Plus-Plus"
        / "conformance"
        / "vectors"
        / "profile_g_artifacts_valid.json"
    )


PROFILE_G_VECTORS = _profile_g_vectors_path()


class MemoryHelia:
    def __init__(self) -> None:
        self.blocks: dict[str, bytes] = {}

    def put(self, data: bytes, *, cid: str, codec: str) -> dict[str, str]:
        assert codec == "dag-json"
        self.blocks[cid] = data
        return {"cid": cid}

    def get(self, cid: str) -> bytes:
        return self.blocks[cid]


@pytest.fixture()
def cases() -> dict[str, dict[str, Any]]:
    document = json.loads(PROFILE_G_VECTORS.read_text(encoding="utf-8"))
    return {case["kind"]: case for case in document["cases"]}


def test_all_profile_g_artifacts_persist_with_canonical_vector_cids(tmp_path: Path, cases: dict[str, Any]) -> None:
    helia = MemoryHelia()
    with DurableCoordinationStore(tmp_path / "store", backend=helia) as store:
        for kind, case in cases.items():
            result = store.put_profile_g(kind, case["payload"], expected_cid=case["expected_cid"])
            assert result["cid"] == case["expected_cid"]
            assert result["replicated"] is True
            assert store.get(result["cid"]) == case["payload"]
            assert helia.blocks[result["cid"]]

        assert store.status()["counts"]["artifacts"] == len(cases)
        assert store.status()["artifact_retention"] == "permanent"


def test_restart_and_index_recovery_from_immutable_blocks(tmp_path: Path, cases: dict[str, Any]) -> None:
    root = tmp_path / "store"
    claim_case = cases["TaskClaim"]
    claim_cid = cid_for_artifact(claim_case["payload"])
    resolution = dict(cases["ClaimResolution"]["payload"])
    resolution["considered_claim_cids"] = [claim_cid]
    resolution["accepted_claim_cid"] = claim_cid

    with DurableCoordinationStore(root) as store:
        store.put_profile_g("TaskClaim", claim_case["payload"])
        resolution_result = store.put_profile_g("ClaimResolution", resolution)
        lease = store.active_lease(claim_case["payload"]["task_cid"], at_ms=resolution["created_at_ms"])
        assert lease is not None
        assert lease["claim_cid"] == claim_cid
        assert lease["claimant_did"] == claim_case["payload"]["claimant_did"]

    (root / "coordination.sqlite3").unlink()
    for sidecar in root.glob("coordination.sqlite3-*"):
        sidecar.unlink()

    with DurableCoordinationStore(root) as recovered:
        report = recovered.recover(rebuild=True)
        assert report == {"verified_blocks": 2, "rebuilt": True, "errors": []}
        assert recovered.get(claim_cid) == claim_case["payload"]
        assert recovered.get(resolution_result["cid"]) == resolution
        assert recovered.claims(claim_case["payload"]["task_cid"])[0]["state"] == "accepted"
        assert recovered.active_lease(
            claim_case["payload"]["task_cid"], at_ms=resolution["created_at_ms"]
        )["resolution_cid"] == resolution_result["cid"]


def test_backend_retrieval_repairs_a_missing_local_block(tmp_path: Path, cases: dict[str, Any]) -> None:
    helia = MemoryHelia()
    with DurableCoordinationStore(tmp_path / "store", backend=helia) as store:
        result = store.put_profile_g("Goal", cases["Goal"]["payload"])
        store._block_path(result["cid"]).unlink()
        assert store.has(result["cid"]) is False
        assert store.get(result["cid"]) == cases["Goal"]["payload"]
        assert store.has(result["cid"]) is True


def test_claim_lease_and_health_indexes_apply_fencing_and_expiry(tmp_path: Path, cases: dict[str, Any]) -> None:
    now = cases["ClaimResolution"]["payload"]["created_at_ms"]
    root = tmp_path / "store"
    claim = cases["TaskClaim"]["payload"]
    claim_cid = cid_for_artifact(claim)
    resolution = dict(cases["ClaimResolution"]["payload"])
    resolution.update(considered_claim_cids=[claim_cid], accepted_claim_cid=claim_cid)

    health = {
        "peer_did": "did:web:worker-a.example",
        "status": "healthy",
        "observed_at_ms": now,
        "expires_at_ms": now + 10_000,
        "capacity_millionths": 750_000,
        "resource_classes": ["cpu-small"],
        "health_evidence_cid": cases["NeighborhoodRecord"]["payload"]["health_evidence_cid"],
        "signer_did": "did:web:worker-a.example",
        "signature_alg": "EdDSA",
        "signature": "test-signature",
    }
    with DurableCoordinationStore(root) as store:
        store.put_profile_g("TaskClaim", claim)
        resolution_result = store.put_profile_g("ClaimResolution", resolution)
        stale = dict(resolution)
        stale["created_at_ms"] += 1
        stale["lease_expires_at_ms"] += 1
        store.put_profile_g("ClaimResolution", stale)
        health_result = store.record_daemon_health(health)
        lease = store.active_lease(claim["task_cid"], at_ms=now)
        assert lease["fencing_token"] == resolution["fencing_token"]
        assert lease["resolution_cid"] == resolution_result["cid"]
        assert store.daemon_health("did:web:worker-a.example", at_ms=now)[0]["health_cid"] == health_result["cid"]
        assert store.active_lease(claim["task_cid"], at_ms=resolution["lease_expires_at_ms"]) is None
        assert store.daemon_health(at_ms=health["expires_at_ms"]) == []


def test_retention_archives_indexes_without_deleting_artifacts_or_profile_f_links(
    tmp_path: Path, cases: dict[str, Any]
) -> None:
    now = cases["ClaimResolution"]["payload"]["lease_expires_at_ms"] + 20_000
    policy = RetentionPolicy(terminal_claim_ms=0, expired_lease_ms=0, expired_health_ms=0)
    claim = cases["TaskClaim"]["payload"]
    claim_cid = cid_for_artifact(claim)
    resolution = dict(cases["ClaimResolution"]["payload"])
    resolution.update(considered_claim_cids=[claim_cid], accepted_claim_cid=claim_cid)

    with DurableCoordinationStore(tmp_path / "coord", retention=policy) as store:
        store.put_profile_g("TaskClaim", claim)
        resolution_result = store.put_profile_g("ClaimResolution", resolution)
        store.active_lease(claim["task_cid"], at_ms=now)  # materialize expiry
        report = store.compact_indexes(at_ms=now)
        assert report["compacted"] is True
        assert claim_cid in report["artifact_cids"]
        assert resolution_result["cid"] in report["artifact_cids"]
        assert store.claims(claim["task_cid"]) == []
        assert store.get(report["archive_cid"])["policy"]["artifact_blocks"] == "retain-forever"

        dag = EventDAGStore(str(tmp_path / "event-dag"), hot_event_max=1, epoch_size=1)
        dag.append({"event_cid": "event-1", "event_type": "task_claimed", "parents": [], "timestamp": "1", "payload": {"claim_cid": claim_cid}})
        dag.append({"event_cid": "event-2", "event_type": "task_expired", "parents": ["event-1"], "timestamp": "2", "payload": {"resolution_cid": resolution_result["cid"]}})
        assert dag.archives()["archives"]

        # Profile F compaction only changes traversal tiers. Every referenced
        # coordination artifact and the retention archive remain CID-readable.
        assert store.get(claim_cid) == claim
        assert store.get(resolution_result["cid"]) == resolution
        assert store.get(report["archive_cid"])["artifact_cids"] == sorted(
            [claim_cid, resolution_result["cid"]]
        )

    # Losing the acceleration database must respect archived tombstones when
    # it rebuilds from immutable blocks; compacted rows do not become hot again.
    database = tmp_path / "coord" / "coordination.sqlite3"
    database.unlink()
    for sidecar in database.parent.glob("coordination.sqlite3-*"):
        sidecar.unlink()
    with DurableCoordinationStore(tmp_path / "coord", retention=policy) as recovered:
        assert recovered.claims(claim["task_cid"]) == []
        assert recovered.status()["counts"]["index_archives"] == 1
        assert recovered.get(claim_cid) == claim


def test_expected_cid_and_recovery_fail_closed_on_corruption(tmp_path: Path, cases: dict[str, Any]) -> None:
    root = tmp_path / "store"
    with DurableCoordinationStore(root) as store:
        with pytest.raises(ArtifactIntegrityError, match="does not match expected"):
            store.put_profile_g("Goal", cases["Goal"]["payload"], expected_cid=cases["TaskSpec"]["expected_cid"])
        result = store.put_profile_g("Goal", cases["Goal"]["payload"])
        store._block_path(result["cid"]).write_bytes(b"{}")
        with pytest.raises(ArtifactIntegrityError, match="corrupt blocks"):
            store.recover()


def test_corrupt_derived_database_is_preserved_and_rebuilt(tmp_path: Path, cases: dict[str, Any]) -> None:
    root = tmp_path / "store"
    with DurableCoordinationStore(root) as store:
        result = store.put_profile_g("Goal", cases["Goal"]["payload"])

    database = root / "coordination.sqlite3"
    database.write_bytes(b"not a sqlite database")
    with DurableCoordinationStore(root) as recovered:
        assert recovered.get(result["cid"]) == cases["Goal"]["payload"]
        assert recovered.status()["counts"]["artifacts"] == 1
    assert len(list(root.glob("coordination.sqlite3.corrupt-*"))) == 1
