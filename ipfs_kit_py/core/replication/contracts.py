"""Closed replica policy and lifecycle contracts (KITA-026).

These records are deliberately inert: they describe replication requirements,
inventory observations, and lifecycle evidence, but perform no storage or
network operation.  A caller must obtain a valid :class:`PlacementPlan` before
it attempts any copy.  In particular, queued or copied-but-unverified work is
never interchangeable with a durable, integrity-verified replica.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Final, TypeVar

from ipfs_kit_py.core.operation_contracts import (
    CanonicalContract,
    InconsistentStateError,
    OperationContractBoundsError,
    OperationContractError,
)

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

REPLICATION_CONTRACTS_NAMESPACE: Final[str] = "ipfs_kit_py/core/replication/contracts"
REPLICA_POLICY_SCHEMA: Final[str] = f"{REPLICATION_CONTRACTS_NAMESPACE}/replica-policy@1"
BACKEND_CAPABILITY_SCHEMA: Final[str] = f"{REPLICATION_CONTRACTS_NAMESPACE}/backend-capability@1"
BACKEND_INVENTORY_SCHEMA: Final[str] = f"{REPLICATION_CONTRACTS_NAMESPACE}/backend-inventory@1"
REPLICA_OBSERVATION_SCHEMA: Final[str] = f"{REPLICATION_CONTRACTS_NAMESPACE}/replica-observation@1"
PLACEMENT_INTENT_SCHEMA: Final[str] = f"{REPLICATION_CONTRACTS_NAMESPACE}/placement-intent@1"
PLACEMENT_PLAN_SCHEMA: Final[str] = f"{REPLICATION_CONTRACTS_NAMESPACE}/placement-plan@1"

# Public interface aliases named in the runtime-readiness plan.
ReplicaPolicy_V1: Final[str] = REPLICA_POLICY_SCHEMA
PlacementPlan_V1: Final[str] = PLACEMENT_PLAN_SCHEMA
ReplicaState_V1: Final[str] = f"{REPLICATION_CONTRACTS_NAMESPACE}/replica-state@1"

MAX_IDENTIFIER_BYTES: Final[int] = 512
MAX_REFERENCE_COUNT: Final[int] = 256
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1
_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@+\-]{0,511}$")
TEnum = TypeVar("TEnum", bound=Enum)


class ReplicaContractError(OperationContractError):
    """Base error for invalid replica-policy contracts."""


class ReplicaPolicyError(ReplicaContractError):
    """A replica policy has contradictory or unsafe requirements."""


class PlacementUnsatisfiableError(ReplicaContractError):
    """The exact inventory snapshot cannot satisfy a valid policy."""


class ReplicaState(str, Enum):
    """Closed state vocabulary for an individual replica.

    Only ``VERIFIED`` can count toward a desired replica count, and only when
    its observation additionally attests durable storage and integrity proof.
    """

    PLANNED = "planned"
    PENDING = "pending"
    QUEUED = "queued"
    COPYING = "copying"
    COPIED = "copied"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    STALE = "stale"
    FAILED = "failed"
    CORRUPT = "corrupt"
    REMOVING = "removing"
    REMOVED = "removed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


NON_DURABLE_REPLICA_STATES: Final[frozenset[ReplicaState]] = frozenset(
    {
        ReplicaState.PLANNED,
        ReplicaState.PENDING,
        ReplicaState.QUEUED,
        ReplicaState.COPYING,
        ReplicaState.COPIED,
        ReplicaState.VERIFYING,
        ReplicaState.STALE,
        ReplicaState.FAILED,
        ReplicaState.CORRUPT,
        ReplicaState.REMOVING,
        ReplicaState.REMOVED,
        ReplicaState.CANCELLED,
        ReplicaState.BLOCKED,
    }
)
VERIFIED_DURABLE_REPLICA_STATES: Final[frozenset[ReplicaState]] = frozenset(
    {ReplicaState.VERIFIED}
)

_REPLICA_TRANSITIONS: Final[dict[ReplicaState, frozenset[ReplicaState]]] = {
    ReplicaState.PLANNED: frozenset({ReplicaState.PENDING, ReplicaState.CANCELLED, ReplicaState.BLOCKED}),
    ReplicaState.PENDING: frozenset({ReplicaState.QUEUED, ReplicaState.COPYING, ReplicaState.CANCELLED, ReplicaState.BLOCKED, ReplicaState.FAILED}),
    ReplicaState.QUEUED: frozenset({ReplicaState.COPYING, ReplicaState.CANCELLED, ReplicaState.BLOCKED, ReplicaState.FAILED}),
    ReplicaState.COPYING: frozenset({ReplicaState.COPIED, ReplicaState.FAILED, ReplicaState.CANCELLED}),
    ReplicaState.COPIED: frozenset({ReplicaState.VERIFYING, ReplicaState.FAILED, ReplicaState.CORRUPT}),
    ReplicaState.VERIFYING: frozenset({ReplicaState.VERIFIED, ReplicaState.FAILED, ReplicaState.CORRUPT}),
    ReplicaState.VERIFIED: frozenset({ReplicaState.STALE, ReplicaState.CORRUPT, ReplicaState.REMOVING}),
    ReplicaState.STALE: frozenset({ReplicaState.COPYING, ReplicaState.REMOVING, ReplicaState.CORRUPT}),
    ReplicaState.FAILED: frozenset({ReplicaState.PENDING, ReplicaState.CANCELLED}),
    ReplicaState.CORRUPT: frozenset({ReplicaState.COPYING, ReplicaState.REMOVING}),
    ReplicaState.REMOVING: frozenset({ReplicaState.REMOVED, ReplicaState.FAILED}),
    ReplicaState.REMOVED: frozenset(),
    ReplicaState.CANCELLED: frozenset(),
    ReplicaState.BLOCKED: frozenset({ReplicaState.PENDING, ReplicaState.CANCELLED}),
}


class ConsistencyLevel(str, Enum):
    EVENTUAL = "eventual"
    READ_YOUR_WRITES = "read_your_writes"
    BOUNDED_STALENESS = "bounded_staleness"
    STRONG = "strong"


class EncryptionLevel(str, Enum):
    NONE = "none"
    AT_REST = "at_rest"
    CUSTOMER_MANAGED = "customer_managed"


class RetentionLevel(str, Enum):
    EPHEMERAL = "ephemeral"
    RETAINED = "retained"
    ARCHIVAL = "archival"


class CostTier(str, Enum):
    ECONOMY = "economy"
    STANDARD = "standard"
    PREMIUM = "premium"


_CONSISTENCY_ORDER: Final[tuple[ConsistencyLevel, ...]] = tuple(ConsistencyLevel)
_ENCRYPTION_ORDER: Final[tuple[EncryptionLevel, ...]] = tuple(EncryptionLevel)
_RETENTION_ORDER: Final[tuple[RetentionLevel, ...]] = tuple(RetentionLevel)
_COST_ORDER: Final[tuple[CostTier, ...]] = tuple(CostTier)


def _enum(value: Any, enum: type[TEnum], field_name: str) -> TEnum:
    try:
        return value if isinstance(value, enum) else enum(value)  # type: ignore[call-arg]
    except (TypeError, ValueError) as exc:
        raise ReplicaContractError(f"{field_name} has an unsupported value") from exc


def _identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ReplicaContractError(f"{field_name} must be an identifier string")
    value = value.strip()
    if not value or len(value.encode("utf-8")) > MAX_IDENTIFIER_BYTES or not _ID_RE.fullmatch(value):
        raise ReplicaContractError(f"{field_name} must be a compact non-empty identifier")
    return value


def _positive_int(value: Any, field_name: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReplicaContractError(f"{field_name} must be an integer")
    minimum = 0 if allow_zero else 1
    if not minimum <= value <= MAX_SAFE_INTEGER:
        raise OperationContractBoundsError(f"{field_name} is outside the supported bound")
    return value


def _bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ReplicaContractError(f"{field_name} must be a boolean")
    return value


def _identifiers(values: Any, field_name: str, *, preserve_order: bool = True) -> tuple[str, ...]:
    if values is None:
        raw: Sequence[Any] = ()
    elif isinstance(values, str) or not isinstance(values, Sequence) or isinstance(values, (bytes, bytearray)):
        raise ReplicaContractError(f"{field_name} must be a sequence of identifiers")
    else:
        raw = values
    if len(raw) > MAX_REFERENCE_COUNT:
        raise OperationContractBoundsError(f"{field_name} exceeds its reference bound")
    result = tuple(_identifier(item, field_name) for item in raw)
    if len(set(result)) != len(result):
        raise ReplicaPolicyError(f"{field_name} must not contain duplicates")
    return result if preserve_order else tuple(sorted(result))


def _at_least(actual: Enum, required: Enum, order: tuple[Enum, ...]) -> bool:
    return order.index(actual) >= order.index(required)


def _at_most(actual: Enum, limit: Enum, order: tuple[Enum, ...]) -> bool:
    return order.index(actual) <= order.index(limit)


def is_legal_replica_transition(previous: ReplicaState, following: ReplicaState) -> bool:
    """Whether a single replica lifecycle transition is admitted."""

    previous = _enum(previous, ReplicaState, "previous")
    following = _enum(following, ReplicaState, "following")
    return previous is following or following in _REPLICA_TRANSITIONS[previous]


def assert_legal_replica_transition(previous: ReplicaState, following: ReplicaState) -> None:
    if not is_legal_replica_transition(previous, following):
        raise InconsistentStateError(f"illegal replica transition: {previous.value} -> {following.value}")


@dataclass(frozen=True)
class ReplicaPolicy(CanonicalContract):
    """Validated redundancy, placement, and storage requirements.

    The cardinality ladder is intentionally strict:
    ``min_replicas <= desired_replicas <= max_replicas <= critical_replicas``.
    ``critical_replicas`` is the capacity that must be demonstrably eligible in
    an inventory before a planner may return any new copy intent.
    """

    SCHEMA: ClassVar[str] = REPLICA_POLICY_SCHEMA

    policy_id: str
    min_replicas: int
    desired_replicas: int
    max_replicas: int
    critical_replicas: int
    required_consistency: ConsistencyLevel = ConsistencyLevel.EVENTUAL
    required_encryption: EncryptionLevel = EncryptionLevel.NONE
    required_retention: RetentionLevel = RetentionLevel.RETAINED
    max_cost_tier: CostTier = CostTier.PREMIUM
    required_localities: tuple[str, ...] = ()
    preferred_backends: tuple[str, ...] = ()
    excluded_backends: tuple[str, ...] = ()
    allowed_backends: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _identifier(self.policy_id, "policy_id"))
        for name in ("min_replicas", "desired_replicas", "max_replicas", "critical_replicas"):
            object.__setattr__(self, name, _positive_int(getattr(self, name), name))
        if not self.min_replicas <= self.desired_replicas <= self.max_replicas <= self.critical_replicas:
            raise ReplicaPolicyError("replica cardinality must satisfy min <= desired <= max <= critical")
        object.__setattr__(self, "required_consistency", _enum(self.required_consistency, ConsistencyLevel, "required_consistency"))
        object.__setattr__(self, "required_encryption", _enum(self.required_encryption, EncryptionLevel, "required_encryption"))
        object.__setattr__(self, "required_retention", _enum(self.required_retention, RetentionLevel, "required_retention"))
        object.__setattr__(self, "max_cost_tier", _enum(self.max_cost_tier, CostTier, "max_cost_tier"))
        object.__setattr__(self, "required_localities", _identifiers(self.required_localities, "required_localities", preserve_order=False))
        object.__setattr__(self, "preferred_backends", _identifiers(self.preferred_backends, "preferred_backends"))
        object.__setattr__(self, "excluded_backends", _identifiers(self.excluded_backends, "excluded_backends", preserve_order=False))
        object.__setattr__(self, "allowed_backends", _identifiers(self.allowed_backends, "allowed_backends", preserve_order=False))
        declared = set(self.preferred_backends) | set(self.allowed_backends)
        overlap = declared & set(self.excluded_backends)
        if overlap:
            raise ReplicaPolicyError("preferred/allowed backends must be disjoint from excluded_backends")
        if self.allowed_backends and not set(self.preferred_backends).issubset(self.allowed_backends):
            raise ReplicaPolicyError("preferred_backends must be a subset of allowed_backends when allowed_backends is declared")

    @property
    def minimum_replicas(self) -> int:
        """Long-form compatibility spelling for ``min_replicas``."""

        return self.min_replicas

    @property
    def maximum_replicas(self) -> int:
        """Long-form compatibility spelling for ``max_replicas``."""

        return self.max_replicas

    def _payload(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "min_replicas": self.min_replicas,
            "desired_replicas": self.desired_replicas,
            "max_replicas": self.max_replicas,
            "critical_replicas": self.critical_replicas,
            "required_consistency": self.required_consistency,
            "required_encryption": self.required_encryption,
            "required_retention": self.required_retention,
            "max_cost_tier": self.max_cost_tier,
            "required_localities": self.required_localities,
            "preferred_backends": self.preferred_backends,
            "excluded_backends": self.excluded_backends,
            "allowed_backends": self.allowed_backends,
        }


@dataclass(frozen=True)
class BackendCapability(CanonicalContract):
    """A bounded observation of a backend's usable replication capability."""

    SCHEMA: ClassVar[str] = BACKEND_CAPABILITY_SCHEMA

    backend_id: str
    failure_domain: str
    available_bytes: int
    writable: bool = True
    available: bool = True
    durable: bool = True
    supports_integrity_verification: bool = True
    consistency: ConsistencyLevel = ConsistencyLevel.STRONG
    encryption: EncryptionLevel = EncryptionLevel.CUSTOMER_MANAGED
    retention: RetentionLevel = RetentionLevel.ARCHIVAL
    cost_tier: CostTier = CostTier.STANDARD
    localities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend_id", _identifier(self.backend_id, "backend_id"))
        object.__setattr__(self, "failure_domain", _identifier(self.failure_domain, "failure_domain"))
        object.__setattr__(self, "available_bytes", _positive_int(self.available_bytes, "available_bytes", allow_zero=True))
        for name in ("writable", "available", "durable", "supports_integrity_verification"):
            object.__setattr__(self, name, _bool(getattr(self, name), name))
        object.__setattr__(self, "consistency", _enum(self.consistency, ConsistencyLevel, "consistency"))
        object.__setattr__(self, "encryption", _enum(self.encryption, EncryptionLevel, "encryption"))
        object.__setattr__(self, "retention", _enum(self.retention, RetentionLevel, "retention"))
        object.__setattr__(self, "cost_tier", _enum(self.cost_tier, CostTier, "cost_tier"))
        object.__setattr__(self, "localities", _identifiers(self.localities, "localities", preserve_order=False))

    def supports(self, policy: ReplicaPolicy, content_size_bytes: int, *, require_writable: bool = True) -> bool:
        """Return whether this observation is an eligible destination.

        A false result is deliberately non-diagnostic so callers cannot turn a
        partially eligible inventory into a successful mutation.
        """

        if not isinstance(policy, ReplicaPolicy):
            raise ReplicaContractError("policy must be a ReplicaPolicy")
        content_size_bytes = _positive_int(content_size_bytes, "content_size_bytes")
        if require_writable and not self.writable:
            return False
        if not (self.available and self.durable and self.supports_integrity_verification):
            return False
        if self.available_bytes < content_size_bytes:
            return False
        if policy.excluded_backends and self.backend_id in policy.excluded_backends:
            return False
        if policy.allowed_backends and self.backend_id not in policy.allowed_backends:
            return False
        if policy.required_localities and not set(policy.required_localities).issubset(self.localities):
            return False
        return (
            _at_least(self.consistency, policy.required_consistency, _CONSISTENCY_ORDER)
            and _at_least(self.encryption, policy.required_encryption, _ENCRYPTION_ORDER)
            and _at_least(self.retention, policy.required_retention, _RETENTION_ORDER)
            and _at_most(self.cost_tier, policy.max_cost_tier, _COST_ORDER)
        )

    def _payload(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "failure_domain": self.failure_domain,
            "available_bytes": self.available_bytes,
            "writable": self.writable,
            "available": self.available,
            "durable": self.durable,
            "supports_integrity_verification": self.supports_integrity_verification,
            "consistency": self.consistency,
            "encryption": self.encryption,
            "retention": self.retention,
            "cost_tier": self.cost_tier,
            "localities": self.localities,
        }


@dataclass(frozen=True)
class BackendInventory(CanonicalContract):
    """Canonical, immutable backend inventory snapshot.

    Capabilities are sorted by backend identifier before identity calculation;
    the resulting ``content_id`` therefore identifies the exact snapshot and
    is independent of a provider's incidental listing order.
    """

    SCHEMA: ClassVar[str] = BACKEND_INVENTORY_SCHEMA

    snapshot_id: str
    capabilities: tuple[BackendCapability, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", _identifier(self.snapshot_id, "snapshot_id"))
        if not isinstance(self.capabilities, Sequence) or isinstance(self.capabilities, (str, bytes, bytearray)):
            raise ReplicaContractError("capabilities must be a sequence")
        if not self.capabilities or len(self.capabilities) > MAX_REFERENCE_COUNT:
            raise ReplicaContractError("capabilities must be a non-empty bounded sequence")
        if not all(isinstance(item, BackendCapability) for item in self.capabilities):
            raise ReplicaContractError("capabilities must contain BackendCapability records")
        capabilities = tuple(sorted(self.capabilities, key=lambda item: item.backend_id))
        if len({item.backend_id for item in capabilities}) != len(capabilities):
            raise ReplicaContractError("inventory cannot contain duplicate backend_id values")
        object.__setattr__(self, "capabilities", capabilities)

    @property
    def by_backend_id(self) -> dict[str, BackendCapability]:
        return {capability.backend_id: capability for capability in self.capabilities}

    def eligible_capabilities(self, policy: ReplicaPolicy, content_size_bytes: int) -> tuple[BackendCapability, ...]:
        return tuple(capability for capability in self.capabilities if capability.supports(policy, content_size_bytes))

    def _payload(self) -> dict[str, Any]:
        return {"snapshot_id": self.snapshot_id, "capabilities": self.capabilities}


@dataclass(frozen=True)
class ReplicaObservation(CanonicalContract):
    """Observed state and evidence for one content replica."""

    SCHEMA: ClassVar[str] = REPLICA_OBSERVATION_SCHEMA

    replica_id: str
    # ``CanonicalContract.content_id`` is the canonical CID of this record.
    # Keep the replicated object's identifier distinct from that identity.
    content_ref: str
    backend_id: str
    state: ReplicaState
    durable: bool = False
    integrity_verified: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "replica_id", _identifier(self.replica_id, "replica_id"))
        object.__setattr__(self, "content_ref", _identifier(self.content_ref, "content_ref"))
        object.__setattr__(self, "backend_id", _identifier(self.backend_id, "backend_id"))
        object.__setattr__(self, "state", _enum(self.state, ReplicaState, "state"))
        object.__setattr__(self, "durable", _bool(self.durable, "durable"))
        object.__setattr__(self, "integrity_verified", _bool(self.integrity_verified, "integrity_verified"))
        if self.state is ReplicaState.VERIFIED and not (self.durable and self.integrity_verified):
            raise InconsistentStateError("verified replica requires durable storage and integrity verification")
        if self.state is not ReplicaState.VERIFIED and self.integrity_verified:
            raise InconsistentStateError("integrity_verified is only valid for a verified replica")

    @property
    def counts_toward_desired(self) -> bool:
        return self.state in VERIFIED_DURABLE_REPLICA_STATES and self.durable and self.integrity_verified

    def _payload(self) -> dict[str, Any]:
        return {
            "replica_id": self.replica_id,
            "content_ref": self.content_ref,
            "backend_id": self.backend_id,
            "state": self.state,
            "durable": self.durable,
            "integrity_verified": self.integrity_verified,
        }


@dataclass(frozen=True)
class PlacementIntent(CanonicalContract):
    """A non-executing copy intent emitted only by a valid placement plan."""

    SCHEMA: ClassVar[str] = PLACEMENT_INTENT_SCHEMA

    backend_id: str
    failure_domain: str
    state: ReplicaState = ReplicaState.PLANNED

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend_id", _identifier(self.backend_id, "backend_id"))
        object.__setattr__(self, "failure_domain", _identifier(self.failure_domain, "failure_domain"))
        object.__setattr__(self, "state", _enum(self.state, ReplicaState, "state"))
        if self.state is not ReplicaState.PLANNED:
            raise InconsistentStateError("a placement intent must begin in planned state")

    def _payload(self) -> dict[str, Any]:
        return {"backend_id": self.backend_id, "failure_domain": self.failure_domain, "state": self.state}


@dataclass(frozen=True)
class PlacementPlan(CanonicalContract):
    """Deterministic, side-effect-free placement result bound to one snapshot."""

    SCHEMA: ClassVar[str] = PLACEMENT_PLAN_SCHEMA

    # ``CanonicalContract.content_id`` remains the canonical CID of the plan.
    content_ref: str
    content_size_bytes: int
    policy_content_id: str
    inventory_content_id: str
    desired_replicas: int
    retained_backend_ids: tuple[str, ...]
    retained_failure_domains: tuple[str, ...]
    intents: tuple[PlacementIntent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "content_ref", _identifier(self.content_ref, "content_ref"))
        object.__setattr__(self, "content_size_bytes", _positive_int(self.content_size_bytes, "content_size_bytes"))
        object.__setattr__(self, "policy_content_id", _identifier(self.policy_content_id, "policy_content_id"))
        object.__setattr__(self, "inventory_content_id", _identifier(self.inventory_content_id, "inventory_content_id"))
        object.__setattr__(self, "desired_replicas", _positive_int(self.desired_replicas, "desired_replicas"))
        object.__setattr__(self, "retained_backend_ids", _identifiers(self.retained_backend_ids, "retained_backend_ids", preserve_order=False))
        object.__setattr__(self, "retained_failure_domains", _identifiers(self.retained_failure_domains, "retained_failure_domains", preserve_order=False))
        if len(self.retained_backend_ids) != len(self.retained_failure_domains):
            raise InconsistentStateError("each retained backend must have one retained failure domain")
        if not isinstance(self.intents, Sequence) or isinstance(self.intents, (str, bytes, bytearray)) or not all(isinstance(item, PlacementIntent) for item in self.intents):
            raise ReplicaContractError("intents must be a sequence of PlacementIntent records")
        intents = tuple(sorted(self.intents, key=lambda item: item.backend_id))
        if len({item.backend_id for item in intents}) != len(intents):
            raise InconsistentStateError("placement intents must use distinct backends")
        if set(self.retained_backend_ids) & {item.backend_id for item in intents}:
            raise InconsistentStateError("retained and planned backends must be disjoint")
        if len(self.retained_backend_ids) + len(intents) != self.desired_replicas:
            raise InconsistentStateError("placement plan must contain exactly desired_replicas distinct backends")
        all_domains = set(self.retained_failure_domains) | {item.failure_domain for item in intents}
        if len(all_domains) != self.desired_replicas:
            raise InconsistentStateError("placement plan must use distinct failure domains")
        object.__setattr__(self, "intents", intents)

    @property
    def planned_backend_ids(self) -> tuple[str, ...]:
        return tuple(item.backend_id for item in self.intents)

    @property
    def selected_backend_ids(self) -> tuple[str, ...]:
        return self.retained_backend_ids + self.planned_backend_ids

    def _payload(self) -> dict[str, Any]:
        return {
            "content_ref": self.content_ref,
            "content_size_bytes": self.content_size_bytes,
            "policy_content_id": self.policy_content_id,
            "inventory_content_id": self.inventory_content_id,
            "desired_replicas": self.desired_replicas,
            "retained_backend_ids": self.retained_backend_ids,
            "retained_failure_domains": self.retained_failure_domains,
            "intents": self.intents,
        }


# ``ReplicaStatus`` was used in early plan discussion; retain it as a clear
# read-only alias while the canonical record name remains ReplicaObservation.
ReplicaStatus = ReplicaObservation


__all__ = [
    "BACKEND_CAPABILITY_SCHEMA", "BACKEND_INVENTORY_SCHEMA", "BackendCapability", "BackendInventory",
    "CONTRACT_VERSION", "ConsistencyLevel", "CostTier", "EncryptionLevel", "NON_DURABLE_REPLICA_STATES",
    "PLACEMENT_INTENT_SCHEMA", "PLACEMENT_PLAN_SCHEMA", "PlacementIntent", "PlacementPlan", "PlacementPlan_V1",
    "PlacementUnsatisfiableError", "REPLICA_OBSERVATION_SCHEMA", "REPLICA_POLICY_SCHEMA", "REPLICATION_CONTRACTS_NAMESPACE",
    "ReplicaContractError", "ReplicaObservation", "ReplicaPolicy", "ReplicaPolicyError", "ReplicaPolicy_V1", "ReplicaState",
    "ReplicaState_V1", "ReplicaStatus", "RetentionLevel", "SCHEMA_VERSION", "VERIFIED_DURABLE_REPLICA_STATES",
    "assert_legal_replica_transition", "is_legal_replica_transition",
]
