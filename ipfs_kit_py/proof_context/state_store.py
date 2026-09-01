"""Hermetic kit v0.1 state/receipt/proof-forest port with ContextPack storage.

Kit proves exact bytes and the durable current root only.  It cannot decide
semantics, freshness, reuse, execution, or promotion.  Candidate ContextPack
storage is separate from current-root publication.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final

from ipfs_kit_py.proof_context.artifacts import (
    ArtifactIdentityError,
    cid_for_bytes,
    get_bytes,
    put_bytes,
)
from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    ArtifactReference,
    CurrentSealPointer,
    SealTransitionPhase,
    SealTransitionRecord,
    SealTransitionState,
)
from ipfs_kit_py.proof_seal_store.local_store import HermeticProofSealStore
from ipfs_kit_py.proof_seal_store.pointer import (
    CurrentSealRepository,
    PointerCasRejected,
)
from ipfs_kit_py.proof_seal_store.recovery import RecoveryReport, recover_seal_transitions
from ipfs_kit_py.proof_seal_store.wal import PHASE_ORDER, SealTransitionWal

PORT_SCHEMA = "ipfs-kit.proof-context.v0.1"
PORT_INTERFACE = "KitProofContextStateStore@0.1"

CONTEXT_PACK_NAMESPACE: Final[str] = "ContextPack"
CONTEXT_PACK_SCHEMA: Final[str] = "ipfs-kit.proof-context.context-pack-store@1"
CONTEXT_PACK_INTERFACE: Final[str] = "KitContextPackStore@1"
CONTEXT_PACK_VECTOR_SCHEMA: Final[str] = (
    "ipfs-kit.proof-context.context-pack-store-vectors@1"
)
CONTEXT_PACK_CANDIDATE_INDEX_SCHEMA: Final[str] = (
    "ipfs-kit.proof-context.context-pack-candidate-index@1"
)
CONTEXT_PACK_STATE_SCHEMA: Final[str] = "ipfs-kit.proof-context.context-pack-state@1"
CONTEXT_PACK_VECTOR_RESOURCE: Final[str] = "context_pack_contract_vectors.json"
CONTEXT_PACK_BRANCH: Final[str] = "current"

CONTEXT_PACK_RECORD_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema",
        "interface",
        "namespace",
        "role",
        "cid",
        "kind",
        "generation",
        "parent_cid",
        "cache_key",
        "byte_length",
    }
)
CONTEXT_PACK_ROLES: Final[frozenset[str]] = frozenset(
    {"candidate", "admitted", "current"}
)
CONTEXT_PACK_ALLOWED_KINDS: Final[frozenset[str]] = frozenset(
    {
        ArtifactKind.CHECKPOINT_SEAL.value,
        ArtifactKind.DELTA_SEAL.value,
        ArtifactKind.PROOF_MANIFEST.value,
        ArtifactKind.PROOF_RECEIPT.value,
        ArtifactKind.MERKLE_NODE.value,
        ArtifactKind.TOMBSTONE.value,
        ArtifactKind.INVALIDATION_RECORD.value,
    }
)
CONTEXT_PACK_SEAL_KINDS: Final[frozenset[str]] = frozenset(
    {
        ArtifactKind.CHECKPOINT_SEAL.value,
        ArtifactKind.DELTA_SEAL.value,
    }
)
CONTEXT_PACK_FORBIDDEN_KINDS: Final[frozenset[str]] = frozenset(
    {
        ArtifactKind.PROOF_OBJECT.value,
        "proving_key",
        "witness",
        "private_witness",
        "witness_material",
    }
)

_CID_RE: Final[re.Pattern[str]] = re.compile(r"^b[a-z2-7]{20,}$")
_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()
_MAX_INDEX_BYTES = 256 * 1024


class UnavailableTransportError(RuntimeError):
    """Optional IPFS transport is not admitted as a passed capability."""


class ContextPackStoreError(RuntimeError):
    """ContextPack durable-store operation failed closed."""

    reason = "invalid"


class StaleContextPackCasError(ContextPackStoreError):
    """Expected parent, generation, or current root no longer matches."""

    reason = "stale"


class UnknownFieldError(ContextPackStoreError):
    """Closed ContextPack storage record contained an unknown field."""

    reason = "unknown_field"


class ContextPackMasqueradeError(ContextPackStoreError):
    """A proof object or forbidden kind was presented as a ContextPack."""

    reason = "masquerade"


class ContextPackRetentionError(ContextPackStoreError):
    """Retention refused to drop the current root or revive a tombstone."""

    reason = "retention"


def _thread_lock(root: Path) -> threading.RLock:
    key = os.path.abspath(os.fspath(root))
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    data = _canonical_json_bytes(payload)
    if len(data) > _MAX_INDEX_BYTES:
        raise ContextPackStoreError("ContextPack index exceeds byte budget")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = -1
    temporary_name = ""
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            written = stream.write(data)
            if written != len(data):
                raise ContextPackStoreError("short write of ContextPack index")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
        temporary_name = ""
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
        raise


def _require_cid(value: Any, field_name: str) -> str:
    if type(value) is not str or not value:
        raise ContextPackStoreError(f"{field_name} must be a non-empty CIDv1")
    if value.startswith("sha256:") or value.startswith("Qm"):
        raise ContextPackStoreError(f"{field_name} rejects pseudo-CID {value!r}")
    if not _CID_RE.fullmatch(value):
        raise ContextPackStoreError(f"{field_name} must be CIDv1 base32")
    return value


def _optional_cid(value: Any, field_name: str) -> str:
    if value is None or value == "":
        return ""
    return _require_cid(value, field_name)


def load_context_pack_contract_vectors() -> dict[str, Any]:
    """Load installed ContextPack store contract vectors as package data."""

    from importlib.resources import files

    resource = files("ipfs_kit_py.proof_context").joinpath(CONTEXT_PACK_VECTOR_RESOURCE)
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ContextPackStoreError("contract vectors must be a JSON object")
    extra = sorted(set(payload) - _VECTOR_DOCUMENT_FIELDS)
    if extra:
        raise UnknownFieldError(f"unknown field: {extra[0]}")
    if payload.get("schema") != CONTEXT_PACK_VECTOR_SCHEMA:
        raise ContextPackStoreError("contract vector schema mismatch")
    if payload.get("namespace") != CONTEXT_PACK_NAMESPACE:
        raise ContextPackStoreError("contract vector namespace must be ContextPack")
    return payload


_VECTOR_DOCUMENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema",
        "interface",
        "namespace",
        "closed_fields",
        "allowed_kinds",
        "forbidden_kinds",
        "roles",
        "cases",
    }
)
_VECTOR_CASE_FIELDS: Final[frozenset[str]] = frozenset(
    {"id", "expect", "reason", "record"}
)


def validate_context_pack_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Admit a closed ContextPack storage record; unknown fields fail closed."""

    if not isinstance(payload, Mapping) or isinstance(payload, (str, bytes)):
        raise ContextPackStoreError("ContextPack record must be an object")
    extra = sorted(set(payload) - CONTEXT_PACK_RECORD_FIELDS)
    if extra:
        raise UnknownFieldError(f"unknown field: {extra[0]}")
    required = ("schema", "interface", "namespace", "role", "kind")
    missing = [field for field in required if field not in payload]
    if missing:
        raise ContextPackStoreError(f"omitted ContextPack field: {missing[0]}")
    if payload.get("schema") != CONTEXT_PACK_SCHEMA:
        raise ContextPackStoreError("ContextPack record schema mismatch")
    if payload.get("interface") != CONTEXT_PACK_INTERFACE:
        raise ContextPackStoreError("ContextPack record interface mismatch")
    if payload.get("namespace") != CONTEXT_PACK_NAMESPACE:
        raise ContextPackStoreError("namespace must be ContextPack")
    role = payload.get("role")
    if role not in CONTEXT_PACK_ROLES:
        raise ContextPackStoreError(f"role {role!r} is outside the closed set")
    kind = payload.get("kind")
    if type(kind) is not str:
        raise ContextPackStoreError("kind must be a string")
    if kind in CONTEXT_PACK_FORBIDDEN_KINDS:
        raise ContextPackMasqueradeError(
            f"proof-object masquerade rejected for kind {kind!r}"
        )
    if kind not in CONTEXT_PACK_ALLOWED_KINDS:
        raise ContextPackMasqueradeError(f"kind {kind!r} is not a ContextPack kind")
    if role == "current" and kind not in CONTEXT_PACK_SEAL_KINDS:
        raise ContextPackMasqueradeError(
            "current-root ContextPack records must be checkpoint_seal or delta_seal"
        )
    cid = payload.get("cid")
    if cid is not None:
        _require_cid(cid, "cid")
    parent_cid = payload.get("parent_cid", "")
    if parent_cid not in (None, ""):
        _optional_cid(parent_cid, "parent_cid")
    generation = payload.get("generation", 0)
    if isinstance(generation, bool) or type(generation) is not int or generation < 0:
        raise ContextPackStoreError("generation must be a non-negative integer")
    cache_key = payload.get("cache_key", "")
    if cache_key is not None and type(cache_key) is not str:
        raise ContextPackStoreError("cache_key must be a string")
    byte_length = payload.get("byte_length", 0)
    if isinstance(byte_length, bool) or type(byte_length) is not int or byte_length < 0:
        raise ContextPackStoreError("byte_length must be a non-negative integer")
    return dict(payload)


def apply_context_pack_contract_vectors(
    vectors: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Evaluate compact contract-vector recipes without bulk golden dumps."""

    document = dict(vectors or load_context_pack_contract_vectors())
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ContextPackStoreError("contract vectors require a non-empty cases list")
    results: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, Mapping):
            raise ContextPackStoreError("contract vector case must be an object")
        extra = sorted(set(case) - _VECTOR_CASE_FIELDS)
        if extra:
            raise UnknownFieldError(f"unknown field: {extra[0]}")
        case_id = case.get("id")
        expect = case.get("expect")
        record = case.get("record")
        if type(case_id) is not str or not case_id:
            raise ContextPackStoreError("contract vector case id is required")
        if expect not in {"accept", "reject"}:
            raise ContextPackStoreError(f"case {case_id!r} expect must be accept or reject")
        if not isinstance(record, Mapping):
            raise ContextPackStoreError(f"case {case_id!r} record must be an object")
        try:
            validate_context_pack_record(record)
        except (UnknownFieldError, ContextPackMasqueradeError, ContextPackStoreError) as exc:
            if expect != "reject":
                raise ContextPackStoreError(
                    f"case {case_id!r} should accept but failed: {exc}"
                ) from exc
            reason = getattr(exc, "reason", "invalid")
            expected_reason = case.get("reason")
            if expected_reason and expected_reason != reason:
                raise ContextPackStoreError(
                    f"case {case_id!r} rejected for {reason!r}, expected {expected_reason!r}"
                ) from exc
            results.append({"id": case_id, "status": "reject", "reason": reason})
            continue
        if expect != "accept":
            raise ContextPackStoreError(f"case {case_id!r} should reject but was admitted")
        results.append({"id": case_id, "status": "accept"})
    return tuple(results)


class ContextPackStore:
    """Explicit ContextPack namespace over hermetic bytes, CAS, WAL, and recovery."""

    namespace = CONTEXT_PACK_NAMESPACE
    schema = CONTEXT_PACK_SCHEMA
    interface = CONTEXT_PACK_INTERFACE
    ipfs_required = False

    def __init__(
        self,
        root: str | Path,
        *,
        hermetic_store: HermeticProofSealStore | None = None,
        crash_injector: Callable[..., Any] | None = None,
        enable_ipfs: bool = False,
    ) -> None:
        if enable_ipfs:
            raise UnavailableTransportError(
                "optional IPFS transport is explicit and unavailable is not success"
            )
        self._root = Path(root)
        self._store = hermetic_store or HermeticProofSealStore(self._root)
        self._pointers = CurrentSealRepository(self._root)
        self._wal = SealTransitionWal(self._root, crash_injector=crash_injector)
        self._lock = _thread_lock(self._root)
        self._crash_injector = crash_injector

    @property
    def root(self) -> Path:
        return self._root

    @property
    def hermetic_store(self) -> HermeticProofSealStore:
        return self._store

    def close(self) -> None:
        self._wal.close()

    def cid_for(self, data: bytes) -> str:
        return cid_for_bytes(data)

    def put_verified_bytes(
        self,
        data: bytes,
        *,
        kind: ArtifactKind | str = ArtifactKind.CHECKPOINT_SEAL,
        claimed_cid: str | None = None,
    ) -> ArtifactReference:
        closed_kind = self._require_pack_kind(kind, role="admitted")
        reference = put_bytes(
            self._store, data, kind=closed_kind, claimed_cid=claimed_cid
        )
        if reference.cid != cid_for_bytes(data):
            raise ArtifactIdentityError("stored CID does not equal recomputed CID")
        return reference

    def get_immutable(self, reference: ArtifactReference) -> bytes:
        data = get_bytes(self._store, reference)
        actual = cid_for_bytes(data)
        if actual != reference.cid:
            raise ArtifactIdentityError("stored bytes do not match reference CID")
        return data

    def put_candidate(
        self,
        data: bytes,
        *,
        cache_key: str | None = None,
        kind: ArtifactKind | str | None = None,
        claimed_cid: str | None = None,
        parent_cid: str = "",
        generation: int = 0,
        branch_id: str = CONTEXT_PACK_BRANCH,
    ) -> ArtifactReference:
        """Store verified candidate bytes without publishing the current root."""

        if kind is None or kind == "":
            closed_kind = (
                ArtifactKind.DELTA_SEAL if parent_cid else ArtifactKind.CHECKPOINT_SEAL
            )
        else:
            closed_kind = self._require_pack_kind(kind, role="candidate")
        reference = self.put_verified_bytes(
            data, kind=closed_kind, claimed_cid=claimed_cid
        )
        key = cache_key or reference.cid
        if type(key) is not str or not key.strip():
            raise ContextPackStoreError("cache_key must be a non-empty string")
        record = validate_context_pack_record(
            {
                "schema": CONTEXT_PACK_SCHEMA,
                "interface": CONTEXT_PACK_INTERFACE,
                "namespace": CONTEXT_PACK_NAMESPACE,
                "role": "candidate",
                "cid": reference.cid,
                "kind": closed_kind.value,
                "generation": generation,
                "parent_cid": parent_cid or "",
                "cache_key": key,
                "byte_length": len(data),
            }
        )
        with self._lock:
            catalog = self._load_candidate_index()
            catalog["entries"][key] = record
            catalog["branch_id"] = branch_id
            self._write_candidate_index(catalog)
        return reference

    def get_candidate(self, cache_key: str) -> dict[str, Any] | None:
        if type(cache_key) is not str or not cache_key:
            raise ContextPackStoreError("cache_key must be a non-empty string")
        with self._lock:
            entry = self._load_candidate_index()["entries"].get(cache_key)
        if entry is None:
            return None
        if entry.get("tombstoned") is True:
            return None
        return dict(entry)

    def list_candidates(self, *, include_tombstoned: bool = False) -> tuple[dict[str, Any], ...]:
        with self._lock:
            entries = self._load_candidate_index()["entries"]
        visible = []
        for record in entries.values():
            if record.get("tombstoned") is True and not include_tombstoned:
                continue
            visible.append(dict(record))
        return tuple(visible)

    def current_root(self, branch_id: str = CONTEXT_PACK_BRANCH) -> CurrentSealPointer | None:
        return self._pointers.get_current_seal(CONTEXT_PACK_NAMESPACE, branch_id)

    def compare_and_swap_current_root(
        self,
        *,
        new_cid: str,
        expected_parent_cid: str | None = None,
        generation: int | None = None,
        kind: ArtifactKind | str = ArtifactKind.CHECKPOINT_SEAL,
        branch_id: str = CONTEXT_PACK_BRANCH,
        transition_id: str | None = None,
    ) -> CurrentSealPointer:
        """Publish an already-admitted seal as current via WAL-backed CAS."""

        closed_kind = self._require_pack_kind(kind, role="current")
        if closed_kind.value not in CONTEXT_PACK_SEAL_KINDS:
            raise ContextPackMasqueradeError(
                "current-root CAS requires checkpoint_seal or delta_seal"
            )
        admitted = ArtifactReference(cid=_require_cid(new_cid, "new_cid"), kind=closed_kind)
        if not self._store.contains(admitted):
            raise ContextPackStoreError("current-root CAS requires admitted verified bytes")
        parent = _optional_cid(expected_parent_cid or "", "expected_parent_cid")
        with self._lock:
            return self._publish_locked(
                admitted=admitted,
                parent=parent,
                generation=generation,
                branch_id=branch_id,
                transition_id=transition_id,
            )

    def publish_candidate(
        self,
        cache_key: str,
        *,
        expected_parent_cid: str | None = None,
        generation: int | None = None,
        branch_id: str = CONTEXT_PACK_BRANCH,
        transition_id: str | None = None,
    ) -> CurrentSealPointer:
        entry = self.get_candidate(cache_key)
        if entry is None:
            raise ContextPackRetentionError(
                f"candidate {cache_key!r} is missing or tombstoned"
            )
        return self.compare_and_swap_current_root(
            new_cid=entry["cid"],
            expected_parent_cid=expected_parent_cid
            if expected_parent_cid is not None
            else entry.get("parent_cid") or "",
            generation=generation if generation is not None else entry.get("generation", 0),
            kind=entry["kind"],
            branch_id=branch_id,
            transition_id=transition_id,
        )

    def recover(self) -> RecoveryReport:
        """Deterministically recover ContextPack WAL/CAS state; never diverges."""

        report = recover_seal_transitions(
            self._root, wal=self._wal, store=self._store, pointers=self._pointers
        )
        self._complete_open_publications()
        return recover_seal_transitions(
            self._root, wal=self._wal, store=self._store, pointers=self._pointers
        )

    def apply_retention(
        self,
        *,
        keep_current: bool = True,
        branch_id: str = CONTEXT_PACK_BRANCH,
    ) -> dict[str, Any]:
        """Tombstone non-current candidates.  The current root is never dropped."""

        if keep_current is not True:
            raise ContextPackRetentionError("current-root retention cannot be disabled")
        current = self.current_root(branch_id)
        current_cid = current.seal_cid if current is not None else None
        tombstoned: list[str] = []
        retained: list[str] = []
        with self._lock:
            catalog = self._load_candidate_index()
            for key, entry in catalog["entries"].items():
                cid = entry.get("cid")
                if current_cid is not None and cid == current_cid:
                    retained.append(key)
                    continue
                if entry.get("tombstoned") is True:
                    tombstoned.append(key)
                    continue
                entry = dict(entry)
                extra = sorted(
                    set(entry)
                    - CONTEXT_PACK_RECORD_FIELDS
                    - {"tombstoned", "tombstone_cid"}
                )
                if extra:
                    raise UnknownFieldError(f"unknown field: {extra[0]}")
                entry["tombstoned"] = True
                catalog["entries"][key] = entry
                tombstone = self._store.put_immutable(
                    ArtifactKind.TOMBSTONE,
                    _canonical_json_bytes(
                        {
                            "schema": CONTEXT_PACK_SCHEMA,
                            "interface": CONTEXT_PACK_INTERFACE,
                            "namespace": CONTEXT_PACK_NAMESPACE,
                            "role": "admitted",
                            "cid": cid,
                            "kind": ArtifactKind.TOMBSTONE.value,
                            "generation": entry.get("generation", 0),
                            "parent_cid": entry.get("parent_cid", ""),
                            "cache_key": key,
                            "byte_length": 0,
                        }
                    ),
                )
                entry["tombstone_cid"] = tombstone.cid
                catalog["entries"][key] = entry
                tombstoned.append(key)
            self._write_candidate_index(catalog)
        if current is not None and current_cid not in {
            entry.get("cid")
            for entry in self._load_candidate_index()["entries"].values()
            if entry.get("cid") == current_cid
        }:
            # Current root bytes remain admitted even when no candidate remains.
            pass
        if current is not None and self.current_root(branch_id) != current:
            raise ContextPackRetentionError("retention mutated the current root")
        return {
            "namespace": CONTEXT_PACK_NAMESPACE,
            "current_cid": current_cid,
            "retained": retained,
            "tombstoned": tombstoned,
        }

    def put_verification_generation(self, generation: int) -> int:
        if isinstance(generation, bool) or type(generation) is not int or generation < 0:
            raise ContextPackStoreError("generation must be a non-negative integer")
        with self._lock:
            state = self._load_state()
            current = int(state.get("verification_generation", 0))
            if generation != current and generation != current + 1:
                raise StaleContextPackCasError(
                    f"ABA/stale generation {generation} vs expected {current}"
                )
            state["verification_generation"] = generation
            self._write_state(state)
            return generation

    def verification_generation(self) -> int:
        with self._lock:
            return int(self._load_state().get("verification_generation", 0))

    def _require_pack_kind(
        self, kind: ArtifactKind | str, *, role: str
    ) -> ArtifactKind:
        label = kind.value if isinstance(kind, ArtifactKind) else kind
        if type(label) is not str:
            raise ContextPackStoreError("kind must be a string")
        if label in CONTEXT_PACK_FORBIDDEN_KINDS:
            raise ContextPackMasqueradeError(
                f"proof-object masquerade rejected for kind {label!r}"
            )
        try:
            closed = ArtifactKind(label) if not isinstance(kind, ArtifactKind) else kind
        except ValueError as exc:
            raise ContextPackMasqueradeError(f"kind {label!r} is not a ContextPack kind") from exc
        if closed.value not in CONTEXT_PACK_ALLOWED_KINDS:
            raise ContextPackMasqueradeError(
                f"kind {closed.value!r} is not a ContextPack kind"
            )
        if role == "current" and closed.value not in CONTEXT_PACK_SEAL_KINDS:
            raise ContextPackMasqueradeError(
                "current-root ContextPack records must be checkpoint_seal or delta_seal"
            )
        return closed

    def _candidate_index_path(self) -> Path:
        return self._root / "context_pack" / "candidates.json"

    def _state_path(self) -> Path:
        return self._root / "context_pack" / "state.json"

    def _load_candidate_index(self) -> dict[str, Any]:
        path = self._candidate_index_path()
        if not path.exists():
            return {
                "schema": CONTEXT_PACK_CANDIDATE_INDEX_SCHEMA,
                "namespace": CONTEXT_PACK_NAMESPACE,
                "entries": {},
            }
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ContextPackStoreError("candidate index must be a JSON object")
        extra = sorted(
            set(payload) - {"schema", "namespace", "entries", "branch_id"}
        )
        if extra:
            raise UnknownFieldError(f"unknown field: {extra[0]}")
        if payload.get("schema") != CONTEXT_PACK_CANDIDATE_INDEX_SCHEMA:
            raise ContextPackStoreError("candidate index schema mismatch")
        if payload.get("namespace") != CONTEXT_PACK_NAMESPACE:
            raise ContextPackStoreError("candidate index namespace must be ContextPack")
        entries = payload.get("entries")
        if not isinstance(entries, dict):
            raise ContextPackStoreError("candidate index entries must be an object")
        return payload

    def _write_candidate_index(self, payload: Mapping[str, Any]) -> None:
        _atomic_write_json(self._candidate_index_path(), payload)

    def _load_state(self) -> dict[str, Any]:
        path = self._state_path()
        if not path.exists():
            return {
                "schema": CONTEXT_PACK_STATE_SCHEMA,
                "namespace": CONTEXT_PACK_NAMESPACE,
                "verification_generation": 0,
            }
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ContextPackStoreError("ContextPack state must be a JSON object")
        extra = sorted(
            set(payload) - {"schema", "namespace", "verification_generation"}
        )
        if extra:
            raise UnknownFieldError(f"unknown field: {extra[0]}")
        return payload

    def _write_state(self, payload: Mapping[str, Any]) -> None:
        _atomic_write_json(self._state_path(), payload)

    def _expected_pointer(
        self, branch_id: str, parent: str
    ) -> CurrentSealPointer | None:
        current = self._pointers.get_current_seal(CONTEXT_PACK_NAMESPACE, branch_id)
        if current is None:
            if parent:
                raise StaleContextPackCasError(
                    "genesis CAS requires empty expected_parent_cid"
                )
            return None
        if parent != current.seal_cid:
            raise StaleContextPackCasError(
                "stale expected parent cannot overwrite the current ContextPack root"
            )
        return current

    def _publish_locked(
        self,
        *,
        admitted: ArtifactReference,
        parent: str,
        generation: int | None,
        branch_id: str,
        transition_id: str | None,
    ) -> CurrentSealPointer:
        expected = self._expected_pointer(branch_id, parent)
        if expected is None:
            next_generation = 0
        else:
            next_generation = expected.generation + 1
        if generation is None:
            generation = next_generation
        if generation != next_generation:
            raise StaleContextPackCasError(
                f"stale generation {generation} vs expected {next_generation}"
            )
        new_pointer = CurrentSealPointer(
            repository_id=CONTEXT_PACK_NAMESPACE,
            branch_id=branch_id,
            seal_cid=admitted.cid,
            seal_kind=admitted.kind,
            generation=generation,
            parent_seal_cid=parent,
        )
        txn = transition_id or (
            f"ctxpack:{branch_id}:{generation}:{admitted.cid[-12:]}:"
            f"{self._wal.sequence_count}"
        )
        intent = SealTransitionRecord(
            transition_id=txn,
            repository_id=CONTEXT_PACK_NAMESPACE,
            branch_id=branch_id,
            phase=SealTransitionPhase.INTENT,
            state=SealTransitionState.OPEN,
            expected_parent_seal_cid=parent,
            new_seal_cid=admitted.cid,
            new_seal_kind=admitted.kind,
            generation=generation,
            artifact_cids=(admitted.cid,),
        )
        self._wal.begin_transition(intent)
        for phase in PHASE_ORDER[1:]:
            if phase is SealTransitionPhase.CURRENT_ROOT_CAS:
                break
            kwargs: dict[str, Any] = {}
            if phase is SealTransitionPhase.SEAL_PERSISTENCE:
                kwargs = {
                    "new_seal_cid": admitted.cid,
                    "new_seal_kind": admitted.kind,
                    "artifact_cids": (admitted.cid,),
                }
            self._wal.record_phase(txn, phase, **kwargs)
        try:
            swapped = self._pointers.compare_and_swap_current_seal(
                expected, new_pointer
            )
        except PointerCasRejected as exc:
            raise StaleContextPackCasError(str(exc)) from exc
        if not swapped:
            raise StaleContextPackCasError(
                "stale concurrent writer lost ContextPack current-root CAS"
            )
        self._wal.record_phase(
            txn,
            SealTransitionPhase.CURRENT_ROOT_CAS,
            new_seal_cid=admitted.cid,
            new_seal_kind=admitted.kind,
        )
        self._wal.record_phase(txn, SealTransitionPhase.CLEANUP)
        self._wal.commit_transition(
            txn,
            new_seal_cid=admitted.cid,
            new_seal_kind=admitted.kind,
            phase=SealTransitionPhase.CLEANUP,
        )
        current = self._pointers.get_current_seal(CONTEXT_PACK_NAMESPACE, branch_id)
        if current is None or current.seal_cid != admitted.cid:
            raise ContextPackStoreError("current-root CAS did not persist")
        return current

    def _complete_open_publications(self) -> None:
        """Finish CAS only when the expected parent is still current."""

        for record in self._wal.open_transitions():
            if record.repository_id != CONTEXT_PACK_NAMESPACE:
                continue
            if not record.new_seal_cid or record.new_seal_kind is None:
                continue
            if record.phase not in {
                SealTransitionPhase.SEAL_PERSISTENCE,
                SealTransitionPhase.CURRENT_ROOT_CAS,
                SealTransitionPhase.CLEANUP,
            }:
                continue
            current = self._pointers.get_current_seal(
                record.repository_id, record.branch_id
            )
            if current is not None and current.seal_cid == record.new_seal_cid:
                continue
            if current is None:
                parent_ok = record.expected_parent_seal_cid == ""
                expected = None
            else:
                parent_ok = current.seal_cid == record.expected_parent_seal_cid
                expected = current
            if not parent_ok:
                continue
            pointer = CurrentSealPointer(
                repository_id=record.repository_id,
                branch_id=record.branch_id,
                seal_cid=record.new_seal_cid,
                seal_kind=record.new_seal_kind,
                generation=record.generation,
                parent_seal_cid=record.expected_parent_seal_cid,
            )
            try:
                self._pointers.compare_and_swap_current_seal(expected, pointer)
            except PointerCasRejected:
                continue


class KitProofContextStateStore:
    """Single durable v0.1 port over the inventoried hermetic store."""

    schema = PORT_SCHEMA
    interface = PORT_INTERFACE
    ipfs_required = False
    context_pack_namespace = CONTEXT_PACK_NAMESPACE
    context_pack_interface = CONTEXT_PACK_INTERFACE

    def __init__(
        self,
        root: str | Path,
        *,
        enable_ipfs: bool = False,
        crash_injector: Callable[..., Any] | None = None,
    ) -> None:
        if enable_ipfs:
            raise UnavailableTransportError(
                "optional IPFS transport is explicit and unavailable is not success"
            )
        self._root = Path(root)
        self._store = HermeticProofSealStore(self._root)
        self._forest = None
        self._crash_injector = crash_injector
        self._context_pack: ContextPackStore | None = None

    @property
    def root(self) -> Path:
        return self._root

    @property
    def hermetic_store(self) -> HermeticProofSealStore:
        return self._store

    @property
    def context_pack(self) -> ContextPackStore:
        if self._context_pack is None:
            self._context_pack = ContextPackStore(
                self._root,
                hermetic_store=self._store,
                crash_injector=self._crash_injector,
            )
        return self._context_pack

    @property
    def forest(self) -> Any:
        if self._forest is None:
            try:
                from ipfs_kit_py.proof_seal_store.forest import ProofForestStore
            except ModuleNotFoundError as exc:
                raise UnavailableTransportError(
                    "proof-forest codec requires installed datasets; unavailable is not success"
                ) from exc
            self._forest = ProofForestStore(self._root, object_store=self._store)
        return self._forest

    def put(self, data: bytes, *, claimed_cid: str | None = None) -> ArtifactReference:
        return put_bytes(self._store, data, claimed_cid=claimed_cid)

    def get(self, reference: ArtifactReference) -> bytes:
        return get_bytes(self._store, reference)

    def cid_for(self, data: bytes) -> str:
        return cid_for_bytes(data)

    def put_context_pack(
        self,
        data: bytes,
        *,
        claimed_cid: str | None = None,
        kind: ArtifactKind | str = ArtifactKind.CHECKPOINT_SEAL,
    ) -> ArtifactReference:
        return self.context_pack.put_verified_bytes(
            data, kind=kind, claimed_cid=claimed_cid
        )

    def get_context_pack(self, reference: ArtifactReference) -> bytes:
        return self.context_pack.get_immutable(reference)

    def put_context_pack_candidate(
        self, data: bytes, **kwargs: Any
    ) -> ArtifactReference:
        return self.context_pack.put_candidate(data, **kwargs)

    def compare_and_swap_context_pack_root(
        self, **kwargs: Any
    ) -> CurrentSealPointer:
        return self.context_pack.compare_and_swap_current_root(**kwargs)

    def recover_context_pack(self) -> RecoveryReport:
        return self.context_pack.recover()

    def retain_context_pack(self, **kwargs: Any) -> dict[str, Any]:
        return self.context_pack.apply_retention(**kwargs)


def open_local_store(root: str | Path) -> KitProofContextStateStore:
    return KitProofContextStateStore(root, enable_ipfs=False)


def open_context_pack_store(
    root: str | Path, *, crash_injector: Callable[..., Any] | None = None
) -> ContextPackStore:
    return ContextPackStore(root, crash_injector=crash_injector)


def reject_default_root() -> None:
    HermeticProofSealStore(None)
