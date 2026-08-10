"""Map flush, fsync, release, and deferred errors to durability receipts (KVFS-300).

This module owns *callback durability modes and receipts* for the kernel VFS
host path:

* ``fsync`` succeeds only after the configured WAL and backend file /
  parent-directory durability boundaries are observed;
* ``flush`` is repeatable and surfaces prior deferred write errors
  consistently without manufacturing durability;
* ``release`` is idempotent and never upgrades buffered work into a durable
  acknowledgement; and
* timeout / cancel / ``ENOSPC`` / ``EIO`` traces fail closed and never
  acknowledge lost data.

Buffered intent, queued work, flush, and release are **not** durable commit
evidence (plan §3.4 / KVFS-G300 refinement).  Native FUSE/WinFsp lifecycle is
out of scope (conflict policy: do not change native lifecycle).

Interfaces (plan aliases): ``DurabilityCoordinator@1``,
``DurabilityReceipt@1``, ``DeferredErrorState@1``.
"""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Final

from ipfs_kit_py.core.vfs.host_contracts import (
    DurabilityMode,
    HostCallbackKind,
    HostErrno,
)
from ipfs_kit_py.core.wal.contracts import (
    WALAcknowledgementMode,
    WALFsyncReceipt,
    ack_requirements_for,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-300"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

DURABILITY_NAMESPACE: Final[str] = "ipfs_kit_py/kernel_vfs/durability"

DURABILITY_COORDINATOR_SCHEMA: Final[str] = (
    f"{DURABILITY_NAMESPACE}/durability-coordinator@{SCHEMA_MAJOR}"
)
DURABILITY_RECEIPT_SCHEMA: Final[str] = (
    f"{DURABILITY_NAMESPACE}/durability-receipt@{SCHEMA_MAJOR}"
)
DEFERRED_ERROR_STATE_SCHEMA: Final[str] = (
    f"{DURABILITY_NAMESPACE}/deferred-error-state@{SCHEMA_MAJOR}"
)
DURABILITY_TRACE_SCHEMA: Final[str] = (
    f"{DURABILITY_NAMESPACE}/durability-trace@{SCHEMA_MAJOR}"
)
DURABILITY_REQUIREMENTS_SCHEMA: Final[str] = (
    f"{DURABILITY_NAMESPACE}/durability-requirements@{SCHEMA_MAJOR}"
)

# Public interface aliases.
DurabilityCoordinator_V1: Final[str] = DURABILITY_COORDINATOR_SCHEMA
DurabilityReceipt_V1: Final[str] = DURABILITY_RECEIPT_SCHEMA
DeferredErrorState_V1: Final[str] = DEFERRED_ERROR_STATE_SCHEMA

MAX_PATH_BYTES: Final[int] = 4_096
MAX_TEXT_BYTES: Final[int] = 4_096
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1
MAX_TRACE_EVENTS: Final[int] = 4_096
MAX_HANDLE_RECORDS: Final[int] = 16_384
DEFAULT_GENERATION_ID: Final[str] = "wal-gen:durability-1"
DEFAULT_MOUNT_ID: Final[str] = "mount:default"


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class DurabilityCallbackKind(str, Enum):
    """Closed host callbacks that participate in durability receipts."""

    FLUSH = "flush"
    FSYNC = "fsync"
    RELEASE = "release"


class DurabilityDisposition(str, Enum):
    """Terminal disposition of one durability callback attempt."""

    SUCCESS = "success"
    DEFERRED_ERROR = "deferred_error"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    IDEMPOTENT = "idempotent"
    ALREADY_RELEASED = "already_released"


class DurabilityErrorCode(str, Enum):
    """Stable error codes for the durability façade."""

    DEFERRED = "DURABILITY_DEFERRED"
    WAL_FSYNC = "DURABILITY_WAL_FSYNC"
    BACKEND_FSYNC = "DURABILITY_BACKEND_FSYNC"
    PARENT_FSYNC = "DURABILITY_PARENT_FSYNC"
    TIMEOUT = "DURABILITY_TIMEOUT"
    CANCELLED = "DURABILITY_CANCELLED"
    ENOSPC = "DURABILITY_ENOSPC"
    EIO = "DURABILITY_EIO"
    VALIDATION = "DURABILITY_VALIDATION"
    PROTOCOL = "DURABILITY_PROTOCOL"
    RELEASED = "DURABILITY_RELEASED"
    INTERNAL = "DURABILITY_INTERNAL"


class DurabilityTraceKind(str, Enum):
    """Closed trace kinds for durability callback evidence."""

    FLUSH = "flush"
    FSYNC = "fsync"
    RELEASE = "release"
    DEFERRED_SET = "deferred_set"
    DEFERRED_REPORT = "deferred_report"
    WAL_FILE_SYNC = "wal_file_sync"
    WAL_PARENT_SYNC = "wal_parent_sync"
    BACKEND_FILE_SYNC = "backend_file_sync"
    BACKEND_PARENT_SYNC = "backend_parent_sync"
    FAULT = "fault"
    RECEIPT = "receipt"


class DurabilityFaultKind(str, Enum):
    """Injected / observed fault kinds that must never acknowledge durability."""

    TIMEOUT = "timeout"
    CANCEL = "cancel"
    ENOSPC = "enospc"
    EIO = "eio"


# Map host DurabilityMode → WAL acknowledgement mode for requirement lookup.
_MODE_TO_WAL_ACK: Final[Mapping[DurabilityMode, WALAcknowledgementMode]] = {
    DurabilityMode.BUFFERED: WALAcknowledgementMode.BUFFERED,
    DurabilityMode.WAL_FILE_SYNC: WALAcknowledgementMode.WAL_FSYNC,
    DurabilityMode.WAL_PARENT_SYNC: WALAcknowledgementMode.WAL_FSYNC_PARENT,
    DurabilityMode.WAL_AND_BACKEND: WALAcknowledgementMode.BACKEND_EFFECT,
    DurabilityMode.COMMITTED_VISIBLE: WALAcknowledgementMode.BACKEND_DURABLE,
}

# fsync may never claim only buffered durability (host contract + plan §3.4).
_FSYNC_MIN_MODE: Final[DurabilityMode] = DurabilityMode.WAL_AND_BACKEND

# Fault kinds → HostErrno.
_FAULT_TO_ERRNO: Final[Mapping[DurabilityFaultKind, HostErrno]] = {
    DurabilityFaultKind.TIMEOUT: HostErrno.ETIMEDOUT,
    DurabilityFaultKind.CANCEL: HostErrno.ECANCELED,
    DurabilityFaultKind.ENOSPC: HostErrno.ENOSPC,
    DurabilityFaultKind.EIO: HostErrno.EIO,
}

_FAULT_TO_ERROR_CODE: Final[Mapping[DurabilityFaultKind, DurabilityErrorCode]] = {
    DurabilityFaultKind.TIMEOUT: DurabilityErrorCode.TIMEOUT,
    DurabilityFaultKind.CANCEL: DurabilityErrorCode.CANCELLED,
    DurabilityFaultKind.ENOSPC: DurabilityErrorCode.ENOSPC,
    DurabilityFaultKind.EIO: DurabilityErrorCode.EIO,
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DurabilityError(Exception):
    """Base class for durability façade failures."""

    def __init__(
        self,
        message: str,
        *,
        code: DurabilityErrorCode = DurabilityErrorCode.INTERNAL,
        errno: HostErrno = HostErrno.EIO,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.errno = errno
        self.detail = dict(detail or {})


class DurabilityValidationError(DurabilityError):
    def __init__(
        self,
        message: str = "durability validation failed",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message,
            code=kwargs.pop("code", DurabilityErrorCode.VALIDATION),
            errno=kwargs.pop("errno", HostErrno.EINVAL),
            **kwargs,
        )


class DurabilityProtocolError(DurabilityError):
    def __init__(
        self,
        message: str = "durability protocol violated",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message,
            code=kwargs.pop("code", DurabilityErrorCode.PROTOCOL),
            errno=kwargs.pop("errno", HostErrno.EIO),
            **kwargs,
        )


class DurabilityFaultError(DurabilityError):
    """Raised when a named durability boundary faults (timeout/cancel/ENOSPC/EIO)."""

    def __init__(
        self,
        message: str,
        *,
        fault: DurabilityFaultKind,
        **kwargs: Any,
    ) -> None:
        errno = kwargs.pop("errno", _FAULT_TO_ERRNO[fault])
        code = kwargs.pop("code", _FAULT_TO_ERROR_CODE[fault])
        super().__init__(message, code=code, errno=errno, **kwargs)
        self.fault = fault


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise DurabilityValidationError(f"{field_name} must be a boolean")
    return value


def _bounded_int(
    value: Any,
    field_name: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_SAFE_INTEGER,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DurabilityValidationError(f"{field_name} must be a finite integer")
    if value < minimum or value > maximum:
        raise DurabilityValidationError(f"{field_name} is outside supported bounds")
    return value


def _text(value: Any, field_name: str, *, limit: int = MAX_TEXT_BYTES) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise DurabilityValidationError(f"{field_name} must be a string")
    if len(value.encode("utf-8")) > limit:
        raise DurabilityValidationError(f"{field_name} exceeds bound")
    return value


def path_to_ref(path: str) -> str:
    """Project a VFS path into a compact opaque path_ref identifier."""

    if not path:
        return ""
    compact = path.replace("/", ".").replace("\\", ".")
    # Keep identifier-safe characters only.
    safe = "".join(ch if ch.isalnum() or ch in "._:+@-" else "_" for ch in compact)
    return f"path:{safe}" if safe else ""


def host_callback_for(kind: DurabilityCallbackKind | str) -> HostCallbackKind:
    """Map a durability callback kind onto the host contract vocabulary."""

    if not isinstance(kind, DurabilityCallbackKind):
        kind = DurabilityCallbackKind(kind)
    return HostCallbackKind(kind.value)


def effective_fsync_mode(mode: DurabilityMode | str) -> DurabilityMode:
    """Return the mode fsync may claim (never mere ``buffered``)."""

    if not isinstance(mode, DurabilityMode):
        mode = DurabilityMode(mode)
    if mode is DurabilityMode.BUFFERED:
        return _FSYNC_MIN_MODE
    return mode


def wal_ack_mode_for(mode: DurabilityMode | str) -> WALAcknowledgementMode:
    """Map host durability mode onto a WAL acknowledgement mode."""

    if not isinstance(mode, DurabilityMode):
        mode = DurabilityMode(mode)
    return _MODE_TO_WAL_ACK[mode]


# ---------------------------------------------------------------------------
# Requirements derived from configured mode
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DurabilityRequirements:
    """Declared evidence a successful fsync must wait for under ``mode``.

    Flush and release never require these; they cannot manufacture durability.
    """

    SCHEMA: ClassVar[str] = DURABILITY_REQUIREMENTS_SCHEMA

    mode: DurabilityMode
    requires_wal_file_fsync: bool
    requires_wal_parent_directory_fsync: bool
    requires_backend_file_fsync: bool
    requires_backend_parent_directory_fsync: bool
    requires_backend_effect: bool
    may_claim_durable: bool
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.mode, DurabilityMode):
            object.__setattr__(self, "mode", DurabilityMode(self.mode))
        object.__setattr__(
            self,
            "requires_wal_file_fsync",
            _bool(self.requires_wal_file_fsync, "requires_wal_file_fsync"),
        )
        object.__setattr__(
            self,
            "requires_wal_parent_directory_fsync",
            _bool(
                self.requires_wal_parent_directory_fsync,
                "requires_wal_parent_directory_fsync",
            ),
        )
        object.__setattr__(
            self,
            "requires_backend_file_fsync",
            _bool(self.requires_backend_file_fsync, "requires_backend_file_fsync"),
        )
        object.__setattr__(
            self,
            "requires_backend_parent_directory_fsync",
            _bool(
                self.requires_backend_parent_directory_fsync,
                "requires_backend_parent_directory_fsync",
            ),
        )
        object.__setattr__(
            self,
            "requires_backend_effect",
            _bool(self.requires_backend_effect, "requires_backend_effect"),
        )
        object.__setattr__(
            self, "may_claim_durable", _bool(self.may_claim_durable, "may_claim_durable")
        )
        object.__setattr__(
            self, "description", _text(self.description, "description")
        )
        if self.mode is DurabilityMode.BUFFERED and self.may_claim_durable:
            raise DurabilityProtocolError(
                "buffered mode must not claim durable acknowledgement"
            )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "mode": self.mode.value,
            "requires_wal_file_fsync": self.requires_wal_file_fsync,
            "requires_wal_parent_directory_fsync": self.requires_wal_parent_directory_fsync,
            "requires_backend_file_fsync": self.requires_backend_file_fsync,
            "requires_backend_parent_directory_fsync": (
                self.requires_backend_parent_directory_fsync
            ),
            "requires_backend_effect": self.requires_backend_effect,
            "may_claim_durable": self.may_claim_durable,
            "description": self.description,
        }


def requirements_for(mode: DurabilityMode | str) -> DurabilityRequirements:
    """Return the declared WAL/backend wait set for ``mode``."""

    if not isinstance(mode, DurabilityMode):
        mode = DurabilityMode(mode)
    ack = ack_requirements_for(wal_ack_mode_for(mode))
    # Backend file/parent durability is required whenever the mode binds a
    # backend effect (WAL_AND_BACKEND / COMMITTED_VISIBLE).  Parent-directory
    # backend fsync tracks the WAL parent requirement for full modes.
    requires_backend_effect = ack.requires_backend_effect
    requires_backend_file = requires_backend_effect
    requires_backend_parent = (
        requires_backend_effect and ack.requires_parent_directory_fsync
    )
    return DurabilityRequirements(
        mode=mode,
        requires_wal_file_fsync=ack.requires_file_fsync,
        requires_wal_parent_directory_fsync=ack.requires_parent_directory_fsync,
        requires_backend_file_fsync=requires_backend_file,
        requires_backend_parent_directory_fsync=requires_backend_parent,
        requires_backend_effect=requires_backend_effect,
        may_claim_durable=ack.may_claim_committed and mode is not DurabilityMode.BUFFERED,
        description=ack.description,
    )


def all_mode_requirements() -> tuple[DurabilityRequirements, ...]:
    """Return requirements for every host durability mode (stable order)."""

    return tuple(requirements_for(mode) for mode in DurabilityMode)


# ---------------------------------------------------------------------------
# Deferred error state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeferredErrorState:
    """Sticky deferred write error bound to one open handle.

    Flush reports this consistently until cleared (release) or overwritten.
    """

    SCHEMA: ClassVar[str] = DEFERRED_ERROR_STATE_SCHEMA

    handle_id: int
    generation: int
    errno: HostErrno
    error_code: DurabilityErrorCode = DurabilityErrorCode.DEFERRED
    message: str = ""
    set_count: int = 1
    report_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "handle_id", _bounded_int(self.handle_id, "handle_id", minimum=0)
        )
        object.__setattr__(
            self,
            "generation",
            _bounded_int(self.generation, "generation", minimum=0),
        )
        if not isinstance(self.errno, HostErrno):
            object.__setattr__(self, "errno", HostErrno(self.errno))
        if not isinstance(self.error_code, DurabilityErrorCode):
            object.__setattr__(
                self, "error_code", DurabilityErrorCode(self.error_code)
            )
        object.__setattr__(self, "message", _text(self.message, "message"))
        object.__setattr__(
            self, "set_count", _bounded_int(self.set_count, "set_count", minimum=1)
        )
        object.__setattr__(
            self,
            "report_count",
            _bounded_int(self.report_count, "report_count", minimum=0),
        )

    def reported(self) -> "DeferredErrorState":
        return DeferredErrorState(
            handle_id=self.handle_id,
            generation=self.generation,
            errno=self.errno,
            error_code=self.error_code,
            message=self.message,
            set_count=self.set_count,
            report_count=self.report_count + 1,
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "handle_id": self.handle_id,
            "generation": self.generation,
            "errno": self.errno.value,
            "error_code": self.error_code.value,
            "message": self.message,
            "set_count": self.set_count,
            "report_count": self.report_count,
        }


# ---------------------------------------------------------------------------
# Durability receipt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DurabilityReceipt:
    """Exact receipt for one flush / fsync / release callback.

    Success with ``durable=True`` is only legal for ``fsync`` after all
    configured WAL and backend boundaries are observed.  Flush and release
    success always report ``durable=False``.
    """

    SCHEMA: ClassVar[str] = DURABILITY_RECEIPT_SCHEMA

    receipt_id: str
    callback: DurabilityCallbackKind
    disposition: DurabilityDisposition
    success: bool
    durable: bool
    durability_mode: DurabilityMode
    handle_id: int = 0
    generation: int = 0
    path: str = ""
    path_ref: str = ""
    errno: HostErrno = HostErrno.OK
    error_code: str = ""
    message: str = ""
    deferred_error: bool = False
    idempotent: bool = False
    already_released: bool = False
    observed_effect: bool = False
    acknowledged_data: bool = False
    """True only when this receipt acknowledges data as durable/committed."""

    wal_file_fsync: bool = False
    wal_parent_directory_fsync: bool = False
    backend_file_fsync: bool = False
    backend_parent_directory_fsync: bool = False
    backend_effect_id: str = ""
    fsync_receipt_id: str = ""
    wal_fsync_receipt: WALFsyncReceipt | None = None
    sequence_number: int = 0
    generation_id: str = DEFAULT_GENERATION_ID
    flush_count: int = 0
    release_count: int = 0
    requirements: DurabilityRequirements | None = None
    deferred: DeferredErrorState | None = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.callback, DurabilityCallbackKind):
            object.__setattr__(
                self, "callback", DurabilityCallbackKind(self.callback)
            )
        if not isinstance(self.disposition, DurabilityDisposition):
            object.__setattr__(
                self, "disposition", DurabilityDisposition(self.disposition)
            )
        if not isinstance(self.durability_mode, DurabilityMode):
            object.__setattr__(
                self, "durability_mode", DurabilityMode(self.durability_mode)
            )
        if not isinstance(self.errno, HostErrno):
            object.__setattr__(self, "errno", HostErrno(self.errno))
        object.__setattr__(self, "success", _bool(self.success, "success"))
        object.__setattr__(self, "durable", _bool(self.durable, "durable"))
        object.__setattr__(
            self,
            "acknowledged_data",
            _bool(self.acknowledged_data, "acknowledged_data"),
        )
        object.__setattr__(
            self, "deferred_error", _bool(self.deferred_error, "deferred_error")
        )
        object.__setattr__(self, "idempotent", _bool(self.idempotent, "idempotent"))
        object.__setattr__(
            self,
            "already_released",
            _bool(self.already_released, "already_released"),
        )
        object.__setattr__(
            self, "observed_effect", _bool(self.observed_effect, "observed_effect")
        )
        object.__setattr__(
            self, "receipt_id", _text(self.receipt_id, "receipt_id") or "receipt:unknown"
        )
        object.__setattr__(self, "path", _text(self.path, "path", limit=MAX_PATH_BYTES))
        if not self.path_ref and self.path:
            object.__setattr__(self, "path_ref", path_to_ref(self.path))
        object.__setattr__(self, "detail", dict(self.detail or {}))
        self._assert_policy()

    def _assert_policy(self) -> None:
        # Success policy: no false durability, no false success.
        if self.success:
            if self.errno is not HostErrno.OK:
                raise DurabilityProtocolError(
                    f"success with non-OK errno {self.errno.value} is forbidden"
                )
            if self.deferred_error:
                raise DurabilityProtocolError(
                    "success receipt cannot carry deferred_error"
                )
            if self.callback is DurabilityCallbackKind.FSYNC:
                if self.durability_mode is DurabilityMode.BUFFERED:
                    raise DurabilityProtocolError(
                        "fsync success cannot claim only buffered durability"
                    )
                if self.durable and not self.acknowledged_data:
                    raise DurabilityProtocolError(
                        "durable fsync success must acknowledge data"
                    )
                if self.durable and not self.fsync_receipt_id and not self.wal_file_fsync:
                    raise DurabilityProtocolError(
                        "durable fsync success requires fsync evidence"
                    )
            else:
                # flush / release never manufacture durability.
                if self.durable:
                    raise DurabilityProtocolError(
                        f"{self.callback.value} success cannot claim durable=True"
                    )
                if self.acknowledged_data:
                    raise DurabilityProtocolError(
                        f"{self.callback.value} success cannot acknowledge data"
                    )
        else:
            if self.errno is HostErrno.OK:
                raise DurabilityProtocolError("failure requires a non-OK errno")
            if self.durable:
                raise DurabilityProtocolError(
                    "failed receipt cannot claim durable=True"
                )
            if self.acknowledged_data:
                raise DurabilityProtocolError(
                    "failed receipt cannot acknowledge data as durable"
                )

    @property
    def host_callback(self) -> HostCallbackKind:
        return host_callback_for(self.callback)

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "receipt_id": self.receipt_id,
            "callback": self.callback.value,
            "disposition": self.disposition.value,
            "success": self.success,
            "durable": self.durable,
            "durability_mode": self.durability_mode.value,
            "handle_id": self.handle_id,
            "generation": self.generation,
            "path": self.path,
            "path_ref": self.path_ref,
            "errno": self.errno.value,
            "error_code": self.error_code,
            "message": self.message,
            "deferred_error": self.deferred_error,
            "idempotent": self.idempotent,
            "already_released": self.already_released,
            "observed_effect": self.observed_effect,
            "acknowledged_data": self.acknowledged_data,
            "wal_file_fsync": self.wal_file_fsync,
            "wal_parent_directory_fsync": self.wal_parent_directory_fsync,
            "backend_file_fsync": self.backend_file_fsync,
            "backend_parent_directory_fsync": self.backend_parent_directory_fsync,
            "backend_effect_id": self.backend_effect_id,
            "fsync_receipt_id": self.fsync_receipt_id,
            "sequence_number": self.sequence_number,
            "generation_id": self.generation_id,
            "flush_count": self.flush_count,
            "release_count": self.release_count,
            "detail": dict(self.detail),
        }
        if self.wal_fsync_receipt is not None:
            record["wal_fsync_receipt"] = self.wal_fsync_receipt.to_dict()
        if self.requirements is not None:
            record["requirements"] = self.requirements.to_record()
        if self.deferred is not None:
            record["deferred"] = self.deferred.to_record()
        return record


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DurabilityTraceEvent:
    SCHEMA: ClassVar[str] = DURABILITY_TRACE_SCHEMA

    kind: DurabilityTraceKind
    success: bool
    callback: str = ""
    code: str = ""
    handle_id: int = 0
    generation: int = 0
    path: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    unix_ms: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind.value if isinstance(self.kind, DurabilityTraceKind) else self.kind,
            "success": self.success,
            "callback": self.callback,
            "code": self.code,
            "handle_id": self.handle_id,
            "generation": self.generation,
            "path": self.path,
            "detail": dict(self.detail),
            "unix_ms": self.unix_ms,
        }


class DurabilityTrace:
    """Bounded ring of durability callback evidence events."""

    def __init__(self, *, capacity: int = MAX_TRACE_EVENTS) -> None:
        self._capacity = max(1, int(capacity))
        self._events: list[DurabilityTraceEvent] = []
        self._lock = threading.RLock()

    def record(
        self,
        kind: DurabilityTraceKind | str,
        *,
        success: bool,
        callback: str = "",
        code: str = "",
        handle_id: int = 0,
        generation: int = 0,
        path: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> DurabilityTraceEvent:
        if not isinstance(kind, DurabilityTraceKind):
            kind = DurabilityTraceKind(kind)
        event = DurabilityTraceEvent(
            kind=kind,
            success=success,
            callback=callback,
            code=code,
            handle_id=handle_id,
            generation=generation,
            path=path,
            detail=dict(detail or {}),
            unix_ms=int(time.time() * 1000),
        )
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._capacity:
                self._events = self._events[-self._capacity :]
        return event

    def events(self) -> tuple[DurabilityTraceEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def kinds(self) -> list[str]:
        return [e.kind.value for e in self.events()]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


# ---------------------------------------------------------------------------
# Durability media operations (injectable)
# ---------------------------------------------------------------------------


@dataclass
class DurabilityBoundaryObservation:
    """Observation of one durability media boundary."""

    boundary: str
    observed: bool
    receipt_id: str = ""
    sequence_number: int = 0
    detail: dict[str, Any] = field(default_factory=dict)


FaultInjector = Callable[[str, str], Any]
# (boundary_name, handle_key) → may raise DurabilityFaultError / OSError


class DurabilityMedia:
    """Injectable WAL + backend durability operations.

    Production wiring may bind these to real ``os.fsync`` / directory fsync
    and WAL writer receipts.  Hermetic tests use the in-memory default.
    """

    def __init__(
        self,
        *,
        generation_id: str = DEFAULT_GENERATION_ID,
        fault_injector: FaultInjector | None = None,
        directory: str | Path | None = None,
    ) -> None:
        self.generation_id = generation_id
        self._fault_injector = fault_injector
        self.directory = Path(directory) if directory is not None else None
        if self.directory is not None:
            self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._sequence = 0
        self._wal_file_synced = False
        self._wal_parent_synced = False
        self._backend_file_synced: set[str] = set()
        self._backend_parent_synced: set[str] = set()
        self._backend_effects: dict[str, str] = {}
        self._observations: list[DurabilityBoundaryObservation] = []

    @property
    def sequence(self) -> int:
        return self._sequence

    @property
    def observations(self) -> tuple[DurabilityBoundaryObservation, ...]:
        with self._lock:
            return tuple(self._observations)

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _boundary(self, name: str, handle_key: str = "") -> None:
        if self._fault_injector is None:
            return
        try:
            self._fault_injector(name, handle_key)
        except TypeError:
            self._fault_injector(name)  # type: ignore[call-arg]
        except DurabilityFaultError:
            raise
        except OSError as exc:
            # Map common OS errors onto closed fault kinds.
            errno_val = getattr(exc, "errno", None)
            if errno_val == 28:  # ENOSPC
                raise DurabilityFaultError(
                    f"{name} hit ENOSPC",
                    fault=DurabilityFaultKind.ENOSPC,
                    detail={"boundary": name, "os_errno": errno_val},
                ) from exc
            raise DurabilityFaultError(
                f"{name} hit EIO: {exc}",
                fault=DurabilityFaultKind.EIO,
                detail={"boundary": name, "os_errno": errno_val},
            ) from exc

    def _observe(
        self,
        boundary: str,
        *,
        observed: bool,
        receipt_id: str = "",
        sequence_number: int = 0,
        detail: Mapping[str, Any] | None = None,
    ) -> DurabilityBoundaryObservation:
        obs = DurabilityBoundaryObservation(
            boundary=boundary,
            observed=observed,
            receipt_id=receipt_id,
            sequence_number=sequence_number,
            detail=dict(detail or {}),
        )
        with self._lock:
            self._observations.append(obs)
        return obs

    def wal_file_fsync(self, *, handle_key: str = "") -> DurabilityBoundaryObservation:
        self._boundary("before_wal_file_fsync", handle_key)
        with self._lock:
            seq = self._next_sequence()
            receipt_id = f"wal-file-fsync:{seq}"
            self._wal_file_synced = True
        self._boundary("after_wal_file_fsync", handle_key)
        return self._observe(
            "wal_file_fsync",
            observed=True,
            receipt_id=receipt_id,
            sequence_number=seq,
        )

    def wal_parent_directory_fsync(
        self, *, handle_key: str = ""
    ) -> DurabilityBoundaryObservation:
        self._boundary("before_wal_parent_fsync", handle_key)
        with self._lock:
            seq = self._next_sequence()
            receipt_id = f"wal-parent-fsync:{seq}"
            self._wal_parent_synced = True
        self._boundary("after_wal_parent_fsync", handle_key)
        return self._observe(
            "wal_parent_directory_fsync",
            observed=True,
            receipt_id=receipt_id,
            sequence_number=seq,
        )

    def backend_file_fsync(
        self, path: str, *, handle_key: str = "", effect_id: str = ""
    ) -> DurabilityBoundaryObservation:
        self._boundary("before_backend_file_fsync", handle_key)
        with self._lock:
            seq = self._next_sequence()
            receipt_id = f"backend-file-fsync:{seq}"
            self._backend_file_synced.add(path or handle_key or "*")
            if effect_id:
                self._backend_effects[path or handle_key or "*"] = effect_id
        self._boundary("after_backend_file_fsync", handle_key)
        return self._observe(
            "backend_file_fsync",
            observed=True,
            receipt_id=receipt_id,
            sequence_number=seq,
            detail={"path": path, "effect_id": effect_id},
        )

    def backend_parent_directory_fsync(
        self, path: str, *, handle_key: str = ""
    ) -> DurabilityBoundaryObservation:
        self._boundary("before_backend_parent_fsync", handle_key)
        with self._lock:
            seq = self._next_sequence()
            receipt_id = f"backend-parent-fsync:{seq}"
            self._backend_parent_synced.add(path or handle_key or "*")
        self._boundary("after_backend_parent_fsync", handle_key)
        return self._observe(
            "backend_parent_directory_fsync",
            observed=True,
            receipt_id=receipt_id,
            sequence_number=seq,
            detail={"path": path},
        )

    def note_backend_effect(self, path: str, effect_id: str) -> None:
        with self._lock:
            self._backend_effects[path] = effect_id

    def backend_effect_id_for(self, path: str) -> str:
        with self._lock:
            return self._backend_effects.get(path, "")

    def reset(self) -> None:
        with self._lock:
            self._wal_file_synced = False
            self._wal_parent_synced = False
            self._backend_file_synced.clear()
            self._backend_parent_synced.clear()
            self._backend_effects.clear()
            self._observations.clear()


# ---------------------------------------------------------------------------
# Per-handle durability state
# ---------------------------------------------------------------------------


@dataclass
class _HandleDurabilityState:
    handle_id: int
    generation: int
    path: str = ""
    effect_id: str = ""
    dirty: bool = False
    released: bool = False
    flush_count: int = 0
    fsync_count: int = 0
    release_count: int = 0
    deferred: DeferredErrorState | None = None
    last_flush_receipt: DurabilityReceipt | None = None
    last_fsync_receipt: DurabilityReceipt | None = None
    last_release_receipt: DurabilityReceipt | None = None
    last_successful_fsync_receipt_id: str = ""


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class DurabilityCoordinator:
    """Map flush / fsync / release callbacks onto durability receipts.

    Production entry point for callback durability modes (KVFS-300).
    """

    SCHEMA: ClassVar[str] = DURABILITY_COORDINATOR_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    # Named crash / fault boundaries for fsync wait ladder.
    FSYNC_BOUNDARIES: Final[tuple[str, ...]] = (
        "before_fsync",
        "before_wal_file_fsync",
        "after_wal_file_fsync",
        "before_wal_parent_fsync",
        "after_wal_parent_fsync",
        "before_backend_file_fsync",
        "after_backend_file_fsync",
        "before_backend_parent_fsync",
        "after_backend_parent_fsync",
        "after_fsync",
    )

    def __init__(
        self,
        *,
        durability_mode: DurabilityMode | str = DurabilityMode.COMMITTED_VISIBLE,
        media: DurabilityMedia | None = None,
        generation_id: str = DEFAULT_GENERATION_ID,
        mount_id: str = DEFAULT_MOUNT_ID,
        fault_injector: FaultInjector | None = None,
        directory: str | Path | None = None,
    ) -> None:
        if not isinstance(durability_mode, DurabilityMode):
            durability_mode = DurabilityMode(durability_mode)
        self._durability_mode = durability_mode
        self._generation_id = generation_id
        self._mount_id = mount_id
        self._media = media or DurabilityMedia(
            generation_id=generation_id,
            fault_injector=fault_injector,
            directory=directory,
        )
        if fault_injector is not None and media is None:
            # already wired via DurabilityMedia above
            pass
        elif fault_injector is not None and media is not None:
            # Prefer explicit media; allow injector override on media.
            self._media._fault_injector = fault_injector  # type: ignore[attr-defined]
        self._trace = DurabilityTrace()
        self._lock = threading.RLock()
        self._handles: dict[tuple[int, int], _HandleDurabilityState] = {}
        self._released: dict[tuple[int, int], _HandleDurabilityState] = {}
        self._sequence = 0
        self._last_receipt: DurabilityReceipt | None = None
        self._receipts: list[DurabilityReceipt] = []

    # -- properties ---------------------------------------------------------

    @property
    def durability_mode(self) -> DurabilityMode:
        return self._durability_mode

    @property
    def media(self) -> DurabilityMedia:
        return self._media

    @property
    def trace(self) -> DurabilityTrace:
        return self._trace

    @property
    def last_receipt(self) -> DurabilityReceipt | None:
        return self._last_receipt

    @property
    def receipts(self) -> tuple[DurabilityReceipt, ...]:
        with self._lock:
            return tuple(self._receipts)

    @property
    def generation_id(self) -> str:
        return self._generation_id

    # -- handle registration ------------------------------------------------

    def register_handle(
        self,
        handle_id: int,
        *,
        generation: int = 1,
        path: str = "",
        effect_id: str = "",
        dirty: bool = False,
    ) -> None:
        """Register (or re-bind) a live handle for durability tracking."""

        key = (int(handle_id), int(generation))
        with self._lock:
            if key in self._released:
                # Re-registration after release requires a new generation.
                raise DurabilityValidationError(
                    "cannot re-register a released handle generation",
                    detail={"handle_id": handle_id, "generation": generation},
                )
            existing = self._handles.get(key)
            if existing is not None:
                existing.path = path or existing.path
                existing.effect_id = effect_id or existing.effect_id
                existing.dirty = existing.dirty or dirty
                return
            if len(self._handles) >= MAX_HANDLE_RECORDS:
                raise DurabilityValidationError("handle durability table is full")
            self._handles[key] = _HandleDurabilityState(
                handle_id=int(handle_id),
                generation=int(generation),
                path=path,
                effect_id=effect_id,
                dirty=bool(dirty),
            )

    def mark_dirty(
        self,
        handle_id: int,
        *,
        generation: int = 1,
        effect_id: str = "",
    ) -> None:
        state = self._require_live(handle_id, generation)
        state.dirty = True
        if effect_id:
            state.effect_id = effect_id

    def set_deferred_error(
        self,
        handle_id: int,
        *,
        generation: int = 1,
        errno: HostErrno | str = HostErrno.EIO,
        error_code: DurabilityErrorCode | str = DurabilityErrorCode.DEFERRED,
        message: str = "deferred write error",
    ) -> DeferredErrorState:
        """Install a sticky deferred error reported by subsequent flush/fsync."""

        if not isinstance(errno, HostErrno):
            errno = HostErrno(errno)
        if not isinstance(error_code, DurabilityErrorCode):
            error_code = DurabilityErrorCode(error_code)
        if errno is HostErrno.OK:
            raise DurabilityValidationError("deferred error requires a non-OK errno")
        with self._lock:
            state = self._require_live_locked(handle_id, generation)
            prior = state.deferred
            deferred = DeferredErrorState(
                handle_id=handle_id,
                generation=generation,
                errno=errno,
                error_code=error_code,
                message=message,
                set_count=(prior.set_count + 1) if prior else 1,
                report_count=0,
            )
            state.deferred = deferred
            self._trace.record(
                DurabilityTraceKind.DEFERRED_SET,
                success=False,
                callback="deferred",
                code=error_code.value,
                handle_id=handle_id,
                generation=generation,
                path=state.path,
                detail=deferred.to_record(),
            )
            return deferred

    def get_deferred_error(
        self, handle_id: int, *, generation: int = 1
    ) -> DeferredErrorState | None:
        with self._lock:
            state = self._handles.get((int(handle_id), int(generation)))
            if state is None:
                return None
            return state.deferred

    # -- flush --------------------------------------------------------------

    def flush(
        self,
        handle_id: int,
        *,
        generation: int = 1,
        path: str = "",
    ) -> DurabilityReceipt:
        """Repeatable flush. Reports deferred errors consistently.

        Flush never claims durable acknowledgement (plan refinement).
        """

        with self._lock:
            state = self._require_live_locked(handle_id, generation)
            if path:
                state.path = path
            state.flush_count += 1
            idempotent = state.flush_count > 1

            if state.deferred is not None:
                deferred = state.deferred.reported()
                state.deferred = deferred
                receipt = self._failure_receipt(
                    callback=DurabilityCallbackKind.FLUSH,
                    disposition=DurabilityDisposition.DEFERRED_ERROR,
                    state=state,
                    errno=deferred.errno,
                    error_code=deferred.error_code.value,
                    message=deferred.message or "deferred write error",
                    deferred_error=True,
                    idempotent=idempotent,
                    deferred=deferred,
                    detail={
                        "flush_count": state.flush_count,
                        "report_count": deferred.report_count,
                    },
                )
                state.last_flush_receipt = receipt
                self._trace.record(
                    DurabilityTraceKind.DEFERRED_REPORT,
                    success=False,
                    callback="flush",
                    code=receipt.error_code,
                    handle_id=handle_id,
                    generation=generation,
                    path=state.path,
                    detail=receipt.to_record(),
                )
                self._trace.record(
                    DurabilityTraceKind.FLUSH,
                    success=False,
                    callback="flush",
                    code=receipt.error_code,
                    handle_id=handle_id,
                    generation=generation,
                    path=state.path,
                    detail={"idempotent": idempotent, "deferred_error": True},
                )
                return self._remember(receipt)

            # Successful flush: no durability claim.
            receipt = DurabilityReceipt(
                receipt_id=self._new_receipt_id("flush"),
                callback=DurabilityCallbackKind.FLUSH,
                disposition=(
                    DurabilityDisposition.IDEMPOTENT
                    if idempotent
                    else DurabilityDisposition.SUCCESS
                ),
                success=True,
                durable=False,
                durability_mode=self._durability_mode,
                handle_id=handle_id,
                generation=generation,
                path=state.path,
                path_ref=path_to_ref(state.path),
                errno=HostErrno.OK,
                deferred_error=False,
                idempotent=idempotent,
                observed_effect=False,
                acknowledged_data=False,
                flush_count=state.flush_count,
                generation_id=self._generation_id,
                detail={"flush_count": state.flush_count, "dirty": state.dirty},
            )
            state.last_flush_receipt = receipt
            self._trace.record(
                DurabilityTraceKind.FLUSH,
                success=True,
                callback="flush",
                handle_id=handle_id,
                generation=generation,
                path=state.path,
                detail={"idempotent": idempotent, "durable": False},
            )
            return self._remember(receipt)

    # -- fsync --------------------------------------------------------------

    def fsync(
        self,
        handle_id: int,
        *,
        generation: int = 1,
        path: str = "",
        datasync: bool = False,
        durability_mode: DurabilityMode | str | None = None,
        effect_id: str = "",
    ) -> DurabilityReceipt:
        """Wait for configured WAL and backend file/parent-directory durability.

        Success never claims only buffered durability.  Any timeout / cancel /
        ENOSPC / EIO fault fails closed without acknowledging data.
        """

        mode = (
            effective_fsync_mode(durability_mode)
            if durability_mode is not None
            else effective_fsync_mode(self._durability_mode)
        )
        reqs = requirements_for(mode)
        handle_key = f"{handle_id}:{generation}"

        with self._lock:
            state = self._require_live_locked(handle_id, generation)
            if path:
                state.path = path
            if effect_id:
                state.effect_id = effect_id
            state.fsync_count += 1
            path_value = state.path
            effect = state.effect_id or f"effect:fsync:{handle_id}:{generation}"

            # Deferred errors block fsync and never commit.
            if state.deferred is not None:
                deferred = state.deferred.reported()
                state.deferred = deferred
                receipt = self._failure_receipt(
                    callback=DurabilityCallbackKind.FSYNC,
                    disposition=DurabilityDisposition.DEFERRED_ERROR,
                    state=state,
                    errno=deferred.errno,
                    error_code=deferred.error_code.value,
                    message=deferred.message or "deferred write error blocks fsync",
                    deferred_error=True,
                    deferred=deferred,
                    durability_mode=mode,
                    requirements=reqs,
                    detail={"datasync": datasync, "fsync_count": state.fsync_count},
                )
                state.last_fsync_receipt = receipt
                self._trace.record(
                    DurabilityTraceKind.FSYNC,
                    success=False,
                    callback="fsync",
                    code=receipt.error_code,
                    handle_id=handle_id,
                    generation=generation,
                    path=path_value,
                    detail={"deferred_error": True, "acknowledged_data": False},
                )
                return self._remember(receipt)

        # Perform durability waits outside the handle lock so media ops can
        # block / inject faults without serialising the whole table.  Re-check
        # state under lock when composing the final receipt.
        try:
            self._media._boundary("before_fsync", handle_key)  # type: ignore[attr-defined]

            wal_file = False
            wal_parent = False
            backend_file = False
            backend_parent = False
            backend_effect_id = ""
            fsync_receipt_id = ""
            sequence_number = 0
            wal_receipt: WALFsyncReceipt | None = None

            if reqs.requires_wal_file_fsync:
                obs = self._media.wal_file_fsync(handle_key=handle_key)
                wal_file = obs.observed
                fsync_receipt_id = obs.receipt_id
                sequence_number = obs.sequence_number
                self._trace.record(
                    DurabilityTraceKind.WAL_FILE_SYNC,
                    success=True,
                    callback="fsync",
                    handle_id=handle_id,
                    generation=generation,
                    path=path_value,
                    detail=obs.detail | {"receipt_id": obs.receipt_id},
                )

            if reqs.requires_wal_parent_directory_fsync:
                obs = self._media.wal_parent_directory_fsync(handle_key=handle_key)
                wal_parent = obs.observed
                if not fsync_receipt_id:
                    fsync_receipt_id = obs.receipt_id
                sequence_number = max(sequence_number, obs.sequence_number)
                self._trace.record(
                    DurabilityTraceKind.WAL_PARENT_SYNC,
                    success=True,
                    callback="fsync",
                    handle_id=handle_id,
                    generation=generation,
                    path=path_value,
                    detail=obs.detail | {"receipt_id": obs.receipt_id},
                )

            if reqs.requires_backend_file_fsync:
                obs = self._media.backend_file_fsync(
                    path_value, handle_key=handle_key, effect_id=effect
                )
                backend_file = obs.observed
                backend_effect_id = effect
                sequence_number = max(sequence_number, obs.sequence_number)
                self._trace.record(
                    DurabilityTraceKind.BACKEND_FILE_SYNC,
                    success=True,
                    callback="fsync",
                    handle_id=handle_id,
                    generation=generation,
                    path=path_value,
                    detail=obs.detail | {"receipt_id": obs.receipt_id},
                )

            if reqs.requires_backend_parent_directory_fsync:
                obs = self._media.backend_parent_directory_fsync(
                    path_value, handle_key=handle_key
                )
                backend_parent = obs.observed
                sequence_number = max(sequence_number, obs.sequence_number)
                self._trace.record(
                    DurabilityTraceKind.BACKEND_PARENT_SYNC,
                    success=True,
                    callback="fsync",
                    handle_id=handle_id,
                    generation=generation,
                    path=path_value,
                    detail=obs.detail | {"receipt_id": obs.receipt_id},
                )

            if reqs.requires_backend_effect and not backend_effect_id:
                backend_effect_id = effect
                self._media.note_backend_effect(path_value, backend_effect_id)

            # Build WAL fsync receipt when any WAL durability was required.
            if reqs.requires_wal_file_fsync or reqs.requires_wal_parent_directory_fsync:
                if not fsync_receipt_id:
                    fsync_receipt_id = f"fsync:{handle_id}:{generation}:{sequence_number}"
                wal_receipt = WALFsyncReceipt(
                    receipt_id=fsync_receipt_id,
                    generation_id=self._generation_id,
                    sequence_number=sequence_number,
                    file_fsync_observed=wal_file if reqs.requires_wal_file_fsync else True,
                    parent_directory_fsync_observed=(
                        wal_parent
                        if reqs.requires_wal_parent_directory_fsync
                        else (not reqs.requires_wal_parent_directory_fsync)
                    ),
                    path_ref=path_to_ref(path_value) or f"handle:{handle_id}",
                    backend_effect_id=backend_effect_id if reqs.requires_backend_effect else "",
                )
                # Verify receipt satisfies the mapped WAL ack requirements.
                wal_ack = ack_requirements_for(wal_ack_mode_for(mode))
                if not wal_receipt.satisfies(wal_ack):
                    raise DurabilityProtocolError(
                        "fsync receipt does not satisfy configured WAL requirements",
                        detail={
                            "mode": mode.value,
                            "receipt": wal_receipt.to_dict(),
                            "requirements": wal_ack.to_dict(),
                        },
                    )

            # Verify every required boundary was observed before acknowledging.
            if reqs.requires_wal_file_fsync and not wal_file:
                raise DurabilityProtocolError("WAL file fsync was not observed")
            if reqs.requires_wal_parent_directory_fsync and not wal_parent:
                raise DurabilityProtocolError(
                    "WAL parent-directory fsync was not observed"
                )
            if reqs.requires_backend_file_fsync and not backend_file:
                raise DurabilityProtocolError("backend file fsync was not observed")
            if reqs.requires_backend_parent_directory_fsync and not backend_parent:
                raise DurabilityProtocolError(
                    "backend parent-directory fsync was not observed"
                )
            if reqs.requires_backend_effect and not backend_effect_id:
                raise DurabilityProtocolError("backend effect identity missing")

            self._media._boundary("after_fsync", handle_key)  # type: ignore[attr-defined]

            may_claim = reqs.may_claim_durable
            with self._lock:
                state = self._require_live_locked(handle_id, generation)
                # Deferred error may have been set concurrently — fail closed.
                if state.deferred is not None:
                    deferred = state.deferred.reported()
                    state.deferred = deferred
                    receipt = self._failure_receipt(
                        callback=DurabilityCallbackKind.FSYNC,
                        disposition=DurabilityDisposition.DEFERRED_ERROR,
                        state=state,
                        errno=deferred.errno,
                        error_code=deferred.error_code.value,
                        message=deferred.message,
                        deferred_error=True,
                        deferred=deferred,
                        durability_mode=mode,
                        requirements=reqs,
                    )
                    state.last_fsync_receipt = receipt
                    return self._remember(receipt)

                state.dirty = False
                receipt = DurabilityReceipt(
                    receipt_id=self._new_receipt_id("fsync"),
                    callback=DurabilityCallbackKind.FSYNC,
                    disposition=DurabilityDisposition.SUCCESS,
                    success=True,
                    durable=may_claim,
                    durability_mode=mode,
                    handle_id=handle_id,
                    generation=generation,
                    path=state.path,
                    path_ref=path_to_ref(state.path),
                    errno=HostErrno.OK,
                    deferred_error=False,
                    observed_effect=True,
                    acknowledged_data=may_claim,
                    wal_file_fsync=wal_file,
                    wal_parent_directory_fsync=wal_parent,
                    backend_file_fsync=backend_file,
                    backend_parent_directory_fsync=backend_parent,
                    backend_effect_id=backend_effect_id,
                    fsync_receipt_id=fsync_receipt_id,
                    wal_fsync_receipt=wal_receipt,
                    sequence_number=sequence_number,
                    generation_id=self._generation_id,
                    requirements=reqs,
                    detail={
                        "datasync": datasync,
                        "fsync_count": state.fsync_count,
                        "mode": mode.value,
                    },
                )
                state.last_fsync_receipt = receipt
                if may_claim:
                    state.last_successful_fsync_receipt_id = fsync_receipt_id
                self._trace.record(
                    DurabilityTraceKind.FSYNC,
                    success=True,
                    callback="fsync",
                    handle_id=handle_id,
                    generation=generation,
                    path=state.path,
                    detail={
                        "durable": may_claim,
                        "acknowledged_data": may_claim,
                        "fsync_receipt_id": fsync_receipt_id,
                    },
                )
                self._trace.record(
                    DurabilityTraceKind.RECEIPT,
                    success=True,
                    callback="fsync",
                    handle_id=handle_id,
                    generation=generation,
                    path=state.path,
                    detail={"receipt_id": receipt.receipt_id},
                )
                return self._remember(receipt)

        except DurabilityFaultError as exc:
            return self._fault_receipt(
                callback=DurabilityCallbackKind.FSYNC,
                handle_id=handle_id,
                generation=generation,
                path=path_value,
                fault=exc.fault,
                message=exc.message,
                durability_mode=mode,
                requirements=reqs,
                detail=exc.detail,
            )
        except DurabilityError as exc:
            return self._error_receipt(
                callback=DurabilityCallbackKind.FSYNC,
                handle_id=handle_id,
                generation=generation,
                path=path_value,
                errno=exc.errno,
                error_code=exc.code.value,
                message=exc.message,
                durability_mode=mode,
                requirements=reqs,
                detail=exc.detail,
            )

    # -- release ------------------------------------------------------------

    def release(
        self,
        handle_id: int,
        *,
        generation: int = 1,
    ) -> DurabilityReceipt:
        """Idempotent release. Never manufactures durability."""

        key = (int(handle_id), int(generation))
        with self._lock:
            state = self._handles.get(key)
            if state is None:
                # Already released or unknown — idempotent success, no durability.
                prior = self._released.get(key)
                release_count = (prior.release_count + 1) if prior else 1
                if prior is not None:
                    prior.release_count = release_count
                receipt = DurabilityReceipt(
                    receipt_id=self._new_receipt_id("release"),
                    callback=DurabilityCallbackKind.RELEASE,
                    disposition=DurabilityDisposition.ALREADY_RELEASED,
                    success=True,
                    durable=False,
                    durability_mode=self._durability_mode,
                    handle_id=handle_id,
                    generation=generation,
                    path=prior.path if prior else "",
                    path_ref=path_to_ref(prior.path) if prior else "",
                    errno=HostErrno.OK,
                    already_released=True,
                    idempotent=True,
                    observed_effect=False,
                    acknowledged_data=False,
                    release_count=release_count,
                    generation_id=self._generation_id,
                    detail={"unknown_or_released": True},
                )
                if prior is not None:
                    prior.last_release_receipt = receipt
                self._trace.record(
                    DurabilityTraceKind.RELEASE,
                    success=True,
                    callback="release",
                    handle_id=handle_id,
                    generation=generation,
                    detail={"already_released": True, "durable": False},
                )
                return self._remember(receipt)

            if state.released:
                state.release_count += 1
                receipt = DurabilityReceipt(
                    receipt_id=self._new_receipt_id("release"),
                    callback=DurabilityCallbackKind.RELEASE,
                    disposition=DurabilityDisposition.ALREADY_RELEASED,
                    success=True,
                    durable=False,
                    durability_mode=self._durability_mode,
                    handle_id=handle_id,
                    generation=generation,
                    path=state.path,
                    path_ref=path_to_ref(state.path),
                    errno=HostErrno.OK,
                    already_released=True,
                    idempotent=True,
                    observed_effect=False,
                    acknowledged_data=False,
                    release_count=state.release_count,
                    generation_id=self._generation_id,
                    detail={"dirty_at_release": state.dirty},
                )
                state.last_release_receipt = receipt
                self._trace.record(
                    DurabilityTraceKind.RELEASE,
                    success=True,
                    callback="release",
                    handle_id=handle_id,
                    generation=generation,
                    path=state.path,
                    detail={"already_released": True, "durable": False},
                )
                return self._remember(receipt)

            # First release: drop dirty without committing; clear deferred.
            state.release_count += 1
            deferred_cleared = state.deferred is not None
            dirty_at_release = state.dirty
            state.deferred = None
            state.dirty = False
            state.released = True
            self._handles.pop(key, None)
            self._released[key] = state

            receipt = DurabilityReceipt(
                receipt_id=self._new_receipt_id("release"),
                callback=DurabilityCallbackKind.RELEASE,
                disposition=DurabilityDisposition.SUCCESS,
                success=True,
                durable=False,
                durability_mode=self._durability_mode,
                handle_id=handle_id,
                generation=generation,
                path=state.path,
                path_ref=path_to_ref(state.path),
                errno=HostErrno.OK,
                already_released=False,
                idempotent=False,
                observed_effect=False,
                acknowledged_data=False,
                release_count=state.release_count,
                generation_id=self._generation_id,
                detail={
                    "dirty_at_release": dirty_at_release,
                    "deferred_error_cleared": deferred_cleared,
                    "manufactured_durability": False,
                },
            )
            state.last_release_receipt = receipt
            self._trace.record(
                DurabilityTraceKind.RELEASE,
                success=True,
                callback="release",
                handle_id=handle_id,
                generation=generation,
                path=state.path,
                detail={
                    "already_released": False,
                    "durable": False,
                    "dirty_at_release": dirty_at_release,
                },
            )
            return self._remember(receipt)

    # -- fault-path helpers for tests / injection ---------------------------

    def inject_fault_receipt(
        self,
        callback: DurabilityCallbackKind | str,
        fault: DurabilityFaultKind | str,
        *,
        handle_id: int = 0,
        generation: int = 0,
        path: str = "",
        message: str = "",
    ) -> DurabilityReceipt:
        """Build a fail-closed fault receipt that never acknowledges data."""

        if not isinstance(callback, DurabilityCallbackKind):
            callback = DurabilityCallbackKind(callback)
        if not isinstance(fault, DurabilityFaultKind):
            fault = DurabilityFaultKind(fault)
        mode = (
            effective_fsync_mode(self._durability_mode)
            if callback is DurabilityCallbackKind.FSYNC
            else self._durability_mode
        )
        return self._fault_receipt(
            callback=callback,
            handle_id=handle_id,
            generation=generation,
            path=path,
            fault=fault,
            message=message or f"{callback.value} {fault.value}",
            durability_mode=mode,
            requirements=requirements_for(mode)
            if callback is DurabilityCallbackKind.FSYNC
            else None,
        )

    # -- introspection ------------------------------------------------------

    def is_released(self, handle_id: int, *, generation: int = 1) -> bool:
        key = (int(handle_id), int(generation))
        with self._lock:
            if key in self._released:
                return True
            state = self._handles.get(key)
            return bool(state and state.released)

    def is_dirty(self, handle_id: int, *, generation: int = 1) -> bool:
        with self._lock:
            state = self._handles.get((int(handle_id), int(generation)))
            return bool(state and state.dirty and not state.released)

    def to_record(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema": self.SCHEMA,
                "contract_version": CONTRACT_VERSION,
                "schema_version": SCHEMA_VERSION,
                "task_id": TASK_ID,
                "durability_mode": self._durability_mode.value,
                "generation_id": self._generation_id,
                "mount_id": self._mount_id,
                "live_handles": len(self._handles),
                "released_handles": len(self._released),
                "receipt_count": len(self._receipts),
                "requirements": requirements_for(
                    effective_fsync_mode(self._durability_mode)
                ).to_record(),
            }

    def close(self) -> None:
        with self._lock:
            self._handles.clear()

    def __enter__(self) -> "DurabilityCoordinator":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- internal -----------------------------------------------------------

    def _new_receipt_id(self, prefix: str) -> str:
        self._sequence += 1
        return f"receipt:{prefix}:{self._sequence}:{uuid.uuid4().hex[:12]}"

    def _remember(self, receipt: DurabilityReceipt) -> DurabilityReceipt:
        self._last_receipt = receipt
        self._receipts.append(receipt)
        if len(self._receipts) > MAX_TRACE_EVENTS:
            self._receipts = self._receipts[-MAX_TRACE_EVENTS:]
        return receipt

    def _require_live(
        self, handle_id: int, generation: int
    ) -> _HandleDurabilityState:
        with self._lock:
            return self._require_live_locked(handle_id, generation)

    def _require_live_locked(
        self, handle_id: int, generation: int
    ) -> _HandleDurabilityState:
        key = (int(handle_id), int(generation))
        state = self._handles.get(key)
        if state is None:
            if key in self._released:
                raise DurabilityError(
                    f"handle {handle_id} gen {generation} is released",
                    code=DurabilityErrorCode.RELEASED,
                    errno=HostErrno.EBADF,
                )
            # Auto-register unknown handles for hermetic call sites.
            state = _HandleDurabilityState(
                handle_id=int(handle_id),
                generation=int(generation),
            )
            self._handles[key] = state
        if state.released:
            raise DurabilityError(
                f"handle {handle_id} gen {generation} is released",
                code=DurabilityErrorCode.RELEASED,
                errno=HostErrno.EBADF,
            )
        return state

    def _failure_receipt(
        self,
        *,
        callback: DurabilityCallbackKind,
        disposition: DurabilityDisposition,
        state: _HandleDurabilityState,
        errno: HostErrno,
        error_code: str,
        message: str,
        deferred_error: bool = False,
        idempotent: bool = False,
        deferred: DeferredErrorState | None = None,
        durability_mode: DurabilityMode | None = None,
        requirements: DurabilityRequirements | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> DurabilityReceipt:
        mode = durability_mode or self._durability_mode
        if callback is DurabilityCallbackKind.FSYNC:
            mode = effective_fsync_mode(mode)
        return DurabilityReceipt(
            receipt_id=self._new_receipt_id(callback.value),
            callback=callback,
            disposition=disposition,
            success=False,
            durable=False,
            durability_mode=mode,
            handle_id=state.handle_id,
            generation=state.generation,
            path=state.path,
            path_ref=path_to_ref(state.path),
            errno=errno,
            error_code=error_code,
            message=message,
            deferred_error=deferred_error,
            idempotent=idempotent,
            observed_effect=False,
            acknowledged_data=False,
            flush_count=state.flush_count,
            release_count=state.release_count,
            generation_id=self._generation_id,
            requirements=requirements,
            deferred=deferred,
            detail=dict(detail or {}),
        )

    def _fault_receipt(
        self,
        *,
        callback: DurabilityCallbackKind,
        handle_id: int,
        generation: int,
        path: str,
        fault: DurabilityFaultKind,
        message: str,
        durability_mode: DurabilityMode,
        requirements: DurabilityRequirements | None,
        detail: Mapping[str, Any] | None = None,
    ) -> DurabilityReceipt:
        errno = _FAULT_TO_ERRNO[fault]
        error_code = _FAULT_TO_ERROR_CODE[fault]
        disposition = {
            DurabilityFaultKind.TIMEOUT: DurabilityDisposition.TIMED_OUT,
            DurabilityFaultKind.CANCEL: DurabilityDisposition.CANCELLED,
            DurabilityFaultKind.ENOSPC: DurabilityDisposition.FAILED,
            DurabilityFaultKind.EIO: DurabilityDisposition.FAILED,
        }[fault]
        receipt = DurabilityReceipt(
            receipt_id=self._new_receipt_id(f"{callback.value}-fault"),
            callback=callback,
            disposition=disposition,
            success=False,
            durable=False,
            durability_mode=durability_mode,
            handle_id=handle_id,
            generation=generation,
            path=path,
            path_ref=path_to_ref(path),
            errno=errno,
            error_code=error_code.value,
            message=message,
            deferred_error=False,
            observed_effect=False,
            acknowledged_data=False,
            generation_id=self._generation_id,
            requirements=requirements,
            detail={
                "fault": fault.value,
                "acknowledged_data": False,
                "lost_data_acknowledged": False,
                **dict(detail or {}),
            },
        )
        with self._lock:
            state = self._handles.get((int(handle_id), int(generation)))
            if state is not None and callback is DurabilityCallbackKind.FSYNC:
                state.last_fsync_receipt = receipt
            self._trace.record(
                DurabilityTraceKind.FAULT,
                success=False,
                callback=callback.value,
                code=error_code.value,
                handle_id=handle_id,
                generation=generation,
                path=path,
                detail={
                    "fault": fault.value,
                    "acknowledged_data": False,
                    "errno": errno.value,
                },
            )
            self._trace.record(
                DurabilityTraceKind(callback.value),
                success=False,
                callback=callback.value,
                code=error_code.value,
                handle_id=handle_id,
                generation=generation,
                path=path,
                detail={"fault": fault.value, "acknowledged_data": False},
            )
            return self._remember(receipt)

    def _error_receipt(
        self,
        *,
        callback: DurabilityCallbackKind,
        handle_id: int,
        generation: int,
        path: str,
        errno: HostErrno,
        error_code: str,
        message: str,
        durability_mode: DurabilityMode,
        requirements: DurabilityRequirements | None,
        detail: Mapping[str, Any] | None = None,
    ) -> DurabilityReceipt:
        receipt = DurabilityReceipt(
            receipt_id=self._new_receipt_id(f"{callback.value}-error"),
            callback=callback,
            disposition=DurabilityDisposition.FAILED,
            success=False,
            durable=False,
            durability_mode=durability_mode,
            handle_id=handle_id,
            generation=generation,
            path=path,
            path_ref=path_to_ref(path),
            errno=errno,
            error_code=error_code,
            message=message,
            observed_effect=False,
            acknowledged_data=False,
            generation_id=self._generation_id,
            requirements=requirements,
            detail={
                "acknowledged_data": False,
                "lost_data_acknowledged": False,
                **dict(detail or {}),
            },
        )
        with self._lock:
            self._trace.record(
                DurabilityTraceKind(callback.value),
                success=False,
                callback=callback.value,
                code=error_code,
                handle_id=handle_id,
                generation=generation,
                path=path,
                detail={"acknowledged_data": False},
            )
            return self._remember(receipt)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def build_durability_coordinator(
    *,
    durability_mode: DurabilityMode | str = DurabilityMode.COMMITTED_VISIBLE,
    directory: str | Path | None = None,
    **kwargs: Any,
) -> DurabilityCoordinator:
    """Construct a :class:`DurabilityCoordinator` with defaults."""

    return DurabilityCoordinator(
        durability_mode=durability_mode,
        directory=directory,
        **kwargs,
    )


def durability_modes() -> tuple[str, ...]:
    """Closed host durability mode vocabulary (stable order)."""

    return tuple(m.value for m in DurabilityMode)


def durability_callbacks() -> tuple[str, ...]:
    """Closed durability callback vocabulary."""

    return tuple(c.value for c in DurabilityCallbackKind)


def fault_kinds() -> tuple[str, ...]:
    """Closed fault kinds that must never acknowledge lost data."""

    return tuple(f.value for f in DurabilityFaultKind)


def content_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


__all__ = [
    "TASK_ID",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "DurabilityCoordinator_V1",
    "DurabilityReceipt_V1",
    "DeferredErrorState_V1",
    "DurabilityCallbackKind",
    "DurabilityDisposition",
    "DurabilityErrorCode",
    "DurabilityTraceKind",
    "DurabilityFaultKind",
    "DurabilityError",
    "DurabilityValidationError",
    "DurabilityProtocolError",
    "DurabilityFaultError",
    "DurabilityRequirements",
    "DeferredErrorState",
    "DurabilityReceipt",
    "DurabilityTraceEvent",
    "DurabilityTrace",
    "DurabilityBoundaryObservation",
    "DurabilityMedia",
    "DurabilityCoordinator",
    "build_durability_coordinator",
    "requirements_for",
    "all_mode_requirements",
    "effective_fsync_mode",
    "wal_ack_mode_for",
    "path_to_ref",
    "host_callback_for",
    "durability_modes",
    "durability_callbacks",
    "fault_kinds",
    "content_digest",
]
