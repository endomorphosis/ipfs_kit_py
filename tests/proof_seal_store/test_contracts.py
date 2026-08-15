"""Regression tests for kit ProofSealStore contracts (IPS-018).

Acceptance coverage:

* closed kinds exactly cover the required public artifact set;
* proving-key / witness kinds are rejected on public surfaces;
* explicit store roots are mandatory (no home/relative/daemon defaults);
* candidate, admitted, and current roles/types cannot be collapsed;
* protocol surface names the bounded store operations without datasets import.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from ipfs_kit_py.proof_seal_store import (
    ADMITTED_OR_CURRENT_ROLES,
    CONTRACT_VERSION,
    EVIDENCE_SUBSET,
    FORBIDDEN_ARTIFACT_KIND_VALUES,
    REQUIRED_ARTIFACT_KIND_VALUES,
    SCHEMA_VERSION,
    ArtifactKind,
    ArtifactKindError,
    ArtifactReference,
    ArtifactRole,
    CacheCandidate,
    CurrentSealPointer,
    ExplicitRootRequiredError,
    ForbiddenArtifactError,
    ForbiddenArtifactKind,
    ProofSealStore,
    ProofSealStore_V1,
    RoleCollapseError,
    SealTransitionError,
    SealTransitionPhase,
    SealTransitionRecord,
    SealTransitionState,
    StoreRoot,
    admitted_is_not_current,
    assert_not_role_collapse,
    assert_public_artifact_kind,
    assert_roles_disjoint,
    candidate_is_not_admitted,
    closed_artifact_kind_values,
    coerce_artifact_kind,
    current_is_not_candidate,
    ensure_protocol_method_names,
    is_forbidden_artifact_kind,
    kinds_exactly_cover_required,
    validate_explicit_root_path,
)
from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind_V1,
    ArtifactReference_V1,
    CacheCandidate_V1,
    CurrentSealPointer_V1,
    SealTransitionRecord_V1,
    StoreRoot_V1,
)


# Stable plan-required kind set (must match contracts exactly).
_PLAN_REQUIRED_KINDS = frozenset(
    {
        "proof_object",
        "proof_receipt",
        "verification_key",
        "proof_manifest",
        "merkle_node",
        "checkpoint_seal",
        "delta_seal",
        "tombstone",
        "invalidation_record",
    }
)

# CIDv1-like base32 (alphabet a-z2-7 only) and sha256 digests for contract tests.
_SAMPLE_CID = "b" + ("a" * 58)
_SAMPLE_CID_B = "b" + ("c" * 58)
_SAMPLE_SHA = "sha256:" + ("ab" * 32)


# ---------------------------------------------------------------------------
# Schema / closed kinds
# ---------------------------------------------------------------------------


def test_schema_versions_and_interface_aliases() -> None:
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert EVIDENCE_SUBSET == "ips/store-protocol@1"
    assert ArtifactKind_V1.endswith("@1")
    assert ArtifactReference_V1.endswith("@1")
    assert CacheCandidate_V1.endswith("@1")
    assert CurrentSealPointer_V1.endswith("@1")
    assert SealTransitionRecord_V1.endswith("@1")
    assert StoreRoot_V1.endswith("@1")
    assert ProofSealStore_V1.endswith("@1")


def test_closed_kinds_exactly_cover_required_artifacts() -> None:
    assert kinds_exactly_cover_required()
    assert closed_artifact_kind_values() == _PLAN_REQUIRED_KINDS
    assert REQUIRED_ARTIFACT_KIND_VALUES == _PLAN_REQUIRED_KINDS
    assert {kind.value for kind in ArtifactKind} == _PLAN_REQUIRED_KINDS
    assert len(ArtifactKind) == 9
    # No extras, no missing members.
    for value in _PLAN_REQUIRED_KINDS:
        assert ArtifactKind(value).value == value


def test_each_required_kind_coerces_and_is_public() -> None:
    for kind in ArtifactKind:
        assert coerce_artifact_kind(kind) is kind
        assert coerce_artifact_kind(kind.value) is kind
        assert assert_public_artifact_kind(kind.value) is kind
        assert not is_forbidden_artifact_kind(kind)
        assert not is_forbidden_artifact_kind(kind.value)


@pytest.mark.parametrize(
    "forbidden",
    [
        "proving_key",
        "witness",
        "private_witness",
        "witness_material",
        "secret_witness",
        "prover_witness",
        "proving-key",
        "witness-material",
        ForbiddenArtifactKind.PROVING_KEY,
        ForbiddenArtifactKind.WITNESS,
    ],
)
def test_public_api_rejects_proving_key_and_witness(forbidden: object) -> None:
    assert is_forbidden_artifact_kind(forbidden)
    with pytest.raises(ForbiddenArtifactError):
        coerce_artifact_kind(forbidden)
    with pytest.raises(ForbiddenArtifactError):
        assert_public_artifact_kind(forbidden)


def test_unknown_kind_rejected() -> None:
    with pytest.raises(ArtifactKindError):
        coerce_artifact_kind("arbitrary_blob")
    with pytest.raises(ArtifactKindError):
        coerce_artifact_kind("zk_verified")
    assert "proving_key" in FORBIDDEN_ARTIFACT_KIND_VALUES
    assert "proving_key" not in REQUIRED_ARTIFACT_KIND_VALUES


# ---------------------------------------------------------------------------
# Explicit roots
# ---------------------------------------------------------------------------


def test_explicit_root_is_mandatory() -> None:
    with pytest.raises(ExplicitRootRequiredError):
        StoreRoot.require(None)
    with pytest.raises(ExplicitRootRequiredError):
        validate_explicit_root_path(None)
    with pytest.raises(ExplicitRootRequiredError):
        validate_explicit_root_path("")
    with pytest.raises(ExplicitRootRequiredError):
        validate_explicit_root_path("relative/store")
    with pytest.raises(ExplicitRootRequiredError):
        validate_explicit_root_path("./local-store")
    with pytest.raises(ExplicitRootRequiredError):
        validate_explicit_root_path("~/proof-seals")
    with pytest.raises(ExplicitRootRequiredError):
        validate_explicit_root_path("/home/user/.ipfs")
    with pytest.raises(ExplicitRootRequiredError):
        validate_explicit_root_path("/var/lib/.iroh/data")


def test_explicit_absolute_root_accepted(tmp_path: Path) -> None:
    root = StoreRoot.require(tmp_path)
    assert root.root_path == str(tmp_path)
    assert root.path == Path(tmp_path)
    assert StoreRoot.from_dict(root.to_dict()) == root
    # String absolute path also works.
    again = StoreRoot(root_path=str(tmp_path))
    assert again.root_path == str(tmp_path)


# ---------------------------------------------------------------------------
# Role separation: candidate / admitted / current
# ---------------------------------------------------------------------------


def _admitted_ref(kind: ArtifactKind = ArtifactKind.PROOF_OBJECT) -> ArtifactReference:
    return ArtifactReference(cid=_SAMPLE_CID, kind=kind, byte_length=32)


def test_assert_roles_disjoint_and_partitioned() -> None:
    assert_roles_disjoint()
    assert ArtifactRole.CANDIDATE not in ADMITTED_OR_CURRENT_ROLES
    assert {role.value for role in ArtifactRole} == {
        "candidate",
        "admitted",
        "current",
    }
    with pytest.raises(RoleCollapseError):
        assert_not_role_collapse(
            role=ArtifactRole.CANDIDATE, claimed_as=ArtifactRole.ADMITTED
        )
    with pytest.raises(RoleCollapseError):
        assert_not_role_collapse(
            role=ArtifactRole.ADMITTED, claimed_as=ArtifactRole.CURRENT
        )
    with pytest.raises(RoleCollapseError):
        assert_not_role_collapse(
            role=ArtifactRole.CURRENT, claimed_as=ArtifactRole.CANDIDATE
        )
    assert_not_role_collapse(
        role=ArtifactRole.CANDIDATE, claimed_as=ArtifactRole.CANDIDATE
    )


def test_artifact_reference_is_always_admitted() -> None:
    ref = _admitted_ref()
    assert ref.role is ArtifactRole.ADMITTED
    assert admitted_is_not_current(ref)
    assert ref.kind is ArtifactKind.PROOF_OBJECT
    restored = ArtifactReference.from_dict(ref.to_dict())
    assert restored == ref
    with pytest.raises(RoleCollapseError):
        ArtifactReference(
            cid=_SAMPLE_CID,
            kind=ArtifactKind.PROOF_OBJECT,
            role=ArtifactRole.CANDIDATE,
        )
    with pytest.raises(RoleCollapseError):
        ArtifactReference(
            cid=_SAMPLE_CID,
            kind=ArtifactKind.CHECKPOINT_SEAL,
            role=ArtifactRole.CURRENT,
        )
    with pytest.raises(ForbiddenArtifactError):
        ArtifactReference(cid=_SAMPLE_CID, kind="proving_key")


def test_cache_candidate_never_acceptance_authority() -> None:
    candidate = CacheCandidate(
        cache_key="proof-unit-key:v1:abcdef",
        artifact=_admitted_ref(),
    )
    assert candidate.role is ArtifactRole.CANDIDATE
    assert candidate.requires_fresh_verification is True
    assert candidate.is_acceptance_authority is False
    assert candidate_is_not_admitted(candidate)
    assert candidate.cid == _SAMPLE_CID
    restored = CacheCandidate.from_dict(candidate.to_dict())
    assert restored == candidate

    with pytest.raises(RoleCollapseError):
        CacheCandidate(
            cache_key="k",
            artifact=_admitted_ref(),
            role=ArtifactRole.ADMITTED,
        )
    with pytest.raises(RoleCollapseError):
        CacheCandidate(
            cache_key="k",
            artifact=_admitted_ref(),
            role=ArtifactRole.CURRENT,
        )
    with pytest.raises(RoleCollapseError):
        CacheCandidate(
            cache_key="k",
            artifact=_admitted_ref(),
            requires_fresh_verification=False,
        )


def test_current_seal_pointer_is_not_candidate() -> None:
    pointer = CurrentSealPointer(
        repository_id="repo:kit",
        branch_id="main",
        seal_cid=_SAMPLE_CID,
        seal_kind=ArtifactKind.CHECKPOINT_SEAL,
        generation=1,
        parent_seal_cid="",
    )
    assert pointer.role is ArtifactRole.CURRENT
    assert current_is_not_candidate(pointer)
    assert pointer.namespace_key == "repo:kit#main"
    admitted = pointer.as_artifact_reference()
    assert admitted.role is ArtifactRole.ADMITTED
    assert admitted.cid == pointer.seal_cid
    # Projection does not collapse the pointer's role.
    assert pointer.role is ArtifactRole.CURRENT
    restored = CurrentSealPointer.from_dict(pointer.to_dict())
    assert restored == pointer

    with pytest.raises(RoleCollapseError):
        CurrentSealPointer(
            repository_id="repo:kit",
            branch_id="main",
            seal_cid=_SAMPLE_CID,
            seal_kind=ArtifactKind.DELTA_SEAL,
            generation=0,
            role=ArtifactRole.CANDIDATE,
        )
    with pytest.raises(ArtifactKindError):
        CurrentSealPointer(
            repository_id="repo:kit",
            branch_id="main",
            seal_cid=_SAMPLE_CID,
            seal_kind=ArtifactKind.PROOF_OBJECT,
            generation=0,
        )
    with pytest.raises(SealTransitionError):
        CurrentSealPointer(
            repository_id="repo:kit",
            branch_id="main",
            seal_cid=_SAMPLE_CID,
            seal_kind=ArtifactKind.DELTA_SEAL,
            generation=2,
            parent_seal_cid=_SAMPLE_CID,
        )


def test_candidate_admitted_current_types_are_not_interchangeable() -> None:
    ref = _admitted_ref(ArtifactKind.PROOF_RECEIPT)
    candidate = CacheCandidate(cache_key="k1", artifact=ref)
    pointer = CurrentSealPointer(
        repository_id="r",
        branch_id="b",
        seal_cid=_SAMPLE_CID_B,
        seal_kind=ArtifactKind.DELTA_SEAL,
        generation=3,
        parent_seal_cid=_SAMPLE_CID,
    )
    assert type(candidate) is not type(ref)
    assert type(pointer) is not type(ref)
    assert type(pointer) is not type(candidate)
    assert candidate.role is not ref.role
    assert pointer.role is not ref.role
    assert pointer.role is not candidate.role
    # Dict payloads cannot re-label roles.
    payload = candidate.to_dict()
    payload["role"] = ArtifactRole.ADMITTED.value
    with pytest.raises(RoleCollapseError):
        CacheCandidate.from_dict(payload)
    pointer_payload = pointer.to_dict()
    pointer_payload["role"] = ArtifactRole.CANDIDATE.value
    with pytest.raises(RoleCollapseError):
        CurrentSealPointer.from_dict(pointer_payload)


# ---------------------------------------------------------------------------
# Seal transition record
# ---------------------------------------------------------------------------


def test_seal_transition_record_round_trip() -> None:
    record = SealTransitionRecord(
        transition_id="txn:1",
        repository_id="repo:a",
        branch_id="feature",
        phase=SealTransitionPhase.INTENT,
        state=SealTransitionState.OPEN,
        expected_parent_seal_cid=_SAMPLE_CID,
        generation=4,
        artifact_cids=(_SAMPLE_CID_B,),
    )
    assert record.namespace_key == "repo:a#feature"
    restored = SealTransitionRecord.from_dict(record.to_dict())
    assert restored == record


def test_seal_transition_phases_are_closed() -> None:
    values = {phase.value for phase in SealTransitionPhase}
    assert values == {
        "intent",
        "proof_execution",
        "receipt_persistence",
        "forest_update",
        "aggregate_generation",
        "seal_persistence",
        "current_root_cas",
        "cleanup",
    }


def test_committed_transition_requires_seal_binding() -> None:
    with pytest.raises(SealTransitionError):
        SealTransitionRecord(
            transition_id="txn:2",
            repository_id="repo:a",
            branch_id="main",
            phase=SealTransitionPhase.CLEANUP,
            state=SealTransitionState.COMMITTED,
        )
    with pytest.raises(SealTransitionError):
        SealTransitionRecord(
            transition_id="txn:3",
            repository_id="repo:a",
            branch_id="main",
            phase=SealTransitionPhase.INTENT,
            state=SealTransitionState.COMMITTED,
            new_seal_cid=_SAMPLE_CID,
            new_seal_kind=ArtifactKind.CHECKPOINT_SEAL,
        )
    ok = SealTransitionRecord(
        transition_id="txn:4",
        repository_id="repo:a",
        branch_id="main",
        phase=SealTransitionPhase.CURRENT_ROOT_CAS,
        state=SealTransitionState.COMMITTED,
        new_seal_cid=_SAMPLE_CID,
        new_seal_kind=ArtifactKind.CHECKPOINT_SEAL,
        generation=1,
    )
    assert ok.new_seal_kind is ArtifactKind.CHECKPOINT_SEAL


def test_transition_rejects_duplicate_artifact_cids_and_forbidden_kinds() -> None:
    with pytest.raises(SealTransitionError):
        SealTransitionRecord(
            transition_id="txn:5",
            repository_id="repo:a",
            branch_id="main",
            phase=SealTransitionPhase.RECEIPT_PERSISTENCE,
            state=SealTransitionState.IN_PROGRESS,
            artifact_cids=(_SAMPLE_CID, _SAMPLE_CID),
        )
    with pytest.raises(ForbiddenArtifactError):
        SealTransitionRecord(
            transition_id="txn:6",
            repository_id="repo:a",
            branch_id="main",
            phase=SealTransitionPhase.SEAL_PERSISTENCE,
            state=SealTransitionState.IN_PROGRESS,
            new_seal_cid=_SAMPLE_CID,
            new_seal_kind="witness",
        )


# ---------------------------------------------------------------------------
# Protocol surface
# ---------------------------------------------------------------------------


def test_proof_seal_store_protocol_method_surface() -> None:
    names = ensure_protocol_method_names()
    assert names == {
        "root",
        "put_immutable",
        "get_verified_bytes",
        "lookup_candidate",
        "get_current_seal",
        "compare_and_swap_current_seal",
        "begin_transition",
    }

    class _Stub:
        @property
        def root(self) -> StoreRoot:
            return StoreRoot(root_path="/tmp/proof-seal-store-test-root")

        def put_immutable(self, kind, data, *, claimed_cid=None):
            return ArtifactReference(
                cid=_SAMPLE_CID, kind=kind, byte_length=len(data)
            )

        def get_verified_bytes(self, reference):
            return b""

        def lookup_candidate(self, cache_key):
            return None

        def get_current_seal(self, repository_id, branch_id):
            return None

        def compare_and_swap_current_seal(self, expected, new_pointer):
            return False

        def begin_transition(self, record):
            return record

    assert isinstance(_Stub(), ProofSealStore)


def test_package_exports_and_cold_import_avoids_datasets() -> None:
    # Fresh import path must not pull datasets.
    before = {name for name in sys.modules if name.startswith("ipfs_datasets")}
    module = importlib.import_module("ipfs_kit_py.proof_seal_store")
    after = {name for name in sys.modules if name.startswith("ipfs_datasets")}
    assert after == before
    assert module.ArtifactKind is ArtifactKind
    assert module.ProofSealStore is ProofSealStore
    assert module.kinds_exactly_cover_required()
    # CID sample used by records is accepted.
    ArtifactReference(cid=_SAMPLE_SHA, kind=ArtifactKind.MERKLE_NODE)


def test_cid_validation_rejects_legacy_pseudo_cids() -> None:
    with pytest.raises(Exception):
        ArtifactReference(cid="QmTest0123456789abcdef", kind=ArtifactKind.PROOF_OBJECT)
    with pytest.raises(Exception):
        ArtifactReference(cid="not-a-cid", kind=ArtifactKind.PROOF_OBJECT)
