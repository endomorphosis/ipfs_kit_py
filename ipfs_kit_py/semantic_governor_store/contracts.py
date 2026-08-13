"""Closed, inert contracts for the durable semantic-governor store protocol.

SCG-010 freezes the narrow storage surface that later kit tasks implement as a
thin typed layer over ``DurableCoordinationStore`` and durable root CAS:

* closed governor artifact kinds and namespace roles;
* caller-supplied verified CIDs (never trusted without recomputation);
* expected generation plus expected root/head CID on CAS and history append;
* operation-id idempotency keys;
* typed ``updated`` / ``unchanged`` / ``conflict`` / ``corrupt`` /
  ``unavailable`` outcomes.

This module owns only validation, wire representations, and protocol shapes.
It does not open a store, compute content identities as an authority, start a
daemon, or introduce a second receipt hierarchy or block engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Final, Mapping, Optional, Protocol, TypeVar

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    validate_transport_cid,
)

# ---------------------------------------------------------------------------
# Schema / interface constants
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SEMANTIC_GOVERNOR_STORE_INTERFACE: Final[str] = "SemanticGovernorStore@1"
SEMANTIC_GOVERNOR_STORE_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-governor-store.contracts@1"
)

GOVERNOR_NAMESPACE_PREFIX: Final[str] = "semantic-governor"
MAX_NAMESPACE_CHARS: Final[int] = 255
MAX_WORKSPACE_CHARS: Final[int] = 63
MAX_OPERATION_ID_CHARS: Final[int] = 128
MAX_REASON_CODE_CHARS: Final[int] = 64
MAX_RECOVERY_ERRORS: Final[int] = 32

_NAMESPACE_SEGMENT: Final[re.Pattern[str]] = re.compile(
    r"[a-z0-9](?:[a-z0-9._-]{0,61}[a-z0-9])?"
)
_WORKSPACE: Final[re.Pattern[str]] = re.compile(
    r"[a-z0-9](?:[a-z0-9._-]{0,61}[a-z0-9])?"
)
_OPERATION_ID: Final[re.Pattern[str]] = re.compile(
    r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?"
)
_REASON_CODE: Final[re.Pattern[str]] = re.compile(r"[a-z][a-z0-9_-]{0,63}")

_T = TypeVar("_T")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SemanticGovernorStoreContractError(ValueError):
    """Raised when a governor-store contract value is malformed or incoherent."""


# ---------------------------------------------------------------------------
# Closed enumerations
# ---------------------------------------------------------------------------


class GovernorArtifactKind(str, Enum):
    """Closed taxonomy of immutable governor payload kinds admitted by storage.

    Kinds name storage admission classes, not datasets evidence schemas.  Neutral
    receipt payloads from datasets are stored under the receipt kinds and bound
    to existing envelope machinery without a second receipt hierarchy.
    """

    AUDIT = "audit"
    CALIBRATION = "calibration"
    BENCHMARK = "benchmark"
    POLICY = "policy"
    POLICY_CANDIDATE = "policy_candidate"
    EVALUATION = "evaluation"
    PROMOTION = "promotion"
    RUN_RECEIPT = "run_receipt"
    PROMOTION_RECEIPT = "promotion_receipt"
    HISTORY_MANIFEST = "history_manifest"


class GovernorNamespaceRole(str, Enum):
    """Closed durable head/history roles under the governor namespace prefix."""

    AUDIT = "audit"
    CALIBRATION = "calibration"
    BENCHMARK = "benchmark"
    POLICY = "policy"
    PROMOTION = "promotion"
    RECEIPTS = "receipts"


class GovernorStoreStatus(str, Enum):
    """Closed outcome set for governor CAS, history append, and head updates."""

    UPDATED = "updated"
    UNCHANGED = "unchanged"
    CONFLICT = "conflict"
    UNAVAILABLE = "unavailable"
    CORRUPT = "corrupt"


class GovernorProviderStatus(str, Enum):
    """Truthful optional remote replication outcome for a durable write."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    CORRUPT = "corrupt"
    NOT_REQUESTED = "not_requested"


class GovernorHistoryRole(str, Enum):
    """Append-only history streams that reference immutable artifact CIDs."""

    AUDIT = "audit"
    CALIBRATION = "calibration"
    BENCHMARK = "benchmark"


_HISTORY_TO_NAMESPACE: Final[Mapping[GovernorHistoryRole, GovernorNamespaceRole]] = (
    MappingProxyType(
        {
            GovernorHistoryRole.AUDIT: GovernorNamespaceRole.AUDIT,
            GovernorHistoryRole.CALIBRATION: GovernorNamespaceRole.CALIBRATION,
            GovernorHistoryRole.BENCHMARK: GovernorNamespaceRole.BENCHMARK,
        }
    )
)

_ADMITTED_RECEIPT_KINDS: Final[frozenset[GovernorArtifactKind]] = frozenset(
    {
        GovernorArtifactKind.RUN_RECEIPT,
        GovernorArtifactKind.PROMOTION_RECEIPT,
    }
)


# ---------------------------------------------------------------------------
# Primitive validators
# ---------------------------------------------------------------------------


def _closed_mapping(
    value: object, fields: frozenset[str], name: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SemanticGovernorStoreContractError(f"{name} must be a mapping")
    actual = frozenset(value)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        problems: list[str] = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        raise SemanticGovernorStoreContractError(
            f"{name} has " + "; ".join(problems)
        )
    return value


def _require_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise SemanticGovernorStoreContractError(f"{name} must be a boolean")
    return value


def _require_nonnegative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SemanticGovernorStoreContractError(
            f"{name} must be a non-negative integer"
        )
    return value


def _status(value: object, enum: type[_T], name: str) -> _T:
    if not isinstance(value, enum):
        raise SemanticGovernorStoreContractError(
            f"{name} must be a {enum.__name__}"
        )
    return value


def validate_governor_workspace(workspace: object) -> str:
    """Validate a single workspace segment used inside closed governor namespaces."""

    if not isinstance(workspace, str) or not workspace:
        raise SemanticGovernorStoreContractError(
            "workspace must be a non-empty normalized string"
        )
    if len(workspace) > MAX_WORKSPACE_CHARS:
        raise SemanticGovernorStoreContractError(
            f"workspace must be at most {MAX_WORKSPACE_CHARS} characters"
        )
    if workspace != workspace.strip() or not _WORKSPACE.fullmatch(workspace):
        raise SemanticGovernorStoreContractError(
            "workspace must be a normalized lowercase segment"
        )
    return workspace


def validate_governor_namespace(namespace: object) -> str:
    """Validate a full namespace against the DurableCoordinationStore grammar."""

    if not isinstance(namespace, str) or not namespace:
        raise SemanticGovernorStoreContractError(
            "namespace must be a non-empty normalized string"
        )
    if len(namespace) > MAX_NAMESPACE_CHARS:
        raise SemanticGovernorStoreContractError(
            f"namespace must be at most {MAX_NAMESPACE_CHARS} characters"
        )
    if namespace != namespace.strip() or "//" in namespace:
        raise SemanticGovernorStoreContractError("namespace must be normalized")
    segments = namespace.split("/")
    if not all(_NAMESPACE_SEGMENT.fullmatch(segment) for segment in segments):
        raise SemanticGovernorStoreContractError(
            "namespace contains an invalid segment"
        )
    return namespace


def validate_operation_id(operation_id: object) -> str:
    """Validate an operation-id / idempotency key (length 1–128)."""

    if not isinstance(operation_id, str) or not _OPERATION_ID.fullmatch(
        operation_id
    ):
        raise SemanticGovernorStoreContractError(
            "operation_id must be a normalized identifier of length 1–128"
        )
    if len(operation_id) > MAX_OPERATION_ID_CHARS:
        raise SemanticGovernorStoreContractError(
            f"operation_id must be at most {MAX_OPERATION_ID_CHARS} characters"
        )
    return operation_id


def validate_reason_code(reason_code: object) -> str:
    if not isinstance(reason_code, str) or not _REASON_CODE.fullmatch(reason_code):
        raise SemanticGovernorStoreContractError(
            "reason_code must be a normalized lowercase token"
        )
    return reason_code


def validate_verified_cid(value: object, name: str = "cid") -> str:
    """Require a caller-supplied canonical transport CID.

    Contracts validate spelling and profile only.  Implementations must still
    recompute canonical bytes and refuse a supplied CID that does not match.
    """

    try:
        validate_transport_cid(value)
    except ValueError as exc:
        raise SemanticGovernorStoreContractError(
            f"{name} must be a canonical transport CID"
        ) from exc
    return value  # type: ignore[return-value]


def validate_semantic_dag_json_cid(value: object, name: str = "cid") -> str:
    """Require a caller-owned canonical dag-json CID for structured artifacts."""

    cid = validate_verified_cid(value, name)
    if validate_transport_cid(cid) != "dag-json":
        raise SemanticGovernorStoreContractError(
            f"{name} must be a canonical dag-json CID"
        )
    return cid


def _optional_cid(value: object, name: str) -> str | None:
    if value is None:
        return None
    return validate_verified_cid(value, name)


def validate_generation_expectation(
    expected_generation: object, expected_root_cid: object
) -> tuple[int, str | None]:
    """Validate the one coherent predecessor form for generation-bearing CAS.

    Generation zero admits only a null expected root.  Non-zero generations
    require a caller-supplied verified root/head CID (ABA-safe expected pair).
    """

    generation = _require_nonnegative_int(
        expected_generation, "expected_generation"
    )
    root_cid = _optional_cid(expected_root_cid, "expected_root_cid")
    if generation == 0 and root_cid is not None:
        raise SemanticGovernorStoreContractError(
            "generation-zero expectations must not have a root CID"
        )
    if generation > 0 and root_cid is None:
        raise SemanticGovernorStoreContractError(
            "non-zero expectations require a root CID"
        )
    return generation, root_cid


def governor_namespace(
    workspace: str, role: GovernorNamespaceRole | str
) -> str:
    """Build the closed ``semantic-governor/<workspace>/<role>`` namespace."""

    workspace_token = validate_governor_workspace(workspace)
    if isinstance(role, GovernorNamespaceRole):
        role_token = role.value
    elif isinstance(role, str):
        try:
            role_token = GovernorNamespaceRole(role).value
        except ValueError as exc:
            raise SemanticGovernorStoreContractError(
                f"unknown governor namespace role: {role!r}"
            ) from exc
    else:
        raise SemanticGovernorStoreContractError(
            "role must be a GovernorNamespaceRole or its value"
        )
    namespace = f"{GOVERNOR_NAMESPACE_PREFIX}/{workspace_token}/{role_token}"
    return validate_governor_namespace(namespace)


def parse_governor_namespace(namespace: object) -> tuple[str, GovernorNamespaceRole]:
    """Parse a closed governor namespace into workspace and role."""

    text = validate_governor_namespace(namespace)
    parts = text.split("/")
    if len(parts) != 3 or parts[0] != GOVERNOR_NAMESPACE_PREFIX:
        raise SemanticGovernorStoreContractError(
            "namespace must be semantic-governor/<workspace>/<role>"
        )
    workspace = validate_governor_workspace(parts[1])
    try:
        role = GovernorNamespaceRole(parts[2])
    except ValueError as exc:
        raise SemanticGovernorStoreContractError(
            f"unknown governor namespace role: {parts[2]!r}"
        ) from exc
    return workspace, role


def history_namespace(workspace: str, role: GovernorHistoryRole | str) -> str:
    """Namespace for an append-only audit/calibration/benchmark history head."""

    if isinstance(role, GovernorHistoryRole):
        history_role = role
    elif isinstance(role, str):
        try:
            history_role = GovernorHistoryRole(role)
        except ValueError as exc:
            raise SemanticGovernorStoreContractError(
                f"unknown governor history role: {role!r}"
            ) from exc
    else:
        raise SemanticGovernorStoreContractError(
            "role must be a GovernorHistoryRole or its value"
        )
    return governor_namespace(workspace, _HISTORY_TO_NAMESPACE[history_role])


def governor_artifact_kinds() -> tuple[str, ...]:
    return tuple(kind.value for kind in GovernorArtifactKind)


def governor_namespace_roles() -> tuple[str, ...]:
    return tuple(role.value for role in GovernorNamespaceRole)


def governor_store_statuses() -> tuple[str, ...]:
    return tuple(status.value for status in GovernorStoreStatus)


# ---------------------------------------------------------------------------
# Wire / value records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GovernorArtifactWriteResult:
    """Verified immutable artifact write with independent local/remote facts."""

    cid: str
    kind: GovernorArtifactKind
    local_durable: bool
    provider_status: GovernorProviderStatus
    replicated: bool
    reason_code: str

    def __post_init__(self) -> None:
        validate_verified_cid(self.cid, "cid")
        _status(self.kind, GovernorArtifactKind, "kind")
        _require_bool(self.local_durable, "local_durable")
        _status(self.provider_status, GovernorProviderStatus, "provider_status")
        _require_bool(self.replicated, "replicated")
        validate_reason_code(self.reason_code)
        if not self.local_durable:
            raise SemanticGovernorStoreContractError(
                "an artifact result cannot claim success without local durability"
            )
        if self.replicated != (
            self.provider_status is GovernorProviderStatus.AVAILABLE
        ):
            raise SemanticGovernorStoreContractError(
                "replicated must exactly match an available provider outcome"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cid": self.cid,
            "kind": self.kind.value,
            "local_durable": self.local_durable,
            "provider_status": self.provider_status.value,
            "replicated": self.replicated,
            "reason_code": self.reason_code,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GovernorArtifactWriteResult":
        data = dict(
            _closed_mapping(
                value,
                frozenset(
                    (
                        "cid",
                        "kind",
                        "local_durable",
                        "provider_status",
                        "replicated",
                        "reason_code",
                    )
                ),
                "artifact write result",
            )
        )
        try:
            data["kind"] = GovernorArtifactKind(data["kind"])
            data["provider_status"] = GovernorProviderStatus(
                data["provider_status"]
            )
        except (TypeError, ValueError) as exc:
            raise SemanticGovernorStoreContractError(
                "kind or provider_status is unknown"
            ) from exc
        return cls(**data)


@dataclass(frozen=True, slots=True)
class PolicyVersionSnapshot:
    """Currently visible compression-policy head for one governor workspace."""

    namespace: str
    policy_cid: str | None
    generation: int
    transition_cid: str | None

    def __post_init__(self) -> None:
        namespace = validate_governor_namespace(self.namespace)
        workspace, role = parse_governor_namespace(namespace)
        if role is not GovernorNamespaceRole.POLICY:
            raise SemanticGovernorStoreContractError(
                "PolicyVersionSnapshot namespace role must be policy"
            )
        object.__setattr__(self, "namespace", governor_namespace(workspace, role))
        _optional_cid(self.policy_cid, "policy_cid")
        _require_nonnegative_int(self.generation, "generation")
        _optional_cid(self.transition_cid, "transition_cid")
        if self.generation == 0 and (
            self.policy_cid is not None or self.transition_cid is not None
        ):
            raise SemanticGovernorStoreContractError(
                "generation-zero policy heads must not have a CID or transition"
            )
        if self.generation > 0 and (
            self.policy_cid is None or self.transition_cid is None
        ):
            raise SemanticGovernorStoreContractError(
                "non-zero policy heads require a policy CID and transition CID"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "policy_cid": self.policy_cid,
            "generation": self.generation,
            "transition_cid": self.transition_cid,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PolicyVersionSnapshot":
        data = _closed_mapping(
            value,
            frozenset(
                ("namespace", "policy_cid", "generation", "transition_cid")
            ),
            "policy snapshot",
        )
        return cls(**data)


@dataclass(frozen=True, slots=True)
class PromotionStateSnapshot:
    """Currently visible promotion head for one governor workspace."""

    namespace: str
    promotion_cid: str | None
    generation: int
    transition_cid: str | None

    def __post_init__(self) -> None:
        namespace = validate_governor_namespace(self.namespace)
        workspace, role = parse_governor_namespace(namespace)
        if role is not GovernorNamespaceRole.PROMOTION:
            raise SemanticGovernorStoreContractError(
                "PromotionStateSnapshot namespace role must be promotion"
            )
        object.__setattr__(
            self, "namespace", governor_namespace(workspace, role)
        )
        _optional_cid(self.promotion_cid, "promotion_cid")
        _require_nonnegative_int(self.generation, "generation")
        _optional_cid(self.transition_cid, "transition_cid")
        if self.generation == 0 and (
            self.promotion_cid is not None or self.transition_cid is not None
        ):
            raise SemanticGovernorStoreContractError(
                "generation-zero promotion heads must not have a CID or transition"
            )
        if self.generation > 0 and (
            self.promotion_cid is None or self.transition_cid is None
        ):
            raise SemanticGovernorStoreContractError(
                "non-zero promotion heads require a promotion CID and transition CID"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "promotion_cid": self.promotion_cid,
            "generation": self.generation,
            "transition_cid": self.transition_cid,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PromotionStateSnapshot":
        data = _closed_mapping(
            value,
            frozenset(
                ("namespace", "promotion_cid", "generation", "transition_cid")
            ),
            "promotion snapshot",
        )
        return cls(**data)


@dataclass(frozen=True, slots=True)
class HistoryHeadSnapshot:
    """Currently visible append-only history head for audit/calibration/benchmark."""

    namespace: str
    head_cid: str | None
    generation: int
    transition_cid: str | None
    history_role: GovernorHistoryRole

    def __post_init__(self) -> None:
        _status(self.history_role, GovernorHistoryRole, "history_role")
        namespace = validate_governor_namespace(self.namespace)
        workspace, role = parse_governor_namespace(namespace)
        expected = _HISTORY_TO_NAMESPACE[self.history_role]
        if role is not expected:
            raise SemanticGovernorStoreContractError(
                "history snapshot namespace role must match history_role"
            )
        object.__setattr__(
            self, "namespace", governor_namespace(workspace, role)
        )
        _optional_cid(self.head_cid, "head_cid")
        _require_nonnegative_int(self.generation, "generation")
        _optional_cid(self.transition_cid, "transition_cid")
        if self.generation == 0 and (
            self.head_cid is not None or self.transition_cid is not None
        ):
            raise SemanticGovernorStoreContractError(
                "generation-zero history heads must not have a CID or transition"
            )
        if self.generation > 0 and (
            self.head_cid is None or self.transition_cid is None
        ):
            raise SemanticGovernorStoreContractError(
                "non-zero history heads require a head CID and transition CID"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "head_cid": self.head_cid,
            "generation": self.generation,
            "transition_cid": self.transition_cid,
            "history_role": self.history_role.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HistoryHeadSnapshot":
        data = dict(
            _closed_mapping(
                value,
                frozenset(
                    (
                        "namespace",
                        "head_cid",
                        "generation",
                        "transition_cid",
                        "history_role",
                    )
                ),
                "history snapshot",
            )
        )
        try:
            data["history_role"] = GovernorHistoryRole(data["history_role"])
        except (TypeError, ValueError) as exc:
            raise SemanticGovernorStoreContractError(
                "history_role is unknown"
            ) from exc
        return cls(**data)


@dataclass(frozen=True, slots=True)
class PolicyCASResult:
    """Closed outcome of an attempted policy-head compare-and-swap."""

    status: GovernorStoreStatus
    before: PolicyVersionSnapshot
    after: PolicyVersionSnapshot
    transition_cid: str | None
    reason_code: str
    local_durable: bool
    replicated: bool
    operation_id: str

    def __post_init__(self) -> None:
        _status(self.status, GovernorStoreStatus, "status")
        if not isinstance(self.before, PolicyVersionSnapshot) or not isinstance(
            self.after, PolicyVersionSnapshot
        ):
            raise SemanticGovernorStoreContractError(
                "before and after must be PolicyVersionSnapshot values"
            )
        if self.before.namespace != self.after.namespace:
            raise SemanticGovernorStoreContractError(
                "before and after namespaces must agree"
            )
        _optional_cid(self.transition_cid, "transition_cid")
        validate_reason_code(self.reason_code)
        _require_bool(self.local_durable, "local_durable")
        _require_bool(self.replicated, "replicated")
        validate_operation_id(self.operation_id)
        if self.replicated and not self.local_durable:
            raise SemanticGovernorStoreContractError(
                "replicated results must also be locally durable"
            )
        if self.status is GovernorStoreStatus.UPDATED:
            if (
                not self.local_durable
                or self.after.generation != self.before.generation + 1
            ):
                raise SemanticGovernorStoreContractError(
                    "updated results require a durable one-generation successor"
                )
            if (
                self.after.policy_cid == self.before.policy_cid
                or self.transition_cid != self.after.transition_cid
            ):
                raise SemanticGovernorStoreContractError(
                    "updated results require a distinct matching transition"
                )
        else:
            if self.after != self.before or self.transition_cid is not None:
                raise SemanticGovernorStoreContractError(
                    "non-updated results must not change the policy head"
                )
            if self.replicated:
                raise SemanticGovernorStoreContractError(
                    "non-updated results cannot claim replication"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "transition_cid": self.transition_cid,
            "reason_code": self.reason_code,
            "local_durable": self.local_durable,
            "replicated": self.replicated,
            "operation_id": self.operation_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PolicyCASResult":
        data = dict(
            _closed_mapping(
                value,
                frozenset(
                    (
                        "status",
                        "before",
                        "after",
                        "transition_cid",
                        "reason_code",
                        "local_durable",
                        "replicated",
                        "operation_id",
                    )
                ),
                "policy CAS result",
            )
        )
        try:
            data["status"] = GovernorStoreStatus(data["status"])
        except (TypeError, ValueError) as exc:
            raise SemanticGovernorStoreContractError("status is unknown") from exc
        data["before"] = PolicyVersionSnapshot.from_dict(data["before"])
        data["after"] = PolicyVersionSnapshot.from_dict(data["after"])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class PromotionCASResult:
    """Closed outcome of an attempted promotion-head compare-and-swap."""

    status: GovernorStoreStatus
    before: PromotionStateSnapshot
    after: PromotionStateSnapshot
    transition_cid: str | None
    reason_code: str
    local_durable: bool
    replicated: bool
    operation_id: str
    candidate_cid: str
    authorization_cid: str

    def __post_init__(self) -> None:
        _status(self.status, GovernorStoreStatus, "status")
        if not isinstance(self.before, PromotionStateSnapshot) or not isinstance(
            self.after, PromotionStateSnapshot
        ):
            raise SemanticGovernorStoreContractError(
                "before and after must be PromotionStateSnapshot values"
            )
        if self.before.namespace != self.after.namespace:
            raise SemanticGovernorStoreContractError(
                "before and after namespaces must agree"
            )
        _optional_cid(self.transition_cid, "transition_cid")
        validate_reason_code(self.reason_code)
        _require_bool(self.local_durable, "local_durable")
        _require_bool(self.replicated, "replicated")
        validate_operation_id(self.operation_id)
        validate_semantic_dag_json_cid(self.candidate_cid, "candidate_cid")
        validate_semantic_dag_json_cid(
            self.authorization_cid, "authorization_cid"
        )
        if self.candidate_cid == self.authorization_cid:
            raise SemanticGovernorStoreContractError(
                "candidate cannot authorize its own promotion"
            )
        if self.replicated and not self.local_durable:
            raise SemanticGovernorStoreContractError(
                "replicated results must also be locally durable"
            )
        if self.status is GovernorStoreStatus.UPDATED:
            if (
                not self.local_durable
                or self.after.generation != self.before.generation + 1
            ):
                raise SemanticGovernorStoreContractError(
                    "updated results require a durable one-generation successor"
                )
            if (
                self.after.promotion_cid == self.before.promotion_cid
                or self.transition_cid != self.after.transition_cid
            ):
                raise SemanticGovernorStoreContractError(
                    "updated results require a distinct matching transition"
                )
        else:
            if self.after != self.before or self.transition_cid is not None:
                raise SemanticGovernorStoreContractError(
                    "non-updated results must not change the promotion head"
                )
            if self.replicated:
                raise SemanticGovernorStoreContractError(
                    "non-updated results cannot claim replication"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "transition_cid": self.transition_cid,
            "reason_code": self.reason_code,
            "local_durable": self.local_durable,
            "replicated": self.replicated,
            "operation_id": self.operation_id,
            "candidate_cid": self.candidate_cid,
            "authorization_cid": self.authorization_cid,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PromotionCASResult":
        data = dict(
            _closed_mapping(
                value,
                frozenset(
                    (
                        "status",
                        "before",
                        "after",
                        "transition_cid",
                        "reason_code",
                        "local_durable",
                        "replicated",
                        "operation_id",
                        "candidate_cid",
                        "authorization_cid",
                    )
                ),
                "promotion CAS result",
            )
        )
        try:
            data["status"] = GovernorStoreStatus(data["status"])
        except (TypeError, ValueError) as exc:
            raise SemanticGovernorStoreContractError("status is unknown") from exc
        data["before"] = PromotionStateSnapshot.from_dict(data["before"])
        data["after"] = PromotionStateSnapshot.from_dict(data["after"])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class HistoryAppendResult:
    """Closed outcome of an append-only history publication."""

    status: GovernorStoreStatus
    before: HistoryHeadSnapshot
    after: HistoryHeadSnapshot
    entry_cid: str
    transition_cid: str | None
    reason_code: str
    local_durable: bool
    operation_id: str

    def __post_init__(self) -> None:
        _status(self.status, GovernorStoreStatus, "status")
        if not isinstance(self.before, HistoryHeadSnapshot) or not isinstance(
            self.after, HistoryHeadSnapshot
        ):
            raise SemanticGovernorStoreContractError(
                "before and after must be HistoryHeadSnapshot values"
            )
        if (
            self.before.namespace != self.after.namespace
            or self.before.history_role != self.after.history_role
        ):
            raise SemanticGovernorStoreContractError(
                "before and after history heads must agree"
            )
        validate_semantic_dag_json_cid(self.entry_cid, "entry_cid")
        _optional_cid(self.transition_cid, "transition_cid")
        validate_reason_code(self.reason_code)
        _require_bool(self.local_durable, "local_durable")
        validate_operation_id(self.operation_id)
        if self.status is GovernorStoreStatus.UPDATED:
            if (
                not self.local_durable
                or self.after.generation != self.before.generation + 1
            ):
                raise SemanticGovernorStoreContractError(
                    "updated history appends require a durable one-generation successor"
                )
            if (
                self.after.head_cid is None
                or self.transition_cid != self.after.transition_cid
            ):
                raise SemanticGovernorStoreContractError(
                    "updated history appends require a matching transition"
                )
        else:
            if self.after != self.before or self.transition_cid is not None:
                raise SemanticGovernorStoreContractError(
                    "non-updated history results must not change the head"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "entry_cid": self.entry_cid,
            "transition_cid": self.transition_cid,
            "reason_code": self.reason_code,
            "local_durable": self.local_durable,
            "operation_id": self.operation_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HistoryAppendResult":
        data = dict(
            _closed_mapping(
                value,
                frozenset(
                    (
                        "status",
                        "before",
                        "after",
                        "entry_cid",
                        "transition_cid",
                        "reason_code",
                        "local_durable",
                        "operation_id",
                    )
                ),
                "history append result",
            )
        )
        try:
            data["status"] = GovernorStoreStatus(data["status"])
        except (TypeError, ValueError) as exc:
            raise SemanticGovernorStoreContractError("status is unknown") from exc
        data["before"] = HistoryHeadSnapshot.from_dict(data["before"])
        data["after"] = HistoryHeadSnapshot.from_dict(data["after"])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ReceiptIssuanceResult:
    """Durable issuance of a neutral datasets receipt payload under existing envelopes.

    Kit stores and binds the payload; it does not invent a second receipt
    hierarchy or envelope schema.
    """

    status: GovernorStoreStatus
    receipt_cid: str
    kind: GovernorArtifactKind
    envelope_schema: str
    local_durable: bool
    reason_code: str
    operation_id: str

    def __post_init__(self) -> None:
        _status(self.status, GovernorStoreStatus, "status")
        validate_semantic_dag_json_cid(self.receipt_cid, "receipt_cid")
        _status(self.kind, GovernorArtifactKind, "kind")
        if self.kind not in _ADMITTED_RECEIPT_KINDS:
            raise SemanticGovernorStoreContractError(
                "receipt issuance admits only run_receipt and promotion_receipt kinds"
            )
        if not isinstance(self.envelope_schema, str) or not self.envelope_schema:
            raise SemanticGovernorStoreContractError(
                "envelope_schema must be a non-empty string naming an existing envelope"
            )
        if self.envelope_schema.startswith("semantic-governor/receipt"):
            raise SemanticGovernorStoreContractError(
                "receipt issuance must bind an existing envelope, not a new hierarchy"
            )
        _require_bool(self.local_durable, "local_durable")
        validate_reason_code(self.reason_code)
        validate_operation_id(self.operation_id)
        if self.status is GovernorStoreStatus.UPDATED and not self.local_durable:
            raise SemanticGovernorStoreContractError(
                "updated receipt issuance requires local durability"
            )
        if self.status is GovernorStoreStatus.CORRUPT and self.local_durable:
            raise SemanticGovernorStoreContractError(
                "corrupt issuance cannot claim local durability"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "receipt_cid": self.receipt_cid,
            "kind": self.kind.value,
            "envelope_schema": self.envelope_schema,
            "local_durable": self.local_durable,
            "reason_code": self.reason_code,
            "operation_id": self.operation_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReceiptIssuanceResult":
        data = dict(
            _closed_mapping(
                value,
                frozenset(
                    (
                        "status",
                        "receipt_cid",
                        "kind",
                        "envelope_schema",
                        "local_durable",
                        "reason_code",
                        "operation_id",
                    )
                ),
                "receipt issuance result",
            )
        )
        try:
            data["status"] = GovernorStoreStatus(data["status"])
            data["kind"] = GovernorArtifactKind(data["kind"])
        except (TypeError, ValueError) as exc:
            raise SemanticGovernorStoreContractError(
                "status or kind is unknown"
            ) from exc
        return cls(**data)


@dataclass(frozen=True, slots=True)
class AuditRecoveryReport:
    """Pure governor-domain recovery evidence reconstructed from immutable blocks.

    Recovery may report verified blocks, reconstructed heads, ignored idempotent
    transitions, and closed error records.  It never invents promotion or
    completion outcomes.
    """

    verified_blocks: int
    reconstructed_policy_heads: tuple[PolicyVersionSnapshot, ...]
    reconstructed_promotion_heads: tuple[PromotionStateSnapshot, ...]
    reconstructed_history_heads: tuple[HistoryHeadSnapshot, ...]
    ignored_idempotent_transitions: tuple[str, ...]
    errors: tuple[Mapping[str, str], ...]

    def __post_init__(self) -> None:
        _require_nonnegative_int(self.verified_blocks, "verified_blocks")
        if not isinstance(self.reconstructed_policy_heads, tuple) or not all(
            isinstance(item, PolicyVersionSnapshot)
            for item in self.reconstructed_policy_heads
        ):
            raise SemanticGovernorStoreContractError(
                "reconstructed_policy_heads must be a tuple of PolicyVersionSnapshot"
            )
        if not isinstance(self.reconstructed_promotion_heads, tuple) or not all(
            isinstance(item, PromotionStateSnapshot)
            for item in self.reconstructed_promotion_heads
        ):
            raise SemanticGovernorStoreContractError(
                "reconstructed_promotion_heads must be a tuple of PromotionStateSnapshot"
            )
        if not isinstance(self.reconstructed_history_heads, tuple) or not all(
            isinstance(item, HistoryHeadSnapshot)
            for item in self.reconstructed_history_heads
        ):
            raise SemanticGovernorStoreContractError(
                "reconstructed_history_heads must be a tuple of HistoryHeadSnapshot"
            )
        for label, heads in (
            ("policy", self.reconstructed_policy_heads),
            ("promotion", self.reconstructed_promotion_heads),
            ("history", self.reconstructed_history_heads),
        ):
            namespaces = [item.namespace for item in heads]
            if len(set(namespaces)) != len(namespaces):
                raise SemanticGovernorStoreContractError(
                    f"reconstructed_{label}_heads may contain only one snapshot per namespace"
                )
        if not isinstance(self.ignored_idempotent_transitions, tuple):
            raise SemanticGovernorStoreContractError(
                "ignored_idempotent_transitions must be a tuple"
            )
        for cid in self.ignored_idempotent_transitions:
            validate_verified_cid(cid, "ignored_idempotent_transition")
        if not isinstance(self.errors, tuple):
            raise SemanticGovernorStoreContractError("errors must be a tuple")
        if len(self.errors) > MAX_RECOVERY_ERRORS:
            raise SemanticGovernorStoreContractError(
                f"errors must contain at most {MAX_RECOVERY_ERRORS} records"
            )
        normalized: list[Mapping[str, str]] = []
        for error in self.errors:
            record = _closed_mapping(
                error, frozenset(("code", "message")), "recovery error"
            )
            code, message = record["code"], record["message"]
            if (
                not isinstance(code, str)
                or not _REASON_CODE.fullmatch(code)
                or not isinstance(message, str)
                or not message
            ):
                raise SemanticGovernorStoreContractError(
                    "recovery errors require a normalized code and non-empty message"
                )
            normalized.append(
                MappingProxyType({"code": code, "message": message})
            )
        object.__setattr__(self, "errors", tuple(normalized))

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified_blocks": self.verified_blocks,
            "reconstructed_policy_heads": [
                item.to_dict() for item in self.reconstructed_policy_heads
            ],
            "reconstructed_promotion_heads": [
                item.to_dict() for item in self.reconstructed_promotion_heads
            ],
            "reconstructed_history_heads": [
                item.to_dict() for item in self.reconstructed_history_heads
            ],
            "ignored_idempotent_transitions": list(
                self.ignored_idempotent_transitions
            ),
            "errors": [dict(item) for item in self.errors],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AuditRecoveryReport":
        data = dict(
            _closed_mapping(
                value,
                frozenset(
                    (
                        "verified_blocks",
                        "reconstructed_policy_heads",
                        "reconstructed_promotion_heads",
                        "reconstructed_history_heads",
                        "ignored_idempotent_transitions",
                        "errors",
                    )
                ),
                "audit recovery report",
            )
        )
        for key in (
            "reconstructed_policy_heads",
            "reconstructed_promotion_heads",
            "reconstructed_history_heads",
            "ignored_idempotent_transitions",
            "errors",
        ):
            if not isinstance(data[key], list):
                raise SemanticGovernorStoreContractError(
                    "recovery report sequences must be lists"
                )
        data["reconstructed_policy_heads"] = tuple(
            PolicyVersionSnapshot.from_dict(item)
            for item in data["reconstructed_policy_heads"]
        )
        data["reconstructed_promotion_heads"] = tuple(
            PromotionStateSnapshot.from_dict(item)
            for item in data["reconstructed_promotion_heads"]
        )
        data["reconstructed_history_heads"] = tuple(
            HistoryHeadSnapshot.from_dict(item)
            for item in data["reconstructed_history_heads"]
        )
        data["ignored_idempotent_transitions"] = tuple(
            data["ignored_idempotent_transitions"]
        )
        data["errors"] = tuple(data["errors"])
        return cls(**data)


# ---------------------------------------------------------------------------
# Narrow protocol surfaces
# ---------------------------------------------------------------------------


class AuditHistoryStore(Protocol):
    """Append-only audit, calibration, and benchmark history operations."""

    def current_history(
        self, workspace: str, role: GovernorHistoryRole
    ) -> HistoryHeadSnapshot: ...

    def append_history(
        self,
        workspace: str,
        role: GovernorHistoryRole,
        *,
        entry_cid: str,
        expected_generation: int,
        expected_head_cid: Optional[str],
        operation_id: str,
    ) -> HistoryAppendResult: ...


class CompressionPolicyRepository(Protocol):
    """Versioned compression-policy head CAS repository."""

    def current_policy(self, workspace: str) -> PolicyVersionSnapshot: ...

    def compare_and_swap_policy(
        self,
        workspace: str,
        *,
        expected_generation: int,
        expected_policy_cid: Optional[str],
        new_policy_cid: str,
        operation_id: str,
    ) -> PolicyCASResult: ...


class PromotionStateRepository(Protocol):
    """Versioned promotion-head CAS repository with separate authorization CIDs."""

    def current_promotion(self, workspace: str) -> PromotionStateSnapshot: ...

    def compare_and_swap_promotion(
        self,
        workspace: str,
        *,
        expected_generation: int,
        expected_promotion_cid: Optional[str],
        new_promotion_cid: str,
        operation_id: str,
        candidate_cid: str,
        authorization_cid: str,
    ) -> PromotionCASResult: ...


class SemanticGovernorStore(Protocol):
    """Closed durable governor store protocol (``SemanticGovernorStore@1``).

    Implementations must compose ``DurableCoordinationStore`` (and the durable
    root adapter for generation-bearing heads).  Callers always supply verified
    CIDs, expected generation/root pairs, and operation IDs.  Outcomes are the
    closed ``GovernorStoreStatus`` set — never silent overwrite.

    The surface unifies immutable artifacts, append-only histories, policy and
    promotion CAS, receipt envelope binding, and recovery without a second
    storage engine or receipt hierarchy.
    """

    def put_artifact(
        self,
        kind: GovernorArtifactKind,
        payload: Mapping[str, Any],
        *,
        expected_cid: str,
        operation_id: str,
        replicate: bool = True,
    ) -> GovernorArtifactWriteResult: ...

    def get_verified_artifact(
        self,
        cid: str,
        *,
        expected_kind: Optional[GovernorArtifactKind] = None,
    ) -> Mapping[str, Any]: ...

    def current_history(
        self, workspace: str, role: GovernorHistoryRole
    ) -> HistoryHeadSnapshot: ...

    def append_history(
        self,
        workspace: str,
        role: GovernorHistoryRole,
        *,
        entry_cid: str,
        expected_generation: int,
        expected_head_cid: Optional[str],
        operation_id: str,
    ) -> HistoryAppendResult: ...

    def current_policy(self, workspace: str) -> PolicyVersionSnapshot: ...

    def compare_and_swap_policy(
        self,
        workspace: str,
        *,
        expected_generation: int,
        expected_policy_cid: Optional[str],
        new_policy_cid: str,
        operation_id: str,
    ) -> PolicyCASResult: ...

    def current_promotion(self, workspace: str) -> PromotionStateSnapshot: ...

    def compare_and_swap_promotion(
        self,
        workspace: str,
        *,
        expected_generation: int,
        expected_promotion_cid: Optional[str],
        new_promotion_cid: str,
        operation_id: str,
        candidate_cid: str,
        authorization_cid: str,
    ) -> PromotionCASResult: ...

    def issue_receipt(
        self,
        kind: GovernorArtifactKind,
        payload: Mapping[str, Any],
        *,
        expected_cid: str,
        envelope_schema: str,
        operation_id: str,
    ) -> ReceiptIssuanceResult: ...

    def recover_governor_store(self) -> AuditRecoveryReport: ...


__all__ = [
    "CONTRACT_VERSION",
    "SEMANTIC_GOVERNOR_STORE_INTERFACE",
    "SEMANTIC_GOVERNOR_STORE_SCHEMA",
    "GOVERNOR_NAMESPACE_PREFIX",
    "MAX_NAMESPACE_CHARS",
    "MAX_OPERATION_ID_CHARS",
    "MAX_RECOVERY_ERRORS",
    "SemanticGovernorStoreContractError",
    "GovernorArtifactKind",
    "GovernorNamespaceRole",
    "GovernorStoreStatus",
    "GovernorProviderStatus",
    "GovernorHistoryRole",
    "GovernorArtifactWriteResult",
    "PolicyVersionSnapshot",
    "PromotionStateSnapshot",
    "HistoryHeadSnapshot",
    "PolicyCASResult",
    "PromotionCASResult",
    "HistoryAppendResult",
    "ReceiptIssuanceResult",
    "AuditRecoveryReport",
    "AuditHistoryStore",
    "CompressionPolicyRepository",
    "PromotionStateRepository",
    "SemanticGovernorStore",
    "validate_governor_workspace",
    "validate_governor_namespace",
    "validate_operation_id",
    "validate_reason_code",
    "validate_verified_cid",
    "validate_semantic_dag_json_cid",
    "validate_generation_expectation",
    "governor_namespace",
    "parse_governor_namespace",
    "history_namespace",
    "governor_artifact_kinds",
    "governor_namespace_roles",
    "governor_store_statuses",
]
