"""CID-native execution artifact helpers for MCP++ Profile B (ipfs_kit_py).

Receipts, output and intent CIDs use the canonical Kubo CIDv1 base32 profile so
output CIDs and intent CIDs are interoperable across servers. The canonical
content address is a Kubo-conformant CIDv1 (raw, sha2-256, base32) -> bafkrei…
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, Optional


def canonicalize_artifact(payload: Dict[str, Any]) -> bytes:
    """Return deterministic bytes for artifact content."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _base32_lower_nopad(data: bytes) -> str:
    import base64
    return base64.b32encode(data).decode("ascii").rstrip("=").lower()


def compute_artifact_cid(payload: Dict[str, Any]) -> str:
    """Kubo-conformant CIDv1 (raw codec, sha2-256, base32) -> bafkrei...

    Bytes: multibase 'b' + base32(<0x01 cidv1><0x55 raw><0x12 sha256><0x20 len><digest>).
    Dependency-free and identical to multiformats cid_for_obj(codec=raw, base32).
    """
    digest = hashlib.sha256(canonicalize_artifact(payload)).digest()
    cid_bytes = bytes([0x01, 0x55, 0x12, 0x20]) + digest
    return "b" + _base32_lower_nopad(cid_bytes)


def build_intent(*, interface_cid: str, tool: str, input_cid: str, correlation_id: str = "") -> Dict[str, Any]:
    return {
        "interface_cid": interface_cid,
        "tool": tool,
        "input_cid": input_cid,
        "expected_output_schema_cid": "",
        "constraints_policy_cid": "",
        "correlation_id": correlation_id,
        "declared_side_effects": [],
    }


def build_decision(*, decision: str, intent_cid: str) -> Dict[str, Any]:
    return {
        "decision": decision,
        "intent_cid": intent_cid,
        "policy_cid": "",
        "proofs_checked": [],
        "evaluation_witness_cid": "",
        "justification": "",
        "obligations": [],
        "policy_version": "",
        "evaluator_dids": [],
        "signatures": [],
    }


def build_receipt(*, intent_cid: str, output_cid: str, decision_cid: str, correlation_id: str = "") -> Dict[str, Any]:
    return {
        "intent_cid": intent_cid,
        "output_cid": output_cid,
        "observed_side_effects": [],
        "proofs_checked": [],
        "decision_cid": decision_cid,
        "correlation_id": correlation_id,
        "time_observed": "",
        "signatures": [],
    }


def envelope_from_payloads(
    *,
    interface_cid: str,
    input_payload: Dict[str, Any],
    tool: str,
    output_payload: Dict[str, Any],
    correlation_id: str = "",
    parents: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Build a full immutable artifact envelope and return payloads + CIDs."""
    input_cid = compute_artifact_cid(input_payload)
    output_cid = compute_artifact_cid(output_payload)
    intent = build_intent(interface_cid=interface_cid, tool=tool, input_cid=input_cid, correlation_id=correlation_id)
    intent_cid = compute_artifact_cid(intent)
    decision = build_decision(decision="allow", intent_cid=intent_cid)
    decision_cid = compute_artifact_cid(decision)
    receipt = build_receipt(
        intent_cid=intent_cid, output_cid=output_cid, decision_cid=decision_cid, correlation_id=correlation_id
    )
    receipt_cid = compute_artifact_cid(receipt)
    event = {
        "parents": list(parents or []),
        "interface_cid": interface_cid,
        "intent_cid": intent_cid,
        "decision_cid": decision_cid,
        "output_cid": output_cid,
        "receipt_cid": receipt_cid,
        "peer_did": "",
        "timestamps": {},
    }
    event_cid = compute_artifact_cid(event)
    return {
        "input_cid": input_cid,
        "intent_cid": intent_cid,
        "decision_cid": decision_cid,
        "output_cid": output_cid,
        "receipt_cid": receipt_cid,
        "event_cid": event_cid,
        "event": event,
        "success": True,
    }
