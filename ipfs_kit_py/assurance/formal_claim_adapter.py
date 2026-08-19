"""Lossless FCA adapter for Kit evidence and proof-role records (FACP-015).

Maps ``ipfs_kit_py`` support-matrix, backend inventory, configured/selected
provider states, candidate/admitted/current proof roles, receipt freshness,
CAS outcomes, and ambiguous-recovery dispositions onto Formal Claim Algebra
``EvidenceEnvelope`` projections **without collapsing Kit distinctions**.

Design invariants (fail-closed):

* Round-trip restores the original Kit record byte-for-byte via the paired
  sidecar; envelope-only reverse projection is refused.
* Unsupported, ambiguous, stale, empty-authority, and zero-qualified records
  remain ``qualifying=False`` and never satisfy ``production_supported``.
* Hermetic/conditional/fixture/candidate/configured evidence never promotes
  into live / selected / verified / current production claims.
* Kernel VFS claim classes and backend support tiers stay separate families.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import Any, Final, Mapping, Optional

SCHEMA: Final[str] = "KitFormalClaimAdapter@1"
SCHEMA_VERSION: Final[str] = "ipfs_kit_py.assurance.formal_claim_adapter@1"
TASK_ID: Final[str] = "FACP-015"
GOAL_ID: Final[str] = "FACP-G120"
FCA_RELEASE: Final[str] = "formal-claim-algebra-v1"
FCA_VOCABULARY_SCHEMA: Final[str] = "facp/formal-claim-algebra-v1@1"
UNSAFE_PROMOTION: Final[bool] = False

DIMENSION_ORDER: Final[tuple[str, ...]] = (
    "origin",
    "integrity",
    "authority",
    "policy",
    "proof",
    "freshness",
    "effect",
    "environment",
    "review",
)

ORIGIN_VALUES: Final[frozenset[str]] = frozenset(
    {
        "absent",
        "declared",
        "fixture",
        "simulated",
        "hermetic_observed",
        "live_observed",
    }
)
INTEGRITY_VALUES: Final[frozenset[str]] = frozenset(
    {"unchecked", "structurally_valid", "digest_valid", "signature_valid"}
)
AUTHORITY_VALUES: Final[frozenset[str]] = frozenset(
    {"unchecked", "absent", "valid", "expired", "revoked", "denied"}
)
POLICY_VALUES: Final[frozenset[str]] = frozenset(
    {
        "unchecked",
        "allowed",
        "denied",
        "allowed_with_obligations",
        "indeterminate",
    }
)
PROOF_VALUES: Final[frozenset[str]] = frozenset(
    {
        "none",
        "candidate",
        "verified",
        "refuted",
        "unknown",
        "verifier_unavailable",
    }
)
FRESHNESS_VALUES: Final[frozenset[str]] = frozenset(
    {"current", "stale", "superseded", "withdrawn"}
)
EFFECT_VALUES: Final[frozenset[str]] = frozenset(
    {
        "not_started",
        "reserved",
        "started",
        "externally_unknown",
        "observed",
        "compensated",
        "failed",
    }
)
ENVIRONMENT_VALUES: Final[frozenset[str]] = frozenset(
    {"hermetic", "conditional", "live"}
)
REVIEW_VALUES: Final[frozenset[str]] = frozenset(
    {"unreviewed", "machine_reviewed", "human_reviewed"}
)

_DIMENSION_CARRIERS: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "origin": ORIGIN_VALUES,
        "integrity": INTEGRITY_VALUES,
        "authority": AUTHORITY_VALUES,
        "policy": POLICY_VALUES,
        "proof": PROOF_VALUES,
        "freshness": FRESHNESS_VALUES,
        "effect": EFFECT_VALUES,
        "environment": ENVIRONMENT_VALUES,
        "review": REVIEW_VALUES,
    }
)

KERNEL_VFS_CLAIM_CLASSES: Final[frozenset[str]] = frozenset(
    {"hermetic", "conditional", "live"}
)
BACKEND_SUPPORT_TIERS: Final[frozenset[str]] = frozenset(
    {
        "production",
        "conditional",
        "configuration-only",
        "experimental",
        "unsupported",
        "unknown-pending-proof",
    }
)
CONFIGURED_SELECTED_STATES: Final[frozenset[str]] = frozenset(
    {
        "absent",
        "unsupported",
        "configured",
        "receipt-required",
        "canonical-adapter-missing",
        "selected",
    }
)
# ProviderAvailability spellings that project onto configured/selected ladder.
_PROVIDER_AVAILABILITY_TO_STATE: Final[Mapping[str, str]] = MappingProxyType(
    {
        "unsupported": "unsupported",
        "configuration-only": "configured",
        "receipt-required": "receipt-required",
        "canonical-adapter-missing": "canonical-adapter-missing",
        "runtime-ready": "selected",
    }
)
PROOF_ROLES: Final[frozenset[str]] = frozenset({"candidate", "admitted", "current"})
RECEIPT_FRESHNESS_LABELS: Final[frozenset[str]] = frozenset(
    {
        "current",
        "stale",
        "missing",
        "empty-authority-current",
        "empty-authority",
        "current-tree-artifact",
        "joined-by-dependency-task",
        "not-required-for-configuration-only",
        "not-applicable",
        "superseded",
        "withdrawn",
    }
)
CAS_OUTCOMES: Final[frozenset[str]] = frozenset(
    {"updated", "unchanged", "conflict"}
)
RECOVERY_DISPOSITIONS: Final[frozenset[str]] = frozenset(
    {
        "rebuilt",
        "ambiguous",
        "corrupt",
        "fail_closed",
    }
)


class KitFormalClaimAdapterError(ValueError):
    """Base error for Kit ↔ FCA adaptation failures."""


class KitRecordIncompatible(KitFormalClaimAdapterError):
    """Kit record is malformed, self-authorizing, or otherwise inadmissible."""


class InformationLosingProjection(KitFormalClaimAdapterError):
    """Envelope-only reverse projection would drop Kit distinctions."""


class KitDistinctionFamily(str, Enum):
    """Closed families of Kit honest distinctions preserved by the adapter."""

    KERNEL_VFS_CLAIM_CLASS = "kernel_vfs_claim_class"
    BACKEND_SUPPORT_TIER = "backend_support_tier"
    CONFIGURED_SELECTED_STATE = "configured_selected_state"
    PROOF_ROLE = "proof_role"
    RECEIPT_FRESHNESS = "receipt_freshness"
    CAS_OUTCOME = "cas_outcome"
    RECOVERY_DISPOSITION = "recovery_disposition"
    LIVE_QUALIFICATION_SUMMARY = "live_qualification_summary"
    CAS_IDENTITY = "cas_identity"


@dataclass(frozen=True, slots=True)
class EvidenceEnvelope:
    """FCA evidence product projection (nine closed dimensions)."""

    origin: str
    integrity: str
    authority: str
    policy: str
    proof: str
    freshness: str
    effect: str
    environment: str
    review: str

    def __post_init__(self) -> None:
        for name in DIMENSION_ORDER:
            value = getattr(self, name)
            allowed = _DIMENSION_CARRIERS[name]
            if value not in allowed:
                raise KitFormalClaimAdapterError(
                    f"unknown {name} value for FCA envelope: {value!r}"
                )

    @classmethod
    def weakest(cls) -> "EvidenceEnvelope":
        """Weakest honest defaults (fail-closed starting point)."""

        return cls(
            origin="absent",
            integrity="unchecked",
            authority="unchecked",
            policy="unchecked",
            proof="none",
            freshness="stale",
            effect="not_started",
            environment="hermetic",
            review="unreviewed",
        )

    def with_overrides(self, **overrides: str) -> "EvidenceEnvelope":
        return replace(self, **overrides)

    def to_dimension_map(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in DIMENSION_ORDER}

    @classmethod
    def from_dimension_map(cls, mapping: Mapping[str, Any]) -> "EvidenceEnvelope":
        if not isinstance(mapping, Mapping):
            raise KitFormalClaimAdapterError("envelope map must be a mapping")
        unknown = sorted(set(mapping) - set(DIMENSION_ORDER))
        missing = [name for name in DIMENSION_ORDER if name not in mapping]
        if unknown:
            raise KitFormalClaimAdapterError(
                f"unknown envelope field(s): {', '.join(unknown)}"
            )
        if missing:
            raise KitFormalClaimAdapterError(
                f"missing envelope field(s): {', '.join(missing)}"
            )
        return cls(**{name: str(mapping[name]) for name in DIMENSION_ORDER})

    def production_supported(self) -> bool:
        """Dimension half of the live production-support predicate.

        Requires live environment, live-observed origin, and current freshness.
        The Kit adapter never invents those from inventory-only records.
        """

        return (
            self.environment == "live"
            and self.origin == "live_observed"
            and self.freshness == "current"
        )


@dataclass(frozen=True, slots=True)
class KitEvidenceRecord:
    """Lossless Kit-native evidence / proof-role record.

    ``family`` + ``value`` carry the primary distinction. Optional identity and
    count fields preserve CAS/proof-role and live-qualification structure that
    cannot fit in an ``EvidenceEnvelope`` alone.
    """

    family: KitDistinctionFamily
    value: str
    backend_name: Optional[str] = None
    inventory_tier: Optional[str] = None
    live_tier: Optional[str] = None
    candidate_cid: Optional[str] = None
    authorization_cid: Optional[str] = None
    current_cid: Optional[str] = None
    expected_cid: Optional[str] = None
    expected_generation: Optional[int] = None
    live_qualified_backend_count: Optional[int] = None
    storage_selectable_count: Optional[int] = None
    inventory_production_count: Optional[int] = None
    live_production_count: Optional[int] = None
    zero_qualified_is_valid_honest_state: Optional[bool] = None
    ambiguous: bool = False
    attributes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.family, KitDistinctionFamily):
            raise KitRecordIncompatible(
                f"family must be KitDistinctionFamily, got {type(self.family)!r}"
            )
        if not isinstance(self.value, str) or not self.value:
            raise KitRecordIncompatible("value must be a non-empty string")
        if not isinstance(self.ambiguous, bool):
            raise KitRecordIncompatible("ambiguous must be a boolean")
        attrs = self.attributes
        if isinstance(attrs, MappingProxyType):
            pass
        elif isinstance(attrs, Mapping):
            object.__setattr__(
                self,
                "attributes",
                MappingProxyType({str(k): str(v) for k, v in attrs.items()}),
            )
        else:
            raise KitRecordIncompatible("attributes must be a mapping")
        for count_name in (
            "live_qualified_backend_count",
            "storage_selectable_count",
            "inventory_production_count",
            "live_production_count",
            "expected_generation",
        ):
            count = getattr(self, count_name)
            if count is not None and (
                isinstance(count, bool) or not isinstance(count, int) or count < 0
            ):
                raise KitRecordIncompatible(
                    f"{count_name} must be a non-negative int when set"
                )
        self._validate_family_value()

    def _validate_family_value(self) -> None:
        family = self.family
        value = self.value
        if family is KitDistinctionFamily.KERNEL_VFS_CLAIM_CLASS:
            if value not in KERNEL_VFS_CLAIM_CLASSES:
                raise KitRecordIncompatible(
                    f"unknown kernel VFS claim class: {value!r}"
                )
        elif family is KitDistinctionFamily.BACKEND_SUPPORT_TIER:
            if value not in BACKEND_SUPPORT_TIERS:
                raise KitRecordIncompatible(
                    f"unknown backend support tier: {value!r}"
                )
        elif family is KitDistinctionFamily.CONFIGURED_SELECTED_STATE:
            if value not in CONFIGURED_SELECTED_STATES:
                raise KitRecordIncompatible(
                    f"unknown configured/selected state: {value!r}"
                )
        elif family is KitDistinctionFamily.PROOF_ROLE:
            if value not in PROOF_ROLES:
                raise KitRecordIncompatible(f"unknown proof role: {value!r}")
        elif family is KitDistinctionFamily.RECEIPT_FRESHNESS:
            if value not in RECEIPT_FRESHNESS_LABELS:
                raise KitRecordIncompatible(
                    f"unknown receipt freshness label: {value!r}"
                )
        elif family is KitDistinctionFamily.CAS_OUTCOME:
            if value not in CAS_OUTCOMES:
                raise KitRecordIncompatible(f"unknown CAS outcome: {value!r}")
        elif family is KitDistinctionFamily.RECOVERY_DISPOSITION:
            if value not in RECOVERY_DISPOSITIONS:
                raise KitRecordIncompatible(
                    f"unknown recovery disposition: {value!r}"
                )
        elif family is KitDistinctionFamily.LIVE_QUALIFICATION_SUMMARY:
            if value not in {"zero_qualified", "live_qualified"}:
                raise KitRecordIncompatible(
                    f"unknown live qualification summary: {value!r}"
                )
        elif family is KitDistinctionFamily.CAS_IDENTITY:
            if value not in {
                "distinct_candidate_authorization_current",
                "self_authorization_rejected",
                "stale_expected_conflict",
                "identity_bound",
            }:
                raise KitRecordIncompatible(f"unknown CAS identity kind: {value!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family.value,
            "value": self.value,
            "backend_name": self.backend_name,
            "inventory_tier": self.inventory_tier,
            "live_tier": self.live_tier,
            "candidate_cid": self.candidate_cid,
            "authorization_cid": self.authorization_cid,
            "current_cid": self.current_cid,
            "expected_cid": self.expected_cid,
            "expected_generation": self.expected_generation,
            "live_qualified_backend_count": self.live_qualified_backend_count,
            "storage_selectable_count": self.storage_selectable_count,
            "inventory_production_count": self.inventory_production_count,
            "live_production_count": self.live_production_count,
            "zero_qualified_is_valid_honest_state": (
                self.zero_qualified_is_valid_honest_state
            ),
            "ambiguous": self.ambiguous,
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "KitEvidenceRecord":
        if not isinstance(payload, Mapping):
            raise KitRecordIncompatible("KitEvidenceRecord payload must be a mapping")
        try:
            family = KitDistinctionFamily(str(payload["family"]))
        except (KeyError, ValueError) as exc:
            raise KitRecordIncompatible(
                f"invalid KitEvidenceRecord family: {payload.get('family')!r}"
            ) from exc
        return cls(
            family=family,
            value=str(payload["value"]),
            backend_name=_optional_str(payload.get("backend_name")),
            inventory_tier=_optional_str(payload.get("inventory_tier")),
            live_tier=_optional_str(payload.get("live_tier")),
            candidate_cid=_optional_str(payload.get("candidate_cid")),
            authorization_cid=_optional_str(payload.get("authorization_cid")),
            current_cid=_optional_str(payload.get("current_cid")),
            expected_cid=_optional_str(payload.get("expected_cid")),
            expected_generation=_optional_int(payload.get("expected_generation")),
            live_qualified_backend_count=_optional_int(
                payload.get("live_qualified_backend_count")
            ),
            storage_selectable_count=_optional_int(
                payload.get("storage_selectable_count")
            ),
            inventory_production_count=_optional_int(
                payload.get("inventory_production_count")
            ),
            live_production_count=_optional_int(payload.get("live_production_count")),
            zero_qualified_is_valid_honest_state=_optional_bool(
                payload.get("zero_qualified_is_valid_honest_state")
            ),
            ambiguous=bool(payload.get("ambiguous", False)),
            attributes=dict(payload.get("attributes") or {}),
        )


@dataclass(frozen=True, slots=True)
class AdaptedKitClaim:
    """Paired Kit record + conservative FCA envelope.

    ``qualifying`` is True only when the record could participate in live
    production promotion. Inventory-only, hermetic, candidate, unsupported,
    ambiguous, and zero-qualified records stay nonqualifying.
    """

    kit: KitEvidenceRecord
    envelope: EvidenceEnvelope
    qualifying: bool
    reason_codes: tuple[str, ...]
    schema: str = SCHEMA
    schema_version: str = SCHEMA_VERSION
    task_id: str = TASK_ID
    fca_release: str = FCA_RELEASE
    unsafe_promotion: bool = UNSAFE_PROMOTION

    def __post_init__(self) -> None:
        if self.unsafe_promotion:
            raise KitFormalClaimAdapterError(
                "Kit FCA adapter forbids unsafe_promotion=True"
            )
        if not isinstance(self.reason_codes, tuple):
            object.__setattr__(self, "reason_codes", tuple(self.reason_codes))

    @property
    def production_supported(self) -> bool:
        return self.qualifying and self.envelope.production_supported()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "fca_release": self.fca_release,
            "unsafe_promotion": self.unsafe_promotion,
            "qualifying": self.qualifying,
            "production_supported": self.production_supported,
            "reason_codes": list(self.reason_codes),
            "kit": self.kit.to_dict(),
            "envelope": self.envelope.to_dimension_map(),
        }


def _optional_str(value: object) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise KitRecordIncompatible(f"expected string or None, got {type(value)!r}")
    return value


def _optional_int(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise KitRecordIncompatible(f"expected int or None, got {type(value)!r}")
    if value < 0:
        raise KitRecordIncompatible("expected non-negative int")
    return value


def _optional_bool(value: object) -> Optional[bool]:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise KitRecordIncompatible(f"expected bool or None, got {type(value)!r}")
    return value


def _reasons(*codes: str) -> tuple[str, ...]:
    return tuple(codes)


def adapt_kit_record(record: KitEvidenceRecord) -> AdaptedKitClaim:
    """Adapt one Kit record into a paired FCA envelope (conservative)."""

    if not isinstance(record, KitEvidenceRecord):
        raise KitRecordIncompatible("adapt_kit_record requires KitEvidenceRecord")

    family = record.family
    if family is KitDistinctionFamily.KERNEL_VFS_CLAIM_CLASS:
        return _adapt_claim_class(record)
    if family is KitDistinctionFamily.BACKEND_SUPPORT_TIER:
        return _adapt_backend_tier(record)
    if family is KitDistinctionFamily.CONFIGURED_SELECTED_STATE:
        return _adapt_configured_selected(record)
    if family is KitDistinctionFamily.PROOF_ROLE:
        return _adapt_proof_role(record)
    if family is KitDistinctionFamily.RECEIPT_FRESHNESS:
        return _adapt_receipt_freshness(record)
    if family is KitDistinctionFamily.CAS_OUTCOME:
        return _adapt_cas_outcome(record)
    if family is KitDistinctionFamily.RECOVERY_DISPOSITION:
        return _adapt_recovery(record)
    if family is KitDistinctionFamily.LIVE_QUALIFICATION_SUMMARY:
        return _adapt_live_qualification(record)
    if family is KitDistinctionFamily.CAS_IDENTITY:
        return _adapt_cas_identity(record)
    raise KitRecordIncompatible(f"unsupported Kit distinction family: {family!r}")


def project_to_kit(adapted: AdaptedKitClaim) -> KitEvidenceRecord:
    """Lossless reverse projection using the paired Kit sidecar."""

    if not isinstance(adapted, AdaptedKitClaim):
        raise KitFormalClaimAdapterError("project_to_kit requires AdaptedKitClaim")
    return KitEvidenceRecord.from_dict(adapted.kit.to_dict())


def round_trip(record: KitEvidenceRecord) -> KitEvidenceRecord:
    """Adapt then project; must preserve every Kit distinction."""

    return project_to_kit(adapt_kit_record(record))


def project_from_envelope_only(
    envelope: EvidenceEnvelope,
    *,
    family: KitDistinctionFamily | None = None,
) -> KitEvidenceRecord:
    """Refuse envelope-only reverse projection (information-losing)."""

    raise InformationLosingProjection(
        "refusing envelope-only reverse projection: Kit distinctions "
        f"(family={family.value if family else 'unspecified'}) cannot be "
        "recovered from an EvidenceEnvelope without the paired Kit sidecar; "
        f"envelope={envelope.to_dimension_map()!r}"
    )


def is_nonqualifying(adapted: AdaptedKitClaim) -> bool:
    return not adapted.qualifying


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def adapt_kernel_vfs_claim_class(claim_class: str) -> AdaptedKitClaim:
    return adapt_kit_record(
        KitEvidenceRecord(
            family=KitDistinctionFamily.KERNEL_VFS_CLAIM_CLASS,
            value=str(claim_class),
        )
    )


def adapt_backend_support_tier(
    tier: str,
    *,
    backend_name: str | None = None,
    live_tier: str | None = None,
) -> AdaptedKitClaim:
    return adapt_kit_record(
        KitEvidenceRecord(
            family=KitDistinctionFamily.BACKEND_SUPPORT_TIER,
            value=str(tier),
            backend_name=backend_name,
            inventory_tier=str(tier),
            live_tier=live_tier,
        )
    )


def adapt_configured_selected_state(state: str, *, backend_name: str | None = None) -> AdaptedKitClaim:
    return adapt_kit_record(
        KitEvidenceRecord(
            family=KitDistinctionFamily.CONFIGURED_SELECTED_STATE,
            value=str(state),
            backend_name=backend_name,
        )
    )


def adapt_provider_availability(
    availability: str, *, backend_name: str | None = None
) -> AdaptedKitClaim:
    """Map ``ProviderAvailability`` spellings onto the configured/selected ladder."""

    key = str(availability)
    try:
        state = _PROVIDER_AVAILABILITY_TO_STATE[key]
    except KeyError as exc:
        raise KitRecordIncompatible(
            f"unknown provider availability: {availability!r}"
        ) from exc
    record = KitEvidenceRecord(
        family=KitDistinctionFamily.CONFIGURED_SELECTED_STATE,
        value=state,
        backend_name=backend_name,
        attributes={"provider_availability": key},
    )
    return adapt_kit_record(record)


def adapt_proof_role(
    role: str,
    *,
    candidate_cid: str | None = None,
    authorization_cid: str | None = None,
    current_cid: str | None = None,
) -> AdaptedKitClaim:
    return adapt_kit_record(
        KitEvidenceRecord(
            family=KitDistinctionFamily.PROOF_ROLE,
            value=str(role),
            candidate_cid=candidate_cid,
            authorization_cid=authorization_cid,
            current_cid=current_cid,
        )
    )


def adapt_receipt_freshness(label: str) -> AdaptedKitClaim:
    return adapt_kit_record(
        KitEvidenceRecord(
            family=KitDistinctionFamily.RECEIPT_FRESHNESS,
            value=str(label),
        )
    )


def adapt_cas_outcome(
    outcome: str,
    *,
    expected_cid: str | None = None,
    current_cid: str | None = None,
    expected_generation: int | None = None,
) -> AdaptedKitClaim:
    return adapt_kit_record(
        KitEvidenceRecord(
            family=KitDistinctionFamily.CAS_OUTCOME,
            value=str(outcome),
            expected_cid=expected_cid,
            current_cid=current_cid,
            expected_generation=expected_generation,
        )
    )


def adapt_recovery_disposition(
    disposition: str, *, ambiguous: bool | None = None
) -> AdaptedKitClaim:
    ambiguous_flag = (
        bool(ambiguous)
        if ambiguous is not None
        else disposition in {"ambiguous", "fail_closed"}
    )
    return adapt_kit_record(
        KitEvidenceRecord(
            family=KitDistinctionFamily.RECOVERY_DISPOSITION,
            value=str(disposition),
            ambiguous=ambiguous_flag,
        )
    )


def adapt_cas_identity(
    *,
    candidate_cid: str,
    authorization_cid: str,
    current_cid: str | None = None,
    expected_cid: str | None = None,
    expected_generation: int | None = None,
) -> AdaptedKitClaim:
    """Adapt distinct candidate / authorization / current CAS identity fields."""

    if candidate_cid == authorization_cid:
        record = KitEvidenceRecord(
            family=KitDistinctionFamily.CAS_IDENTITY,
            value="self_authorization_rejected",
            candidate_cid=candidate_cid,
            authorization_cid=authorization_cid,
            current_cid=current_cid,
            expected_cid=expected_cid,
            expected_generation=expected_generation,
            ambiguous=False,
        )
        return adapt_kit_record(record)

    if (
        expected_cid is not None
        and current_cid is not None
        and expected_cid != current_cid
    ):
        record = KitEvidenceRecord(
            family=KitDistinctionFamily.CAS_IDENTITY,
            value="stale_expected_conflict",
            candidate_cid=candidate_cid,
            authorization_cid=authorization_cid,
            current_cid=current_cid,
            expected_cid=expected_cid,
            expected_generation=expected_generation,
        )
        return adapt_kit_record(record)

    record = KitEvidenceRecord(
        family=KitDistinctionFamily.CAS_IDENTITY,
        value="distinct_candidate_authorization_current",
        candidate_cid=candidate_cid,
        authorization_cid=authorization_cid,
        current_cid=current_cid,
        expected_cid=expected_cid,
        expected_generation=expected_generation,
    )
    return adapt_kit_record(record)


def adapt_live_qualification_summary(
    *,
    live_qualified_backend_count: int,
    storage_selectable_count: int,
    inventory_production_count: int,
    live_production_count: int | None = None,
    zero_qualified_is_valid_honest_state: bool | None = None,
) -> AdaptedKitClaim:
    live_prod = (
        live_production_count
        if live_production_count is not None
        else live_qualified_backend_count
    )
    zero = (
        live_qualified_backend_count == 0
        and storage_selectable_count == 0
        and inventory_production_count == 0
        and live_prod == 0
    )
    if zero_qualified_is_valid_honest_state is None:
        zero_qualified_is_valid_honest_state = zero
    value = "zero_qualified" if zero else "live_qualified"
    return adapt_kit_record(
        KitEvidenceRecord(
            family=KitDistinctionFamily.LIVE_QUALIFICATION_SUMMARY,
            value=value,
            live_qualified_backend_count=live_qualified_backend_count,
            storage_selectable_count=storage_selectable_count,
            inventory_production_count=inventory_production_count,
            live_production_count=live_prod,
            zero_qualified_is_valid_honest_state=zero_qualified_is_valid_honest_state,
        )
    )


def adapt_zero_qualified_state(
    summary: Mapping[str, Any] | None = None,
) -> AdaptedKitClaim:
    """Adapt the honest zero live-qualified backend state.

    When ``summary`` is omitted, uses the closed zero counts that FACP-004
    recorded against the current Kit support matrix.
    """

    if summary is None:
        return adapt_live_qualification_summary(
            live_qualified_backend_count=0,
            storage_selectable_count=0,
            inventory_production_count=0,
            live_production_count=0,
            zero_qualified_is_valid_honest_state=True,
        )

    live_qualified = int(
        summary.get(
            "live_qualified_backend_count",
            summary.get("live_production_count", 0),
        )
    )
    storage_selectable = int(summary.get("storage_selectable_count", 0))
    inventory_production = int(summary.get("production_count", summary.get("inventory_production_count", 0)))
    live_production = int(summary.get("live_production_count", live_qualified))
    return adapt_live_qualification_summary(
        live_qualified_backend_count=live_qualified,
        storage_selectable_count=storage_selectable,
        inventory_production_count=inventory_production,
        live_production_count=live_production,
        zero_qualified_is_valid_honest_state=bool(
            summary.get("zero_qualified_is_valid_honest_state", True)
        ),
    )


def adapt_joined_manifest_summary(summary: Mapping[str, Any]) -> AdaptedKitClaim:
    """Adapt a joined backend support-manifest ``summary`` object."""

    if not isinstance(summary, Mapping):
        raise KitRecordIncompatible("joined manifest summary must be a mapping")
    return adapt_zero_qualified_state(
        {
            "live_production_count": summary.get("live_production_count", 0),
            "live_qualified_backend_count": summary.get("live_production_count", 0),
            "storage_selectable_count": summary.get("storage_selectable_count", 0),
            "production_count": summary.get("production_count", 0),
            "inventory_production_count": summary.get("production_count", 0),
            "zero_qualified_is_valid_honest_state": True,
        }
    )


# ---------------------------------------------------------------------------
# Family-specific adapters
# ---------------------------------------------------------------------------


def _adapt_claim_class(record: KitEvidenceRecord) -> AdaptedKitClaim:
    claim = record.value
    # Matrix claim-class annotation is declared inventory, not live observation.
    if claim == "hermetic":
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="declared",
            environment="hermetic",
            proof="none",
            freshness="stale",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "kernel_vfs_claim_class_hermetic",
                "hermetic_is_not_live",
                "inventory_annotation_only",
            ),
        )
    if claim == "conditional":
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="declared",
            environment="conditional",
            proof="none",
            freshness="stale",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "kernel_vfs_claim_class_conditional",
                "conditional_requires_current_capability_receipt",
                "inventory_annotation_only",
            ),
        )
    # live claim *class* still requires live qualification (§4.5 / §8.3).
    envelope = EvidenceEnvelope.weakest().with_overrides(
        origin="declared",
        environment="live",
        proof="none",
        freshness="stale",
    )
    return AdaptedKitClaim(
        kit=record,
        envelope=envelope,
        qualifying=False,
        reason_codes=_reasons(
            "kernel_vfs_claim_class_live",
            "live_class_requires_live_qualification",
            "origin_not_live_observed",
            "inventory_annotation_only",
        ),
    )


def _adapt_backend_tier(record: KitEvidenceRecord) -> AdaptedKitClaim:
    tier = record.value
    env = "conditional" if tier == "conditional" else "hermetic"
    if tier == "unsupported":
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="declared",
            environment=env,
            proof="none",
            freshness="stale",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "backend_support_tier_unsupported",
                "unsupported_remains_nonqualifying",
                "inventory_discovery_only",
            ),
        )
    if tier in {"configuration-only", "experimental", "unknown-pending-proof"}:
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="declared",
            environment=env,
            proof="none",
            freshness="stale",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                f"backend_support_tier_{tier.replace('-', '_')}",
                "inventory_discovery_only",
                "inventory_tier_is_not_live_qualification",
            ),
        )
    if tier == "conditional":
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="declared",
            environment="conditional",
            proof="none",
            freshness="stale",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "backend_support_tier_conditional",
                "inventory_discovery_only",
                "conditional_without_current_receipt_nonqualifying",
            ),
        )
    # inventory "production" still does not imply live qualification
    envelope = EvidenceEnvelope.weakest().with_overrides(
        origin="declared",
        environment="hermetic",
        proof="none",
        freshness="stale",
    )
    return AdaptedKitClaim(
        kit=record,
        envelope=envelope,
        qualifying=False,
        reason_codes=_reasons(
            "backend_support_tier_production",
            "inventory_production_is_not_live_qualification",
            "inventory_discovery_only",
        ),
    )


def _adapt_configured_selected(record: KitEvidenceRecord) -> AdaptedKitClaim:
    state = record.value
    if state == "absent":
        envelope = EvidenceEnvelope.weakest().with_overrides(origin="absent")
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons("provider_absent", "nonqualifying"),
        )
    if state == "unsupported":
        envelope = EvidenceEnvelope.weakest().with_overrides(origin="declared")
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "provider_unsupported",
                "unsupported_remains_nonqualifying",
            ),
        )
    if state == "configured":
        envelope = EvidenceEnvelope.weakest().with_overrides(origin="declared")
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "provider_configured",
                "configured_is_not_selected",
                "nonqualifying_for_storage",
            ),
        )
    if state == "receipt-required":
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="declared",
            environment="conditional",
            freshness="stale",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "provider_receipt_required",
                "missing_current_receipt",
                "nonqualifying",
            ),
        )
    if state == "canonical-adapter-missing":
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="declared",
            environment="conditional",
            freshness="stale",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "canonical_adapter_missing",
                "nonqualifying",
            ),
        )
    # selected / runtime-ready: storage-selectable still ≠ live production.
    envelope = EvidenceEnvelope.weakest().with_overrides(
        origin="declared",
        environment="conditional",
        freshness="stale",
        proof="none",
    )
    return AdaptedKitClaim(
        kit=record,
        envelope=envelope,
        qualifying=False,
        reason_codes=_reasons(
            "provider_selected",
            "selected_is_not_live_qualification",
            "production_supported_requires_live_observed_current",
        ),
    )


def _adapt_proof_role(record: KitEvidenceRecord) -> AdaptedKitClaim:
    role = record.value
    candidate = record.candidate_cid
    authorization = record.authorization_cid
    if (
        candidate is not None
        and authorization is not None
        and candidate == authorization
    ):
        envelope = EvidenceEnvelope.weakest().with_overrides(
            proof="candidate",
            authority="denied",
            freshness="stale",
        )
        return AdaptedKitClaim(
            kit=replace(record, ambiguous=False),
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "self_authorization_forbidden",
                "candidate_cid_equals_authorization_cid",
                "nonqualifying",
            ),
        )

    if role == "candidate":
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="declared",
            proof="candidate",
            authority="unchecked",
            freshness="stale",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "proof_role_candidate",
                "candidate_is_not_verified",
                "candidate_cannot_self_promote",
            ),
        )
    if role == "admitted":
        # Admitted authorization is distinct from proof.verified.
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="declared",
            proof="candidate",
            authority="unchecked",
            freshness="stale",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "proof_role_admitted",
                "admitted_authorization_is_not_proof_verified",
                "nonqualifying_without_live_qualification",
            ),
        )
    # current head pointer
    envelope = EvidenceEnvelope.weakest().with_overrides(
        origin="declared",
        proof="candidate",
        freshness="current",
        authority="unchecked",
    )
    return AdaptedKitClaim(
        kit=record,
        envelope=envelope,
        qualifying=False,
        reason_codes=_reasons(
            "proof_role_current",
            "current_head_is_not_live_qualification",
            "cas_head_currency_only",
        ),
    )


def _adapt_receipt_freshness(record: KitEvidenceRecord) -> AdaptedKitClaim:
    label = record.value
    if label in {"stale", "missing", "superseded", "withdrawn"}:
        freshness = (
            "stale"
            if label in {"stale", "missing"}
            else ("superseded" if label == "superseded" else "withdrawn")
        )
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="declared",
            freshness=freshness,
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                f"receipt_freshness_{label.replace('-', '_')}",
                "stale_or_missing_receipt_nonqualifying",
            ),
        )
    if label in {"empty-authority-current", "empty-authority"}:
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="absent",
            freshness="stale",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "empty_receipt_authority",
                "empty_authority_is_not_production_evidence",
                "nonqualifying",
            ),
        )
    if label in {
        "not-required-for-configuration-only",
        "not-applicable",
        "joined-by-dependency-task",
        "current-tree-artifact",
    }:
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="declared",
            freshness="stale",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                f"receipt_freshness_{label.replace('-', '_')}",
                "non_live_freshness_annotation",
                "nonqualifying",
            ),
        )
    # explicit current receipt label — still not live qualification alone
    envelope = EvidenceEnvelope.weakest().with_overrides(
        origin="declared",
        freshness="current",
    )
    return AdaptedKitClaim(
        kit=record,
        envelope=envelope,
        qualifying=False,
        reason_codes=_reasons(
            "receipt_freshness_current",
            "current_receipt_alone_is_not_live_qualification",
        ),
    )


def _adapt_cas_outcome(record: KitEvidenceRecord) -> AdaptedKitClaim:
    outcome = record.value
    if outcome == "conflict":
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="declared",
            freshness="stale",
            effect="failed",
            integrity="digest_valid"
            if record.expected_cid or record.current_cid
            else "unchecked",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "cas_conflict",
                "stale_expected_rejected",
                "no_silent_overwrite",
                "nonqualifying",
            ),
        )
    if outcome == "unchanged":
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="declared",
            freshness="current",
            effect="not_started",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons("cas_unchanged", "head_preserved"),
        )
    envelope = EvidenceEnvelope.weakest().with_overrides(
        origin="declared",
        freshness="current",
        effect="observed",
        integrity="digest_valid"
        if record.current_cid
        else "unchecked",
    )
    return AdaptedKitClaim(
        kit=record,
        envelope=envelope,
        qualifying=False,
        reason_codes=_reasons(
            "cas_updated",
            "cas_head_update_is_not_live_qualification",
        ),
    )


def _adapt_recovery(record: KitEvidenceRecord) -> AdaptedKitClaim:
    disposition = record.value
    if disposition in {"ambiguous", "corrupt", "fail_closed"} or record.ambiguous:
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="declared",
            effect="externally_unknown",
            freshness="stale",
            proof="unknown",
        )
        return AdaptedKitClaim(
            kit=replace(record, ambiguous=True)
            if disposition == "ambiguous" or record.ambiguous
            else record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                f"recovery_{disposition}",
                "ambiguous_or_corrupt_recovery_nonqualifying",
                "never_invent_promotion_winner",
            ),
        )
    envelope = EvidenceEnvelope.weakest().with_overrides(
        origin="declared",
        effect="not_started",
        freshness="stale",
        integrity="digest_valid",
    )
    return AdaptedKitClaim(
        kit=record,
        envelope=envelope,
        qualifying=False,
        reason_codes=_reasons(
            "recovery_rebuilt",
            "index_rebuild_is_not_live_qualification",
        ),
    )


def _adapt_live_qualification(record: KitEvidenceRecord) -> AdaptedKitClaim:
    live_count = record.live_qualified_backend_count or 0
    selectable = record.storage_selectable_count or 0
    inventory_prod = record.inventory_production_count or 0
    live_prod = (
        record.live_production_count
        if record.live_production_count is not None
        else live_count
    )
    zero = record.value == "zero_qualified" or (
        live_count == 0 and selectable == 0 and inventory_prod == 0 and live_prod == 0
    )
    if zero:
        envelope = EvidenceEnvelope.weakest().with_overrides(
            origin="absent",
            environment="hermetic",
            freshness="stale",
            proof="none",
        )
        kit = replace(
            record,
            value="zero_qualified",
            live_qualified_backend_count=live_count,
            storage_selectable_count=selectable,
            inventory_production_count=inventory_prod,
            live_production_count=live_prod,
            zero_qualified_is_valid_honest_state=(
                True
                if record.zero_qualified_is_valid_honest_state is None
                else record.zero_qualified_is_valid_honest_state
            ),
        )
        return AdaptedKitClaim(
            kit=kit,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "zero_live_qualified_backends",
                "zero_qualified_is_valid_honest_state",
                "production_supported_false",
            ),
        )

    # Non-zero live-qualified summary still requires full dimension conjunction
    # before production_supported; counts alone do not fill origin/freshness.
    envelope = EvidenceEnvelope.weakest().with_overrides(
        origin="declared",
        environment="live",
        freshness="stale",
        proof="none",
    )
    return AdaptedKitClaim(
        kit=record,
        envelope=envelope,
        qualifying=False,
        reason_codes=_reasons(
            "live_qualification_summary_present",
            "counts_alone_do_not_satisfy_live_observed_current",
            "nonqualifying_without_full_product",
        ),
    )


def _adapt_cas_identity(record: KitEvidenceRecord) -> AdaptedKitClaim:
    kind = record.value
    if kind == "self_authorization_rejected":
        envelope = EvidenceEnvelope.weakest().with_overrides(
            proof="candidate",
            authority="denied",
            freshness="stale",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "cas_identity_self_authorization",
                "candidate_cannot_equal_authorization",
                "nonqualifying",
            ),
        )
    if kind == "stale_expected_conflict":
        envelope = EvidenceEnvelope.weakest().with_overrides(
            freshness="stale",
            effect="failed",
            integrity="digest_valid",
        )
        return AdaptedKitClaim(
            kit=record,
            envelope=envelope,
            qualifying=False,
            reason_codes=_reasons(
                "cas_identity_stale_expected",
                "conflict_no_silent_overwrite",
                "nonqualifying",
            ),
        )
    envelope = EvidenceEnvelope.weakest().with_overrides(
        origin="declared",
        proof="candidate",
        freshness="current" if record.current_cid else "stale",
        integrity="digest_valid",
    )
    return AdaptedKitClaim(
        kit=record,
        envelope=envelope,
        qualifying=False,
        reason_codes=_reasons(
            f"cas_identity_{kind}",
            "distinct_cids_preserved",
            "identity_is_not_live_qualification",
        ),
    )


__all__ = [
    "SCHEMA",
    "SCHEMA_VERSION",
    "TASK_ID",
    "GOAL_ID",
    "FCA_RELEASE",
    "FCA_VOCABULARY_SCHEMA",
    "DIMENSION_ORDER",
    "KERNEL_VFS_CLAIM_CLASSES",
    "BACKEND_SUPPORT_TIERS",
    "CONFIGURED_SELECTED_STATES",
    "PROOF_ROLES",
    "RECEIPT_FRESHNESS_LABELS",
    "CAS_OUTCOMES",
    "RECOVERY_DISPOSITIONS",
    "KitFormalClaimAdapterError",
    "KitRecordIncompatible",
    "InformationLosingProjection",
    "KitDistinctionFamily",
    "EvidenceEnvelope",
    "KitEvidenceRecord",
    "AdaptedKitClaim",
    "adapt_kit_record",
    "project_to_kit",
    "round_trip",
    "project_from_envelope_only",
    "is_nonqualifying",
    "adapt_kernel_vfs_claim_class",
    "adapt_backend_support_tier",
    "adapt_configured_selected_state",
    "adapt_provider_availability",
    "adapt_proof_role",
    "adapt_receipt_freshness",
    "adapt_cas_outcome",
    "adapt_recovery_disposition",
    "adapt_cas_identity",
    "adapt_live_qualification_summary",
    "adapt_zero_qualified_state",
    "adapt_joined_manifest_summary",
]
