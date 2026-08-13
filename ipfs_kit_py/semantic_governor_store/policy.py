"""Versioned compression-policy and promotion CAS repositories (SCG-021).

Thin typed heads over ``DurableCoordinationStore`` root CAS:

* policy and promotion namespaces under ``semantic-governor/<workspace>/…``
* expected generation + expected head CID (ABA-safe)
* operation-id idempotency and closed ``updated`` / ``unchanged`` / ``conflict``
  / ``corrupt`` / ``unavailable`` outcomes
* promotion requires a distinct authorization CID (candidates cannot self-promote)
* rollback is a normal CAS to a prior policy CID; transition history is retained

Does not open a second object store, WAL, daemon, or receipt hierarchy.
"""

from __future__ import annotations

from typing import Any, Final, Mapping, Optional

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    DurableCoordinationStore,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    GovernorNamespaceRole,
    GovernorStoreStatus,
    PolicyCASResult,
    PolicyVersionSnapshot,
    PromotionCASResult,
    PromotionStateSnapshot,
    SemanticGovernorStoreContractError,
    governor_namespace,
    validate_generation_expectation,
    validate_governor_workspace,
    validate_operation_id,
    validate_semantic_dag_json_cid,
)

# ---------------------------------------------------------------------------
# Schema / interface constants
# ---------------------------------------------------------------------------

POLICY_MODULE_INTERFACE: Final[str] = "DurableCompressionPolicyRepository@1"
PROMOTION_MODULE_INTERFACE: Final[str] = "DurablePromotionStateRepository@1"
POLICY_CAS_SCHEMA: Final[str] = "ipfs-kit.semantic-governor-store.policy-cas@1"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GovernorPolicyError(ValueError):
    """Base error for policy/promotion CAS admission or integrity failures."""


class GovernorPolicyAdmissionError(GovernorPolicyError):
    """Raised when a CAS request is rejected before durable mutation."""


class GovernorPolicyIntegrityError(GovernorPolicyError):
    """Raised when stored head evidence fails verification."""


# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------


def _status_from_wire(value: object) -> GovernorStoreStatus:
    if not isinstance(value, str):
        raise GovernorPolicyIntegrityError("CAS status must be a string")
    try:
        return GovernorStoreStatus(value)
    except ValueError as exc:
        raise GovernorPolicyIntegrityError(f"unknown CAS status: {value!r}") from exc


def _policy_snapshot(root: Mapping[str, Any]) -> PolicyVersionSnapshot:
    """Project a coordination-store root row into a policy head snapshot."""

    try:
        return PolicyVersionSnapshot(
            namespace=str(root["namespace"]),
            policy_cid=root.get("root_cid"),
            generation=int(root["revision"]),
            transition_cid=root.get("transition_cid"),
        )
    except (KeyError, TypeError, ValueError, SemanticGovernorStoreContractError) as exc:
        raise GovernorPolicyIntegrityError(
            f"invalid policy head projection: {exc}"
        ) from exc


def _promotion_snapshot(root: Mapping[str, Any]) -> PromotionStateSnapshot:
    """Project a coordination-store root row into a promotion head snapshot."""

    try:
        return PromotionStateSnapshot(
            namespace=str(root["namespace"]),
            promotion_cid=root.get("root_cid"),
            generation=int(root["revision"]),
            transition_cid=root.get("transition_cid"),
        )
    except (KeyError, TypeError, ValueError, SemanticGovernorStoreContractError) as exc:
        raise GovernorPolicyIntegrityError(
            f"invalid promotion head projection: {exc}"
        ) from exc


def _require_dag_json_optional(
    value: Optional[str], name: str
) -> Optional[str]:
    if value is None:
        return None
    try:
        return validate_semantic_dag_json_cid(value, name)
    except SemanticGovernorStoreContractError as exc:
        raise GovernorPolicyAdmissionError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Policy repository
# ---------------------------------------------------------------------------


class DurableCompressionPolicyRepository:
    """Versioned compression-policy head CAS over ``DurableCoordinationStore``.

    Implements ``CompressionPolicyRepository``.  Heads live in
    ``semantic-governor/<workspace>/policy``.  Each successful CAS stores an
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

    def _namespace(self, workspace: str) -> str:
        try:
            workspace = validate_governor_workspace(workspace)
            return governor_namespace(workspace, GovernorNamespaceRole.POLICY)
        except SemanticGovernorStoreContractError as exc:
            raise GovernorPolicyAdmissionError(str(exc)) from exc

    def current_policy(self, workspace: str) -> PolicyVersionSnapshot:
        """Return the currently visible policy head (generation zero if empty)."""

        namespace = self._namespace(workspace)
        try:
            root = self._store.current_state_root(namespace)
        except ArtifactIntegrityError as exc:
            raise GovernorPolicyIntegrityError(str(exc)) from exc
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
    ) -> PolicyCASResult:
        """Atomically publish a successor policy head or report a typed conflict.

        Preconditions (fail-closed):

        * generation-zero expects a null policy CID; non-zero expects a CID
        * ``new_policy_cid`` is a distinct canonical dag-json CID already stored
        * ``operation_id`` is a durable idempotency key
        """

        namespace = self._namespace(workspace)
        try:
            expected_generation, expected_policy_cid = validate_generation_expectation(
                expected_generation, expected_policy_cid
            )
            operation_id = validate_operation_id(operation_id)
            new_policy_cid = validate_semantic_dag_json_cid(
                new_policy_cid, "new_policy_cid"
            )
            if expected_policy_cid is not None:
                expected_policy_cid = validate_semantic_dag_json_cid(
                    expected_policy_cid, "expected_policy_cid"
                )
        except SemanticGovernorStoreContractError as exc:
            raise GovernorPolicyAdmissionError(str(exc)) from exc

        if expected_policy_cid == new_policy_cid:
            raise GovernorPolicyAdmissionError(
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
        except ArtifactNotFound as exc:
            # Successor block missing: do not invent a head mutation.
            try:
                before = self.current_policy(workspace)
            except GovernorPolicyError:
                before = PolicyVersionSnapshot(namespace, None, 0, None)
            return PolicyCASResult(
                GovernorStoreStatus.UNAVAILABLE,
                before,
                before,
                None,
                "successor_unavailable",
                False,
                False,
                operation_id,
            )
        except ArtifactIntegrityError as exc:
            try:
                before = self.current_policy(workspace)
            except GovernorPolicyIntegrityError:
                # Current head itself is corrupt — report without mutation.
                before = PolicyVersionSnapshot(namespace, None, 0, None)
                return PolicyCASResult(
                    GovernorStoreStatus.CORRUPT,
                    before,
                    before,
                    None,
                    "integrity_failure",
                    False,
                    False,
                    operation_id,
                )
            return PolicyCASResult(
                GovernorStoreStatus.CORRUPT,
                before,
                before,
                None,
                "integrity_failure",
                False,
                False,
                operation_id,
            )
        except ValueError as exc:
            raise GovernorPolicyAdmissionError(str(exc)) from exc

        return self._policy_result_from_wire(raw, operation_id=operation_id)

    def rollback_policy(
        self,
        workspace: str,
        *,
        expected_generation: int,
        expected_policy_cid: Optional[str],
        target_policy_cid: str,
        operation_id: str,
    ) -> PolicyCASResult:
        """CAS the policy head back to a prior policy CID without erasing history.

        Rollback is a forward transition: generation advances, a new transition
        block is indexed, and every earlier transition remains listable.  The
        target CID must already appear in this workspace's policy transition
        history (or be the generation-zero empty head, which is rejected — only
        previously published policy CIDs are valid rollback targets).
        """

        target_policy_cid = _require_dag_json_optional(
            target_policy_cid, "target_policy_cid"
        )
        assert target_policy_cid is not None

        history = self.policy_transitions(workspace)
        published = {row["new_root_cid"] for row in history}
        if target_policy_cid not in published:
            raise GovernorPolicyAdmissionError(
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

        namespace = self._namespace(workspace)
        rows = self._store.root_transitions(namespace)
        return [dict(row) for row in rows]

    @staticmethod
    def _policy_result_from_wire(
        raw: Mapping[str, Any], *, operation_id: str
    ) -> PolicyCASResult:
        status = _status_from_wire(raw.get("status"))
        before = _policy_snapshot(raw["before"])
        after = _policy_snapshot(raw["after"])
        transition_cid = raw.get("transition_cid")
        if transition_cid is not None:
            try:
                transition_cid = validate_semantic_dag_json_cid(
                    transition_cid, "transition_cid"
                )
            except SemanticGovernorStoreContractError as exc:
                raise GovernorPolicyIntegrityError(str(exc)) from exc
        reason_code = raw.get("reason_code")
        if not isinstance(reason_code, str):
            raise GovernorPolicyIntegrityError("CAS reason_code must be a string")
        local_durable = bool(raw.get("local_durable"))
        replicated = bool(raw.get("replicated"))
        # Prefer the caller's validated operation_id when the wire omits it.
        wire_op = raw.get("operation_id", operation_id)
        if not isinstance(wire_op, str):
            wire_op = operation_id
        try:
            return PolicyCASResult(
                status,
                before,
                after,
                transition_cid,
                reason_code,
                local_durable,
                replicated,
                wire_op,
            )
        except SemanticGovernorStoreContractError as exc:
            raise GovernorPolicyIntegrityError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Promotion repository
# ---------------------------------------------------------------------------


class DurablePromotionStateRepository:
    """Versioned promotion-head CAS with separate, immutable authorization CIDs.

    Implements ``PromotionStateRepository``.  A candidate cannot authorize its
    own promotion: ``candidate_cid`` and ``authorization_cid`` must be distinct
    dag-json CIDs, and both are recorded on every result (including conflicts).
    """

    def __init__(self, store: DurableCoordinationStore) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store

    @property
    def store(self) -> DurableCoordinationStore:
        """Injected coordination store (diagnostics / composition only)."""

        return self._store

    def _namespace(self, workspace: str) -> str:
        try:
            workspace = validate_governor_workspace(workspace)
            return governor_namespace(workspace, GovernorNamespaceRole.PROMOTION)
        except SemanticGovernorStoreContractError as exc:
            raise GovernorPolicyAdmissionError(str(exc)) from exc

    def current_promotion(self, workspace: str) -> PromotionStateSnapshot:
        """Return the currently visible promotion head (generation zero if empty)."""

        namespace = self._namespace(workspace)
        try:
            root = self._store.current_state_root(namespace)
        except ArtifactIntegrityError as exc:
            raise GovernorPolicyIntegrityError(str(exc)) from exc
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
        authorization_cid: str,
    ) -> PromotionCASResult:
        """Atomically publish a successor promotion head with separate authorization.

        Authority rules (fail-closed):

        * ``candidate_cid`` must not equal ``authorization_cid`` (no self-promotion)
        * expected generation + expected promotion CID must match the live head
        * concurrent writers / ABA pairs yield at most one ``updated`` success
        """

        namespace = self._namespace(workspace)
        try:
            expected_generation, expected_promotion_cid = (
                validate_generation_expectation(
                    expected_generation, expected_promotion_cid
                )
            )
            operation_id = validate_operation_id(operation_id)
            new_promotion_cid = validate_semantic_dag_json_cid(
                new_promotion_cid, "new_promotion_cid"
            )
            candidate_cid = validate_semantic_dag_json_cid(
                candidate_cid, "candidate_cid"
            )
            authorization_cid = validate_semantic_dag_json_cid(
                authorization_cid, "authorization_cid"
            )
            if expected_promotion_cid is not None:
                expected_promotion_cid = validate_semantic_dag_json_cid(
                    expected_promotion_cid, "expected_promotion_cid"
                )
        except SemanticGovernorStoreContractError as exc:
            raise GovernorPolicyAdmissionError(str(exc)) from exc

        if candidate_cid == authorization_cid:
            raise GovernorPolicyAdmissionError(
                "candidate cannot authorize its own promotion"
            )
        if expected_promotion_cid == new_promotion_cid:
            raise GovernorPolicyAdmissionError(
                "new_promotion_cid must differ from expected_promotion_cid"
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
            except GovernorPolicyError:
                before = PromotionStateSnapshot(namespace, None, 0, None)
            return PromotionCASResult(
                GovernorStoreStatus.UNAVAILABLE,
                before,
                before,
                None,
                "successor_unavailable",
                False,
                False,
                operation_id,
                candidate_cid,
                authorization_cid,
            )
        except ArtifactIntegrityError:
            try:
                before = self.current_promotion(workspace)
            except GovernorPolicyIntegrityError:
                before = PromotionStateSnapshot(namespace, None, 0, None)
                return PromotionCASResult(
                    GovernorStoreStatus.CORRUPT,
                    before,
                    before,
                    None,
                    "integrity_failure",
                    False,
                    False,
                    operation_id,
                    candidate_cid,
                    authorization_cid,
                )
            return PromotionCASResult(
                GovernorStoreStatus.CORRUPT,
                before,
                before,
                None,
                "integrity_failure",
                False,
                False,
                operation_id,
                candidate_cid,
                authorization_cid,
            )
        except ValueError as exc:
            raise GovernorPolicyAdmissionError(str(exc)) from exc

        return self._promotion_result_from_wire(
            raw,
            operation_id=operation_id,
            candidate_cid=candidate_cid,
            authorization_cid=authorization_cid,
        )

    def promotion_transitions(self, workspace: str) -> list[dict[str, Any]]:
        """Return immutable promotion root transitions in generation order."""

        namespace = self._namespace(workspace)
        rows = self._store.root_transitions(namespace)
        return [dict(row) for row in rows]

    @staticmethod
    def _promotion_result_from_wire(
        raw: Mapping[str, Any],
        *,
        operation_id: str,
        candidate_cid: str,
        authorization_cid: str,
    ) -> PromotionCASResult:
        status = _status_from_wire(raw.get("status"))
        before = _promotion_snapshot(raw["before"])
        after = _promotion_snapshot(raw["after"])
        transition_cid = raw.get("transition_cid")
        if transition_cid is not None:
            try:
                transition_cid = validate_semantic_dag_json_cid(
                    transition_cid, "transition_cid"
                )
            except SemanticGovernorStoreContractError as exc:
                raise GovernorPolicyIntegrityError(str(exc)) from exc
        reason_code = raw.get("reason_code")
        if not isinstance(reason_code, str):
            raise GovernorPolicyIntegrityError("CAS reason_code must be a string")
        local_durable = bool(raw.get("local_durable"))
        replicated = bool(raw.get("replicated"))
        wire_op = raw.get("operation_id", operation_id)
        if not isinstance(wire_op, str):
            wire_op = operation_id
        try:
            return PromotionCASResult(
                status,
                before,
                after,
                transition_cid,
                reason_code,
                local_durable,
                replicated,
                wire_op,
                candidate_cid,
                authorization_cid,
            )
        except SemanticGovernorStoreContractError as exc:
            raise GovernorPolicyIntegrityError(str(exc)) from exc


class DurablePolicyCASRepositories:
    """Compose policy and promotion CAS repositories over one coordination store."""

    def __init__(self, store: DurableCoordinationStore) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store
        self.policy = DurableCompressionPolicyRepository(store)
        self.promotion = DurablePromotionStateRepository(store)

    @property
    def store(self) -> DurableCoordinationStore:
        return self._store

    def current_policy(self, workspace: str) -> PolicyVersionSnapshot:
        return self.policy.current_policy(workspace)

    def compare_and_swap_policy(
        self,
        workspace: str,
        *,
        expected_generation: int,
        expected_policy_cid: Optional[str],
        new_policy_cid: str,
        operation_id: str,
    ) -> PolicyCASResult:
        return self.policy.compare_and_swap_policy(
            workspace,
            expected_generation=expected_generation,
            expected_policy_cid=expected_policy_cid,
            new_policy_cid=new_policy_cid,
            operation_id=operation_id,
        )

    def rollback_policy(
        self,
        workspace: str,
        *,
        expected_generation: int,
        expected_policy_cid: Optional[str],
        target_policy_cid: str,
        operation_id: str,
    ) -> PolicyCASResult:
        return self.policy.rollback_policy(
            workspace,
            expected_generation=expected_generation,
            expected_policy_cid=expected_policy_cid,
            target_policy_cid=target_policy_cid,
            operation_id=operation_id,
        )

    def policy_transitions(self, workspace: str) -> list[dict[str, Any]]:
        return self.policy.policy_transitions(workspace)

    def current_promotion(self, workspace: str) -> PromotionStateSnapshot:
        return self.promotion.current_promotion(workspace)

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
    ) -> PromotionCASResult:
        return self.promotion.compare_and_swap_promotion(
            workspace,
            expected_generation=expected_generation,
            expected_promotion_cid=expected_promotion_cid,
            new_promotion_cid=new_promotion_cid,
            operation_id=operation_id,
            candidate_cid=candidate_cid,
            authorization_cid=authorization_cid,
        )

    def promotion_transitions(self, workspace: str) -> list[dict[str, Any]]:
        return self.promotion.promotion_transitions(workspace)


__all__ = [
    "POLICY_MODULE_INTERFACE",
    "PROMOTION_MODULE_INTERFACE",
    "POLICY_CAS_SCHEMA",
    "GovernorPolicyError",
    "GovernorPolicyAdmissionError",
    "GovernorPolicyIntegrityError",
    "DurableCompressionPolicyRepository",
    "DurablePromotionStateRepository",
    "DurablePolicyCASRepositories",
]
