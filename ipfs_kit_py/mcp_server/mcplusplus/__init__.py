"""MCP++ integration layer and inert durable-state-root facade.

Optional integrations are discovered only when a caller asks for capabilities
or validation. Importing this package never imports optional providers or
performs installation work. Durable state roots are exported lazily so their
public API remains a thin facade over an injected coordination store.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

HAVE_MCPLUSPLUS = False
HAVE_VALIDATOR = True  # The built-in packet shape validator is always present.
HAVE_SPEC_VALIDATOR = False
mcplusplus_version = "unknown"

_ROOT_EXPORTS = frozenset((
    "ArtifactWriteResult", "DurableStateRootAdapter", "DurableStateRoots",
    "ProviderStatus", "RootUpdateStatus", "StateRootCASResult",
    "StateRootRecoveryReport", "StateRootSnapshot",
))


def _optional_spec_validator() -> Any:
    """Return the optional validator without making package import eager."""

    global HAVE_SPEC_VALIDATOR
    try:
        from validators import validate_envelope  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        HAVE_SPEC_VALIDATOR = False
        return None
    HAVE_SPEC_VALIDATOR = True
    return validate_envelope


def _optional_mcplusplus() -> None:
    """Populate capability metadata only when capability inspection is requested."""

    global HAVE_MCPLUSPLUS, mcplusplus_version
    try:
        import ipfs_accelerate_py.mcplusplus_module as mpp  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        HAVE_MCPLUSPLUS = False
        mcplusplus_version = "unknown"
        return
    HAVE_MCPLUSPLUS = True
    mcplusplus_version = getattr(mpp, "__version__", "unknown")


def __getattr__(name: str) -> Any:
    """Lazily expose the closed durable-state-root contracts and adapter."""

    if name not in _ROOT_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    if name == "DurableStateRootAdapter":
        from .state_root_adapter import DurableStateRootAdapter

        value = DurableStateRootAdapter
    else:
        from . import state_root_contracts

        value = getattr(state_root_contracts, name)
    globals()[name] = value
    return value


def get_capabilities() -> Dict[str, Any]:
    _optional_mcplusplus()
    _optional_spec_validator()
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
    spec_validator = _optional_spec_validator()
    if spec_validator is None:
        return None
    try:
        spec_validator(envelope)
        return None
    except Exception as e:  # pragma: no cover
        return str(e)


__all__ = [
    "ArtifactWriteResult", "DurableStateRootAdapter", "DurableStateRoots",
    "ProviderStatus", "RootUpdateStatus", "StateRootCASResult",
    "StateRootRecoveryReport", "StateRootSnapshot", "get_capabilities",
    "validate_packet",
]
