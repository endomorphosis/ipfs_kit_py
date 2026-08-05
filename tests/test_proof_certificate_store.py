from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest

from ipfs_kit_py.proof_certificate_store import (
    CertificateTransportReason,
    CertificateTransportStatus,
    IpfsKitProofCertificateStore,
    cid_for_certificate_bytes,
    decode_certificate_cid,
    verify_certificate_cid,
)


def _varint(value: int) -> bytes:
    result = bytearray()
    while value >= 0x80:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def _external_cid(data: bytes, codec: int = 0x0129) -> str:
    raw = (
        _varint(1)
        + _varint(codec)
        + _varint(0x12)
        + _varint(32)
        + hashlib.sha256(data).digest()
    )
    return "b" + base64.b32encode(raw).decode().lower().rstrip("=")


def test_external_cid_decodes_and_rehashes_exact_bytes(tmp_path: Path) -> None:
    data = b'{"certificate":"external","passed":true}'
    external = _external_cid(data)
    parsed = decode_certificate_cid(external)
    assert parsed.codec == 0x0129
    assert parsed.verifies(data)
    assert verify_certificate_cid(external, data)
    assert not verify_certificate_cid(external, data + b"\n")

    store = IpfsKitProofCertificateStore(tmp_path)
    put = store.put_bytes(data, claimed_cid=external)
    assert put.stored and put.cid == external
    result = store.get_bytes(external)
    assert result.status is CertificateTransportStatus.HIT
    assert result.data == data


@pytest.mark.parametrize(
    "fake",
    [
        "QmTest0123456789abcdef0123456789abcdef",
        "bafy-test-certificate",
        "bafkreifake",
        "sha256:" + "0" * 64,
    ],
)
def test_legacy_fake_hashes_are_rejected(tmp_path: Path, fake: str) -> None:
    store = IpfsKitProofCertificateStore(tmp_path)
    assert not store.put_bytes(b"certificate", claimed_cid=fake)
    miss = store.get_bytes(fake)
    assert not miss.hit
    assert miss.reason_code is CertificateTransportReason.MALFORMED


def test_local_transport_is_atomic_bounded_and_rehashed(tmp_path: Path) -> None:
    store = IpfsKitProofCertificateStore(tmp_path, max_blob_bytes=32)
    data = b"exact-certificate"
    cid = cid_for_certificate_bytes(data)
    assert store.put(data) == cid
    assert store.get(cid) == data
    assert not list(tmp_path.rglob("*.tmp"))

    second = store.put_bytes(data, claimed_cid=cid)
    assert second.stored
    assert second.reason_code is CertificateTransportReason.ALREADY_EXISTS

    oversized = store.put_bytes(b"x" * 33)
    assert not oversized
    assert oversized.reason_code is CertificateTransportReason.OVER_BUDGET

    blob = next(tmp_path.rglob("*.blob"))
    blob.write_bytes(b"changed")
    corrupt = store.get_bytes(cid)
    assert not corrupt.hit
    assert corrupt.reason_code is CertificateTransportReason.INTEGRITY_FAILED


def test_local_transport_rejects_symlink_blob(tmp_path: Path) -> None:
    data = b"certificate"
    cid = cid_for_certificate_bytes(data)
    store = IpfsKitProofCertificateStore(tmp_path)
    path = store._blob_path(cid)
    path.parent.mkdir(parents=True)
    target = tmp_path / "outside"
    target.write_bytes(data)
    path.symlink_to(target)
    result = store.get_bytes(cid)
    assert not result.hit
    assert result.reason_code is CertificateTransportReason.SYMLINK_REJECTED


def test_local_transport_does_not_create_through_symlink_directory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cache"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "certificates").symlink_to(outside, target_is_directory=True)

    result = IpfsKitProofCertificateStore(root).put_bytes(b"certificate")

    assert not result.stored
    assert result.reason_code is CertificateTransportReason.SYMLINK_REJECTED
    assert not list(outside.iterdir())


def test_ipfs_error_is_a_miss_and_never_raises() -> None:
    calls: list[str] = []

    def failing_get(cid: str) -> bytes:
        calls.append(cid)
        raise RuntimeError("daemon unavailable")

    cid = cid_for_certificate_bytes(b"certificate")
    store = IpfsKitProofCertificateStore(ipfs_get=failing_get)
    result = store.get_bytes(cid)
    assert calls == [cid]
    assert not result.hit
    assert result.reason_code is CertificateTransportReason.IPFS_ERROR


def test_ipfs_bytes_are_bounded_verified_and_optionally_cached(tmp_path: Path) -> None:
    data = b"remote certificate"
    cid = _external_cid(data)
    calls: list[str] = []

    def get_remote(requested: str) -> bytes:
        calls.append(requested)
        return data

    store = IpfsKitProofCertificateStore(tmp_path, ipfs_get=get_remote)
    first = store.get_bytes(cid)
    assert first.hit and first.source == "ipfs" and first.data == data
    second = store.get_bytes(cid)
    assert second.hit and second.source == "local"
    assert calls == [cid]

    mismatch = IpfsKitProofCertificateStore(ipfs_get=lambda unused: data + b"!")
    assert mismatch.get_bytes(cid).reason_code is CertificateTransportReason.INTEGRITY_FAILED

    oversized = IpfsKitProofCertificateStore(
        ipfs_get=lambda unused: b"x" * 9, max_blob_bytes=8
    )
    assert oversized.get_bytes(cid).reason_code is CertificateTransportReason.IPFS_RESPONSE_INVALID


def test_default_store_has_no_filesystem_or_ipfs_side_effect(tmp_path: Path) -> None:
    store = IpfsKitProofCertificateStore()
    cid = cid_for_certificate_bytes(b"certificate")
    assert not store.put_bytes(b"certificate", claimed_cid=cid)
    assert store.get(cid) is None
    assert not list(tmp_path.iterdir())


def test_ipfs_put_response_must_carry_exact_byte_digest() -> None:
    data = b"certificate"
    expected = cid_for_certificate_bytes(data)
    wrong = cid_for_certificate_bytes(b"other")
    bad = IpfsKitProofCertificateStore(ipfs_put=lambda payload: {"Key": wrong})
    result = bad.put_bytes(data, claimed_cid=expected)
    assert not result.stored
    assert result.reason_code is CertificateTransportReason.CID_MISMATCH

    good = IpfsKitProofCertificateStore(ipfs_put=lambda payload: {"Key": expected})
    assert good.put_bytes(data, claimed_cid=expected).ipfs_stored
