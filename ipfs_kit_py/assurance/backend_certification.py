"""Backend certification suite generator (FACP-053).

Deterministically synthesizes BackendContract-driven test / model / fault /
receipt artifacts for the first-program cohort:

* local durable filesystem
* pinned IPFS daemon configuration
* Iroh

Fail-closed invariants:

* Hermetic generation never contacts a live backend.
* Absent live runner yields Conditional or Unavailable evidence with reasons.
* LiveQualified requires a **complete** observed suite under a live runner;
  partial, hermetic, configured, or fixture observations cannot promote.
* Unlisted backends are rejected; credentials are never stored.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Final, Iterable, Mapping, Optional, Sequence

SCHEMA: Final[str] = "BackendCertificationSuite@1"
SCHEMA_VERSION: Final[str] = "ipfs_kit_py.assurance.backend_certification@1"
RECEIPT_SCHEMA: Final[str] = "BackendCertificationReceipt@1"
SUPPORT_ROW_SCHEMA: Final[str] = "BackendSupportRow@1"
TASK_ID: Final[str] = "FACP-053"
GOAL_ID: Final[str] = "FACP-G520"
EVIDENCE_BUNDLE: Final[str] = "facp/backend-suite@1"
FCA_RELEASE: Final[str] = "formal-claim-algebra-v1"
FCA_VOCABULARY_SCHEMA: Final[str] = "facp/formal-claim-algebra-v1@1"
UNSAFE_PROMOTION: Final[bool] = False

CLOSED_OUTCOME_UNAVAILABLE: Final[str] = "Unavailable"
CLOSED_OUTCOME_OBSERVED: Final[str] = "Observed"
CLOSED_OUTCOME_VERIFIED: Final[str] = "Verified"

# Evidence-subset operations required by FACP-053 / FACP-G520.
REQUIRED_SUITE_OPERATIONS: Final[tuple[str, ...]] = (
    "write",
    "read_back",
    "digest",
    "delete",
    "replay",
    "timeout",
    "concurrency",
    "restart",
    "corruption",
    "large_object",
    "credential",
    "interface_parity",
)

# Metadata dimensions that every generated suite / receipt must bind.
REQUIRED_EVIDENCE_BINDINGS: Final[tuple[str, ...]] = (
    "environment",
    "source",
    "signature",
    "freshness",
)

# First-program cohort (plan BCS gate). Inventory aliases normalize here.
COHORT_BACKEND_IDS: Final[tuple[str, ...]] = (
    "local_filesystem",
    "pinned_ipfs",
    "iroh",
)

_BACKEND_ALIASES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "local_filesystem": "local_filesystem",
        "filesystem": "local_filesystem",
        "local": "local_filesystem",
        "local_fs": "local_filesystem",
        "local-fs": "local_filesystem",
        "local_storage": "local_filesystem",
        "local-storage": "local_filesystem",
        "pinned_ipfs": "pinned_ipfs",
        "ipfs": "pinned_ipfs",
        "kubo": "pinned_ipfs",
        "iroh": "iroh",
    }
)


class BackendCertificationError(ValueError):
    """Malformed certification generator input."""


class BackendCertificationRejected(RuntimeError):
    """Typed rejection: certification cannot promote to LiveQualified.

    Carries the evaluation result. Never implies live qualification or that
    a credential / configuration alone was enough.
    """

    def __init__(self, result: "CertificationResult") -> None:
        if result.disposition is CertificationDisposition.LIVE_QUALIFIED:
            raise BackendCertificationError(
                "BackendCertificationRejected forbids LiveQualified results"
            )
        self.result = result
        self.disposition = result.disposition
        self.closed_outcome = result.closed_outcome
        message = (
            result.message
            or f"backend certification rejected: {result.disposition.value}"
        )
        super().__init__(message)


class CertificationDisposition(str, Enum):
    """Closed certification dispositions (acceptance vocabulary)."""

    LIVE_QUALIFIED = "LiveQualified"
    CONDITIONAL = "Conditional"
    UNAVAILABLE = "Unavailable"


class SuiteCaseKind(str, Enum):
    """Generated artifact kinds (allowed effects: test/model/fault/receipt)."""

    TEST = "test"
    MODEL = "model"
    FAULT = "fault"
    RECEIPT = "receipt"


class ObservationStatus(str, Enum):
    """Per-operation observation outcomes under a live runner."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    UNOBSERVED = "unobserved"


@dataclass(frozen=True, slots=True)
class BackendContract:
    """Declarative BackendContract used as the sole suite generation input."""

    backend_id: str
    display_name: str
    inventory_names: tuple[str, ...]
    capabilities: tuple[str, ...]
    interfaces: tuple[str, ...]
    durability: str
    credential_policy: str
    requires_live_daemon: bool
    allowed_environments: tuple[str, ...]
    prohibited_effects: tuple[str, ...] = (
        "store_credential",
        "configuration_to_live_promotion",
        "certify_unlisted_backend",
        "live_call_in_unit_test",
    )
    attributes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.backend_id not in COHORT_BACKEND_IDS:
            raise BackendCertificationError(
                f"backend_id {self.backend_id!r} is not in the first-program cohort"
            )
        if not self.display_name.strip():
            raise BackendCertificationError("display_name must be non-empty")
        if not self.inventory_names:
            raise BackendCertificationError("inventory_names must be non-empty")
        if not self.capabilities:
            raise BackendCertificationError("capabilities must be non-empty")
        if not self.interfaces:
            raise BackendCertificationError("interfaces must be non-empty")
        if not isinstance(self.attributes, MappingProxyType):
            if not isinstance(self.attributes, Mapping):
                raise BackendCertificationError("attributes must be a mapping")
            object.__setattr__(
                self,
                "attributes",
                MappingProxyType({str(k): str(v) for k, v in self.attributes.items()}),
            )

    def with_overrides(self, **overrides: Any) -> "BackendContract":
        return replace(self, **overrides)


@dataclass(frozen=True, slots=True)
class SuiteCase:
    """One deterministically generated certification case."""

    case_id: str
    operation: str
    kind: SuiteCaseKind
    title: str
    model: Mapping[str, Any]
    fault_model: Mapping[str, Any]
    assertions: tuple[str, ...]
    interfaces: tuple[str, ...]
    requires_live_runner: bool
    binds: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.operation not in REQUIRED_SUITE_OPERATIONS:
            raise BackendCertificationError(
                f"operation {self.operation!r} is outside the required suite"
            )
        if not isinstance(self.kind, SuiteCaseKind):
            raise BackendCertificationError("kind must be SuiteCaseKind")
        for map_name in ("model", "fault_model", "binds"):
            raw = getattr(self, map_name)
            if isinstance(raw, MappingProxyType):
                continue
            if not isinstance(raw, Mapping):
                raise BackendCertificationError(f"{map_name} must be a mapping")
            object.__setattr__(
                self,
                map_name,
                MappingProxyType({str(k): raw[k] for k in raw}),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "operation": self.operation,
            "kind": self.kind.value,
            "title": self.title,
            "model": dict(self.model),
            "fault_model": dict(self.fault_model),
            "assertions": list(self.assertions),
            "interfaces": list(self.interfaces),
            "requires_live_runner": self.requires_live_runner,
            "binds": dict(self.binds),
        }


@dataclass(frozen=True, slots=True)
class CertificationSuite:
    """Deterministic suite synthesized from a BackendContract."""

    schema: str
    schema_version: str
    task_id: str
    goal_id: str
    evidence_bundle: str
    backend_id: str
    contract_digest: str
    suite_digest: str
    operations: tuple[str, ...]
    cases: tuple[SuiteCase, ...]
    receipt_schema: str
    evidence_bindings: tuple[str, ...]
    generated_at: str
    hermetic: bool = True
    live_calls: bool = False

    def __post_init__(self) -> None:
        if self.operations != REQUIRED_SUITE_OPERATIONS:
            raise BackendCertificationError(
                "suite operations must equal REQUIRED_SUITE_OPERATIONS exactly"
            )
        if len(self.cases) < len(REQUIRED_SUITE_OPERATIONS):
            raise BackendCertificationError(
                "suite must include at least one case per required operation"
            )
        observed_ops = {case.operation for case in self.cases}
        missing = set(REQUIRED_SUITE_OPERATIONS) - observed_ops
        if missing:
            raise BackendCertificationError(
                f"suite missing required operations: {sorted(missing)}"
            )
        if self.live_calls:
            raise BackendCertificationError(
                "generated suites must not record live_calls=True"
            )
        if not self.hermetic:
            raise BackendCertificationError("generated suites must be hermetic")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "goal_id": self.goal_id,
            "evidence_bundle": self.evidence_bundle,
            "backend_id": self.backend_id,
            "contract_digest": self.contract_digest,
            "suite_digest": self.suite_digest,
            "operations": list(self.operations),
            "cases": [case.to_dict() for case in self.cases],
            "receipt_schema": self.receipt_schema,
            "evidence_bindings": list(self.evidence_bindings),
            "generated_at": self.generated_at,
            "hermetic": self.hermetic,
            "live_calls": self.live_calls,
            "unsafe_promotion": UNSAFE_PROMOTION,
        }


@dataclass(frozen=True, slots=True)
class SupportRow:
    """One support-matrix row projected from contract + certification result."""

    schema: str
    backend_id: str
    display_name: str
    inventory_names: tuple[str, ...]
    inventory_tier: str
    live_tier: str
    disposition: CertificationDisposition
    storage_selectable: bool
    suite_complete: bool
    receipt_schema: str
    evidence_freshness: str
    evidence_status: str
    reason_codes: tuple[str, ...]
    operations_required: tuple[str, ...]
    operations_observed: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "backend_id": self.backend_id,
            "display_name": self.display_name,
            "inventory_names": list(self.inventory_names),
            "inventory_tier": self.inventory_tier,
            "live_tier": self.live_tier,
            "disposition": self.disposition.value,
            "storage_selectable": self.storage_selectable,
            "suite_complete": self.suite_complete,
            "receipt_schema": self.receipt_schema,
            "evidence_freshness": self.evidence_freshness,
            "evidence_status": self.evidence_status,
            "reason_codes": list(self.reason_codes),
            "operations_required": list(self.operations_required),
            "operations_observed": list(self.operations_observed),
            "certification_receipt_schema": RECEIPT_SCHEMA,
        }


@dataclass(frozen=True, slots=True)
class OperationObservation:
    """Observed result for one required suite operation."""

    operation: str
    status: ObservationStatus
    environment: str = "hermetic"
    source: str = "fixture"
    signature_valid: bool = False
    freshness: str = "missing"
    digests: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        if self.operation not in REQUIRED_SUITE_OPERATIONS:
            raise BackendCertificationError(
                f"observation operation {self.operation!r} is not required-suite"
            )
        if not isinstance(self.status, ObservationStatus):
            raise BackendCertificationError("status must be ObservationStatus")
        if not isinstance(self.signature_valid, bool):
            raise BackendCertificationError("signature_valid must be bool")
        if not isinstance(self.digests, MappingProxyType):
            if not isinstance(self.digests, Mapping):
                raise BackendCertificationError("digests must be a mapping")
            object.__setattr__(
                self,
                "digests",
                MappingProxyType({str(k): str(v) for k, v in self.digests.items()}),
            )
        if not isinstance(self.limitations, tuple) or any(
            not isinstance(item, str) for item in self.limitations
        ):
            raise BackendCertificationError("limitations must be tuple[str, ...]")


@dataclass(frozen=True, slots=True)
class CertificationResult:
    """Fail-closed evaluation of suite observations for one backend."""

    backend_id: str
    disposition: CertificationDisposition
    closed_outcome: str
    live_qualified: bool
    suite_complete: bool
    live_runner_present: bool
    reason_codes: tuple[str, ...]
    operations_required: tuple[str, ...]
    operations_observed: tuple[str, ...]
    operations_failed: tuple[str, ...]
    operations_missing: tuple[str, ...]
    receipt: Mapping[str, Any]
    support_row: SupportRow
    message: Optional[str] = None

    def __post_init__(self) -> None:
        if self.live_qualified and self.disposition is not (
            CertificationDisposition.LIVE_QUALIFIED
        ):
            raise BackendCertificationError(
                "live_qualified requires disposition=LiveQualified"
            )
        if (
            self.disposition is CertificationDisposition.LIVE_QUALIFIED
            and not self.suite_complete
        ):
            raise BackendCertificationError(
                "LiveQualified forbids incomplete observed suite"
            )
        if (
            self.disposition is CertificationDisposition.LIVE_QUALIFIED
            and not self.live_runner_present
        ):
            raise BackendCertificationError(
                "LiveQualified forbids absent live runner"
            )
        if not isinstance(self.receipt, MappingProxyType):
            if not isinstance(self.receipt, Mapping):
                raise BackendCertificationError("receipt must be a mapping")
            object.__setattr__(
                self,
                "receipt",
                MappingProxyType({str(k): self.receipt[k] for k in self.receipt}),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "disposition": self.disposition.value,
            "closed_outcome": self.closed_outcome,
            "live_qualified": self.live_qualified,
            "suite_complete": self.suite_complete,
            "live_runner_present": self.live_runner_present,
            "reason_codes": list(self.reason_codes),
            "operations_required": list(self.operations_required),
            "operations_observed": list(self.operations_observed),
            "operations_failed": list(self.operations_failed),
            "operations_missing": list(self.operations_missing),
            "receipt": dict(self.receipt),
            "support_row": self.support_row.to_dict(),
            "message": self.message,
            "unsafe_promotion": UNSAFE_PROMOTION,
        }


def _utc_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise BackendCertificationError("now must be timezone-aware")
    return now.astimezone(timezone.utc)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    payload = _canonical_json(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _reasons(*codes: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(code for code in codes if code))


def normalize_backend_id(name: str) -> str:
    """Map an inventory spelling onto the first-program cohort id."""

    if not isinstance(name, str) or not name.strip():
        raise BackendCertificationError("backend name must be a non-empty string")
    key = name.strip()
    try:
        return _BACKEND_ALIASES[key]
    except KeyError as exc:
        raise BackendCertificationError(
            f"backend {name!r} is not in the first-program certification cohort"
        ) from exc


def is_cohort_backend(name: str) -> bool:
    try:
        normalize_backend_id(name)
    except BackendCertificationError:
        return False
    return True


def receipt_schema() -> dict[str, Any]:
    """Deterministic BackendCertificationReceipt@1 schema document."""

    return {
        "schema": RECEIPT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "goal_id": GOAL_ID,
        "evidence_bundle": EVIDENCE_BUNDLE,
        "required_fields": [
            "schema",
            "receipt_id",
            "backend_id",
            "provider_type",
            "disposition",
            "live_qualified",
            "suite_complete",
            "operations_required",
            "operations_observed",
            "operations_failed",
            "environment",
            "source",
            "signature_valid",
            "freshness",
            "issued_at",
            "suite_digest",
            "contract_digest",
            "reason_codes",
            "hidden_fallback",
            "storage_selectable",
            "credentials_stored",
        ],
        "disposition_enum": [item.value for item in CertificationDisposition],
        "operations_enum": list(REQUIRED_SUITE_OPERATIONS),
        "evidence_bindings": list(REQUIRED_EVIDENCE_BINDINGS),
        "forbidden": [
            "store_credential",
            "configuration_to_live_promotion",
            "certify_unlisted_backend",
            "live_qualified_without_complete_suite",
            "live_qualified_without_live_runner",
            "generic_success_true",
        ],
        "closed_outcomes": [
            CLOSED_OUTCOME_UNAVAILABLE,
            CLOSED_OUTCOME_OBSERVED,
            CLOSED_OUTCOME_VERIFIED,
        ],
    }


def cohort_contracts() -> tuple[BackendContract, ...]:
    """Return the deterministic first-program BackendContract set."""

    return (
        BackendContract(
            backend_id="local_filesystem",
            display_name="Local durable filesystem",
            inventory_names=("filesystem", "local", "local_fs", "local_storage"),
            capabilities=("configuration", "health", "storage", "durability"),
            interfaces=("python", "cli", "mcp", "mcpp"),
            durability="local-durable",
            credential_policy="none-required; secret material rejected",
            requires_live_daemon=False,
            allowed_environments=("hermetic", "live"),
            attributes={
                "cohort_role": "local_reference",
                "daemon": "none",
            },
        ),
        BackendContract(
            backend_id="pinned_ipfs",
            display_name="Pinned IPFS daemon configuration",
            inventory_names=("ipfs", "kubo"),
            capabilities=("configuration", "health", "storage"),
            interfaces=("python", "cli", "mcp", "mcpp"),
            durability="pinned-daemon",
            credential_policy="authorized secret references only; never retained",
            requires_live_daemon=True,
            allowed_environments=("live", "conditional"),
            attributes={
                "cohort_role": "pinned_ipfs",
                "daemon": "kubo",
            },
        ),
        BackendContract(
            backend_id="iroh",
            display_name="Iroh",
            inventory_names=("iroh",),
            capabilities=(
                "configuration",
                "health",
                "runtime_factory",
                "storage",
            ),
            interfaces=("python", "cli", "mcp", "mcpp"),
            durability="content-addressed",
            credential_policy="authorized secret references only; never retained",
            requires_live_daemon=True,
            allowed_environments=("live", "conditional"),
            attributes={
                "cohort_role": "iroh",
                "daemon": "iroh",
                "runtime_factory": "create_filesystem",
            },
        ),
    )


def contract_for(backend_name: str) -> BackendContract:
    backend_id = normalize_backend_id(backend_name)
    for contract in cohort_contracts():
        if contract.backend_id == backend_id:
            return contract
    raise BackendCertificationError(f"no contract for backend {backend_name!r}")


def contract_digest(contract: BackendContract) -> str:
    payload = {
        "backend_id": contract.backend_id,
        "display_name": contract.display_name,
        "inventory_names": list(contract.inventory_names),
        "capabilities": list(contract.capabilities),
        "interfaces": list(contract.interfaces),
        "durability": contract.durability,
        "credential_policy": contract.credential_policy,
        "requires_live_daemon": contract.requires_live_daemon,
        "allowed_environments": list(contract.allowed_environments),
        "prohibited_effects": list(contract.prohibited_effects),
        "attributes": dict(contract.attributes),
    }
    return _digest(payload)


def _case_bindings(contract: BackendContract, operation: str) -> dict[str, str]:
    return {
        "environment": "hermetic_generation",
        "source": f"BackendContract:{contract.backend_id}",
        "signature": "unsigned_generator_artifact",
        "freshness": "current_tree",
        "operation": operation,
        "backend_id": contract.backend_id,
    }


def _operation_models(operation: str) -> tuple[dict[str, Any], dict[str, Any], tuple[str, ...]]:
    """Return (model, fault_model, assertions) for a required operation."""

    catalog: dict[str, tuple[dict[str, Any], dict[str, Any], tuple[str, ...]]] = {
        "write": (
            {"effect": "put", "idempotency": "required", "payload_class": "small"},
            {"inject": "disk_full", "expect": "Failed"},
            ("bytes_persisted", "cid_or_path_returned", "no_partial_commit"),
        ),
        "read_back": (
            {"effect": "get", "after": "write", "consistency": "read_your_writes"},
            {"inject": "missing_object", "expect": "Failed"},
            ("bytes_match_write", "identity_stable"),
        ),
        "digest": (
            {"effect": "digest", "algorithm": "content_address", "bind": "bytes"},
            {"inject": "digest_mismatch", "expect": "Failed"},
            ("digest_recomputes", "mismatch_rejects"),
        ),
        "delete": (
            {"effect": "delete", "idempotent": True},
            {"inject": "delete_tombstone_race", "expect": "Compensated_or_Failed"},
            ("absent_after_delete", "replay_delete_safe"),
        ),
        "replay": (
            {"effect": "replay", "idempotency_key": "required"},
            {"inject": "duplicate_mutation", "expect": "no_double_effect"},
            ("same_key_same_result", "effect_count_stable"),
        ),
        "timeout": (
            {"effect": "bounded_deadline", "timeout_seconds": 5},
            {"inject": "hang", "expect": "Unavailable"},
            ("deadline_honored", "no_unbounded_wait"),
        ),
        "concurrency": (
            {"effect": "parallel_ops", "workers": 4, "bounded": True},
            {"inject": "lost_update", "expect": "Rejected_or_serializable"},
            ("no_corruption", "bounded_parallelism"),
        ),
        "restart": (
            {"effect": "process_restart", "durability": "required"},
            {"inject": "kill_mid_write", "expect": "recover_or_Failed"},
            ("durable_after_restart", "no_silent_loss"),
        ),
        "corruption": (
            {"effect": "integrity_check", "on": "read"},
            {"inject": "bit_flip", "expect": "Failed"},
            ("tamper_detected", "no_false_success"),
        ),
        "large_object": (
            {"effect": "put_get", "payload_class": "large", "streaming": True},
            {"inject": "truncated_stream", "expect": "Failed"},
            ("stream_integrity", "size_matches"),
        ),
        "credential": (
            {"effect": "credential_boundary", "refs_only": True},
            {"inject": "raw_secret", "expect": "Rejected"},
            ("raw_secret_rejected", "secret_absent_from_receipts"),
        ),
        "interface_parity": (
            {
                "effect": "parity",
                "surfaces": ["python", "cli", "mcp", "mcpp"],
                "strip_transport_fields": True,
            },
            {"inject": "surface_drift", "expect": "Rejected"},
            ("results_match", "errors_match", "cids_match"),
        ),
    }
    try:
        return catalog[operation]
    except KeyError as exc:
        raise BackendCertificationError(f"no model for operation {operation!r}") from exc


def _cases_for_operation(
    contract: BackendContract, operation: str
) -> tuple[SuiteCase, ...]:
    model, fault_model, assertions = _operation_models(operation)
    binds = _case_bindings(contract, operation)
    base_id = f"{contract.backend_id}:{operation}"
    test_case = SuiteCase(
        case_id=f"{base_id}:test",
        operation=operation,
        kind=SuiteCaseKind.TEST,
        title=f"{contract.display_name} {operation} conformance test",
        model=model,
        fault_model={},
        assertions=assertions,
        interfaces=contract.interfaces,
        requires_live_runner=True,
        binds=binds,
    )
    model_case = SuiteCase(
        case_id=f"{base_id}:model",
        operation=operation,
        kind=SuiteCaseKind.MODEL,
        title=f"{contract.display_name} {operation} reference model",
        model=model,
        fault_model={},
        assertions=assertions,
        interfaces=contract.interfaces,
        requires_live_runner=False,
        binds=binds,
    )
    fault_case = SuiteCase(
        case_id=f"{base_id}:fault",
        operation=operation,
        kind=SuiteCaseKind.FAULT,
        title=f"{contract.display_name} {operation} fault injection",
        model=model,
        fault_model=fault_model,
        assertions=assertions + ("fault_typed_outcome",),
        interfaces=contract.interfaces,
        requires_live_runner=True,
        binds=binds,
    )
    receipt_case = SuiteCase(
        case_id=f"{base_id}:receipt",
        operation=operation,
        kind=SuiteCaseKind.RECEIPT,
        title=f"{contract.display_name} {operation} receipt binding",
        model={"receipt_schema": RECEIPT_SCHEMA, "binds": list(REQUIRED_EVIDENCE_BINDINGS)},
        fault_model={},
        assertions=("receipt_fields_present", "no_credential_material"),
        interfaces=contract.interfaces,
        requires_live_runner=False,
        binds=binds,
    )
    return (test_case, model_case, fault_case, receipt_case)


def generate_suite(
    contract: BackendContract,
    *,
    now: datetime | None = None,
) -> CertificationSuite:
    """Deterministically generate the full certification suite for ``contract``."""

    if not isinstance(contract, BackendContract):
        raise BackendCertificationError("contract must be BackendContract")
    reference = _utc_now(now)
    cases: list[SuiteCase] = []
    for operation in REQUIRED_SUITE_OPERATIONS:
        cases.extend(_cases_for_operation(contract, operation))
    c_digest = contract_digest(contract)
    suite = CertificationSuite(
        schema=SCHEMA,
        schema_version=SCHEMA_VERSION,
        task_id=TASK_ID,
        goal_id=GOAL_ID,
        evidence_bundle=EVIDENCE_BUNDLE,
        backend_id=contract.backend_id,
        contract_digest=c_digest,
        suite_digest="",  # filled below after payload freeze
        operations=REQUIRED_SUITE_OPERATIONS,
        cases=tuple(cases),
        receipt_schema=RECEIPT_SCHEMA,
        evidence_bindings=REQUIRED_EVIDENCE_BINDINGS,
        generated_at=reference.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        hermetic=True,
        live_calls=False,
    )
    digest_payload = {
        "backend_id": suite.backend_id,
        "contract_digest": suite.contract_digest,
        "operations": list(suite.operations),
        "cases": [case.to_dict() for case in suite.cases],
        "receipt_schema": suite.receipt_schema,
        "evidence_bindings": list(suite.evidence_bindings),
    }
    return replace(suite, suite_digest=_digest(digest_payload))


def generate_cohort_suites(
    *, now: datetime | None = None
) -> dict[str, CertificationSuite]:
    """Generate hermetic suites for every first-program cohort backend."""

    reference = _utc_now(now)
    return {
        contract.backend_id: generate_suite(contract, now=reference)
        for contract in cohort_contracts()
    }


def build_receipt(
    contract: BackendContract,
    *,
    disposition: CertificationDisposition,
    live_qualified: bool,
    suite_complete: bool,
    operations_observed: Sequence[str],
    operations_failed: Sequence[str],
    reason_codes: Sequence[str],
    suite: CertificationSuite | None = None,
    environment: str,
    source: str,
    signature_valid: bool,
    freshness: str,
    live_runner_present: bool,
    now: datetime | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """Build a sanitized BackendCertificationReceipt@1 document."""

    reference = _utc_now(now)
    suite_obj = suite or generate_suite(contract, now=reference)
    if live_qualified and not suite_complete:
        raise BackendCertificationError(
            "cannot mint LiveQualified receipt without complete observed suite"
        )
    if live_qualified and not live_runner_present:
        raise BackendCertificationError(
            "cannot mint LiveQualified receipt without live runner"
        )
    receipt_id = (
        f"facp-053-{contract.backend_id}-"
        f"{disposition.value.lower()}-{suite_obj.suite_digest[-12:]}"
    )
    return {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": receipt_id,
        "backend_id": contract.backend_id,
        "provider_type": contract.backend_id,
        "display_name": contract.display_name,
        "disposition": disposition.value,
        "live_qualified": live_qualified,
        "suite_complete": suite_complete,
        "operations_required": list(REQUIRED_SUITE_OPERATIONS),
        "operations_observed": list(operations_observed),
        "operations_failed": list(operations_failed),
        "environment": environment,
        "source": source,
        "signature_valid": signature_valid,
        "freshness": freshness,
        "issued_at": reference.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "suite_digest": suite_obj.suite_digest,
        "contract_digest": suite_obj.contract_digest,
        "reason_codes": list(_reasons(*reason_codes)),
        "hidden_fallback": False,
        "storage_selectable": bool(
            live_qualified and disposition is CertificationDisposition.LIVE_QUALIFIED
        ),
        "credentials_stored": False,
        "live_runner_present": live_runner_present,
        "message": message,
        "task_id": TASK_ID,
        "goal_id": GOAL_ID,
        "evidence_bundle": EVIDENCE_BUNDLE,
        "unsafe_promotion": UNSAFE_PROMOTION,
    }


def build_support_row(
    contract: BackendContract,
    *,
    disposition: CertificationDisposition,
    suite_complete: bool,
    operations_observed: Sequence[str],
    reason_codes: Sequence[str],
    evidence_freshness: str,
    evidence_status: str,
    inventory_tier: str | None = None,
) -> SupportRow:
    """Project a support-matrix row from contract + evaluation outcome."""

    live_tier = {
        CertificationDisposition.LIVE_QUALIFIED: "production",
        CertificationDisposition.CONDITIONAL: "conditional",
        CertificationDisposition.UNAVAILABLE: "unavailable",
    }[disposition]
    tier = inventory_tier or (
        "conditional" if contract.requires_live_daemon else "conditional"
    )
    return SupportRow(
        schema=SUPPORT_ROW_SCHEMA,
        backend_id=contract.backend_id,
        display_name=contract.display_name,
        inventory_names=contract.inventory_names,
        inventory_tier=tier,
        live_tier=live_tier,
        disposition=disposition,
        storage_selectable=disposition is CertificationDisposition.LIVE_QUALIFIED,
        suite_complete=suite_complete,
        receipt_schema=RECEIPT_SCHEMA,
        evidence_freshness=evidence_freshness,
        evidence_status=evidence_status,
        reason_codes=_reasons(*reason_codes),
        operations_required=REQUIRED_SUITE_OPERATIONS,
        operations_observed=tuple(operations_observed),
    )


def absent_live_runner_result(
    contract: BackendContract,
    *,
    now: datetime | None = None,
    suite: CertificationSuite | None = None,
) -> CertificationResult:
    """Evidence product when no live runner is available.

    Yields Conditional for cohort backends (certification remains possible
    once a runner is authorized) with closed outcome Unavailable — never
    LiveQualified.
    """

    reference = _utc_now(now)
    suite_obj = suite or generate_suite(contract, now=reference)
    reasons = _reasons(
        "live_runner_absent",
        "hermetic_generation_only",
        "live_qualified_requires_complete_observed_suite",
        "configuration_is_not_live_qualification",
    )
    disposition = CertificationDisposition.CONDITIONAL
    if contract.requires_live_daemon:
        # Daemon-backed targets without a runner are explicitly Unavailable
        # as live evidence, while remaining Conditional in the support matrix
        # inventory sense via reason codes.
        disposition = CertificationDisposition.UNAVAILABLE
        reasons = _reasons(
            "live_runner_absent",
            "daemon_required",
            "live_evidence_unavailable",
            "live_qualified_requires_complete_observed_suite",
            *reasons,
        )
    support = build_support_row(
        contract,
        disposition=(
            CertificationDisposition.CONDITIONAL
            if disposition is CertificationDisposition.UNAVAILABLE
            else disposition
        ),
        suite_complete=False,
        operations_observed=(),
        reason_codes=reasons,
        evidence_freshness="missing",
        evidence_status="runner_absent",
    )
    # Support row stays Conditional (honest inventory); result disposition
    # distinguishes Unavailable live evidence for daemon backends.
    if disposition is CertificationDisposition.UNAVAILABLE:
        support = replace(
            support,
            disposition=CertificationDisposition.CONDITIONAL,
            live_tier="conditional",
            storage_selectable=False,
            evidence_status="runner_absent",
        )
    receipt = build_receipt(
        contract,
        disposition=disposition,
        live_qualified=False,
        suite_complete=False,
        operations_observed=(),
        operations_failed=(),
        reason_codes=reasons,
        suite=suite_obj,
        environment="conditional" if contract.requires_live_daemon else "hermetic",
        source="generator_absent_runner",
        signature_valid=False,
        freshness="missing",
        live_runner_present=False,
        now=reference,
        message="live runner absent; Conditional/Unavailable evidence only",
    )
    return CertificationResult(
        backend_id=contract.backend_id,
        disposition=disposition,
        closed_outcome=CLOSED_OUTCOME_UNAVAILABLE,
        live_qualified=False,
        suite_complete=False,
        live_runner_present=False,
        reason_codes=reasons,
        operations_required=REQUIRED_SUITE_OPERATIONS,
        operations_observed=(),
        operations_failed=(),
        operations_missing=REQUIRED_SUITE_OPERATIONS,
        receipt=receipt,
        support_row=support,
        message=receipt["message"],
    )


def _index_observations(
    observations: Sequence[OperationObservation],
) -> dict[str, OperationObservation]:
    indexed: dict[str, OperationObservation] = {}
    for item in observations:
        if not isinstance(item, OperationObservation):
            raise BackendCertificationError(
                "observations must be OperationObservation instances"
            )
        if item.operation in indexed:
            raise BackendCertificationError(
                f"duplicate observation for operation {item.operation!r}"
            )
        indexed[item.operation] = item
    return indexed


def evaluate_observations(
    contract: BackendContract,
    observations: Sequence[OperationObservation],
    *,
    live_runner_present: bool,
    now: datetime | None = None,
    suite: CertificationSuite | None = None,
) -> CertificationResult:
    """Evaluate observations. LiveQualified only on complete live suite.

    Without a live runner, delegates to :func:`absent_live_runner_result`.
    Incomplete, failed, non-live, unsigned, or stale observations cannot
    produce LiveQualified.
    """

    if not isinstance(contract, BackendContract):
        raise BackendCertificationError("contract must be BackendContract")
    reference = _utc_now(now)
    suite_obj = suite or generate_suite(contract, now=reference)

    if not live_runner_present:
        if observations:
            # Observations without a live runner cannot be treated as live.
            # Fold into absent-runner Conditional/Unavailable path and annotate.
            base = absent_live_runner_result(
                contract, now=reference, suite=suite_obj
            )
            reasons = _reasons(
                "observations_without_live_runner_ignored",
                *base.reason_codes,
            )
            return replace(
                base,
                reason_codes=reasons,
                message=(
                    "observations supplied without live runner; "
                    "Conditional/Unavailable evidence only"
                ),
            )
        return absent_live_runner_result(contract, now=reference, suite=suite_obj)

    indexed = _index_observations(observations)
    observed_passed: list[str] = []
    failed: list[str] = []
    missing: list[str] = []
    reasons: list[str] = []

    for operation in REQUIRED_SUITE_OPERATIONS:
        item = indexed.get(operation)
        if item is None or item.status is ObservationStatus.UNOBSERVED:
            missing.append(operation)
            continue
        if item.status in {ObservationStatus.SKIPPED, ObservationStatus.BLOCKED}:
            missing.append(operation)
            reasons.append(f"operation_{operation}_{item.status.value}")
            continue
        if item.status is ObservationStatus.FAILED:
            failed.append(operation)
            reasons.append(f"operation_{operation}_failed")
            continue
        if item.status is not ObservationStatus.PASSED:
            missing.append(operation)
            reasons.append(f"operation_{operation}_not_passed")
            continue

        # Live qualification requires live environment + valid signature + current.
        if item.environment != "live":
            missing.append(operation)
            reasons.append(f"operation_{operation}_environment_not_live")
            continue
        if item.source in {"fixture", "simulated", "declared", "hermetic", "configured"}:
            missing.append(operation)
            reasons.append(f"operation_{operation}_source_not_live_observed")
            continue
        if item.source != "live_observed":
            missing.append(operation)
            reasons.append(f"operation_{operation}_source_untrusted")
            continue
        if not item.signature_valid:
            missing.append(operation)
            reasons.append(f"operation_{operation}_signature_invalid")
            continue
        if item.freshness != "current":
            missing.append(operation)
            reasons.append(f"operation_{operation}_freshness_{item.freshness}")
            continue
        observed_passed.append(operation)

    suite_complete = (
        not missing
        and not failed
        and set(observed_passed) == set(REQUIRED_SUITE_OPERATIONS)
    )

    if failed:
        disposition = CertificationDisposition.UNAVAILABLE
        closed = CLOSED_OUTCOME_UNAVAILABLE
        reasons = list(
            _reasons(
                "observed_suite_failed",
                "live_qualified_requires_complete_observed_suite",
                *reasons,
            )
        )
        support_status = "failed"
        freshness = "current"
        message = "one or more required operations failed under live runner"
    elif not suite_complete:
        disposition = CertificationDisposition.CONDITIONAL
        closed = CLOSED_OUTCOME_UNAVAILABLE
        reasons = list(
            _reasons(
                "incomplete_observed_suite",
                "live_qualified_requires_complete_observed_suite",
                *reasons,
            )
        )
        support_status = "incomplete"
        freshness = "missing" if missing else "stale"
        message = "observed suite incomplete; cannot set LiveQualified"
    else:
        disposition = CertificationDisposition.LIVE_QUALIFIED
        closed = CLOSED_OUTCOME_VERIFIED
        reasons = list(
            _reasons(
                "complete_observed_suite",
                "live_runner_present",
                "signature_valid",
                "freshness_current",
                "environment_live",
                "source_live_observed",
            )
        )
        support_status = "live_qualified"
        freshness = "current"
        message = "complete current live observed suite"

    support = build_support_row(
        contract,
        disposition=(
            CertificationDisposition.CONDITIONAL
            if disposition is CertificationDisposition.UNAVAILABLE
            and not suite_complete
            else disposition
        ),
        suite_complete=suite_complete,
        operations_observed=tuple(observed_passed),
        reason_codes=reasons,
        evidence_freshness=freshness,
        evidence_status=support_status,
    )
    if disposition is CertificationDisposition.LIVE_QUALIFIED:
        support = replace(
            support,
            disposition=CertificationDisposition.LIVE_QUALIFIED,
            live_tier="production",
            storage_selectable=True,
        )
    elif disposition is CertificationDisposition.UNAVAILABLE:
        # Failed live attempts: support row stays honest Conditional/Unavailable.
        support = replace(
            support,
            disposition=CertificationDisposition.UNAVAILABLE,
            live_tier="unavailable",
            storage_selectable=False,
        )

    receipt = build_receipt(
        contract,
        disposition=disposition,
        live_qualified=disposition is CertificationDisposition.LIVE_QUALIFIED,
        suite_complete=suite_complete,
        operations_observed=tuple(observed_passed),
        operations_failed=tuple(failed),
        reason_codes=reasons,
        suite=suite_obj,
        environment="live" if live_runner_present else "hermetic",
        source="live_runner" if suite_complete else "live_runner_incomplete",
        signature_valid=suite_complete,
        freshness=freshness,
        live_runner_present=True,
        now=reference,
        message=message,
    )

    result = CertificationResult(
        backend_id=contract.backend_id,
        disposition=disposition,
        closed_outcome=closed,
        live_qualified=disposition is CertificationDisposition.LIVE_QUALIFIED,
        suite_complete=suite_complete,
        live_runner_present=True,
        reason_codes=tuple(reasons),
        operations_required=REQUIRED_SUITE_OPERATIONS,
        operations_observed=tuple(observed_passed),
        operations_failed=tuple(failed),
        operations_missing=tuple(missing),
        receipt=receipt,
        support_row=support,
        message=message,
    )
    return result


def require_live_qualified(result: CertificationResult) -> CertificationResult:
    """Raise typed rejection unless ``result`` is LiveQualified."""

    if result.disposition is CertificationDisposition.LIVE_QUALIFIED and (
        result.live_qualified and result.suite_complete
    ):
        return result
    raise BackendCertificationRejected(result)


def complete_live_observations(
    *,
    source: str = "live_observed",
    environment: str = "live",
    signature_valid: bool = True,
    freshness: str = "current",
) -> tuple[OperationObservation, ...]:
    """Helper: one passed observation per required operation (tests / runners)."""

    return tuple(
        OperationObservation(
            operation=operation,
            status=ObservationStatus.PASSED,
            environment=environment,
            source=source,
            signature_valid=signature_valid,
            freshness=freshness,
            digests={"observation": f"digest:{operation}"},
        )
        for operation in REQUIRED_SUITE_OPERATIONS
    )


def generate_all_artifacts(
    *, now: datetime | None = None
) -> dict[str, Any]:
    """Deterministic cohort artifact bundle (suites, schema, absent-runner rows)."""

    reference = _utc_now(now)
    suites = generate_cohort_suites(now=reference)
    schema_doc = receipt_schema()
    results = {
        backend_id: absent_live_runner_result(
            contract_for(backend_id), now=reference, suite=suite
        )
        for backend_id, suite in suites.items()
    }
    support_rows = [result.support_row.to_dict() for result in results.values()]
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "goal_id": GOAL_ID,
        "evidence_bundle": EVIDENCE_BUNDLE,
        "receipt_schema": schema_doc,
        "cohort": list(COHORT_BACKEND_IDS),
        "required_operations": list(REQUIRED_SUITE_OPERATIONS),
        "suites": {key: suite.to_dict() for key, suite in suites.items()},
        "absent_runner_results": {
            key: result.to_dict() for key, result in results.items()
        },
        "support_rows": support_rows,
        "unsafe_promotion": UNSAFE_PROMOTION,
        "generated_at": reference.replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }


__all__ = [
    "SCHEMA",
    "SCHEMA_VERSION",
    "RECEIPT_SCHEMA",
    "SUPPORT_ROW_SCHEMA",
    "TASK_ID",
    "GOAL_ID",
    "EVIDENCE_BUNDLE",
    "FCA_RELEASE",
    "FCA_VOCABULARY_SCHEMA",
    "UNSAFE_PROMOTION",
    "CLOSED_OUTCOME_UNAVAILABLE",
    "CLOSED_OUTCOME_OBSERVED",
    "CLOSED_OUTCOME_VERIFIED",
    "REQUIRED_SUITE_OPERATIONS",
    "REQUIRED_EVIDENCE_BINDINGS",
    "COHORT_BACKEND_IDS",
    "BackendCertificationError",
    "BackendCertificationRejected",
    "CertificationDisposition",
    "SuiteCaseKind",
    "ObservationStatus",
    "BackendContract",
    "SuiteCase",
    "CertificationSuite",
    "SupportRow",
    "OperationObservation",
    "CertificationResult",
    "normalize_backend_id",
    "is_cohort_backend",
    "receipt_schema",
    "cohort_contracts",
    "contract_for",
    "contract_digest",
    "generate_suite",
    "generate_cohort_suites",
    "build_receipt",
    "build_support_row",
    "absent_live_runner_result",
    "evaluate_observations",
    "require_live_qualified",
    "complete_live_observations",
    "generate_all_artifacts",
]
