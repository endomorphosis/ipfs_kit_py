"""Kit persistence adapter for incremental seals (PCCE-014)."""

from __future__ import annotations

from pathlib import Path

from ipfs_kit_py.proof_context.artifacts import cid_for_bytes, get_bytes, put_bytes
from ipfs_kit_py.proof_context.verification_store import (
    SimulatedArtifactError,
    StaleWriterError,
)
from ipfs_kit_py.proof_seal_store.contracts import ArtifactKind, ArtifactReference
from ipfs_kit_py.proof_seal_store.local_store import HermeticProofSealStore

INTERFACE = "KitIncrementalSealStore@0.1"


class IncrementalSealStore:
    """Persist checkpoint/delta seals through the hermetic store only."""

    interface = INTERFACE

    def __init__(self, root: str | Path) -> None:
        self._store = HermeticProofSealStore(root)

    def put_seal(
        self,
        payload: bytes,
        *,
        kind: ArtifactKind | str = ArtifactKind.CHECKPOINT_SEAL,
        claimed_cid: str | None = None,
        provenance: str = "live",
        parent_cid: str | None = None,
        expected_parent_cid: str | None = None,
    ) -> ArtifactReference:
        if provenance == "simulated":
            raise SimulatedArtifactError("simulated seals cannot be admitted")
        if expected_parent_cid is not None and parent_cid != expected_parent_cid:
            raise StaleWriterError("wrong parent seal cannot be admitted")
        return put_bytes(self._store, payload, kind=kind, claimed_cid=claimed_cid)

    def get_seal(self, reference: ArtifactReference) -> bytes:
        return get_bytes(self._store, reference)

    def cid_for(self, payload: bytes) -> str:
        return cid_for_bytes(payload)


def open_incremental_seal_store(root: str | Path) -> IncrementalSealStore:
    return IncrementalSealStore(root)
