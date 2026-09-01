"""Kit persistence adapter for incremental seals (PCCE-014 / ASEH-032).

ContextPack seals reuse the hermetic store, WAL, and current-root CAS under
the explicit ContextPack namespace.  Candidate seals never auto-publish.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ipfs_kit_py.proof_context.artifacts import cid_for_bytes, get_bytes, put_bytes
from ipfs_kit_py.proof_context.state_store import (
    CONTEXT_PACK_INTERFACE,
    CONTEXT_PACK_NAMESPACE,
    ContextPackMasqueradeError,
    ContextPackStore,
    StaleContextPackCasError,
)
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
    context_pack_namespace = CONTEXT_PACK_NAMESPACE
    context_pack_interface = CONTEXT_PACK_INTERFACE

    def __init__(
        self,
        root: str | Path,
        *,
        crash_injector: Callable[..., Any] | None = None,
    ) -> None:
        self._root = Path(root)
        self._store = HermeticProofSealStore(self._root)
        self._context_pack = ContextPackStore(
            self._root, hermetic_store=self._store, crash_injector=crash_injector
        )

    @property
    def context_pack(self) -> ContextPackStore:
        return self._context_pack

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

    def put_context_pack_candidate_seal(
        self,
        payload: bytes,
        *,
        cache_key: str | None = None,
        kind: ArtifactKind | str | None = None,
        claimed_cid: str | None = None,
        parent_cid: str = "",
        generation: int = 0,
    ) -> ArtifactReference:
        """Admit a ContextPack seal candidate without publishing the current root."""

        try:
            return self._context_pack.put_candidate(
                payload,
                cache_key=cache_key,
                kind=kind,
                claimed_cid=claimed_cid,
                parent_cid=parent_cid,
                generation=generation,
            )
        except ContextPackMasqueradeError:
            raise
        except StaleContextPackCasError as exc:
            raise StaleWriterError(str(exc)) from exc

    def publish_context_pack_seal(
        self,
        payload: bytes,
        *,
        kind: ArtifactKind | str | None = None,
        claimed_cid: str | None = None,
        expected_parent_cid: str | None = None,
        generation: int | None = None,
        cache_key: str | None = None,
        branch_id: str = "current",
    ) -> ArtifactReference:
        """Persist a ContextPack seal and CAS-publish it as the current root."""

        parent = expected_parent_cid or ""
        closed_kind = kind
        reference = self._context_pack.put_candidate(
            payload,
            cache_key=cache_key,
            kind=closed_kind,
            claimed_cid=claimed_cid,
            parent_cid=parent,
            generation=generation or 0,
            branch_id=branch_id,
        )
        try:
            pointer = self._context_pack.compare_and_swap_current_root(
                new_cid=reference.cid,
                expected_parent_cid=parent,
                generation=generation,
                kind=reference.kind,
                branch_id=branch_id,
            )
        except StaleContextPackCasError as exc:
            raise StaleWriterError(str(exc)) from exc
        if pointer.seal_cid != reference.cid:
            raise StaleWriterError("published ContextPack seal CID mismatch")
        return reference

    def recover_context_pack_seals(self):
        return self._context_pack.recover()

    def close(self) -> None:
        self._context_pack.close()


def open_incremental_seal_store(
    root: str | Path, *, crash_injector: Callable[..., Any] | None = None
) -> IncrementalSealStore:
    return IncrementalSealStore(root, crash_injector=crash_injector)
