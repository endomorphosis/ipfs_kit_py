"""Fail-closed vectors for logical graph history and world-root manifests."""

from __future__ import annotations

import importlib
import inspect
import json
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
    assert_physical_dag_acyclic,
    delta_between_snapshots,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    SEMANTIC_IDENTITY_EXCLUDED_FIELDS,
    ExecutionTraceIdentity,
    ProgramEventIdentity,
    ProgramIdentityError,
    RawExecutionStateIdentity,
    SemanticWorldRootIdentity,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_transition import (
    PROGRAM_TRANSITION_OBSERVATION_SCHEMA,
    PROGRAM_TRANSITION_PREDICTION_SCHEMA,
    AdmissionVerdict,
    ObservationStatus,
    ProgramTransitionError,
    ProgramTransitionPrediction,
    QueryFamily,
    SpecialistFamily,
    TransitionModelProfile,
    admit_program_transition,
    decode_transition_observation,
    issue_transition_receipt,
    observe_program_transition,
    propose_program_transition,
    select_and_parameterize_candidate,
    ProgramTransitionQuery,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
    cid_for_bytes as kit_cid_for_bytes,
)
from ipfs_kit_py.semantic_world_store.graph_history import (
    PROGRAM_GRAPH_HISTORY_INTERFACE,
    STORED_HISTORY_INTERFACE,
    STORED_HISTORY_SCHEMA,
    GraphHistoryAdmissionError,
    GraphHistoryConflictError,
    GraphHistoryEntry,
    GraphHistoryIntegrityError,
    GraphHistoryNotFound,
    HistoryRecordKind,
    LogicalProgramGraphStore,
    ProgramTransitionLog,
    TransitionLogEntry,
    append_program_graph_snapshot,
    append_transition_receipt,
    assert_history_physical_dag_acyclic,
    seal_history_record,
)
from ipfs_kit_py.semantic_world_store.world_roots import (
    SEMANTIC_WORLD_ROOT_INTERFACE,
    SemanticWorldRootManifest,
    SemanticWorldSnapshot,
    SemanticWorldSnapshotStore,
    WorldRootAdmissionError,
    build_world_root_manifest,
)


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


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
def graph(coordination: DurableCoordinationStore) -> LogicalProgramGraphStore:
    store = LogicalProgramGraphStore(coordination)
    yield store
    store.close()


@pytest.fixture()
def transitions(graph: LogicalProgramGraphStore) -> ProgramTransitionLog:
    return ProgramTransitionLog(graph.blocks)


@pytest.fixture()
def roots(
    graph: LogicalProgramGraphStore, transitions: ProgramTransitionLog
) -> SemanticWorldSnapshotStore:
    return SemanticWorldSnapshotStore(
        graph.blocks, graph_store=graph, transition_log=transitions
    )


def _binding(graph: LogicalProgramGraphStore, label: str) -> str:
    return graph.put_opaque_subroot(label).cid


def _profile(**overrides: Any) -> TransitionModelProfile:
    fields: dict[str, Any] = {
        "profile_name": "next-call-specialist-v1",
        "specialist_family": SpecialistFamily.CALL_TARGET,
        "model_cid": _cid("model-v1"),
        "tokenizer_cid": _cid("tok-v1"),
        "preprocessing_profile_cid": _cid("prep-v1"),
    }
    fields.update(overrides)
    return TransitionModelProfile(**fields)


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


def _candidate(query: ProgramTransitionQuery, **overrides: Any):
    selected = query.allowed_symbol_cids[0]
    fields: dict[str, Any] = {
        "candidate_kind": "call_target",
        "selected_cid": selected,
    }
    fields.update(overrides)
    return select_and_parameterize_candidate(query, **fields)


def _prediction(
    query: ProgramTransitionQuery,
    candidates: list[Any] | None = None,
    **overrides: Any,
) -> ProgramTransitionPrediction:
    items = candidates if candidates is not None else [_candidate(query)]
    profile = overrides.pop("model_profile", None) or _profile()
    return propose_program_transition(
        query,
        items,
        model_profile=profile,
        **overrides,
    )


def _observation(query: ProgramTransitionQuery, **overrides: Any):
    fields: dict[str, Any] = {
        "observed_cid": query.allowed_symbol_cids[0],
        "observation_status": ObservationStatus.OBSERVED,
        "evidence_cids": [_cid("obs-ev")],
    }
    fields.update(overrides)
    return observe_program_transition(query, **fields)


def _identity_for_snapshot(
    graph: LogicalProgramGraphStore,
    snapshot: ProgramGraphSnapshot,
    **overrides: Any,
) -> SemanticWorldRootIdentity:
    fields: dict[str, Any] = {
        "domain_state_cid": _binding(graph, "domain"),
        "canonical_program_graph_cid": snapshot.canonical_program_graph_cid,
        "program_graph_snapshot_cid": snapshot.program_graph_snapshot_cid,
        "semantic_object_index_cid": _binding(graph, "objects"),
        "environment_binding_set_cid": snapshot.environment_binding_set_cid,
        "policy_cid": _binding(graph, "policy"),
        "analysis_limitation_index_cid": _binding(graph, "limits"),
    }
    fields.update(overrides)
    return SemanticWorldRootIdentity(**fields)


# ---------------------------------------------------------------------------
# Cold import / interfaces / no second CID engine
# ---------------------------------------------------------------------------


def test_cold_import_of_declared_modules() -> None:
    for name in list(sys.modules):
        if "semantic_world_store.graph_history" in name or "semantic_world_store.world_roots" in name:
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
    assert roots_mod.SEMANTIC_WORLD_ROOT_INTERFACE == "SemanticWorldRoot@1"
    assert roots_mod.SemanticWorldSnapshotStore.__name__ == "SemanticWorldSnapshotStore"
    assert roots_mod.SemanticWorldRootManifest.__name__ == "SemanticWorldRootManifest"
    assert callable(history_mod.append_program_graph_snapshot)
    assert callable(history_mod.append_transition_receipt)
    assert callable(roots_mod.build_world_root_manifest)


def test_module_interfaces_are_versioned() -> None:
    assert PROGRAM_GRAPH_HISTORY_INTERFACE == "ProgramGraphHistory@1"
    assert SEMANTIC_WORLD_ROOT_INTERFACE == "SemanticWorldRoot@1"
    assert LogicalProgramGraphStore.INTERFACE == "ProgramGraphHistory@1"
    assert ProgramTransitionLog.INTERFACE == "ProgramGraphHistory@1"
    assert SemanticWorldSnapshotStore.INTERFACE == "SemanticWorldRoot@1"
    assert STORED_HISTORY_INTERFACE == "SemanticWorldHistoryRecord@1"
    assert STORED_HISTORY_SCHEMA.endswith("@1")
    assert GraphHistoryEntry.INTERFACE == "GraphHistoryEntry@1"
    assert TransitionLogEntry.INTERFACE == "TransitionLogEntry@1"


def test_kit_owned_history_payloads_bind_schema_and_interface() -> None:
    entry = GraphHistoryEntry(snapshot_cid=_cid("snap"), sequence=1)
    payload = entry.to_payload()
    assert payload["schema"] == GraphHistoryEntry.SCHEMA
    assert payload["interface"] == GraphHistoryEntry.INTERFACE
    assert "SCHEMA" not in payload
    assert "INTERFACE" not in payload
    loaded = GraphHistoryEntry.from_payload(payload)
    assert loaded.snapshot_cid == entry.snapshot_cid
    assert loaded.sequence == 1
    with pytest.raises(GraphHistoryIntegrityError, match="unknown"):
        GraphHistoryEntry.from_payload({**payload, "SCHEMA": entry.SCHEMA})
    log_entry = TransitionLogEntry(
        receipt_cid=_cid("receipt"),
        query_cid=_cid("query"),
        admission_cid=_cid("admission"),
        verdict="admitted",
        sequence=1,
        prediction_cid=_cid("prediction"),
        observation_cid=_cid("observation"),
    )
    log_payload = log_entry.to_payload()
    assert log_payload["schema"] == TransitionLogEntry.SCHEMA
    assert log_payload["interface"] == TransitionLogEntry.INTERFACE
    restored = TransitionLogEntry.from_payload(log_payload)
    assert restored.verdict == "admitted"
    assert restored.prediction_cid != restored.observation_cid


def test_no_second_cid_or_cas_engine() -> None:
    history_source = Path(inspect.getsourcefile(LogicalProgramGraphStore)).read_text(
        encoding="utf-8"
    )
    roots_source = Path(inspect.getsourcefile(SemanticWorldRootManifest)).read_text(
        encoding="utf-8"
    )
    for source in (history_source, roots_source):
        assert "from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import" in source
        assert "DurableCoordinationStore" in source
        assert "def _varint" not in source
        assert "base64.b32encode" not in source
        assert "multihash.digest" not in source
        assert "hashlib.sha256" not in source
        assert "compare_and_swap_world_root" not in source
        assert "replay_semantic_world_wal" not in source
    assert "cid_for_artifact" in history_source
    assert "cid_for_bytes" in history_source
    assert "sqlite3.connect" in history_source
    assert "semantic_world_history_index.sqlite3" in history_source
    assert "CREATE TABLE IF NOT EXISTS artifacts" not in history_source


def test_store_composes_injected_coordination_engine(
    coordination: DurableCoordinationStore, graph: LogicalProgramGraphStore
) -> None:
    assert graph.store is coordination
    result = graph.put_opaque_subroot("probe")
    assert coordination.has(result.storage_cid)
    sealed_path = coordination._block_path(result.storage_cid)
    raw = json.loads(sealed_path.read_text(encoding="utf-8"))
    assert raw["schema"] == STORED_HISTORY_SCHEMA
    assert raw["kind"] == HistoryRecordKind.OPAQUE_SUBROOT.value
    assert cid_for_artifact(raw) == result.storage_cid


# ---------------------------------------------------------------------------
# Store-before-reference
# ---------------------------------------------------------------------------


def test_snapshot_without_stored_nodes_fails_closed(
    graph: LogicalProgramGraphStore,
) -> None:
    ping = _node("function", "pkg.mod.ping")
    pong = _node("function", "pkg.mod.pong")
    edge = _edge("mutual_recursion", ping, pong, logical_cycle=True)
    env = _binding(graph, "bindings")
    sealed = _binding(graph, "sealed")
    snapshot = assemble_program_graph_snapshot(
        nodes=[ping, pong],
        edges=[edge],
        environment_binding_set_cid=env,
        sealed_binding_cid=sealed,
    )
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        graph.put_record(snapshot)


def test_edge_without_stored_nodes_fails_closed(graph: LogicalProgramGraphStore) -> None:
    ping = _node("function", "pkg.mod.ping")
    pong = _node("function", "pkg.mod.pong")
    edge = _edge("calls", ping, pong)
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference: source_node_cid"):
        graph.put_record(edge)


def test_receipt_without_stored_query_fails_closed(
    transitions: ProgramTransitionLog,
) -> None:
    query = _query()
    observation = _observation(query)
    admission = admit_program_transition(
        query,
        current_subject_cid=query.subject_cid,
        current_source_cid=query.current_source_cid,
        current_environment_binding_cid=query.environment_binding_cid,
        current_state_cid=query.current_state_cid,
        observation=observation,
    )
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference: query_cid"):
        transitions.put_admission(admission)


def test_world_root_without_stored_snapshot_fails_closed(
    graph: LogicalProgramGraphStore, roots: SemanticWorldSnapshotStore
) -> None:
    ping = _node("function", "pkg.mod.ping")
    env = _binding(graph, "bindings")
    sealed = _binding(graph, "sealed")
    snapshot = assemble_program_graph_snapshot(
        nodes=[ping],
        edges=[],
        environment_binding_set_cid=env,
        sealed_binding_cid=sealed,
    )
    identity = SemanticWorldRootIdentity(
        domain_state_cid=_binding(graph, "domain"),
        canonical_program_graph_cid=snapshot.canonical_program_graph_cid,
        program_graph_snapshot_cid=snapshot.program_graph_snapshot_cid,
        semantic_object_index_cid=_binding(graph, "objects"),
        environment_binding_set_cid=env,
        policy_cid=_binding(graph, "policy"),
        analysis_limitation_index_cid=_binding(graph, "limits"),
    )
    with pytest.raises(WorldRootAdmissionError, match="store-before-reference"):
        build_world_root_manifest(roots, identity=identity, generation=1)


# ---------------------------------------------------------------------------
# Logical cycles on an acyclic physical DAG
# ---------------------------------------------------------------------------


def test_mutual_recursion_snapshot_is_queryable_on_acyclic_ipld(
    graph: LogicalProgramGraphStore,
) -> None:
    ping = _node("function", "pkg.mod.ping")
    pong = _node("function", "pkg.mod.pong")
    left = _edge("mutual_recursion", ping, pong, logical_cycle=True)
    right = _edge("mutual_recursion", pong, ping, logical_cycle=True)
    result = append_program_graph_snapshot(
        graph,
        nodes=[pong, ping],
        edges=[right, left],
        environment_binding_set_cid=_binding(graph, "bindings"),
        sealed_binding_cid=_binding(graph, "sealed"),
        operation_id="op-cycle-1",
    )
    loaded = graph.get_verified_snapshot(result.cid)
    cycles = graph.query_logical_cycles(loaded)
    assert cycles
    assert left.program_graph_edge_cid in cycles[0]
    assert right.program_graph_edge_cid in cycles[0]
    catalog = graph.physical_catalog_for_snapshot(loaded)
    assert_physical_dag_acyclic(catalog)
    assert_history_physical_dag_acyclic(catalog)
    assert result.history_entry_cid is not None
    entry = graph.get_verified_history_entry(result.history_entry_cid)
    assert entry.snapshot_cid == loaded.program_graph_snapshot_cid
    assert entry.sequence == 1


def test_cyclic_import_and_cfg_loop_remain_queryable(
    graph: LogicalProgramGraphStore,
) -> None:
    mod_a = _node("module", "pkg.a")
    mod_b = _node("module", "pkg.b")
    imports_ab = _edge("cyclic_import", mod_a, mod_b, logical_cycle=True)
    imports_ba = _edge("cyclic_import", mod_b, mod_a, logical_cycle=True)
    cyclic = append_program_graph_snapshot(
        graph,
        nodes=[mod_a, mod_b],
        edges=[imports_ab, imports_ba],
        environment_binding_set_cid=_binding(graph, "import-bindings"),
        sealed_binding_cid=_binding(graph, "import-sealed"),
    )
    assert graph.query_logical_cycles(cyclic.cid)

    entry = _node("cfg_block", "pkg.mod.loop.entry")
    body = _node("cfg_block", "pkg.mod.loop.body")
    forward = _edge("cfg_next", entry, body)
    back = _edge("cfg_next", body, entry, logical_cycle=True)
    loop = append_program_graph_snapshot(
        graph,
        nodes=[entry, body],
        edges=[forward, back],
        environment_binding_set_cid=_binding(graph, "cfg-bindings"),
        sealed_binding_cid=_binding(graph, "cfg-sealed"),
    )
    cycles = graph.query_logical_cycles(loop.cid)
    assert any(back.program_graph_edge_cid in cycle for cycle in cycles)
    assert_physical_dag_acyclic(graph.physical_catalog_for_snapshot(loop.cid))


def test_unmarked_logical_cycle_fails_closed(graph: LogicalProgramGraphStore) -> None:
    ping = _node("function", "pkg.mod.ping")
    pong = _node("function", "pkg.mod.pong")
    with pytest.raises(GraphHistoryAdmissionError, match="logical-cycle records"):
        append_program_graph_snapshot(
            graph,
            nodes=[ping, pong],
            edges=[
                _edge("cfg_next", ping, pong),
                _edge("cfg_next", pong, ping),
            ],
            environment_binding_set_cid=_binding(graph, "bindings"),
            sealed_binding_cid=_binding(graph, "sealed"),
        )


# ---------------------------------------------------------------------------
# Repeated-state distinct history
# ---------------------------------------------------------------------------


def test_repeated_states_preserve_distinct_event_history(
    graph: LogicalProgramGraphStore,
) -> None:
    raw = RawExecutionStateIdentity(
        language="python",
        capture_profile_cid=_cid("capture"),
        observed_state={"pc": "loop"},
    )
    graph.put_raw_execution_state(raw)
    first = ProgramEventIdentity(
        event_kind="enter",
        observation_status="observed",
        subject_cid=raw.raw_execution_state_cid,
    )
    second = ProgramEventIdentity(
        event_kind="assign",
        observation_status="observed",
        subject_cid=raw.raw_execution_state_cid,
        predecessor_event_cid=first.program_event_cid,
    )
    third = ProgramEventIdentity(
        event_kind="enter",
        observation_status="observed",
        subject_cid=raw.raw_execution_state_cid,
        predecessor_event_cid=second.program_event_cid,
        payload={"visit": 2},
    )
    graph.put_event(first)
    graph.put_event(second)
    graph.put_event(third)
    assert first.program_event_cid != third.program_event_cid
    assert first.subject_cid == third.subject_cid == raw.raw_execution_state_cid
    trace = ExecutionTraceIdentity(
        event_cids=[
            first.program_event_cid,
            second.program_event_cid,
            third.program_event_cid,
        ],
        raw_execution_state_cids=[
            raw.raw_execution_state_cid,
            raw.raw_execution_state_cid,
            raw.raw_execution_state_cid,
        ],
    )
    result = graph.put_trace(trace)
    loaded = graph.get_verified_record(
        result.cid, expected_kind=HistoryRecordKind.EXECUTION_TRACE
    )
    assert isinstance(loaded, ExecutionTraceIdentity)
    assert loaded.event_cids == trace.event_cids
    assert loaded.raw_execution_state_cids.count(raw.raw_execution_state_cid) == 3


def test_trace_without_stored_predecessor_fails_closed(
    graph: LogicalProgramGraphStore,
) -> None:
    event = ProgramEventIdentity(
        event_kind="enter",
        observation_status="observed",
        subject_cid=_cid("state"),
        predecessor_event_cid=_cid("missing-pred"),
    )
    with pytest.raises(
        GraphHistoryAdmissionError, match="store-before-reference: predecessor_event_cid"
    ):
        graph.put_event(event)


# ---------------------------------------------------------------------------
# Deterministic ordering and unchanged subroots
# ---------------------------------------------------------------------------


def test_snapshot_cid_is_independent_of_input_order(
    graph: LogicalProgramGraphStore,
) -> None:
    ping = _node("function", "pkg.mod.ping")
    pong = _node("function", "pkg.mod.pong")
    left = _edge("mutual_recursion", ping, pong, logical_cycle=True)
    right = _edge("mutual_recursion", pong, ping, logical_cycle=True)
    env = _binding(graph, "order-bindings")
    sealed = _binding(graph, "order-sealed")
    first = append_program_graph_snapshot(
        graph,
        nodes=[ping, pong],
        edges=[left, right],
        environment_binding_set_cid=env,
        sealed_binding_cid=sealed,
    )
    second = append_program_graph_snapshot(
        graph,
        nodes=[pong, ping],
        edges=[right, left],
        environment_binding_set_cid=env,
        sealed_binding_cid=sealed,
    )
    assert first.cid == second.cid
    assert first.storage_cid == second.storage_cid
    assert second.reason_code == "unchanged"
    assert second.created is False


def test_delta_retains_unchanged_subroots(graph: LogicalProgramGraphStore) -> None:
    keep = _node("module", "pkg.mod")
    ping = _node("function", "pkg.mod.ping")
    env = _binding(graph, "delta-bindings")
    sealed = _binding(graph, "delta-sealed")
    first = append_program_graph_snapshot(
        graph,
        nodes=[keep, ping],
        edges=[_edge("contains", keep, ping)],
        environment_binding_set_cid=env,
        sealed_binding_cid=sealed,
        retained_subroot_cids=[keep.program_graph_node_cid],
    )
    pong = _node("function", "pkg.mod.pong")
    previous = graph.get_verified_snapshot(first.cid)
    second = append_program_graph_snapshot(
        graph,
        nodes=[keep, ping, pong],
        edges=[
            _edge("contains", keep, ping),
            _edge("contains", keep, pong),
        ],
        environment_binding_set_cid=env,
        sealed_binding_cid=sealed,
        retained_subroot_cids=[
            keep.program_graph_node_cid,
            ping.program_graph_node_cid,
        ],
        previous_snapshot=previous,
        previous_entry_cid=first.history_entry_cid,
    )
    assert second.delta_cid is not None
    delta = graph.get_verified_delta(second.delta_cid)
    assert keep.program_graph_node_cid in delta.retained_subroot_cids
    assert ping.program_graph_node_cid in delta.retained_subroot_cids
    assert pong.program_graph_node_cid in delta.added_node_cids
    assert keep.program_graph_node_cid not in delta.added_node_cids
    rebuilt = delta_between_snapshots(previous, graph.get_verified_snapshot(second.cid))
    assert rebuilt.program_graph_delta_cid == delta.program_graph_delta_cid
    entry = graph.get_verified_history_entry(second.history_entry_cid)
    assert entry.previous_entry_cid == first.history_entry_cid
    assert entry.sequence == 2
    assert entry.snapshot_cid == second.cid
    assert entry.snapshot_cid != first.cid


# ---------------------------------------------------------------------------
# Transition predictions vs admitted observations
# ---------------------------------------------------------------------------


def test_predictions_are_distinguishable_from_admitted_observations(
    transitions: ProgramTransitionLog,
) -> None:
    query = _query()
    candidate = _candidate(query)
    prediction = _prediction(query, [candidate])
    observation = _observation(query)
    admission = admit_program_transition(
        query,
        current_subject_cid=query.subject_cid,
        current_source_cid=query.current_source_cid,
        current_environment_binding_cid=query.environment_binding_cid,
        current_state_cid=query.current_state_cid,
        prediction=prediction,
        observation=observation,
    )
    result = append_transition_receipt(
        transitions,
        query=query,
        admission=admission,
        prediction=prediction,
        observation=observation,
        candidates=[candidate],
        operation_id="op-receipt-1",
    )
    stored_prediction = transitions.get_verified_prediction(prediction.prediction_cid)
    stored_observation = transitions.get_verified_observation(observation.observation_cid)
    assert stored_prediction.SCHEMA == PROGRAM_TRANSITION_PREDICTION_SCHEMA
    assert stored_observation.SCHEMA == PROGRAM_TRANSITION_OBSERVATION_SCHEMA
    assert stored_prediction.proposal_only is True
    assert stored_observation.proposal_only is False
    with pytest.raises(ProgramTransitionError, match="cannot decode as observations"):
        decode_transition_observation(stored_prediction.to_dict())
    assert decode_transition_observation(stored_observation.to_dict()).observation_cid == (
        observation.observation_cid
    )
    receipt = transitions.get_verified_receipt(result.cid)
    assert receipt.prediction_cid == prediction.prediction_cid
    assert receipt.observation_cid == observation.observation_cid
    assert receipt.prediction_authoritative is False
    assert receipt.may_influence_planning is True
    assert receipt.verdict == AdmissionVerdict.ADMITTED.value
    with pytest.raises(GraphHistoryIntegrityError, match="wrong history kind"):
        transitions.get_verified_observation(prediction.prediction_cid)
    with pytest.raises(GraphHistoryIntegrityError, match="wrong history kind"):
        transitions.get_verified_prediction(observation.observation_cid)
    log_entry = transitions.get_verified_log_entry(result.log_entry_cid)
    assert log_entry.prediction_cid == prediction.prediction_cid
    assert log_entry.observation_cid == observation.observation_cid
    assert log_entry.verdict == "admitted"


def test_prediction_cannot_self_admit(transitions: ProgramTransitionLog) -> None:
    query = _query()
    prediction = _prediction(query)
    transitions.put_query(query)
    transitions.put_candidate(_candidate(query))
    transitions.put_prediction(prediction)
    admission = admit_program_transition(
        query,
        current_subject_cid=query.subject_cid,
        current_source_cid=query.current_source_cid,
        current_environment_binding_cid=query.environment_binding_cid,
        current_state_cid=query.current_state_cid,
        prediction=prediction,
    )
    assert admission.verdict == AdmissionVerdict.ABSTAIN.value
    assert admission.may_influence_planning is False
    result = append_transition_receipt(
        transitions,
        query=query,
        admission=admission,
        prediction=prediction,
        candidates=[_candidate(query)],
    )
    receipt = transitions.get_verified_receipt(result.cid)
    assert receipt.observation_cid is None
    assert receipt.prediction_cid == prediction.prediction_cid
    assert receipt.may_influence_planning is False


# ---------------------------------------------------------------------------
# Corrupt / missing references and idempotency
# ---------------------------------------------------------------------------


def test_corrupt_present_history_block_fails_closed(
    graph: LogicalProgramGraphStore,
) -> None:
    ping = _node("function", "pkg.mod.ping")
    result = append_program_graph_snapshot(
        graph,
        nodes=[ping],
        edges=[],
        environment_binding_set_cid=_binding(graph, "bindings"),
        sealed_binding_cid=_binding(graph, "sealed"),
        operation_id="op-corrupt",
    )
    path = graph.store._block_path(result.storage_cid)
    path.write_bytes(b'{"schema":"tampered","kind":"program_graph_snapshot","payload":{}}')
    with pytest.raises(GraphHistoryIntegrityError):
        graph.get_verified_snapshot(result.cid)
    with pytest.raises(GraphHistoryIntegrityError):
        graph.blocks.get_verified_record(result.storage_cid)


def test_missing_reference_get_fails_closed(graph: LogicalProgramGraphStore) -> None:
    with pytest.raises(GraphHistoryNotFound):
        graph.get_verified_snapshot(_cid("absent-snapshot"))


def test_forged_expected_cid_fails_closed(graph: LogicalProgramGraphStore) -> None:
    ping = _node("function", "pkg.mod.ping")
    graph.put_record(ping)
    forged = kit_cid_for_bytes(b"not-the-node", "raw")
    with pytest.raises(GraphHistoryIntegrityError, match="forged|mismatched"):
        graph.put_record(ping, expected_cid=forged)


def test_append_idempotency_and_operation_id_conflict(
    graph: LogicalProgramGraphStore,
) -> None:
    ping = _node("function", "pkg.mod.ping")
    env = _binding(graph, "id-bindings")
    sealed = _binding(graph, "id-sealed")
    first = append_program_graph_snapshot(
        graph,
        nodes=[ping],
        edges=[],
        environment_binding_set_cid=env,
        sealed_binding_cid=sealed,
        operation_id="op-idempotent",
    )
    second = append_program_graph_snapshot(
        graph,
        nodes=[ping],
        edges=[],
        environment_binding_set_cid=env,
        sealed_binding_cid=sealed,
        operation_id="op-idempotent",
    )
    assert first.cid == second.cid
    assert second.reason_code == "unchanged"
    assert second.created is False
    pong = _node("function", "pkg.mod.pong")
    with pytest.raises(GraphHistoryConflictError, match="operation_id"):
        append_program_graph_snapshot(
            graph,
            nodes=[pong],
            edges=[],
            environment_binding_set_cid=env,
            sealed_binding_cid=sealed,
            operation_id="op-idempotent",
        )


# ---------------------------------------------------------------------------
# World snapshots and generation-bearing root manifests
# ---------------------------------------------------------------------------


def test_world_root_binds_every_referenced_subroot(
    graph: LogicalProgramGraphStore,
    transitions: ProgramTransitionLog,
    roots: SemanticWorldSnapshotStore,
) -> None:
    ping = _node("function", "pkg.mod.ping")
    pong = _node("function", "pkg.mod.pong")
    snap_result = append_program_graph_snapshot(
        graph,
        nodes=[ping, pong],
        edges=[
            _edge("mutual_recursion", ping, pong, logical_cycle=True),
            _edge("mutual_recursion", pong, ping, logical_cycle=True),
        ],
        environment_binding_set_cid=_binding(graph, "root-bindings"),
        sealed_binding_cid=_binding(graph, "root-sealed"),
    )
    snapshot = graph.get_verified_snapshot(snap_result.cid)
    query = _query()
    observation = _observation(query)
    admission = admit_program_transition(
        query,
        current_subject_cid=query.subject_cid,
        current_source_cid=query.current_source_cid,
        current_environment_binding_cid=query.environment_binding_cid,
        current_state_cid=query.current_state_cid,
        observation=observation,
    )
    receipt = append_transition_receipt(
        transitions,
        query=query,
        admission=admission,
        observation=observation,
    )
    identity = _identity_for_snapshot(graph, snapshot)
    world = SemanticWorldSnapshot(
        identity=identity,
        graph_history_head_cid=snap_result.history_entry_cid,
        transition_log_head_cid=receipt.log_entry_cid,
        transition_receipt_cids=[receipt.cid],
    )
    manifest = build_world_root_manifest(
        roots,
        snapshot=world,
        generation=1,
        operation_id="op-root-1",
    )
    assert manifest.generation == 1
    assert "generation" in SEMANTIC_IDENTITY_EXCLUDED_FIELDS
    assert "generation" not in manifest.identity.to_dict()
    bound = set(manifest.referenced_subroot_cids)
    assert identity.semantic_world_root_cid in bound
    assert identity.domain_state_cid in bound
    assert identity.canonical_program_graph_cid in bound
    assert identity.program_graph_snapshot_cid in bound
    assert identity.semantic_object_index_cid in bound
    assert identity.environment_binding_set_cid in bound
    assert identity.policy_cid in bound
    assert identity.analysis_limitation_index_cid in bound
    assert snap_result.history_entry_cid in bound
    assert receipt.log_entry_cid in bound
    assert receipt.cid in bound
    assert world.world_snapshot_cid in bound
    loaded = roots.get_verified_manifest(manifest.world_root_manifest_cid)
    assert loaded.world_root_manifest_cid == manifest.world_root_manifest_cid
    assert loaded.referenced_subroot_cids == manifest.referenced_subroot_cids
    for cid in loaded.referenced_subroot_cids:
        assert graph.blocks.has_identity(cid)


def test_world_root_manifest_cid_is_order_independent(
    graph: LogicalProgramGraphStore, roots: SemanticWorldSnapshotStore
) -> None:
    ping = _node("function", "pkg.mod.ping")
    snap = append_program_graph_snapshot(
        graph,
        nodes=[ping],
        edges=[],
        environment_binding_set_cid=_binding(graph, "ord-bindings"),
        sealed_binding_cid=_binding(graph, "ord-sealed"),
    )
    snapshot = graph.get_verified_snapshot(snap.cid)
    identity = _identity_for_snapshot(graph, snapshot)
    traces = [_binding(graph, "trace-b"), _binding(graph, "trace-a")]
    left = SemanticWorldRootManifest(
        generation=1,
        identity=identity,
        execution_trace_cids=traces,
    )
    right = SemanticWorldRootManifest(
        generation=1,
        identity=identity,
        execution_trace_cids=list(reversed(traces)),
    )
    assert left.world_root_manifest_cid == right.world_root_manifest_cid
    assert left.referenced_subroot_cids == right.referenced_subroot_cids
    assert left.execution_trace_cids == tuple(sorted(traces))


def test_generation_bearing_predecessor_chain(
    graph: LogicalProgramGraphStore, roots: SemanticWorldSnapshotStore
) -> None:
    ping = _node("function", "pkg.mod.ping")
    first_snap = append_program_graph_snapshot(
        graph,
        nodes=[ping],
        edges=[],
        environment_binding_set_cid=_binding(graph, "gen-bindings"),
        sealed_binding_cid=_binding(graph, "gen-sealed"),
    )
    snapshot = graph.get_verified_snapshot(first_snap.cid)
    first = build_world_root_manifest(
        roots,
        identity=_identity_for_snapshot(graph, snapshot),
        graph_history_head_cid=first_snap.history_entry_cid,
    )
    assert first.generation == 1
    pong = _node("function", "pkg.mod.pong")
    second_snap = append_program_graph_snapshot(
        graph,
        nodes=[ping, pong],
        edges=[_edge("calls", ping, pong)],
        environment_binding_set_cid=snapshot.environment_binding_set_cid,
        sealed_binding_cid=_binding(graph, "gen-sealed-2"),
        previous_snapshot=snapshot,
        previous_entry_cid=first_snap.history_entry_cid,
    )
    successor = graph.get_verified_snapshot(second_snap.cid)
    second = build_world_root_manifest(
        roots,
        identity=_identity_for_snapshot(
            graph,
            successor,
            domain_state_cid=_binding(graph, "domain-2"),
            semantic_object_index_cid=_binding(graph, "objects-2"),
            policy_cid=_binding(graph, "policy-2"),
            analysis_limitation_index_cid=_binding(graph, "limits-2"),
        ),
        previous_manifest_cid=first.world_root_manifest_cid,
        graph_history_head_cid=second_snap.history_entry_cid,
    )
    assert second.generation == 2
    assert second.previous_manifest_cid == first.world_root_manifest_cid
    with pytest.raises(WorldRootAdmissionError, match="sole successor"):
        build_world_root_manifest(
            roots,
            identity=second.identity,
            previous_manifest_cid=first.world_root_manifest_cid,
            generation=4,
            graph_history_head_cid=second_snap.history_entry_cid,
        )


def test_world_root_rejects_generation_in_semantic_identity(
    graph: LogicalProgramGraphStore,
) -> None:
    ping = _node("function", "pkg.mod.ping")
    snap = append_program_graph_snapshot(
        graph,
        nodes=[ping],
        edges=[],
        environment_binding_set_cid=_binding(graph, "id-bind"),
        sealed_binding_cid=_binding(graph, "id-seal"),
    )
    snapshot = graph.get_verified_snapshot(snap.cid)
    identity = _identity_for_snapshot(graph, snapshot)
    payload = identity.to_dict()
    payload["generation"] = 1
    with pytest.raises(ProgramIdentityError, match="excluded fields"):
        SemanticWorldRootIdentity.from_dict(payload)


def test_append_helpers_accept_coordination_store(
    coordination: DurableCoordinationStore,
) -> None:
    ping = _node("function", "pkg.mod.ping")
    graph = LogicalProgramGraphStore(coordination)
    env = _binding(graph, "helper-bind")
    sealed = _binding(graph, "helper-seal")
    result = append_program_graph_snapshot(
        coordination,
        nodes=[ping],
        edges=[],
        environment_binding_set_cid=env,
        sealed_binding_cid=sealed,
    )
    assert result.kind is HistoryRecordKind.PROGRAM_GRAPH_SNAPSHOT
    query = _query()
    observation = _observation(query)
    admission = admit_program_transition(
        query,
        current_subject_cid=query.subject_cid,
        current_source_cid=query.current_source_cid,
        current_environment_binding_cid=query.environment_binding_cid,
        current_state_cid=query.current_state_cid,
        observation=observation,
    )
    receipt = append_transition_receipt(
        coordination,
        query=query,
        admission=admission,
        observation=observation,
    )
    assert receipt.kind is HistoryRecordKind.TRANSITION_RECEIPT
    reopened = LogicalProgramGraphStore(coordination)
    snapshot = reopened.get_verified_snapshot(result.cid)
    manifest = build_world_root_manifest(
        coordination,
        identity=_identity_for_snapshot(reopened, snapshot),
        graph_history_head_cid=result.history_entry_cid,
        transition_log_head_cid=receipt.log_entry_cid,
        transition_receipt_cids=[receipt.cid],
    )
    assert manifest.generation == 1
    assert seal_history_record(
        HistoryRecordKind.WORLD_ROOT_MANIFEST, manifest.to_payload()
    )["interface_id"] == STORED_HISTORY_INTERFACE
