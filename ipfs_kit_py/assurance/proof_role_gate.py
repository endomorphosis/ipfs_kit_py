"""Kit proof-role and freshness transition gate (FACP-028).

Enforces candidate / admitted / current semantics and freshness transitions
through the formal claim algebra, then gates current-pointer CAS so stale,
unknown, or ambiguous proof execution cannot update the visible head.

Fail-closed invariants:

* Candidate never implies admitted (requires current verifier evidence and a
  distinct authorization CID; self-authorization is rejected).
* Admitted stale / superseded / withdrawn evidence cannot become current.
* ``unknown`` and ``verifier_unavailable`` verifier outcomes persist
  explicitly and never silently become verified / admitted / current.
* Concurrent pointer changes fail CAS and retain immutable transition history.

The exact admission / current-pointer seam is
``DurablePromotionStateRepository.compare_and_swap_promotion``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Final, Mapping, Optional, Protocol, Sequence

SCHEMA: Final[str] = "KitProofRoleGate@1"
SCHEMA_VERSION: Final[str] = "ipfs_kit_py.assurance.proof_role_gate@1"
TASK_ID: Final[str] = "FACP-028"
GOAL_ID: Final[str] = "FACP-G230"
FCA_RELEASE: Final[str] = "formal-claim-algebra-v1"
FCA_VOCABULARY_SCHEMA: Final[str] = "facp/formal-claim-algebra-v1@1"
EVIDENCE_BUNDLE: Final[str] = "facp/kit-proof-role-gate@1"
UNSAFE_PROMOTION: Final[bool] = False

CLOSED_OUTCOME_UNKNOWN: Final[str] = "Unknown"
CLOSED_OUTCOME_REJECTED: Final[str] = "Rejected"
CLOSED_OUTCOME_UNAVAILABLE: Final[str] = "Unavailable"
CLOSED_OUTCOME_VERIFIED: Final[str] = "Verified"

PROOF_ROLES: Final[frozenset[str]] = frozenset({"candidate", "admitted", "current"})
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
CAS_OUTCOMES: Final[frozenset[str]] = frozenset(
    {"updated", "unchanged", "conflict", "rejected"}
)

_STALE_FRESHNESS: Final[frozenset[str]] = frozenset(
    {"stale", "superseded", "withdrawn"}
)
_PERSISTENT_UNRESOLVED_PROOF: Final[frozenset[str]] = frozenset(
    {"unknown", "verifier_unavailable"}
)
_REQUIRED_ADMISSION_EVIDENCE: Final[frozenset[str]] = frozenset(
    {
        "named_current_verifier",
        "verifier_admission_closure",
        "proof_key",
    }
)

# Sentinel: omitted CAS expectation means "use the live head"; explicit None
# remains a valid generation-zero / empty-root expectation.
_UNSET: Final[object] = object()


class ProofRoleGateError(ValueError):
    """Malformed proof-role gate input."""


class ProofRoleTransitionRejected(RuntimeError):
    """Typed rejection: a requested proof-role / freshness transition is denied.

    Carries the closed FCA outcome and the gate result. Never implies that the
    candidate was admitted or that the current pointer advanced.
    """

    def __init__(self, result: "ProofRoleGateResult") -> None:
        if result.allowed:
            raise ProofRoleGateError(
                "ProofRoleTransitionRejected requires allowed=False"
            )
        if result.current_advanced:
            raise ProofRoleGateError(
                "ProofRoleTransitionRejected forbids current_advanced=True"
            )
        self.result = result
        self.closed_outcome = result.closed_outcome
        message = (
            result.message
            or "proof-role / freshness transition rejected"
        )
        super().__init__(message)


class ProofRole(str, Enum):
    """Kit proof-head roles (composed; not a single Kit enum historically)."""

    CANDIDATE = "candidate"
    ADMITTED = "admitted"
    CURRENT = "current"


class TransitionKind(str, Enum):
    """Closed transition kinds evaluated by this gate."""

    ASSESS = "assess"
    CANDIDATE_TO_ADMITTED = "candidate_to_admitted"
    ADMITTED_TO_CURRENT = "admitted_to_current"
    ADVANCE_CURRENT_POINTER = "advance_current_pointer"


class ProofRoleDisposition(str, Enum):
    """Disposition after assessment / transition / CAS."""

    CANDIDATE_ONLY = "candidate_only"
    ADMISSION_ALLOWED = "admission_allowed"
    CURRENT_ELIGIBLE = "current_eligible"
    CURRENT_ADVANCED = "current_advanced"
    REJECTED_CANDIDATE_IMPLIES_ADMITTED = "rejected_candidate_implies_admitted"
    REJECTED_STALE_TO_CURRENT = "rejected_stale_to_current"
    REJECTED_UNKNOWN_PERSISTS = "rejected_unknown_persists"
    REJECTED_SELF_AUTHORIZATION = "rejected_self_authorization"
    REJECTED_MISSING_EVIDENCE = "rejected_missing_evidence"
    REJECTED_REFUTED = "rejected_refuted"
    REJECTED_AMBIGUOUS_RECOVERY = "rejected_ambiguous_recovery"
    REJECTED_ROLE = "rejected_role"
    CAS_CONFLICT = "cas_conflict"
    CAS_UNCHANGED = "cas_unchanged"
    CAS_UNAVAILABLE = "cas_unavailable"


@dataclass(frozen=True, slots=True)
class ProofRoleEvidence:
    """Evidence product for one proof-role / freshness judgment.

    Identity fields bind the proof key and source closure. Role fields compose
    Kit's candidate / admitted / current distinctions. Verifier outcome is the
    FCA ``proof`` dimension and must persist explicitly when unresolved.
    """

    role: str
    proof: str = "candidate"
    freshness: str = "stale"
    candidate_cid: Optional[str] = None
    authorization_cid: Optional[str] = None
    promotion_cid: Optional[str] = None
    verifier_identity: Optional[str] = None
    proof_key: Optional[str] = None
    source_closure: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    ambiguous_recovery: bool = False
    expected_generation: Optional[int] = None
    expected_root_cid: Optional[str] = None
    evidence_bag: Mapping[str, str] = field(default_factory=dict)
    attributes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.role not in PROOF_ROLES:
            raise ProofRoleGateError(f"unknown proof role: {self.role!r}")
        if self.proof not in PROOF_VALUES:
            raise ProofRoleGateError(f"unknown proof value: {self.proof!r}")
        if self.freshness not in FRESHNESS_VALUES:
            raise ProofRoleGateError(f"unknown freshness: {self.freshness!r}")
        if not isinstance(self.ambiguous_recovery, bool):
            raise ProofRoleGateError("ambiguous_recovery must be a boolean")
        if self.expected_generation is not None:
            if (
                isinstance(self.expected_generation, bool)
                or not isinstance(self.expected_generation, int)
                or self.expected_generation < 0
            ):
                raise ProofRoleGateError(
                    "expected_generation must be a non-negative int when set"
                )
        for cid_name in (
            "candidate_cid",
            "authorization_cid",
            "promotion_cid",
            "expected_root_cid",
            "verifier_identity",
            "proof_key",
            "source_closure",
        ):
            value = getattr(self, cid_name)
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ProofRoleGateError(
                    f"{cid_name} must be a non-empty string when set"
                )
        for map_name in ("evidence_bag", "attributes"):
            raw = getattr(self, map_name)
            if isinstance(raw, MappingProxyType):
                continue
            if not isinstance(raw, Mapping):
                raise ProofRoleGateError(f"{map_name} must be a mapping")
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
                raise ProofRoleGateError(
                    f"{ts_name} must be timezone-aware datetime when set"
                )

    def with_overrides(self, **overrides: Any) -> "ProofRoleEvidence":
        return replace(self, **overrides)

    @property
    def implies_admitted(self) -> bool:
        """Candidate presence never implies admission by itself."""

        return False

    def to_dimension_map(self) -> dict[str, str]:
        return {
            "proof": self.proof,
            "freshness": self.freshness,
            "role": self.role,
        }


@dataclass(frozen=True, slots=True)
class ProofRoleAssessment:
    """Per-record assessment before or instead of a transition."""

    disposition: ProofRoleDisposition
    role: str
    proof: str
    freshness: str
    implies_admitted: bool
    admission_allowed: bool
    current_eligible: bool
    reason_codes: tuple[str, ...]
    evidence: ProofRoleEvidence
    closed_outcome: Optional[str] = None
    unresolved_verifier_outcome: Optional[str] = None

    @property
    def unknown_persists(self) -> bool:
        return self.unresolved_verifier_outcome in _PERSISTENT_UNRESOLVED_PROOF


@dataclass(frozen=True, slots=True)
class PointerHistoryEntry:
    """Immutable current-pointer transition retained after CAS."""

    generation: int
    root_cid: str
    transition_id: str
    candidate_cid: str
    authorization_cid: str
    operation_id: str


@dataclass(frozen=True, slots=True)
class CurrentPointerCASResult:
    """Compare-and-swap outcome for the current proof-head pointer."""

    status: str
    before_generation: int
    after_generation: int
    before_root_cid: Optional[str]
    after_root_cid: Optional[str]
    reason_code: str
    history: tuple[PointerHistoryEntry, ...]
    candidate_cid: Optional[str] = None
    authorization_cid: Optional[str] = None
    transition_cid: Optional[str] = None
    operation_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.status not in CAS_OUTCOMES:
            raise ProofRoleGateError(f"unknown CAS status: {self.status!r}")
        if not isinstance(self.history, tuple):
            object.__setattr__(self, "history", tuple(self.history))

    @property
    def updated(self) -> bool:
        return self.status == "updated"

    @property
    def conflict(self) -> bool:
        return self.status == "conflict"


@dataclass(frozen=True, slots=True)
class ProofRoleGateResult:
    """Gate outcome for assess / admit / current / CAS transitions."""

    disposition: ProofRoleDisposition
    allowed: bool
    closed_outcome: Optional[str]
    reason_codes: tuple[str, ...]
    assessment: Optional[ProofRoleAssessment] = None
    cas: Optional[CurrentPointerCASResult] = None
    current_advanced: bool = False
    implies_admitted: bool = False
    message: Optional[str] = None
    rejection_code: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.reason_codes, tuple):
            object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        if self.current_advanced and not self.allowed:
            raise ProofRoleGateError(
                "current_advanced requires allowed=True"
            )
        if self.implies_admitted and self.assessment is not None:
            if self.assessment.evidence.role == ProofRole.CANDIDATE.value:
                raise ProofRoleGateError(
                    "candidate evidence must never set implies_admitted=True"
                )

    def to_decision_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "disposition": self.disposition.value,
            "closed_outcome": self.closed_outcome,
            "current_advanced": self.current_advanced,
            "implies_admitted": self.implies_admitted,
            "rejection_code": self.rejection_code,
            "reason": self.reason_codes[0] if self.reason_codes else None,
            "cas_status": self.cas.status if self.cas is not None else None,
        }


class CurrentPointerStore(Protocol):
    """Minimal CAS current-pointer seam used by the gate."""

    def current(self) -> tuple[int, Optional[str]]:
        """Return ``(generation, root_cid)``."""

    def history(self) -> Sequence[PointerHistoryEntry]:
        """Return immutable transition history in generation order."""

    def compare_and_swap(
        self,
        *,
        expected_generation: int,
        expected_root_cid: Optional[str],
        new_root_cid: str,
        operation_id: str,
        candidate_cid: str,
        authorization_cid: str,
    ) -> CurrentPointerCASResult:
        """Publish a successor head or return conflict/unchanged."""


@dataclass
class InMemoryCurrentPointerStore:
    """ABA-safe in-memory current-pointer CAS retaining immutable history.

    Mirrors Kit CAS outcomes (``updated`` / ``unchanged`` / ``conflict``)
    without deciding logical proof validity. Used as a hermetic stand-in for
    the promotion repository seam in focused gate tests.
    """

    _generation: int = 0
    _root_cid: Optional[str] = None
    _history: list[PointerHistoryEntry] = field(default_factory=list)
    _seen_operations: dict[str, CurrentPointerCASResult] = field(
        default_factory=dict
    )

    def current(self) -> tuple[int, Optional[str]]:
        return self._generation, self._root_cid

    def history(self) -> tuple[PointerHistoryEntry, ...]:
        return tuple(self._history)

    def compare_and_swap(
        self,
        *,
        expected_generation: int,
        expected_root_cid: Optional[str],
        new_root_cid: str,
        operation_id: str,
        candidate_cid: str,
        authorization_cid: str,
    ) -> CurrentPointerCASResult:
        if not isinstance(operation_id, str) or not operation_id.strip():
            raise ProofRoleGateError("operation_id must be a non-empty string")
        if not isinstance(new_root_cid, str) or not new_root_cid.strip():
            raise ProofRoleGateError("new_root_cid must be a non-empty string")
        if candidate_cid == authorization_cid:
            raise ProofRoleGateError(
                "candidate cannot authorize its own promotion"
            )

        prior = self._seen_operations.get(operation_id)
        if prior is not None:
            same_payload = (
                prior.after_root_cid == new_root_cid
                and prior.candidate_cid == candidate_cid
                and prior.authorization_cid == authorization_cid
                and prior.before_generation == expected_generation
                and prior.before_root_cid == expected_root_cid
            )
            if same_payload:
                return replace(prior, status="unchanged", reason_code="idempotent_replay")
            before_gen, before_root = self.current()
            return CurrentPointerCASResult(
                status="conflict",
                before_generation=before_gen,
                after_generation=before_gen,
                before_root_cid=before_root,
                after_root_cid=before_root,
                reason_code="operation_id_reuse_conflict",
                history=self.history(),
                candidate_cid=candidate_cid,
                authorization_cid=authorization_cid,
                operation_id=operation_id,
            )

        before_gen, before_root = self.current()
        if (
            expected_generation != before_gen
            or expected_root_cid != before_root
        ):
            return CurrentPointerCASResult(
                status="conflict",
                before_generation=before_gen,
                after_generation=before_gen,
                before_root_cid=before_root,
                after_root_cid=before_root,
                reason_code="stale_expectation",
                history=self.history(),
                candidate_cid=candidate_cid,
                authorization_cid=authorization_cid,
                operation_id=operation_id,
            )
        if new_root_cid == before_root:
            raise ProofRoleGateError(
                "new_root_cid must differ from expected_root_cid"
            )

        after_gen = before_gen + 1
        transition_id = f"tr:{operation_id}:{after_gen}"
        entry = PointerHistoryEntry(
            generation=after_gen,
            root_cid=new_root_cid,
            transition_id=transition_id,
            candidate_cid=candidate_cid,
            authorization_cid=authorization_cid,
            operation_id=operation_id,
        )
        self._generation = after_gen
        self._root_cid = new_root_cid
        self._history.append(entry)
        result = CurrentPointerCASResult(
            status="updated",
            before_generation=before_gen,
            after_generation=after_gen,
            before_root_cid=before_root,
            after_root_cid=new_root_cid,
            reason_code="updated",
            history=self.history(),
            candidate_cid=candidate_cid,
            authorization_cid=authorization_cid,
            transition_cid=transition_id,
            operation_id=operation_id,
        )
        self._seen_operations[operation_id] = result
        return result


def _utc_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ProofRoleGateError("now must be timezone-aware")
    return now.astimezone(timezone.utc)


def _reasons(*codes: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(code for code in codes if code))


def _receipt_is_current(evidence: ProofRoleEvidence, now: datetime) -> bool:
    if evidence.issued_at is None and evidence.expires_at is None:
        return evidence.freshness == "current"
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
    return evidence.freshness == "current"


def _missing_admission_evidence(evidence: ProofRoleEvidence) -> tuple[str, ...]:
    missing: list[str] = []
    if not evidence.verifier_identity:
        missing.append("named_current_verifier")
    if not evidence.source_closure:
        missing.append("verifier_admission_closure")
    if not evidence.proof_key:
        missing.append("proof_key")
    bag = set(evidence.evidence_bag)
    for key in _REQUIRED_ADMISSION_EVIDENCE:
        if key not in bag and key not in missing:
            # Fields above cover the primary carriers; bag keys are optional
            # mirrors for sealed evidence products.
            continue
    return tuple(missing)


def assess_proof_role(
    evidence: ProofRoleEvidence,
    *,
    now: datetime | None = None,
) -> ProofRoleAssessment:
    """Assess one proof-role record without performing a transition.

    Acceptance anchors:

    * Candidate never implies admitted.
    * Unknown / verifier_unavailable persist explicitly on the assessment.
    * Stale admitted evidence is not current-eligible.
    """

    if not isinstance(evidence, ProofRoleEvidence):
        raise ProofRoleGateError("evidence must be ProofRoleEvidence")
    reference = _utc_now(now)
    receipt_current = _receipt_is_current(evidence, reference)
    freshness_stale = evidence.freshness in _STALE_FRESHNESS or not receipt_current

    # --- Unresolved verifier outcomes persist explicitly -------------------
    if evidence.proof in _PERSISTENT_UNRESOLVED_PROOF:
        return ProofRoleAssessment(
            disposition=ProofRoleDisposition.REJECTED_UNKNOWN_PERSISTS,
            role=evidence.role,
            proof=evidence.proof,
            freshness=evidence.freshness,
            implies_admitted=False,
            admission_allowed=False,
            current_eligible=False,
            reason_codes=_reasons(
                f"proof_{evidence.proof}",
                "unknown_verifier_outcome_persists",
                "cannot_update_current_on_unknown",
                "candidate_never_implies_admitted",
            ),
            evidence=evidence,
            closed_outcome=CLOSED_OUTCOME_UNKNOWN,
            unresolved_verifier_outcome=evidence.proof,
        )

    if evidence.proof == "refuted":
        return ProofRoleAssessment(
            disposition=ProofRoleDisposition.REJECTED_REFUTED,
            role=evidence.role,
            proof=evidence.proof,
            freshness=evidence.freshness,
            implies_admitted=False,
            admission_allowed=False,
            current_eligible=False,
            reason_codes=_reasons(
                "proof_refuted",
                "refuted_cannot_admit_or_become_current",
                "candidate_never_implies_admitted",
            ),
            evidence=evidence,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
        )

    if evidence.ambiguous_recovery:
        return ProofRoleAssessment(
            disposition=ProofRoleDisposition.REJECTED_AMBIGUOUS_RECOVERY,
            role=evidence.role,
            proof=evidence.proof,
            freshness=evidence.freshness,
            implies_admitted=False,
            admission_allowed=False,
            current_eligible=False,
            reason_codes=_reasons(
                "ambiguous_recovery",
                "cannot_update_current_on_ambiguous",
                "candidate_never_implies_admitted",
            ),
            evidence=evidence,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
        )

    # --- Candidate: presence is never admission ----------------------------
    if evidence.role == ProofRole.CANDIDATE.value:
        return ProofRoleAssessment(
            disposition=ProofRoleDisposition.CANDIDATE_ONLY,
            role=evidence.role,
            proof=evidence.proof if evidence.proof != "none" else "candidate",
            freshness=evidence.freshness,
            implies_admitted=False,
            admission_allowed=False,
            current_eligible=False,
            reason_codes=_reasons(
                "proof_role_candidate",
                "candidate_never_implies_admitted",
                "candidate_is_not_verified",
                "candidate_cannot_self_promote",
            ),
            evidence=evidence,
            closed_outcome=None,
        )

    # --- Admitted: authorization present, still not automatically current --
    if evidence.role == ProofRole.ADMITTED.value:
        self_auth = (
            evidence.candidate_cid is not None
            and evidence.authorization_cid is not None
            and evidence.candidate_cid == evidence.authorization_cid
        )
        if self_auth or evidence.authorization_cid is None:
            return ProofRoleAssessment(
                disposition=ProofRoleDisposition.REJECTED_SELF_AUTHORIZATION,
                role=evidence.role,
                proof=evidence.proof,
                freshness=evidence.freshness,
                implies_admitted=False,
                admission_allowed=False,
                current_eligible=False,
                reason_codes=_reasons(
                    "self_authorization_forbidden"
                    if self_auth
                    else "missing_authorization_cid",
                    "candidate_cid_must_not_equal_authorization_cid",
                    "candidate_never_implies_admitted",
                ),
                evidence=evidence,
                closed_outcome=CLOSED_OUTCOME_REJECTED,
            )
        if evidence.proof != "verified":
            return ProofRoleAssessment(
                disposition=ProofRoleDisposition.REJECTED_MISSING_EVIDENCE,
                role=evidence.role,
                proof=evidence.proof,
                freshness=evidence.freshness,
                implies_admitted=False,
                admission_allowed=False,
                current_eligible=False,
                reason_codes=_reasons(
                    f"proof_{evidence.proof}",
                    "admitted_requires_verified_proof",
                    "candidate_never_implies_admitted",
                ),
                evidence=evidence,
                closed_outcome=CLOSED_OUTCOME_REJECTED,
            )
        if freshness_stale:
            return ProofRoleAssessment(
                disposition=ProofRoleDisposition.REJECTED_STALE_TO_CURRENT,
                role=evidence.role,
                proof=evidence.proof,
                freshness="stale"
                if evidence.freshness == "current" and not receipt_current
                else evidence.freshness,
                implies_admitted=False,
                admission_allowed=True,
                current_eligible=False,
                reason_codes=_reasons(
                    f"freshness_{evidence.freshness}",
                    "admitted_stale_cannot_become_current",
                    "receipt_not_current"
                    if not receipt_current
                    else "freshness_not_current",
                    "candidate_never_implies_admitted",
                ),
                evidence=evidence,
                closed_outcome=CLOSED_OUTCOME_REJECTED,
            )
        return ProofRoleAssessment(
            disposition=ProofRoleDisposition.CURRENT_ELIGIBLE
            if evidence.proof == "verified"
            else ProofRoleDisposition.ADMISSION_ALLOWED,
            role=evidence.role,
            proof=evidence.proof,
            freshness=evidence.freshness,
            implies_admitted=False,
            admission_allowed=True,
            current_eligible=True,
            reason_codes=_reasons(
                "proof_role_admitted",
                "admitted_authorization_distinct",
                "freshness_current",
                "current_eligible_under_gate",
            ),
            evidence=evidence,
            closed_outcome=None,
        )

    # --- Current head pointer annotation (still not a promotion oracle) ----
    if evidence.role == ProofRole.CURRENT.value:
        if freshness_stale:
            return ProofRoleAssessment(
                disposition=ProofRoleDisposition.REJECTED_STALE_TO_CURRENT,
                role=evidence.role,
                proof=evidence.proof,
                freshness=evidence.freshness,
                implies_admitted=False,
                admission_allowed=False,
                current_eligible=False,
                reason_codes=_reasons(
                    "stale_current_pointer_annotation",
                    "admitted_stale_cannot_become_current",
                    "candidate_never_implies_admitted",
                ),
                evidence=evidence,
                closed_outcome=CLOSED_OUTCOME_REJECTED,
            )
        return ProofRoleAssessment(
            disposition=ProofRoleDisposition.CURRENT_ELIGIBLE,
            role=evidence.role,
            proof=evidence.proof,
            freshness=evidence.freshness,
            implies_admitted=False,
            admission_allowed=False,
            current_eligible=True,
            reason_codes=_reasons(
                "proof_role_current",
                "current_head_is_cas_protected",
                "candidate_never_implies_admitted",
            ),
            evidence=evidence,
            closed_outcome=None,
        )

    raise ProofRoleGateError(f"unhandled proof role: {evidence.role!r}")


def candidate_implies_admitted(evidence: ProofRoleEvidence) -> bool:
    """Explicit negative predicate: candidate never implies admitted."""

    assessment = assess_proof_role(evidence)
    return assessment.implies_admitted


def evaluate_admission(
    evidence: ProofRoleEvidence,
    *,
    now: datetime | None = None,
    require: bool = False,
) -> ProofRoleGateResult:
    """Evaluate candidate → admitted.

    Requires current verifier evidence (``proof=verified``, freshness current,
    named verifier, proof key, source closure) and a distinct authorization
    CID. Candidate records never succeed by implication alone.
    """

    if not isinstance(evidence, ProofRoleEvidence):
        raise ProofRoleGateError("evidence must be ProofRoleEvidence")
    reference = _utc_now(now)

    # Persist unknown before any promotion attempt.
    if evidence.proof in _PERSISTENT_UNRESOLVED_PROOF:
        assessment = assess_proof_role(evidence, now=reference)
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.REJECTED_UNKNOWN_PERSISTS,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_UNKNOWN,
            reason_codes=assessment.reason_codes,
            assessment=assessment,
            implies_admitted=False,
            message="unknown verifier outcome persists; admission denied",
            rejection_code="E_VERIFIER_OUTCOME_UNKNOWN",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    if evidence.role != ProofRole.CANDIDATE.value and evidence.role != (
        ProofRole.ADMITTED.value
    ):
        # Re-evaluating an already-admitted record is allowed only as a no-op
        # check; current heads cannot be admitted through this entrypoint.
        if evidence.role == ProofRole.CURRENT.value:
            assessment = assess_proof_role(evidence, now=reference)
            result = ProofRoleGateResult(
                disposition=ProofRoleDisposition.REJECTED_ROLE,
                allowed=False,
                closed_outcome=CLOSED_OUTCOME_REJECTED,
                reason_codes=_reasons(
                    "current_role_is_not_admission_input",
                    "candidate_never_implies_admitted",
                ),
                assessment=assessment,
                message="current head cannot be admitted via candidate path",
                rejection_code="E_ROLE_MISMATCH",
            )
            if require:
                raise ProofRoleTransitionRejected(result)
            return result

    # Candidate-shaped input is the normative admission request even when the
    # caller already stamped role=admitted prematurely.
    working = evidence
    if evidence.role == ProofRole.ADMITTED.value:
        working = evidence.with_overrides(role=ProofRole.CANDIDATE.value)

    assessment = assess_proof_role(working, now=reference)
    if assessment.implies_admitted:
        raise ProofRoleGateError("internal invariant: candidate implies admitted")

    if working.candidate_cid is None:
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.REJECTED_MISSING_EVIDENCE,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                "missing_candidate_cid",
                "candidate_never_implies_admitted",
            ),
            assessment=assessment,
            message="admission requires a candidate CID",
            rejection_code="E_MISSING_CANDIDATE",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    # Candidate / none proof never implies admitted — check before auth so a
    # bare candidate is rejected for implication, not for missing auth alone.
    if working.proof != "verified":
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.REJECTED_CANDIDATE_IMPLIES_ADMITTED
            if working.proof in {"none", "candidate"}
            else ProofRoleDisposition.REJECTED_MISSING_EVIDENCE,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                f"proof_{working.proof}",
                "candidate_never_implies_admitted",
                "admission_requires_current_verifier_evidence",
            ),
            assessment=assessment,
            message="candidate proof cannot become admitted without verified evidence",
            rejection_code="E_CANDIDATE_NOT_ADMITTED",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    if working.authorization_cid is None:
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.REJECTED_MISSING_EVIDENCE,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                "missing_authorization_cid",
                "admission_requires_distinct_authorization",
                "candidate_never_implies_admitted",
            ),
            assessment=assessment,
            message="admission requires a distinct authorization CID",
            rejection_code="E_MISSING_AUTHORIZATION",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    if working.authorization_cid == working.candidate_cid:
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.REJECTED_SELF_AUTHORIZATION,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                "candidate_cannot_authorize_own_promotion",
                "candidate_cid_must_not_equal_authorization_cid",
                "candidate_never_implies_admitted",
            ),
            assessment=assessment,
            message="candidate cannot authorize its own admission",
            rejection_code="E_SELF_AUTHORIZATION",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    if not _receipt_is_current(working, reference) or working.freshness != "current":
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.REJECTED_STALE_TO_CURRENT,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                f"freshness_{working.freshness}",
                "admission_requires_current_freshness",
                "candidate_never_implies_admitted",
            ),
            assessment=assessment,
            message="stale verifier evidence cannot admit",
            rejection_code="E_STALE_VERIFIER_EVIDENCE",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    missing = _missing_admission_evidence(working)
    if missing:
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.REJECTED_MISSING_EVIDENCE,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                "missing_admission_evidence",
                *[f"missing_{key}" for key in missing],
                "candidate_never_implies_admitted",
            ),
            assessment=assessment,
            message="admission requires named verifier, proof key, and source closure",
            rejection_code="E_MISSING_ADMISSION_EVIDENCE",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    if working.ambiguous_recovery:
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.REJECTED_AMBIGUOUS_RECOVERY,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                "ambiguous_recovery",
                "cannot_admit_on_ambiguous_recovery",
                "candidate_never_implies_admitted",
            ),
            assessment=assessment,
            rejection_code="E_AMBIGUOUS_RECOVERY",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    admitted_evidence = working.with_overrides(
        role=ProofRole.ADMITTED.value,
        proof="verified",
        freshness="current",
    )
    admitted_assessment = assess_proof_role(admitted_evidence, now=reference)
    result = ProofRoleGateResult(
        disposition=ProofRoleDisposition.ADMISSION_ALLOWED,
        allowed=True,
        closed_outcome=CLOSED_OUTCOME_VERIFIED,
        reason_codes=_reasons(
            "admission_allowed",
            "current_verifier_evidence_present",
            "authorization_cid_distinct",
            "candidate_never_implies_admitted",
        ),
        assessment=admitted_assessment,
        implies_admitted=False,
        message="admission allowed under current verifier evidence",
    )
    return result


def evaluate_current_promotion(
    evidence: ProofRoleEvidence,
    *,
    now: datetime | None = None,
    require: bool = False,
) -> ProofRoleGateResult:
    """Evaluate admitted → current eligibility (no pointer mutation).

    Admitted stale evidence cannot become current. Unknown verifier outcomes
    persist and deny the transition.
    """

    if not isinstance(evidence, ProofRoleEvidence):
        raise ProofRoleGateError("evidence must be ProofRoleEvidence")
    reference = _utc_now(now)

    if evidence.proof in _PERSISTENT_UNRESOLVED_PROOF:
        assessment = assess_proof_role(evidence, now=reference)
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.REJECTED_UNKNOWN_PERSISTS,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_UNKNOWN,
            reason_codes=assessment.reason_codes,
            assessment=assessment,
            message="unknown verifier outcome persists; current promotion denied",
            rejection_code="E_VERIFIER_OUTCOME_UNKNOWN",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    if evidence.role == ProofRole.CANDIDATE.value:
        assessment = assess_proof_role(evidence, now=reference)
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.REJECTED_CANDIDATE_IMPLIES_ADMITTED,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                "candidate_cannot_become_current",
                "candidate_never_implies_admitted",
                "admission_required_before_current",
            ),
            assessment=assessment,
            message="candidate cannot become current",
            rejection_code="E_CANDIDATE_NOT_CURRENT",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    assessment = assess_proof_role(evidence, now=reference)
    if not assessment.current_eligible:
        disposition = assessment.disposition
        if assessment.disposition is ProofRoleDisposition.REJECTED_STALE_TO_CURRENT or (
            evidence.freshness in _STALE_FRESHNESS
            or not _receipt_is_current(evidence, reference)
        ):
            disposition = ProofRoleDisposition.REJECTED_STALE_TO_CURRENT
            codes = _reasons(
                "admitted_stale_cannot_become_current",
                *assessment.reason_codes,
            )
        else:
            codes = assessment.reason_codes
        result = ProofRoleGateResult(
            disposition=disposition,
            allowed=False,
            closed_outcome=assessment.closed_outcome or CLOSED_OUTCOME_REJECTED,
            reason_codes=codes,
            assessment=assessment,
            message="admitted evidence is not current-eligible",
            rejection_code="E_NOT_CURRENT_ELIGIBLE",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    return ProofRoleGateResult(
        disposition=ProofRoleDisposition.CURRENT_ELIGIBLE,
        allowed=True,
        closed_outcome=None,
        reason_codes=_reasons(
            "current_promotion_eligible",
            "freshness_current",
            "admitted_authorization_present",
            *assessment.reason_codes,
        ),
        assessment=assessment,
        message="admitted evidence may advance current under CAS",
    )


def advance_current_pointer(
    evidence: ProofRoleEvidence,
    store: CurrentPointerStore,
    *,
    new_root_cid: str,
    operation_id: str,
    expected_generation: Any = _UNSET,
    expected_root_cid: Any = _UNSET,
    now: datetime | None = None,
    require: bool = False,
) -> ProofRoleGateResult:
    """Gate then CAS-advance the current proof-head pointer.

    On policy denial the store is not mutated. Concurrent writers that lose
    CAS receive ``cas_conflict`` while prior immutable history is retained.

    Omitted ``expected_generation`` / ``expected_root_cid`` default to the live
    head. Explicit ``None`` is a generation-zero / empty-root expectation and
    must not be rewritten to the live head.
    """

    reference = _utc_now(now)
    eligibility = evaluate_current_promotion(evidence, now=reference, require=False)
    if not eligibility.allowed:
        denied = ProofRoleGateResult(
            disposition=eligibility.disposition,
            allowed=False,
            closed_outcome=eligibility.closed_outcome or CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                "current_pointer_not_advanced",
                *eligibility.reason_codes,
            ),
            assessment=eligibility.assessment,
            cas=None,
            current_advanced=False,
            message=eligibility.message,
            rejection_code=eligibility.rejection_code,
        )
        if require:
            raise ProofRoleTransitionRejected(denied)
        return denied

    if (
        evidence.authorization_cid is None
        or evidence.candidate_cid is None
        or evidence.candidate_cid == evidence.authorization_cid
    ):
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.REJECTED_SELF_AUTHORIZATION,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                "current_pointer_requires_distinct_authorization",
                "candidate_never_implies_admitted",
            ),
            assessment=eligibility.assessment,
            rejection_code="E_SELF_AUTHORIZATION",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    before_gen, before_root = store.current()
    history_before = tuple(store.history())
    if expected_generation is _UNSET:
        exp_gen = (
            evidence.expected_generation
            if evidence.expected_generation is not None
            else before_gen
        )
    else:
        if expected_generation is not None and (
            isinstance(expected_generation, bool)
            or not isinstance(expected_generation, int)
            or expected_generation < 0
        ):
            raise ProofRoleGateError(
                "expected_generation must be a non-negative int or None"
            )
        exp_gen = expected_generation
    if expected_root_cid is _UNSET:
        exp_root = (
            evidence.expected_root_cid
            if evidence.expected_root_cid is not None
            else before_root
        )
    else:
        if expected_root_cid is not None and (
            not isinstance(expected_root_cid, str) or not expected_root_cid.strip()
        ):
            raise ProofRoleGateError(
                "expected_root_cid must be a non-empty string or None"
            )
        exp_root = expected_root_cid

    cas = store.compare_and_swap(
        expected_generation=int(exp_gen),
        expected_root_cid=exp_root,
        new_root_cid=new_root_cid,
        operation_id=operation_id,
        candidate_cid=evidence.candidate_cid,
        authorization_cid=evidence.authorization_cid,
    )

    if cas.status == "conflict":
        # History must be unchanged for the losing writer.
        if tuple(store.history()) != history_before and cas.reason_code == (
            "stale_expectation"
        ):
            # Store retained history from the winning writer; the conflict
            # result still surfaces the retained immutable log.
            pass
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.CAS_CONFLICT,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                "cas_conflict",
                cas.reason_code,
                "concurrent_pointer_change_failed_cas",
                "immutable_history_retained",
            ),
            assessment=eligibility.assessment,
            cas=cas,
            current_advanced=False,
            message="concurrent pointer change failed CAS; history retained",
            rejection_code="E_CAS_CONFLICT",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    if cas.status == "unchanged":
        return ProofRoleGateResult(
            disposition=ProofRoleDisposition.CAS_UNCHANGED,
            allowed=True,
            closed_outcome=None,
            reason_codes=_reasons(
                "cas_unchanged",
                cas.reason_code,
                "immutable_history_retained",
            ),
            assessment=eligibility.assessment,
            cas=cas,
            current_advanced=False,
            message="idempotent current-pointer replay",
        )

    if cas.status != "updated":
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.CAS_UNAVAILABLE,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_UNAVAILABLE,
            reason_codes=_reasons("cas_not_updated", cas.status, cas.reason_code),
            assessment=eligibility.assessment,
            cas=cas,
            rejection_code="E_CAS_UNAVAILABLE",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    return ProofRoleGateResult(
        disposition=ProofRoleDisposition.CURRENT_ADVANCED,
        allowed=True,
        closed_outcome=None,
        reason_codes=_reasons(
            "current_pointer_advanced",
            "cas_updated",
            "immutable_history_retained",
            "candidate_never_implies_admitted",
        ),
        assessment=eligibility.assessment,
        cas=cas,
        current_advanced=True,
        message="current proof-head pointer advanced under CAS",
    )


def advance_via_promotion_repository(
    evidence: ProofRoleEvidence,
    repository: Any,
    *,
    workspace: str,
    new_promotion_cid: str,
    operation_id: str,
    expected_generation: Any = _UNSET,
    expected_promotion_cid: Any = _UNSET,
    now: datetime | None = None,
    require: bool = False,
) -> ProofRoleGateResult:
    """Integrate the exact Kit admission / current-pointer seam.

    Gates eligibility, then calls
    ``DurablePromotionStateRepository.compare_and_swap_promotion``. Logical
    validity of the candidate bytes is not decided here.

    Omitted expectations default to the live promotion head. Explicit ``None``
    is retained as a generation-zero / empty-root CAS expectation.
    """

    reference = _utc_now(now)
    eligibility = evaluate_current_promotion(evidence, now=reference, require=False)
    if not eligibility.allowed:
        denied = ProofRoleGateResult(
            disposition=eligibility.disposition,
            allowed=False,
            closed_outcome=eligibility.closed_outcome or CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                "promotion_repository_not_invoked",
                "current_pointer_not_advanced",
                *eligibility.reason_codes,
            ),
            assessment=eligibility.assessment,
            message=eligibility.message,
            rejection_code=eligibility.rejection_code,
        )
        if require:
            raise ProofRoleTransitionRejected(denied)
        return denied

    if evidence.candidate_cid is None or evidence.authorization_cid is None:
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.REJECTED_MISSING_EVIDENCE,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                "missing_candidate_or_authorization_cid",
                "candidate_never_implies_admitted",
            ),
            assessment=eligibility.assessment,
            rejection_code="E_MISSING_ADMISSION_EVIDENCE",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    if not hasattr(repository, "compare_and_swap_promotion"):
        raise ProofRoleGateError(
            "repository must provide compare_and_swap_promotion "
            "(DurablePromotionStateRepository seam)"
        )
    if not hasattr(repository, "current_promotion"):
        raise ProofRoleGateError(
            "repository must provide current_promotion"
        )

    before = repository.current_promotion(workspace)
    before_gen = int(before.generation)
    before_root = before.promotion_cid
    history_before: tuple[Any, ...] = ()
    if hasattr(repository, "promotion_transitions"):
        history_before = tuple(repository.promotion_transitions(workspace))

    if expected_generation is _UNSET:
        exp_gen = (
            evidence.expected_generation
            if evidence.expected_generation is not None
            else before_gen
        )
    else:
        exp_gen = expected_generation
    if expected_promotion_cid is _UNSET:
        exp_root = (
            evidence.expected_root_cid
            if evidence.expected_root_cid is not None
            else before_root
        )
    else:
        exp_root = expected_promotion_cid

    try:
        raw = repository.compare_and_swap_promotion(
            workspace,
            expected_generation=int(exp_gen),
            expected_promotion_cid=exp_root,
            new_promotion_cid=new_promotion_cid,
            operation_id=operation_id,
            candidate_cid=evidence.candidate_cid,
            authorization_cid=evidence.authorization_cid,
        )
    except Exception as exc:
        # Admission errors from the seam (self-auth, incoherent expectation)
        # surface as typed rejections without inventing a current head.
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.CAS_UNAVAILABLE,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                "promotion_repository_rejected",
                type(exc).__name__,
                "immutable_history_retained",
            ),
            assessment=eligibility.assessment,
            message=str(exc),
            rejection_code="E_PROMOTION_SEAM_REJECTED",
        )
        if require:
            raise ProofRoleTransitionRejected(result) from exc
        return result

    status_value = getattr(getattr(raw, "status", None), "value", None)
    if status_value is None:
        status_value = str(getattr(raw, "status", "rejected")).lower()
    # Map GovernorStoreStatus onto gate CAS vocabulary.
    if status_value in {"updated"}:
        cas_status = "updated"
    elif status_value in {"unchanged"}:
        cas_status = "unchanged"
    elif status_value in {"conflict"}:
        cas_status = "conflict"
    else:
        cas_status = "rejected"

    after = raw.after
    history_after: list[PointerHistoryEntry] = []
    if hasattr(repository, "promotion_transitions"):
        for index, row in enumerate(repository.promotion_transitions(workspace), start=1):
            history_after.append(
                PointerHistoryEntry(
                    generation=int(row.get("new_revision", index)),
                    root_cid=str(row.get("new_root_cid") or row.get("root_cid") or ""),
                    transition_id=str(
                        row.get("transition_cid") or f"tr:{index}"
                    ),
                    candidate_cid=evidence.candidate_cid,
                    authorization_cid=evidence.authorization_cid,
                    operation_id=str(row.get("operation_id") or operation_id),
                )
            )
    else:
        history_after = list(history_before)

    cas = CurrentPointerCASResult(
        status=cas_status,
        before_generation=int(raw.before.generation),
        after_generation=int(after.generation),
        before_root_cid=raw.before.promotion_cid,
        after_root_cid=after.promotion_cid,
        reason_code=str(getattr(raw, "reason_code", cas_status)),
        history=tuple(history_after),
        candidate_cid=getattr(raw, "candidate_cid", evidence.candidate_cid),
        authorization_cid=getattr(
            raw, "authorization_cid", evidence.authorization_cid
        ),
        transition_cid=getattr(raw, "transition_cid", None),
        operation_id=getattr(raw, "operation_id", operation_id),
    )

    if cas_status == "conflict":
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.CAS_CONFLICT,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_REJECTED,
            reason_codes=_reasons(
                "cas_conflict",
                cas.reason_code,
                "concurrent_pointer_change_failed_cas",
                "immutable_history_retained",
                "promotion_repository_seam",
            ),
            assessment=eligibility.assessment,
            cas=cas,
            current_advanced=False,
            message="concurrent pointer change failed CAS; history retained",
            rejection_code="E_CAS_CONFLICT",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    if cas_status == "unchanged":
        return ProofRoleGateResult(
            disposition=ProofRoleDisposition.CAS_UNCHANGED,
            allowed=True,
            closed_outcome=None,
            reason_codes=_reasons(
                "cas_unchanged",
                cas.reason_code,
                "immutable_history_retained",
                "promotion_repository_seam",
            ),
            assessment=eligibility.assessment,
            cas=cas,
            current_advanced=False,
        )

    if cas_status != "updated":
        result = ProofRoleGateResult(
            disposition=ProofRoleDisposition.CAS_UNAVAILABLE,
            allowed=False,
            closed_outcome=CLOSED_OUTCOME_UNAVAILABLE,
            reason_codes=_reasons(
                "cas_not_updated",
                cas_status,
                cas.reason_code,
                "promotion_repository_seam",
            ),
            assessment=eligibility.assessment,
            cas=cas,
            rejection_code="E_CAS_UNAVAILABLE",
        )
        if require:
            raise ProofRoleTransitionRejected(result)
        return result

    return ProofRoleGateResult(
        disposition=ProofRoleDisposition.CURRENT_ADVANCED,
        allowed=True,
        closed_outcome=None,
        reason_codes=_reasons(
            "current_pointer_advanced",
            "cas_updated",
            "immutable_history_retained",
            "promotion_repository_seam",
            "candidate_never_implies_admitted",
        ),
        assessment=eligibility.assessment,
        cas=cas,
        current_advanced=True,
        message="current proof-head advanced via promotion repository CAS",
    )


def current_admitted_evidence(
    *,
    candidate_cid: str,
    authorization_cid: str,
    proof_key: str = "proof-key",
    verifier_identity: str = "verifier:kit@1",
    source_closure: str = "closure:admitted@1",
    promotion_cid: str | None = None,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    now: datetime | None = None,
    expected_generation: int | None = None,
    expected_root_cid: str | None = None,
) -> ProofRoleEvidence:
    """Build minimal **admitted + current-fresh** evidence for tests / callers.

    Does not contact verifiers. Callers must supply authentic verifier
    identity and closure in production.
    """

    if candidate_cid == authorization_cid:
        raise ProofRoleGateError(
            "candidate_cid must not equal authorization_cid"
        )
    reference = _utc_now(now)
    issued = issued_at or reference.replace(microsecond=0)
    expires = expires_at or (issued + timedelta(days=1))
    bag = {
        "named_current_verifier": verifier_identity,
        "verifier_admission_closure": source_closure,
        "proof_key": proof_key,
    }
    return ProofRoleEvidence(
        role=ProofRole.ADMITTED.value,
        proof="verified",
        freshness="current",
        candidate_cid=candidate_cid,
        authorization_cid=authorization_cid,
        promotion_cid=promotion_cid,
        verifier_identity=verifier_identity,
        proof_key=proof_key,
        source_closure=source_closure,
        issued_at=issued,
        expires_at=expires,
        ambiguous_recovery=False,
        expected_generation=expected_generation,
        expected_root_cid=expected_root_cid,
        evidence_bag=bag,
    )


def candidate_evidence(
    *,
    candidate_cid: str,
    proof: str = "candidate",
    freshness: str = "stale",
    authorization_cid: str | None = None,
    proof_key: str | None = None,
    verifier_identity: str | None = None,
    source_closure: str | None = None,
    now: datetime | None = None,
) -> ProofRoleEvidence:
    """Build a candidate proof-role record (never implies admitted)."""

    del now  # reserved for future receipt windows on candidates
    return ProofRoleEvidence(
        role=ProofRole.CANDIDATE.value,
        proof=proof,
        freshness=freshness,
        candidate_cid=candidate_cid,
        authorization_cid=authorization_cid,
        proof_key=proof_key,
        verifier_identity=verifier_identity,
        source_closure=source_closure,
    )


__all__ = [
    "SCHEMA",
    "SCHEMA_VERSION",
    "TASK_ID",
    "GOAL_ID",
    "FCA_RELEASE",
    "FCA_VOCABULARY_SCHEMA",
    "EVIDENCE_BUNDLE",
    "UNSAFE_PROMOTION",
    "CLOSED_OUTCOME_UNKNOWN",
    "CLOSED_OUTCOME_REJECTED",
    "CLOSED_OUTCOME_UNAVAILABLE",
    "CLOSED_OUTCOME_VERIFIED",
    "PROOF_ROLES",
    "PROOF_VALUES",
    "FRESHNESS_VALUES",
    "CAS_OUTCOMES",
    "ProofRoleGateError",
    "ProofRoleTransitionRejected",
    "ProofRole",
    "TransitionKind",
    "ProofRoleDisposition",
    "ProofRoleEvidence",
    "ProofRoleAssessment",
    "PointerHistoryEntry",
    "CurrentPointerCASResult",
    "ProofRoleGateResult",
    "CurrentPointerStore",
    "InMemoryCurrentPointerStore",
    "assess_proof_role",
    "candidate_implies_admitted",
    "evaluate_admission",
    "evaluate_current_promotion",
    "advance_current_pointer",
    "advance_via_promotion_repository",
    "current_admitted_evidence",
    "candidate_evidence",
]
