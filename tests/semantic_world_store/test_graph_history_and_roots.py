"""Fail-closed vectors for logical graph history and world-root manifests."""

from __future__ import annotations

import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from ipfs_datasets_py.logic.software_contracts.content import cid_for_bytes as datasets_cid_for_bytes
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_graph import (
    ProgramGraphEdge,
    ProgramGraphNode,
    assemble_program_graph_snapshot,
    assert_physical_dag_acyclic,
    delta_between_snapshots,
    directed_logical_cycles,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    EventKind,
    ExecutionTraceIdentity,
    ObservationStatus,
    ProgramEventIdentity,
    SemanticWorldRootIdentity,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_transition import (
    AdmissionVerdict,
    ProgramTransitionObservation,
    QueryFamily,
    SpecialistFamily,
    TransitionModelProfile,
    admit_program_transition,
    decode_transition_observation,
    issue_transition_receipt,
    propose_program_transition,
    select_and_parameterize_candidate,
    ProgramTransitionQuery,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
    cid_for_bytes,
)
from ipfs_kit_py.semantic_world_store.graph_history import (
    GRAPH_HISTORY_ARTIFACT_INTERFACE,
    GRAPH_HISTORY_ARTIFACT_SCHEMA,
    OBSERVATION_HISTORY_KIND,
    PREDICTION_HISTORY_KIND,
    PROGRAM_GRAPH_HISTORY_INTERFACE,
    GraphHistoryAdmissionError,
    GraphHistoryConflictError,
    GraphHistoryIntegrityError,
    GraphHistoryNotFound,
    LogicalProgramGraphStore,
    ProgramGraphHistory,
    SemanticWorldHistoryKind,
    append_program_graph_snapshot,
    append_transition_receipt,
    cid_for_graph_history_artifact,
    seal_graph_history_artifact,
)
from ipfs_kit_py.semantic_world_store.world_roots import (
    SEMANTIC_WORLD_ROOT_INTERFACE,
    SemanticWorldRootManifest,
    SemanticWorldSnapshotStore,
    WorldRootAdmissionError,
    build_world_root_manifest,
)


def _cid(label: str) -> str:
    return cid_for_bytes(label.encode("utf-8"), "raw")


def _source() -> str:
    return cid_for_bytes(b"def ping():\n    return pong()\n", "raw")


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
        "logical_cycle": kind in {"mutual_recursion", "cyclic_import"},
        "unavailable_dimensions": (),
        "metadata": {},
    }
    fields.update(overrides)
    return ProgramGraphEdge(**fields)


def _cyclic_graph() -> dict[str, Any]:
    module = _node("module", "pkg.mod")
    ping = _node("function", "pkg.mod.ping")
    pong = _node("function", "pkg.mod.pong")
    edges = [
        _edge("declares", module, ping),
        _edge("declares", module, pong),
        _edge("mutual_recursion", ping, pong, logical_cycle=True),
        _edge("mutual_recursion", pong, ping, logical_cycle=True),
        _edge("cfg_next", ping, ping, logical_cycle=True),
    ]
    snapshot = assemble_program_graph_snapshot(
        nodes=[module, ping, pong],
        edges=edges,
        environment_binding_set_cid=_cid("bindings"),
        sealed_binding_cid=_cid("sealed"),
    )
    return {
        "module": module,
        "ping": ping,
        "pong": pong,
        "edges": edges,
        "snapshot": snapshot,
    }


def _query(**overrides: Any) -> ProgramTransitionQuery:
    fields: dict[str, Any] = {
        "query_family": QueryFamily.NEXT_CALL,
        "language": "python",
        "subject_cid": _cid("state-current"),
        "current_source_cid": _cid("source-current"),
        "current_state_cid": _cid("state-current"),
        "environment_binding_cid": _cid("env-v1"),
        "policy_cid": _cid("policy-v1"),
        "allowed_symbol_cids": [_cid("sym-b"), _cid("sym-a")],
        "evidence_cids": [_cid("ev-1")],
        "unavailable_dimensions": ("native_stack",),
    }
    fields.update(overrides)
    return ProgramTransitionQuery(**fields)


def _profile() -> TransitionModelProfile:
    return TransitionModelProfile(
        profile_name="next-call-specialist-v1",
        specialist_family=SpecialistFamily.CALL_TARGET,
        model_cid=_cid("model-v1"),
        tokenizer_cid=_cid("tok-v1"),
        preprocessing_profile_cid=_cid("prep-v1"),
    )


def _event(subject: str, predecessor: str | None = None, kind: str = "call") -> ProgramEventIdentity:
    return ProgramEventIdentity(
        event_kind=EventKind.CALL if kind == "call" else kind,
        observation_status=ObservationStatus.OBSERVED,
        subject_cid=subject,
        payload={"state": subject},
        predecessor_event_cid=predecessor,
    )


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


@pytest.fixture()
def roots(history: ProgramGraphHistory) -> SemanticWorldSnapshotStore:
    store = SemanticWorldSnapshotStore(history)
    yield store
    store.close()


def _put_identity_leaves(roots: SemanticWorldSnapshotStore, identity: SemanticWorldRootIdentity) -> None:
    for role, field in (
        ("domain_state", "domain_state_cid"),
        ("semantic_object_index", "semantic_object_index_cid"),
        ("environment_binding_set", "environment_binding_set_cid"),
        ("policy", "policy_cid"),
        ("analysis_limitation_index", "analysis_limitation_index_cid"),
    ):
        cid = getattr(identity, field)
        roots.put_immutable_subroot(
            {"role": role, "subroot_cid": cid, "label": role},
            operation_id=f"subroot-{role}",
        )


# ---------------------------------------------------------------------------
# Cold import / interfaces / no second CID engine
# ---------------------------------------------------------------------------


def test_cold_import_of_declared_modules() -> None:
    for name in list(sys.modules):
        if "semantic_world_store" in name:
            del sys.modules[name]
    history_mod = importlib.import_module("ipfs_kit_py.semantic_world_store.graph_history")
    roots_mod = importlib.import_module("ipfs_kit_py.semantic_world_store.world_roots")
    assert history_mod.PROGRAM_GRAPH_HISTORY_INTERFACE == "ProgramGraphHistory@1"
    assert history_mod.LogicalProgramGraphStore.__name__ == "LogicalProgramGraphStore"
    assert history_mod.ProgramTransitionLog.__name__ == "ProgramTransitionLog"
    assert roots_mod.SEMANTIC_WORLD_ROOT_INTERFACE == "SemanticWorldRoot@1"
    assert roots_mod.SemanticWorldRootManifest.__name__ == "SemanticWorldRootManifest"
    assert roots_mod.SemanticWorldSnapshotStore.__name__ == "SemanticWorldSnapshotStore"
    assert callable(history_mod.append_program_graph_snapshot)
    assert callable(history_mod.append_transition_receipt)
    assert callable(roots_mod.build_world_root_manifest)


def test_module_interfaces_are_versioned() -> None:
    assert PROGRAM_GRAPH_HISTORY_INTERFACE == "ProgramGraphHistory@1"
    assert SEMANTIC_WORLD_ROOT_INTERFACE == "SemanticWorldRoot@1"
    assert GRAPH_HISTORY_ARTIFACT_INTERFACE == "SemanticWorldGraphHistoryArtifact@1"
    assert GRAPH_HISTORY_ARTIFACT_SCHEMA.endswith("@1")
    assert ProgramGraphHistory.INTERFACE == "ProgramGraphHistory@1"
    assert LogicalProgramGraphStore.INTERFACE == "ProgramGraphHistory@1"
    assert SemanticWorldSnapshotStore.INTERFACE == "SemanticWorldRoot@1"
    assert SemanticWorldRootManifest.INTERFACE == "SemanticWorldRoot@1"
    assert PREDICTION_HISTORY_KIND != OBSERVATION_HISTORY_KIND


def test_no_second_cid_or_storage_engine_or_current_root_cas() -> None:
    history_source = Path(inspect.getsourcefile(ProgramGraphHistory)).read_text(encoding="utf-8")
    roots_source = Path(inspect.getsourcefile(SemanticWorldSnapshotStore)).read_text(
        encoding="utf-8"
    )
    for source in (history_source, roots_source):
        assert "from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import" in source
        assert "DurableCoordinationStore" in source
        assert "def _varint" not in source
        assert "base64.b32encode" not in source
        assert "multihash.digest" not in source
        assert "hashlib.sha256" not in source
        assert "compare_and_swap" not in source
        assert "compare_and_swap_world_root" not in source
    assert "cid_for_artifact" in history_source
    assert "cid_for_bytes" in history_source
    assert "sqlite3.connect" in history_source
    assert "semantic_world_history_index.sqlite3" in history_source
    assert "CREATE TABLE IF NOT EXISTS artifacts" not in history_source
    assert "never publishes a mutable current pointer" in roots_source


def test_store_composes_injected_coordination_engine(
    coordination: DurableCoordinationStore,
    history: ProgramGraphHistory,
) -> None:
    assert history.store is coordination
    ping = _node("function", "pkg.mod.ping")
    result = history.graphs.put_node(ping)
    assert coordination.has(result.storage_cid)
    sealed_path = coordination._block_path(result.storage_cid)
    raw = json.loads(sealed_path.read_text(encoding="utf-8"))
    assert raw["schema"] == GRAPH_HISTORY_ARTIFACT_SCHEMA
    assert raw["kind"] == SemanticWorldHistoryKind.PROGRAM_GRAPH_NODE.value
    assert cid_for_artifact(raw) == result.storage_cid
    assert result.cid == ping.program_graph_node_cid


# ---------------------------------------------------------------------------
# Store-before-reference, cycles, traces
# ---------------------------------------------------------------------------


def test_store_before_reference_rejects_edge_without_nodes(
    history: ProgramGraphHistory,
) -> None:
    ping = _node("function", "pkg.mod.ping")
    pong = _node("function", "pkg.mod.pong")
    edge = _edge("calls", ping, pong)
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        history.graphs.put_edge(edge)
    history.graphs.put_node(ping)
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        history.graphs.put_edge(edge)
    history.graphs.put_node(pong)
    stored = history.graphs.put_edge(edge)
    assert stored.cid == edge.program_graph_edge_cid
    loaded = history.graphs.get_verified_edge(stored.cid)
    assert loaded.source_node_cid == ping.program_graph_node_cid


def test_snapshot_requires_stored_nodes_and_edges(history: ProgramGraphHistory) -> None:
    graph = _cyclic_graph()
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        append_program_graph_snapshot(history, graph["snapshot"])
    result = append_program_graph_snapshot(
        history,
        graph["snapshot"],
        nodes=[graph["module"], graph["ping"], graph["pong"]],
        edges=graph["edges"],
        operation_id="snap-1",
    )
    assert result.cid == graph["snapshot"].program_graph_snapshot_cid
    loaded = history.graphs.get_verified_snapshot(result.cid)
    assert loaded.node_cids == graph["snapshot"].node_cids
    assert loaded.edge_cids == graph["snapshot"].edge_cids


def test_physical_ipld_remains_acyclic_while_logical_cycles_are_queryable(
    history: ProgramGraphHistory,
) -> None:
    graph = _cyclic_graph()
    append_program_graph_snapshot(
        history,
        graph["snapshot"],
        nodes=[graph["module"], graph["ping"], graph["pong"]],
        edges=graph["edges"],
    )
    catalog = history.graphs.load_snapshot_catalog(graph["snapshot"].program_graph_snapshot_cid)
    assert_physical_dag_acyclic(catalog)
    cycles = history.graphs.query_logical_cycles(graph["snapshot"].program_graph_snapshot_cid)
    assert cycles
    edges = [history.graphs.get_verified_edge(cid) for cid in graph["snapshot"].edge_cids]
    logical = [edge for edge in edges if edge.logical_cycle]
    assert len(logical) >= 2
    assert directed_logical_cycles(edges) == cycles
    ping_cid = graph["ping"].program_graph_node_cid
    pong_cid = graph["pong"].program_graph_node_cid
    mutual = [
        edge
        for edge in logical
        if {edge.source_node_cid, edge.target_node_cid} == {ping_cid, pong_cid}
    ]
    assert len(mutual) == 2


def test_repeated_states_preserve_distinct_event_history(
    history: ProgramGraphHistory,
) -> None:
    state = _cid("state-loop")
    first = _event(state)
    second = _event(state, predecessor=first.program_event_cid)
    third = _event(state, predecessor=second.program_event_cid)
    history.graphs.put_event(first)
    history.graphs.put_event(second)
    history.graphs.put_event(third)
    trace_a = ExecutionTraceIdentity(event_cids=[first.program_event_cid, second.program_event_cid])
    trace_b = ExecutionTraceIdentity(
        event_cids=[
            first.program_event_cid,
            second.program_event_cid,
            third.program_event_cid,
        ]
    )
    stored_a = history.graphs.put_trace(trace_a)
    stored_b = history.graphs.put_trace(trace_b)
    assert stored_a.cid != stored_b.cid
    loaded_a = history.graphs.get_verified_trace(stored_a.cid)
    loaded_b = history.graphs.get_verified_trace(stored_b.cid)
    assert list(loaded_a["event_cids"]) == [first.program_event_cid, second.program_event_cid]
    assert list(loaded_b["event_cids"]) == [
        first.program_event_cid,
        second.program_event_cid,
        third.program_event_cid,
    ]
    assert first.subject_cid == second.subject_cid == third.subject_cid
    assert first.program_event_cid != second.program_event_cid != third.program_event_cid


def test_trace_without_events_fails_store_before_reference(
    history: ProgramGraphHistory,
) -> None:
    event = _event(_cid("state"))
    trace = ExecutionTraceIdentity(event_cids=[event.program_event_cid])
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        history.graphs.put_trace(trace)


def test_deterministic_snapshot_ordering(history: ProgramGraphHistory) -> None:
    graph = _cyclic_graph()
    nodes = [graph["pong"], graph["module"], graph["ping"]]
    edges = list(reversed(graph["edges"]))
    first = append_program_graph_snapshot(history, graph["snapshot"], nodes=nodes, edges=edges)
    second = append_program_graph_snapshot(
        history,
        graph["snapshot"],
        nodes=list(reversed(nodes)),
        edges=graph["edges"],
    )
    assert first.cid == second.cid == graph["snapshot"].program_graph_snapshot_cid
    assert second.created is False
    assert second.reason_code == "unchanged"


def test_delta_retains_unchanged_subroots(history: ProgramGraphHistory) -> None:
    graph = _cyclic_graph()
    append_program_graph_snapshot(
        history,
        graph["snapshot"],
        nodes=[graph["module"], graph["ping"], graph["pong"]],
        edges=graph["edges"],
    )
    extra = _node("function", "pkg.mod.helper")
    extra_edge = _edge("declares", graph["module"], extra)
    successor = assemble_program_graph_snapshot(
        nodes=[graph["module"], graph["ping"], graph["pong"], extra],
        edges=[*graph["edges"], extra_edge],
        environment_binding_set_cid=_cid("bindings"),
        sealed_binding_cid=_cid("sealed-2"),
        retained_subroot_cids=[
            graph["module"].program_graph_node_cid,
            graph["ping"].program_graph_node_cid,
            graph["pong"].program_graph_node_cid,
        ],
    )
    append_program_graph_snapshot(
        history,
        successor,
        nodes=[extra],
        edges=[extra_edge],
        operation_id="snap-2",
    )
    delta = delta_between_snapshots(graph["snapshot"], successor)
    assert graph["ping"].program_graph_node_cid in delta.retained_subroot_cids
    assert extra.program_graph_node_cid not in delta.retained_subroot_cids
    stored = history.graphs.put_delta(delta)
    loaded = history.graphs.get_verified_delta(stored.cid)
    assert loaded.retained_subroot_cids == delta.retained_subroot_cids
    assert loaded.added_node_cids == (extra.program_graph_node_cid,)
    assert loaded.previous_snapshot_cid == graph["snapshot"].program_graph_snapshot_cid


def test_delta_without_previous_snapshot_fails(history: ProgramGraphHistory) -> None:
    graph = _cyclic_graph()
    extra = _node("function", "pkg.mod.helper")
    successor = assemble_program_graph_snapshot(
        nodes=[graph["module"], graph["ping"], graph["pong"], extra],
        edges=graph["edges"],
        environment_binding_set_cid=_cid("bindings"),
        sealed_binding_cid=_cid("sealed-2"),
        retained_subroot_cids=[
            graph["module"].program_graph_node_cid,
            graph["ping"].program_graph_node_cid,
            graph["pong"].program_graph_node_cid,
        ],
    )
    delta = delta_between_snapshots(graph["snapshot"], successor)
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        history.graphs.put_delta(delta)


# ---------------------------------------------------------------------------
# Transitions: predictions vs observations
# ---------------------------------------------------------------------------


def _transition_bundle(history: ProgramGraphHistory, *, admit: bool) -> dict[str, Any]:
    query = _query()
    candidate = select_and_parameterize_candidate(
        query, candidate_kind="call_target", selected_cid=query.allowed_symbol_cids[0]
    )
    prediction = propose_program_transition(query, [candidate], model_profile=_profile())
    observation = ProgramTransitionObservation(
        query_cid=query.query_cid,
        subject_cid=query.subject_cid,
        observed_cid=query.allowed_symbol_cids[0],
        observation_status="observed",
        environment_binding_cid=query.environment_binding_cid,
        query_family=query.query_family,
        evidence_cids=[_cid("obs-ev")],
    )
    admission = admit_program_transition(
        query,
        current_subject_cid=query.subject_cid,
        current_source_cid=query.current_source_cid,
        current_environment_binding_cid=query.environment_binding_cid,
        current_state_cid=query.current_state_cid,
        prediction=prediction,
        observation=observation if admit else None,
        validation_evidence_cids=(_cid("obs-ev"),) if admit else (),
    )
    receipt = issue_transition_receipt(
        query,
        admission,
        prediction=prediction,
        observation=observation if admit else None,
    )
    return {
        "query": query,
        "prediction": prediction,
        "observation": observation,
        "admission": admission,
        "receipt": receipt,
    }


def test_predictions_are_distinguishable_from_admitted_observations(
    history: ProgramGraphHistory,
) -> None:
    bundle = _transition_bundle(history, admit=True)
    assert bundle["admission"].verdict == AdmissionVerdict.ADMITTED.value
    assert bundle["receipt"].observation_cid == bundle["observation"].observation_cid
    assert bundle["receipt"].prediction_cid == bundle["prediction"].prediction_cid
    assert bundle["receipt"].may_influence_planning is True
    stored = append_transition_receipt(
        history,
        bundle["receipt"],
        query=bundle["query"],
        prediction=bundle["prediction"],
        observation=bundle["observation"],
        admission=bundle["admission"],
        operation_id="receipt-admitted",
    )
    loaded = history.transitions.get_verified_receipt(stored.cid)
    prediction = history.transitions.get_verified_prediction(loaded.prediction_cid)
    observation = history.transitions.get_verified_observation(loaded.observation_cid)
    assert prediction.prediction_cid != observation.observation_cid
    assert prediction.proposal_only is True
    assert observation.proposal_only is False
    assert history.transitions.prediction_is_distinct_from_observation(
        prediction.prediction_cid, observation.observation_cid
    )
    with pytest.raises(GraphHistoryIntegrityError, match="wrong artifact kind"):
        history.transitions.get_verified_observation(prediction.prediction_cid)
    with pytest.raises(Exception, match="predictions cannot decode as observations"):
        decode_transition_observation(prediction.to_dict())
    prediction_block = history.history.get_verified_artifact(prediction.prediction_cid)
    observation_block = history.history.get_verified_artifact(observation.observation_cid)
    assert prediction_block["kind"] == PREDICTION_HISTORY_KIND
    assert observation_block["kind"] == OBSERVATION_HISTORY_KIND


def test_prediction_only_admission_cannot_self_admit(
    history: ProgramGraphHistory,
) -> None:
    bundle = _transition_bundle(history, admit=False)
    assert bundle["admission"].verdict != AdmissionVerdict.ADMITTED.value
    assert bundle["receipt"].may_influence_planning is False
    stored = append_transition_receipt(
        history,
        bundle["receipt"],
        query=bundle["query"],
        prediction=bundle["prediction"],
        admission=bundle["admission"],
    )
    loaded = history.transitions.get_verified_receipt(stored.cid)
    assert loaded.observation_cid is None
    assert loaded.prediction_cid == bundle["prediction"].prediction_cid
    assert loaded.may_influence_planning is False


def test_receipt_without_query_fails_store_before_reference(
    history: ProgramGraphHistory,
) -> None:
    bundle = _transition_bundle(history, admit=True)
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        append_transition_receipt(history, bundle["receipt"])


# ---------------------------------------------------------------------------
# Corruption, missing refs, idempotency
# ---------------------------------------------------------------------------


def test_corrupt_present_block_fails_closed(history: ProgramGraphHistory) -> None:
    ping = _node("function", "pkg.mod.ping")
    result = history.graphs.put_node(ping, operation_id="op-corrupt")
    path = history.store._block_path(result.storage_cid)
    path.write_bytes(b'{"schema":"tampered","kind":"program_graph_node","payload":{}}')
    with pytest.raises(GraphHistoryIntegrityError):
        history.graphs.get_verified_node(ping.program_graph_node_cid)
    with pytest.raises(GraphHistoryIntegrityError):
        history.history.get_verified_artifact(result.storage_cid)


def test_missing_reference_fails_closed(history: ProgramGraphHistory) -> None:
    missing = _cid("absent-node")
    with pytest.raises((GraphHistoryNotFound, GraphHistoryIntegrityError)):
        history.graphs.get_verified_node(missing)
    ping = _node("function", "pkg.mod.missing-edge-src")
    pong = _node("function", "pkg.mod.missing-edge-dst")
    edge = _edge("calls", ping, pong)
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        history.graphs.put_edge(edge)


def test_append_idempotency_and_operation_id_conflict(
    history: ProgramGraphHistory,
) -> None:
    graph = _cyclic_graph()
    first = append_program_graph_snapshot(
        history,
        graph["snapshot"],
        nodes=[graph["module"], graph["ping"], graph["pong"]],
        edges=graph["edges"],
        operation_id="op-snap",
    )
    second = append_program_graph_snapshot(
        history,
        graph["snapshot"],
        nodes=[graph["module"], graph["ping"], graph["pong"]],
        edges=graph["edges"],
        operation_id="op-snap",
    )
    assert first.cid == second.cid
    assert second.created is False
    assert second.reason_code == "unchanged"
    other = _node("function", "pkg.mod.other")
    with pytest.raises(GraphHistoryConflictError, match="operation_id"):
        history.graphs.put_node(other, operation_id="op-snap")


def test_forged_expected_cid_fails_closed(history: ProgramGraphHistory) -> None:
    ping = _node("function", "pkg.mod.ping")
    forged = _cid("not-the-node")
    with pytest.raises(GraphHistoryIntegrityError, match="forged|mismatched"):
        history.graphs.put_node(ping, expected_cid=forged)


def test_seal_is_deterministic() -> None:
    ping = _node("function", "pkg.mod.ping")
    sealed_a = seal_graph_history_artifact(
        SemanticWorldHistoryKind.PROGRAM_GRAPH_NODE, ping.to_dict()
    )
    sealed_b = seal_graph_history_artifact("program_graph_node", ping.to_dict())
    assert sealed_a == sealed_b
    assert cid_for_graph_history_artifact(
        SemanticWorldHistoryKind.PROGRAM_GRAPH_NODE, ping.to_dict()
    ) == cid_for_artifact(sealed_a)


# ---------------------------------------------------------------------------
# World roots
# ---------------------------------------------------------------------------


def _identity_for(snapshot, **overrides: Any) -> SemanticWorldRootIdentity:
    fields = {
        "domain_state_cid": _cid("domain"),
        "canonical_program_graph_cid": snapshot.canonical_program_graph_cid,
        "program_graph_snapshot_cid": snapshot.program_graph_snapshot_cid,
        "semantic_object_index_cid": _cid("objects"),
        "environment_binding_set_cid": snapshot.environment_binding_set_cid,
        "policy_cid": _cid("policy"),
        "analysis_limitation_index_cid": _cid("limits"),
    }
    fields.update(overrides)
    return SemanticWorldRootIdentity(**fields)


def test_world_root_binds_every_referenced_subroot(
    history: ProgramGraphHistory,
    roots: SemanticWorldSnapshotStore,
) -> None:
    graph = _cyclic_graph()
    append_program_graph_snapshot(
        history,
        graph["snapshot"],
        nodes=[graph["module"], graph["ping"], graph["pong"]],
        edges=graph["edges"],
    )
    bundle = _transition_bundle(history, admit=True)
    receipt = append_transition_receipt(
        history,
        bundle["receipt"],
        query=bundle["query"],
        prediction=bundle["prediction"],
        observation=bundle["observation"],
        admission=bundle["admission"],
    )
    event = _event(_cid("state-root"))
    history.graphs.put_event(event)
    trace = history.graphs.put_trace(
        ExecutionTraceIdentity(event_cids=[event.program_event_cid])
    )
    identity = _identity_for(graph["snapshot"])
    _put_identity_leaves(roots, identity)
    manifest, result = build_world_root_manifest(
        roots,
        identity,
        generation=0,
        execution_trace_cids=[trace.cid],
        transition_receipt_cids=[receipt.cid],
        operation_id="root-0",
    )
    assert result.cid == manifest.world_root_manifest_cid
    loaded = roots.get_verified_manifest(result.cid)
    bound = {(item["role"], item["cid"]) for item in loaded.subroots}
    assert ("program_graph_snapshot", identity.program_graph_snapshot_cid) in bound
    assert ("canonical_program_graph", identity.canonical_program_graph_cid) in bound
    assert ("domain_state", identity.domain_state_cid) in bound
    assert ("policy", identity.policy_cid) in bound
    assert ("execution_trace", trace.cid) in bound
    assert ("transition_receipt", receipt.cid) in bound
    assert ("world_snapshot", loaded.world_snapshot_cid) in bound
    roles_and_cids = [item["role"] + ":" + item["cid"] for item in loaded.subroots]
    assert roles_and_cids == sorted(roles_and_cids)
    assert loaded.generation == 0
    assert loaded.previous_manifest_cid is None
    assert loaded.identity.semantic_world_root_cid == identity.semantic_world_root_cid
    assert "generation" not in loaded.identity.to_dict()


def test_world_root_missing_subroot_fails_closed(
    history: ProgramGraphHistory,
    roots: SemanticWorldSnapshotStore,
) -> None:
    graph = _cyclic_graph()
    append_program_graph_snapshot(
        history,
        graph["snapshot"],
        nodes=[graph["module"], graph["ping"], graph["pong"]],
        edges=graph["edges"],
    )
    identity = _identity_for(graph["snapshot"])
    with pytest.raises(WorldRootAdmissionError, match="store-before-reference"):
        build_world_root_manifest(roots, identity, generation=0)


def test_world_root_delta_retains_unchanged_subroots(
    history: ProgramGraphHistory,
    roots: SemanticWorldSnapshotStore,
) -> None:
    graph = _cyclic_graph()
    append_program_graph_snapshot(
        history,
        graph["snapshot"],
        nodes=[graph["module"], graph["ping"], graph["pong"]],
        edges=graph["edges"],
    )
    extra = _node("function", "pkg.mod.helper")
    extra_edge = _edge("declares", graph["module"], extra)
    successor = assemble_program_graph_snapshot(
        nodes=[graph["module"], graph["ping"], graph["pong"], extra],
        edges=[*graph["edges"], extra_edge],
        environment_binding_set_cid=_cid("bindings"),
        sealed_binding_cid=_cid("sealed-2"),
        retained_subroot_cids=[
            graph["module"].program_graph_node_cid,
            graph["ping"].program_graph_node_cid,
            graph["pong"].program_graph_node_cid,
        ],
    )
    append_program_graph_snapshot(
        history, successor, nodes=[extra], edges=[extra_edge], operation_id="snap-2"
    )
    delta = delta_between_snapshots(graph["snapshot"], successor)
    history.graphs.put_delta(delta)
    first_identity = _identity_for(graph["snapshot"])
    _put_identity_leaves(roots, first_identity)
    first, _ = build_world_root_manifest(
        roots, first_identity, generation=0, operation_id="root-0"
    )
    second_identity = _identity_for(
        successor,
        domain_state_cid=first_identity.domain_state_cid,
        semantic_object_index_cid=first_identity.semantic_object_index_cid,
        policy_cid=first_identity.policy_cid,
        analysis_limitation_index_cid=first_identity.analysis_limitation_index_cid,
        environment_binding_set_cid=first_identity.environment_binding_set_cid,
    )
    second, result = build_world_root_manifest(
        roots,
        second_identity,
        generation=1,
        previous_manifest_cid=first.world_root_manifest_cid,
        graph_delta_cid=delta.program_graph_delta_cid,
        operation_id="root-1",
    )
    loaded = roots.get_verified_manifest(result.cid)
    assert loaded.generation == 1
    assert loaded.previous_manifest_cid == first.world_root_manifest_cid
    assert first_identity.policy_cid in loaded.retained_subroot_cids
    assert first_identity.domain_state_cid in loaded.retained_subroot_cids
    assert graph["ping"].program_graph_node_cid in loaded.retained_subroot_cids
    assert loaded.identity.program_graph_snapshot_cid == successor.program_graph_snapshot_cid
    assert loaded.graph_delta_cid == delta.program_graph_delta_cid
    rebuilt = SemanticWorldRootManifest.from_dict(loaded.to_dict())
    assert rebuilt.world_root_manifest_cid == loaded.world_root_manifest_cid


def test_world_root_manifest_is_deterministic(
    history: ProgramGraphHistory,
    roots: SemanticWorldSnapshotStore,
) -> None:
    graph = _cyclic_graph()
    append_program_graph_snapshot(
        history,
        graph["snapshot"],
        nodes=[graph["module"], graph["ping"], graph["pong"]],
        edges=graph["edges"],
    )
    identity = _identity_for(graph["snapshot"])
    _put_identity_leaves(roots, identity)
    first, first_result = build_world_root_manifest(
        roots, identity, generation=0, operation_id="det-a"
    )
    second, second_result = build_world_root_manifest(
        roots, identity, generation=0, operation_id="det-b"
    )
    assert first.world_root_manifest_cid == second.world_root_manifest_cid
    assert first_result.cid == second_result.cid
    assert second_result.created is False
    assert list(first.subroots) == list(second.subroots)


def test_generation_must_advance_from_previous_manifest(
    history: ProgramGraphHistory,
    roots: SemanticWorldSnapshotStore,
) -> None:
    graph = _cyclic_graph()
    append_program_graph_snapshot(
        history,
        graph["snapshot"],
        nodes=[graph["module"], graph["ping"], graph["pong"]],
        edges=graph["edges"],
    )
    identity = _identity_for(graph["snapshot"])
    _put_identity_leaves(roots, identity)
    first, _ = build_world_root_manifest(roots, identity, generation=0)
    with pytest.raises(WorldRootAdmissionError, match="generation"):
        build_world_root_manifest(
            roots,
            identity,
            generation=0,
            previous_manifest_cid=first.world_root_manifest_cid,
        )
    with pytest.raises(WorldRootAdmissionError, match="generation"):
        build_world_root_manifest(roots, identity, generation=2)


def test_kit_cid_profile_matches_datasets_raw_profile() -> None:
    payload = b"graph-history-raw"
    assert cid_for_bytes(payload, "raw") == datasets_cid_for_bytes(payload)
