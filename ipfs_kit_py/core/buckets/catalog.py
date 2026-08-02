"""Concurrent bucket catalog and durable-in-process compensation journal.

The immutable ``BucketCatalog`` contract in :mod:`.contracts` describes a
catalog *record*.  This module supplies the stateful ``BucketCatalog@1``
boundary used by the bucket service.  Its single lock makes a catalog compare
and swap and compensation-journal updates indivisible.  A service can therefore
leave a failed multi-store saga in a visible, recoverable state instead of
silently treating a partial effect as a commit.

The boundary is deliberately hermetic: callers can replace it with a durable
implementation later without changing bucket lifecycle semantics.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final

from ipfs_kit_py.core.buckets.contracts import (
    BucketCatalog as BucketCatalogRecord,
    BucketManifest,
)


CATALOG_CONTRACT_VERSION: Final[int] = 1
BUCKET_CATALOG_SCHEMA: Final[str] = "ipfs_kit_py/core/buckets/catalog/runtime@1"
BucketCatalog_V1: Final[str] = BUCKET_CATALOG_SCHEMA


class CatalogError(Exception):
    """Base class for runtime catalog failures."""


class CatalogConflictError(CatalogError):
    """The expected generation no longer names the current catalog state."""


class CatalogNotFoundError(CatalogError):
    """A requested catalog entry does not exist."""


class CatalogInvariantError(CatalogError):
    """The proposed entries do not form a valid contract catalog."""


class CompensationState(str, Enum):
    """Lifecycle of a recorded compensating action."""

    PENDING = "pending"
    RECOVERED = "recovered"


@dataclass(frozen=True)
class CompensationRecord:
    """A recoverable description of a partially applied multi-store action.

    ``detail`` contains the deterministic inverse-operation inputs required
    to resume the action after a service restart.  It deliberately contains
    immutable contracts and object bytes only--never backend instances or
    process-local callbacks--so a durable catalog adapter can persist it.
    """

    operation_id: str
    action: str
    bucket_key: str
    applied_backend_ids: tuple[str, ...] = ()
    pending_backend_ids: tuple[str, ...] = ()
    detail: Mapping[str, Any] = field(default_factory=dict)
    state: CompensationState = CompensationState.PENDING

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, str) or not self.operation_id:
            raise CatalogInvariantError("compensation operation_id must be non-empty")
        if not isinstance(self.action, str) or not self.action:
            raise CatalogInvariantError("compensation action must be non-empty")
        if not isinstance(self.bucket_key, str) or not self.bucket_key:
            raise CatalogInvariantError("compensation bucket_key must be non-empty")
        object.__setattr__(self, "applied_backend_ids", tuple(sorted(set(self.applied_backend_ids))))
        object.__setattr__(self, "pending_backend_ids", tuple(sorted(set(self.pending_backend_ids))))
        object.__setattr__(self, "detail", dict(self.detail))


@dataclass(frozen=True)
class CatalogSnapshot:
    """An immutable, generation-bound view of catalog contents."""

    catalog_id: str
    generation: int
    entries: tuple[BucketManifest, ...]
    pending_compensations: tuple[CompensationRecord, ...] = ()

    def resolve(self, backend_id: str, name_or_alias: str) -> BucketManifest:
        for entry in self.entries:
            if entry.identity.backend_id == backend_id and entry.identity.matches_name(name_or_alias):
                return entry
        raise CatalogNotFoundError(
            f"no bucket named {name_or_alias!r} exists on backend {backend_id!r}"
        )

    def as_contract(self) -> BucketCatalogRecord:
        """Project this state into the immutable public contract record."""

        # Contract records require a positive generation; a newly-created
        # runtime catalog is generation zero until its first successful CAS.
        return BucketCatalogRecord(
            catalog_id=self.catalog_id,
            generation=max(1, self.generation),
            entries=self.entries,
        )


class BucketCatalog:
    """In-memory, generation-CAS bucket catalog with a compensation journal."""

    SCHEMA: Final[str] = BUCKET_CATALOG_SCHEMA
    CONTRACT_VERSION: Final[int] = CATALOG_CONTRACT_VERSION

    def __init__(
        self,
        catalog_id: str = "bucket-catalog",
        entries: Iterable[BucketManifest] = (),
    ) -> None:
        initial = tuple(entries)
        try:
            record = BucketCatalogRecord(
                catalog_id=catalog_id,
                generation=1,
                entries=initial,
            )
        except Exception as exc:  # contracts retain the precise validation rules
            raise CatalogInvariantError(str(exc)) from exc
        self._catalog_id = record.catalog_id
        self._entries: dict[str, BucketManifest] = {
            entry.identity.catalog_key: entry for entry in record.entries
        }
        # Existing entries have already been published as one valid catalog
        # record.  Starting their runtime generation at one preserves that
        # fact and makes a caller's first CAS meaningful.
        self._generation = 1 if initial else 0
        self._compensations: dict[str, CompensationRecord] = {}
        self._lock = threading.RLock()

    @property
    def catalog_id(self) -> str:
        return self._catalog_id

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    @contextmanager
    def operation_lock(self) -> Iterator[None]:
        """Serialize a service operation against all users of this catalog.

        The individual catalog methods remain independently thread-safe.  A
        bucket service uses this broader lock while it performs the backend
        portion of a lifecycle mutation, which prevents another service that
        shares the catalog from writing through a deletion fence mid-flight.
        """

        with self._lock:
            yield

    def snapshot(self) -> CatalogSnapshot:
        with self._lock:
            return CatalogSnapshot(
                catalog_id=self._catalog_id,
                generation=self._generation,
                entries=self._ordered_entries(),
                pending_compensations=tuple(
                    sorted(
                        (item for item in self._compensations.values() if item.state is CompensationState.PENDING),
                        key=lambda item: item.operation_id,
                    )
                ),
            )

    def get(self, bucket_key: str) -> BucketManifest:
        with self._lock:
            try:
                return self._entries[bucket_key]
            except KeyError as exc:
                raise CatalogNotFoundError(f"bucket {bucket_key!r} does not exist") from exc

    def resolve(self, backend_id: str, name_or_alias: str) -> BucketManifest:
        return self.snapshot().resolve(backend_id, name_or_alias)

    def compare_and_swap(
        self,
        expected_generation: int,
        entries: Iterable[BucketManifest],
    ) -> CatalogSnapshot:
        """Atomically validate and publish a complete replacement entry set."""

        if not isinstance(expected_generation, int) or expected_generation < 0:
            raise CatalogConflictError("expected_generation must be a non-negative integer")
        candidate = tuple(entries)
        with self._lock:
            if expected_generation != self._generation:
                raise CatalogConflictError(
                    f"catalog generation changed (expected {expected_generation}, actual {self._generation})"
                )
            try:
                record = BucketCatalogRecord(
                    catalog_id=self._catalog_id,
                    generation=max(1, self._generation + 1),
                    entries=candidate,
                )
            except Exception as exc:
                raise CatalogInvariantError(str(exc)) from exc
            self._entries = {entry.identity.catalog_key: entry for entry in record.entries}
            self._generation += 1
            return self.snapshot()

    def record_compensation(self, record: CompensationRecord) -> CompensationRecord:
        """Persist a pending recovery record before reporting partial failure."""

        if not isinstance(record, CompensationRecord):
            raise CatalogInvariantError("record must be a CompensationRecord")
        with self._lock:
            existing = self._compensations.get(record.operation_id)
            if existing is not None and existing != record:
                raise CatalogInvariantError(
                    f"compensation operation {record.operation_id!r} was reused with different details"
                )
            self._compensations[record.operation_id] = record
            return record

    def compensation(self, operation_id: str) -> CompensationRecord:
        with self._lock:
            try:
                return self._compensations[operation_id]
            except KeyError as exc:
                raise CatalogNotFoundError(f"compensation {operation_id!r} does not exist") from exc

    def mark_recovered(self, operation_id: str) -> CompensationRecord:
        with self._lock:
            old = self.compensation(operation_id)
            recovered = CompensationRecord(
                operation_id=old.operation_id,
                action=old.action,
                bucket_key=old.bucket_key,
                applied_backend_ids=old.applied_backend_ids,
                pending_backend_ids=(),
                detail=old.detail,
                state=CompensationState.RECOVERED,
            )
            self._compensations[operation_id] = recovered
            return recovered

    def _ordered_entries(self) -> tuple[BucketManifest, ...]:
        return tuple(sorted(self._entries.values(), key=lambda item: item.identity.catalog_key))


# Less ambiguous alias for callers that need the immutable contract record too.
BucketCatalogContract = BucketCatalogRecord

__all__ = [
    "BUCKET_CATALOG_SCHEMA",
    "CATALOG_CONTRACT_VERSION",
    "BucketCatalog",
    "BucketCatalogContract",
    "BucketCatalog_V1",
    "CatalogConflictError",
    "CatalogError",
    "CatalogInvariantError",
    "CatalogNotFoundError",
    "CatalogSnapshot",
    "CompensationRecord",
    "CompensationState",
]
