"""Durable, fail-closed state for strict UCAN verification.

The ledger intentionally stores only public verification material.  It is not a
credential wallet and must never be used to persist private keys or bearer
tokens.  Every mutation is written atomically so replay and revocation state
survives a process restart.
"""

from __future__ import annotations

import base64
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Callable, Mapping

try:  # POSIX is the supported deployment target for the MCP daemon.
    import fcntl
except ImportError:  # pragma: no cover - retained so absence fails closed
    fcntl = None  # type: ignore[assignment]


class LedgerUnavailableError(RuntimeError):
    """Raised when durable authorization state cannot be safely consulted."""


class LedgerFormatError(LedgerUnavailableError):
    """Raised for corrupt or unrecognised on-disk ledger state."""


_SCHEMA = "ipfs-kit.ucan-revocation-ledger@1"
_LOCK = threading.RLock()


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64url(value: str) -> bytes:
    text = str(value).strip()
    if not text or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in text):
        raise ValueError("invalid_base64url")
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise LedgerFormatError("invalid_" + field)
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise LedgerFormatError("invalid_" + field) from exc
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        raise LedgerFormatError("invalid_" + field)
    return parsed


class RevocationLedger:
    """An atomically persisted revocation, nonce, and public-key ledger.

    ``path`` is mandatory for normal verification.  A missing, unreadable, or
    malformed ledger is deliberately unavailable rather than treated as empty.
    """

    def __init__(self, path: str | os.PathLike[str] | None):
        self.path = Path(path) if path is not None else None
        self._failure: str | None = None
        if self.path is None:
            self._failure = "ledger_path_missing"
            return
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self.path.exists():
                self._read_state()
            else:
                self._write_state(self._empty_state())
        except Exception as exc:  # retain reason but never silently recover
            self._failure = type(exc).__name__

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {"schema": _SCHEMA, "version": 1, "revoked": {}, "nonces": {}, "keys": {}}

    @property
    def available(self) -> bool:
        if self._failure is not None or self.path is None or fcntl is None:
            return False
        try:
            self._read_state()
            return True
        except Exception:
            return False

    @property
    def failure_reason(self) -> str | None:
        return self._failure

    def _require_available(self) -> Path:
        if self.path is None or fcntl is None:
            raise LedgerUnavailableError(self._failure or "ledger_unavailable")
        if self._failure is not None:
            raise LedgerUnavailableError(self._failure)
        return self.path

    def _lock_path(self) -> Path:
        path = self._require_available()
        return path.with_name(path.name + ".lock")

    def _validate_state(self, state: Any) -> dict[str, Any]:
        if not isinstance(state, dict) or state.get("schema") != _SCHEMA or state.get("version") != 1:
            raise LedgerFormatError("invalid_ledger_schema")
        for name in ("revoked", "nonces", "keys"):
            if not isinstance(state.get(name), dict):
                raise LedgerFormatError("invalid_ledger_" + name)
        # Validate enough of every persisted item that a corrupt state cannot
        # turn into an authorization bypass after a restart.
        for identifier, record in state["revoked"].items():
            if not isinstance(identifier, str) or not identifier or not isinstance(record, dict):
                raise LedgerFormatError("invalid_revocation")
            _number(record.get("revoked_at"), "revoked_at")
        for nonce_key, expiry in state["nonces"].items():
            if not isinstance(nonce_key, str) or not nonce_key:
                raise LedgerFormatError("invalid_nonce")
            _number(expiry, "nonce_expiry")
        for issuer, entries in state["keys"].items():
            if not isinstance(issuer, str) or not issuer or not isinstance(entries, dict):
                raise LedgerFormatError("invalid_key_record")
            for kid, record in entries.items():
                if not isinstance(kid, str) or not kid or not isinstance(record, dict):
                    raise LedgerFormatError("invalid_key_record")
                key = record.get("public_key")
                if not isinstance(key, str) or len(_unb64url(key)) != 32:
                    raise LedgerFormatError("invalid_public_key")
                if not isinstance(record.get("revoked"), bool):
                    raise LedgerFormatError("invalid_key_revocation")
                if record.get("not_before") is not None:
                    _number(record["not_before"], "key_not_before")
                if record.get("not_after") is not None:
                    _number(record["not_after"], "key_not_after")
        return state

    def _read_state(self) -> dict[str, Any]:
        path = self._require_available()
        try:
            raw = path.read_bytes()
            state = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LedgerFormatError("ledger_read_failed") from exc
        return self._validate_state(state)

    def _write_state(self, state: Mapping[str, Any]) -> None:
        path = self._require_available()
        checked = self._validate_state(copy.deepcopy(dict(state)))
        encoded = json.dumps(checked, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        descriptor, temporary_name = tempfile.mkstemp(prefix=".ucan-ledger-", dir=str(path.parent))
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
            directory_descriptor = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise

    def _mutate(self, operation: Callable[[dict[str, Any]], Any]) -> Any:
        lock_path = self._lock_path()
        with _LOCK, open(lock_path, "a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                state = self._read_state()
                result = operation(state)
                self._write_state(state)
                return result
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _inspect(self, operation: Callable[[dict[str, Any]], Any]) -> Any:
        lock_path = self._lock_path()
        with _LOCK, open(lock_path, "a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_SH)
            try:
                return operation(self._read_state())
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _identifier(identifier: str) -> str:
        value = str(identifier or "").strip()
        if not value or len(value) > 512:
            raise ValueError("invalid_identifier")
        return value

    def revoke(self, identifier: str, *, reason: str = "") -> None:
        identifier = self._identifier(identifier)
        safe_reason = str(reason or "")[:256]
        self._mutate(lambda state: state["revoked"].setdefault(identifier, {"revoked_at": time.time(), "reason": safe_reason}))

    def is_revoked(self, identifier: str) -> bool:
        identifier = self._identifier(identifier)
        return bool(self._inspect(lambda state: identifier in state["revoked"]))

    def consume_nonce(self, namespace: str, nonce: str, *, expires_at: float) -> bool:
        """Persistently consume a nonce.  Returns false for a replay."""
        namespace, nonce = self._identifier(namespace), self._identifier(nonce)
        expiry = _number(expires_at, "nonce_expiry")
        key = _b64url((namespace + "\x00" + nonce).encode("utf-8"))

        def consume(state: dict[str, Any]) -> bool:
            now = time.time()
            state["nonces"] = {k: v for k, v in state["nonces"].items() if _number(v, "nonce_expiry") >= now}
            if key in state["nonces"]:
                return False
            state["nonces"][key] = expiry
            return True

        return bool(self._mutate(consume))

    def register_public_key(
        self, issuer: str, kid: str, public_key: bytes | str, *, not_before: float | None = None,
        not_after: float | None = None, replace: bool = False,
    ) -> None:
        issuer, kid = self._identifier(issuer), self._identifier(kid)
        raw = _unb64url(public_key) if isinstance(public_key, str) else bytes(public_key)
        if len(raw) != 32:
            raise ValueError("ed25519_public_key_must_be_32_bytes")
        start = None if not_before is None else _number(not_before, "key_not_before")
        end = None if not_after is None else _number(not_after, "key_not_after")
        if start is not None and end is not None and start > end:
            raise ValueError("invalid_key_validity_window")

        def register(state: dict[str, Any]) -> None:
            entries = state["keys"].setdefault(issuer, {})
            if kid in entries and not replace:
                raise ValueError("key_already_registered")
            entries[kid] = {"public_key": _b64url(raw), "not_before": start, "not_after": end, "revoked": False}

        self._mutate(register)

    def rotate_key(self, issuer: str, old_kid: str, new_kid: str, public_key: bytes | str, **validity: Any) -> None:
        """Register a replacement public key and revoke the old key atomically."""
        issuer, old_kid, new_kid = self._identifier(issuer), self._identifier(old_kid), self._identifier(new_kid)
        raw = _unb64url(public_key) if isinstance(public_key, str) else bytes(public_key)
        if len(raw) != 32:
            raise ValueError("ed25519_public_key_must_be_32_bytes")
        start = validity.get("not_before")
        end = validity.get("not_after")
        start = None if start is None else _number(start, "key_not_before")
        end = None if end is None else _number(end, "key_not_after")

        def rotate(state: dict[str, Any]) -> None:
            entries = state["keys"].get(issuer, {})
            if old_kid not in entries or new_kid in entries:
                raise ValueError("invalid_key_rotation")
            entries[old_kid]["revoked"] = True
            entries[new_kid] = {"public_key": _b64url(raw), "not_before": start, "not_after": end, "revoked": False}

        self._mutate(rotate)

    def revoke_key(self, issuer: str, kid: str) -> None:
        issuer, kid = self._identifier(issuer), self._identifier(kid)

        def revoke_key(state: dict[str, Any]) -> None:
            try:
                state["keys"][issuer][kid]["revoked"] = True
            except KeyError as exc:
                raise ValueError("unknown_key") from exc

        self._mutate(revoke_key)

    def resolve_public_key(self, issuer: str, kid: str, *, now: float | None = None) -> bytes | None:
        issuer, kid = self._identifier(issuer), self._identifier(kid)
        current = time.time() if now is None else _number(now, "key_time")

        def resolve(state: dict[str, Any]) -> bytes | None:
            record = state["keys"].get(issuer, {}).get(kid)
            if not isinstance(record, dict) or record.get("revoked"):
                return None
            if record.get("not_before") is not None and current < _number(record["not_before"], "key_not_before"):
                return None
            if record.get("not_after") is not None and current > _number(record["not_after"], "key_not_after"):
                return None
            return _unb64url(record["public_key"])

        return self._inspect(resolve)
