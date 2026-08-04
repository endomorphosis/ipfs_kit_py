"""Backend-scoped bucket catalog and policy contracts (KITA-010).

The records in this module are declarations, not storage operations.  They
make a bucket's namespace, lifecycle, policy, and placement evidence explicit
before an adapter can create or mutate a bucket.  In particular, a bare bucket
name is never an identity: ``logs`` on two backends produces two distinct
``BucketIdentity`` records.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Final, TypeVar

from ipfs_kit_py.core.operation_contracts import (
    CanonicalContract,
    ForgedIdentityError,
    InconsistentStateError,
    OperationContractBoundsError,
    OperationContractError,
    canonical_json_bytes,
)

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

BUCKET_CONTRACTS_NAMESPACE: Final[str] = "ipfs_kit_py/core/buckets/contracts"
BUCKET_IDENTITY_SCHEMA: Final[str] = f"{BUCKET_CONTRACTS_NAMESPACE}/bucket-identity@1"
BUCKET_POLICY_SCHEMA: Final[str] = f"{BUCKET_CONTRACTS_NAMESPACE}/bucket-policy@1"
BACKEND_CAPABILITY_SCHEMA: Final[str] = f"{BUCKET_CONTRACTS_NAMESPACE}/backend-capability@1"
BUCKET_REPLICA_SCHEMA: Final[str] = f"{BUCKET_CONTRACTS_NAMESPACE}/bucket-replica@1"
BUCKET_MANIFEST_SCHEMA: Final[str] = f"{BUCKET_CONTRACTS_NAMESPACE}/bucket-manifest@1"
BUCKET_CATALOG_SCHEMA: Final[str] = f"{BUCKET_CONTRACTS_NAMESPACE}/bucket-catalog@1"

# Public interface aliases named in the runtime-readiness plan.
BucketIdentity_V1: Final[str] = BUCKET_IDENTITY_SCHEMA
BucketCatalog_V1: Final[str] = BUCKET_CATALOG_SCHEMA
BucketPolicy_V1: Final[str] = BUCKET_POLICY_SCHEMA
BucketManifest_V1: Final[str] = BUCKET_MANIFEST_SCHEMA

MAX_IDENTIFIER_BYTES: Final[int] = 512
MAX_BUCKET_NAME_BYTES: Final[int] = 63
MAX_ALIAS_COUNT: Final[int] = 128
MAX_CATALOG_ENTRIES: Final[int] = 4096
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1
_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@+\-]{0,511}$")
_BUCKET_NAME_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
TEnum = TypeVar("TEnum", bound=Enum)


class BucketContractError(OperationContractError):
    """Base error for invalid bucket contract records."""


class BucketIdentityError(BucketContractError):
    """A backend-scoped bucket identity or alias is invalid."""


class BucketPolicyError(BucketContractError):
    """A bucket policy contains contradictory requirements."""


class BackendCapabilityInsufficientError(BucketContractError):
    """The declared backend cannot supply a bucket policy."""


class BucketCatalogError(BucketContractError):
    """A catalog has duplicate or ambiguous backend-scoped names."""


class BucketLifecycleState(str, Enum):
    """Closed lifecycle vocabulary for a bucket declaration."""

    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETING = "deleting"
    TOMBSTONED = "tombstoned"
    DELETED = "deleted"
    FAILED = "failed"


class PolicyEnforcementState(str, Enum):
    """Whether a record is policy configuration or observed enforcement.

    ``BucketPolicy`` and ``BucketManifest`` in this module only carry
    configuration.  An adapter must emit separate operation evidence before it
    may claim enforcement; consequently passing ``ENFORCED`` here is rejected.
    """

    CONFIGURED = "configured"
    ENFORCED = "enforced"


class RetentionMode(str, Enum):
    NONE = "none"
    GOVERNANCE = "governance"
    COMPLIANCE = "compliance"


class EncryptionMode(str, Enum):
    NONE = "none"
    SERVER_MANAGED = "server_managed"
    CUSTOMER_MANAGED = "customer_managed"


class StorageTier(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"


class TransferFormat(str, Enum):
    CAR = "car"
    DAG_JSON = "dag_json"


class QueryMode(str, Enum):
    DISABLED = "disabled"
    METADATA = "metadata"
    CONTENT = "content"


class BucketReplicaRole(str, Enum):
    """The one primary and any additional replicas of a bucket.

    A ``VERIFIED_REPLICA`` is specifically a non-primary placement with state
    ``VERIFIED`` plus durable storage and integrity verification.  The primary
    never contributes to ``verified_replica_count``.
    """

    PRIMARY = "primary"
    REPLICA = "replica"


class BucketReplicaState(str, Enum):
    PENDING = "pending"
    COPYING = "copying"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    FAILED = "failed"
    REMOVING = "removing"
    REMOVED = "removed"


VERIFIED_REPLICA_STATES: Final[frozenset[BucketReplicaState]] = frozenset({BucketReplicaState.VERIFIED})

_BUCKET_LIFECYCLE_TRANSITIONS: Final[dict[BucketLifecycleState, frozenset[BucketLifecycleState]]] = {
    BucketLifecycleState.PROVISIONING: frozenset({BucketLifecycleState.ACTIVE, BucketLifecycleState.FAILED, BucketLifecycleState.DELETING}),
    BucketLifecycleState.ACTIVE: frozenset({BucketLifecycleState.SUSPENDED, BucketLifecycleState.DELETING, BucketLifecycleState.FAILED}),
    BucketLifecycleState.SUSPENDED: frozenset({BucketLifecycleState.ACTIVE, BucketLifecycleState.DELETING, BucketLifecycleState.FAILED}),
    BucketLifecycleState.DELETING: frozenset({BucketLifecycleState.TOMBSTONED, BucketLifecycleState.FAILED}),
    BucketLifecycleState.TOMBSTONED: frozenset({BucketLifecycleState.DELETED}),
    BucketLifecycleState.DELETED: frozenset(),
    BucketLifecycleState.FAILED: frozenset({BucketLifecycleState.PROVISIONING, BucketLifecycleState.DELETING}),
}

_REPLICA_TRANSITIONS: Final[dict[BucketReplicaState, frozenset[BucketReplicaState]]] = {
    BucketReplicaState.PENDING: frozenset({BucketReplicaState.COPYING, BucketReplicaState.FAILED, BucketReplicaState.REMOVING}),
    BucketReplicaState.COPYING: frozenset({BucketReplicaState.VERIFYING, BucketReplicaState.FAILED, BucketReplicaState.REMOVING}),
    BucketReplicaState.VERIFYING: frozenset({BucketReplicaState.VERIFIED, BucketReplicaState.FAILED, BucketReplicaState.REMOVING}),
    BucketReplicaState.VERIFIED: frozenset({BucketReplicaState.FAILED, BucketReplicaState.REMOVING}),
    BucketReplicaState.FAILED: frozenset({BucketReplicaState.PENDING, BucketReplicaState.REMOVING}),
    BucketReplicaState.REMOVING: frozenset({BucketReplicaState.REMOVED, BucketReplicaState.FAILED}),
    BucketReplicaState.REMOVED: frozenset(),
}


def _enum(value: Any, enum: type[TEnum], field_name: str) -> TEnum:
    try:
        return value if isinstance(value, enum) else enum(value)  # type: ignore[call-arg]
    except (TypeError, ValueError) as exc:
        raise BucketContractError(f"{field_name} has an unsupported value") from exc


def _identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise BucketContractError(f"{field_name} must be an identifier string")
    value = value.strip()
    if not value or len(value.encode("utf-8")) > MAX_IDENTIFIER_BYTES or not _IDENTIFIER_RE.fullmatch(value):
        raise BucketContractError(f"{field_name} must be a compact non-empty identifier")
    return value


def _bucket_name(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise BucketIdentityError(f"{field_name} must be a bucket-name string")
    if value != unicodedata.normalize("NFC", value):
        raise BucketIdentityError(f"{field_name} must be Unicode NFC")
    if value != value.lower() or len(value.encode("utf-8")) > MAX_BUCKET_NAME_BYTES or not _BUCKET_NAME_RE.fullmatch(value):
        raise BucketIdentityError(f"{field_name} must be lowercase DNS-style bucket name")
    return value


def _integer(value: Any, field_name: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BucketContractError(f"{field_name} must be an integer")
    if value < (0 if allow_zero else 1) or value > MAX_SAFE_INTEGER:
        raise OperationContractBoundsError(f"{field_name} is outside the supported bound")
    return value


def _bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise BucketContractError(f"{field_name} must be a boolean")
    return value


def _closed_values(values: Any, enum: type[TEnum], field_name: str) -> tuple[TEnum, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence) or isinstance(values, (bytes, bytearray)):
        raise BucketContractError(f"{field_name} must be a sequence")
    result = tuple(_enum(value, enum, field_name) for value in values)
    if not result:
        raise BucketContractError(f"{field_name} must not be empty")
    if len(set(result)) != len(result):
        raise BucketContractError(f"{field_name} must not contain duplicates")
    return tuple(sorted(result, key=lambda item: item.value))


def _decode(payload: Mapping[str, Any], schema: str, fields: tuple[str, ...], artifact_name: str) -> dict[str, Any]:
    """Strictly decode a wire record and reject unknown/unsafe material."""

    if not isinstance(payload, Mapping):
        raise BucketContractError(f"{artifact_name} payload must be an object")
    # This invokes the shared secret/body and reference-cycle guards before
    # accessing individual fields.
    canonical_json_bytes(payload)
    unknown = set(payload).difference(set(fields) | {"schema", "contract_version", "content_id"})
    if unknown:
        raise BucketContractError(f"{artifact_name} contains unsupported fields")
    if payload.get("schema") not in (None, "", schema):
        raise BucketContractError(f"unsupported {artifact_name} schema; use {schema}")
    if payload.get("contract_version") not in (None, CONTRACT_VERSION):
        raise BucketContractError(f"unsupported {artifact_name} contract version")
    missing = [field for field in fields if field not in payload]
    if missing:
        raise BucketContractError(f"{artifact_name} is missing required fields: {', '.join(missing)}")
    return {field: payload[field] for field in fields}


def _verify_identity(payload: Mapping[str, Any], record: CanonicalContract) -> None:
    supplied = payload.get("content_id")
    if supplied is None:
        return
    if not isinstance(supplied, str) or not supplied or supplied != record.content_id:
        raise ForgedIdentityError("content_id does not match the canonical preimage")


def is_legal_bucket_transition(previous: BucketLifecycleState, following: BucketLifecycleState) -> bool:
    previous = _enum(previous, BucketLifecycleState, "previous")
    following = _enum(following, BucketLifecycleState, "following")
    return previous is following or following in _BUCKET_LIFECYCLE_TRANSITIONS[previous]


def assert_legal_bucket_transition(previous: BucketLifecycleState, following: BucketLifecycleState) -> None:
    if not is_legal_bucket_transition(previous, following):
        raise InconsistentStateError(f"illegal bucket transition: {previous.value} -> {following.value}")


def is_legal_replica_transition(previous: BucketReplicaState, following: BucketReplicaState) -> bool:
    previous = _enum(previous, BucketReplicaState, "previous")
    following = _enum(following, BucketReplicaState, "following")
    return previous is following or following in _REPLICA_TRANSITIONS[previous]


def assert_legal_replica_transition(previous: BucketReplicaState, following: BucketReplicaState) -> None:
    if not is_legal_replica_transition(previous, following):
        raise InconsistentStateError(f"illegal bucket replica transition: {previous.value} -> {following.value}")


@dataclass(frozen=True)
class BucketIdentity(CanonicalContract):
    """One canonical bucket name plus aliases in exactly one backend scope."""

    SCHEMA: ClassVar[str] = BUCKET_IDENTITY_SCHEMA

    backend_id: str
    name: str
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend_id", _identifier(self.backend_id, "backend_id"))
        object.__setattr__(self, "name", _bucket_name(self.name, "name"))
        if isinstance(self.aliases, str) or not isinstance(self.aliases, Sequence) or isinstance(self.aliases, (bytes, bytearray)):
            raise BucketIdentityError("aliases must be a sequence of bucket names")
        if len(self.aliases) > MAX_ALIAS_COUNT:
            raise OperationContractBoundsError("aliases exceeds its supported bound")
        aliases = tuple(_bucket_name(value, "aliases") for value in self.aliases)
        if self.name in aliases or len(set(aliases)) != len(aliases):
            raise BucketIdentityError("aliases must be distinct and exclude the canonical name")
        object.__setattr__(self, "aliases", tuple(sorted(aliases)))

    @property
    def canonical_name(self) -> str:
        return self.name

    @property
    def backend_scoped_name(self) -> str:
        """Stable human-readable identity; backend is deliberately included."""

        return f"{self.backend_id}/{self.name}"

    @property
    def catalog_key(self) -> str:
        return self.backend_scoped_name

    @property
    def bucket_key(self) -> str:
        return self.backend_scoped_name

    def matches_name(self, candidate: str) -> bool:
        candidate = _bucket_name(candidate, "candidate")
        return candidate == self.name or candidate in self.aliases

    def _payload(self) -> dict[str, Any]:
        return {"backend_id": self.backend_id, "name": self.name, "aliases": self.aliases}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BucketIdentity":
        raw = _decode(payload, cls.SCHEMA, ("backend_id", "name", "aliases"), "bucket identity")
        record = cls(**raw)
        _verify_identity(payload, record)
        return record


@dataclass(frozen=True)
class BucketPolicy(CanonicalContract):
    """Finite, versioned quota, retention, encryption, tier, and access policy.

    ``replica_count`` is the total intended placement count, including the one
    primary.  ``minimum_verified_replicas`` counts only non-primary verified
    replicas, so it can never exceed ``replica_count - 1``.
    """

    SCHEMA: ClassVar[str] = BUCKET_POLICY_SCHEMA

    policy_id: str
    quota_bytes: int = 1 << 30
    quota_objects: int = 100_000
    retention_days: int = 0
    retention_mode: RetentionMode = RetentionMode.NONE
    encryption: EncryptionMode = EncryptionMode.SERVER_MANAGED
    tier: StorageTier = StorageTier.HOT
    replica_count: int = 1
    minimum_verified_replicas: int = 0
    import_formats: tuple[TransferFormat, ...] = (TransferFormat.CAR,)
    export_formats: tuple[TransferFormat, ...] = (TransferFormat.CAR,)
    query_mode: QueryMode = QueryMode.METADATA
    query_indexing: bool = False
    enforcement_state: PolicyEnforcementState = PolicyEnforcementState.CONFIGURED

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _identifier(self.policy_id, "policy_id"))
        object.__setattr__(self, "quota_bytes", _integer(self.quota_bytes, "quota_bytes"))
        object.__setattr__(self, "quota_objects", _integer(self.quota_objects, "quota_objects"))
        object.__setattr__(self, "retention_days", _integer(self.retention_days, "retention_days", allow_zero=True))
        object.__setattr__(self, "retention_mode", _enum(self.retention_mode, RetentionMode, "retention_mode"))
        object.__setattr__(self, "encryption", _enum(self.encryption, EncryptionMode, "encryption"))
        object.__setattr__(self, "tier", _enum(self.tier, StorageTier, "tier"))
        object.__setattr__(self, "replica_count", _integer(self.replica_count, "replica_count"))
        object.__setattr__(self, "minimum_verified_replicas", _integer(self.minimum_verified_replicas, "minimum_verified_replicas", allow_zero=True))
        object.__setattr__(self, "import_formats", _closed_values(self.import_formats, TransferFormat, "import_formats"))
        object.__setattr__(self, "export_formats", _closed_values(self.export_formats, TransferFormat, "export_formats"))
        object.__setattr__(self, "query_mode", _enum(self.query_mode, QueryMode, "query_mode"))
        object.__setattr__(self, "query_indexing", _bool(self.query_indexing, "query_indexing"))
        object.__setattr__(self, "enforcement_state", _enum(self.enforcement_state, PolicyEnforcementState, "enforcement_state"))
        if self.retention_mode is RetentionMode.NONE and self.retention_days != 0:
            raise BucketPolicyError("retention_days must be zero when retention_mode is none")
        if self.retention_mode is not RetentionMode.NONE and self.retention_days == 0:
            raise BucketPolicyError("retention_days must be positive when retention is enabled")
        if self.retention_mode is RetentionMode.COMPLIANCE and self.encryption is EncryptionMode.NONE:
            raise BucketPolicyError("compliance retention requires encryption")
        if self.minimum_verified_replicas > self.replica_count - 1:
            raise BucketPolicyError("minimum_verified_replicas cannot exceed non-primary placement count")
        if self.query_mode is QueryMode.DISABLED and self.query_indexing:
            raise BucketPolicyError("disabled query mode cannot enable query indexing")
        if self.query_mode is QueryMode.CONTENT and not self.query_indexing:
            raise BucketPolicyError("content query mode requires query indexing")
        if self.enforcement_state is not PolicyEnforcementState.CONFIGURED:
            raise InconsistentStateError("a configured bucket policy cannot claim enforced state")

    @property
    def desired_replicas(self) -> int:
        return self.replica_count

    def _payload(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "quota_bytes": self.quota_bytes,
            "quota_objects": self.quota_objects,
            "retention_days": self.retention_days,
            "retention_mode": self.retention_mode,
            "encryption": self.encryption,
            "tier": self.tier,
            "replica_count": self.replica_count,
            "minimum_verified_replicas": self.minimum_verified_replicas,
            "import_formats": self.import_formats,
            "export_formats": self.export_formats,
            "query_mode": self.query_mode,
            "query_indexing": self.query_indexing,
            "enforcement_state": self.enforcement_state,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BucketPolicy":
        raw = _decode(
            payload,
            cls.SCHEMA,
            (
                "policy_id",
                "quota_bytes",
                "quota_objects",
                "retention_days",
                "retention_mode",
                "encryption",
                "tier",
                "replica_count",
                "minimum_verified_replicas",
                "import_formats",
                "export_formats",
                "query_mode",
                "query_indexing",
                "enforcement_state",
            ),
            "bucket policy",
        )
        record = cls(**raw)
        _verify_identity(payload, record)
        return record


@dataclass(frozen=True)
class BackendCapability(CanonicalContract):
    """Bounded capability declaration used to check policy sufficiency."""

    SCHEMA: ClassVar[str] = BACKEND_CAPABILITY_SCHEMA

    backend_id: str
    max_bucket_bytes: int
    max_bucket_objects: int
    supported_encryption: tuple[EncryptionMode, ...] = tuple(EncryptionMode)
    supported_tiers: tuple[StorageTier, ...] = tuple(StorageTier)
    supported_import_formats: tuple[TransferFormat, ...] = tuple(TransferFormat)
    supported_export_formats: tuple[TransferFormat, ...] = tuple(TransferFormat)
    supported_query_modes: tuple[QueryMode, ...] = tuple(QueryMode)
    supports_retention: bool = True
    supports_verified_replicas: bool = True
    writable: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend_id", _identifier(self.backend_id, "backend_id"))
        object.__setattr__(self, "max_bucket_bytes", _integer(self.max_bucket_bytes, "max_bucket_bytes"))
        object.__setattr__(self, "max_bucket_objects", _integer(self.max_bucket_objects, "max_bucket_objects"))
        object.__setattr__(self, "supported_encryption", _closed_values(self.supported_encryption, EncryptionMode, "supported_encryption"))
        object.__setattr__(self, "supported_tiers", _closed_values(self.supported_tiers, StorageTier, "supported_tiers"))
        object.__setattr__(self, "supported_import_formats", _closed_values(self.supported_import_formats, TransferFormat, "supported_import_formats"))
        object.__setattr__(self, "supported_export_formats", _closed_values(self.supported_export_formats, TransferFormat, "supported_export_formats"))
        object.__setattr__(self, "supported_query_modes", _closed_values(self.supported_query_modes, QueryMode, "supported_query_modes"))
        for field_name in ("supports_retention", "supports_verified_replicas", "writable"):
            object.__setattr__(self, field_name, _bool(getattr(self, field_name), field_name))

    def supports(self, policy: BucketPolicy) -> bool:
        if not isinstance(policy, BucketPolicy):
            raise BucketContractError("policy must be a BucketPolicy")
        return (
            self.writable
            and policy.quota_bytes <= self.max_bucket_bytes
            and policy.quota_objects <= self.max_bucket_objects
            and policy.encryption in self.supported_encryption
            and policy.tier in self.supported_tiers
            and set(policy.import_formats).issubset(self.supported_import_formats)
            and set(policy.export_formats).issubset(self.supported_export_formats)
            and policy.query_mode in self.supported_query_modes
            and (policy.retention_mode is RetentionMode.NONE or self.supports_retention)
            and (policy.minimum_verified_replicas == 0 or self.supports_verified_replicas)
        )

    def assert_supports(self, policy: BucketPolicy) -> None:
        if not self.supports(policy):
            raise BackendCapabilityInsufficientError(
                f"backend {self.backend_id!r} cannot satisfy bucket policy {policy.policy_id!r}"
            )

    def _payload(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "max_bucket_bytes": self.max_bucket_bytes,
            "max_bucket_objects": self.max_bucket_objects,
            "supported_encryption": self.supported_encryption,
            "supported_tiers": self.supported_tiers,
            "supported_import_formats": self.supported_import_formats,
            "supported_export_formats": self.supported_export_formats,
            "supported_query_modes": self.supported_query_modes,
            "supports_retention": self.supports_retention,
            "supports_verified_replicas": self.supports_verified_replicas,
            "writable": self.writable,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BackendCapability":
        raw = _decode(
            payload,
            cls.SCHEMA,
            (
                "backend_id",
                "max_bucket_bytes",
                "max_bucket_objects",
                "supported_encryption",
                "supported_tiers",
                "supported_import_formats",
                "supported_export_formats",
                "supported_query_modes",
                "supports_retention",
                "supports_verified_replicas",
                "writable",
            ),
            "backend capability",
        )
        record = cls(**raw)
        _verify_identity(payload, record)
        return record


def assert_backend_supports_policy(capability: BackendCapability, policy: BucketPolicy) -> None:
    """Raise unless a specific backend capability suffices for ``policy``."""

    if not isinstance(capability, BackendCapability):
        raise BucketContractError("capability must be a BackendCapability")
    capability.assert_supports(policy)


@dataclass(frozen=True)
class BucketReplica(CanonicalContract):
    """One primary or replica placement and its durable verification evidence."""

    SCHEMA: ClassVar[str] = BUCKET_REPLICA_SCHEMA

    backend_id: str
    role: BucketReplicaRole
    state: BucketReplicaState = BucketReplicaState.PENDING
    durable: bool = False
    integrity_verified: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend_id", _identifier(self.backend_id, "backend_id"))
        object.__setattr__(self, "role", _enum(self.role, BucketReplicaRole, "role"))
        object.__setattr__(self, "state", _enum(self.state, BucketReplicaState, "state"))
        object.__setattr__(self, "durable", _bool(self.durable, "durable"))
        object.__setattr__(self, "integrity_verified", _bool(self.integrity_verified, "integrity_verified"))
        if self.state is BucketReplicaState.VERIFIED and not (self.durable and self.integrity_verified):
            raise InconsistentStateError("a verified replica requires durable storage and integrity verification")
        if self.state is not BucketReplicaState.VERIFIED and self.integrity_verified:
            raise InconsistentStateError("integrity_verified is valid only for a verified replica")

    @property
    def is_verified_replica(self) -> bool:
        return (
            self.role is BucketReplicaRole.REPLICA
            and self.state in VERIFIED_REPLICA_STATES
            and self.durable
            and self.integrity_verified
        )

    def _payload(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "role": self.role,
            "state": self.state,
            "durable": self.durable,
            "integrity_verified": self.integrity_verified,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BucketReplica":
        raw = _decode(
            payload,
            cls.SCHEMA,
            ("backend_id", "role", "state", "durable", "integrity_verified"),
            "bucket replica",
        )
        record = cls(**raw)
        _verify_identity(payload, record)
        return record


@dataclass(frozen=True)
class BucketManifest(CanonicalContract):
    """One bucket's identity, configured policy, placement, and capability."""

    SCHEMA: ClassVar[str] = BUCKET_MANIFEST_SCHEMA

    identity_record: BucketIdentity
    policy: BucketPolicy
    backend_capability: BackendCapability
    replicas: tuple[BucketReplica, ...]
    lifecycle_state: BucketLifecycleState = BucketLifecycleState.PROVISIONING
    policy_enforcement_state: PolicyEnforcementState = PolicyEnforcementState.CONFIGURED

    def __post_init__(self) -> None:
        if not isinstance(self.identity_record, BucketIdentity):
            raise BucketContractError("identity_record must be a BucketIdentity")
        if not isinstance(self.policy, BucketPolicy):
            raise BucketContractError("policy must be a BucketPolicy")
        if not isinstance(self.backend_capability, BackendCapability):
            raise BucketContractError("backend_capability must be a BackendCapability")
        if self.identity_record.backend_id != self.backend_capability.backend_id:
            raise BucketCatalogError("bucket identity and capability must use the same backend_id")
        self.backend_capability.assert_supports(self.policy)
        if isinstance(self.replicas, str) or not isinstance(self.replicas, Sequence) or isinstance(self.replicas, (bytes, bytearray)):
            raise BucketContractError("replicas must be a sequence of BucketReplica records")
        if len(self.replicas) != self.policy.replica_count:
            raise BucketPolicyError("replicas must contain exactly policy.replica_count placements")
        if not all(isinstance(replica, BucketReplica) for replica in self.replicas):
            raise BucketContractError("replicas must contain BucketReplica records")
        replicas = tuple(sorted(self.replicas, key=lambda item: (item.role.value, item.backend_id)))
        if len({replica.backend_id for replica in replicas}) != len(replicas):
            raise BucketCatalogError("a bucket cannot place two roles on one backend")
        primary = [replica for replica in replicas if replica.role is BucketReplicaRole.PRIMARY]
        if len(primary) != 1:
            raise InconsistentStateError("a bucket manifest requires exactly one primary")
        object.__setattr__(self, "replicas", replicas)
        object.__setattr__(self, "lifecycle_state", _enum(self.lifecycle_state, BucketLifecycleState, "lifecycle_state"))
        object.__setattr__(self, "policy_enforcement_state", _enum(self.policy_enforcement_state, PolicyEnforcementState, "policy_enforcement_state"))
        if self.policy_enforcement_state is not PolicyEnforcementState.CONFIGURED:
            raise InconsistentStateError("a configured policy cannot claim enforced state")
        if self.lifecycle_state is BucketLifecycleState.ACTIVE and self.verified_replica_count < self.policy.minimum_verified_replicas:
            raise InconsistentStateError("active bucket lacks its required verified replicas")

    @property
    def identity(self) -> BucketIdentity:
        return self.identity_record

    @property
    def verified_replica_count(self) -> int:
        return sum(replica.is_verified_replica for replica in self.replicas)

    @property
    def primary(self) -> BucketReplica:
        return next(replica for replica in self.replicas if replica.role is BucketReplicaRole.PRIMARY)

    def _payload(self) -> dict[str, Any]:
        return {
            "identity_record": self.identity_record,
            "policy": self.policy,
            "backend_capability": self.backend_capability,
            "replicas": self.replicas,
            "lifecycle_state": self.lifecycle_state,
            "policy_enforcement_state": self.policy_enforcement_state,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BucketManifest":
        raw = _decode(
            payload,
            cls.SCHEMA,
            (
                "identity_record",
                "policy",
                "backend_capability",
                "replicas",
                "lifecycle_state",
                "policy_enforcement_state",
            ),
            "bucket manifest",
        )
        try:
            raw["identity_record"] = BucketIdentity.from_dict(raw["identity_record"])
            raw["policy"] = BucketPolicy.from_dict(raw["policy"])
            raw["backend_capability"] = BackendCapability.from_dict(raw["backend_capability"])
            raw["replicas"] = tuple(BucketReplica.from_dict(item) for item in raw["replicas"])
        except (TypeError, AttributeError) as exc:
            raise BucketContractError("bucket manifest contains malformed nested records") from exc
        record = cls(**raw)
        _verify_identity(payload, record)
        return record


@dataclass(frozen=True)
class BucketCatalog(CanonicalContract):
    """Generation-bound catalog that resolves names only inside a backend scope."""

    SCHEMA: ClassVar[str] = BUCKET_CATALOG_SCHEMA

    catalog_id: str
    generation: int
    entries: tuple[BucketManifest, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "catalog_id", _identifier(self.catalog_id, "catalog_id"))
        object.__setattr__(self, "generation", _integer(self.generation, "generation"))
        if isinstance(self.entries, str) or not isinstance(self.entries, Sequence) or isinstance(self.entries, (bytes, bytearray)):
            raise BucketCatalogError("entries must be a sequence of BucketManifest records")
        if len(self.entries) > MAX_CATALOG_ENTRIES or not all(isinstance(entry, BucketManifest) for entry in self.entries):
            raise BucketCatalogError("entries must contain a bounded sequence of BucketManifest records")
        entries = tuple(sorted(self.entries, key=lambda entry: entry.identity.catalog_key))
        canonical_keys: set[tuple[str, str]] = set()
        occupied_names: set[tuple[str, str]] = set()
        for entry in entries:
            identity = entry.identity
            key = (identity.backend_id, identity.name)
            if key in canonical_keys:
                raise BucketCatalogError("catalog cannot contain duplicate backend-scoped canonical names")
            canonical_keys.add(key)
            for name in (identity.name, *identity.aliases):
                scoped_name = (identity.backend_id, name)
                if scoped_name in occupied_names:
                    raise BucketCatalogError("canonical names and aliases must not collide within a backend")
                occupied_names.add(scoped_name)
        object.__setattr__(self, "entries", entries)

    @property
    def buckets(self) -> tuple[BucketManifest, ...]:
        return self.entries

    def resolve(self, backend_id: str, name_or_alias: str) -> BucketManifest:
        backend_id = _identifier(backend_id, "backend_id")
        name_or_alias = _bucket_name(name_or_alias, "name_or_alias")
        for entry in self.entries:
            if entry.identity.backend_id == backend_id and entry.identity.matches_name(name_or_alias):
                return entry
        raise KeyError(f"no bucket named {name_or_alias!r} exists on backend {backend_id!r}")

    def _payload(self) -> dict[str, Any]:
        return {"catalog_id": self.catalog_id, "generation": self.generation, "entries": self.entries}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BucketCatalog":
        raw = _decode(payload, cls.SCHEMA, ("catalog_id", "generation", "entries"), "bucket catalog")
        try:
            raw["entries"] = tuple(BucketManifest.from_dict(item) for item in raw["entries"])
        except (TypeError, AttributeError) as exc:
            raise BucketCatalogError("catalog contains malformed manifest records") from exc
        record = cls(**raw)
        _verify_identity(payload, record)
        return record


# Concise aliases for callers which use the generic replication terminology.
ReplicaRole = BucketReplicaRole
ReplicaState = BucketReplicaState
BucketCatalogEntry = BucketManifest

__all__ = [
    "BACKEND_CAPABILITY_SCHEMA",
    "BUCKET_CATALOG_SCHEMA",
    "BUCKET_CONTRACTS_NAMESPACE",
    "BUCKET_IDENTITY_SCHEMA",
    "BUCKET_MANIFEST_SCHEMA",
    "BUCKET_POLICY_SCHEMA",
    "BUCKET_REPLICA_SCHEMA",
    "BackendCapability",
    "BackendCapabilityInsufficientError",
    "BucketCatalog",
    "BucketCatalogEntry",
    "BucketCatalogError",
    "BucketCatalog_V1",
    "BucketContractError",
    "BucketIdentity",
    "BucketIdentityError",
    "BucketIdentity_V1",
    "BucketLifecycleState",
    "BucketManifest",
    "BucketManifest_V1",
    "BucketPolicy",
    "BucketPolicyError",
    "BucketPolicy_V1",
    "BucketReplica",
    "BucketReplicaRole",
    "BucketReplicaState",
    "CONTRACT_VERSION",
    "EncryptionMode",
    "MAX_BUCKET_NAME_BYTES",
    "PolicyEnforcementState",
    "QueryMode",
    "ReplicaRole",
    "ReplicaState",
    "RetentionMode",
    "SCHEMA_VERSION",
    "StorageTier",
    "TransferFormat",
    "VERIFIED_REPLICA_STATES",
    "assert_backend_supports_policy",
    "assert_legal_bucket_transition",
    "assert_legal_replica_transition",
    "is_legal_bucket_transition",
    "is_legal_replica_transition",
]
