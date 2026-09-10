"""ABA-safe world-root CAS, WAL replay, restart, and optional replication.

``SemanticWorldRootRepository`` and ``SemanticWorldRecovery`` implement
``SemanticWorldRootCAS@1``.  They adapt the landed coordination-store
generation CAS, kit WAL replay, and optional block replication.  Kit
persists and recovers a current root pointer; it never accepts semantics
or supervisor completion.

Authority rules (normative, fail-closed):

* One expected generation admits at most one successor.  The expected
  ``(generation, root CID)`` pair is ABA-safe: generations only advance.
* Stale writers observe a typed conflict and do not mutate the visible root.
* Restart reconstructs at most one valid visible root per workspace from
  immutable transition evidence plus idempotent WAL replay.
* Durable file mutation, WAL append, and optional replication never equal
  supervisor acceptance.
* Replication cannot change identity.  An absent backend is typed
  unavailable; ordinary tests do not simulate a network.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar, Final, Mapping, Sequence

from ipfs_kit_py.core.wal.contracts import (
    WALAcknowledgementMode,
    WALRecord,
    WALRecordKind,
    WALRecordState,
    make_committed_record,
)
from ipfs_kit_py.core.wal.recovery import WALRecovery, WALRecoveryReceipt
from ipfs_kit_py.core.wal.segments import WALSegmentFile
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    DurableCoordinationStore,
    cid_for_bytes,
    validate_transport_cid,
)
from ipfs_kit_py.mcp_server.mcplusplus.state_root_contracts import (
    ProviderStatus,
    RootUpdateStatus,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    SemanticGovernorStoreContractError,
    validate_generation_expectation,
    validate_governor_namespace,
    validate_governor_workspace,
    validate_operation_id,
    validate_reason_code,
    validate_semantic_dag_json_cid,
)
from ipfs_kit_py.semantic_world_store.world_roots import (
    SemanticWorldRootManifest,
    SemanticWorldSnapshotStore,
    WorldRootAdmissionError,
    WorldRootError,
    WorldRootIntegrityError,
    WorldRootNotFound,
)


SEMANTIC_WORLD_ROOT_CAS_INTERFACE: Final[str] = "SemanticWorldRootCAS@1"
SEMANTIC_WORLD_RECOVERY_INTERFACE: Final[str] = "SemanticWorldRecovery@1"
SEMANTIC_WORLD_REPLICATION_INTERFACE: Final[str] = "SemanticWorldReplication@1"
WORLD_ROOT_CAS_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.world-root-cas@1"
)
WORLD_ROOT_RECOVERY_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.world-root-recovery@1"
)
SEMANTIC_WORLD_NAMESPACE_PREFIX: Final[str] = "semantic-world"
DEFAULT_WORLD_ROOT_WORKSPACE: Final[str] = "default"
WAL_DIRECTORY_NAME: Final[str] = "semantic-world-wal"
WAL_EFFECT_LEDGER_NAME: Final[str] = "effects.json"
MAX_RECOVERY_ERRORS: Final[int] = 32
_WAL_NOTES_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "workspace",
        "expected_generation",
        "expected_root_cid",
        "new_root_cid",
        "operation_id",
    }
)


class SemanticWorldRecoveryError(WorldRootError):
    """Base error for current-root CAS, WAL replay, and replication."""


class SemanticWorldCASAdmissionError(
    SemanticWorldRecoveryError, WorldRootAdmissionError
):
    """Raised when a current-root CAS request is refused before mutation."""


class SemanticWorldRecoveryIntegrityError(
    SemanticWorldRecoveryError, WorldRootIntegrityError
):
    """Raised when recovered root evidence fails closed verification."""


class SemanticWorldReplicationError(SemanticWorldRecoveryError):
    """Raised when optional replication would change identity."""


def _reject_supervisor_acceptance(
    value: object,
    *,
    path: str,
    error_cls: type[Exception] | None = None,
) -> bool:
    cls = SemanticWorldCASAdmissionError if error_cls is None else error_cls
    if value is True:
        raise cls(f"{path} durable file mutation is not supervisor acceptance")
    if value is not False:
        raise cls(f"{path} supervisor_accepted must be false")
    return False


def _require_bool(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise SemanticWorldCASAdmissionError(f"{name} must be a boolean")
    return value


def world_root_namespace(workspace: str = DEFAULT_WORLD_ROOT_WORKSPACE) -> str:
    """Return the closed ``semantic-world/<workspace>`` CAS namespace."""

    try:
        token = validate_governor_workspace(workspace)
        return validate_governor_namespace(
            f"{SEMANTIC_WORLD_NAMESPACE_PREFIX}/{token}"
        )
    except SemanticGovernorStoreContractError as exc:
        raise SemanticWorldCASAdmissionError(str(exc)) from exc


def parse_world_root_namespace(namespace: object) -> str:
    """Return the workspace token from a closed world-root namespace."""

    try:
        text = validate_governor_namespace(namespace)
    except SemanticGovernorStoreContractError as exc:
        raise SemanticWorldCASAdmissionError(str(exc)) from exc
    parts = text.split("/")
    if len(parts) != 2 or parts[0] != SEMANTIC_WORLD_NAMESPACE_PREFIX:
        raise SemanticWorldCASAdmissionError(
            "namespace must be semantic-world/<workspace>"
        )
    try:
        return validate_governor_workspace(parts[1])
    except SemanticGovernorStoreContractError as exc:
        raise SemanticWorldCASAdmissionError(str(exc)) from exc


def _as_snapshot_store(
    store: DurableCoordinationStore
    | SemanticWorldSnapshotStore
    | SemanticWorldRootRepository
    | SemanticWorldRecovery,
) -> SemanticWorldSnapshotStore:
    if isinstance(store, SemanticWorldSnapshotStore):
        return store
    repository = getattr(store, "repository", None)
    if isinstance(repository, SemanticWorldRootRepository):
        return repository.roots
    roots = getattr(store, "roots", None)
    if isinstance(roots, SemanticWorldSnapshotStore):
        return roots
    return SemanticWorldSnapshotStore(store)


def _coordination_store(store: Any) -> DurableCoordinationStore:
    if isinstance(store, DurableCoordinationStore):
        return store
    inner = getattr(store, "store", None)
    if isinstance(inner, DurableCoordinationStore):
        return inner
    raise TypeError("store must compose a DurableCoordinationStore")


def _wal_directory_for(store: DurableCoordinationStore, wal_dir: Path | None) -> Path:
    path = Path(wal_dir) if wal_dir is not None else store.root / WAL_DIRECTORY_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _status_from_wire(value: object) -> RootUpdateStatus:
    if isinstance(value, RootUpdateStatus):
        return value
    if isinstance(value, str):
        try:
            return RootUpdateStatus(value)
        except ValueError as exc:
            raise SemanticWorldRecoveryIntegrityError(
                f"unknown CAS status: {value!r}"
            ) from exc
    raise SemanticWorldRecoveryIntegrityError("CAS status must be a closed token")


def _encode_wal_notes(
    *,
    workspace: str,
    expected_generation: int,
    expected_root_cid: str | None,
    new_root_cid: str,
    operation_id: str,
) -> str:
    return json.dumps(
        {
            "workspace": workspace,
            "expected_generation": expected_generation,
            "expected_root_cid": expected_root_cid,
            "new_root_cid": new_root_cid,
            "operation_id": operation_id,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _decode_wal_notes(value: object) -> dict[str, Any]:
    if type(value) is not str or not value:
        raise SemanticWorldRecoveryIntegrityError("WAL notes must be canonical JSON")
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SemanticWorldRecoveryIntegrityError("WAL notes are not JSON") from exc
    if not isinstance(payload, Mapping):
        raise SemanticWorldRecoveryIntegrityError("WAL notes must be a mapping")
    actual = frozenset(payload)
    if actual != _WAL_NOTES_FIELDS:
        raise SemanticWorldRecoveryIntegrityError(
            "WAL notes are not a closed CAS envelope"
        )
    return dict(payload)


@dataclass(frozen=True, slots=True)
class WorldRootSnapshot:
    """Currently visible generation-bearing world root for one workspace."""

    namespace: str
    root_cid: str | None
    generation: int
    transition_cid: str | None
    supervisor_accepted: bool = False

    SCHEMA: ClassVar[str] = WORLD_ROOT_CAS_SCHEMA
    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_ROOT_CAS_INTERFACE

    def __post_init__(self) -> None:
        raw_namespace = str(self.namespace)
        if raw_namespace.startswith(f"{SEMANTIC_WORLD_NAMESPACE_PREFIX}/"):
            workspace = parse_world_root_namespace(raw_namespace)
        else:
            workspace = raw_namespace
        object.__setattr__(self, "namespace", world_root_namespace(workspace))
        if type(self.generation) is not int or isinstance(self.generation, bool) or self.generation < 0:
            raise SemanticWorldCASAdmissionError("generation must be a non-negative integer")
        if self.root_cid is not None:
            try:
                validate_semantic_dag_json_cid(self.root_cid, "root_cid")
            except SemanticGovernorStoreContractError as exc:
                raise SemanticWorldCASAdmissionError(str(exc)) from exc
        if self.transition_cid is not None:
            try:
                validate_semantic_dag_json_cid(self.transition_cid, "transition_cid")
            except SemanticGovernorStoreContractError as exc:
                raise SemanticWorldCASAdmissionError(str(exc)) from exc
        object.__setattr__(
            self,
            "supervisor_accepted",
            _reject_supervisor_acceptance(
                self.supervisor_accepted, path="WorldRootSnapshot"
            ),
        )
        if self.generation == 0 and (
            self.root_cid is not None or self.transition_cid is not None
        ):
            raise SemanticWorldCASAdmissionError(
                "generation-zero roots must not have a CID or transition"
            )
        if self.generation > 0 and (
            self.root_cid is None or self.transition_cid is None
        ):
            raise SemanticWorldCASAdmissionError(
                "non-zero roots require a root CID and transition CID"
            )

    @property
    def workspace(self) -> str:
        return parse_world_root_namespace(self.namespace)

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "root_cid": self.root_cid,
            "generation": self.generation,
            "transition_cid": self.transition_cid,
            "supervisor_accepted": False,
        }

    @classmethod
    def from_wire(cls, value: Mapping[str, Any]) -> "WorldRootSnapshot":
        if not isinstance(value, Mapping):
            raise SemanticWorldRecoveryIntegrityError("root snapshot must be a mapping")
        generation = value.get("generation", value.get("revision"))
        return cls(
            namespace=str(value["namespace"]),
            root_cid=value.get("root_cid"),
            generation=int(generation),
            transition_cid=value.get("transition_cid"),
            supervisor_accepted=False,
        )


@dataclass(frozen=True, slots=True)
class WorldRootCASResult:
    """Closed outcome of an attempted world-root compare-and-swap."""

    status: RootUpdateStatus
    before: WorldRootSnapshot
    after: WorldRootSnapshot
    transition_cid: str | None
    reason_code: str
    local_durable: bool
    replicated: bool
    operation_id: str
    supervisor_accepted: bool = False

    SCHEMA: ClassVar[str] = WORLD_ROOT_CAS_SCHEMA
    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_ROOT_CAS_INTERFACE

    def __post_init__(self) -> None:
        if not isinstance(self.status, RootUpdateStatus):
            raise SemanticWorldCASAdmissionError("status must be a RootUpdateStatus")
        if not isinstance(self.before, WorldRootSnapshot) or not isinstance(
            self.after, WorldRootSnapshot
        ):
            raise SemanticWorldCASAdmissionError(
                "before and after must be WorldRootSnapshot values"
            )
        if self.before.namespace != self.after.namespace:
            raise SemanticWorldCASAdmissionError("before and after namespaces must agree")
        if self.transition_cid is not None:
            try:
                validate_semantic_dag_json_cid(self.transition_cid, "transition_cid")
            except SemanticGovernorStoreContractError as exc:
                raise SemanticWorldCASAdmissionError(str(exc)) from exc
        try:
            validate_reason_code(self.reason_code)
            validate_operation_id(self.operation_id)
        except SemanticGovernorStoreContractError as exc:
            raise SemanticWorldCASAdmissionError(str(exc)) from exc
        object.__setattr__(self, "local_durable", _require_bool(self.local_durable, "local_durable"))
        object.__setattr__(self, "replicated", _require_bool(self.replicated, "replicated"))
        object.__setattr__(
            self,
            "supervisor_accepted",
            _reject_supervisor_acceptance(
                self.supervisor_accepted, path="WorldRootCASResult"
            ),
        )
        if self.replicated and not self.local_durable:
            raise SemanticWorldCASAdmissionError(
                "replicated results must also be locally durable"
            )
        if self.status is RootUpdateStatus.UPDATED:
            if not self.local_durable or self.after.generation != self.before.generation + 1:
                raise SemanticWorldCASAdmissionError(
                    "updated results require a durable one-generation successor"
                )
            if (
                self.after.root_cid == self.before.root_cid
                or self.transition_cid != self.after.transition_cid
            ):
                raise SemanticWorldCASAdmissionError(
                    "updated results require a distinct matching transition"
                )
        else:
            if self.after != self.before or self.transition_cid is not None:
                raise SemanticWorldCASAdmissionError(
                    "non-updated results must not change the root"
                )
            if self.replicated:
                raise SemanticWorldCASAdmissionError(
                    "non-updated results cannot claim replication"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "transition_cid": self.transition_cid,
            "reason_code": self.reason_code,
            "local_durable": self.local_durable,
            "replicated": self.replicated,
            "operation_id": self.operation_id,
            "supervisor_accepted": False,
        }


@dataclass(frozen=True, slots=True)
class WorldRootRecoveryReport:
    """Pure recovery evidence; errors are closed code/message records."""

    verified_blocks: int
    reconstructed_roots: tuple[WorldRootSnapshot, ...]
    replayed_operation_ids: tuple[str, ...]
    ignored_idempotent_transitions: tuple[str, ...]
    errors: tuple[Mapping[str, str], ...]
    supervisor_accepted: bool = False

    SCHEMA: ClassVar[str] = WORLD_ROOT_RECOVERY_SCHEMA
    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_RECOVERY_INTERFACE

    def __post_init__(self) -> None:
        if type(self.verified_blocks) is not int or self.verified_blocks < 0:
            raise SemanticWorldRecoveryIntegrityError(
                "verified_blocks must be a non-negative integer"
            )
        if not isinstance(self.reconstructed_roots, tuple) or not all(
            isinstance(item, WorldRootSnapshot) for item in self.reconstructed_roots
        ):
            raise SemanticWorldRecoveryIntegrityError(
                "reconstructed_roots must be a tuple of snapshots"
            )
        namespaces = [item.namespace for item in self.reconstructed_roots]
        if len(set(namespaces)) != len(namespaces):
            raise SemanticWorldRecoveryIntegrityError(
                "reconstructed_roots may contain only one snapshot per namespace"
            )
        object.__setattr__(
            self,
            "supervisor_accepted",
            _reject_supervisor_acceptance(
                self.supervisor_accepted, path="WorldRootRecoveryReport"
            ),
        )
        normalized: list[Mapping[str, str]] = []
        for error in self.errors:
            if not isinstance(error, Mapping) or frozenset(error) != {"code", "message"}:
                raise SemanticWorldRecoveryIntegrityError(
                    "recovery errors require closed code/message records"
                )
            code, message = error["code"], error["message"]
            if type(code) is not str or type(message) is not str or not message:
                raise SemanticWorldRecoveryIntegrityError(
                    "recovery errors require a normalized code and non-empty message"
                )
            normalized.append(MappingProxyType({"code": code, "message": message}))
        object.__setattr__(self, "errors", tuple(normalized))

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified_blocks": self.verified_blocks,
            "reconstructed_roots": [item.to_dict() for item in self.reconstructed_roots],
            "replayed_operation_ids": list(self.replayed_operation_ids),
            "ignored_idempotent_transitions": list(self.ignored_idempotent_transitions),
            "errors": [dict(item) for item in self.errors],
            "supervisor_accepted": False,
        }


@dataclass(frozen=True, slots=True)
class SemanticWorldReplicationResult:
    """Truthful optional replication of already-durable semantic blocks."""

    cid: str
    identity_cid: str
    local_durable: bool
    provider_status: ProviderStatus
    replicated: bool
    reason_code: str
    supervisor_accepted: bool = False

    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_REPLICATION_INTERFACE

    def __post_init__(self) -> None:
        try:
            validate_semantic_dag_json_cid(self.cid, "cid")
            validate_semantic_dag_json_cid(self.identity_cid, "identity_cid")
            validate_reason_code(self.reason_code)
        except SemanticGovernorStoreContractError as exc:
            raise SemanticWorldReplicationError(str(exc)) from exc
        if self.cid != self.identity_cid:
            raise SemanticWorldReplicationError(
                "replication cannot change identity"
            )
        if not isinstance(self.provider_status, ProviderStatus):
            raise SemanticWorldReplicationError(
                "provider_status must be a ProviderStatus"
            )
        object.__setattr__(
            self, "local_durable", _require_bool(self.local_durable, "local_durable")
        )
        object.__setattr__(self, "replicated", _require_bool(self.replicated, "replicated"))
        object.__setattr__(
            self,
            "supervisor_accepted",
            _reject_supervisor_acceptance(
                self.supervisor_accepted, path="SemanticWorldReplicationResult"
            ),
        )
        if self.replicated != (self.provider_status is ProviderStatus.AVAILABLE):
            raise SemanticWorldReplicationError(
                "replicated must exactly match an available provider outcome"
            )
        if not self.local_durable:
            raise SemanticWorldReplicationError(
                "replication cannot be claimed without local durability"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cid": self.cid,
            "identity_cid": self.identity_cid,
            "local_durable": self.local_durable,
            "provider_status": self.provider_status.value,
            "replicated": self.replicated,
            "reason_code": self.reason_code,
            "supervisor_accepted": False,
        }


def _snapshot_from_wire(value: Mapping[str, Any]) -> WorldRootSnapshot:
    return WorldRootSnapshot.from_wire(value)


def _cas_result_from_wire(
    raw: Mapping[str, Any], *, operation_id: str
) -> WorldRootCASResult:
    status = _status_from_wire(raw.get("status"))
    before = _snapshot_from_wire(raw["before"])
    after = _snapshot_from_wire(raw["after"])
    transition_cid = raw.get("transition_cid")
    if transition_cid is not None:
        try:
            transition_cid = validate_semantic_dag_json_cid(
                transition_cid, "transition_cid"
            )
        except SemanticGovernorStoreContractError as exc:
            raise SemanticWorldRecoveryIntegrityError(str(exc)) from exc
    reason_code = raw.get("reason_code")
    if type(reason_code) is not str:
        raise SemanticWorldRecoveryIntegrityError("CAS reason_code must be a string")
    try:
        validate_reason_code(reason_code)
    except SemanticGovernorStoreContractError as exc:
        raise SemanticWorldRecoveryIntegrityError(str(exc)) from exc
    return WorldRootCASResult(
        status=status,
        before=before,
        after=after,
        transition_cid=transition_cid,
        reason_code=reason_code,
        local_durable=bool(raw.get("local_durable")),
        replicated=bool(raw.get("replicated")),
        operation_id=operation_id,
        supervisor_accepted=False,
    )


def _successor_count(
    store: DurableCoordinationStore, namespace: str, expected_generation: int
) -> int:
    return sum(
        1
        for row in store.root_transitions(namespace)
        if int(row["expected_revision"]) == expected_generation
    )


class SemanticWorldRootRepository:
    """Mutable current-root pointer over generation-bearing world manifests."""

    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_ROOT_CAS_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldSnapshotStore
        | SemanticWorldRecovery,
        *,
        wal_dir: Path | str | None = None,
    ) -> None:
        self._roots = _as_snapshot_store(store)
        self._store = _coordination_store(self._roots)
        self._wal_dir = _wal_directory_for(
            self._store, Path(wal_dir) if wal_dir is not None else None
        )
        self._wal_lock = threading.Lock()

    @property
    def roots(self) -> SemanticWorldSnapshotStore:
        return self._roots

    @property
    def store(self) -> DurableCoordinationStore:
        return self._store

    @property
    def wal_dir(self) -> Path:
        return self._wal_dir

    def close(self) -> None:
        self._roots.close()

    def __enter__(self) -> "SemanticWorldRootRepository":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def current_world_root(
        self, workspace: str = DEFAULT_WORLD_ROOT_WORKSPACE
    ) -> WorldRootSnapshot:
        """Return the currently visible root (generation zero if unpublished)."""

        namespace = world_root_namespace(workspace)
        try:
            raw = self._store.current_state_root(namespace)
        except ArtifactIntegrityError as exc:
            raise SemanticWorldRecoveryIntegrityError(str(exc)) from exc
        snapshot = _snapshot_from_wire(raw)
        if snapshot.root_cid is not None:
            self._require_verified_manifest(
                snapshot.root_cid, expected_generation=snapshot.generation
            )
        return snapshot

    def _require_verified_manifest(
        self, cid: str, *, expected_generation: int | None = None
    ) -> SemanticWorldRootManifest:
        try:
            manifest = self._roots.get_verified_manifest(cid)
        except WorldRootNotFound as exc:
            raise SemanticWorldCASAdmissionError(
                "store-before-reference: new world-root manifest is not stored"
            ) from exc
        except WorldRootError as exc:
            raise SemanticWorldCASAdmissionError(str(exc)) from exc
        if expected_generation is not None and manifest.generation != expected_generation:
            raise SemanticWorldCASAdmissionError(
                "world-root manifest generation does not match the CAS generation"
            )
        return manifest

    def _append_committed_wal(
        self,
        *,
        workspace: str,
        expected_generation: int,
        expected_root_cid: str | None,
        new_root_cid: str,
        operation_id: str,
    ) -> None:
        """Append a post-commit WAL transaction.  File durability is not acceptance."""

        generation_id = f"sawm-{operation_id}"
        segment_id = f"seg-{operation_id}"
        path = self._wal_dir / f"{operation_id.replace(':', '-')}.wal"
        notes = _encode_wal_notes(
            workspace=workspace,
            expected_generation=expected_generation,
            expected_root_cid=expected_root_cid,
            new_root_cid=new_root_cid,
            operation_id=operation_id,
        )
        with self._wal_lock:
            if path.exists() and path.stat().st_size > 0:
                return
            segment = WALSegmentFile(
                path, generation_id=generation_id, segment_id=segment_id
            )
            try:
                segment.append(
                    WALRecord(
                        generation_id=generation_id,
                        sequence_number=0,
                        kind=WALRecordKind.BEGIN,
                        state=WALRecordState.APPENDED,
                        acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
                        transaction_id=operation_id,
                        segment_id=segment_id,
                        operation_id=operation_id,
                    )
                )
                segment.append(
                    WALRecord(
                        generation_id=generation_id,
                        sequence_number=1,
                        kind=WALRecordKind.MUTATE,
                        state=WALRecordState.APPENDED,
                        acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
                        transaction_id=operation_id,
                        segment_id=segment_id,
                        record_key=operation_id,
                        payload_cid=new_root_cid,
                        operation_id=operation_id,
                        notes=notes,
                    )
                )
                segment.append(
                    make_committed_record(
                        generation_id=generation_id,
                        sequence_number=2,
                        transaction_id=operation_id,
                        fsync_receipt_id=f"fsync-{operation_id}",
                        segment_id=segment_id,
                        operation_id=operation_id,
                        payload_cid=new_root_cid,
                    )
                )
                segment.flush()
                segment.sync_file()
                segment.sync_parent()
                segment.seal()
            finally:
                segment.close()

    def compare_and_swap_world_root(
        self,
        workspace: str = DEFAULT_WORLD_ROOT_WORKSPACE,
        *,
        expected_generation: int,
        expected_root_cid: str | None,
        new_root_cid: str,
        operation_id: str,
        append_wal: bool = True,
    ) -> WorldRootCASResult:
        """Atomically publish one successor root or report a typed conflict.

        The successor must already be a stored generation-bearing world-root
        manifest whose generation is exactly ``expected_generation + 1``.
        """

        namespace = world_root_namespace(workspace)
        try:
            expected_generation, expected_root_cid = validate_generation_expectation(
                expected_generation, expected_root_cid
            )
            operation_id = validate_operation_id(operation_id)
            new_root_cid = validate_semantic_dag_json_cid(new_root_cid, "new_root_cid")
            if expected_root_cid is not None:
                expected_root_cid = validate_semantic_dag_json_cid(
                    expected_root_cid, "expected_root_cid"
                )
        except SemanticGovernorStoreContractError as exc:
            raise SemanticWorldCASAdmissionError(str(exc)) from exc

        manifest = self._require_verified_manifest(
            new_root_cid, expected_generation=expected_generation + 1
        )
        if expected_root_cid == new_root_cid:
            raise SemanticWorldCASAdmissionError(
                "new_root_cid must differ from expected_root_cid"
            )
        if expected_generation == 0:
            if manifest.previous_manifest_cid is not None:
                raise SemanticWorldCASAdmissionError(
                    "generation-zero successor must not cite a previous manifest"
                )
        else:
            if manifest.previous_manifest_cid != expected_root_cid:
                raise SemanticWorldCASAdmissionError(
                    "successor manifest must bind the expected predecessor CID"
                )
            self._require_verified_manifest(
                expected_root_cid, expected_generation=expected_generation
            )

        existing_successors = _successor_count(
            self._store, namespace, expected_generation
        )
        if existing_successors > 1:
            raise SemanticWorldRecoveryIntegrityError(
                "one expected generation admits at most one successor"
            )

        try:
            raw = self._store.compare_and_swap_state_root(
                namespace,
                expected_revision=expected_generation,
                expected_root_cid=expected_root_cid,
                new_root_cid=new_root_cid,
                operation_id=operation_id,
            )
        except ArtifactNotFound as exc:
            before = self.current_world_root(workspace)
            return WorldRootCASResult(
                RootUpdateStatus.UNAVAILABLE,
                before,
                before,
                None,
                "successor_unavailable",
                False,
                False,
                operation_id,
                False,
            )
        except ArtifactIntegrityError as exc:
            try:
                before = self.current_world_root(workspace)
            except SemanticWorldRecoveryError:
                before = WorldRootSnapshot(namespace, None, 0, None, False)
                return WorldRootCASResult(
                    RootUpdateStatus.CORRUPT,
                    before,
                    before,
                    None,
                    "integrity_failure",
                    False,
                    False,
                    operation_id,
                    False,
                )
            return WorldRootCASResult(
                RootUpdateStatus.CORRUPT,
                before,
                before,
                None,
                "integrity_failure",
                False,
                False,
                operation_id,
                False,
            )
        except ValueError as exc:
            raise SemanticWorldCASAdmissionError(str(exc)) from exc

        result = _cas_result_from_wire(raw, operation_id=operation_id)
        if result.status is RootUpdateStatus.UPDATED:
            if _successor_count(self._store, namespace, expected_generation) != 1:
                raise SemanticWorldRecoveryIntegrityError(
                    "one expected generation admits at most one successor"
                )
            if append_wal:
                self._append_committed_wal(
                    workspace=parse_world_root_namespace(namespace),
                    expected_generation=expected_generation,
                    expected_root_cid=expected_root_cid,
                    new_root_cid=new_root_cid,
                    operation_id=operation_id,
                )
        return result


class SemanticWorldReplicationAdapter:
    """Optional, identity-preserving replica of locally durable blocks."""

    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_REPLICATION_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldSnapshotStore
        | SemanticWorldRootRepository
        | SemanticWorldRecovery,
    ) -> None:
        self._store = _coordination_store(store)

    @property
    def store(self) -> DurableCoordinationStore:
        return self._store

    def replicate_semantic_blocks(
        self, cids: Sequence[str]
    ) -> tuple[SemanticWorldReplicationResult, ...]:
        """Copy already-durable blocks.  Identity is the local CID."""

        if isinstance(cids, (str, bytes)):
            raise SemanticWorldReplicationError("cids must be a sequence of CIDs")
        results: list[SemanticWorldReplicationResult] = []
        for cid in cids:
            results.append(self._replicate_one(cid))
        return tuple(results)

    def _replicate_one(self, cid: object) -> SemanticWorldReplicationResult:
        try:
            identity = validate_semantic_dag_json_cid(cid, "cid")
        except SemanticGovernorStoreContractError as exc:
            raise SemanticWorldReplicationError(str(exc)) from exc
        try:
            data = self._store.get_bytes(identity)
        except ArtifactNotFound as exc:
            raise SemanticWorldReplicationError(
                f"store-before-reference: {identity}"
            ) from exc
        except ArtifactIntegrityError as exc:
            raise SemanticWorldReplicationError(str(exc)) from exc
        codec = validate_transport_cid(identity)
        recomputed = cid_for_bytes(data, codec)
        if recomputed != identity:
            raise SemanticWorldReplicationError(
                "local bytes do not rehash the claimed identity CID"
            )
        backend = self._store.backend
        if backend is None:
            return SemanticWorldReplicationResult(
                identity,
                identity,
                True,
                ProviderStatus.UNAVAILABLE,
                False,
                "provider_unavailable",
                False,
            )
        try:
            backend.store_block(identity, data, codec)
            loaded = backend.load_block(identity)
        except ArtifactIntegrityError:
            return SemanticWorldReplicationResult(
                identity,
                identity,
                True,
                ProviderStatus.CORRUPT,
                False,
                "provider_corrupt",
                False,
            )
        except Exception:
            return SemanticWorldReplicationResult(
                identity,
                identity,
                True,
                ProviderStatus.FAILED,
                False,
                "provider_failed",
                False,
            )
        if not isinstance(loaded, (bytes, bytearray, memoryview)):
            return SemanticWorldReplicationResult(
                identity,
                identity,
                True,
                ProviderStatus.CORRUPT,
                False,
                "provider_corrupt",
                False,
            )
        remote_bytes = bytes(loaded)
        if cid_for_bytes(remote_bytes, codec) != identity:
            raise SemanticWorldReplicationError(
                "replication cannot change identity"
            )
        return SemanticWorldReplicationResult(
            identity,
            identity,
            True,
            ProviderStatus.AVAILABLE,
            True,
            "replicated",
            False,
        )


class SemanticWorldRecovery:
    """Restart, WAL replay, and corruption-closed reconstruction of one root."""

    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_RECOVERY_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldSnapshotStore
        | SemanticWorldRootRepository,
        *,
        wal_dir: Path | str | None = None,
        repository: SemanticWorldRootRepository | None = None,
    ) -> None:
        if isinstance(store, SemanticWorldRootRepository):
            self._repository = store
        elif repository is not None:
            self._repository = repository
        else:
            self._repository = SemanticWorldRootRepository(store, wal_dir=wal_dir)
        self._store = self._repository.store
        self._wal_dir = (
            Path(wal_dir) if wal_dir is not None else self._repository.wal_dir
        )
        self._wal_dir.mkdir(parents=True, exist_ok=True)
        self._replication = SemanticWorldReplicationAdapter(self._store)

    @property
    def repository(self) -> SemanticWorldRootRepository:
        return self._repository

    @property
    def store(self) -> DurableCoordinationStore:
        return self._store

    @property
    def wal_dir(self) -> Path:
        return self._wal_dir

    @property
    def replication(self) -> SemanticWorldReplicationAdapter:
        return self._replication

    def close(self) -> None:
        self._repository.close()

    def __enter__(self) -> "SemanticWorldRecovery":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def replay_semantic_world_wal(
        self, *, workspace: str | None = None
    ) -> WALRecoveryReceipt:
        """Idempotently replay committed post-CAS WAL mutations."""

        del workspace  # workspace is bound inside each committed record
        ledger = self._wal_dir / WAL_EFFECT_LEDGER_NAME
        recovery = WALRecovery(self._wal_dir, effect_ledger=ledger)

        def handler(record: WALRecord) -> None:
            notes = _decode_wal_notes(record.notes)
            expected = notes["expected_root_cid"]
            self._repository.compare_and_swap_world_root(
                str(notes["workspace"]),
                expected_generation=int(notes["expected_generation"]),
                expected_root_cid=expected,
                new_root_cid=str(notes["new_root_cid"]),
                operation_id=str(notes["operation_id"]),
                append_wal=False,
            )

        return recovery.recover(handler)

    def recover(
        self,
        *,
        rebuild: bool = True,
        workspace: str | None = None,
    ) -> WorldRootRecoveryReport:
        """Verify blocks, replay WAL, and expose at most one valid root."""

        errors: list[Mapping[str, str]] = []
        verified_blocks = 0
        try:
            raw = self._store.recover(rebuild=rebuild)
            verified_blocks = int(raw["verified_blocks"])
        except ArtifactIntegrityError as exc:
            message = str(exc)
            code = (
                "ambiguous_successor"
                if "breaks its namespace chain" in message
                else "corrupt"
            )
            return WorldRootRecoveryReport(
                verified_blocks,
                (),
                (),
                (),
                (MappingProxyType({"code": code, "message": message}),),
                False,
            )

        replayed: tuple[str, ...] = ()
        ignored: tuple[str, ...] = ()
        try:
            receipt = self.replay_semantic_world_wal(workspace=workspace)
            replayed = receipt.replayed_record_ids
            ignored = receipt.skipped_effect_keys
        except (SemanticWorldRecoveryError, WorldRootError, ValueError, OSError) as exc:
            errors.append(
                MappingProxyType({"code": "corrupt", "message": str(exc)})
            )
            return WorldRootRecoveryReport(
                verified_blocks, (), replayed, ignored, tuple(errors), False
            )

        roots: list[WorldRootSnapshot] = []
        try:
            raw_roots = self._store.state_roots()
        except ArtifactIntegrityError as exc:
            return WorldRootRecoveryReport(
                verified_blocks,
                (),
                replayed,
                ignored,
                (MappingProxyType({"code": "corrupt", "message": str(exc)}),),
                False,
            )
        wanted = (
            None
            if workspace is None
            else world_root_namespace(workspace)
        )
        for row in raw_roots:
            namespace = row.get("namespace")
            if type(namespace) is not str:
                errors.append(
                    MappingProxyType(
                        {"code": "corrupt", "message": "state root row missing namespace"}
                    )
                )
                continue
            if not namespace.startswith(f"{SEMANTIC_WORLD_NAMESPACE_PREFIX}/"):
                continue
            if wanted is not None and namespace != wanted:
                continue
            try:
                snapshot = _snapshot_from_wire(row)
                if snapshot.root_cid is not None:
                    self._repository._require_verified_manifest(
                        snapshot.root_cid, expected_generation=snapshot.generation
                    )
                successors = _successor_count(
                    self._store, snapshot.namespace, max(snapshot.generation - 1, 0)
                )
                if snapshot.generation > 0 and successors > 1:
                    raise SemanticWorldRecoveryIntegrityError(
                        "one expected generation admits at most one successor"
                    )
                roots.append(snapshot)
            except (
                SemanticWorldRecoveryError,
                WorldRootError,
                SemanticGovernorStoreContractError,
                TypeError,
                ValueError,
            ) as exc:
                errors.append(
                    MappingProxyType({"code": "corrupt", "message": str(exc)})
                )

        if errors:
            return WorldRootRecoveryReport(
                verified_blocks, (), replayed, ignored, tuple(errors[:MAX_RECOVERY_ERRORS]), False
            )
        return WorldRootRecoveryReport(
            verified_blocks, tuple(roots), replayed, ignored, (), False
        )


def compare_and_swap_world_root(
    store: DurableCoordinationStore
    | SemanticWorldSnapshotStore
    | SemanticWorldRootRepository
    | SemanticWorldRecovery,
    workspace: str = DEFAULT_WORLD_ROOT_WORKSPACE,
    *,
    expected_generation: int,
    expected_root_cid: str | None,
    new_root_cid: str,
    operation_id: str,
    append_wal: bool = True,
) -> WorldRootCASResult:
    """Publish one generation-bearing current root or report a typed conflict."""

    repository = (
        store
        if isinstance(store, SemanticWorldRootRepository)
        else store.repository
        if isinstance(store, SemanticWorldRecovery)
        else SemanticWorldRootRepository(store)
    )
    return repository.compare_and_swap_world_root(
        workspace,
        expected_generation=expected_generation,
        expected_root_cid=expected_root_cid,
        new_root_cid=new_root_cid,
        operation_id=operation_id,
        append_wal=append_wal,
    )


def replay_semantic_world_wal(
    store: DurableCoordinationStore
    | SemanticWorldSnapshotStore
    | SemanticWorldRootRepository
    | SemanticWorldRecovery,
    *,
    wal_dir: Path | str | None = None,
    workspace: str | None = None,
) -> WALRecoveryReceipt:
    """Replay committed semantic-world WAL mutations through generation CAS."""

    recovery = (
        store
        if isinstance(store, SemanticWorldRecovery)
        else SemanticWorldRecovery(store, wal_dir=wal_dir)
    )
    return recovery.replay_semantic_world_wal(workspace=workspace)


def replicate_semantic_blocks(
    store: DurableCoordinationStore
    | SemanticWorldSnapshotStore
    | SemanticWorldRootRepository
    | SemanticWorldRecovery
    | SemanticWorldReplicationAdapter,
    cids: Sequence[str],
) -> tuple[SemanticWorldReplicationResult, ...]:
    """Replicate locally durable blocks without changing their identity CIDs."""

    adapter = (
        store
        if isinstance(store, SemanticWorldReplicationAdapter)
        else SemanticWorldReplicationAdapter(store)
    )
    return adapter.replicate_semantic_blocks(cids)


__all__ = [
    "DEFAULT_WORLD_ROOT_WORKSPACE",
    "SEMANTIC_WORLD_NAMESPACE_PREFIX",
    "SEMANTIC_WORLD_RECOVERY_INTERFACE",
    "SEMANTIC_WORLD_REPLICATION_INTERFACE",
    "SEMANTIC_WORLD_ROOT_CAS_INTERFACE",
    "WAL_DIRECTORY_NAME",
    "WORLD_ROOT_CAS_SCHEMA",
    "WORLD_ROOT_RECOVERY_SCHEMA",
    "SemanticWorldCASAdmissionError",
    "SemanticWorldRecovery",
    "SemanticWorldRecoveryError",
    "SemanticWorldRecoveryIntegrityError",
    "SemanticWorldReplicationAdapter",
    "SemanticWorldReplicationError",
    "SemanticWorldReplicationResult",
    "SemanticWorldRootRepository",
    "WorldRootCASResult",
    "WorldRootRecoveryReport",
    "WorldRootSnapshot",
    "compare_and_swap_world_root",
    "parse_world_root_namespace",
    "replay_semantic_world_wal",
    "replicate_semantic_blocks",
    "world_root_namespace",
]
