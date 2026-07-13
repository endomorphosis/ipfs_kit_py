"""Typed failures exposed by the Iroh runtime boundary.

The sidecar's error vocabulary is deliberately small and versioned.  This
module is the only place where wire error codes are translated into Python
exception types.  Callers can therefore catch a useful built-in base class
(for example :class:`FileNotFoundError`) while still inspecting ``code`` for a
stable, backend-specific reason.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar


ERROR_CODES = frozenset(
    {
        "invalid_url",
        "invalid_path",
        "invalid_hash",
        "invalid_manifest",
        "invalid_config",
        "unsupported_version",
        "unsupported_operation",
        "not_found",
        "already_exists",
        "not_directory",
        "is_directory",
        "not_empty",
        "permission_denied",
        "conflict",
        "unavailable",
        "timeout",
        "cancelled",
        "integrity_error",
        "io_error",
        "protocol_error",
    }
)


class IrohError(Exception):
    """Base error whose fields are safe to expose above the runtime boundary."""

    code: ClassVar[str] = "protocol_error"

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        # Materialize metadata so a caller cannot mutate an exception through
        # the mapping it originally supplied.  Boundary code is responsible
        # for passing only its redacted, public allowlist here.
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.metadata = dict(metadata or {})

    def __str__(self) -> str:
        if self.operation:
            return f"{self.operation}: {self.message}"
        return self.message

    def as_dict(self) -> dict[str, Any]:
        """Return the stable, serialization-friendly public error shape."""

        return {
            "code": self.code,
            "message": self.message,
            "operation": self.operation,
            "metadata": dict(self.metadata),
        }


class IrohInvalidURLError(IrohError, ValueError):
    code = "invalid_url"


class IrohInvalidPathError(IrohError, ValueError):
    code = "invalid_path"


class IrohInvalidHashError(IrohError, ValueError):
    code = "invalid_hash"


class IrohInvalidManifestError(IrohError, ValueError):
    code = "invalid_manifest"


class IrohInvalidConfigError(IrohError, ValueError):
    code = "invalid_config"


class IrohUnsupportedVersionError(IrohError):
    code = "unsupported_version"


class IrohUnsupportedOperationError(IrohError, NotImplementedError):
    code = "unsupported_operation"


class IrohNotFoundError(IrohError, FileNotFoundError):
    code = "not_found"


class IrohAlreadyExistsError(IrohError, FileExistsError):
    code = "already_exists"


class IrohNotDirectoryError(IrohError, NotADirectoryError):
    code = "not_directory"


class IrohIsDirectoryError(IrohError, IsADirectoryError):
    code = "is_directory"


class IrohNotEmptyError(IrohError, OSError):
    code = "not_empty"


class IrohPermissionDeniedError(IrohError, PermissionError):
    code = "permission_denied"


class IrohConflictError(IrohError):
    code = "conflict"


class IrohUnavailableError(IrohError, ConnectionError):
    code = "unavailable"


class IrohTimeoutError(IrohError, TimeoutError):
    code = "timeout"


class IrohCancelledError(IrohError):
    code = "cancelled"


class IrohIntegrityError(IrohError):
    code = "integrity_error"


class IrohIOError(IrohError, OSError):
    code = "io_error"


class IrohProtocolError(IrohError):
    code = "protocol_error"


_ERROR_TYPES: dict[str, type[IrohError]] = {
    error_type.code: error_type
    for error_type in (
        IrohInvalidURLError,
        IrohInvalidPathError,
        IrohInvalidHashError,
        IrohInvalidManifestError,
        IrohInvalidConfigError,
        IrohUnsupportedVersionError,
        IrohUnsupportedOperationError,
        IrohNotFoundError,
        IrohAlreadyExistsError,
        IrohNotDirectoryError,
        IrohIsDirectoryError,
        IrohNotEmptyError,
        IrohPermissionDeniedError,
        IrohConflictError,
        IrohUnavailableError,
        IrohTimeoutError,
        IrohCancelledError,
        IrohIntegrityError,
        IrohIOError,
        IrohProtocolError,
    )
}


def error_from_code(
    code: str,
    message: str,
    *,
    operation: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> IrohError:
    """Create the public exception corresponding to a sidecar error code.

    Unknown codes fail closed as protocol errors.  The unknown value is not
    copied into the exception because an untrusted sidecar could place secret
    or attacker-controlled material in that field.
    """

    error_type = _ERROR_TYPES.get(code)
    if error_type is None:
        return IrohProtocolError(
            "sidecar returned an unknown error code",
            operation=operation,
            metadata={"sidecar_code": "unknown"},
        )
    return error_type(message, operation=operation, metadata=metadata)


# Compact compatibility names used by early consumers of the boundary.
InvalidURLError = IrohInvalidURLError
InvalidPathError = IrohInvalidPathError
InvalidHashError = IrohInvalidHashError
InvalidManifestError = IrohInvalidManifestError
InvalidConfigError = IrohInvalidConfigError
UnsupportedVersionError = IrohUnsupportedVersionError
UnsupportedOperationError = IrohUnsupportedOperationError
NotFoundError = IrohNotFoundError
AlreadyExistsError = IrohAlreadyExistsError
NotDirectoryError = IrohNotDirectoryError
IsDirectoryError = IrohIsDirectoryError
NotEmptyError = IrohNotEmptyError
PermissionDeniedError = IrohPermissionDeniedError
ConflictError = IrohConflictError
UnavailableError = IrohUnavailableError
RuntimeTimeoutError = IrohTimeoutError
CancelledError = IrohCancelledError
IntegrityError = IrohIntegrityError
IOError = IrohIOError
ProtocolError = IrohProtocolError


__all__ = [
    "ERROR_CODES",
    "IrohError",
    "IrohInvalidURLError",
    "IrohInvalidPathError",
    "IrohInvalidHashError",
    "IrohInvalidManifestError",
    "IrohInvalidConfigError",
    "IrohUnsupportedVersionError",
    "IrohUnsupportedOperationError",
    "IrohNotFoundError",
    "IrohAlreadyExistsError",
    "IrohNotDirectoryError",
    "IrohIsDirectoryError",
    "IrohNotEmptyError",
    "IrohPermissionDeniedError",
    "IrohConflictError",
    "IrohUnavailableError",
    "IrohTimeoutError",
    "IrohCancelledError",
    "IrohIntegrityError",
    "IrohIOError",
    "IrohProtocolError",
    "error_from_code",
]
