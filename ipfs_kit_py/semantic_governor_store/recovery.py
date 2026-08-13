"""Governor-domain recovery over DurableCoordinationStore (SCG-022).

``recover_governor_store`` rebuilds derived indexes from verified immutable
blocks and projects closed policy, promotion, and history heads into an
``AuditRecoveryReport``.

Authority rules (normative, fail-closed):

* Immutable blocks are authoritative; SQLite indexes are rebuildable only.
* Recovery never invents promotion, completion, or a winner among ambiguous
  successors — those conditions surface as closed corruption errors.
* Semantic heads must re-verify as canonical dag-json CIDs and, for history,
  as closed history-manifest envelopes that re-derive their head CID.
* Interrupted audits reopen to the prior head or the sole durable successor;
  idempotent operation-id replay completes any unfinished publication without
  silent overwrite.

Does not open a second object store, WAL, daemon, or receipt hierarchy.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Final, Mapping, Optional

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    DurableCoordinationStore,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    MAX_RECOVERY_ERRORS,
    AuditRecoveryReport,
    GovernorHistoryRole,
    GovernorNamespaceRole,
    HistoryHeadSnapshot,
    PolicyVersionSnapshot,
    PromotionStateSnapshot,
    SemanticGovernorStoreContractError,
    parse_governor_namespace,
    validate_semantic_dag_json_cid,
)
from ipfs_kit_py.semantic_governor_store.history import (
    HISTORY_MANIFEST_INTERFACE,
    HISTORY_MANIFEST_SCHEMA,
    DurableAuditHistoryStore,
    GovernorHistoryIntegrityError,
    cid_for_history_manifest,
)

# ---------------------------------------------------------------------------
# Schema / interface constants
# ---------------------------------------------------------------------------

RECOVERY_MODULE_INTERFACE: Final[str] = "GovernorStoreRecovery@1"
RECOVERY_SCHEMA: Final[str] = "ipfs-kit.semantic-governor-store.recovery@1"

_HISTORY_NAMESPACE_TO_ROLE: Final[Mapping[GovernorNamespaceRole, GovernorHistoryRole]] = (
    MappingProxyType(
        {
            GovernorNamespaceRole.AUDIT: GovernorHistoryRole.AUDIT,
            GovernorNamespaceRole.CALIBRATION: GovernorHistoryRole.CALIBRATION,
            GovernorNamespaceRole.BENCHMARK: GovernorHistoryRole.BENCHMARK,
        }
    )
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GovernorRecoveryError(ValueError):
    """Base error for governor store recovery admission failures."""


class GovernorRecoveryIntegrityError(GovernorRecoveryError):
    """Raised when recovery evidence fails closed verification (optional raise path)."""


# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------


def _error_record(code: str, message: str) -> Mapping[str, str]:
    return MappingProxyType({"code": code, "message": message})


def _append_error(
    errors: list[Mapping[str, str]], *, code: str, message: str
) -> None:
    if len(errors) >= MAX_RECOVERY_ERRORS:
        return
    errors.append(_error_record(code, message))


def _require_dag_json_optional(
    value: Optional[str], name: str
) -> Optional[str]:
    if value is None:
        return None
    return validate_semantic_dag_json_cid(value, name)


def _project_policy_snapshot(root: Mapping[str, Any]) -> PolicyVersionSnapshot:
    return PolicyVersionSnapshot(
        namespace=str(root["namespace"]),
        policy_cid=root.get("root_cid"),
        generation=int(root["revision"]),
        transition_cid=root.get("transition_cid"),
    )


def _project_promotion_snapshot(root: Mapping[str, Any]) -> PromotionStateSnapshot:
    return PromotionStateSnapshot(
        namespace=str(root["namespace"]),
        promotion_cid=root.get("root_cid"),
        generation=int(root["revision"]),
        transition_cid=root.get("transition_cid"),
    )


def _project_history_snapshot(
    root: Mapping[str, Any], *, history_role: GovernorHistoryRole
) -> HistoryHeadSnapshot:
    return HistoryHeadSnapshot(
        namespace=str(root["namespace"]),
        head_cid=root.get("root_cid"),
        generation=int(root["revision"]),
        transition_cid=root.get("transition_cid"),
        history_role=history_role,
    )


def _verify_history_manifest_head(
    store: DurableCoordinationStore, head_cid: str
) -> None:
    """Require a closed, self-identifying history-manifest head (fail closed)."""

    try:
        raw = store.get(head_cid)
    except Exception as exc:
        raise GovernorRecoveryIntegrityError(
            f"history head {head_cid} is not retrievable: {exc}"
        ) from exc
    if not isinstance(raw, Mapping):
        raise GovernorRecoveryIntegrityError(
            f"history head {head_cid} is not a mapping"
        )
    manifest = dict(raw)
    if manifest.get("schema") != HISTORY_MANIFEST_SCHEMA:
        raise GovernorRecoveryIntegrityError(
            f"history head {head_cid} has unknown manifest schema"
        )
    if manifest.get("interface_id") != HISTORY_MANIFEST_INTERFACE:
        raise GovernorRecoveryIntegrityError(
            f"history head {head_cid} has unknown manifest interface"
        )
    try:
        validate_semantic_dag_json_cid(manifest.get("entry_cid"), "entry_cid")
    except SemanticGovernorStoreContractError as exc:
        raise GovernorRecoveryIntegrityError(str(exc)) from exc
    previous = manifest.get("previous_head_cid")
    if previous is not None:
        try:
            validate_semantic_dag_json_cid(previous, "previous_head_cid")
        except SemanticGovernorStoreContractError as exc:
            raise GovernorRecoveryIntegrityError(str(exc)) from exc
    recomputed = cid_for_history_manifest(manifest)
    if recomputed != head_cid:
        raise GovernorRecoveryIntegrityError(
            f"history manifest CID mismatch: recomputed {recomputed}, "
            f"expected {head_cid}"
        )


def _collect_ignored_idempotent_transitions(
    store: DurableCoordinationStore,
) -> tuple[str, ...]:
    """Return transition CIDs that are durable evidence of idempotent replays.

    Recovery never invents transitions.  When the same operation_id already
    has a durable transition, the CAS path reports ``unchanged`` without a new
    transition CID.  The ignored set therefore remains empty unless a future
    reconstruction path surfaces explicit no-op transition markers.
    """

    del store  # present for API symmetry with reconstruction sources
    return ()


# ---------------------------------------------------------------------------
# Core recovery
# ---------------------------------------------------------------------------


def recover_governor_store(
    store: DurableCoordinationStore,
    *,
    rebuild: bool = True,
) -> AuditRecoveryReport:
    """Verify immutable blocks, rebuild indexes, and project governor heads.

    Parameters
    ----------
    store:
        Injected ``DurableCoordinationStore`` (sole storage authority).
    rebuild:
        When true (default), recreate derived indexes from verified blocks.
        When false, only verify; heads are still projected from the live index
        after a successful verify pass.

    Returns
    -------
    AuditRecoveryReport
        Closed recovery evidence.  On corruption or ambiguous successor chains
        the reconstructed head tuples are empty and ``errors`` carries closed
        ``{code, message}`` records.  Recovery never invents promotion or
        completion outcomes.
    """

    if not isinstance(store, DurableCoordinationStore):
        raise TypeError("store must be a DurableCoordinationStore")

    verified_blocks = 0
    errors: list[Mapping[str, str]] = []
    raw_report: Mapping[str, Any] | None = None

    try:
        raw_report = store.recover(rebuild=rebuild)
        verified_blocks = int(raw_report["verified_blocks"])
    except ArtifactIntegrityError as exc:
        # Underlying reconstruction fails closed (corrupt blocks, forks, raw
        # transitions).  Do not invent governor heads from partial evidence.
        message = str(exc)
        code = "ambiguous_promotion" if "breaks its namespace chain" in message else "corrupt"
        return AuditRecoveryReport(
            verified_blocks,
            (),
            (),
            (),
            (),
            (_error_record(code, message),),
        )
    except (TypeError, ValueError, OSError) as exc:
        return AuditRecoveryReport(
            verified_blocks,
            (),
            (),
            (),
            (),
            (_error_record("corrupt", str(exc)),),
        )

    policy_heads: list[PolicyVersionSnapshot] = []
    promotion_heads: list[PromotionStateSnapshot] = []
    history_heads: list[HistoryHeadSnapshot] = []
    projection_failed = False

    try:
        roots = store.state_roots()
    except ArtifactIntegrityError as exc:
        return AuditRecoveryReport(
            verified_blocks,
            (),
            (),
            (),
            (),
            (_error_record("corrupt", str(exc)),),
        )

    for root in roots:
        namespace = root.get("namespace")
        if not isinstance(namespace, str):
            projection_failed = True
            _append_error(
                errors,
                code="corrupt",
                message="state root row missing namespace",
            )
            continue
        try:
            _workspace, role = parse_governor_namespace(namespace)
        except SemanticGovernorStoreContractError:
            # Non-governor coordination roots are out of this domain projection.
            continue

        try:
            if role is GovernorNamespaceRole.POLICY:
                snapshot = _project_policy_snapshot(root)
                if snapshot.policy_cid is not None:
                    _require_dag_json_optional(snapshot.policy_cid, "policy_cid")
                if snapshot.transition_cid is not None:
                    _require_dag_json_optional(
                        snapshot.transition_cid, "transition_cid"
                    )
                policy_heads.append(snapshot)
            elif role is GovernorNamespaceRole.PROMOTION:
                snapshot = _project_promotion_snapshot(root)
                if snapshot.promotion_cid is not None:
                    _require_dag_json_optional(
                        snapshot.promotion_cid, "promotion_cid"
                    )
                if snapshot.transition_cid is not None:
                    _require_dag_json_optional(
                        snapshot.transition_cid, "transition_cid"
                    )
                # Recovery reports the reconstructed promotion head only; it
                # never asserts completion or invents authorization.
                promotion_heads.append(snapshot)
            elif role in _HISTORY_NAMESPACE_TO_ROLE:
                history_role = _HISTORY_NAMESPACE_TO_ROLE[role]
                snapshot = _project_history_snapshot(
                    root, history_role=history_role
                )
                if snapshot.head_cid is not None:
                    _require_dag_json_optional(snapshot.head_cid, "head_cid")
                    _verify_history_manifest_head(store, snapshot.head_cid)
                if snapshot.transition_cid is not None:
                    _require_dag_json_optional(
                        snapshot.transition_cid, "transition_cid"
                    )
                history_heads.append(snapshot)
            # RECEIPTS namespace is a head/history role in contracts but has no
            # generation-bearing CAS repository in this package yet — skip.
        except (
            SemanticGovernorStoreContractError,
            GovernorRecoveryIntegrityError,
            TypeError,
            ValueError,
            KeyError,
        ) as exc:
            projection_failed = True
            code = "corrupt"
            message = str(exc)
            if "promotion" in message.lower() and "ambiguous" in message.lower():
                code = "ambiguous_promotion"
            _append_error(errors, code=code, message=message)

    # Deep-verify history chains when projection still looks healthy so a
    # broken previous_head link cannot surface as a trusted reconstructed head.
    if not projection_failed and history_heads:
        history_store = DurableAuditHistoryStore(store)
        for head in list(history_heads):
            if head.generation == 0 or head.head_cid is None:
                continue
            try:
                # Walk re-verifies each manifest CID and generation linkage.
                history_store.list_entry_cids(
                    parse_governor_namespace(head.namespace)[0],
                    head.history_role,
                    offset=0,
                    limit=1,
                )
            except (
                GovernorHistoryIntegrityError,
                SemanticGovernorStoreContractError,
                ArtifactIntegrityError,
                ValueError,
            ) as exc:
                projection_failed = True
                _append_error(
                    errors,
                    code="corrupt",
                    message=(
                        f"history chain verification failed for "
                        f"{head.namespace}: {exc}"
                    ),
                )

    ignored = _collect_ignored_idempotent_transitions(store)

    if projection_failed:
        # Fail closed: do not return partial heads that could be mistaken for
        # a complete, authoritative recovery of promotion or audit state.
        return AuditRecoveryReport(
            verified_blocks,
            (),
            (),
            (),
            ignored,
            tuple(errors) if errors else (
                _error_record("corrupt", "governor head projection failed"),
            ),
        )

    # Deterministic ordering by namespace for stable report identity.
    policy_heads.sort(key=lambda item: item.namespace)
    promotion_heads.sort(key=lambda item: item.namespace)
    history_heads.sort(key=lambda item: item.namespace)

    return AuditRecoveryReport(
        verified_blocks,
        tuple(policy_heads),
        tuple(promotion_heads),
        tuple(history_heads),
        ignored,
        tuple(errors),
    )


# ---------------------------------------------------------------------------
# Facade class (protocol-shaped recover_governor_store surface)
# ---------------------------------------------------------------------------


class DurableGovernorStoreRecovery:
    """Thin recovery facade over an injected ``DurableCoordinationStore``.

    Implements the ``recover_governor_store`` method of ``SemanticGovernorStore@1``
    without owning artifacts, histories, or policy CAS writers.
    """

    def __init__(self, store: DurableCoordinationStore) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store

    @property
    def store(self) -> DurableCoordinationStore:
        """Injected coordination store (diagnostics / composition only)."""

        return self._store

    def recover_governor_store(self, *, rebuild: bool = True) -> AuditRecoveryReport:
        """Rebuild indexes from verified blocks and project governor heads."""

        return recover_governor_store(self._store, rebuild=rebuild)


__all__ = [
    "RECOVERY_MODULE_INTERFACE",
    "RECOVERY_SCHEMA",
    "GovernorRecoveryError",
    "GovernorRecoveryIntegrityError",
    "recover_governor_store",
    "DurableGovernorStoreRecovery",
]
