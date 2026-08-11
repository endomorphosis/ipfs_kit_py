"""Durable CID storage and recovery for MCP++ coordination artifacts.

The immutable block store is authoritative.  The SQLite database is a local,
rebuildable acceleration structure for claims, leases, and daemon health.  A
retention pass may remove terminal/expired rows from those indexes, but never
removes their content-addressed blocks.

An optional backend can be a Kubo client (``add_bytes``/``cat``), a Helia
bridge (``put``/``get``), or an object implementing ``store_block`` and
``load_block``.  Local durable storage is always written first, making restart
recovery independent of daemon availability; backend reads repair the local
copy.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional, Protocol, Tuple

from .state_root_contracts import RootUpdateStatus, StateRootCASResult, StateRootSnapshot


PROFILE_G_PREFIX = "mcp++/profile-g/"
COORDINATION_ARCHIVE_SCHEMA = "mcp++/coordination-index-archive@1"
DAEMON_HEALTH_SCHEMA = "mcp++/coordination/daemon-health@1"
STATE_ROOT_TRANSITION_SCHEMA = "mcp++/coordination/state-root-transition@1"
_STATE_ROOT_OPERATION_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")
PROFILE_G_KINDS = {
    "goal": "Goal",
    "subgoal": "Subgoal",
    "plan-branch": "PlanBranch",
    "plan-selection": "PlanSelection",
    "task": "TaskSpec",
    "risk-model": "RiskModel",
    "risk-evidence": "RiskEvidence",
    "risk-assessment": "RiskAssessment",
    "neighborhood-record": "NeighborhoodRecord",
    "neighborhood-attestation": "NeighborhoodAttestation",
    "schedule-proposal": "ScheduleProposal",
    "task-claim": "TaskClaim",
    "claim-resolution": "ClaimResolution",
    "task-receipt": "TaskReceipt",
}


class CoordinationStorageError(RuntimeError):
    """Base error for durable coordination storage."""


class ArtifactNotFound(CoordinationStorageError, KeyError):
    """Raised when neither the local block store nor backend has a CID."""


class ArtifactIntegrityError(CoordinationStorageError):
    """Raised when bytes do not match their declared CID."""


class BlockBackend(Protocol):
    """Minimal interface understood by :class:`DurableCoordinationStore`."""

    def store_block(self, cid: str, data: bytes, codec: str) -> Any: ...
    def load_block(self, cid: str) -> bytes: ...


@dataclass(frozen=True)
class RetentionPolicy:
    """Index retention policy; immutable artifact blocks are always retained."""

    terminal_claim_ms: int = 7 * 24 * 60 * 60 * 1000
    expired_lease_ms: int = 7 * 24 * 60 * 60 * 1000
    expired_health_ms: int = 24 * 60 * 60 * 1000

    def __post_init__(self) -> None:
        if min(self.terminal_claim_ms, self.expired_lease_ms, self.expired_health_ms) < 0:
            raise ValueError("retention durations must be non-negative")


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"artifact is not canonical JSON: {exc}") from exc


def _varint(value: int) -> bytes:
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def cid_for_bytes(data: bytes, codec: str = "dag-json") -> str:
    """Return CIDv1/sha2-256 using the canonical Profile G codec by default."""

    codec_code = {"raw": 0x55, "dag-json": 0x0129}.get(codec)
    if codec_code is None:
        raise ValueError(f"unsupported CID codec: {codec}")
    digest = hashlib.sha256(data).digest()
    binary = _varint(1) + _varint(codec_code) + _varint(0x12) + _varint(len(digest)) + digest
    return "b" + base64.b32encode(binary).decode("ascii").lower().rstrip("=")


def cid_for_artifact(artifact: Mapping[str, Any], codec: str = "dag-json") -> str:
    return cid_for_bytes(_canonical_json(artifact), codec)


def _codec_from_cid(cid: str) -> str:
    try:
        padded = cid[1:].upper() + "=" * ((8 - len(cid[1:]) % 8) % 8)
        data = base64.b32decode(padded)

        def read(offset: int) -> tuple[int, int]:
            value = shift = 0
            while offset < len(data):
                byte = data[offset]
                offset += 1
                value |= (byte & 0x7F) << shift
                if not byte & 0x80:
                    return value, offset
                shift += 7
            raise ValueError

        version, offset = read(0)
        codec_code, _ = read(offset)
        if version != 1:
            raise ValueError
        return {0x55: "raw", 0x0129: "dag-json"}[codec_code]
    except (ValueError, KeyError, TypeError, base64.binascii.Error) as exc:
        raise ValueError("unsupported or malformed CID") from exc


def _artifact_kind(artifact: Mapping[str, Any]) -> str:
    schema = artifact.get("schema")
    if not isinstance(schema, str) or not schema:
        raise ValueError("coordination artifact requires a non-empty schema")
    if schema.startswith(PROFILE_G_PREFIX) and schema.endswith("@1"):
        schema_name = schema[len(PROFILE_G_PREFIX) : -2]
        try:
            return PROFILE_G_KINDS[schema_name]
        except KeyError as exc:
            raise ValueError(f"unknown Profile G artifact schema: {schema}") from exc
    if schema == DAEMON_HEALTH_SCHEMA:
        return "DaemonHealth"
    if schema == COORDINATION_ARCHIVE_SCHEMA:
        return "CoordinationArchive"
    if schema == STATE_ROOT_TRANSITION_SCHEMA:
        return "StateRootTransition"
    return str(artifact.get("kind") or schema)


def _require_string(artifact: Mapping[str, Any], name: str) -> str:
    value = artifact.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _require_integer(artifact: Mapping[str, Any], name: str, minimum: int = 0) -> int:
    value = artifact.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


class IPFSHeliaBlockBackend:
    """Adapter for common Kubo and Helia Python/bridge client shapes.

    Helia is normally hosted in a JavaScript process.  A small bridge can expose
    ``put(data, cid=..., codec=...)`` and ``get(cid)``; Kubo clients commonly
    expose ``add_bytes`` and ``cat``.  Returned CIDs are checked when available.
    """

    def __init__(self, client: Any) -> None:
        self.client = client

    @staticmethod
    def _returned_cid(result: Any) -> Optional[str]:
        if isinstance(result, str):
            return result
        if isinstance(result, Mapping):
            value = result.get("cid") or result.get("Hash") or result.get("hash")
            if isinstance(value, Mapping):
                value = value.get("/")
            return str(value) if value else None
        return None

    def store_block(self, cid: str, data: bytes, codec: str) -> Any:
        client = self.client
        if hasattr(client, "store_block"):
            result = client.store_block(cid, data, codec)
        elif hasattr(client, "put"):
            try:
                result = client.put(data, cid=cid, codec=codec)
            except TypeError:
                result = client.put(cid, data)
        elif hasattr(client, "block") and hasattr(client.block, "put"):
            result = client.block.put(data, format=codec, mhtype="sha2-256")
        elif hasattr(client, "dag") and hasattr(client.dag, "put") and codec == "dag-json":
            result = client.dag.put(
                json.loads(data.decode("utf-8")), store_codec="dag-json", input_codec="dag-json", hash="sha2-256"
            )
        elif hasattr(client, "add_bytes") and codec == "raw":
            result = client.add_bytes(data)
        elif hasattr(client, "block_put"):
            result = client.block_put(data, cid_codec=codec, mhtype="sha2-256")
        else:
            raise TypeError("IPFS/Helia client has no supported block write method")
        returned = self._returned_cid(result)
        # Kubo add_bytes creates raw CIDs. A bridge may omit its result. Only
        # compare like-for-like CID results; callers choose the matching codec.
        if returned and returned != cid:
            raise ArtifactIntegrityError(f"backend returned {returned}, expected {cid}")
        return result

    def load_block(self, cid: str) -> bytes:
        client = self.client
        if hasattr(client, "load_block"):
            result = client.load_block(cid)
        elif hasattr(client, "block") and hasattr(client.block, "get"):
            result = client.block.get(cid)
        elif hasattr(client, "cat"):
            result = client.cat(cid)
        elif hasattr(client, "block_get"):
            result = client.block_get(cid)
        elif hasattr(client, "get"):
            result = client.get(cid)
        else:
            raise TypeError("IPFS/Helia client has no supported block read method")
        if isinstance(result, str):
            return result.encode("utf-8")
        if isinstance(result, (bytes, bytearray, memoryview)):
            return bytes(result)
        if isinstance(result, Mapping) and isinstance(result.get("data"), (bytes, bytearray, memoryview)):
            return bytes(result["data"])
        raise TypeError("IPFS/Helia client returned non-byte block data")


class DurableCoordinationStore:
    """Immutable artifact persistence with rebuildable claim/lease indexes."""

    DB_VERSION = 1

    def __init__(
        self,
        storage_dir: Optional[os.PathLike[str] | str] = None,
        *,
        backend: Optional[BlockBackend | Any] = None,
        retention: Optional[RetentionPolicy] = None,
        clock_ms: Optional[Any] = None,
    ) -> None:
        root = storage_dir or os.environ.get(
            "MCPPLUSPLUS_COORDINATION_DIR",
            os.path.expanduser("~/.local/share/ipfs_kit_py/mcppp_coordination"),
        )
        self.root = Path(root)
        self.blocks_dir = self.root / "blocks"
        self.db_path = self.root / "coordination.sqlite3"
        self.blocks_dir.mkdir(parents=True, exist_ok=True)
        self.backend = (
            backend
            if backend is None or (hasattr(backend, "store_block") and hasattr(backend, "load_block"))
            else IPFSHeliaBlockBackend(backend)
        )
        self.retention = retention or RetentionPolicy()
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self._lock = threading.RLock()
        self._connection = self._open_database()
        # A missing/recreated index next to existing blocks is recovered
        # automatically. Operators can also request an explicit full rebuild.
        indexed = int(self._connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0])
        has_blocks = next(self.blocks_dir.glob("*/*.json"), None) is not None
        self.recover(rebuild=has_blocks and indexed == 0)

    def _open_database(self) -> sqlite3.Connection:
        try:
            return self._connect_database()
        except sqlite3.DatabaseError:
            # Immutable blocks, not SQLite, are authoritative. Preserve the bad
            # file for diagnosis and recreate a clean index on startup.
            if self.db_path.exists():
                corrupt = self.db_path.with_name(f"{self.db_path.name}.corrupt-{int(time.time() * 1000)}")
                self.db_path.replace(corrupt)
            for suffix in ("-wal", "-shm"):
                Path(f"{self.db_path}{suffix}").unlink(missing_ok=True)
            return self._connect_database()

    def _connect_database(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
            self._create_schema(connection)
            return connection
        except Exception:
            connection.close()
            raise

    @classmethod
    def _create_schema(cls, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS artifacts (
              cid TEXT PRIMARY KEY, kind TEXT NOT NULL, schema_uri TEXT NOT NULL,
              codec TEXT NOT NULL, byte_length INTEGER NOT NULL, stored_at_ms INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS claims (
              claim_cid TEXT PRIMARY KEY REFERENCES artifacts(cid), task_cid TEXT NOT NULL,
              proposal_cid TEXT NOT NULL, claimant_did TEXT NOT NULL, logical_epoch INTEGER NOT NULL,
              requested_lease_ms INTEGER NOT NULL, attempt INTEGER NOT NULL,
              created_at_ms INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
              resolution_cid TEXT
            );
            CREATE INDEX IF NOT EXISTS claims_task_epoch ON claims(task_cid, logical_epoch DESC, created_at_ms DESC);
            CREATE TABLE IF NOT EXISTS leases (
              resolution_cid TEXT PRIMARY KEY REFERENCES artifacts(cid), task_cid TEXT NOT NULL,
              claim_cid TEXT NOT NULL, logical_epoch INTEGER NOT NULL, fencing_token INTEGER NOT NULL,
              expires_at_ms INTEGER NOT NULL, outcome TEXT NOT NULL, active INTEGER NOT NULL,
              created_at_ms INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS leases_active_task ON leases(task_cid, active, logical_epoch DESC, fencing_token DESC);
            CREATE TABLE IF NOT EXISTS daemon_health (
              health_cid TEXT PRIMARY KEY REFERENCES artifacts(cid), peer_did TEXT NOT NULL,
              status TEXT NOT NULL, observed_at_ms INTEGER NOT NULL, expires_at_ms INTEGER NOT NULL,
              capacity_millionths INTEGER NOT NULL, artifact_kind TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS health_peer_expiry ON daemon_health(peer_did, expires_at_ms DESC);
            CREATE TABLE IF NOT EXISTS index_archives (
              archive_cid TEXT PRIMARY KEY REFERENCES artifacts(cid), created_at_ms INTEGER NOT NULL,
              row_count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS state_roots (
              namespace TEXT PRIMARY KEY, root_cid TEXT, revision INTEGER NOT NULL,
              transition_cid TEXT
            );
            CREATE TABLE IF NOT EXISTS root_transitions (
              transition_cid TEXT PRIMARY KEY REFERENCES artifacts(cid), namespace TEXT NOT NULL,
              operation_id TEXT NOT NULL, expected_root_cid TEXT, expected_revision INTEGER NOT NULL,
              successor_cid TEXT NOT NULL, successor_revision INTEGER NOT NULL,
              created_at_ms INTEGER NOT NULL,
              UNIQUE(namespace, operation_id)
            );
            CREATE INDEX IF NOT EXISTS root_transitions_namespace_revision
              ON root_transitions(namespace, successor_revision);
            """
        )
        connection.execute(
            "INSERT OR REPLACE INTO metadata(key,value) VALUES('version',?)", (str(cls.DB_VERSION),)
        )
        connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "DurableCoordinationStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _block_path(self, cid: str) -> Path:
        if not cid.startswith("b") or any(char not in "abcdefghijklmnopqrstuvwxyz234567" for char in cid):
            raise ValueError("CID must be lowercase base32")
        directory = self.blocks_dir / cid[1:3]
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{cid}.json"

    def _write_block(self, cid: str, data: bytes) -> bool:
        path = self._block_path(cid)
        if path.exists():
            existing = path.read_bytes()
            if existing != data:
                raise ArtifactIntegrityError(f"immutable block collision for {cid}")
            return False
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise ArtifactIntegrityError(f"immutable block collision for {cid}")
            return True
        finally:
            temporary.unlink(missing_ok=True)

    def put(
        self,
        artifact: Mapping[str, Any],
        *,
        expected_cid: Optional[str] = None,
        codec: str = "dag-json",
        replicate: bool = True,
    ) -> Dict[str, Any]:
        """Durably store and index an artifact, returning only after fsync/commit."""

        if not isinstance(artifact, Mapping):
            raise ValueError("artifact must be an object")
        value = dict(artifact)
        kind = _artifact_kind(value)
        data = _canonical_json(value)
        cid = cid_for_bytes(data, codec)
        if expected_cid is not None and expected_cid != cid:
            raise ArtifactIntegrityError(f"artifact CID {cid} does not match expected {expected_cid}")
        stored_at = int(self._clock_ms())
        with self._lock:
            created = self._write_block(cid, data)
            with self._connection:
                self._connection.execute(
                    "INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?,?,?)",
                    (cid, kind, str(value["schema"]), codec, len(data), stored_at),
                )
                self._index_artifact(self._connection, cid, kind, value)
        replicated = False
        if replicate and self.backend is not None:
            self.backend.store_block(cid, data, codec)
            replicated = True
        return {
            "cid": cid,
            "kind": kind,
            "codec": codec,
            "byte_length": len(data),
            "created": created,
            "replicated": replicated,
            "durable": True,
        }

    def put_profile_g(self, kind: str, artifact: Mapping[str, Any], *, expected_cid: Optional[str] = None) -> Dict[str, Any]:
        """Store a canonical Profile G artifact and verify its declared kind."""

        actual_kind = _artifact_kind(artifact)
        if actual_kind != kind:
            raise ValueError(f"artifact kind is {actual_kind}, expected {kind}")
        return self.put(artifact, expected_cid=expected_cid, codec="dag-json")

    def get_bytes(self, cid: str) -> bytes:
        codec = _codec_from_cid(cid)
        path = self._block_path(cid)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            if self.backend is None:
                raise ArtifactNotFound(cid)
            try:
                data = self.backend.load_block(cid)
            except Exception as exc:
                raise ArtifactNotFound(cid) from exc
            # Codec is discoverable from CID, but coordination artifacts use
            # dag-json. Integrity validation happens before local repair.
            if cid_for_bytes(data, codec) != cid:
                raise ArtifactIntegrityError(f"backend bytes do not match {cid}")
            with self._lock:
                self._write_block(cid, data)
        if cid_for_bytes(data, codec) != cid:
            raise ArtifactIntegrityError(f"local bytes do not match {cid}")
        return data

    def get(self, cid: str) -> Dict[str, Any]:
        data = self.get_bytes(cid)
        try:
            value = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ArtifactIntegrityError(f"{cid} is not canonical JSON") from exc
        if not isinstance(value, dict) or _canonical_json(value) != data:
            raise ArtifactIntegrityError(f"{cid} is not canonical JSON")
        return value

    def has(self, cid: str, *, include_backend: bool = False) -> bool:
        if self._block_path(cid).is_file():
            return True
        if include_backend and self.backend is not None:
            try:
                self.get_bytes(cid)
                return True
            except CoordinationStorageError:
                return False
        return False

    @staticmethod
    def _validate_state_root_operation(namespace: str, expected_revision: int,
                                       expected_root_cid: Optional[str], new_root_cid: str,
                                       operation_id: str) -> None:
        """Validate the closed root-CAS inputs without deriving any semantic CID."""

        # The closed contract is the source of truth for namespace and CID
        # syntax. A non-zero snapshot only needs a syntactically valid
        # transition CID, so a valid root CID can safely stand in here.
        StateRootSnapshot(namespace, None, 0, None)
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise ValueError("expected_revision must be a non-negative integer")
        if expected_root_cid is not None:
            StateRootSnapshot(namespace, expected_root_cid, 1, expected_root_cid)
        StateRootSnapshot(namespace, new_root_cid, 1, new_root_cid)
        if not isinstance(operation_id, str) or not _STATE_ROOT_OPERATION_ID.fullmatch(operation_id):
            raise ValueError("operation_id must be a normalized identifier")
        if (expected_revision == 0) != (expected_root_cid is None):
            raise ValueError("revision-zero expectations require no root CID")

    @staticmethod
    def _state_root_snapshot_from_row(namespace: str, row: Optional[sqlite3.Row]) -> StateRootSnapshot:
        if row is None:
            return StateRootSnapshot(namespace, None, 0, None)
        return StateRootSnapshot(namespace, row["root_cid"], int(row["revision"]), row["transition_cid"])

    def current_state_root(self, namespace: str) -> StateRootSnapshot:
        """Return the currently visible root, or the revision-zero empty root."""

        StateRootSnapshot(namespace, None, 0, None)
        with self._lock:
            row = self._connection.execute(
                "SELECT root_cid,revision,transition_cid FROM state_roots WHERE namespace=?", (namespace,)
            ).fetchone()
            return self._state_root_snapshot_from_row(namespace, row)

    def compare_and_swap_state_root(
        self,
        namespace: str,
        *,
        expected_revision: int,
        expected_root_cid: Optional[str],
        new_root_cid: str,
        operation_id: str,
    ) -> StateRootCASResult:
        """Atomically publish a verified successor root under CID-plus-revision CAS.

        The successor is verified before entering the writer transaction.  The
        immutable transition block, its index, and the visible root row are
        then made durable as one SQLite transaction.
        """

        self._validate_state_root_operation(
            namespace, expected_revision, expected_root_cid, new_root_cid, operation_id
        )
        # This verifies both local bytes and CID integrity.  A missing or
        # corrupt successor therefore cannot become visible.
        self.get_bytes(new_root_cid)

        with self._lock:
            connection = self._connection
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT root_cid,revision,transition_cid FROM state_roots WHERE namespace=?", (namespace,)
                ).fetchone()
                before = self._state_root_snapshot_from_row(namespace, row)
                prior_operation = connection.execute(
                    """SELECT expected_root_cid,expected_revision,successor_cid,successor_revision
                       FROM root_transitions WHERE namespace=? AND operation_id=?""",
                    (namespace, operation_id),
                ).fetchone()
                if prior_operation is not None:
                    same_operation = (
                        prior_operation["expected_root_cid"] == expected_root_cid
                        and int(prior_operation["expected_revision"]) == expected_revision
                        and prior_operation["successor_cid"] == new_root_cid
                        and int(prior_operation["successor_revision"]) == expected_revision + 1
                    )
                    connection.execute("COMMIT")
                    return StateRootCASResult(
                        RootUpdateStatus.UNCHANGED if same_operation else RootUpdateStatus.CONFLICT,
                        before, before, None,
                        "replayed" if same_operation else "operation_id_reused", True, False,
                    )
                if before.revision != expected_revision or before.root_cid != expected_root_cid:
                    connection.execute("COMMIT")
                    return StateRootCASResult(
                        RootUpdateStatus.CONFLICT, before, before, None, "stale_expectation", True, False
                    )
                if before.root_cid == new_root_cid:
                    connection.execute("COMMIT")
                    return StateRootCASResult(
                        RootUpdateStatus.UNCHANGED, before, before, None, "already_current", True, False
                    )

                successor_revision = expected_revision + 1
                transition = {
                    "schema": STATE_ROOT_TRANSITION_SCHEMA,
                    "namespace": namespace,
                    "operation_id": operation_id,
                    "expected_root_cid": expected_root_cid,
                    "expected_revision": expected_revision,
                    "successor_cid": new_root_cid,
                    "successor_revision": successor_revision,
                    "created_at_ms": int(self._clock_ms()),
                }
                data = _canonical_json(transition)
                transition_cid = cid_for_bytes(data)
                self._write_block(transition_cid, data)
                connection.execute(
                    "INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?,?,?)",
                    (transition_cid, "StateRootTransition", STATE_ROOT_TRANSITION_SCHEMA,
                     "dag-json", len(data), transition["created_at_ms"]),
                )
                connection.execute(
                    """INSERT INTO root_transitions
                       (transition_cid,namespace,operation_id,expected_root_cid,expected_revision,
                        successor_cid,successor_revision,created_at_ms) VALUES(?,?,?,?,?,?,?,?)""",
                    (transition_cid, namespace, operation_id, expected_root_cid, expected_revision,
                     new_root_cid, successor_revision, transition["created_at_ms"]),
                )
                connection.execute(
                    """INSERT INTO state_roots(namespace,root_cid,revision,transition_cid) VALUES(?,?,?,?)
                       ON CONFLICT(namespace) DO UPDATE SET root_cid=excluded.root_cid,
                       revision=excluded.revision,transition_cid=excluded.transition_cid""",
                    (namespace, new_root_cid, successor_revision, transition_cid),
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        after = StateRootSnapshot(namespace, new_root_cid, successor_revision, transition_cid)
        return StateRootCASResult(RootUpdateStatus.UPDATED, before, after, transition_cid, "updated", True, False)

    # Names used by the storage-facing root protocol; the longer names above
    # keep the coordination-store API explicit and remain the primary surface.
    current_root = current_state_root
    compare_and_swap_root = compare_and_swap_state_root

    def _index_artifact(
        self, connection: sqlite3.Connection, cid: str, kind: str, artifact: Mapping[str, Any]
    ) -> None:
        if kind == "TaskClaim":
            connection.execute(
                """INSERT OR REPLACE INTO claims
                   (claim_cid,task_cid,proposal_cid,claimant_did,logical_epoch,requested_lease_ms,
                    attempt,created_at_ms,state,resolution_cid)
                   VALUES(?,?,?,?,?,?,?,?,COALESCE((SELECT state FROM claims WHERE claim_cid=?),'pending'),
                          (SELECT resolution_cid FROM claims WHERE claim_cid=?))""",
                (
                    cid, _require_string(artifact, "task_cid"), _require_string(artifact, "proposal_cid"),
                    _require_string(artifact, "claimant_did"), _require_integer(artifact, "logical_epoch", 1),
                    _require_integer(artifact, "requested_lease_ms", 1), _require_integer(artifact, "attempt", 1),
                    _require_integer(artifact, "created_at_ms"), cid, cid,
                ),
            )
        elif kind == "ClaimResolution":
            self._index_resolution(connection, cid, artifact)
        elif kind in ("NeighborhoodRecord", "DaemonHealth"):
            self._index_health(connection, cid, kind, artifact)

    def _index_resolution(self, connection: sqlite3.Connection, cid: str, artifact: Mapping[str, Any]) -> None:
        task_cid = _require_string(artifact, "task_cid")
        outcome = _require_string(artifact, "outcome")
        accepted = artifact.get("accepted_claim_cid")
        created = _require_integer(artifact, "created_at_ms")
        if outcome == "accepted":
            if not isinstance(accepted, str) or not accepted:
                raise ValueError("accepted resolution requires accepted_claim_cid")
            expires = _require_integer(artifact, "lease_expires_at_ms", 1)
            epoch = _require_integer(artifact, "logical_epoch", 1)
            token = _require_integer(artifact, "fencing_token", 1)
            current = connection.execute(
                """SELECT logical_epoch,fencing_token FROM leases
                   WHERE task_cid=? AND active=1
                   ORDER BY logical_epoch DESC,fencing_token DESC LIMIT 1""",
                (task_cid,),
            ).fetchone()
            if current is not None and (epoch, token) <= (current["logical_epoch"], current["fencing_token"]):
                connection.execute(
                    "INSERT OR REPLACE INTO leases VALUES(?,?,?,?,?,?,?,?,?)",
                    (cid, task_cid, accepted, epoch, token, expires, "stale", 0, created),
                )
                return
            connection.execute(
                """UPDATE claims SET state='superseded'
                   WHERE state='accepted' AND claim_cid IN
                     (SELECT claim_cid FROM leases WHERE task_cid=? AND active=1)""",
                (task_cid,),
            )
            connection.execute(
                "UPDATE leases SET active=0, outcome='superseded' WHERE task_cid=? AND active=1",
                (task_cid,),
            )
            connection.execute(
                "INSERT OR REPLACE INTO leases VALUES(?,?,?,?,?,?,?,?,?)",
                (cid, task_cid, accepted, epoch, token, expires, outcome, 1, created),
            )
            connection.execute(
                "UPDATE claims SET state='accepted', resolution_cid=? WHERE claim_cid=?", (cid, accepted)
            )
            considered = artifact.get("considered_claim_cids", [])
            for claim_cid in considered if isinstance(considered, list) else []:
                if claim_cid != accepted:
                    connection.execute(
                        "UPDATE claims SET state='conflict', resolution_cid=? WHERE claim_cid=?", (cid, claim_cid)
                    )
        else:
            connection.execute("UPDATE leases SET active=0, outcome=? WHERE task_cid=? AND active=1", (outcome, task_cid))
            for claim_cid in artifact.get("considered_claim_cids", []):
                connection.execute(
                    "UPDATE claims SET state=?, resolution_cid=? WHERE claim_cid=?", (outcome, cid, claim_cid)
                )

    def _index_health(
        self, connection: sqlite3.Connection, cid: str, kind: str, artifact: Mapping[str, Any]
    ) -> None:
        peer = _require_string(artifact, "peer_did")
        observed = int(artifact.get("observed_at_ms", artifact.get("valid_from_ms", artifact.get("created_at_ms", 0))))
        expires = _require_integer(artifact, "expires_at_ms", 1)
        capacity = _require_integer(artifact, "capacity_millionths")
        status = str(artifact.get("status", "healthy" if capacity > 0 else "unavailable"))
        connection.execute(
            "INSERT OR REPLACE INTO daemon_health VALUES(?,?,?,?,?,?,?)",
            (cid, peer, status, observed, expires, capacity, kind),
        )

    def _index_recovered_state_root_transition(
        self, connection: sqlite3.Connection, transition_cid: str, artifact: Mapping[str, Any],
        verified_cids: set[str],
    ) -> None:
        """Rebuild one root transition only when its entire prior chain verifies."""

        required = {
            "schema", "namespace", "operation_id", "expected_root_cid", "expected_revision",
            "successor_cid", "successor_revision", "created_at_ms",
        }
        if set(artifact) != required:
            raise ArtifactIntegrityError("state-root transition has an invalid field set")
        namespace = artifact["namespace"]
        expected_root_cid = artifact["expected_root_cid"]
        expected_revision = artifact["expected_revision"]
        successor_cid = artifact["successor_cid"]
        operation_id = artifact["operation_id"]
        self._validate_state_root_operation(
            namespace, expected_revision, expected_root_cid, successor_cid, operation_id
        )
        successor_revision = artifact["successor_revision"]
        created_at_ms = artifact["created_at_ms"]
        if (isinstance(successor_revision, bool) or not isinstance(successor_revision, int)
                or successor_revision != expected_revision + 1):
            raise ArtifactIntegrityError("state-root transition has an invalid successor revision")
        if isinstance(created_at_ms, bool) or not isinstance(created_at_ms, int) or created_at_ms < 0:
            raise ArtifactIntegrityError("state-root transition has an invalid creation time")
        if successor_cid not in verified_cids:
            raise ArtifactIntegrityError("state-root transition successor is absent or corrupt")
        row = connection.execute(
            "SELECT root_cid,revision,transition_cid FROM state_roots WHERE namespace=?", (namespace,)
        ).fetchone()
        before = self._state_root_snapshot_from_row(namespace, row)
        if before.revision != expected_revision or before.root_cid != expected_root_cid:
            raise ArtifactIntegrityError("state-root transition does not continue the verified root chain")
        if before.root_cid == successor_cid:
            raise ArtifactIntegrityError("state-root transition does not change its root")
        connection.execute(
            """INSERT INTO root_transitions
               (transition_cid,namespace,operation_id,expected_root_cid,expected_revision,
                successor_cid,successor_revision,created_at_ms) VALUES(?,?,?,?,?,?,?,?)""",
            (transition_cid, namespace, operation_id, expected_root_cid, expected_revision,
             successor_cid, successor_revision, created_at_ms),
        )
        connection.execute(
            "INSERT INTO state_roots(namespace,root_cid,revision,transition_cid) VALUES(?,?,?,?)",
            (namespace, successor_cid, successor_revision, transition_cid),
        )

    def record_daemon_health(self, record: Mapping[str, Any]) -> Dict[str, Any]:
        """Persist a signed, expiring daemon capacity/health observation."""

        value = dict(record)
        value.setdefault("schema", DAEMON_HEALTH_SCHEMA)
        required = (
            "peer_did", "status", "observed_at_ms", "expires_at_ms", "capacity_millionths",
            "resource_classes", "health_evidence_cid", "signer_did", "signature_alg", "signature",
        )
        missing = [name for name in required if name not in value]
        if missing:
            raise ValueError(f"daemon health record missing: {', '.join(missing)}")
        observed = _require_integer(value, "observed_at_ms")
        if _require_integer(value, "expires_at_ms", 1) <= observed:
            raise ValueError("expires_at_ms must be later than observed_at_ms")
        capacity = _require_integer(value, "capacity_millionths")
        if capacity > 1_000_000:
            raise ValueError("capacity_millionths must not exceed 1000000")
        return self.put(value)

    @staticmethod
    def _rows(cursor: sqlite3.Cursor) -> list[Dict[str, Any]]:
        return [dict(row) for row in cursor.fetchall()]

    def claims(self, task_cid: str, *, include_terminal: bool = True) -> list[Dict[str, Any]]:
        sql = "SELECT * FROM claims WHERE task_cid=?"
        parameters: list[Any] = [task_cid]
        if not include_terminal:
            sql += " AND state IN ('pending','accepted')"
        sql += " ORDER BY logical_epoch DESC, created_at_ms DESC, claim_cid"
        with self._lock:
            return self._rows(self._connection.execute(sql, parameters))

    def active_lease(self, task_cid: str, *, at_ms: Optional[int] = None) -> Optional[Dict[str, Any]]:
        now = int(self._clock_ms() if at_ms is None else at_ms)
        with self._lock, self._connection:
            self._connection.execute(
                """UPDATE claims SET state='expired'
                   WHERE state='accepted' AND claim_cid IN
                     (SELECT claim_cid FROM leases WHERE active=1 AND expires_at_ms<=?)""",
                (now,),
            )
            self._connection.execute(
                "UPDATE leases SET active=0, outcome='expired' WHERE active=1 AND expires_at_ms<=?", (now,)
            )
            row = self._connection.execute(
                """SELECT leases.*, claims.claimant_did FROM leases
                   LEFT JOIN claims ON claims.claim_cid=leases.claim_cid
                   WHERE leases.task_cid=? AND leases.active=1 AND leases.expires_at_ms>?
                   ORDER BY leases.logical_epoch DESC, leases.fencing_token DESC LIMIT 1""",
                (task_cid, now),
            ).fetchone()
            return dict(row) if row else None

    def daemon_health(self, peer_did: Optional[str] = None, *, at_ms: Optional[int] = None) -> list[Dict[str, Any]]:
        now = int(self._clock_ms() if at_ms is None else at_ms)
        sql = "SELECT * FROM daemon_health WHERE expires_at_ms>?"
        params: list[Any] = [now]
        if peer_did is not None:
            sql += " AND peer_did=?"
            params.append(peer_did)
        sql += " ORDER BY peer_did, expires_at_ms DESC"
        with self._lock:
            return self._rows(self._connection.execute(sql, params))

    def compact_indexes(self, *, at_ms: Optional[int] = None) -> Dict[str, Any]:
        """Archive and prune stale index rows while preserving every CID block."""

        now = int(self._clock_ms() if at_ms is None else at_ms)
        claim_before = now - self.retention.terminal_claim_ms
        lease_before = now - self.retention.expired_lease_ms
        health_before = now - self.retention.expired_health_ms
        with self._lock:
            claims = self._rows(self._connection.execute(
                "SELECT * FROM claims WHERE state NOT IN ('pending','accepted') AND created_at_ms<=?", (claim_before,)
            ))
            leases = self._rows(self._connection.execute(
                "SELECT * FROM leases WHERE active=0 AND expires_at_ms<=?", (lease_before,)
            ))
            health = self._rows(self._connection.execute(
                "SELECT * FROM daemon_health WHERE expires_at_ms<=?", (health_before,)
            ))
        if not (claims or leases or health):
            return {"compacted": False, "reason": "no_eligible_index_rows", "row_count": 0}
        artifact = {
            "schema": COORDINATION_ARCHIVE_SCHEMA,
            "created_at_ms": now,
            "policy": {
                "terminal_claim_ms": self.retention.terminal_claim_ms,
                "expired_lease_ms": self.retention.expired_lease_ms,
                "expired_health_ms": self.retention.expired_health_ms,
                "artifact_blocks": "retain-forever",
            },
            "claims": claims,
            "leases": leases,
            "daemon_health": health,
            "artifact_cids": sorted({
                *(row["claim_cid"] for row in claims),
                *(row["resolution_cid"] for row in leases),
                *(row["health_cid"] for row in health),
            }),
        }
        stored = self.put(artifact)
        with self._lock, self._connection:
            self._connection.executemany("DELETE FROM claims WHERE claim_cid=?", [(row["claim_cid"],) for row in claims])
            self._connection.executemany("DELETE FROM leases WHERE resolution_cid=?", [(row["resolution_cid"],) for row in leases])
            self._connection.executemany("DELETE FROM daemon_health WHERE health_cid=?", [(row["health_cid"],) for row in health])
            self._connection.execute(
                "INSERT OR REPLACE INTO index_archives VALUES(?,?,?)",
                (stored["cid"], now, len(claims) + len(leases) + len(health)),
            )
        return {
            "compacted": True,
            "archive_cid": stored["cid"],
            "row_count": len(claims) + len(leases) + len(health),
            "artifact_cids": artifact["artifact_cids"],
        }

    def _iter_local_blocks(self) -> Iterator[Tuple[str, bytes]]:
        for path in sorted(self.blocks_dir.glob("*/*.json")):
            yield path.stem, path.read_bytes()

    def recover(self, *, rebuild: bool = True) -> Dict[str, Any]:
        """Verify immutable blocks and optionally recreate all derived indexes."""

        verified: list[Tuple[str, Dict[str, Any], bytes]] = []
        errors: list[Dict[str, str]] = []
        for cid, data in self._iter_local_blocks():
            try:
                if cid_for_bytes(data, _codec_from_cid(cid)) != cid:
                    raise ArtifactIntegrityError("CID mismatch")
                value = json.loads(data.decode("utf-8"))
                if not isinstance(value, dict) or _canonical_json(value) != data:
                    raise ArtifactIntegrityError("non-canonical JSON")
                _artifact_kind(value)
                verified.append((cid, value, data))
            except Exception as exc:
                errors.append({"cid": cid, "error": str(exc)})
        if errors:
            raise ArtifactIntegrityError(f"coordination recovery found corrupt blocks: {errors}")
        if rebuild:
            with self._lock, self._connection:
                self._connection.execute("DELETE FROM claims")
                self._connection.execute("DELETE FROM leases")
                self._connection.execute("DELETE FROM daemon_health")
                self._connection.execute("DELETE FROM index_archives")
                self._connection.execute("DELETE FROM state_roots")
                self._connection.execute("DELETE FROM root_transitions")
                self._connection.execute("DELETE FROM artifacts")
                # Creation order is stable so claims precede resolutions in the
                # normal case. A second resolution pass handles arbitrary scans.
                ordered = sorted(verified, key=lambda row: (int(row[1].get("created_at_ms", 0)), row[0]))
                for cid, value, data in ordered:
                    kind = _artifact_kind(value)
                    self._connection.execute(
                        "INSERT INTO artifacts VALUES(?,?,?,?,?,?)",
                        (cid, kind, str(value["schema"]), _codec_from_cid(cid), len(data), int(value.get("created_at_ms", 0))),
                    )
                    if kind != "ClaimResolution":
                        self._index_artifact(self._connection, cid, kind, value)
                for cid, value, _ in ordered:
                    if _artifact_kind(value) == "ClaimResolution":
                        self._index_artifact(self._connection, cid, "ClaimResolution", value)
                for cid, value, _ in ordered:
                    if _artifact_kind(value) == "CoordinationArchive":
                        row_count = sum(len(value.get(name, [])) for name in ("claims", "leases", "daemon_health"))
                        self._connection.executemany(
                            "DELETE FROM claims WHERE claim_cid=?",
                            [(row["claim_cid"],) for row in value.get("claims", [])],
                        )
                        self._connection.executemany(
                            "DELETE FROM leases WHERE resolution_cid=?",
                            [(row["resolution_cid"],) for row in value.get("leases", [])],
                        )
                        self._connection.executemany(
                            "DELETE FROM daemon_health WHERE health_cid=?",
                            [(row["health_cid"],) for row in value.get("daemon_health", [])],
                        )
                        self._connection.execute(
                            "INSERT OR REPLACE INTO index_archives VALUES(?,?,?)",
                            (cid, int(value.get("created_at_ms", 0)), row_count),
                        )
                verified_cids = {cid for cid, _, _ in verified}
                transitions = sorted(
                    ((cid, value) for cid, value, _ in verified
                     if _artifact_kind(value) == "StateRootTransition"),
                    key=lambda item: (item[1]["namespace"], item[1].get("successor_revision", -1), item[0]),
                )
                for cid, value in transitions:
                    self._index_recovered_state_root_transition(self._connection, cid, value, verified_cids)
        return {"verified_blocks": len(verified), "rebuilt": rebuild, "errors": []}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            counts = {
                table: int(self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in ("artifacts", "claims", "leases", "daemon_health", "index_archives",
                              "state_roots", "root_transitions")
            }
        return {
            "storage_dir": str(self.root),
            "backend": type(self.backend).__name__ if self.backend is not None else None,
            "counts": counts,
            "artifact_retention": "permanent",
            "index_retention": self.retention.__dict__.copy(),
        }


__all__ = [
    "ArtifactIntegrityError",
    "ArtifactNotFound",
    "BlockBackend",
    "COORDINATION_ARCHIVE_SCHEMA",
    "DAEMON_HEALTH_SCHEMA",
    "DurableCoordinationStore",
    "IPFSHeliaBlockBackend",
    "RetentionPolicy",
    "STATE_ROOT_TRANSITION_SCHEMA",
    "cid_for_artifact",
    "cid_for_bytes",
]
