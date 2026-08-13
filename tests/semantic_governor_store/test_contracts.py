"""Contract vectors for the narrow durable SemanticGovernorStore protocol (SCG-010)."""

from __future__ import annotations

import inspect
from typing import Any, Mapping, Optional, get_type_hints

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import cid_for_bytes
from ipfs_kit_py.semantic_governor_store import (
    CONTRACT_VERSION,
    GOVERNOR_NAMESPACE_PREFIX,
    SEMANTIC_GOVERNOR_STORE_INTERFACE,
    AuditRecoveryReport,
    GovernorArtifactKind,
    GovernorArtifactWriteResult,
    GovernorHistoryRole,
    GovernorNamespaceRole,
    GovernorProviderStatus,
    GovernorStoreStatus,
    HistoryAppendResult,
    HistoryHeadSnapshot,
    PolicyCASResult,
    PolicyVersionSnapshot,
    PromotionCASResult,
    PromotionStateSnapshot,
    ReceiptIssuanceResult,
    SemanticGovernorStore,
    SemanticGovernorStoreContractError,
    governor_artifact_kinds,
    governor_namespace,
    governor_namespace_roles,
    governor_store_statuses,
    history_namespace,
    parse_governor_namespace,
    validate_generation_expectation,
    validate_governor_namespace,
    validate_governor_workspace,
    validate_operation_id,
    validate_semantic_dag_json_cid,
    validate_verified_cid,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    AuditHistoryStore,
    CompressionPolicyRepository,
    PromotionStateRepository,
)


CID = cid_for_bytes(b"governor-store-contract")
TRANSITION = cid_for_bytes(b"governor-store-transition")
POLICY = cid_for_bytes(b"governor-policy-v1")
POLICY_NEXT = cid_for_bytes(b"governor-policy-v2")
PROMOTION = cid_for_bytes(b"governor-promotion-v1")
PROMOTION_NEXT = cid_for_bytes(b"governor-promotion-v2")
CANDIDATE = cid_for_bytes(b"governor-candidate")
AUTHORIZATION = cid_for_bytes(b"governor-authorization")
ENTRY = cid_for_bytes(b"governor-history-entry")
HEAD = cid_for_bytes(b"governor-history-head")


def _policy_ns(workspace: str = "default") -> str:
    return governor_namespace(workspace, GovernorNamespaceRole.POLICY)


def _promotion_ns(workspace: str = "default") -> str:
    return governor_namespace(workspace, GovernorNamespaceRole.PROMOTION)


def _history_ns(
    workspace: str = "default", role: GovernorHistoryRole = GovernorHistoryRole.AUDIT
) -> str:
    return history_namespace(workspace, role)


# ---------------------------------------------------------------------------
# Closed vocabularies and package surface
# ---------------------------------------------------------------------------


def test_interface_constants_are_versioned() -> None:
    assert CONTRACT_VERSION == 1
    assert SEMANTIC_GOVERNOR_STORE_INTERFACE == "SemanticGovernorStore@1"
    assert GOVERNOR_NAMESPACE_PREFIX == "semantic-governor"


def test_artifact_kinds_are_closed() -> None:
    expected = (
        "audit",
        "calibration",
        "benchmark",
        "policy",
        "policy_candidate",
        "evaluation",
        "promotion",
        "run_receipt",
        "promotion_receipt",
        "history_manifest",
    )
    assert governor_artifact_kinds() == expected
    assert len(GovernorArtifactKind) == len(expected)
    with pytest.raises(ValueError):
        GovernorArtifactKind("model_reasoning")


def test_namespace_roles_and_statuses_are_closed() -> None:
    assert governor_namespace_roles() == (
        "audit",
        "calibration",
        "benchmark",
        "policy",
        "promotion",
        "receipts",
    )
    assert governor_store_statuses() == (
        "updated",
        "unchanged",
        "conflict",
        "unavailable",
        "corrupt",
    )
    assert set(governor_store_statuses()) >= {
        "conflict",
        "corrupt",
        "unavailable",
    }


# ---------------------------------------------------------------------------
# Namespaces, operation IDs, verified CIDs, generation expectations
# ---------------------------------------------------------------------------


def test_closed_governor_namespaces_round_trip() -> None:
    for role in GovernorNamespaceRole:
        ns = governor_namespace("worker-1", role)
        workspace, parsed = parse_governor_namespace(ns)
        assert workspace == "worker-1"
        assert parsed is role
        assert ns.startswith("semantic-governor/worker-1/")


def test_history_namespaces_map_to_closed_roles() -> None:
    assert history_namespace("ws", GovernorHistoryRole.AUDIT) == (
        "semantic-governor/ws/audit"
    )
    assert history_namespace("ws", "calibration") == (
        "semantic-governor/ws/calibration"
    )
    assert history_namespace("ws", GovernorHistoryRole.BENCHMARK) == (
        "semantic-governor/ws/benchmark"
    )


@pytest.mark.parametrize(
    "workspace",
    ["", "Upper", "/bad", "has space", "a" * 64, "-leading", "trailing-"],
)
def test_workspace_and_namespace_validation_fail_closed(workspace: str) -> None:
    with pytest.raises(SemanticGovernorStoreContractError):
        validate_governor_workspace(workspace)
    with pytest.raises(SemanticGovernorStoreContractError):
        governor_namespace(workspace, GovernorNamespaceRole.POLICY)


@pytest.mark.parametrize(
    "namespace",
    [
        "",
        "Upper/x/y",
        "semantic-governor//policy",
        "semantic-governor/ws",
        "semantic-governor/ws/unknown",
        "other/ws/policy",
        "semantic-governor/ws/policy/extra",
    ],
)
def test_parse_governor_namespace_rejects_open_shapes(namespace: str) -> None:
    with pytest.raises(SemanticGovernorStoreContractError):
        parse_governor_namespace(namespace)


@pytest.mark.parametrize(
    "operation_id",
    ["", "Bad", "-x", "x-", "a" * 129, "has space", "UPPER"],
)
def test_operation_ids_are_strict(operation_id: str) -> None:
    with pytest.raises(SemanticGovernorStoreContractError):
        validate_operation_id(operation_id)


def test_operation_ids_accept_normalized_tokens() -> None:
    assert validate_operation_id("put-artifact:1") == "put-artifact:1"
    assert validate_operation_id("a") == "a"
    assert validate_operation_id("a" * 128) == "a" * 128


@pytest.mark.parametrize("cid", ["cid", "bnot-base32!", "B" + CID[1:], ""])
def test_verified_cids_reject_malformed_values(cid: str) -> None:
    with pytest.raises(SemanticGovernorStoreContractError):
        validate_verified_cid(cid)


def test_semantic_cids_reject_raw_transport_blocks() -> None:
    raw = cid_for_bytes(b"structured-but-raw", codec="raw")
    with pytest.raises(SemanticGovernorStoreContractError, match="dag-json"):
        validate_semantic_dag_json_cid(raw)
    assert validate_semantic_dag_json_cid(CID) == CID


@pytest.mark.parametrize("generation,cid", [(0, CID), (1, None)])
def test_generation_expectations_are_closed_and_coherent(
    generation: int, cid: str | None
) -> None:
    with pytest.raises(SemanticGovernorStoreContractError):
        validate_generation_expectation(generation, cid)


def test_generation_expectations_accept_coherent_pairs() -> None:
    assert validate_generation_expectation(0, None) == (0, None)
    assert validate_generation_expectation(3, CID) == (3, CID)


# ---------------------------------------------------------------------------
# Value records: round-trip and fail-closed invariants
# ---------------------------------------------------------------------------


def test_artifact_write_result_round_trips() -> None:
    write = GovernorArtifactWriteResult(
        CID,
        GovernorArtifactKind.AUDIT,
        True,
        GovernorProviderStatus.AVAILABLE,
        True,
        "replicated",
    )
    assert GovernorArtifactWriteResult.from_dict(write.to_dict()) == write


def test_artifact_write_result_rejects_false_durability_claims() -> None:
    with pytest.raises(SemanticGovernorStoreContractError):
        GovernorArtifactWriteResult(
            CID,
            GovernorArtifactKind.AUDIT,
            False,
            GovernorProviderStatus.AVAILABLE,
            True,
            "bad",
        )
    with pytest.raises(SemanticGovernorStoreContractError):
        GovernorArtifactWriteResult(
            CID,
            GovernorArtifactKind.AUDIT,
            True,
            GovernorProviderStatus.UNAVAILABLE,
            True,
            "mismatch",
        )


def test_policy_snapshot_and_cas_round_trip() -> None:
    before = PolicyVersionSnapshot(_policy_ns(), None, 0, None)
    after = PolicyVersionSnapshot(_policy_ns(), POLICY, 1, TRANSITION)
    result = PolicyCASResult(
        GovernorStoreStatus.UPDATED,
        before,
        after,
        TRANSITION,
        "updated",
        True,
        False,
        "cas-policy-1",
    )
    assert PolicyCASResult.from_dict(result.to_dict()) == result
    assert PolicyVersionSnapshot.from_dict(before.to_dict()) == before


def test_policy_snapshot_requires_policy_namespace_role() -> None:
    with pytest.raises(SemanticGovernorStoreContractError, match="policy"):
        PolicyVersionSnapshot(_promotion_ns(), None, 0, None)


def test_policy_cas_conflict_and_corrupt_outcomes_preserve_head() -> None:
    head = PolicyVersionSnapshot(_policy_ns(), POLICY, 2, TRANSITION)
    conflict = PolicyCASResult(
        GovernorStoreStatus.CONFLICT,
        head,
        head,
        None,
        "stale_expectation",
        True,
        False,
        "cas-policy-stale",
    )
    corrupt = PolicyCASResult(
        GovernorStoreStatus.CORRUPT,
        head,
        head,
        None,
        "integrity_failure",
        False,
        False,
        "cas-policy-corrupt",
    )
    unavailable = PolicyCASResult(
        GovernorStoreStatus.UNAVAILABLE,
        head,
        head,
        None,
        "store_unavailable",
        False,
        False,
        "cas-policy-down",
    )
    for result in (conflict, corrupt, unavailable):
        assert result.after == result.before
        assert result.transition_cid is None
        assert PolicyCASResult.from_dict(result.to_dict()).status is result.status


def test_policy_cas_rejects_incoherent_updates() -> None:
    before = PolicyVersionSnapshot(_policy_ns(), None, 0, None)
    after = PolicyVersionSnapshot(_policy_ns(), POLICY, 2, TRANSITION)
    with pytest.raises(SemanticGovernorStoreContractError):
        PolicyCASResult(
            GovernorStoreStatus.UPDATED,
            before,
            after,
            TRANSITION,
            "updated",
            True,
            False,
            "bad-gen",
        )
    with pytest.raises(SemanticGovernorStoreContractError):
        PolicyCASResult(
            GovernorStoreStatus.CONFLICT,
            before,
            PolicyVersionSnapshot(_policy_ns(), POLICY, 1, TRANSITION),
            None,
            "stale_expectation",
            True,
            False,
            "mutated",
        )


def test_promotion_cas_rejects_self_authorization() -> None:
    before = PromotionStateSnapshot(_promotion_ns(), None, 0, None)
    after = PromotionStateSnapshot(
        _promotion_ns(), PROMOTION, 1, TRANSITION
    )
    with pytest.raises(SemanticGovernorStoreContractError, match="authorize"):
        PromotionCASResult(
            GovernorStoreStatus.UPDATED,
            before,
            after,
            TRANSITION,
            "updated",
            True,
            False,
            "promote-1",
            CANDIDATE,
            CANDIDATE,
        )


def test_promotion_cas_round_trip_and_idempotent_unchanged() -> None:
    before = PromotionStateSnapshot(_promotion_ns(), None, 0, None)
    after = PromotionStateSnapshot(
        _promotion_ns(), PROMOTION_NEXT, 1, TRANSITION
    )
    updated = PromotionCASResult(
        GovernorStoreStatus.UPDATED,
        before,
        after,
        TRANSITION,
        "updated",
        True,
        True,
        "promote-1",
        CANDIDATE,
        AUTHORIZATION,
    )
    unchanged = PromotionCASResult(
        GovernorStoreStatus.UNCHANGED,
        after,
        after,
        None,
        "idempotent_replay",
        True,
        False,
        "promote-1",
        CANDIDATE,
        AUTHORIZATION,
    )
    assert PromotionCASResult.from_dict(updated.to_dict()) == updated
    assert PromotionCASResult.from_dict(unchanged.to_dict()).status is (
        GovernorStoreStatus.UNCHANGED
    )


def test_history_append_result_round_trip() -> None:
    before = HistoryHeadSnapshot(
        _history_ns(), None, 0, None, GovernorHistoryRole.AUDIT
    )
    after = HistoryHeadSnapshot(
        _history_ns(), HEAD, 1, TRANSITION, GovernorHistoryRole.AUDIT
    )
    result = HistoryAppendResult(
        GovernorStoreStatus.UPDATED,
        before,
        after,
        ENTRY,
        TRANSITION,
        "updated",
        True,
        "append-audit-1",
    )
    assert HistoryAppendResult.from_dict(result.to_dict()) == result


def test_history_snapshot_requires_matching_role() -> None:
    with pytest.raises(SemanticGovernorStoreContractError):
        HistoryHeadSnapshot(
            _history_ns(role=GovernorHistoryRole.AUDIT),
            None,
            0,
            None,
            GovernorHistoryRole.CALIBRATION,
        )


def test_receipt_issuance_binds_existing_envelope_only() -> None:
    ok = ReceiptIssuanceResult(
        GovernorStoreStatus.UPDATED,
        CID,
        GovernorArtifactKind.RUN_RECEIPT,
        "mcp++/profile-g/task-receipt@1",
        True,
        "issued",
        "issue-run-1",
    )
    assert ReceiptIssuanceResult.from_dict(ok.to_dict()) == ok
    with pytest.raises(SemanticGovernorStoreContractError, match="existing envelope"):
        ReceiptIssuanceResult(
            GovernorStoreStatus.UPDATED,
            CID,
            GovernorArtifactKind.RUN_RECEIPT,
            "semantic-governor/receipt@1",
            True,
            "issued",
            "issue-run-2",
        )
    with pytest.raises(SemanticGovernorStoreContractError):
        ReceiptIssuanceResult(
            GovernorStoreStatus.UPDATED,
            CID,
            GovernorArtifactKind.AUDIT,
            "mcp++/profile-g/task-receipt@1",
            True,
            "issued",
            "issue-run-3",
        )


def test_audit_recovery_report_round_trip_and_closed_errors() -> None:
    policy = PolicyVersionSnapshot(_policy_ns("a"), POLICY, 1, TRANSITION)
    promotion = PromotionStateSnapshot(
        _promotion_ns("a"), PROMOTION, 1, TRANSITION
    )
    history = HistoryHeadSnapshot(
        _history_ns("a"), HEAD, 1, TRANSITION, GovernorHistoryRole.AUDIT
    )
    report = AuditRecoveryReport(
        4,
        (policy,),
        (promotion,),
        (history,),
        (TRANSITION,),
        ({"code": "corrupt", "message": "block failed verification"},),
    )
    assert AuditRecoveryReport.from_dict(report.to_dict()).to_dict() == (
        report.to_dict()
    )
    with pytest.raises(SemanticGovernorStoreContractError):
        AuditRecoveryReport(
            1,
            (policy, PolicyVersionSnapshot(_policy_ns("a"), POLICY_NEXT, 2, TRANSITION)),
            (),
            (),
            (),
            (),
        )
    with pytest.raises(SemanticGovernorStoreContractError):
        AuditRecoveryReport(-1, (), (), (), (), ())
    with pytest.raises(SemanticGovernorStoreContractError):
        AuditRecoveryReport(
            0,
            (),
            (),
            (),
            (),
            ({"code": "Bad", "message": "x"},),
        )


def test_closed_wire_objects_reject_unknown_fields() -> None:
    with pytest.raises(SemanticGovernorStoreContractError):
        PolicyVersionSnapshot.from_dict(
            {
                "namespace": _policy_ns(),
                "policy_cid": None,
                "generation": 0,
                "transition_cid": None,
                "extra": True,
            }
        )


# ---------------------------------------------------------------------------
# Protocol surface: required caller-supplied parameters
# ---------------------------------------------------------------------------


def test_semantic_governor_store_protocol_requires_verified_cid_generation_and_operation_id() -> None:
    required = {
        "put_artifact": {"expected_cid", "operation_id"},
        "get_verified_artifact": set(),
        "append_history": {
            "entry_cid",
            "expected_generation",
            "expected_head_cid",
            "operation_id",
        },
        "compare_and_swap_policy": {
            "expected_generation",
            "expected_policy_cid",
            "new_policy_cid",
            "operation_id",
        },
        "compare_and_swap_promotion": {
            "expected_generation",
            "expected_promotion_cid",
            "new_promotion_cid",
            "operation_id",
            "candidate_cid",
            "authorization_cid",
        },
        "issue_receipt": {
            "expected_cid",
            "envelope_schema",
            "operation_id",
        },
        "recover_governor_store": set(),
        "current_history": set(),
        "current_policy": set(),
        "current_promotion": set(),
    }
    for name, expected_kw in required.items():
        method = getattr(SemanticGovernorStore, name)
        sig = inspect.signature(method)
        keyword_only = {
            parameter.name
            for parameter in sig.parameters.values()
            if parameter.kind is inspect.Parameter.KEYWORD_ONLY
        }
        assert expected_kw <= keyword_only | set(sig.parameters), name
        for key in expected_kw:
            assert key in sig.parameters, f"{name} missing {key}"


def test_protocol_methods_are_declared_on_narrow_slices() -> None:
    assert hasattr(AuditHistoryStore, "append_history")
    assert hasattr(CompressionPolicyRepository, "compare_and_swap_policy")
    assert hasattr(PromotionStateRepository, "compare_and_swap_promotion")
    assert hasattr(SemanticGovernorStore, "put_artifact")
    assert hasattr(SemanticGovernorStore, "recover_governor_store")


def test_structural_protocol_accepts_complete_stub() -> None:
    class _Stub:
        def put_artifact(
            self,
            kind: GovernorArtifactKind,
            payload: Mapping[str, Any],
            *,
            expected_cid: str,
            operation_id: str,
            replicate: bool = True,
        ) -> GovernorArtifactWriteResult:
            return GovernorArtifactWriteResult(
                expected_cid,
                kind,
                True,
                GovernorProviderStatus.NOT_REQUESTED,
                False,
                "stored",
            )

        def get_verified_artifact(
            self,
            cid: str,
            *,
            expected_kind: Optional[GovernorArtifactKind] = None,
        ) -> Mapping[str, Any]:
            return {"cid": cid, "kind": None if expected_kind is None else expected_kind.value}

        def current_history(
            self, workspace: str, role: GovernorHistoryRole
        ) -> HistoryHeadSnapshot:
            return HistoryHeadSnapshot(
                history_namespace(workspace, role),
                None,
                0,
                None,
                role,
            )

        def append_history(
            self,
            workspace: str,
            role: GovernorHistoryRole,
            *,
            entry_cid: str,
            expected_generation: int,
            expected_head_cid: Optional[str],
            operation_id: str,
        ) -> HistoryAppendResult:
            before = HistoryHeadSnapshot(
                history_namespace(workspace, role),
                expected_head_cid,
                expected_generation,
                TRANSITION if expected_generation else None,
                role,
            )
            after = HistoryHeadSnapshot(
                history_namespace(workspace, role),
                entry_cid,
                expected_generation + 1,
                TRANSITION,
                role,
            )
            return HistoryAppendResult(
                GovernorStoreStatus.UPDATED,
                before,
                after,
                entry_cid,
                TRANSITION,
                "updated",
                True,
                operation_id,
            )

        def current_policy(self, workspace: str) -> PolicyVersionSnapshot:
            return PolicyVersionSnapshot(
                governor_namespace(workspace, GovernorNamespaceRole.POLICY),
                None,
                0,
                None,
            )

        def compare_and_swap_policy(
            self,
            workspace: str,
            *,
            expected_generation: int,
            expected_policy_cid: Optional[str],
            new_policy_cid: str,
            operation_id: str,
        ) -> PolicyCASResult:
            before = PolicyVersionSnapshot(
                governor_namespace(workspace, GovernorNamespaceRole.POLICY),
                expected_policy_cid,
                expected_generation,
                TRANSITION if expected_generation else None,
            )
            after = PolicyVersionSnapshot(
                governor_namespace(workspace, GovernorNamespaceRole.POLICY),
                new_policy_cid,
                expected_generation + 1,
                TRANSITION,
            )
            return PolicyCASResult(
                GovernorStoreStatus.UPDATED,
                before,
                after,
                TRANSITION,
                "updated",
                True,
                False,
                operation_id,
            )

        def current_promotion(self, workspace: str) -> PromotionStateSnapshot:
            return PromotionStateSnapshot(
                governor_namespace(workspace, GovernorNamespaceRole.PROMOTION),
                None,
                0,
                None,
            )

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
            before = PromotionStateSnapshot(
                governor_namespace(workspace, GovernorNamespaceRole.PROMOTION),
                expected_promotion_cid,
                expected_generation,
                TRANSITION if expected_generation else None,
            )
            after = PromotionStateSnapshot(
                governor_namespace(workspace, GovernorNamespaceRole.PROMOTION),
                new_promotion_cid,
                expected_generation + 1,
                TRANSITION,
            )
            return PromotionCASResult(
                GovernorStoreStatus.UPDATED,
                before,
                after,
                TRANSITION,
                "updated",
                True,
                False,
                operation_id,
                candidate_cid,
                authorization_cid,
            )

        def issue_receipt(
            self,
            kind: GovernorArtifactKind,
            payload: Mapping[str, Any],
            *,
            expected_cid: str,
            envelope_schema: str,
            operation_id: str,
        ) -> ReceiptIssuanceResult:
            return ReceiptIssuanceResult(
                GovernorStoreStatus.UPDATED,
                expected_cid,
                kind,
                envelope_schema,
                True,
                "issued",
                operation_id,
            )

        def recover_governor_store(self) -> AuditRecoveryReport:
            return AuditRecoveryReport(0, (), (), (), (), ())

    stub: SemanticGovernorStore = _Stub()
    write = stub.put_artifact(
        GovernorArtifactKind.POLICY,
        {"schema": "example"},
        expected_cid=CID,
        operation_id="op-1",
        replicate=False,
    )
    assert write.cid == CID
    cas = stub.compare_and_swap_policy(
        "default",
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=POLICY,
        operation_id="cas-1",
    )
    assert cas.status is GovernorStoreStatus.UPDATED
    assert cas.operation_id == "cas-1"
    report = stub.recover_governor_store()
    assert report.verified_blocks == 0


def test_package_import_is_inert_and_exports_protocol() -> None:
    import ipfs_kit_py.semantic_governor_store as pkg

    assert pkg.SemanticGovernorStore is SemanticGovernorStore
    assert "put_artifact" in dir(pkg.SemanticGovernorStore)
    # Importing contracts must not require constructing a store.
    assert inspect.isclass(pkg.GovernorArtifactKind)


def test_protocol_annotations_mention_expected_generation_and_cids() -> None:
    hints = get_type_hints(SemanticGovernorStore.compare_and_swap_policy)
    assert "expected_generation" in hints
    assert "expected_policy_cid" in hints
    assert "new_policy_cid" in hints
    assert "operation_id" in hints
    hist = get_type_hints(SemanticGovernorStore.append_history)
    assert "expected_generation" in hist
    assert "expected_head_cid" in hist
    assert "entry_cid" in hist
    assert "operation_id" in hist
