from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import ipfs_kit_py.iroh_install_cli as lifecycle_module
from ipfs_kit_py.iroh_install_cli import (
    IrohInstallManager,
    IrohLifecycleError,
    IrohUpdateLockedError,
    LOCK_FILENAME,
    RECEIPT_FILENAME,
)


class FakeInstaller:
    def __init__(self, bin_dir: Path, version: str = "1.0.0") -> None:
        self.bin_dir = bin_dir.resolve()
        self.release = {
            "sidecar": {
                "binary": "ipfs-kit-iroh-sidecar",
                "version": version,
            }
        }
        self.install_calls = 0

    def select_artifact(self) -> dict[str, object]:
        version = self.release["sidecar"]["version"]
        return {
            "id": "linux_x86_64_gnu",
            "url": f"https://github.com/example/releases/download/v{version}/sidecar.tar.gz",
            "checksum_sha256": hashlib.sha256(str(version).encode()).hexdigest(),
        }

    def install(self) -> Path:
        self.install_calls += 1
        version = str(self.release["sidecar"]["version"])
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        destination = self.bin_dir / "ipfs-kit-iroh-sidecar"
        destination.write_text(
            f"#!/bin/sh\nprintf 'ipfs-kit-iroh-sidecar {version}\\n'\n",
            encoding="utf-8",
        )
        destination.chmod(0o755)
        return destination


def manager(tmp_path: Path, version: str = "1.0.0") -> tuple[IrohInstallManager, FakeInstaller]:
    installer = FakeInstaller(tmp_path / "bin", version)
    lifecycle = IrohInstallManager(
        installer=installer,  # type: ignore[arg-type]
        clock=lambda: datetime(2026, 7, 13, 12, 30, tzinfo=timezone.utc),
    )
    return lifecycle, installer


def test_install_writes_a_complete_receipt_and_inspects(tmp_path: Path) -> None:
    lifecycle, installer = manager(tmp_path)

    result = lifecycle.install(check=True)

    receipt = json.loads((installer.bin_dir / RECEIPT_FILENAME).read_text(encoding="utf-8"))
    assert result["healthy"] is True
    assert receipt["version"] == "1.0.0"
    assert receipt["source"].startswith("https://")
    assert len(receipt["digest"]) == 64
    assert receipt["time"] == "2026-07-13T12:30:00Z"
    assert len(receipt["binary_digest"]) == 64
    assert receipt["binary"] == str((installer.bin_dir / "ipfs-kit-iroh-sidecar").resolve())


def test_install_refuses_existing_unpinned_and_prerelease_versions(tmp_path: Path) -> None:
    lifecycle, _ = manager(tmp_path)
    lifecycle.install()
    with pytest.raises(IrohLifecycleError, match="already installed"):
        lifecycle.install()
    with pytest.raises(IrohLifecycleError, match="not in the pinned"):
        lifecycle.install(version="9.9.9")

    prerelease, _ = manager(tmp_path / "prerelease", "2.0.0-rc1")
    with pytest.raises(IrohLifecycleError, match="allow-prerelease"):
        prerelease.install()
    assert prerelease.install(allow_prerelease=True)["version"] == "2.0.0-rc1"

    build_metadata, _ = manager(tmp_path / "build", "2.0.0+build.1")
    assert build_metadata.install()["version"] == "2.0.0+build.1"


def test_dry_run_is_side_effect_free(tmp_path: Path) -> None:
    lifecycle, installer = manager(tmp_path)

    plan = lifecycle.install(dry_run=True)

    assert plan["operation"] == "install"
    assert plan["dry_run"] is True
    assert installer.install_calls == 0
    assert not installer.bin_dir.exists()


def test_update_retains_previous_and_rollback_swaps_versions(tmp_path: Path) -> None:
    lifecycle, installer = manager(tmp_path, "1.0.0")
    lifecycle.install()
    installer.release["sidecar"]["version"] = "1.1.0"

    updated = lifecycle.update()

    assert updated["version"] == "1.1.0"
    assert updated["previous_available"] is True
    assert lifecycle.previous_binary_path.is_file()
    previous = json.loads(lifecycle.previous_receipt_path.read_text(encoding="utf-8"))
    assert previous["version"] == "1.0.0"

    rolled_back = lifecycle.rollback(check=True)
    assert rolled_back["version"] == "1.0.0"
    retained = json.loads(lifecycle.previous_receipt_path.read_text(encoding="utf-8"))
    assert retained["version"] == "1.1.0"
    assert "1.0.0" in lifecycle.binary_path.read_text(encoding="utf-8")


def test_update_check_and_dry_run_do_not_install(tmp_path: Path) -> None:
    lifecycle, installer = manager(tmp_path, "1.0.0")
    lifecycle.install()
    installer.release["sidecar"]["version"] = "1.1.0"
    before = installer.install_calls

    checked = lifecycle.update(check=True)
    planned = lifecycle.update(dry_run=True)

    assert checked["available"] is True
    assert checked["available_version"] == "1.1.0"
    assert planned["current_version"] == "1.0.0"
    assert installer.install_calls == before


def test_final_release_updates_the_same_core_prerelease(tmp_path: Path) -> None:
    lifecycle, installer = manager(tmp_path, "2.0.0-rc1")
    lifecycle.install(allow_prerelease=True)
    installer.release["sidecar"]["version"] = "2.0.0"

    assert lifecycle.update()["version"] == "2.0.0"


def test_failed_update_receipt_restores_current_and_previous_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    lifecycle, installer = manager(tmp_path, "1.0.0")
    lifecycle.install()
    installer.release["sidecar"]["version"] = "1.1.0"
    lifecycle.update()
    installer.release["sidecar"]["version"] = "1.2.0"
    real_atomic_json = lifecycle_module._atomic_json
    calls = 0

    def fail_current_receipt(path: Path, value: dict[str, object]) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise IrohLifecycleError("simulated receipt failure")
        real_atomic_json(path, value)

    monkeypatch.setattr(lifecycle_module, "_atomic_json", fail_current_receipt)
    with pytest.raises(IrohLifecycleError, match="simulated"):
        lifecycle.update()

    assert json.loads(lifecycle.receipt_path.read_text(encoding="utf-8"))["version"] == "1.1.0"
    assert (
        json.loads(lifecycle.previous_receipt_path.read_text(encoding="utf-8"))["version"]
        == "1.0.0"
    )
    assert "1.1.0" in lifecycle.binary_path.read_text(encoding="utf-8")
    assert "1.0.0" in lifecycle.previous_binary_path.read_text(encoding="utf-8")


def test_rollback_refuses_a_corrupt_retained_binary(tmp_path: Path) -> None:
    lifecycle, installer = manager(tmp_path, "1.0.0")
    lifecycle.install()
    installer.release["sidecar"]["version"] = "1.1.0"
    lifecycle.update()
    lifecycle.previous_binary_path.write_bytes(b"corrupt")

    with pytest.raises(IrohLifecycleError, match="digest"):
        lifecycle.rollback()


def test_update_refuses_a_corrupt_current_binary(tmp_path: Path) -> None:
    lifecycle, installer = manager(tmp_path, "1.0.0")
    lifecycle.install()
    lifecycle.binary_path.write_bytes(b"corrupt")
    installer.release["sidecar"]["version"] = "1.1.0"

    with pytest.raises(IrohLifecycleError, match="digest"):
        lifecycle.update()
    assert installer.install_calls == 1


@pytest.mark.skipif(os.name == "nt", reason="fcntl is POSIX-specific")
def test_mutations_refuse_a_concurrent_update_lock(tmp_path: Path) -> None:
    import fcntl

    lifecycle, installer = manager(tmp_path)
    installer.bin_dir.mkdir(parents=True)
    lock_path = installer.bin_dir / LOCK_FILENAME
    with lock_path.open("a+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(IrohUpdateLockedError):
            lifecycle.install()


def test_inspect_check_uses_an_absolute_path_not_path_lookup(tmp_path: Path) -> None:
    observed: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        observed.append(argv)
        return SimpleNamespace(
            returncode=0,
            stdout="ipfs-kit-iroh-sidecar 1.0.0\n",
            stderr="",
        )

    installer = FakeInstaller(tmp_path / "bin")
    lifecycle = IrohInstallManager(installer=installer, command_runner=run)  # type: ignore[arg-type]
    lifecycle.install(check=True)

    assert Path(observed[0][0]).is_absolute()
    assert observed[0][0] == str(lifecycle.binary_path.resolve())
    assert observed[0][1:] == ["--version"]


def test_module_cli_is_path_independent_and_login_shell_discoverable(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    python = str(Path(sys.executable).resolve())
    env = os.environ.copy()
    env["IPFS_KIT_AUTO_INSTALL_BINARIES"] = "0"
    env["PATH"] = ""
    direct = subprocess.run(
        [python, "-m", "ipfs_kit_py.iroh_install_cli", "inspect", "--bin-dir", str(tmp_path)],
        cwd=root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert direct.returncode == 0, direct.stderr
    assert json.loads(direct.stdout)["installed"] is False

    command = (
        f"{python} -m ipfs_kit_py.iroh_install_cli inspect "
        f"--bin-dir {tmp_path} --json"
    )
    login = subprocess.run(
        ["/bin/bash", "-lc", command],
        cwd=root,
        env={**env, "PATH": "/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )
    assert login.returncode == 0, login.stderr
    assert json.loads(login.stdout)["installed"] is False


def test_console_script_is_declared() -> None:
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert 'ipfs-kit-iroh = "ipfs_kit_py.iroh_install_cli:main"' in pyproject
