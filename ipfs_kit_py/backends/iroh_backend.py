"""Compatibility imports for the validated Iroh named-backend plugin.

The runtime adapter itself is :class:`ipfs_kit_py.iroh_fsspec.IrohFileSystem`.
Construction should go through ``BackendManager.get_backend_adapter(name)`` so
the persisted named configuration is validated first.
"""

from ..iroh.backend import (
    IROH_BACKEND_SCHEMA_VERSION,
    IrohBackendPlugin,
    migrate_iroh_backend_config,
    validate_iroh_backend_config,
)
from ..iroh_fsspec import IrohFileSystem
from ..iroh_vfs import IrohVFSAdapter


IrohBackend = IrohFileSystem

__all__ = [
    "IROH_BACKEND_SCHEMA_VERSION",
    "IrohBackend",
    "IrohBackendPlugin",
    "IrohFileSystem",
    "IrohVFSAdapter",
    "migrate_iroh_backend_config",
    "validate_iroh_backend_config",
]
