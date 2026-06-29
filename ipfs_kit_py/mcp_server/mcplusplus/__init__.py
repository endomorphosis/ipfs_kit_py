"""MCP++ integration layer for ipfs_kit_py (graceful).

Provides optional packet validation against the canonical Mcp-Plus-Plus spec and
optional P2P/workflow features imported from ipfs_accelerate_py. All imports are
guarded so the server runs as a plain MCP server when extras are absent.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

HAVE_MCPLUSPLUS = False
HAVE_VALIDATOR = False
mcplusplus_version = "unknown"

try:  # canonical accelerate mcplusplus module (P2P, CID/UCAN, workflows)
    import ipfs_accelerate_py.mcplusplus_module as _mpp  # type: ignore
    HAVE_MCPLUSPLUS = True
    mcplusplus_version = getattr(_mpp, "__version__", "unknown")
except Exception:  # pragma: no cover
    _mpp = None

try:  # python validator from the spec submodule
    from validators import validate_envelope  # type: ignore
    HAVE_VALIDATOR = True
except Exception:  # pragma: no cover
    validate_envelope = None  # type: ignore


def get_capabilities() -> Dict[str, Any]:
    try:
        from .p2p_transport import HAVE_LIBP2P
    except Exception:  # pragma: no cover
        HAVE_LIBP2P = False
    return {
        "mcplusplus_available": HAVE_MCPLUSPLUS,
        "mcplusplus_version": mcplusplus_version,
        "validator_available": HAVE_VALIDATOR,
        "profiles": {
            "A_interface_descriptors": True,
            "B_cid_envelopes": True,
            "C_ucan": HAVE_MCPLUSPLUS,
            "E_p2p_transport": HAVE_LIBP2P,
        },
    }


def validate_packet(envelope: Dict[str, Any]) -> Optional[str]:
    """Return None if valid, else an error string. No-op when validator absent."""
    if not HAVE_VALIDATOR or validate_envelope is None:
        return None
    try:
        validate_envelope(envelope)
        return None
    except Exception as e:  # pragma: no cover
        return str(e)
