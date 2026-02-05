"""Compatibility shim for importing `install_ipfs`.

Some older scripts/tests expect `from install_ipfs import install_ipfs` from the
repository root. The canonical implementation lives in `ipfs_kit_py.install_ipfs`.
"""

from ipfs_kit_py.install_ipfs import install_ipfs

__all__ = ["install_ipfs"]
