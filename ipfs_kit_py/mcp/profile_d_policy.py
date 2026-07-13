"""Profile D policy bridge for IPFS Kit MCP operations.

IPFS Kit owns storage and transport behavior, not a competing deontic logic
engine.  It therefore calls the canonical ``ipfs_datasets_py`` package export
before a policy-governed operation and returns the formal-logic provenance plus
the ZKP-ready policy statement to its caller.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def evaluate_execution_policy(
    *,
    actor: str,
    action: str,
    resource: str | None = None,
    policy: Mapping[str, Any] | None = None,
    policy_text: str | Sequence[str] | None = None,
    evaluated_at: str | None = None,
    intent_cid: str | None = None,
    request_zkp_certificate: bool = True,
) -> dict[str, Any]:
    """Delegate Profile D validation to ``ipfs_datasets_py`` or fail closed."""
    try:
        from ipfs_datasets_py.logic.profile_d_policy import evaluate_execution_policy as evaluate
    except Exception as error:
        raise RuntimeError(
            "ipfs_datasets_py Profile D evaluator is unavailable; refusing policy-governed execution"
        ) from error
    return evaluate(
        actor=actor,
        action=action,
        resource=resource,
        policy=policy,
        policy_text=policy_text,
        evaluated_at=evaluated_at,
        intent_cid=intent_cid,
        request_zkp_certificate=request_zkp_certificate,
    )


__all__ = ["evaluate_execution_policy"]
