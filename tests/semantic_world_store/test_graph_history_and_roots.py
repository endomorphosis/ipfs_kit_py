"""Fail-closed vectors for logical graph history and world-root manifests."""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from typing import Any

import pytest

from ipfs_datasets_py.logic.software_contracts.content import cid_for_bytes
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_execution import (
    CompletenessClaim,
    EventKind,
    EventOrigin,
    ExecutionTrace,
    ObservationStatus as ExecutionObservationStatus,
    PrivacyClass,
    ProgramEvent,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_graph import (
    LOGICAL_CYCLE_REQUIRED_KINDS,
    CallsiteRecord,
    ContractKind,
    ContractStateRecord,
    DynamicFrontierRecord,
    FunctionSymbolRecord,
    ProgramGraphEdge,
    ProgramGraphIndexKind,
    ProgramGraphIndexManifest,
    ProgramGraphNode,
    ProgramGraphSnapshot,
    ProofObligationGraph,
    ResolutionStatus,
    StaticSuccessorSet,
    assemble_program_graph_snapshot,
    assert_physical_dag_acyclic,
    delta_between_snapshots,
    directed_logical_cycles,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    SemanticWorldRootIdentity,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_transition import (
    ObservationStatus,
    ProgramTransitionPrediction,
    QueryFamily,
    SpecialistFamily,
    TransitionModelProfile,
    admit_program_transition,
    observe_program_transition,
    propose_program_transition,
    select_and_parameterize_candidate,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
)
from ipfs_kit_py.semantic_world_store.graph_history import (
    GRAPH_HISTORY_EVIDENCE,
    GRAPH_HISTORY_MODULE_INTERFACE,
    GRAPH_HISTORY_STORED_SCHEMA,
    MAX_HISTORY_BYTES,
    PROGRAM_GRAPH_HISTORY_INTERFACE,
    GraphHistoryAdmissionError,
    GraphHistoryConflictError,
    GraphHistoryIntegrityError,
    GraphHistoryKind,
    GraphHistoryMissingReference,
    LogicalProgramGraphStore,
    ProgramTransitionLog,
    SemanticWorldSnapshot,
    SemanticWorldSnapshotStore,
    append_program_graph_snapshot,
    append_transition_receipt,
    world_history_blocks,
)
from ipfs_kit_py.semantic_world_store.world_roots import (
    SEMANTIC_WORLD_ROOT_INTERFACE,
    WORLD_ROOT_HISTORY_EVIDENCE,
    WORLD_ROOT_MANIFEST_SCHEMA,
    SemanticWorldRootHistory,
    SemanticWorldRootManifest,
    WorldRootAdmissionError,
    build_world_root_manifest,
)


def _raw_cid(label: str) -> str:
    return cid_for_bytes(label.encode("utf-8"))


def _source() -> str:
    return cid_for_bytes(b"def ping():\n    return pong()\n")


def _put_opaque(coordination: DurableCoordinationStore, label: str) -> str:
    result = coordination.put(
        {
            "schema": "ipfs-kit.semantic-world-store.opaque-subroot@1",
            "kind": "opaque_subroot",
            "label": label,
        },
        codec="dag-json",
        replicate=False,
    )
    return str(result["cid"])


def _node(kind: str, name: str, **overrides: Any) -> ProgramGraphNode:
    fields: dict[str, Any] = {
        "node_kind": kind,
        "language": "python",
        "logical_name": name,
        "source_cid": _source(),
        "declaration_cid": _raw_cid(f"decl:{name}"),
        "environment_binding_cid": _raw_cid("env-v1"),
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
        "environment_binding_cid": _raw_cid("env-v1"),
        "resolution_status": ResolutionStatus.DEFINITE,
        "logical_cycle": kind in LOGICAL_CYCLE_REQUIRED_KINDS,
        "unavailable_dimensions": (),
        "metadata": {},
    }
    fields.update(overrides)
    return ProgramGraphEdge(**fields)


def _function(name: str, **overrides: Any) -> FunctionSymbolRecord:
    fields: dict[str, Any] = {
        "language": "python",
        "logical_name": name,
        "source_cid": _source(),
        "declaration_cid": _raw_cid(f"decl:{name}"),
        "parameter_names": (),
        "return_annotation": "None",
        "unavailable_dimensions": (),
    }
    fields.update(overrides)
    return FunctionSymbolRecord(**fields)


def _callsite(caller: str, callee: str, ordinal: int = 0) -> CallsiteRecord:
    return CallsiteRecord(
        language="python",
        caller_logical_name=caller,
        callee_logical_name=callee,
        source_cid=_source(),
        ordinal=ordinal,
        resolution_status=ResolutionStatus.DEFINITE,
        callee_declaration_cid=_raw_cid(f"decl:{callee}"),
    )


def _contract(name: str) -> ContractStateRecord:
    return ContractStateRecord(
        language="python",
        subject_logical_name=name,
        contract_kind=ContractKind.PRECONDITION,
        specification_cid=_raw_cid(f"spec:{name}"),
        discharge_status="unknown",
    )


def _mutual_graph(*, env_cid: str, sealed_cid: str) -> dict[str, Any]:
    ping_fn = _function("pkg.mod.ping")
    pong_fn = _function("pkg.mod.pong")
    ping_call = _callsite("pkg.mod.ping", "pkg.mod.pong", 0)
    pong_call = _callsite("pkg.mod.pong", "pkg.mod.ping", 0)
    module = _node("module", "pkg.mod")
    ping = _node("function", "pkg.mod.ping", record_cid=ping_fn.function_symbol_record_cid)
    pong = _node("function", "pkg.mod.pong", record_cid=pong_fn.function_symbol_record_cid)
    ping_site = _node("callsite", "pkg.mod.ping#0", record_cid=ping_call.callsite_record_cid)
    pong_site = _node("callsite", "pkg.mod.pong#0", record_cid=pong_call.callsite_record_cid)
    obligation = _node("proof_obligation", "pkg.mod.ping.post")
    contract = _contract("pkg.mod.ping")
    contract_node = _node(
        "contract_state",
        "pkg.mod.ping.pre",
        record_cid=contract.contract_state_record_cid,
    )
    dynamic = _node("unresolved_dynamic", "pkg.mod.ping.__getattr__")
    edges = [
        _edge("declares", module, ping),
        _edge("declares", module, pong),
        _edge("calls", ping, ping_site),
        _edge("calls", pong, pong_site),
        _edge("mutual_recursion", ping, pong, logical_cycle=True),
        _edge("mutual_recursion", pong, ping, logical_cycle=True),
        _edge("binds_contract", ping, contract_node),
        _edge("proved_by", ping, obligation),
        _edge(
            "unresolved_dynamic",
            ping,
            dynamic,
            resolution_status="unresolved",
            unavailable_dimensions=("reflection",),
        ),
    ]
    pog = ProofObligationGraph(
        language="python",
        root_obligation_cid=obligation.program_graph_node_cid,
        obligation_node_cids=[obligation.program_graph_node_cid],
        obligation_edge_cids=[],
    )
    successors = StaticSuccessorSet(
        language="python",
        subject_node_cid=ping.program_graph_node_cid,
        successor_node_cids=[
            ping_site.program_graph_node_cid,
            dynamic.program_graph_node_cid,
        ],
        successor_edge_cids=[
            edges[2].program_graph_edge_cid,
            edges[-1].program_graph_edge_cid,
        ],
        complete=False,
        unavailable_dimensions=("reflection",),
    )
    frontier = DynamicFrontierRecord(
        language="python",
        unresolved_node_cids=[dynamic.program_graph_node_cid],
        unresolved_edge_cids=[edges[-1].program_graph_edge_cid],
        reasons=["reflection", "unknown_callee"],
        unavailable_dimensions=("reflection",),
    )
    nodes = [module, ping, pong, ping_site, pong_site, obligation, contract_node, dynamic]
    snapshot = assemble_program_graph_snapshot(
        nodes=nodes,
        edges=edges,
        environment_binding_set_cid=env_cid,
        sealed_binding_cid=sealed_cid,
        callsites=[ping_call, pong_call],
        function_symbols=[ping_fn, pong_fn],
        contract_states=[contract],
        proof_obligation_graphs=[pog],
        successor_sets=[successors],
        frontiers=[frontier],
        retained_subroot_cids=[module.program_graph_node_cid],
        unavailable_dimensions=["reflection"],
    )
    return {
        "nodes": nodes,
        "edges": edges,
        "snapshot": snapshot,
        "module": module,
        "ping": ping,
        "pong": pong,
        "callsites": [ping_call, pong_call],
        "function_symbols": [ping_fn, pong_fn],
        "contract_states": [contract],
        "proof_obligation_graphs": [pog],
        "successor_sets": [successors],
        "frontiers": [frontier],
    }


def _cfg_cycle_graph(*, env_cid: str, sealed_cid: str) -> dict[str, Any]:
    entry = _node("cfg_block", "pkg.mod.loop.entry")
    body = _node("cfg_block", "pkg.mod.loop.body")
    edges = [
        _edge("cfg_next", entry, body),
        _edge("cfg_next", body, entry, logical_cycle=True),
    ]
    snapshot = assemble_program_graph_snapshot(
        nodes=[entry, body],
        edges=edges,
        environment_binding_set_cid=env_cid,
        sealed_binding_cid=sealed_cid,
    )
    return {"nodes": [entry, body], "edges": edges, "snapshot": snapshot}


def _event(subject: str, *, predecessor: str | None = None, name: str = "a") -> ProgramEvent:
    return ProgramEvent(
        event_kind=EventKind.OBSERVE,
        event_origin=EventOrigin.OBSERVED,
        observation_status=ExecutionObservationStatus.OBSERVED,
        language="python",
        tree_cid=_raw_cid("tree"),
        source_cid=_source(),
        code_cid=_raw_cid("code"),
        environment_binding_cid=_raw_cid("env-event"),
        subject_cid=subject,
        logical_name=f"pkg.mod.step.{name}",
        payload={"step": name},
        predecessor_event_cid=predecessor,
        stack_frame_cids=(),
        completeness_claim=CompletenessClaim.FULL_STATE,
        privacy_class=PrivacyClass.INTERNAL,
    )


def _trace(events: list[ProgramEvent]) -> ExecutionTrace:
    return ExecutionTrace(
        language="python",
        tree_cid=_raw_cid("tree"),
        source_cid=_source(),
        environment_binding_cid=_raw_cid("env-event"),
        event_cids=[event.program_event_cid for event in events],
        completeness_claim=CompletenessClaim.FULL_STATE,
        privacy_class=PrivacyClass.INTERNAL,
        includes_raw_bodies=False,
    )


def _query(**overrides: Any):
    from ipfs_datasets_py.logic.software_contracts.semantic_state.program_transition import (
        ProgramTransitionQuery,
    )

    fields: dict[str, Any] = {
        "query_family": QueryFamily.NEXT_CALL,
        "language": "python",
        "subject_cid": _raw_cid("state-current"),
        "current_source_cid": _raw_cid("source-current"),
        "current_state_cid": _raw_cid("state-current"),
        "environment_binding_cid": _raw_cid("env-v1"),
        "policy_cid": _raw_cid("policy-v1"),
        "allowed_symbol_cids": [_raw_cid("sym-b"), _raw_cid("sym-a")],
        "evidence_cids": [_raw_cid("ev-1")],
        "unavailable_dimensions": ("native_stack",),
    }
    fields.update(overrides)
    return ProgramTransitionQuery(**fields)


def _profile() -> TransitionModelProfile:
    return TransitionModelProfile(
        profile_name="next-call-specialist-v1",
        specialist_family=SpecialistFamily.CALL_TARGET,
        model_cid=_raw_cid("model-v1"),
        tokenizer_cid=_raw_cid("tok-v1"),
        preprocessing_profile_cid=_raw_cid("prep-v1"),
    )


def _transition_bundle():
    query = _query()
    profile = _profile()
    candidate = select_and_parameterize_candidate(
        query,
        candidate_kind="call_target",
        selected_cid=query.allowed_symbol_cids[0],
    )
    prediction = propose_program_transition(
        query, [candidate], model_profile=profile
    )
    observation = observe_program_transition(
        query,
        observed_cid=query.allowed_symbol_cids[0],
        observation_status=ObservationStatus.OBSERVED,
        evidence_cids=[_raw_cid("obs-ev")],
    )
    admission = admit_program_transition(
        query,
        current_subject_cid=query.subject_cid,
        current_source_cid=query.current_source_cid,
        current_environment_binding_cid=query.environment_binding_cid,
        current_state_cid=query.current_state_cid,
        prediction=prediction,
        observation=observation,
        validation_evidence_cids=[_raw_cid("val-ev")],
    )
    return {
        "query": query,
        "profile": profile,
        "candidate": candidate,
        "prediction": prediction,
        "observation": observation,
        "admission": admission,
    }


@pytest.fixture()
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "semantic-world-history"


@pytest.fixture()
def coordination(store_dir: Path) -> DurableCoordinationStore:
    root = DurableCoordinationStore(store_dir)
    yield root
    root.close()


@pytest.fixture()
def graphs(coordination: DurableCoordinationStore) -> LogicalProgramGraphStore:
    return LogicalProgramGraphStore(coordination)


@pytest.fixture()
def transitions(coordination: DurableCoordinationStore) -> ProgramTransitionLog:
    return ProgramTransitionLog(coordination)


@pytest.fixture()
def snapshots(coordination: DurableCoordinationStore) -> SemanticWorldSnapshotStore:
    return SemanticWorldSnapshotStore(coordination)


@pytest.fixture()
def roots(coordination: DurableCoordinationStore) -> SemanticWorldRootHistory:
    return SemanticWorldRootHistory(coordination)


def _append_graph(graphs: LogicalProgramGraphStore, graph: dict[str, Any], **kwargs: Any):
    return graphs.append_program_graph_snapshot(
        graph["snapshot"],
        nodes=graph["nodes"],
        edges=graph["edges"],
        callsites=graph.get("callsites") or (),
        function_symbols=graph.get("function_symbols") or (),
        contract_states=graph.get("contract_states") or (),
        proof_obligation_graphs=graph.get("proof_obligation_graphs") or (),
        successor_sets=graph.get("successor_sets") or (),
        frontiers=graph.get("frontiers") or (),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Cold import, interfaces, no second CID/engine
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
    assert roots_mod.SEMANTIC_WORLD_ROOT_INTERFACE == "SemanticWorldRoot@1"
    assert roots_mod.SemanticWorldRootManifest.__name__ == "SemanticWorldRootManifest"
    assert callable(history_mod.append_program_graph_snapshot)
    assert callable(history_mod.append_transition_receipt)
    assert callable(roots_mod.build_world_root_manifest)


def test_module_interfaces_are_versioned() -> None:
    assert PROGRAM_GRAPH_HISTORY_INTERFACE == "ProgramGraphHistory@1"
    assert GRAPH_HISTORY_MODULE_INTERFACE == "ProgramGraphHistory@1"
    assert SEMANTIC_WORLD_ROOT_INTERFACE == "SemanticWorldRoot@1"
    assert GRAPH_HISTORY_EVIDENCE == "sawm/graph-history@1"
    assert WORLD_ROOT_HISTORY_EVIDENCE == "sawm/world-root-history@1"
    assert GRAPH_HISTORY_STORED_SCHEMA.endswith("@1")
    assert WORLD_ROOT_MANIFEST_SCHEMA.endswith("@1")
    assert MAX_HISTORY_BYTES == 1_048_576


def test_no_second_cid_or_storage_engine() -> None:
    history_source = Path(
        inspect.getsourcefile(LogicalProgramGraphStore)
    ).read_text(encoding="utf-8")
    roots_source = Path(
        inspect.getsourcefile(SemanticWorldRootManifest)
    ).read_text(encoding="utf-8")
    for source in (history_source, roots_source):
        assert "from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import" in source
        assert "DurableCoordinationStore" in source
        assert "def _varint" not in source
        assert "base64.b32encode" not in source
        assert "multihash.digest" not in source
        assert "hashlib.sha256" not in source
        assert "cid_for_artifact" in source


# ---------------------------------------------------------------------------
# Graph snapshots: cycles, store-before-reference, deltas, idempotency
# ---------------------------------------------------------------------------


def test_mutual_recursion_snapshot_is_physically_acyclic_and_logically_queryable(
    graphs: LogicalProgramGraphStore,
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env")
    sealed_cid = _put_opaque(coordination, "sealed")
    graph = _mutual_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    result = _append_graph(graphs, graph, operation_id="op-graph-1")
    assert result.created is True
    assert result.cid == graph["snapshot"].program_graph_snapshot_cid
    loaded = graphs.get_verified_snapshot(result.cid)
    assert loaded.program_graph_snapshot_cid == graph["snapshot"].program_graph_snapshot_cid
    cycles = graphs.query_logical_cycles(result.cid)
    assert cycles
    catalog = graphs.physical_ipld_catalog(result.cid)
    assert_physical_dag_acyclic(catalog)
    ping = graph["ping"]
    pong = graph["pong"]
    cycle_edges = [
        edge
        for edge in graph["edges"]
        if edge.logical_cycle
        and {edge.source_node_cid, edge.target_node_cid}
        == {ping.program_graph_node_cid, pong.program_graph_node_cid}
    ]
    assert len(cycle_edges) == 2
    queried = directed_logical_cycles(cycle_edges)
    assert queried
    assert graphs.get_verified_node(ping.program_graph_node_cid).logical_name == "pkg.mod.ping"


def test_cfg_state_cycle_snapshot_remains_queryable(
    graphs: LogicalProgramGraphStore,
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env-cfg")
    sealed_cid = _put_opaque(coordination, "sealed-cfg")
    graph = _cfg_cycle_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    result = _append_graph(graphs, graph)
    cycles = graphs.query_logical_cycles(result.cid)
    assert cycles
    catalog = graphs.physical_ipld_catalog(result.cid)
    assert_physical_dag_acyclic(catalog)


def test_store_before_reference_rejects_snapshot_without_nodes(
    graphs: LogicalProgramGraphStore,
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env-missing")
    sealed_cid = _put_opaque(coordination, "sealed-missing")
    graph = _cfg_cycle_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    with pytest.raises(GraphHistoryMissingReference):
        graphs.put_snapshot(graph["snapshot"])
    graphs.put_node(graph["nodes"][0])
    with pytest.raises(GraphHistoryMissingReference):
        graphs.put_snapshot(graph["snapshot"])


def test_delta_retains_unchanged_subroots(
    graphs: LogicalProgramGraphStore,
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env-delta")
    sealed_cid = _put_opaque(coordination, "sealed-delta")
    first = _cfg_cycle_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    _append_graph(graphs, first, operation_id="op-delta-1")
    extra = _node("test", "pkg.mod.loop.test")
    current = assemble_program_graph_snapshot(
        nodes=[*first["nodes"], extra],
        edges=[*first["edges"], _edge("tested_by", first["nodes"][0], extra)],
        environment_binding_set_cid=env_cid,
        sealed_binding_cid=sealed_cid,
        retained_subroot_cids=[node.program_graph_node_cid for node in first["nodes"]],
    )
    result = graphs.append_program_graph_snapshot(
        current,
        nodes=[*first["nodes"], extra],
        edges=[*first["edges"], _edge("tested_by", first["nodes"][0], extra)],
        previous_snapshot=first["snapshot"],
        operation_id="op-delta-2",
    )
    delta = delta_between_snapshots(first["snapshot"], current)
    stored_delta = graphs.get_verified_delta(delta.program_graph_delta_cid)
    assert stored_delta.retained_subroot_cids == tuple(
        sorted(node.program_graph_node_cid for node in first["nodes"])
    )
    assert extra.program_graph_node_cid in stored_delta.added_node_cids
    unchanged = graphs.get_verified_node(first["nodes"][0].program_graph_node_cid)
    assert unchanged.program_graph_node_cid == first["nodes"][0].program_graph_node_cid
    again = graphs.put_node(first["nodes"][0], operation_id="op-delta-node-repeat")
    assert again.created is False
    assert again.reason_code == "unchanged"
    loaded = graphs.get_verified_snapshot(result.cid)
    assert first["nodes"][0].program_graph_node_cid in loaded.retained_subroot_cids


def test_deterministic_snapshot_ordering(
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env-order")
    sealed_cid = _put_opaque(coordination, "sealed-order")
    graph = _mutual_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    reversed_nodes = list(reversed(graph["nodes"]))
    reversed_edges = list(reversed(graph["edges"]))
    left = assemble_program_graph_snapshot(
        nodes=graph["nodes"],
        edges=graph["edges"],
        environment_binding_set_cid=env_cid,
        sealed_binding_cid=sealed_cid,
        callsites=graph["callsites"],
        function_symbols=graph["function_symbols"],
        contract_states=graph["contract_states"],
        proof_obligation_graphs=graph["proof_obligation_graphs"],
        successor_sets=graph["successor_sets"],
        frontiers=graph["frontiers"],
        retained_subroot_cids=graph["snapshot"].retained_subroot_cids,
        unavailable_dimensions=graph["snapshot"].unavailable_dimensions,
    )
    right = assemble_program_graph_snapshot(
        nodes=reversed_nodes,
        edges=reversed_edges,
        environment_binding_set_cid=env_cid,
        sealed_binding_cid=sealed_cid,
        callsites=list(reversed(graph["callsites"])),
        function_symbols=list(reversed(graph["function_symbols"])),
        contract_states=graph["contract_states"],
        proof_obligation_graphs=graph["proof_obligation_graphs"],
        successor_sets=graph["successor_sets"],
        frontiers=graph["frontiers"],
        retained_subroot_cids=list(reversed(list(graph["snapshot"].retained_subroot_cids))),
        unavailable_dimensions=graph["snapshot"].unavailable_dimensions,
    )
    assert left.program_graph_snapshot_cid == right.program_graph_snapshot_cid
    assert list(left.node_cids) == sorted(left.node_cids)
    assert list(left.edge_cids) == sorted(left.edge_cids)


def test_append_snapshot_is_idempotent(
    graphs: LogicalProgramGraphStore,
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env-idemp")
    sealed_cid = _put_opaque(coordination, "sealed-idemp")
    graph = _cfg_cycle_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    first = _append_graph(graphs, graph, operation_id="op-idemp")
    second = _append_graph(graphs, graph, operation_id="op-idemp")
    assert first.cid == second.cid
    assert second.created is False
    assert second.reason_code == "unchanged"


def test_operation_id_conflict_on_different_snapshot(
    graphs: LogicalProgramGraphStore,
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env-conflict")
    sealed_cid = _put_opaque(coordination, "sealed-conflict")
    first = _cfg_cycle_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    _append_graph(graphs, first, operation_id="op-conflict")
    extra = _node("test", "pkg.mod.other")
    second_snapshot = assemble_program_graph_snapshot(
        nodes=[*first["nodes"], extra],
        edges=first["edges"],
        environment_binding_set_cid=env_cid,
        sealed_binding_cid=sealed_cid,
    )
    with pytest.raises(GraphHistoryConflictError):
        graphs.append_program_graph_snapshot(
            second_snapshot,
            nodes=[*first["nodes"], extra],
            edges=first["edges"],
            operation_id="op-conflict",
        )


def test_corrupt_present_block_fails_closed(
    graphs: LogicalProgramGraphStore,
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env-corrupt")
    sealed_cid = _put_opaque(coordination, "sealed-corrupt")
    graph = _cfg_cycle_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    result = _append_graph(graphs, graph)
    path = coordination._block_path(result.storage_cid)
    path.write_text('{"schema":"tampered"}', encoding="utf-8")
    with pytest.raises(GraphHistoryIntegrityError):
        graphs.get_verified_snapshot(result.cid)


def test_missing_reference_on_forged_snapshot_cid_set(
    graphs: LogicalProgramGraphStore,
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env-forged")
    sealed_cid = _put_opaque(coordination, "sealed-forged")
    graph = _cfg_cycle_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    _append_graph(graphs, graph)
    missing = _node("function", "pkg.mod.absent")
    forged = assemble_program_graph_snapshot(
        nodes=[*graph["nodes"], missing],
        edges=graph["edges"],
        environment_binding_set_cid=env_cid,
        sealed_binding_cid=sealed_cid,
    )
    with pytest.raises(GraphHistoryMissingReference):
        graphs.put_snapshot(forged)


def test_public_append_program_graph_snapshot_function(
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env-public")
    sealed_cid = _put_opaque(coordination, "sealed-public")
    graph = _cfg_cycle_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    result = append_program_graph_snapshot(
        coordination,
        graph["snapshot"],
        nodes=graph["nodes"],
        edges=graph["edges"],
        operation_id="op-public-graph",
    )
    loaded = LogicalProgramGraphStore(coordination).get_verified_snapshot(result.cid)
    assert loaded.program_graph_snapshot_cid == graph["snapshot"].program_graph_snapshot_cid


# ---------------------------------------------------------------------------
# Transition log: predictions distinguishable from observations
# ---------------------------------------------------------------------------


def test_predictions_are_distinguishable_from_admitted_observations(
    transitions: ProgramTransitionLog,
) -> None:
    bundle = _transition_bundle()
    result = transitions.append_transition_receipt(
        query=bundle["query"],
        admission=bundle["admission"],
        prediction=bundle["prediction"],
        observation=bundle["observation"],
        candidates=[bundle["candidate"]],
        model_profile=bundle["profile"],
        operation_id="op-transition-1",
    )
    receipt = transitions.get_verified_receipt(result.cid)
    assert receipt.prediction_cid == bundle["prediction"].prediction_cid
    assert receipt.observation_cid == bundle["observation"].observation_cid
    assert receipt.prediction_cid != receipt.observation_cid
    prediction = transitions.get_verified_prediction(receipt.prediction_cid)
    observation = transitions.get_verified_observation(receipt.observation_cid)
    assert isinstance(prediction, ProgramTransitionPrediction)
    assert prediction.proposal_only is True
    assert observation.proposal_only is False
    assert observation.is_authoritative_observation is True
    assert transitions.kind_of(prediction.prediction_cid) is GraphHistoryKind.TRANSITION_PREDICTION
    assert transitions.kind_of(observation.observation_cid) is GraphHistoryKind.TRANSITION_OBSERVATION
    with pytest.raises(GraphHistoryIntegrityError):
        transitions.get_verified_observation(prediction.prediction_cid)
    with pytest.raises(GraphHistoryIntegrityError):
        transitions.get_verified_prediction(observation.observation_cid)
    with pytest.raises(GraphHistoryAdmissionError):
        transitions.put_observation(prediction.to_dict())


def test_append_transition_receipt_is_idempotent(
    transitions: ProgramTransitionLog,
) -> None:
    bundle = _transition_bundle()
    first = transitions.append_transition_receipt(
        query=bundle["query"],
        admission=bundle["admission"],
        prediction=bundle["prediction"],
        observation=bundle["observation"],
        candidates=[bundle["candidate"]],
        model_profile=bundle["profile"],
        operation_id="op-transition-idemp",
    )
    second = transitions.append_transition_receipt(
        query=bundle["query"],
        admission=bundle["admission"],
        prediction=bundle["prediction"],
        observation=bundle["observation"],
        candidates=[bundle["candidate"]],
        model_profile=bundle["profile"],
        operation_id="op-transition-idemp",
    )
    assert first.cid == second.cid
    assert second.created is False


def test_store_before_reference_rejects_receipt_without_admission(
    transitions: ProgramTransitionLog,
) -> None:
    bundle = _transition_bundle()
    from ipfs_datasets_py.logic.software_contracts.semantic_state.program_transition import (
        issue_transition_receipt,
    )

    receipt = issue_transition_receipt(
        bundle["query"],
        bundle["admission"],
        prediction=bundle["prediction"],
        observation=bundle["observation"],
    )
    with pytest.raises(GraphHistoryMissingReference):
        transitions.blocks.put_record(GraphHistoryKind.TRANSITION_RECEIPT, receipt)


def test_public_append_transition_receipt_function(
    coordination: DurableCoordinationStore,
) -> None:
    bundle = _transition_bundle()
    result = append_transition_receipt(
        coordination,
        query=bundle["query"],
        admission=bundle["admission"],
        prediction=bundle["prediction"],
        observation=bundle["observation"],
        candidates=[bundle["candidate"]],
        model_profile=bundle["profile"],
        operation_id="op-public-transition",
    )
    loaded = ProgramTransitionLog(coordination).get_verified_receipt(result.cid)
    assert loaded.observation_cid == bundle["observation"].observation_cid


# ---------------------------------------------------------------------------
# Repeated-state distinct history
# ---------------------------------------------------------------------------


def test_repeated_states_keep_distinct_trace_history(
    snapshots: SemanticWorldSnapshotStore,
    graphs: LogicalProgramGraphStore,
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env-trace")
    sealed_cid = _put_opaque(coordination, "sealed-trace")
    graph = _cfg_cycle_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    _append_graph(graphs, graph)
    state = _raw_cid("state-s")
    first = _event(state, name="enter")
    second = _event(state, predecessor=first.program_event_cid, name="again")
    assert first.subject_cid == second.subject_cid
    assert first.program_event_cid != second.program_event_cid
    trace_a = _trace([first])
    trace_b = _trace([first, second])
    assert trace_a.execution_trace_cid != trace_b.execution_trace_cid
    domain = _put_opaque(coordination, "domain")
    objects = _put_opaque(coordination, "objects")
    policy = _put_opaque(coordination, "policy")
    limits = _put_opaque(coordination, "limits")
    world = SemanticWorldSnapshot(
        program_graph_snapshot_cid=graph["snapshot"].program_graph_snapshot_cid,
        canonical_program_graph_cid=graph["snapshot"].canonical_program_graph_cid,
        domain_state_cid=domain,
        semantic_object_index_cid=objects,
        environment_binding_set_cid=env_cid,
        policy_cid=policy,
        analysis_limitation_index_cid=limits,
        execution_trace_cids=[
            trace_a.execution_trace_cid,
            trace_b.execution_trace_cid,
        ],
        retained_subroot_cids=[graph["nodes"][0].program_graph_node_cid],
    )
    result = snapshots.append_world_snapshot(
        world,
        events=[first, second],
        traces=[trace_a, trace_b],
        operation_id="op-world-1",
    )
    loaded = snapshots.get_verified_snapshot(result.cid)
    assert loaded.execution_trace_cids == (
        trace_a.execution_trace_cid,
        trace_b.execution_trace_cid,
    )
    restored_a = snapshots.get_verified_trace(trace_a.execution_trace_cid)
    restored_b = snapshots.get_verified_trace(trace_b.execution_trace_cid)
    assert restored_a.event_cids == (first.program_event_cid,)
    assert restored_b.event_cids == (first.program_event_cid, second.program_event_cid)
    assert snapshots.get_verified_event(first.program_event_cid).subject_cid == state
    assert snapshots.get_verified_event(second.program_event_cid).subject_cid == state


# ---------------------------------------------------------------------------
# World-root manifests
# ---------------------------------------------------------------------------


def _world_and_identity(
    *,
    graph: dict[str, Any],
    env_cid: str,
    coordination: DurableCoordinationStore,
    transitions: ProgramTransitionLog | None = None,
) -> tuple[SemanticWorldSnapshot, SemanticWorldRootIdentity, dict[str, Any]]:
    domain = _put_opaque(coordination, "domain-root")
    objects = _put_opaque(coordination, "objects-root")
    policy = _put_opaque(coordination, "policy-root")
    limits = _put_opaque(coordination, "limits-root")
    bundle = _transition_bundle()
    receipt_cids: tuple[str, ...] = ()
    prediction_cids: tuple[str, ...] = ()
    observation_cids: tuple[str, ...] = ()
    if transitions is not None:
        written = transitions.append_transition_receipt(
            query=bundle["query"],
            admission=bundle["admission"],
            prediction=bundle["prediction"],
            observation=bundle["observation"],
            candidates=[bundle["candidate"]],
            model_profile=bundle["profile"],
            operation_id="op-root-transition",
        )
        receipt_cids = (written.cid,)
        prediction_cids = (bundle["prediction"].prediction_cid,)
        observation_cids = (bundle["observation"].observation_cid,)
    world = SemanticWorldSnapshot(
        program_graph_snapshot_cid=graph["snapshot"].program_graph_snapshot_cid,
        canonical_program_graph_cid=graph["snapshot"].canonical_program_graph_cid,
        domain_state_cid=domain,
        semantic_object_index_cid=objects,
        environment_binding_set_cid=env_cid,
        policy_cid=policy,
        analysis_limitation_index_cid=limits,
        transition_receipt_cids=receipt_cids,
        prediction_cids=prediction_cids,
        observation_cids=observation_cids,
        retained_subroot_cids=list(graph["snapshot"].node_cids[:1]),
    )
    identity = SemanticWorldRootIdentity(
        domain_state_cid=domain,
        canonical_program_graph_cid=graph["snapshot"].canonical_program_graph_cid,
        program_graph_snapshot_cid=graph["snapshot"].program_graph_snapshot_cid,
        semantic_object_index_cid=objects,
        environment_binding_set_cid=env_cid,
        policy_cid=policy,
        analysis_limitation_index_cid=limits,
    )
    extras = {
        "bundle": bundle,
        "domain": domain,
        "objects": objects,
        "policy": policy,
        "limits": limits,
    }
    return world, identity, extras


def test_roots_deterministically_bind_every_referenced_subroot(
    graphs: LogicalProgramGraphStore,
    snapshots: SemanticWorldSnapshotStore,
    transitions: ProgramTransitionLog,
    roots: SemanticWorldRootHistory,
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env-root")
    sealed_cid = _put_opaque(coordination, "sealed-root")
    graph = _mutual_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    _append_graph(graphs, graph, operation_id="op-root-graph")
    world, identity, extras = _world_and_identity(
        graph=graph,
        env_cid=env_cid,
        coordination=coordination,
        transitions=transitions,
    )
    snapshots.append_world_snapshot(world, operation_id="op-root-world")
    reversed_receipts = list(reversed(list(world.transition_receipt_cids)))
    manifest = build_world_root_manifest(
        identity=identity,
        world_snapshot=world,
        extra_subroot_cids=list(reversed(list(world.bound_subroot_cids()))),
        store=coordination,
    )
    again = build_world_root_manifest(
        identity=identity.to_dict(),
        world_snapshot=world.to_dict(),
        extra_subroot_cids=list(world.bound_subroot_cids()),
        store=coordination,
    )
    assert manifest.world_root_manifest_cid == again.world_root_manifest_cid
    assert list(manifest.subroot_cids) == sorted(manifest.subroot_cids)
    bound = set(manifest.subroot_cids)
    for cid in (
        identity.domain_state_cid,
        identity.canonical_program_graph_cid,
        identity.program_graph_snapshot_cid,
        identity.semantic_object_index_cid,
        identity.environment_binding_set_cid,
        identity.policy_cid,
        identity.analysis_limitation_index_cid,
        identity.semantic_world_root_cid,
        world.semantic_world_snapshot_cid,
        *world.transition_receipt_cids,
        *world.prediction_cids,
        *world.observation_cids,
        *world.retained_subroot_cids,
    ):
        assert cid in bound
    written = roots.append_manifest(manifest, operation_id="op-root-1")
    loaded = roots.get_verified_manifest(written.cid)
    assert loaded.generation == 1
    assert loaded.previous_manifest_cid is None
    assert loaded.semantic_world_root_cid == identity.semantic_world_root_cid
    assert loaded.to_semantic_identity().semantic_world_root_cid == identity.semantic_world_root_cid
    assert cid_for_artifact(loaded.identity_payload()) == loaded.world_root_manifest_cid
    assert extras["bundle"]["prediction"].prediction_cid in loaded.subroot_cids
    assert reversed_receipts[0] in loaded.transition_receipt_cids


def test_generation_bearing_successor_binds_previous_manifest(
    graphs: LogicalProgramGraphStore,
    snapshots: SemanticWorldSnapshotStore,
    roots: SemanticWorldRootHistory,
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env-gen")
    sealed_cid = _put_opaque(coordination, "sealed-gen")
    graph = _cfg_cycle_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    _append_graph(graphs, graph)
    world, identity, _extras = _world_and_identity(
        graph=graph, env_cid=env_cid, coordination=coordination
    )
    snapshots.append_world_snapshot(world)
    first = build_world_root_manifest(
        identity=identity, world_snapshot=world, store=coordination
    )
    roots.append_manifest(first, operation_id="op-gen-1")
    successor = build_world_root_manifest(
        identity=identity,
        world_snapshot=world,
        previous_manifest=first,
        store=coordination,
    )
    assert successor.generation == 2
    assert successor.previous_manifest_cid == first.world_root_manifest_cid
    assert first.world_root_manifest_cid in successor.subroot_cids
    assert successor.world_root_manifest_cid != first.world_root_manifest_cid
    written = roots.append_manifest(successor, operation_id="op-gen-2")
    loaded = roots.get_verified_manifest(written.cid)
    assert loaded.generation == 2
    unchanged = roots.append_manifest(successor, operation_id="op-gen-2")
    assert unchanged.created is False


def test_missing_subroot_fails_closed(
    graphs: LogicalProgramGraphStore,
    snapshots: SemanticWorldSnapshotStore,
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env-gap")
    sealed_cid = _put_opaque(coordination, "sealed-gap")
    graph = _cfg_cycle_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    _append_graph(graphs, graph)
    world, identity, _extras = _world_and_identity(
        graph=graph, env_cid=env_cid, coordination=coordination
    )
    snapshots.append_world_snapshot(world)
    missing = _put_opaque(DurableCoordinationStore(coordination.root / "other"), "absent")
    with pytest.raises(GraphHistoryMissingReference):
        build_world_root_manifest(
            identity=identity,
            world_snapshot=world,
            extra_subroot_cids=[missing],
            store=coordination,
        )


def test_world_snapshot_rejects_overlapping_prediction_and_observation_cids() -> None:
    snapshot_cid = _raw_cid("snap")
    canonical = _raw_cid("canon")
    shared = _raw_cid("shared")
    with pytest.raises(Exception):
        SemanticWorldSnapshot(
            program_graph_snapshot_cid=snapshot_cid,
            canonical_program_graph_cid=canonical,
            domain_state_cid=_raw_cid("d"),
            semantic_object_index_cid=_raw_cid("o"),
            environment_binding_set_cid=_raw_cid("e"),
            policy_cid=_raw_cid("p"),
            analysis_limitation_index_cid=_raw_cid("l"),
            prediction_cids=[shared],
            observation_cids=[shared],
        )


def test_first_manifest_cannot_cite_predecessor() -> None:
    identity_fields = {
        "domain_state_cid": _raw_cid("d"),
        "canonical_program_graph_cid": _raw_cid("c"),
        "program_graph_snapshot_cid": _raw_cid("s"),
        "semantic_object_index_cid": _raw_cid("o"),
        "environment_binding_set_cid": _raw_cid("e"),
        "policy_cid": _raw_cid("p"),
        "analysis_limitation_index_cid": _raw_cid("l"),
    }
    identity = SemanticWorldRootIdentity(**identity_fields)
    with pytest.raises(WorldRootAdmissionError):
        SemanticWorldRootManifest(
            generation=1,
            semantic_world_root_cid=identity.semantic_world_root_cid,
            previous_manifest_cid=_raw_cid("prev"),
            subroot_cids=[
                identity.semantic_world_root_cid,
                *identity_fields.values(),
                _raw_cid("prev"),
            ],
            **identity_fields,
        )


def test_index_manifest_is_bound_after_snapshot(
    graphs: LogicalProgramGraphStore,
    coordination: DurableCoordinationStore,
) -> None:
    env_cid = _put_opaque(coordination, "env-index")
    sealed_cid = _put_opaque(coordination, "sealed-index")
    graph = _cfg_cycle_graph(env_cid=env_cid, sealed_cid=sealed_cid)
    manifest = ProgramGraphIndexManifest(
        snapshot_cid=graph["snapshot"].program_graph_snapshot_cid,
        index_kind=ProgramGraphIndexKind.ADJACENCY,
        schema_ids=["ipfs-datasets.software-contracts.program-graph-snapshot@1"],
    )
    result = graphs.append_program_graph_snapshot(
        graph["snapshot"],
        nodes=graph["nodes"],
        edges=graph["edges"],
        index_manifest=manifest,
        operation_id="op-index",
    )
    loaded = world_history_blocks(coordination).get_decoded(
        manifest.program_graph_index_manifest_cid,
        expected_kind=GraphHistoryKind.PROGRAM_GRAPH_INDEX_MANIFEST,
    )
    assert loaded.snapshot_cid == result.cid


def test_shared_history_store_composes_injected_coordination(
    coordination: DurableCoordinationStore,
    graphs: LogicalProgramGraphStore,
    transitions: ProgramTransitionLog,
    snapshots: SemanticWorldSnapshotStore,
    roots: SemanticWorldRootHistory,
) -> None:
    assert graphs.store is coordination
    assert transitions.store is coordination
    assert snapshots.store is coordination
    assert roots.store is coordination
    assert graphs.blocks is transitions.blocks
    assert graphs.blocks is snapshots.blocks
    assert graphs.blocks is roots.blocks
