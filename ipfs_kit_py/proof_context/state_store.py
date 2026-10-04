"""Hermetic kit v0.1 state/receipt/proof-forest port."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ipfs_kit_py.proof_context.artifacts import cid_for_bytes, get_bytes, put_bytes
from ipfs_kit_py.proof_seal_store.local_store import HermeticProofSealStore

PORT_SCHEMA = "ipfs-kit.proof-context.v0.1"
PORT_INTERFACE = "KitProofContextStateStore@0.1"


class UnavailableTransportError(RuntimeError):
    """Optional IPFS transport is not admitted as a passed capability."""


class KitProofContextStateStore:
    """Single durable v0.1 port over the inventoried hermetic store."""

    schema = PORT_SCHEMA
    interface = PORT_INTERFACE
    ipfs_required = False

    def __init__(self, root: str | Path, *, enable_ipfs: bool = False) -> None:
        if enable_ipfs:
            raise UnavailableTransportError(
                "optional IPFS transport is explicit and unavailable is not success"
            )
        self._root = Path(root)
        self._store = HermeticProofSealStore(self._root)
        self._forest = None

    @property
    def root(self) -> Path:
        return self._root

    @property
    def hermetic_store(self) -> HermeticProofSealStore:
        return self._store

    @property
    def forest(self) -> Any:
        if self._forest is None:
            try:
                from ipfs_kit_py.proof_seal_store.forest import ProofForestStore
            except ModuleNotFoundError as exc:
                raise UnavailableTransportError(
                    "proof-forest codec requires installed datasets; unavailable is not success"
                ) from exc
            self._forest = ProofForestStore(self._root, object_store=self._store)
        return self._forest

    def put(self, data: bytes, *, claimed_cid: str | None = None) -> ArtifactReference:
        return put_bytes(self._store, data, claimed_cid=claimed_cid)

    def get(self, reference: ArtifactReference) -> bytes:
        return get_bytes(self._store, reference)

    def cid_for(self, data: bytes) -> str:
        return cid_for_bytes(data)


def open_local_store(root: str | Path) -> KitProofContextStateStore:
    return KitProofContextStateStore(root, enable_ipfs=False)


def reject_default_root() -> None:
    HermeticProofSealStore(None)
