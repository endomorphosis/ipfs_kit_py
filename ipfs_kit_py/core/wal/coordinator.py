"""Durable transaction coordination on top of the canonical WAL writer.

The writer is deliberately a record append primitive.  This module supplies the
small amount of protocol that callers need for an external effect: intent is
durable before the effect runs, commit is durable before success is returned,
and an uncommitted effect is compensated during recovery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping
import json
import os
import threading
import uuid

from .contracts import WALAcknowledgementMode, WALRecordKind
from .writer import WALWriter

# Shared hot-path settings fingerprint — optimization must never drift these
# durability / consistency contracts (KITA-044).
try:
    from ipfs_kit_py.core.performance import (
        default_reference_settings,
        settings_fingerprint as _settings_fingerprint,
    )
except Exception:  # pragma: no cover - fail open only if performance surface absent
    default_reference_settings = None  # type: ignore[assignment]
    _settings_fingerprint = None  # type: ignore[assignment]


class WALTransactionError(RuntimeError):
    """A transaction could not reach the requested durable boundary."""


class WALTransactionCrash(RuntimeError):
    """Raised by an optional test crash injector at a named protocol boundary."""


@dataclass(frozen=True, slots=True)
class TransactionResult:
    transaction_id: str
    committed: bool
    effect_id: str


@dataclass(slots=True)
class _Transaction:
    transaction_id: str
    intents: list[dict[str, Any]] = field(default_factory=list)
    compensations: list[Callable[[], Any]] = field(default_factory=list)
    committed: bool = False
    aborting: bool = False


class WALTransactionCoordinator:
    """Coordinates durable intent/effect/decision transactions.

    ``effect`` and ``compensate`` are application supplied and may be simple
    callables.  A false return value is considered a failed effect or failed
    compensation; ``None`` is accepted because many Python mutation APIs do
    not return a value.  Recovery handlers receive the durable intent and its
    stable effect ID, allowing backend implementations to use the ID as an
    idempotency key.
    """

    CRASH_BOUNDARIES = (
        "before_begin", "after_begin", "before_intent", "after_intent",
        "before_effect", "after_effect", "before_commit", "after_commit",
        "before_abort", "after_abort",
    )

    def __init__(
        self,
        directory: str | Path,
        *,
        writer: WALWriter | None = None,
        crash_injector: Callable[..., Any] | None = None,
    ) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._writer = writer or WALWriter(self.directory / "records")
        self._owns_writer = writer is None
        self._decision_path = self.directory / "transaction-decisions.jsonl"
        self._replay_path = self.directory / "transaction-replay.jsonl"
        self._crash_injector = crash_injector
        self._lock = threading.RLock()
        self._transactions: dict[str, _Transaction] = {}
        # Cache the settings fingerprint once so hot paths do not re-hash.
        if default_reference_settings is not None and _settings_fingerprint is not None:
            self._settings_fingerprint = _settings_fingerprint(default_reference_settings())
        else:
            self._settings_fingerprint = ""
        # Keep a reusable decision-file handle open for ordered appends.  Each
        # write is still flushed + fsynced before the call returns so fsync
        # ordering and crash recovery semantics remain identical.
        self._decision_handle: Any = None

    @property
    def settings_fingerprint(self) -> str:
        """Pinned durability/consistency settings identity (KITA-044)."""
        return self._settings_fingerprint

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        try:
            descriptor = os.open(path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _decision_file(self) -> Any:
        if self._decision_handle is None or self._decision_handle.closed:
            self._decision_handle = open(self._decision_path, "a", encoding="utf-8")
        return self._decision_handle

    def _append_json(self, path: Path, value: Mapping[str, Any]) -> None:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
        if path == self._decision_path:
            handle = self._decision_file()
            handle.write(encoded + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            self._fsync_directory(path.parent)
            return
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._fsync_directory(path.parent)

    def _boundary(self, name: str, transaction_id: str) -> None:
        if self._crash_injector is None:
            return
        try:
            self._crash_injector(name, transaction_id)
        except TypeError:
            self._crash_injector(name)

    def _marker(self, kind: WALRecordKind, transaction_id: str, *, effect_id: str = "") -> None:
        result = self._writer.append(
            kind,
            acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC_PARENT,
            transaction_id=transaction_id,
            record_key=f"transaction:{transaction_id}:{kind.value}:{effect_id or uuid.uuid4().hex}",
            operation_id=effect_id,
        )
        if not result.durable:
            raise WALTransactionError(
                f"{kind.value} for transaction {transaction_id} was not durably acknowledged"
            )

    @staticmethod
    def _normalise_intent(intent: Mapping[str, Any]) -> dict[str, Any]:
        try:
            encoded = json.dumps(dict(intent), sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise WALTransactionError("transaction intent must be JSON serialisable") from exc
        return json.loads(encoded)

    def begin(self, transaction_id: str | None = None) -> str:
        transaction_id = transaction_id or str(uuid.uuid4())
        with self._lock:
            if transaction_id in self._transactions:
                raise WALTransactionError(f"transaction already active: {transaction_id}")
            self._boundary("before_begin", transaction_id)
            self._marker(WALRecordKind.BEGIN, transaction_id)
            self._append_json(self._decision_path, {
                "kind": "begin", "transaction_id": transaction_id,
            })
            self._transactions[transaction_id] = _Transaction(transaction_id)
            self._boundary("after_begin", transaction_id)
            return transaction_id

    def record_intent(
        self, transaction_id: str, intent: Mapping[str, Any], *, effect_id: str | None = None
    ) -> str:
        with self._lock:
            transaction = self._transactions.get(transaction_id)
            if transaction is None or transaction.committed or transaction.aborting:
                raise WALTransactionError(f"transaction is not active: {transaction_id}")
            durable_intent = self._normalise_intent(intent)
            effect_id = effect_id or str(uuid.uuid4())
            self._boundary("before_intent", transaction_id)
            self._marker(WALRecordKind.INTENT, transaction_id, effect_id=effect_id)
            entry = {"kind": "intent", "transaction_id": transaction_id,
                     "effect_id": effect_id, "intent": durable_intent}
            self._append_json(self._decision_path, entry)
            transaction.intents.append(entry)
            self._boundary("after_intent", transaction_id)
            return effect_id

    def perform(
        self,
        transaction_id: str,
        intent: Mapping[str, Any],
        effect: Callable[[], Any],
        compensate: Callable[[], Any],
        *,
        effect_id: str | None = None,
    ) -> str:
        effect_id = self.record_intent(transaction_id, intent, effect_id=effect_id)
        self._boundary("before_effect", transaction_id)
        result = effect()
        if result is False:
            raise WALTransactionError(f"effect {effect_id} reported failure")
        with self._lock:
            transaction = self._transactions[transaction_id]
            transaction.compensations.append(compensate)
        self._boundary("after_effect", transaction_id)
        return effect_id

    def commit(self, transaction_id: str) -> TransactionResult:
        with self._lock:
            transaction = self._transactions.get(transaction_id)
            if transaction is None:
                raise WALTransactionError(f"transaction is not active: {transaction_id}")
            if transaction.committed:
                raise WALTransactionError(f"transaction already committed: {transaction_id}")
            self._boundary("before_commit", transaction_id)
            # A pending decision lets recovery distinguish an interrupted commit
            # from a completed one without ever treating a begin marker as commit.
            self._append_json(self._decision_path, {
                "kind": "commit_pending", "transaction_id": transaction_id,
            })
            self._marker(WALRecordKind.COMMIT, transaction_id)
            transaction.committed = True
            self._append_json(self._decision_path, {
                "kind": "commit", "transaction_id": transaction_id,
            })
            self._boundary("after_commit", transaction_id)
            self._transactions.pop(transaction_id, None)
            effect_id = transaction.intents[-1]["effect_id"] if transaction.intents else ""
            return TransactionResult(transaction_id, True, effect_id)

    def abort(self, transaction_id: str) -> bool:
        with self._lock:
            transaction = self._transactions.get(transaction_id)
            if transaction is None:
                return False
            if transaction.committed:
                raise WALTransactionError("refusing to abort a committed transaction")
            transaction.aborting = True
            self._boundary("before_abort", transaction_id)
            for compensate in reversed(transaction.compensations):
                result = compensate()
                if result is False:
                    transaction.aborting = False
                    raise WALTransactionError("rollback compensation reported failure")
            self._marker(WALRecordKind.ABORT, transaction_id)
            self._append_json(self._decision_path, {
                "kind": "abort", "transaction_id": transaction_id,
            })
            self._boundary("after_abort", transaction_id)
            self._transactions.pop(transaction_id, None)
            return True

    def execute(
        self,
        intent: Mapping[str, Any],
        effect: Callable[[], Any],
        compensate: Callable[[], Any],
        *,
        transaction_id: str | None = None,
        effect_id: str | None = None,
    ) -> TransactionResult:
        transaction_id = self.begin(transaction_id)
        try:
            effect_id = self.perform(transaction_id, intent, effect, compensate, effect_id=effect_id)
            result = self.commit(transaction_id)
            return TransactionResult(result.transaction_id, result.committed, effect_id)
        except WALTransactionCrash:
            raise
        except Exception:
            # If the commit marker has been written, abort deliberately refuses
            # to compensate a potentially committed external effect.
            transaction = self._transactions.get(transaction_id)
            if transaction is not None and not transaction.committed:
                self.abort(transaction_id)
            raise

    def _decisions(self) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
        transactions: dict[str, list[dict[str, Any]]] = {}
        replayed: set[str] = set()
        for path, is_replay in ((self._decision_path, False), (self._replay_path, True)):
            if not path.exists():
                continue
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        # A torn final append was never acknowledged.
                        continue
                    if is_replay:
                        if entry.get("effect_id"):
                            replayed.add(entry["effect_id"])
                    elif entry.get("transaction_id"):
                        transactions.setdefault(entry["transaction_id"], []).append(entry)
        return transactions, replayed

    def recover(
        self,
        replay_effect: Callable[[Mapping[str, Any], str], Any] | None = None,
        rollback_effect: Callable[[Mapping[str, Any], str], Any] | None = None,
    ) -> dict[str, int]:
        """Replay commits and compensate every durable, non-committed intent.

        Each durable replay acknowledgement is recorded before a subsequent
        recovery invocation returns, so repeated recovery calls never invoke a
        completed handler twice.
        """
        transactions, replayed = self._decisions()
        replay_count = rollback_count = 0
        for transaction_id, entries in transactions.items():
            committed = any(entry.get("kind") == "commit" for entry in entries)
            aborted = any(entry.get("kind") == "abort" for entry in entries)
            intents = [entry for entry in entries if entry.get("kind") == "intent"]
            if committed:
                handler = replay_effect
                action = "replayed"
            elif not aborted:
                handler = rollback_effect
                action = "rolled_back"
            else:
                continue
            if handler is None:
                continue
            for entry in intents:
                effect_id = entry["effect_id"]
                ledger_id = f"{action}:{effect_id}"
                if ledger_id in replayed:
                    continue
                result = handler(entry["intent"], effect_id)
                if result is False:
                    raise WALTransactionError(f"recovery {action} for {effect_id} reported failure")
                self._append_json(self._replay_path, {"effect_id": ledger_id})
                replayed.add(ledger_id)
                if committed:
                    replay_count += 1
                else:
                    rollback_count += 1
        return {"replayed": replay_count, "rolled_back": rollback_count}

    def close(self) -> None:
        if self._decision_handle is not None:
            try:
                self._decision_handle.close()
            except Exception:
                pass
            self._decision_handle = None
        if self._owns_writer:
            self._writer.close()

    def __enter__(self) -> "WALTransactionCoordinator":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


TransactionCoordinator = WALTransactionCoordinator
WALCoordinator = WALTransactionCoordinator
