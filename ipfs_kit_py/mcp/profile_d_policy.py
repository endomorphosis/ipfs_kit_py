"""Canonical, fail-closed Profile D policy provider.

The MCP server does not maintain a second deontic evaluator.  This adapter is
both the policy decision source and the source of advertised Profile D state.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping, Sequence


def policy_root(
    policy: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    policy_text: str | Sequence[str] | None = None,
) -> str:
    """Return the stable root that an authorization envelope must bind."""
    payload = {"policy": policy or (), "policy_text": policy_text or ""}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class ProfileDPolicyProvider:
    """The single Profile D provider used by MCP advertisement and decisions."""

    provider_id = "ipfs_datasets_py.profile_d_policy"

    def __init__(self, evaluator: Callable[..., Mapping[str, Any]] | None = None) -> None:
        self._evaluator = evaluator
        self._load_error: Exception | None = None

    def _resolve(self) -> Callable[..., Mapping[str, Any]] | None:
        if self._evaluator is not None:
            return self._evaluator
        if self._load_error is not None:
            return None
        try:
            from ipfs_datasets_py.logic.profile_d_policy import (
                evaluate_execution_policy as evaluate,
            )
        except Exception as error:
            self._load_error = error
            return None
        self._evaluator = evaluate
        return evaluate

    @property
    def available(self) -> bool:
        return self._resolve() is not None

    def metadata(self) -> Mapping[str, Any]:
        return {
            "provider": self.provider_id,
            "available": self.available,
            "fail_closed": True,
        }

    def evaluate(
        self,
        *,
        actor: str,
        action: str,
        resource: str | None = None,
        policy: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
        policy_text: str | Sequence[str] | None = None,
        evaluated_at: str | None = None,
        intent_cid: str | None = None,
        request_zkp_certificate: bool = True,
        **context: Any,
    ) -> Mapping[str, Any]:
        evaluator = self._resolve()
        if evaluator is None:
            raise RuntimeError(
                "ipfs_datasets_py Profile D evaluator is unavailable; refusing policy-governed execution"
            ) from self._load_error
        result = dict(evaluator(
            actor=actor, action=action, resource=resource, policy=policy,
            policy_text=policy_text, evaluated_at=evaluated_at, intent_cid=intent_cid,
            request_zkp_certificate=request_zkp_certificate, **context,
        ))
        result.setdefault("policy_provider", self.provider_id)
        result.setdefault("policy_root", policy_root(policy, policy_text))
        return result


_DEFAULT_PROVIDER = ProfileDPolicyProvider()


def get_profile_d_policy_provider() -> ProfileDPolicyProvider:
    return _DEFAULT_PROVIDER


def evaluate_execution_policy(
    *,
    actor: str,
    action: str,
    resource: str | None = None,
    policy: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    policy_text: str | Sequence[str] | None = None,
    evaluated_at: str | None = None,
    intent_cid: str | None = None,
    request_zkp_certificate: bool = True,
) -> Mapping[str, Any]:
    """Evaluate Profile D through the canonical provider or fail closed."""
    return get_profile_d_policy_provider().evaluate(
        actor=actor, action=action, resource=resource, policy=policy,
        policy_text=policy_text, evaluated_at=evaluated_at, intent_cid=intent_cid,
        request_zkp_certificate=request_zkp_certificate,
    )


__all__ = [
    "ProfileDPolicyProvider",
    "evaluate_execution_policy",
    "get_profile_d_policy_provider",
    "policy_root",
]
