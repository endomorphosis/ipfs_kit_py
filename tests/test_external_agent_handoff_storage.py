"""Security and contract tests for EAAEF-011 encrypted export storage."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from ipfs_kit_py.external_agent_handoff.storage import (
    DEFAULT_MAX_EVENTS,
    DISCLOSURE_ENCRYPTED_RAW,
    DISCLOSURE_PUBLIC_PROJECTION,
    ENCRYPTED_EXPORT_REFERENCE_INTERFACE,
    ENCRYPTED_EXPORT_REFERENCE_SCHEMA,
    ENCRYPTION_ALGORITHM,
    HANDOFF_STORAGE_CONTRACT_VERSION,
    KEY_ENVELOPE_INTERFACE,
    KEY_ENVELOPE_SCHEMA,
    NORMALIZED_STREAM_SCHEMA,
    EncryptedExportReference,
    EncryptedExportStore,
    EncryptedHandoffStore,
    HandoffStorageBoundsError,
    HandoffStorageDisclosureError,
    HandoffStorageError,
    HandoffStorageIdentityError,
    HandoffStorageIntegrityError,
    MemoryBlobStore,
    NormalizedProjection,
    PublicHandoffReceipt,
    aes_256_encrypt_block,
    aes_256_gcm_decrypt,
    aes_256_gcm_encrypt,
    canonical_storage_json_bytes,
    content_identity,
    digest_sha256,
    normalized_stream_identity,
    sha256_identity,
)

MASTER_KEY = bytes(range(32))
ALT_MASTER_KEY = bytes(range(32, 64))
EXPORT_A = b"codex-export-bytes\x00\xffexact-payload"
EXPORT_B = b"codex-export-bytes\x00\xffexact-payload!"
EVENT_A = "sha256:" + ("a" * 64)
EVENT_B = "sha256:" + ("b" * 64)
EVENT_C = "sha256:" + ("c" * 64)
FIXED_MS = 1_700_000_000_000


def _store(master_key: bytes = MASTER_KEY, **kwargs: object) -> EncryptedHandoffStore:
    return EncryptedHandoffStore(master_key, **kwargs)  # type: ignore[arg-type]


def test_aes_256_block_matches_fips_197() -> None:
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")
    plain = bytes.fromhex("00112233445566778899aabbccddeeff")
    expected = bytes.fromhex("8ea2b7ca516745bfeafc49904b496089")
    assert aes_256_encrypt_block(key, plain) == expected


def test_aes_256_gcm_round_trip_and_rejects_tampering() -> None:
    nonce = b"\x11" * 12
    aad = b"digest-aad"
    blob = aes_256_gcm_encrypt(MASTER_KEY, nonce, EXPORT_A, aad=aad)
    assert blob.startswith(nonce)
    assert aes_256_gcm_decrypt(MASTER_KEY, blob, aad=aad) == EXPORT_A
    tampered = bytearray(blob)
    tampered[-1] ^= 0x01
    with pytest.raises(HandoffStorageIntegrityError, match="authentication"):
        aes_256_gcm_decrypt(MASTER_KEY, bytes(tampered), aad=aad)
    with pytest.raises(HandoffStorageIntegrityError, match="authentication"):
        aes_256_gcm_decrypt(MASTER_KEY, blob, aad=b"other")
    empty = aes_256_gcm_encrypt(MASTER_KEY, nonce, b"", aad=b"")
    assert aes_256_gcm_decrypt(MASTER_KEY, empty, aad=b"") == b""


def test_store_returns_exact_exported_bytes_through_encrypted_reference() -> None:
    store = _store()
    export_ref = store.store_exported_bytes(EXPORT_A)
    assert export_ref.encryption_algorithm == ENCRYPTION_ALGORITHM
    assert export_ref.disclosure_class == DISCLOSURE_ENCRYPTED_RAW
    assert export_ref.byte_count == len(EXPORT_A)
    assert export_ref.digest_sha256 == digest_sha256(EXPORT_A)
    assert store.retrieve_exported_bytes(export_ref) == EXPORT_A
    restored = EncryptedExportReference.from_dict(export_ref.to_dict())
    assert restored == export_ref
    assert restored.content_id == export_ref.content_id
    assert store.retrieve_exported_bytes(export_ref.to_dict()) == EXPORT_A


def test_store_randomizes_ciphertext_while_preserving_plaintext_identity() -> None:
    first = _store().store_exported_bytes(EXPORT_A)
    second = _store().store_exported_bytes(EXPORT_A)
    assert first != second
    assert first.content_id != second.content_id
    assert first.ciphertext_cid != second.ciphertext_cid
    assert first.key_envelope_cid != second.key_envelope_cid
    assert first.digest_sha256 == second.digest_sha256 == digest_sha256(EXPORT_A)
    assert _store().key_id == _store().key_id
    first_store = _store()
    first_ref = first_store.store_exported_bytes(EXPORT_A)
    assert first_store.retrieve_exported_bytes(first_ref) == EXPORT_A
    other = _store().store_exported_bytes(EXPORT_B)
    assert other.ciphertext_cid != first.ciphertext_cid
    assert other.digest_sha256 != first.digest_sha256
    assert other.content_id != first.content_id


def test_encrypted_identities_are_distinct_from_stream_and_ciphertext() -> None:
    store = _store()
    preserved = store.preserve(EXPORT_A, (EVENT_A, EVENT_B), created_at_ms=FIXED_MS)
    export_ref = preserved.export_ref
    assert export_ref.content_id != export_ref.ciphertext_cid
    assert export_ref.content_id != export_ref.digest_sha256
    assert export_ref.content_id != export_ref.key_envelope_cid
    assert export_ref.ciphertext_cid != export_ref.digest_sha256
    assert export_ref.ciphertext_cid != export_ref.key_envelope_cid
    assert export_ref.digest_sha256 != export_ref.key_envelope_cid
    assert preserved.raw_export_id != preserved.normalized_stream_id
    assert preserved.normalized_stream_id == normalized_stream_identity((EVENT_A, EVENT_B))
    assert export_ref.content_id.startswith("b")
    assert export_ref.ciphertext_cid.startswith("sha256:")


def test_preserve_emits_ordered_projection_without_transcript_bodies() -> None:
    store = _store()
    preserved = store.preserve(
        EXPORT_A,
        (EVENT_A, EVENT_B, EVENT_C),
        created_at_ms=FIXED_MS,
    )
    projection = preserved.projection
    receipt = preserved.public_receipt
    assert projection.event_content_ids == (EVENT_A, EVENT_B, EVENT_C)
    assert projection.normalized_stream_id == normalized_stream_identity(
        (EVENT_A, EVENT_B, EVENT_C)
    )
    reordered = store.store_normalized_projection((EVENT_B, EVENT_A, EVENT_C))
    assert reordered.normalized_stream_id != projection.normalized_stream_id
    payload = receipt.to_dict()
    encoded = json.dumps(payload)
    for forbidden in (
        "transcript",
        "transcript_body",
        "raw_bytes",
        "raw_export",
        "raw_transcript",
        "full_transcript",
        "transcript_text",
        "body",
    ):
        assert forbidden not in payload
        if forbidden != "raw_export":
            assert f'"{forbidden}"' not in encoded
    assert "raw_export_ref" in payload
    assert payload["disclosure_class"] == DISCLOSURE_PUBLIC_PROJECTION
    assert EXPORT_A not in encoded.encode("utf-8")
    assert EXPORT_A.decode("latin1") not in encoded


def test_public_receipt_rejects_embedded_transcript_bodies() -> None:
    store = _store()
    preserved = store.preserve(EXPORT_A, (EVENT_A,), created_at_ms=FIXED_MS)
    payload = preserved.public_receipt.to_dict()
    payload["transcript_body"] = "exported chat"
    with pytest.raises(HandoffStorageDisclosureError, match="transcript"):
        PublicHandoffReceipt.from_dict(payload)
    with pytest.raises(HandoffStorageError, match="public_projection"):
        PublicHandoffReceipt(
            raw_export_ref=preserved.export_ref,
            normalized_stream_id=preserved.normalized_stream_id,
            event_content_ids=(EVENT_A,),
            disclosure_class=DISCLOSURE_ENCRYPTED_RAW,
        )


def test_normalized_events_reject_transcript_bodies_and_hidden_thoughts() -> None:
    store = _store()
    with pytest.raises(HandoffStorageDisclosureError, match="transcript"):
        store.store_normalized_projection(
            (EVENT_A,),
            events=({"content_id": EVENT_A, "transcript_body": "nope"},),
        )
    with pytest.raises(HandoffStorageDisclosureError, match="chain-of-thought"):
        store.store_normalized_projection(
            (EVENT_A,),
            events=({"content_id": EVENT_A, "thinking": "hidden"},),
        )
    with pytest.raises(HandoffStorageDisclosureError, match="private"):
        store.store_normalized_projection(
            (EVENT_A,),
            events=({"content_id": EVENT_A, "api_key": "sk-test"},),
        )


def test_blob_store_never_persists_plaintext() -> None:
    store = _store()
    preserved = store.preserve(EXPORT_A, (EVENT_A, EVENT_B))
    blobs = dict(store.stored_blobs())
    assert preserved.export_ref.ciphertext_cid in blobs
    assert preserved.export_ref.key_envelope_cid in blobs
    assert preserved.normalized_stream_id in blobs
    for cid, payload in blobs.items():
        assert EXPORT_A not in payload
        assert MASTER_KEY not in payload
        assert b"exported chat" not in payload
        if cid == preserved.normalized_stream_id:
            stream = json.loads(payload.decode("utf-8"))
            assert stream["schema"] == NORMALIZED_STREAM_SCHEMA
            assert stream["event_content_ids"] == [EVENT_A, EVENT_B]
            assert "transcript" not in stream
            assert content_identity(stream) == preserved.normalized_stream_id


def test_altered_ciphertext_and_wrong_wrapping_key_fail_closed() -> None:
    store = _store()
    export_ref = store.store_exported_bytes(EXPORT_A)
    ciphertext = bytearray(store.blobs.get(export_ref.ciphertext_cid))
    ciphertext[-2] ^= 0x5A
    store.blobs.put(  # type: ignore[attr-defined]
        sha256_identity(bytes(ciphertext)),
        bytes(ciphertext),
    )
    forged = EncryptedExportReference(
        ciphertext_cid=sha256_identity(bytes(ciphertext)),
        digest_sha256=export_ref.digest_sha256,
        byte_count=export_ref.byte_count,
        key_envelope_cid=export_ref.key_envelope_cid,
        media_type=export_ref.media_type,
        retention_class=export_ref.retention_class,
    )
    with pytest.raises(HandoffStorageIntegrityError, match="authentication"):
        store.retrieve_exported_bytes(forged)
    other = EncryptedHandoffStore(ALT_MASTER_KEY, blobs=store.blobs)
    with pytest.raises(HandoffStorageIntegrityError):
        other.retrieve_exported_bytes(export_ref)


def test_export_reference_wire_form_matches_handoff_contract_family() -> None:
    export_ref = _store().store_exported_bytes(EXPORT_A, media_type="application/json")
    payload = export_ref.to_dict()
    assert payload["schema"] == ENCRYPTED_EXPORT_REFERENCE_SCHEMA
    assert payload["interface"] == ENCRYPTED_EXPORT_REFERENCE_INTERFACE
    assert payload["contract_version"] == HANDOFF_STORAGE_CONTRACT_VERSION
    assert payload["encryption_algorithm"] == "aes-256-gcm"
    assert payload["disclosure_class"] == "encrypted_raw"
    assert "content_id" not in payload
    round_trip = json.loads(export_ref.to_json())
    assert round_trip == json.loads(
        json.dumps(round_trip, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )
    with pytest.raises(HandoffStorageError, match="encrypted_raw"):
        EncryptedExportReference(
            ciphertext_cid=export_ref.ciphertext_cid,
            digest_sha256=export_ref.digest_sha256,
            byte_count=export_ref.byte_count,
            key_envelope_cid=export_ref.key_envelope_cid,
            disclosure_class=DISCLOSURE_PUBLIC_PROJECTION,
        )


def test_records_are_frozen_and_reject_identity_mismatch() -> None:
    store = _store()
    preserved = store.preserve(EXPORT_A, (EVENT_A, EVENT_B))
    with pytest.raises(FrozenInstanceError):
        preserved.export_ref.byte_count = 1  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        preserved.projection.normalized_stream_id = EVENT_A  # type: ignore[misc]
    with pytest.raises(HandoffStorageIdentityError, match="distinct"):
        EncryptedExportReference(
            ciphertext_cid=preserved.export_ref.digest_sha256,
            digest_sha256=preserved.export_ref.digest_sha256,
            byte_count=8,
            key_envelope_cid=preserved.export_ref.key_envelope_cid,
        )
    with pytest.raises(HandoffStorageIdentityError):
        NormalizedProjection(
            event_content_ids=(EVENT_A, EVENT_B),
            normalized_stream_id=EVENT_A,
        )


def test_bounds_and_type_errors_fail_closed() -> None:
    store = EncryptedHandoffStore(MASTER_KEY, max_export_bytes=8, max_events=1)
    with pytest.raises(HandoffStorageBoundsError, match="max_export_bytes"):
        store.store_exported_bytes(b"0123456789")
    with pytest.raises(HandoffStorageBoundsError, match="max_events"):
        store.store_normalized_projection((EVENT_A, EVENT_B))
    with pytest.raises(HandoffStorageError, match="exact bytes"):
        store.store_exported_bytes("not-bytes")  # type: ignore[arg-type]
    with pytest.raises(HandoffStorageError, match="32 bytes"):
        EncryptedHandoffStore(b"short")
    with pytest.raises(HandoffStorageError, match="duplicate"):
        store.store_normalized_projection((EVENT_A, EVENT_A))
    with pytest.raises(HandoffStorageError, match="sha256 or CIDv1"):
        store.store_normalized_projection(("event:not-addressed",))
    with pytest.raises(HandoffStorageBoundsError):
        EncryptedHandoffStore(MASTER_KEY, max_events=DEFAULT_MAX_EVENTS * 100)


def test_empty_and_binary_exports_round_trip() -> None:
    store = _store()
    empty = store.store_exported_bytes(b"")
    assert empty.byte_count == 0
    assert store.retrieve_exported_bytes(empty) == b""
    binary = bytes(range(256)) * 4
    reference = store.store_exported_bytes(binary, media_type="application/octet-stream")
    assert store.retrieve_exported_bytes(reference) == binary
    assert binary not in store.blobs.get(reference.ciphertext_cid)


def test_public_receipt_stream_identity_is_independent_of_export_bodies() -> None:
    first = _store().preserve(EXPORT_A, (EVENT_A, EVENT_B), created_at_ms=FIXED_MS)
    second = _store().preserve(EXPORT_B, (EVENT_A, EVENT_B), created_at_ms=FIXED_MS)
    assert first.normalized_stream_id == second.normalized_stream_id
    assert first.raw_export_id != second.raw_export_id
    assert first.public_receipt.event_content_ids == (EVENT_A, EVENT_B)
    assert first.public_receipt.raw_export_id == first.export_ref.content_id
    restored = PublicHandoffReceipt.from_dict(first.public_receipt.to_dict())
    assert restored == first.public_receipt
    assert restored.content_id == first.public_receipt.content_id


def test_memory_blob_store_rejects_identity_collisions() -> None:
    blobs = MemoryBlobStore()
    blobs.put(EVENT_A, b"one")
    blobs.put(EVENT_A, b"one")
    with pytest.raises(HandoffStorageIdentityError, match="collision"):
        blobs.put(EVENT_A, b"two")
    assert EVENT_A in blobs
    assert "not-a-cid" not in blobs


def test_directory_compatibility_adapter_uses_randomized_canonical_storage(
    tmp_path,
) -> None:
    store = EncryptedExportStore(tmp_path / "handoff-store")
    first = store.store_raw_export(EXPORT_A, master_key=MASTER_KEY)
    second = store.store_raw_export(EXPORT_A, master_key=MASTER_KEY)
    assert first["digest_sha256"] == second["digest_sha256"] == digest_sha256(EXPORT_A)
    assert first["ciphertext_cid"] != second["ciphertext_cid"]
    assert store.load_raw_export(first, master_key=MASTER_KEY) == EXPORT_A
    projection = store.emit_normalized_projection((EVENT_A, EVENT_B))
    assert projection.stream_id == normalized_stream_identity((EVENT_A, EVENT_B))
    receipt = store.public_receipt(first, event_content_ids=(EVENT_A, EVENT_B))
    assert receipt.to_dict()["ciphertext_cid"] == first["ciphertext_cid"]
    assert EXPORT_A not in str(receipt.to_dict()).encode("utf-8")


def test_reads_legacy_nonce_ciphertext_tag_wire_form() -> None:
    blobs = MemoryBlobStore()
    writer = EncryptedHandoffStore(MASTER_KEY, blobs=blobs)
    data_key = bytes(reversed(range(32)))
    digest = digest_sha256(EXPORT_A)
    digest_raw = bytes.fromhex(digest[7:])
    ciphertext = aes_256_gcm_encrypt(data_key, b"\x31" * 12, EXPORT_A, aad=digest_raw)
    wrapped = aes_256_gcm_encrypt(MASTER_KEY, b"\x52" * 12, data_key, aad=digest_raw)
    envelope = canonical_storage_json_bytes(
        {
            "schema": KEY_ENVELOPE_SCHEMA,
            "interface": KEY_ENVELOPE_INTERFACE,
            "contract_version": HANDOFF_STORAGE_CONTRACT_VERSION,
            "wrapping_algorithm": ENCRYPTION_ALGORITHM,
            "key_id": writer.key_id,
            "nonce": (b"\x52" * 12).hex(),
            "wrapped_key": wrapped.hex(),
        }
    )
    ciphertext_cid = sha256_identity(ciphertext)
    envelope_cid = sha256_identity(envelope)
    blobs.put(ciphertext_cid, ciphertext)
    blobs.put(envelope_cid, envelope)
    reference = EncryptedExportReference(
        ciphertext_cid=ciphertext_cid,
        digest_sha256=digest,
        byte_count=len(EXPORT_A),
        key_envelope_cid=envelope_cid,
    )
    assert writer.retrieve_exported_bytes(reference) == EXPORT_A
