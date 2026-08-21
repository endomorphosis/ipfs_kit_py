"""PCCE-014: kit incremental-seal persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from ipfs_kit_py.proof_context.incremental_seal_store import open_incremental_seal_store
from ipfs_kit_py.proof_context.verification_store import (
    SimulatedArtifactError,
    StaleWriterError,
)
from ipfs_kit_py.proof_seal_store.contracts import ArtifactKind


def test_put_get_checkpoint_seal(tmp_path: Path) -> None:
    store = open_incremental_seal_store(tmp_path)
    payload = b'{"kind":"checkpoint_seal","parent":null}'
    ref = store.put_seal(payload, kind=ArtifactKind.CHECKPOINT_SEAL)
    assert store.get_seal(ref) == payload
    assert ref.cid.startswith("b")


def test_wrong_parent_fails_closed(tmp_path: Path) -> None:
    store = open_incremental_seal_store(tmp_path)
    with pytest.raises(StaleWriterError):
        store.put_seal(
            b'{"kind":"delta_seal"}',
            kind=ArtifactKind.DELTA_SEAL,
            parent_cid="b" + "a" * 58,
            expected_parent_cid="b" + "c" * 58,
        )


def test_simulated_seal_rejected(tmp_path: Path) -> None:
    store = open_incremental_seal_store(tmp_path)
    with pytest.raises(SimulatedArtifactError):
        store.put_seal(b"{}", provenance="simulated")
