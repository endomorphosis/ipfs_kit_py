"""Regression tests for canonical operation contracts (KITA-002).

Acceptance coverage:

* states distinguish accepted / queued / committed / verified / converged and
  every failure / partial-effect disposition;
* request, idempotency, principal, policy, backend, WAL, cache, index, replica,
  and environment identities bind as applicable;
* secrets, bodies, cycles, non-finite / unbounded fields, forged IDs,
  inconsistent states, and success without required evidence are rejected; and
* type / resource / memory facets remain distinct.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from ipfs_kit_py.core.operation_contracts import (
    CONTRACT_VERSION,
    CONVERGED_STATES,
    DURABLE_STATES,
    FAILURE_STATES,
    MAX_RECORD_BYTES,
    MAX_REFERENCE_COUNT,
    MAX_TEXT_BYTES,
    OPERATION_REQUEST_SCHEMA,
    OPERATION_RESULT_SCHEMA,
    PARTIAL_STATES,
    SCHEMA_VERSION,
    STATE_TRANSITION_RECEIPT_SCHEMA,
    STORAGE_ERROR_SCHEMA,
    SUCCESS_STATES,
    VERIFIED_STATES,
    BodyRejectedError,
    ConsistencyRequirement,
    CycleDetectedError,
    DurabilityEvidence,
    DurabilityMode,
    EffectEvidence,
    EffectKind,
    ErrorCategory,
    ErrorCode,
    EvidenceKind,
    FacetKind,
    FacetRef,
    FallbackPolicy,
    ForgedIdentityError,
    IdentityBindings,
    InconsistentStateError,
    OperationContractBoundsError,
    OperationContractError,
    OperationRequest,
    OperationResult,
    OperationState,
    PartialEffectRecord,
    PayloadKind,
    PayloadReference,
    Retryability,
    SecretMaterialError,
    StateTransitionReceipt,
    StorageError,
    TimingBounds,
    assert_acyclic_evidence_refs,
    assert_acyclic_state_chain,
    canonical_json_bytes,
    content_identity,
    durability_for_converged,
    durability_for_verified,
    durability_for_wal_fsync,
    is_legal_transition,
)


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def identities(**overrides: Any) -> IdentityBindings:
    base = dict(
        request_id="request:alpha",
        operation_id="operation:write-object",
        idempotency_key="idem:alpha-1",
        principal_id="principal:alice",
        tenant_id="tenant:acme",
        policy_id="policy:profile-d@1",
        policy_decision_cid="sha256:" + ("ab" * 32),
        backend_id="backend:ipfs-primary",
        backend_capability_id="capability:ipfs-block-put",
        wal_generation_id="wal-gen:7",
        wal_segment_id="wal-seg:3",
        cache_generation_id="cache-gen:2",
        index_generation_id="index-gen:4",
        replica_policy_id="replica-policy:default",
        environment_id="environment:ci-hermetic",
        transaction_id="txn:9001",
        bucket_id="bucket:docs",
        catalog_generation_id="catalog-gen:1",
        graphrag_generation_id="graphrag-gen:0",
        trace_id="trace:deadbeef",
        cancellation_token_id="cancel:token-1",
        ucan_resource="resource:/buckets/docs",
        ucan_ability="ability:object/write",
    )
    base.update(overrides)
    return IdentityBindings(**base)


def wal_durability(**overrides: Any) -> DurabilityEvidence:
    base = dict(
        mode=DurabilityMode.WAL_FSYNC,
        wal_record_id="wal-rec:100",
        fsync_receipt_id="fsync:100",
        wal_generation_id="wal-gen:7",
        transaction_commit_id="txn-commit:9001",
        effect_evidence_ids=("effect:wal-append",),
    )
    base.update(overrides)
    return DurabilityEvidence(**base)


def effect(
    evidence_id: str = "effect:wal-append",
    *,
    kind: EvidenceKind = EvidenceKind.WAL_RECORD,
    effect_kind: EffectKind = EffectKind.WAL_APPEND,
    reference: str = "wal-rec:100",
) -> EffectEvidence:
    return EffectEvidence(
        evidence_id=evidence_id,
        kind=kind,
        effect_kind=effect_kind,
        reference=reference,
        backend_id="backend:ipfs-primary",
        generation_id="wal-gen:7",
        observed=True,
    )


def type_facet(
    facet_id: str = "facet:type-payload",
    *,
    contract_ref: str = "type:ObjectWrite",
) -> FacetRef:
    return FacetRef(
        facet_id=facet_id,
        kind=FacetKind.TYPE,
        subject_id="subject:write-object",
        contract_ref=contract_ref,
    )


def resource_facet(
    facet_id: str = "facet:resource-budget",
    *,
    contract_ref: str = "resource:bytes<=1MiB",
) -> FacetRef:
    return FacetRef(
        facet_id=facet_id,
        kind=FacetKind.RESOURCE,
        subject_id="subject:write-object",
        contract_ref=contract_ref,
    )


def memory_facet(
    facet_id: str = "facet:memory-region",
    *,
    contract_ref: str = "memory:scratch-arena",
) -> FacetRef:
    return FacetRef(
        facet_id=facet_id,
        kind=FacetKind.MEMORY,
        subject_id="subject:write-object",
        contract_ref=contract_ref,
    )


def sample_request(**overrides: Any) -> OperationRequest:
    base: dict[str, Any] = dict(
        identities=identities(),
        operation_name="vfs.write",
        consistency=ConsistencyRequirement.STRONG,
        durability=DurabilityMode.WAL_FSYNC,
        fallback_policy=FallbackPolicy.REJECT_IF_UNAVAILABLE,
        path="/buckets/docs/readme.md",
        key="readme.md",
        precondition_version_cid="sha256:" + ("cd" * 32),
        payload=PayloadReference(
            kind=PayloadKind.CONTENT_CID,
            content_cid="sha256:" + ("11" * 32),
            media_type="text/markdown",
            size_bytes=128,
        ),
        backend_requirements=("backend:ipfs-primary",),
        required_capabilities=("capability:ipfs-block-put",),
        facets=(type_facet(), resource_facet(), memory_facet()),
        timing=TimingBounds(timeout_ms=5_000, deadline_unix_ms=1_700_000_000_000),
        evidence_refs=("evidence:precondition",),
    )
    base.update(overrides)
    return OperationRequest(**base)


def committed_result(**overrides: Any) -> OperationResult:
    durability = wal_durability()
    base: dict[str, Any] = dict(
        request_id="request:alpha",
        operation_id="operation:write-object",
        state=OperationState.COMMITTED,
        success=True,
        resulting_content_cid="sha256:" + ("11" * 32),
        resulting_version_cid="sha256:" + ("22" * 32),
        durability=durability,
        effect_evidence=(effect(),),
        backend_id="backend:ipfs-primary",
        wal_generation_id="wal-gen:7",
        cache_generation_id="cache-gen:2",
        index_generation_id="index-gen:4",
        replica_policy_id="replica-policy:default",
        environment_id="environment:ci-hermetic",
        idempotency_key="idem:alpha-1",
        principal_id="principal:alice",
        policy_decision_cid="sha256:" + ("ab" * 32),
        facets=(type_facet(), resource_facet(), memory_facet()),
        evidence_refs=("effect:wal-append",),
    )
    base.update(overrides)
    return OperationResult(**base)


# ---------------------------------------------------------------------------
# Schema / vocabulary
# ---------------------------------------------------------------------------


def test_schema_versions_and_interface_aliases() -> None:
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert OPERATION_REQUEST_SCHEMA.endswith("@1")
    assert OPERATION_RESULT_SCHEMA.endswith("@1")
    assert STORAGE_ERROR_SCHEMA.endswith("@1")
    assert STATE_TRANSITION_RECEIPT_SCHEMA.endswith("@1")


def test_state_vocabularies_cover_acceptance_ladder() -> None:
    for name in (
        "accepted",
        "queued",
        "committed",
        "verified",
        "converged",
        "partial_effect",
        "failed",
        "rejected",
        "cancelled",
        "timed_out",
        "aborted",
        "unsupported",
        "unavailable",
        "conflict",
        "deadline_exceeded",
        "backpressure",
        "compensating",
        "rolled_back",
        "precondition_failed",
        "authorization_denied",
    ):
        assert OperationState(name)

    assert OperationState.ACCEPTED in SUCCESS_STATES
    assert OperationState.QUEUED in SUCCESS_STATES
    assert OperationState.COMMITTED in DURABLE_STATES
    assert OperationState.VERIFIED in VERIFIED_STATES
    assert OperationState.CONVERGED in CONVERGED_STATES
    assert OperationState.PARTIAL_EFFECT in PARTIAL_STATES
    assert OperationState.FAILED in FAILURE_STATES
    assert OperationState.COMPENSATING in PARTIAL_STATES


def test_legal_transitions_reject_impossible_upgrades() -> None:
    assert is_legal_transition(OperationState.ACCEPTED, OperationState.QUEUED)
    assert is_legal_transition(OperationState.QUEUED, OperationState.PROCESSING)
    assert is_legal_transition(OperationState.PROCESSING, OperationState.COMMITTED)
    assert is_legal_transition(OperationState.COMMITTED, OperationState.VERIFIED)
    assert is_legal_transition(OperationState.VERIFIED, OperationState.CONVERGED)
    # Cannot jump from accepted straight to converged without intermediate path
    # through the transition table (accepted does not list converged).
    assert not is_legal_transition(OperationState.ACCEPTED, OperationState.CONVERGED)
    assert not is_legal_transition(OperationState.CONVERGED, OperationState.COMMITTED)
    assert not is_legal_transition(OperationState.FAILED, OperationState.COMMITTED)
    assert not is_legal_transition(OperationState.QUEUED, OperationState.COMMITTED)


# ---------------------------------------------------------------------------
# Identity bindings
# ---------------------------------------------------------------------------


def test_identity_bindings_cover_required_facets() -> None:
    bound = identities()
    assert bound.request_id == "request:alpha"
    assert bound.idempotency_key == "idem:alpha-1"
    assert bound.principal_id == "principal:alice"
    assert bound.policy_id == "policy:profile-d@1"
    assert bound.policy_decision_cid.startswith("sha256:")
    assert bound.backend_id == "backend:ipfs-primary"
    assert bound.wal_generation_id == "wal-gen:7"
    assert bound.cache_generation_id == "cache-gen:2"
    assert bound.index_generation_id == "index-gen:4"
    assert bound.replica_policy_id == "replica-policy:default"
    assert bound.environment_id == "environment:ci-hermetic"
    record = bound.to_record()
    assert IdentityBindings.from_dict(record) == bound
    assert bound.content_id.startswith("b")


def test_round_trip_request_result_error_receipt() -> None:
    request = sample_request()
    assert OperationRequest.from_dict(request.to_record()) == request

    result = committed_result()
    assert OperationResult.from_dict(result.to_record()) == result

    error = StorageError(
        code=ErrorCode.CONFLICT,
        category=ErrorCategory.CONFLICT,
        message="precondition version mismatch",
        retryability=Retryability.NEVER,
        state=OperationState.CONFLICT,
        http_status_hint=409,
        exit_code_hint=1,
        json_rpc_code_hint=-32009,
    )
    assert StorageError.from_dict(error.to_record()) == error
    projection = error.as_transport_projection()
    assert projection["error"] is True
    assert projection["code"] == ErrorCode.CONFLICT.value
    assert projection["state"] == "conflict"

    durability = wal_durability()
    receipt = StateTransitionReceipt(
        receipt_id="receipt:1",
        request_id="request:alpha",
        operation_id="operation:write-object",
        from_state=OperationState.PROCESSING,
        to_state=OperationState.COMMITTED,
        at_unix_ms=1_700_000_000_100,
        durability=durability,
        evidence_refs=("effect:wal-append",),
        backend_id="backend:ipfs-primary",
        wal_generation_id="wal-gen:7",
        environment_id="environment:ci-hermetic",
    )
    assert StateTransitionReceipt.from_dict(receipt.to_record()) == receipt


def test_canonical_serialization_is_deterministic() -> None:
    a = sample_request()
    b = sample_request()
    assert a.canonical_bytes() == b.canonical_bytes()
    assert a.content_id == b.content_id
    assert content_identity(a.to_dict()) == a.content_id


# ---------------------------------------------------------------------------
# Facets remain distinct
# ---------------------------------------------------------------------------


def test_type_resource_memory_facets_remain_distinct() -> None:
    ok = sample_request(
        facets=(type_facet(), resource_facet(), memory_facet()),
    )
    assert {f.kind for f in ok.facets} == {
        FacetKind.TYPE,
        FacetKind.RESOURCE,
        FacetKind.MEMORY,
    }

    with pytest.raises(InconsistentStateError, match="type facets cannot bind"):
        FacetRef(
            facet_id="facet:bad-type",
            kind=FacetKind.TYPE,
            subject_id="subject:x",
            contract_ref="memory:arena",
        )

    with pytest.raises(InconsistentStateError, match="resource facets cannot bind"):
        FacetRef(
            facet_id="facet:bad-resource",
            kind=FacetKind.RESOURCE,
            subject_id="subject:x",
            contract_ref="type:Foo",
        )

    with pytest.raises(InconsistentStateError, match="memory facets cannot bind"):
        FacetRef(
            facet_id="facet:bad-memory",
            kind=FacetKind.MEMORY,
            subject_id="subject:x",
            contract_ref="resource:cpu",
        )

    # Same contract_ref claimed by two kinds is rejected on the request.
    with pytest.raises(InconsistentStateError, match="disjoint"):
        sample_request(
            facets=(
                FacetRef(
                    facet_id="facet:a",
                    kind=FacetKind.TYPE,
                    subject_id="subject:x",
                    contract_ref="shared:name",
                ),
                FacetRef(
                    facet_id="facet:b",
                    kind=FacetKind.RESOURCE,
                    subject_id="subject:x",
                    contract_ref="shared:name",
                ),
            )
        )


# ---------------------------------------------------------------------------
# Success ladder requires evidence
# ---------------------------------------------------------------------------


def test_accepted_and_queued_do_not_require_durability_evidence() -> None:
    accepted = OperationResult(
        request_id="request:alpha",
        operation_id="operation:write-object",
        state=OperationState.ACCEPTED,
        success=True,
    )
    assert accepted.success is True
    assert accepted.durability is None

    queued = OperationResult(
        request_id="request:alpha",
        operation_id="operation:write-object",
        state=OperationState.QUEUED,
        success=True,
    )
    assert queued.state is OperationState.QUEUED


def test_committed_requires_durability_and_effect_evidence() -> None:
    with pytest.raises(InconsistentStateError, match="DurabilityEvidence"):
        OperationResult(
            request_id="request:alpha",
            operation_id="operation:write-object",
            state=OperationState.COMMITTED,
            success=True,
        )

    with pytest.raises(InconsistentStateError, match="durability evidence"):
        OperationResult(
            request_id="request:alpha",
            operation_id="operation:write-object",
            state=OperationState.COMMITTED,
            success=True,
            durability=DurabilityEvidence(mode=DurabilityMode.ACCEPTED_ONLY),
            effect_evidence=(effect(),),
        )

    with pytest.raises(InconsistentStateError, match="effect evidence"):
        OperationResult(
            request_id="request:alpha",
            operation_id="operation:write-object",
            state=OperationState.COMMITTED,
            success=True,
            durability=wal_durability(effect_evidence_ids=()),
            effect_evidence=(),
        )

    ok = committed_result()
    assert ok.state is OperationState.COMMITTED
    assert ok.durability is not None
    assert ok.durability.supports_committed()


def test_verified_and_converged_require_escalating_evidence() -> None:
    base = wal_durability()
    with pytest.raises(InconsistentStateError, match="integrity"):
        OperationResult(
            request_id="request:alpha",
            operation_id="operation:write-object",
            state=OperationState.VERIFIED,
            success=True,
            durability=base,
            effect_evidence=(effect(),),
        )

    verified_ev = durability_for_verified(
        base=base, integrity_proof_id="integrity:proof-1"
    )
    verified = OperationResult(
        request_id="request:alpha",
        operation_id="operation:write-object",
        state=OperationState.VERIFIED,
        success=True,
        durability=verified_ev,
        effect_evidence=(effect(),),
        resulting_content_cid="sha256:" + ("11" * 32),
    )
    assert verified.state is OperationState.VERIFIED

    with pytest.raises(InconsistentStateError, match="replica/cache/index"):
        OperationResult(
            request_id="request:alpha",
            operation_id="operation:write-object",
            state=OperationState.CONVERGED,
            success=True,
            durability=verified_ev,
            effect_evidence=(effect(),),
        )

    converged_ev = durability_for_converged(
        base=verified_ev,
        replica_receipt_ids=("replica:ack-1",),
        cache_generation_id="cache-gen:2",
        index_generation_id="index-gen:4",
    )
    converged = OperationResult(
        request_id="request:alpha",
        operation_id="operation:write-object",
        state=OperationState.CONVERGED,
        success=True,
        durability=converged_ev,
        effect_evidence=(effect(),),
        resulting_content_cid="sha256:" + ("11" * 32),
        cache_generation_id="cache-gen:2",
        index_generation_id="index-gen:4",
        replica_policy_id="replica-policy:default",
    )
    assert converged.state is OperationState.CONVERGED
    assert converged.durability is not None
    assert converged.durability.supports_converged()


def test_helpers_build_wal_fsync_evidence() -> None:
    ev = durability_for_wal_fsync(
        wal_record_id="wal-rec:1",
        fsync_receipt_id="fsync:1",
        effect_evidence_ids=("effect:1",),
    )
    assert ev.supports_committed()
    assert not ev.supports_verified()


# ---------------------------------------------------------------------------
# Failure / partial-effect states
# ---------------------------------------------------------------------------


def test_failure_states_require_storage_error() -> None:
    for state in (
        OperationState.FAILED,
        OperationState.REJECTED,
        OperationState.CANCELLED,
        OperationState.TIMED_OUT,
        OperationState.UNSUPPORTED,
        OperationState.UNAVAILABLE,
        OperationState.AUTHORIZATION_DENIED,
    ):
        with pytest.raises(InconsistentStateError, match="requires a StorageError"):
            OperationResult(
                request_id="request:alpha",
                operation_id="operation:write-object",
                state=state,
                success=False,
            )

        error = StorageError(
            code=ErrorCode.STORAGE_FAILURE,
            category=ErrorCategory.STORAGE,
            message=f"failed in {state.value}",
            retryability=Retryability.AFTER_RECONCILE,
            state=state,
        )
        result = OperationResult(
            request_id="request:alpha",
            operation_id="operation:write-object",
            state=state,
            success=False,
            error=error,
        )
        assert result.success is False
        assert result.error is not None


def test_partial_effect_state_and_record() -> None:
    partial = PartialEffectRecord(
        partial_id="partial:1",
        effect_kind=EffectKind.BACKEND_WRITE,
        state=OperationState.PARTIAL_EFFECT,
        description="backend wrote bytes; WAL commit marker missing",
        applied_evidence_ids=("effect:backend-write",),
        pending_evidence_ids=("effect:wal-commit",),
        compensation_required=True,
        backend_id="backend:ipfs-primary",
    )
    assert partial.state is OperationState.PARTIAL_EFFECT

    with pytest.raises(InconsistentStateError, match="terminal success"):
        PartialEffectRecord(
            partial_id="partial:bad",
            effect_kind=EffectKind.BACKEND_WRITE,
            state=OperationState.COMMITTED,
            description="illegal",
        )

    result = OperationResult(
        request_id="request:alpha",
        operation_id="operation:write-object",
        state=OperationState.PARTIAL_EFFECT,
        success=False,
        partial_effects=(partial,),
        error=StorageError(
            code=ErrorCode.PARTIAL_EFFECT,
            category=ErrorCategory.PARTIAL_EFFECT,
            message="partial external effect requires compensation",
            retryability=Retryability.AFTER_RECONCILE,
            state=OperationState.PARTIAL_EFFECT,
            partial_effect_ids=("partial:1",),
        ),
    )
    assert result.partial_effects[0].compensation_required is True

    with pytest.raises(InconsistentStateError, match="PartialEffectRecord"):
        OperationResult(
            request_id="request:alpha",
            operation_id="operation:write-object",
            state=OperationState.PARTIAL_EFFECT,
            success=False,
            error=StorageError(
                code=ErrorCode.PARTIAL_EFFECT,
                category=ErrorCategory.PARTIAL_EFFECT,
                message="missing partial records",
                state=OperationState.PARTIAL_EFFECT,
            ),
        )


def test_success_with_error_or_failure_state_is_rejected() -> None:
    with pytest.raises(InconsistentStateError, match="cannot carry StorageError"):
        OperationResult(
            request_id="request:alpha",
            operation_id="operation:write-object",
            state=OperationState.ACCEPTED,
            success=True,
            error=StorageError(
                code=ErrorCode.INTERNAL,
                category=ErrorCategory.INTERNAL,
                message="should not appear",
                state=OperationState.FAILED,
            ),
        )

    with pytest.raises(InconsistentStateError, match="inconsistent with failure"):
        OperationResult(
            request_id="request:alpha",
            operation_id="operation:write-object",
            state=OperationState.FAILED,
            success=True,
            error=StorageError(
                code=ErrorCode.INTERNAL,
                category=ErrorCategory.INTERNAL,
                message="x",
                state=OperationState.FAILED,
            ),
        )


def test_storage_error_cannot_claim_success_state() -> None:
    with pytest.raises(InconsistentStateError, match="success acknowledgement"):
        StorageError(
            code=ErrorCode.INTERNAL,
            category=ErrorCategory.INTERNAL,
            message="bad",
            state=OperationState.COMMITTED,
        )


# ---------------------------------------------------------------------------
# State transition receipts
# ---------------------------------------------------------------------------


def test_state_transition_receipt_enforces_legality_and_evidence() -> None:
    durability = wal_durability()
    ok = StateTransitionReceipt(
        receipt_id="receipt:ok",
        request_id="request:alpha",
        operation_id="operation:write-object",
        from_state=OperationState.PROCESSING,
        to_state=OperationState.COMMITTED,
        at_unix_ms=100,
        durability=durability,
        evidence_refs=("effect:wal-append",),
    )
    assert ok.to_state is OperationState.COMMITTED

    with pytest.raises(InconsistentStateError, match="illegal state transition"):
        StateTransitionReceipt(
            receipt_id="receipt:bad",
            request_id="request:alpha",
            operation_id="operation:write-object",
            from_state=OperationState.ACCEPTED,
            to_state=OperationState.CONVERGED,
            at_unix_ms=100,
            durability=durability_for_converged(
                base=durability_for_verified(
                    base=durability, integrity_proof_id="integrity:1"
                ),
                replica_receipt_ids=("replica:1",),
            ),
        )

    with pytest.raises(InconsistentStateError, match="durability evidence"):
        StateTransitionReceipt(
            receipt_id="receipt:no-ev",
            request_id="request:alpha",
            operation_id="operation:write-object",
            from_state=OperationState.PROCESSING,
            to_state=OperationState.COMMITTED,
            at_unix_ms=100,
        )

    with pytest.raises(InconsistentStateError, match="requires StorageError"):
        StateTransitionReceipt(
            receipt_id="receipt:fail",
            request_id="request:alpha",
            operation_id="operation:write-object",
            from_state=OperationState.PROCESSING,
            to_state=OperationState.FAILED,
            at_unix_ms=100,
        )


def test_state_chain_contiguity_and_cycle_detection() -> None:
    durability = wal_durability()
    t1 = StateTransitionReceipt(
        receipt_id="receipt:1",
        request_id="request:alpha",
        operation_id="operation:write-object",
        from_state=OperationState.ACCEPTED,
        to_state=OperationState.PROCESSING,
        at_unix_ms=1,
    )
    t2 = StateTransitionReceipt(
        receipt_id="receipt:2",
        request_id="request:alpha",
        operation_id="operation:write-object",
        from_state=OperationState.PROCESSING,
        to_state=OperationState.COMMITTED,
        at_unix_ms=2,
        durability=durability,
        evidence_refs=("effect:wal-append",),
    )
    assert_acyclic_state_chain((t1, t2))

    # Non-contiguous
    t_bad = StateTransitionReceipt(
        receipt_id="receipt:3",
        request_id="request:alpha",
        operation_id="operation:write-object",
        from_state=OperationState.QUEUED,
        to_state=OperationState.PROCESSING,
        at_unix_ms=3,
    )
    with pytest.raises(InconsistentStateError, match="not contiguous"):
        assert_acyclic_state_chain((t1, t_bad))


def test_evidence_graph_cycle_rejected() -> None:
    assert_acyclic_evidence_refs(
        {
            "a": ("b",),
            "b": ("c",),
            "c": (),
        }
    )
    with pytest.raises(CycleDetectedError):
        assert_acyclic_evidence_refs(
            {
                "a": ("b",),
                "b": ("c",),
                "c": ("a",),
            }
        )


# ---------------------------------------------------------------------------
# Forged IDs, secrets, bodies, non-finite, unbounded, unknown fields
# ---------------------------------------------------------------------------


def test_forged_content_identity_rejected() -> None:
    request = sample_request()
    payload = request.to_record()
    payload["content_id"] = "baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    with pytest.raises(ForgedIdentityError):
        OperationRequest.from_dict(payload)

    result = committed_result()
    payload = result.to_record()
    payload["content_id"] = "b" + ("a" * 58)
    with pytest.raises(ForgedIdentityError):
        OperationResult.from_dict(payload)


def test_secrets_rejected_in_records_and_text() -> None:
    with pytest.raises(SecretMaterialError):
        IdentityBindings(
            request_id="request:alpha",
            operation_id="operation:x",
            principal_id="password=hunter2",
        )

    with pytest.raises(SecretMaterialError):
        StorageError(
            code=ErrorCode.INTERNAL,
            category=ErrorCategory.INTERNAL,
            message="token failure: bearer abc.def.ghi",
            state=OperationState.FAILED,
        )

    # Secret key names in free-form mappings (via canonicalization of nested dicts
    # is covered when smuggled through metadata — ensure body path rejects too).
    with pytest.raises(SecretMaterialError):
        canonical_json_bytes({"api_key": "x", "ok": True})


def test_bodies_rejected() -> None:
    with pytest.raises(BodyRejectedError):
        canonical_json_bytes({"source_body": "print('hi')", "ok": True})

    with pytest.raises(BodyRejectedError):
        PayloadReference(
            kind=PayloadKind.CONTENT_CID,
            content_cid="sha256:" + ("11" * 32),
            inline_utf8="should not be present",
        )

    # INLINE_BOUNDED is allowed only within MAX_TEXT_BYTES
    ok = PayloadReference(
        kind=PayloadKind.INLINE_BOUNDED,
        inline_utf8="small",
        size_bytes=5,
    )
    assert ok.inline_utf8 == "small"

    with pytest.raises(OperationContractBoundsError):
        PayloadReference(
            kind=PayloadKind.INLINE_BOUNDED,
            inline_utf8="x" * (MAX_TEXT_BYTES + 1),
        )


def test_non_finite_and_float_rejected() -> None:
    with pytest.raises(OperationContractError, match="non-finite|floats"):
        canonical_json_bytes({"value": math.nan})
    with pytest.raises(OperationContractError, match="non-finite|floats"):
        canonical_json_bytes({"value": math.inf})
    with pytest.raises(OperationContractError, match="floats"):
        canonical_json_bytes({"value": 1.5})


def test_unbounded_fields_and_oversized_text_rejected() -> None:
    with pytest.raises(OperationContractBoundsError):
        IdentityBindings(
            request_id="r" * (MAX_TEXT_BYTES + 50),
            operation_id="operation:x",
        )

    with pytest.raises(OperationContractBoundsError):
        sample_request(
            evidence_refs=tuple(f"evidence:{i}" for i in range(MAX_REFERENCE_COUNT + 1))
        )

    with pytest.raises(OperationContractError, match="unsupported fields"):
        OperationRequest.from_dict(
            {
                **sample_request().to_dict(),
                "unexpected_field": "nope",
            }
        )


def test_cycle_in_mapping_structure_rejected() -> None:
    cyclic: dict[str, Any] = {"a": 1}
    cyclic["self"] = cyclic
    with pytest.raises(CycleDetectedError):
        canonical_json_bytes(cyclic)


def test_timing_invariants() -> None:
    with pytest.raises(InconsistentStateError, match="finished_at"):
        TimingBounds(started_at_unix_ms=100, finished_at_unix_ms=50)

    ok = TimingBounds(
        started_at_unix_ms=100,
        finished_at_unix_ms=150,
        duration_ms=50,
    )
    assert ok.duration_ms == 50


def test_fallback_policy_requires_declared_alternates_consistently() -> None:
    with pytest.raises(InconsistentStateError, match="alternate_backend_ids"):
        sample_request(
            fallback_policy=FallbackPolicy.REQUIRE_EXACT,
            alternate_backend_ids=("backend:other",),
        )

    ok = sample_request(
        fallback_policy=FallbackPolicy.ALLOW_DECLARED_ALTERNATES,
        alternate_backend_ids=("backend:other",),
    )
    assert ok.alternate_backend_ids == ("backend:other",)


def test_payload_empty_invariants() -> None:
    empty = PayloadReference(kind=PayloadKind.EMPTY)
    assert empty.kind is PayloadKind.EMPTY
    with pytest.raises(InconsistentStateError, match="empty payload"):
        PayloadReference(
            kind=PayloadKind.EMPTY,
            content_cid="sha256:" + ("11" * 32),
        )


def test_immutability_of_core_records() -> None:
    request = sample_request()
    with pytest.raises(Exception):
        request.operation_name = "mutated"  # type: ignore[misc]

    result = committed_result()
    with pytest.raises(Exception):
        result.success = False  # type: ignore[misc]


def test_record_size_bound_constant_is_finite() -> None:
    assert MAX_RECORD_BYTES > 0
    request = sample_request()
    assert len(request.canonical_bytes()) < MAX_RECORD_BYTES


def test_unsupported_contract_version_rejected() -> None:
    payload = sample_request().to_dict()
    payload["contract_version"] = 99
    with pytest.raises(OperationContractError, match="version"):
        OperationRequest.from_dict(payload)
