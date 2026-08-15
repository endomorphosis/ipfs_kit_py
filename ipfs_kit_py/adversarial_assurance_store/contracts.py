"""Closed, inert contracts for the durable AssuranceArtifactStore protocol.

AAE-034 freezes the narrow immutable-artifact surface that later kit tasks
compose over ``DurableCoordinationStore``:

* closed assurance artifact kinds projected from the datasets catalog;
* typed projections that consume datasets schemas without redefining them;
* caller-supplied verified CIDs (never trusted without recomputation);
* operation-id idempotency keys;
* closed adversarial-assurance namespaces;
* typed provider / write outcomes.

This module owns only validation, wire representations, protocol shapes, and
projections into the existing datasets authorities.  It does not open a store,
mint content identities as an authority, invent envelopes, or introduce a
second signature scheme.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Final, Mapping, Optional, Protocol, TypeVar

from ipfs_datasets_py.logic.software_contracts.adversarial_assurance import (
    AssuranceCampaignReceipt,
    AssuranceGap,
    AssurancePolicyPromotionReceipt,
    CandidateAnalyzerRule,
    CandidatePolicyConstraint,
    CandidateProofObligation,
    CandidateTestSpecification,
    CapsuleAdequacyProfile,
    DetectionFailure,
    ExpectedDetectionSet,
    GapRemediationPlan,
    MutationCampaignPlan,
    MutationCampaignPolicy,
    MutationCandidate,
    MutationEquivalenceAssessment,
    MutationExecutionPlan,
    MutationExecutionReceipt,
    MutationOperatorDefinition,
    MutationOutcome,
    MutationTarget,
    PolicyAdequacyProfile,
    ProofAdequacyProfile,
    RemediationEvaluationReport,
    SurvivingMutantReport,
    TestAdequacyProfile,
    VacuityFinding,
    adversarial_assurance_artifact_catalog,
    require_verified_signature_before_persistence,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    validate_transport_cid,
)

# ---------------------------------------------------------------------------
# Schema / interface constants
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
ASSURANCE_ARTIFACT_STORE_INTERFACE: Final[str] = "AssuranceArtifactStore@1"
ASSURANCE_ARTIFACT_STORE_SCHEMA: Final[str] = (
    "ipfs-kit.adversarial-assurance-store.contracts@1"
)

ASSURANCE_NAMESPACE_PREFIX: Final[str] = "adversarial-assurance"
MAX_NAMESPACE_CHARS: Final[int] = 255
MAX_WORKSPACE_CHARS: Final[int] = 63
MAX_OPERATION_ID_CHARS: Final[int] = 128
MAX_REASON_CODE_CHARS: Final[int] = 64

# Canonical sealed record ceiling (dag-json bytes). Matches kit 1 MiB admission.
MAX_ARTIFACT_BYTES: Final[int] = 1_048_576

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


class AssuranceArtifactStoreContractError(ValueError):
    """Raised when an assurance-store contract value is malformed or incoherent."""


# ---------------------------------------------------------------------------
# Closed enumerations
# ---------------------------------------------------------------------------


class AssuranceArtifactKind(str, Enum):
    """Closed taxonomy of durable AAE payload kinds admitted by storage.

    Kind tokens are the datasets catalog ``artifact_kind`` values.  Payload
    schemas and identity rules remain owned by
    ``ipfs_datasets_py.logic.software_contracts.adversarial_assurance``.
    """

    MUTATION_OPERATOR_DEFINITION = "mutation_operator_definition"
    MUTATION_TARGET = "mutation_target"
    MUTATION_CANDIDATE = "mutation_candidate"
    MUTATION_CAMPAIGN_POLICY = "mutation_campaign_policy"
    MUTATION_CAMPAIGN_PLAN = "mutation_campaign_plan"
    EXPECTED_DETECTION_SET = "expected_detection_set"
    MUTATION_EXECUTION_PLAN = "mutation_execution_plan"
    MUTATION_EXECUTION_RECEIPT = "mutation_execution_receipt"
    MUTATION_OUTCOME = "mutation_outcome"
    MUTATION_EQUIVALENCE_ASSESSMENT = "mutation_equivalence_assessment"
    SURVIVING_MUTANT_REPORT = "surviving_mutant_report"
    ASSURANCE_GAP = "assurance_gap"
    VACUITY_FINDING = "vacuity_finding"
    DETECTION_FAILURE = "detection_failure"
    TEST_ADEQUACY_PROFILE = "test_adequacy_profile"
    PROOF_ADEQUACY_PROFILE = "proof_adequacy_profile"
    POLICY_ADEQUACY_PROFILE = "policy_adequacy_profile"
    CAPSULE_ADEQUACY_PROFILE = "capsule_adequacy_profile"
    CANDIDATE_TEST_SPECIFICATION = "candidate_test_specification"
    CANDIDATE_PROOF_OBLIGATION = "candidate_proof_obligation"
    CANDIDATE_POLICY_CONSTRAINT = "candidate_policy_constraint"
    CANDIDATE_ANALYZER_RULE = "candidate_analyzer_rule"
    GAP_REMEDIATION_PLAN = "gap_remediation_plan"
    REMEDIATION_EVALUATION_REPORT = "remediation_evaluation_report"
    ASSURANCE_CAMPAIGN_RECEIPT = "assurance_campaign_receipt"
    ASSURANCE_POLICY_PROMOTION_RECEIPT = "assurance_policy_promotion_receipt"


class AssuranceNamespaceRole(str, Enum):
    """Closed durable head/history roles under the assurance namespace prefix."""

    ARTIFACTS = "artifacts"
    CAMPAIGNS = "campaigns"
    GAPS = "gaps"
    RECEIPTS = "receipts"
    POLICY = "policy"
    PROMOTION = "promotion"
    MERKLE = "merkle"


class AssuranceStoreStatus(str, Enum):
    """Closed outcome set for assurance CAS, history, and head updates."""

    UPDATED = "updated"
    UNCHANGED = "unchanged"
    CONFLICT = "conflict"
    UNAVAILABLE = "unavailable"
    CORRUPT = "corrupt"


class AssuranceProviderStatus(str, Enum):
    """Truthful optional remote replication outcome for a durable write."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    CORRUPT = "corrupt"
    NOT_REQUESTED = "not_requested"


# Signed receipt kinds that must pass the datasets signature gate before any
# durable write, content addressing, Merkle inclusion, or seal eligibility.
_SIGNED_RECEIPT_KINDS: Final[frozenset[AssuranceArtifactKind]] = frozenset(
    {
        AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT,
        AssuranceArtifactKind.ASSURANCE_POLICY_PROMOTION_RECEIPT,
    }
)


# ---------------------------------------------------------------------------
# Datasets projection registry (consume, do not redefine)
# ---------------------------------------------------------------------------

_FromDict = Callable[[Mapping[str, Any]], Any]


def _catalog_kind_entries() -> Mapping[str, Mapping[str, Any]]:
    """Index datasets catalog rows that declare an artifact_kind."""

    rows: dict[str, Mapping[str, Any]] = {}
    for entry in adversarial_assurance_artifact_catalog():
        kind = entry.get("artifact_kind")
        if not isinstance(kind, str) or not kind:
            continue
        rows[kind] = entry
    return MappingProxyType(rows)


_CATALOG_BY_KIND: Final[Mapping[str, Mapping[str, Any]]] = _catalog_kind_entries()

# Loaders re-derive canonical records through datasets from_dict/to_dict.
_PAYLOAD_LOADERS: Final[Mapping[str, _FromDict]] = MappingProxyType(
    {
        AssuranceArtifactKind.MUTATION_OPERATOR_DEFINITION.value: (
            MutationOperatorDefinition.from_dict
        ),
        AssuranceArtifactKind.MUTATION_TARGET.value: MutationTarget.from_dict,
        AssuranceArtifactKind.MUTATION_CANDIDATE.value: MutationCandidate.from_dict,
        AssuranceArtifactKind.MUTATION_CAMPAIGN_POLICY.value: (
            MutationCampaignPolicy.from_dict
        ),
        AssuranceArtifactKind.MUTATION_CAMPAIGN_PLAN.value: (
            MutationCampaignPlan.from_dict
        ),
        AssuranceArtifactKind.EXPECTED_DETECTION_SET.value: (
            ExpectedDetectionSet.from_dict
        ),
        AssuranceArtifactKind.MUTATION_EXECUTION_PLAN.value: (
            MutationExecutionPlan.from_dict
        ),
        AssuranceArtifactKind.MUTATION_EXECUTION_RECEIPT.value: (
            MutationExecutionReceipt.from_dict
        ),
        AssuranceArtifactKind.MUTATION_OUTCOME.value: MutationOutcome.from_dict,
        AssuranceArtifactKind.MUTATION_EQUIVALENCE_ASSESSMENT.value: (
            MutationEquivalenceAssessment.from_dict
        ),
        AssuranceArtifactKind.SURVIVING_MUTANT_REPORT.value: (
            SurvivingMutantReport.from_dict
        ),
        AssuranceArtifactKind.ASSURANCE_GAP.value: AssuranceGap.from_dict,
        AssuranceArtifactKind.VACUITY_FINDING.value: VacuityFinding.from_dict,
        AssuranceArtifactKind.DETECTION_FAILURE.value: DetectionFailure.from_dict,
        AssuranceArtifactKind.TEST_ADEQUACY_PROFILE.value: (
            TestAdequacyProfile.from_dict
        ),
        AssuranceArtifactKind.PROOF_ADEQUACY_PROFILE.value: (
            ProofAdequacyProfile.from_dict
        ),
        AssuranceArtifactKind.POLICY_ADEQUACY_PROFILE.value: (
            PolicyAdequacyProfile.from_dict
        ),
        AssuranceArtifactKind.CAPSULE_ADEQUACY_PROFILE.value: (
            CapsuleAdequacyProfile.from_dict
        ),
        AssuranceArtifactKind.CANDIDATE_TEST_SPECIFICATION.value: (
            CandidateTestSpecification.from_dict
        ),
        AssuranceArtifactKind.CANDIDATE_PROOF_OBLIGATION.value: (
            CandidateProofObligation.from_dict
        ),
        AssuranceArtifactKind.CANDIDATE_POLICY_CONSTRAINT.value: (
            CandidatePolicyConstraint.from_dict
        ),
        AssuranceArtifactKind.CANDIDATE_ANALYZER_RULE.value: (
            CandidateAnalyzerRule.from_dict
        ),
        AssuranceArtifactKind.GAP_REMEDIATION_PLAN.value: (
            GapRemediationPlan.from_dict
        ),
        AssuranceArtifactKind.REMEDIATION_EVALUATION_REPORT.value: (
            RemediationEvaluationReport.from_dict
        ),
        AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT.value: (
            AssuranceCampaignReceipt.from_dict
        ),
        AssuranceArtifactKind.ASSURANCE_POLICY_PROMOTION_RECEIPT.value: (
            AssurancePolicyPromotionReceipt.from_dict
        ),
    }
)


def _assert_projection_registry_closed() -> None:
    kinds = {kind.value for kind in AssuranceArtifactKind}
    catalog_kinds = set(_CATALOG_BY_KIND)
    loader_kinds = set(_PAYLOAD_LOADERS)
    if kinds != catalog_kinds:
        raise RuntimeError(
            "AssuranceArtifactKind must match datasets catalog artifact_kind set: "
            f"missing={sorted(catalog_kinds - kinds)} "
            f"extra={sorted(kinds - catalog_kinds)}"
        )
    if kinds != loader_kinds:
        raise RuntimeError(
            "payload loaders must cover every AssuranceArtifactKind: "
            f"missing={sorted(kinds - loader_kinds)} "
            f"extra={sorted(loader_kinds - kinds)}"
        )


_assert_projection_registry_closed()


# ---------------------------------------------------------------------------
# Primitive validators
# ---------------------------------------------------------------------------


def _closed_mapping(
    value: object, fields: frozenset[str], name: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AssuranceArtifactStoreContractError(f"{name} must be a mapping")
    actual = frozenset(value)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        problems: list[str] = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        raise AssuranceArtifactStoreContractError(
            f"{name} has " + "; ".join(problems)
        )
    return value


def _require_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise AssuranceArtifactStoreContractError(f"{name} must be a boolean")
    return value


def _status(value: object, enum: type[_T], name: str) -> _T:
    if not isinstance(value, enum):
        raise AssuranceArtifactStoreContractError(
            f"{name} must be a {enum.__name__}"
        )
    return value


def validate_assurance_workspace(workspace: object) -> str:
    """Validate a single workspace segment used inside closed assurance namespaces."""

    if not isinstance(workspace, str) or not workspace:
        raise AssuranceArtifactStoreContractError(
            "workspace must be a non-empty normalized string"
        )
    if len(workspace) > MAX_WORKSPACE_CHARS:
        raise AssuranceArtifactStoreContractError(
            f"workspace must be at most {MAX_WORKSPACE_CHARS} characters"
        )
    if workspace != workspace.strip() or not _WORKSPACE.fullmatch(workspace):
        raise AssuranceArtifactStoreContractError(
            "workspace must be a normalized lowercase segment"
        )
    return workspace


def validate_assurance_namespace(namespace: object) -> str:
    """Validate a full namespace against the DurableCoordinationStore grammar."""

    if not isinstance(namespace, str) or not namespace:
        raise AssuranceArtifactStoreContractError(
            "namespace must be a non-empty normalized string"
        )
    if len(namespace) > MAX_NAMESPACE_CHARS:
        raise AssuranceArtifactStoreContractError(
            f"namespace must be at most {MAX_NAMESPACE_CHARS} characters"
        )
    if namespace != namespace.strip() or "//" in namespace:
        raise AssuranceArtifactStoreContractError("namespace must be normalized")
    segments = namespace.split("/")
    if not all(_NAMESPACE_SEGMENT.fullmatch(segment) for segment in segments):
        raise AssuranceArtifactStoreContractError(
            "namespace contains an invalid segment"
        )
    return namespace


def validate_operation_id(operation_id: object) -> str:
    """Validate an operation-id / idempotency key (length 1–128)."""

    if not isinstance(operation_id, str) or not _OPERATION_ID.fullmatch(
        operation_id
    ):
        raise AssuranceArtifactStoreContractError(
            "operation_id must be a normalized identifier of length 1–128"
        )
    if len(operation_id) > MAX_OPERATION_ID_CHARS:
        raise AssuranceArtifactStoreContractError(
            f"operation_id must be at most {MAX_OPERATION_ID_CHARS} characters"
        )
    return operation_id


def validate_reason_code(reason_code: object) -> str:
    if not isinstance(reason_code, str) or not _REASON_CODE.fullmatch(reason_code):
        raise AssuranceArtifactStoreContractError(
            "reason_code must be a normalized lowercase token"
        )
    return reason_code


def validate_verified_cid(value: object, name: str = "cid") -> str:
    """Require a caller-supplied canonical transport CID spelling."""

    try:
        validate_transport_cid(value)
    except ValueError as exc:
        raise AssuranceArtifactStoreContractError(
            f"{name} must be a canonical transport CID"
        ) from exc
    return value  # type: ignore[return-value]


def validate_semantic_dag_json_cid(value: object, name: str = "cid") -> str:
    """Require a caller-owned canonical dag-json CID for structured artifacts."""

    cid = validate_verified_cid(value, name)
    if validate_transport_cid(cid) != "dag-json":
        raise AssuranceArtifactStoreContractError(
            f"{name} must be a canonical dag-json CID"
        )
    return cid


def assurance_namespace(
    workspace: str, role: AssuranceNamespaceRole | str
) -> str:
    """Build the closed ``adversarial-assurance/<workspace>/<role>`` namespace."""

    workspace_token = validate_assurance_workspace(workspace)
    if isinstance(role, AssuranceNamespaceRole):
        role_token = role.value
    elif isinstance(role, str):
        try:
            role_token = AssuranceNamespaceRole(role).value
        except ValueError as exc:
            raise AssuranceArtifactStoreContractError(
                f"unknown assurance namespace role: {role!r}"
            ) from exc
    else:
        raise AssuranceArtifactStoreContractError(
            "role must be an AssuranceNamespaceRole or its value"
        )
    namespace = f"{ASSURANCE_NAMESPACE_PREFIX}/{workspace_token}/{role_token}"
    return validate_assurance_namespace(namespace)


def parse_assurance_namespace(
    namespace: object,
) -> tuple[str, AssuranceNamespaceRole]:
    """Parse a closed assurance namespace into workspace and role."""

    text = validate_assurance_namespace(namespace)
    parts = text.split("/")
    if len(parts) != 3 or parts[0] != ASSURANCE_NAMESPACE_PREFIX:
        raise AssuranceArtifactStoreContractError(
            "namespace must be adversarial-assurance/<workspace>/<role>"
        )
    workspace = validate_assurance_workspace(parts[1])
    try:
        role = AssuranceNamespaceRole(parts[2])
    except ValueError as exc:
        raise AssuranceArtifactStoreContractError(
            f"unknown assurance namespace role: {parts[2]!r}"
        ) from exc
    return workspace, role


def coerce_assurance_artifact_kind(
    kind: AssuranceArtifactKind | str,
) -> AssuranceArtifactKind:
    """Coerce a closed kind token; unknown values fail closed."""

    if isinstance(kind, AssuranceArtifactKind):
        return kind
    if isinstance(kind, str):
        try:
            return AssuranceArtifactKind(kind)
        except ValueError as exc:
            raise AssuranceArtifactStoreContractError(
                f"unknown assurance artifact kind: {kind!r}"
            ) from exc
    raise AssuranceArtifactStoreContractError(
        "kind must be an AssuranceArtifactKind or its closed string value"
    )


def assurance_artifact_kinds() -> tuple[str, ...]:
    return tuple(kind.value for kind in AssuranceArtifactKind)


def assurance_namespace_roles() -> tuple[str, ...]:
    return tuple(role.value for role in AssuranceNamespaceRole)


def assurance_store_statuses() -> tuple[str, ...]:
    return tuple(status.value for status in AssuranceStoreStatus)


def is_signed_receipt_kind(kind: AssuranceArtifactKind | str) -> bool:
    """Return whether the kind is a signed campaign/promotion receipt."""

    return coerce_assurance_artifact_kind(kind) in _SIGNED_RECEIPT_KINDS


def signed_receipt_kinds() -> tuple[str, ...]:
    return tuple(sorted(kind.value for kind in _SIGNED_RECEIPT_KINDS))


def datasets_catalog_entry(
    kind: AssuranceArtifactKind | str,
) -> Mapping[str, Any]:
    """Return the datasets catalog row for a closed kind (read-only)."""

    artifact_kind = coerce_assurance_artifact_kind(kind)
    entry = _CATALOG_BY_KIND.get(artifact_kind.value)
    if entry is None:
        raise AssuranceArtifactStoreContractError(
            f"no datasets catalog entry for kind {artifact_kind.value!r}"
        )
    return entry


def datasets_schema_for_kind(kind: AssuranceArtifactKind | str) -> str:
    """Return the datasets-owned schema URI for a kind (never redefined here)."""

    schema = datasets_catalog_entry(kind).get("schema")
    if not isinstance(schema, str) or not schema:
        raise AssuranceArtifactStoreContractError(
            "datasets catalog entry is missing schema"
        )
    return schema


def datasets_interface_for_kind(kind: AssuranceArtifactKind | str) -> str:
    """Return the datasets-owned interface id for a kind."""

    interface_id = datasets_catalog_entry(kind).get("interface_id")
    if not isinstance(interface_id, str) or not interface_id:
        raise AssuranceArtifactStoreContractError(
            "datasets catalog entry is missing interface_id"
        )
    return interface_id


def require_verified_signature_gate(
    payload: Mapping[str, Any] | AssuranceCampaignReceipt | AssurancePolicyPromotionReceipt,
) -> str:
    """Gate signed receipts before durable write / content addressing / seal.

    Delegates entirely to the datasets
    ``require_verified_signature_before_persistence`` authority.
    """

    try:
        return require_verified_signature_before_persistence(payload)
    except Exception as exc:
        # Datasets receipt errors and type errors all fail closed at the gate.
        raise AssuranceArtifactStoreContractError(
            f"signature verification required before persistence: {exc}"
        ) from exc


def project_assurance_payload(
    kind: AssuranceArtifactKind | str,
    payload: Mapping[str, Any],
    *,
    enforce_signature_gate: bool = False,
) -> dict[str, Any]:
    """Re-derive a canonical datasets record for storage without redefining it.

    Loads the mapping through the datasets ``from_dict`` authority for the kind,
    optionally enforces the signed-receipt gate, and returns ``to_dict()`` so
    the sealed form is always the datasets-owned wire representation.
    """

    artifact_kind = coerce_assurance_artifact_kind(kind)
    if not isinstance(payload, Mapping):
        raise AssuranceArtifactStoreContractError("payload must be a mapping")

    expected_schema = datasets_schema_for_kind(artifact_kind)
    expected_interface = datasets_interface_for_kind(artifact_kind)
    claimed_schema = payload.get("schema")
    claimed_interface = payload.get("interface_id")
    if claimed_schema != expected_schema:
        raise AssuranceArtifactStoreContractError(
            f"payload schema must be the datasets schema for "
            f"{artifact_kind.value}: expected {expected_schema!r}, "
            f"got {claimed_schema!r}"
        )
    if claimed_interface != expected_interface:
        raise AssuranceArtifactStoreContractError(
            f"payload interface_id must be the datasets interface for "
            f"{artifact_kind.value}: expected {expected_interface!r}, "
            f"got {claimed_interface!r}"
        )

    header = payload.get("header")
    if isinstance(header, Mapping):
        header_kind = header.get("artifact_kind")
        if header_kind is not None and header_kind != artifact_kind.value:
            raise AssuranceArtifactStoreContractError(
                f"header.artifact_kind {header_kind!r} does not match "
                f"storage kind {artifact_kind.value!r}"
            )

    if enforce_signature_gate and artifact_kind in _SIGNED_RECEIPT_KINDS:
        require_verified_signature_gate(payload)

    loader = _PAYLOAD_LOADERS[artifact_kind.value]
    try:
        model = loader(dict(payload))
    except AssuranceArtifactStoreContractError:
        raise
    except Exception as exc:
        raise AssuranceArtifactStoreContractError(
            f"datasets projection failed for {artifact_kind.value}: {exc}"
        ) from exc

    try:
        sealed = model.to_dict()
    except Exception as exc:
        raise AssuranceArtifactStoreContractError(
            f"datasets re-seal failed for {artifact_kind.value}: {exc}"
        ) from exc

    if not isinstance(sealed, dict):
        raise AssuranceArtifactStoreContractError(
            "datasets to_dict must return a dict"
        )
    if sealed.get("schema") != expected_schema:
        raise AssuranceArtifactStoreContractError(
            "datasets re-seal produced an unexpected schema"
        )
    if sealed.get("interface_id") != expected_interface:
        raise AssuranceArtifactStoreContractError(
            "datasets re-seal produced an unexpected interface_id"
        )
    return sealed


# ---------------------------------------------------------------------------
# Wire / value records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AssuranceArtifactWriteResult:
    """Verified immutable artifact write with independent local/remote facts."""

    cid: str
    kind: AssuranceArtifactKind
    local_durable: bool
    provider_status: AssuranceProviderStatus
    replicated: bool
    reason_code: str

    def __post_init__(self) -> None:
        validate_verified_cid(self.cid, "cid")
        _status(self.kind, AssuranceArtifactKind, "kind")
        _require_bool(self.local_durable, "local_durable")
        _status(self.provider_status, AssuranceProviderStatus, "provider_status")
        _require_bool(self.replicated, "replicated")
        validate_reason_code(self.reason_code)
        if not self.local_durable:
            raise AssuranceArtifactStoreContractError(
                "an artifact result cannot claim success without local durability"
            )
        if self.replicated != (
            self.provider_status is AssuranceProviderStatus.AVAILABLE
        ):
            raise AssuranceArtifactStoreContractError(
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
    def from_dict(cls, value: Mapping[str, Any]) -> "AssuranceArtifactWriteResult":
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
            data["kind"] = AssuranceArtifactKind(data["kind"])
            data["provider_status"] = AssuranceProviderStatus(
                data["provider_status"]
            )
        except (TypeError, ValueError) as exc:
            raise AssuranceArtifactStoreContractError(
                "kind or provider_status is unknown"
            ) from exc
        return cls(**data)


# ---------------------------------------------------------------------------
# Protocol surface
# ---------------------------------------------------------------------------


class AssuranceArtifactStore(Protocol):
    """Closed durable assurance artifact store (``AssuranceArtifactStore@1``).

    Implementations must compose ``DurableCoordinationStore``.  Callers always
    supply verified CIDs and operation IDs.  Signed receipts are gated by the
    datasets signature authority before the first durable write or content
    addressing, and are re-projected and re-gated on verified read.
    """

    def put_artifact(
        self,
        kind: AssuranceArtifactKind,
        payload: Mapping[str, Any],
        *,
        expected_cid: str,
        operation_id: str,
        replicate: bool = True,
    ) -> AssuranceArtifactWriteResult: ...

    def get_verified_artifact(
        self,
        cid: str,
        *,
        expected_kind: Optional[AssuranceArtifactKind] = None,
    ) -> Mapping[str, Any]: ...


__all__ = [
    "CONTRACT_VERSION",
    "ASSURANCE_ARTIFACT_STORE_INTERFACE",
    "ASSURANCE_ARTIFACT_STORE_SCHEMA",
    "ASSURANCE_NAMESPACE_PREFIX",
    "MAX_NAMESPACE_CHARS",
    "MAX_WORKSPACE_CHARS",
    "MAX_OPERATION_ID_CHARS",
    "MAX_REASON_CODE_CHARS",
    "MAX_ARTIFACT_BYTES",
    "AssuranceArtifactStoreContractError",
    "AssuranceArtifactKind",
    "AssuranceNamespaceRole",
    "AssuranceStoreStatus",
    "AssuranceProviderStatus",
    "AssuranceArtifactWriteResult",
    "AssuranceArtifactStore",
    "validate_assurance_workspace",
    "validate_assurance_namespace",
    "validate_operation_id",
    "validate_reason_code",
    "validate_verified_cid",
    "validate_semantic_dag_json_cid",
    "assurance_namespace",
    "parse_assurance_namespace",
    "coerce_assurance_artifact_kind",
    "assurance_artifact_kinds",
    "assurance_namespace_roles",
    "assurance_store_statuses",
    "is_signed_receipt_kind",
    "signed_receipt_kinds",
    "datasets_catalog_entry",
    "datasets_schema_for_kind",
    "datasets_interface_for_kind",
    "require_verified_signature_gate",
    "project_assurance_payload",
]
