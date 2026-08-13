"""Append-only audit, calibration, and benchmark histories (SCG-020).

``DurableAuditHistoryStore`` is a thin typed layer over
``DurableCoordinationStore`` root CAS:

* closed history roles under ``semantic-governor/<workspace>/{audit,calibration,benchmark}``
* each append CAS-publishes a deterministic history-manifest head that references
  an immutable entry CID (and the prior head)
* operation-id idempotency; rejected/stale records are never rewritten
* bounded pagination over immutable transition evidence
* public projections expose only portable CIDs/generations — never raw private
  source fields or arbitrary local filesystem paths

Does not open a second object store, WAL, daemon, or receipt hierarchy.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Mapping, Optional

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    DurableCoordinationStore,
    cid_for_artifact,
    cid_for_bytes,
)
from ipfs_kit_py.semantic_governor_store.artifacts import (
    PRIVATE_FIELD_MARKERS,
    reject_private_raw_source,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    GovernorHistoryRole,
    GovernorStoreStatus,
    HistoryAppendResult,
    HistoryHeadSnapshot,
    SemanticGovernorStoreContractError,
    history_namespace,
    validate_generation_expectation,
    validate_governor_workspace,
    validate_operation_id,
    validate_semantic_dag_json_cid,
)

# ---------------------------------------------------------------------------
# Schema / limits
# ---------------------------------------------------------------------------

HISTORY_MODULE_INTERFACE: Final[str] = "DurableAuditHistoryStore@1"
HISTORY_MANIFEST_INTERFACE: Final[str] = "GovernorHistoryManifest@1"
HISTORY_MANIFEST_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-governor-store.history-manifest@1"
)
HISTORY_PUBLIC_PROJECTION_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-governor-store.history-public@1"
)
HISTORY_PRIVATE_PROJECTION_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-governor-store.history-private@1"
)

# Bounded page sizes for transition / entry enumeration (fail closed above max).
DEFAULT_HISTORY_PAGE_SIZE: Final[int] = 64
MAX_HISTORY_PAGE_SIZE: Final[int] = 256
MAX_PUBLIC_PROJECTION_ENTRIES: Final[int] = 256

_ROLE_TO_ENTRY_KIND: Final[Mapping[GovernorHistoryRole, str]] = MappingProxyType(
    {
        GovernorHistoryRole.AUDIT: "audit",
        GovernorHistoryRole.CALIBRATION: "calibration",
        GovernorHistoryRole.BENCHMARK: "benchmark",
    }
)

# Absolute / host-local path markers rejected from public projections.
_ABSOLUTE_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:"
    r"/|"  # POSIX absolute
    r"[A-Za-z]:[\\/]|"  # Windows drive
    r"\\\\|"  # UNC
    r"file:"  # file URI
    r")"
)
_HOME_PATH_RE: Final[re.Pattern[str]] = re.compile(r"^~/")
_PATH_KEY_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "absolute_path",
        "file_path",
        "filesystem_path",
        "host_path",
        "local_path",
        "path",
        "realpath",
        "source_path",
        "workdir",
        "working_directory",
        "workspace_path",
    }
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GovernorHistoryError(ValueError):
    """Base error for append-only history admission or integrity failures."""


class GovernorHistoryAdmissionError(GovernorHistoryError):
    """Raised when an append or projection request is rejected before mutation."""


class GovernorHistoryIntegrityError(GovernorHistoryError):
    """Raised when stored head or manifest evidence fails verification."""


# ---------------------------------------------------------------------------
# Role / projection helpers
# ---------------------------------------------------------------------------


def _coerce_history_role(role: GovernorHistoryRole | str) -> GovernorHistoryRole:
    if isinstance(role, GovernorHistoryRole):
        return role
    if isinstance(role, str):
        try:
            return GovernorHistoryRole(role)
        except ValueError as exc:
            raise GovernorHistoryAdmissionError(
                f"unknown governor history role: {role!r}"
            ) from exc
    raise GovernorHistoryAdmissionError(
        "role must be a GovernorHistoryRole or its closed string value"
    )


def _status_from_wire(value: object) -> GovernorStoreStatus:
    if not isinstance(value, str):
        raise GovernorHistoryIntegrityError("history status must be a string")
    try:
        return GovernorStoreStatus(value)
    except ValueError as exc:
        raise GovernorHistoryIntegrityError(
            f"unknown history status: {value!r}"
        ) from exc


def _key_is_private(name: str) -> bool:
    lowered = name.lower()
    if lowered in PRIVATE_FIELD_MARKERS:
        return True
    for marker in PRIVATE_FIELD_MARKERS:
        if marker in lowered:
            return True
    return False


def _key_looks_like_path_field(name: str) -> bool:
    lowered = name.lower()
    if lowered in _PATH_KEY_MARKERS:
        return True
    if lowered.endswith("_path") or lowered.endswith("_dir") or lowered.endswith(
        "_directory"
    ):
        return True
    return False


def _string_looks_like_local_path(value: str) -> bool:
    if not value:
        return False
    if _ABSOLUTE_PATH_RE.match(value) or _HOME_PATH_RE.match(value):
        return True
    # Relative path with directory separators but no scheme — still host-local.
    if ("/" in value or "\\" in value) and "://" not in value:
        # Content-addressed / logical refs use slashes too (e.g. semantic-governor/...).
        # Only treat as local path when it begins like a filesystem path fragment.
        if value.startswith("./") or value.startswith(".\\") or value.startswith("../"):
            return True
        try:
            path = Path(value)
            if path.is_absolute():
                return True
        except (TypeError, ValueError, OSError):
            return False
    return False


def reject_public_local_paths(value: Any, *, path: str = "$") -> None:
    """Fail closed when an arbitrary local filesystem path is present."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                raise GovernorHistoryAdmissionError(
                    f"{path} map keys must be str, got {type(key).__name__}"
                )
            key_path = f"{path}.{key}"
            if _key_looks_like_path_field(key) and isinstance(item, str):
                if _string_looks_like_local_path(item) or item:
                    # Path-named fields are never public even when relative.
                    raise GovernorHistoryAdmissionError(
                        f"{key_path} rejects arbitrary local path field {key!r}"
                    )
            if isinstance(item, str) and _string_looks_like_local_path(item):
                raise GovernorHistoryAdmissionError(
                    f"{key_path} rejects arbitrary local path value"
                )
            reject_public_local_paths(item, path=key_path)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            reject_public_local_paths(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str) and _string_looks_like_local_path(value):
        raise GovernorHistoryAdmissionError(
            f"{path} rejects arbitrary local path value"
        )


def project_public_value(value: Any, *, path: str = "$") -> Any:
    """Return a deep copy with private markers and local paths removed.

    Raises ``GovernorHistoryAdmissionError`` when a private field or absolute
    local path cannot be redacted without inventing structure.
    """

    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise GovernorHistoryAdmissionError(
                    f"{path} map keys must be str, got {type(key).__name__}"
                )
            key_path = f"{path}.{key}"
            if _key_is_private(key):
                raise GovernorHistoryAdmissionError(
                    f"{key_path} rejects private raw source / private field {key!r}"
                )
            if _key_looks_like_path_field(key):
                raise GovernorHistoryAdmissionError(
                    f"{key_path} rejects arbitrary local path field {key!r}"
                )
            if isinstance(item, str) and _string_looks_like_local_path(item):
                raise GovernorHistoryAdmissionError(
                    f"{key_path} rejects arbitrary local path value"
                )
            out[key] = project_public_value(item, path=key_path)
        return out
    if isinstance(value, (list, tuple)):
        return [
            project_public_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, str):
        if _string_looks_like_local_path(value):
            raise GovernorHistoryAdmissionError(
                f"{path} rejects arbitrary local path value"
            )
        return value
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise GovernorHistoryAdmissionError(
        f"{path} public projection admits only strict JSON scalars/containers; "
        f"got {type(value).__name__}"
    )


def build_history_manifest(
    *,
    workspace: str,
    role: GovernorHistoryRole,
    generation: int,
    entry_cid: str,
    previous_head_cid: Optional[str],
    operation_id: str,
) -> dict[str, Any]:
    """Build the closed, content-addressed append-manifest for a history head."""

    workspace = validate_governor_workspace(workspace)
    role = _coerce_history_role(role)
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
        raise GovernorHistoryAdmissionError(
            "history manifest generation must be a positive integer"
        )
    entry_cid = validate_semantic_dag_json_cid(entry_cid, "entry_cid")
    if previous_head_cid is not None:
        previous_head_cid = validate_semantic_dag_json_cid(
            previous_head_cid, "previous_head_cid"
        )
    operation_id = validate_operation_id(operation_id)

    payload = {
        "schema": HISTORY_MANIFEST_SCHEMA,
        "interface_id": HISTORY_MANIFEST_INTERFACE,
        "workspace": workspace,
        "role": role.value,
        "generation": generation,
        "entry_cid": entry_cid,
        "previous_head_cid": previous_head_cid,
        "operation_id": operation_id,
    }
    # Fail closed: manifests are public-safe durable evidence.
    try:
        reject_private_raw_source(payload, path="manifest")
    except ValueError as exc:
        raise GovernorHistoryAdmissionError(str(exc)) from exc
    reject_public_local_paths(payload, path="manifest")
    return payload


def cid_for_history_manifest(manifest: Mapping[str, Any]) -> str:
    """Return the dag-json CIDv1 of a history-manifest mapping."""

    if not isinstance(manifest, Mapping):
        raise GovernorHistoryAdmissionError("history manifest must be a mapping")
    return cid_for_artifact(dict(manifest))


def _history_snapshot(
    root: Mapping[str, Any], *, history_role: GovernorHistoryRole
) -> HistoryHeadSnapshot:
    """Project a coordination-store root row into a history head snapshot."""

    try:
        return HistoryHeadSnapshot(
            namespace=str(root["namespace"]),
            head_cid=root.get("root_cid"),
            generation=int(root["revision"]),
            transition_cid=root.get("transition_cid"),
            history_role=history_role,
        )
    except (KeyError, TypeError, ValueError, SemanticGovernorStoreContractError) as exc:
        raise GovernorHistoryIntegrityError(
            f"invalid history head projection: {exc}"
        ) from exc


def _require_dag_json_optional(
    value: Optional[str], name: str
) -> Optional[str]:
    if value is None:
        return None
    try:
        return validate_semantic_dag_json_cid(value, name)
    except SemanticGovernorStoreContractError as exc:
        raise GovernorHistoryAdmissionError(str(exc)) from exc


def _clamp_page(*, offset: int, limit: int) -> tuple[int, int]:
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise GovernorHistoryAdmissionError("offset must be a non-negative integer")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise GovernorHistoryAdmissionError("limit must be a positive integer")
    if limit > MAX_HISTORY_PAGE_SIZE:
        raise GovernorHistoryAdmissionError(
            f"limit exceeds MAX_HISTORY_PAGE_SIZE ({limit} > {MAX_HISTORY_PAGE_SIZE})"
        )
    return offset, limit


# ---------------------------------------------------------------------------
# Store implementation
# ---------------------------------------------------------------------------


class DurableAuditHistoryStore:
    """Append-only audit/calibration/benchmark history over root CAS.

    Implements ``AuditHistoryStore``.  Each successful append:

    1. verifies the caller-supplied entry CID is already durable;
    2. materializes a deterministic history-manifest head that links the prior
       head and the new entry;
    3. CAS-publishes that manifest under the role namespace.

    Concurrent writers never silently overwrite: at most one CAS succeeds for a
    given expected generation.  The loser's immutable entry remains durable and
    can be re-appended against the successor head so both histories are
    preserved.  Transitions are never deleted.
    """

    def __init__(self, store: DurableCoordinationStore) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store

    @property
    def store(self) -> DurableCoordinationStore:
        """Injected coordination store (diagnostics / composition only)."""

        return self._store

    def _namespace(
        self, workspace: str, role: GovernorHistoryRole | str
    ) -> tuple[str, GovernorHistoryRole]:
        try:
            workspace = validate_governor_workspace(workspace)
            history_role = _coerce_history_role(role)
            return history_namespace(workspace, history_role), history_role
        except SemanticGovernorStoreContractError as exc:
            raise GovernorHistoryAdmissionError(str(exc)) from exc

    def current_history(
        self, workspace: str, role: GovernorHistoryRole | str
    ) -> HistoryHeadSnapshot:
        """Return the currently visible history head (generation zero if empty)."""

        namespace, history_role = self._namespace(workspace, role)
        try:
            root = self._store.current_state_root(namespace)
        except ArtifactIntegrityError as exc:
            raise GovernorHistoryIntegrityError(str(exc)) from exc
        snapshot = _history_snapshot(root, history_role=history_role)
        if snapshot.head_cid is not None:
            _require_dag_json_optional(snapshot.head_cid, "head_cid")
        if snapshot.transition_cid is not None:
            _require_dag_json_optional(snapshot.transition_cid, "transition_cid")
        return snapshot

    def append_history(
        self,
        workspace: str,
        role: GovernorHistoryRole | str,
        *,
        entry_cid: str,
        expected_generation: int,
        expected_head_cid: Optional[str],
        operation_id: str,
    ) -> HistoryAppendResult:
        """Atomically append one immutable entry or report a typed conflict.

        Preconditions (fail-closed):

        * generation-zero expects a null head CID; non-zero expects a head CID
        * ``entry_cid`` is a canonical dag-json CID already stored
        * ``operation_id`` is a durable idempotency key
        * the successor history-manifest is derived deterministically
        """

        namespace, history_role = self._namespace(workspace, role)
        try:
            expected_generation, expected_head_cid = validate_generation_expectation(
                expected_generation, expected_head_cid
            )
            operation_id = validate_operation_id(operation_id)
            entry_cid = validate_semantic_dag_json_cid(entry_cid, "entry_cid")
            if expected_head_cid is not None:
                expected_head_cid = validate_semantic_dag_json_cid(
                    expected_head_cid, "expected_head_cid"
                )
            workspace_token = validate_governor_workspace(workspace)
        except SemanticGovernorStoreContractError as exc:
            raise GovernorHistoryAdmissionError(str(exc)) from exc

        # Entry must already be durable — histories only reference immutable CIDs.
        try:
            self._store.get_bytes(entry_cid)
        except ArtifactNotFound:
            before = self._empty_or_current(workspace, history_role, namespace)
            return HistoryAppendResult(
                GovernorStoreStatus.UNAVAILABLE,
                before,
                before,
                entry_cid,
                None,
                "entry_unavailable",
                False,
                operation_id,
            )
        except ArtifactIntegrityError:
            before = self._empty_or_current(workspace, history_role, namespace)
            return HistoryAppendResult(
                GovernorStoreStatus.CORRUPT,
                before,
                before,
                entry_cid,
                None,
                "entry_integrity_failure",
                False,
                operation_id,
            )

        # Optionally enforce sealed kind when the entry is a governor envelope.
        self._admit_entry_kind(entry_cid, history_role)

        next_generation = expected_generation + 1
        try:
            manifest = build_history_manifest(
                workspace=workspace_token,
                role=history_role,
                generation=next_generation,
                entry_cid=entry_cid,
                previous_head_cid=expected_head_cid,
                operation_id=operation_id,
            )
        except SemanticGovernorStoreContractError as exc:
            raise GovernorHistoryAdmissionError(str(exc)) from exc

        manifest_cid = cid_for_history_manifest(manifest)
        if expected_head_cid is not None and expected_head_cid == manifest_cid:
            raise GovernorHistoryAdmissionError(
                "history manifest CID must differ from expected_head_cid"
            )

        # Persist the deterministic manifest before CAS so the successor exists.
        try:
            put_result = self._store.put(
                manifest,
                expected_cid=manifest_cid,
                codec="dag-json",
                replicate=False,
            )
        except ArtifactIntegrityError as exc:
            raise GovernorHistoryIntegrityError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise GovernorHistoryAdmissionError(str(exc)) from exc
        if str(put_result["cid"]) != manifest_cid:
            raise GovernorHistoryIntegrityError(
                f"store returned unexpected manifest CID {put_result['cid']!r}"
            )

        try:
            raw = self._store.compare_and_swap_state_root(
                namespace,
                expected_revision=expected_generation,
                expected_root_cid=expected_head_cid,
                new_root_cid=manifest_cid,
                operation_id=operation_id,
            )
        except ArtifactNotFound:
            before = self._empty_or_current(workspace, history_role, namespace)
            return HistoryAppendResult(
                GovernorStoreStatus.UNAVAILABLE,
                before,
                before,
                entry_cid,
                None,
                "successor_unavailable",
                False,
                operation_id,
            )
        except ArtifactIntegrityError:
            try:
                before = self.current_history(workspace, history_role)
            except GovernorHistoryIntegrityError:
                before = HistoryHeadSnapshot(
                    namespace, None, 0, None, history_role
                )
                return HistoryAppendResult(
                    GovernorStoreStatus.CORRUPT,
                    before,
                    before,
                    entry_cid,
                    None,
                    "integrity_failure",
                    False,
                    operation_id,
                )
            return HistoryAppendResult(
                GovernorStoreStatus.CORRUPT,
                before,
                before,
                entry_cid,
                None,
                "integrity_failure",
                False,
                operation_id,
            )
        except ValueError as exc:
            raise GovernorHistoryAdmissionError(str(exc)) from exc

        return self._result_from_wire(
            raw,
            history_role=history_role,
            entry_cid=entry_cid,
            operation_id=operation_id,
        )

    def append_audit(
        self,
        workspace: str,
        *,
        entry_cid: str,
        expected_generation: int,
        expected_head_cid: Optional[str],
        operation_id: str,
    ) -> HistoryAppendResult:
        """Append an audit entry to the workspace audit history."""

        return self.append_history(
            workspace,
            GovernorHistoryRole.AUDIT,
            entry_cid=entry_cid,
            expected_generation=expected_generation,
            expected_head_cid=expected_head_cid,
            operation_id=operation_id,
        )

    def append_calibration(
        self,
        workspace: str,
        *,
        entry_cid: str,
        expected_generation: int,
        expected_head_cid: Optional[str],
        operation_id: str,
    ) -> HistoryAppendResult:
        """Append a calibration entry to the workspace calibration history."""

        return self.append_history(
            workspace,
            GovernorHistoryRole.CALIBRATION,
            entry_cid=entry_cid,
            expected_generation=expected_generation,
            expected_head_cid=expected_head_cid,
            operation_id=operation_id,
        )

    def append_benchmark(
        self,
        workspace: str,
        *,
        entry_cid: str,
        expected_generation: int,
        expected_head_cid: Optional[str],
        operation_id: str,
    ) -> HistoryAppendResult:
        """Append a benchmark entry to the workspace benchmark history."""

        return self.append_history(
            workspace,
            GovernorHistoryRole.BENCHMARK,
            entry_cid=entry_cid,
            expected_generation=expected_generation,
            expected_head_cid=expected_head_cid,
            operation_id=operation_id,
        )

    def history_transitions(
        self,
        workspace: str,
        role: GovernorHistoryRole | str,
        *,
        offset: int = 0,
        limit: int = DEFAULT_HISTORY_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """Return immutable history root transitions in generation order (paged)."""

        namespace, _ = self._namespace(workspace, role)
        offset, limit = _clamp_page(offset=offset, limit=limit)
        rows = self._store.root_transitions(namespace)
        page = rows[offset : offset + limit]
        return [dict(row) for row in page]

    def list_entry_cids(
        self,
        workspace: str,
        role: GovernorHistoryRole | str,
        *,
        offset: int = 0,
        limit: int = DEFAULT_HISTORY_PAGE_SIZE,
    ) -> list[str]:
        """Return entry CIDs in append order by walking verified manifests (paged)."""

        offset, limit = _clamp_page(offset=offset, limit=limit)
        chain = self._walk_manifest_chain(workspace, role)
        page = chain[offset : offset + limit]
        return [item["entry_cid"] for item in page]

    def public_history_projection(
        self,
        workspace: str,
        role: GovernorHistoryRole | str,
        *,
        offset: int = 0,
        limit: int = DEFAULT_HISTORY_PAGE_SIZE,
    ) -> Mapping[str, Any]:
        """Return a portable public view of history heads and entry references.

        The projection contains only schema, namespace, role, generation, CIDs,
        and operation identifiers.  It never includes raw private source fields
        or arbitrary local filesystem paths.
        """

        offset, limit = _clamp_page(offset=offset, limit=limit)
        if limit > MAX_PUBLIC_PROJECTION_ENTRIES:
            raise GovernorHistoryAdmissionError(
                f"public projection limit exceeds MAX_PUBLIC_PROJECTION_ENTRIES "
                f"({limit} > {MAX_PUBLIC_PROJECTION_ENTRIES})"
            )

        head = self.current_history(workspace, role)
        chain = self._walk_manifest_chain(workspace, role)
        page = chain[offset : offset + limit]
        entries: list[dict[str, Any]] = []
        for item in page:
            entries.append(
                {
                    "generation": item["generation"],
                    "entry_cid": item["entry_cid"],
                    "head_cid": item["head_cid"],
                    "previous_head_cid": item["previous_head_cid"],
                    "operation_id": item["operation_id"],
                }
            )

        projection: dict[str, Any] = {
            "schema": HISTORY_PUBLIC_PROJECTION_SCHEMA,
            "interface_id": HISTORY_MODULE_INTERFACE,
            "namespace": head.namespace,
            "history_role": head.history_role.value,
            "generation": head.generation,
            "head_cid": head.head_cid,
            "transition_cid": head.transition_cid,
            "offset": offset,
            "limit": limit,
            "total_entries": len(chain),
            "entries": entries,
        }
        # Fail closed on accidental private/path leakage.
        try:
            reject_private_raw_source(projection, path="public")
        except ValueError as exc:
            raise GovernorHistoryAdmissionError(str(exc)) from exc
        reject_public_local_paths(projection, path="public")
        safe = project_public_value(projection, path="public")
        return MappingProxyType(safe)

    def private_history_projection(
        self,
        workspace: str,
        role: GovernorHistoryRole | str,
        *,
        offset: int = 0,
        limit: int = DEFAULT_HISTORY_PAGE_SIZE,
    ) -> Mapping[str, Any]:
        """Return a local-only projection that still omits raw private source.

        Private projections may include transition metadata for recovery and
        diagnostics but must never embed raw private source fields.  Absolute
        local paths are also rejected so a private view cannot be accidentally
        published as-is.
        """

        offset, limit = _clamp_page(offset=offset, limit=limit)
        head = self.current_history(workspace, role)
        transitions = self.history_transitions(
            workspace, role, offset=offset, limit=limit
        )
        chain = self._walk_manifest_chain(workspace, role)
        page = chain[offset : offset + limit]

        projection: dict[str, Any] = {
            "schema": HISTORY_PRIVATE_PROJECTION_SCHEMA,
            "interface_id": HISTORY_MODULE_INTERFACE,
            "namespace": head.namespace,
            "history_role": head.history_role.value,
            "generation": head.generation,
            "head_cid": head.head_cid,
            "transition_cid": head.transition_cid,
            "offset": offset,
            "limit": limit,
            "total_entries": len(chain),
            "entries": [
                {
                    "generation": item["generation"],
                    "entry_cid": item["entry_cid"],
                    "head_cid": item["head_cid"],
                    "previous_head_cid": item["previous_head_cid"],
                    "operation_id": item["operation_id"],
                    "manifest": item["manifest"],
                }
                for item in page
            ],
            "transitions": transitions,
        }
        try:
            reject_private_raw_source(projection, path="private")
        except ValueError as exc:
            raise GovernorHistoryAdmissionError(str(exc)) from exc
        reject_public_local_paths(projection, path="private")
        return MappingProxyType(json.loads(json.dumps(projection, sort_keys=True)))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _empty_or_current(
        self,
        workspace: str,
        history_role: GovernorHistoryRole,
        namespace: str,
    ) -> HistoryHeadSnapshot:
        try:
            return self.current_history(workspace, history_role)
        except GovernorHistoryError:
            return HistoryHeadSnapshot(namespace, None, 0, None, history_role)

    def _admit_entry_kind(
        self, entry_cid: str, history_role: GovernorHistoryRole
    ) -> None:
        """When the entry is a sealed governor envelope, require matching kind."""

        try:
            raw = self._store.get(entry_cid)
        except (ArtifactNotFound, ArtifactIntegrityError, TypeError, ValueError):
            return
        if not isinstance(raw, Mapping):
            return
        kind = raw.get("kind")
        if not isinstance(kind, str):
            # Plain application payload — admitted as long as the CID is durable.
            return
        expected = _ROLE_TO_ENTRY_KIND[history_role]
        # history_manifest heads are not valid entry payloads for append.
        if kind == "history_manifest":
            raise GovernorHistoryAdmissionError(
                "entry_cid must not be a history_manifest head"
            )
        if kind != expected:
            raise GovernorHistoryAdmissionError(
                f"entry kind {kind!r} is not valid for history role "
                f"{history_role.value!r} (expected {expected!r})"
            )

    def _load_manifest(self, head_cid: str) -> dict[str, Any]:
        try:
            raw = self._store.get(head_cid)
        except ArtifactNotFound as exc:
            raise GovernorHistoryIntegrityError(
                f"history head {head_cid} is missing"
            ) from exc
        except ArtifactIntegrityError as exc:
            raise GovernorHistoryIntegrityError(str(exc)) from exc
        if not isinstance(raw, Mapping):
            raise GovernorHistoryIntegrityError(
                f"history head {head_cid} is not a mapping"
            )
        manifest = dict(raw)
        if manifest.get("schema") != HISTORY_MANIFEST_SCHEMA:
            raise GovernorHistoryIntegrityError(
                f"history head {head_cid} has unknown manifest schema"
            )
        if manifest.get("interface_id") != HISTORY_MANIFEST_INTERFACE:
            raise GovernorHistoryIntegrityError(
                f"history head {head_cid} has unknown manifest interface"
            )
        try:
            validate_semantic_dag_json_cid(manifest.get("entry_cid"), "entry_cid")
        except SemanticGovernorStoreContractError as exc:
            raise GovernorHistoryIntegrityError(str(exc)) from exc
        previous = manifest.get("previous_head_cid")
        if previous is not None:
            try:
                validate_semantic_dag_json_cid(previous, "previous_head_cid")
            except SemanticGovernorStoreContractError as exc:
                raise GovernorHistoryIntegrityError(str(exc)) from exc
        recomputed = cid_for_history_manifest(manifest)
        if recomputed != head_cid:
            raise GovernorHistoryIntegrityError(
                f"history manifest CID mismatch: recomputed {recomputed}, "
                f"expected {head_cid}"
            )
        return manifest

    def _walk_manifest_chain(
        self, workspace: str, role: GovernorHistoryRole | str
    ) -> list[dict[str, Any]]:
        """Walk previous_head links from the live head back to genesis, then reverse."""

        head = self.current_history(workspace, role)
        if head.generation == 0 or head.head_cid is None:
            return []

        chain_rev: list[dict[str, Any]] = []
        seen: set[str] = set()
        cursor: Optional[str] = head.head_cid
        expected_generation = head.generation

        while cursor is not None:
            if cursor in seen:
                raise GovernorHistoryIntegrityError(
                    "history manifest chain contains a cycle"
                )
            seen.add(cursor)
            manifest = self._load_manifest(cursor)
            generation = manifest.get("generation")
            if generation != expected_generation:
                raise GovernorHistoryIntegrityError(
                    f"history manifest generation mismatch at {cursor}: "
                    f"expected {expected_generation}, got {generation!r}"
                )
            chain_rev.append(
                {
                    "generation": generation,
                    "entry_cid": str(manifest["entry_cid"]),
                    "head_cid": cursor,
                    "previous_head_cid": manifest.get("previous_head_cid"),
                    "operation_id": str(manifest.get("operation_id", "")),
                    "manifest": manifest,
                }
            )
            cursor = manifest.get("previous_head_cid")
            expected_generation -= 1
            if cursor is None and expected_generation != 0:
                raise GovernorHistoryIntegrityError(
                    "history manifest chain terminated before generation zero"
                )
            if expected_generation < 0:
                raise GovernorHistoryIntegrityError(
                    "history manifest chain is longer than head generation"
                )

        chain_rev.reverse()
        return chain_rev

    @staticmethod
    def _result_from_wire(
        raw: Mapping[str, Any],
        *,
        history_role: GovernorHistoryRole,
        entry_cid: str,
        operation_id: str,
    ) -> HistoryAppendResult:
        status = _status_from_wire(raw.get("status"))
        before = _history_snapshot(raw["before"], history_role=history_role)
        after = _history_snapshot(raw["after"], history_role=history_role)
        transition_cid = raw.get("transition_cid")
        if transition_cid is not None:
            try:
                transition_cid = validate_semantic_dag_json_cid(
                    transition_cid, "transition_cid"
                )
            except SemanticGovernorStoreContractError as exc:
                raise GovernorHistoryIntegrityError(str(exc)) from exc
        reason_code = raw.get("reason_code")
        if not isinstance(reason_code, str):
            raise GovernorHistoryIntegrityError(
                "history reason_code must be a string"
            )
        local_durable = bool(raw.get("local_durable"))
        wire_op = raw.get("operation_id", operation_id)
        if not isinstance(wire_op, str):
            wire_op = operation_id
        try:
            return HistoryAppendResult(
                status,
                before,
                after,
                entry_cid,
                transition_cid,
                reason_code,
                local_durable,
                wire_op,
            )
        except SemanticGovernorStoreContractError as exc:
            raise GovernorHistoryIntegrityError(str(exc)) from exc


__all__ = [
    "HISTORY_MODULE_INTERFACE",
    "HISTORY_MANIFEST_INTERFACE",
    "HISTORY_MANIFEST_SCHEMA",
    "HISTORY_PUBLIC_PROJECTION_SCHEMA",
    "HISTORY_PRIVATE_PROJECTION_SCHEMA",
    "DEFAULT_HISTORY_PAGE_SIZE",
    "MAX_HISTORY_PAGE_SIZE",
    "MAX_PUBLIC_PROJECTION_ENTRIES",
    "GovernorHistoryError",
    "GovernorHistoryAdmissionError",
    "GovernorHistoryIntegrityError",
    "build_history_manifest",
    "cid_for_history_manifest",
    "project_public_value",
    "reject_public_local_paths",
    "DurableAuditHistoryStore",
]
