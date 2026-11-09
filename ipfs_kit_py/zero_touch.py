"""Zero-touch installers.

This module centralizes the "install everything needed" path so CI, local
bootstrap, and Docker all share the same installer code.

Design goals:
- Keep a single source of truth for binary installation (Kubo/IPFS Cluster/Lassie/Lotus)
- Be safe by default on developer machines (Lotus system deps are opt-in)
- Be easy to invoke from shell: `python -m ipfs_kit_py.zero_touch`
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import subprocess
from pathlib import Path


def _truthy_env(name: str) -> bool | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def _package_bin_dir() -> Path:
    import ipfs_kit_py  # noqa: WPS433 (runtime import is intentional)

    return Path(ipfs_kit_py.__file__).resolve().parent / "bin"


def _prepend_path(path: Path) -> None:
    current = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{path}{os.pathsep}{current}" if current else str(path)


def _platform_info() -> tuple[str, str, str, str]:
    os_raw = platform.system()
    arch_raw = platform.machine().lower()

    if os_raw.startswith("Linux"):
        os_name = "linux"
    elif os_raw.startswith("Darwin"):
        os_name = "darwin"
    else:
        os_name = os_raw.lower()

    if arch_raw in {"x86_64", "amd64"}:
        arch = "x86_64"
    elif arch_raw in {"aarch64", "arm64"}:
        arch = "arm64"
    elif arch_raw in {"armv7l", "armv7", "armv6l", "armv6"}:
        arch = "arm"
    elif arch_raw in {"i386", "i686", "x86"}:
        arch = "x86"
    else:
        arch = arch_raw

    libc = "gnu"
    if os_name == "linux":
        try:
            out = subprocess.check_output(["ldd", "--version"], text=True)
            if "musl" in out.lower():
                libc = "musl"
        except Exception:
            libc = "gnu"

    tag = f"{os_name}-{arch}-{libc}"
    return os_name, arch, libc, tag


def _supports_kubo(os_name: str, arch: str) -> bool:
    if os_name == "linux":
        return arch in {"x86_64", "arm64", "arm", "x86"}
    if os_name == "darwin":
        return arch in {"x86_64", "arm64"}
    return False


def _supports_lassie(os_name: str, arch: str) -> bool:
    if os_name == "linux":
        return arch in {"x86_64", "arm64"}
    if os_name == "darwin":
        return arch in {"x86_64", "arm64"}
    return False


def _supports_lotus(os_name: str, arch: str) -> bool:
    if os_name == "linux":
        return arch in {"x86_64", "arm64"}
    if os_name == "darwin":
        return arch in {"x86_64", "arm64"}
    return False


def _install_python_deps(level: str) -> None:
    if level == "none":
        return

    requirements = Path(__file__).resolve().parents[1] / "requirements.txt"
    if not requirements.exists():
        raise RuntimeError(f"Requirements file not found: {requirements}")

    print(f"📦 Installing Python dependencies ({level}) from {requirements}...")
    subprocess.check_call([
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        str(requirements),
    ])


def install_all_binaries(*, include_cluster: bool = True, include_lassie: bool = True, include_lotus: bool = True) -> None:
    """Install all supported external binaries into the package bin directory."""

    bin_dir = _package_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)
    _prepend_path(bin_dir)

    os_name, arch, libc, tag = _platform_info()
    os.environ["IPFS_KIT_PLATFORM_OS"] = os_name
    os.environ["IPFS_KIT_PLATFORM_ARCH"] = arch
    os.environ["IPFS_KIT_PLATFORM_LIBC"] = libc
    os.environ["IPFS_KIT_PLATFORM_TAG"] = tag

    repo_root = Path(__file__).resolve().parents[1]
    ipfs_repo = repo_root / ".cache" / "ipfs-repo"
    ipfs_repo.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("IPFS_PATH", str(ipfs_repo))

    from ipfs_kit_py.install_ipfs import install_ipfs

    if _supports_kubo(os_name, arch):
        ipfs_installer = install_ipfs(metadata={"role": "leecher", "bin_dir": str(bin_dir), "ipfs_path": str(ipfs_repo)})
        ipfs_installer.install_ipfs_daemon()
    else:
        print(f"⚠️  Kubo/IPFS install skipped on unsupported platform: {os_name}/{arch}")

    if include_cluster:
        if _supports_kubo(os_name, arch):
            ipfs_installer.install_ipfs_cluster_service()
            ipfs_installer.install_ipfs_cluster_ctl()
            ipfs_installer.install_ipfs_cluster_follow()

    if include_lassie:
        if _supports_lassie(os_name, arch):
            from ipfs_kit_py.install_lassie import install_lassie

            lassie_installer = install_lassie(metadata={"bin_dir": str(bin_dir)})
            lassie_installer.install_lassie_daemon()
        else:
            print(f"⚠️  Lassie install skipped on unsupported platform: {os_name}/{arch}")

    if include_lotus:
        # Lotus is only supported on Linux/macOS in our zero-touch pathway.
        # On other platforms, skip rather than crashing.
        if not _supports_lotus(os_name, arch):
            print(f"⚠️  Lotus install skipped on unsupported platform: {os_name}/{arch}")
            return

        # Safer default: only auto-install system deps when explicitly opted-in.
        auto_install_deps = (
            _truthy_env("IPFS_KIT_AUTO_INSTALL_LOTUS_DEPS")
            if _truthy_env("IPFS_KIT_AUTO_INSTALL_LOTUS_DEPS") is not None
            else _truthy_env("IPFS_KIT_AUTO_INSTALL_DEPS")
        )

        try:
            from ipfs_kit_py.install_lotus import install_lotus

            lotus_metadata: dict[str, object] = {"role": "leecher", "bin_dir": str(bin_dir)}
            if auto_install_deps is not None:
                lotus_metadata["auto_install_deps"] = bool(auto_install_deps)

            lotus_installer = install_lotus(metadata=lotus_metadata)
            lotus_installer.install_lotus_daemon()
        except RuntimeError as e:
            # On Linux/macOS we don't silently skip Lotus: if prerequisites are missing,
            # fail with a clear message unless auto-install is explicitly enabled.
            if auto_install_deps is True:
                raise
            message = str(e)
            raise RuntimeError(
                "Lotus prerequisites missing on a supported platform. "
                "Install the listed packages manually, or rerun with IPFS_KIT_AUTO_INSTALL_LOTUS_DEPS=1 (requires sudo).\n\n"
                + message
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ipfs_kit_py zero-touch installers")
    parser.add_argument(
        "--binaries",
        choices=["core", "full"],
        default=os.environ.get("IPFS_KIT_ZERO_TOUCH_BINARIES", "full"),
        help="Which set of external binaries to install (default: full)",
    )
    parser.add_argument(
        "--python-deps",
        choices=["none", "runtime", "tests"],
        default=os.environ.get("IPFS_KIT_ZERO_TOUCH_PY_DEPS", "tests"),
        help="Install Python dependencies (default: tests)",
    )
    args = parser.parse_args(argv)

    include_cluster = args.binaries == "full"
    include_lassie = args.binaries == "full"
    include_lotus = args.binaries == "full"

    _install_python_deps(args.python_deps)

    install_all_binaries(
        include_cluster=include_cluster,
        include_lassie=include_lassie,
        include_lotus=include_lotus,
    )

    # Make the bin directory discoverable for subsequent steps.
    bin_dir = _package_bin_dir()
    print(f"✅ zero-touch binaries ready (bin: {bin_dir})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
