"""Public kit facade for verified semantic-world persistence.

``SemanticWorldStore@1`` integrates verified blocks, projection resolution,
graph history, generation-bearing roots, ABA-safe current-root CAS, WAL
recovery, post-commit VFS outbox, and optional replication.  Kit stores and
retrieves; it never accepts semantics or supervisor completion.
"""

from __future__ import annotations

from typing import Any, ClassVar, Final

from ipfs_kit_py.core.vfs.service import CanonicalVFSService
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import DurableCoordinationStore
from ipfs_kit_py.semantic_world_store.artifacts import (
    ARTIFACT_MODULE_INTERFACE,
    SemanticWorldArtifactStore,
)
from ipfs_kit_py.semantic_world_store.graph_history import (
    PROGRAM_GRAPH_HISTORY_INTERFACE,
    HistoryBlockStore,
    LogicalProgramGraphStore,
    ProgramTransitionLog,
)
from ipfs_kit_py.semantic_world_store.recovery import (
    DEFAULT_WORLD_ROOT_WORKSPACE,
    SEMANTIC_WORLD_RECOVERY_INTERFACE,
    SEMANTIC_WORLD_REPLICATION_INTERFACE,
    SEMANTIC_WORLD_ROOT_CAS_INTERFACE,
    SemanticWorldRecovery,
    SemanticWorldReplicationAdapter,
    SemanticWorldReplicationResult,
    SemanticWorldRootRepository,
    WorldRootCASResult,
    WorldRootRecoveryReport,
    WorldRootSnapshot,
    compare_and_swap_world_root,
    replay_semantic_world_wal,
    replicate_semantic_blocks,
    world_root_namespace,
)
from ipfs_kit_py.semantic_world_store.verified_store import (
    VERIFIED_SEMANTIC_STORE_INTERFACE,
    VerifiedSemanticBlockStore,
)
from ipfs_kit_py.semantic_world_store.vfs_outbox import (
    SEMANTIC_OUTBOX_INTERFACE,
    VFSOutboxResult,
    VFSSemanticOutbox,
    publish_vfs_semantic_outbox,
)
from ipfs_kit_py.semantic_world_store.world_roots import (
    SEMANTIC_WORLD_ROOT_INTERFACE,
    SemanticWorldRootManifest,
    SemanticWorldSnapshotStore,
    build_world_root_manifest,
)


SEMANTIC_WORLD_STORE_INTERFACE: Final[str] = "SemanticWorldStore@1"


class SemanticWorldStore:
    """Composed kit facade over one injected ``DurableCoordinationStore``."""

    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_STORE_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore,
        *,
        wal_dir: Any = None,
        vfs: CanonicalVFSService | None = None,
    ) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        if vfs is None:
            from ipfs_kit_py.semantic_world_store.durable_vfs import (
                canonical_vfs_for_store,
            )

            vfs = canonical_vfs_for_store(store.root)
        self._store = store
        self.artifacts = SemanticWorldArtifactStore(store)
        self.verified = VerifiedSemanticBlockStore(self.artifacts)
        self.graph = LogicalProgramGraphStore(store)
        self.transitions = ProgramTransitionLog(self.graph.blocks)
        self.roots = SemanticWorldSnapshotStore(
            self.graph.blocks,
            graph_store=self.graph,
            transition_log=self.transitions,
        )
        self.repository = SemanticWorldRootRepository(self.roots, wal_dir=wal_dir)
        self.recovery = SemanticWorldRecovery(
            self.repository, wal_dir=self.repository.wal_dir
        )
        self.outbox = VFSSemanticOutbox(self.repository, vfs=vfs)
        self.replication = SemanticWorldReplicationAdapter(store)

    @property
    def store(self) -> DurableCoordinationStore:
        return self._store

    @property
    def blocks(self) -> HistoryBlockStore:
        return self.graph.blocks

    def current_world_root(
        self, workspace: str = DEFAULT_WORLD_ROOT_WORKSPACE
    ) -> WorldRootSnapshot:
        return self.repository.current_world_root(workspace)

    def compare_and_swap_world_root(self, *args: Any, **kwargs: Any) -> WorldRootCASResult:
        return self.repository.compare_and_swap_world_root(*args, **kwargs)

    def replay_semantic_world_wal(self, **kwargs: Any) -> Any:
        return self.recovery.replay_semantic_world_wal(**kwargs)

    def publish_vfs_semantic_outbox(self, *args: Any, **kwargs: Any) -> VFSOutboxResult:
        return self.outbox.publish_vfs_semantic_outbox(*args, **kwargs)

    def replicate_semantic_blocks(self, cids: Any) -> tuple[SemanticWorldReplicationResult, ...]:
        return self.replication.replicate_semantic_blocks(cids)

    def close(self) -> None:
        self.recovery.close()
        self.artifacts.close()

    def __enter__(self) -> "SemanticWorldStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


__all__ = [
    "ARTIFACT_MODULE_INTERFACE",
    "DEFAULT_WORLD_ROOT_WORKSPACE",
    "PROGRAM_GRAPH_HISTORY_INTERFACE",
    "SEMANTIC_OUTBOX_INTERFACE",
    "SEMANTIC_WORLD_RECOVERY_INTERFACE",
    "SEMANTIC_WORLD_REPLICATION_INTERFACE",
    "SEMANTIC_WORLD_ROOT_CAS_INTERFACE",
    "SEMANTIC_WORLD_ROOT_INTERFACE",
    "SEMANTIC_WORLD_STORE_INTERFACE",
    "VERIFIED_SEMANTIC_STORE_INTERFACE",
    "LogicalProgramGraphStore",
    "ProgramTransitionLog",
    "SemanticWorldRecovery",
    "SemanticWorldReplicationAdapter",
    "SemanticWorldReplicationResult",
    "SemanticWorldRootManifest",
    "SemanticWorldRootRepository",
    "SemanticWorldSnapshotStore",
    "SemanticWorldStore",
    "VFSOutboxResult",
    "VFSSemanticOutbox",
    "VerifiedSemanticBlockStore",
    "WorldRootCASResult",
    "WorldRootRecoveryReport",
    "WorldRootSnapshot",
    "build_world_root_manifest",
    "compare_and_swap_world_root",
    "publish_vfs_semantic_outbox",
    "replay_semantic_world_wal",
    "replicate_semantic_blocks",
    "world_root_namespace",
]
