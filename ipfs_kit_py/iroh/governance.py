"""Governed operation boundary shared by the Iroh MCP and HTTP surfaces.

This module deliberately exposes a small allowlist of operations backed by the
managed Iroh runtime.  It owns authorization, destructive confirmation,
operation envelopes, progress reporting, audit records, input validation, and
safe error translation so transports cannot accidentally diverge.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import os
import re
import threading
import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from .blob_store import IrohBlobStore, TransferProgress, validate_blob_hash
from .config import IrohServiceConfig, validate_instance_name
from .errors import (
    IrohConflictError,
    IrohError,
    IrohIntegrityError,
    IrohInvalidConfigError,
    IrohNotFoundError,
    IrohPermissionDeniedError,
    IrohTimeoutError,
    IrohUnavailableError,
)
from .service import IrohService


MAX_TICKET_BYTES = 1024 * 1024
_OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class IrohPermission(str, Enum):
    """Independent permissions understood by every governed transport."""

    READ = "iroh.read"
    CONTROL = "iroh.control"
    DESTRUCTIVE = "iroh.destructive"


class GovernedOperationError(RuntimeError):
    """Typed, public failure that is safe to serialize."""

    def __init__(self, code: str, message: str, *, status_code: int = 400, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.public_message = message
        self.status_code = status_code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class OperationDefinition:
    name: str
    permission: IrohPermission
    description: str
    handler: str
    input_schema: Mapping[str, Any]
    destructive: bool = False


@dataclass(slots=True)
class AuditRecord:
    audit_id: str
    operation_id: str
    operation: str
    permission: str
    outcome: str
    started_at: str
    finished_at: str
    actor: str
    error_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class AuditSink(Protocol):
    def append(self, record: Mapping[str, Any]) -> None: ...


@dataclass(slots=True)
class MemoryAuditSink:
    """Thread-safe audit sink useful for embedding and tests."""

    records: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def append(self, record: Mapping[str, Any]) -> None:
        with self._lock:
            self.records.append(dict(record))


class JSONLinesAuditSink:
    """Owner-only append-only JSONL audit sink for server processes."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def append(self, record: Mapping[str, Any]) -> None:
        payload = json.dumps(dict(record), sort_keys=True, separators=(",", ":")) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, payload.encode("utf-8"))
            finally:
                os.close(fd)


def _object_schema(properties: Mapping[str, Any], required: Iterable[str] = ()) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": dict(properties),
        "additionalProperties": False,
    }
    required_values = list(required)
    if required_values:
        schema["required"] = required_values
    return schema


_INSTANCE = {
    "type": "string",
    "pattern": "^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$",
    "default": "default",
}
_OPERATION_ID = {
    "type": "string",
    "pattern": "^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
}
_HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
_COMMON = {"instance": _INSTANCE, "operation_id": _OPERATION_ID}


OPERATION_DEFINITIONS: dict[str, OperationDefinition] = {
    "diagnostics": OperationDefinition(
        "diagnostics",
        IrohPermission.READ,
        "Read a redacted health receipt or bounded-label metrics.",
        "_diagnostics",
        _object_schema({**_COMMON, "format": {"type": "string", "enum": ["health", "metrics", "prometheus"], "default": "health"}, "persist": {"type": "boolean", "default": True}}),
    ),
    "service.status": OperationDefinition(
        "service.status", IrohPermission.READ, "Read managed Iroh service status.", "_service_status", _object_schema(_COMMON)
    ),
    "blob.stat": OperationDefinition(
        "blob.stat", IrohPermission.READ, "Read verified immutable blob metadata.", "_blob_stat", _object_schema({**_COMMON, "blob_hash": _HASH}, ["blob_hash"])
    ),
    "service.start": OperationDefinition(
        "service.start", IrohPermission.CONTROL, "Start the managed Iroh service.", "_service_start", _object_schema(_COMMON)
    ),
    "blob.fetch": OperationDefinition(
        "blob.fetch", IrohPermission.CONTROL, "Fetch and verify an immutable blob from an explicit provider.", "_blob_fetch", _object_schema({**_COMMON, "blob_hash": _HASH, "provider": {"type": "string", "minLength": 1, "maxLength": 2048}}, ["blob_hash", "provider"])
    ),
    "ticket.import": OperationDefinition(
        "ticket.import", IrohPermission.CONTROL, "Import and verify a bearer read ticket without reflecting it.", "_ticket_import", _object_schema({**_COMMON, "ticket": {"type": "string", "minLength": 1, "maxLength": MAX_TICKET_BYTES, "writeOnly": True}, "expected_hash": _HASH}, ["ticket", "expected_hash"])
    ),
    "service.stop": OperationDefinition(
        "service.stop", IrohPermission.DESTRUCTIVE, "Stop the managed Iroh service.", "_service_stop", _object_schema(_COMMON), True
    ),
    "service.restart": OperationDefinition(
        "service.restart", IrohPermission.DESTRUCTIVE, "Restart the managed Iroh service.", "_service_restart", _object_schema(_COMMON), True
    ),
}


def normalize_permissions(values: Iterable[str | IrohPermission] | str | IrohPermission | None) -> frozenset[str]:
    if values is None:
        return frozenset({IrohPermission.READ.value})
    if isinstance(values, (str, IrohPermission)):
        values = [values]
    normalized: set[str] = set()
    aliases = {
        "read": IrohPermission.READ.value,
        "control": IrohPermission.CONTROL.value,
        "destructive": IrohPermission.DESTRUCTIVE.value,
    }
    for value in values:
        text = value.value if isinstance(value, IrohPermission) else str(value).strip().lower()
        if text in aliases:
            text = aliases[text]
        if text in {permission.value for permission in IrohPermission} or text in {"iroh.*", "*"}:
            normalized.add(text)
    return frozenset(normalized)


def validate_ticket(value: Any) -> str:
    """Validate a ticket's safe outer encoding without parsing secret contents."""

    if not isinstance(value, str):
        raise GovernedOperationError("invalid_ticket", "ticket must be a string")
    size = len(value.encode("utf-8"))
    if not value or size > MAX_TICKET_BYTES or value != value.strip():
        raise GovernedOperationError("invalid_ticket", "ticket is empty or malformed")
    if any(ord(character) < 33 or ord(character) == 127 for character in value):
        raise GovernedOperationError("invalid_ticket", "ticket is empty or malformed")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {key: _jsonable(item) for key, item in dataclasses.asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return os.fspath(value)
    return value


class IrohOperationController:
    """Execute the transport-neutral allowlist with governance guarantees."""

    def __init__(
        self,
        *,
        state_root: str | os.PathLike[str] | None = None,
        service_factory: Callable[[IrohServiceConfig], Any] = IrohService,
        blob_store_factory: Callable[[Any], Any] = IrohBlobStore,
        client_factory: Callable[[IrohServiceConfig], Any] | None = None,
        audit_sink: AuditSink | None = None,
        diagnostics_handler: Callable[..., Awaitable[Mapping[str, Any]]] | None = None,
    ) -> None:
        self.state_root = state_root
        self.service_factory = service_factory
        self.blob_store_factory = blob_store_factory
        self.client_factory = client_factory
        self.audit_sink = audit_sink or MemoryAuditSink()
        self.diagnostics_handler = diagnostics_handler

    async def execute(
        self,
        operation: str,
        arguments: Mapping[str, Any] | None,
        *,
        permissions: Iterable[str | IrohPermission] | str | IrohPermission | None = None,
        confirm: bool = False,
        actor: str = "anonymous",
    ) -> dict[str, Any]:
        started = _now()
        op_id = self._operation_id(arguments)
        progress = [{"sequence": 0, "state": "accepted", "at": started}]
        definition = OPERATION_DEFINITIONS.get(operation)
        public_operation = operation if definition is not None else "unsupported"
        try:
            if definition is None:
                raise GovernedOperationError("unsupported_operation", "Iroh operation is not exposed", status_code=404)
            args = self._validate_arguments(definition, arguments)
            allowed = normalize_permissions(permissions)
            if definition.permission.value not in allowed and "iroh.*" not in allowed and "*" not in allowed:
                raise GovernedOperationError("permission_denied", "permission is required for this Iroh operation", status_code=403)
            if definition.destructive and confirm is not True:
                raise GovernedOperationError("confirmation_required", "explicit confirmation is required for this destructive Iroh operation", status_code=409)
            progress.append({"sequence": 1, "state": "running", "at": _now()})
            result = await getattr(self, definition.handler)(args, progress)
            progress.append({"sequence": len(progress), "state": "completed", "at": _now()})
            audit = self._audit(definition, op_id, actor, started, "success")
            return {
                "success": True,
                "operation": public_operation,
                "operation_id": op_id,
                "permission": definition.permission.value,
                "progress": progress,
                "result": _jsonable(result),
                "audit": audit,
            }
        except Exception as exc:
            error = self._public_error(exc)
            progress.append({"sequence": len(progress), "state": "failed", "at": _now(), "code": error["code"]})
            audit_definition = definition or OperationDefinition(
                public_operation, IrohPermission.READ, "", "", {}
            )
            audit = self._audit(audit_definition, op_id, actor, started, "failure", error["code"])
            return {
                "success": False,
                "operation": public_operation,
                "operation_id": op_id,
                "permission": definition.permission.value if definition else None,
                "progress": progress,
                "error": error,
                "audit": audit,
            }

    @staticmethod
    def _operation_id(arguments: Mapping[str, Any] | None) -> str:
        value = arguments.get("operation_id") if isinstance(arguments, Mapping) else None
        if value is None:
            return str(uuid.uuid4())
        if not isinstance(value, str) or not _OPERATION_ID_RE.fullmatch(value):
            return str(uuid.uuid4())
        return value

    @staticmethod
    def _validate_arguments(definition: OperationDefinition, value: Mapping[str, Any] | None) -> dict[str, Any]:
        if value is not None and not isinstance(value, Mapping):
            raise GovernedOperationError("invalid_arguments", "arguments must be an object")
        args = dict(value or {})
        schema = definition.input_schema
        properties = schema.get("properties", {})
        if set(args) - set(properties):
            raise GovernedOperationError("invalid_arguments", "arguments contain unsupported fields")
        for required in schema.get("required", []):
            if required not in args:
                raise GovernedOperationError("invalid_arguments", "required argument is missing")
        try:
            args["instance"] = validate_instance_name(args.get("instance", "default"))
            if "operation_id" in args and (
                not isinstance(args["operation_id"], str)
                or not _OPERATION_ID_RE.fullmatch(args["operation_id"])
            ):
                raise GovernedOperationError(
                    "invalid_arguments", "operation_id is invalid"
                )
            if "blob_hash" in args:
                args["blob_hash"] = validate_blob_hash(args["blob_hash"])
            if "expected_hash" in args:
                args["expected_hash"] = validate_blob_hash(args["expected_hash"])
            if "ticket" in args:
                args["ticket"] = validate_ticket(args["ticket"])
        except GovernedOperationError:
            raise
        except Exception:
            raise GovernedOperationError("invalid_arguments", "Iroh operation arguments are invalid") from None
        if "provider" in args and (not isinstance(args["provider"], str) or not args["provider"] or len(args["provider"]) > 2048):
            raise GovernedOperationError("invalid_arguments", "provider is invalid")
        if "persist" in args and not isinstance(args["persist"], bool):
            raise GovernedOperationError("invalid_arguments", "persist must be boolean")
        if args.get("format", "health") not in {"health", "metrics", "prometheus"}:
            raise GovernedOperationError("invalid_arguments", "diagnostic format is invalid")
        return args

    def _config(self, args: Mapping[str, Any]) -> IrohServiceConfig:
        return IrohServiceConfig.default(args["instance"], state_root=self.state_root, enabled=True)

    def _client(self, config: IrohServiceConfig) -> Any:
        if self.client_factory is not None:
            return self.client_factory(config)
        from .client import IrohRuntimeClient

        return IrohRuntimeClient(endpoint=config.rpc_endpoint)

    async def _close(self, value: Any) -> None:
        method = getattr(value, "aclose", None) or getattr(value, "close", None)
        if method is not None:
            result = method()
            if inspect.isawaitable(result):
                await result

    async def _diagnostics(self, args: dict[str, Any], _progress: list[dict[str, Any]]) -> Any:
        if self.diagnostics_handler is None:
            from ipfs_kit_py.mcp.servers.iroh_mcp_tools import _run_diagnostics

            handler = _run_diagnostics
        else:
            handler = self.diagnostics_handler
        return await handler({"instance": args["instance"], "format": args.get("format", "health"), "persist": args.get("persist", True)}, state_root=os.fspath(self.state_root) if self.state_root is not None else None)

    async def _service_status(self, args: dict[str, Any], _progress: list[dict[str, Any]]) -> Any:
        return await self.service_factory(self._config(args)).status()

    async def _service_start(self, args: dict[str, Any], _progress: list[dict[str, Any]]) -> Any:
        changed = await self.service_factory(self._config(args)).start()
        return {"changed": bool(changed), "status": "started"}

    async def _service_stop(self, args: dict[str, Any], _progress: list[dict[str, Any]]) -> Any:
        changed = await self.service_factory(self._config(args)).stop()
        return {"changed": bool(changed), "status": "stopped"}

    async def _service_restart(self, args: dict[str, Any], _progress: list[dict[str, Any]]) -> Any:
        changed = await self.service_factory(self._config(args)).restart()
        return {"changed": bool(changed), "status": "restarted"}

    async def _with_blob_store(self, args: dict[str, Any], callback: Callable[[Any], Awaitable[Any]]) -> Any:
        client = self._client(self._config(args))
        try:
            return await callback(self.blob_store_factory(client))
        finally:
            await self._close(client)

    async def _blob_stat(self, args: dict[str, Any], _progress: list[dict[str, Any]]) -> Any:
        return await self._with_blob_store(args, lambda store: store.stat(args["blob_hash"]))

    @staticmethod
    def _transfer_progress(progress: list[dict[str, Any]]) -> Callable[[TransferProgress], None]:
        def report(event: TransferProgress) -> None:
            progress.append({
                "sequence": len(progress),
                "state": "running",
                "phase": event.operation,
                "completed": event.completed,
                "total": event.total,
                "resumed": event.resumed,
                "at": _now(),
            })

        return report

    async def _blob_fetch(self, args: dict[str, Any], progress: list[dict[str, Any]]) -> Any:
        callback = self._transfer_progress(progress)
        return await self._with_blob_store(args, lambda store: store.fetch(args["blob_hash"], provider=args["provider"], progress=callback))

    async def _ticket_import(self, args: dict[str, Any], progress: list[dict[str, Any]]) -> Any:
        callback = self._transfer_progress(progress)
        ticket = args.pop("ticket")
        try:
            return await self._with_blob_store(args, lambda store: store.import_ticket(ticket, expected_hash=args["expected_hash"], progress=callback))
        finally:
            ticket = ""

    def _audit(self, definition: OperationDefinition, operation_id: str, actor: str, started: str, outcome: str, error_code: str | None = None) -> dict[str, Any]:
        safe_actor = actor if isinstance(actor, str) and 0 < len(actor) <= 128 and all(31 < ord(c) < 127 for c in actor) else "anonymous"
        record = AuditRecord(str(uuid.uuid4()), operation_id, definition.name, definition.permission.value, outcome, started, _now(), safe_actor, error_code).as_dict()
        self.audit_sink.append(record)
        return record

    @staticmethod
    def _public_error(exc: BaseException) -> dict[str, Any]:
        if isinstance(exc, GovernedOperationError):
            return {"code": exc.code, "type": "IrohOperationError", "message": exc.public_message, "status": exc.status_code, "retryable": exc.retryable}
        if isinstance(exc, (IrohPermissionDeniedError, PermissionError)):
            return {"code": "permission_denied", "type": "IrohPermissionError", "message": "Iroh operation is not permitted", "status": 403, "retryable": False}
        if isinstance(exc, (IrohNotFoundError, FileNotFoundError)):
            return {"code": "not_found", "type": "IrohNotFoundError", "message": "Iroh resource was not found", "status": 404, "retryable": False}
        if isinstance(exc, IrohConflictError):
            return {"code": "conflict", "type": "IrohConflictError", "message": "Iroh operation conflicts with current state", "status": 409, "retryable": False}
        if isinstance(exc, (IrohUnavailableError, IrohTimeoutError, ConnectionError, TimeoutError)):
            return {"code": getattr(exc, "code", "unavailable"), "type": "IrohUnavailableError", "message": "Iroh service is unavailable", "status": 503, "retryable": True}
        if isinstance(exc, IrohIntegrityError):
            return {"code": "integrity_error", "type": "IrohIntegrityError", "message": "Iroh integrity verification failed", "status": 422, "retryable": False}
        if isinstance(exc, (IrohInvalidConfigError, ValueError, TypeError)):
            return {"code": getattr(exc, "code", "invalid_arguments"), "type": "IrohValidationError", "message": "Iroh operation arguments are invalid", "status": 400, "retryable": False}
        if isinstance(exc, IrohError):
            return {"code": exc.code, "type": type(exc).__name__, "message": "Iroh operation failed", "status": 500, "retryable": False}
        return {"code": "operation_failed", "type": "IrohOperationError", "message": "Iroh operation failed", "status": 500, "retryable": False}


__all__ = [
    "AuditRecord",
    "GovernedOperationError",
    "IrohOperationController",
    "IrohPermission",
    "JSONLinesAuditSink",
    "MAX_TICKET_BYTES",
    "MemoryAuditSink",
    "OPERATION_DEFINITIONS",
    "OperationDefinition",
    "normalize_permissions",
    "validate_ticket",
]
