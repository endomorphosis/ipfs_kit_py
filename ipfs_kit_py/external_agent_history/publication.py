"""Content-addressed Parquet/IPLD/CAR/IPFS history publication (EAAEF-095).

Committed events and snapshots are hashed in-process. Publication is optional;
unpublished artifacts remain content-addressed. Replication lag cannot grant
or revoke authority. No live IPFS daemon is required.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final


PUBLICATION_SCHEMA: Final[str] = (
    "ipfs_kit_py/external-agent-history-publication@1"
)
ARTIFACT_SCHEMA: Final[str] = (
    "ipfs_kit_py/external-agent-history-artifact@1"
)
MANIFEST_SCHEMA: Final[str] = (
    "ipfs_kit_py/external-agent-history-manifest@1"
)

ARTIFACT_KINDS: Final[frozenset[str]] = frozenset({"parquet", "ipld", "car", "ipfs"})

_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")

_HIDDEN_CHAIN_OF_THOUGHT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "chain_of_thought",
        "cot",
        "hidden_chain_of_thought",
        "hidden_cot",
        "hidden_reasoning",
        "thinking",
        "thinking_text",
    }
)
_PRIVATE_FIELD_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "cookie",
        "credential",
        "password",
        "private_key",
        "secret",
        "session_token",
        "transcript_body",
    }
)
_TRANSCRIPT_BODY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "body",
        "full_transcript",
        "prompt",
        "raw_transcript",
        "transcript",
        "transcript_body",
        "transcript_text",
    }
)


class HistoryPublicationError(ValueError):
    """Fail-closed history publication rejection."""


class HistoryPublicationPrivacyError(HistoryPublicationError):
    """Manifest carried secrets or transcript bodies."""


class HistoryLagAuthorityError(HistoryPublicationError):
    """Replication lag was used to grant or revoke authority."""


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_key(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_")


def _reject_forbidden_keys(value: Any, *, name: str) -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            normalized = _normalize_key(raw_key)
            if normalized in _HIDDEN_CHAIN_OF_THOUGHT_KEYS:
                raise HistoryPublicationPrivacyError(
                    f"{name} must not represent hidden chain-of-thought"
                )
            if normalized in _TRANSCRIPT_BODY_KEYS:
                raise HistoryPublicationPrivacyError(
                    f"{name} must not embed transcript bodies"
                )
            if any(
                normalized == marker
                or normalized.endswith("_" + marker)
                or marker in normalized
                for marker in _PRIVATE_FIELD_MARKERS
            ):
                raise HistoryPublicationPrivacyError(
                    f"{name} must not contain secrets or private material"
                )
            _reject_forbidden_keys(item, name=name)
        return
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray, memoryview)
    ):
        for item in value:
            _reject_forbidden_keys(item, name=name)


def _require_kind(kind: Any) -> str:
    text = str(kind or "").strip().lower()
    if text not in ARTIFACT_KINDS:
        raise HistoryPublicationError(f"unknown artifact kind {kind!r}")
    return text


def _require_bytes(payload: Any, *, field_name: str) -> bytes:
    if isinstance(payload, memoryview):
        payload = payload.tobytes()
    if isinstance(payload, bytearray):
        payload = bytes(payload)
    if not isinstance(payload, bytes):
        raise HistoryPublicationError(f"{field_name} must be bytes")
    return payload


@dataclass(frozen=True, slots=True)
class ContentAddressedArtifact:
    """In-memory content-addressed parquet/ipld/car/ipfs bytes."""

    kind: str
    digest: str
    payload: bytes
    published: bool = False
    size: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _require_kind(self.kind))
        payload = _require_bytes(self.payload, field_name="payload")
        object.__setattr__(self, "payload", payload)
        digest = str(self.digest or "").strip() or _sha256_bytes(payload)
        if not _SHA256_RE.fullmatch(digest):
            raise HistoryPublicationError("digest must be sha256:<64-hex>")
        expected = _sha256_bytes(payload)
        if digest != expected:
            raise HistoryPublicationError("artifact digest does not match payload")
        object.__setattr__(self, "digest", digest)
        object.__setattr__(self, "published", bool(self.published))
        object.__setattr__(self, "size", len(payload))

    def as_mapping(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "schema": ARTIFACT_SCHEMA,
                "kind": self.kind,
                "digest": self.digest,
                "size": self.size,
                "published": self.published,
            }
        )


@dataclass(frozen=True, slots=True)
class PrivacySafeManifest:
    """Privacy-safe publication manifest: identities and digests only."""

    epoch_id: str
    event_ids: tuple[str, ...]
    snapshot_digest: str
    artifacts: tuple[ContentAddressedArtifact, ...]
    published: bool
    content_digest: str

    def __post_init__(self) -> None:
        epoch_id = str(self.epoch_id or "").strip()
        if not epoch_id:
            raise HistoryPublicationError("epoch_id is required")
        object.__setattr__(self, "epoch_id", epoch_id)
        ids = tuple(str(item).strip() for item in self.event_ids if str(item).strip())
        object.__setattr__(self, "event_ids", ids)
        snap = str(self.snapshot_digest or "").strip()
        if snap and not _SHA256_RE.fullmatch(snap):
            raise HistoryPublicationError("snapshot_digest must be sha256:<64-hex>")
        object.__setattr__(self, "snapshot_digest", snap)
        artifacts = tuple(self.artifacts)
        for artifact in artifacts:
            if not isinstance(artifact, ContentAddressedArtifact):
                raise HistoryPublicationError("artifacts must be ContentAddressedArtifact")
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "published", bool(self.published))
        digest = str(self.content_digest or "").strip()
        if not _SHA256_RE.fullmatch(digest):
            raise HistoryPublicationError("content_digest must be sha256:<64-hex>")
        object.__setattr__(self, "content_digest", digest)

    def as_mapping(self) -> Mapping[str, Any]:
        payload = {
            "schema": MANIFEST_SCHEMA,
            "publication_schema": PUBLICATION_SCHEMA,
            "epoch_id": self.epoch_id,
            "event_ids": list(self.event_ids),
            "snapshot_digest": self.snapshot_digest,
            "artifacts": [dict(item.as_mapping()) for item in self.artifacts],
            "published": self.published,
            "content_digest": self.content_digest,
            "grants_current_authority": False,
        }
        _reject_forbidden_keys(payload, name="publication manifest")
        return MappingProxyType(payload)


def content_address(kind: str, payload: bytes) -> ContentAddressedArtifact:
    """Content-address in-memory bytes. No daemon, no sockets."""

    data = _require_bytes(payload, field_name="payload")
    return ContentAddressedArtifact(
        kind=kind,
        digest=_sha256_bytes(data),
        payload=data,
        published=False,
    )


def address_parquet(payload: bytes) -> ContentAddressedArtifact:
    return content_address("parquet", payload)


def address_ipld(payload: Mapping[str, Any] | bytes) -> ContentAddressedArtifact:
    if isinstance(payload, (bytes, bytearray, memoryview)):
        data = _require_bytes(payload, field_name="payload")
    else:
        if not isinstance(payload, Mapping):
            raise HistoryPublicationError("ipld payload must be bytes or an object")
        _reject_forbidden_keys(payload, name="ipld payload")
        data = _canonical_json(dict(payload)).encode("utf-8")
    return content_address("ipld", data)


def address_car(payload: bytes) -> ContentAddressedArtifact:
    return content_address("car", payload)


def address_ipfs(payload: bytes) -> ContentAddressedArtifact:
    return content_address("ipfs", payload)


def build_manifest(
    *,
    epoch_id: str,
    event_ids: Sequence[str] = (),
    snapshot_digest: str = "",
    artifacts: Sequence[ContentAddressedArtifact] = (),
    published: bool = False,
    extra: Mapping[str, Any] | None = None,
) -> PrivacySafeManifest:
    if extra:
        _reject_forbidden_keys(extra, name="publication manifest")
    body = {
        "epoch_id": epoch_id,
        "event_ids": list(event_ids),
        "snapshot_digest": snapshot_digest,
        "artifacts": [dict(item.as_mapping()) for item in artifacts],
        "published": bool(published),
    }
    if extra:
        body["extra"] = dict(extra)
    _reject_forbidden_keys(body, name="publication manifest")
    return PrivacySafeManifest(
        epoch_id=epoch_id,
        event_ids=tuple(event_ids),
        snapshot_digest=snapshot_digest,
        artifacts=tuple(artifacts),
        published=bool(published),
        content_digest=_sha256_text(_canonical_json(body)),
    )


def publish_artifacts(
    artifacts: Sequence[ContentAddressedArtifact],
    *,
    epoch_id: str,
    event_ids: Sequence[str] = (),
    snapshot_digest: str = "",
    publish: bool = False,
) -> PrivacySafeManifest:
    """Optionally mark artifacts published. Unpublished remains content-addressed."""

    addressed = tuple(
        ContentAddressedArtifact(
            kind=item.kind,
            digest=item.digest,
            payload=item.payload,
            published=bool(publish),
        )
        for item in artifacts
    )
    if not addressed:
        raise HistoryPublicationError("artifacts are required")
    return build_manifest(
        epoch_id=epoch_id,
        event_ids=event_ids,
        snapshot_digest=snapshot_digest,
        artifacts=addressed,
        published=bool(publish),
    )


def authority_from_lag(lag_status: Any = None) -> bool:
    """Replication lag never grants or revokes authority."""

    if lag_status is None:
        raise HistoryLagAuthorityError("lag_status is required")
    if isinstance(lag_status, Mapping):
        _reject_forbidden_keys(lag_status, name="lag_status")
        if lag_status.get("grant_authority") or lag_status.get("revoke_authority"):
            raise HistoryLagAuthorityError(
                "replication lag cannot grant or revoke authority"
            )
    return False


__all__ = (
    "ARTIFACT_KINDS",
    "ARTIFACT_SCHEMA",
    "ContentAddressedArtifact",
    "HistoryLagAuthorityError",
    "HistoryPublicationError",
    "HistoryPublicationPrivacyError",
    "MANIFEST_SCHEMA",
    "PUBLICATION_SCHEMA",
    "PrivacySafeManifest",
    "address_car",
    "address_ipfs",
    "address_ipld",
    "address_parquet",
    "authority_from_lag",
    "build_manifest",
    "content_address",
    "publish_artifacts",
)
