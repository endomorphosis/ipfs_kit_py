"""Agent Supervisor immutable receipt resolution owned by ``ipfs_kit_py``.

The resolver deliberately has no fixture or synthetic-success fallback.  A
receipt is returned only when its content-addressed artifact can be loaded and
verified by :class:`DurableCoordinationStore`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from .mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    DurableCoordinationStore,
)

METHOD = "agent_supervisor.receipts.read"
CAPABILITY_ID = "supervisor.receipts.read"
OWNER = "ipfs_kit_py"
MAX_LIMIT = 500
_PAYLOAD_KEYS = frozenset({"receipt_ids", "limit", "cursor", "status", "target_id"})
_ENVELOPE_KEYS = frozenset({
    "owner", "capability_id", "method", "access", "policy_class", "correlation_id",
})


class AgentSupervisorReceiptResolver:
    """Resolve verified receipt artifacts from the kit immutable block store."""

    def __init__(self, store: DurableCoordinationStore | None = None) -> None:
        self.store = store or DurableCoordinationStore()

    def read(self, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if params is not None and not isinstance(params, Mapping):
            return _denied("scope_not_allowed", "Receipt resolution requires an object payload")
        raw = dict(params or {})
        correlation_id = raw.get("correlation_id")
        envelope_error = _validate_envelope(raw)
        if envelope_error:
            return _denied("scope_not_allowed", envelope_error, correlation_id=correlation_id)
        request = _payload(raw)
        if request is None:
            return _denied(
                "scope_not_allowed", "Receipt resolution payload must be an object",
                correlation_id=correlation_id,
            )
        unknown = sorted(set(request).difference(_PAYLOAD_KEYS))
        if unknown:
            return _denied(
                "scope_not_allowed",
                f"Unsupported receipt resolution fields: {', '.join(unknown)}",
                correlation_id=correlation_id,
            )
        requested = request.get("receipt_ids")
        if requested is not None and (
            not isinstance(requested, Sequence) or isinstance(requested, (str, bytes))
        ):
            return _denied(
                "scope_not_allowed", "receipt_ids must be an array of receipt IDs or CIDs",
                correlation_id=correlation_id,
            )
        if requested is not None and any(not isinstance(value, str) or not value.strip() for value in requested):
            return _denied(
                "scope_not_allowed", "receipt_ids entries must be non-empty strings",
                correlation_id=correlation_id,
            )

        try:
            limit = _bounded_limit(request.get("limit"))
            cursor = _cursor(request.get("cursor"))
            status = _optional_string(request.get("status"))
            target_id = _optional_string(request.get("target_id"))
        except ValueError as exc:
            return _denied("scope_not_allowed", str(exc), correlation_id=correlation_id)
        rows = self._artifact_rows()
        by_id: dict[str, tuple[str, dict[str, Any], int]] = {}
        for cid, artifact, stored_at_ms in rows:
            if not _is_receipt(artifact):
                continue
            if status is not None and str(artifact.get("status", "")) != status:
                continue
            if target_id is not None and not _matches_target(artifact, target_id):
                continue
            receipt_id = str(artifact.get("receipt_id") or artifact.get("receiptId") or cid)
            by_id[receipt_id] = (cid, artifact, stored_at_ms)
            by_id.setdefault(cid, (cid, artifact, stored_at_ms))

        missing: list[str] = []
        selected: list[tuple[str, dict[str, Any], int]] = []
        if requested is not None:
            seen: set[str] = set()
            for value in requested:
                receipt_id = str(value).strip()
                if not receipt_id or receipt_id in seen:
                    continue
                seen.add(receipt_id)
                row = by_id.get(receipt_id)
                if row is None:
                    # A CID may exist in the backend but not the local index.
                    row = self._load_direct(receipt_id)
                if (
                    row is None
                    or not _is_receipt(row[1])
                    or (status is not None and str(row[1].get("status", "")) != status)
                    or (target_id is not None and not _matches_target(row[1], target_id))
                ):
                    missing.append(receipt_id)
                else:
                    selected.append(row)
            if missing:
                return _unavailable(
                    "receipt_unavailable",
                    "One or more immutable receipts could not be resolved: " + ", ".join(missing),
                    correlation_id=correlation_id,
                )
        else:
            # Deduplicate the receipt-id and CID aliases above.
            selected = list({row[0]: row for row in by_id.values()}.values())
            selected.sort(key=lambda row: (row[2], row[0]), reverse=True)

        selected = selected[cursor : cursor + limit]
        data = []
        for cid, artifact, stored_at_ms in selected:
            reference = {
                "receipt_id": str(artifact.get("receipt_id") or artifact.get("receiptId") or cid),
                "cid": cid,
                "owner": OWNER,
            }
            created_at = _created_at(artifact, stored_at_ms)
            if created_at is not None:
                reference["created_at"] = created_at
            data.append(reference)
        result = {
            "state": "available",
            "capability_id": CAPABILITY_ID,
            "owner": OWNER,
            "data": data,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        if correlation_id is not None:
            result["correlation_id"] = correlation_id
        return result

    def _artifact_rows(self) -> list[tuple[str, dict[str, Any], int]]:
        """Read the rebuildable index, then verify every selected block."""
        with self.store._lock:  # same lock used by the store's public reads
            indexed = self.store._connection.execute(
                "SELECT cid, stored_at_ms FROM artifacts ORDER BY stored_at_ms DESC, cid DESC"
            ).fetchall()
        rows: list[tuple[str, dict[str, Any], int]] = []
        for row in indexed:
            try:
                rows.append((str(row["cid"]), self.store.get(str(row["cid"])), int(row["stored_at_ms"])))
            except (ArtifactNotFound, ArtifactIntegrityError, ValueError):
                # Corrupt or missing immutable evidence is never reported as a
                # successfully resolved receipt.
                continue
        return rows

    def _load_direct(self, receipt_id: str) -> tuple[str, dict[str, Any], int] | None:
        if not receipt_id.startswith("b"):
            return None
        try:
            artifact = self.store.get(receipt_id)
        except (ArtifactNotFound, ArtifactIntegrityError, ValueError):
            return None
        return receipt_id, artifact, int(artifact.get("created_at_ms", 0) or 0)


def descriptor() -> dict[str, Any]:
    """MCP/Profile-A descriptor for the direct HTTP and Profile-E method."""
    input_schema = {
        "type": "object",
        "properties": {
            "receipt_ids": {"type": "array", "items": {"type": "string", "minLength": 1}},
            "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT},
            "cursor": {"type": "string"},
            "status": {"type": "string"},
            "target_id": {"type": "string"},
        },
        "additionalProperties": False,
    }
    receipt_ref = {
        "type": "object",
        "required": ["receipt_id", "owner"],
        "properties": {
            "receipt_id": {"type": "string", "minLength": 1},
            "cid": {"type": "string", "minLength": 1},
            "owner": {"const": OWNER},
            "created_at": {"type": "string"},
        },
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "required": ["state", "capability_id", "owner"],
        "properties": {
            "state": {"enum": ["available", "unavailable", "denied"]},
            "capability_id": {"const": CAPABILITY_ID},
            "owner": {"const": OWNER},
            "data": {"type": "array", "items": receipt_ref},
            "reason": {
                "enum": ["receipt_unavailable", "scope_not_allowed"],
            },
            "message": {"type": "string"},
            "policy_class": {"const": "read"},
            "correlation_id": {"type": ["string", "null"]},
            "observed_at": {"type": "string"},
        },
        "additionalProperties": False,
    }
    return {
        "namespace": "agent_supervisor",
        "name": METHOD,
        "description": "Resolve verified immutable Agent Supervisor receipt references.",
        "owner": OWNER,
        "access": "read",
        "transports": ["mcp", "mcp++", "libp2p"],
        "inputSchema": input_schema,
        "input_schema": input_schema,
        "outputSchema": output_schema,
        "output_schema": output_schema,
        "errors": ["receipt_unavailable", "scope_not_allowed"],
        "semantic_tags": ["agent-supervisor", "receipt", "immutable", "read"],
        "compatibility": {"mcp": True, "mcp++": True},
    }


def _payload(params: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(params, Mapping):
        return {}
    payload = params.get("payload")
    if "payload" in params:
        return dict(payload) if isinstance(payload, Mapping) else None
    return {key: value for key, value in params.items() if key not in _ENVELOPE_KEYS}


def _validate_envelope(params: Mapping[str, Any]) -> str | None:
    expected = {
        "owner": OWNER,
        "capability_id": CAPABILITY_ID,
        "method": METHOD,
        "access": "read",
        "policy_class": "read",
    }
    for field, value in expected.items():
        if field in params and params.get(field) != value:
            return f"{METHOD} requires {field}={value}"
    return None


def _is_receipt(artifact: Mapping[str, Any]) -> bool:
    schema = str(artifact.get("schema", "")).lower()
    kind = str(artifact.get("kind", "")).lower()
    return (
        kind == "agentsupervisorreceipt"
        or schema == "swissknife/agent-supervisor/receipt@1"
        or schema == "ipfs_kit.agent_supervisor_receipt.v1"
    )


def _bounded_limit(value: Any) -> int:
    if value is None:
        return 50
    if isinstance(value, bool):
        raise ValueError(f"limit must be an integer between 1 and {MAX_LIMIT}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"limit must be an integer between 1 and {MAX_LIMIT}") from exc
    if parsed < 1 or parsed > MAX_LIMIT:
        raise ValueError(f"limit must be an integer between 1 and {MAX_LIMIT}")
    return parsed


def _cursor(value: Any) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, bool):
        raise ValueError("cursor must be a non-negative integer string")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("cursor must be a non-negative integer string") from exc
    if parsed < 0 or str(parsed) != str(value):
        raise ValueError("cursor must be a non-negative integer string")
    return parsed


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("status and target_id filters must be strings")
    return value


def _matches_target(artifact: Mapping[str, Any], target_id: str) -> bool:
    candidates = {
        str(artifact.get(key) or "")
        for key in ("target_id", "task_id", "goal_id", "subgoal_id", "normalized_target")
    }
    return target_id in candidates or any(value.endswith(f":{target_id}") for value in candidates)


def _created_at(artifact: Mapping[str, Any], stored_at_ms: int) -> str | None:
    value = artifact.get("created_at") or artifact.get("createdAt")
    if value:
        return str(value)
    millis = artifact.get("created_at_ms", stored_at_ms)
    try:
        return datetime.fromtimestamp(int(millis) / 1000, timezone.utc).isoformat() if int(millis) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _unavailable(
    reason: str,
    message: str,
    *,
    correlation_id: Any = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "state": "unavailable",
        "capability_id": CAPABILITY_ID,
        "owner": OWNER,
        "reason": reason,
        "message": message,
    }
    if correlation_id is not None:
        result["correlation_id"] = correlation_id
    return result


def _denied(reason: str, message: str, *, correlation_id: Any = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "state": "denied",
        "capability_id": CAPABILITY_ID,
        "owner": OWNER,
        "reason": reason,
        "message": message,
        "policy_class": "read",
    }
    if correlation_id is not None:
        result["correlation_id"] = correlation_id
    return result


__all__ = ["AgentSupervisorReceiptResolver", "CAPABILITY_ID", "MAX_LIMIT", "METHOD", "OWNER", "descriptor"]
