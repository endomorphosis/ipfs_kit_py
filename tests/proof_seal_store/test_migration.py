"""Public adapter freeze and legacy certificate migration (IPS-027).

Acceptance:

* cold import stays hermetic;
* lazy public adapters resolve without changing contract boundaries;
* old exact-byte blobs can be staged but are not admitted or accepted;
* proving keys / witnesses never surface;
* docs record storage nonclaims.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

from ipfs_kit_py.proof_seal_store import (
    MIGRATION_SUBSET,
    PUBLIC_ADAPTER_SUBSET,
    ForbiddenArtifactError,
    LegacyBlobStagingRecord,
    ProofSealStore,
    stage_legacy_certificate_blob,
)
from ipfs_kit_py.proof_seal_store.cache_index import ProofCacheIndex
from ipfs_kit_py.proof_seal_store.local_store import HermeticProofSealStore


def test_adapter_and_migration_subsets() -> None:
    assert PUBLIC_ADAPTER_SUBSET == "ips/kit-public-adapter@1"
    assert MIGRATION_SUBSET == "ips/kit-migration@1"


def test_cold_public_adapter_import_is_hermetic() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib, sys; "
                "assert 'multiformats' not in sys.modules; "
                "mod = importlib.import_module('ipfs_kit_py.proof_seal_store'); "
                "assert mod.PUBLIC_ADAPTER_SUBSET == 'ips/kit-public-adapter@1'; "
                "assert 'ipfs_datasets_py' not in sys.modules; "
                "assert 'provekit' not in sys.modules; "
                "assert 'ipfshttpclient' not in sys.modules"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_lazy_implementation_exports_resolve() -> None:
    package = importlib.import_module("ipfs_kit_py.proof_seal_store")
    for name in (
        "HermeticProofSealStore",
        "IpfsProofArtifactTransport",
        "ProofCacheIndex",
        "ProofForestStore",
        "CurrentSealRepository",
        "SealTransitionWal",
        "recover_seal_transitions",
        "RecoveryDisposition",
        "stage_legacy_certificate_blob",
    ):
        assert hasattr(package, name)
        assert getattr(package, name) is not None


def test_package_still_exports_protocol() -> None:
    package = importlib.import_module("ipfs_kit_py.proof_seal_store")
    assert package.ProofSealStore is ProofSealStore


def test_stage_legacy_blob_is_not_admission(tmp_path: Path) -> None:
    data = b'{"certificate":"legacy","passed":true}'
    staged = stage_legacy_certificate_blob(tmp_path, data)
    assert isinstance(staged, LegacyBlobStagingRecord)
    assert staged.staged is True
    assert staged.requires_accelerate_verification is True
    assert staged.admitted is False
    assert staged.accepted is False
    assert staged.byte_length == len(data)

    store = HermeticProofSealStore(tmp_path)
    from ipfs_kit_py.proof_seal_store.contracts import ArtifactKind, ArtifactReference

    ref = ArtifactReference(
        cid=staged.cid,
        kind=ArtifactKind.PROOF_RECEIPT,
        byte_length=staged.byte_length,
    )
    assert store.contains(ref) is False

    index = ProofCacheIndex(tmp_path)
    assert index.lookup_candidate("legacy:" + staged.cid) is None


def test_staged_blob_round_trip_via_certificate_store(tmp_path: Path) -> None:
    from ipfs_kit_py.proof_certificate_store import IpfsKitProofCertificateStore

    data = b'{"certificate":"exact-bytes"}'
    staged = stage_legacy_certificate_blob(tmp_path, data)
    transport = IpfsKitProofCertificateStore(tmp_path)
    fetched = transport.get_bytes(staged.cid)
    assert fetched.hit
    assert fetched.data == data


def test_proving_key_cannot_be_staged(tmp_path: Path) -> None:
    with pytest.raises(ForbiddenArtifactError):
        stage_legacy_certificate_blob(
            tmp_path,
            b"secret-proving-key",
            claimed_kind="proving_key",
        )
    with pytest.raises(ForbiddenArtifactError):
        stage_legacy_certificate_blob(
            tmp_path,
            b"witness-bytes",
            claimed_kind="witness",
        )


def test_docs_record_storage_nonclaims() -> None:
    doc = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "architecture"
        / "INCREMENTAL_PROOF_SEAL_STORE.md"
    )
    text = doc.read_text(encoding="utf-8")
    assert "ips/kit-public-adapter@1" in text
    assert "ips/kit-migration@1" in text
    lowered = text.lower()
    assert "does **not** claim" in text or "nonclaims" in lowered
    assert "reuse" in lowered
    assert "proving" in lowered
    assert "does not decide" in lowered or "never decides" in lowered
    assert "repository correctness" in lowered or "test execution" in lowered
