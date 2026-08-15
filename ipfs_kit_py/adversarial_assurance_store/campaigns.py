"""Campaign state, receipts, gaps, and append-only histories (AAE-035).

``DurableMutationCampaignRepository`` and ``DurableAssuranceGapRepository``
are thin typed layers over ``DurableCoordinationStore`` and
``DurableAssuranceArtifactStore``:

* closed campaign phases and execution-claim statuses with an explicit
  transition table (no open-ended status strings);
* campaign-state CAS under ``adversarial-assurance/<workspace>/campaigns``;
* append-only history-manifest heads under campaigns / receipts / gaps roles;
* signed campaign receipts gated for verified signature, required audience,
  and closed action before the first durable write or history inclusion;
* partial and ambiguous execution claims cannot advance to terminal success;
* operation-id idempotent replay on CAS and history appends;
* completed immutable artifacts re-verify after process restart.

Does not open a second object store, WAL, daemon, envelope hierarchy, or
content-identity path.  Datasets schemas remain the payload authority for
receipts and gaps; kit owns only transition/state/history manifests.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Final, Mapping, Optional, Protocol

from ipfs_datasets_py.logic.software_contracts.adversarial_assurance import (
    AssuranceTerminalStatus,
    ExecutionMode,
    ReceiptAction,
    SignatureVerificationStatus,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    DurableCoordinationStore,
    cid_for_artifact,
)
from ipfs_kit_py.adversarial_assurance_store.artifacts import (
    AssuranceArtifactAdmissionError,
    AssuranceArtifactConflictError,
    AssuranceArtifactError,
    AssuranceArtifactIntegrityError,
    AssuranceArtifactNotFound,
    DurableAssuranceArtifactStore,
    cid_for_assurance_artifact,
    seal_assurance_artifact,
)
from ipfs_kit_py.adversarial_assurance_store.contracts import (
    AssuranceArtifactKind,
    AssuranceArtifactStoreContractError,
    AssuranceArtifactWriteResult,
    AssuranceNamespaceRole,
    AssuranceStoreStatus,
    assurance_namespace,
    validate_assurance_workspace,
    validate_operation_id,
    validate_reason_code,
    validate_semantic_dag_json_cid,
)

# ---------------------------------------------------------------------------
# Schema / interface constants
# ---------------------------------------------------------------------------

CAMPAIGN_MODULE_INTERFACE: Final[str] = "MutationCampaignRepository@1"
GAP_MODULE_INTERFACE: Final[str] = "AssuranceGapRepository@1"

CAMPAIGN_STATE_INTERFACE: Final[str] = "MutationCampaignState@1"
CAMPAIGN_STATE_SCHEMA: Final[str] = (
    "ipfs-kit.adversarial-assurance-store.campaign-state@1"
)

CAMPAIGN_HISTORY_MANIFEST_INTERFACE: Final[str] = "AssuranceHistoryManifest@1"
CAMPAIGN_HISTORY_MANIFEST_SCHEMA: Final[str] = (
    "ipfs-kit.adversarial-assurance-store.history-manifest@1"
)

# Required audience for signed receipts admitted into assurance store heads.
REQUIRED_RECEIPT_AUDIENCE: Final[str] = "adversarial_assurance.store"

# Closed action set for campaign receipts that may enter durable store history.
_CAMPAIGN_RECEIPT_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        ReceiptAction.SEAL_CAMPAIGN.value,
        ReceiptAction.COMPLETE_CAMPAIGN.value,
    }
)

DEFAULT_HISTORY_PAGE_SIZE: Final[int] = 64
MAX_HISTORY_PAGE_SIZE: Final[int] = 256
MAX_ARTIFACT_CID_LIST: Final[int] = 4_096

_CAMPAIGN_ID: Final[re.Pattern[str]] = re.compile(
    r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?"
)

_CAMPAIGN_STATE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema",
        "interface_id",
        "workspace",
        "campaign_id",
        "generation",
        "phase",
        "execution_claim_status",
        "plan_cid",
        "policy_cid",
        "receipt_cid",
        "previous_state_cid",
        "artifact_cids",
        "operation_id",
    }
)

_HISTORY_MANIFEST_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema",
        "interface_id",
        "workspace",
        "role",
        "generation",
        "entry_cid",
        "previous_head_cid",
        "operation_id",
    }
)

# History-manifest roles (receipts/gaps). Campaign state history is the
# immutable root-transition chain under the campaigns namespace head.
_HISTORY_ROLES: Final[frozenset[AssuranceNamespaceRole]] = frozenset(
    {
        AssuranceNamespaceRole.RECEIPTS,
        AssuranceNamespaceRole.GAPS,
    }
)


# ---------------------------------------------------------------------------
# Closed enumerations
# ---------------------------------------------------------------------------


class CampaignPhase(str, Enum):
    """Closed campaign lifecycle phases for durable campaign-state heads."""

    PLANNED = "planned"
    EXECUTING = "executing"
    DIAGNOSING = "diagnosing"
    EVALUATING = "evaluating"
    COMPLETE = "complete"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INCONCLUSIVE = "inconclusive"


class ExecutionClaimStatus(str, Enum):
    """Closed execution-claim completeness vocabulary for campaign state.

    ``partial`` and ``ambiguous`` may never transition a campaign into
    terminal success (``complete``).
    """

    NONE = "none"
    PARTIAL = "partial"
    COMPLETE = "complete"
    AMBIGUOUS = "ambiguous"
    FAILED = "failed"


# Terminal (absorbing) phases — no further transitions.
_TERMINAL_PHASES: Final[frozenset[CampaignPhase]] = frozenset(
    {
        CampaignPhase.COMPLETE,
        CampaignPhase.REJECTED,
        CampaignPhase.FAILED,
        CampaignPhase.CANCELLED,
        CampaignPhase.INCONCLUSIVE,
    }
)

# Closed directed transition graph: from_phase -> allowed successor phases.
# Genesis (generation zero / no prior state) admits only PLANNED.
_PHASE_TRANSITIONS: Final[Mapping[CampaignPhase, frozenset[CampaignPhase]]] = (
    MappingProxyType(
        {
            CampaignPhase.PLANNED: frozenset(
                {
                    CampaignPhase.EXECUTING,
                    CampaignPhase.CANCELLED,
                    CampaignPhase.REJECTED,
                }
            ),
            CampaignPhase.EXECUTING: frozenset(
                {
                    CampaignPhase.DIAGNOSING,
                    CampaignPhase.EVALUATING,
                    CampaignPhase.FAILED,
                    CampaignPhase.CANCELLED,
                    CampaignPhase.INCONCLUSIVE,
                }
            ),
            CampaignPhase.DIAGNOSING: frozenset(
                {
                    CampaignPhase.EVALUATING,
                    CampaignPhase.FAILED,
                    CampaignPhase.CANCELLED,
                    CampaignPhase.INCONCLUSIVE,
                }
            ),
            CampaignPhase.EVALUATING: frozenset(
                {
                    CampaignPhase.COMPLETE,
                    CampaignPhase.REJECTED,
                    CampaignPhase.FAILED,
                    CampaignPhase.INCONCLUSIVE,
                    CampaignPhase.CANCELLED,
                }
            ),
            CampaignPhase.COMPLETE: frozenset(),
            CampaignPhase.REJECTED: frozenset(),
            CampaignPhase.FAILED: frozenset(),
            CampaignPhase.CANCELLED: frozenset(),
            CampaignPhase.INCONCLUSIVE: frozenset(),
        }
    )
)

_NON_SUCCESS_CLAIMS: Final[frozenset[ExecutionClaimStatus]] = frozenset(
    {
        ExecutionClaimStatus.NONE,
        ExecutionClaimStatus.PARTIAL,
        ExecutionClaimStatus.AMBIGUOUS,
        ExecutionClaimStatus.FAILED,
    }
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CampaignStoreError(ValueError):
    """Base error for campaign / gap repository admission or integrity failures."""


class CampaignAdmissionError(CampaignStoreError):
    """Raised when a write is rejected by closed admission policy before mutation."""


class CampaignIntegrityError(CampaignStoreError):
    """Raised when stored heads, manifests, or transitions fail verification."""


class CampaignConflictError(CampaignStoreError):
    """Raised when an operation_id is reused for a different transition."""


class CampaignTransitionError(CampaignAdmissionError):
    """Raised when a phase / claim transition is not in the closed table."""


# ---------------------------------------------------------------------------
# Wire / value records
# ---------------------------------------------------------------------------


def _require_nonnegative_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CampaignAdmissionError(f"{name} must be a non-negative integer")
    return value


def _require_positive_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise CampaignAdmissionError(f"{name} must be a positive integer")
    return value


def _require_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise CampaignAdmissionError(f"{name} must be a boolean")
    return value


def _closed_mapping(
    value: object, fields: frozenset[str], name: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CampaignAdmissionError(f"{name} must be a mapping")
    actual = frozenset(value)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        problems: list[str] = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        raise CampaignAdmissionError(f"{name} has " + "; ".join(problems))
    return value


def validate_campaign_id(campaign_id: object) -> str:
    if not isinstance(campaign_id, str) or not _CAMPAIGN_ID.fullmatch(campaign_id):
        raise CampaignAdmissionError(
            "campaign_id must be a normalized identifier of length 1–128"
        )
    return campaign_id


def validate_generation_expectation(
    expected_generation: object, expected_root_cid: object
) -> tuple[int, str | None]:
    """Validate ABA-safe generation / expected-head pairing."""

    generation = _require_nonnegative_int(expected_generation, "expected_generation")
    if expected_root_cid is None:
        root_cid: str | None = None
    else:
        try:
            root_cid = validate_semantic_dag_json_cid(
                expected_root_cid, "expected_root_cid"
            )
        except AssuranceArtifactStoreContractError as exc:
            raise CampaignAdmissionError(str(exc)) from exc
    if generation == 0 and root_cid is not None:
        raise CampaignAdmissionError(
            "generation-zero expectations must not have a root CID"
        )
    if generation > 0 and root_cid is None:
        raise CampaignAdmissionError("non-zero expectations require a root CID")
    return generation, root_cid


def coerce_campaign_phase(value: CampaignPhase | str) -> CampaignPhase:
    if isinstance(value, CampaignPhase):
        return value
    if isinstance(value, str):
        try:
            return CampaignPhase(value)
        except ValueError as exc:
            raise CampaignAdmissionError(
                f"unknown campaign phase: {value!r}"
            ) from exc
    raise CampaignAdmissionError(
        "phase must be a CampaignPhase or its closed string value"
    )


def coerce_execution_claim_status(
    value: ExecutionClaimStatus | str,
) -> ExecutionClaimStatus:
    if isinstance(value, ExecutionClaimStatus):
        return value
    if isinstance(value, str):
        try:
            return ExecutionClaimStatus(value)
        except ValueError as exc:
            raise CampaignAdmissionError(
                f"unknown execution_claim_status: {value!r}"
            ) from exc
    raise CampaignAdmissionError(
        "execution_claim_status must be an ExecutionClaimStatus or its value"
    )


def campaign_phases() -> tuple[str, ...]:
    return tuple(phase.value for phase in CampaignPhase)


def execution_claim_statuses() -> tuple[str, ...]:
    return tuple(status.value for status in ExecutionClaimStatus)


def allowed_phase_transitions(
    phase: CampaignPhase | str,
) -> frozenset[CampaignPhase]:
    return _PHASE_TRANSITIONS[coerce_campaign_phase(phase)]


def assert_phase_transition_allowed(
    previous: CampaignPhase | None,
    next_phase: CampaignPhase | str,
) -> CampaignPhase:
    """Fail closed unless the phase edge is in the closed transition table."""

    nxt = coerce_campaign_phase(next_phase)
    if previous is None:
        if nxt is not CampaignPhase.PLANNED:
            raise CampaignTransitionError(
                "genesis campaign state must begin in phase 'planned'"
            )
        return nxt
    allowed = _PHASE_TRANSITIONS[previous]
    if nxt not in allowed:
        raise CampaignTransitionError(
            f"closed transition table rejects {previous.value!r} -> {nxt.value!r}"
        )
    return nxt


def assert_terminal_success_admissible(
    *,
    phase: CampaignPhase,
    execution_claim_status: ExecutionClaimStatus,
    receipt_cid: str | None,
) -> None:
    """Reject partial/ambiguous/none/failed claims as terminal success."""

    if phase is not CampaignPhase.COMPLETE:
        return
    if execution_claim_status is not ExecutionClaimStatus.COMPLETE:
        raise CampaignTransitionError(
            "partial and ambiguous execution claims cannot become terminal "
            f"success (execution_claim_status={execution_claim_status.value!r})"
        )
    if receipt_cid is None:
        raise CampaignTransitionError(
            "terminal success requires a verified signed campaign receipt_cid"
        )


@dataclass(frozen=True, slots=True)
class CampaignStateSnapshot:
    """Currently visible campaign-state head for a workspace."""

    namespace: str
    state_cid: str | None
    generation: int
    transition_cid: str | None
    phase: CampaignPhase | None
    campaign_id: str | None
    execution_claim_status: ExecutionClaimStatus | None
    receipt_cid: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise CampaignIntegrityError("namespace must be a non-empty string")
        if not isinstance(self.generation, int) or isinstance(self.generation, bool):
            raise CampaignIntegrityError("generation must be an integer")
        if self.generation < 0:
            raise CampaignIntegrityError("generation must be non-negative")
        if self.generation == 0:
            if (
                self.state_cid is not None
                or self.transition_cid is not None
                or self.phase is not None
                or self.campaign_id is not None
                or self.execution_claim_status is not None
                or self.receipt_cid is not None
            ):
                raise CampaignIntegrityError(
                    "generation-zero campaign heads must be empty"
                )
        else:
            if self.state_cid is None or self.transition_cid is None:
                raise CampaignIntegrityError(
                    "non-zero campaign heads require state and transition CIDs"
                )
            if self.phase is None or self.campaign_id is None:
                raise CampaignIntegrityError(
                    "non-zero campaign heads require phase and campaign_id"
                )
            if self.execution_claim_status is None:
                raise CampaignIntegrityError(
                    "non-zero campaign heads require execution_claim_status"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "state_cid": self.state_cid,
            "generation": self.generation,
            "transition_cid": self.transition_cid,
            "phase": None if self.phase is None else self.phase.value,
            "campaign_id": self.campaign_id,
            "execution_claim_status": (
                None
                if self.execution_claim_status is None
                else self.execution_claim_status.value
            ),
            "receipt_cid": self.receipt_cid,
        }


@dataclass(frozen=True, slots=True)
class CampaignTransitionResult:
    """Closed outcome of a campaign-state CAS publication."""

    status: AssuranceStoreStatus
    before: CampaignStateSnapshot
    after: CampaignStateSnapshot
    state_cid: str | None
    transition_cid: str | None
    reason_code: str
    local_durable: bool
    operation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, AssuranceStoreStatus):
            raise CampaignIntegrityError("status must be AssuranceStoreStatus")
        if not isinstance(self.before, CampaignStateSnapshot) or not isinstance(
            self.after, CampaignStateSnapshot
        ):
            raise CampaignIntegrityError(
                "before and after must be CampaignStateSnapshot values"
            )
        if self.before.namespace != self.after.namespace:
            raise CampaignIntegrityError("before and after namespaces must agree")
        try:
            validate_reason_code(self.reason_code)
            validate_operation_id(self.operation_id)
        except AssuranceArtifactStoreContractError as exc:
            raise CampaignIntegrityError(str(exc)) from exc
        if not isinstance(self.local_durable, bool):
            raise CampaignIntegrityError("local_durable must be a boolean")
        if self.status is AssuranceStoreStatus.UPDATED:
            if (
                not self.local_durable
                or self.after.generation != self.before.generation + 1
            ):
                raise CampaignIntegrityError(
                    "updated transitions require a durable one-generation successor"
                )
            if self.state_cid is None or self.transition_cid is None:
                raise CampaignIntegrityError(
                    "updated transitions require state_cid and transition_cid"
                )


@dataclass(frozen=True, slots=True)
class HistoryHeadSnapshot:
    """Currently visible append-only history head for a campaigns/receipts/gaps role."""

    namespace: str
    head_cid: str | None
    generation: int
    transition_cid: str | None
    role: AssuranceNamespaceRole

    def __post_init__(self) -> None:
        if not isinstance(self.role, AssuranceNamespaceRole):
            raise CampaignIntegrityError("role must be AssuranceNamespaceRole")
        if self.role not in _HISTORY_ROLES:
            raise CampaignIntegrityError(
                f"history role {self.role.value!r} is not managed by campaigns"
            )
        if not isinstance(self.generation, int) or isinstance(self.generation, bool):
            raise CampaignIntegrityError("generation must be an integer")
        if self.generation < 0:
            raise CampaignIntegrityError("generation must be non-negative")
        if self.generation == 0 and (
            self.head_cid is not None or self.transition_cid is not None
        ):
            raise CampaignIntegrityError(
                "generation-zero history heads must not have a CID or transition"
            )
        if self.generation > 0 and (
            self.head_cid is None or self.transition_cid is None
        ):
            raise CampaignIntegrityError(
                "non-zero history heads require a head CID and transition CID"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "head_cid": self.head_cid,
            "generation": self.generation,
            "transition_cid": self.transition_cid,
            "role": self.role.value,
        }


@dataclass(frozen=True, slots=True)
class HistoryAppendResult:
    """Closed outcome of an append-only history publication."""

    status: AssuranceStoreStatus
    before: HistoryHeadSnapshot
    after: HistoryHeadSnapshot
    entry_cid: str
    transition_cid: str | None
    reason_code: str
    local_durable: bool
    operation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, AssuranceStoreStatus):
            raise CampaignIntegrityError("status must be AssuranceStoreStatus")
        if not isinstance(self.before, HistoryHeadSnapshot) or not isinstance(
            self.after, HistoryHeadSnapshot
        ):
            raise CampaignIntegrityError(
                "before and after must be HistoryHeadSnapshot values"
            )
        if (
            self.before.namespace != self.after.namespace
            or self.before.role != self.after.role
        ):
            raise CampaignIntegrityError("before and after history heads must agree")
        try:
            validate_semantic_dag_json_cid(self.entry_cid, "entry_cid")
            validate_reason_code(self.reason_code)
            validate_operation_id(self.operation_id)
        except AssuranceArtifactStoreContractError as exc:
            raise CampaignIntegrityError(str(exc)) from exc
        if not isinstance(self.local_durable, bool):
            raise CampaignIntegrityError("local_durable must be a boolean")
        if self.status is AssuranceStoreStatus.UPDATED:
            if (
                not self.local_durable
                or self.after.generation != self.before.generation + 1
            ):
                raise CampaignIntegrityError(
                    "updated history appends require a durable one-generation successor"
                )


@dataclass(frozen=True, slots=True)
class ReceiptPersistResult:
    """Outcome of signature-gated campaign receipt persistence + history append."""

    artifact: AssuranceArtifactWriteResult
    history: HistoryAppendResult
    receipt_cid: str


@dataclass(frozen=True, slots=True)
class GapPersistResult:
    """Outcome of assurance-gap persistence + history append."""

    artifact: AssuranceArtifactWriteResult
    history: HistoryAppendResult
    gap_cid: str


# ---------------------------------------------------------------------------
# Campaign state / history manifest builders
# ---------------------------------------------------------------------------


def build_campaign_state(
    *,
    workspace: str,
    campaign_id: str,
    generation: int,
    phase: CampaignPhase | str,
    execution_claim_status: ExecutionClaimStatus | str,
    plan_cid: str | None,
    policy_cid: str | None,
    receipt_cid: str | None,
    previous_state_cid: str | None,
    artifact_cids: list[str] | tuple[str, ...] | None,
    operation_id: str,
    previous_phase: CampaignPhase | None = None,
    enforce_transition: bool = True,
) -> dict[str, Any]:
    """Build a closed, content-addressed campaign-state head payload."""

    try:
        workspace = validate_assurance_workspace(workspace)
        campaign_id = validate_campaign_id(campaign_id)
        operation_id = validate_operation_id(operation_id)
    except AssuranceArtifactStoreContractError as exc:
        raise CampaignAdmissionError(str(exc)) from exc

    generation = _require_positive_int(generation, "generation")
    phase_token = coerce_campaign_phase(phase)
    claim = coerce_execution_claim_status(execution_claim_status)

    if enforce_transition:
        assert_phase_transition_allowed(previous_phase, phase_token)
    assert_terminal_success_admissible(
        phase=phase_token,
        execution_claim_status=claim,
        receipt_cid=receipt_cid,
    )

    def _opt_cid(value: str | None, name: str) -> str | None:
        if value is None:
            return None
        try:
            return validate_semantic_dag_json_cid(value, name)
        except AssuranceArtifactStoreContractError as exc:
            raise CampaignAdmissionError(str(exc)) from exc

    plan = _opt_cid(plan_cid, "plan_cid")
    policy = _opt_cid(policy_cid, "policy_cid")
    receipt = _opt_cid(receipt_cid, "receipt_cid")
    previous = _opt_cid(previous_state_cid, "previous_state_cid")

    if generation == 1:
        if previous is not None:
            raise CampaignAdmissionError(
                "generation-1 campaign state must not reference previous_state_cid"
            )
    else:
        if previous is None:
            raise CampaignAdmissionError(
                "non-genesis campaign state requires previous_state_cid"
            )

    if phase_token is CampaignPhase.PLANNED and plan is None:
        raise CampaignAdmissionError("planned phase requires plan_cid")

    raw_cids = list(artifact_cids or ())
    if len(raw_cids) > MAX_ARTIFACT_CID_LIST:
        raise CampaignAdmissionError(
            f"artifact_cids exceeds MAX_ARTIFACT_CID_LIST ({len(raw_cids)})"
        )
    sealed_cids: list[str] = []
    seen: set[str] = set()
    for index, cid in enumerate(raw_cids):
        try:
            token = validate_semantic_dag_json_cid(cid, f"artifact_cids[{index}]")
        except AssuranceArtifactStoreContractError as exc:
            raise CampaignAdmissionError(str(exc)) from exc
        if token in seen:
            continue
        seen.add(token)
        sealed_cids.append(token)
    sealed_cids.sort()

    payload = {
        "schema": CAMPAIGN_STATE_SCHEMA,
        "interface_id": CAMPAIGN_STATE_INTERFACE,
        "workspace": workspace,
        "campaign_id": campaign_id,
        "generation": generation,
        "phase": phase_token.value,
        "execution_claim_status": claim.value,
        "plan_cid": plan,
        "policy_cid": policy,
        "receipt_cid": receipt,
        "previous_state_cid": previous,
        "artifact_cids": sealed_cids,
        "operation_id": operation_id,
    }
    # Fail closed on unknown keys by reconstructing through the closed field set.
    _closed_mapping(payload, _CAMPAIGN_STATE_FIELDS, "campaign state")
    return payload


def cid_for_campaign_state(state: Mapping[str, Any]) -> str:
    if not isinstance(state, Mapping):
        raise CampaignAdmissionError("campaign state must be a mapping")
    return cid_for_artifact(dict(state))


def admit_campaign_state(
    state: Mapping[str, Any],
    *,
    previous_phase: CampaignPhase | None = None,
    enforce_transition: bool = False,
) -> dict[str, Any]:
    """Validate and re-seal a campaign-state mapping (closed keys, closed enums)."""

    data = dict(_closed_mapping(state, _CAMPAIGN_STATE_FIELDS, "campaign state"))
    if data.get("schema") != CAMPAIGN_STATE_SCHEMA:
        raise CampaignIntegrityError(
            f"campaign state schema must be {CAMPAIGN_STATE_SCHEMA!r}"
        )
    if data.get("interface_id") != CAMPAIGN_STATE_INTERFACE:
        raise CampaignIntegrityError(
            f"campaign state interface_id must be {CAMPAIGN_STATE_INTERFACE!r}"
        )
    return build_campaign_state(
        workspace=data["workspace"],
        campaign_id=data["campaign_id"],
        generation=data["generation"],
        phase=data["phase"],
        execution_claim_status=data["execution_claim_status"],
        plan_cid=data["plan_cid"],
        policy_cid=data["policy_cid"],
        receipt_cid=data["receipt_cid"],
        previous_state_cid=data["previous_state_cid"],
        artifact_cids=data["artifact_cids"],
        operation_id=data["operation_id"],
        previous_phase=previous_phase,
        enforce_transition=enforce_transition,
    )


def build_history_manifest(
    *,
    workspace: str,
    role: AssuranceNamespaceRole | str,
    generation: int,
    entry_cid: str,
    previous_head_cid: Optional[str],
    operation_id: str,
) -> dict[str, Any]:
    """Build the closed append-manifest for an assurance history head."""

    try:
        workspace = validate_assurance_workspace(workspace)
        operation_id = validate_operation_id(operation_id)
        entry_cid = validate_semantic_dag_json_cid(entry_cid, "entry_cid")
        if previous_head_cid is not None:
            previous_head_cid = validate_semantic_dag_json_cid(
                previous_head_cid, "previous_head_cid"
            )
    except AssuranceArtifactStoreContractError as exc:
        raise CampaignAdmissionError(str(exc)) from exc

    if isinstance(role, AssuranceNamespaceRole):
        role_token = role
    elif isinstance(role, str):
        try:
            role_token = AssuranceNamespaceRole(role)
        except ValueError as exc:
            raise CampaignAdmissionError(
                f"unknown assurance history role: {role!r}"
            ) from exc
    else:
        raise CampaignAdmissionError(
            "role must be an AssuranceNamespaceRole or its value"
        )
    if role_token not in _HISTORY_ROLES:
        raise CampaignAdmissionError(
            f"history role {role_token.value!r} is not managed by campaigns"
        )

    generation = _require_positive_int(generation, "generation")
    payload = {
        "schema": CAMPAIGN_HISTORY_MANIFEST_SCHEMA,
        "interface_id": CAMPAIGN_HISTORY_MANIFEST_INTERFACE,
        "workspace": workspace,
        "role": role_token.value,
        "generation": generation,
        "entry_cid": entry_cid,
        "previous_head_cid": previous_head_cid,
        "operation_id": operation_id,
    }
    _closed_mapping(payload, _HISTORY_MANIFEST_FIELDS, "history manifest")
    return payload


def cid_for_history_manifest(manifest: Mapping[str, Any]) -> str:
    if not isinstance(manifest, Mapping):
        raise CampaignAdmissionError("history manifest must be a mapping")
    return cid_for_artifact(dict(manifest))


# ---------------------------------------------------------------------------
# Signed receipt admission (audience / action / verification)
# ---------------------------------------------------------------------------


def admit_campaign_receipt_payload(
    payload: Mapping[str, Any],
    *,
    expected_audience: str = REQUIRED_RECEIPT_AUDIENCE,
    allowed_actions: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Signature-gate, audience/action-check, and re-seal a campaign receipt.

    All gates run before content addressing or any durable write.  Unknown
    keys are rejected by datasets projection and by closed signature checks.
    """

    if not isinstance(payload, Mapping):
        raise CampaignAdmissionError("receipt payload must be a mapping")

    actions = allowed_actions if allowed_actions is not None else _CAMPAIGN_RECEIPT_ACTIONS

    # Project + signature gate through the artifact admission layer (datasets).
    try:
        sealed = seal_assurance_artifact(
            AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT,
            payload,
            enforce_signature_gate=True,
        )
    except AssuranceArtifactAdmissionError as exc:
        raise CampaignAdmissionError(str(exc)) from exc
    except AssuranceArtifactError as exc:
        raise CampaignAdmissionError(str(exc)) from exc

    signature = sealed.get("signature")
    if not isinstance(signature, Mapping):
        raise CampaignAdmissionError("receipt signature binding is required")

    audience = signature.get("audience")
    if audience != expected_audience:
        raise CampaignAdmissionError(
            f"wrong-audience receipt rejected before persistence: "
            f"expected {expected_audience!r}, got {audience!r}"
        )

    action = signature.get("action")
    if action not in actions:
        raise CampaignAdmissionError(
            f"wrong-action receipt rejected before persistence: "
            f"action {action!r} not in closed set"
        )

    status = signature.get("signature_verification_status")
    if status != SignatureVerificationStatus.VERIFIED.value:
        raise CampaignAdmissionError(
            f"unverified signed receipt rejected before persistence "
            f"(status={status!r})"
        )

    header = sealed.get("header")
    if not isinstance(header, Mapping):
        raise CampaignAdmissionError("receipt header is required")
    terminal = header.get("terminal_status")
    provenance = header.get("provenance")
    if (
        terminal == AssuranceTerminalStatus.COMPLETE.value
        and isinstance(provenance, Mapping)
        and provenance.get("execution_mode") == ExecutionMode.SIMULATED.value
    ):
        raise CampaignAdmissionError(
            "simulated provenance cannot claim complete terminal success"
        )

    return sealed


def _status_from_wire(value: object) -> AssuranceStoreStatus:
    if not isinstance(value, str):
        raise CampaignIntegrityError("status must be a string")
    try:
        return AssuranceStoreStatus(value)
    except ValueError as exc:
        raise CampaignIntegrityError(f"unknown store status: {value!r}") from exc


def _clamp_page(*, offset: int, limit: int) -> tuple[int, int]:
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise CampaignAdmissionError("offset must be a non-negative integer")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise CampaignAdmissionError("limit must be a positive integer")
    if limit > MAX_HISTORY_PAGE_SIZE:
        raise CampaignAdmissionError(
            f"limit exceeds MAX_HISTORY_PAGE_SIZE ({limit} > {MAX_HISTORY_PAGE_SIZE})"
        )
    return offset, limit


# ---------------------------------------------------------------------------
# Shared append-only history helper
# ---------------------------------------------------------------------------


class _AssuranceHistoryCore:
    """CAS-linked history-manifest appends for campaigns/receipts/gaps roles."""

    def __init__(self, store: DurableCoordinationStore) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store

    def _namespace(
        self, workspace: str, role: AssuranceNamespaceRole | str
    ) -> tuple[str, AssuranceNamespaceRole]:
        try:
            workspace = validate_assurance_workspace(workspace)
            if isinstance(role, AssuranceNamespaceRole):
                role_token = role
            elif isinstance(role, str):
                role_token = AssuranceNamespaceRole(role)
            else:
                raise CampaignAdmissionError(
                    "role must be an AssuranceNamespaceRole or its value"
                )
            if role_token not in _HISTORY_ROLES:
                raise CampaignAdmissionError(
                    f"history role {role_token.value!r} is not managed by campaigns"
                )
            return assurance_namespace(workspace, role_token), role_token
        except (AssuranceArtifactStoreContractError, ValueError) as exc:
            raise CampaignAdmissionError(str(exc)) from exc

    def current_history(
        self, workspace: str, role: AssuranceNamespaceRole | str
    ) -> HistoryHeadSnapshot:
        namespace, role_token = self._namespace(workspace, role)
        try:
            root = self._store.current_state_root(namespace)
        except ArtifactIntegrityError as exc:
            raise CampaignIntegrityError(str(exc)) from exc
        return HistoryHeadSnapshot(
            namespace=str(root["namespace"]),
            head_cid=root.get("root_cid"),
            generation=int(root["revision"]),
            transition_cid=root.get("transition_cid"),
            role=role_token,
        )

    def append_history(
        self,
        workspace: str,
        role: AssuranceNamespaceRole | str,
        *,
        entry_cid: str,
        expected_generation: int,
        expected_head_cid: Optional[str],
        operation_id: str,
    ) -> HistoryAppendResult:
        namespace, role_token = self._namespace(workspace, role)
        try:
            expected_generation, expected_head_cid = validate_generation_expectation(
                expected_generation, expected_head_cid
            )
            operation_id = validate_operation_id(operation_id)
            entry_cid = validate_semantic_dag_json_cid(entry_cid, "entry_cid")
            workspace_token = validate_assurance_workspace(workspace)
        except AssuranceArtifactStoreContractError as exc:
            raise CampaignAdmissionError(str(exc)) from exc

        try:
            self._store.get_bytes(entry_cid)
        except ArtifactNotFound:
            before = self._empty_or_current(workspace, role_token, namespace)
            return HistoryAppendResult(
                AssuranceStoreStatus.UNAVAILABLE,
                before,
                before,
                entry_cid,
                None,
                "entry_unavailable",
                False,
                operation_id,
            )
        except ArtifactIntegrityError:
            before = self._empty_or_current(workspace, role_token, namespace)
            return HistoryAppendResult(
                AssuranceStoreStatus.CORRUPT,
                before,
                before,
                entry_cid,
                None,
                "entry_integrity_failure",
                False,
                operation_id,
            )

        next_generation = expected_generation + 1
        manifest = build_history_manifest(
            workspace=workspace_token,
            role=role_token,
            generation=next_generation,
            entry_cid=entry_cid,
            previous_head_cid=expected_head_cid,
            operation_id=operation_id,
        )
        manifest_cid = cid_for_history_manifest(manifest)
        if expected_head_cid is not None and expected_head_cid == manifest_cid:
            raise CampaignAdmissionError(
                "history manifest CID must differ from expected_head_cid"
            )

        try:
            put_result = self._store.put(
                manifest,
                expected_cid=manifest_cid,
                codec="dag-json",
                replicate=False,
            )
        except ArtifactIntegrityError as exc:
            raise CampaignIntegrityError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise CampaignAdmissionError(str(exc)) from exc
        if str(put_result["cid"]) != manifest_cid:
            raise CampaignIntegrityError(
                f"store returned unexpected manifest CID {put_result['cid']!r}"
            )

        try:
            raw = self._store.compare_and_swap_state_root(
                namespace,
                expected_revision=expected_generation,
                expected_root_cid=expected_head_cid,
                new_root_cid=manifest_cid,
                operation_id=operation_id,
            )
        except ArtifactNotFound:
            before = self._empty_or_current(workspace, role_token, namespace)
            return HistoryAppendResult(
                AssuranceStoreStatus.UNAVAILABLE,
                before,
                before,
                entry_cid,
                None,
                "successor_unavailable",
                False,
                operation_id,
            )
        except ArtifactIntegrityError:
            before = self._empty_or_current(workspace, role_token, namespace)
            return HistoryAppendResult(
                AssuranceStoreStatus.CORRUPT,
                before,
                before,
                entry_cid,
                None,
                "integrity_failure",
                False,
                operation_id,
            )
        except ValueError as exc:
            raise CampaignAdmissionError(str(exc)) from exc

        return self._result_from_wire(
            raw,
            role=role_token,
            entry_cid=entry_cid,
            operation_id=operation_id,
        )

    def history_transitions(
        self,
        workspace: str,
        role: AssuranceNamespaceRole | str,
        *,
        offset: int = 0,
        limit: int = DEFAULT_HISTORY_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        namespace, _ = self._namespace(workspace, role)
        offset, limit = _clamp_page(offset=offset, limit=limit)
        rows = self._store.root_transitions(namespace)
        page = rows[offset : offset + limit]
        return [dict(row) for row in page]

    def list_entry_cids(
        self,
        workspace: str,
        role: AssuranceNamespaceRole | str,
        *,
        offset: int = 0,
        limit: int = DEFAULT_HISTORY_PAGE_SIZE,
    ) -> list[str]:
        offset, limit = _clamp_page(offset=offset, limit=limit)
        chain = self._walk_manifest_chain(workspace, role)
        page = chain[offset : offset + limit]
        return [item["entry_cid"] for item in page]

    def _empty_or_current(
        self,
        workspace: str,
        role: AssuranceNamespaceRole,
        namespace: str,
    ) -> HistoryHeadSnapshot:
        try:
            return self.current_history(workspace, role)
        except CampaignStoreError:
            return HistoryHeadSnapshot(namespace, None, 0, None, role)

    def _load_manifest(self, head_cid: str) -> dict[str, Any]:
        try:
            raw = self._store.get(head_cid)
        except ArtifactNotFound as exc:
            raise CampaignIntegrityError(
                f"history head {head_cid} is missing"
            ) from exc
        except ArtifactIntegrityError as exc:
            raise CampaignIntegrityError(str(exc)) from exc
        if not isinstance(raw, Mapping):
            raise CampaignIntegrityError(
                f"history head {head_cid} is not a mapping"
            )
        try:
            manifest = dict(
                _closed_mapping(raw, _HISTORY_MANIFEST_FIELDS, "history manifest")
            )
        except CampaignAdmissionError as exc:
            raise CampaignIntegrityError(str(exc)) from exc
        if manifest.get("schema") != CAMPAIGN_HISTORY_MANIFEST_SCHEMA:
            raise CampaignIntegrityError(
                f"history head {head_cid} has unknown manifest schema"
            )
        if manifest.get("interface_id") != CAMPAIGN_HISTORY_MANIFEST_INTERFACE:
            raise CampaignIntegrityError(
                f"history head {head_cid} has unknown manifest interface"
            )
        recomputed = cid_for_history_manifest(manifest)
        if recomputed != head_cid:
            raise CampaignIntegrityError(
                f"history manifest CID mismatch: recomputed {recomputed}, "
                f"expected {head_cid}"
            )
        return manifest

    def _walk_manifest_chain(
        self, workspace: str, role: AssuranceNamespaceRole | str
    ) -> list[dict[str, Any]]:
        head = self.current_history(workspace, role)
        if head.generation == 0 or head.head_cid is None:
            return []

        chain_rev: list[dict[str, Any]] = []
        seen: set[str] = set()
        cursor: Optional[str] = head.head_cid
        expected_generation = head.generation

        while cursor is not None:
            if cursor in seen:
                raise CampaignIntegrityError(
                    "history manifest chain contains a cycle"
                )
            seen.add(cursor)
            manifest = self._load_manifest(cursor)
            generation = manifest.get("generation")
            if generation != expected_generation:
                raise CampaignIntegrityError(
                    f"history manifest generation mismatch at {cursor}: "
                    f"expected {expected_generation}, got {generation!r}"
                )
            chain_rev.append(
                {
                    "generation": generation,
                    "entry_cid": str(manifest["entry_cid"]),
                    "head_cid": cursor,
                    "previous_head_cid": manifest.get("previous_head_cid"),
                    "operation_id": str(manifest.get("operation_id", "")),
                    "manifest": manifest,
                }
            )
            cursor = manifest.get("previous_head_cid")
            expected_generation -= 1
            if cursor is None and expected_generation != 0:
                raise CampaignIntegrityError(
                    "history manifest chain terminated before generation zero"
                )
            if expected_generation < 0:
                raise CampaignIntegrityError(
                    "history manifest chain is longer than head generation"
                )

        chain_rev.reverse()
        return chain_rev

    @staticmethod
    def _result_from_wire(
        raw: Mapping[str, Any],
        *,
        role: AssuranceNamespaceRole,
        entry_cid: str,
        operation_id: str,
    ) -> HistoryAppendResult:
        status = _status_from_wire(raw.get("status"))
        before_raw = raw["before"]
        after_raw = raw["after"]
        before = HistoryHeadSnapshot(
            namespace=str(before_raw["namespace"]),
            head_cid=before_raw.get("root_cid"),
            generation=int(before_raw["revision"]),
            transition_cid=before_raw.get("transition_cid"),
            role=role,
        )
        after = HistoryHeadSnapshot(
            namespace=str(after_raw["namespace"]),
            head_cid=after_raw.get("root_cid"),
            generation=int(after_raw["revision"]),
            transition_cid=after_raw.get("transition_cid"),
            role=role,
        )
        transition_cid = raw.get("transition_cid")
        if transition_cid is not None:
            try:
                transition_cid = validate_semantic_dag_json_cid(
                    transition_cid, "transition_cid"
                )
            except AssuranceArtifactStoreContractError as exc:
                raise CampaignIntegrityError(str(exc)) from exc
        reason_code = raw.get("reason_code")
        if not isinstance(reason_code, str):
            raise CampaignIntegrityError("history reason_code must be a string")
        local_durable = bool(raw.get("local_durable"))
        wire_op = raw.get("operation_id", operation_id)
        if not isinstance(wire_op, str):
            wire_op = operation_id
        return HistoryAppendResult(
            status,
            before,
            after,
            entry_cid,
            transition_cid,
            reason_code,
            local_durable,
            wire_op,
        )


# ---------------------------------------------------------------------------
# MutationCampaignRepository@1
# ---------------------------------------------------------------------------


class MutationCampaignRepository(Protocol):
    """Closed durable campaign-state and receipt repository surface."""

    def current_campaign_state(self, workspace: str) -> CampaignStateSnapshot: ...

    def transition_campaign_state(
        self,
        workspace: str,
        *,
        state: Mapping[str, Any],
        expected_generation: int,
        expected_state_cid: Optional[str],
        operation_id: str,
    ) -> CampaignTransitionResult: ...

    def persist_campaign_receipt(
        self,
        workspace: str,
        payload: Mapping[str, Any],
        *,
        expected_cid: str,
        artifact_operation_id: str,
        history_operation_id: str,
        expected_history_generation: int,
        expected_history_head_cid: Optional[str],
        replicate: bool = False,
    ) -> ReceiptPersistResult: ...


class DurableMutationCampaignRepository:
    """Durable campaign state, receipts, and append-only campaign histories.

    Implements ``MutationCampaignRepository@1``.
    """

    def __init__(
        self,
        store: DurableCoordinationStore,
        *,
        artifacts: DurableAssuranceArtifactStore | None = None,
    ) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store
        self._artifacts = artifacts or DurableAssuranceArtifactStore(store)
        self._owns_artifacts = artifacts is None
        self._history = _AssuranceHistoryCore(store)

    @property
    def store(self) -> DurableCoordinationStore:
        return self._store

    @property
    def artifacts(self) -> DurableAssuranceArtifactStore:
        return self._artifacts

    def close(self) -> None:
        if self._owns_artifacts:
            self._artifacts.close()

    def __enter__(self) -> "DurableMutationCampaignRepository":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _campaigns_namespace(self, workspace: str) -> str:
        try:
            workspace = validate_assurance_workspace(workspace)
            return assurance_namespace(workspace, AssuranceNamespaceRole.CAMPAIGNS)
        except AssuranceArtifactStoreContractError as exc:
            raise CampaignAdmissionError(str(exc)) from exc

    def current_campaign_state(self, workspace: str) -> CampaignStateSnapshot:
        """Return the currently visible campaign-state head (gen 0 if empty)."""

        namespace = self._campaigns_namespace(workspace)
        try:
            root = self._store.current_state_root(namespace)
        except ArtifactIntegrityError as exc:
            raise CampaignIntegrityError(str(exc)) from exc

        generation = int(root["revision"])
        state_cid = root.get("root_cid")
        transition_cid = root.get("transition_cid")
        if generation == 0 or state_cid is None:
            return CampaignStateSnapshot(
                namespace=str(root["namespace"]),
                state_cid=None,
                generation=0,
                transition_cid=None,
                phase=None,
                campaign_id=None,
                execution_claim_status=None,
                receipt_cid=None,
            )

        sealed = self.get_verified_campaign_state(str(state_cid))
        return CampaignStateSnapshot(
            namespace=str(root["namespace"]),
            state_cid=str(state_cid),
            generation=generation,
            transition_cid=None if transition_cid is None else str(transition_cid),
            phase=coerce_campaign_phase(str(sealed["phase"])),
            campaign_id=str(sealed["campaign_id"]),
            execution_claim_status=coerce_execution_claim_status(
                str(sealed["execution_claim_status"])
            ),
            receipt_cid=sealed.get("receipt_cid"),
        )

    def get_verified_campaign_state(self, state_cid: str) -> Mapping[str, Any]:
        """Load and re-verify a campaign-state block by CID."""

        try:
            state_cid = validate_semantic_dag_json_cid(state_cid, "state_cid")
        except AssuranceArtifactStoreContractError as exc:
            raise CampaignIntegrityError(str(exc)) from exc
        try:
            raw = self._store.get(state_cid)
        except ArtifactNotFound as exc:
            raise CampaignIntegrityError(
                f"campaign state {state_cid} is missing"
            ) from exc
        except ArtifactIntegrityError as exc:
            raise CampaignIntegrityError(str(exc)) from exc
        if not isinstance(raw, Mapping):
            raise CampaignIntegrityError(
                f"campaign state {state_cid} is not a mapping"
            )
        try:
            sealed = admit_campaign_state(raw, enforce_transition=False)
        except CampaignAdmissionError as exc:
            raise CampaignIntegrityError(str(exc)) from exc
        recomputed = cid_for_campaign_state(sealed)
        if recomputed != state_cid:
            raise CampaignIntegrityError(
                f"campaign state CID mismatch: recomputed {recomputed}, "
                f"expected {state_cid}"
            )
        return MappingProxyType(sealed)

    def transition_campaign_state(
        self,
        workspace: str,
        *,
        state: Mapping[str, Any],
        expected_generation: int,
        expected_state_cid: Optional[str],
        operation_id: str,
    ) -> CampaignTransitionResult:
        """Atomically publish a successor campaign-state head or report conflict.

        Campaign-state heads live under the ``campaigns`` namespace.  Successful
        CAS writes leave an immutable root-transition record — that chain is the
        append-only campaign history (no second head is published under the same
        namespace).

        Preconditions (fail-closed):

        * generation-zero expects a null state CID; non-zero expects a state CID
        * ``state`` is a closed campaign-state mapping (or builder fields)
        * phase edge is in the closed transition table
        * complete phase forbids partial/ambiguous execution claims
        * if ``receipt_cid`` is set, the receipt block must already be durable
          and pass verified-signature / audience / action gates
        * ``operation_id`` is a durable idempotency key
        """

        namespace = self._campaigns_namespace(workspace)
        try:
            expected_generation, expected_state_cid = validate_generation_expectation(
                expected_generation, expected_state_cid
            )
            operation_id = validate_operation_id(operation_id)
            workspace_token = validate_assurance_workspace(workspace)
        except AssuranceArtifactStoreContractError as exc:
            raise CampaignAdmissionError(str(exc)) from exc

        previous_phase: CampaignPhase | None = None
        if expected_generation == 0:
            if expected_state_cid is not None:
                raise CampaignAdmissionError(
                    "generation-zero expects a null state CID"
                )
        else:
            assert expected_state_cid is not None
            prior = self.get_verified_campaign_state(expected_state_cid)
            previous_phase = coerce_campaign_phase(str(prior["phase"]))
            if str(prior.get("workspace")) != workspace_token:
                raise CampaignAdmissionError(
                    "campaign state workspace does not match transition workspace"
                )

        # Allow either a full sealed mapping or builder kwargs-style mapping.
        if (
            isinstance(state, Mapping)
            and state.get("schema") == CAMPAIGN_STATE_SCHEMA
        ):
            sealed = admit_campaign_state(
                state,
                previous_phase=previous_phase,
                enforce_transition=True,
            )
        else:
            if not isinstance(state, Mapping):
                raise CampaignAdmissionError("state must be a mapping")
            # Builder-style fields (without schema) for convenience.
            required_builder = frozenset(
                {
                    "campaign_id",
                    "phase",
                    "execution_claim_status",
                    "plan_cid",
                    "policy_cid",
                    "receipt_cid",
                    "artifact_cids",
                }
            )
            actual = frozenset(state)
            # Reject unknown builder keys fail-closed.
            unknown = actual - required_builder - {"previous_state_cid", "generation"}
            if unknown:
                raise CampaignAdmissionError(
                    "campaign state has unknown "
                    + ", ".join(sorted(unknown))
                )
            missing = required_builder - actual
            if missing:
                raise CampaignAdmissionError(
                    "campaign state has missing "
                    + ", ".join(sorted(missing))
                )
            sealed = build_campaign_state(
                workspace=workspace_token,
                campaign_id=state["campaign_id"],  # type: ignore[index]
                generation=expected_generation + 1,
                phase=state["phase"],  # type: ignore[index]
                execution_claim_status=state["execution_claim_status"],  # type: ignore[index]
                plan_cid=state.get("plan_cid"),  # type: ignore[union-attr]
                policy_cid=state.get("policy_cid"),  # type: ignore[union-attr]
                receipt_cid=state.get("receipt_cid"),  # type: ignore[union-attr]
                previous_state_cid=expected_state_cid,
                artifact_cids=state.get("artifact_cids") or (),  # type: ignore[union-attr]
                operation_id=operation_id,
                previous_phase=previous_phase,
                enforce_transition=True,
            )

        # Align generation / previous / workspace with CAS expectation.
        if int(sealed["generation"]) != expected_generation + 1:
            raise CampaignAdmissionError(
                "campaign state generation must be expected_generation + 1"
            )
        if sealed.get("previous_state_cid") != expected_state_cid:
            raise CampaignAdmissionError(
                "campaign state previous_state_cid must equal expected_state_cid"
            )
        if sealed.get("workspace") != workspace_token:
            raise CampaignAdmissionError(
                "campaign state workspace must match transition workspace"
            )
        if sealed.get("operation_id") != operation_id:
            # Force operation_id binding for deterministic CAS identity.
            sealed = dict(sealed)
            sealed["operation_id"] = operation_id
            sealed = admit_campaign_state(
                sealed,
                previous_phase=previous_phase,
                enforce_transition=False,
            )

        # If a receipt is claimed, it must already be durable and verified.
        receipt_cid = sealed.get("receipt_cid")
        if receipt_cid is not None:
            self._require_verified_durable_receipt(str(receipt_cid))

        state_cid = cid_for_campaign_state(sealed)
        try:
            put_result = self._store.put(
                sealed,
                expected_cid=state_cid,
                codec="dag-json",
                replicate=False,
            )
        except ArtifactIntegrityError as exc:
            raise CampaignIntegrityError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise CampaignAdmissionError(str(exc)) from exc
        if str(put_result["cid"]) != state_cid:
            raise CampaignIntegrityError(
                f"store returned unexpected state CID {put_result['cid']!r}"
            )

        try:
            raw = self._store.compare_and_swap_state_root(
                namespace,
                expected_revision=expected_generation,
                expected_root_cid=expected_state_cid,
                new_root_cid=state_cid,
                operation_id=operation_id,
            )
        except ArtifactNotFound:
            before = self._empty_or_current_state(workspace, namespace)
            return CampaignTransitionResult(
                AssuranceStoreStatus.UNAVAILABLE,
                before,
                before,
                None,
                None,
                "successor_unavailable",
                False,
                operation_id,
            )
        except ArtifactIntegrityError:
            before = self._empty_or_current_state(workspace, namespace)
            return CampaignTransitionResult(
                AssuranceStoreStatus.CORRUPT,
                before,
                before,
                None,
                None,
                "integrity_failure",
                False,
                operation_id,
            )
        except ValueError as exc:
            raise CampaignAdmissionError(str(exc)) from exc

        return self._state_result_from_wire(
            raw, operation_id=operation_id, state_cid=state_cid
        )

    def persist_campaign_receipt(
        self,
        workspace: str,
        payload: Mapping[str, Any],
        *,
        expected_cid: str,
        artifact_operation_id: str,
        history_operation_id: str,
        expected_history_generation: int,
        expected_history_head_cid: Optional[str],
        replicate: bool = False,
    ) -> ReceiptPersistResult:
        """Admit a signed campaign receipt, store it immutably, append history.

        Rejects invalid, unknown-key, wrong-audience/action, or unverified
        signed receipts before any durable write or history inclusion.
        """

        sealed = admit_campaign_receipt_payload(payload)
        actual_cid = cid_for_assurance_artifact(
            AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT,
            sealed,
            enforce_signature_gate=True,
        )
        try:
            expected_cid = validate_semantic_dag_json_cid(expected_cid, "expected_cid")
        except AssuranceArtifactStoreContractError as exc:
            raise CampaignAdmissionError(str(exc)) from exc
        if actual_cid != expected_cid:
            raise CampaignIntegrityError(
                f"forged or mismatched receipt CID: computed {actual_cid}, "
                f"expected {expected_cid}"
            )

        try:
            artifact_result = self._artifacts.put_artifact(
                AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT,
                sealed,
                expected_cid=expected_cid,
                operation_id=artifact_operation_id,
                replicate=replicate,
            )
        except AssuranceArtifactAdmissionError as exc:
            raise CampaignAdmissionError(str(exc)) from exc
        except AssuranceArtifactConflictError as exc:
            raise CampaignConflictError(str(exc)) from exc
        except AssuranceArtifactError as exc:
            raise CampaignAdmissionError(str(exc)) from exc

        history = self._history.append_history(
            workspace,
            AssuranceNamespaceRole.RECEIPTS,
            entry_cid=expected_cid,
            expected_generation=expected_history_generation,
            expected_head_cid=expected_history_head_cid,
            operation_id=history_operation_id,
        )
        return ReceiptPersistResult(artifact_result, history, expected_cid)

    def current_receipts_history(self, workspace: str) -> HistoryHeadSnapshot:
        return self._history.current_history(
            workspace, AssuranceNamespaceRole.RECEIPTS
        )

    def campaign_state_transitions(
        self,
        workspace: str,
        *,
        offset: int = 0,
        limit: int = DEFAULT_HISTORY_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """Return immutable campaign-state root transitions in generation order."""

        namespace = self._campaigns_namespace(workspace)
        offset, limit = _clamp_page(offset=offset, limit=limit)
        rows = self._store.root_transitions(namespace)
        page = rows[offset : offset + limit]
        return [dict(row) for row in page]

    def campaign_state_history_cids(
        self,
        workspace: str,
        *,
        offset: int = 0,
        limit: int = DEFAULT_HISTORY_PAGE_SIZE,
    ) -> list[str]:
        """Return campaign-state CIDs in append (transition) order."""

        rows = self.campaign_state_transitions(
            workspace, offset=offset, limit=limit
        )
        return [str(row["new_root_cid"]) for row in rows]

    def append_receipt_history(
        self,
        workspace: str,
        *,
        entry_cid: str,
        expected_generation: int,
        expected_head_cid: Optional[str],
        operation_id: str,
    ) -> HistoryAppendResult:
        """Append an already-durable receipt CID to the receipts history."""

        return self._history.append_history(
            workspace,
            AssuranceNamespaceRole.RECEIPTS,
            entry_cid=entry_cid,
            expected_generation=expected_generation,
            expected_head_cid=expected_head_cid,
            operation_id=operation_id,
        )

    def receipt_history_entry_cids(
        self,
        workspace: str,
        *,
        offset: int = 0,
        limit: int = DEFAULT_HISTORY_PAGE_SIZE,
    ) -> list[str]:
        return self._history.list_entry_cids(
            workspace,
            AssuranceNamespaceRole.RECEIPTS,
            offset=offset,
            limit=limit,
        )

    def get_verified_receipt(self, cid: str) -> Mapping[str, Any]:
        try:
            return self._artifacts.get_verified_artifact(
                cid,
                expected_kind=AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT,
            )
        except AssuranceArtifactNotFound as exc:
            raise CampaignIntegrityError(str(exc)) from exc
        except AssuranceArtifactError as exc:
            raise CampaignIntegrityError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_verified_durable_receipt(self, receipt_cid: str) -> Mapping[str, Any]:
        try:
            receipt_cid = validate_semantic_dag_json_cid(receipt_cid, "receipt_cid")
        except AssuranceArtifactStoreContractError as exc:
            raise CampaignAdmissionError(str(exc)) from exc
        try:
            raw = self._artifacts.get_verified_artifact(
                receipt_cid,
                expected_kind=AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT,
            )
        except AssuranceArtifactNotFound as exc:
            raise CampaignAdmissionError(
                f"receipt_cid {receipt_cid} is not durable"
            ) from exc
        except AssuranceArtifactAdmissionError as exc:
            raise CampaignAdmissionError(str(exc)) from exc
        except AssuranceArtifactError as exc:
            raise CampaignAdmissionError(str(exc)) from exc
        # Re-run audience/action gates on the verified record.
        admit_campaign_receipt_payload(dict(raw))
        return raw

    def _empty_or_current_state(
        self, workspace: str, namespace: str
    ) -> CampaignStateSnapshot:
        try:
            return self.current_campaign_state(workspace)
        except CampaignStoreError:
            return CampaignStateSnapshot(
                namespace, None, 0, None, None, None, None, None
            )

    def _state_result_from_wire(
        self,
        raw: Mapping[str, Any],
        *,
        operation_id: str,
        state_cid: str,
    ) -> CampaignTransitionResult:
        status = _status_from_wire(raw.get("status"))
        before_raw = raw["before"]
        after_raw = raw["after"]

        def _snap(row: Mapping[str, Any]) -> CampaignStateSnapshot:
            gen = int(row["revision"])
            cid = row.get("root_cid")
            transition = row.get("transition_cid")
            if gen == 0 or cid is None:
                return CampaignStateSnapshot(
                    namespace=str(row["namespace"]),
                    state_cid=None,
                    generation=0,
                    transition_cid=None,
                    phase=None,
                    campaign_id=None,
                    execution_claim_status=None,
                    receipt_cid=None,
                )
            sealed = self.get_verified_campaign_state(str(cid))
            return CampaignStateSnapshot(
                namespace=str(row["namespace"]),
                state_cid=str(cid),
                generation=gen,
                transition_cid=None if transition is None else str(transition),
                phase=coerce_campaign_phase(str(sealed["phase"])),
                campaign_id=str(sealed["campaign_id"]),
                execution_claim_status=coerce_execution_claim_status(
                    str(sealed["execution_claim_status"])
                ),
                receipt_cid=sealed.get("receipt_cid"),
            )

        before = _snap(before_raw)
        after = _snap(after_raw)
        transition_cid = raw.get("transition_cid")
        if transition_cid is not None:
            try:
                transition_cid = validate_semantic_dag_json_cid(
                    transition_cid, "transition_cid"
                )
            except AssuranceArtifactStoreContractError as exc:
                raise CampaignIntegrityError(str(exc)) from exc
        reason_code = raw.get("reason_code")
        if not isinstance(reason_code, str):
            raise CampaignIntegrityError("reason_code must be a string")
        local_durable = bool(raw.get("local_durable"))
        wire_op = raw.get("operation_id", operation_id)
        if not isinstance(wire_op, str):
            wire_op = operation_id
        result_state_cid: str | None
        if status is AssuranceStoreStatus.UPDATED:
            result_state_cid = state_cid
        elif status is AssuranceStoreStatus.UNCHANGED:
            result_state_cid = after.state_cid
        else:
            result_state_cid = None
        return CampaignTransitionResult(
            status,
            before,
            after,
            result_state_cid,
            transition_cid,
            reason_code,
            local_durable,
            wire_op,
        )


# ---------------------------------------------------------------------------
# AssuranceGapRepository@1
# ---------------------------------------------------------------------------


class AssuranceGapRepository(Protocol):
    """Closed durable assurance-gap repository surface."""

    def persist_gap(
        self,
        workspace: str,
        payload: Mapping[str, Any],
        *,
        expected_cid: str,
        artifact_operation_id: str,
        history_operation_id: str,
        expected_history_generation: int,
        expected_history_head_cid: Optional[str],
        replicate: bool = False,
    ) -> GapPersistResult: ...


class DurableAssuranceGapRepository:
    """Durable assurance-gap artifacts and append-only gap histories.

    Implements ``AssuranceGapRepository@1``.
    """

    def __init__(
        self,
        store: DurableCoordinationStore,
        *,
        artifacts: DurableAssuranceArtifactStore | None = None,
    ) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store
        self._artifacts = artifacts or DurableAssuranceArtifactStore(store)
        self._owns_artifacts = artifacts is None
        self._history = _AssuranceHistoryCore(store)

    @property
    def store(self) -> DurableCoordinationStore:
        return self._store

    @property
    def artifacts(self) -> DurableAssuranceArtifactStore:
        return self._artifacts

    def close(self) -> None:
        if self._owns_artifacts:
            self._artifacts.close()

    def __enter__(self) -> "DurableAssuranceGapRepository":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def persist_gap(
        self,
        workspace: str,
        payload: Mapping[str, Any],
        *,
        expected_cid: str,
        artifact_operation_id: str,
        history_operation_id: str,
        expected_history_generation: int,
        expected_history_head_cid: Optional[str],
        replicate: bool = False,
    ) -> GapPersistResult:
        """Project, store, and history-append one assurance gap (fail closed)."""

        if not isinstance(payload, Mapping):
            raise CampaignAdmissionError("gap payload must be a mapping")

        try:
            sealed = seal_assurance_artifact(
                AssuranceArtifactKind.ASSURANCE_GAP,
                payload,
                enforce_signature_gate=False,
            )
            actual_cid = cid_for_assurance_artifact(
                AssuranceArtifactKind.ASSURANCE_GAP,
                sealed,
                enforce_signature_gate=False,
            )
            expected_cid = validate_semantic_dag_json_cid(expected_cid, "expected_cid")
        except AssuranceArtifactAdmissionError as exc:
            raise CampaignAdmissionError(str(exc)) from exc
        except AssuranceArtifactStoreContractError as exc:
            raise CampaignAdmissionError(str(exc)) from exc
        except AssuranceArtifactError as exc:
            raise CampaignAdmissionError(str(exc)) from exc

        if actual_cid != expected_cid:
            raise CampaignIntegrityError(
                f"forged or mismatched gap CID: computed {actual_cid}, "
                f"expected {expected_cid}"
            )

        try:
            artifact_result = self._artifacts.put_artifact(
                AssuranceArtifactKind.ASSURANCE_GAP,
                sealed,
                expected_cid=expected_cid,
                operation_id=artifact_operation_id,
                replicate=replicate,
            )
        except AssuranceArtifactAdmissionError as exc:
            raise CampaignAdmissionError(str(exc)) from exc
        except AssuranceArtifactConflictError as exc:
            raise CampaignConflictError(str(exc)) from exc
        except AssuranceArtifactError as exc:
            raise CampaignAdmissionError(str(exc)) from exc

        history = self._history.append_history(
            workspace,
            AssuranceNamespaceRole.GAPS,
            entry_cid=expected_cid,
            expected_generation=expected_history_generation,
            expected_head_cid=expected_history_head_cid,
            operation_id=history_operation_id,
        )
        return GapPersistResult(artifact_result, history, expected_cid)

    def current_gaps_history(self, workspace: str) -> HistoryHeadSnapshot:
        return self._history.current_history(workspace, AssuranceNamespaceRole.GAPS)

    def gap_history_entry_cids(
        self,
        workspace: str,
        *,
        offset: int = 0,
        limit: int = DEFAULT_HISTORY_PAGE_SIZE,
    ) -> list[str]:
        return self._history.list_entry_cids(
            workspace,
            AssuranceNamespaceRole.GAPS,
            offset=offset,
            limit=limit,
        )

    def get_verified_gap(self, cid: str) -> Mapping[str, Any]:
        try:
            return self._artifacts.get_verified_artifact(
                cid, expected_kind=AssuranceArtifactKind.ASSURANCE_GAP
            )
        except AssuranceArtifactNotFound as exc:
            raise CampaignIntegrityError(str(exc)) from exc
        except AssuranceArtifactError as exc:
            raise CampaignIntegrityError(str(exc)) from exc

    def append_gap_history(
        self,
        workspace: str,
        *,
        entry_cid: str,
        expected_generation: int,
        expected_head_cid: Optional[str],
        operation_id: str,
    ) -> HistoryAppendResult:
        return self._history.append_history(
            workspace,
            AssuranceNamespaceRole.GAPS,
            entry_cid=entry_cid,
            expected_generation=expected_generation,
            expected_head_cid=expected_head_cid,
            operation_id=operation_id,
        )


__all__ = [
    "CAMPAIGN_MODULE_INTERFACE",
    "GAP_MODULE_INTERFACE",
    "CAMPAIGN_STATE_INTERFACE",
    "CAMPAIGN_STATE_SCHEMA",
    "CAMPAIGN_HISTORY_MANIFEST_INTERFACE",
    "CAMPAIGN_HISTORY_MANIFEST_SCHEMA",
    "REQUIRED_RECEIPT_AUDIENCE",
    "DEFAULT_HISTORY_PAGE_SIZE",
    "MAX_HISTORY_PAGE_SIZE",
    "CampaignPhase",
    "ExecutionClaimStatus",
    "CampaignStoreError",
    "CampaignAdmissionError",
    "CampaignIntegrityError",
    "CampaignConflictError",
    "CampaignTransitionError",
    "CampaignStateSnapshot",
    "CampaignTransitionResult",
    "HistoryHeadSnapshot",
    "HistoryAppendResult",
    "ReceiptPersistResult",
    "GapPersistResult",
    "MutationCampaignRepository",
    "AssuranceGapRepository",
    "DurableMutationCampaignRepository",
    "DurableAssuranceGapRepository",
    "build_campaign_state",
    "cid_for_campaign_state",
    "admit_campaign_state",
    "build_history_manifest",
    "cid_for_history_manifest",
    "admit_campaign_receipt_payload",
    "validate_campaign_id",
    "validate_generation_expectation",
    "coerce_campaign_phase",
    "coerce_execution_claim_status",
    "campaign_phases",
    "execution_claim_statuses",
    "allowed_phase_transitions",
    "assert_phase_transition_allowed",
    "assert_terminal_success_admissible",
]
