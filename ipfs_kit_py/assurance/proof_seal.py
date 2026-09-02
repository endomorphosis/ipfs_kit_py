"""Hermetic proof-seal store qualification surface (PCPR-024).

Composes the current-head kit proof-seal store: exact-byte local objects,
candidate cache index, current-seal CAS, WAL, recovery, and integrity-only
legacy-certificate staging. This adapter is not a mock, not a live IPFS
transport, not a proof-validity authority, and not a closed PCPR release.

Fail-closed invariants:

* the adapter is hermetic: it never claims live IPFS, CLI, MCP, or MCP++
  support;
* injected or simulated backends cannot mint live qualification;
* public proving-key and witness material is rejected and never persisted;
* cache candidates always require fresh verification and never collapse into
  current-seal authority;
* secret-bearing configuration is rejected without retention;
* kit never decides proof validity, reuse, or admission.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from ipfs_kit_py.core.operation_contracts import (
    ErrorCategory,
    ErrorCode,
    OperationState,
    Retryability,
    StorageError,
)
from ipfs_kit_py.proof_seal_store import (
    LegacyBlobStagingRecord,
    stage_legacy_certificate_blob,
)
from ipfs_kit_py.proof_seal_store.cache_index import ProofCacheIndex
from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    ArtifactReference,
    CacheCandidate,
    CurrentSealPointer,
    ForbiddenArtifactError,
    ProofSealStoreContractError,
    SealTransitionRecord,
    StoreRoot,
    coerce_artifact_kind,
    validate_explicit_root_path,
)
from ipfs_kit_py.proof_seal_store.local_store import HermeticProofSealStore
from ipfs_kit_py.proof_seal_store.pointer import CurrentSealRepository
from ipfs_kit_py.proof_seal_store.recovery import recover_seal_transitions
from ipfs_kit_py.proof_seal_store.wal import SealTransitionWal


SCHEMA: Final = "ipfs_kit_py/assurance/proof-seal-store@1"
INTERFACE: Final = "HermeticProofSealQualificationSurface@1"
BACKEND_ID: Final = "proof_seal_store"
CERTIFICATION_SCOPE: Final = (
    "pcpr-024-proof-seal-store-hermetic; not a closed PCPR release"
)
SUPPORT_CLASS: Final = "hermetic_qualified"
LIVE_SUPPORT_CLAIM: Final = False
REPOSITORY_ID: Final = "repo:pcpr-024"
BRANCH_ID: Final = "main"

_SECRET_KEY_FRAGMENTS: Final[tuple[str, ...]] = (
    "secret",
    "token",
    "password",
    "credential",
    "authorization",
    "api_key",
    "private_key",
    "bearer",
    "witness",
    "proving_key",
)


class ProofSealSurfaceError(RuntimeError):
    """Typed proof-seal surface failure carrying a StorageError."""

    def __init__(self, error: StorageError) -> None:
        self.error = error
        super().__init__(error.message)


def _raise(
    code: ErrorCode,
    category: ErrorCategory,
    message: str,
    *,
    state: OperationState = OperationState.FAILED,
    retryability: Retryability = Retryability.NEVER,
) -> None:
    raise ProofSealSurfaceError(
        StorageError(
            code=code,
            category=category,
            message=message,
            retryability=retryability,
            state=state,
        )
    )


def _reject_secret_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if any(part in normalized for part in _SECRET_KEY_FRAGMENTS):
                _raise(
                    ErrorCode.SECRET_MATERIAL,
                    ErrorCategory.AUTHORIZATION,
                    "secret-bearing configuration is forbidden",
                    state=OperationState.REJECTED,
                )
            _reject_secret_keys(nested)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for nested in value:
            _reject_secret_keys(nested)


class HermeticProofSealQualificationSurface:
    """Compose the current-head hermetic proof-seal store under one root.

    ``live_provider`` is False. Hermetic results cannot mint live qualification
    or a closed PCPR release.
    """

    __test__ = False
    backend_id: Final[str] = BACKEND_ID
    schema: Final[str] = SCHEMA
    interface: Final[str] = INTERFACE
    certification_scope: Final[str] = CERTIFICATION_SCOPE
    support_class: Final[str] = SUPPORT_CLASS
    live_support_claim: Final[bool] = LIVE_SUPPORT_CLAIM
    production_authorized: Final[bool] = False
    is_hermetic: Final[bool] = True
    live_provider: Final[bool] = False
    simulated: Final[bool] = False

    def __init__(
        self,
        root: StoreRoot | str | Path | None,
        *,
        configuration: Mapping[str, Any] | None = None,
        create: bool = True,
    ) -> None:
        if configuration:
            _reject_secret_keys(configuration)
        if root is None:
            raise ProofSealStoreContractError(
                "HermeticProofSealQualificationSurface requires an explicit root"
            )
        if isinstance(root, StoreRoot):
            store_root = root
        else:
            store_root = StoreRoot.require(root)
        validate_explicit_root_path(store_root.root_path, field_name="root_path")
        self._root = store_root
        self._root_path = Path(store_root.root_path)
        self._root_path.mkdir(parents=True, exist_ok=create)
        self.objects = HermeticProofSealStore(self._root, create=create)
        self.index = ProofCacheIndex(self._root, create=create)
        self.pointers = CurrentSealRepository(self._root, create=create)
        self.wal = SealTransitionWal(self._root, create=create)

    @property
    def root(self) -> StoreRoot:
        return self._root

    @property
    def root_path(self) -> Path:
        return self._root_path

    @classmethod
    def reopen(cls, root: StoreRoot | str | Path) -> HermeticProofSealQualificationSurface:
        return cls(root, create=True)

    def put_immutable(
        self,
        kind: ArtifactKind | str,
        data: bytes,
        *,
        claimed_cid: str | None = None,
    ) -> ArtifactReference:
        closed = coerce_artifact_kind(kind, field_name="kind")
        return self.objects.put_immutable(closed, data, claimed_cid=claimed_cid)

    def get_verified_bytes(self, reference: ArtifactReference) -> bytes:
        return self.objects.get_verified_bytes(reference)

    def lookup_candidate(self, cache_key: str) -> CacheCandidate | None:
        return self.index.lookup_candidate(cache_key)

    def get_current_seal(
        self, repository_id: str = REPOSITORY_ID, branch_id: str = BRANCH_ID
    ) -> CurrentSealPointer | None:
        return self.pointers.get_current_seal(repository_id, branch_id)

    def compare_and_swap_current_seal(
        self,
        expected: CurrentSealPointer | None,
        new_pointer: CurrentSealPointer,
    ) -> bool:
        return self.pointers.compare_and_swap_current_seal(expected, new_pointer)

    def begin_transition(self, record: SealTransitionRecord) -> SealTransitionRecord:
        return self.wal.begin_transition(record)

    def recover(self) -> Any:
        return recover_seal_transitions(
            self._root,
            wal=self.wal,
            store=self.objects,
            pointers=self.pointers,
        )

    def stage_legacy_blob(
        self,
        data: bytes,
        *,
        claimed_cid: str | None = None,
        claimed_kind: str | None = None,
    ) -> LegacyBlobStagingRecord:
        return stage_legacy_certificate_blob(
            self._root_path,
            data,
            claimed_cid=claimed_cid,
            claimed_kind=claimed_kind,
        )

    def reject_forbidden_kind(self, kind: str) -> None:
        try:
            coerce_artifact_kind(kind, field_name="kind")
        except ForbiddenArtifactError:
            return
        _raise(
            ErrorCode.FORBIDDEN,
            ErrorCategory.AUTHORIZATION,
            "forbidden proving-key or witness kind was not rejected",
            state=OperationState.REJECTED,
        )

    def close(self) -> None:
        try:
            self.wal.close()
        except Exception:
            pass


__all__ = [
    "SCHEMA",
    "INTERFACE",
    "BACKEND_ID",
    "CERTIFICATION_SCOPE",
    "SUPPORT_CLASS",
    "LIVE_SUPPORT_CLAIM",
    "REPOSITORY_ID",
    "BRANCH_ID",
    "ProofSealSurfaceError",
    "HermeticProofSealQualificationSurface",
]
