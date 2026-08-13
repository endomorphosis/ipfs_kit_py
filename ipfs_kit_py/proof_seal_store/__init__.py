"""Hermetic proof-seal storage authority for kit (IPS-018+ / IPS-027).

Cold import is inert: closed contracts and the ``ProofSealStore`` protocol are
imported immediately.  Local store, transport, cache index, forest, pointer,
WAL, and recovery implementations resolve lazily and never open a network,
daemon, or user-state path on import.

Legacy ``proof_certificate_store`` blobs may be staged as exact bytes.  Staging
is not admission and is not reuse authority — accelerate must verify before a
candidate may enter the index.

Kit never decides proof validity, execution success, or reuse acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ipfs_kit_py.proof_seal_store.contracts import (
    ADMITTED_ARTIFACT_KINDS,
    ADMITTED_OR_CURRENT_ROLES,
    ARTIFACT_REFERENCE_SCHEMA,
    ARTIFACT_ROLES,
    CANDIDATE_ARTIFACT_KINDS,
    CACHE_CANDIDATE_SCHEMA,
    CONTRACT_VERSION,
    CURRENT_SEAL_POINTER_SCHEMA,
    DEFAULT_MAX_ARTIFACT_BYTES,
    EVIDENCE_SUBSET,
    FORBIDDEN_ARTIFACT_KIND_VALUES,
    MAX_ARTIFACT_BYTES_BOUND,
    PROOF_SEAL_STORE_NAMESPACE,
    PROOF_SEAL_STORE_PROTOCOL_SCHEMA,
    REQUIRED_ARTIFACT_KINDS,
    REQUIRED_ARTIFACT_KIND_VALUES,
    SEAL_ARTIFACT_KINDS,
    SEAL_TRANSITION_PHASES,
    SEAL_TRANSITION_RECORD_SCHEMA,
    SCHEMA_VERSION,
    STORE_ROOT_SCHEMA,
    ArtifactKind,
    ArtifactKindError,
    ArtifactKind_V1,
    ArtifactReference,
    ArtifactReference_V1,
    ArtifactRole,
    CacheCandidate,
    CacheCandidate_V1,
    CurrentSealPointer,
    CurrentSealPointer_V1,
    ExplicitRootRequiredError,
    ForbiddenArtifactError,
    ForbiddenArtifactKind,
    ProofSealStore,
    ProofSealStoreContractError,
    ProofSealStore_V1,
    RoleCollapseError,
    SealTransitionError,
    SealTransitionPhase,
    SealTransitionRecord,
    SealTransitionRecord_V1,
    SealTransitionState,
    StoreGetDisposition,
    StorePutDisposition,
    StoreRoot,
    StoreRoot_V1,
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
    reject_if_forbidden_kind,
    validate_explicit_root_path,
)

PUBLIC_ADAPTER_SUBSET = "ips/kit-public-adapter@1"
MIGRATION_SUBSET = "ips/kit-migration@1"

_IMPLEMENTATION_EXPORTS: dict[str, tuple[str, str]] = {
    "HermeticProofSealStore": (".local_store", "HermeticProofSealStore"),
    "IpfsProofArtifactTransport": (".ipfs_transport", "IpfsProofArtifactTransport"),
    "ProofCacheIndex": (".cache_index", "ProofCacheIndex"),
    "ProofForestStore": (".forest", "ProofForestStore"),
    "CurrentSealRepository": (".pointer", "CurrentSealRepository"),
    "SealTransitionWal": (".wal", "SealTransitionWal"),
    "recover_seal_transitions": (".recovery", "recover_seal_transitions"),
    "RecoveryDisposition": (".recovery", "RecoveryDisposition"),
    "stage_legacy_certificate_blob": (__name__, "stage_legacy_certificate_blob"),
    "LegacyBlobStagingRecord": (__name__, "LegacyBlobStagingRecord"),
    "PUBLIC_ADAPTER_SUBSET": (__name__, "PUBLIC_ADAPTER_SUBSET"),
    "MIGRATION_SUBSET": (__name__, "MIGRATION_SUBSET"),
}


@dataclass(frozen=True)
class LegacyBlobStagingRecord:
    """Integrity-only staging of a legacy certificate blob.

    ``staged`` means exact bytes were persisted under a rehashed CID.
    ``admitted`` and ``accepted`` stay false: accelerate must verify before
    the bytes may enter the candidate index or become a current seal.
    """

    cid: str
    byte_length: int
    staged: bool
    requires_accelerate_verification: bool = True
    admitted: bool = False
    accepted: bool = False
    schema: str = "ipfs_kit_py/proof_seal_store/legacy-blob-staging@1"


def stage_legacy_certificate_blob(
    root: Any,
    data: bytes,
    *,
    claimed_cid: str | None = None,
    claimed_kind: str | None = None,
) -> LegacyBlobStagingRecord:
    """Stage exact-byte legacy blobs without admitting them as proof artifacts.

    Uses ``proof_certificate_store`` as integrity transport only.  Forbidden
    proving-key / witness kinds are rejected.  The result never authorizes
    reuse or current-seal publication.
    """

    if claimed_kind is not None and is_forbidden_artifact_kind(claimed_kind):
        raise ForbiddenArtifactError(
            "proving-key and witness material cannot be staged on the public adapter"
        )
    if type(data) is not bytes:
        raise ProofSealStoreContractError("legacy blob payload must be exact bytes")
    from ipfs_kit_py.proof_certificate_store import IpfsKitProofCertificateStore

    transport = IpfsKitProofCertificateStore(root)
    put = transport.put_bytes(data, claimed_cid=claimed_cid)
    if not getattr(put, "stored", False):
        raise ProofSealStoreContractError(
            f"legacy blob staging failed: {getattr(put, 'reason_code', put)}"
        )
    return LegacyBlobStagingRecord(
        cid=put.cid,
        byte_length=len(data),
        staged=True,
        requires_accelerate_verification=True,
        admitted=False,
        accepted=False,
    )


def __getattr__(name: str) -> Any:
    """Resolve implementation adapters on demand without eager side effects."""

    try:
        module_name, attr_name = _IMPLEMENTATION_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    if module_name == __name__:
        return globals()[attr_name]
    from importlib import import_module

    module = import_module(module_name, package=__name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


__all__ = [
    "ADMITTED_ARTIFACT_KINDS",
    "ADMITTED_OR_CURRENT_ROLES",
    "ARTIFACT_REFERENCE_SCHEMA",
    "ARTIFACT_ROLES",
    "CANDIDATE_ARTIFACT_KINDS",
    "CACHE_CANDIDATE_SCHEMA",
    "CONTRACT_VERSION",
    "CURRENT_SEAL_POINTER_SCHEMA",
    "DEFAULT_MAX_ARTIFACT_BYTES",
    "EVIDENCE_SUBSET",
    "FORBIDDEN_ARTIFACT_KIND_VALUES",
    "MAX_ARTIFACT_BYTES_BOUND",
    "PROOF_SEAL_STORE_NAMESPACE",
    "PROOF_SEAL_STORE_PROTOCOL_SCHEMA",
    "REQUIRED_ARTIFACT_KINDS",
    "REQUIRED_ARTIFACT_KIND_VALUES",
    "SEAL_ARTIFACT_KINDS",
    "SEAL_TRANSITION_PHASES",
    "SEAL_TRANSITION_RECORD_SCHEMA",
    "SCHEMA_VERSION",
    "STORE_ROOT_SCHEMA",
    "ArtifactKind",
    "ArtifactKindError",
    "ArtifactKind_V1",
    "ArtifactReference",
    "ArtifactReference_V1",
    "ArtifactRole",
    "CacheCandidate",
    "CacheCandidate_V1",
    "CurrentSealPointer",
    "CurrentSealPointer_V1",
    "ExplicitRootRequiredError",
    "ForbiddenArtifactError",
    "ForbiddenArtifactKind",
    "ProofSealStore",
    "ProofSealStoreContractError",
    "ProofSealStore_V1",
    "RoleCollapseError",
    "SealTransitionError",
    "SealTransitionPhase",
    "SealTransitionRecord",
    "SealTransitionRecord_V1",
    "SealTransitionState",
    "StoreGetDisposition",
    "StorePutDisposition",
    "StoreRoot",
    "StoreRoot_V1",
    "admitted_is_not_current",
    "assert_not_role_collapse",
    "assert_public_artifact_kind",
    "assert_roles_disjoint",
    "candidate_is_not_admitted",
    "closed_artifact_kind_values",
    "coerce_artifact_kind",
    "current_is_not_candidate",
    "ensure_protocol_method_names",
    "is_forbidden_artifact_kind",
    "kinds_exactly_cover_required",
    "reject_if_forbidden_kind",
    "validate_explicit_root_path",
    "PUBLIC_ADAPTER_SUBSET",
    "MIGRATION_SUBSET",
    "HermeticProofSealStore",
    "IpfsProofArtifactTransport",
    "ProofCacheIndex",
    "ProofForestStore",
    "CurrentSealRepository",
    "SealTransitionWal",
    "recover_seal_transitions",
    "RecoveryDisposition",
    "stage_legacy_certificate_blob",
    "LegacyBlobStagingRecord",
]
