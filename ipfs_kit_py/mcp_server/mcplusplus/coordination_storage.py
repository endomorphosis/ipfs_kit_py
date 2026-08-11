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
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional, Protocol, Tuple


PROFILE_G_PREFIX = "mcp++/profile-g/"
COORDINATION_ARCHIVE_SCHEMA = "mcp++/coordination-index-archive@1"
DAEMON_HEALTH_SCHEMA = "mcp++/coordination/daemon-health@1"
STATE_ROOT_TRANSITION_SCHEMA = "mcp++/coordination/state-root-transition@1"
# These names are deliberately part of the small test seam for this storage
# primitive.  An injector raises at one boundary to model a process stopping;
# reopening the store must then derive either the old root or the sole durable
# transition from immutable blocks.
ROOT_CAS_INTERRUPTION_POINTS = (
    "before_transaction",
    "after_expectation_verification",
    "after_transition_block_fsync",
    "after_transition_indexing",
    "before_sqlite_commit",
    "after_sqlite_commit",
)
MAX_RECOVERY_ERRORS = 32
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


def _read_canonical_varint(data: bytes, offset: int) -> tuple[int, int]:
    """Read one minimally encoded unsigned varint from CID bytes."""

    start = offset
    value = shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            if _varint(value) != data[start:offset]:
                raise ValueError("CID contains a non-minimal varint")
            return value, offset
        shift += 7
        if shift > 63:
            break
    raise ValueError("CID contains an invalid varint")


def validate_transport_cid(cid: object) -> str:
    """Require the one canonical CIDv1 spelling accepted by coordination."""

    try:
        if not isinstance(cid, str) or len(cid) < 10 or cid[0] != "b":
            raise ValueError
        if any(character not in "abcdefghijklmnopqrstuvwxyz234567" for character in cid[1:]):
            raise ValueError
        padded = cid[1:].upper() + "=" * ((8 - len(cid[1:]) % 8) % 8)
        data = base64.b32decode(padded)
        if base64.b32encode(data).decode("ascii").lower().rstrip("=") != cid[1:]:
            raise ValueError
        version, offset = _read_canonical_varint(data, 0)
        codec_code, offset = _read_canonical_varint(data, offset)
        multihash_code, offset = _read_canonical_varint(data, offset)
        digest_length, offset = _read_canonical_varint(data, offset)
        if version != 1 or multihash_code != 0x12 or digest_length != 32 or len(data) != offset + digest_length:
            raise ValueError
        return {0x55: "raw", 0x0129: "dag-json"}[codec_code]
    except (IndexError, ValueError, KeyError, TypeError, base64.binascii.Error) as exc:
        raise ValueError("unsupported or malformed CID") from exc


def _codec_from_cid(cid: str) -> str:
    return validate_transport_cid(cid)


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
        if returned:
            try:
                validate_transport_cid(returned)
            except ValueError as exc:
                raise ArtifactIntegrityError(f"backend returned a non-canonical CID: {returned}") from exc
            if returned != cid:
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

    DB_VERSION = 2

    def __init__(
        self,
        storage_dir: Optional[os.PathLike[str] | str] = None,
        *,
        backend: Optional[BlockBackend | Any] = None,
        retention: Optional[RetentionPolicy] = None,
        clock_ms: Optional[Any] = None,
        crash_injector: Optional[Any] = None,
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
        self._crash_injector = crash_injector
        self._lock = threading.RLock()
        # These are deliberately structural counters, rather than timings: a
        # reopen may verify immutable evidence, but it must not rewrite healthy
        # root indexes merely because historical transitions exist.
        self._root_recovery_metrics = {
            "root_index_verifications": 0,
            "root_index_rebuild_mutations": 0,
        }
        self._last_root_indexes_match = True
        self._connection = self._open_database()
        # A missing/recreated index next to existing blocks is recovered
        # automatically. Operators can also request an explicit full rebuild.
        indexed = int(self._connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0])
        has_blocks = next(self.blocks_dir.glob("*/*.json"), None) is not None
        # Verify every immutable block on reopen.  Rebuild only when the
        # generic index is absent or the authoritative root-transition chain
        # disagrees with the acceleration rows.  This detects orphan evidence
        # left by an interrupted CAS without turning every healthy reopen into
        # a DELETE/INSERT root-index rewrite.
        if has_blocks:
            self.recover(rebuild=False)
            if indexed == 0 or not self._last_root_indexes_match:
                self.recover(rebuild=True)

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
              transition_cid TEXT REFERENCES artifacts(cid),
              CHECK (revision >= 0),
              CHECK ((revision = 0 AND root_cid IS NULL AND transition_cid IS NULL)
                  OR (revision > 0 AND root_cid IS NOT NULL AND transition_cid IS NOT NULL))
            );
            CREATE TABLE IF NOT EXISTS state_root_transitions (
              transition_cid TEXT PRIMARY KEY REFERENCES artifacts(cid), namespace TEXT NOT NULL,
              operation_id TEXT NOT NULL, expected_root_cid TEXT, expected_revision INTEGER NOT NULL,
              new_root_cid TEXT NOT NULL, new_revision INTEGER NOT NULL, created_at_ms INTEGER NOT NULL,
              UNIQUE(namespace, operation_id),
              CHECK (expected_revision >= 0), CHECK (new_revision = expected_revision + 1)
            );
            CREATE INDEX IF NOT EXISTS state_root_transitions_namespace_revision
              ON state_root_transitions(namespace, new_revision);
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
        validate_transport_cid(cid)
        directory = self.blocks_dir / cid[1:3]
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{cid}.json"

    def _has_local_state_root_transition(self) -> bool:
        """Return whether immutable storage contains a root transition.

        This is intentionally only a startup rebuild trigger.  ``recover``
        remains the verifier and will reject malformed candidate blocks rather
        than trusting this inexpensive schema probe.
        """

        for _, data in self._iter_local_blocks():
            try:
                if json.loads(data.decode("utf-8")).get("schema") == STATE_ROOT_TRANSITION_SCHEMA:
                    return True
            except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
                # The full verifier below handles corrupt blocks when a
                # rebuild is otherwise needed; this probe must not mask them.
                continue
        return False

    def root_recovery_metrics(self) -> Dict[str, int]:
        """Return session-local structural root recovery counters.

        The counters make reopen-cost assertions deterministic.  They do not
        express elapsed time and are not persisted as coordination state.
        """

        with self._lock:
            return dict(self._root_recovery_metrics)

    def _interrupt_root_cas(self, boundary: str) -> None:
        """Invoke the optional test-only crash seam at a named durable boundary.

        This deliberately has no recovery behavior of its own: a real process
        death cannot run cleanup either.  The surrounding transaction and the
        immutable-block-first ordering are what make reopening safe.
        """

        if self._crash_injector is not None:
            self._crash_injector(boundary)

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
        if expected_cid is not None:
            validate_transport_cid(expected_cid)
            if expected_cid != cid:
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
    def _root_namespace(namespace: str) -> str:
        """Validate the deliberately small namespace grammar used by root rows."""

        if not isinstance(namespace, str) or not namespace or len(namespace) > 255:
            raise ValueError("namespace must be a non-empty normalized string up to 255 characters")
        if namespace != namespace.strip() or "//" in namespace:
            raise ValueError("namespace must be normalized")
        for segment in namespace.split("/"):
            if not segment or len(segment) > 63:
                raise ValueError("namespace contains an invalid segment")
            if segment[0] not in "abcdefghijklmnopqrstuvwxyz0123456789" or segment[-1] not in "abcdefghijklmnopqrstuvwxyz0123456789":
                raise ValueError("namespace contains an invalid segment")
            if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for character in segment):
                raise ValueError("namespace contains an invalid segment")
        return namespace

    @staticmethod
    def _operation_id(operation_id: str) -> str:
        if not isinstance(operation_id, str) or not (1 <= len(operation_id) <= 128):
            raise ValueError("operation_id must be a normalized identifier")
        if operation_id[0] not in "abcdefghijklmnopqrstuvwxyz0123456789" or operation_id[-1] not in "abcdefghijklmnopqrstuvwxyz0123456789":
            raise ValueError("operation_id must be a normalized identifier")
        if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789._:-" for character in operation_id):
            raise ValueError("operation_id must be a normalized identifier")
        return operation_id

    @staticmethod
    def _root_revision(value: int, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
        return value

    @classmethod
    def _root_expectation(
        cls, expected_revision: int, expected_root_cid: Optional[str]
    ) -> tuple[int, Optional[str]]:
        """Validate the only coherent predecessor representations for CAS."""

        revision = cls._root_revision(expected_revision, "expected_revision")
        if expected_root_cid is not None:
            _codec_from_cid(expected_root_cid)
        if revision == 0 and expected_root_cid is not None:
            raise ValueError("revision-zero expectations must not have a root CID")
        if revision > 0 and expected_root_cid is None:
            raise ValueError("non-zero expectations require a root CID")
        return revision, expected_root_cid

    @staticmethod
    def _root_snapshot_from_row(namespace: str, row: Optional[sqlite3.Row]) -> Dict[str, Any]:
        if row is None:
            return {"namespace": namespace, "root_cid": None, "revision": 0, "transition_cid": None}
        root_cid = row["root_cid"]
        transition_cid = row["transition_cid"]
        if root_cid is not None:
            validate_transport_cid(root_cid)
        if transition_cid is not None:
            validate_transport_cid(transition_cid)
        return {
            "namespace": namespace,
            "root_cid": root_cid,
            "revision": int(row["revision"]),
            "transition_cid": transition_cid,
        }

    def _verified_indexed_state_root(
        self, namespace: str, connection: sqlite3.Connection
    ) -> Dict[str, Any]:
        """Return a root only after proving its complete indexed evidence chain.

        SQLite is an acceleration index, not root authority.  In particular,
        do not let a locally tampered root row turn an immutable transition
        into a different live state.  Every indexed transition is checked
        against its CID-addressed dag-json block, its artifact metadata, and
        the predecessor reconstructed from the prior transition.
        """

        root_row = connection.execute(
            "SELECT root_cid,revision,transition_cid FROM state_roots WHERE namespace=?", (namespace,)
        ).fetchone()
        transition_rows = connection.execute(
            "SELECT * FROM state_root_transitions WHERE namespace=? "
            "ORDER BY new_revision,transition_cid",
            (namespace,),
        ).fetchall()

        try:
            snapshot = self._root_snapshot_from_row(namespace, root_row)
            revision = self._root_revision(snapshot["revision"], "revision")
            if (revision == 0) != (snapshot["root_cid"] is None):
                raise ValueError("root row has inconsistent initial fields")
            if (revision == 0) != (snapshot["transition_cid"] is None):
                raise ValueError("root row has inconsistent transition fields")

            predecessor = {"root_cid": None, "revision": 0, "transition_cid": None}
            for row in transition_rows:
                transition_cid = row["transition_cid"]
                # State-root transitions are structured records.  A raw CID
                # can name valid coordination bytes, but never this wire type.
                if _codec_from_cid(transition_cid) != "dag-json":
                    raise ValueError("state root transition has a non-dag-json CID")
                artifact_row = connection.execute(
                    "SELECT kind,schema_uri,codec,byte_length FROM artifacts WHERE cid=?", (transition_cid,)
                ).fetchone()
                if artifact_row is None:
                    raise ValueError("state root transition is absent from artifacts")
                if (
                    artifact_row["kind"] != _artifact_kind(self.get(transition_cid))
                    or
                    artifact_row["schema_uri"] != STATE_ROOT_TRANSITION_SCHEMA
                    or artifact_row["codec"] != "dag-json"
                ):
                    raise ValueError("state root transition has inconsistent artifact metadata")
                data = self.get_bytes(transition_cid)
                if artifact_row["byte_length"] != len(data):
                    raise ValueError("state root transition has inconsistent artifact length")
                fields = self._state_root_transition_fields(self.get(transition_cid))
                row_fields = (
                    "namespace", "operation_id", "expected_root_cid", "expected_revision",
                    "new_root_cid", "new_revision", "created_at_ms",
                )
                if any(row[name] != fields[name] for name in row_fields):
                    raise ValueError("state root transition index does not match its block")
                if (fields["expected_root_cid"], fields["expected_revision"]) != (
                    predecessor["root_cid"], predecessor["revision"]
                ):
                    raise ValueError("state root transition breaks its predecessor chain")
                # Reading every successor makes a missing or corrupt earlier
                # root fail even when a later transition is otherwise intact.
                self.get_bytes(fields["new_root_cid"])
                predecessor = {
                    "root_cid": fields["new_root_cid"], "revision": fields["new_revision"],
                    "transition_cid": transition_cid,
                }

            if (snapshot["root_cid"], snapshot["revision"], snapshot["transition_cid"]) != (
                predecessor["root_cid"], predecessor["revision"], predecessor["transition_cid"]
            ):
                raise ValueError("root row does not match its indexed transition chain")
            return snapshot
        except (ArtifactIntegrityError, ArtifactNotFound) as exc:
            raise ArtifactIntegrityError(f"state root {namespace!r} has invalid immutable evidence: {exc}") from exc
        except (KeyError, TypeError, ValueError, sqlite3.DatabaseError) as exc:
            raise ArtifactIntegrityError(f"state root {namespace!r} has invalid indexed evidence: {exc}") from exc

    def current_state_root(self, namespace: str) -> Dict[str, Any]:
        """Return a namespace's current root; absent namespaces begin at revision zero."""

        namespace = self._root_namespace(namespace)
        with self._lock:
            return self._verified_indexed_state_root(namespace, self._connection)

    def state_roots(self) -> list[Dict[str, Any]]:
        """List visible non-initial roots in deterministic namespace order."""

        with self._lock:
            rows = self._connection.execute(
                "SELECT namespace,root_cid,revision,transition_cid FROM state_roots ORDER BY namespace"
            ).fetchall()
            return [self._verified_indexed_state_root(row["namespace"], self._connection) for row in rows]

    def root_transitions(self, namespace: Optional[str] = None) -> list[Dict[str, Any]]:
        """List indexed root transitions, optionally for one namespace."""

        if namespace is not None:
            namespace = self._root_namespace(namespace)
        sql = "SELECT * FROM state_root_transitions"
        params: tuple[Any, ...] = ()
        if namespace is not None:
            sql += " WHERE namespace=?"
            params = (namespace,)
        sql += " ORDER BY namespace,new_revision,transition_cid"
        with self._lock:
            return self._rows(self._connection.execute(sql, params))

    def compare_and_swap_state_root(
        self,
        namespace: str,
        *,
        expected_revision: int,
        expected_root_cid: Optional[str],
        new_root_cid: str,
        operation_id: str,
    ) -> Dict[str, Any]:
        """Atomically publish a verified successor root or report a stale CAS.

        The transition block is immutable evidence.  The root index is changed
        only in the same full-synchronous transaction that indexes that block.
        ``BEGIN IMMEDIATE`` is intentional: SQLite serializes writers from
        other processes before either can observe the expectation as current.
        """

        namespace = self._root_namespace(namespace)
        operation_id = self._operation_id(operation_id)
        expected_revision, expected_root_cid = self._root_expectation(
            expected_revision, expected_root_cid
        )
        _codec_from_cid(new_root_cid)
        if expected_root_cid == new_root_cid:
            raise ValueError("new_root_cid must differ from expected_root_cid")

        # Input validation above is deliberately I/O-free.  A transaction is
        # then used to resolve an existing operation before reading a proposed
        # successor: operation IDs are durable idempotency keys, so a changed
        # reuse is a typed conflict even if its new CID is unavailable.
        self._interrupt_root_cas("before_transaction")

        with self._lock:
            connection = self._connection
            connection.execute("BEGIN IMMEDIATE")
            try:
                before = self._verified_indexed_state_root(namespace, connection)
                existing = connection.execute(
                    "SELECT * FROM state_root_transitions WHERE namespace=? AND operation_id=?",
                    (namespace, operation_id),
                ).fetchone()
                if existing is not None:
                    same_request = (
                        existing["expected_revision"] == expected_revision
                        and existing["expected_root_cid"] == expected_root_cid
                        and existing["new_root_cid"] == new_root_cid
                    )
                    if same_request:
                        connection.rollback()
                        return {
                            "status": "unchanged", "before": before, "after": before,
                            "transition_cid": None, "reason_code": "idempotent_replay",
                            "local_durable": True, "replicated": False,
                        }
                    connection.rollback()
                    return {
                        "status": "conflict", "before": before, "after": before,
                        "transition_cid": None, "reason_code": "operation_id_reused",
                        "local_durable": True, "replicated": False,
                    }
                # Verify the successor only after replay/reuse resolution,
                # but before the expectation can publish it.
                self.get_bytes(new_root_cid)
                self._interrupt_root_cas("after_expectation_verification")
                if before["revision"] != expected_revision or before["root_cid"] != expected_root_cid:
                    connection.rollback()
                    return {
                        "status": "conflict", "before": before, "after": before,
                        "transition_cid": None, "reason_code": "stale_expectation",
                        "local_durable": True, "replicated": False,
                    }

                transition = {
                    "schema": STATE_ROOT_TRANSITION_SCHEMA,
                    "namespace": namespace,
                    "operation_id": operation_id,
                    "expected_root_cid": expected_root_cid,
                    "expected_revision": expected_revision,
                    "new_root_cid": new_root_cid,
                    "new_revision": expected_revision + 1,
                    "created_at_ms": int(self._clock_ms()),
                }
                data = _canonical_json(transition)
                transition_cid = cid_for_bytes(data)
                self._write_block(transition_cid, data)
                self._interrupt_root_cas("after_transition_block_fsync")
                kind = _artifact_kind(transition)
                connection.execute(
                    "INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?,?,?)",
                    (transition_cid, kind, STATE_ROOT_TRANSITION_SCHEMA, "dag-json", len(data), transition["created_at_ms"]),
                )
                connection.execute(
                    """INSERT INTO state_root_transitions
                       (transition_cid,namespace,operation_id,expected_root_cid,expected_revision,
                        new_root_cid,new_revision,created_at_ms) VALUES(?,?,?,?,?,?,?,?)""",
                    (transition_cid, namespace, operation_id, expected_root_cid, expected_revision,
                     new_root_cid, expected_revision + 1, transition["created_at_ms"]),
                )
                connection.execute(
                    """INSERT INTO state_roots(namespace,root_cid,revision,transition_cid) VALUES(?,?,?,?)
                       ON CONFLICT(namespace) DO UPDATE SET root_cid=excluded.root_cid,
                         revision=excluded.revision,transition_cid=excluded.transition_cid""",
                    (namespace, new_root_cid, expected_revision + 1, transition_cid),
                )
                self._interrupt_root_cas("after_transition_indexing")
                after = {"namespace": namespace, "root_cid": new_root_cid,
                         "revision": expected_revision + 1, "transition_cid": transition_cid}
                self._interrupt_root_cas("before_sqlite_commit")
                connection.commit()
                self._interrupt_root_cas("after_sqlite_commit")
            except Exception:
                connection.rollback()
                raise
        return {
            "status": "updated", "before": before, "after": after,
            "transition_cid": transition_cid, "reason_code": "updated",
            "local_durable": True, "replicated": False,
        }

    # These short aliases make the storage primitive convenient for the later
    # adapter while retaining explicit names for the coordination-store API.
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

    def _state_root_transition_fields(self, artifact: Mapping[str, Any]) -> Dict[str, Any]:
        """Validate the closed immutable transition wire record for rebuilding."""

        required = {
            "schema", "namespace", "operation_id", "expected_root_cid", "expected_revision",
            "new_root_cid", "new_revision", "created_at_ms",
        }
        if set(artifact) != required or artifact.get("schema") != STATE_ROOT_TRANSITION_SCHEMA:
            raise ValueError("state root transition has an invalid schema or fields")
        namespace = self._root_namespace(artifact["namespace"])
        operation_id = self._operation_id(artifact["operation_id"])
        expected_revision = self._root_revision(artifact["expected_revision"], "expected_revision")
        new_revision = self._root_revision(artifact["new_revision"], "new_revision")
        created_at_ms = self._root_revision(artifact["created_at_ms"], "created_at_ms")
        expected_root_cid = artifact["expected_root_cid"]
        if expected_root_cid is not None:
            _codec_from_cid(expected_root_cid)
        new_root_cid = artifact["new_root_cid"]
        _codec_from_cid(new_root_cid)
        if new_revision != expected_revision + 1 or expected_root_cid == new_root_cid:
            raise ValueError("state root transition has an invalid revision or successor")
        return {
            "namespace": namespace, "operation_id": operation_id, "expected_root_cid": expected_root_cid,
            "expected_revision": expected_revision, "new_root_cid": new_root_cid,
            "new_revision": new_revision, "created_at_ms": created_at_ms,
        }

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

    def _reconstructed_root_chain(
        self, verified: list[Tuple[str, Dict[str, Any], bytes]]
    ) -> tuple[list[tuple[str, Dict[str, Any]]], Dict[str, Dict[str, Any]]]:
        """Derive the only valid root chain from verified immutable blocks."""

        root_transitions: list[tuple[str, Dict[str, Any]]] = []
        verified_cids = {cid for cid, _, _ in verified}
        for cid, value, _ in verified:
            if value.get("schema") == STATE_ROOT_TRANSITION_SCHEMA:
                fields = self._state_root_transition_fields(value)
                if fields["new_root_cid"] not in verified_cids:
                    raise ArtifactIntegrityError(
                        f"state root transition {cid} has a missing successor block"
                    )
                root_transitions.append((cid, fields))

        snapshots: Dict[str, Dict[str, Any]] = {}
        operations: set[tuple[str, str]] = set()
        for cid, fields in sorted(root_transitions, key=lambda item: (
            item[1]["namespace"], item[1]["new_revision"], item[0]
        )):
            operation = (fields["namespace"], fields["operation_id"])
            if operation in operations:
                raise ArtifactIntegrityError(f"duplicate state root operation {operation!r}")
            operations.add(operation)
            before = snapshots.get(fields["namespace"], {
                "root_cid": None, "revision": 0, "transition_cid": None,
            })
            if (before["root_cid"], before["revision"]) != (
                fields["expected_root_cid"], fields["expected_revision"]
            ):
                raise ArtifactIntegrityError(f"state root transition {cid} breaks its namespace chain")
            snapshots[fields["namespace"]] = {
                "root_cid": fields["new_root_cid"], "revision": fields["new_revision"],
                "transition_cid": cid,
            }
        return root_transitions, snapshots

    def _root_indexes_match(
        self,
        connection: sqlite3.Connection,
        root_transitions: list[tuple[str, Dict[str, Any]]],
        snapshots: Mapping[str, Mapping[str, Any]],
    ) -> bool:
        """Check root acceleration rows against immutable reconstruction.

        This is read-only by design.  In particular it catches a transition
        block written before a crash but absent from SQLite, while allowing a
        healthy reopen to avoid any root-index mutation.
        """

        actual_transitions = {
            row["transition_cid"]: dict(row)
            for row in connection.execute("SELECT * FROM state_root_transitions")
        }
        if set(actual_transitions) != {cid for cid, _ in root_transitions}:
            return False
        for cid, fields in root_transitions:
            row = actual_transitions[cid]
            if any(row[name] != fields[name] for name in fields):
                return False
            artifact = connection.execute(
                "SELECT kind,schema_uri,codec FROM artifacts WHERE cid=?", (cid,)
            ).fetchone()
            if artifact is None or (
                artifact["kind"] != STATE_ROOT_TRANSITION_SCHEMA
                or artifact["schema_uri"] != STATE_ROOT_TRANSITION_SCHEMA
                or artifact["codec"] != "dag-json"
            ):
                return False
        actual_roots = {
            row["namespace"]: dict(row)
            for row in connection.execute(
                "SELECT namespace,root_cid,revision,transition_cid FROM state_roots"
            )
        }
        if set(actual_roots) != set(snapshots):
            return False
        return all(
            all(actual_roots[namespace][field] == value for field, value in snapshot.items())
            for namespace, snapshot in snapshots.items()
        )

    def recover(self, *, rebuild: bool = True) -> Dict[str, Any]:
        """Verify immutable blocks and optionally recreate all derived indexes.

        The immutable scan and any derived-index replacement are one writer
        epoch.  A CAS obtains this same ``BEGIN IMMEDIATE`` fence *before* it
        writes its transition block, so a recovery snapshot cannot omit a
        transition which commits before that recovery's rebuilt indexes do.
        """

        with self._lock:
            connection = self._connection
            connection.execute("BEGIN IMMEDIATE")
            try:
                verified: list[Tuple[str, Dict[str, Any], bytes]] = []
                errors: list[Dict[str, str]] = []
                corrupt_count = 0
                # This must remain inside the writer epoch.  Moving only the
                # DELETE/INSERT work under the transaction leaves a stale
                # block snapshot able to roll a later committed root back.
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
                        corrupt_count += 1
                        if len(errors) < MAX_RECOVERY_ERRORS:
                            errors.append({"cid": cid, "error": str(exc)})
                if errors:
                    suffix = "" if corrupt_count == len(errors) else f" (showing first {len(errors)} of {corrupt_count})"
                    raise ArtifactIntegrityError(f"coordination recovery found corrupt blocks{suffix}: {errors}")
                root_transitions, snapshots = self._reconstructed_root_chain(verified)
                root_indexes_match = self._root_indexes_match(connection, root_transitions, snapshots)
                self._last_root_indexes_match = root_indexes_match
                self._root_recovery_metrics["root_index_verifications"] += 1
                if not rebuild:
                    connection.commit()
                    return {
                        "verified_blocks": len(verified), "rebuilt": False, "errors": [],
                    }

                deleted_root_rows = int(connection.execute("SELECT COUNT(*) FROM state_roots").fetchone()[0])
                deleted_transition_rows = int(
                    connection.execute("SELECT COUNT(*) FROM state_root_transitions").fetchone()[0]
                )
                self._connection.execute("DELETE FROM claims")
                self._connection.execute("DELETE FROM leases")
                self._connection.execute("DELETE FROM daemon_health")
                self._connection.execute("DELETE FROM index_archives")
                self._connection.execute("DELETE FROM state_roots")
                self._connection.execute("DELETE FROM state_root_transitions")
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
                self._root_recovery_metrics["root_index_rebuild_mutations"] += (
                    deleted_root_rows + deleted_transition_rows + len(root_transitions) + len(snapshots)
                )
                for cid, fields in root_transitions:
                    self._connection.execute(
                        """INSERT INTO state_root_transitions
                           (transition_cid,namespace,operation_id,expected_root_cid,expected_revision,
                            new_root_cid,new_revision,created_at_ms) VALUES(?,?,?,?,?,?,?,?)""",
                        (cid, fields["namespace"], fields["operation_id"], fields["expected_root_cid"],
                         fields["expected_revision"], fields["new_root_cid"], fields["new_revision"],
                         fields["created_at_ms"]),
                    )
                for namespace, snapshot in snapshots.items():
                    self._connection.execute(
                        "INSERT INTO state_roots(namespace,root_cid,revision,transition_cid) VALUES(?,?,?,?)",
                        (namespace, snapshot["root_cid"], snapshot["revision"], snapshot["transition_cid"]),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return {"verified_blocks": len(verified), "rebuilt": True, "errors": []}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            counts = {
                table: int(self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in ("artifacts", "claims", "leases", "daemon_health", "index_archives")
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
    "MAX_RECOVERY_ERRORS",
    "RetentionPolicy",
    "ROOT_CAS_INTERRUPTION_POINTS",
    "STATE_ROOT_TRANSITION_SCHEMA",
    "cid_for_artifact",
    "cid_for_bytes",
    "validate_transport_cid",
]
