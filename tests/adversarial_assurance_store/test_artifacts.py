"""Fail-closed vectors for immutable assurance artifact storage (AAE-034)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# Prefer this worktree's kit package when an outer PYTHONPATH pin is present.
_KIT_ROOT = Path(__file__).resolve().parents[2]
_KIT_PKG = _KIT_ROOT / "ipfs_kit_py"
if sys.path[:1] != [str(_KIT_ROOT)]:
    sys.path.insert(0, str(_KIT_ROOT))
import ipfs_kit_py as _ipfs_kit_py  # noqa: E402

if str(_KIT_PKG) not in list(_ipfs_kit_py.__path__):
    _ipfs_kit_py.__path__.insert(0, str(_KIT_PKG))

from ipfs_datasets_py.logic.software_contracts.adversarial_assurance import (
    AssuranceTerminalStatus,
    HeldOutResult,
    SignatureVerificationStatus,
)
from ipfs_datasets_py.tests.unit.logic.software_contracts.adversarial_assurance import (
    test_mutation_contracts as mutation_fixtures,
    test_receipt_contracts as receipt_fixtures,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
    cid_for_bytes,
)
from ipfs_kit_py.adversarial_assurance_store.artifacts import (
    ARTIFACT_MODULE_INTERFACE,
    MAX_ARTIFACT_BYTES,
    AssuranceArtifactAdmissionError,
    AssuranceArtifactConflictError,
    AssuranceArtifactIntegrityError,
    AssuranceArtifactNotFound,
    DurableAssuranceArtifactStore,
    admit_stored_record,
    cid_for_assurance_artifact,
    seal_assurance_artifact,
)
from ipfs_kit_py.adversarial_assurance_store.contracts import (
    AssuranceArtifactKind,
    AssuranceProviderStatus,
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


def _candidate_payload(**extra: Any) -> dict[str, Any]:
    body = mutation_fixtures._candidate().to_dict()
    if extra:
        # Only allow additive metadata keys that remain valid DAG-JSON.
        metadata = dict(body.get("metadata") or {})
        metadata.update(extra)
        body = mutation_fixtures._candidate(metadata=metadata).to_dict()
    return body


def _operator_payload(**extra: Any) -> dict[str, Any]:
    if extra:
        return mutation_fixtures._operator(metadata=extra).to_dict()
    return mutation_fixtures._operator().to_dict()


def _campaign_payload() -> dict[str, Any]:
    return receipt_fixtures._campaign().to_dict()


def _unverified_campaign_payload() -> dict[str, Any]:
    return receipt_fixtures._campaign(
        header=receipt_fixtures._header(
            "assurance_campaign_receipt",
            terminal_status=AssuranceTerminalStatus.REJECTED,
        ),
        held_out_result=HeldOutResult.FAILED,
        signature=receipt_fixtures._signature(
            signature_verification_status=SignatureVerificationStatus.UNVERIFIED
        ),
    ).to_dict()


@pytest.fixture()
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "assurance-store"


@pytest.fixture()
def coordination(store_dir: Path) -> DurableCoordinationStore:
    root = DurableCoordinationStore(store_dir)
    yield root
    root.close()


@pytest.fixture()
def assurance(
    coordination: DurableCoordinationStore,
) -> DurableAssuranceArtifactStore:
    store = DurableAssuranceArtifactStore(coordination)
    yield store
    store.close()


# ---------------------------------------------------------------------------
# Envelope helpers and closed constants
# ---------------------------------------------------------------------------


def test_module_interface_and_size_bound() -> None:
    assert ARTIFACT_MODULE_INTERFACE == "DurableAssuranceArtifactStore@1"
    assert MAX_ARTIFACT_BYTES == 1_048_576


def test_seal_and_cid_are_deterministic() -> None:
    payload = _candidate_payload()
    kind = AssuranceArtifactKind.MUTATION_CANDIDATE
    sealed_a = seal_assurance_artifact(kind, payload)
    sealed_b = seal_assurance_artifact("mutation_candidate", dict(payload))
    assert sealed_a == sealed_b
    assert sealed_a["schema"] == payload["schema"]
    assert sealed_a["header"]["artifact_kind"] == "mutation_candidate"
    cid = cid_for_assurance_artifact(kind, payload)
    assert cid == cid_for_artifact(sealed_a)
    assert cid == cid_for_assurance_artifact(kind, payload)


# ---------------------------------------------------------------------------
# Happy path: put + get
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind,payload_factory",
    [
        (AssuranceArtifactKind.MUTATION_CANDIDATE, _candidate_payload),
        (AssuranceArtifactKind.MUTATION_OPERATOR_DEFINITION, _operator_payload),
        (AssuranceArtifactKind.MUTATION_TARGET, lambda: mutation_fixtures._target().to_dict()),
        (AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT, _campaign_payload),
        (
            AssuranceArtifactKind.ASSURANCE_POLICY_PROMOTION_RECEIPT,
            lambda: receipt_fixtures._promotion().to_dict(),
        ),
    ],
)
def test_put_and_get_verified_artifact_round_trip(
    assurance: DurableAssuranceArtifactStore,
    kind: AssuranceArtifactKind,
    payload_factory,
) -> None:
    payload = payload_factory()
    expected = cid_for_assurance_artifact(kind, payload)
    result = assurance.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id=f"op-{kind.value}-1",
        replicate=False,
    )
    assert result.cid == expected
    assert result.kind is kind
    assert result.local_durable is True
    assert result.provider_status is AssuranceProviderStatus.NOT_REQUESTED
    assert result.replicated is False
    assert result.reason_code in {"stored", "not_requested"}

    verified = assurance.get_verified_artifact(expected, expected_kind=kind)
    assert dict(verified) == payload
    assert verified["schema"] == payload["schema"]


def test_replication_when_backend_available(store_dir: Path) -> None:
    helia = MemoryHelia()
    with DurableCoordinationStore(store_dir, backend=helia) as coordination:
        with DurableAssuranceArtifactStore(coordination) as store:
            payload = _candidate_payload()
            kind = AssuranceArtifactKind.MUTATION_CANDIDATE
            expected = cid_for_assurance_artifact(kind, payload)
            result = store.put_artifact(
                kind,
                payload,
                expected_cid=expected,
                operation_id="op-replicate-1",
                replicate=True,
            )
            assert result.replicated is True
            assert result.provider_status is AssuranceProviderStatus.AVAILABLE
            assert result.reason_code == "replicated"
            assert expected in helia.blocks


def test_provider_unavailable_when_no_backend(
    assurance: DurableAssuranceArtifactStore,
) -> None:
    payload = _operator_payload()
    kind = AssuranceArtifactKind.MUTATION_OPERATOR_DEFINITION
    expected = cid_for_assurance_artifact(kind, payload)
    result = assurance.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id="op-no-backend",
        replicate=True,
    )
    assert result.local_durable is True
    assert result.replicated is False
    assert result.provider_status is AssuranceProviderStatus.UNAVAILABLE
    assert result.reason_code == "provider_unavailable"


def test_restart_reads_immutable_block_from_coordination_store(
    store_dir: Path,
) -> None:
    payload = _candidate_payload()
    kind = AssuranceArtifactKind.MUTATION_CANDIDATE
    expected = cid_for_assurance_artifact(kind, payload)
    with DurableCoordinationStore(store_dir) as coordination:
        with DurableAssuranceArtifactStore(coordination) as store:
            store.put_artifact(
                kind,
                payload,
                expected_cid=expected,
                operation_id="op-reopen-1",
                replicate=False,
            )
    with DurableCoordinationStore(store_dir) as coordination:
        with DurableAssuranceArtifactStore(coordination) as store:
            verified = store.get_verified_artifact(
                expected, expected_kind=kind
            )
            assert dict(verified) == payload


def test_idempotent_operation_id_replay(
    assurance: DurableAssuranceArtifactStore,
) -> None:
    payload = _candidate_payload()
    kind = AssuranceArtifactKind.MUTATION_CANDIDATE
    expected = cid_for_assurance_artifact(kind, payload)
    first = assurance.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id="op-idempotent",
        replicate=False,
    )
    second = assurance.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id="op-idempotent",
        replicate=False,
    )
    assert first.reason_code in {"stored", "not_requested"}
    assert second.reason_code == "unchanged"
    assert second.cid == expected


def test_operation_id_conflict_on_different_cid(
    assurance: DurableAssuranceArtifactStore,
) -> None:
    kind = AssuranceArtifactKind.MUTATION_CANDIDATE
    payload_a = mutation_fixtures._candidate(candidate_id="cand_a").to_dict()
    payload_b = mutation_fixtures._candidate(candidate_id="cand_b").to_dict()
    cid_a = cid_for_assurance_artifact(kind, payload_a)
    cid_b = cid_for_assurance_artifact(kind, payload_b)
    assert cid_a != cid_b
    assurance.put_artifact(
        kind,
        payload_a,
        expected_cid=cid_a,
        operation_id="op-conflict",
        replicate=False,
    )
    with pytest.raises(AssuranceArtifactConflictError, match="operation_id"):
        assurance.put_artifact(
            kind,
            payload_b,
            expected_cid=cid_b,
            operation_id="op-conflict",
            replicate=False,
        )


# ---------------------------------------------------------------------------
# Fail-closed: forged, wrong-kind, oversized, signature, missing
# ---------------------------------------------------------------------------


def test_forged_expected_cid_fails_closed(
    assurance: DurableAssuranceArtifactStore,
) -> None:
    payload = _candidate_payload()
    kind = AssuranceArtifactKind.MUTATION_CANDIDATE
    real = cid_for_assurance_artifact(kind, payload)
    forged = cid_for_bytes(b"not-the-artifact")
    assert forged != real
    with pytest.raises(AssuranceArtifactIntegrityError, match="forged|mismatched"):
        assurance.put_artifact(
            kind,
            payload,
            expected_cid=forged,
            operation_id="op-forged",
            replicate=False,
        )
    with pytest.raises(AssuranceArtifactNotFound):
        assurance.get_verified_artifact(forged)


def test_wrong_kind_on_put_fails_closed(
    assurance: DurableAssuranceArtifactStore,
) -> None:
    payload = _candidate_payload()
    with pytest.raises(AssuranceArtifactAdmissionError, match="schema"):
        assurance.put_artifact(
            AssuranceArtifactKind.MUTATION_OPERATOR_DEFINITION,
            payload,
            expected_cid=cid_for_bytes(b"unused"),
            operation_id="op-wrong-kind",
            replicate=False,
        )


def test_wrong_kind_on_get_fails_closed(
    assurance: DurableAssuranceArtifactStore,
) -> None:
    payload = _candidate_payload()
    kind = AssuranceArtifactKind.MUTATION_CANDIDATE
    expected = cid_for_assurance_artifact(kind, payload)
    assurance.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id="op-wrong-get",
        replicate=False,
    )
    with pytest.raises(AssuranceArtifactIntegrityError, match="wrong artifact kind|schema"):
        assurance.get_verified_artifact(
            expected,
            expected_kind=AssuranceArtifactKind.MUTATION_OPERATOR_DEFINITION,
        )


def test_oversized_artifact_fails_closed(
    assurance: DurableAssuranceArtifactStore,
) -> None:
    # Pad metadata past the sealed-record ceiling while remaining datasets-valid.
    blob = "x" * 20_000
    meta = {f"k{i}": blob for i in range(60)}
    payload = _operator_payload(**meta)
    kind = AssuranceArtifactKind.MUTATION_OPERATOR_DEFINITION
    with pytest.raises(AssuranceArtifactAdmissionError, match="MAX_ARTIFACT_BYTES"):
        seal_assurance_artifact(kind, payload)
    with pytest.raises(AssuranceArtifactAdmissionError, match="MAX_ARTIFACT_BYTES"):
        assurance.put_artifact(
            kind,
            payload,
            expected_cid=cid_for_bytes(b"unused"),
            operation_id="op-oversize",
            replicate=False,
        )


def test_unverified_signature_rejected_before_durable_write(
    assurance: DurableAssuranceArtifactStore,
    coordination: DurableCoordinationStore,
) -> None:
    payload = _unverified_campaign_payload()
    kind = AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT
    # Signature gate must fail before CID computation / durable put.
    with pytest.raises(AssuranceArtifactAdmissionError, match="signature"):
        seal_assurance_artifact(kind, payload)
    with pytest.raises(AssuranceArtifactAdmissionError, match="signature"):
        cid_for_assurance_artifact(kind, payload)
    with pytest.raises(AssuranceArtifactAdmissionError, match="signature"):
        assurance.put_artifact(
            kind,
            payload,
            expected_cid=cid_for_bytes(b"unused"),
            operation_id="op-unverified",
            replicate=False,
        )
    # Unverified signed receipts never reach content addressing, so no block
    # identity derived from the payload can exist in the coordination store.
    # Even the datasets receipt_cid must not be present as a durable block.
    from ipfs_datasets_py.logic.software_contracts.adversarial_assurance import (
        AssuranceCampaignReceipt,
    )

    receipt_cid = AssuranceCampaignReceipt.from_dict(payload).receipt_cid
    assert coordination.has(receipt_cid) is False
    # No operation binding was recorded either.
    assert assurance._ops.lookup("op-unverified") is None


def test_verified_signed_receipt_round_trip(
    assurance: DurableAssuranceArtifactStore,
) -> None:
    payload = _campaign_payload()
    kind = AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT
    expected = cid_for_assurance_artifact(kind, payload)
    assurance.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id="op-receipt-1",
        replicate=False,
    )
    verified = assurance.get_verified_artifact(expected, expected_kind=kind)
    assert verified["signature"]["signature_verification_status"] == "verified"
    assert dict(verified) == payload


def test_admit_stored_record_reprojects_and_regates() -> None:
    payload = _campaign_payload()
    kind = AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT
    admitted = admit_stored_record(kind, payload)
    assert admitted == payload
    unverified = _unverified_campaign_payload()
    with pytest.raises(AssuranceArtifactIntegrityError, match="signature"):
        admit_stored_record(kind, unverified)


def test_missing_cid_raises_not_found(
    assurance: DurableAssuranceArtifactStore,
) -> None:
    missing = cid_for_bytes(b"assurance-missing-block")
    with pytest.raises(AssuranceArtifactNotFound):
        assurance.get_verified_artifact(missing)


def test_get_infers_kind_from_header_when_not_supplied(
    assurance: DurableAssuranceArtifactStore,
) -> None:
    payload = _candidate_payload()
    kind = AssuranceArtifactKind.MUTATION_CANDIDATE
    expected = cid_for_assurance_artifact(kind, payload)
    assurance.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id="op-infer-kind",
        replicate=False,
    )
    verified = assurance.get_verified_artifact(expected)
    assert dict(verified) == payload


def test_put_rejects_unknown_kind(
    assurance: DurableAssuranceArtifactStore,
) -> None:
    with pytest.raises(AssuranceArtifactAdmissionError, match="unknown"):
        assurance.put_artifact(
            "not_a_real_kind",  # type: ignore[arg-type]
            _candidate_payload(),
            expected_cid=cid_for_bytes(b"unused"),
            operation_id="op-unknown-kind",
            replicate=False,
        )
