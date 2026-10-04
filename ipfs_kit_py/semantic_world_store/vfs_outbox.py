"""Post-commit VFS semantic outbox.

``VFSSemanticOutbox`` implements ``SemanticOutbox@1``.  It publishes an
already-committed world-root CID through the landed canonical VFS after
generation CAS succeeds.  A durable file mutation is never supervisor
acceptance.

Authority rules (normative, fail-closed):

* Outbox publication is post-commit only.  A generation-zero or mismatched
  current root is refused.
* Canonical VFS is the sole mutation authority for the published path.
* Success of a VFS write does not accept semantics, complete a task, or
  mutate the current-root pointer.
* Tampering with the published file cannot become supervisor acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Final

from ipfs_kit_py.core.vfs.contracts import VFSErrorCode, VFSOperationKind
from ipfs_kit_py.core.vfs.service import (
    CanonicalVFSService,
    VFSExecuteRequest,
    VFSServiceOutcome,
    make_op,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    SemanticGovernorStoreContractError,
    validate_operation_id,
    validate_semantic_dag_json_cid,
)
from ipfs_kit_py.semantic_world_store.recovery import (
    DEFAULT_WORLD_ROOT_WORKSPACE,
    SemanticWorldCASAdmissionError,
    SemanticWorldRecoveryError,
    SemanticWorldRootRepository,
    WorldRootCASResult,
    WorldRootSnapshot,
    _reject_supervisor_acceptance,
    _require_bool,
)


SEMANTIC_OUTBOX_INTERFACE: Final[str] = "SemanticOutbox@1"
VFS_SEMANTIC_OUTBOX_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.vfs-semantic-outbox@1"
)
DEFAULT_OUTBOX_DIRECTORY: Final[str] = "outbox"
DEFAULT_OUTBOX_PATH: Final[str] = "outbox/world-root"


class SemanticOutboxError(SemanticWorldRecoveryError):
    """Base error for post-commit VFS semantic-outbox publication."""


class SemanticOutboxAdmissionError(SemanticOutboxError, SemanticWorldCASAdmissionError):
    """Raised when outbox publication is refused (including pre-commit)."""


@dataclass(frozen=True, slots=True)
class VFSOutboxResult:
    """Closed evidence of a post-commit VFS publication attempt."""

    path: str
    root_cid: str
    generation: int
    vfs_success: bool
    durable_file_mutated: bool
    reason_code: str
    operation_id: str
    supervisor_accepted: bool = False

    SCHEMA: ClassVar[str] = VFS_SEMANTIC_OUTBOX_SCHEMA
    INTERFACE: ClassVar[str] = SEMANTIC_OUTBOX_INTERFACE

    def __post_init__(self) -> None:
        if type(self.path) is not str or not self.path:
            raise SemanticOutboxAdmissionError("path must be a nonempty string")
        try:
            validate_semantic_dag_json_cid(self.root_cid, "root_cid")
            validate_operation_id(self.operation_id)
        except SemanticGovernorStoreContractError as exc:
            raise SemanticOutboxAdmissionError(str(exc)) from exc
        if type(self.generation) is not int or self.generation < 1:
            raise SemanticOutboxAdmissionError(
                "outbox generation must be a committed positive integer"
            )
        object.__setattr__(self, "vfs_success", _require_bool(self.vfs_success, "vfs_success"))
        object.__setattr__(
            self,
            "durable_file_mutated",
            _require_bool(self.durable_file_mutated, "durable_file_mutated"),
        )
        if type(self.reason_code) is not str or not self.reason_code:
            raise SemanticOutboxAdmissionError("reason_code must be a nonempty string")
        object.__setattr__(
            self,
            "supervisor_accepted",
            _reject_supervisor_acceptance(
                self.supervisor_accepted,
                path="VFSOutboxResult",
                error_cls=SemanticOutboxAdmissionError,
            ),
        )
        if self.durable_file_mutated and not self.vfs_success:
            raise SemanticOutboxAdmissionError(
                "durable file mutation requires an observed VFS success"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "root_cid": self.root_cid,
            "generation": self.generation,
            "vfs_success": self.vfs_success,
            "durable_file_mutated": self.durable_file_mutated,
            "reason_code": self.reason_code,
            "operation_id": self.operation_id,
            "supervisor_accepted": False,
        }


class VFSSemanticOutbox:
    """Publish a committed world-root CID through canonical VFS."""

    INTERFACE: ClassVar[str] = SEMANTIC_OUTBOX_INTERFACE
    PATH: ClassVar[str] = DEFAULT_OUTBOX_PATH

    def __init__(
        self,
        repository: SemanticWorldRootRepository,
        *,
        vfs: CanonicalVFSService | None = None,
        path: str = DEFAULT_OUTBOX_PATH,
    ) -> None:
        if not isinstance(repository, SemanticWorldRootRepository):
            raise TypeError("repository must be a SemanticWorldRootRepository")
        self._repository = repository
        self._vfs = vfs if vfs is not None else CanonicalVFSService()
        if type(path) is not str or not path:
            raise SemanticOutboxAdmissionError("outbox path must be a nonempty string")
        self._path = path

    @property
    def repository(self) -> SemanticWorldRootRepository:
        return self._repository

    @property
    def vfs(self) -> CanonicalVFSService:
        return self._vfs

    @property
    def path(self) -> str:
        return self._path

    def read_published(self) -> bytes | None:
        """Return the published outbox bytes, or ``None`` when absent."""

        outcome = self._vfs.execute(
            make_op(
                VFSOperationKind.READ,
                operation_id="outbox-read",
                path=self._path,
            )
        )
        if not outcome.success:
            return None
        return outcome.data

    def _ensure_parent(self, operation_id: str) -> None:
        parent = self._path.rsplit("/", 1)[0] if "/" in self._path else ""
        if not parent:
            return
        stated = self._vfs.execute(
            make_op(
                VFSOperationKind.STAT,
                operation_id=f"{operation_id}-stat-dir",
                path=parent,
            )
        )
        if stated.success:
            return
        created = self._vfs.execute(
            make_op(
                VFSOperationKind.MKDIR,
                operation_id=f"{operation_id}-mkdir",
                path=parent,
            )
        )
        if created.success:
            return
        error = created.result.error
        if error is not None and error.code is VFSErrorCode.ALREADY_EXISTS:
            return
        raise SemanticOutboxAdmissionError(
            f"unable to admit outbox directory {parent!r}"
        )

    def _write(self, payload: bytes, *, operation_id: str) -> VFSServiceOutcome:
        self._ensure_parent(operation_id)
        stated = self._vfs.execute(
            make_op(
                VFSOperationKind.STAT,
                operation_id=f"{operation_id}-stat",
                path=self._path,
            )
        )
        kind = VFSOperationKind.REPLACE if stated.success else VFSOperationKind.CREATE
        return self._vfs.execute(
            make_op(kind, operation_id=operation_id, path=self._path),
            VFSExecuteRequest(payload=payload),
        )

    def publish_vfs_semantic_outbox(
        self,
        workspace: str = DEFAULT_WORLD_ROOT_WORKSPACE,
        *,
        root_cid: str,
        operation_id: str,
        cas_result: WorldRootCASResult | None = None,
    ) -> VFSOutboxResult:
        """Publish ``root_cid`` only after it is the committed current root."""

        try:
            root_cid = validate_semantic_dag_json_cid(root_cid, "root_cid")
            operation_id = validate_operation_id(operation_id)
        except SemanticGovernorStoreContractError as exc:
            raise SemanticOutboxAdmissionError(str(exc)) from exc

        if cas_result is not None:
            if cas_result.supervisor_accepted:
                raise SemanticOutboxAdmissionError(
                    "durable file mutation is not supervisor acceptance"
                )
            if cas_result.after.root_cid != root_cid:
                raise SemanticOutboxAdmissionError(
                    "VFS outbox is post-commit only; CAS result does not bind root_cid"
                )
            if not cas_result.local_durable:
                raise SemanticOutboxAdmissionError(
                    "VFS outbox is post-commit only; CAS is not locally durable"
                )

        current = self._require_committed_root(workspace, root_cid)
        outcome = self._write(root_cid.encode("utf-8"), operation_id=operation_id)
        if not outcome.success:
            return VFSOutboxResult(
                path=self._path,
                root_cid=root_cid,
                generation=current.generation,
                vfs_success=False,
                durable_file_mutated=False,
                reason_code="vfs_publish_failed",
                operation_id=operation_id,
                supervisor_accepted=False,
            )
        return VFSOutboxResult(
            path=self._path,
            root_cid=root_cid,
            generation=current.generation,
            vfs_success=True,
            durable_file_mutated=True,
            reason_code="published",
            operation_id=operation_id,
            supervisor_accepted=False,
        )

    def _require_committed_root(
        self, workspace: str, root_cid: str
    ) -> WorldRootSnapshot:
        current = self._repository.current_world_root(workspace)
        if current.generation < 1 or current.root_cid is None:
            raise SemanticOutboxAdmissionError(
                "VFS outbox is post-commit only; no committed world root"
            )
        if current.root_cid != root_cid:
            raise SemanticOutboxAdmissionError(
                "VFS outbox is post-commit only; root_cid is not the committed current root"
            )
        return current


def publish_vfs_semantic_outbox(
    repository: SemanticWorldRootRepository | VFSSemanticOutbox,
    workspace: str = DEFAULT_WORLD_ROOT_WORKSPACE,
    *,
    root_cid: str,
    operation_id: str,
    cas_result: WorldRootCASResult | None = None,
    vfs: CanonicalVFSService | None = None,
) -> VFSOutboxResult:
    """Publish a committed world-root CID through the VFS semantic outbox."""

    outbox = (
        repository
        if isinstance(repository, VFSSemanticOutbox)
        else VFSSemanticOutbox(repository, vfs=vfs)
    )
    return outbox.publish_vfs_semantic_outbox(
        workspace,
        root_cid=root_cid,
        operation_id=operation_id,
        cas_result=cas_result,
    )


__all__ = [
    "DEFAULT_OUTBOX_DIRECTORY",
    "DEFAULT_OUTBOX_PATH",
    "SEMANTIC_OUTBOX_INTERFACE",
    "VFS_SEMANTIC_OUTBOX_SCHEMA",
    "SemanticOutboxAdmissionError",
    "SemanticOutboxError",
    "VFSOutboxResult",
    "VFSSemanticOutbox",
    "publish_vfs_semantic_outbox",
]
