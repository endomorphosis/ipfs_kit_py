"""Kit immutable blocks and root CAS on an already admitted native DuckDB owner.

This module never opens a database, owns a connection, or falls back to a file
store. The launcher supplies its live owner connection and shared transaction
lock. Reads are transaction-neutral so they can participate in a native status
snapshot. Persistence receipts do not confer semantic acceptance.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any

from .coordination_storage import (
    STATE_ROOT_TRANSITION_SCHEMA,
    ArtifactIntegrityError,
    ArtifactNotFound,
    CoordinationStorageError,
    DurableCoordinationStore,
    _artifact_kind,
    _canonical_json,
    cid_for_bytes,
    validate_transport_cid,
)


class NativeOwnerBindingError(CoordinationStorageError):
    """The supplied connection no longer belongs to the admitted owner."""


class DuckDBCoordinationStore:
    """A fixed namespace within an existing native owner's transaction domain.

    Construct after the owner reaches READY, outside a caller transaction.
    The caller retains connection ownership; this class deliberately has no
    close, path, backend, or connection-opening interface. All users of the
    supplied connection must use the same transaction lock.
    """

    _root_namespace = staticmethod(DurableCoordinationStore._root_namespace)
    _operation_id = staticmethod(DurableCoordinationStore._operation_id)
    _root_revision = staticmethod(DurableCoordinationStore._root_revision)

    def __init__(
        self,
        connection: Any,
        *,
        transaction_lock: Any,
        owner_identity: Mapping[str, Any],
        namespace: str,
    ) -> None:
        if not callable(getattr(connection, "execute", None)):
            raise TypeError("an existing native owner connection is required")
        if not all(
            callable(getattr(transaction_lock, name, None)) for name in ("__enter__", "__exit__")
        ):
            raise TypeError("the native owner's shared transaction lock is required")
        if not isinstance(owner_identity, Mapping):
            raise TypeError("owner_identity must be a mapping")
        self._namespace = self._root_namespace(namespace)
        self._connection = connection
        self._lock = transaction_lock
        self._identity = dict(owner_identity)
        self._namespace_initialized = False
        for name in ("store_id", "server_id", "database_uuid", "process_birth_id"):
            if not isinstance(self._identity.get(name), str) or not self._identity[name]:
                raise ValueError(f"owner_identity requires {name}")
        for name in ("generation", "fence_epoch", "schema_revision"):
            self._root_revision(self._identity.get(name), name)
        with self._lock:
            try:
                engine = self._connection.execute("SELECT current_setting('duckdb_api')").fetchone()
                if engine is None or not isinstance(engine[0], str) or not engine[0]:
                    raise NativeOwnerBindingError("an existing DuckDB owner connection is required")
                catalog = self._connection.execute(
                    "SELECT path FROM duckdb_databases() "
                    "WHERE database_name=current_database() AND internal=FALSE"
                ).fetchone()
                if catalog is None or not catalog[0] or catalog[0] == ":memory:":
                    raise NativeOwnerBindingError(
                        "durable receipts require a persistent native DuckDB catalog"
                    )
            except NativeOwnerBindingError:
                raise
            except Exception as exc:
                raise NativeOwnerBindingError(
                    "an existing DuckDB owner connection is required"
                ) from exc
        with self._write_transaction():
            for statement in (
                """CREATE TABLE IF NOT EXISTS kit_coordination_namespaces (
                    namespace VARCHAR PRIMARY KEY, store_id VARCHAR NOT NULL,
                    database_uuid VARCHAR NOT NULL, format_revision BIGINT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS kit_coordination_blocks (
                    namespace VARCHAR NOT NULL, cid VARCHAR NOT NULL,
                    kind VARCHAR NOT NULL, codec VARCHAR NOT NULL,
                    byte_length BIGINT NOT NULL, block_bytes BLOB NOT NULL,
                    PRIMARY KEY (namespace, cid))""",
                """CREATE TABLE IF NOT EXISTS kit_coordination_roots (
                    namespace VARCHAR PRIMARY KEY, root_cid VARCHAR NOT NULL,
                    revision BIGINT NOT NULL, transition_cid VARCHAR NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS kit_coordination_transitions (
                    namespace VARCHAR NOT NULL, operation_id VARCHAR NOT NULL,
                    transition_cid VARCHAR NOT NULL,
                    expected_root_cid VARCHAR, expected_revision BIGINT NOT NULL,
                    new_root_cid VARCHAR NOT NULL, new_revision BIGINT NOT NULL,
                    created_at_ms BIGINT NOT NULL,
                    PRIMARY KEY (namespace, operation_id),
                    UNIQUE (namespace, new_revision), UNIQUE (namespace, transition_cid))""",
            ):
                self._connection.execute(statement)
            row = self._connection.execute(
                "SELECT store_id, database_uuid, format_revision "
                "FROM kit_coordination_namespaces WHERE namespace=?",
                [self.namespace],
            ).fetchone()
            expected = (self._identity["store_id"], self._identity["database_uuid"], 1)
            if row is None:
                self._connection.execute(
                    "INSERT INTO kit_coordination_namespaces VALUES (?, ?, ?, ?)",
                    [self.namespace, *expected],
                )
            elif tuple(row[i] for i in range(3)) != expected:
                raise NativeOwnerBindingError("namespace belongs to a different store or format")
        self._namespace_initialized = True

    @property
    def namespace(self) -> str:
        """The launcher-selected namespace cannot be retargeted through the API."""
        return self._namespace

    def _assert_owner(self) -> None:
        identity = self._identity
        try:
            row = self._connection.execute(
                "SELECT generation, schema_revision, fence_epoch, database_uuid, birth_id "
                "FROM store_generations ORDER BY generation DESC LIMIT 1"
            ).fetchone()
            expected = tuple(
                identity[name]
                for name in (
                    "generation",
                    "schema_revision",
                    "fence_epoch",
                    "database_uuid",
                    "process_birth_id",
                )
            )
            if row is None or tuple(row[i] for i in range(5)) != expected:
                raise NativeOwnerBindingError("native owner generation or fence is stale")
            server = self._connection.execute(
                "SELECT store_id, database_uuid, process_birth_id, generation, schema_revision, "
                "status, stopped_at FROM state_servers WHERE server_id=?",
                [identity["server_id"]],
            ).fetchone()
            expected_server = tuple(
                identity[name]
                for name in (
                    "store_id",
                    "database_uuid",
                    "process_birth_id",
                    "generation",
                    "schema_revision",
                )
            )
            if (
                server is None
                or tuple(server[i] for i in range(5)) != expected_server
                or server[5] != "ready"
                or server[6] is not None
            ):
                raise NativeOwnerBindingError("native server identity is not the ready owner")
            if self._namespace_initialized:
                binding = self._connection.execute(
                    "SELECT store_id, database_uuid, format_revision "
                    "FROM kit_coordination_namespaces WHERE namespace=?",
                    [self.namespace],
                ).fetchone()
                expected_binding = (identity["store_id"], identity["database_uuid"], 1)
                if binding is None or tuple(binding[i] for i in range(3)) != expected_binding:
                    raise NativeOwnerBindingError("native namespace binding is missing or changed")
        except NativeOwnerBindingError:
            raise
        except Exception as exc:
            raise NativeOwnerBindingError("native owner identity is unavailable") from exc

    @contextmanager
    def _write_transaction(self):
        with self._lock:
            self._assert_owner()
            # If BEGIN fails (e.g. the caller already owns a transaction), do not
            # roll back that caller's transaction.
            self._connection.execute("BEGIN TRANSACTION")
            try:
                yield
                self._assert_owner()
                self._connection.execute("COMMIT")
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise

    def _require_namespace(self, namespace: str) -> str:
        if self._root_namespace(namespace) != self.namespace:
            raise ValueError("namespace is outside the bound native owner scope")
        return namespace

    def _transition_fields(self, artifact: Mapping[str, Any]) -> dict[str, Any]:
        return DurableCoordinationStore._state_root_transition_fields(self, artifact)

    def _read_bytes(self, cid: str) -> bytes:
        codec = validate_transport_cid(cid)
        row = self._connection.execute(
            "SELECT kind, codec, byte_length, block_bytes FROM kit_coordination_blocks "
            "WHERE namespace=? AND cid=?",
            [self.namespace, cid],
        ).fetchone()
        if row is None:
            raise ArtifactNotFound(cid)
        data = bytes(row[3])
        if row[1] != codec or row[2] != len(data) or cid_for_bytes(data, codec=codec) != cid:
            raise ArtifactIntegrityError("native coordination block metadata or CID mismatch")
        try:
            artifact = json.loads(data)
            if not isinstance(artifact, dict) or _canonical_json(artifact) != data:
                raise ValueError("noncanonical artifact")
            if _artifact_kind(artifact) != row[0]:
                raise ValueError("artifact kind differs")
        except (ValueError, TypeError, UnicodeError) as exc:
            raise ArtifactIntegrityError("native coordination artifact is invalid") from exc
        return data

    def _read_artifact(self, cid: str) -> dict[str, Any]:
        return json.loads(self._read_bytes(cid))

    def _insert_block(self, artifact: Mapping[str, Any], data: bytes, cid: str, codec: str) -> bool:
        row = self._connection.execute(
            "SELECT cid FROM kit_coordination_blocks WHERE namespace=? AND cid=?",
            [self.namespace, cid],
        ).fetchone()
        if row is not None:
            if self._read_bytes(cid) != data:
                raise ArtifactIntegrityError("immutable native coordination block differs")
            return False
        self._connection.execute(
            "INSERT INTO kit_coordination_blocks VALUES (?, ?, ?, ?, ?, ?)",
            [self.namespace, cid, _artifact_kind(artifact), codec, len(data), data],
        )
        return True

    def put(
        self,
        artifact: Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        codec: str = "dag-json",
        replicate: bool = False,
    ) -> dict[str, Any]:
        if replicate is not False:
            raise ValueError("native owner storage has no replication backend")
        if not isinstance(artifact, Mapping):
            raise TypeError("artifact must be a mapping")
        kind = _artifact_kind(artifact)
        data = _canonical_json(artifact)
        cid = cid_for_bytes(data, codec=codec)
        if expected_cid is not None and cid != expected_cid:
            raise ArtifactIntegrityError("artifact CID does not match expected_cid")
        if artifact.get("schema") == STATE_ROOT_TRANSITION_SCHEMA:
            fields = self._transition_fields(artifact)
            self._require_namespace(fields["namespace"])
        with self._write_transaction():
            created = self._insert_block(artifact, data, cid, codec)
        return {
            "cid": cid,
            "kind": kind,
            "codec": codec,
            "byte_length": len(data),
            "created": created,
            "replicated": False,
            "durable": True,
        }

    def get_bytes(self, cid: str) -> bytes:
        with self._lock:
            self._assert_owner()
            return self._read_bytes(cid)

    def get(self, cid: str) -> dict[str, Any]:
        with self._lock:
            self._assert_owner()
            return self._read_artifact(cid)

    def has(self, cid: str, *, include_backend: bool = False) -> bool:
        if include_backend is not False:
            raise ValueError("native owner storage has no alternate backend")
        with self._lock:
            self._assert_owner()
            try:
                self._read_bytes(cid)
            except ArtifactNotFound:
                return False
            return True

    def _verified_root(self) -> dict[str, Any]:
        namespace = self.namespace
        before = {"namespace": namespace, "root_cid": None, "revision": 0, "transition_cid": None}
        root_row = self._connection.execute(
            "SELECT root_cid, revision, transition_cid FROM kit_coordination_roots WHERE namespace=?",
            [namespace],
        ).fetchone()
        rows = self._connection.execute(
            "SELECT operation_id, transition_cid, expected_root_cid, expected_revision, "
            "new_root_cid, new_revision, created_at_ms FROM kit_coordination_transitions "
            "WHERE namespace=? ORDER BY new_revision",
            [namespace],
        ).fetchall()
        for row in rows:
            operation_id, cid, expected_cid, expected_revision, new_cid, new_revision, created = (
                row[i] for i in range(7)
            )
            try:
                if validate_transport_cid(cid) != "dag-json":
                    raise ValueError("transition requires dag-json")
                fields = self._transition_fields(self._read_artifact(cid))
                expected_fields = dict(
                    namespace=namespace,
                    operation_id=operation_id,
                    expected_root_cid=expected_cid,
                    expected_revision=expected_revision,
                    new_root_cid=new_cid,
                    new_revision=new_revision,
                    created_at_ms=created,
                )
                if fields != expected_fields:
                    raise ValueError("transition metadata differs from immutable content")
                if expected_cid != before["root_cid"] or expected_revision != before["revision"]:
                    raise ValueError("transition chain predecessor differs")
                self._read_bytes(new_cid)
            except (ValueError, TypeError, ArtifactNotFound) as exc:
                raise ArtifactIntegrityError(
                    "native state root chain is incomplete or corrupt"
                ) from exc
            before = dict(
                namespace=namespace, root_cid=new_cid, revision=new_revision, transition_cid=cid
            )
        expected_row = (
            None if not rows else (before["root_cid"], before["revision"], before["transition_cid"])
        )
        if (None if root_row is None else tuple(root_row[i] for i in range(3))) != expected_row:
            raise ArtifactIntegrityError(
                "native state root pointer differs from its transition chain"
            )
        return before

    def current_state_root(self, namespace: str) -> dict[str, Any]:
        self._require_namespace(namespace)
        with self._lock:
            self._assert_owner()
            return self._verified_root()

    def compare_and_swap_state_root(
        self,
        namespace: str,
        *,
        expected_revision: int,
        expected_root_cid: str | None,
        new_root_cid: str,
        operation_id: str,
    ) -> dict[str, Any]:
        self._require_namespace(namespace)
        operation_id = self._operation_id(operation_id)
        expected_revision, expected_root_cid = DurableCoordinationStore._root_expectation(
            expected_revision, expected_root_cid
        )
        validate_transport_cid(new_root_cid)
        if new_root_cid == expected_root_cid:
            raise ValueError("new root must differ from expected root")
        with self._write_transaction():
            before = self._verified_root()
            prior = self._connection.execute(
                "SELECT expected_revision, expected_root_cid, new_root_cid "
                "FROM kit_coordination_transitions WHERE namespace=? AND operation_id=?",
                [namespace, operation_id],
            ).fetchone()
            reason = None
            if prior is not None:
                reason = (
                    "idempotent_replay"
                    if tuple(prior[i] for i in range(3))
                    == (expected_revision, expected_root_cid, new_root_cid)
                    else "operation_id_reused"
                )
            else:
                self._read_bytes(new_root_cid)
                if (
                    before["revision"] != expected_revision
                    or before["root_cid"] != expected_root_cid
                ):
                    reason = "stale_expectation"
            if reason is not None:
                return {
                    "status": "unchanged" if reason == "idempotent_replay" else "conflict",
                    "before": before,
                    "after": dict(before),
                    "transition_cid": None,
                    "reason_code": reason,
                    "local_durable": True,
                    "replicated": False,
                }
            transition = dict(
                schema=STATE_ROOT_TRANSITION_SCHEMA,
                namespace=namespace,
                operation_id=operation_id,
                expected_root_cid=expected_root_cid,
                expected_revision=expected_revision,
                new_root_cid=new_root_cid,
                new_revision=expected_revision + 1,
                created_at_ms=time.time_ns() // 1_000_000,
            )
            self._transition_fields(transition)
            data = _canonical_json(transition)
            cid = cid_for_bytes(data)
            self._insert_block(transition, data, cid, "dag-json")
            self._connection.execute(
                "INSERT INTO kit_coordination_transitions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    namespace,
                    operation_id,
                    cid,
                    expected_root_cid,
                    expected_revision,
                    new_root_cid,
                    expected_revision + 1,
                    transition["created_at_ms"],
                ],
            )
            self._connection.execute(
                "INSERT INTO kit_coordination_roots VALUES (?, ?, ?, ?) "
                "ON CONFLICT (namespace) DO UPDATE SET root_cid=excluded.root_cid, "
                "revision=excluded.revision, transition_cid=excluded.transition_cid",
                [namespace, new_root_cid, expected_revision + 1, cid],
            )
            after = dict(
                namespace=namespace,
                root_cid=new_root_cid,
                revision=expected_revision + 1,
                transition_cid=cid,
            )
        return {
            "status": "updated",
            "before": before,
            "after": after,
            "transition_cid": cid,
            "reason_code": "updated",
            "local_durable": True,
            "replicated": False,
        }

    current_root = current_state_root
    compare_and_swap_root = compare_and_swap_state_root
