"""Assurance-policy revision and promotion compare-and-swap (AAE-037).

Thin typed heads over ``DurableCoordinationStore`` root CAS:

* policy and promotion namespaces under ``adversarial-assurance/<workspace>/…``
* expected generation + expected head CID (ABA-safe expected-old revision)
* operation-id idempotency and closed ``updated`` / ``unchanged`` / ``conflict``
  / ``corrupt`` / ``unavailable`` outcomes
* promotion requires exact candidate, evaluation, and authorization identities
  (pairwise distinct; candidates cannot self-authorize)
* stale or concurrent writers fail without overwriting a newer policy head
* rollback is a normal CAS to a prior policy CID; transition history is retained

Does not open a second object store, WAL, daemon, or receipt hierarchy.  Does
not change production policy outside the caller's disposable coordination store.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Mapping, Optional, Protocol

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    DurableCoordinationStore,
)
from ipfs_kit_py.adversarial_assurance_store.contracts import (
    AssuranceArtifactStoreContractError,
    AssuranceNamespaceRole,
    AssuranceStoreStatus,
    assurance_namespace,
    parse_assurance_namespace,
    validate_assurance_workspace,
    validate_operation_id,
    validate_reason_code,
    validate_semantic_dag_json_cid,
)
from ipfs_kit_py.adversarial_assurance_store.campaigns import (
    CampaignAdmissionError,
    validate_generation_expectation,
)

# ---------------------------------------------------------------------------
# Schema / interface constants
# ---------------------------------------------------------------------------

ASSURANCE_POLICY_REPOSITORY_INTERFACE: Final[str] = "AssurancePolicyRepository@1"
POLICY_MODULE_INTERFACE: Final[str] = ASSURANCE_POLICY_REPOSITORY_INTERFACE
PROMOTION_MODULE_INTERFACE: Final[str] = "AssurancePromotionStateRepository@1"
POLICY_CAS_SCHEMA: Final[str] = "ipfs-kit.adversarial-assurance-store.policy-cas@1"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AssurancePolicyError(ValueError):
    """Base error for assurance policy/promotion CAS admission or integrity."""


class AssurancePolicyAdmissionError(AssurancePolicyError):
    """Raised when a CAS request is rejected before durable mutation."""


class AssurancePolicyIntegrityError(AssurancePolicyError):
    """Raised when stored head evidence fails verification."""


# ---------------------------------------------------------------------------
# Snapshots and results
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AssurancePolicyVersionSnapshot:
    """Currently visible assurance-policy head for one workspace."""

    namespace: str
    policy_cid: str | None
    generation: int
    transition_cid: str | None

    def __post_init__(self) -> None:
        try:
            namespace = str(self.namespace)
            workspace, role = parse_assurance_namespace(namespace)
            if role is not AssuranceNamespaceRole.POLICY:
                raise AssurancePolicyIntegrityError(
                    "AssurancePolicyVersionSnapshot namespace role must be policy"
                )
            object.__setattr__(
                self, "namespace", assurance_namespace(workspace, role)
            )
            if self.policy_cid is not None:
                validate_semantic_dag_json_cid(self.policy_cid, "policy_cid")
            if self.transition_cid is not None:
                validate_semantic_dag_json_cid(
                    self.transition_cid, "transition_cid"
                )
        except AssuranceArtifactStoreContractError as exc:
            raise AssurancePolicyIntegrityError(str(exc)) from exc
        if not isinstance(self.generation, int) or isinstance(
            self.generation, bool
        ):
            raise AssurancePolicyIntegrityError("generation must be an integer")
        if self.generation < 0:
            raise AssurancePolicyIntegrityError("generation must be non-negative")
        if self.generation == 0 and (
            self.policy_cid is not None or self.transition_cid is not None
        ):
            raise AssurancePolicyIntegrityError(
                "generation-zero policy heads must not have a CID or transition"
            )
        if self.generation > 0 and (
            self.policy_cid is None or self.transition_cid is None
        ):
            raise AssurancePolicyIntegrityError(
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
    def from_dict(cls, value: Mapping[str, Any]) -> "AssurancePolicyVersionSnapshot":
        if not isinstance(value, Mapping):
            raise AssurancePolicyIntegrityError(
                "policy snapshot must be a mapping"
            )
        return cls(
            namespace=str(value["namespace"]),
            policy_cid=value.get("policy_cid"),
            generation=int(value["generation"]),
            transition_cid=value.get("transition_cid"),
        )


@dataclass(frozen=True, slots=True)
class AssurancePromotionStateSnapshot:
    """Currently visible promotion head for one workspace."""

    namespace: str
    promotion_cid: str | None
    generation: int
    transition_cid: str | None

    def __post_init__(self) -> None:
        try:
            namespace = str(self.namespace)
            workspace, role = parse_assurance_namespace(namespace)
            if role is not AssuranceNamespaceRole.PROMOTION:
                raise AssurancePolicyIntegrityError(
                    "AssurancePromotionStateSnapshot namespace role must be promotion"
                )
            object.__setattr__(
                self, "namespace", assurance_namespace(workspace, role)
            )
            if self.promotion_cid is not None:
                validate_semantic_dag_json_cid(
                    self.promotion_cid, "promotion_cid"
                )
            if self.transition_cid is not None:
                validate_semantic_dag_json_cid(
                    self.transition_cid, "transition_cid"
                )
        except AssuranceArtifactStoreContractError as exc:
            raise AssurancePolicyIntegrityError(str(exc)) from exc
        if not isinstance(self.generation, int) or isinstance(
            self.generation, bool
        ):
            raise AssurancePolicyIntegrityError("generation must be an integer")
        if self.generation < 0:
            raise AssurancePolicyIntegrityError("generation must be non-negative")
        if self.generation == 0 and (
            self.promotion_cid is not None or self.transition_cid is not None
        ):
            raise AssurancePolicyIntegrityError(
                "generation-zero promotion heads must not have a CID or transition"
            )
        if self.generation > 0 and (
            self.promotion_cid is None or self.transition_cid is None
        ):
            raise AssurancePolicyIntegrityError(
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
    def from_dict(
        cls, value: Mapping[str, Any]
    ) -> "AssurancePromotionStateSnapshot":
        if not isinstance(value, Mapping):
            raise AssurancePolicyIntegrityError(
                "promotion snapshot must be a mapping"
            )
        return cls(
            namespace=str(value["namespace"]),
            promotion_cid=value.get("promotion_cid"),
            generation=int(value["generation"]),
            transition_cid=value.get("transition_cid"),
        )


@dataclass(frozen=True, slots=True)
class AssurancePolicyCASResult:
    """Closed outcome of an attempted policy-head compare-and-swap."""

    status: AssuranceStoreStatus
    before: AssurancePolicyVersionSnapshot
    after: AssurancePolicyVersionSnapshot
    transition_cid: str | None
    reason_code: str
    local_durable: bool
    replicated: bool
    operation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, AssuranceStoreStatus):
            raise AssurancePolicyIntegrityError(
                "status must be AssuranceStoreStatus"
            )
        if not isinstance(self.before, AssurancePolicyVersionSnapshot) or not isinstance(
            self.after, AssurancePolicyVersionSnapshot
        ):
            raise AssurancePolicyIntegrityError(
                "before and after must be AssurancePolicyVersionSnapshot values"
            )
        if self.before.namespace != self.after.namespace:
            raise AssurancePolicyIntegrityError(
                "before and after namespaces must agree"
            )
        try:
            if self.transition_cid is not None:
                validate_semantic_dag_json_cid(
                    self.transition_cid, "transition_cid"
                )
            validate_reason_code(self.reason_code)
            validate_operation_id(self.operation_id)
        except AssuranceArtifactStoreContractError as exc:
            raise AssurancePolicyIntegrityError(str(exc)) from exc
        if not isinstance(self.local_durable, bool):
            raise AssurancePolicyIntegrityError("local_durable must be a boolean")
        if not isinstance(self.replicated, bool):
            raise AssurancePolicyIntegrityError("replicated must be a boolean")
        if self.replicated and not self.local_durable:
            raise AssurancePolicyIntegrityError(
                "replicated results must also be locally durable"
            )
        if self.status is AssuranceStoreStatus.UPDATED:
            if (
                not self.local_durable
                or self.after.generation != self.before.generation + 1
            ):
                raise AssurancePolicyIntegrityError(
                    "updated results require a durable one-generation successor"
                )
            if (
                self.after.policy_cid == self.before.policy_cid
                or self.transition_cid != self.after.transition_cid
            ):
                raise AssurancePolicyIntegrityError(
                    "updated results require a distinct matching transition"
                )
        else:
            if self.after != self.before or self.transition_cid is not None:
                raise AssurancePolicyIntegrityError(
                    "non-updated results must not change the policy head"
                )
            if self.replicated:
                raise AssurancePolicyIntegrityError(
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


@dataclass(frozen=True, slots=True)
class AssurancePromotionCASResult:
    """Closed outcome of an attempted promotion CAS with identity bindings.

    Promotion always binds exact candidate, evaluation, and authorization
    identities plus the expected-old policy revision that the writer observed.
    """

    status: AssuranceStoreStatus
    before: AssurancePromotionStateSnapshot | AssurancePolicyVersionSnapshot
    after: AssurancePromotionStateSnapshot | AssurancePolicyVersionSnapshot
    transition_cid: str | None
    reason_code: str
    local_durable: bool
    replicated: bool
    operation_id: str
    candidate_cid: str
    evaluation_cid: str
    authorization_cid: str
    expected_old_policy_generation: int
    expected_old_policy_cid: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, AssuranceStoreStatus):
            raise AssurancePolicyIntegrityError(
                "status must be AssuranceStoreStatus"
            )
        if type(self.before) is not type(self.after):
            raise AssurancePolicyIntegrityError(
                "before and after snapshot types must agree"
            )
        if not isinstance(
            self.before,
            (AssurancePromotionStateSnapshot, AssurancePolicyVersionSnapshot),
        ) or not isinstance(
            self.after,
            (AssurancePromotionStateSnapshot, AssurancePolicyVersionSnapshot),
        ):
            raise AssurancePolicyIntegrityError(
                "before and after must be policy or promotion snapshots"
            )
        if self.before.namespace != self.after.namespace:
            raise AssurancePolicyIntegrityError(
                "before and after namespaces must agree"
            )
        try:
            if self.transition_cid is not None:
                validate_semantic_dag_json_cid(
                    self.transition_cid, "transition_cid"
                )
            validate_reason_code(self.reason_code)
            validate_operation_id(self.operation_id)
            validate_semantic_dag_json_cid(self.candidate_cid, "candidate_cid")
            validate_semantic_dag_json_cid(self.evaluation_cid, "evaluation_cid")
            validate_semantic_dag_json_cid(
                self.authorization_cid, "authorization_cid"
            )
            if self.expected_old_policy_cid is not None:
                validate_semantic_dag_json_cid(
                    self.expected_old_policy_cid, "expected_old_policy_cid"
                )
        except AssuranceArtifactStoreContractError as exc:
            raise AssurancePolicyIntegrityError(str(exc)) from exc
        if not isinstance(self.local_durable, bool):
            raise AssurancePolicyIntegrityError("local_durable must be a boolean")
        if not isinstance(self.replicated, bool):
            raise AssurancePolicyIntegrityError("replicated must be a boolean")
        if not isinstance(self.expected_old_policy_generation, int) or isinstance(
            self.expected_old_policy_generation, bool
        ):
            raise AssurancePolicyIntegrityError(
                "expected_old_policy_generation must be an integer"
            )
        if self.expected_old_policy_generation < 0:
            raise AssurancePolicyIntegrityError(
                "expected_old_policy_generation must be non-negative"
            )
        if self.expected_old_policy_generation == 0:
            if self.expected_old_policy_cid is not None:
                raise AssurancePolicyIntegrityError(
                    "generation-zero expected-old policy must not have a CID"
                )
        elif self.expected_old_policy_cid is None:
            raise AssurancePolicyIntegrityError(
                "non-zero expected-old policy requires a policy CID"
            )
        try:
            _assert_promotion_identities_distinct(
                candidate_cid=self.candidate_cid,
                evaluation_cid=self.evaluation_cid,
                authorization_cid=self.authorization_cid,
            )
        except AssurancePolicyAdmissionError as exc:
            raise AssurancePolicyIntegrityError(str(exc)) from exc
        if self.replicated and not self.local_durable:
            raise AssurancePolicyIntegrityError(
                "replicated results must also be locally durable"
            )
        if self.status is AssuranceStoreStatus.UPDATED:
            if (
                not self.local_durable
                or self.after.generation != self.before.generation + 1
            ):
                raise AssurancePolicyIntegrityError(
                    "updated results require a durable one-generation successor"
                )
            if self.transition_cid != self.after.transition_cid:
                raise AssurancePolicyIntegrityError(
                    "updated results require a distinct matching transition"
                )
            # Head CID field name differs by snapshot kind.
            before_cid = _snapshot_head_cid(self.before)
            after_cid = _snapshot_head_cid(self.after)
            if after_cid == before_cid:
                raise AssurancePolicyIntegrityError(
                    "updated results require a distinct head CID"
                )
        else:
            if self.after != self.before or self.transition_cid is not None:
                raise AssurancePolicyIntegrityError(
                    "non-updated results must not change the head"
                )
            if self.replicated:
                raise AssurancePolicyIntegrityError(
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
            "evaluation_cid": self.evaluation_cid,
            "authorization_cid": self.authorization_cid,
            "expected_old_policy_generation": self.expected_old_policy_generation,
            "expected_old_policy_cid": self.expected_old_policy_cid,
        }


# ---------------------------------------------------------------------------
# Identity helpers
# ---------------------------------------------------------------------------


def _snapshot_head_cid(
    snapshot: AssurancePromotionStateSnapshot | AssurancePolicyVersionSnapshot,
) -> str | None:
    if isinstance(snapshot, AssurancePolicyVersionSnapshot):
        return snapshot.policy_cid
    return snapshot.promotion_cid


def _assert_promotion_identities_distinct(
    *,
    candidate_cid: str,
    evaluation_cid: str,
    authorization_cid: str,
    new_head_cid: str | None = None,
) -> None:
    """Fail closed when promotion identities collide (no self-promotion)."""

    if candidate_cid == authorization_cid:
        raise AssurancePolicyAdmissionError(
            "candidate cannot authorize its own promotion"
        )
    if candidate_cid == evaluation_cid:
        raise AssurancePolicyAdmissionError(
            "candidate_cid must differ from evaluation_cid"
        )
    if evaluation_cid == authorization_cid:
        raise AssurancePolicyAdmissionError(
            "evaluation_cid must differ from authorization_cid"
        )
    if new_head_cid is not None:
        for name, cid in (
            ("candidate_cid", candidate_cid),
            ("evaluation_cid", evaluation_cid),
            ("authorization_cid", authorization_cid),
        ):
            if cid == new_head_cid:
                raise AssurancePolicyAdmissionError(
                    f"{name} must differ from the promoted head CID"
                )


def _status_from_wire(value: object) -> AssuranceStoreStatus:
    if not isinstance(value, str):
        raise AssurancePolicyIntegrityError("CAS status must be a string")
    try:
        return AssuranceStoreStatus(value)
    except ValueError as exc:
        raise AssurancePolicyIntegrityError(
            f"unknown CAS status: {value!r}"
        ) from exc


def _policy_snapshot(root: Mapping[str, Any]) -> AssurancePolicyVersionSnapshot:
    try:
        return AssurancePolicyVersionSnapshot(
            namespace=str(root["namespace"]),
            policy_cid=root.get("root_cid"),
            generation=int(root["revision"]),
            transition_cid=root.get("transition_cid"),
        )
    except (KeyError, TypeError, ValueError, AssurancePolicyIntegrityError) as exc:
        raise AssurancePolicyIntegrityError(
            f"invalid policy head projection: {exc}"
        ) from exc


def _promotion_snapshot(
    root: Mapping[str, Any],
) -> AssurancePromotionStateSnapshot:
    try:
        return AssurancePromotionStateSnapshot(
            namespace=str(root["namespace"]),
            promotion_cid=root.get("root_cid"),
            generation=int(root["revision"]),
            transition_cid=root.get("transition_cid"),
        )
    except (KeyError, TypeError, ValueError, AssurancePolicyIntegrityError) as exc:
        raise AssurancePolicyIntegrityError(
            f"invalid promotion head projection: {exc}"
        ) from exc


def _require_dag_json_optional(
    value: Optional[str], name: str
) -> Optional[str]:
    if value is None:
        return None
    try:
        return validate_semantic_dag_json_cid(value, name)
    except AssuranceArtifactStoreContractError as exc:
        raise AssurancePolicyAdmissionError(str(exc)) from exc


def _validate_promotion_identity_args(
    *,
    candidate_cid: object,
    evaluation_cid: object,
    authorization_cid: object,
    new_head_cid: str | None = None,
) -> tuple[str, str, str]:
    try:
        candidate = validate_semantic_dag_json_cid(candidate_cid, "candidate_cid")
        evaluation = validate_semantic_dag_json_cid(
            evaluation_cid, "evaluation_cid"
        )
        authorization = validate_semantic_dag_json_cid(
            authorization_cid, "authorization_cid"
        )
    except AssuranceArtifactStoreContractError as exc:
        raise AssurancePolicyAdmissionError(str(exc)) from exc
    _assert_promotion_identities_distinct(
        candidate_cid=candidate,
        evaluation_cid=evaluation,
        authorization_cid=authorization,
        new_head_cid=new_head_cid,
    )
    return candidate, evaluation, authorization


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class AssurancePolicyRepository(Protocol):
    """Closed assurance-policy revision and promotion CAS surface.

    Interface: ``AssurancePolicyRepository@1``.
    """

    def current_policy(self, workspace: str) -> AssurancePolicyVersionSnapshot: ...

    def compare_and_swap_policy(
        self,
        workspace: str,
        *,
        expected_generation: int,
        expected_policy_cid: Optional[str],
        new_policy_cid: str,
        operation_id: str,
    ) -> AssurancePolicyCASResult: ...

    def promote_policy(
        self,
        workspace: str,
        *,
        expected_generation: int,
        expected_policy_cid: Optional[str],
        new_policy_cid: str,
        operation_id: str,
        candidate_cid: str,
        evaluation_cid: str,
        authorization_cid: str,
    ) -> AssurancePromotionCASResult: ...

    def current_promotion(
        self, workspace: str
    ) -> AssurancePromotionStateSnapshot: ...

    def compare_and_swap_promotion(
        self,
        workspace: str,
        *,
        expected_generation: int,
        expected_promotion_cid: Optional[str],
        new_promotion_cid: str,
        operation_id: str,
        candidate_cid: str,
        evaluation_cid: str,
        authorization_cid: str,
        expected_old_policy_generation: int,
        expected_old_policy_cid: Optional[str],
    ) -> AssurancePromotionCASResult: ...


# ---------------------------------------------------------------------------
# Repository implementation
# ---------------------------------------------------------------------------


class DurableAssurancePolicyRepository:
    """Versioned assurance-policy and promotion CAS over DurableCoordinationStore.

    Implements ``AssurancePolicyRepository@1``.  Policy heads live in
    ``adversarial-assurance/<workspace>/policy``; promotion heads live in
    ``adversarial-assurance/<workspace>/promotion``.  Successful CAS stores an
    immutable root-transition block; prior transitions remain queryable after
    rollback so history is never rewritten.
    """

    def __init__(self, store: DurableCoordinationStore) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store

    @property
    def store(self) -> DurableCoordinationStore:
        """Injected coordination store (diagnostics / composition only)."""

        return self._store

    def _policy_namespace(self, workspace: str) -> str:
        try:
            workspace = validate_assurance_workspace(workspace)
            return assurance_namespace(workspace, AssuranceNamespaceRole.POLICY)
        except AssuranceArtifactStoreContractError as exc:
            raise AssurancePolicyAdmissionError(str(exc)) from exc

    def _promotion_namespace(self, workspace: str) -> str:
        try:
            workspace = validate_assurance_workspace(workspace)
            return assurance_namespace(
                workspace, AssuranceNamespaceRole.PROMOTION
            )
        except AssuranceArtifactStoreContractError as exc:
            raise AssurancePolicyAdmissionError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Policy revision CAS
    # ------------------------------------------------------------------

    def current_policy(self, workspace: str) -> AssurancePolicyVersionSnapshot:
        """Return the currently visible policy head (generation zero if empty)."""

        namespace = self._policy_namespace(workspace)
        try:
            root = self._store.current_state_root(namespace)
        except ArtifactIntegrityError as exc:
            raise AssurancePolicyIntegrityError(str(exc)) from exc
        snapshot = _policy_snapshot(root)
        if snapshot.policy_cid is not None:
            _require_dag_json_optional(snapshot.policy_cid, "policy_cid")
        if snapshot.transition_cid is not None:
            _require_dag_json_optional(snapshot.transition_cid, "transition_cid")
        return snapshot

    def compare_and_swap_policy(
        self,
        workspace: str,
        *,
        expected_generation: int,
        expected_policy_cid: Optional[str],
        new_policy_cid: str,
        operation_id: str,
    ) -> AssurancePolicyCASResult:
        """Atomically publish a successor policy head or report a typed conflict.

        Preconditions (fail-closed):

        * generation-zero expects a null policy CID; non-zero expects a CID
        * ``new_policy_cid`` is a distinct canonical dag-json CID already stored
        * ``operation_id`` is a durable idempotency key

        Stale generation/CID pairs and concurrent writers yield at most one
        ``updated`` success; losers observe ``conflict`` without overwriting.
        """

        namespace = self._policy_namespace(workspace)
        try:
            expected_generation, expected_policy_cid = (
                validate_generation_expectation(
                    expected_generation, expected_policy_cid
                )
            )
            operation_id = validate_operation_id(operation_id)
            new_policy_cid = validate_semantic_dag_json_cid(
                new_policy_cid, "new_policy_cid"
            )
            if expected_policy_cid is not None:
                expected_policy_cid = validate_semantic_dag_json_cid(
                    expected_policy_cid, "expected_policy_cid"
                )
        except (
            AssuranceArtifactStoreContractError,
            CampaignAdmissionError,
        ) as exc:
            raise AssurancePolicyAdmissionError(str(exc)) from exc

        if expected_policy_cid == new_policy_cid:
            raise AssurancePolicyAdmissionError(
                "new_policy_cid must differ from expected_policy_cid"
            )

        try:
            raw = self._store.compare_and_swap_state_root(
                namespace,
                expected_revision=expected_generation,
                expected_root_cid=expected_policy_cid,
                new_root_cid=new_policy_cid,
                operation_id=operation_id,
            )
        except ArtifactNotFound:
            try:
                before = self.current_policy(workspace)
            except AssurancePolicyError:
                before = AssurancePolicyVersionSnapshot(namespace, None, 0, None)
            return AssurancePolicyCASResult(
                AssuranceStoreStatus.UNAVAILABLE,
                before,
                before,
                None,
                "successor_unavailable",
                False,
                False,
                operation_id,
            )
        except ArtifactIntegrityError:
            try:
                before = self.current_policy(workspace)
            except AssurancePolicyIntegrityError:
                before = AssurancePolicyVersionSnapshot(namespace, None, 0, None)
                return AssurancePolicyCASResult(
                    AssuranceStoreStatus.CORRUPT,
                    before,
                    before,
                    None,
                    "integrity_failure",
                    False,
                    False,
                    operation_id,
                )
            return AssurancePolicyCASResult(
                AssuranceStoreStatus.CORRUPT,
                before,
                before,
                None,
                "integrity_failure",
                False,
                False,
                operation_id,
            )
        except ValueError as exc:
            raise AssurancePolicyAdmissionError(str(exc)) from exc

        return self._policy_result_from_wire(raw, operation_id=operation_id)

    def promote_policy(
        self,
        workspace: str,
        *,
        expected_generation: int,
        expected_policy_cid: Optional[str],
        new_policy_cid: str,
        operation_id: str,
        candidate_cid: str,
        evaluation_cid: str,
        authorization_cid: str,
    ) -> AssurancePromotionCASResult:
        """CAS the policy head under promotion identity + expected-old constraints.

        Authority rules (fail-closed):

        * exact ``candidate_cid``, ``evaluation_cid``, and ``authorization_cid``
          must be pairwise-distinct dag-json CIDs (no self-authorization)
        * expected generation + expected policy CID must match the live head
        * concurrent / stale writers yield at most one ``updated`` success and
          never overwrite a newer policy revision
        """

        new_policy = _require_dag_json_optional(new_policy_cid, "new_policy_cid")
        assert new_policy is not None
        candidate, evaluation, authorization = _validate_promotion_identity_args(
            candidate_cid=candidate_cid,
            evaluation_cid=evaluation_cid,
            authorization_cid=authorization_cid,
            new_head_cid=new_policy,
        )

        # Capture expected-old revision as admitted before the CAS attempt.
        try:
            expected_generation, expected_policy_cid = (
                validate_generation_expectation(
                    expected_generation, expected_policy_cid
                )
            )
        except CampaignAdmissionError as exc:
            raise AssurancePolicyAdmissionError(str(exc)) from exc

        cas = self.compare_and_swap_policy(
            workspace,
            expected_generation=expected_generation,
            expected_policy_cid=expected_policy_cid,
            new_policy_cid=new_policy,
            operation_id=operation_id,
        )
        return AssurancePromotionCASResult(
            status=cas.status,
            before=cas.before,
            after=cas.after,
            transition_cid=cas.transition_cid,
            reason_code=cas.reason_code,
            local_durable=cas.local_durable,
            replicated=cas.replicated,
            operation_id=cas.operation_id,
            candidate_cid=candidate,
            evaluation_cid=evaluation,
            authorization_cid=authorization,
            expected_old_policy_generation=expected_generation,
            expected_old_policy_cid=expected_policy_cid,
        )

    def rollback_policy(
        self,
        workspace: str,
        *,
        expected_generation: int,
        expected_policy_cid: Optional[str],
        target_policy_cid: str,
        operation_id: str,
    ) -> AssurancePolicyCASResult:
        """CAS the policy head back to a prior policy CID without erasing history.

        Rollback is a forward transition: generation advances, a new transition
        block is indexed, and every earlier transition remains listable.  Only
        previously published policy CIDs are valid rollback targets.
        """

        target_policy_cid = _require_dag_json_optional(
            target_policy_cid, "target_policy_cid"
        )
        assert target_policy_cid is not None

        history = self.policy_transitions(workspace)
        published = {row["new_root_cid"] for row in history}
        if target_policy_cid not in published:
            raise AssurancePolicyAdmissionError(
                "rollback target is not a previously published policy CID"
            )

        return self.compare_and_swap_policy(
            workspace,
            expected_generation=expected_generation,
            expected_policy_cid=expected_policy_cid,
            new_policy_cid=target_policy_cid,
            operation_id=operation_id,
        )

    def policy_transitions(self, workspace: str) -> list[dict[str, Any]]:
        """Return immutable policy root transitions in generation order."""

        namespace = self._policy_namespace(workspace)
        rows = self._store.root_transitions(namespace)
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Promotion-state CAS (receipt head tracking)
    # ------------------------------------------------------------------

    def current_promotion(
        self, workspace: str
    ) -> AssurancePromotionStateSnapshot:
        """Return the currently visible promotion head (generation zero if empty)."""

        namespace = self._promotion_namespace(workspace)
        try:
            root = self._store.current_state_root(namespace)
        except ArtifactIntegrityError as exc:
            raise AssurancePolicyIntegrityError(str(exc)) from exc
        snapshot = _promotion_snapshot(root)
        if snapshot.promotion_cid is not None:
            _require_dag_json_optional(snapshot.promotion_cid, "promotion_cid")
        if snapshot.transition_cid is not None:
            _require_dag_json_optional(snapshot.transition_cid, "transition_cid")
        return snapshot

    def compare_and_swap_promotion(
        self,
        workspace: str,
        *,
        expected_generation: int,
        expected_promotion_cid: Optional[str],
        new_promotion_cid: str,
        operation_id: str,
        candidate_cid: str,
        evaluation_cid: str,
        authorization_cid: str,
        expected_old_policy_generation: int,
        expected_old_policy_cid: Optional[str],
    ) -> AssurancePromotionCASResult:
        """Atomically publish a successor promotion head with identity bindings.

        Authority rules (fail-closed):

        * exact ``candidate_cid``, ``evaluation_cid``, ``authorization_cid``
        * expected-old policy revision (generation + CID) must match the live
          policy head at admission (prevents promoting against a moved policy)
        * expected generation + expected promotion CID must match the live
          promotion head; stale/concurrent writers fail without overwrite
        """

        namespace = self._promotion_namespace(workspace)
        try:
            expected_generation, expected_promotion_cid = (
                validate_generation_expectation(
                    expected_generation, expected_promotion_cid
                )
            )
            expected_old_policy_generation, expected_old_policy_cid = (
                validate_generation_expectation(
                    expected_old_policy_generation, expected_old_policy_cid
                )
            )
            operation_id = validate_operation_id(operation_id)
            new_promotion_cid = validate_semantic_dag_json_cid(
                new_promotion_cid, "new_promotion_cid"
            )
            if expected_promotion_cid is not None:
                expected_promotion_cid = validate_semantic_dag_json_cid(
                    expected_promotion_cid, "expected_promotion_cid"
                )
            if expected_old_policy_cid is not None:
                expected_old_policy_cid = validate_semantic_dag_json_cid(
                    expected_old_policy_cid, "expected_old_policy_cid"
                )
        except (
            AssuranceArtifactStoreContractError,
            CampaignAdmissionError,
        ) as exc:
            raise AssurancePolicyAdmissionError(str(exc)) from exc

        candidate, evaluation, authorization = _validate_promotion_identity_args(
            candidate_cid=candidate_cid,
            evaluation_cid=evaluation_cid,
            authorization_cid=authorization_cid,
            new_head_cid=new_promotion_cid,
        )

        if expected_promotion_cid == new_promotion_cid:
            raise AssurancePolicyAdmissionError(
                "new_promotion_cid must differ from expected_promotion_cid"
            )

        # Expected-old policy revision must still be the live policy head.
        live_policy = self.current_policy(workspace)
        if (
            live_policy.generation != expected_old_policy_generation
            or live_policy.policy_cid != expected_old_policy_cid
        ):
            # Fail closed without mutating promotion head: report conflict
            # against the current promotion snapshot so callers observe a
            # typed non-update rather than a partial write.
            try:
                before = self.current_promotion(workspace)
            except AssurancePolicyError:
                before = AssurancePromotionStateSnapshot(namespace, None, 0, None)
            return AssurancePromotionCASResult(
                status=AssuranceStoreStatus.CONFLICT,
                before=before,
                after=before,
                transition_cid=None,
                reason_code="stale_policy_revision",
                local_durable=False,
                replicated=False,
                operation_id=operation_id,
                candidate_cid=candidate,
                evaluation_cid=evaluation,
                authorization_cid=authorization,
                expected_old_policy_generation=expected_old_policy_generation,
                expected_old_policy_cid=expected_old_policy_cid,
            )

        try:
            raw = self._store.compare_and_swap_state_root(
                namespace,
                expected_revision=expected_generation,
                expected_root_cid=expected_promotion_cid,
                new_root_cid=new_promotion_cid,
                operation_id=operation_id,
            )
        except ArtifactNotFound:
            try:
                before = self.current_promotion(workspace)
            except AssurancePolicyError:
                before = AssurancePromotionStateSnapshot(namespace, None, 0, None)
            return AssurancePromotionCASResult(
                AssuranceStoreStatus.UNAVAILABLE,
                before,
                before,
                None,
                "successor_unavailable",
                False,
                False,
                operation_id,
                candidate,
                evaluation,
                authorization,
                expected_old_policy_generation,
                expected_old_policy_cid,
            )
        except ArtifactIntegrityError:
            try:
                before = self.current_promotion(workspace)
            except AssurancePolicyIntegrityError:
                before = AssurancePromotionStateSnapshot(namespace, None, 0, None)
                return AssurancePromotionCASResult(
                    AssuranceStoreStatus.CORRUPT,
                    before,
                    before,
                    None,
                    "integrity_failure",
                    False,
                    False,
                    operation_id,
                    candidate,
                    evaluation,
                    authorization,
                    expected_old_policy_generation,
                    expected_old_policy_cid,
                )
            return AssurancePromotionCASResult(
                AssuranceStoreStatus.CORRUPT,
                before,
                before,
                None,
                "integrity_failure",
                False,
                False,
                operation_id,
                candidate,
                evaluation,
                authorization,
                expected_old_policy_generation,
                expected_old_policy_cid,
            )
        except ValueError as exc:
            raise AssurancePolicyAdmissionError(str(exc)) from exc

        return self._promotion_result_from_wire(
            raw,
            operation_id=operation_id,
            candidate_cid=candidate,
            evaluation_cid=evaluation,
            authorization_cid=authorization,
            expected_old_policy_generation=expected_old_policy_generation,
            expected_old_policy_cid=expected_old_policy_cid,
        )

    def promotion_transitions(self, workspace: str) -> list[dict[str, Any]]:
        """Return immutable promotion root transitions in generation order."""

        namespace = self._promotion_namespace(workspace)
        rows = self._store.root_transitions(namespace)
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Wire projection
    # ------------------------------------------------------------------

    @staticmethod
    def _policy_result_from_wire(
        raw: Mapping[str, Any], *, operation_id: str
    ) -> AssurancePolicyCASResult:
        status = _status_from_wire(raw.get("status"))
        before = _policy_snapshot(raw["before"])
        after = _policy_snapshot(raw["after"])
        transition_cid = raw.get("transition_cid")
        if transition_cid is not None:
            try:
                transition_cid = validate_semantic_dag_json_cid(
                    transition_cid, "transition_cid"
                )
            except AssuranceArtifactStoreContractError as exc:
                raise AssurancePolicyIntegrityError(str(exc)) from exc
        reason_code = raw.get("reason_code")
        if not isinstance(reason_code, str):
            raise AssurancePolicyIntegrityError("CAS reason_code must be a string")
        local_durable = bool(raw.get("local_durable"))
        replicated = bool(raw.get("replicated"))
        wire_op = raw.get("operation_id", operation_id)
        if not isinstance(wire_op, str):
            wire_op = operation_id
        try:
            return AssurancePolicyCASResult(
                status,
                before,
                after,
                transition_cid,
                reason_code,
                local_durable,
                replicated,
                wire_op,
            )
        except AssurancePolicyIntegrityError:
            raise
        except Exception as exc:
            raise AssurancePolicyIntegrityError(str(exc)) from exc

    @staticmethod
    def _promotion_result_from_wire(
        raw: Mapping[str, Any],
        *,
        operation_id: str,
        candidate_cid: str,
        evaluation_cid: str,
        authorization_cid: str,
        expected_old_policy_generation: int,
        expected_old_policy_cid: Optional[str],
    ) -> AssurancePromotionCASResult:
        status = _status_from_wire(raw.get("status"))
        before = _promotion_snapshot(raw["before"])
        after = _promotion_snapshot(raw["after"])
        transition_cid = raw.get("transition_cid")
        if transition_cid is not None:
            try:
                transition_cid = validate_semantic_dag_json_cid(
                    transition_cid, "transition_cid"
                )
            except AssuranceArtifactStoreContractError as exc:
                raise AssurancePolicyIntegrityError(str(exc)) from exc
        reason_code = raw.get("reason_code")
        if not isinstance(reason_code, str):
            raise AssurancePolicyIntegrityError("CAS reason_code must be a string")
        local_durable = bool(raw.get("local_durable"))
        replicated = bool(raw.get("replicated"))
        wire_op = raw.get("operation_id", operation_id)
        if not isinstance(wire_op, str):
            wire_op = operation_id
        try:
            return AssurancePromotionCASResult(
                status,
                before,
                after,
                transition_cid,
                reason_code,
                local_durable,
                replicated,
                wire_op,
                candidate_cid,
                evaluation_cid,
                authorization_cid,
                expected_old_policy_generation,
                expected_old_policy_cid,
            )
        except AssurancePolicyIntegrityError:
            raise
        except Exception as exc:
            raise AssurancePolicyIntegrityError(str(exc)) from exc


__all__ = [
    "ASSURANCE_POLICY_REPOSITORY_INTERFACE",
    "POLICY_MODULE_INTERFACE",
    "PROMOTION_MODULE_INTERFACE",
    "POLICY_CAS_SCHEMA",
    "AssurancePolicyError",
    "AssurancePolicyAdmissionError",
    "AssurancePolicyIntegrityError",
    "AssurancePolicyVersionSnapshot",
    "AssurancePromotionStateSnapshot",
    "AssurancePolicyCASResult",
    "AssurancePromotionCASResult",
    "AssurancePolicyRepository",
    "DurableAssurancePolicyRepository",
]
