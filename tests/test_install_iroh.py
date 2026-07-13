from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from ipfs_kit_py.install_iroh import (
    AttestationVerificationError,
    DownloadVerificationError,
    IrohInstallError,
    IrohInstaller,
    ReleaseUnavailableError,
    UnsafeArchiveError,
    UnsupportedTargetError,
    detect_platform,
    load_release_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
TARGET_FIXTURE = ROOT / "tests/fixtures/iroh/installer/targets.json"
RELEASE_PATH = ROOT / "ipfs_kit_py/resources/iroh-releases.json"


def _archive(
    payload: bytes = b"#!/bin/sh\nprintf 'iroh fixture\\n'\n",
    name: str = "bundle/ipfs-kit-iroh-sidecar",
) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as bundle:
        member = tarfile.TarInfo(name)
        member.mode = 0o644
        member.size = len(payload)
        bundle.addfile(member, io.BytesIO(payload))
    return output.getvalue()


def _published_release(archive: bytes) -> dict:
    release = load_release_manifest(RELEASE_PATH)
    release["sidecar"]["distribution_status"] = "published"
    platform_entry = next(
        item for item in release["platforms"] if item["id"] == "linux_x86_64_gnu"
    )
    platform_entry.update(
        installable=True,
        url=(
            "https://github.com/endomorphosis/ipfs_kit_py/releases/download/"
            "iroh-sidecar-v0.1.0/linux_x86_64_gnu.tar.gz"
        ),
        size=len(archive),
        checksum_sha256=hashlib.sha256(archive).hexdigest(),
    )
    return release


class _Response(io.BytesIO):
    pass


def _installer(
    tmp_path: Path,
    archive: bytes,
    release: dict | None = None,
    returncode: int = 0,
) -> IrohInstaller:
    return IrohInstaller(
        metadata={"bin_dir": str(tmp_path / "bin")},
        release_manifest=release or _published_release(archive),
        opener=lambda _url, **_kwargs: _Response(archive),
        command_runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=returncode,
            stdout="",
            stderr="bad provenance" if returncode else "",
        ),
    )


def test_target_normalization_fixture() -> None:
    fixture = json.loads(TARGET_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["schema_version"] == 1
    for case in fixture["normalization"]:
        assert list(
            detect_platform(
                system=case["system"], machine=case["machine"], libc=case["libc"]
            )
        ) == case["expected"]


def test_unsupported_architectures_are_rejected() -> None:
    fixture = json.loads(TARGET_FIXTURE.read_text(encoding="utf-8"))
    for architecture in fixture["unsupported_architectures"]:
        with pytest.raises(UnsupportedTargetError, match="architecture"):
            detect_platform(system="Linux", machine=architecture, libc="glibc")


def test_unpublished_default_release_fails_closed(tmp_path: Path) -> None:
    installer = IrohInstaller(
        metadata={"bin_dir": str(tmp_path / "bin")}, manifest_path=RELEASE_PATH
    )
    with pytest.raises(ReleaseUnavailableError, match="not published"):
        installer.select_artifact(system="Linux", machine="x86_64", libc="glibc")


def test_verified_archive_installs_atomically_and_sets_executable(tmp_path: Path) -> None:
    archive = _archive()
    installer = _installer(tmp_path, archive)

    destination = installer.install(system="Linux", machine="AMD64", libc="glibc")

    assert destination == (tmp_path / "bin/ipfs-kit-iroh-sidecar").resolve()
    assert destination.read_bytes().startswith(b"#!/bin/sh")
    assert os.access(destination, os.X_OK)
    assert not list(destination.parent.glob(".iroh-install-*"))


def test_ipfs_kit_bin_dir_is_honored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    archive = _archive()
    monkeypatch.setenv("IPFS_KIT_BIN_DIR", str(tmp_path / "managed"))
    installer = IrohInstaller(
        release_manifest=_published_release(archive),
        opener=lambda _url, **_kwargs: _Response(archive),
        command_runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout="", stderr=""
        ),
    )

    assert installer.install(
        system="Linux", machine="x86_64", libc="gnu"
    ).parent == (tmp_path / "managed").resolve()


def test_truncated_download_fails_and_preserves_existing_binary(tmp_path: Path) -> None:
    archive = _archive()
    release = _published_release(archive)
    release["platforms"][0]["size"] = len(archive) + 7
    installer = _installer(tmp_path, archive, release)
    installer.bin_dir.mkdir(parents=True)
    existing = installer.bin_dir / "ipfs-kit-iroh-sidecar"
    existing.write_bytes(b"existing")

    with pytest.raises(DownloadVerificationError, match="truncated"):
        installer.install(system="Linux", machine="x86_64", libc="glibc")
    assert existing.read_bytes() == b"existing"


def test_digest_mismatch_fails(tmp_path: Path) -> None:
    archive = _archive()
    release = _published_release(archive)
    release["platforms"][0]["checksum_sha256"] = "0" * 64
    with pytest.raises(DownloadVerificationError, match="SHA-256"):
        _installer(tmp_path, archive, release).install(
            system="Linux", machine="x86_64", libc="glibc"
        )


def test_failed_attestation_fails_before_extraction(tmp_path: Path) -> None:
    archive = _archive()
    with pytest.raises(AttestationVerificationError, match="bad provenance"):
        _installer(tmp_path, archive, returncode=1).install(
            system="Linux", machine="x86_64", libc="glibc"
        )
    assert not (tmp_path / "bin/ipfs-kit-iroh-sidecar").exists()


def test_archive_traversal_is_rejected(tmp_path: Path) -> None:
    archive = _archive(name="../ipfs-kit-iroh-sidecar")
    with pytest.raises(UnsafeArchiveError, match="unsafe archive member"):
        _installer(tmp_path, archive).install(
            system="Linux", machine="x86_64", libc="glibc"
        )


def test_non_executable_result_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive = _archive()
    installer = _installer(tmp_path, archive)
    real_access = os.access

    def deny_staged(path: os.PathLike[str] | str, mode: int) -> bool:
        if mode == os.X_OK and ".iroh-install-" in str(path):
            return False
        return real_access(path, mode)

    monkeypatch.setattr("ipfs_kit_py.install_iroh.os.access", deny_staged)
    with pytest.raises(IrohInstallError, match="not executable"):
        installer.install(system="Linux", machine="x86_64", libc="glibc")
    assert not (tmp_path / "bin/ipfs-kit-iroh-sidecar").exists()


def test_untrusted_download_authority_is_rejected(tmp_path: Path) -> None:
    archive = _archive()
    release = _published_release(archive)
    release["platforms"][0]["url"] = "https://example.invalid/sidecar.tar.gz"
    with pytest.raises(ReleaseUnavailableError, match="pinned release repository"):
        _installer(tmp_path, archive, release).select_artifact(
            system="Linux", machine="x86_64", libc="glibc"
        )
