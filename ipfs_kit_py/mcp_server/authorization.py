"""Fail-closed authorization for MCP tool dispatch.

This is the sole dispatch gate for protected MCP tools.  Audit records contain
only stable digests and binding values, never bearer tokens or request bodies.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .mcplusplus.ucan import UCANVerifier
from ..mcp.profile_d_policy import ProfileDPolicyProvider, policy_root


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_binding_evidence(envelope: Mapping[str, Any]) -> dict[str, Any]:
    actor = envelope.get("actor", envelope.get("audience"))
    resource = envelope.get("resource")
    request_id = envelope.get("request_id")
    transaction_id = envelope.get("transaction_id")
    return {
        "actor_digest": _digest(actor) if isinstance(actor, str) else None,
        "resource_digest": _digest(resource) if isinstance(resource, str) else None,
        "ability": envelope.get("ability") if isinstance(envelope.get("ability"), str) else None,
        "policy_root": (
            envelope.get("policy_root")
            if isinstance(envelope.get("policy_root"), str)
            else None
        ),
        "request_identity_digest": _digest(
            {
                "request_id": request_id if isinstance(request_id, str) else None,
                "transaction_id": (
                    transaction_id if isinstance(transaction_id, str) else None
                ),
            }
        ),
    }


def semantic_decision_cid(event: Mapping[str, Any]) -> str:
    """CID for the safe, transport-independent authorization semantics."""

    return _digest(
        {
            key: event.get(key)
            for key in (
                "schema",
                "event_type",
                "decision",
                "reason",
                "tool",
                "actor_digest",
                "resource_digest",
                "ability",
                "policy_root",
                "request_identity_digest",
            )
        }
    )


class AuthorizationDenied(PermissionError):
    """A denial safe to return through an MCP transport."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

    def data(self) -> dict[str, str]:
        return {"authorization": "denied", "reason": self.code}


@dataclass(frozen=True)
class AuthorizationDecision:
    request_id: str
    transaction_id: str
    tool: str
    resource: str
    ability: str
    policy_root: str
    envelope_digest: str
    authorization_event_cid: str

    def public(self) -> dict[str, str]:
        return {
            "decision": "allow", "request_id": self.request_id,
            "transaction_id": self.transaction_id, "tool": self.tool,
            "resource_digest": _digest(self.resource), "ability": self.ability,
            "policy_root": self.policy_root, "envelope_digest": self.envelope_digest,
        }


class AuthorizationGate:
    """Bind a tool effect to a validated envelope, UCAN, and Profile D result."""

    def __init__(
        self, *, policy_provider: ProfileDPolicyProvider, ucan_verifier: UCANVerifier | Any | None,
        ledger: Any | None, audit_store: Any | None,
        envelope_validator: Callable[[Mapping[str, Any]], Any] | None = None,
        validator_available: bool = False,
    ) -> None:
        self.policy_provider = policy_provider
        self.ucan_verifier = ucan_verifier
        self.ledger = ledger
        self.audit_store = audit_store
        self.envelope_validator = envelope_validator
        self.validator_available = bool(validator_available)

    @staticmethod
    def _identity(envelope: Mapping[str, Any]) -> tuple[str, str]:
        request_id, transaction_id = envelope.get("request_id"), envelope.get("transaction_id")
        if request_id is not None and (not isinstance(request_id, str) or not request_id):
            raise AuthorizationDenied("invalid_request_identity")
        if transaction_id is not None and (not isinstance(transaction_id, str) or not transaction_id):
            raise AuthorizationDenied("invalid_transaction_identity")
        if request_id is not None and transaction_id is not None and request_id != transaction_id:
            raise AuthorizationDenied("identity_mismatch")
        identity = request_id or transaction_id or str(uuid.uuid4())
        return identity, identity

    def _append(self, event: Mapping[str, Any]) -> str:
        if self.audit_store is None or not callable(getattr(self.audit_store, "append", None)):
            raise AuthorizationDenied("audit_unavailable")
        try:
            record = self.audit_store.append(dict(event))
        except Exception as exc:
            raise AuthorizationDenied("audit_unavailable") from exc
        if not isinstance(record, Mapping) or not isinstance(record.get("event_cid"), str):
            raise AuthorizationDenied("audit_unavailable")
        return record["event_cid"]

    def _deny(self, code: str, *, tool: str = "", envelope: Mapping[str, Any] | None = None) -> None:
        # A denial is not complete until it is durably recorded.  In
        # particular, do not turn an unavailable audit DAG into an unaudited
        # authorization result.
        event = {
            "schema": "ipfs-kit.authorization-audit@1", "event_type": "authorization.decision",
            "timestamp": _now(), "decision": "deny", "reason": code, "tool": tool,
            "envelope_digest": _digest(envelope) if envelope is not None else None,
        }
        if envelope is not None:
            event.update(_safe_binding_evidence(envelope))
        event["semantic_decision_cid"] = semantic_decision_cid(event)
        self._append(event)
        raise AuthorizationDenied(code)

    def authorize(self, *, tool: str, arguments: Mapping[str, Any], envelope: Any) -> AuthorizationDecision:
        if not isinstance(envelope, Mapping):
            self._deny("authorization_envelope_required", tool=tool)
        assert isinstance(envelope, Mapping)
        if not self.validator_available or self.envelope_validator is None:
            self._deny("envelope_validator_unavailable", tool=tool, envelope=envelope)
        try:
            validator_result = self.envelope_validator(envelope)
            if validator_result:
                self._deny("invalid_envelope", tool=tool, envelope=envelope)
        except AuthorizationDenied:
            raise
        except Exception:
            self._deny("invalid_envelope", tool=tool, envelope=envelope)
        if envelope.get("tool") != tool:
            self._deny("tool_binding_mismatch", tool=tool, envelope=envelope)
        resource, ability = envelope.get("resource"), envelope.get("ability")
        actor = envelope.get("actor", envelope.get("audience"))
        if not isinstance(resource, str) or not resource or resource == "*":
            self._deny("invalid_resource_binding", tool=tool, envelope=envelope)
        if not isinstance(ability, str) or ability != tool or ability == "*":
            self._deny("ability_binding_mismatch", tool=tool, envelope=envelope)
        if not isinstance(actor, str) or not actor:
            self._deny("actor_binding_required", tool=tool, envelope=envelope)
        requested_resource = arguments.get("resource")
        if not isinstance(requested_resource, str) or requested_resource != resource:
            self._deny("resource_binding_mismatch", tool=tool, envelope=envelope)
        try:
            expected_policy_root = policy_root(arguments.get("policy"), arguments.get("policy_text"))
        except Exception:
            self._deny("invalid_policy_root", tool=tool, envelope=envelope)
        if envelope.get("policy_root") != expected_policy_root:
            self._deny("policy_root_mismatch", tool=tool, envelope=envelope)
        if self.ledger is None or not bool(getattr(self.ledger, "available", False)):
            self._deny("ledger_unavailable", tool=tool, envelope=envelope)
        if self.ucan_verifier is None or not callable(getattr(self.ucan_verifier, "verify", None)):
            self._deny("ucan_verifier_unavailable", tool=tool, envelope=envelope)
        chain = envelope.get("ucan", envelope.get("ucan_chain", envelope.get("ucans")))
        if chain is None:
            self._deny("ucan_required", tool=tool, envelope=envelope)
        try:
            verified = self.ucan_verifier.verify(
                chain, expected_resource=resource, expected_ability=ability,
                expected_audience=actor, request_bounds=envelope.get("request_bounds") or {},
            )
        except Exception:
            self._deny("ucan_verification_unavailable", tool=tool, envelope=envelope)
        # `allowed` is deliberately the only success signal.  The legacy
        # verifier's `valid` marker only meant a token could be parsed.
        if not bool(getattr(verified, "allowed", False)):
            # Verifier-provided diagnostic text can contain token parser
            # details.  Do not put it in an audit event or transport error.
            self._deny("ucan_denied", tool=tool, envelope=envelope)
        receipt_method = getattr(verified, "to_receipt", None)
        if not callable(receipt_method):
            self._deny("ucan_receipt_unavailable", tool=tool, envelope=envelope)
        try:
            verifier_receipt = receipt_method()
        except Exception:
            self._deny("ucan_receipt_unavailable", tool=tool, envelope=envelope)
        if not isinstance(verifier_receipt, Mapping):
            self._deny("ucan_receipt_unavailable", tool=tool, envelope=envelope)
        if not bool(getattr(self.policy_provider, "available", False)):
            self._deny("policy_provider_unavailable", tool=tool, envelope=envelope)
        try:
            evaluation = self.policy_provider.evaluate(
                actor=actor, action=ability, resource=resource, policy=arguments.get("policy"),
                policy_text=arguments.get("policy_text"), intent_cid=envelope.get("intent_cid"),
                request_zkp_certificate=False,
            )
        except Exception:
            self._deny("policy_provider_unavailable", tool=tool, envelope=envelope)
        if not isinstance(evaluation, Mapping) or evaluation.get("decision") != "allow":
            self._deny("policy_denied", tool=tool, envelope=envelope)
        if evaluation.get("policy_root", expected_policy_root) != expected_policy_root:
            self._deny("policy_root_mismatch", tool=tool, envelope=envelope)
        try:
            request_id, transaction_id = self._identity(envelope)
        except AuthorizationDenied as error:
            self._deny(error.code, tool=tool, envelope=envelope)
        envelope_digest = _digest(envelope)
        event = {
            "schema": "ipfs-kit.authorization-audit@1", "event_type": "authorization.decision",
            "timestamp": _now(), "decision": "allow", "request_id": request_id,
            "transaction_id": transaction_id, "tool": tool, "ability": ability,
            "actor_digest": _digest(actor),
            "resource_digest": _digest(resource), "policy_root": expected_policy_root,
            "request_identity_digest": _digest(
                {"request_id": request_id, "transaction_id": transaction_id}
            ),
            "envelope_digest": envelope_digest,
            "ucan_receipt": self._redacted_ucan_receipt(verifier_receipt),
        }
        event["semantic_decision_cid"] = semantic_decision_cid(event)
        event_cid = self._append(event)
        return AuthorizationDecision(request_id, transaction_id, tool, resource, ability, expected_policy_root, envelope_digest, event_cid)

    def record_effect(self, decision: AuthorizationDecision, result: Any) -> str:
        return self._append({
            "schema": "ipfs-kit.authorization-audit@1", "event_type": "authorization.effect",
            "timestamp": _now(), "decision": "allow", "request_id": decision.request_id,
            "transaction_id": decision.transaction_id,
            "parents": [decision.authorization_event_cid],
            "authorization_event_cid": decision.authorization_event_cid, "tool": decision.tool,
            "ability": decision.ability, "resource_digest": _digest(decision.resource),
            "policy_root": decision.policy_root, "envelope_digest": decision.envelope_digest,
            "result_digest": _digest(result),
        })

    @staticmethod
    def _redacted_ucan_receipt(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
        """Allow-list verifier evidence; never persist bearer-token fields."""

        return {
            key: value
            for key in ("schema", "allowed", "code", "chain_length")
            if isinstance((value := receipt.get(key)), (str, bool, int))
        }


__all__ = [
    "AuthorizationDecision",
    "AuthorizationDenied",
    "AuthorizationGate",
    "semantic_decision_cid",
]
