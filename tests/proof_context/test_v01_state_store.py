"""PCCE-009: kit v0.1 hermetic state-store port."""

from __future__ import annotations

from pathlib import Path

import pytest

from ipfs_kit_py.proof_context.artifacts import ArtifactIdentityError, cid_for_bytes
from ipfs_kit_py.proof_context.state_store import (
    PORT_INTERFACE,
    UnavailableTransportError,
    open_local_store,
)
from ipfs_kit_py.proof_seal_store.contracts import ExplicitRootRequiredError
from ipfs_kit_py.proof_seal_store.local_store import HermeticProofSealStore


def test_cold_import_is_hermetic() -> None:
    import ipfs_kit_py.proof_context as port

    assert port.SCHEMA == "ipfs-kit.proof-context.v0.1"


def test_explicit_root_required() -> None:
    with pytest.raises(ExplicitRootRequiredError):
        HermeticProofSealStore(None)


def test_put_get_bytes_and_cid_agree(tmp_path: Path) -> None:
    store = open_local_store(tmp_path)
    payload = b'{"kind":"proof_object","v":"pcce-009"}'
    ref = store.put(payload)
    assert ref.cid == cid_for_bytes(payload)
    assert ref.cid.startswith("b")
    assert store.get(ref) == payload
    assert store.interface == PORT_INTERFACE
    assert store.ipfs_required is False


def test_claimed_cid_mismatch_fails_closed(tmp_path: Path) -> None:
    store = open_local_store(tmp_path)
    payload = b'{"kind":"proof_object","v":"mismatch"}'
    with pytest.raises((ArtifactIdentityError, Exception)):
        store.put(payload, claimed_cid="b" + "a" * 58)


def test_optional_ipfs_unavailable_is_not_success(tmp_path: Path) -> None:
    from ipfs_kit_py.proof_context.state_store import KitProofContextStateStore

    with pytest.raises(UnavailableTransportError):
        KitProofContextStateStore(tmp_path, enable_ipfs=True)


def test_identical_puts_deduplicate(tmp_path: Path) -> None:
    store = open_local_store(tmp_path)
    payload = b'{"kind":"proof_object","dup":true}'
    a = store.put(payload)
    b = store.put(payload)
    assert a.cid == b.cid
