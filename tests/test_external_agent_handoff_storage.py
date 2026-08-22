"""Kit-local focused tests for EAAEF-011 encrypted raw-export storage."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
if str(KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(KIT_ROOT))

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from external_agent_handoff.storage import (
    ENCRYPTION_ALGORITHM,
    EncryptedExportStore,
    HandoffStorageError,
    digest_sha256,
)


PLAINTEXT = b'{"session":"codex-export","messages":[{"role":"user","text":"secret transcript"}]}'
EVENT_A = "sha256:" + ("a" * 64)
EVENT_B = "sha256:" + ("b" * 64)


@pytest.fixture
def store(tmp_path: Path) -> EncryptedExportStore:
    return EncryptedExportStore(tmp_path / "handoff-store")


@pytest.fixture
def master_key() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def test_roundtrip_and_public_receipt(store: EncryptedExportStore, master_key: bytes) -> None:
    reference = store.store_raw_export(PLAINTEXT, master_key=master_key)
    assert store.load_raw_export(reference, master_key=master_key) == PLAINTEXT
    assert reference["encryption_algorithm"] == ENCRYPTION_ALGORITHM
    receipt = store.public_receipt(reference, event_content_ids=(EVENT_A, EVENT_B))
    payload = dict(receipt.to_dict())
    assert "secret transcript" not in str(payload)
    assert payload["event_content_ids"] == [EVENT_A, EVENT_B]
    blob = (store.ciphertext_dir / reference["ciphertext_cid"][7:]).read_bytes()
    assert b"secret transcript" not in blob
    assert digest_sha256(PLAINTEXT, prefixed=True) == reference["digest_sha256"]


def test_projection_has_no_transcript(store: EncryptedExportStore) -> None:
    projection = store.emit_normalized_projection((EVENT_A, EVENT_B))
    assert "transcript" not in str(projection.to_dict())
    with pytest.raises(HandoffStorageError):
        store.emit_normalized_projection(())
