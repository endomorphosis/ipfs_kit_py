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
import sys
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


def install_all_binaries(*, include_cluster: bool = True, include_lassie: bool = True, include_lotus: bool = True) -> None:
    """Install all supported external binaries into the package bin directory."""

    bin_dir = _package_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)
    _prepend_path(bin_dir)

    from ipfs_kit_py.install_ipfs import install_ipfs

    ipfs_installer = install_ipfs(metadata={"role": "leecher", "bin_dir": str(bin_dir)})
    ipfs_installer.install_ipfs_daemon()

    if include_cluster:
        ipfs_installer.install_ipfs_cluster_service()
        ipfs_installer.install_ipfs_cluster_ctl()
        ipfs_installer.install_ipfs_cluster_follow()

    if include_lassie:
        from ipfs_kit_py.install_lassie import install_lassie

        lassie_installer = install_lassie(metadata={"bin_dir": str(bin_dir)})
        lassie_installer.install_lassie_daemon()

    if include_lotus:
        from ipfs_kit_py.install_lotus import install_lotus

        # Safer default: only auto-install system deps when explicitly opted-in.
        auto_install_deps = (
            _truthy_env("IPFS_KIT_AUTO_INSTALL_LOTUS_DEPS")
            if _truthy_env("IPFS_KIT_AUTO_INSTALL_LOTUS_DEPS") is not None
            else _truthy_env("IPFS_KIT_AUTO_INSTALL_DEPS")
        )

        lotus_metadata: dict[str, object] = {"role": "leecher", "bin_dir": str(bin_dir)}
        if auto_install_deps is not None:
            lotus_metadata["auto_install_deps"] = bool(auto_install_deps)

        lotus_installer = install_lotus(metadata=lotus_metadata)
        lotus_installer.install_lotus_daemon()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ipfs_kit_py zero-touch installers")
    parser.add_argument(
        "--binaries",
        choices=["core", "full"],
        default=os.environ.get("IPFS_KIT_ZERO_TOUCH_BINARIES", "full"),
        help="Which set of external binaries to install (default: full)",
    )
    args = parser.parse_args(argv)

    include_cluster = args.binaries == "full"
    include_lassie = args.binaries == "full"
    include_lotus = args.binaries == "full"

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
