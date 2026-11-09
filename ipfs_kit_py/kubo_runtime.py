"""Package-local Kubo resolution, installation, and upgrade support."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_CHECKED_BIN_DIRS: set[str] = set()


def _enabled(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def managed_bin_dir() -> Path:
    """Return the writable directory reserved for ipfs_kit_py binaries."""
    override = os.environ.get("IPFS_KIT_BIN_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent / "bin"


def kubo_binary(bin_dir: Optional[Path] = None) -> Path:
    name = "ipfs.exe" if os.name == "nt" else "ipfs"
    return (bin_dir or managed_bin_dir()) / name


def prepend_managed_bin_to_path(bin_dir: Optional[Path] = None) -> Path:
    """Put the managed Kubo directory before legacy shell installations."""
    directory = (bin_dir or managed_bin_dir()).resolve()
    directory_text = str(directory)
    current = [entry for entry in os.environ.get("PATH", "").split(os.pathsep) if entry]
    current = [entry for entry in current if os.path.abspath(entry) != directory_text]
    os.environ["PATH"] = os.pathsep.join([directory_text, *current])
    return directory


def _install_or_upgrade(bin_dir: Path) -> bool:
    from .install_ipfs import install_ipfs

    metadata = {"bin_dir": str(bin_dir)}
    ipfs_path = os.environ.get("IPFS_PATH")
    if ipfs_path:
        metadata["ipfs_path"] = ipfs_path
    installer = install_ipfs(metadata=metadata)
    return bool(installer.install_ipfs_daemon())


def ensure_kubo_binary(
    *,
    install: Optional[bool] = None,
    upgrade: Optional[bool] = None,
    bin_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Ensure that the package-managed Kubo binary exists and is current.

    Installation and upgrade are disabled by default. Set
    ``IPFS_KIT_AUTO_INSTALL_BINARIES=1`` to opt in, or
    ``IPFS_KIT_AUTO_UPGRADE_KUBO=0`` to retain the installed package binary.
    The managed directory is always prepended to ``PATH`` for this process.
    """
    directory = prepend_managed_bin_to_path(bin_dir)
    binary = kubo_binary(directory)
    install_enabled = _enabled("IPFS_KIT_AUTO_INSTALL_BINARIES", False) if install is None else install
    upgrade_enabled = _enabled("IPFS_KIT_AUTO_UPGRADE_KUBO", True) if upgrade is None else upgrade
    key = str(directory)

    with _LOCK:
        if binary.is_file() and os.access(binary, os.X_OK) and key in _CHECKED_BIN_DIRS:
            return binary
        if not install_enabled:
            return binary if binary.is_file() and os.access(binary, os.X_OK) else None

        needs_install = not binary.is_file() or not os.access(binary, os.X_OK)
        if needs_install or upgrade_enabled:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                _install_or_upgrade(directory)
            except Exception as error:
                logger.warning("Unable to install or upgrade package-managed Kubo: %s", error)

        if binary.is_file() and os.access(binary, os.X_OK):
            _CHECKED_BIN_DIRS.add(key)
            return binary
        return None
