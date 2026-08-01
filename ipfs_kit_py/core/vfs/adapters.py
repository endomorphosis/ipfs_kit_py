"""Closed compatibility adapters for legacy VFS callers.

The legacy managers expose small string-based APIs.  This module is their
single bridge to :class:`CanonicalVFSService`; it deliberately does not
perform attribute discovery or delegate to provider-specific methods.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final
from uuid import uuid4

from .contracts import AtomicBoundary, VFSOperation, VFSOperationKind
from .service import CanonicalVFSService, VFSExecuteRequest


LEGACY_VFS_OPERATION_KINDS: Final[dict[str, VFSOperationKind]] = {
    "ls": VFSOperationKind.LIST,
    "cat": VFSOperationKind.READ,
    "write": VFSOperationKind.REPLACE,
    "mkdir": VFSOperationKind.MKDIR,
    "rmdir": VFSOperationKind.RMDIR,
    "rm": VFSOperationKind.DELETE,
    "info": VFSOperationKind.STAT,
    "rename": VFSOperationKind.RENAME,
    "move": VFSOperationKind.MOVE,
}


class LegacyVFSAdapter:
    """Project the resolved legacy VFS vocabulary onto the canonical service.

    Unknown legacy operation names are intentionally rejected.  Reopening the
    former dynamic ``getattr`` dispatch would permit an unresolved caller to
    bypass the cutover and makes its state semantics unreviewable.
    """

    def __init__(
        self,
        service: CanonicalVFSService | None = None,
        *,
        journal: Any | None = None,
    ) -> None:
        self._service = service or CanonicalVFSService()
        self._journal = journal

    @property
    def service(self) -> CanonicalVFSService:
        return self._service

    def set_journal(self, journal: Any | None) -> None:
        """Set the journal used after a canonical mutation has committed."""
        self._journal = journal

    async def execute(self, operation: str, **kwargs: Any) -> dict[str, Any]:
        """Execute an admitted legacy operation without manufacturing success."""
        kind = LEGACY_VFS_OPERATION_KINDS.get(operation)
        if kind is None:
            return self._failure(
                operation,
                "unsupported_legacy_operation",
                f"unsupported legacy VFS operation: {operation}",
            )

        try:
            canonical_operation, request = self._build_operation(kind, **kwargs)
        except (TypeError, ValueError) as exc:
            return self._failure(operation, "invalid_legacy_request", str(exc))

        try:
            outcome = self._service.execute(canonical_operation, request)
        except Exception as exc:  # Defensive boundary around an injected service.
            return self._failure(operation, "canonical_service_error", str(exc))

        record = outcome.result.to_record()
        # A result with an error, or without the canonical observed-success
        # acknowledgement, never becomes a legacy success response.
        if outcome.success is not True or record.get("success") is not True or record.get("error"):
            error = record.get("error")
            if not isinstance(error, Mapping):
                error = {}
            return {
                "success": False,
                "operation": operation,
                "operation_id": canonical_operation.operation_id,
                "state": record.get("state"),
                "error": error.get("message", "canonical VFS operation failed"),
                "code": error.get("code", "canonical_operation_failed"),
                "result": record,
            }

        projected: dict[str, Any] = {
            "success": True,
            "operation": operation,
            "operation_id": canonical_operation.operation_id,
            "state": record.get("state"),
            "path": record.get("path", canonical_operation.path),
            "result": record,
            "events": [event.to_record() for event in outcome.events],
        }
        if kind is VFSOperationKind.LIST:
            listing = record.get("listing")
            projected["listing"] = listing
            projected["items"] = listing.get("entries", []) if isinstance(listing, Mapping) else []
        elif kind is VFSOperationKind.STAT:
            projected["info"] = record.get("stat")
        elif kind is VFSOperationKind.READ:
            projected["data"] = outcome.data
        elif kind in {VFSOperationKind.RENAME, VFSOperationKind.MOVE}:
            projected["source_path"] = canonical_operation.source_path
            projected["target_path"] = canonical_operation.target_path
        return projected

    def record_committed_operation(
        self,
        result: Mapping[str, Any],
        operation: str,
        path: str,
        details: Mapping[str, Any] | None = None,
    ) -> str | None:
        """Record only a committed canonical mutation using the real API name."""
        if not self.is_committed_result(result) or self._journal is None:
            return None
        return self._journal.record_operation(
            operation,
            path,
            details=dict(details or {}),
            metadata={"operation_id": result.get("operation_id", "")},
        )

    def get_entries(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """Read journal entries using ``FilesystemJournal.get_entries`` only."""
        if self._journal is None:
            return []
        entries = self._journal.get_entries(limit=limit)
        return [dict(entry) for entry in entries if isinstance(entry, Mapping)]

    @staticmethod
    def is_committed_result(result: Mapping[str, Any] | Any) -> bool:
        if not (
            isinstance(result, Mapping)
            and result.get("success") is True
            and not result.get("error")
        ):
            return False

        # Legacy responses retain the canonical record below ``result``.  A
        # contradictory nested failure must not trigger compatibility events.
        nested_result = result.get("result")
        return not (
            isinstance(nested_result, Mapping)
            and (
                nested_result.get("success") is False
                or bool(nested_result.get("error"))
            )
        )

    @staticmethod
    def _failure(operation: str, code: str, message: str) -> dict[str, Any]:
        return {"success": False, "operation": operation, "code": code, "error": message}

    @staticmethod
    def _payload(value: Any) -> bytes:
        if value is None:
            return b""
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, str):
            return value.encode("utf-8")
        raise TypeError("write payload must be bytes or text")

    def _build_operation(
        self, kind: VFSOperationKind, **kwargs: Any
    ) -> tuple[VFSOperation, VFSExecuteRequest]:
        operation_id = kwargs.get("operation_id") or f"legacy-vfs-{uuid4().hex}"
        if not isinstance(operation_id, str):
            raise TypeError("operation_id must be a string")
        path = kwargs.get("path", "")
        if not isinstance(path, str):
            raise TypeError("path must be a string")
        source_path = kwargs.get("source_path", kwargs.get("old_path", ""))
        target_path = kwargs.get("target_path", kwargs.get("new_path", ""))
        if kind in {VFSOperationKind.RENAME, VFSOperationKind.MOVE}:
            if not isinstance(source_path, str) or not isinstance(target_path, str):
                raise TypeError("source_path and target_path must be strings")
        else:
            source_path = ""
            target_path = ""

        payload = self._payload(
            kwargs.get("data", kwargs.get("content", kwargs.get("payload")))
        )
        page_size = kwargs.get("page_size", kwargs.get("limit", 0))
        if not isinstance(page_size, int):
            raise TypeError("page_size must be an integer")
        cursor = kwargs.get("cursor", "")
        if not isinstance(cursor, str):
            raise TypeError("cursor must be a string")
        return (
            VFSOperation(
                operation_id=operation_id,
                kind=kind,
                path=path,
                source_path=source_path,
                target_path=target_path,
                atomic_boundary=AtomicBoundary.SINGLE_MOUNT,
            ),
            VFSExecuteRequest(payload=payload, page_size=page_size, cursor=cursor),
        )
