"""Fail-closed vectors for world-root CAS, recovery, replication, and VFS outbox."""

from __future__ import annotations

import importlib
import inspect
import json
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

from ipfs_datasets_py.logic.software_contracts.content import cid_for_bytes
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_graph import (
    ProgramGraphNode,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    SemanticWorldRootIdentity,
)
from ipfs_kit_py.core.vfs.contracts import VFSOperationKind
from ipfs_kit_py.core.vfs.service import VFSExecuteRequest, make_op
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ROOT_CAS_INTERRUPTION_POINTS,
    DurableCoordinationStore,
    cid_for_artifact,
    cid_for_bytes as kit_cid_for_bytes,
)
from ipfs_kit_py.mcp_server.mcplusplus.state_root_contracts import (
    ProviderStatus,
    RootUpdateStatus,
)
from ipfs_kit_py.semantic_world_store import (
    SEMANTIC_OUTBOX_INTERFACE,
    SEMANTIC_WORLD_RECOVERY_INTERFACE,
    SEMANTIC_WORLD_ROOT_CAS_INTERFACE,
    SEMANTIC_WORLD_STORE_INTERFACE,
    SemanticWorldRecovery,
    SemanticWorldReplicationAdapter,
    SemanticWorldRootRepository,
    SemanticWorldStore,
    VFSSemanticOutbox,
    compare_and_swap_world_root,
    publish_vfs_semantic_outbox,
    replay_semantic_world_wal,
    replicate_semantic_blocks,
)
from ipfs_kit_py.semantic_world_store.graph_history import (
    LogicalProgramGraphStore,
    append_program_graph_snapshot,
)
from ipfs_kit_py.semantic_world_store.recovery import (
    SemanticWorldCASAdmissionError,
    SemanticWorldReplicationError,
    WorldRootCASResult,
    WorldRootSnapshot,
)
from ipfs_kit_py.semantic_world_store.vfs_outbox import (
    SemanticOutboxAdmissionError,
    VFSOutboxResult,
)
from ipfs_kit_py.semantic_world_store.world_roots import (
    SemanticWorldSnapshotStore,
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


def _binding(graph: LogicalProgramGraphStore, label: str) -> str:
    return graph.put_opaque_subroot(label).cid


def _identity_for_snapshot(
    graph: LogicalProgramGraphStore, snapshot: Any, **overrides: Any
) -> SemanticWorldRootIdentity:
    fields: dict[str, Any] = {
        "domain_state_cid": _binding(graph, f"domain-{overrides.pop('suffix', 'a')}"),
        "canonical_program_graph_cid": snapshot.canonical_program_graph_cid,
        "program_graph_snapshot_cid": snapshot.program_graph_snapshot_cid,
        "semantic_object_index_cid": _binding(graph, "objects"),
        "environment_binding_set_cid": snapshot.environment_binding_set_cid,
        "policy_cid": _binding(graph, "policy"),
        "analysis_limitation_index_cid": _binding(graph, "limits"),
    }
    fields.update(overrides)
    return SemanticWorldRootIdentity(**fields)


def _graph_bundle(store: DurableCoordinationStore) -> tuple[
    LogicalProgramGraphStore, SemanticWorldSnapshotStore
]:
    graph = LogicalProgramGraphStore(store)
    roots = SemanticWorldSnapshotStore(graph.blocks, graph_store=graph)
    return graph, roots


def _manifest(
    store: DurableCoordinationStore,
    *,
    label: str,
    previous_manifest_cid: str | None = None,
    generation: int | None = None,
) -> Any:
    graph, roots = _graph_bundle(store)
    ping = _node("function", f"pkg.mod.{label}")
    snap = append_program_graph_snapshot(
        graph,
        nodes=[ping],
        edges=[],
        environment_binding_set_cid=_binding(graph, f"{label}-bind"),
        sealed_binding_cid=_binding(graph, f"{label}-seal"),
    )
    snapshot = graph.get_verified_snapshot(snap.cid)
    return build_world_root_manifest(
        roots,
        identity=_identity_for_snapshot(graph, snapshot, suffix=label),
        graph_history_head_cid=snap.history_entry_cid,
        previous_manifest_cid=previous_manifest_cid,
        generation=generation,
        operation_id=f"op-manifest-{label}",
    )


class InjectedInterruption(RuntimeError):
    """A recoverable stand-in for a process stopping at a durable boundary."""


class _MemoryBlockBackend:
    """In-process replica that preserves CID identity.  Not a network backend."""

    def __init__(self) -> None:
        self.blocks: dict[str, bytes] = {}

    def store_block(self, cid: str, data: bytes, codec: str) -> str:
        del codec
        self.blocks[cid] = data
        return cid

    def load_block(self, cid: str) -> bytes:
        return self.blocks[cid]


@pytest.fixture()
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "semantic-world-recovery"


@pytest.fixture()
def coordination(store_dir: Path) -> DurableCoordinationStore:
    root = DurableCoordinationStore(store_dir)
    yield root
    root.close()


# ---------------------------------------------------------------------------
# Cold import / interfaces / no second engine
# ---------------------------------------------------------------------------


def test_cold_import_of_declared_modules() -> None:
    for name in list(sys.modules):
        if "semantic_world_store" in name:
            del sys.modules[name]
    recovery = importlib.import_module("ipfs_kit_py.semantic_world_store.recovery")
    outbox = importlib.import_module("ipfs_kit_py.semantic_world_store.vfs_outbox")
    facade = importlib.import_module("ipfs_kit_py.semantic_world_store")
    assert recovery.SEMANTIC_WORLD_ROOT_CAS_INTERFACE == "SemanticWorldRootCAS@1"
    assert recovery.SEMANTIC_WORLD_RECOVERY_INTERFACE == "SemanticWorldRecovery@1"
    assert outbox.SEMANTIC_OUTBOX_INTERFACE == "SemanticOutbox@1"
    assert facade.SEMANTIC_WORLD_STORE_INTERFACE == "SemanticWorldStore@1"
    assert callable(recovery.compare_and_swap_world_root)
    assert callable(recovery.replay_semantic_world_wal)
    assert callable(recovery.replicate_semantic_blocks)
    assert callable(outbox.publish_vfs_semantic_outbox)
    assert facade.compare_and_swap_world_root is recovery.compare_and_swap_world_root
    assert facade.publish_vfs_semantic_outbox is outbox.publish_vfs_semantic_outbox


def test_module_interfaces_are_versioned() -> None:
    assert SEMANTIC_WORLD_ROOT_CAS_INTERFACE == "SemanticWorldRootCAS@1"
    assert SEMANTIC_WORLD_RECOVERY_INTERFACE == "SemanticWorldRecovery@1"
    assert SEMANTIC_OUTBOX_INTERFACE == "SemanticOutbox@1"
    assert SEMANTIC_WORLD_STORE_INTERFACE == "SemanticWorldStore@1"
    assert SemanticWorldRootRepository.INTERFACE == "SemanticWorldRootCAS@1"
    assert SemanticWorldRecovery.INTERFACE == "SemanticWorldRecovery@1"
    assert VFSSemanticOutbox.INTERFACE == "SemanticOutbox@1"
    assert SemanticWorldReplicationAdapter.INTERFACE == "SemanticWorldReplication@1"
    assert SemanticWorldStore.INTERFACE == "SemanticWorldStore@1"


def test_recovery_extends_landed_cas_wal_vfs_not_a_second_engine() -> None:
    recovery_source = Path(
        inspect.getsourcefile(SemanticWorldRootRepository)
    ).read_text(encoding="utf-8")
    outbox_source = Path(inspect.getsourcefile(VFSSemanticOutbox)).read_text(
        encoding="utf-8"
    )
    assert "DurableCoordinationStore" in recovery_source
    assert "compare_and_swap_state_root" in recovery_source
    assert "from ipfs_kit_py.core.wal" in recovery_source
    assert "WALRecovery" in recovery_source
    assert "def _varint" not in recovery_source
    assert "base64.b32encode" not in recovery_source
    assert "CREATE TABLE IF NOT EXISTS state_roots" not in recovery_source
    assert "from ipfs_kit_py.core.vfs" in outbox_source
    assert "CanonicalVFSService" in outbox_source
    assert "supervisor_accepted" in recovery_source
    assert "supervisor_accepted" in outbox_source


def test_supervisor_acceptance_cannot_be_claimed() -> None:
    namespace = "semantic-world/default"
    empty = WorldRootSnapshot(namespace, None, 0, None, False)
    with pytest.raises(SemanticWorldCASAdmissionError, match="supervisor"):
        WorldRootSnapshot(namespace, None, 0, None, True)
    with pytest.raises(SemanticWorldCASAdmissionError, match="supervisor"):
        WorldRootCASResult(
            RootUpdateStatus.UNCHANGED,
            empty,
            empty,
            None,
            "idempotent_replay",
            True,
            False,
            "op-x",
            True,
        )
    with pytest.raises(SemanticOutboxAdmissionError, match="supervisor"):
        VFSOutboxResult(
            path="outbox/world-root",
            root_cid=cid_for_artifact({"schema": "example/state@1", "n": 1}),
            generation=1,
            vfs_success=True,
            durable_file_mutated=True,
            reason_code="published",
            operation_id="op-outbox",
            supervisor_accepted=True,
        )


# ---------------------------------------------------------------------------
# Generation CAS: one successor, stale writers, ABA
# ---------------------------------------------------------------------------


def test_one_expected_generation_admits_at_most_one_successor(
    coordination: DurableCoordinationStore,
) -> None:
    first = _manifest(coordination, label="alpha")
    second = _manifest(coordination, label="beta")
    repo = SemanticWorldRootRepository(coordination)
    updated = repo.compare_and_swap_world_root(
        expected_generation=0,
        expected_root_cid=None,
        new_root_cid=first.world_root_manifest_cid,
        operation_id="publish-alpha",
    )
    conflict = repo.compare_and_swap_world_root(
        expected_generation=0,
        expected_root_cid=None,
        new_root_cid=second.world_root_manifest_cid,
        operation_id="publish-beta",
    )
    assert updated.status is RootUpdateStatus.UPDATED
    assert updated.after.generation == 1
    assert updated.after.root_cid == first.world_root_manifest_cid
    assert updated.supervisor_accepted is False
    assert conflict.status is RootUpdateStatus.CONFLICT
    assert conflict.reason_code == "stale_expectation"
    assert conflict.after.root_cid == first.world_root_manifest_cid
    assert conflict.supervisor_accepted is False
    current = repo.current_world_root()
    assert current.root_cid == first.world_root_manifest_cid
    successors = [
        row
        for row in coordination.root_transitions(current.namespace)
        if int(row["expected_revision"]) == 0
    ]
    assert len(successors) == 1
    assert successors[0]["new_root_cid"] == first.world_root_manifest_cid


def test_stale_writer_conflicts_after_generation_advances(
    coordination: DurableCoordinationStore,
) -> None:
    first = _manifest(coordination, label="one")
    repo = SemanticWorldRootRepository(coordination)
    updated = compare_and_swap_world_root(
        repo,
        expected_generation=0,
        expected_root_cid=None,
        new_root_cid=first.world_root_manifest_cid,
        operation_id="cas-one",
    )
    stale = compare_and_swap_world_root(
        repo,
        expected_generation=0,
        expected_root_cid=None,
        new_root_cid=first.world_root_manifest_cid,
        operation_id="cas-stale",
    )
    assert updated.status is RootUpdateStatus.UPDATED
    assert stale.status is RootUpdateStatus.CONFLICT
    assert repo.current_world_root().generation == 1


def test_aba_safe_expected_generation_and_cid_pair(
    coordination: DurableCoordinationStore,
) -> None:
    first = _manifest(coordination, label="gen1")
    repo = SemanticWorldRootRepository(coordination)
    first_cas = repo.compare_and_swap_world_root(
        expected_generation=0,
        expected_root_cid=None,
        new_root_cid=first.world_root_manifest_cid,
        operation_id="cas-gen1",
    )
    second = _manifest(
        coordination,
        label="gen2",
        previous_manifest_cid=first.world_root_manifest_cid,
    )
    second_cas = repo.compare_and_swap_world_root(
        expected_generation=1,
        expected_root_cid=first.world_root_manifest_cid,
        new_root_cid=second.world_root_manifest_cid,
        operation_id="cas-gen2",
    )
    assert first_cas.status is RootUpdateStatus.UPDATED
    assert second_cas.status is RootUpdateStatus.UPDATED
    assert second_cas.after.generation == 2
    aba = repo.compare_and_swap_world_root(
        expected_generation=0,
        expected_root_cid=None,
        new_root_cid=first.world_root_manifest_cid,
        operation_id="cas-aba",
    )
    assert aba.status is RootUpdateStatus.CONFLICT
    assert repo.current_world_root().root_cid == second.world_root_manifest_cid
    alt = _manifest(coordination, label="alt")
    wrong = _manifest(
        coordination,
        label="wrong-pred",
        previous_manifest_cid=alt.world_root_manifest_cid,
    )
    with pytest.raises(SemanticWorldCASAdmissionError, match="predecessor"):
        repo.compare_and_swap_world_root(
            expected_generation=1,
            expected_root_cid=first.world_root_manifest_cid,
            new_root_cid=wrong.world_root_manifest_cid,
            operation_id="cas-wrong-predecessor",
        )


def test_concurrent_writers_admit_one_successor(
    coordination: DurableCoordinationStore,
) -> None:
    left = _manifest(coordination, label="left")
    right = _manifest(coordination, label="right")
    repo = SemanticWorldRootRepository(coordination)
    barrier = threading.Barrier(2, timeout=5)
    outcomes: list[WorldRootCASResult] = []
    lock = threading.Lock()

    def publish(manifest_cid: str, operation_id: str) -> None:
        barrier.wait()
        result = repo.compare_and_swap_world_root(
            expected_generation=0,
            expected_root_cid=None,
            new_root_cid=manifest_cid,
            operation_id=operation_id,
        )
        with lock:
            outcomes.append(result)

    threads = [
        threading.Thread(target=publish, args=(left.world_root_manifest_cid, "writer-left")),
        threading.Thread(target=publish, args=(right.world_root_manifest_cid, "writer-right")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
        assert not thread.is_alive()
    statuses = {item.status for item in outcomes}
    assert RootUpdateStatus.UPDATED in statuses
    assert RootUpdateStatus.CONFLICT in statuses
    updated = [item for item in outcomes if item.status is RootUpdateStatus.UPDATED]
    assert len(updated) == 1
    current = repo.current_world_root()
    assert current.generation == 1
    assert current.root_cid == updated[0].after.root_cid
    assert all(item.supervisor_accepted is False for item in outcomes)


def test_idempotent_operation_id_replay_does_not_fork(
    coordination: DurableCoordinationStore,
) -> None:
    first = _manifest(coordination, label="idem")
    repo = SemanticWorldRootRepository(coordination)
    first_cas = repo.compare_and_swap_world_root(
        expected_generation=0,
        expected_root_cid=None,
        new_root_cid=first.world_root_manifest_cid,
        operation_id="op-idempotent",
    )
    replay = repo.compare_and_swap_world_root(
        expected_generation=0,
        expected_root_cid=None,
        new_root_cid=first.world_root_manifest_cid,
        operation_id="op-idempotent",
    )
    assert first_cas.status is RootUpdateStatus.UPDATED
    assert replay.status is RootUpdateStatus.UNCHANGED
    assert replay.reason_code == "idempotent_replay"
    assert repo.current_world_root().generation == 1


def test_generation_mismatch_is_refused_before_cas(
    coordination: DurableCoordinationStore,
) -> None:
    first = _manifest(coordination, label="mismatch")
    repo = SemanticWorldRootRepository(coordination)
    with pytest.raises(SemanticWorldCASAdmissionError, match="generation"):
        repo.compare_and_swap_world_root(
            expected_generation=2,
            expected_root_cid=first.world_root_manifest_cid,
            new_root_cid=first.world_root_manifest_cid,
            operation_id="bad-generation",
        )


# ---------------------------------------------------------------------------
# Crash window, restart, WAL replay, corrupt present
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("boundary", ROOT_CAS_INTERRUPTION_POINTS)
def test_crash_window_recovers_one_valid_root(tmp_path: Path, boundary: str) -> None:
    root = tmp_path / boundary

    def interrupt(point: str) -> None:
        if point == boundary:
            raise InjectedInterruption(point)

    with DurableCoordinationStore(root, crash_injector=interrupt) as store:
        successor = _manifest(store, label=f"crash-{boundary}")
        cid = successor.world_root_manifest_cid
        repo = SemanticWorldRootRepository(store)
        with pytest.raises(InjectedInterruption, match=boundary):
            repo.compare_and_swap_world_root(
                expected_generation=0,
                expected_root_cid=None,
                new_root_cid=cid,
                operation_id="interrupted-publish",
            )

    with DurableCoordinationStore(root) as recovered:
        recovery = SemanticWorldRecovery(recovered)
        report = recovery.recover()
        assert report.supervisor_accepted is False
        assert report.errors == ()
        current = recovery.repository.current_world_root()
        if boundary in {"before_transaction", "after_expectation_verification"}:
            assert current.generation == 0
            assert current.root_cid is None
            replay = recovery.repository.compare_and_swap_world_root(
                expected_generation=0,
                expected_root_cid=None,
                new_root_cid=cid,
                operation_id="interrupted-publish",
            )
            assert replay.status is RootUpdateStatus.UPDATED
        else:
            assert current.generation == 1
            assert current.root_cid == cid
            replay = recovery.repository.compare_and_swap_world_root(
                expected_generation=0,
                expected_root_cid=None,
                new_root_cid=cid,
                operation_id="interrupted-publish",
            )
            assert replay.status is RootUpdateStatus.UNCHANGED
        visible = recovery.repository.current_world_root()
        assert visible.generation == 1
        assert visible.root_cid == cid
        assert len(report.reconstructed_roots) <= 1


def test_restart_exposes_one_valid_root(tmp_path: Path) -> None:
    root = tmp_path / "restart"
    with DurableCoordinationStore(root) as store:
        first = _manifest(store, label="live")
        repo = SemanticWorldRootRepository(store)
        result = repo.compare_and_swap_world_root(
            expected_generation=0,
            expected_root_cid=None,
            new_root_cid=first.world_root_manifest_cid,
            operation_id="publish-live",
        )
        assert result.status is RootUpdateStatus.UPDATED
        cid = first.world_root_manifest_cid

    with DurableCoordinationStore(root) as recovered:
        recovery = SemanticWorldRecovery(recovered)
        report = recovery.recover()
        assert report.errors == ()
        assert len(report.reconstructed_roots) == 1
        snapshot = report.reconstructed_roots[0]
        assert snapshot.generation == 1
        assert snapshot.root_cid == cid
        assert snapshot.supervisor_accepted is False
        assert recovery.repository.current_world_root().root_cid == cid
        wal = replay_semantic_world_wal(recovery)
        assert snapshot.root_cid == cid
        assert wal.replayed_count in {0, 1}


def test_wal_replay_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "wal-replay"
    with DurableCoordinationStore(root) as store:
        first = _manifest(store, label="wal")
        recovery = SemanticWorldRecovery(store)
        recovery.repository.compare_and_swap_world_root(
            expected_generation=0,
            expected_root_cid=None,
            new_root_cid=first.world_root_manifest_cid,
            operation_id="wal-publish",
        )
        first_replay = recovery.replay_semantic_world_wal()
        second_replay = recovery.replay_semantic_world_wal()
        assert recovery.repository.current_world_root().generation == 1
        assert first_replay.replayed_count + second_replay.replayed_count == 1
        assert second_replay.skipped_effect_keys


def test_corrupt_present_block_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "corrupt"
    with DurableCoordinationStore(root) as store:
        first = _manifest(store, label="corrupt")
        repo = SemanticWorldRootRepository(store)
        repo.compare_and_swap_world_root(
            expected_generation=0,
            expected_root_cid=None,
            new_root_cid=first.world_root_manifest_cid,
            operation_id="publish-corrupt",
        )
        path = store._block_path(first.world_root_manifest_cid)
        path.write_bytes(b'{"schema":"tampered","kind":"world_root_manifest","payload":{}}')
        report = SemanticWorldRecovery(store).recover()
        assert report.reconstructed_roots == ()
        assert report.errors
        assert report.errors[0]["code"] == "corrupt"
        assert report.supervisor_accepted is False


# ---------------------------------------------------------------------------
# VFS post-commit outbox
# ---------------------------------------------------------------------------


def test_vfs_outbox_is_post_commit_and_not_supervisor_acceptance(
    coordination: DurableCoordinationStore,
) -> None:
    first = _manifest(coordination, label="vfs")
    store = SemanticWorldStore(coordination)
    with pytest.raises(SemanticOutboxAdmissionError, match="post-commit"):
        store.publish_vfs_semantic_outbox(
            root_cid=first.world_root_manifest_cid,
            operation_id="outbox-early",
        )
    cas = store.compare_and_swap_world_root(
        expected_generation=0,
        expected_root_cid=None,
        new_root_cid=first.world_root_manifest_cid,
        operation_id="cas-vfs",
    )
    assert cas.supervisor_accepted is False
    published = publish_vfs_semantic_outbox(
        store.outbox,
        root_cid=first.world_root_manifest_cid,
        operation_id="outbox-commit",
        cas_result=cas,
    )
    assert published.vfs_success is True
    assert published.durable_file_mutated is True
    assert published.supervisor_accepted is False
    assert published.generation == 1
    assert store.outbox.read_published() == first.world_root_manifest_cid.encode("utf-8")
    other = _manifest(coordination, label="not-current")
    with pytest.raises(SemanticOutboxAdmissionError, match="post-commit"):
        store.publish_vfs_semantic_outbox(
            root_cid=other.world_root_manifest_cid,
            operation_id="outbox-stale",
        )


def test_durable_file_mutation_never_equals_supervisor_acceptance(
    coordination: DurableCoordinationStore,
) -> None:
    first = _manifest(coordination, label="mutate")
    repo = SemanticWorldRootRepository(coordination)
    cas = repo.compare_and_swap_world_root(
        expected_generation=0,
        expected_root_cid=None,
        new_root_cid=first.world_root_manifest_cid,
        operation_id="cas-mutate",
    )
    outbox = VFSSemanticOutbox(repo)
    published = outbox.publish_vfs_semantic_outbox(
        root_cid=first.world_root_manifest_cid,
        operation_id="outbox-mutate",
        cas_result=cas,
    )
    assert published.durable_file_mutated is True
    assert published.supervisor_accepted is False
    mutated = outbox.vfs.execute(
        make_op(
            VFSOperationKind.REPLACE,
            operation_id="tamper-outbox",
            path=outbox.path,
        ),
        VFSExecuteRequest(payload=b"tampered-file-bytes"),
    )
    assert mutated.success is True
    assert outbox.read_published() == b"tampered-file-bytes"
    current = repo.current_world_root()
    assert current.root_cid == first.world_root_manifest_cid
    assert current.supervisor_accepted is False
    spilled = coordination.root / "spilled-acceptance.json"
    spilled.write_text(json.dumps({"accepted": True}), encoding="utf-8")
    assert spilled.is_file()
    assert repo.current_world_root().supervisor_accepted is False
    assert cas.supervisor_accepted is False


def test_vfs_post_commit_order_is_cas_then_outbox(
    coordination: DurableCoordinationStore,
) -> None:
    first = _manifest(coordination, label="order")
    repo = SemanticWorldRootRepository(coordination)
    outbox = VFSSemanticOutbox(repo)
    order: list[str] = []
    with pytest.raises(SemanticOutboxAdmissionError):
        order.append("outbox")
        outbox.publish_vfs_semantic_outbox(
            root_cid=first.world_root_manifest_cid,
            operation_id="outbox-before-cas",
        )
    order.append("cas")
    cas = repo.compare_and_swap_world_root(
        expected_generation=0,
        expected_root_cid=None,
        new_root_cid=first.world_root_manifest_cid,
        operation_id="cas-order",
    )
    order.append("outbox")
    published = outbox.publish_vfs_semantic_outbox(
        root_cid=cas.after.root_cid or first.world_root_manifest_cid,
        operation_id="outbox-after-cas",
        cas_result=cas,
    )
    assert order == ["outbox", "cas", "outbox"]
    assert published.durable_file_mutated is True
    assert published.supervisor_accepted is False


# ---------------------------------------------------------------------------
# Replication identity / typed unavailable
# ---------------------------------------------------------------------------


def test_typed_unavailable_replication_does_not_simulate_a_backend(
    coordination: DurableCoordinationStore,
) -> None:
    first = _manifest(coordination, label="repl")
    assert coordination.backend is None
    results = replicate_semantic_blocks(
        coordination, [first.world_root_manifest_cid]
    )
    assert len(results) == 1
    result = results[0]
    assert result.provider_status is ProviderStatus.UNAVAILABLE
    assert result.replicated is False
    assert result.local_durable is True
    assert result.cid == first.world_root_manifest_cid
    assert result.identity_cid == first.world_root_manifest_cid
    assert result.reason_code == "provider_unavailable"
    assert result.supervisor_accepted is False


def test_replication_cannot_change_identity(tmp_path: Path) -> None:
    backend = _MemoryBlockBackend()
    with DurableCoordinationStore(tmp_path / "replica", backend=backend) as store:
        first = _manifest(store, label="ident")
        adapter = SemanticWorldReplicationAdapter(store)
        results = adapter.replicate_semantic_blocks([first.world_root_manifest_cid])
        assert results[0].provider_status is ProviderStatus.AVAILABLE
        assert results[0].replicated is True
        assert results[0].cid == first.world_root_manifest_cid
        assert results[0].identity_cid == first.world_root_manifest_cid
        assert results[0].supervisor_accepted is False
        copied = backend.blocks[first.world_root_manifest_cid]
        assert kit_cid_for_bytes(copied) == first.world_root_manifest_cid

    class _CorruptLoadBackend:
        def store_block(self, cid: str, data: bytes, codec: str) -> str:
            del data, codec
            return cid

        def load_block(self, cid: str) -> bytes:
            del cid
            return b"not-the-original-bytes"

    with DurableCoordinationStore(
        tmp_path / "corrupt-replica", backend=_CorruptLoadBackend()
    ) as store:
        first = _manifest(store, label="ident2")
        adapter = SemanticWorldReplicationAdapter(store)
        with pytest.raises(SemanticWorldReplicationError, match="identity"):
            adapter.replicate_semantic_blocks([first.world_root_manifest_cid])


def test_facade_composes_cas_recovery_outbox_and_replication(
    coordination: DurableCoordinationStore,
) -> None:
    facade = SemanticWorldStore(coordination)
    first = _manifest(coordination, label="facade")
    cas = facade.compare_and_swap_world_root(
        expected_generation=0,
        expected_root_cid=None,
        new_root_cid=first.world_root_manifest_cid,
        operation_id="facade-cas",
    )
    published = facade.publish_vfs_semantic_outbox(
        root_cid=first.world_root_manifest_cid,
        operation_id="facade-outbox",
        cas_result=cas,
    )
    replica = facade.replicate_semantic_blocks([first.world_root_manifest_cid])
    assert cas.status is RootUpdateStatus.UPDATED
    assert published.supervisor_accepted is False
    assert replica[0].provider_status is ProviderStatus.UNAVAILABLE
    assert facade.current_world_root().root_cid == first.world_root_manifest_cid
    assert facade.INTERFACE == "SemanticWorldStore@1"
