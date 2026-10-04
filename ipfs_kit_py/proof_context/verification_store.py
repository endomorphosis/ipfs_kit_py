"""Kit-owned v0.1 verification receipt and proof persistence (PCCE-013 / ASEH-032).

Production writes go through the inventoried hermetic proof-seal store.
ContextPack receipts share that store, the explicit ContextPack namespace,
and durable generation fencing.  This module does not add a second block
store or WAL; it reuses the existing hermetic, pointer, and WAL surfaces.
Optional IPFS is not required and unavailable is not success.  Accelerator
may only schedule.  Stored receipts prove durability, not semantic admission.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ipfs_kit_py.proof_context.artifacts import (
    ArtifactIdentityError,
    cid_for_bytes,
    get_bytes,
    put_bytes,
)
from ipfs_kit_py.proof_context.state_store import (
    CONTEXT_PACK_INTERFACE,
    CONTEXT_PACK_NAMESPACE,
    ContextPackMasqueradeError,
    ContextPackStore,
    StaleContextPackCasError,
    UnavailableTransportError,
    UnknownFieldError,
    validate_context_pack_record,
)
from ipfs_kit_py.proof_seal_store.contracts import ArtifactKind, ArtifactReference
from ipfs_kit_py.proof_seal_store.local_store import HermeticProofSealStore

INTERFACE = "KitVerificationStore@0.1"
AUTHORITY = "ipfs_kit_py.proof_context.verification_store"


class VerificationStoreError(RuntimeError):
    reason = "invalid"


class StaleWriterError(VerificationStoreError):
    reason = "stale"


class SimulatedArtifactError(VerificationStoreError):
    reason = "simulated"


class KitVerificationStore:
    """Single production writer for v0.1 verification receipts."""

    schema = "ipfs-kit.proof-context.verification-store@0.1"
    interface = INTERFACE
    ipfs_required = False
    context_pack_namespace = CONTEXT_PACK_NAMESPACE
    context_pack_interface = CONTEXT_PACK_INTERFACE

    def __init__(
        self,
        root: str | Path,
        *,
        enable_ipfs: bool = False,
        crash_injector: Callable[..., Any] | None = None,
    ) -> None:
        if enable_ipfs:
            raise UnavailableTransportError(
                "optional IPFS is explicit; unavailable is not a passed write"
            )
        self._root = Path(root)
        self._store = HermeticProofSealStore(self._root)
        self._context_pack = ContextPackStore(
            self._root,
            hermetic_store=self._store,
            crash_injector=crash_injector,
        )

    @property
    def hermetic_store(self) -> HermeticProofSealStore:
        return self._store

    @property
    def context_pack(self) -> ContextPackStore:
        return self._context_pack

    def put_verification_receipt(
        self,
        payload: bytes,
        *,
        claimed_cid: str | None = None,
        provenance: str = "live",
        generation: int | None = None,
        expected_generation: int | None = None,
    ) -> ArtifactReference:
        if provenance == "simulated":
            raise SimulatedArtifactError("simulated receipts cannot be admitted live")
        if payload[:7] == b"sha256:" or payload[:3] == b"Qm":
            raise VerificationStoreError("pseudo-CID payloads are rejected")
        if expected_generation is not None and generation is not None:
            if generation != expected_generation + 1 and generation != expected_generation:
                raise StaleWriterError(
                    f"ABA/stale generation {generation} vs expected {expected_generation}"
                )
        try:
            return put_bytes(
                self._store,
                payload,
                kind=ArtifactKind.PROOF_RECEIPT,
                claimed_cid=claimed_cid,
            )
        except ArtifactIdentityError as exc:
            raise StaleWriterError(str(exc)) from exc

    def get_verification_receipt(self, reference: ArtifactReference) -> bytes:
        return get_bytes(self._store, reference)

    def cid_for(self, payload: bytes) -> str:
        return cid_for_bytes(payload)

    def put_context_pack_verification_receipt(
        self,
        payload: bytes,
        *,
        claimed_cid: str | None = None,
        provenance: str = "live",
        generation: int | None = None,
        expected_generation: int | None = None,
        record: dict[str, Any] | None = None,
    ) -> ArtifactReference:
        """Persist a ContextPack verification receipt.  Durability is not admission."""

        if provenance == "simulated":
            raise SimulatedArtifactError("simulated receipts cannot be admitted live")
        if payload[:7] == b"sha256:" or payload[:3] == b"Qm":
            raise VerificationStoreError("pseudo-CID payloads are rejected")
        if record is not None:
            try:
                closed = validate_context_pack_record(record)
            except UnknownFieldError:
                raise
            except ContextPackMasqueradeError as exc:
                raise VerificationStoreError(str(exc)) from exc
            if closed.get("kind") != ArtifactKind.PROOF_RECEIPT.value:
                raise ContextPackMasqueradeError(
                    "ContextPack verification receipts must use proof_receipt"
                )
            if closed.get("role") == "current":
                raise ContextPackMasqueradeError(
                    "verification receipts cannot masquerade as the current root"
                )
            record_cid = closed.get("cid")
            if record_cid and record_cid != cid_for_bytes(payload):
                raise StaleWriterError("claimed ContextPack receipt CID does not match bytes")
        if expected_generation is not None:
            current = self._context_pack.verification_generation()
            if expected_generation != current:
                raise StaleWriterError(
                    f"ABA/stale generation fence {expected_generation} vs {current}"
                )
        if generation is not None:
            try:
                self._context_pack.put_verification_generation(generation)
            except StaleContextPackCasError as exc:
                raise StaleWriterError(str(exc)) from exc
        try:
            return put_bytes(
                self._store,
                payload,
                kind=ArtifactKind.PROOF_RECEIPT,
                claimed_cid=claimed_cid,
            )
        except ArtifactIdentityError as exc:
            raise StaleWriterError(str(exc)) from exc
        except ContextPackMasqueradeError:
            raise

    def get_context_pack_verification_receipt(
        self, reference: ArtifactReference
    ) -> bytes:
        if reference.kind is not ArtifactKind.PROOF_RECEIPT:
            raise ContextPackMasqueradeError(
                "ContextPack verification get rejects non-receipt kinds"
            )
        return get_bytes(self._store, reference)

    def recover_context_pack(self):
        return self._context_pack.recover()

    def close(self) -> None:
        self._context_pack.close()


def open_verification_store(
    root: str | Path, *, crash_injector: Callable[..., Any] | None = None
) -> KitVerificationStore:
    return KitVerificationStore(root, enable_ipfs=False, crash_injector=crash_injector)
