"""Fail-closed vectors for logical graph history and world-root manifests."""

from __future__ import annotations

import inspect
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ipfs_datasets_py.logic.software_contracts.content import cid_for_bytes
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_execution import (
    CompletenessClaim,
    EventOrigin,
    ObservationStatus as ExecutionObservationStatus,
    PrivacyClass,
    ProgramEvent,
    assemble_execution_trace,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_graph import (
    LOGICAL_CYCLE_REQUIRED_KINDS,
    CallsiteRecord,
    ContractKind,
    ContractStateRecord,
    DynamicFrontierRecord,
    FunctionSymbolRecord,
    ProgramGraphDelta,
    ProgramGraphEdge,
    ProgramGraphNode,
    ProgramGraphSnapshot,
    ProofObligationGraph,
    ResolutionStatus,
    StaticSuccessorSet,
    apply_program_graph_delta,
    assemble_program_graph_snapshot,
    assert_physical_dag_acyclic,
    directed_logical_cycles,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    SemanticWorldRootIdentity,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_transition import (
    AdmissionVerdict,
    ObservationStatus,
    ProgramTransitionObservation,
    ProgramTransitionPrediction,
    ProgramTransitionQuery,
    ProgramTransitionReceipt,
    QueryFamily,
    SpecialistFamily,
    TransitionModelProfile,
    admit_program_transition,
    decode_transition_observation,
    issue_transition_receipt,
    observe_program_transition,
    propose_program_transition,
    select_and_parameterize_candidate,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_bytes as kit_cid_for_bytes,
)
from ipfs_kit_py.semantic_world_store.graph_history import (
    PROGRAM_GRAPH_HISTORY_INTERFACE,
    GraphHistoryAdmissionError,
    GraphHistoryBlockStore,
    GraphHistoryConflictError,
    GraphHistoryIntegrityError,
    GraphHistoryKind,
    GraphHistoryNotFound,
    LogicalProgramGraphStore,
    ProgramTransitionLog,
    SemanticWorldSnapshot,
    SemanticWorldSnapshotStore,
    append_program_graph_snapshot,
    append_transition_receipt,
)
from ipfs_kit_py.semantic_world_store.world_roots import (
    SEMANTIC_WORLD_ROOT_INTERFACE,
    SemanticWorldRootManifest,
    WorldRootError,
    build_world_root_manifest,
    collect_world_root_subroots,
    get_verified_world_root_manifest,
)


_PACKAGE_HISTORY = "ipfs_kit_py.semantic_world_store.graph_history"
_PACKAGE_ROOTS = "ipfs_kit_py.semantic_world_store.world_roots"
_OPT_OUTS = {
    "IPFS_DATASETS_AUTO_INSTALL": "0",
    "IPFS_DATASETS_AUTO_INSTALL_TEST_DEPS": "0",
    "IPFS_DATASETS_PY_MINIMAL_IMPORTS": "1",
    "IPFS_KIT_AUTO_INSTALL_DEPS": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
}


# ---------------------------------------------------------------------------
# Builders
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
        "declaration_cid": _cid(f"decl:{name}"),
        "parameter_names": (),
        "return_annotation": "None",
        "unavailable_dimensions": (),
    }
    fields.update(overrides)
    return FunctionSymbolRecord(**fields)


def _callsite(caller: str, callee: str, ordinal: int = 0, **overrides: Any) -> CallsiteRecord:
    fields: dict[str, Any] = {
        "language": "python",
        "caller_logical_name": caller,
        "callee_logical_name": callee,
        "source_cid": _source(),
        "ordinal": ordinal,
        "resolution_status": ResolutionStatus.DEFINITE,
        "callee_declaration_cid": _cid(f"decl:{callee}"),
        "unavailable_dimensions": (),
    }
    fields.update(overrides)
    return CallsiteRecord(**fields)


def _contract(name: str, **overrides: Any) -> ContractStateRecord:
    fields: dict[str, Any] = {
        "language": "python",
        "subject_logical_name": name,
        "contract_kind": ContractKind.PRECONDITION,
        "specification_cid": _cid(f"spec:{name}"),
        "discharge_status": "unknown",
        "unavailable_dimensions": (),
    }
    fields.update(overrides)
    return ContractStateRecord(**fields)


def _assemble(
    nodes: list[ProgramGraphNode],
    edges: list[ProgramGraphEdge],
    **overrides: Any,
) -> ProgramGraphSnapshot:
    fields: dict[str, Any] = {
        "nodes": nodes,
        "edges": edges,
        "environment_binding_set_cid": _cid("bindings"),
        "sealed_binding_cid": _cid("sealed"),
    }
    fields.update(overrides)
    return assemble_program_graph_snapshot(**fields)


def _cyclic_graph() -> dict[str, Any]:
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
    snapshot = _assemble(
        [module, ping, pong, ping_site, pong_site, obligation, contract_node, dynamic],
        edges,
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
        "module": module,
        "ping": ping,
        "pong": pong,
        "edges": edges,
        "snapshot": snapshot,
        "ping_fn": ping_fn,
        "pong_fn": pong_fn,
        "ping_call": ping_call,
        "pong_call": pong_call,
        "contract": contract,
        "pog": pog,
        "successors": successors,
        "frontier": frontier,
        "dynamic": dynamic,
        "ping_site": ping_site,
        "pong_site": pong_site,
        "obligation": obligation,
        "contract_node": contract_node,
    }


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


def _prediction(query: ProgramTransitionQuery | None = None) -> ProgramTransitionPrediction:
    bound = query or _query()
    candidate = select_and_parameterize_candidate(
        bound,
        candidate_kind="call_target",
        selected_cid=bound.allowed_symbol_cids[0],
    )
    return propose_program_transition(bound, [candidate], model_profile=_profile())


def _observation(query: ProgramTransitionQuery | None = None) -> ProgramTransitionObservation:
    bound = query or _query()
    return observe_program_transition(
        bound,
        observed_cid=bound.allowed_symbol_cids[0],
        observation_status=ObservationStatus.OBSERVED,
        evidence_cids=[_cid("obs-ev")],
    )


def _event(kind: str = "call", *, predecessor: str | None = None, **overrides: Any) -> ProgramEvent:
    fields: dict[str, Any] = {
        "event_kind": kind,
        "event_origin": EventOrigin.OBSERVED,
        "observation_status": ExecutionObservationStatus.OBSERVED,
        "language": "python",
        "tree_cid": _cid("tree"),
        "source_cid": _source(),
        "code_cid": _cid("code"),
        "environment_binding_cid": _cid("env-v1"),
        "subject_cid": _cid("state-current"),
        "logical_name": "pkg.mod.ping",
        "payload": {"callee": "pkg.mod.pong"} if kind == "call" else {},
        "line": 2,
        "column": 4,
        "predecessor_event_cid": predecessor,
        "stack_frame_cids": (_cid("frame-0"), _cid("frame-1")),
        "exception_snapshot_cid": None,
        "handler_state_cid": None,
        "redaction_profile_cid": None,
        "redacted_dimensions": (),
        "unavailable_dimensions": (),
        "completeness_claim": CompletenessClaim.FULL_STATE,
        "privacy_class": PrivacyClass.INTERNAL,
    }
    fields.update(overrides)
    return ProgramEvent(**fields)


def _append_graph(graphs: LogicalProgramGraphStore, graph: dict[str, Any], **kwargs: Any):
    snapshot = graph["snapshot"]
    return append_program_graph_snapshot(
        graphs,
        snapshot,
        nodes=[
            graph["module"],
            graph["ping"],
            graph["pong"],
            graph["ping_site"],
            graph["pong_site"],
            graph["obligation"],
            graph["contract_node"],
            graph["dynamic"],
        ],
        edges=graph["edges"],
        callsites=[graph["ping_call"], graph["pong_call"]],
        function_symbols=[graph["ping_fn"], graph["pong_fn"]],
        contract_states=[graph["contract"]],
        proof_obligation_graphs=[graph["pog"]],
        successor_sets=[graph["successors"]],
        frontiers=[graph["frontier"]],
        **kwargs,
    )


def _admit_identity_leaves(blocks: GraphHistoryBlockStore, identity: SemanticWorldRootIdentity) -> None:
    blocks.admit_subroot(identity.domain_state_cid, role="domain_state")
    blocks.admit_subroot(identity.semantic_object_index_cid, role="semantic_object_index")
    blocks.admit_subroot(identity.environment_binding_set_cid, role="environment_binding_set")
    blocks.admit_subroot(identity.policy_cid, role="policy")
    blocks.admit_subroot(identity.analysis_limitation_index_cid, role="analysis_limitation_index")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "semantic-world-history"


@pytest.fixture()
def coordination(store_dir: Path) -> DurableCoordinationStore:
    root = DurableCoordinationStore(store_dir)
    yield root
    root.close()


@pytest.fixture()
def blocks(coordination: DurableCoordinationStore) -> GraphHistoryBlockStore:
    store = GraphHistoryBlockStore(coordination)
    yield store
    store.close()


@pytest.fixture()
def graphs(blocks: GraphHistoryBlockStore) -> LogicalProgramGraphStore:
    return LogicalProgramGraphStore(blocks)


@pytest.fixture()
def transitions(blocks: GraphHistoryBlockStore) -> ProgramTransitionLog:
    return ProgramTransitionLog(blocks)


@pytest.fixture()
def snapshots(blocks: GraphHistoryBlockStore) -> SemanticWorldSnapshotStore:
    return SemanticWorldSnapshotStore(blocks)


# ---------------------------------------------------------------------------
# Interfaces / import safety
# ---------------------------------------------------------------------------


def test_public_interfaces_are_versioned() -> None:
    assert PROGRAM_GRAPH_HISTORY_INTERFACE == "ProgramGraphHistory@1"
    assert SEMANTIC_WORLD_ROOT_INTERFACE == "SemanticWorldRoot@1"
    assert LogicalProgramGraphStore.INTERFACE == PROGRAM_GRAPH_HISTORY_INTERFACE
    assert ProgramTransitionLog.INTERFACE == PROGRAM_GRAPH_HISTORY_INTERFACE
    assert SemanticWorldSnapshotStore.INTERFACE == PROGRAM_GRAPH_HISTORY_INTERFACE
    assert SemanticWorldRootManifest.INTERFACE == SEMANTIC_WORLD_ROOT_INTERFACE


def test_import_has_no_store_side_effects() -> None:
    env = os.environ.copy()
    env.update(_OPT_OUTS)
    script = (
        "import importlib, sys\n"
        f"mod = importlib.import_module({_PACKAGE_HISTORY!r})\n"
        f"roots = importlib.import_module({_PACKAGE_ROOTS!r})\n"
        "assert not hasattr(mod, '_STORE')\n"
        "print('ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[3]),
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_append_functions_are_public() -> None:
    assert inspect.isfunction(append_program_graph_snapshot)
    assert inspect.isfunction(append_transition_receipt)
    assert inspect.isfunction(build_world_root_manifest)


# ---------------------------------------------------------------------------
# Graph snapshots: cycles, store-before-reference, deltas, idempotency
# ---------------------------------------------------------------------------


def test_mutual_recursion_snapshot_keeps_physical_ipld_acyclic_and_cycles_queryable(
    graphs: LogicalProgramGraphStore,
) -> None:
    graph = _cyclic_graph()
    result = _append_graph(graphs, graph, operation_id="op-cycle-1")
    loaded = graphs.get_verified_snapshot(result.snapshot_cid)
    assert loaded.program_graph_snapshot_cid == graph["snapshot"].program_graph_snapshot_cid
    cycles = graphs.query_logical_cycles(result.snapshot_cid)
    assert cycles
    left = graph["edges"][4].program_graph_edge_cid
    right = graph["edges"][5].program_graph_edge_cid
    assert any(left in cycle and right in cycle for cycle in cycles)
    catalog = {
        graph["ping"].program_graph_node_cid: graph["ping"].identity_payload(),
        graph["pong"].program_graph_node_cid: graph["pong"].identity_payload(),
        graph["edges"][4].program_graph_edge_cid: graph["edges"][4].identity_payload(),
        graph["edges"][5].program_graph_edge_cid: graph["edges"][5].identity_payload(),
        loaded.program_graph_snapshot_cid: loaded.identity_payload(),
    }
    assert_physical_dag_acyclic(catalog)
    assert result.logical_cycle_edge_cids == cycles


def test_cfg_and_state_cycles_remain_queryable_on_acyclic_physical_dag(
    graphs: LogicalProgramGraphStore,
) -> None:
    entry = _node("cfg_block", "pkg.mod.loop.entry")
    body = _node("cfg_block", "pkg.mod.loop.body")
    forward = _edge("cfg_next", entry, body)
    back = _edge("cfg_next", body, entry, logical_cycle=True)
    snapshot = _assemble([entry, body], [forward, back])
    result = append_program_graph_snapshot(
        graphs,
        snapshot,
        nodes=[entry, body],
        edges=[forward, back],
        operation_id="op-cfg-cycle",
    )
    cycles = graphs.query_logical_cycles(result.snapshot_cid)
    assert any(back.program_graph_edge_cid in cycle for cycle in cycles)
    loaded = graphs.get_verified_snapshot(result.snapshot_cid)
    catalog = {
        entry.program_graph_node_cid: entry.identity_payload(),
        body.program_graph_node_cid: body.identity_payload(),
        forward.program_graph_edge_cid: forward.identity_payload(),
        back.program_graph_edge_cid: back.identity_payload(),
        loaded.program_graph_snapshot_cid: loaded.identity_payload(),
    }
    assert_physical_dag_acyclic(catalog)


def test_snapshot_without_stored_nodes_fails_closed(blocks: GraphHistoryBlockStore) -> None:
    ping = _node("function", "pkg.mod.ping")
    snapshot = _assemble([ping], [])
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        blocks.put_record(
            GraphHistoryKind.PROGRAM_GRAPH_SNAPSHOT,
            snapshot.to_dict(),
            expected_cid=snapshot.program_graph_snapshot_cid,
        )


def test_edge_without_stored_nodes_fails_closed(graphs: LogicalProgramGraphStore) -> None:
    ping = _node("function", "pkg.mod.ping")
    pong = _node("function", "pkg.mod.pong")
    edge = _edge("calls", ping, pong)
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        graphs.put_edge(edge)


def test_missing_and_corrupt_references_fail_closed(
    graphs: LogicalProgramGraphStore, blocks: GraphHistoryBlockStore
) -> None:
    missing = kit_cid_for_bytes(b"absent-graph-history", "raw")
    with pytest.raises(GraphHistoryNotFound):
        graphs.get_verified_snapshot(missing)
    ping = _node("function", "pkg.mod.ping")
    graphs.put_node(ping)
    result = graphs.put_node(_node("function", "pkg.mod.pong"))
    path = blocks.store._block_path(result.storage_cid)
    path.write_bytes(b'{"schema":"tampered","kind":"program_graph_node","payload":{}}')
    with pytest.raises(GraphHistoryIntegrityError):
        graphs.get_verified_node(result.cid)


def test_delta_preserves_unchanged_subroots_and_is_deterministic(
    graphs: LogicalProgramGraphStore,
) -> None:
    graph = _cyclic_graph()
    first = _append_graph(graphs, graph, operation_id="op-delta-prev")
    extra = _node("test", "pkg.mod.test_ping")
    current_nodes = [
        graph["module"],
        graph["ping"],
        graph["pong"],
        graph["ping_site"],
        graph["pong_site"],
        graph["obligation"],
        graph["contract_node"],
        graph["dynamic"],
        extra,
    ]
    current_edges = graph["edges"] + [_edge("tested_by", graph["ping"], extra)]
    current = _assemble(
        current_nodes,
        current_edges,
        callsites=[graph["ping_call"], graph["pong_call"]],
        function_symbols=[graph["ping_fn"], graph["pong_fn"]],
        contract_states=[graph["contract"]],
        proof_obligation_graphs=[graph["pog"]],
        successor_sets=[graph["successors"]],
        frontiers=[graph["frontier"]],
        retained_subroot_cids=[graph["module"].program_graph_node_cid],
        unavailable_dimensions=["reflection"],
    )
    second = append_program_graph_snapshot(
        graphs,
        current,
        nodes=current_nodes,
        edges=current_edges,
        callsites=[graph["ping_call"], graph["pong_call"]],
        function_symbols=[graph["ping_fn"], graph["pong_fn"]],
        contract_states=[graph["contract"]],
        proof_obligation_graphs=[graph["pog"]],
        successor_sets=[graph["successors"]],
        frontiers=[graph["frontier"]],
        previous_snapshot=graph["snapshot"],
        previous_entry_cid=first.history_entry_cid,
        operation_id="op-delta-next",
    )
    assert second.delta_cid is not None
    delta = graphs.get_verified_delta(second.delta_cid)
    assert extra.program_graph_node_cid in delta.added_node_cids
    assert graph["module"].program_graph_node_cid in delta.retained_subroot_cids
    assert graph["ping"].program_graph_node_cid in delta.retained_subroot_cids
    applied = apply_program_graph_delta(graph["snapshot"], delta)
    assert extra.program_graph_node_cid in applied["node_cids"]
    shuffled = ProgramGraphDelta(
        previous_snapshot_cid=delta.previous_snapshot_cid,
        added_node_cids=list(reversed(list(delta.added_node_cids))),
        removed_node_cids=list(reversed(list(delta.removed_node_cids))),
        added_edge_cids=list(reversed(list(delta.added_edge_cids))),
        removed_edge_cids=list(reversed(list(delta.removed_edge_cids))),
        retained_subroot_cids=list(reversed(list(delta.retained_subroot_cids))),
    )
    assert shuffled.program_graph_delta_cid == delta.program_graph_delta_cid
    again = append_program_graph_snapshot(
        graphs,
        current,
        nodes=current_nodes,
        edges=current_edges,
        callsites=[graph["ping_call"], graph["pong_call"]],
        function_symbols=[graph["ping_fn"], graph["pong_fn"]],
        contract_states=[graph["contract"]],
        proof_obligation_graphs=[graph["pog"]],
        successor_sets=[graph["successors"]],
        frontiers=[graph["frontier"]],
        previous_snapshot=graph["snapshot"],
        previous_entry_cid=first.history_entry_cid,
        operation_id="op-delta-next",
    )
    assert again.snapshot_cid == second.snapshot_cid
    assert again.history_entry_cid == second.history_entry_cid
    assert again.created is False
    assert again.reason_code == "unchanged"


def test_append_idempotency_and_operation_id_conflict(
    graphs: LogicalProgramGraphStore,
) -> None:
    graph = _cyclic_graph()
    first = _append_graph(graphs, graph, operation_id="op-idempotent")
    second = _append_graph(graphs, graph, operation_id="op-idempotent")
    assert first.snapshot_cid == second.snapshot_cid
    assert second.created is False
    other = _node("module", "pkg.other")
    other_snapshot = _assemble([other], [])
    with pytest.raises(GraphHistoryConflictError, match="operation_id"):
        append_program_graph_snapshot(
            graphs,
            other_snapshot,
            nodes=[other],
            edges=[],
            operation_id="op-idempotent",
        )


def test_deterministic_node_edge_ordering_in_snapshots(graphs: LogicalProgramGraphStore) -> None:
    left = _node("function", "pkg.mod.a")
    right = _node("function", "pkg.mod.b")
    edge = _edge("calls", left, right)
    first = _assemble([right, left], [edge])
    second = _assemble([left, right], [edge])
    assert first.program_graph_snapshot_cid == second.program_graph_snapshot_cid
    assert list(first.node_cids) == sorted(first.node_cids)
    result = append_program_graph_snapshot(
        graphs, first, nodes=[right, left], edges=[edge], operation_id="op-order"
    )
    loaded = graphs.get_verified_snapshot(result.snapshot_cid)
    assert list(loaded.node_cids) == list(first.node_cids)


# ---------------------------------------------------------------------------
# Transition log: prediction vs observation, receipts, history
# ---------------------------------------------------------------------------


def _admitted_bundle():
    query = _query()
    prediction = _prediction(query)
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
    receipt = issue_transition_receipt(
        query, admission, prediction=prediction, observation=observation
    )
    return query, prediction, observation, admission, receipt


def test_predictions_are_distinguishable_from_admitted_observations(
    transitions: ProgramTransitionLog,
) -> None:
    query, prediction, observation, admission, receipt = _admitted_bundle()
    result = append_transition_receipt(
        transitions,
        receipt,
        query=query,
        admission=admission,
        prediction=prediction,
        observation=observation,
        operation_id="op-receipt-1",
    )
    loaded_pred = transitions.get_verified_prediction(prediction.prediction_cid)
    loaded_obs = transitions.get_verified_observation(observation.observation_cid)
    assert loaded_pred.proposal_only is True
    assert loaded_obs.proposal_only is False
    assert loaded_pred.prediction_cid != loaded_obs.observation_cid
    with pytest.raises(GraphHistoryIntegrityError, match="wrong artifact kind"):
        transitions.get_verified_observation(prediction.prediction_cid)
    with pytest.raises(Exception, match="cannot decode as observations"):
        decode_transition_observation(loaded_pred.to_dict())
    loaded_receipt = transitions.get_verified_receipt(result.receipt_cid)
    assert loaded_receipt.observation_cid == observation.observation_cid
    assert loaded_receipt.prediction_cid == prediction.prediction_cid
    assert loaded_receipt.prediction_authoritative is False
    assert str(loaded_receipt.verdict) == AdmissionVerdict.ADMITTED.value


def test_prediction_cannot_self_admit_into_the_transition_log(
    transitions: ProgramTransitionLog,
) -> None:
    query = _query()
    prediction = _prediction(query)
    admission = admit_program_transition(
        query,
        current_subject_cid=query.subject_cid,
        current_source_cid=query.current_source_cid,
        current_environment_binding_cid=query.environment_binding_cid,
        current_state_cid=query.current_state_cid,
        prediction=prediction,
    )
    assert str(admission.verdict) != AdmissionVerdict.ADMITTED.value
    receipt = issue_transition_receipt(query, admission, prediction=prediction)
    assert receipt.observation_cid is None
    assert receipt.may_influence_planning is False
    result = append_transition_receipt(
        transitions,
        receipt,
        query=query,
        admission=admission,
        prediction=prediction,
        operation_id="op-pred-only",
    )
    loaded = transitions.get_verified_receipt(result.receipt_cid)
    assert loaded.observation_cid is None
    assert loaded.prediction_cid == prediction.prediction_cid
    assert loaded.may_influence_planning is False


def test_receipt_without_stored_query_fails_closed(blocks: GraphHistoryBlockStore) -> None:
    query, prediction, observation, admission, receipt = _admitted_bundle()
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        blocks.put_record(
            GraphHistoryKind.PROGRAM_TRANSITION_RECEIPT,
            receipt.to_dict(),
            expected_cid=receipt.receipt_cid,
        )
    del prediction, observation, admission, query


def test_repeated_state_keeps_distinct_transition_histories(
    transitions: ProgramTransitionLog,
) -> None:
    query, prediction, observation, admission, receipt = _admitted_bundle()
    first = append_transition_receipt(
        transitions,
        receipt,
        query=query,
        admission=admission,
        prediction=prediction,
        observation=observation,
        operation_id="op-hist-1",
    )
    second_query = _query(evidence_cids=[_cid("ev-2")])
    second_obs = _observation(second_query)
    second_pred = _prediction(second_query)
    second_admission = admit_program_transition(
        second_query,
        current_subject_cid=second_query.subject_cid,
        current_source_cid=second_query.current_source_cid,
        current_environment_binding_cid=second_query.environment_binding_cid,
        current_state_cid=second_query.current_state_cid,
        prediction=second_pred,
        observation=second_obs,
    )
    second_receipt = issue_transition_receipt(
        second_query,
        second_admission,
        prediction=second_pred,
        observation=second_obs,
    )
    second = append_transition_receipt(
        transitions,
        second_receipt,
        query=second_query,
        admission=second_admission,
        prediction=second_pred,
        observation=second_obs,
        previous_entry_cid=first.log_entry_cid,
        operation_id="op-hist-2",
    )
    assert second.log_entry_cid != first.log_entry_cid
    assert second.receipt_cid != first.receipt_cid
    entry = transitions.get_verified_log_entry(second.log_entry_cid)
    assert entry.previous_entry_cid == first.log_entry_cid
    assert entry.receipt_cid == second.receipt_cid


# ---------------------------------------------------------------------------
# World snapshots and traces
# ---------------------------------------------------------------------------


def test_repeated_state_distinct_event_histories(
    snapshots: SemanticWorldSnapshotStore, graphs: LogicalProgramGraphStore
) -> None:
    graph = _cyclic_graph()
    _append_graph(graphs, graph, operation_id="op-world-graph")
    first_event = _event("call")
    second_event = _event("return", predecessor=first_event.program_event_cid)
    first_trace = assemble_execution_trace(
        tree_cid=first_event.tree_cid,
        source_cid=first_event.source_cid,
        environment_binding_cid=first_event.environment_binding_cid,
        events=[first_event, second_event],
    )
    replay_first = _event("call")
    replay_second = _event(
        "return",
        predecessor=replay_first.program_event_cid,
        payload={"callee": "pkg.mod.pong", "replay": 1},
    )
    second_trace = assemble_execution_trace(
        tree_cid=replay_first.tree_cid,
        source_cid=replay_first.source_cid,
        environment_binding_cid=replay_first.environment_binding_cid,
        events=[replay_first, replay_second],
    )
    assert first_event.subject_cid == replay_first.subject_cid
    assert first_trace.execution_trace_cid != second_trace.execution_trace_cid
    snapshots.put_trace(first_trace, events=[first_event, second_event])
    snapshots.put_trace(second_trace, events=[replay_first, replay_second])
    world_a = SemanticWorldSnapshot(
        program_graph_snapshot_cid=graph["snapshot"].program_graph_snapshot_cid,
        domain_state_cid=_cid("state-current"),
        environment_binding_set_cid=_cid("bindings"),
        execution_trace_cids=[first_trace.execution_trace_cid],
        event_history_cids=[
            first_event.program_event_cid,
            second_event.program_event_cid,
        ],
    )
    world_b = SemanticWorldSnapshot(
        program_graph_snapshot_cid=graph["snapshot"].program_graph_snapshot_cid,
        domain_state_cid=_cid("state-current"),
        environment_binding_set_cid=_cid("bindings"),
        execution_trace_cids=[second_trace.execution_trace_cid],
        event_history_cids=[
            replay_first.program_event_cid,
            replay_second.program_event_cid,
        ],
    )
    assert world_a.world_snapshot_cid != world_b.world_snapshot_cid
    snapshots.append_world_snapshot(world_a, operation_id="op-world-a")
    snapshots.append_world_snapshot(world_b, operation_id="op-world-b")
    loaded_a = snapshots.get_verified_world_snapshot(world_a.world_snapshot_cid)
    loaded_b = snapshots.get_verified_world_snapshot(world_b.world_snapshot_cid)
    assert loaded_a.event_history_cids != loaded_b.event_history_cids
    assert loaded_a.program_graph_snapshot_cid == loaded_b.program_graph_snapshot_cid


def test_world_snapshot_without_stored_graph_fails_closed(
    snapshots: SemanticWorldSnapshotStore,
) -> None:
    world = SemanticWorldSnapshot(
        program_graph_snapshot_cid=_cid("missing-snapshot"),
        domain_state_cid=_cid("state-current"),
        environment_binding_set_cid=_cid("bindings"),
    )
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        snapshots.append_world_snapshot(world)


# ---------------------------------------------------------------------------
# World-root manifests
# ---------------------------------------------------------------------------


def _identity_for(snapshot: ProgramGraphSnapshot, **overrides: Any) -> SemanticWorldRootIdentity:
    fields: dict[str, Any] = {
        "domain_state_cid": _cid("state-current"),
        "canonical_program_graph_cid": snapshot.canonical_program_graph_cid,
        "program_graph_snapshot_cid": snapshot.program_graph_snapshot_cid,
        "semantic_object_index_cid": _cid("object-index"),
        "environment_binding_set_cid": snapshot.environment_binding_set_cid,
        "policy_cid": _cid("policy-v1"),
        "analysis_limitation_index_cid": _cid("limitations"),
    }
    fields.update(overrides)
    return SemanticWorldRootIdentity(**fields)


def test_world_root_binds_every_referenced_subroot_deterministically(
    graphs: LogicalProgramGraphStore,
    transitions: ProgramTransitionLog,
    snapshots: SemanticWorldSnapshotStore,
    blocks: GraphHistoryBlockStore,
) -> None:
    graph = _cyclic_graph()
    graph_result = _append_graph(graphs, graph, operation_id="op-root-graph")
    query, prediction, observation, admission, receipt = _admitted_bundle()
    receipt_result = append_transition_receipt(
        transitions,
        receipt,
        query=query,
        admission=admission,
        prediction=prediction,
        observation=observation,
        operation_id="op-root-receipt",
    )
    event = _event("observe")
    trace = assemble_execution_trace(
        tree_cid=event.tree_cid,
        source_cid=event.source_cid,
        environment_binding_cid=event.environment_binding_cid,
        events=[event],
    )
    snapshots.put_trace(trace, events=[event])
    world = SemanticWorldSnapshot(
        program_graph_snapshot_cid=graph["snapshot"].program_graph_snapshot_cid,
        domain_state_cid=_cid("state-current"),
        environment_binding_set_cid=graph["snapshot"].environment_binding_set_cid,
        execution_trace_cids=[trace.execution_trace_cid],
        transition_receipt_cids=[receipt.receipt_cid],
        event_history_cids=[event.program_event_cid],
    )
    snapshots.append_world_snapshot(world, operation_id="op-root-world")
    identity = _identity_for(graph["snapshot"])
    _admit_identity_leaves(blocks, identity)
    first = build_world_root_manifest(
        blocks,
        identity=identity,
        world_snapshot_cid=world.world_snapshot_cid,
        graph_history_entry_cid=graph_result.history_entry_cid,
        transition_log_entry_cid=receipt_result.log_entry_cid,
        transition_receipt_cids=[receipt.receipt_cid],
        execution_trace_cids=[trace.execution_trace_cid],
        operation_id="op-root-1",
    )
    assert first.generation == 1
    assert first.INTERFACE == SEMANTIC_WORLD_ROOT_INTERFACE
    expected = collect_world_root_subroots(
        identity,
        world_snapshot_cid=world.world_snapshot_cid,
        graph_history_entry_cid=graph_result.history_entry_cid,
        transition_log_entry_cid=receipt_result.log_entry_cid,
        transition_receipt_cids=[receipt.receipt_cid],
        execution_trace_cids=[trace.execution_trace_cid],
    )
    assert tuple(first.subroot_cids) == expected
    assert list(first.subroot_cids) == sorted(first.subroot_cids)
    for cid in first.subroot_cids:
        assert blocks.has_identity(cid)
    loaded = get_verified_world_root_manifest(blocks, first.world_root_manifest_cid)
    assert loaded.world_root_manifest_cid == first.world_root_manifest_cid
    assert loaded.semantic_world_root_cid == identity.semantic_world_root_cid
    shuffled_receipts = [receipt.receipt_cid]
    again = build_world_root_manifest(
        blocks,
        identity=identity,
        world_snapshot_cid=world.world_snapshot_cid,
        graph_history_entry_cid=graph_result.history_entry_cid,
        transition_log_entry_cid=receipt_result.log_entry_cid,
        transition_receipt_cids=shuffled_receipts,
        execution_trace_cids=[trace.execution_trace_cid],
        persist=False,
    )
    assert again.world_root_manifest_cid == first.world_root_manifest_cid


def test_world_root_delta_retains_unchanged_subroots(
    graphs: LogicalProgramGraphStore, blocks: GraphHistoryBlockStore
) -> None:
    graph = _cyclic_graph()
    first_graph = _append_graph(graphs, graph, operation_id="op-root-delta-graph")
    identity = _identity_for(graph["snapshot"])
    _admit_identity_leaves(blocks, identity)
    first = build_world_root_manifest(
        blocks,
        identity=identity,
        graph_history_entry_cid=first_graph.history_entry_cid,
        operation_id="op-root-gen-1",
    )
    extra = _node("test", "pkg.mod.test_ping")
    current_nodes = [
        graph["module"],
        graph["ping"],
        graph["pong"],
        graph["ping_site"],
        graph["pong_site"],
        graph["obligation"],
        graph["contract_node"],
        graph["dynamic"],
        extra,
    ]
    current_edges = graph["edges"] + [_edge("tested_by", graph["ping"], extra)]
    current = _assemble(
        current_nodes,
        current_edges,
        callsites=[graph["ping_call"], graph["pong_call"]],
        function_symbols=[graph["ping_fn"], graph["pong_fn"]],
        contract_states=[graph["contract"]],
        proof_obligation_graphs=[graph["pog"]],
        successor_sets=[graph["successors"]],
        frontiers=[graph["frontier"]],
        retained_subroot_cids=[graph["module"].program_graph_node_cid],
        unavailable_dimensions=["reflection"],
    )
    second_graph = append_program_graph_snapshot(
        graphs,
        current,
        nodes=current_nodes,
        edges=current_edges,
        callsites=[graph["ping_call"], graph["pong_call"]],
        function_symbols=[graph["ping_fn"], graph["pong_fn"]],
        contract_states=[graph["contract"]],
        proof_obligation_graphs=[graph["pog"]],
        successor_sets=[graph["successors"]],
        frontiers=[graph["frontier"]],
        previous_snapshot=graph["snapshot"],
        previous_entry_cid=first_graph.history_entry_cid,
        operation_id="op-root-delta-graph-2",
    )
    next_identity = _identity_for(current)
    blocks.admit_subroot(next_identity.domain_state_cid, role="domain_state")
    blocks.admit_subroot(next_identity.semantic_object_index_cid, role="semantic_object_index")
    blocks.admit_subroot(next_identity.policy_cid, role="policy")
    blocks.admit_subroot(
        next_identity.analysis_limitation_index_cid, role="analysis_limitation_index"
    )
    second = build_world_root_manifest(
        blocks,
        identity=next_identity,
        previous_manifest=first,
        graph_history_entry_cid=second_graph.history_entry_cid,
        operation_id="op-root-gen-2",
    )
    assert second.generation == 2
    assert second.previous_manifest_cid == first.world_root_manifest_cid
    assert first.identity.environment_binding_set_cid in second.retained_subroot_cids
    assert current.program_graph_snapshot_cid in second.subroot_cids
    assert current.program_graph_snapshot_cid not in second.retained_subroot_cids
    assert graph["snapshot"].program_graph_snapshot_cid not in second.subroot_cids
    loaded = get_verified_world_root_manifest(blocks, second.world_root_manifest_cid)
    assert loaded.retained_subroot_cids == second.retained_subroot_cids


def test_world_root_missing_subroot_fails_closed(
    graphs: LogicalProgramGraphStore, blocks: GraphHistoryBlockStore
) -> None:
    graph = _cyclic_graph()
    _append_graph(graphs, graph, operation_id="op-root-missing-graph")
    identity = _identity_for(graph["snapshot"])
    with pytest.raises(GraphHistoryAdmissionError, match="store-before-reference"):
        build_world_root_manifest(blocks, identity=identity)


def test_world_root_append_idempotency(
    graphs: LogicalProgramGraphStore, blocks: GraphHistoryBlockStore
) -> None:
    graph = _cyclic_graph()
    graph_result = _append_graph(graphs, graph, operation_id="op-root-id-graph")
    identity = _identity_for(graph["snapshot"])
    _admit_identity_leaves(blocks, identity)
    first = build_world_root_manifest(
        blocks,
        identity=identity,
        graph_history_entry_cid=graph_result.history_entry_cid,
        operation_id="op-root-id",
    )
    second = build_world_root_manifest(
        blocks,
        identity=identity,
        graph_history_entry_cid=graph_result.history_entry_cid,
        operation_id="op-root-id",
    )
    assert first.world_root_manifest_cid == second.world_root_manifest_cid
    other = _identity_for(graph["snapshot"], policy_cid=_cid("policy-other"))
    _admit_identity_leaves(blocks, other)
    with pytest.raises(GraphHistoryConflictError, match="operation_id"):
        build_world_root_manifest(
            blocks,
            identity=other,
            graph_history_entry_cid=graph_result.history_entry_cid,
            operation_id="op-root-id",
        )


def test_world_root_generation_and_physical_back_edge(
    graphs: LogicalProgramGraphStore, blocks: GraphHistoryBlockStore
) -> None:
    graph = _cyclic_graph()
    graph_result = _append_graph(graphs, graph, operation_id="op-root-gen-graph")
    identity = _identity_for(graph["snapshot"])
    _admit_identity_leaves(blocks, identity)
    with pytest.raises(WorldRootError, match="generation-1"):
        SemanticWorldRootManifest(
            generation=1,
            identity=identity,
            previous_manifest_cid=graph_result.history_entry_cid,
            subroot_cids=collect_world_root_subroots(identity),
        )
    first = build_world_root_manifest(
        blocks,
        identity=identity,
        graph_history_entry_cid=graph_result.history_entry_cid,
        operation_id="op-root-first",
    )
    with pytest.raises(WorldRootError, match="exactly one greater"):
        build_world_root_manifest(
            blocks,
            identity=identity,
            generation=3,
            previous_manifest=first,
            graph_history_entry_cid=graph_result.history_entry_cid,
            persist=False,
        )


def test_restart_rereads_graph_history_and_roots(
    store_dir: Path,
) -> None:
    graph = _cyclic_graph()
    snapshot_cid: str
    manifest_cid: str
    with DurableCoordinationStore(store_dir) as coordination:
        with GraphHistoryBlockStore(coordination) as blocks:
            graphs = LogicalProgramGraphStore(blocks)
            result = _append_graph(graphs, graph, operation_id="op-reopen-graph")
            snapshot_cid = result.snapshot_cid
            identity = _identity_for(graph["snapshot"])
            _admit_identity_leaves(blocks, identity)
            manifest = build_world_root_manifest(
                blocks,
                identity=identity,
                graph_history_entry_cid=result.history_entry_cid,
                operation_id="op-reopen-root",
            )
            manifest_cid = manifest.world_root_manifest_cid
    with DurableCoordinationStore(store_dir) as coordination:
        with GraphHistoryBlockStore(coordination) as blocks:
            graphs = LogicalProgramGraphStore(blocks)
            loaded_snapshot = graphs.get_verified_snapshot(snapshot_cid)
            assert loaded_snapshot.program_graph_snapshot_cid == snapshot_cid
            loaded_manifest = get_verified_world_root_manifest(blocks, manifest_cid)
            assert loaded_manifest.world_root_manifest_cid == manifest_cid
            cycles = graphs.query_logical_cycles(snapshot_cid)
            assert cycles


def test_kit_does_not_accept_semantics_on_storage_success(
    graphs: LogicalProgramGraphStore,
) -> None:
    graph = _cyclic_graph()
    result = _append_graph(graphs, graph, operation_id="op-no-accept")
    loaded = graphs.get_verified_snapshot(result.snapshot_cid)
    assert loaded.program_graph_snapshot_cid == result.snapshot_cid
    source = inspect.getsource(LogicalProgramGraphStore.append_program_graph_snapshot)
    assert "may_influence_planning" not in source
    roots_source = inspect.getsource(build_world_root_manifest)
    assert "compare_and_swap_state_root" not in roots_source
    assert "current_state_root" not in roots_source
