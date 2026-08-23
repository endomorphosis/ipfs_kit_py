"""Short-lived opaque secret broker for leased workers (EAAEF-124).

Handles resolve only under their exact current lease/task/policy binding.
Secret material can be exposed as a bounded owner-only ephemeral file, never
as an event field. Checkpoint and terminal boundaries revoke matching handles,
zero in-memory buffers, and remove only the exact files created by this broker.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final
from uuid import uuid4

BROKER_SCHEMA: Final[str] = "ipfs_kit_py/secret-broker/external-worker@1"
DEFAULT_TTL_SECONDS: Final[float] = 300.0
MAX_TTL_SECONDS: Final[float] = 3_600.0
MAX_SECRET_BYTES: Final[int] = 1_048_576
_HANDLE_RE: Final[re.Pattern[str]] = re.compile(r"^opaque:[0-9a-f]{32}$")
_FILENAME_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_REDACTED: Final[str] = "[redacted]"
_SENSITIVE_KEY_MARKERS: Final[tuple[str, ...]] = (
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "password",
    "private_key",
    "secret",
    "session_token",
    "token",
)


class SecretBrokerError(ValueError):
    """Opaque handle could not be resolved under the current lease."""

    def __init__(self, message: str, *, reason_code: str = "denied") -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _required_text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text or len(text.encode("utf-8")) > 256:
        raise SecretBrokerError(f"{name} is required and bounded", reason_code="invalid")
    return text


@dataclass(frozen=True, slots=True)
class OpaqueHandle:
    handle_id: str
    lease_id: str
    task_id: str
    policy_id: str

    def __post_init__(self) -> None:
        handle_id = str(self.handle_id or "").strip()
        if not _HANDLE_RE.fullmatch(handle_id):
            raise SecretBrokerError("handle_id is malformed", reason_code="invalid")
        object.__setattr__(self, "handle_id", handle_id)
        for name in ("lease_id", "task_id", "policy_id"):
            object.__setattr__(self, name, _required_text(getattr(self, name), name))

    def as_event_field(self) -> str:
        return self.handle_id

    def to_event(self) -> Mapping[str, str]:
        return MappingProxyType(
            {
                "handle_id": self.handle_id,
                "lease_id": self.lease_id,
                "task_id": self.task_id,
                "policy_id": self.policy_id,
            }
        )


@dataclass(frozen=True, slots=True)
class EphemeralSecretFile:
    """Runtime-only path to an owner-readable file, never an event payload."""

    handle_id: str
    path: Path
    byte_count: int
    mode: int = 0o400


@dataclass(slots=True)
class _SecretMaterial:
    buffer: bytearray
    text: bool

    def reveal(self) -> str | bytes:
        payload = bytes(self.buffer)
        return payload.decode("utf-8") if self.text else payload

    def zero(self) -> None:
        for index in range(len(self.buffer)):
            self.buffer[index] = 0


@dataclass(frozen=True, slots=True)
class _MountRecord:
    directory_name: str
    filename: str
    directory_identity: tuple[int, int]


def _prepare_root(path: Path) -> tuple[Path, tuple[int, int]]:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if current.is_symlink():
            raise SecretBrokerError(
                "secret root must not contain symlinks",
                reason_code="unsafe_root",
            )
    absolute.mkdir(parents=True, exist_ok=True, mode=0o700)
    if absolute.resolve(strict=True) != absolute:
        raise SecretBrokerError("secret root escaped", reason_code="unsafe_root")
    metadata = absolute.stat(follow_symlinks=False)
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.geteuid():
        raise SecretBrokerError(
            "secret root must be an owned directory",
            reason_code="unsafe_root",
        )
    if metadata.st_mode & 0o022:
        raise SecretBrokerError(
            "secret root must not be group/world writable",
            reason_code="unsafe_root",
        )
    os.chmod(absolute, 0o700, follow_symlinks=False)
    return absolute, (metadata.st_dev, metadata.st_ino)


class SecretBroker:
    """Lease-bound broker with TTL, recursive redaction and bounded cleanup."""

    def __init__(
        self,
        root: Path | str | None = None,
        *,
        default_ttl_seconds: float = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if (
            isinstance(default_ttl_seconds, bool)
            or not isinstance(default_ttl_seconds, (int, float))
            or default_ttl_seconds <= 0
            or default_ttl_seconds > MAX_TTL_SECONDS
        ):
            raise SecretBrokerError("default TTL is outside the admitted bound")
        self._root: Path | None = None
        self._root_identity: tuple[int, int] | None = None
        if root is not None:
            self._root, self._root_identity = _prepare_root(Path(root))
        self._default_ttl = float(default_ttl_seconds)
        self._clock = clock
        self._secrets: dict[str, _SecretMaterial] = {}
        self._meta: dict[str, OpaqueHandle] = {}
        self._expires_at: dict[str, float] = {}
        self._mounts: dict[str, _MountRecord] = {}
        self._revoked: set[str] = set()
        self._redaction_digests: set[str] = set()
        self._lock = threading.RLock()

    def issue(
        self,
        secret: str | bytes,
        *,
        lease_id: str,
        task_id: str,
        policy_id: str,
        ttl_seconds: float | None = None,
    ) -> OpaqueHandle:
        if isinstance(secret, str):
            payload = secret.encode("utf-8")
            text = True
        elif isinstance(secret, bytes):
            payload = secret
            text = False
        else:
            raise SecretBrokerError("secret must be text or bytes", reason_code="invalid")
        if not payload or len(payload) > MAX_SECRET_BYTES:
            raise SecretBrokerError(
                "secret byte length is outside the admitted bound",
                reason_code="invalid",
            )
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        if (
            isinstance(ttl, bool)
            or not isinstance(ttl, (int, float))
            or ttl <= 0
            or ttl > MAX_TTL_SECONDS
        ):
            raise SecretBrokerError("TTL is outside the admitted bound", reason_code="invalid")
        handle = OpaqueHandle(
            handle_id=f"opaque:{uuid4().hex}",
            lease_id=lease_id,
            task_id=task_id,
            policy_id=policy_id,
        )
        with self._lock:
            self._secrets[handle.handle_id] = _SecretMaterial(bytearray(payload), text)
            self._meta[handle.handle_id] = handle
            self._expires_at[handle.handle_id] = self._clock() + float(ttl)
            self._redaction_digests.add(hashlib.sha256(payload).hexdigest())
        return handle

    @staticmethod
    def _handle_id(handle: OpaqueHandle | str) -> str:
        handle_id = handle.handle_id if isinstance(handle, OpaqueHandle) else str(handle)
        if not _HANDLE_RE.fullmatch(handle_id):
            raise SecretBrokerError("unknown handle", reason_code="unknown_handle")
        return handle_id

    def _bound_material(
        self,
        handle: OpaqueHandle | str,
        *,
        lease_id: str | None,
        task_id: str | None,
        policy_id: str | None,
    ) -> tuple[str, _SecretMaterial]:
        handle_id = self._handle_id(handle)
        if handle_id in self._revoked:
            raise SecretBrokerError("handle is revoked", reason_code="revoked")
        meta = self._meta.get(handle_id)
        material = self._secrets.get(handle_id)
        if meta is None or material is None:
            raise SecretBrokerError("unknown handle", reason_code="unknown_handle")
        if self._clock() >= self._expires_at[handle_id]:
            try:
                self._revoke_locked(handle_id)
            except SecretBrokerError:
                pass
            raise SecretBrokerError("handle is expired", reason_code="expired")
        if lease_id != meta.lease_id or task_id != meta.task_id or policy_id != meta.policy_id:
            raise SecretBrokerError(
                "handle is not bound to this lease/task/policy",
                reason_code="lease_mismatch",
            )
        return handle_id, material

    def resolve(
        self,
        handle: OpaqueHandle | str,
        lease_id: str | None = None,
        task_id: str | None = None,
        policy_id: str | None = None,
        **kwargs: str,
    ) -> str | bytes:
        lease_id = kwargs.get("lease_id", lease_id)
        task_id = kwargs.get("task_id", task_id)
        policy_id = kwargs.get("policy_id", policy_id)
        with self._lock:
            _, material = self._bound_material(
                handle,
                lease_id=lease_id,
                task_id=task_id,
                policy_id=policy_id,
            )
            return material.reveal()

    def _open_root(self) -> int:
        if self._root is None or self._root_identity is None:
            raise SecretBrokerError(
                "ephemeral secret root is not configured",
                reason_code="root_unconfigured",
            )
        try:
            descriptor = os.open(
                self._root,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            )
        except OSError as exc:
            raise SecretBrokerError(
                "secret root cannot be opened",
                reason_code="unsafe_root",
            ) from exc
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or (metadata.st_dev, metadata.st_ino) != self._root_identity
        ):
            os.close(descriptor)
            raise SecretBrokerError("secret root identity changed", reason_code="unsafe_root")
        return descriptor

    def mount_ephemeral_file(
        self,
        handle: OpaqueHandle | str,
        *,
        lease_id: str,
        task_id: str,
        policy_id: str,
        filename: str = "secret",
    ) -> EphemeralSecretFile:
        if not _FILENAME_RE.fullmatch(filename) or filename in {".", ".."}:
            raise SecretBrokerError("ephemeral filename is unsafe", reason_code="invalid")
        with self._lock:
            handle_id, material = self._bound_material(
                handle,
                lease_id=lease_id,
                task_id=task_id,
                policy_id=policy_id,
            )
            if handle_id in self._mounts:
                raise SecretBrokerError("handle is already mounted", reason_code="already_mounted")
            root_fd = self._open_root()
            directory_name = handle_id.split(":", 1)[1]
            directory_created = False
            file_created = False
            try:
                os.mkdir(directory_name, 0o700, dir_fd=root_fd)
                directory_created = True
                directory_fd = os.open(
                    directory_name,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=root_fd,
                )
                try:
                    directory_stat = os.fstat(directory_fd)
                    file_fd = os.open(
                        filename,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=directory_fd,
                    )
                    file_created = True
                    try:
                        view = memoryview(material.buffer)
                        while view:
                            written = os.write(file_fd, view)
                            if written <= 0:
                                raise SecretBrokerError(
                                    "ephemeral secret write made no progress",
                                    reason_code="mount_failed",
                                )
                            view = view[written:]
                        os.fsync(file_fd)
                        os.fchmod(file_fd, 0o400)
                    finally:
                        os.close(file_fd)
                finally:
                    os.close(directory_fd)
            except (OSError, SecretBrokerError) as exc:
                if directory_created:
                    try:
                        cleanup_fd = os.open(
                            directory_name,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=root_fd,
                        )
                        try:
                            if file_created:
                                os.unlink(filename, dir_fd=cleanup_fd)
                            if os.listdir(cleanup_fd):
                                raise SecretBrokerError(
                                    "failed mount contains unexpected entries",
                                    reason_code="cleanup_failed",
                                )
                        finally:
                            os.close(cleanup_fd)
                        os.rmdir(directory_name, dir_fd=root_fd)
                    except OSError as cleanup_exc:
                        raise SecretBrokerError(
                            "bounded failed-mount cleanup failed",
                            reason_code="cleanup_failed",
                        ) from cleanup_exc
                if isinstance(exc, SecretBrokerError):
                    raise
                raise SecretBrokerError(
                    "ephemeral secret mount failed",
                    reason_code="mount_failed",
                ) from exc
            finally:
                os.close(root_fd)
            self._mounts[handle_id] = _MountRecord(
                directory_name=directory_name,
                filename=filename,
                directory_identity=(directory_stat.st_dev, directory_stat.st_ino),
            )
            assert self._root is not None
            return EphemeralSecretFile(
                handle_id=handle_id,
                path=self._root / directory_name / filename,
                byte_count=len(material.buffer),
            )

    def _remove_mount_locked(self, handle_id: str) -> None:
        record = self._mounts.get(handle_id)
        if record is None:
            return
        root_fd = self._open_root()
        try:
            directory_fd = os.open(
                record.directory_name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=root_fd,
            )
            try:
                metadata = os.fstat(directory_fd)
                if (metadata.st_dev, metadata.st_ino) != record.directory_identity:
                    raise SecretBrokerError(
                        "ephemeral mount identity changed",
                        reason_code="cleanup_failed",
                    )
                try:
                    os.unlink(record.filename, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
                if os.listdir(directory_fd):
                    raise SecretBrokerError(
                        "ephemeral mount contains unexpected entries",
                        reason_code="cleanup_failed",
                    )
            finally:
                os.close(directory_fd)
            os.rmdir(record.directory_name, dir_fd=root_fd)
            self._mounts.pop(handle_id, None)
        except OSError as exc:
            raise SecretBrokerError(
                "bounded ephemeral cleanup failed",
                reason_code="cleanup_failed",
            ) from exc
        finally:
            os.close(root_fd)

    def _revoke_locked(self, handle_id: str) -> None:
        self._revoked.add(handle_id)
        material = self._secrets.pop(handle_id, None)
        self._expires_at.pop(handle_id, None)
        cleanup_error: SecretBrokerError | None = None
        try:
            self._remove_mount_locked(handle_id)
        except SecretBrokerError as exc:
            cleanup_error = exc
        if material is not None:
            material.zero()
        if cleanup_error is not None:
            raise cleanup_error

    def revoke(self, handle: OpaqueHandle | str) -> None:
        handle_id = self._handle_id(handle)
        with self._lock:
            if handle_id in self._revoked:
                self._remove_mount_locked(handle_id)
                return
            if handle_id not in self._meta:
                raise SecretBrokerError("unknown handle", reason_code="unknown_handle")
            self._revoke_locked(handle_id)

    def revoke_at_boundary(
        self,
        *,
        lease_id: str,
        task_id: str,
        policy_id: str,
        boundary: str,
    ) -> tuple[str, ...]:
        if boundary not in {"checkpoint", "terminal"}:
            raise SecretBrokerError("unknown revocation boundary", reason_code="invalid")
        binding = (
            _required_text(lease_id, "lease_id"),
            _required_text(task_id, "task_id"),
            _required_text(policy_id, "policy_id"),
        )
        with self._lock:
            selected = tuple(
                handle_id
                for handle_id, meta in self._meta.items()
                if (meta.lease_id, meta.task_id, meta.policy_id) == binding
                and (handle_id not in self._revoked or handle_id in self._mounts)
            )
            first_error: SecretBrokerError | None = None
            for handle_id in selected:
                try:
                    self._revoke_locked(handle_id)
                except SecretBrokerError as exc:
                    first_error = first_error or exc
            if first_error is not None:
                raise first_error
            return selected

    def redact(self, event: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(event, Mapping):
            raise SecretBrokerError("event must be an object", reason_code="invalid")
        with self._lock:
            active = tuple(bytes(item.buffer) for item in self._secrets.values())
            historical_digests = frozenset(self._redaction_digests)

        def scrub(value: Any, key: str = "") -> Any:
            normalized = key.strip().lower().replace("-", "_")
            if any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS):
                return _REDACTED
            if isinstance(value, Mapping):
                return {
                    str(item_key): scrub(item, str(item_key))
                    for item_key, item in value.items()
                }
            if isinstance(value, (list, tuple)):
                return [scrub(item) for item in value]
            if isinstance(value, bytes):
                if any(secret and secret in value for secret in active):
                    return _REDACTED
                if hashlib.sha256(value).hexdigest() in historical_digests:
                    return _REDACTED
                return value
            if isinstance(value, str):
                encoded = value.encode("utf-8")
                if hashlib.sha256(encoded).hexdigest() in historical_digests:
                    return _REDACTED
                redacted = value
                for secret in active:
                    if not secret:
                        continue
                    try:
                        secret_text = secret.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    if secret_text in redacted:
                        redacted = redacted.replace(secret_text, _REDACTED)
                return redacted
            return value

        return MappingProxyType(
            {str(key): scrub(value, str(key)) for key, value in event.items()}
        )


__all__ = (
    "BROKER_SCHEMA",
    "DEFAULT_TTL_SECONDS",
    "EphemeralSecretFile",
    "OpaqueHandle",
    "SecretBroker",
    "SecretBrokerError",
)
