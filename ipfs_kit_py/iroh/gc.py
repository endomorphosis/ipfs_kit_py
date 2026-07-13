"""Durable reference tracking and conservative garbage collection for Iroh.

Iroh blobs are immutable, but an Iroh filesystem is not: namespace heads move
and readers can remain on an older revision.  This module keeps the information
needed to decide when a blob is safe to release in a small SQLite database.  A
collector never relies on a stale reference count.  Candidates are marked in a
transaction and every candidate is checked again immediately before it is sent
to the sidecar.

The default policy deliberately has a grace period.  Consequently a blob which
has only just become unreferenced cannot be destroyed by a default collection.
Leases provide the corresponding protection for active readers and writers.
Sweep operation ids and candidate state are durable, so retrying an interrupted
run is safe when used with the protocol-1 idempotent ``blobs.release`` method.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import sqlite3
import time
import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, TypeAlias

from blake3 import blake3

from .blob_store import validate_blob_hash
from .errors import IrohConflictError, IrohIntegrityError, IrohProtocolError
from .manifest import DirectoryManifest, validate_manifest

GC_SCHEMA_VERSION = 1
GC_RECEIPT_SCHEMA_VERSION = 1
GC_RECEIPT_KIND = "ipfs-kit-iroh-gc-receipt"
DEFAULT_RETENTION_SECONDS = 24 * 60 * 60
MAX_LEASE_SECONDS = 30 * 24 * 60 * 60


class Clock(Protocol):
    def __call__(self) -> float: ...


DeleteBlob: TypeAlias = Callable[[str, str], Awaitable[Any] | Any]


def _system_clock() -> float:
    return time.time()


@dataclass(frozen=True, slots=True)
class GCPolicy:
    """Safety and quota policy for one collection.

    ``retention_seconds`` is measured from the instant the last durable
    reference disappears.  Setting it to zero is explicit opt-in to immediate
    collection.  ``max_delete_bytes`` and ``max_delete_count`` bound one sweep;
    omitted bounds are unlimited.  A quota limits the desired total tracked
    storage, but never overrides retention or a lease.
    """

    retention_seconds: float = DEFAULT_RETENTION_SECONDS
    max_delete_bytes: int | None = None
    max_delete_count: int | None = None
    quota_bytes: int | None = None

    def __post_init__(self) -> None:
        _non_negative_number(self.retention_seconds, "retention_seconds")
        _optional_uint(self.max_delete_bytes, "max_delete_bytes")
        _optional_uint(self.max_delete_count, "max_delete_count")
        _optional_uint(self.quota_bytes, "quota_bytes")


@dataclass(frozen=True, slots=True)
class GCCandidate:
    blob_hash: str
    size: int
    unreferenced_at: str
    operation_id: str

    @property
    def hash(self) -> str:
        return self.blob_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "blob_hash": self.blob_hash,
            "size": self.size,
            "unreferenced_at": self.unreferenced_at,
            "operation_id": self.operation_id,
        }


@dataclass(frozen=True, slots=True)
class GCMark:
    run_id: str
    marked_at: str
    retention_seconds: float
    candidates: tuple[GCCandidate, ...]
    tracked_bytes: int
    referenced_bytes: int
    leased_bytes: int
    quota_bytes: int | None

    @property
    def candidate_bytes(self) -> int:
        return sum(item.size for item in self.candidates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "marked_at": self.marked_at,
            "retention_seconds": self.retention_seconds,
            "tracked_bytes": self.tracked_bytes,
            "referenced_bytes": self.referenced_bytes,
            "leased_bytes": self.leased_bytes,
            "quota_bytes": self.quota_bytes,
            "candidate_count": len(self.candidates),
            "candidate_bytes": self.candidate_bytes,
            "candidates": [item.to_dict() for item in self.candidates],
        }


@dataclass(frozen=True, slots=True)
class GCFailure:
    blob_hash: str
    code: str

    def to_dict(self) -> dict[str, str]:
        return {"blob_hash": self.blob_hash, "code": self.code}


@dataclass(frozen=True, slots=True)
class GCReceipt:
    """Canonical, secret-free evidence for a mark/sweep run."""

    run_id: str
    started_at: str
    completed_at: str
    dry_run: bool
    retention_seconds: float
    marked: tuple[GCCandidate, ...]
    deleted: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    failures: tuple[GCFailure, ...] = ()
    tracked_bytes: int = 0
    referenced_bytes: int = 0
    leased_bytes: int = 0
    quota_bytes: int | None = None
    reclaimed_bytes: int = 0
    interrupted: bool = False
    kind: str = GC_RECEIPT_KIND
    schema_version: int = GC_RECEIPT_SCHEMA_VERSION

    @property
    def candidate_count(self) -> int:
        return len(self.marked)

    @property
    def deleted_count(self) -> int:
        return len(self.deleted)

    @property
    def success(self) -> bool:
        return not self.failures and not self.interrupted

    def to_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "dry_run": self.dry_run,
            "interrupted": self.interrupted,
            "retention_seconds": self.retention_seconds,
            "tracked_bytes": self.tracked_bytes,
            "referenced_bytes": self.referenced_bytes,
            "leased_bytes": self.leased_bytes,
            "quota_bytes": self.quota_bytes,
            "candidate_count": self.candidate_count,
            "candidate_bytes": sum(item.size for item in self.marked),
            "deleted_count": self.deleted_count,
            "reclaimed_bytes": self.reclaimed_bytes,
            "marked": [item.to_dict() for item in self.marked],
            "deleted": list(self.deleted),
            "skipped": list(self.skipped),
            "failures": [item.to_dict() for item in self.failures],
        }
        if include_digest:
            value["receipt_digest"] = blake3(_canonical_json(value)).hexdigest()
        return value

    @property
    def receipt_digest(self) -> str:
        return self.to_dict()["receipt_digest"]

    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.to_dict())

    def to_json(self) -> str:
        return self.canonical_bytes().decode("utf-8")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GCReceipt":
        """Parse and cryptographically verify an audit receipt."""

        if not isinstance(value, Mapping):
            raise IrohIntegrityError("GC receipt must be an object", operation="gc.receipt")
        document = dict(value)
        declared_digest = document.pop("receipt_digest", None)
        if (
            not isinstance(declared_digest, str)
            or declared_digest != blake3(_canonical_json(document)).hexdigest()
        ):
            raise IrohIntegrityError("GC receipt digest is invalid", operation="gc.receipt")
        allowed = {
            "schema_version",
            "kind",
            "run_id",
            "started_at",
            "completed_at",
            "dry_run",
            "interrupted",
            "retention_seconds",
            "tracked_bytes",
            "referenced_bytes",
            "leased_bytes",
            "quota_bytes",
            "candidate_count",
            "candidate_bytes",
            "deleted_count",
            "reclaimed_bytes",
            "marked",
            "deleted",
            "skipped",
            "failures",
        }
        if set(document) != allowed:
            raise IrohIntegrityError("GC receipt shape is invalid", operation="gc.receipt")
        if (
            document["schema_version"] != GC_RECEIPT_SCHEMA_VERSION
            or document["kind"] != GC_RECEIPT_KIND
        ):
            raise IrohIntegrityError("GC receipt version is unsupported", operation="gc.receipt")
        try:
            marked = tuple(
                GCCandidate(
                    item["blob_hash"],
                    item["size"],
                    item["unreferenced_at"],
                    item["operation_id"],
                )
                for item in document["marked"]
            )
            failures = tuple(
                GCFailure(item["blob_hash"], item["code"]) for item in document["failures"]
            )
            receipt = cls(
                document["run_id"],
                document["started_at"],
                document["completed_at"],
                document["dry_run"],
                document["retention_seconds"],
                marked,
                tuple(document["deleted"]),
                tuple(document["skipped"]),
                failures,
                document["tracked_bytes"],
                document["referenced_bytes"],
                document["leased_bytes"],
                document["quota_bytes"],
                document["reclaimed_bytes"],
                document["interrupted"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise IrohIntegrityError("GC receipt is malformed", operation="gc.receipt") from exc
        if receipt.to_dict() != value:
            raise IrohIntegrityError("GC receipt counts are inconsistent", operation="gc.receipt")
        return receipt

    def write(self, destination: str | os.PathLike[str]) -> Path:
        """Atomically persist the canonical receipt with owner-only permissions."""

        target = Path(destination)
        parent_existed = target.parent.exists()
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not parent_existed:
            try:
                os.chmod(target.parent, 0o700)
            except OSError:
                pass
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        descriptor: int | None = None
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            data = self.canonical_bytes()
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("short receipt write")
                view = view[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.replace(temporary, target)
            os.chmod(target, 0o600)
            try:
                directory = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            except OSError:
                # Windows does not permit opening a directory as a file.  The
                # receipt itself has already been flushed and atomically moved.
                pass
            return target
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    save = write


@dataclass(frozen=True, slots=True)
class RepairReceipt:
    manifests_examined: int
    blobs_examined: int
    references_added: int
    references_removed: int
    missing_blobs: tuple[str, ...]
    dry_run: bool

    @property
    def healthy(self) -> bool:
        return not self.missing_blobs

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifests_examined": self.manifests_examined,
            "blobs_examined": self.blobs_examined,
            "references_added": self.references_added,
            "references_removed": self.references_removed,
            "missing_blobs": list(self.missing_blobs),
            "dry_run": self.dry_run,
            "healthy": self.healthy,
        }


@dataclass(frozen=True, slots=True)
class Lease:
    lease_id: str
    blob_hashes: tuple[str, ...]
    owner: str
    expires_at: str


@dataclass(frozen=True, slots=True)
class QuotaStatus:
    namespace_id: str
    usage_bytes: int
    quota_bytes: int | None
    additional_bytes: int = 0

    @property
    def allowed(self) -> bool:
        return self.quota_bytes is None or (
            self.usage_bytes + self.additional_bytes <= self.quota_bytes
        )

    @property
    def remaining_bytes(self) -> int | None:
        if self.quota_bytes is None:
            return None
        return max(self.quota_bytes - self.usage_bytes, 0)


class LeaseHandle:
    """A renewable sync/async context manager for an index lease."""

    def __init__(self, index: "ReferenceTracker", lease: Lease) -> None:
        self.index = index
        self.lease = lease
        self.closed = False

    def renew(self, ttl_seconds: float) -> Lease:
        self.lease = self.index.renew_lease(self.lease.lease_id, ttl_seconds)
        return self.lease

    @property
    def lease_id(self) -> str:
        return self.lease.lease_id

    @property
    def blob_hashes(self) -> tuple[str, ...]:
        return self.lease.blob_hashes

    @property
    def owner(self) -> str:
        return self.lease.owner

    @property
    def expires_at(self) -> str:
        return self.lease.expires_at

    def close(self) -> None:
        if not self.closed:
            self.index.release_lease(self.lease.lease_id)
            self.closed = True

    def __enter__(self) -> "LeaseHandle":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    async def __aenter__(self) -> "LeaseHandle":
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.close()


class ReferenceTracker:
    """Transactional SQLite index of blobs, revisions, and active leases."""

    def __init__(
        self,
        database: str | os.PathLike[str] = ":memory:",
        *,
        clock: Clock = _system_clock,
    ) -> None:
        self.database = os.fspath(database)
        self.clock = clock
        if self.database != ":memory:":
            path = Path(self.database)
            parent_existed = path.parent.exists()
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not parent_existed:
                try:
                    os.chmod(path.parent, 0o700)
                except OSError:
                    pass
        self._db = sqlite3.connect(self.database, isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.execute("PRAGMA synchronous=FULL")
        if self.database != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
            try:
                os.chmod(self.database, 0o600)
            except OSError:
                pass
        self._create_schema()

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "ReferenceTracker":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _create_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS gc_metadata (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS blobs (
                blob_hash TEXT PRIMARY KEY, size INTEGER NOT NULL CHECK(size >= 0),
                first_seen REAL NOT NULL, unreferenced_at REAL, deleted_at REAL
            );
            CREATE TABLE IF NOT EXISTS revisions (
                namespace_id TEXT NOT NULL, revision INTEGER NOT NULL,
                manifest_hash TEXT NOT NULL, created_at REAL NOT NULL,
                retained_until REAL, active INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY(namespace_id, revision)
            );
            CREATE TABLE IF NOT EXISTS revision_refs (
                namespace_id TEXT NOT NULL, revision INTEGER NOT NULL,
                blob_hash TEXT NOT NULL,
                PRIMARY KEY(namespace_id, revision, blob_hash),
                FOREIGN KEY(namespace_id, revision) REFERENCES revisions(namespace_id, revision)
                    ON DELETE CASCADE,
                FOREIGN KEY(blob_hash) REFERENCES blobs(blob_hash)
            );
            CREATE TABLE IF NOT EXISTS leases (
                lease_id TEXT NOT NULL, blob_hash TEXT NOT NULL, owner TEXT NOT NULL,
                expires_at REAL NOT NULL,
                PRIMARY KEY(lease_id, blob_hash),
                FOREIGN KEY(blob_hash) REFERENCES blobs(blob_hash)
            );
            CREATE TABLE IF NOT EXISTS namespace_quotas (
                namespace_id TEXT PRIMARY KEY,
                quota_bytes INTEGER NOT NULL CHECK(quota_bytes >= 0)
            );
            CREATE TABLE IF NOT EXISTS gc_runs (
                run_id TEXT PRIMARY KEY, marked_at REAL NOT NULL,
                retention_seconds REAL NOT NULL, dry_run INTEGER NOT NULL,
                policy_json TEXT NOT NULL, status TEXT NOT NULL,
                completed_at REAL, receipt_json TEXT
            );
            CREATE TABLE IF NOT EXISTS gc_candidates (
                run_id TEXT NOT NULL, blob_hash TEXT NOT NULL, size INTEGER NOT NULL,
                unreferenced_at REAL NOT NULL, operation_id TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'marked', error_code TEXT,
                PRIMARY KEY(run_id, blob_hash),
                FOREIGN KEY(run_id) REFERENCES gc_runs(run_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS revision_refs_hash ON revision_refs(blob_hash);
            CREATE INDEX IF NOT EXISTS leases_hash_expiry ON leases(blob_hash, expires_at);
            """
        )
        row = self._db.execute(
            "SELECT value FROM gc_metadata WHERE key='schema_version'"
        ).fetchone()
        if row is None:
            self._db.execute(
                "INSERT INTO gc_metadata(key, value) VALUES('schema_version', ?)",
                (str(GC_SCHEMA_VERSION),),
            )
        elif row[0] != str(GC_SCHEMA_VERSION):
            raise IrohIntegrityError("unsupported GC index schema", operation="gc.open")
        # Additive migration for schema-1 databases created before finalized
        # receipts were journaled.
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(gc_runs)")}
        if "completed_at" not in columns:
            self._db.execute("ALTER TABLE gc_runs ADD COLUMN completed_at REAL")
        if "receipt_json" not in columns:
            self._db.execute("ALTER TABLE gc_runs ADD COLUMN receipt_json TEXT")

    def register_blob(
        self, blob_hash: str, size: int, *, first_seen: float | datetime | None = None
    ) -> None:
        digest = validate_blob_hash(blob_hash)
        _uint(size, "size")
        seen = _epoch(first_seen, self.clock())
        with self._transaction():
            row = self._db.execute("SELECT size FROM blobs WHERE blob_hash=?", (digest,)).fetchone()
            if row is not None and row[0] not in (0, size) and size != 0:
                raise IrohIntegrityError(
                    "tracked blob size changed",
                    operation="gc.register",
                    metadata={"blob_hash": digest},
                )
            self._db.execute(
                """INSERT INTO blobs(blob_hash,size,first_seen,unreferenced_at)
                   VALUES(?,?,?,?) ON CONFLICT(blob_hash) DO UPDATE SET
                     size=CASE WHEN blobs.size=0 THEN excluded.size ELSE blobs.size END,
                     unreferenced_at=CASE WHEN blobs.deleted_at IS NOT NULL
                       THEN excluded.unreferenced_at ELSE blobs.unreferenced_at END,
                     deleted_at=NULL""",
                (digest, size, seen, seen),
            )

    def register_blobs(self, blobs: Iterable[Any]) -> None:
        for blob in blobs:
            if isinstance(blob, Mapping):
                self.register_blob(blob.get("blob_hash", blob.get("hash")), blob["size"])
            elif hasattr(blob, "hash") and hasattr(blob, "size"):
                self.register_blob(blob.hash, blob.size)
            else:
                digest, size = blob
                self.register_blob(digest, size)

    def track_manifest(
        self,
        manifest: DirectoryManifest | Mapping[str, Any] | str | bytes,
        *,
        retained_until: float | datetime | None = None,
        blob_sizes: Mapping[str, int] | None = None,
    ) -> int:
        """Record one immutable revision; repeated identical calls are idempotent."""

        value = validate_manifest(manifest)
        now = self.clock()
        until = _epoch(retained_until, None)
        references: dict[str, int] = {}
        sizes = blob_sizes or {}
        for entry in value.entries:
            # The strict v1 manifest retains old file references in the prior
            # immutable revision, while tombstones intentionally carry no blob
            # fields.  Legacy manifests may expose ``prior_blob_hash`` during
            # migration, so accept it without requiring that compatibility
            # attribute on every ManifestEntry.
            digest = (
                entry.blob_hash if entry.kind == "file" else getattr(entry, "prior_blob_hash", None)
            )
            if digest is not None:
                size = entry.size if entry.size is not None else sizes.get(digest, 0)
                previous = references.get(digest)
                if previous not in (None, 0, size) and size != 0:
                    raise IrohIntegrityError(
                        "one blob has inconsistent sizes in a manifest",
                        operation="gc.track_manifest",
                        metadata={"blob_hash": digest},
                    )
                references[digest] = previous if size == 0 and previous is not None else size
        with self._transaction():
            existing = self._db.execute(
                "SELECT manifest_hash FROM revisions WHERE namespace_id=? AND revision=?",
                (value.namespace_id, value.revision),
            ).fetchone()
            if existing is not None and existing[0] != value.manifest_hash:
                raise IrohConflictError(
                    "revision is already tracked with a different manifest",
                    operation="gc.track_manifest",
                )
            self._db.execute(
                """INSERT INTO revisions(namespace_id,revision,manifest_hash,created_at,retained_until,active)
                   VALUES(?,?,?,?,?,1)
                   ON CONFLICT(namespace_id,revision) DO UPDATE SET active=1,
                       retained_until=excluded.retained_until""",
                (
                    value.namespace_id,
                    value.revision,
                    value.manifest_hash,
                    _timestamp_epoch(value.created_at),
                    until,
                ),
            )
            old = {
                row[0]
                for row in self._db.execute(
                    "SELECT blob_hash FROM revision_refs WHERE namespace_id=? AND revision=?",
                    (value.namespace_id, value.revision),
                )
            }
            if existing is not None and old != set(references):
                raise IrohIntegrityError(
                    "tracked revision references do not match its manifest",
                    operation="gc.track_manifest",
                )
            for digest, size in references.items():
                validate_blob_hash(digest)
                _uint(size, "blob size")
                row = self._db.execute(
                    "SELECT size FROM blobs WHERE blob_hash=?", (digest,)
                ).fetchone()
                if row is not None and size and row[0] not in (0, size):
                    raise IrohIntegrityError(
                        "manifest blob size conflicts with tracked size",
                        operation="gc.track_manifest",
                        metadata={"blob_hash": digest},
                    )
                self._db.execute(
                    """INSERT INTO blobs(blob_hash,size,first_seen,unreferenced_at)
                       VALUES(?,?,?,NULL)
                       ON CONFLICT(blob_hash) DO UPDATE SET
                         size=CASE WHEN blobs.size=0 THEN excluded.size ELSE blobs.size END,
                         unreferenced_at=NULL, deleted_at=NULL""",
                    (digest, size, now),
                )
                self._db.execute(
                    "INSERT OR IGNORE INTO revision_refs(namespace_id,revision,blob_hash) VALUES(?,?,?)",
                    (value.namespace_id, value.revision, digest),
                )
            self._refresh_unreferenced(now)
        return len(references)

    record_manifest = track_manifest

    def retire_revision(
        self,
        namespace_id: str,
        revision: int,
        *,
        retain_for: float = DEFAULT_RETENTION_SECONDS,
    ) -> None:
        _identifier(namespace_id, "namespace_id")
        _uint(revision, "revision")
        _non_negative_number(retain_for, "retain_for")
        now = self.clock()
        with self._transaction():
            cursor = self._db.execute(
                """UPDATE revisions SET active=0, retained_until=?
                   WHERE namespace_id=? AND revision=?""",
                (now + float(retain_for), namespace_id, revision),
            )
            if cursor.rowcount != 1:
                raise KeyError((namespace_id, revision))
            self._refresh_unreferenced(now)

    release_revision = retire_revision

    def forget_revision(self, namespace_id: str, revision: int) -> None:
        """Remove a revision now; GC policy still applies to its blobs."""

        _identifier(namespace_id, "namespace_id")
        _uint(revision, "revision")
        now = self.clock()
        with self._transaction():
            self._db.execute(
                "DELETE FROM revisions WHERE namespace_id=? AND revision=?",
                (namespace_id, revision),
            )
            self._refresh_unreferenced(now)

    def acquire_lease(
        self,
        blob_hashes: str | Iterable[str],
        *,
        ttl_seconds: float,
        owner: str = "anonymous",
        lease_id: str | None = None,
    ) -> LeaseHandle:
        _lease_ttl(ttl_seconds)
        _identifier(owner, "owner", max_length=255)
        lease_id = lease_id or str(uuid.uuid4())
        _identifier(lease_id, "lease_id", max_length=255)
        values = (blob_hashes,) if isinstance(blob_hashes, str) else tuple(blob_hashes)
        hashes = tuple(sorted({validate_blob_hash(item) for item in values}))
        if not hashes:
            raise ValueError("a lease must protect at least one blob")
        expires = self.clock() + float(ttl_seconds)
        with self._transaction():
            for digest in hashes:
                if (
                    self._db.execute("SELECT 1 FROM blobs WHERE blob_hash=?", (digest,)).fetchone()
                    is None
                ):
                    raise KeyError(digest)
                self._db.execute(
                    "INSERT INTO leases(lease_id,blob_hash,owner,expires_at) VALUES(?,?,?,?)",
                    (lease_id, digest, owner, expires),
                )
        lease = Lease(lease_id, hashes, owner, _rfc3339(expires))
        return LeaseHandle(self, lease)

    lease = acquire_lease

    def renew_lease(self, lease_id: str, ttl_seconds: float) -> Lease:
        _identifier(lease_id, "lease_id", max_length=255)
        _lease_ttl(ttl_seconds)
        expires = self.clock() + float(ttl_seconds)
        with self._transaction():
            rows = self._db.execute(
                "SELECT blob_hash,owner FROM leases WHERE lease_id=?", (lease_id,)
            ).fetchall()
            if not rows:
                raise KeyError(lease_id)
            self._db.execute("UPDATE leases SET expires_at=? WHERE lease_id=?", (expires, lease_id))
        return Lease(lease_id, tuple(sorted(row[0] for row in rows)), rows[0][1], _rfc3339(expires))

    def release_lease(self, lease_id: str | Lease | LeaseHandle) -> None:
        if isinstance(lease_id, LeaseHandle):
            lease_id = lease_id.lease_id
        elif isinstance(lease_id, Lease):
            lease_id = lease_id.lease_id
        _identifier(lease_id, "lease_id", max_length=255)
        self._db.execute("DELETE FROM leases WHERE lease_id=?", (lease_id,))

    def quota_usage(self, namespace_id: str | None = None) -> int:
        """Return unique live bytes globally or for one namespace."""

        now = self.clock()
        if namespace_id is None:
            row = self._db.execute(
                "SELECT COALESCE(SUM(size),0) FROM blobs WHERE deleted_at IS NULL"
            ).fetchone()
        else:
            _identifier(namespace_id, "namespace_id")
            row = self._db.execute(
                """SELECT COALESCE(SUM(b.size),0) FROM blobs b WHERE b.deleted_at IS NULL
                   AND EXISTS (SELECT 1 FROM revision_refs rr JOIN revisions r
                     ON r.namespace_id=rr.namespace_id AND r.revision=rr.revision
                     WHERE rr.blob_hash=b.blob_hash AND r.namespace_id=?
                       AND (r.active=1 OR r.retained_until>?))""",
                (namespace_id, now),
            ).fetchone()
        return int(row[0])

    def set_quota(self, namespace_id: str, quota_bytes: int | None) -> None:
        """Set or clear a durable namespace quota."""

        _identifier(namespace_id, "namespace_id")
        _optional_uint(quota_bytes, "quota_bytes")
        if quota_bytes is None:
            self._db.execute("DELETE FROM namespace_quotas WHERE namespace_id=?", (namespace_id,))
        else:
            self._db.execute(
                """INSERT INTO namespace_quotas(namespace_id,quota_bytes) VALUES(?,?)
                   ON CONFLICT(namespace_id) DO UPDATE SET quota_bytes=excluded.quota_bytes""",
                (namespace_id, quota_bytes),
            )

    def quota_status(self, namespace_id: str, *, additional_bytes: int = 0) -> QuotaStatus:
        _identifier(namespace_id, "namespace_id")
        _uint(additional_bytes, "additional_bytes")
        row = self._db.execute(
            "SELECT quota_bytes FROM namespace_quotas WHERE namespace_id=?", (namespace_id,)
        ).fetchone()
        return QuotaStatus(
            namespace_id,
            self.quota_usage(namespace_id),
            None if row is None else int(row[0]),
            additional_bytes,
        )

    def check_quota(self, namespace_id: str, *, additional_bytes: int = 0) -> bool:
        return self.quota_status(namespace_id, additional_bytes=additional_bytes).allowed

    def enforce_quota(self, namespace_id: str, *, additional_bytes: int = 0) -> QuotaStatus:
        status = self.quota_status(namespace_id, additional_bytes=additional_bytes)
        if not status.allowed:
            raise IrohConflictError(
                "namespace storage quota would be exceeded",
                operation="gc.quota",
                metadata={
                    "usage_bytes": status.usage_bytes,
                    "quota_bytes": status.quota_bytes,
                    "additional_bytes": status.additional_bytes,
                },
            )
        return status

    def repair(
        self,
        manifests: Iterable[DirectoryManifest | Mapping[str, Any] | str | bytes],
        blobs: Iterable[Any] | None = None,
        *,
        dry_run: bool = True,
    ) -> RepairReceipt:
        """Audit/rebuild revision references from authoritative manifests."""

        values = tuple(validate_manifest(item) for item in manifests)
        inventory: dict[str, int] = {}
        for item in blobs or ():
            if isinstance(item, Mapping):
                inventory[validate_blob_hash(item.get("blob_hash", item.get("hash")))] = item[
                    "size"
                ]
            elif hasattr(item, "hash"):
                inventory[validate_blob_hash(item.hash)] = item.size
            else:
                digest, size = item
                inventory[validate_blob_hash(digest)] = size
        desired = {
            (manifest.namespace_id, manifest.revision, digest)
            for manifest in values
            for entry in manifest.entries
            for digest in (
                (
                    entry.blob_hash
                    if entry.kind == "file"
                    else getattr(entry, "prior_blob_hash", None)
                ),
            )
            if digest is not None
        }
        current = {
            tuple(row)
            for row in self._db.execute("SELECT namespace_id,revision,blob_hash FROM revision_refs")
        }
        missing = (
            tuple(sorted({item[2] for item in desired} - set(inventory)))
            if blobs is not None
            else ()
        )
        receipt = RepairReceipt(
            len(values),
            len(inventory),
            len(desired - current),
            len(current - desired),
            missing,
            dry_run,
        )
        if dry_run:
            return receipt
        now = self.clock()
        with self._transaction():
            for digest, size in inventory.items():
                _uint(size, "size")
                self._db.execute(
                    """INSERT INTO blobs(blob_hash,size,first_seen,unreferenced_at)
                       VALUES(?,?,?,?) ON CONFLICT(blob_hash) DO UPDATE SET
                         size=excluded.size,unreferenced_at=excluded.unreferenced_at,
                         deleted_at=NULL""",
                    (digest, size, now, now),
                )
            # Only revisions supplied by this repair are authoritative.  This is
            # intentionally a full repair operation, not an incremental update.
            self._db.execute("DELETE FROM revisions")
            for manifest in values:
                self.track_manifest(manifest, blob_sizes=inventory)
            self._refresh_unreferenced(now)
        return receipt

    def _refresh_unreferenced(self, now: float) -> None:
        self._db.execute("DELETE FROM leases WHERE expires_at<=?", (now,))
        self._db.execute(
            """UPDATE blobs SET unreferenced_at=NULL WHERE deleted_at IS NULL AND EXISTS (
                 SELECT 1 FROM revision_refs rr JOIN revisions r
                   ON r.namespace_id=rr.namespace_id AND r.revision=rr.revision
                 WHERE rr.blob_hash=blobs.blob_hash
                   AND (r.active=1 OR r.retained_until>?))""",
            (now,),
        )
        self._db.execute(
            """UPDATE blobs SET unreferenced_at=COALESCE(unreferenced_at, ?)
               WHERE deleted_at IS NULL AND NOT EXISTS (
                 SELECT 1 FROM revision_refs rr JOIN revisions r
                   ON r.namespace_id=rr.namespace_id AND r.revision=rr.revision
                 WHERE rr.blob_hash=blobs.blob_hash
                   AND (r.active=1 OR r.retained_until>?))""",
            (now, now),
        )

    def _is_protected(self, digest: str, now: float) -> bool:
        return (
            self._db.execute(
                """SELECT 1 FROM blobs b WHERE b.blob_hash=? AND b.deleted_at IS NULL AND (
                 EXISTS (SELECT 1 FROM revision_refs rr JOIN revisions r
                   ON r.namespace_id=rr.namespace_id AND r.revision=rr.revision
                   WHERE rr.blob_hash=b.blob_hash AND (r.active=1 OR r.retained_until>?))
                 OR EXISTS (SELECT 1 FROM leases l WHERE l.blob_hash=b.blob_hash
                   AND l.expires_at>?))""",
                (digest, now, now),
            ).fetchone()
            is not None
        )

    def _transaction(self) -> "_Transaction":
        return _Transaction(self._db)


class _Transaction:
    def __init__(self, database: sqlite3.Connection) -> None:
        self.database = database
        self.savepoint: str | None = None

    def __enter__(self) -> None:
        if self.database.in_transaction:
            self.savepoint = "gc_" + uuid.uuid4().hex
            self.database.execute(f"SAVEPOINT {self.savepoint}")
        else:
            self.database.execute("BEGIN IMMEDIATE")

    def __exit__(self, exc_type: Any, *_: Any) -> None:
        if self.savepoint is None:
            self.database.execute("ROLLBACK" if exc_type else "COMMIT")
        elif exc_type:
            self.database.execute(f"ROLLBACK TO {self.savepoint}")
            self.database.execute(f"RELEASE {self.savepoint}")
        else:
            self.database.execute(f"RELEASE {self.savepoint}")


class IrohGarbageCollector:
    """Mark/sweep coordinator using a :class:`ReferenceTracker`."""

    def __init__(
        self,
        index: ReferenceTracker,
        client: Any | None = None,
        *,
        delete_blob: DeleteBlob | None = None,
        clock: Clock | None = None,
    ) -> None:
        if client is None and delete_blob is None:
            # Dry-run-only collectors are useful for audits.  A live sweep will
            # fail explicitly rather than pretending bytes were reclaimed.
            self._delete_blob = None
        elif delete_blob is not None:
            self._delete_blob = delete_blob
        else:

            async def release(digest: str, operation_id: str) -> Any:
                return await client.request(
                    "blobs.release",
                    {
                        "hash": digest,
                        "reference": "gc",
                        "operation_id": operation_id,
                        "only_if_unprotected": True,
                    },
                )

            self._delete_blob = release
        self.index = index
        self.clock = clock or index.clock
        self._lock = asyncio.Lock()

    async def mark(
        self,
        policy: GCPolicy | None = None,
        *,
        dry_run: bool = True,
        run_id: str | None = None,
    ) -> GCMark:
        policy = policy or GCPolicy()
        run_id = run_id or str(uuid.uuid4())
        _identifier(run_id, "run_id", max_length=255)
        now = self.clock()
        cutoff = now - float(policy.retention_seconds)
        db = self.index._db
        with self.index._transaction():
            self.index._refresh_unreferenced(now)
            if db.execute("SELECT 1 FROM gc_runs WHERE run_id=?", (run_id,)).fetchone():
                raise IrohConflictError("GC run id already exists", operation="gc.mark")
            stats = db.execute(
                """SELECT COALESCE(SUM(size),0),
                   COALESCE(SUM(CASE WHEN unreferenced_at IS NULL THEN size ELSE 0 END),0)
                   FROM blobs WHERE deleted_at IS NULL"""
            ).fetchone()
            leased = db.execute(
                """SELECT COALESCE(SUM(size),0) FROM blobs b WHERE b.deleted_at IS NULL
                   AND EXISTS(SELECT 1 FROM leases l WHERE l.blob_hash=b.blob_hash
                     AND l.expires_at>?)""",
                (now,),
            ).fetchone()[0]
            rows = db.execute(
                """SELECT blob_hash,size,unreferenced_at FROM blobs b
                   WHERE deleted_at IS NULL AND unreferenced_at IS NOT NULL
                     AND unreferenced_at<=?
                     AND NOT EXISTS(SELECT 1 FROM leases l WHERE l.blob_hash=b.blob_hash
                       AND l.expires_at>?)
                   ORDER BY unreferenced_at, blob_hash""",
                (cutoff, now),
            ).fetchall()
            rows = self._apply_limits(rows, policy, int(stats[0]))
            policy_json = json.dumps(
                {
                    "retention_seconds": policy.retention_seconds,
                    "max_delete_bytes": policy.max_delete_bytes,
                    "max_delete_count": policy.max_delete_count,
                    "quota_bytes": policy.quota_bytes,
                    "_tracked_bytes": int(stats[0]),
                    "_referenced_bytes": int(stats[1]),
                    "_leased_bytes": int(leased),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            db.execute(
                """INSERT INTO gc_runs(
                     run_id,marked_at,retention_seconds,dry_run,policy_json,status
                   ) VALUES(?,?,?,?,?,'marked')""",
                (run_id, now, float(policy.retention_seconds), int(dry_run), policy_json),
            )
            candidates: list[GCCandidate] = []
            for row in rows:
                operation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"iroh-gc:{run_id}:{row[0]}"))
                db.execute(
                    "INSERT INTO gc_candidates VALUES(?,?,?,?,?,'marked',NULL)",
                    (run_id, row[0], row[1], row[2], operation_id),
                )
                candidates.append(GCCandidate(row[0], row[1], _rfc3339(row[2]), operation_id))
        return GCMark(
            run_id,
            _rfc3339(now),
            float(policy.retention_seconds),
            tuple(candidates),
            int(stats[0]),
            int(stats[1]),
            int(leased),
            policy.quota_bytes,
        )

    @staticmethod
    def _apply_limits(
        rows: Sequence[sqlite3.Row], policy: GCPolicy, usage: int
    ) -> list[sqlite3.Row]:
        count_limit = policy.max_delete_count
        byte_limit = policy.max_delete_bytes
        # With a quota, reclaim only the eligible bytes required to reach it.
        quota_need = None if policy.quota_bytes is None else max(usage - policy.quota_bytes, 0)
        selected: list[sqlite3.Row] = []
        total = 0
        for row in rows:
            if count_limit is not None and len(selected) >= count_limit:
                break
            if byte_limit is not None and total + row[1] > byte_limit:
                continue
            if quota_need is not None and total >= quota_need:
                break
            selected.append(row)
            total += row[1]
        return selected

    async def sweep(self, mark: GCMark | str, *, dry_run: bool | None = None) -> GCReceipt:
        run_id = mark.run_id if isinstance(mark, GCMark) else mark
        _identifier(run_id, "run_id", max_length=255)
        async with self._lock:
            return await self._sweep_locked(run_id, dry_run=dry_run)

    async def _sweep_locked(self, run_id: str, *, dry_run: bool | None) -> GCReceipt:
        db = self.index._db
        run = db.execute("SELECT * FROM gc_runs WHERE run_id=?", (run_id,)).fetchone()
        if run is None:
            raise KeyError(run_id)
        if run["receipt_json"] is not None:
            return verify_gc_receipt(run["receipt_json"])
        actual_dry_run = bool(run["dry_run"]) if dry_run is None else dry_run
        if not isinstance(actual_dry_run, bool):
            raise TypeError("dry_run must be a boolean")
        rows = db.execute(
            "SELECT * FROM gc_candidates WHERE run_id=? ORDER BY unreferenced_at,blob_hash",
            (run_id,),
        ).fetchall()
        marked = tuple(
            GCCandidate(
                row["blob_hash"], row["size"], _rfc3339(row["unreferenced_at"]), row["operation_id"]
            )
            for row in rows
        )
        started = run["marked_at"]
        if actual_dry_run:
            db.execute("UPDATE gc_runs SET status='dry-run' WHERE run_id=?", (run_id,))
            return self._receipt(run, marked, (), (), (), 0, started, actual_dry_run)
        if self._delete_blob is None:
            raise RuntimeError("live garbage collection requires a client or delete_blob callback")
        deleted: list[str] = []
        skipped: list[str] = []
        failures: list[GCFailure] = []
        reclaimed = 0
        for row in rows:
            if row["state"] == "deleted":
                deleted.append(row["blob_hash"])
                reclaimed += row["size"]
                continue
            now = self.clock()
            with self.index._transaction():
                self.index._refresh_unreferenced(now)
                current = db.execute(
                    "SELECT unreferenced_at,deleted_at FROM blobs WHERE blob_hash=?",
                    (row["blob_hash"],),
                ).fetchone()
                protected = (
                    current is None
                    or current["deleted_at"] is not None
                    or self.index._is_protected(row["blob_hash"], now)
                )
                # A remove/re-add cycle changes unreferenced_at.  Such a blob is
                # skipped even if its new reference has already disappeared.
                changed = (
                    current is not None and current["unreferenced_at"] != row["unreferenced_at"]
                )
                if protected or changed:
                    db.execute(
                        "UPDATE gc_candidates SET state='skipped' WHERE run_id=? AND blob_hash=?",
                        (run_id, row["blob_hash"]),
                    )
                    skipped.append(row["blob_hash"])
                    continue
                db.execute(
                    "UPDATE gc_candidates SET state='deleting' WHERE run_id=? AND blob_hash=?",
                    (run_id, row["blob_hash"]),
                )
            try:
                result = _call_delete(self._delete_blob, row["blob_hash"], row["operation_id"])
                if inspect.isawaitable(result):
                    result = await result
                if not _release_confirmed(result, row["blob_hash"]):
                    db.execute(
                        "UPDATE gc_candidates SET state='skipped' WHERE run_id=? AND blob_hash=?",
                        (run_id, row["blob_hash"]),
                    )
                    skipped.append(row["blob_hash"])
                    continue
            except asyncio.CancelledError:
                db.execute("UPDATE gc_runs SET status='interrupted' WHERE run_id=?", (run_id,))
                raise
            except Exception as exc:  # one failed blob must not hide other safe candidates
                code = _failure_code(exc)
                db.execute(
                    "UPDATE gc_candidates SET state='failed',error_code=? WHERE run_id=? AND blob_hash=?",
                    (code, run_id, row["blob_hash"]),
                )
                failures.append(GCFailure(row["blob_hash"], code))
                continue
            with self.index._transaction():
                # A reference may have appeared while the idempotent release was
                # in flight.  It remains tracked and is reported as skipped; the
                # sidecar's reference protection prevents physical collection.
                now = self.clock()
                if self.index._is_protected(row["blob_hash"], now):
                    db.execute(
                        "UPDATE gc_candidates SET state='skipped' WHERE run_id=? AND blob_hash=?",
                        (run_id, row["blob_hash"]),
                    )
                    skipped.append(row["blob_hash"])
                else:
                    db.execute(
                        "UPDATE blobs SET deleted_at=? WHERE blob_hash=?", (now, row["blob_hash"])
                    )
                    db.execute(
                        "UPDATE gc_candidates SET state='deleted',error_code=NULL WHERE run_id=? AND blob_hash=?",
                        (run_id, row["blob_hash"]),
                    )
                    deleted.append(row["blob_hash"])
                    reclaimed += row["size"]
        status = "failed" if failures else "completed"
        db.execute("UPDATE gc_runs SET status=? WHERE run_id=?", (status, run_id))
        return self._receipt(
            run,
            marked,
            tuple(deleted),
            tuple(skipped),
            tuple(failures),
            reclaimed,
            started,
            actual_dry_run,
        )

    def _receipt(
        self,
        run: sqlite3.Row,
        marked: tuple[GCCandidate, ...],
        deleted: tuple[str, ...],
        skipped: tuple[str, ...],
        failures: tuple[GCFailure, ...],
        reclaimed: int,
        started: float,
        dry_run: bool,
    ) -> GCReceipt:
        now = self.clock()
        policy = json.loads(run["policy_json"])
        receipt = GCReceipt(
            run["run_id"],
            _rfc3339(started),
            _rfc3339(now),
            dry_run,
            run["retention_seconds"],
            marked,
            deleted,
            skipped,
            failures,
            policy.get("_tracked_bytes", 0),
            policy.get("_referenced_bytes", 0),
            policy.get("_leased_bytes", 0),
            policy.get("quota_bytes"),
            reclaimed,
        )
        self.index._db.execute(
            "UPDATE gc_runs SET completed_at=?,receipt_json=? WHERE run_id=?",
            (now, receipt.to_json(), run["run_id"]),
        )
        return receipt

    async def collect(
        self,
        *,
        dry_run: bool = True,
        policy: GCPolicy | None = None,
        run_id: str | None = None,
    ) -> GCReceipt:
        async with self._lock:
            mark = await self.mark(policy, dry_run=dry_run, run_id=run_id)
            return await self._sweep_locked(mark.run_id, dry_run=dry_run)

    run = collect

    async def resume(self, run_id: str) -> GCReceipt:
        """Resume an interrupted live run using its stable operation ids."""

        return await self.sweep(run_id, dry_run=False)


GarbageCollector = IrohGarbageCollector
ReferenceIndex = ReferenceTracker


def verify_gc_receipt(
    value: Mapping[str, Any] | str | bytes | os.PathLike[str],
) -> GCReceipt:
    """Load and verify a canonical receipt or owner-provided receipt path."""

    if isinstance(value, os.PathLike):
        path = Path(value)
        if path.is_symlink() or not path.is_file():
            raise IrohIntegrityError("GC receipt is not a regular file", operation="gc.receipt")
        value = path.read_bytes()
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeError as exc:
            raise IrohIntegrityError("GC receipt is not UTF-8", operation="gc.receipt") from exc
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise IrohIntegrityError("GC receipt is invalid JSON", operation="gc.receipt") from exc
    return GCReceipt.from_dict(value)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _rfc3339(value: float) -> str:
    return (
        datetime.fromtimestamp(value, timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _timestamp_epoch(value: str) -> float:
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").timestamp()
    except (ValueError, TypeError) as exc:
        raise IrohProtocolError(
            "manifest timestamp is invalid", operation="gc.track_manifest"
        ) from exc


def _epoch(value: float | datetime | None, default: float | None) -> float | None:
    if value is None:
        return default
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.timestamp()
    _non_negative_number(value, "timestamp")
    return float(value)


def _uint(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _optional_uint(value: Any, name: str) -> None:
    if value is not None:
        _uint(value, name)


def _non_negative_number(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{name} must be a non-negative number")


def _identifier(value: Any, name: str, *, max_length: int = 1024) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length or "\x00" in value:
        raise ValueError(f"{name} must be a non-empty bounded string")
    return value


def _lease_ttl(value: Any) -> None:
    _non_negative_number(value, "ttl_seconds")
    if value <= 0 or value > MAX_LEASE_SECONDS:
        raise ValueError("ttl_seconds is outside the supported lease range")


def _failure_code(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, ConnectionError):
        return "unavailable"
    return "release_failed"


def _release_confirmed(value: Any, expected_hash: str) -> bool:
    """Validate sidecar release receipts while allowing simple callback hooks."""

    if value is None or isinstance(value, bool):
        return value is not False
    if not isinstance(value, Mapping):
        raise IrohProtocolError("invalid blob release receipt", operation="gc.sweep")
    digest = value.get("blob_hash", value.get("hash", expected_hash))
    if digest != expected_hash:
        raise IrohIntegrityError("blob release receipt hash mismatch", operation="gc.sweep")
    released = value.get("released", value.get("deleted"))
    if not isinstance(released, bool):
        raise IrohProtocolError("invalid blob release receipt", operation="gc.sweep")
    return released


def _call_delete(callback: DeleteBlob, digest: str, operation_id: str) -> Any:
    """Call both the documented two-argument hook and simple one-arg adapters."""

    try:
        signature = inspect.signature(callback)
    except (TypeError, ValueError):
        return callback(digest, operation_id)
    positional = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
    ]
    has_varargs = any(
        parameter.kind == parameter.VAR_POSITIONAL for parameter in signature.parameters.values()
    )
    return (
        callback(digest, operation_id) if has_varargs or len(positional) >= 2 else callback(digest)
    )  # type: ignore[call-arg]


__all__ = [
    "DEFAULT_RETENTION_SECONDS",
    "GC_RECEIPT_KIND",
    "GC_RECEIPT_SCHEMA_VERSION",
    "GC_SCHEMA_VERSION",
    "GCPolicy",
    "GCCandidate",
    "GCMark",
    "GCFailure",
    "GCReceipt",
    "RepairReceipt",
    "Lease",
    "LeaseHandle",
    "QuotaStatus",
    "ReferenceTracker",
    "ReferenceIndex",
    "IrohGarbageCollector",
    "GarbageCollector",
    "verify_gc_receipt",
]
