"""MCP++ integration layer for ipfs_kit_py (graceful).

Provides optional packet validation against the canonical Mcp-Plus-Plus spec and
optional P2P/workflow features imported from ipfs_accelerate_py. All imports are
guarded so the server runs as a plain MCP server when extras are absent.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

HAVE_MCPLUSPLUS = False
HAVE_VALIDATOR = True
HAVE_SPEC_VALIDATOR = False
mcplusplus_version = "unknown"

try:  # canonical accelerate mcplusplus module (P2P, CID/UCAN, workflows)
    import ipfs_accelerate_py.mcplusplus_module as _mpp  # type: ignore
    HAVE_MCPLUSPLUS = True
    mcplusplus_version = getattr(_mpp, "__version__", "unknown")
except Exception:  # pragma: no cover
    _mpp = None

try:  # python validator from the spec submodule
    from validators import validate_envelope  # type: ignore
    HAVE_SPEC_VALIDATOR = True
except Exception:  # pragma: no cover
    validate_envelope = None  # type: ignore


def get_capabilities() -> Dict[str, Any]:
    try:
        from .p2p_transport import HAVE_LIBP2P
    except Exception:  # pragma: no cover
        HAVE_LIBP2P = False
    try:
        from .ucan import HAVE_CRYPTO_ED25519
    except Exception:  # pragma: no cover
        HAVE_CRYPTO_ED25519 = False
    return {
        "mcplusplus_available": HAVE_MCPLUSPLUS,
        "mcplusplus_version": mcplusplus_version,
        "validator_available": HAVE_VALIDATOR,
        "spec_validator_available": HAVE_SPEC_VALIDATOR,
        "profiles": {
            "A_interface_descriptors": True,
            "B_cid_envelopes": True,
            "B_artifact_cids": True,
            "C_ucan_signed": HAVE_CRYPTO_ED25519,
            "D_policy": True,
            "E_dag_events": True,
            "C_ucan": HAVE_CRYPTO_ED25519,
            "E_p2p_transport": HAVE_LIBP2P,
            "G_risk_scheduling": True,
        },
    }


def validate_packet(envelope: Dict[str, Any]) -> Optional[str]:
    """Validate the authorization-envelope shape, then the optional spec model.

    The built-in checks are always active, so callers that explicitly select
    this validator never receive a permissive success merely because the
    optional MCP++ model package is unavailable.
    """

    if not isinstance(envelope, dict):
        return "envelope must be an object"
    for field in (
        "tool",
        "resource",
        "ability",
        "actor",
        "policy_root",
        "request_id",
        "transaction_id",
    ):
        if not isinstance(envelope.get(field), str) or not envelope[field]:
            return f"{field} must be a non-empty string"
    if envelope["request_id"] != envelope["transaction_id"]:
        return "request_id and transaction_id must match"
    token = envelope.get("ucan", envelope.get("ucan_chain", envelope.get("ucans")))
    if not (
        isinstance(token, str)
        and token
        or isinstance(token, (list, tuple))
        and token
        and all(isinstance(item, str) and item for item in token)
    ):
        return "ucan must be a signed token or non-empty token chain"
    if not HAVE_SPEC_VALIDATOR or validate_envelope is None:
        return None
    try:
        validate_envelope(envelope)
        return None
    except Exception as e:  # pragma: no cover
        return str(e)
