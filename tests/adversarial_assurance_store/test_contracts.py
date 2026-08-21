"""Contract vectors for AssuranceArtifactStore@1 (AAE-034)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import get_type_hints

import pytest

# Prefer this worktree's kit package when an outer PYTHONPATH pin is present.
_KIT_ROOT = Path(__file__).resolve().parents[2]
_KIT_PKG = _KIT_ROOT / "ipfs_kit_py"
if sys.path[:1] != [str(_KIT_ROOT)]:
    sys.path.insert(0, str(_KIT_ROOT))
# If ipfs_kit_py was already imported from another pin, still resolve submodules
# from this worktree.
import ipfs_kit_py as _ipfs_kit_py  # noqa: E402

if str(_KIT_PKG) not in list(_ipfs_kit_py.__path__):
    _ipfs_kit_py.__path__.insert(0, str(_KIT_PKG))

from ipfs_datasets_py.logic.software_contracts.adversarial_assurance import (
    ASSURANCE_CAMPAIGN_RECEIPT_SCHEMA,
    MUTATION_CANDIDATE_SCHEMA,
    MUTATION_OPERATOR_DEFINITION_SCHEMA,
    AssuranceTerminalStatus,
    HeldOutResult,
    SignatureVerificationStatus,
    adversarial_assurance_artifact_catalog,
    require_verified_signature_before_persistence,
)
from tests.adversarial_assurance_store.datasets_test_fixtures import (
    mutation_fixtures,
    receipt_fixtures,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import cid_for_bytes

from ipfs_kit_py.adversarial_assurance_store.contracts import (
    ASSURANCE_ARTIFACT_STORE_INTERFACE,
    ASSURANCE_ARTIFACT_STORE_SCHEMA,
    ASSURANCE_NAMESPACE_PREFIX,
    CONTRACT_VERSION,
    MAX_ARTIFACT_BYTES,
    AssuranceArtifactKind,
    AssuranceArtifactStore,
    AssuranceArtifactStoreContractError,
    AssuranceArtifactWriteResult,
    AssuranceNamespaceRole,
    AssuranceProviderStatus,
    AssuranceStoreStatus,
    assurance_artifact_kinds,
    assurance_namespace,
    assurance_namespace_roles,
    assurance_store_statuses,
    coerce_assurance_artifact_kind,
    datasets_interface_for_kind,
    datasets_schema_for_kind,
    is_signed_receipt_kind,
    parse_assurance_namespace,
    project_assurance_payload,
    require_verified_signature_gate,
    signed_receipt_kinds,
    validate_assurance_namespace,
    validate_assurance_workspace,
    validate_operation_id,
    validate_semantic_dag_json_cid,
    validate_verified_cid,
)


CID = cid_for_bytes(b"assurance-store-contract")


# ---------------------------------------------------------------------------
# Closed vocabularies and package surface
# ---------------------------------------------------------------------------


def test_interface_constants_are_versioned() -> None:
    assert CONTRACT_VERSION == 1
    assert ASSURANCE_ARTIFACT_STORE_INTERFACE == "AssuranceArtifactStore@1"
    assert ASSURANCE_ARTIFACT_STORE_SCHEMA.endswith("@1")
    assert ASSURANCE_NAMESPACE_PREFIX == "adversarial-assurance"
    assert MAX_ARTIFACT_BYTES == 1_048_576


def test_artifact_kinds_match_datasets_catalog() -> None:
    catalog_kinds = tuple(
        sorted(
            entry["artifact_kind"]
            for entry in adversarial_assurance_artifact_catalog()
            if entry.get("artifact_kind")
        )
    )
    kinds = assurance_artifact_kinds()
    assert tuple(sorted(kinds)) == catalog_kinds
    assert len(AssuranceArtifactKind) == len(catalog_kinds)
    with pytest.raises(AssuranceArtifactStoreContractError, match="unknown"):
        coerce_assurance_artifact_kind("model_reasoning")


def test_namespace_roles_and_statuses_are_closed() -> None:
    assert assurance_namespace_roles() == (
        "artifacts",
        "campaigns",
        "gaps",
        "receipts",
        "policy",
        "promotion",
        "merkle",
    )
    assert assurance_store_statuses() == (
        "updated",
        "unchanged",
        "conflict",
        "unavailable",
        "corrupt",
    )
    assert set(assurance_store_statuses()) >= {
        "conflict",
        "corrupt",
        "unavailable",
    }


def test_signed_receipt_kinds_are_closed() -> None:
    assert set(signed_receipt_kinds()) == {
        "assurance_campaign_receipt",
        "assurance_policy_promotion_receipt",
    }
    assert is_signed_receipt_kind(AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT)
    assert is_signed_receipt_kind("assurance_policy_promotion_receipt")
    assert not is_signed_receipt_kind(AssuranceArtifactKind.MUTATION_CANDIDATE)


# ---------------------------------------------------------------------------
# Namespaces, operation IDs, verified CIDs
# ---------------------------------------------------------------------------


def test_closed_assurance_namespaces_round_trip() -> None:
    for role in AssuranceNamespaceRole:
        ns = assurance_namespace("worker-1", role)
        workspace, parsed = parse_assurance_namespace(ns)
        assert workspace == "worker-1"
        assert parsed is role
        assert ns.startswith("adversarial-assurance/worker-1/")
        assert "semantic-governor/" not in ns


def test_namespace_rejects_governor_prefix_and_unknown_roles() -> None:
    with pytest.raises(AssuranceArtifactStoreContractError, match="adversarial-assurance"):
        parse_assurance_namespace("semantic-governor/ws/audit")
    with pytest.raises(AssuranceArtifactStoreContractError, match="unknown"):
        assurance_namespace("ws", "not-a-role")
    with pytest.raises(AssuranceArtifactStoreContractError):
        validate_assurance_workspace("BAD_CASE")
    with pytest.raises(AssuranceArtifactStoreContractError):
        validate_assurance_namespace("adversarial-assurance//artifacts")


def test_operation_id_and_cid_validators() -> None:
    assert validate_operation_id("op-1") == "op-1"
    with pytest.raises(AssuranceArtifactStoreContractError):
        validate_operation_id("OP UPPER")
    assert validate_verified_cid(CID) == CID
    assert validate_semantic_dag_json_cid(CID) == CID


# ---------------------------------------------------------------------------
# Typed projections consume datasets schemas (no redefinition)
# ---------------------------------------------------------------------------


def test_datasets_schema_projections_are_catalog_owned() -> None:
    assert (
        datasets_schema_for_kind(AssuranceArtifactKind.MUTATION_CANDIDATE)
        == MUTATION_CANDIDATE_SCHEMA
    )
    assert (
        datasets_schema_for_kind("mutation_operator_definition")
        == MUTATION_OPERATOR_DEFINITION_SCHEMA
    )
    assert (
        datasets_schema_for_kind(AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT)
        == ASSURANCE_CAMPAIGN_RECEIPT_SCHEMA
    )
    assert datasets_interface_for_kind(
        AssuranceArtifactKind.MUTATION_CANDIDATE
    ) == "MutationCandidate@1"
    # Kit contracts must not invent alternate datasets schema URIs.
    assert datasets_schema_for_kind("mutation_candidate").startswith(
        "ipfs-datasets.software-contracts."
    )


def test_project_assurance_payload_round_trips_candidate() -> None:
    candidate = mutation_fixtures._candidate()
    payload = candidate.to_dict()
    sealed = project_assurance_payload(
        AssuranceArtifactKind.MUTATION_CANDIDATE, payload
    )
    assert sealed == payload
    assert sealed["schema"] == MUTATION_CANDIDATE_SCHEMA
    assert sealed["header"]["artifact_kind"] == "mutation_candidate"


def test_project_rejects_schema_kind_mismatch() -> None:
    candidate = mutation_fixtures._candidate().to_dict()
    with pytest.raises(AssuranceArtifactStoreContractError, match="schema"):
        project_assurance_payload(
            AssuranceArtifactKind.MUTATION_OPERATOR_DEFINITION, candidate
        )


def test_project_rejects_header_kind_mismatch() -> None:
    candidate = mutation_fixtures._candidate().to_dict()
    # Tamper header kind while keeping candidate schema.
    candidate["header"] = dict(candidate["header"])
    candidate["header"]["artifact_kind"] = "assurance_gap"
    with pytest.raises(AssuranceArtifactStoreContractError, match="artifact_kind"):
        project_assurance_payload(
            AssuranceArtifactKind.MUTATION_CANDIDATE, candidate
        )


def test_project_operator_without_header() -> None:
    operator = mutation_fixtures._operator().to_dict()
    sealed = project_assurance_payload(
        AssuranceArtifactKind.MUTATION_OPERATOR_DEFINITION, operator
    )
    assert sealed["schema"] == MUTATION_OPERATOR_DEFINITION_SCHEMA
    assert "header" not in sealed


# ---------------------------------------------------------------------------
# Signature gate before persistence / content addressing / seal eligibility
# ---------------------------------------------------------------------------


def test_require_verified_signature_gate_accepts_verified_receipts() -> None:
    campaign = receipt_fixtures._campaign()
    assert require_verified_signature_gate(campaign) == campaign.receipt_cid
    assert (
        require_verified_signature_gate(campaign.to_dict()) == campaign.receipt_cid
    )
    # Same authority the datasets package exports.
    assert (
        require_verified_signature_before_persistence(campaign)
        == campaign.receipt_cid
    )


def test_require_verified_signature_gate_rejects_unverified() -> None:
    receipt = receipt_fixtures._campaign(
        header=receipt_fixtures._header(
            "assurance_campaign_receipt",
            terminal_status=AssuranceTerminalStatus.REJECTED,
        ),
        held_out_result=HeldOutResult.FAILED,
        signature=receipt_fixtures._signature(
            signature_verification_status=SignatureVerificationStatus.UNVERIFIED
        ),
    )
    with pytest.raises(AssuranceArtifactStoreContractError, match="signature"):
        require_verified_signature_gate(receipt.to_dict())


def test_project_signed_receipt_enforces_signature_gate() -> None:
    body = receipt_fixtures._campaign().to_dict()
    sealed = project_assurance_payload(
        AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT,
        body,
        enforce_signature_gate=True,
    )
    assert sealed["schema"] == ASSURANCE_CAMPAIGN_RECEIPT_SCHEMA

    unverified = receipt_fixtures._campaign(
        header=receipt_fixtures._header(
            "assurance_campaign_receipt",
            terminal_status=AssuranceTerminalStatus.REJECTED,
        ),
        held_out_result=HeldOutResult.FAILED,
        signature=receipt_fixtures._signature(
            signature_verification_status=SignatureVerificationStatus.INVALID
        ),
    ).to_dict()
    with pytest.raises(AssuranceArtifactStoreContractError, match="signature"):
        project_assurance_payload(
            AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT,
            unverified,
            enforce_signature_gate=True,
        )


# ---------------------------------------------------------------------------
# Write result and protocol surface
# ---------------------------------------------------------------------------


def test_write_result_round_trip_and_invariants() -> None:
    result = AssuranceArtifactWriteResult(
        cid=CID,
        kind=AssuranceArtifactKind.MUTATION_CANDIDATE,
        local_durable=True,
        provider_status=AssuranceProviderStatus.NOT_REQUESTED,
        replicated=False,
        reason_code="stored",
    )
    assert AssuranceArtifactWriteResult.from_dict(result.to_dict()) == result
    with pytest.raises(AssuranceArtifactStoreContractError):
        AssuranceArtifactWriteResult(
            cid=CID,
            kind=AssuranceArtifactKind.MUTATION_CANDIDATE,
            local_durable=False,
            provider_status=AssuranceProviderStatus.NOT_REQUESTED,
            replicated=False,
            reason_code="stored",
        )
    with pytest.raises(AssuranceArtifactStoreContractError):
        AssuranceArtifactWriteResult(
            cid=CID,
            kind=AssuranceArtifactKind.MUTATION_CANDIDATE,
            local_durable=True,
            provider_status=AssuranceProviderStatus.UNAVAILABLE,
            replicated=True,
            reason_code="stored",
        )


def test_protocol_exposes_put_and_get() -> None:
    hints = get_type_hints(AssuranceArtifactStore.put_artifact)
    assert "kind" in hints
    assert "payload" in hints
    assert "expected_cid" in hints
    assert "operation_id" in hints
    get_hints = get_type_hints(AssuranceArtifactStore.get_verified_artifact)
    assert "cid" in get_hints
    assert "expected_kind" in get_hints
    # Status enum is available for later CAS modules without expanding this surface.
    assert AssuranceStoreStatus.CONFLICT.value == "conflict"
