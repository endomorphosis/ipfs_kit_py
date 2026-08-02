"""Regression tests for backend-scoped bucket catalog contracts (KITA-010)."""

from __future__ import annotations

import pytest

from ipfs_kit_py.core.operation_contracts import (
    CycleDetectedError,
    ForgedIdentityError,
    InconsistentStateError,
    SecretMaterialError,
)
from ipfs_kit_py.core.buckets.contracts import (
    CONTRACT_VERSION,
    BackendCapability,
    BackendCapabilityInsufficientError,
    BucketCatalog,
    BucketCatalogError,
    BucketContractError,
    BucketIdentity,
    BucketIdentityError,
    BucketLifecycleState,
    BucketManifest,
    BucketPolicy,
    BucketPolicyError,
    BucketReplica,
    BucketReplicaRole,
    BucketReplicaState,
    BucketCatalog_V1,
    BucketIdentity_V1,
    BucketManifest_V1,
    BucketPolicy_V1,
    EncryptionMode,
    PolicyEnforcementState,
    QueryMode,
    RetentionMode,
    StorageTier,
    TransferFormat,
    assert_backend_supports_policy,
    assert_legal_bucket_transition,
    assert_legal_replica_transition,
    is_legal_bucket_transition,
)


def _capability(backend_id: str = "backend-a", **overrides: object) -> BackendCapability:
    values: dict[str, object] = {
        "backend_id": backend_id,
        "max_bucket_bytes": 10_000,
        "max_bucket_objects": 100,
    }
    values.update(overrides)
    return BackendCapability(**values)  # type: ignore[arg-type]


def _policy(**overrides: object) -> BucketPolicy:
    values: dict[str, object] = {
        "policy_id": "policy-a",
        "quota_bytes": 1000,
        "quota_objects": 10,
    }
    values.update(overrides)
    return BucketPolicy(**values)  # type: ignore[arg-type]


def _manifest(backend_id: str = "backend-a", name: str = "logs", **overrides: object) -> BucketManifest:
    values: dict[str, object] = {
        "identity_record": BucketIdentity(backend_id, name),
        "policy": _policy(),
        "backend_capability": _capability(backend_id),
        "replicas": (BucketReplica(backend_id, BucketReplicaRole.PRIMARY),),
    }
    values.update(overrides)
    return BucketManifest(**values)  # type: ignore[arg-type]


def test_schema_aliases_and_backend_scoped_identity() -> None:
    assert CONTRACT_VERSION == 1
    assert BucketIdentity_V1.endswith("@1")
    assert BucketCatalog_V1.endswith("@1")
    assert BucketPolicy_V1.endswith("@1")
    assert BucketManifest_V1.endswith("@1")

    left = BucketIdentity("s3-a", "logs", aliases=("archive",))
    right = BucketIdentity("s3-b", "logs", aliases=("archive",))
    assert left != right
    assert left.catalog_key == "s3-a/logs"
    assert right.catalog_key == "s3-b/logs"
    assert left.content_id != right.content_id


def test_canonical_names_and_aliases_are_strict_and_catalog_scoped() -> None:
    with pytest.raises(BucketIdentityError):
        BucketIdentity("backend-a", "Logs")
    with pytest.raises(BucketIdentityError):
        BucketIdentity("backend-a", "logs", aliases=("logs",))
    with pytest.raises(BucketIdentityError):
        BucketIdentity("backend-a", "logs", aliases=("alias", "alias"))

    first = _manifest(name="logs")
    same_backend_alias = _manifest(name="metrics", identity_record=BucketIdentity("backend-a", "metrics", aliases=("logs",)))
    with pytest.raises(BucketCatalogError):
        BucketCatalog("catalog", 1, (first, same_backend_alias))

    other_backend = _manifest("backend-b", "logs")
    catalog = BucketCatalog("catalog", 1, (first, other_backend))
    assert catalog.resolve("backend-a", "logs") is first
    assert catalog.resolve("backend-b", "logs") is other_backend


def test_policy_has_finite_cross_field_invariants() -> None:
    with pytest.raises(BucketPolicyError):
        _policy(retention_mode=RetentionMode.NONE, retention_days=1)
    with pytest.raises(BucketPolicyError):
        _policy(retention_mode=RetentionMode.GOVERNANCE, retention_days=0)
    with pytest.raises(BucketPolicyError):
        _policy(replica_count=2, minimum_verified_replicas=2)
    with pytest.raises(BucketPolicyError):
        _policy(query_mode=QueryMode.CONTENT, query_indexing=False)
    with pytest.raises(BucketPolicyError):
        _policy(query_mode=QueryMode.DISABLED, query_indexing=True)
    with pytest.raises(InconsistentStateError):
        _policy(enforcement_state=PolicyEnforcementState.ENFORCED)


def test_backend_capability_must_satisfy_policy() -> None:
    policy = _policy(
        quota_bytes=5000,
        retention_mode=RetentionMode.GOVERNANCE,
        retention_days=7,
        encryption=EncryptionMode.CUSTOMER_MANAGED,
        tier=StorageTier.ARCHIVE,
        import_formats=(TransferFormat.CAR, TransferFormat.DAG_JSON),
        export_formats=(TransferFormat.DAG_JSON,),
        query_mode=QueryMode.CONTENT,
        query_indexing=True,
    )
    capable = _capability(
        max_bucket_bytes=6000,
        supported_tiers=(StorageTier.HOT, StorageTier.ARCHIVE),
        supported_import_formats=(TransferFormat.CAR, TransferFormat.DAG_JSON),
        supported_export_formats=(TransferFormat.DAG_JSON,),
    )
    assert capable.supports(policy)
    assert_backend_supports_policy(capable, policy)

    insufficient = _capability(max_bucket_bytes=4999)
    assert not insufficient.supports(policy)
    with pytest.raises(BackendCapabilityInsufficientError):
        assert_backend_supports_policy(insufficient, policy)
    with pytest.raises(BackendCapabilityInsufficientError):
        _manifest(policy=policy, backend_capability=insufficient)


def test_exactly_one_primary_and_verified_replica_definition() -> None:
    policy = _policy(replica_count=2, minimum_verified_replicas=1)
    primary = BucketReplica("backend-a", BucketReplicaRole.PRIMARY)
    verified = BucketReplica(
        "backend-b",
        BucketReplicaRole.REPLICA,
        BucketReplicaState.VERIFIED,
        durable=True,
        integrity_verified=True,
    )
    manifest = _manifest(
        policy=policy,
        replicas=(primary, verified),
        lifecycle_state=BucketLifecycleState.ACTIVE,
    )
    assert manifest.primary is primary
    assert verified.is_verified_replica
    assert manifest.verified_replica_count == 1

    with pytest.raises(InconsistentStateError):
        _manifest(policy=policy, replicas=(verified, BucketReplica("backend-c", BucketReplicaRole.REPLICA)))
    with pytest.raises(InconsistentStateError):
        BucketReplica("backend-b", BucketReplicaRole.REPLICA, BucketReplicaState.VERIFIED)
    with pytest.raises(InconsistentStateError):
        _manifest(
            policy=policy,
            replicas=(primary, BucketReplica("backend-b", BucketReplicaRole.REPLICA)),
            lifecycle_state=BucketLifecycleState.ACTIVE,
        )


def test_lifecycle_and_replica_transitions_reject_invalid_edges() -> None:
    assert is_legal_bucket_transition(BucketLifecycleState.PROVISIONING, BucketLifecycleState.ACTIVE)
    assert_legal_bucket_transition(BucketLifecycleState.ACTIVE, BucketLifecycleState.SUSPENDED)
    assert_legal_replica_transition(BucketReplicaState.COPYING, BucketReplicaState.VERIFYING)
    with pytest.raises(InconsistentStateError):
        assert_legal_bucket_transition(BucketLifecycleState.DELETED, BucketLifecycleState.ACTIVE)
    with pytest.raises(InconsistentStateError):
        assert_legal_replica_transition(BucketReplicaState.REMOVED, BucketReplicaState.COPYING)


def test_wire_parsers_reject_unknown_fields_secrets_cycles_and_forged_ids() -> None:
    payload = BucketIdentity("backend-a", "logs").to_record()
    assert BucketIdentity.from_dict(payload) == BucketIdentity("backend-a", "logs")

    with pytest.raises(BucketContractError):
        BucketIdentity.from_dict({"backend_id": "backend-a", "name": "logs", "aliases": (), "surprise": True})
    with pytest.raises(SecretMaterialError):
        BucketIdentity.from_dict({"backend_id": "backend-a", "name": "logs", "aliases": (), "access_token": "x"})
    cyclic: dict[str, object] = {"backend_id": "backend-a", "name": "logs", "aliases": ()}
    cyclic["cycle"] = cyclic
    with pytest.raises(CycleDetectedError):
        BucketIdentity.from_dict(cyclic)
    forged = dict(payload)
    forged["content_id"] = "sha256:not-the-real-identity"
    with pytest.raises(ForgedIdentityError):
        BucketIdentity.from_dict(forged)


def test_nested_contract_wire_records_round_trip_without_class_variables() -> None:
    manifest = _manifest()
    assert BucketPolicy.from_dict(manifest.policy.to_record()) == manifest.policy
    assert BackendCapability.from_dict(manifest.backend_capability.to_record()) == manifest.backend_capability
    assert BucketReplica.from_dict(manifest.primary.to_record()) == manifest.primary
    assert BucketManifest.from_dict(manifest.to_record()) == manifest
    catalog = BucketCatalog("catalog", 1, (manifest,))
    assert BucketCatalog.from_dict(catalog.to_record()) == catalog


def test_configured_policy_manifest_cannot_claim_enforcement() -> None:
    with pytest.raises(InconsistentStateError):
        _manifest(policy_enforcement_state=PolicyEnforcementState.ENFORCED)
