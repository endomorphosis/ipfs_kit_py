"""Crash recovery, idempotent replay, and concurrency fencing (AAE-038).

``recover_assurance_campaigns`` projects assurance-domain heads after the
existing ``DurableCoordinationStore.recover`` primitive rebuilds indexes from
immutable blocks.  It does not invent a second rebuild engine, object store,
WAL, or receipt hierarchy.

Authority rules (normative, fail-closed):

* Injected interruptions at every root-CAS durable boundary leave either the
  prior head or the sole durable successor; reopening + recovery resumes.
* Immutable completed artifacts and campaign/policy/merkle heads re-verify.
* Partial and ambiguous execution claims never become terminal success, and
  recovery never invents promotion or completion outcomes.
* Stale writers are rejected by expected-generation + expected-head CAS fencing
  (and by the explicit writer-fence helper) without overwriting newer heads.
* Corruption fails closed: reconstructed heads are omitted rather than partially
  promoted.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, Mapping, Optional, Protocol

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    DurableCoordinationStore,
    ROOT_CAS_INTERRUPTION_POINTS,
)
from ipfs_kit_py.adversarial_assurance_store.artifacts import (
    DurableAssuranceArtifactStore,
)
from ipfs_kit_py.adversarial_assurance_store.campaigns import (
    CampaignAdmissionError,
    CampaignPhase,
    CampaignStateSnapshot,
    CampaignStoreError,
    CampaignTransitionError,
    DurableAssuranceGapRepository,
    DurableMutationCampaignRepository,
    ExecutionClaimStatus,
    HistoryHeadSnapshot,
    assert_terminal_success_admissible,
    coerce_campaign_phase,
    coerce_execution_claim_status,
    validate_generation_expectation,
)
from ipfs_kit_py.adversarial_assurance_store.contracts import (
    ASSURANCE_NAMESPACE_PREFIX,
    AssuranceArtifactStoreContractError,
    AssuranceNamespaceRole,
    parse_assurance_namespace,
    validate_operation_id,
    validate_reason_code,
    validate_semantic_dag_json_cid,
    validate_verified_cid,
)
from ipfs_kit_py.adversarial_assurance_store.merkle import (
    DurableAssuranceCampaignMerkleRepository,
    MerkleIntegrityError,
    MerkleRootSnapshot,
    MerkleStoreError,
)
from ipfs_kit_py.adversarial_assurance_store.policy import (
    AssurancePolicyError,
    AssurancePolicyIntegrityError,
    AssurancePolicyVersionSnapshot,
    AssurancePromotionStateSnapshot,
    DurableAssurancePolicyRepository,
)

# ---------------------------------------------------------------------------
# Schema / interface constants
# ---------------------------------------------------------------------------

ASSURANCE_RECOVERY_INTERFACE: Final[str] = "AssuranceRecovery@1"
ASSURANCE_RECOVERY_REPORT_INTERFACE: Final[str] = "AssuranceRecoveryReport@1"
ASSURANCE_RECOVERY_SCHEMA: Final[str] = (
    "ipfs-kit.adversarial-assurance-store.recovery@1"
)
RECOVERY_MODULE_INTERFACE: Final[str] = ASSURANCE_RECOVERY_INTERFACE

# Required durable CAS interruption points reused from the coordination store.
# Tests inject a crash at each name; recovery must resume without ambiguity.
REQUIRED_CAS_INTERRUPTION_POINTS: Final[tuple[str, ...]] = tuple(
    ROOT_CAS_INTERRUPTION_POINTS
)
MAX_RECOVERY_ERRORS: Final[int] = 32

_HISTORY_ROLES: Final[frozenset[AssuranceNamespaceRole]] = frozenset(
    {
        AssuranceNamespaceRole.RECEIPTS,
        AssuranceNamespaceRole.GAPS,
    }
)

_CLOSED_ERROR_FIELDS: Final[frozenset[str]] = frozenset(("code", "message"))
_REPORT_FIELDS: Final[frozenset[str]] = frozenset(
    (
        "verified_blocks",
        "reconstructed_campaign_heads",
        "reconstructed_history_heads",
        "reconstructed_merkle_heads",
        "reconstructed_policy_heads",
        "reconstructed_promotion_heads",
        "ignored_idempotent_transitions",
        "errors",
    )
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AssuranceRecoveryError(ValueError):
    """Base error for assurance recovery admission or integrity failures."""


class AssuranceRecoveryAdmissionError(AssuranceRecoveryError):
    """Raised when a recovery or fencing request is rejected before mutation."""


class AssuranceRecoveryIntegrityError(AssuranceRecoveryError):
    """Raised when reconstructed evidence fails closed verification."""


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _closed_mapping(
    value: object, fields: frozenset[str], name: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AssuranceRecoveryIntegrityError(f"{name} must be a mapping")
    actual = frozenset(value)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        problems: list[str] = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        raise AssuranceRecoveryIntegrityError(
            f"{name} has {'; '.join(problems)}"
        )
    return value


def _require_nonnegative_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise AssuranceRecoveryIntegrityError(
            f"{name} must be a non-negative integer"
        )
    return value


def _campaign_snapshot_from_dict(value: Mapping[str, Any]) -> CampaignStateSnapshot:
    phase_raw = value.get("phase")
    claim_raw = value.get("execution_claim_status")
    phase = None if phase_raw is None else coerce_campaign_phase(str(phase_raw))
    claim = (
        None
        if claim_raw is None
        else coerce_execution_claim_status(str(claim_raw))
    )
    return CampaignStateSnapshot(
        namespace=str(value["namespace"]),
        state_cid=value.get("state_cid"),
        generation=int(value["generation"]),
        transition_cid=value.get("transition_cid"),
        phase=phase,
        campaign_id=value.get("campaign_id"),
        execution_claim_status=claim,
        receipt_cid=value.get("receipt_cid"),
    )


def _history_snapshot_from_dict(value: Mapping[str, Any]) -> HistoryHeadSnapshot:
    role = AssuranceNamespaceRole(str(value["role"]))
    return HistoryHeadSnapshot(
        namespace=str(value["namespace"]),
        head_cid=value.get("head_cid"),
        generation=int(value["generation"]),
        transition_cid=value.get("transition_cid"),
        role=role,
    )


def _merkle_snapshot_from_dict(value: Mapping[str, Any]) -> MerkleRootSnapshot:
    return MerkleRootSnapshot(
        namespace=str(value["namespace"]),
        root_cid=value.get("root_cid"),
        generation=int(value["generation"]),
        transition_cid=value.get("transition_cid"),
        campaign_id=value.get("campaign_id"),
        campaign_root=value.get("campaign_root"),
        required_set_completeness=value.get("required_set_completeness"),
        seal_manifest_cid=value.get("seal_manifest_cid"),
    )


@dataclass(frozen=True, slots=True)
class AssuranceRecoveryReport:
    """Pure assurance-domain recovery evidence (``AssuranceRecoveryReport@1``).

    Recovery may report verified blocks, reconstructed heads, ignored
    idempotent transitions, and closed error records.  It never invents
    promotion or terminal-success outcomes from partial or ambiguous evidence.
    """

    verified_blocks: int
    reconstructed_campaign_heads: tuple[CampaignStateSnapshot, ...]
    reconstructed_history_heads: tuple[HistoryHeadSnapshot, ...]
    reconstructed_merkle_heads: tuple[MerkleRootSnapshot, ...]
    reconstructed_policy_heads: tuple[AssurancePolicyVersionSnapshot, ...]
    reconstructed_promotion_heads: tuple[AssurancePromotionStateSnapshot, ...]
    ignored_idempotent_transitions: tuple[str, ...]
    errors: tuple[Mapping[str, str], ...]

    def __post_init__(self) -> None:
        _require_nonnegative_int(self.verified_blocks, "verified_blocks")
        if not isinstance(self.reconstructed_campaign_heads, tuple) or not all(
            isinstance(item, CampaignStateSnapshot)
            for item in self.reconstructed_campaign_heads
        ):
            raise AssuranceRecoveryIntegrityError(
                "reconstructed_campaign_heads must be a tuple of CampaignStateSnapshot"
            )
        if not isinstance(self.reconstructed_history_heads, tuple) or not all(
            isinstance(item, HistoryHeadSnapshot)
            for item in self.reconstructed_history_heads
        ):
            raise AssuranceRecoveryIntegrityError(
                "reconstructed_history_heads must be a tuple of HistoryHeadSnapshot"
            )
        if not isinstance(self.reconstructed_merkle_heads, tuple) or not all(
            isinstance(item, MerkleRootSnapshot)
            for item in self.reconstructed_merkle_heads
        ):
            raise AssuranceRecoveryIntegrityError(
                "reconstructed_merkle_heads must be a tuple of MerkleRootSnapshot"
            )
        if not isinstance(self.reconstructed_policy_heads, tuple) or not all(
            isinstance(item, AssurancePolicyVersionSnapshot)
            for item in self.reconstructed_policy_heads
        ):
            raise AssuranceRecoveryIntegrityError(
                "reconstructed_policy_heads must be a tuple of "
                "AssurancePolicyVersionSnapshot"
            )
        if not isinstance(self.reconstructed_promotion_heads, tuple) or not all(
            isinstance(item, AssurancePromotionStateSnapshot)
            for item in self.reconstructed_promotion_heads
        ):
            raise AssuranceRecoveryIntegrityError(
                "reconstructed_promotion_heads must be a tuple of "
                "AssurancePromotionStateSnapshot"
            )
        for label, heads in (
            ("campaign", self.reconstructed_campaign_heads),
            ("history", self.reconstructed_history_heads),
            ("merkle", self.reconstructed_merkle_heads),
            ("policy", self.reconstructed_policy_heads),
            ("promotion", self.reconstructed_promotion_heads),
        ):
            namespaces = [item.namespace for item in heads]
            if len(set(namespaces)) != len(namespaces):
                raise AssuranceRecoveryIntegrityError(
                    f"reconstructed_{label}_heads may contain only one "
                    "snapshot per namespace"
                )
        if not isinstance(self.ignored_idempotent_transitions, tuple):
            raise AssuranceRecoveryIntegrityError(
                "ignored_idempotent_transitions must be a tuple"
            )
        for cid in self.ignored_idempotent_transitions:
            try:
                validate_verified_cid(cid, "ignored_idempotent_transition")
            except AssuranceArtifactStoreContractError as exc:
                raise AssuranceRecoveryIntegrityError(str(exc)) from exc
        if not isinstance(self.errors, tuple):
            raise AssuranceRecoveryIntegrityError("errors must be a tuple")
        if len(self.errors) > MAX_RECOVERY_ERRORS:
            raise AssuranceRecoveryIntegrityError(
                f"errors must contain at most {MAX_RECOVERY_ERRORS} records"
            )
        normalized: list[Mapping[str, str]] = []
        for error in self.errors:
            record = _closed_mapping(error, _CLOSED_ERROR_FIELDS, "recovery error")
            code, message = record["code"], record["message"]
            if not isinstance(code, str) or not isinstance(message, str) or not message:
                raise AssuranceRecoveryIntegrityError(
                    "recovery errors require a normalized code and non-empty message"
                )
            try:
                validate_reason_code(code)
            except AssuranceArtifactStoreContractError as exc:
                raise AssuranceRecoveryIntegrityError(str(exc)) from exc
            normalized.append(
                MappingProxyType({"code": code, "message": message})
            )
        object.__setattr__(self, "errors", tuple(normalized))

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified_blocks": self.verified_blocks,
            "reconstructed_campaign_heads": [
                item.to_dict() for item in self.reconstructed_campaign_heads
            ],
            "reconstructed_history_heads": [
                item.to_dict() for item in self.reconstructed_history_heads
            ],
            "reconstructed_merkle_heads": [
                item.to_dict() for item in self.reconstructed_merkle_heads
            ],
            "reconstructed_policy_heads": [
                item.to_dict() for item in self.reconstructed_policy_heads
            ],
            "reconstructed_promotion_heads": [
                item.to_dict() for item in self.reconstructed_promotion_heads
            ],
            "ignored_idempotent_transitions": list(
                self.ignored_idempotent_transitions
            ),
            "errors": [dict(item) for item in self.errors],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AssuranceRecoveryReport":
        data = dict(_closed_mapping(value, _REPORT_FIELDS, "assurance recovery report"))
        for key in (
            "reconstructed_campaign_heads",
            "reconstructed_history_heads",
            "reconstructed_merkle_heads",
            "reconstructed_policy_heads",
            "reconstructed_promotion_heads",
            "ignored_idempotent_transitions",
            "errors",
        ):
            if not isinstance(data[key], list):
                raise AssuranceRecoveryIntegrityError(
                    "recovery report sequences must be lists"
                )
        try:
            data["reconstructed_campaign_heads"] = tuple(
                _campaign_snapshot_from_dict(item)
                for item in data["reconstructed_campaign_heads"]
            )
            data["reconstructed_history_heads"] = tuple(
                _history_snapshot_from_dict(item)
                for item in data["reconstructed_history_heads"]
            )
            data["reconstructed_merkle_heads"] = tuple(
                _merkle_snapshot_from_dict(item)
                for item in data["reconstructed_merkle_heads"]
            )
            data["reconstructed_policy_heads"] = tuple(
                AssurancePolicyVersionSnapshot.from_dict(item)
                for item in data["reconstructed_policy_heads"]
            )
            data["reconstructed_promotion_heads"] = tuple(
                AssurancePromotionStateSnapshot.from_dict(item)
                for item in data["reconstructed_promotion_heads"]
            )
        except (
            CampaignStoreError,
            MerkleStoreError,
            AssurancePolicyError,
            TypeError,
            ValueError,
            KeyError,
        ) as exc:
            raise AssuranceRecoveryIntegrityError(str(exc)) from exc
        data["ignored_idempotent_transitions"] = tuple(
            data["ignored_idempotent_transitions"]
        )
        data["errors"] = tuple(data["errors"])
        data["verified_blocks"] = int(data["verified_blocks"])
        return cls(**data)


# ---------------------------------------------------------------------------
# Writer fencing helpers
# ---------------------------------------------------------------------------


def assert_writer_fence(
    *,
    expected_generation: int,
    expected_head_cid: Optional[str],
    current_generation: int,
    current_head_cid: Optional[str],
) -> None:
    """Reject a stale writer whose expected generation/CID is no longer current.

    CAS paths already fail closed with ``stale_expectation``; this helper makes
    the same generation+CID fence explicit for recovery and concurrent writers
    before they attempt a durable mutation.
    """

    try:
        expected_generation, expected_head_cid = validate_generation_expectation(
            expected_generation, expected_head_cid
        )
    except (AssuranceArtifactStoreContractError, CampaignAdmissionError) as exc:
        raise AssuranceRecoveryAdmissionError(str(exc)) from exc
    if not isinstance(current_generation, int) or isinstance(
        current_generation, bool
    ):
        raise AssuranceRecoveryAdmissionError(
            "current_generation must be an integer"
        )
    if current_generation < 0:
        raise AssuranceRecoveryAdmissionError(
            "current_generation must be non-negative"
        )
    if current_head_cid is not None:
        try:
            current_head_cid = validate_semantic_dag_json_cid(
                current_head_cid, "current_head_cid"
            )
        except AssuranceArtifactStoreContractError as exc:
            raise AssuranceRecoveryAdmissionError(str(exc)) from exc
    if (
        expected_generation != current_generation
        or expected_head_cid != current_head_cid
    ):
        raise AssuranceRecoveryAdmissionError(
            "stale writer expectation rejected by concurrency fence"
        )


def assert_terminal_claim_not_ambiguous(
    *,
    phase: CampaignPhase | str,
    execution_claim_status: ExecutionClaimStatus | str,
    receipt_cid: Optional[str],
) -> None:
    """Fail closed when a terminal-success claim is partial or ambiguous."""

    try:
        phase_token = coerce_campaign_phase(phase)
        claim_token = coerce_execution_claim_status(execution_claim_status)
        assert_terminal_success_admissible(
            phase=phase_token,
            execution_claim_status=claim_token,
            receipt_cid=receipt_cid,
        )
    except (CampaignTransitionError, CampaignAdmissionError, CampaignStoreError) as exc:
        raise AssuranceRecoveryAdmissionError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Protocol and implementation
# ---------------------------------------------------------------------------


class AssuranceRecovery(Protocol):
    """Closed crash-recovery surface (``AssuranceRecovery@1``)."""

    def recover_assurance_campaigns(self) -> AssuranceRecoveryReport: ...


class DurableAssuranceRecovery:
    """Project assurance heads after primitive coordination-store recovery.

    Implements ``AssuranceRecovery@1``.  Rebuild work is always delegated to
    ``DurableCoordinationStore.recover``; this facade only re-verifies and
    projects closed AAE heads under ``adversarial-assurance/…`` namespaces.
    """

    def __init__(self, store: DurableCoordinationStore) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store

    @property
    def store(self) -> DurableCoordinationStore:
        """Injected coordination store (diagnostics / composition only)."""

        return self._store

    def recover_assurance_campaigns(self) -> AssuranceRecoveryReport:
        """Rebuild indexes and return closed assurance recovery evidence.

        Corruption remains fail-closed: no reconstructed head is returned for a
        namespace whose evidence fails re-verification, and partial promotion or
        ambiguous terminal claims are reported as errors rather than invented
        successes.
        """

        return recover_assurance_campaigns(self._store)


def recover_assurance_campaigns(
    store: DurableCoordinationStore,
) -> AssuranceRecoveryReport:
    """Recover assurance campaign, history, Merkle, policy, and promotion heads.

    Steps:

    1. Run the existing coordination-store recovery primitive (rebuild indexes
       from immutable blocks under a writer fence).
    2. Discover workspaces that own assurance namespaces in the recovered root
       index.
    3. Project and re-verify each domain head through the typed repositories.
    4. Reject ambiguous/partial terminal campaign claims and never invent a
       promotion outcome that is not durably present.
    """

    if not isinstance(store, DurableCoordinationStore):
        raise TypeError("store must be a DurableCoordinationStore")

    raw_report: Mapping[str, Any] | None = None
    try:
        raw_report = store.recover(rebuild=True)
        verified_blocks = int(raw_report["verified_blocks"])
    except (ArtifactIntegrityError, ValueError, TypeError, KeyError) as exc:
        verified = 0 if raw_report is None else int(raw_report.get("verified_blocks", 0))
        return AssuranceRecoveryReport(
            verified_blocks=verified,
            reconstructed_campaign_heads=(),
            reconstructed_history_heads=(),
            reconstructed_merkle_heads=(),
            reconstructed_policy_heads=(),
            reconstructed_promotion_heads=(),
            ignored_idempotent_transitions=(),
            errors=({"code": "corrupt", "message": str(exc)},),
        )

    workspaces = _discover_assurance_workspaces(store)
    artifacts = DurableAssuranceArtifactStore(store)
    try:
        campaigns = DurableMutationCampaignRepository(store, artifacts=artifacts)
        gaps = DurableAssuranceGapRepository(store, artifacts=artifacts)
        merkle = DurableAssuranceCampaignMerkleRepository(store, artifacts=artifacts)
        policy = DurableAssurancePolicyRepository(store)

        campaign_heads: list[CampaignStateSnapshot] = []
        history_heads: list[HistoryHeadSnapshot] = []
        merkle_heads: list[MerkleRootSnapshot] = []
        policy_heads: list[AssurancePolicyVersionSnapshot] = []
        promotion_heads: list[AssurancePromotionStateSnapshot] = []
        errors: list[Mapping[str, str]] = []

        for workspace in workspaces:
            _project_campaign_head(
                campaigns, artifacts, workspace, campaign_heads, errors
            )
            _project_history_head(
                campaigns.current_receipts_history,
                workspace,
                history_heads,
                errors,
                role=AssuranceNamespaceRole.RECEIPTS,
            )
            _project_history_head(
                gaps.current_gaps_history,
                workspace,
                history_heads,
                errors,
                role=AssuranceNamespaceRole.GAPS,
            )
            _project_merkle_head(merkle, workspace, merkle_heads, errors)
            _project_policy_head(policy, workspace, policy_heads, errors)
            _project_promotion_head(policy, workspace, promotion_heads, errors)

        # Stable order for deterministic report evidence.
        campaign_heads.sort(key=lambda item: item.namespace)
        history_heads.sort(key=lambda item: item.namespace)
        merkle_heads.sort(key=lambda item: item.namespace)
        policy_heads.sort(key=lambda item: item.namespace)
        promotion_heads.sort(key=lambda item: item.namespace)

        return AssuranceRecoveryReport(
            verified_blocks=verified_blocks,
            reconstructed_campaign_heads=tuple(campaign_heads),
            reconstructed_history_heads=tuple(history_heads),
            reconstructed_merkle_heads=tuple(merkle_heads),
            reconstructed_policy_heads=tuple(policy_heads),
            reconstructed_promotion_heads=tuple(promotion_heads),
            ignored_idempotent_transitions=(),
            errors=tuple(errors[:MAX_RECOVERY_ERRORS]),
        )
    finally:
        artifacts.close()


def _discover_assurance_workspaces(store: DurableCoordinationStore) -> list[str]:
    found: set[str] = set()
    try:
        roots = store.state_roots()
    except Exception:
        return []
    for root in roots:
        namespace = root.get("namespace")
        if not isinstance(namespace, str):
            continue
        if not namespace.startswith(f"{ASSURANCE_NAMESPACE_PREFIX}/"):
            continue
        try:
            workspace, _role = parse_assurance_namespace(namespace)
        except AssuranceArtifactStoreContractError:
            continue
        found.add(workspace)
    return sorted(found)


def _append_error(
    errors: list[Mapping[str, str]], *, code: str, message: str
) -> None:
    if len(errors) >= MAX_RECOVERY_ERRORS:
        return
    try:
        code = validate_reason_code(code)
    except AssuranceArtifactStoreContractError:
        code = "corrupt"
    text = message if isinstance(message, str) and message else "recovery error"
    errors.append({"code": code, "message": text})


def _project_campaign_head(
    campaigns: DurableMutationCampaignRepository,
    artifacts: DurableAssuranceArtifactStore,
    workspace: str,
    heads: list[CampaignStateSnapshot],
    errors: list[Mapping[str, str]],
) -> None:
    try:
        head = campaigns.current_campaign_state(workspace)
    except (CampaignStoreError, ArtifactIntegrityError, ValueError, TypeError) as exc:
        _append_error(errors, code="corrupt", message=str(exc))
        return
    if head.generation == 0:
        return
    try:
        if head.phase is CampaignPhase.COMPLETE:
            assert_terminal_success_admissible(
                phase=head.phase,
                execution_claim_status=head.execution_claim_status
                or ExecutionClaimStatus.NONE,
                receipt_cid=head.receipt_cid,
            )
            if head.receipt_cid is not None:
                # Completed immutable receipt must re-verify after restart.
                artifacts.get_verified_artifact(head.receipt_cid)
        elif head.execution_claim_status in (
            ExecutionClaimStatus.PARTIAL,
            ExecutionClaimStatus.AMBIGUOUS,
        ):
            # Partial/ambiguous claims may exist mid-campaign but never as
            # terminal success; recovery reports them as non-terminal evidence
            # and does not invent a completion.
            if head.phase in (
                CampaignPhase.COMPLETE,
                CampaignPhase.REJECTED,
            ):
                raise CampaignTransitionError(
                    "partial and ambiguous execution claims cannot become "
                    "terminal success"
                )
        if head.state_cid is not None:
            campaigns.get_verified_campaign_state(head.state_cid)
    except (
        CampaignTransitionError,
        CampaignStoreError,
        ArtifactIntegrityError,
        ValueError,
        TypeError,
    ) as exc:
        code = "ambiguous_claim"
        message = str(exc)
        if "partial" in message or "ambiguous" in message:
            code = "ambiguous_claim"
        elif "corrupt" in message.lower() or "mismatch" in message.lower():
            code = "corrupt"
        else:
            code = "integrity_failure"
        _append_error(errors, code=code, message=message)
        return
    heads.append(head)


def _project_history_head(
    loader: Any,
    workspace: str,
    heads: list[HistoryHeadSnapshot],
    errors: list[Mapping[str, str]],
    *,
    role: AssuranceNamespaceRole,
) -> None:
    try:
        head = loader(workspace)
    except (CampaignStoreError, ArtifactIntegrityError, ValueError, TypeError) as exc:
        _append_error(errors, code="corrupt", message=str(exc))
        return
    if not isinstance(head, HistoryHeadSnapshot):
        _append_error(
            errors,
            code="integrity_failure",
            message=f"history head for {role.value} is not a HistoryHeadSnapshot",
        )
        return
    if head.generation == 0:
        return
    if head.role not in _HISTORY_ROLES:
        _append_error(
            errors,
            code="integrity_failure",
            message=f"unexpected history role {head.role.value!r}",
        )
        return
    heads.append(head)


def _project_merkle_head(
    merkle: DurableAssuranceCampaignMerkleRepository,
    workspace: str,
    heads: list[MerkleRootSnapshot],
    errors: list[Mapping[str, str]],
) -> None:
    try:
        head = merkle.current_merkle_root(workspace)
    except (MerkleStoreError, ArtifactIntegrityError, ValueError, TypeError) as exc:
        _append_error(errors, code="corrupt", message=str(exc))
        return
    if head.generation == 0:
        return
    try:
        if head.root_cid is not None:
            sealed = merkle.get_verified_campaign_merkle_root(head.root_cid)
            # Incomplete required sets must not be promoted as complete roots.
            if sealed.get("required_set_completeness") is not True:
                raise MerkleIntegrityError(
                    "partial merkle root cannot be promoted as complete"
                )
    except (MerkleStoreError, ArtifactIntegrityError, ValueError, TypeError) as exc:
        _append_error(errors, code="partial_promotion", message=str(exc))
        return
    heads.append(head)


def _project_policy_head(
    policy: DurableAssurancePolicyRepository,
    workspace: str,
    heads: list[AssurancePolicyVersionSnapshot],
    errors: list[Mapping[str, str]],
) -> None:
    try:
        head = policy.current_policy(workspace)
    except (
        AssurancePolicyError,
        ArtifactIntegrityError,
        ValueError,
        TypeError,
    ) as exc:
        _append_error(errors, code="corrupt", message=str(exc))
        return
    if head.generation == 0:
        return
    heads.append(head)


def _project_promotion_head(
    policy: DurableAssurancePolicyRepository,
    workspace: str,
    heads: list[AssurancePromotionStateSnapshot],
    errors: list[Mapping[str, str]],
) -> None:
    try:
        head = policy.current_promotion(workspace)
    except (
        AssurancePolicyError,
        ArtifactIntegrityError,
        ValueError,
        TypeError,
    ) as exc:
        _append_error(errors, code="corrupt", message=str(exc))
        return
    if head.generation == 0:
        return
    # Promotion heads are independent of policy heads.  Recovery never claims
    # a promotion completed solely because a policy revision advanced.
    heads.append(head)


def validate_recovery_operation_id(operation_id: object) -> str:
    """Validate an operation-id used for idempotent recovery replays."""

    try:
        return validate_operation_id(operation_id)
    except AssuranceArtifactStoreContractError as exc:
        raise AssuranceRecoveryAdmissionError(str(exc)) from exc


__all__ = [
    "ASSURANCE_RECOVERY_INTERFACE",
    "ASSURANCE_RECOVERY_REPORT_INTERFACE",
    "ASSURANCE_RECOVERY_SCHEMA",
    "RECOVERY_MODULE_INTERFACE",
    "REQUIRED_CAS_INTERRUPTION_POINTS",
    "MAX_RECOVERY_ERRORS",
    "AssuranceRecoveryError",
    "AssuranceRecoveryAdmissionError",
    "AssuranceRecoveryIntegrityError",
    "AssuranceRecoveryReport",
    "AssuranceRecovery",
    "DurableAssuranceRecovery",
    "recover_assurance_campaigns",
    "assert_writer_fence",
    "assert_terminal_claim_not_ambiguous",
    "validate_recovery_operation_id",
]
