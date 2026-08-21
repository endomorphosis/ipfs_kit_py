"""PCCE-013: kit verification-store port."""

from __future__ import annotations

from pathlib import Path

import pytest

from ipfs_kit_py.proof_context.state_store import UnavailableTransportError
from ipfs_kit_py.proof_context.verification_store import (
    AUTHORITY,
    KitVerificationStore,
    SimulatedArtifactError,
    StaleWriterError,
    open_verification_store,
)


def test_put_get_roundtrip(tmp_path: Path) -> None:
    store = open_verification_store(tmp_path)
    payload = b'{"kind":"proof_receipt","status":"succeeded"}'
    ref = store.put_verification_receipt(payload)
    assert ref.cid.startswith("b")
    assert store.get_verification_receipt(ref) == payload
    assert AUTHORITY.endswith("verification_store")
    assert store.ipfs_required is False


def test_claimed_cid_mismatch_is_stale(tmp_path: Path) -> None:
    store = open_verification_store(tmp_path)
    with pytest.raises(StaleWriterError):
        store.put_verification_receipt(
            b'{"kind":"proof_receipt"}',
            claimed_cid="b" + "a" * 58,
        )


def test_simulated_is_rejected(tmp_path: Path) -> None:
    store = open_verification_store(tmp_path)
    with pytest.raises(SimulatedArtifactError):
        store.put_verification_receipt(b"{}", provenance="simulated")


def test_generation_aba_fails_closed(tmp_path: Path) -> None:
    store = open_verification_store(tmp_path)
    with pytest.raises(StaleWriterError):
        store.put_verification_receipt(
            b'{"kind":"proof_receipt","g":3}',
            generation=1,
            expected_generation=7,
        )


def test_ipfs_unavailable_is_not_success(tmp_path: Path) -> None:
    with pytest.raises(UnavailableTransportError):
        KitVerificationStore(tmp_path, enable_ipfs=True)
