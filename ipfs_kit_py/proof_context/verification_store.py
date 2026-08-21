"""Kit-owned v0.1 verification receipt and proof persistence (PCCE-013).

Production writes go through the inventoried hermetic proof-seal store.
This module does not add a second block store or WAL. Optional IPFS is
not required and unavailable is not success. Accelerator may only schedule.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ipfs_kit_py.proof_context.artifacts import (
    ArtifactIdentityError,
    cid_for_bytes,
    get_bytes,
    put_bytes,
)
from ipfs_kit_py.proof_context.state_store import (
    PORT_INTERFACE,
    UnavailableTransportError,
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

    def __init__(self, root: str | Path, *, enable_ipfs: bool = False) -> None:
        if enable_ipfs:
            raise UnavailableTransportError(
                "optional IPFS is explicit; unavailable is not a passed write"
            )
        self._root = Path(root)
        self._store = HermeticProofSealStore(self._root)

    @property
    def hermetic_store(self) -> HermeticProofSealStore:
        return self._store

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


def open_verification_store(root: str | Path) -> KitVerificationStore:
    return KitVerificationStore(root, enable_ipfs=False)
