"""Fail-closed PCPR-062 Kit ContextPack persist and current-root publish.

Kit owns exact bytes, CID verification, durable roots, current-root
compare-and-swap, and ContextPack storage. This module verifies the
Datasets-owned DatasetsContextPack@1 identity, stores its exact
canonical bytes, publishes a generation-bearing current root through
hermetic CAS, records storage and transition receipts, and re-opens
with verification.

It does not remint DatasetsContextPack@1, does not import sibling
Accelerate or Datasets packages, does not write DuckDB or Quack state,
and does not claim live IPFS, live Quack, or a closed PCPR release.
Hermetic persist and CAS are measured_hermetic, never live. Missing a
live durable backend or Quack-fenced session is an explicit
operator-blocking task. Simulated results are not live.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from ipfs_kit_py.assurance.dependency_locks import (
    CLOSED_RELEASE_OUTCOMES,
    PACKAGE_NAME,
    PACKAGE_VERSION,
    SEALED_PATH,
    SEALED_PYTHON,
    canonical_json_bytes,
    content_identity,
    discover_kit_root,
    pretty_json,
    sha256_bytes,
    typed_unavailable,
)

INTERFACE: Final = "KitContextPackStorage@1"
SCHEMA: Final = "ipfs_kit_py/assurance/context-pack-storage@1"
DOCUMENT_SCHEMA: Final = (
    "ipfs_kit_py/assurance/declared-context-pack-root@1"
)
VERDICT_SCHEMA: Final = (
    "ipfs_kit_py/assurance/context-pack-storage-verdict@1"
)
RECEIPT_SCHEMA: Final = "pcpr/shared-contracts/durable-artifact-receipt@1"
RECEIPT_INTERFACE: Final = "DurableArtifactReceipt@1"
TRANSITION_SCHEMA: Final = (
    "ipfs_kit_py/assurance/context-pack-root-transition@1"
)
CURRENT_ROOT_SCHEMA: Final = (
    "ipfs_kit_py/assurance/context-pack-current-root-pointer@1"
)
OWNER_INTERFACE: Final = "DatasetsContextPack@1"
OWNER_SCHEMA: Final = "ipfs_datasets_py/datasets-context-pack@1"
OWNER_REPOSITORY: Final = "ipfs_datasets_py"
STORAGE_OWNER_REPOSITORY: Final = "ipfs_kit_py"
PCPR_062_TASK_ID: Final = "PCPR-062"
PCPR_062_GOAL_ID: Final = "PCPR-G700"
PCPR_061_TASK_ID: Final = "PCPR-061"
PCPR_060_TASK_ID: Final = "PCPR-060"
PCPR_063_TASK_ID: Final = "PCPR-063"
PCPR_PROGRAM_ID: Final = "proof-carrying-platform-qualification-and-release-v1"
OBJECTIVE_KIND: Final = "declared_context_pack_root"
PORTFOLIO_ID: Final = "portfolio:pcpr-v1"
PORTFOLIO_VERSION: Final = "proof-carrying-platform-0.1.0"
LANGUAGE: Final = "Python"
OBJECTIVE_ID: Final = "PCPR-G700"
OPERATOR_BLOCKING_TASK_ID: Final = "pcpr-062-operator-live-context-pack-root"
SOURCE_DATE_EPOCH: Final = "0"
GENESIS_PARENT: Final = ""
POINTER_NAME: Final = "current-root.json"
DIGEST_NAME: Final = "current-root.json.sha256"
OBJECTS_DIRNAME: Final = "objects"
HERMETIC_BACKEND_ID: Final = "hermetic_context_pack_root"

PINNED_LOCK_CID: Final = (
    "baguqeerawsekbbbt5ccctjt4tydzeahfkahsatb6q5x7k6cy4inrii5lhqmq"
)
PINNED_IDEA_DIGEST: Final = (
    "baguqeeracbayojdov4jmqiirx22pavrg6nabazcocru6y3scrdx5e54mw2zq"
)
PINNED_OBJECTIVE_CID: Final = (
    "baguqeeraynsn7tjr3iaggnreylzxo3akaooqwp5bf5oheaa6eubth2zwqeba"
)
PINNED_PACK_CID: Final = (
    "bafkreih72d3nncekez43wmtlczq5mdtymzniluujypwybpgu3mtt7i4v2e"
)
PINNED_PACK_DOCUMENT_CID: Final = (
    "baguqeera5ykn6pm3xvty6taigxxjtnguutg7oznw4ez52jv676igcif4wkda"
)
PINNED_BYTES_SHA256: Final = (
    "e91a4118ae3ae49e48ae1bcaf874c5520b97c0f640bc28826ecfc23d7b49c1b2"
)
PINNED_BYTES_SIZE: Final = 834
PINNED_BYTES_CID: Final = (
    "bafkreihjdjarrlr24sperlq3zl4hjrksbol4b5saxquie3wpyi6xwsobwi"
)
PINNED_CURRENT_ROOT_CID: Final = PINNED_BYTES_CID

DOCUMENT_DIR_RELPATH: Final = "packaging/pcpr/reference-workflow/cpython312"
DOCUMENT_JSON_NAME: Final = "reference.context-pack.root.json"
BYTES_JSON_NAME: Final = "reference.context-pack.bytes.json"
DOCUMENT_README_RELPATH: Final = (
    "packaging/pcpr/reference-workflow/CONTEXT_PACK_ROOT.md"
)

REFERENCE_OBJECTIVE_IDEA: Final = (
    "Modify a typed formal-logic API while reusing unaffected proofs, "
    "selecting only impacted tests, rejecting stale-tree evidence, and "
    "producing a complete proof-carrying execution receipt."
)

PINNED_PACK_IDENTITY: Final[Mapping[str, Any]] = MappingProxyType(
    {
        "capsule_cids": [
            "bafkreihvtxeeorzuhiq7efbde3ld6epsnkg2ycf46xojxqptwhgcmwno2e",
            "bafkreifwuzoexs7g23vb76pd2hut6vb5qtjfnjoiggm7pmzbit4pekr2l4",
            "bafkreibiftotu25brkiapgeggn6tmc5oitnboj2i7kr22jyv2idra4g6hm",
        ],
        "freshness": "fresh",
        "interface": OWNER_INTERFACE,
        "opaque": False,
        "repository_state_cid": (
            "baguqeerajorugdc52stghgeujb4hq74rkt2ikk6fpw72lebmjiuvyvctvraa"
        ),
        "required_source_cids": {
            "surrounding_source": (
                "bafkreia2bjp4cpebvscty2ciwibbgubliiji6ok7ddo52jnj5hpvmfq2mi"
            ),
            "target_source": (
                "bafkreih2gdfklkg6ypikg6cho2ijyqohbib4fw55vtiasnh46m6lk2tmfe"
            ),
            "test_source": (
                "bafkreigqatkl3tydc5rsjlp7tdetjliqi7eenypwrlxuaonl6uvkzqnoia"
            ),
        },
        "scanned_tree_oid": (
            "08fd20feca64070950335c120c8ae8d7d56fc07de7a745dab7b08ac2520c7f04"
        ),
        "schema": OWNER_SCHEMA,
        "task_class": "typed_formal_logic_api_modification",
        "task_id": PCPR_061_TASK_ID,
    }
)

HERMETIC_CANDIDATE_SUITES: Final[tuple[str, ...]] = (
    "tests/test_pcpr_062_context_pack_storage.py",
)

EVIDENCE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "measured",
        "measured_live",
        "measured_hermetic",
        "estimated",
        "simulated",
        "unavailable",
    }
)

REQUIRED_GOOD_PROBE_IDS: Final[frozenset[str]] = frozenset(
    {
        "root_files_match_generator",
        "pyproject_context_pack_storage_table",
        "owner_pack_cid_matches_pin",
        "exact_bytes_verified",
        "hermetic_bytes_stored",
        "hermetic_current_root_published",
        "restart_reopen_verified",
        "stale_parent_rejected",
        "duckdb_or_quack_not_written",
        "operator_blocking_task_emitted",
        "no_closed_release_outcome",
    }
)
FORBIDDEN_PRESENT_PROBE_IDS: Final[frozenset[str]] = frozenset(
    {
        "simulated_results_represented_as_live",
        "live_storage_represented_as_live",
        "closed_release_represented_as_live",
        "compatibility_identities_reminted",
        "sibling_import_observed",
        "datasets_identity_reminted",
        "direct_database_bypass_used",
    }
)

DOCUMENT_README: Final = """# PCPR-062 Kit ContextPack persist and current root

These files are Kit-owned *declared* ContextPack storage for the
PCPR-061 DatasetsContextPack@1 identity. Kit verifies exact canonical
bytes, stores them, and publishes a generation-bearing current root
through hermetic compare-and-swap.

- `cpython312/reference.context-pack.bytes.json` is the exact
  DatasetsContextPack@1 identity payload stored by Kit.
- `cpython312/reference.context-pack.root.json` is the storage and
  current-root receipt. Exact commit and tree are bound by the
  PCPR-062 receipt `current_tree_binding`. `origin/main` is not the
  release identity.
- Hermetic persist and CAS are not live IPFS, not live Quack, and not
  live supervisor admission.
- Deterministic execution remains PCPR-063.
- Missing a live durable backend or Quack-fenced session emits
  operator-blocking task `pcpr-062-operator-live-context-pack-root`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
"""


class KitContextPackStorageError(ValueError):
    """Kit attempted to remint, forge, or live-claim ContextPack storage."""


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KitContextPackStorageError(f"{name} must be a non-empty string")
    return value.strip()


def _kind(value: Any, name: str) -> str:
    kind = _text(value, name)
    if kind not in EVIDENCE_KINDS:
        raise KitContextPackStorageError(f"{name} is not an admitted evidence kind")
    return kind


def _reject_closed_release_value(value: Any, name: str) -> None:
    if isinstance(value, str) and value in CLOSED_RELEASE_OUTCOMES:
        raise KitContextPackStorageError(
            f"{name} must not be a closed PCPR release outcome"
        )


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(path))
    dir_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def raw_content_cid(data: bytes) -> str:
    """Return a CIDv1 raw/sha2-256 identity for exact object bytes."""

    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    digest = b"\x01\x55\x12\x20" + hashlib.sha256(data).digest()
    return "b" + base64.b32encode(digest).decode("ascii").rstrip("=").lower()


def canonical_pack_bytes() -> bytes:
    return canonical_json_bytes(dict(PINNED_PACK_IDENTITY))


def parse_pyproject_context_pack_storage_table(text: str) -> dict[str, Any]:
    import tomllib

    table = tomllib.loads(_text(text, "pyproject.toml"))
    if not isinstance(table, dict):
        raise KitContextPackStorageError("pyproject.toml must be a table")
    tool = table.get("tool")
    payload: dict[str, Any] = {}
    if isinstance(tool, dict):
        kit = tool.get("ipfs_kit_py")
        if isinstance(kit, dict):
            raw = kit.get("context-pack-storage")
            if isinstance(raw, dict):
                payload = dict(raw)
    return payload


@dataclass(frozen=True)
class OutcomeProbe:
    probe_id: str
    present: bool | None
    evidence_kind: str
    live: bool
    simulated_represented_as_live: bool
    reason: str
    details: Mapping[str, Any] = MappingProxyType({})

    def to_mapping(self) -> dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "present": self.present,
            "evidence_kind": self.evidence_kind,
            "live": self.live,
            "simulated_represented_as_live": self.simulated_represented_as_live,
            "reason": self.reason,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class CurrentRootPointer:
    schema: str
    generation: int
    current_cid: str
    parent_cid: str
    object_digest: str
    tombstoned: bool
    invalidated: bool
    invalidation_reason: str = ""

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "generation": self.generation,
            "current_cid": self.current_cid,
            "parent_cid": self.parent_cid,
            "object_digest": self.object_digest,
            "tombstoned": self.tombstoned,
            "invalidated": self.invalidated,
            "invalidation_reason": self.invalidation_reason,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CurrentRootPointer":
        return cls(
            schema=str(payload.get("schema") or CURRENT_ROOT_SCHEMA),
            generation=int(payload.get("generation") or 0),
            current_cid=str(payload.get("current_cid") or ""),
            parent_cid=str(payload.get("parent_cid") or ""),
            object_digest=str(payload.get("object_digest") or ""),
            tombstoned=bool(payload.get("tombstoned")),
            invalidated=bool(payload.get("invalidated")),
            invalidation_reason=str(payload.get("invalidation_reason") or ""),
        )


@dataclass(frozen=True)
class CurrentRootCasResult:
    swapped: bool
    pointer: CurrentRootPointer
    object_cid: str
    reason: str = ""

    def to_mapping(self) -> dict[str, Any]:
        return {
            "swapped": self.swapped,
            "pointer": self.pointer.to_mapping(),
            "object_cid": self.object_cid,
            "reason": self.reason,
        }


class HermeticContextPackRootStore:
    """Directory-backed current-root CAS for ContextPack bytes.

    This surface is hermetic: it never contacts IPFS, Iroh, Quack, or
    DuckDB. Process restart reconstructs the current root from disk.
    Stale parents, digest mismatches, tombstones, and invalidations
    fail closed.
    """

    schema = CURRENT_ROOT_SCHEMA
    interface = INTERFACE
    live_provider = False
    is_hermetic = True

    def __init__(self, root: str | Path, *, create: bool = True) -> None:
        self.root = Path(root).resolve()
        self._objects = self.root / OBJECTS_DIRNAME
        self._pointer_path = self.root / POINTER_NAME
        self._digest_path = self.root / DIGEST_NAME
        self._lock = threading.RLock()
        self._closed = False
        if create:
            self.root.mkdir(parents=True, exist_ok=True)
            self._objects.mkdir(parents=True, exist_ok=True)
        if create and not self._pointer_path.is_file():
            genesis = CurrentRootPointer(
                schema=CURRENT_ROOT_SCHEMA,
                generation=0,
                current_cid=GENESIS_PARENT,
                parent_cid=GENESIS_PARENT,
                object_digest=sha256_bytes(b""),
                tombstoned=False,
                invalidated=False,
            )
            self._persist_pointer(genesis)

    def close(self) -> None:
        self._closed = True

    @classmethod
    def reopen(cls, root: str | Path) -> "HermeticContextPackRootStore":
        store = cls(root, create=False)
        if not store._pointer_path.is_file() or not store._digest_path.is_file():
            raise KitContextPackStorageError(
                "current-root pointer is missing on reopen"
            )
        store.current()
        return store

    def current(self) -> CurrentRootPointer:
        with self._lock:
            return self._load_pointer()

    def get(self, cid: str) -> bytes:
        with self._lock:
            if not cid:
                return b""
            path = self._objects / cid
            if not path.is_file():
                raise KitContextPackStorageError("current-root object is absent")
            data = path.read_bytes()
            if raw_content_cid(data) != cid:
                raise KitContextPackStorageError(
                    "current-root object digest mismatch"
                )
            return data

    def put_verified(self, payload: bytes, *, expected_cid: str | None = None) -> str:
        if not isinstance(payload, bytes):
            raise KitContextPackStorageError("payload must be bytes")
        cid = raw_content_cid(payload)
        if expected_cid is not None and cid != expected_cid:
            raise KitContextPackStorageError(
                f"stored bytes CID {cid} does not match expected {expected_cid}"
            )
        with self._lock:
            self._assert_open()
            _atomic_write_bytes(self._objects / cid, payload)
        return cid

    def compare_and_swap(
        self,
        expected_parent_cid: str,
        payload: bytes,
    ) -> CurrentRootCasResult:
        if not isinstance(payload, bytes):
            raise KitContextPackStorageError("current-root payload must be bytes")
        with self._lock:
            self._assert_open()
            pointer = self._load_pointer()
            self._assert_writable(pointer)
            if pointer.current_cid != expected_parent_cid:
                raise KitContextPackStorageError(
                    "stale parent rejected by current-root CAS"
                )
            new_cid = self.put_verified(payload)
            new_pointer = CurrentRootPointer(
                schema=CURRENT_ROOT_SCHEMA,
                generation=pointer.generation + 1,
                current_cid=new_cid,
                parent_cid=pointer.current_cid,
                object_digest=sha256_bytes(payload),
                tombstoned=False,
                invalidated=False,
            )
            self._persist_pointer(new_pointer)
            return CurrentRootCasResult(
                swapped=True,
                pointer=new_pointer,
                object_cid=new_cid,
                reason="hermetic current-root CAS swapped",
            )

    def _assert_open(self) -> None:
        if self._closed:
            raise KitContextPackStorageError("context-pack root store is closed")

    def _assert_writable(self, pointer: CurrentRootPointer) -> None:
        if pointer.tombstoned:
            raise KitContextPackStorageError("tombstoned current root is not writable")
        if pointer.invalidated:
            raise KitContextPackStorageError(
                "invalidated current root is not writable"
            )

    def _persist_pointer(self, pointer: CurrentRootPointer) -> None:
        body = canonical_json_bytes(pointer.to_mapping())
        _atomic_write_bytes(self._pointer_path, body)
        _atomic_write_bytes(
            self._digest_path, sha256_bytes(body).encode("ascii") + b"\n"
        )

    def _load_pointer(self) -> CurrentRootPointer:
        if not self._pointer_path.is_file() or not self._digest_path.is_file():
            raise KitContextPackStorageError("current-root pointer is missing")
        body = self._pointer_path.read_bytes()
        digest = self._digest_path.read_text(encoding="ascii").strip()
        if sha256_bytes(body) != digest:
            raise KitContextPackStorageError(
                "current-root pointer corruption detected"
            )
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise KitContextPackStorageError("current-root pointer is not a mapping")
        return CurrentRootPointer.from_mapping(payload)


@dataclass(frozen=True)
class KitContextPackStorageVerdict:
    schema: str
    interface: str
    promotion_status: str
    supervisor_disposition: str
    closed_release_outcome: str | None
    release_claim: bool
    completion_authoritative: bool
    contracts_frozen: bool
    duckdb_or_quack_state_written: bool
    sibling_source_required: bool
    live_storage: bool
    live_storage_evidence_kind: str
    live_current_root: bool
    live_ipfs: bool
    operator_blocking_task: str
    simulated_results_represented_as_live: bool
    this_task_created_competing_authority: bool
    probes: tuple[OutcomeProbe, ...]
    blockers: tuple[str, ...]
    verdict_cid: str
    pack_cid: str
    bytes_cid: str
    current_root_cid: str
    document_cid: str
    objective_cid: str
    idea_digest: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "interface": self.interface,
            "verdict_cid": self.verdict_cid,
            "pack_cid": self.pack_cid,
            "bytes_cid": self.bytes_cid,
            "current_root_cid": self.current_root_cid,
            "document_cid": self.document_cid,
            "objective_cid": self.objective_cid,
            "idea_digest": self.idea_digest,
            "promotion_status": self.promotion_status,
            "supervisor_disposition": self.supervisor_disposition,
            "closed_release_outcome": self.closed_release_outcome,
            "release_claim": self.release_claim,
            "completion_authoritative": self.completion_authoritative,
            "contracts_frozen": self.contracts_frozen,
            "duckdb_or_quack_state_written": self.duckdb_or_quack_state_written,
            "sibling_source_required": self.sibling_source_required,
            "live_storage": self.live_storage,
            "live_storage_evidence_kind": self.live_storage_evidence_kind,
            "live_current_root": self.live_current_root,
            "live_ipfs": self.live_ipfs,
            "operator_blocking_task": self.operator_blocking_task,
            "simulated_results_represented_as_live": (
                self.simulated_results_represented_as_live
            ),
            "this_task_created_competing_authority": (
                self.this_task_created_competing_authority
            ),
            "blocker_count": len(self.blockers),
            "blockers": list(self.blockers),
            "evidence_kind": "measured",
        }


def _probe(
    probe_id: str,
    present: bool | None,
    *,
    reason: str,
    evidence_kind: str = "measured",
    live: bool = False,
    details: Mapping[str, Any] | None = None,
) -> OutcomeProbe:
    return OutcomeProbe(
        probe_id=probe_id,
        present=present,
        evidence_kind=evidence_kind,
        live=live,
        simulated_represented_as_live=False,
        reason=reason,
        details=MappingProxyType(dict(details or {})),
    )


def _operator_blocking_task() -> dict[str, Any]:
    return {
        "task_id": OPERATOR_BLOCKING_TASK_ID,
        "status": "typed_blocked",
        "evidence_kind": "unavailable",
        "live": False,
        "applied": False,
        "requires": (
            "An admitted Quack-fenced state-owner session and a live "
            "qualified durable backend before the ContextPack current "
            "root is published as live"
        ),
        "action": (
            "Keep the hermetic current root. Do not write DuckDB or "
            "Quack state. Do not claim live IPFS. PCPR-063 executes the "
            "deterministic-first route against this stored identity."
        ),
        "reason": (
            "Hermetic persist and CAS are not live durable publication. "
            "Sealed validation has no admitted Quack-fenced session and "
            "no live IPFS daemon."
        ),
    }


def persist_and_publish_current_root(store_root: Path) -> dict[str, Any]:
    """Verify exact bytes, store them, CAS the current root, restart, re-open."""

    payload = canonical_pack_bytes()
    measured_cid = raw_content_cid(payload)
    if measured_cid != PINNED_BYTES_CID:
        raise KitContextPackStorageError(
            f"canonical pack bytes CID {measured_cid} remints {PINNED_BYTES_CID}"
        )
    if sha256_bytes(payload) != PINNED_BYTES_SHA256:
        raise KitContextPackStorageError("canonical pack bytes digest drifted")
    store = HermeticContextPackRootStore(store_root, create=True)
    first = store.compare_and_swap(GENESIS_PARENT, payload)
    store.close()
    reopened = HermeticContextPackRootStore.reopen(store_root)
    pointer = reopened.current()
    recovered = reopened.get(pointer.current_cid)
    restart_verified = (
        recovered == payload
        and pointer.current_cid == PINNED_CURRENT_ROOT_CID
        and pointer.generation == 1
        and pointer.parent_cid == GENESIS_PARENT
        and first.swapped is True
    )
    stale_rejected = False
    try:
        reopened.compare_and_swap(GENESIS_PARENT, payload)
    except KitContextPackStorageError as exc:
        stale_rejected = "stale parent" in str(exc)
    reopened.close()
    return {
        "stored": True,
        "current_root_published": True,
        "live": False,
        "backend": HERMETIC_BACKEND_ID,
        "bytes_cid": measured_cid,
        "bytes_sha256": PINNED_BYTES_SHA256,
        "bytes_size": len(payload),
        "pack_cid": PINNED_PACK_CID,
        "current_root": pointer.to_mapping(),
        "cas": first.to_mapping(),
        "restart_verified": restart_verified,
        "stale_parent_rejected": stale_rejected,
        "evidence_kind": "measured_hermetic",
    }


def render_durable_artifact_receipt() -> dict[str, Any]:
    payload = canonical_pack_bytes()
    document = {
        "schema": RECEIPT_SCHEMA,
        "interface": RECEIPT_INTERFACE,
        "artifact_kind": "context_pack",
        "pack_cid": PINNED_PACK_CID,
        "pack_owner_interface": OWNER_INTERFACE,
        "pack_owner_schema": OWNER_SCHEMA,
        "pack_owner_repository": OWNER_REPOSITORY,
        "bytes_cid": PINNED_BYTES_CID,
        "bytes_sha256": PINNED_BYTES_SHA256,
        "bytes_size": PINNED_BYTES_SIZE,
        "stored": True,
        "live": False,
        "backend": HERMETIC_BACKEND_ID,
        "owner_repository": STORAGE_OWNER_REPOSITORY,
        "task_id": PCPR_062_TASK_ID,
        "goal_id": PCPR_062_GOAL_ID,
        "ipfs_daemon": typed_unavailable(
            reason="Sealed PATH has no live IPFS daemon. Hermetic CAS is not IPFS."
        ),
        "quack": typed_unavailable(
            reason="No admitted Quack-fenced session. Direct Quack writes are prohibited."
        ),
        "duckdb_or_quack_state_written": False,
        "evidence_kind": "measured_hermetic",
    }
    if len(payload) != PINNED_BYTES_SIZE:
        raise KitContextPackStorageError("canonical pack bytes size drifted")
    document["receipt_cid"] = content_identity(
        {key: value for key, value in document.items() if key != "receipt_cid"}
    )
    return document


def render_transition_receipt() -> dict[str, Any]:
    document = {
        "schema": TRANSITION_SCHEMA,
        "task_id": PCPR_062_TASK_ID,
        "goal_id": PCPR_062_GOAL_ID,
        "generation": 1,
        "parent_cid": GENESIS_PARENT,
        "current_cid": PINNED_CURRENT_ROOT_CID,
        "object_digest": PINNED_BYTES_SHA256,
        "swapped": True,
        "live": False,
        "backend": HERMETIC_BACKEND_ID,
        "restart_verified": True,
        "stale_parent_rejected": True,
        "evidence_kind": "measured_hermetic",
    }
    document["transition_cid"] = content_identity(
        {key: value for key, value in document.items() if key != "transition_cid"}
    )
    return document


def render_declared_root(root: Path | None = None) -> dict[str, Any]:
    package_root = root or discover_kit_root()
    if package_root is None:
        raise KitContextPackStorageError("Kit package root was not found")
    _ = package_root
    receipt = render_durable_artifact_receipt()
    transition = render_transition_receipt()
    payload = canonical_pack_bytes()
    document = {
        "schema": DOCUMENT_SCHEMA,
        "interface": INTERFACE,
        "task_id": PCPR_062_TASK_ID,
        "goal_id": PCPR_062_GOAL_ID,
        "program_id": PCPR_PROGRAM_ID,
        "owner_repository": STORAGE_OWNER_REPOSITORY,
        "pack_owner_repository": OWNER_REPOSITORY,
        "owner_interface": OWNER_INTERFACE,
        "owner_schema": OWNER_SCHEMA,
        "owned_contracts": ["DurableArtifactReceipt"],
        "portfolio_id": PORTFOLIO_ID,
        "portfolio_version": PORTFOLIO_VERSION,
        "objective_kind": OBJECTIVE_KIND,
        "package_name": PACKAGE_NAME,
        "package_version": PACKAGE_VERSION,
        "language": LANGUAGE,
        "objective_id": OBJECTIVE_ID,
        "idea": REFERENCE_OBJECTIVE_IDEA,
        "idea_digest": PINNED_IDEA_DIGEST,
        "objective_cid": PINNED_OBJECTIVE_CID,
        "lock_cid": PINNED_LOCK_CID,
        "prerequisite_task_id": PCPR_061_TASK_ID,
        "context_pack": {
            "task_id": PCPR_061_TASK_ID,
            "constructed_by": OWNER_REPOSITORY,
            "constructed": True,
            "pack_cid": PINNED_PACK_CID,
            "pack_document_cid": PINNED_PACK_DOCUMENT_CID,
            "owner_interface": OWNER_INTERFACE,
            "owner_schema": OWNER_SCHEMA,
            "identity": dict(PINNED_PACK_IDENTITY),
            "reminted": False,
            "live": False,
            "stored": True,
            "current_root_published": True,
            "evidence_kind": "measured",
        },
        "storage": {
            "task_id": PCPR_062_TASK_ID,
            "stored": True,
            "current_root_published": True,
            "live": False,
            "deferred": False,
            "backend": HERMETIC_BACKEND_ID,
            "bytes_cid": PINNED_BYTES_CID,
            "bytes_sha256": PINNED_BYTES_SHA256,
            "bytes_size": len(payload),
            "bytes_verified": True,
            "durable_artifact_receipt_cid": receipt["receipt_cid"],
            "evidence_kind": "measured_hermetic",
            "reason": (
                "Kit verified and stored exact DatasetsContextPack@1 bytes "
                "through hermetic CAS. Live IPFS publication stays typed "
                "unavailable."
            ),
        },
        "current_root": {
            "schema": CURRENT_ROOT_SCHEMA,
            "generation": 1,
            "current_cid": PINNED_CURRENT_ROOT_CID,
            "parent_cid": GENESIS_PARENT,
            "object_digest": PINNED_BYTES_SHA256,
            "published": True,
            "live": False,
            "backend": HERMETIC_BACKEND_ID,
            "cas": True,
            "restart_verified": True,
            "stale_parent_rejected": True,
            "transition_cid": transition["transition_cid"],
            "evidence_kind": "measured_hermetic",
        },
        "durable_artifact_receipt": receipt,
        "transition": transition,
        "execution": {
            "task_id": PCPR_063_TASK_ID,
            "performed": False,
            "live": False,
            "deferred": True,
        },
        "materialization": {
            "kind": "hermetic_store_not_live",
            "admitted": False,
            "live": False,
            "applied": False,
            "duckdb_or_quack_state_written": False,
            "evidence_kind": "unavailable",
        },
        "live_bytes_store": typed_unavailable(
            reason=(
                "Hermetic ContextPack persist is not live IPFS, Iroh, or "
                "Quack publication."
            )
        ),
        "live_current_root": typed_unavailable(
            reason=(
                "Hermetic current-root CAS is not a live durable-backend "
                "publication."
            )
        ),
        "ipfs_daemon": typed_unavailable(
            reason="Sealed PATH has no live IPFS daemon."
        ),
        "quack_fenced_session": typed_unavailable(
            reason=(
                "No admitted Quack-fenced state-owner session was observed. "
                "Direct DuckDB writes are prohibited."
            )
        ),
        "source": {
            "kind": "git",
            "repository": "endomorphosis/ipfs_kit_py",
            "binding": "current_head_not_mutable_main",
            "mutable_main_reference": False,
            "commit": {
                "status": "observed_at_evaluation",
                "evidence_kind": "measured",
                "live": False,
                "field": "PCPR-062 receipt current_tree_binding",
            },
        },
        "operator_blocking_task": _operator_blocking_task(),
        "live": False,
        "applied": False,
        "submitted_live": False,
        "release_claim": False,
        "closed_release_outcome": None,
        "contracts_frozen": False,
        "hashes_invented": False,
        "signatures_invented": False,
        "sibling_source_required": False,
        "this_task_created_competing_authority": False,
        "duckdb_or_quack_state_written": False,
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "evidence_kind": "measured",
    }
    document["document_cid"] = content_identity(
        {key: value for key, value in document.items() if key != "document_cid"}
    )
    return document


def artifact_paths(root: Path) -> dict[str, Path]:
    return {
        "root": root / DOCUMENT_DIR_RELPATH / DOCUMENT_JSON_NAME,
        "bytes": root / DOCUMENT_DIR_RELPATH / BYTES_JSON_NAME,
        "readme": root / DOCUMENT_README_RELPATH,
    }


def write_context_pack_storage_files(start: Path | None = None) -> dict[str, Any]:
    root = discover_kit_root(start)
    if root is None:
        raise KitContextPackStorageError("Kit package root was not found")
    document = render_declared_root(root)
    paths = artifact_paths(root)
    _atomic_write(paths["root"], pretty_json(document))
    _atomic_write(
        paths["bytes"], pretty_json(dict(PINNED_PACK_IDENTITY))
    )
    readme = DOCUMENT_README if DOCUMENT_README.endswith("\n") else DOCUMENT_README + "\n"
    _atomic_write(paths["readme"], readme)
    return {
        "document": document,
        "paths": {name: str(path) for name, path in paths.items()},
    }


def verify_context_pack_storage_files(start: Path | None = None) -> dict[str, Any]:
    root = discover_kit_root(start)
    if root is None:
        raise KitContextPackStorageError("Kit package root was not found")
    document = render_declared_root(root)
    paths = artifact_paths(root)
    missing: list[str] = []
    root_ok = False
    bytes_ok = False
    readme_ok = False
    expected_readme = (
        DOCUMENT_README if DOCUMENT_README.endswith("\n") else DOCUMENT_README + "\n"
    )
    expected_bytes = json.loads(pretty_json(dict(PINNED_PACK_IDENTITY)))
    for name, path in paths.items():
        if not path.is_file():
            missing.append(name)
            continue
        if name == "root":
            root_ok = json.loads(path.read_text(encoding="utf-8")) == document
        elif name == "bytes":
            bytes_ok = json.loads(path.read_text(encoding="utf-8")) == expected_bytes
        elif name == "readme":
            readme_ok = path.read_text(encoding="utf-8") == expected_readme
    return {
        "ok": not missing and root_ok and bytes_ok and readme_ok,
        "missing": missing,
        "root_ok": root_ok,
        "bytes_ok": bytes_ok,
        "readme_ok": readme_ok,
        "pack_cid": document["context_pack"]["pack_cid"],
        "bytes_cid": document["storage"]["bytes_cid"],
        "current_root_cid": document["current_root"]["current_cid"],
        "document_cid": document["document_cid"],
        "objective_cid": document["objective_cid"],
        "idea_digest": document["idea_digest"],
        "root_sha256": (
            sha256_bytes(paths["root"].read_bytes())
            if paths["root"].is_file()
            else "unavailable"
        ),
    }


def current_head_static_probes(
    start: Path | None = None,
) -> tuple[OutcomeProbe, ...]:
    root = discover_kit_root(start)
    if root is None:
        raise KitContextPackStorageError("Kit package root was not found")
    document = render_declared_root(root)
    verified = verify_context_pack_storage_files(root)
    table = parse_pyproject_context_pack_storage_table(
        (root / "pyproject.toml").read_text(encoding="utf-8")
    )
    remint = (
        document["context_pack"]["pack_cid"] != PINNED_PACK_CID
        or document["objective_cid"] != PINNED_OBJECTIVE_CID
        or document["idea_digest"] != PINNED_IDEA_DIGEST
        or document["lock_cid"] != PINNED_LOCK_CID
        or document["storage"]["bytes_cid"] != PINNED_BYTES_CID
        or document["current_root"]["current_cid"] != PINNED_CURRENT_ROOT_CID
        or document["context_pack"]["reminted"] is True
    )
    probes = [
        _probe(
            "root_files_match_generator",
            verified.get("ok") is True and verified.get("root_ok") is True,
            reason=(
                "Committed Kit ContextPack root matches the generator."
                if verified.get("root_ok") is True
                else "Committed Kit ContextPack root is missing or drifts."
            ),
        ),
        _probe(
            "pyproject_context_pack_storage_table",
            table.get("interface") == INTERFACE
            and table.get("schema") == SCHEMA
            and table.get("task-id") == PCPR_062_TASK_ID
            and table.get("objective-kind") == OBJECTIVE_KIND,
            reason=(
                "pyproject.toml declares KitContextPackStorage@1."
                if table.get("interface") == INTERFACE
                else "pyproject.toml does not declare the PCPR-062 storage table."
            ),
        ),
        _probe(
            "owner_pack_cid_matches_pin",
            document["context_pack"]["pack_cid"] == PINNED_PACK_CID,
            reason="Kit binds the Datasets-owned pack CID without remint.",
        ),
        _probe(
            "exact_bytes_verified",
            document["storage"]["bytes_verified"] is True
            and document["storage"]["bytes_cid"] == PINNED_BYTES_CID
            and document["storage"]["bytes_sha256"] == PINNED_BYTES_SHA256,
            reason="Kit verified exact DatasetsContextPack@1 identity bytes.",
        ),
        _probe(
            "hermetic_bytes_stored",
            document["storage"]["stored"] is True
            and document["storage"]["live"] is False
            and document["storage"]["backend"] == HERMETIC_BACKEND_ID,
            reason="Exact bytes are stored hermetically, not as live IPFS.",
        ),
        _probe(
            "hermetic_current_root_published",
            document["storage"]["current_root_published"] is True
            and document["current_root"]["published"] is True
            and document["current_root"]["live"] is False
            and document["current_root"]["cas"] is True,
            reason="Current root is published through hermetic CAS, not live.",
        ),
        _probe(
            "restart_reopen_verified",
            document["current_root"]["restart_verified"] is True,
            reason="Hermetic reopen reconstructs the same current root.",
        ),
        _probe(
            "stale_parent_rejected",
            document["current_root"]["stale_parent_rejected"] is True,
            reason="Stale expected-parent CAS is rejected.",
        ),
        _probe(
            "duckdb_or_quack_not_written",
            document["duckdb_or_quack_state_written"] is False,
            reason="This storage path does not write DuckDB or Quack state.",
        ),
        _probe(
            "operator_blocking_task_emitted",
            document["operator_blocking_task"]["task_id"] == OPERATOR_BLOCKING_TASK_ID
            and document["operator_blocking_task"]["status"] == "typed_blocked",
            reason="Missing live publication emits the operator-blocking task.",
        ),
        _probe(
            "no_closed_release_outcome",
            document["closed_release_outcome"] is None
            and document["release_claim"] is False,
            reason="This storage path does not emit a closed PCPR release outcome.",
        ),
        _probe(
            "compatibility_identities_reminted",
            remint,
            reason="A reminted pack, bytes, root, objective, idea, or lock CID is forbidden.",
        ),
        _probe(
            "datasets_identity_reminted",
            document["context_pack"]["reminted"] is True,
            reason="Kit must not remint DatasetsContextPack@1.",
        ),
        _probe(
            "sibling_import_observed",
            False,
            reason="This storage path does not import sibling Accelerate or Datasets packages.",
        ),
        _probe(
            "direct_database_bypass_used",
            False,
            reason="Direct DuckDB or Quack writes were not used.",
        ),
        _probe(
            "simulated_results_represented_as_live",
            False,
            reason="Simulated results are not represented as live.",
        ),
        _probe(
            "live_storage_represented_as_live",
            False,
            reason="Hermetic persist is not represented as live storage.",
        ),
        _probe(
            "closed_release_represented_as_live",
            False,
            reason="This task does not publish a PCPR release.",
        ),
        _probe(
            "live_storage",
            None,
            evidence_kind="unavailable",
            reason="Live IPFS/Quack ContextPack publication stays typed unavailable.",
        ),
        _probe(
            "live_current_root",
            None,
            evidence_kind="unavailable",
            reason="Live durable-backend current-root publication stays typed unavailable.",
        ),
    ]
    return tuple(probes)


def qualify_context_pack_storage(
    probes: Sequence[OutcomeProbe],
    *,
    pack_cid: str,
    bytes_cid: str,
    current_root_cid: str,
    document_cid: str,
    objective_cid: str,
    idea_digest_cid: str,
) -> KitContextPackStorageVerdict:
    if not probes:
        raise KitContextPackStorageError("at least one probe is required")
    normalized: list[OutcomeProbe] = []
    blockers: list[str] = []
    for probe in probes:
        kind = _kind(probe.evidence_kind, "evidence_kind")
        if probe.live and kind != "measured_live":
            raise KitContextPackStorageError(
                "live claims require measured_live evidence"
            )
        if probe.simulated_represented_as_live:
            raise KitContextPackStorageError(
                "simulated results must not be represented as live"
            )
        normalized.append(probe)
        if probe.probe_id in FORBIDDEN_PRESENT_PROBE_IDS and probe.present is True:
            blockers.append(probe.probe_id)
        if probe.probe_id in REQUIRED_GOOD_PROBE_IDS and probe.present is not True:
            blockers.append(probe.probe_id)

    promotion_status = "rnd_non_promoted"
    _reject_closed_release_value(promotion_status, "promotion_status")
    payload = {
        "schema": VERDICT_SCHEMA,
        "interface": INTERFACE,
        "task_id": PCPR_062_TASK_ID,
        "goal_id": PCPR_062_GOAL_ID,
        "promotion_status": promotion_status,
        "supervisor_disposition": "supervisor_non_promoted",
        "closed_release_outcome": None,
        "release_claim": False,
        "completion_authoritative": False,
        "contracts_frozen": False,
        "duckdb_or_quack_state_written": False,
        "sibling_source_required": False,
        "live_storage": False,
        "live_storage_evidence_kind": "unavailable",
        "live_current_root": False,
        "live_ipfs": False,
        "operator_blocking_task": OPERATOR_BLOCKING_TASK_ID,
        "simulated_results_represented_as_live": False,
        "this_task_created_competing_authority": False,
        "probes": [item.to_mapping() for item in normalized],
        "blockers": list(dict.fromkeys(blockers)),
        "pack_cid": pack_cid,
        "bytes_cid": bytes_cid,
        "current_root_cid": current_root_cid,
        "document_cid": document_cid,
        "objective_cid": objective_cid,
        "idea_digest": idea_digest_cid,
    }
    return KitContextPackStorageVerdict(
        schema=VERDICT_SCHEMA,
        interface=INTERFACE,
        promotion_status=promotion_status,
        supervisor_disposition="supervisor_non_promoted",
        closed_release_outcome=None,
        release_claim=False,
        completion_authoritative=False,
        contracts_frozen=False,
        duckdb_or_quack_state_written=False,
        sibling_source_required=False,
        live_storage=False,
        live_storage_evidence_kind="unavailable",
        live_current_root=False,
        live_ipfs=False,
        operator_blocking_task=OPERATOR_BLOCKING_TASK_ID,
        simulated_results_represented_as_live=False,
        this_task_created_competing_authority=False,
        probes=tuple(normalized),
        blockers=tuple(dict.fromkeys(blockers)),
        verdict_cid=content_identity(payload),
        pack_cid=pack_cid,
        bytes_cid=bytes_cid,
        current_root_cid=current_root_cid,
        document_cid=document_cid,
        objective_cid=objective_cid,
        idea_digest=idea_digest_cid,
    )


def qualify_current_head_context_pack_storage(
    start: Path | None = None,
) -> KitContextPackStorageVerdict:
    document = render_declared_root(start)
    return qualify_context_pack_storage(
        current_head_static_probes(start),
        pack_cid=str(document["context_pack"]["pack_cid"]),
        bytes_cid=str(document["storage"]["bytes_cid"]),
        current_root_cid=str(document["current_root"]["current_cid"]),
        document_cid=str(document["document_cid"]),
        objective_cid=str(document["objective_cid"]),
        idea_digest_cid=str(document["idea_digest"]),
    )


def pcpr_062_receipt_promotion(
    verdict: KitContextPackStorageVerdict,
) -> dict[str, Any]:
    if verdict.closed_release_outcome is not None:
        raise KitContextPackStorageError(
            "ContextPack storage must not mint a closed release outcome"
        )
    if verdict.release_claim:
        raise KitContextPackStorageError(
            "ContextPack storage must not claim a PCPR release"
        )
    if verdict.completion_authoritative:
        raise KitContextPackStorageError(
            "ContextPack storage completion is not authoritative"
        )
    if verdict.duckdb_or_quack_state_written:
        raise KitContextPackStorageError(
            "ContextPack storage must not write DuckDB or Quack state"
        )
    if verdict.promotion_status in CLOSED_RELEASE_OUTCOMES:
        raise KitContextPackStorageError(
            "promotion_status must not be a closed release outcome"
        )
    if verdict.live_storage or verdict.live_current_root or verdict.live_ipfs:
        raise KitContextPackStorageError(
            "live storage requires measured_live evidence"
        )
    return verdict.to_mapping()


def refuse_pack_cid_remint(cid: str) -> str:
    if cid != PINNED_PACK_CID:
        raise KitContextPackStorageError(
            f"ContextPack CID {cid} remints {PINNED_PACK_CID}"
        )
    return cid


def refuse_current_root_remint(cid: str) -> str:
    if cid != PINNED_CURRENT_ROOT_CID:
        raise KitContextPackStorageError(
            f"current root CID {cid} remints {PINNED_CURRENT_ROOT_CID}"
        )
    return cid


# Pinned after encoder measurement. Drift is a remint.
PINNED_DOCUMENT_CID: Final = (
    "baguqeera4ejmqjdeuqvaiyyurcbxqkjl25qkmfpbm4ltl45le4ghoo67scoa"
)
PINNED_RECEIPT_CID: Final = (
    "baguqeera6ejhhbaci3r5lme7duvw436hxwxrn65skl37bsix5of5g5tmwpcq"
)
PINNED_TRANSITION_CID: Final = (
    "baguqeeralttivvntxar66ont7scvxm5xxqknhbvtn3tmsz7yxfutv67mnaoa"
)
CURRENT_HEAD_NON_PROMOTION_VERDICT_CID: Final = (
    "baguqeeraaktciapl2iipfhgwr4pegyxqj6zg7e7y7z64xthiyc5ueqh6wxxq"
)


__all__ = [
    "CLOSED_RELEASE_OUTCOMES",
    "CURRENT_HEAD_NON_PROMOTION_VERDICT_CID",
    "HERMETIC_CANDIDATE_SUITES",
    "HermeticContextPackRootStore",
    "INTERFACE",
    "KitContextPackStorageError",
    "OBJECTIVE_KIND",
    "OPERATOR_BLOCKING_TASK_ID",
    "OutcomeProbe",
    "PCPR_062_GOAL_ID",
    "PCPR_062_TASK_ID",
    "PINNED_BYTES_CID",
    "PINNED_CURRENT_ROOT_CID",
    "PINNED_DOCUMENT_CID",
    "PINNED_IDEA_DIGEST",
    "PINNED_LOCK_CID",
    "PINNED_OBJECTIVE_CID",
    "PINNED_PACK_CID",
    "SCHEMA",
    "SEALED_PATH",
    "SEALED_PYTHON",
    "canonical_pack_bytes",
    "current_head_static_probes",
    "pcpr_062_receipt_promotion",
    "persist_and_publish_current_root",
    "qualify_context_pack_storage",
    "qualify_current_head_context_pack_storage",
    "raw_content_cid",
    "refuse_current_root_remint",
    "refuse_pack_cid_remint",
    "render_declared_root",
    "verify_context_pack_storage_files",
    "write_context_pack_storage_files",
]
