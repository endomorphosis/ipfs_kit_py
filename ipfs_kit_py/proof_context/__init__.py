"""Public, inert entry point for the kit proof-context persistence provider.

Importing this namespace only publishes versioned compatibility metadata.  The
local CAS, receipt store, seal store, WAL, and optional IPFS adapter are loaded
only when a caller explicitly requests one.  In particular, import never
chooses a state root, starts a daemon, or performs network I/O.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

SCHEMA = "ipfs-kit.proof-context.v0.1"
VERSION = "0.1"
PROOF_SEAL_STORE_SCHEMA_VERSION = "1.0.0"
IPFS_TRANSPORT_EXTRA = "proof-context-ipfs"

# These are compatibility identities, rather than version ranges: consumers
# can reject a package whose proof-context or proof-seal contract differs.
COMPATIBLE_VERSIONS = {
    "proof_context": VERSION,
    "proof_seal_store": PROOF_SEAL_STORE_SCHEMA_VERSION,
}

_EXPORTS: dict[str, tuple[str, str]] = {
    "KitProofContextStateStore": (".state_store", "KitProofContextStateStore"),
    "open_local_store": (".state_store", "open_local_store"),
    "UnavailableTransportError": (".state_store", "UnavailableTransportError"),
    "KitVerificationStore": (".verification_store", "KitVerificationStore"),
    "open_verification_store": (".verification_store", "open_verification_store"),
    "IncrementalSealStore": (".incremental_seal_store", "IncrementalSealStore"),
    "open_incremental_seal_store": (
        ".incremental_seal_store",
        "open_incremental_seal_store",
    ),
    # Transport construction is deliberately opt-in.  It accepts injected
    # callables; installing the extra never makes a daemon implicit.
    "IpfsProofArtifactTransport": (
        "ipfs_kit_py.proof_seal_store.ipfs_transport",
        "IpfsProofArtifactTransport",
    ),
}


def __getattr__(name: str) -> Any:
    """Resolve a provider surface lazily, preserving cold-import inertness."""

    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    module = import_module(module_name, package=__name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))

__all__ = [
    "COMPATIBLE_VERSIONS",
    "IPFS_TRANSPORT_EXTRA",
    "IncrementalSealStore",
    "IpfsProofArtifactTransport",
    "KitProofContextStateStore",
    "KitVerificationStore",
    "PROOF_SEAL_STORE_SCHEMA_VERSION",
    "SCHEMA",
    "UnavailableTransportError",
    "VERSION",
    "open_incremental_seal_store",
    "open_local_store",
    "open_verification_store",
]
