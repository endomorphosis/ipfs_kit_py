"""MCP++ Profile C (UCAN delegation) + Profile D (policy) — kit port.

Dependency-light, deterministic delegation-chain validation matching the
unsigned-path semantics of ipfs_accelerate_py so authorization decisions are
interoperable. Capabilities are {resource, ability}; chains attenuate root->leaf
and audience(i) must equal issuer(i+1).
"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _caps(raw: Iterable[Dict[str, Any]]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        r = str(item.get("resource") or item.get("with") or "").strip() or "*"
        a = str(item.get("ability") or item.get("can") or "").strip() or "*"
        out.append((r, a))
    return out


def _matches(cap: Tuple[str, str], *, resource: str, ability: str) -> bool:
    return cap[0] in {"*", resource} and cap[1] in {"*", ability}


def _covers(parent: List[Tuple[str, str]], child: List[Tuple[str, str]]) -> bool:
    if not child:
        return False
    return all(any(_matches(p, resource=c[0], ability=c[1]) for p in parent) for c in child)


def validate_raw_delegation_chain(
    *, raw_chain: Iterable[Dict[str, Any]], resource: str, ability: str, actor: str = "", now: Optional[float] = None
) -> Dict[str, Any]:
    """Return {allowed, reason, chain_length, failure_hop} — unsigned semantics."""
    chain = [d for d in raw_chain if isinstance(d, dict)]
    n = len(chain)
    if not chain:
        return {"allowed": False, "reason": "missing_delegation_chain", "chain_length": 0, "failure_hop": None}
    t = float(now if now is not None else time.time())

    def res(ok: bool, reason: str, hop=None):
        return {"allowed": ok, "reason": reason, "chain_length": n, "failure_hop": hop}

    parsed = [(_caps(d.get("capabilities", [])), d) for d in chain]
    for i, (_, d) in enumerate(parsed):
        if not str(d.get("issuer", "")).strip() or not str(d.get("audience", "")).strip():
            return res(False, f"invalid_principal_at_hop_{i}", i)
        if d.get("revoked"):
            return res(False, f"revoked_at_hop_{i}", i)
        if d.get("expiry") is not None and t > float(d["expiry"]):
            return res(False, f"expired_at_hop_{i}", i)
    for i in range(n - 1):
        if chain[i].get("audience") != chain[i + 1].get("issuer"):
            return res(False, f"broken_chain_at_hop_{i}", i + 1)
    for i in range(n - 1):
        if not _covers(parsed[i][0], parsed[i + 1][0]):
            return res(False, f"capability_escalation_at_hop_{i+1}", i + 1)
    leaf = parsed[-1]
    if actor and leaf[1].get("audience") != actor:
        return res(False, "actor_mismatch", n - 1)
    if not any(_matches(c, resource=resource, ability=ability) for c in leaf[0]):
        return res(False, "capability_not_granted", n - 1)
    return res(True, "allowed", None)


def evaluate_policy(*, tool: str, deny: Optional[Iterable[str]] = None, risk: float = 0.0, threshold: float = 0.7) -> Dict[str, Any]:
    """Profile D: deterministic allow/deny decision for a tool invocation."""
    deny_set = {str(x).strip() for x in (deny or [])}
    if tool in deny_set:
        return {"decision": "deny", "reason": "tool_denied", "tool": tool}
    if risk >= threshold:
        return {"decision": "deny", "reason": "risk_threshold", "tool": tool}
    return {"decision": "allow", "reason": "ok", "tool": tool}
