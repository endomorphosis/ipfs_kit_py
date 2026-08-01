"""Safe replay of durable WAL transactions.

Recovery treats the write-ahead log as evidence, not as a command stream.  It
replays only mutations belonging to a fully committed transaction, maintains a
durable effect ledger, and never lets a checkpoint hide bytes that it does not
identify exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import inspect
import json
import os
from pathlib import Path
import tempfile
from typing import Callable, Iterable, Mapping, Sequence

from .checkpoint import CheckpointBundle, SealedSegmentIdentity
from .contracts import WALCorruptionDisposition, WALRecord, WALRecordKind
from .segments import SegmentRecovery, recover_segment


class WALRecoveryError(RuntimeError):
    """Base error for recovery failures that must not be ignored."""


class WALNonIdempotentHandlerError(WALRecoveryError):
    """A non-idempotent effect lacks a durable verified reconciliation path."""


class WALRecoveryCorruptionError(WALRecoveryError):
    """Two records or segment identities conflict irreconcilably."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _fsync_directory(directory: Path) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class EffectLedger:
    """A small durable ledger of externally completed WAL effects.

    A ledger is optional for intrinsically idempotent handlers, but is mandatory
    for non-idempotent handlers.  Updating it uses an atomic replace so a
    completed effect is never represented by a torn ledger entry.
    """

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._keys: set[str] = set()
        if self.path is not None and self.path.exists():
            try:
                decoded = json.loads(self.path.read_text("utf-8"))
                keys = decoded.get("keys", [])
                if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys):
                    raise ValueError("invalid key list")
                self._keys = set(keys)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise WALRecoveryCorruptionError("effect ledger is corrupt") from exc

    def contains(self, key: str) -> bool:
        return key in self._keys

    def mark(self, key: str) -> None:
        if not key:
            raise WALRecoveryError("effect ledger key is empty")
        if key in self._keys:
            return
        updated = self._keys | {key}
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary_name = tempfile.mkstemp(prefix="." + self.path.name + ".", dir=self.path.parent)
            temporary = Path(temporary_name)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(_canonical_bytes({"keys": sorted(updated)}))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
                _fsync_directory(self.path.parent)
            except BaseException:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
                raise
        self._keys = updated


@dataclass(frozen=True)
class RecoveryIssue:
    path: str
    valid_bytes: int
    error: str
    disposition: WALCorruptionDisposition


@dataclass(frozen=True)
class WALRecoveryReceipt:
    """Deterministic audit result for one replay attempt."""

    scanned_records: int
    committed_transactions: tuple[str, ...]
    replayed_record_ids: tuple[str, ...]
    skipped_effect_keys: tuple[str, ...]
    corruption_issues: tuple[RecoveryIssue, ...]

    @property
    def replayed_count(self) -> int:
        return len(self.replayed_record_ids)


def _record_identity(record: WALRecord) -> str:
    return record.record_key or record.operation_id or record.identity_key


class WALRecovery:
    """Recover one WAL generation from segment files and an optional checkpoint."""

    def __init__(
        self,
        segment_paths: Iterable[str | os.PathLike[str]] | str | os.PathLike[str],
        *,
        checkpoint: CheckpointBundle | None = None,
        corruption_disposition: WALCorruptionDisposition = WALCorruptionDisposition.BOUND_AND_REPORT,
        effect_ledger: EffectLedger | str | os.PathLike[str] | None = None,
    ) -> None:
        if isinstance(segment_paths, (str, os.PathLike)):
            candidate = Path(segment_paths)
            self.segment_paths = (
                tuple(sorted(candidate.glob("*.wal"))) if candidate.is_dir() else (candidate,)
            )
        else:
            self.segment_paths = tuple(Path(path) for path in segment_paths)
        self.checkpoint = checkpoint
        self.corruption_disposition = corruption_disposition
        self.effect_ledger = (
            effect_ledger
            if isinstance(effect_ledger, EffectLedger)
            else EffectLedger(effect_ledger)
        )

    @staticmethod
    def _identity(path: Path, recovered: SegmentRecovery) -> SealedSegmentIdentity | None:
        records = recovered.records
        if not records:
            return None
        segment_ids = {record.segment_id for record in records}
        generation_ids = {record.generation_id for record in records}
        if len(segment_ids) != 1 or "" in segment_ids or len(generation_ids) != 1:
            raise WALRecoveryCorruptionError(f"segment metadata conflicts in {path}")
        try:
            bytes_prefix = path.read_bytes()[: recovered.valid_bytes]
        except OSError as exc:
            raise WALRecoveryError(f"cannot read recovered prefix: {path}") from exc
        sequence_numbers = [record.sequence_number for record in records]
        return SealedSegmentIdentity(
            segment_id=next(iter(segment_ids)),
            generation_id=next(iter(generation_ids)),
            first_sequence=min(sequence_numbers),
            last_sequence=max(sequence_numbers),
            record_count=len(records),
            checksum=_sha256(bytes_prefix),
        )

    def scan(self) -> tuple[tuple[WALRecord, ...], tuple[RecoveryIssue, ...]]:
        """Read valid prefixes, reporting bounded corruption without losing them."""

        by_identity: dict[str, WALRecord] = {}
        issues: list[RecoveryIssue] = []
        for path in sorted(self.segment_paths, key=lambda item: str(item)):
            try:
                recovered = recover_segment(path, disposition=self.corruption_disposition)
            except Exception as exc:
                # FAIL_CLOSED from the segment layer remains fail-closed, with a
                # recovery-specific error type for callers.
                raise WALRecoveryError(f"unable to recover WAL segment {path}") from exc
            if recovered.tail_corrupt:
                issues.append(
                    RecoveryIssue(
                        str(path),
                        recovered.valid_bytes,
                        recovered.error or "invalid WAL tail",
                        self.corruption_disposition,
                    )
                )
            identity = self._identity(path, recovered)
            # A checkpoint can skip only a byte-for-byte matching sealed segment.
            # It cannot skip a new segment or a segment that gained an append.
            if (
                identity is not None
                and not recovered.tail_corrupt
                and self.checkpoint is not None
                and self.checkpoint.matches(identity)
            ):
                continue
            for record in recovered.records:
                prior = by_identity.get(record.identity_key)
                if prior is not None:
                    if prior.canonical_bytes() != record.canonical_bytes():
                        raise WALRecoveryCorruptionError(
                            f"conflicting duplicate WAL record {record.identity_key}"
                        )
                    continue
                by_identity[record.identity_key] = record
        records = tuple(
            sorted(
                by_identity.values(),
                key=lambda record: (
                    record.generation_id,
                    record.sequence_number,
                    record.transaction_id,
                    record.identity_key,
                ),
            )
        )
        return records, tuple(issues)

    @staticmethod
    def _committed_mutations(records: Sequence[WALRecord]) -> tuple[tuple[str, tuple[WALRecord, ...]], ...]:
        transactions: dict[str, list[WALRecord]] = {}
        for record in records:
            if record.transaction_id:
                transactions.setdefault(record.transaction_id, []).append(record)
        completed: list[tuple[str, tuple[WALRecord, ...]]] = []
        for transaction_id, transaction_records in transactions.items():
            ordered = sorted(transaction_records, key=lambda record: record.sequence_number)
            begins = [record for record in ordered if record.kind is WALRecordKind.BEGIN]
            # Replaying an ambiguous lifecycle is riskier than omitting it.  A
            # later COMMIT must never revive an ABORTed transaction.
            if len(begins) != 1:
                continue
            begin = begins[0]
            if any(
                record.kind is WALRecordKind.ABORT and record.sequence_number > begin.sequence_number
                for record in ordered
            ):
                continue
            commits = [
                record
                for record in ordered
                if record.kind is WALRecordKind.COMMIT
                and record.is_committed
                and record.is_durable
                and record.sequence_number > begin.sequence_number
            ]
            if not commits:
                continue
            commit = commits[-1]
            mutations = tuple(
                record
                for record in ordered
                if record.kind in {WALRecordKind.MUTATE, WALRecordKind.INTENT}
                and begin.sequence_number < record.sequence_number < commit.sequence_number
            )
            completed.append((transaction_id, mutations))
        return tuple(sorted(completed, key=lambda item: item[0]))

    @staticmethod
    def _call_reconciliation(
        reconciliation: Callable[..., bool], key: str, record: WALRecord
    ) -> bool:
        try:
            signature = inspect.signature(reconciliation)
        except (TypeError, ValueError):
            return bool(reconciliation(key, record))
        positional = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind
            in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
        ]
        if len(positional) <= 1:
            return bool(reconciliation(key))
        return bool(reconciliation(key, record))

    def recover(
        self,
        handler: Callable[[WALRecord], None],
        *,
        handler_idempotent: bool = True,
        effect_key: Callable[[WALRecord], str] | None = None,
        reconciliation: Callable[..., bool] | None = None,
    ) -> WALRecoveryReceipt:
        """Replay fully committed mutations exactly once as far as durable evidence permits.

        Non-idempotent handlers must supply both an explicit effect key and a
        reconciliation callback.  The callback is checked before and after the
        handler invocation; an unverified effect is never recorded as completed.
        """

        if not handler_idempotent and (effect_key is None or reconciliation is None):
            raise WALNonIdempotentHandlerError(
                "non-idempotent recovery requires effect_key and reconciliation"
            )
        records, issues = self.scan()
        committed = self._committed_mutations(records)
        replayed: list[str] = []
        skipped: list[str] = []
        for _, mutations in committed:
            for record in mutations:
                key = effect_key(record) if effect_key is not None else _record_identity(record)
                if not isinstance(key, str) or not key:
                    raise WALRecoveryError("recovery effect key is empty")
                if self.effect_ledger.contains(key):
                    skipped.append(key)
                    continue
                if not handler_idempotent:
                    assert reconciliation is not None
                    if self._call_reconciliation(reconciliation, key, record):
                        self.effect_ledger.mark(key)
                        skipped.append(key)
                        continue
                handler(record)
                if not handler_idempotent:
                    assert reconciliation is not None
                    if not self._call_reconciliation(reconciliation, key, record):
                        raise WALNonIdempotentHandlerError(
                            "non-idempotent effect was not verified after replay"
                        )
                self.effect_ledger.mark(key)
                replayed.append(record.identity_key)
        return WALRecoveryReceipt(
            scanned_records=len(records),
            committed_transactions=tuple(transaction_id for transaction_id, _ in committed),
            replayed_record_ids=tuple(replayed),
            skipped_effect_keys=tuple(skipped),
            corruption_issues=issues,
        )


def recover_wal(
    segment_paths: Iterable[str | os.PathLike[str]] | str | os.PathLike[str],
    handler: Callable[[WALRecord], None],
    **kwargs: object,
) -> WALRecoveryReceipt:
    """Convenience entry point for one-shot WAL recovery."""

    recovery_keys = {
        "checkpoint",
        "corruption_disposition",
        "effect_ledger",
    }
    recovery_kwargs = {key: value for key, value in kwargs.items() if key in recovery_keys}
    handler_kwargs = {key: value for key, value in kwargs.items() if key not in recovery_keys}
    return WALRecovery(segment_paths, **recovery_kwargs).recover(handler, **handler_kwargs)
