"""Closed, inert contracts for revisioned durable state roots.

This module deliberately owns only value validation and wire representations.
It neither opens a store nor derives a semantic CID; persistence is supplied by
the later state-root adapter and ``DurableCoordinationStore`` integration.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, TypeVar


_T = TypeVar("_T")
_NAMESPACE_SEGMENT = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,61}[a-z0-9])?")
_IDENTIFIER = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")
_REASON_CODE = re.compile(r"[a-z][a-z0-9_-]{0,63}")


class RootUpdateStatus(str, Enum):
    """The complete set of outcomes of a root compare-and-swap."""

    UPDATED = "updated"
    UNCHANGED = "unchanged"
    CONFLICT = "conflict"
    UNAVAILABLE = "unavailable"
    CORRUPT = "corrupt"


class ProviderStatus(str, Enum):
    """Truthful outcome of optional remote replication."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    CORRUPT = "corrupt"
    NOT_REQUESTED = "not_requested"


def _closed_mapping(value: object, fields: frozenset[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    actual = frozenset(value)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        problems = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        raise ValueError(f"{name} has " + "; ".join(problems))
    return value


def _require_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _require_nonnegative_revision(value: object, name: str = "revision") -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _validate_namespace(namespace: object) -> str:
    if not isinstance(namespace, str) or not namespace or len(namespace) > 255:
        raise ValueError("namespace must be a non-empty normalized string up to 255 characters")
    if namespace != namespace.strip() or "//" in namespace:
        raise ValueError("namespace must be normalized")
    segments = namespace.split("/")
    if not all(_NAMESPACE_SEGMENT.fullmatch(segment) for segment in segments):
        raise ValueError("namespace contains an invalid segment")
    return namespace


def _validate_identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} must be a normalized identifier")
    return value


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
        if shift > 63:
            break
    raise ValueError("CID contains an invalid varint")


def _validate_cid(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) < 10 or value[0] != "b":
        raise ValueError(f"{name} must be a lowercase CIDv1")
    encoded = value[1:]
    if any(character not in "abcdefghijklmnopqrstuvwxyz234567" for character in encoded):
        raise ValueError(f"{name} must be lowercase base32")
    try:
        raw = base64.b32decode(encoded.upper() + "=" * ((8 - len(encoded) % 8) % 8))
        version, offset = _read_varint(raw, 0)
        codec, offset = _read_varint(raw, offset)
        multihash, offset = _read_varint(raw, offset)
        digest_length, offset = _read_varint(raw, offset)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError(f"{name} is malformed") from exc
    if version != 1 or codec not in (0x55, 0x0129) or multihash != 0x12 or digest_length != 32:
        raise ValueError(f"{name} uses an unsupported CID profile")
    if len(raw) != offset + digest_length:
        raise ValueError(f"{name} has an invalid digest length")
    return value


def _optional_cid(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _validate_cid(value, name)


def _status(value: object, enum: type[_T], name: str) -> _T:
    if not isinstance(value, enum):
        raise ValueError(f"{name} must be a {enum.__name__}")
    return value


@dataclass(frozen=True, slots=True)
class StateRootSnapshot:
    """A single namespace's currently visible root and generation."""

    namespace: str
    root_cid: str | None
    revision: int
    transition_cid: str | None

    def __post_init__(self) -> None:
        _validate_namespace(self.namespace)
        _optional_cid(self.root_cid, "root_cid")
        _require_nonnegative_revision(self.revision)
        _optional_cid(self.transition_cid, "transition_cid")
        if self.revision == 0 and (self.root_cid is not None or self.transition_cid is not None):
            raise ValueError("revision-zero roots must not have a CID or transition")
        if self.revision > 0 and (self.root_cid is None or self.transition_cid is None):
            raise ValueError("non-zero roots require a root CID and transition CID")

    def to_dict(self) -> dict[str, Any]:
        return {"namespace": self.namespace, "root_cid": self.root_cid, "revision": self.revision,
                "transition_cid": self.transition_cid}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StateRootSnapshot":
        data = _closed_mapping(value, frozenset(("namespace", "root_cid", "revision", "transition_cid")), "snapshot")
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ArtifactWriteResult:
    """A verified artifact write with independent local and remote facts."""

    cid: str
    local_durable: bool
    provider_status: ProviderStatus
    replicated: bool
    reason_code: str

    def __post_init__(self) -> None:
        _validate_cid(self.cid, "cid")
        _require_bool(self.local_durable, "local_durable")
        _status(self.provider_status, ProviderStatus, "provider_status")
        _require_bool(self.replicated, "replicated")
        _validate_identifier(self.reason_code, "reason_code")
        if not self.local_durable:
            raise ValueError("an artifact result cannot claim replication without local durability")
        if self.replicated != (self.provider_status is ProviderStatus.AVAILABLE):
            raise ValueError("replicated must exactly match an available provider outcome")

    def to_dict(self) -> dict[str, Any]:
        return {"cid": self.cid, "local_durable": self.local_durable,
                "provider_status": self.provider_status.value, "replicated": self.replicated,
                "reason_code": self.reason_code}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ArtifactWriteResult":
        data = dict(_closed_mapping(value, frozenset(("cid", "local_durable", "provider_status", "replicated", "reason_code")), "artifact write result"))
        try:
            data["provider_status"] = ProviderStatus(data["provider_status"])
        except (TypeError, ValueError) as exc:
            raise ValueError("provider_status is unknown") from exc
        return cls(**data)


@dataclass(frozen=True, slots=True)
class StateRootCASResult:
    """Closed outcome of an attempted root compare-and-swap."""

    status: RootUpdateStatus
    before: StateRootSnapshot
    after: StateRootSnapshot
    transition_cid: str | None
    reason_code: str
    local_durable: bool
    replicated: bool

    def __post_init__(self) -> None:
        _status(self.status, RootUpdateStatus, "status")
        if not isinstance(self.before, StateRootSnapshot) or not isinstance(self.after, StateRootSnapshot):
            raise ValueError("before and after must be StateRootSnapshot values")
        if self.before.namespace != self.after.namespace:
            raise ValueError("before and after namespaces must agree")
        _optional_cid(self.transition_cid, "transition_cid")
        _validate_identifier(self.reason_code, "reason_code")
        _require_bool(self.local_durable, "local_durable")
        _require_bool(self.replicated, "replicated")
        if self.replicated and not self.local_durable:
            raise ValueError("replicated results must also be locally durable")
        if self.status is RootUpdateStatus.UPDATED:
            if not self.local_durable or self.after.revision != self.before.revision + 1:
                raise ValueError("updated results require a durable one-revision successor")
            if self.after.root_cid == self.before.root_cid or self.transition_cid != self.after.transition_cid:
                raise ValueError("updated results require a distinct matching transition")
        else:
            if self.after != self.before or self.transition_cid is not None:
                raise ValueError("non-updated results must not change the root")
            if self.replicated:
                raise ValueError("non-updated results cannot claim replication")

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status.value, "before": self.before.to_dict(), "after": self.after.to_dict(),
                "transition_cid": self.transition_cid, "reason_code": self.reason_code,
                "local_durable": self.local_durable, "replicated": self.replicated}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StateRootCASResult":
        data = dict(_closed_mapping(value, frozenset(("status", "before", "after", "transition_cid", "reason_code", "local_durable", "replicated")), "CAS result"))
        try:
            data["status"] = RootUpdateStatus(data["status"])
        except (TypeError, ValueError) as exc:
            raise ValueError("status is unknown") from exc
        data["before"] = StateRootSnapshot.from_dict(data["before"])
        data["after"] = StateRootSnapshot.from_dict(data["after"])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class StateRootRecoveryReport:
    """Pure recovery evidence; errors are closed code/message records."""

    verified_blocks: int
    reconstructed_roots: tuple[StateRootSnapshot, ...]
    ignored_idempotent_transitions: tuple[str, ...]
    errors: tuple[Mapping[str, str], ...]

    def __post_init__(self) -> None:
        _require_nonnegative_revision(self.verified_blocks, "verified_blocks")
        if not isinstance(self.reconstructed_roots, tuple) or not all(isinstance(item, StateRootSnapshot) for item in self.reconstructed_roots):
            raise ValueError("reconstructed_roots must be a tuple of snapshots")
        namespaces = [item.namespace for item in self.reconstructed_roots]
        if len(set(namespaces)) != len(namespaces):
            raise ValueError("reconstructed_roots may contain only one snapshot per namespace")
        if not isinstance(self.ignored_idempotent_transitions, tuple):
            raise ValueError("ignored_idempotent_transitions must be a tuple")
        for cid in self.ignored_idempotent_transitions:
            _validate_cid(cid, "ignored_idempotent_transition")
        if not isinstance(self.errors, tuple):
            raise ValueError("errors must be a tuple")
        normalized = []
        for error in self.errors:
            record = _closed_mapping(error, frozenset(("code", "message")), "recovery error")
            code, message = record["code"], record["message"]
            if not isinstance(code, str) or not _REASON_CODE.fullmatch(code) or not isinstance(message, str) or not message:
                raise ValueError("recovery errors require a normalized code and non-empty message")
            normalized.append(MappingProxyType({"code": code, "message": message}))
        object.__setattr__(self, "errors", tuple(normalized))

    def to_dict(self) -> dict[str, Any]:
        return {"verified_blocks": self.verified_blocks,
                "reconstructed_roots": [item.to_dict() for item in self.reconstructed_roots],
                "ignored_idempotent_transitions": list(self.ignored_idempotent_transitions),
                "errors": [dict(item) for item in self.errors]}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StateRootRecoveryReport":
        data = dict(_closed_mapping(value, frozenset(("verified_blocks", "reconstructed_roots", "ignored_idempotent_transitions", "errors")), "recovery report"))
        if not isinstance(data["reconstructed_roots"], list) or not isinstance(data["ignored_idempotent_transitions"], list) or not isinstance(data["errors"], list):
            raise ValueError("recovery report sequences must be lists")
        data["reconstructed_roots"] = tuple(StateRootSnapshot.from_dict(item) for item in data["reconstructed_roots"])
        data["ignored_idempotent_transitions"] = tuple(data["ignored_idempotent_transitions"])
        data["errors"] = tuple(data["errors"])
        return cls(**data)


class DurableStateRoots(Protocol):
    """Storage-facing protocol; implementations own all I/O and publication."""

    def put_verified(self, payload: Mapping[str, Any], *, expected_cid: str, replicate: bool = True) -> ArtifactWriteResult: ...
    def get_verified(self, cid: str) -> Mapping[str, Any]: ...
    def current_root(self, namespace: str) -> StateRootSnapshot: ...
    def compare_and_swap_root(self, namespace: str, *, expected_revision: int, expected_root_cid: str | None, new_root_cid: str, operation_id: str) -> StateRootCASResult: ...
    def recover_roots(self) -> StateRootRecoveryReport: ...


__all__ = ["ArtifactWriteResult", "DurableStateRoots", "ProviderStatus", "RootUpdateStatus",
           "StateRootCASResult", "StateRootRecoveryReport", "StateRootSnapshot"]
