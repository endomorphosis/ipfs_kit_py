"""Immutable artifact helpers for the kit v0.1 port."""

from __future__ import annotations

from typing import Any

from ipfs_kit_py.proof_seal_store.contracts import ArtifactKind, ArtifactReference
from ipfs_kit_py.proof_seal_store.local_store import (
    HermeticProofSealStore,
    LocalStoreError,
    content_cid_for_bytes,
)


class ArtifactIdentityError(RuntimeError):
    """Bytes and authoritative CID disagree."""


def cid_for_bytes(data: bytes) -> str:
    cid = content_cid_for_bytes(data)
    if not cid.startswith("b"):
        raise ArtifactIdentityError("kit v0.1 requires CIDv1 base32, not a pseudo-CID")
    return cid


def put_bytes(
    store: HermeticProofSealStore,
    data: bytes,
    *,
    kind: ArtifactKind | str = ArtifactKind.PROOF_OBJECT,
    claimed_cid: str | None = None,
) -> ArtifactReference:
    if claimed_cid is not None and claimed_cid != cid_for_bytes(data):
        raise ArtifactIdentityError("claimed CID does not match artifact bytes")
    return store.put_immutable(kind, data, claimed_cid=claimed_cid)


def get_bytes(store: HermeticProofSealStore, reference: ArtifactReference) -> bytes:
    data = store.get_verified_bytes(reference)
    actual = cid_for_bytes(data)
    if actual != reference.cid:
        raise ArtifactIdentityError("stored bytes do not match reference CID")
    return data
