"""Fail-closed vectors for immutable governor artifact storage (SCG-019)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
    cid_for_bytes,
)
from ipfs_kit_py.semantic_governor_store.artifacts import (
    ARTIFACT_MODULE_INTERFACE,
    ARTIFACT_SCHEMA_VERSION,
    GOVERNOR_STORED_ARTIFACT_INTERFACE,
    GOVERNOR_STORED_ARTIFACT_SCHEMA,
    MAX_ARTIFACT_BYTES,
    DurableSemanticGovernorStore,
    GovernorArtifactAdmissionError,
    GovernorArtifactConflictError,
    GovernorArtifactIntegrityError,
    GovernorArtifactNotFound,
    admit_sealed_record,
    cid_for_governor_artifact,
    reject_private_raw_source,
    seal_governor_artifact,
    validate_stored_artifact_schema,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    GovernorArtifactKind,
    GovernorProviderStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class MemoryHelia:
    def __init__(self) -> None:
        self.blocks: dict[str, bytes] = {}

    def put(self, data: bytes, *, cid: str, codec: str) -> dict[str, str]:
        assert codec == "dag-json"
        self.blocks[cid] = data
        return {"cid": cid}

    def get(self, cid: str) -> bytes:
        return self.blocks[cid]


def _payload(**extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "case_id": "audit-case-1",
        "summary": "bounded coverage audit",
        "status": "complete",
    }
    body.update(extra)
    return body


@pytest.fixture()
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "governor-store"


@pytest.fixture()
def coordination(store_dir: Path) -> DurableCoordinationStore:
    root = DurableCoordinationStore(store_dir)
    yield root
    root.close()


@pytest.fixture()
def governor(coordination: DurableCoordinationStore) -> DurableSemanticGovernorStore:
    store = DurableSemanticGovernorStore(coordination)
    yield store
    store.close()


# ---------------------------------------------------------------------------
# Envelope helpers and closed constants
# ---------------------------------------------------------------------------


def test_module_interface_and_schema_are_versioned() -> None:
    assert ARTIFACT_MODULE_INTERFACE == "DurableSemanticGovernorStore@1"
    assert GOVERNOR_STORED_ARTIFACT_INTERFACE == "GovernorStoredArtifact@1"
    assert GOVERNOR_STORED_ARTIFACT_SCHEMA.endswith(f"@{ARTIFACT_SCHEMA_VERSION}")
    assert MAX_ARTIFACT_BYTES == 1_048_576


def test_seal_and_cid_are_deterministic() -> None:
    payload = _payload()
    sealed_a = seal_governor_artifact(GovernorArtifactKind.AUDIT, payload)
    sealed_b = seal_governor_artifact("audit", dict(payload))
    assert sealed_a == sealed_b
    assert sealed_a["schema"] == GOVERNOR_STORED_ARTIFACT_SCHEMA
    assert sealed_a["kind"] == "audit"
    assert sealed_a["payload"] == payload
    cid = cid_for_governor_artifact(GovernorArtifactKind.AUDIT, payload)
    assert cid == cid_for_artifact(sealed_a)
    assert cid == cid_for_governor_artifact(GovernorArtifactKind.AUDIT, payload)


def test_validate_stored_artifact_schema_rejects_unknown_version() -> None:
    validate_stored_artifact_schema(GOVERNOR_STORED_ARTIFACT_SCHEMA)
    with pytest.raises(GovernorArtifactAdmissionError, match="unknown artifact schema version"):
        validate_stored_artifact_schema(
            "ipfs-kit.semantic-governor-store.artifact@2"
        )
    with pytest.raises(GovernorArtifactAdmissionError, match="unknown artifact schema"):
        validate_stored_artifact_schema(
            "ipfs-kit.semantic-governor-store.other@1"
        )
    with pytest.raises(GovernorArtifactAdmissionError, match="version suffix"):
        validate_stored_artifact_schema("no-version-here")


# ---------------------------------------------------------------------------
# Happy path: put + get across closed kinds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    [
        GovernorArtifactKind.AUDIT,
        GovernorArtifactKind.CALIBRATION,
        GovernorArtifactKind.BENCHMARK,
        GovernorArtifactKind.POLICY,
        GovernorArtifactKind.POLICY_CANDIDATE,
        GovernorArtifactKind.EVALUATION,
        GovernorArtifactKind.PROMOTION,
        GovernorArtifactKind.RUN_RECEIPT,
        GovernorArtifactKind.PROMOTION_RECEIPT,
        GovernorArtifactKind.HISTORY_MANIFEST,
    ],
)
def test_put_and_get_verified_artifact_round_trip(
    governor: DurableSemanticGovernorStore, kind: GovernorArtifactKind
) -> None:
    payload = _payload(kind_tag=kind.value)
    expected = cid_for_governor_artifact(kind, payload)
    result = governor.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id=f"op-{kind.value}-1",
        replicate=False,
    )
    assert result.cid == expected
    assert result.kind is kind
    assert result.local_durable is True
    assert result.provider_status is GovernorProviderStatus.NOT_REQUESTED
    assert result.replicated is False
    assert result.reason_code in {"stored", "not_requested"}

    verified = governor.get_verified_artifact(expected, expected_kind=kind)
    assert verified["schema"] == GOVERNOR_STORED_ARTIFACT_SCHEMA
    assert verified["kind"] == kind.value
    assert dict(verified["payload"]) == payload


def test_replication_when_backend_available(store_dir: Path) -> None:
    helia = MemoryHelia()
    with DurableCoordinationStore(store_dir, backend=helia) as coordination:
        with DurableSemanticGovernorStore(coordination) as governor:
            payload = _payload()
            kind = GovernorArtifactKind.BENCHMARK
            expected = cid_for_governor_artifact(kind, payload)
            result = governor.put_artifact(
                kind,
                payload,
                expected_cid=expected,
                operation_id="op-replicate-1",
                replicate=True,
            )
            assert result.replicated is True
            assert result.provider_status is GovernorProviderStatus.AVAILABLE
            assert result.reason_code == "replicated"
            assert expected in helia.blocks


def test_provider_unavailable_when_no_backend(
    governor: DurableSemanticGovernorStore,
) -> None:
    payload = _payload()
    kind = GovernorArtifactKind.POLICY
    expected = cid_for_governor_artifact(kind, payload)
    result = governor.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id="op-no-backend",
        replicate=True,
    )
    assert result.local_durable is True
    assert result.replicated is False
    assert result.provider_status is GovernorProviderStatus.UNAVAILABLE
    assert result.reason_code == "provider_unavailable"


def test_restart_reads_immutable_block_from_coordination_store(
    store_dir: Path,
) -> None:
    payload = _payload(note="durable across reopen")
    kind = GovernorArtifactKind.AUDIT
    expected = cid_for_governor_artifact(kind, payload)
    with DurableCoordinationStore(store_dir) as coordination:
        with DurableSemanticGovernorStore(coordination) as governor:
            governor.put_artifact(
                kind,
                payload,
                expected_cid=expected,
                operation_id="op-reopen-1",
                replicate=False,
            )
    with DurableCoordinationStore(store_dir) as coordination:
        with DurableSemanticGovernorStore(coordination) as governor:
            verified = governor.get_verified_artifact(
                expected, expected_kind=kind
            )
            assert dict(verified["payload"]) == payload


# ---------------------------------------------------------------------------
# Fail-closed: forged, wrong-kind, oversized, private-raw-source, unknown-version, corrupt
# ---------------------------------------------------------------------------


def test_forged_expected_cid_fails_closed(
    governor: DurableSemanticGovernorStore,
) -> None:
    payload = _payload()
    kind = GovernorArtifactKind.AUDIT
    real = cid_for_governor_artifact(kind, payload)
    forged = cid_for_bytes(b"not-the-artifact")
    assert forged != real
    with pytest.raises(GovernorArtifactIntegrityError, match="forged|mismatched"):
        governor.put_artifact(
            kind,
            payload,
            expected_cid=forged,
            operation_id="op-forged",
            replicate=False,
        )
    # Nothing durable was written under the forged identity.
    with pytest.raises(GovernorArtifactNotFound):
        governor.get_verified_artifact(forged)


def test_wrong_kind_on_put_fails_closed(
    governor: DurableSemanticGovernorStore,
) -> None:
    payload = _payload()
    with pytest.raises(GovernorArtifactAdmissionError, match="unknown governor artifact kind"):
        governor.put_artifact(
            "model_reasoning",  # type: ignore[arg-type]
            payload,
            expected_cid=cid_for_bytes(b"unused"),
            operation_id="op-wrong-kind",
            replicate=False,
        )


def test_wrong_kind_on_get_fails_closed(
    governor: DurableSemanticGovernorStore,
) -> None:
    payload = _payload()
    kind = GovernorArtifactKind.CALIBRATION
    expected = cid_for_governor_artifact(kind, payload)
    governor.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id="op-kind-get",
        replicate=False,
    )
    with pytest.raises(GovernorArtifactIntegrityError, match="wrong artifact kind"):
        governor.get_verified_artifact(
            expected, expected_kind=GovernorArtifactKind.POLICY
        )


def test_oversized_artifact_fails_closed(
    governor: DurableSemanticGovernorStore,
) -> None:
    # Build a payload that pushes the sealed envelope past the byte ceiling.
    huge = "x" * (MAX_ARTIFACT_BYTES + 64)
    payload = _payload(blob=huge)
    with pytest.raises(GovernorArtifactAdmissionError, match="MAX_ARTIFACT_BYTES"):
        seal_governor_artifact(GovernorArtifactKind.AUDIT, payload)
    with pytest.raises(GovernorArtifactAdmissionError, match="MAX_ARTIFACT_BYTES"):
        governor.put_artifact(
            GovernorArtifactKind.AUDIT,
            payload,
            expected_cid=cid_for_bytes(b"unused"),
            operation_id="op-oversize",
            replicate=False,
        )


@pytest.mark.parametrize(
    "private_key",
    [
        "raw_private_source",
        "private_source",
        "raw_source",
        "source_text",
        "source_bytes",
        "secret",
        "api_key",
        "nested_raw_private_source_field",
    ],
)
def test_private_raw_source_fails_closed(
    governor: DurableSemanticGovernorStore, private_key: str
) -> None:
    payload = _payload(**{private_key: "CLASSIFIED"})
    with pytest.raises(GovernorArtifactAdmissionError, match="private"):
        reject_private_raw_source(payload)
    with pytest.raises(GovernorArtifactAdmissionError, match="private"):
        governor.put_artifact(
            GovernorArtifactKind.AUDIT,
            payload,
            expected_cid=cid_for_bytes(b"unused"),
            operation_id=f"op-private-{private_key}",
            replicate=False,
        )


def test_nested_private_raw_source_fails_closed(
    governor: DurableSemanticGovernorStore,
) -> None:
    payload = _payload(meta={"raw_private_source": "leak"})
    with pytest.raises(GovernorArtifactAdmissionError, match="private"):
        governor.put_artifact(
            GovernorArtifactKind.EVALUATION,
            payload,
            expected_cid=cid_for_bytes(b"unused"),
            operation_id="op-nested-private",
            replicate=False,
        )


def test_unknown_version_sealed_record_fails_on_get(
    coordination: DurableCoordinationStore,
    governor: DurableSemanticGovernorStore,
) -> None:
    # Plant a block with an unknown envelope version directly in the backend store.
    foreign = {
        "schema": "ipfs-kit.semantic-governor-store.artifact@99",
        "interface_id": GOVERNOR_STORED_ARTIFACT_INTERFACE,
        "kind": "audit",
        "payload": _payload(),
    }
    cid = cid_for_artifact(foreign)
    coordination.put(foreign, expected_cid=cid, replicate=False)
    with pytest.raises(
        GovernorArtifactIntegrityError, match="unknown artifact schema version"
    ):
        governor.get_verified_artifact(cid)


def test_unknown_version_on_admit_helper() -> None:
    record = {
        "schema": "ipfs-kit.semantic-governor-store.artifact@0",
        "interface_id": GOVERNOR_STORED_ARTIFACT_INTERFACE,
        "kind": "audit",
        "payload": {},
    }
    with pytest.raises(GovernorArtifactIntegrityError, match="unknown artifact schema version"):
        admit_sealed_record(record)


def test_corrupt_block_fails_closed(
    store_dir: Path, governor: DurableSemanticGovernorStore
) -> None:
    payload = _payload()
    kind = GovernorArtifactKind.AUDIT
    expected = cid_for_governor_artifact(kind, payload)
    governor.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id="op-corrupt",
        replicate=False,
    )
    path = governor.store._block_path(expected)
    # Tamper durable bytes after a successful write.
    path.write_bytes(b'{"schema":"tampered","kind":"audit","payload":{}}')
    with pytest.raises(GovernorArtifactIntegrityError):
        governor.get_verified_artifact(expected)


def test_non_dag_json_types_fail_closed(
    governor: DurableSemanticGovernorStore,
) -> None:
    with pytest.raises(GovernorArtifactAdmissionError, match="DAG-JSON"):
        governor.put_artifact(
            GovernorArtifactKind.AUDIT,
            {"ratio": 1.5},  # floats are forbidden
            expected_cid=cid_for_bytes(b"unused"),
            operation_id="op-float",
            replicate=False,
        )


def test_missing_cid_fails_closed(governor: DurableSemanticGovernorStore) -> None:
    missing = cid_for_bytes(b"absent-governor-artifact")
    with pytest.raises(GovernorArtifactNotFound):
        governor.get_verified_artifact(missing)


# ---------------------------------------------------------------------------
# Operation-id idempotency and conflict
# ---------------------------------------------------------------------------


def test_operation_id_is_idempotent(
    governor: DurableSemanticGovernorStore,
) -> None:
    payload = _payload()
    kind = GovernorArtifactKind.AUDIT
    expected = cid_for_governor_artifact(kind, payload)
    first = governor.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id="op-idempotent",
        replicate=False,
    )
    second = governor.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id="op-idempotent",
        replicate=False,
    )
    assert first.cid == second.cid == expected
    assert second.reason_code == "unchanged"
    assert second.local_durable is True


def test_operation_id_conflict_on_different_cid(
    governor: DurableSemanticGovernorStore,
) -> None:
    kind = GovernorArtifactKind.AUDIT
    first_payload = _payload(case_id="a")
    second_payload = _payload(case_id="b")
    first_cid = cid_for_governor_artifact(kind, first_payload)
    second_cid = cid_for_governor_artifact(kind, second_payload)
    assert first_cid != second_cid
    governor.put_artifact(
        kind,
        first_payload,
        expected_cid=first_cid,
        operation_id="op-conflict",
        replicate=False,
    )
    with pytest.raises(GovernorArtifactConflictError, match="operation_id"):
        governor.put_artifact(
            kind,
            second_payload,
            expected_cid=second_cid,
            operation_id="op-conflict",
            replicate=False,
        )


def test_invalid_operation_id_fails_closed(
    governor: DurableSemanticGovernorStore,
) -> None:
    payload = _payload()
    kind = GovernorArtifactKind.AUDIT
    expected = cid_for_governor_artifact(kind, payload)
    with pytest.raises(GovernorArtifactAdmissionError):
        governor.put_artifact(
            kind,
            payload,
            expected_cid=expected,
            operation_id="BAD ID",
            replicate=False,
        )


# ---------------------------------------------------------------------------
# Composition / non-goals
# ---------------------------------------------------------------------------


def test_requires_durable_coordination_store() -> None:
    with pytest.raises(TypeError, match="DurableCoordinationStore"):
        DurableSemanticGovernorStore(object())  # type: ignore[arg-type]


def test_get_returns_read_only_mapping(
    governor: DurableSemanticGovernorStore,
) -> None:
    payload = _payload()
    kind = GovernorArtifactKind.HISTORY_MANIFEST
    expected = cid_for_governor_artifact(kind, payload)
    governor.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id="op-ro",
        replicate=False,
    )
    verified = governor.get_verified_artifact(expected)
    assert isinstance(verified, Mapping)
    with pytest.raises(TypeError):
        verified["kind"] = "policy"  # type: ignore[index]


def test_direct_store_block_without_governor_schema_is_not_admitted(
    coordination: DurableCoordinationStore,
    governor: DurableSemanticGovernorStore,
) -> None:
    foreign = {"schema": "mcp++/profile-g/goal@1", "goal_id": "g1"}
    # Profile G schema may or may not be fully valid for coordination indexing;
    # store a generic sealed object with a foreign schema string instead.
    foreign = {
        "schema": "example.foreign-artifact@1",
        "kind": "audit",
        "payload": {"ok": True},
        "interface_id": GOVERNOR_STORED_ARTIFACT_INTERFACE,
    }
    cid = cid_for_artifact(foreign)
    coordination.put(foreign, expected_cid=cid, replicate=False)
    with pytest.raises(GovernorArtifactIntegrityError):
        governor.get_verified_artifact(cid)
