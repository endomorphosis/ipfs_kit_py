"""Kit current live-backend qualification gate (FACP-027).

Storage selection for live production use requires a **current live evidence
product**. Hermetic, conditional-inventory, configuration-only, and
registration presence evidence never satisfy this gate.

Fail-closed invariants:

* Stale, degraded, or revoked evidence demotes automatically before selection.
* Runtime-ready / storage-selectable alone is not live qualification.
* When no backend is live-qualified, selection yields typed ``Unavailable``
  with ``fallback_attempted=False`` (never a soft success).
* Zero live-qualified backends is a valid honest state.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Final, Iterable, Mapping, Optional, Sequence

SCHEMA: Final[str] = "KitLiveBackendGate@1"
SCHEMA_VERSION: Final[str] = "ipfs_kit_py.assurance.live_backend_gate@1"
TASK_ID: Final[str] = "FACP-027"
GOAL_ID: Final[str] = "FACP-G230"
FCA_RELEASE: Final[str] = "formal-claim-algebra-v1"
FCA_VOCABULARY_SCHEMA: Final[str] = "facp/formal-claim-algebra-v1@1"
CLOSED_OUTCOME_UNAVAILABLE: Final[str] = "Unavailable"
UNSAFE_PROMOTION: Final[bool] = False

# Minimal live-qualification conjunction (FCA §4.5) plus production_supported
# necessary dimensions from sealed promotion rules (FACP-010 / FACP-020).
_LIVE_ORIGINS: Final[frozenset[str]] = frozenset({"live_observed"})
_LIVE_ENVIRONMENTS: Final[frozenset[str]] = frozenset({"live"})
_CURRENT_FRESHNESS: Final[frozenset[str]] = frozenset({"current"})
_VALID_INTEGRITY: Final[frozenset[str]] = frozenset(
    {"digest_valid", "signature_valid"}
)
_VALID_AUTHORITY: Final[frozenset[str]] = frozenset({"valid"})
_ALLOWED_POLICY: Final[frozenset[str]] = frozenset(
    {"allowed", "allowed_with_obligations"}
)

_STALE_FRESHNESS: Final[frozenset[str]] = frozenset(
    {"stale", "superseded", "withdrawn", "missing"}
)
_REVOKED_AUTHORITY: Final[frozenset[str]] = frozenset(
    {"revoked", "expired", "denied"}
)
_NON_LIVE_ORIGINS: Final[frozenset[str]] = frozenset(
    {"absent", "declared", "fixture", "simulated", "hermetic_observed"}
)
_NON_LIVE_ENVIRONMENTS: Final[frozenset[str]] = frozenset(
    {"hermetic", "conditional"}
)

_REQUIRED_EVIDENCE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "live_qualification_receipt",
        "current_capability_admission",
        "authenticated_host_policy_decision",
    }
)


class LiveBackendGateError(ValueError):
    """Base error for malformed live-backend gate inputs."""


class LiveBackendUnavailable(RuntimeError):
    """Typed Unavailable: no live-qualified backend may be selected.

    Carries the closed FCA outcome and the gate result. Never implies that a
    fallback backend was successfully selected.
    """

    def __init__(self, result: "LiveBackendGateResult") -> None:
        if result.closed_outcome != CLOSED_OUTCOME_UNAVAILABLE:
            raise LiveBackendGateError(
                "LiveBackendUnavailable requires closed_outcome='Unavailable'"
            )
        if result.fallback_attempted:
            raise LiveBackendGateError(
                "LiveBackendUnavailable forbids fallback_attempted=True"
            )
        if result.selected_backend is not None:
            raise LiveBackendGateError(
                "LiveBackendUnavailable forbids a selected backend"
            )
        self.result = result
        self.closed_outcome = CLOSED_OUTCOME_UNAVAILABLE
        self.fallback_attempted = False
        message = (
            result.message
            or "no live-qualified backend available for storage selection"
        )
        super().__init__(message)


class DemotionReason(str, Enum):
    """Closed automatic demotion reasons (acceptance: stale/degraded/revoked)."""

    STALE = "stale"
    DEGRADED = "degraded"
    REVOKED = "revoked"
    NON_LIVE = "non_live"
    MISSING_EVIDENCE = "missing_evidence"
    UNSUPPORTED = "unsupported"
    CONFIGURATION_ONLY = "configuration_only"
    RECEIPT_REQUIRED = "receipt_required"
    ADAPTER_MISSING = "adapter_missing"


class LiveBackendDisposition(str, Enum):
    """Disposition after qualification / demotion assessment."""

    LIVE_QUALIFIED = "live_qualified"
    DEMOTED_STALE = "demoted_stale"
    DEMOTED_DEGRADED = "demoted_degraded"
    DEMOTED_REVOKED = "demoted_revoked"
    NONQUALIFYING = "nonqualifying"
    ZERO_QUALIFIED = "zero_qualified"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class LiveBackendEvidence:
    """Current live evidence product for one backend candidate.

    Identity fields bind backend / operation / environment. Qualification
    requires the FCA live conjunction plus sealed ``production_supported``
    necessary dimensions and evidence bag keys. Expiry is checked against
    ``now`` when ``expires_at`` is set.
    """

    backend_name: str
    operation: str = "storage"
    origin: str = "absent"
    integrity: str = "unchecked"
    authority: str = "unchecked"
    policy: str = "unchecked"
    proof: str = "none"
    freshness: str = "stale"
    effect: str = "not_started"
    environment: str = "hermetic"
    review: str = "unreviewed"
    receipt_id: Optional[str] = None
    source_release: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    signature_valid: bool = False
    degraded: bool = False
    limitations: tuple[str, ...] = ()
    evidence_bag: Mapping[str, str] = field(default_factory=dict)
    attributes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.backend_name, str) or not self.backend_name.strip():
            raise LiveBackendGateError("backend_name must be a non-empty string")
        if not isinstance(self.operation, str) or not self.operation.strip():
            raise LiveBackendGateError("operation must be a non-empty string")
        if not isinstance(self.degraded, bool):
            raise LiveBackendGateError("degraded must be a boolean")
        if not isinstance(self.signature_valid, bool):
            raise LiveBackendGateError("signature_valid must be a boolean")
        for field_name in ("limitations",):
            value = getattr(self, field_name)
            if not isinstance(value, tuple) or any(
                not isinstance(item, str) for item in value
            ):
                raise LiveBackendGateError(f"{field_name} must be a tuple[str, ...]")
        for map_name in ("evidence_bag", "attributes"):
            raw = getattr(self, map_name)
            if isinstance(raw, MappingProxyType):
                continue
            if not isinstance(raw, Mapping):
                raise LiveBackendGateError(f"{map_name} must be a mapping")
            object.__setattr__(
                self,
                map_name,
                MappingProxyType({str(k): str(v) for k, v in raw.items()}),
            )
        for ts_name in ("issued_at", "expires_at"):
            ts = getattr(self, ts_name)
            if ts is not None and (
                not isinstance(ts, datetime) or ts.tzinfo is None
            ):
                raise LiveBackendGateError(
                    f"{ts_name} must be timezone-aware datetime when set"
                )

    def to_dimension_map(self) -> dict[str, str]:
        return {
            "origin": self.origin,
            "integrity": self.integrity,
            "authority": self.authority,
            "policy": self.policy,
            "proof": self.proof,
            "freshness": self.freshness,
            "effect": self.effect,
            "environment": self.environment,
            "review": self.review,
        }

    def with_overrides(self, **overrides: Any) -> "LiveBackendEvidence":
        return replace(self, **overrides)


@dataclass(frozen=True, slots=True)
class LiveBackendAssessment:
    """Per-backend qualification assessment after automatic demotion."""

    backend_name: str
    disposition: LiveBackendDisposition
    demotion_reason: Optional[DemotionReason]
    reason_codes: tuple[str, ...]
    live_qualified: bool
    evidence: LiveBackendEvidence
    availability: Optional[str] = None

    @property
    def demoted(self) -> bool:
        return self.disposition in {
            LiveBackendDisposition.DEMOTED_STALE,
            LiveBackendDisposition.DEMOTED_DEGRADED,
            LiveBackendDisposition.DEMOTED_REVOKED,
        }


@dataclass(frozen=True, slots=True)
class LiveBackendGateResult:
    """Storage-selection / gate outcome (fail-closed; no hidden fallback)."""

    disposition: LiveBackendDisposition
    closed_outcome: Optional[str]
    selected_backend: Optional[str]
    fallback_attempted: bool
    reason_codes: tuple[str, ...]
    assessments: tuple[LiveBackendAssessment, ...] = ()
    rejection_code: Optional[str] = None
    message: Optional[str] = None
    live_qualified_count: int = 0
    zero_qualified_is_valid_honest_state: bool = False

    def __post_init__(self) -> None:
        if self.fallback_attempted is not False:
            raise LiveBackendGateError(
                "fallback_attempted must be False (hidden fallback forbidden)"
            )
        if not isinstance(self.reason_codes, tuple):
            object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        if not isinstance(self.assessments, tuple):
            object.__setattr__(self, "assessments", tuple(self.assessments))
        if self.selected_backend is not None and self.closed_outcome == (
            CLOSED_OUTCOME_UNAVAILABLE
        ):
            raise LiveBackendGateError(
                "cannot select a backend under closed_outcome='Unavailable'"
            )
        if (
            self.disposition is LiveBackendDisposition.LIVE_QUALIFIED
            and self.selected_backend is None
        ):
            raise LiveBackendGateError(
                "LIVE_QUALIFIED disposition requires selected_backend"
            )
        if (
            self.disposition
            in {
                LiveBackendDisposition.UNAVAILABLE,
                LiveBackendDisposition.ZERO_QUALIFIED,
            }
            and self.closed_outcome != CLOSED_OUTCOME_UNAVAILABLE
        ):
            raise LiveBackendGateError(
                "unavailable/zero-qualified results require closed_outcome='Unavailable'"
            )

    @property
    def production_supported(self) -> bool:
        return (
            self.disposition is LiveBackendDisposition.LIVE_QUALIFIED
            and self.selected_backend is not None
            and self.closed_outcome != CLOSED_OUTCOME_UNAVAILABLE
        )

    def to_decision_dict(self) -> dict[str, Any]:
        """Selector-seam decision shape (joined-matrix compatible)."""

        return {
            "selected": self.selected_backend,
            "reason": self.reason_codes[0] if self.reason_codes else self.disposition.value,
            "rejection_code": self.rejection_code,
            "fallback_attempted": False,
            "closed_outcome": self.closed_outcome,
            "disposition": self.disposition.value,
            "live_qualified_count": self.live_qualified_count,
        }


def _utc_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise LiveBackendGateError("now must be timezone-aware")
    return now.astimezone(timezone.utc)


def _reasons(*codes: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(codes))


def _receipt_is_current(evidence: LiveBackendEvidence, now: datetime) -> bool:
    if evidence.expires_at is None and evidence.issued_at is None:
        # No explicit receipt window: freshness dimension alone governs.
        return evidence.freshness in _CURRENT_FRESHNESS
    if evidence.issued_at is not None and evidence.issued_at > now:
        return False
    if evidence.expires_at is not None and evidence.expires_at <= now:
        return False
    if (
        evidence.issued_at is not None
        and evidence.expires_at is not None
        and evidence.expires_at <= evidence.issued_at
    ):
        return False
    return evidence.freshness in _CURRENT_FRESHNESS


def _missing_required_evidence(evidence: LiveBackendEvidence) -> tuple[str, ...]:
    missing = sorted(_REQUIRED_EVIDENCE_KEYS - set(evidence.evidence_bag))
    return tuple(missing)


def assess_live_evidence(
    evidence: LiveBackendEvidence,
    *,
    now: datetime | None = None,
    availability: str | None = None,
) -> LiveBackendAssessment:
    """Assess one backend's live evidence with automatic demotion.

    Demotion order (acceptance): revoked → stale → degraded → other
    non-qualifying causes. Hermetic / configured / fixture origins never
    qualify.
    """

    if not isinstance(evidence, LiveBackendEvidence):
        raise LiveBackendGateError("evidence must be LiveBackendEvidence")
    reference = _utc_now(now)
    codes: list[str] = []

    # --- Revoked / expired / denied authority demotes first -----------------
    if evidence.authority in _REVOKED_AUTHORITY:
        return LiveBackendAssessment(
            backend_name=evidence.backend_name,
            disposition=LiveBackendDisposition.DEMOTED_REVOKED,
            demotion_reason=DemotionReason.REVOKED,
            reason_codes=_reasons(
                f"authority_{evidence.authority}",
                "automatic_demotion_revoked",
                "live_qualification_denied",
            ),
            live_qualified=False,
            evidence=evidence,
            availability=availability,
        )

    # --- Stale / expired freshness demotes ----------------------------------
    freshness_stale = evidence.freshness in _STALE_FRESHNESS
    receipt_current = _receipt_is_current(evidence, reference)
    if freshness_stale or not receipt_current:
        if freshness_stale:
            codes.append(f"freshness_{evidence.freshness}")
        if not receipt_current:
            codes.append("receipt_not_current")
        codes.extend(("automatic_demotion_stale", "live_qualification_denied"))
        return LiveBackendAssessment(
            backend_name=evidence.backend_name,
            disposition=LiveBackendDisposition.DEMOTED_STALE,
            demotion_reason=DemotionReason.STALE,
            reason_codes=_reasons(*codes),
            live_qualified=False,
            evidence=evidence,
            availability=availability,
        )

    # --- Degraded health / blocking limitations -----------------------------
    blocking_limitations = tuple(
        lim
        for lim in evidence.limitations
        if lim
        and lim
        not in {
            "none",
            "informational",
        }
    )
    if evidence.degraded or blocking_limitations:
        return LiveBackendAssessment(
            backend_name=evidence.backend_name,
            disposition=LiveBackendDisposition.DEMOTED_DEGRADED,
            demotion_reason=DemotionReason.DEGRADED,
            reason_codes=_reasons(
                "backend_degraded" if evidence.degraded else "limitations_block_live",
                *blocking_limitations,
                "automatic_demotion_degraded",
                "live_qualification_denied",
            ),
            live_qualified=False,
            evidence=evidence,
            availability=availability,
        )

    # --- Catalog availability demotions (selector seam) ---------------------
    if availability in {"unsupported"}:
        return LiveBackendAssessment(
            backend_name=evidence.backend_name,
            disposition=LiveBackendDisposition.NONQUALIFYING,
            demotion_reason=DemotionReason.UNSUPPORTED,
            reason_codes=_reasons(
                "provider_unsupported",
                "inventory_is_not_live_qualification",
            ),
            live_qualified=False,
            evidence=evidence,
            availability=availability,
        )
    if availability in {"configuration-only"}:
        return LiveBackendAssessment(
            backend_name=evidence.backend_name,
            disposition=LiveBackendDisposition.NONQUALIFYING,
            demotion_reason=DemotionReason.CONFIGURATION_ONLY,
            reason_codes=_reasons(
                "provider_configuration_only",
                "configured_is_not_live_qualification",
            ),
            live_qualified=False,
            evidence=evidence,
            availability=availability,
        )
    if availability in {"receipt-required"}:
        return LiveBackendAssessment(
            backend_name=evidence.backend_name,
            disposition=LiveBackendDisposition.NONQUALIFYING,
            demotion_reason=DemotionReason.RECEIPT_REQUIRED,
            reason_codes=_reasons(
                "provider_receipt_required",
                "missing_current_live_receipt",
            ),
            live_qualified=False,
            evidence=evidence,
            availability=availability,
        )
    if availability in {"canonical-adapter-missing"}:
        return LiveBackendAssessment(
            backend_name=evidence.backend_name,
            disposition=LiveBackendDisposition.NONQUALIFYING,
            demotion_reason=DemotionReason.ADAPTER_MISSING,
            reason_codes=_reasons(
                "canonical_adapter_missing",
                "runtime_ready_requires_canonical_factory",
            ),
            live_qualified=False,
            evidence=evidence,
            availability=availability,
        )

    # --- Non-live origin / environment cannot satisfy live gate -------------
    if (
        evidence.origin in _NON_LIVE_ORIGINS
        or evidence.environment in _NON_LIVE_ENVIRONMENTS
        or evidence.origin not in _LIVE_ORIGINS
        or evidence.environment not in _LIVE_ENVIRONMENTS
    ):
        return LiveBackendAssessment(
            backend_name=evidence.backend_name,
            disposition=LiveBackendDisposition.NONQUALIFYING,
            demotion_reason=DemotionReason.NON_LIVE,
            reason_codes=_reasons(
                f"origin_{evidence.origin}",
                f"environment_{evidence.environment}",
                "hermetic_or_configured_cannot_satisfy_live_gate",
                "live_qualification_requires_live_observed_current",
            ),
            live_qualified=False,
            evidence=evidence,
            availability=availability,
        )

    # --- Missing sealed production_supported evidence / dimensions ----------
    missing = _missing_required_evidence(evidence)
    integrity_ok = evidence.integrity in _VALID_INTEGRITY
    # Signature bit is required when integrity claims signature_valid.
    if evidence.integrity == "signature_valid" and not evidence.signature_valid:
        integrity_ok = False

    authority_ok = evidence.authority in _VALID_AUTHORITY
    policy_ok = evidence.policy in _ALLOWED_POLICY
    freshness_ok = evidence.freshness in _CURRENT_FRESHNESS and receipt_current

    if missing or not integrity_ok or not authority_ok or not policy_ok or not freshness_ok:
        detail: list[str] = []
        if missing:
            detail.append("missing_required_evidence")
            detail.extend(f"missing_{key}" for key in missing)
        if not integrity_ok:
            detail.append(f"integrity_{evidence.integrity}")
        if not authority_ok:
            detail.append(f"authority_{evidence.authority}")
        if not policy_ok:
            detail.append(f"policy_{evidence.policy}")
        if not freshness_ok:
            detail.append("freshness_not_current")
        return LiveBackendAssessment(
            backend_name=evidence.backend_name,
            disposition=LiveBackendDisposition.NONQUALIFYING,
            demotion_reason=DemotionReason.MISSING_EVIDENCE,
            reason_codes=_reasons(
                *detail,
                "production_supported_conjunction_incomplete",
            ),
            live_qualified=False,
            evidence=evidence,
            availability=availability,
        )

    # Runtime-ready alone still needs the full live product (already checked).
    # At this point the conjunction holds.
    return LiveBackendAssessment(
        backend_name=evidence.backend_name,
        disposition=LiveBackendDisposition.LIVE_QUALIFIED,
        demotion_reason=None,
        reason_codes=_reasons(
            "live_qualification_current",
            "production_supported_conjunction_holds",
            f"operation_{evidence.operation}",
        ),
        live_qualified=True,
        evidence=evidence,
        availability=availability,
    )


def demote_if_not_current(
    evidence: LiveBackendEvidence,
    *,
    now: datetime | None = None,
    availability: str | None = None,
) -> LiveBackendAssessment:
    """Explicit demotion entrypoint; identical to :func:`assess_live_evidence`."""

    return assess_live_evidence(evidence, now=now, availability=availability)


def is_live_qualified(assessment: LiveBackendAssessment | LiveBackendGateResult) -> bool:
    if isinstance(assessment, LiveBackendGateResult):
        return assessment.production_supported
    return assessment.live_qualified


def _unavailable_result(
    *,
    assessments: Sequence[LiveBackendAssessment],
    reason_codes: Sequence[str],
    disposition: LiveBackendDisposition = LiveBackendDisposition.UNAVAILABLE,
    rejection_code: str = "E_CAPABILITY_MISSING",
    message: str | None = None,
    zero_qualified: bool = False,
) -> LiveBackendGateResult:
    live_count = sum(1 for item in assessments if item.live_qualified)
    codes = list(reason_codes)
    if zero_qualified:
        codes = [
            "zero_live_qualified_backends",
            "zero_qualified_is_valid_honest_state",
            *codes,
        ]
        disposition = LiveBackendDisposition.ZERO_QUALIFIED
    return LiveBackendGateResult(
        disposition=disposition,
        closed_outcome=CLOSED_OUTCOME_UNAVAILABLE,
        selected_backend=None,
        fallback_attempted=False,
        reason_codes=_reasons(*codes, "typed_unavailable", "no_fallback_success"),
        assessments=tuple(assessments),
        rejection_code=rejection_code,
        message=message
        or "no live-qualified backend available for storage selection",
        live_qualified_count=live_count,
        zero_qualified_is_valid_honest_state=zero_qualified or live_count == 0,
    )


def select_storage_backend(
    candidates: Sequence[LiveBackendEvidence] | None = None,
    *,
    now: datetime | None = None,
    availabilities: Mapping[str, str] | None = None,
    require: bool = False,
) -> LiveBackendGateResult:
    """Select a storage backend that is currently live-qualified.

    Candidates are assessed in order. The first live-qualified backend is
    selected. Demoted (stale/degraded/revoked) and otherwise nonqualifying
    backends are skipped **without** attempting a success-yielding fallback.

    When no candidate qualifies, returns typed ``Unavailable`` with
    ``fallback_attempted=False``. If ``require`` is True, raises
    :class:`LiveBackendUnavailable` instead of returning.
    """

    reference = _utc_now(now)
    evidence_list = tuple(candidates or ())
    availability_map = dict(availabilities or {})
    assessments: list[LiveBackendAssessment] = []

    for evidence in evidence_list:
        if not isinstance(evidence, LiveBackendEvidence):
            raise LiveBackendGateError(
                "candidates must contain LiveBackendEvidence instances"
            )
        assessment = assess_live_evidence(
            evidence,
            now=reference,
            availability=availability_map.get(evidence.backend_name),
        )
        assessments.append(assessment)
        if assessment.live_qualified:
            result = LiveBackendGateResult(
                disposition=LiveBackendDisposition.LIVE_QUALIFIED,
                # Qualification is a predicate over the evidence product, not an
                # effectful closed outcome. Only failures use Unavailable.
                closed_outcome=None,
                selected_backend=evidence.backend_name,
                fallback_attempted=False,
                reason_codes=_reasons(
                    "storage_selection_requires_current_live_evidence",
                    *assessment.reason_codes,
                ),
                assessments=tuple(assessments),
                rejection_code=None,
                message=f"selected live-qualified backend {evidence.backend_name}",
                live_qualified_count=sum(1 for item in assessments if item.live_qualified),
                zero_qualified_is_valid_honest_state=False,
            )
            return result

    # No live-qualified backend. Any demotions are recorded; never invent a
    # successful selection from hermetic/configured/stale evidence.
    demoted = [item for item in assessments if item.demoted]
    zero = len(assessments) == 0 or all(not item.live_qualified for item in assessments)
    reason_codes: list[str] = ["storage_selection_requires_current_live_evidence"]
    if demoted:
        reason_codes.append("demoted_candidates_skipped_without_fallback")
        reason_codes.extend(
            item.demotion_reason.value
            for item in demoted
            if item.demotion_reason is not None
        )
    if not assessments:
        reason_codes.append("empty_candidate_set")

    result = _unavailable_result(
        assessments=assessments,
        reason_codes=reason_codes,
        zero_qualified=zero,
        message="no live-qualified backend available for storage selection",
    )
    if require:
        raise LiveBackendUnavailable(result)
    return result


def require_live_qualified(
    result: LiveBackendGateResult,
) -> LiveBackendGateResult:
    """Raise typed Unavailable unless ``result`` selected a live-qualified backend."""

    if result.production_supported and result.selected_backend is not None:
        return result
    if result.closed_outcome == CLOSED_OUTCOME_UNAVAILABLE:
        raise LiveBackendUnavailable(result)
    unavailable = _unavailable_result(
        assessments=result.assessments,
        reason_codes=result.reason_codes,
        zero_qualified=result.live_qualified_count == 0,
        rejection_code=result.rejection_code or "E_CAPABILITY_MISSING",
        message=result.message,
    )
    raise LiveBackendUnavailable(unavailable)


def evaluate_provider_adapter(
    type_name: str,
    *,
    evidence: LiveBackendEvidence | None = None,
    catalog: Any | None = None,
    configuration: Mapping[str, Any] | None = None,
    receipts: Mapping[str, Any] | None = None,
    runtime_factories: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> LiveBackendAssessment:
    """Integrate the exact Kit provider-adapter selector seam.

    Resolves ``type_name`` through ``ProviderAdapterCatalog`` (configured →
    runtime-ready ladder) and combines that availability with the supplied
    live evidence product. Catalog runtime-ready alone never promotes to live
    qualification without current live evidence.
    """

    reference = _utc_now(now)
    availability_value: str | None = None
    if catalog is None and (receipts is not None or runtime_factories is not None):
        from ipfs_kit_py.backends.provider_adapters import ProviderAdapterCatalog

        catalog = ProviderAdapterCatalog(
            receipts=receipts,
            runtime_factories=runtime_factories,
            now=reference,
        )
    if catalog is not None:
        adapter = catalog.resolve(type_name, configuration=configuration)
        availability_value = getattr(
            getattr(adapter, "availability", None), "value", None
        )
        if availability_value is None and hasattr(adapter, "availability"):
            availability_value = str(adapter.availability)

    if evidence is None:
        # Inventory / catalog presence without a live evidence product is
        # nonqualifying. Freshness stays "current" only as an inventory
        # annotation timestamp so automatic stale demotion does not mask the
        # real availability / non-live reason codes.
        evidence = LiveBackendEvidence(
            backend_name=type_name,
            origin="declared",
            environment="conditional"
            if availability_value
            in {"receipt-required", "canonical-adapter-missing", "runtime-ready"}
            else "hermetic",
            freshness="current",
            authority="unchecked",
            policy="unchecked",
            integrity="unchecked",
        )
    elif evidence.backend_name != type_name:
        raise LiveBackendGateError(
            f"evidence.backend_name {evidence.backend_name!r} does not match "
            f"type_name {type_name!r}"
        )

    return assess_live_evidence(
        evidence, now=reference, availability=availability_value
    )


def select_from_provider_catalog(
    candidates: Sequence[str] | None = None,
    *,
    live_evidence: Mapping[str, LiveBackendEvidence] | None = None,
    catalog: Any | None = None,
    configurations: Mapping[str, Mapping[str, Any]] | None = None,
    receipts: Mapping[str, Any] | None = None,
    runtime_factories: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    require: bool = False,
) -> LiveBackendGateResult:
    """Select among inventoried backends using the provider catalog seam.

    Each candidate is resolved through the catalog and assessed against its
    live evidence (if any). Missing live evidence demotes / nonqualifies.
    No hidden fallback is attempted when the preferred candidate fails.
    """

    reference = _utc_now(now)
    from ipfs_kit_py.backends.provider_adapters import ProviderAdapterCatalog
    from ipfs_kit_py.backends.spec import BACKEND_SPECS

    if catalog is None:
        catalog = ProviderAdapterCatalog(
            receipts=receipts,
            runtime_factories=runtime_factories,
            now=reference,
        )

    names: Sequence[str]
    if candidates is None:
        names = tuple(sorted(BACKEND_SPECS))
    else:
        names = tuple(candidates)

    evidence_map = dict(live_evidence or {})
    configs = dict(configurations or {})
    assessments: list[LiveBackendAssessment] = []

    for name in names:
        assessment = evaluate_provider_adapter(
            name,
            evidence=evidence_map.get(name),
            catalog=catalog,
            configuration=configs.get(name),
            now=reference,
        )
        assessments.append(assessment)
        if assessment.live_qualified:
            return LiveBackendGateResult(
                disposition=LiveBackendDisposition.LIVE_QUALIFIED,
                closed_outcome=None,
                selected_backend=name,
                fallback_attempted=False,
                reason_codes=_reasons(
                    "storage_selection_requires_current_live_evidence",
                    *assessment.reason_codes,
                ),
                assessments=tuple(assessments),
                live_qualified_count=sum(
                    1 for item in assessments if item.live_qualified
                ),
                message=f"selected live-qualified backend {name}",
            )

    demoted = [item for item in assessments if item.demoted]
    reason_codes = ["storage_selection_requires_current_live_evidence"]
    if demoted:
        reason_codes.append("demoted_candidates_skipped_without_fallback")
    # Honest zero-qualified inventory (default Kit state) remains valid.
    zero = all(not item.live_qualified for item in assessments)
    result = _unavailable_result(
        assessments=assessments,
        reason_codes=reason_codes,
        zero_qualified=zero,
    )
    if require:
        raise LiveBackendUnavailable(result)
    return result


def current_live_evidence(
    backend_name: str,
    *,
    operation: str = "storage",
    receipt_id: str = "live-receipt",
    source_release: str = "formal-assurance-control-plane",
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    now: datetime | None = None,
    limitations: Iterable[str] = (),
    extra_evidence: Mapping[str, str] | None = None,
) -> LiveBackendEvidence:
    """Build a minimal **current** live evidence product for tests / callers.

    Does not contact live backends. Callers must supply authentic receipts in
    production; this helper only constructs the dimension/evidence shape.
    """

    reference = _utc_now(now)
    issued = issued_at or (reference.replace(microsecond=0))
    expires = expires_at
    if expires is None:
        # Default one-day window; callers should override with real expiry.
        from datetime import timedelta

        expires = issued + timedelta(days=1)
    bag = {
        "live_qualification_receipt": receipt_id,
        "current_capability_admission": f"admit:{backend_name}:{operation}",
        "authenticated_host_policy_decision": "host-policy:allowed",
    }
    if extra_evidence:
        bag.update({str(k): str(v) for k, v in extra_evidence.items()})
    return LiveBackendEvidence(
        backend_name=backend_name,
        operation=operation,
        origin="live_observed",
        integrity="signature_valid",
        authority="valid",
        policy="allowed",
        proof="verified",
        freshness="current",
        effect="observed",
        environment="live",
        review="machine_reviewed",
        receipt_id=receipt_id,
        source_release=source_release,
        issued_at=issued,
        expires_at=expires,
        signature_valid=True,
        degraded=False,
        limitations=tuple(limitations),
        evidence_bag=bag,
    )


__all__ = [
    "SCHEMA",
    "SCHEMA_VERSION",
    "TASK_ID",
    "GOAL_ID",
    "FCA_RELEASE",
    "FCA_VOCABULARY_SCHEMA",
    "CLOSED_OUTCOME_UNAVAILABLE",
    "UNSAFE_PROMOTION",
    "LiveBackendGateError",
    "LiveBackendUnavailable",
    "DemotionReason",
    "LiveBackendDisposition",
    "LiveBackendEvidence",
    "LiveBackendAssessment",
    "LiveBackendGateResult",
    "assess_live_evidence",
    "demote_if_not_current",
    "is_live_qualified",
    "select_storage_backend",
    "require_live_qualified",
    "evaluate_provider_adapter",
    "select_from_provider_catalog",
    "current_live_evidence",
]
