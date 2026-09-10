"""Fail-closed vectors for logical graph history and world-root manifests."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

from ipfs_datasets_py.logic.software_contracts.content import cid_for_bytes
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_graph import (
    LOGICAL_CYCLE_REQUIRED_KINDS,
    ProgramGraphEdge,
    ProgramGraphNode,
    ProgramGraphSnapshot,
    assemble_program_graph_snapshot,
    delta_between_snapshots,
    directed_logical_cycles,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    CanonicalProgramGraphIdentity,
    ExecutionTraceIdentity,
    ProgramEventIdentity,
    ProgramGraphSnapshotIdentity,
    TransitionIdentity,
    TransitionKind,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_transition import (
    ProgramTransitionAdmission,
    ProgramTransitionCandidate,
    ProgramTransitionError,
    ProgramTransitionObservation,
    ProgramTransitionPrediction,
    ProgramTransitionQuery,
    ProgramTransitionReceipt,
    TransitionModelProfile,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
)
from ipfs_kit_py.semantic_world_store.graph_history import (
    PROGRAM_GRAPH_HISTORY_INTERFACE,
    GraphHistoryAdmissionError,
    GraphHistoryConflictError,
    GraphHistoryIntegrityError,
    GraphHistoryKind,
    LogicalProgramGraphStore,
    ProgramGraphHistory,
    ProgramTransitionLog,
    SemanticWorldSnapshot,
    append_program_graph_snapshot,
    append_transition_receipt,
)
from ipfs_kit_py.semantic_world_store.world_roots import (
    SEMANTIC_WORLD_ROOT_INTERFACE,
    SemanticWorldRootManifest,
    SemanticWorldRootStore,
    build_world_root_manifest,
)


def _cid(label: str) -> str:
    return cid_for_bytes(label.encode("utf-8"))


def _source() -> str:
    return cid_for_bytes(b"def ping():\n    return pong()\n")


def _node(kind: str, name: str, **overrides: Any) -> ProgramGraphNode:
    fields: dict[str, Any] = {
        "node_kind": kind,
        "language": "python",
        "logical_name": name,
        "source_cid": _source(),
        "declaration_cid": _cid(f"decl:{name}"),
        "environment_binding_cid": _cid("env-v1"),
        "subject_cid": None,
        "record_cid": None,
        "unavailable_dimensions": (),
        "metadata": {},
    }
    fields.update(overrides)
    return ProgramGraphNode(**fields)


def _edge(
    kind: str,
    source: ProgramGraphNode,
    target: ProgramGraphNode,
    **overrides: Any,
) -> ProgramGraphEdge:
    fields: dict[str, Any] = {
        "edge_kind": kind,
        "source_node_cid": source.program_graph_node_cid,
        "target_node_cid": target.program_graph_node_cid,
        "language": "python",
        "environment_binding_cid": _cid("env-v1"),
        "resolution_status": "definite",
        "logical_cycle": kind in LOGICAL_CYCLE_REQUIRED_KINDS,
        "unavailable_dimensions": (),
        "metadata": {},
    }
    fields.update(overrides)
    return ProgramGraphEdge(**fields)


@pytest.fixture()
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "semantic-world-history"


@pytest.fixture()
def coordination(store_dir: Path) -> DurableCoordinationStore:
    root = DurableCoordinationStore(store_dir)
    yield root
    root.close()


@pytest.fixture()
def history(coordination: DurableCoordinationStore) -> ProgramGraphHistory:
    store = ProgramGraphHistory(coordination)
    yield store
    store.close()


def _leaf(history: ProgramGraphHistory, kind: str, label: str) -> str:
    return history.world_snapshots.put_leaf_subroot(kind, {"label": label}).cid


def _cyclic_members(
    extra_nodes: list[ProgramGraphNode] | None = None,
) -> tuple[list[ProgramGraphNode], list[ProgramGraphEdge]]:
    ping = _node("function", "pkg.mod.ping")
    pong = _node("function", "pkg.mod.pong")
    module = _node("module", "pkg.mod")
    nodes = [module, ping, pong]
    if extra_nodes:
        nodes.extend(extra_nodes)
    edges = [
        _edge("declares", module, ping),
        _edge("declares", module, pong),
        _edge("mutual_recursion", ping, pong, logical_cycle=True),
        _edge("mutual_recursion", pong, ping, logical_cycle=True),
        _edge("cfg_next", ping, ping, logical_cycle=True),
    ]
    return nodes, edges


def _append_graph(
    history: ProgramGraphHistory,
    *,
    extra_nodes: list[ProgramGraphNode] | None = None,
    previous_snapshot: ProgramGraphSnapshot | None = None,
    operation_id: str | None = None,
    env: str | None = None,
    sealed: str | None = None,
) -> tuple[ProgramGraphSnapshot, Any]:
    nodes, edges = _cyclic_members(extra_nodes)
    env_cid = env or _leaf(history, "environment_binding_set", "bindings")
    sealed_cid = sealed or _leaf(history, "sealed_binding", "sealed")
    result = append_program_graph_snapshot(
        history,
        nodes=nodes,
        edges=edges,
        previous_snapshot=previous_snapshot,
        environment_binding_set_cid=env_cid,
        sealed_binding_cid=sealed_cid,
        operation_id=operation_id,
    )
    return history.graphs.get_snapshot(result.cid), result


def _snapshot_identity(snapshot: ProgramGraphSnapshot) -> ProgramGraphSnapshotIdentity:
    return ProgramGraphSnapshotIdentity.from_dict(snapshot.to_identity_record())


def _head_for_receipt(history: ProgramGraphHistory, receipt_cid: str) -> str:
    return history.transitions.head_for_receipt(receipt_cid).log_head_cid


def _make_query(
    *,
    subject: str,
    source: str,
    env: str,
    policy: str,
    state: str,
    selected: str,
) -> ProgramTransitionQuery:
    return ProgramTransitionQuery(
        query_family="next_call",
        language="python",
        subject_cid=subject,
        current_source_cid=source,
        environment_binding_cid=env,
        policy_cid=policy,
        current_state_cid=state,
        allowed_symbol_cids=(selected,),
    )


# ---------------------------------------------------------------------------
# Cold import / interfaces
# ---------------------------------------------------------------------------


def test_cold_import_of_declared_modules() -> None:
    for name in list(sys.modules):
        if "semantic_world_store" in name:
            del sys.modules[name]
    history_mod = importlib.import_module(
        "ipfs_kit_py.semantic_world_store.graph_history"
    )
    roots_mod = importlib.import_module(
        "ipfs_kit_py.semantic_world_store.world_roots"
    )
    assert history_mod.PROGRAM_GRAPH_HISTORY_INTERFACE == "ProgramGraphHistory@1"
    assert history_mod.LogicalProgramGraphStore.__name__ == "LogicalProgramGraphStore"
    assert history_mod.ProgramTransitionLog.__name__ == "ProgramTransitionLog"
    assert history_mod.SemanticWorldSnapshotStore.__name__ == "SemanticWorldSnapshotStore"
    assert roots_mod.SemanticWorldRootManifest.__name__ == "SemanticWorldRootManifest"
    assert roots_mod.SEMANTIC_WORLD_ROOT_INTERFACE == "SemanticWorldRoot@1"
    assert callable(history_mod.append_program_graph_snapshot)
    assert callable(history_mod.append_transition_receipt)
    assert callable(roots_mod.build_world_root_manifest)


def test_module_interfaces_are_versioned() -> None:
    assert PROGRAM_GRAPH_HISTORY_INTERFACE == "ProgramGraphHistory@1"
    assert SEMANTIC_WORLD_ROOT_INTERFACE == "SemanticWorldRoot@1"
    assert ProgramGraphHistory.INTERFACE == "ProgramGraphHistory@1"
    assert LogicalProgramGraphStore.INTERFACE == "ProgramGraphHistory@1"
    assert ProgramTransitionLog.INTERFACE == "ProgramGraphHistory@1"
    assert SemanticWorldRootManifest.INTERFACE == "SemanticWorldRootManifest@1"
    assert SemanticWorldRootStore.INTERFACE == "SemanticWorldRoot@1"


def test_root_store_does_not_expose_current_pointer_cas() -> None:
    assert not hasattr(SemanticWorldRootStore, "compare_and_swap_world_root")
    assert not hasattr(SemanticWorldRootManifest, "compare_and_swap_world_root")


# ---------------------------------------------------------------------------
# Store-before-reference / missing / corrupt / idempotency
# ---------------------------------------------------------------------------


def test_snapshot_without_stored_nodes_fails_closed(
    history: ProgramGraphHistory,
) -> None:
    ping = _node("function", "pkg.mod.ping")
    pong = _node("function", "pkg.mod.pong")
    edge = _edge("mutual_recursion", ping, pong, logical_cycle=True)
    env = _leaf(history, "environment_binding_set", "bindings")
    sealed = _leaf(history, "sealed_binding", "sealed")
    snapshot = assemble_program_graph_snapshot(
        nodes=[ping, pong],
        edges=[edge],
        environment_binding_set_cid=env,
        sealed_binding_cid=sealed,
    )
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        history.graphs.put_snapshot(snapshot)


def test_edge_without_stored_nodes_fails_closed(history: ProgramGraphHistory) -> None:
    ping = _node("function", "pkg.mod.ping")
    pong = _node("function", "pkg.mod.pong")
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        history.graphs.put_edge(_edge("mutual_recursion", ping, pong, logical_cycle=True))


def test_receipt_without_stored_admission_fails_closed(
    history: ProgramGraphHistory,
) -> None:
    subject = _leaf(history, "subject", "fn")
    state = _leaf(history, "state", "s0")
    source = _leaf(history, "source", "src")
    env = _leaf(history, "env", "env")
    policy = _leaf(history, "policy", "pol")
    selected = _leaf(history, "symbol", "callee")
    query = _make_query(
        subject=subject, source=source, env=env, policy=policy, state=state, selected=selected
    )
    history.transitions.put_query(query)
    ghost_admission = ProgramTransitionAdmission(
        query_cid=query.query_cid,
        policy_cid=policy,
        current_subject_cid=subject,
        current_environment_binding_cid=env,
        verdict="abstain",
    )
    receipt = ProgramTransitionReceipt(
        query_cid=query.query_cid,
        admission_cid=ghost_admission.admission_cid,
        verdict="abstain",
    )
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        append_transition_receipt(history, receipt)


def test_missing_reference_on_world_root_fails_closed(
    history: ProgramGraphHistory,
) -> None:
    snapshot, _result = _append_graph(history)
    identity = _snapshot_identity(snapshot)
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        build_world_root_manifest(
            history,
            generation=1,
            domain_state_cid=_cid("missing-domain"),
            canonical_program_graph_cid=snapshot.canonical_program_graph_cid,
            program_graph_snapshot_cid=identity.program_graph_snapshot_cid,
            semantic_object_index_cid=_leaf(history, "semantic_object_index", "idx"),
            environment_binding_set_cid=snapshot.environment_binding_set_cid,
            policy_cid=_leaf(history, "policy", "policy"),
            analysis_limitation_index_cid=_leaf(history, "limits", "limits"),
        )


def test_corrupt_present_block_fails_closed(history: ProgramGraphHistory) -> None:
    snapshot, result = _append_graph(history)
    path = history.store._block_path(result.storage_cid)
    path.write_bytes(b'{"schema":"tampered","kind":"graph_snapshot","payload":{}}')
    with pytest.raises(GraphHistoryIntegrityError):
        history.graphs.get_snapshot(snapshot.program_graph_snapshot_cid)


def test_append_snapshot_is_idempotent(history: ProgramGraphHistory) -> None:
    snapshot, first = _append_graph(history, operation_id="op-snap-1")
    second = append_program_graph_snapshot(
        history,
        snapshot,
        nodes=list(history.graphs.load_snapshot_nodes(snapshot)),
        edges=list(history.graphs.load_snapshot_edges(snapshot)),
        operation_id="op-snap-1",
    )
    assert first.cid == second.cid
    assert second.created is False
    assert second.reason_code == "unchanged"


def test_operation_id_conflict_fails_closed(history: ProgramGraphHistory) -> None:
    env = _leaf(history, "environment_binding_set", "bindings")
    sealed = _leaf(history, "sealed_binding", "sealed")
    _append_graph(history, operation_id="op-shared", env=env, sealed=sealed)
    extra = _node("function", "pkg.mod.other")
    with pytest.raises(GraphHistoryConflictError):
        _append_graph(
            history,
            extra_nodes=[extra],
            operation_id="op-shared",
            env=env,
            sealed=sealed,
        )


# ---------------------------------------------------------------------------
# Logical cycles remain queryable; physical IPLD stays acyclic
# ---------------------------------------------------------------------------


def test_mutual_recursion_and_state_cycles_are_queryable(
    history: ProgramGraphHistory,
) -> None:
    snapshot, _result = _append_graph(history)
    cycles = history.graphs.query_logical_cycles(snapshot)
    assert cycles
    edges = history.graphs.load_snapshot_edges(snapshot)
    names = {
        (
            history.graphs.get_node(edge.source_node_cid).logical_name,
            history.graphs.get_node(edge.target_node_cid).logical_name,
        )
        for edge in edges
        if edge.logical_cycle
    }
    assert ("pkg.mod.ping", "pkg.mod.pong") in names
    assert ("pkg.mod.pong", "pkg.mod.ping") in names
    assert ("pkg.mod.ping", "pkg.mod.ping") in names
    assert directed_logical_cycles(edges) == cycles
    history.graphs.assert_physical_ipld_acyclic()
    for edge in edges:
        assert edge.program_graph_edge_cid != edge.source_node_cid
        assert edge.program_graph_edge_cid != edge.target_node_cid


def test_snapshot_node_and_edge_sets_are_deterministically_ordered(
    history: ProgramGraphHistory,
) -> None:
    snapshot, _result = _append_graph(history)
    assert list(snapshot.node_cids) == sorted(snapshot.node_cids)
    assert list(snapshot.edge_cids) == sorted(snapshot.edge_cids)
    canonical = CanonicalProgramGraphIdentity.from_dict(
        dict(
            history.blocks.get_verified_payload(
                snapshot.canonical_program_graph_cid,
                expected_kind=GraphHistoryKind.CANONICAL_PROGRAM_GRAPH,
            )["payload"]
        )
    )
    assert list(canonical.node_cids) == list(snapshot.node_cids)
    assert list(canonical.edge_cids) == list(snapshot.edge_cids)


# ---------------------------------------------------------------------------
# Repeated-state distinct history
# ---------------------------------------------------------------------------


def test_repeated_states_preserve_distinct_event_history(
    history: ProgramGraphHistory,
) -> None:
    state = _leaf(history, "raw_execution_state", "loop-state")
    first = ProgramEventIdentity(
        event_kind="call",
        observation_status="observed",
        subject_cid=state,
        payload={"step": "enter"},
    )
    second = ProgramEventIdentity(
        event_kind="call",
        observation_status="observed",
        subject_cid=state,
        payload={"step": "again"},
        predecessor_event_cid=first.program_event_cid,
    )
    history.transitions.put_event(first)
    history.transitions.put_event(second)
    short = ExecutionTraceIdentity(
        event_cids=(first.program_event_cid, second.program_event_cid),
        raw_execution_state_cids=(state, state),
    )
    long = ExecutionTraceIdentity(
        event_cids=(
            first.program_event_cid,
            second.program_event_cid,
            first.program_event_cid,
        ),
        raw_execution_state_cids=(state, state, state),
    )
    history.transitions.put_trace(short)
    history.transitions.put_trace(long)
    assert short.execution_trace_cid != long.execution_trace_cid
    loaded_long = history.transitions.get_trace(long.execution_trace_cid)
    assert loaded_long.event_cids == long.event_cids
    assert loaded_long.event_cids[0] == loaded_long.event_cids[2]
    assert loaded_long.raw_execution_state_cids == (state, state, state)
    assert history.transitions.get_event(first.program_event_cid).subject_cid == state
    assert history.transitions.get_event(second.program_event_cid).subject_cid == state
    assert first.program_event_cid != second.program_event_cid


# ---------------------------------------------------------------------------
# Predictions distinguishable from admitted observations
# ---------------------------------------------------------------------------


def test_predictions_are_distinguishable_from_admitted_observations(
    history: ProgramGraphHistory,
) -> None:
    subject = _leaf(history, "subject", "fn")
    state = _leaf(history, "state", "s0")
    source = _leaf(history, "source", "src")
    env = _leaf(history, "env", "env")
    policy = _leaf(history, "policy", "pol")
    selected = _leaf(history, "symbol", "callee")
    observed = _leaf(history, "observed-state", "s1")
    query = _make_query(
        subject=subject, source=source, env=env, policy=policy, state=state, selected=selected
    )
    history.transitions.put_query(query)
    profile = TransitionModelProfile(
        profile_name="call-target-a",
        specialist_family="call_target",
        model_cid=_cid("model-a"),
        tokenizer_cid=_cid("tok-a"),
        preprocessing_profile_cid=_cid("pre-a"),
    )
    history.transitions.put_model_profile(profile)
    candidate = ProgramTransitionCandidate(
        query_cid=query.query_cid,
        candidate_kind="call_target",
        selected_cid=selected,
        query_family="next_call",
        current_subject_cid=subject,
        current_source_cid=source,
        current_environment_binding_cid=env,
        current_state_cid=state,
    )
    history.transitions.put_candidate(candidate)
    prediction = ProgramTransitionPrediction(
        query_cid=query.query_cid,
        subject_cid=subject,
        model_profile_cid=profile.model_profile_cid,
        candidate_cids=(candidate.candidate_cid,),
        environment_binding_cid=env,
        policy_cid=policy,
    )
    observation = ProgramTransitionObservation(
        query_cid=query.query_cid,
        subject_cid=subject,
        observed_cid=observed,
        observation_status="observed",
        environment_binding_cid=env,
        query_family="next_call",
        policy_cid=policy,
    )
    admission = ProgramTransitionAdmission(
        query_cid=query.query_cid,
        policy_cid=policy,
        current_subject_cid=subject,
        current_environment_binding_cid=env,
        verdict="admitted",
        prediction_cid=prediction.prediction_cid,
        observation_cid=observation.observation_cid,
    )
    receipt = ProgramTransitionReceipt(
        query_cid=query.query_cid,
        admission_cid=admission.admission_cid,
        verdict="admitted",
        prediction_cid=prediction.prediction_cid,
        observation_cid=observation.observation_cid,
        may_influence_planning=True,
    )
    first = append_transition_receipt(
        history,
        receipt,
        prediction=prediction,
        observation=observation,
        admission=admission,
        operation_id="op-receipt-1",
    )
    loaded_pred = history.transitions.get_prediction(prediction.prediction_cid)
    loaded_obs = history.transitions.get_observation(observation.observation_cid)
    assert loaded_pred.proposal_only is True
    assert loaded_obs.proposal_only is False
    assert loaded_pred.SCHEMA != loaded_obs.SCHEMA
    assert loaded_pred.prediction_cid != loaded_obs.observation_cid
    with pytest.raises(GraphHistoryIntegrityError, match="wrong history kind"):
        history.transitions.get_prediction(observation.observation_cid)
    with pytest.raises(GraphHistoryIntegrityError, match="wrong history kind"):
        history.transitions.get_observation(prediction.prediction_cid)
    with pytest.raises(ProgramTransitionError):
        ProgramTransitionObservation.from_dict(prediction.to_dict())
    pred_identity = TransitionIdentity.from_dict(prediction.to_identity_record())
    obs_identity = TransitionIdentity.from_dict(observation.to_identity_record())
    assert pred_identity.transition_kind == TransitionKind.PREDICTION.value
    assert pred_identity.proposal_only is True
    assert obs_identity.transition_kind == TransitionKind.OBSERVATION.value
    assert obs_identity.proposal_only is False
    stored_receipt = history.transitions.get_receipt(first.cid)
    assert stored_receipt.prediction_cid == prediction.prediction_cid
    assert stored_receipt.observation_cid == observation.observation_cid
    assert stored_receipt.may_influence_planning is True

    abstain_admission = ProgramTransitionAdmission(
        query_cid=query.query_cid,
        policy_cid=policy,
        current_subject_cid=subject,
        current_environment_binding_cid=env,
        verdict="abstain",
        prediction_cid=prediction.prediction_cid,
    )
    proposal_receipt = ProgramTransitionReceipt(
        query_cid=query.query_cid,
        admission_cid=abstain_admission.admission_cid,
        verdict="abstain",
        prediction_cid=prediction.prediction_cid,
        may_influence_planning=False,
    )
    first_head = _head_for_receipt(history, first.cid)
    second = append_transition_receipt(
        history,
        proposal_receipt,
        admission=abstain_admission,
        previous_head_cid=first_head,
        operation_id="op-receipt-2",
    )
    ordered = history.transitions.iter_receipt_history(_head_for_receipt(history, second.cid))
    assert [item.receipt_cid for item in ordered] == [first.cid, second.cid]
    assert ordered[0].observation_cid is not None
    assert ordered[1].observation_cid is None
    assert ordered[1].prediction_cid == prediction.prediction_cid


def test_append_receipt_is_idempotent(history: ProgramGraphHistory) -> None:
    subject = _leaf(history, "subject", "fn")
    state = _leaf(history, "state", "s0")
    source = _leaf(history, "source", "src")
    env = _leaf(history, "env", "env")
    policy = _leaf(history, "policy", "pol")
    selected = _leaf(history, "symbol", "callee")
    query = _make_query(
        subject=subject, source=source, env=env, policy=policy, state=state, selected=selected
    )
    history.transitions.put_query(query)
    admission = ProgramTransitionAdmission(
        query_cid=query.query_cid,
        policy_cid=policy,
        current_subject_cid=subject,
        current_environment_binding_cid=env,
        verdict="abstain",
    )
    receipt = ProgramTransitionReceipt(
        query_cid=query.query_cid,
        admission_cid=admission.admission_cid,
        verdict="abstain",
    )
    first = append_transition_receipt(
        history, receipt, admission=admission, operation_id="op-receipt-idem"
    )
    second = append_transition_receipt(
        history, receipt, operation_id="op-receipt-idem"
    )
    assert first.cid == second.cid
    assert second.reason_code == "unchanged"
    assert second.created is False


# ---------------------------------------------------------------------------
# Delta unchanged-subroot and generation-bearing roots
# ---------------------------------------------------------------------------


def test_delta_retains_unchanged_subroots(history: ProgramGraphHistory) -> None:
    env = _leaf(history, "environment_binding_set", "bindings")
    sealed = _leaf(history, "sealed_binding", "sealed")
    first, _ = _append_graph(history, env=env, sealed=sealed)
    helper = _node("function", "pkg.mod.helper")
    second, _ = _append_graph(
        history,
        extra_nodes=[helper],
        previous_snapshot=first,
        env=env,
        sealed=sealed,
    )
    delta = delta_between_snapshots(first, second)
    assert helper.program_graph_node_cid in delta.added_node_cids
    retained = set(delta.retained_subroot_cids)
    assert set(first.node_cids) <= retained
    assert helper.program_graph_node_cid not in retained
    stored = history.graphs.get_delta(delta.program_graph_delta_cid)
    assert stored.retained_subroot_cids == delta.retained_subroot_cids
    assert stored.previous_snapshot_cid == first.program_graph_snapshot_cid


def test_world_root_binds_every_referenced_subroot_deterministically(
    history: ProgramGraphHistory,
) -> None:
    env = _leaf(history, "environment_binding_set", "bindings")
    sealed = _leaf(history, "sealed_binding", "sealed")
    snapshot, _ = _append_graph(history, env=env, sealed=sealed)
    identity = _snapshot_identity(snapshot)
    domain = _leaf(history, "domain_state", "domain")
    objects = _leaf(history, "semantic_object_index", "objects")
    policy = _leaf(history, "policy", "policy")
    limits = _leaf(history, "limits", "limits")
    world = SemanticWorldSnapshot(
        program_graph_snapshot_cid=snapshot.program_graph_snapshot_cid,
        program_graph_snapshot_identity_cid=identity.program_graph_snapshot_cid,
        canonical_program_graph_cid=snapshot.canonical_program_graph_cid,
        domain_state_cid=domain,
        semantic_object_index_cid=objects,
        environment_binding_set_cid=env,
        policy_cid=policy,
        analysis_limitation_index_cid=limits,
    )
    history.world_snapshots.put_snapshot(world)
    first = build_world_root_manifest(
        history,
        generation=1,
        domain_state_cid=domain,
        canonical_program_graph_cid=snapshot.canonical_program_graph_cid,
        program_graph_snapshot_cid=identity.program_graph_snapshot_cid,
        semantic_object_index_cid=objects,
        environment_binding_set_cid=env,
        policy_cid=policy,
        analysis_limitation_index_cid=limits,
        world_snapshot_cid=world.world_snapshot_cid,
        extra_bindings=(("sealed_binding_cid", sealed),),
        operation_id="op-root-1",
    )
    again = build_world_root_manifest(
        history,
        generation=1,
        domain_state_cid=domain,
        canonical_program_graph_cid=snapshot.canonical_program_graph_cid,
        program_graph_snapshot_cid=identity.program_graph_snapshot_cid,
        semantic_object_index_cid=objects,
        environment_binding_set_cid=env,
        policy_cid=policy,
        analysis_limitation_index_cid=limits,
        world_snapshot_cid=world.world_snapshot_cid,
        extra_bindings=(("sealed_binding_cid", sealed),),
        operation_id="op-root-1",
    )
    assert first.world_root_manifest_cid == again.world_root_manifest_cid
    assert first.semantic_world_root_cid == first.identity.semantic_world_root_cid
    bound = first.binding_map()
    for name in (
        "domain_state_cid",
        "canonical_program_graph_cid",
        "program_graph_snapshot_cid",
        "semantic_object_index_cid",
        "environment_binding_set_cid",
        "policy_cid",
        "analysis_limitation_index_cid",
        "world_snapshot_cid",
        "sealed_binding_cid",
    ):
        assert name in bound
        assert bound[name]
    assert list(first.subroot_bindings) == sorted(first.subroot_bindings)
    assert set(first.referenced_subroot_cids()) == {cid for _name, cid in first.subroot_bindings}
    loaded = SemanticWorldRootStore(history.blocks).get_manifest(first.world_root_manifest_cid)
    assert loaded.world_root_manifest_cid == first.world_root_manifest_cid
    assert "generation" not in first.identity.to_dict()

    helper = _node("function", "pkg.mod.helper")
    second_snapshot, _ = _append_graph(
        history, extra_nodes=[helper], previous_snapshot=snapshot, env=env, sealed=sealed
    )
    second_identity = _snapshot_identity(second_snapshot)
    second_world = SemanticWorldSnapshot(
        program_graph_snapshot_cid=second_snapshot.program_graph_snapshot_cid,
        program_graph_snapshot_identity_cid=second_identity.program_graph_snapshot_cid,
        canonical_program_graph_cid=second_snapshot.canonical_program_graph_cid,
        domain_state_cid=domain,
        semantic_object_index_cid=objects,
        environment_binding_set_cid=env,
        policy_cid=policy,
        analysis_limitation_index_cid=limits,
    )
    history.world_snapshots.put_snapshot(second_world)
    successor = build_world_root_manifest(
        history,
        generation=2,
        domain_state_cid=domain,
        canonical_program_graph_cid=second_snapshot.canonical_program_graph_cid,
        program_graph_snapshot_cid=second_identity.program_graph_snapshot_cid,
        semantic_object_index_cid=objects,
        environment_binding_set_cid=env,
        policy_cid=policy,
        analysis_limitation_index_cid=limits,
        world_snapshot_cid=second_world.world_snapshot_cid,
        previous_manifest=first,
        extra_bindings=(("sealed_binding_cid", sealed),),
        operation_id="op-root-2",
    )
    assert successor.generation == 2
    assert successor.previous_manifest_cid == first.world_root_manifest_cid
    assert successor.world_root_manifest_cid != first.world_root_manifest_cid
    unchanged = set(successor.unchanged_subroot_cids)
    assert domain in unchanged
    assert objects in unchanged
    assert env in unchanged
    assert policy in unchanged
    assert limits in unchanged
    assert sealed in unchanged
    assert identity.program_graph_snapshot_cid not in unchanged
    assert snapshot.canonical_program_graph_cid not in unchanged
    same_semantic = build_world_root_manifest(
        history,
        generation=3,
        domain_state_cid=domain,
        canonical_program_graph_cid=second_snapshot.canonical_program_graph_cid,
        program_graph_snapshot_cid=second_identity.program_graph_snapshot_cid,
        semantic_object_index_cid=objects,
        environment_binding_set_cid=env,
        policy_cid=policy,
        analysis_limitation_index_cid=limits,
        world_snapshot_cid=second_world.world_snapshot_cid,
        previous_manifest=successor,
        extra_bindings=(("sealed_binding_cid", sealed),),
        persist=True,
    )
    assert same_semantic.semantic_world_root_cid == successor.semantic_world_root_cid
    assert same_semantic.world_root_manifest_cid != successor.world_root_manifest_cid
    shuffled = SemanticWorldRootManifest.from_identity(
        successor.identity,
        generation=2,
        world_snapshot_cid=second_world.world_snapshot_cid,
        previous_manifest_cid=first.world_root_manifest_cid,
        unchanged_subroot_cids=successor.unchanged_subroot_cids,
        extra_bindings=(("sealed_binding_cid", sealed),),
    )
    assert shuffled.world_root_manifest_cid == successor.world_root_manifest_cid
    assert shuffled.subroot_bindings == successor.subroot_bindings
