"""Repository/branch current-seal compare-and-swap (IPS-023).

Kit storage authority for the namespaced current-seal pointer.  A seal becomes
current only through expected-parent compare-and-swap under exclusive
process/thread fencing.  Kit never decides proof validity.

Fail-closed guarantees:

* repository and branch form the pointer namespace;
* CAS binds expected parent seal, generation, and branch;
* stale concurrent writers never overwrite the current pointer;
* wrong branch / parent / generation is rejected;
* every read rehashes durable pointer bytes against the stored digest;
* writes are published atomically after file and parent-directory fsync;
* construction requires an explicit store root (no daemon/home default).

Interfaces: ``CurrentSealRepository``, ``compare_and_swap_current_seal``.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
import threading
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Final, Iterator

from ipfs_kit_py.proof_seal_store.contracts import (
    CurrentSealPointer,
    ExplicitRootRequiredError,
    ProofSealStoreContractError,
    SealTransitionError,
    StoreRoot,
    validate_explicit_root_path,
)

EVIDENCE_SUBSET: Final[str] = "ips/current-seal-cas@1"
POINTER_STORE_SCHEMA: Final[str] = "ipfs_kit_py/proof_seal_store/pointer@1"
POINTER_STORE_INTERFACE: Final[str] = "CurrentSealRepository@1"
POINTER_ENVELOPE_SCHEMA: Final[str] = (
    "ipfs_kit_py/proof_seal_store/current-seal-pointer-envelope@1"
)
CONTRACT_VERSION: Final[int] = 1

_POINTERS_DIR: Final[str] = "current_seals"
_LOCKS_DIR: Final[str] = "locks"
_POINTER_SUFFIX: Final[str] = ".json"
_LOCK_SUFFIX: Final[str] = ".lock"
_MAX_RECORD_BYTES: Final[int] = 256 * 1024
_HEX64_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")

_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class PointerDisposition(str, Enum):
    """Closed outcomes for current-seal pointer operations."""

    HIT = "hit"
    MISS = "miss"
    SWAPPED = "swapped"
    REJECTED = "rejected"
    STALE = "stale"
    ERROR = "error"


class PointerReason(str, Enum):
    """Closed diagnostic reasons for pointer CAS outcomes."""

    OK = "ok"
    NOT_FOUND = "not_found"
    STALE_PARENT = "stale_parent"
    BRANCH_MISMATCH = "branch_mismatch"
    PARENT_MISMATCH = "parent_mismatch"
    GENERATION_MISMATCH = "generation_mismatch"
    NAMESPACE_MISMATCH = "namespace_mismatch"
    MALFORMED = "malformed"
    CORRUPTED = "corrupted"
    INTEGRITY_FAILED = "integrity_failed"
    OVER_BUDGET = "over_budget"
    SHORT_WRITE = "short_write"
    FSYNC_FAILED = "fsync_failed"
    READBACK_FAILED = "readback_failed"
    SYMLINK_REJECTED = "symlink_rejected"
    PATH_ESCAPE = "path_escape"
    IO_ERROR = "io_error"
    LOCK_FAILED = "lock_failed"


# ---------------------------------------------------------------------------
# Errors / results
# ---------------------------------------------------------------------------


class PointerStoreError(ProofSealStoreContractError):
    """A current-seal pointer operation failed closed."""

    def __init__(
        self,
        message: str,
        *,
        reason: PointerReason = PointerReason.IO_ERROR,
        disposition: PointerDisposition | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.disposition = disposition


class PointerIntegrityError(PointerStoreError):
    """Pointer bytes failed rehash or envelope integrity checks."""


class PointerCasRejected(PointerStoreError):
    """CAS rejected for wrong branch, parent, generation, or namespace."""


@dataclass(frozen=True)
class PointerCasResult:
    """Structured outcome of a compare-and-swap attempt."""

    disposition: PointerDisposition
    reason: PointerReason
    pointer: CurrentSealPointer | None = None
    current: CurrentSealPointer | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.disposition is PointerDisposition.SWAPPED

    @property
    def swapped(self) -> bool:
        return bool(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def payload_digest_hex(data: bytes) -> str:
    """Return the lowercase sha2-256 hex digest of exact pointer bytes."""

    if type(data) is not bytes:
        raise PointerStoreError(
            "pointer payload must be exact bytes",
            reason=PointerReason.MALFORMED,
            disposition=PointerDisposition.REJECTED,
        )
    return hashlib.sha256(data).hexdigest()


def namespace_key(repository_id: str, branch_id: str) -> str:
    """Return the canonical repository/branch namespace key."""

    if type(repository_id) is not str or not repository_id.strip():
        raise ProofSealStoreContractError("repository_id must be a non-empty string")
    if type(branch_id) is not str or not branch_id.strip():
        raise ProofSealStoreContractError("branch_id must be a non-empty string")
    if repository_id.strip() != repository_id or branch_id.strip() != branch_id:
        raise ProofSealStoreContractError(
            "repository_id and branch_id must not have surrounding whitespace"
        )
    return f"{repository_id}#{branch_id}"


def namespace_digest(repository_id: str, branch_id: str) -> str:
    """Return the sha2-256 hex digest binding a repository/branch namespace."""

    key = namespace_key(repository_id, branch_id)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def pointer_payload_bytes(pointer: CurrentSealPointer) -> bytes:
    """Return canonical bytes of a current-seal pointer for rehash binding."""

    if not isinstance(pointer, CurrentSealPointer):
        raise ProofSealStoreContractError("pointer must be a CurrentSealPointer")
    return _canonical_json_bytes(pointer.to_dict())


def _pointers_match(
    left: CurrentSealPointer | None, right: CurrentSealPointer | None
) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return (
        left.repository_id == right.repository_id
        and left.branch_id == right.branch_id
        and left.seal_cid == right.seal_cid
        and left.seal_kind == right.seal_kind
        and left.generation == right.generation
        and left.parent_seal_cid == right.parent_seal_cid
        and left.role == right.role
        and left.schema == right.schema
        and left.contract_version == right.contract_version
    )


def _validate_cas_chain(
    expected: CurrentSealPointer | None,
    new_pointer: CurrentSealPointer,
) -> None:
    """Reject wrong branch/parent/generation between expected and candidate."""

    if expected is None:
        if new_pointer.parent_seal_cid:
            raise PointerCasRejected(
                "genesis CAS requires empty parent_seal_cid",
                reason=PointerReason.PARENT_MISMATCH,
                disposition=PointerDisposition.REJECTED,
            )
        return

    if (
        expected.repository_id != new_pointer.repository_id
        or expected.branch_id != new_pointer.branch_id
    ):
        raise PointerCasRejected(
            "CAS expected and new_pointer must share repository/branch namespace",
            reason=PointerReason.BRANCH_MISMATCH,
            disposition=PointerDisposition.REJECTED,
        )

    if new_pointer.parent_seal_cid != expected.seal_cid:
        raise PointerCasRejected(
            "new_pointer.parent_seal_cid must equal expected.seal_cid",
            reason=PointerReason.PARENT_MISMATCH,
            disposition=PointerDisposition.REJECTED,
        )

    if new_pointer.generation != expected.generation + 1:
        raise PointerCasRejected(
            "new_pointer.generation must be expected.generation + 1",
            reason=PointerReason.GENERATION_MISMATCH,
            disposition=PointerDisposition.REJECTED,
        )


# ---------------------------------------------------------------------------
# On-disk envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _PointerEnvelope:
    """Durable on-disk envelope binding rehashed current-seal pointer bytes."""

    namespace_key: str
    namespace_digest: str
    payload_digest: str
    pointer: CurrentSealPointer
    schema: str = POINTER_ENVELOPE_SCHEMA
    contract_version: int = CONTRACT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "contract_version": self.contract_version,
            "namespace_key": self.namespace_key,
            "namespace_digest": self.namespace_digest,
            "payload_digest": self.payload_digest,
            "pointer": self.pointer.to_dict(),
        }

    @classmethod
    def from_pointer(cls, pointer: CurrentSealPointer) -> _PointerEnvelope:
        key = pointer.namespace_key
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        payload = pointer_payload_bytes(pointer)
        return cls(
            namespace_key=key,
            namespace_digest=digest,
            payload_digest=payload_digest_hex(payload),
            pointer=pointer,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> _PointerEnvelope:
        if not isinstance(payload, Mapping):
            raise PointerIntegrityError(
                "pointer envelope must be a JSON object",
                reason=PointerReason.CORRUPTED,
                disposition=PointerDisposition.ERROR,
            )
        if payload.get("schema", POINTER_ENVELOPE_SCHEMA) != POINTER_ENVELOPE_SCHEMA:
            raise PointerIntegrityError(
                "pointer envelope schema mismatch",
                reason=PointerReason.CORRUPTED,
                disposition=PointerDisposition.ERROR,
            )
        contract_version = payload.get("contract_version", CONTRACT_VERSION)
        if isinstance(contract_version, bool) or not isinstance(contract_version, int):
            raise PointerIntegrityError(
                "pointer envelope contract_version must be an integer",
                reason=PointerReason.CORRUPTED,
                disposition=PointerDisposition.ERROR,
            )
        if contract_version != CONTRACT_VERSION:
            raise PointerIntegrityError(
                "pointer envelope contract_version mismatch",
                reason=PointerReason.CORRUPTED,
                disposition=PointerDisposition.ERROR,
            )

        ns_key = payload.get("namespace_key")
        if type(ns_key) is not str or not ns_key or "#" not in ns_key:
            raise PointerIntegrityError(
                "pointer envelope namespace_key is malformed",
                reason=PointerReason.CORRUPTED,
                disposition=PointerDisposition.ERROR,
            )
        ns_digest = payload.get("namespace_digest")
        if type(ns_digest) is not str or not _HEX64_RE.fullmatch(ns_digest):
            raise PointerIntegrityError(
                "pointer envelope namespace_digest must be 64 lowercase hex characters",
                reason=PointerReason.CORRUPTED,
                disposition=PointerDisposition.ERROR,
            )
        if ns_digest != hashlib.sha256(ns_key.encode("utf-8")).hexdigest():
            raise PointerIntegrityError(
                "namespace_digest does not bind namespace_key",
                reason=PointerReason.INTEGRITY_FAILED,
                disposition=PointerDisposition.ERROR,
            )

        payload_digest = payload.get("payload_digest")
        if type(payload_digest) is not str or not _HEX64_RE.fullmatch(payload_digest):
            raise PointerIntegrityError(
                "payload_digest must be 64 lowercase hex characters",
                reason=PointerReason.CORRUPTED,
                disposition=PointerDisposition.ERROR,
            )

        pointer_payload = payload.get("pointer")
        if not isinstance(pointer_payload, Mapping):
            raise PointerIntegrityError(
                "pointer envelope requires a pointer object",
                reason=PointerReason.CORRUPTED,
                disposition=PointerDisposition.ERROR,
            )
        try:
            pointer = CurrentSealPointer.from_dict(pointer_payload)
        except (
            ProofSealStoreContractError,
            SealTransitionError,
            TypeError,
            ValueError,
        ) as exc:
            raise PointerIntegrityError(
                f"pointer envelope pointer is malformed: {exc}",
                reason=PointerReason.CORRUPTED,
                disposition=PointerDisposition.ERROR,
            ) from exc

        if pointer.namespace_key != ns_key:
            raise PointerIntegrityError(
                "pointer repository/branch does not match envelope namespace_key",
                reason=PointerReason.NAMESPACE_MISMATCH,
                disposition=PointerDisposition.ERROR,
            )

        recomputed = payload_digest_hex(pointer_payload_bytes(pointer))
        if recomputed != payload_digest:
            raise PointerIntegrityError(
                "pointer bytes failed rehash against payload_digest",
                reason=PointerReason.INTEGRITY_FAILED,
                disposition=PointerDisposition.ERROR,
            )

        return cls(
            namespace_key=ns_key,
            namespace_digest=ns_digest,
            payload_digest=payload_digest,
            pointer=pointer,
            schema=POINTER_ENVELOPE_SCHEMA,
            contract_version=CONTRACT_VERSION,
        )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class CurrentSealRepository:
    """Repository/branch-namespaced current-seal pointer CAS store.

    Construction requires an explicit :class:`StoreRoot`.  There is no default
    under ``~``, ``$XDG_*``, ``~/.ipfs``, or any daemon path.
    """

    __test__ = False

    def __init__(
        self,
        root: StoreRoot | str | Path | os.PathLike[str] | None,
        *,
        create: bool = True,
    ) -> None:
        if root is None:
            raise ExplicitRootRequiredError(
                "CurrentSealRepository requires an explicit StoreRoot; "
                "no default user-state or daemon root exists"
            )
        if isinstance(root, StoreRoot):
            store_root = root
        else:
            store_root = StoreRoot.require(root)
        validate_explicit_root_path(store_root.root_path, field_name="root_path")

        self._root = store_root
        self._root_path = Path(store_root.root_path)
        self._lock = _thread_lock(self._root_path)

        if self._root_path.exists() and self._root_path.is_symlink():
            raise PointerStoreError(
                "store root must not be a symlink",
                reason=PointerReason.SYMLINK_REJECTED,
                disposition=PointerDisposition.ERROR,
            )
        if create:
            self._ensure_root()

    # -- protocol surface ---------------------------------------------------

    @property
    def root(self) -> StoreRoot:
        """Return the mandatory explicit store root."""

        return self._root

    @property
    def root_path(self) -> Path:
        return self._root_path

    def get_current_seal(
        self, repository_id: str, branch_id: str
    ) -> CurrentSealPointer | None:
        """Read and rehash the repository/branch current-seal pointer."""

        key = namespace_key(repository_id, branch_id)
        digest = namespace_digest(repository_id, branch_id)
        with self._lock:
            with self._namespace_lock(digest):
                envelope = self._read_envelope(digest, expected_namespace=key)
                if envelope is None:
                    return None
                return envelope.pointer

    def compare_and_swap_current_seal(
        self,
        expected: CurrentSealPointer | None,
        new_pointer: CurrentSealPointer,
    ) -> bool:
        """CAS-publish ``new_pointer`` only when ``expected`` still holds.

        Returns ``True`` when exactly this writer published the pointer.
        Returns ``False`` when the on-disk current pointer no longer matches
        ``expected`` (stale concurrent writer / wrong parent generation).
        Wrong branch/parent/generation between ``expected`` and ``new_pointer``
        raises :class:`PointerCasRejected`.
        """

        return self.compare_and_swap_current_seal_result(expected, new_pointer).swapped

    def compare_and_swap_current_seal_result(
        self,
        expected: CurrentSealPointer | None,
        new_pointer: CurrentSealPointer,
    ) -> PointerCasResult:
        """Result-oriented CAS with closed disposition/reason codes."""

        if not isinstance(new_pointer, CurrentSealPointer):
            raise ProofSealStoreContractError("new_pointer must be a CurrentSealPointer")
        if expected is not None and not isinstance(expected, CurrentSealPointer):
            raise ProofSealStoreContractError(
                "expected must be CurrentSealPointer or None"
            )

        _validate_cas_chain(expected, new_pointer)

        digest = namespace_digest(new_pointer.repository_id, new_pointer.branch_id)
        key = new_pointer.namespace_key

        with self._lock:
            with self._namespace_lock(digest):
                # Integrity/corruption failures raise; only I/O/durability
                # faults become structured ERROR results.
                try:
                    current_envelope = self._read_envelope(
                        digest, expected_namespace=key
                    )
                except PointerIntegrityError:
                    raise
                except PointerStoreError as exc:
                    return PointerCasResult(
                        PointerDisposition.ERROR,
                        exc.reason,
                        current=None,
                        diagnostics={"error": str(exc)},
                    )

                current = (
                    None if current_envelope is None else current_envelope.pointer
                )

                if not _pointers_match(current, expected):
                    # Concurrent winner already advanced the pointer, or the
                    # caller's expected parent/generation/branch is stale.
                    # Plan recovery vocabulary: stale_parent for any lost CAS.
                    diagnostics: dict[str, Any] = {}
                    if current is not None and expected is not None:
                        if (
                            current.repository_id != expected.repository_id
                            or current.branch_id != expected.branch_id
                        ):
                            diagnostics["detail"] = PointerReason.BRANCH_MISMATCH.value
                        elif current.generation != expected.generation:
                            diagnostics["detail"] = (
                                PointerReason.GENERATION_MISMATCH.value
                            )
                        elif current.seal_cid != expected.seal_cid:
                            diagnostics["detail"] = PointerReason.PARENT_MISMATCH.value
                    return PointerCasResult(
                        PointerDisposition.STALE,
                        PointerReason.STALE_PARENT,
                        pointer=new_pointer,
                        current=current,
                        diagnostics=diagnostics,
                    )

                envelope = _PointerEnvelope.from_pointer(new_pointer)
                try:
                    self._atomic_write_envelope(digest, envelope)
                except PointerStoreError as exc:
                    return PointerCasResult(
                        PointerDisposition.ERROR,
                        exc.reason,
                        pointer=new_pointer,
                        current=current,
                        diagnostics={"error": str(exc)},
                    )

                # Mandatory readback rehash after publication.
                try:
                    readback = self._read_envelope(digest, expected_namespace=key)
                except PointerStoreError as exc:
                    try:
                        path = self._pointer_path(digest)
                        if path.exists() and not path.is_symlink():
                            os.unlink(path)
                    except OSError:
                        pass
                    return PointerCasResult(
                        PointerDisposition.ERROR,
                        PointerReason.READBACK_FAILED
                        if exc.reason is PointerReason.INTEGRITY_FAILED
                        else exc.reason,
                        pointer=new_pointer,
                        current=current,
                        diagnostics={"error": str(exc)},
                    )

                if readback is None or not _pointers_match(
                    readback.pointer, new_pointer
                ):
                    try:
                        path = self._pointer_path(digest)
                        if path.exists() and not path.is_symlink():
                            os.unlink(path)
                    except OSError:
                        pass
                    return PointerCasResult(
                        PointerDisposition.ERROR,
                        PointerReason.READBACK_FAILED,
                        pointer=new_pointer,
                        current=current,
                    )

                return PointerCasResult(
                    PointerDisposition.SWAPPED,
                    PointerReason.OK,
                    pointer=new_pointer,
                    current=new_pointer,
                )

    # -- paths / durability -------------------------------------------------

    def _ensure_root(self) -> None:
        self._root_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        pointers = self._root_path / _POINTERS_DIR
        locks = pointers / _LOCKS_DIR
        pointers.mkdir(parents=True, exist_ok=True, mode=0o700)
        locks.mkdir(parents=True, exist_ok=True, mode=0o700)
        for path in (self._root_path, pointers, locks):
            if path.is_symlink():
                raise PointerStoreError(
                    "pointer store path must not be a symlink",
                    reason=PointerReason.SYMLINK_REJECTED,
                    disposition=PointerDisposition.ERROR,
                )

    def _pointer_path(self, digest: str) -> Path:
        if not _HEX64_RE.fullmatch(digest):
            raise PointerStoreError(
                "namespace digest is not filesystem-safe",
                reason=PointerReason.PATH_ESCAPE,
                disposition=PointerDisposition.ERROR,
            )
        return self._root_path / _POINTERS_DIR / f"{digest}{_POINTER_SUFFIX}"

    def _lock_path(self, digest: str) -> Path:
        if not _HEX64_RE.fullmatch(digest):
            raise PointerStoreError(
                "namespace digest is not filesystem-safe",
                reason=PointerReason.PATH_ESCAPE,
                disposition=PointerDisposition.ERROR,
            )
        return (
            self._root_path
            / _POINTERS_DIR
            / _LOCKS_DIR
            / f"{digest}{_LOCK_SUFFIX}"
        )

    @contextmanager
    def _namespace_lock(self, digest: str) -> Iterator[None]:
        """Exclusive process fence for one repository/branch namespace."""

        path = self._lock_path(digest)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.parent.is_symlink() or (path.exists() and path.is_symlink()):
            raise PointerStoreError(
                "pointer lock path must not be a symlink",
                reason=PointerReason.SYMLINK_REJECTED,
                disposition=PointerDisposition.ERROR,
            )
        try:
            fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
        except OSError as exc:
            raise PointerStoreError(
                f"unable to open pointer lock: {exc}",
                reason=PointerReason.LOCK_FAILED,
                disposition=PointerDisposition.ERROR,
            ) from exc
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
            except OSError as exc:
                raise PointerStoreError(
                    f"unable to acquire pointer lock: {exc}",
                    reason=PointerReason.LOCK_FAILED,
                    disposition=PointerDisposition.ERROR,
                ) from exc
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(fd)
            except OSError:
                pass

    def _read_envelope(
        self,
        digest: str,
        *,
        expected_namespace: str,
    ) -> _PointerEnvelope | None:
        path = self._pointer_path(digest)
        if not path.exists():
            return None
        if path.is_symlink():
            raise PointerIntegrityError(
                "pointer path is a symlink",
                reason=PointerReason.SYMLINK_REJECTED,
                disposition=PointerDisposition.ERROR,
            )
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise PointerStoreError(
                f"unable to read pointer envelope: {exc}",
                reason=PointerReason.IO_ERROR,
                disposition=PointerDisposition.ERROR,
            ) from exc
        if len(data) > _MAX_RECORD_BYTES:
            raise PointerIntegrityError(
                "pointer envelope exceeds byte budget",
                reason=PointerReason.OVER_BUDGET,
                disposition=PointerDisposition.ERROR,
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PointerIntegrityError(
                "pointer envelope is not UTF-8",
                reason=PointerReason.CORRUPTED,
                disposition=PointerDisposition.ERROR,
            ) from exc
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PointerIntegrityError(
                "pointer envelope is not valid JSON",
                reason=PointerReason.CORRUPTED,
                disposition=PointerDisposition.ERROR,
            ) from exc

        envelope = _PointerEnvelope.from_dict(payload)
        if envelope.namespace_digest != digest:
            raise PointerIntegrityError(
                "pointer path digest does not match envelope namespace_digest",
                reason=PointerReason.INTEGRITY_FAILED,
                disposition=PointerDisposition.ERROR,
            )
        if envelope.namespace_key != expected_namespace:
            raise PointerIntegrityError(
                "pointer envelope namespace does not match requested repository/branch",
                reason=PointerReason.NAMESPACE_MISMATCH,
                disposition=PointerDisposition.ERROR,
            )

        # Rehash the on-disk envelope bytes against the canonical serialization
        # of the envelope's pointer binding (payload_digest already checked).
        recomputed_payload = payload_digest_hex(
            pointer_payload_bytes(envelope.pointer)
        )
        if recomputed_payload != envelope.payload_digest:
            raise PointerIntegrityError(
                "pointer bytes failed rehash on read",
                reason=PointerReason.INTEGRITY_FAILED,
                disposition=PointerDisposition.ERROR,
            )
        return envelope

    def _atomic_write_envelope(self, digest: str, envelope: _PointerEnvelope) -> None:
        data = _canonical_json_bytes(envelope.to_dict())
        if len(data) > _MAX_RECORD_BYTES:
            raise PointerStoreError(
                "pointer envelope exceeds byte budget",
                reason=PointerReason.OVER_BUDGET,
                disposition=PointerDisposition.REJECTED,
            )
        path = self._pointer_path(digest)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.parent.is_symlink():
            raise PointerStoreError(
                "pointer parent directory must not be a symlink",
                reason=PointerReason.SYMLINK_REJECTED,
                disposition=PointerDisposition.ERROR,
            )

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
                    raise PointerStoreError(
                        f"short write: wrote {written} of {len(data)} bytes",
                        reason=PointerReason.SHORT_WRITE,
                        disposition=PointerDisposition.ERROR,
                    )
                stream.flush()
                try:
                    os.fsync(stream.fileno())
                except OSError as exc:
                    raise PointerStoreError(
                        f"fsync of pointer file failed: {exc}",
                        reason=PointerReason.FSYNC_FAILED,
                        disposition=PointerDisposition.ERROR,
                    ) from exc
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, path)
            temporary_name = ""

            try:
                dir_fd = os.open(path.parent, os.O_RDONLY)
            except OSError as exc:
                try:
                    os.unlink(path)
                except OSError:
                    pass
                raise PointerStoreError(
                    f"unable to open parent directory for fsync: {exc}",
                    reason=PointerReason.FSYNC_FAILED,
                    disposition=PointerDisposition.ERROR,
                ) from exc
            try:
                try:
                    os.fsync(dir_fd)
                except OSError as exc:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                    raise PointerStoreError(
                        f"fsync of parent directory failed: {exc}",
                        reason=PointerReason.FSYNC_FAILED,
                        disposition=PointerDisposition.ERROR,
                    ) from exc
            finally:
                os.close(dir_fd)
        except PointerStoreError:
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
        except OSError as exc:
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
            raise PointerStoreError(
                f"pointer write failed: {exc}",
                reason=PointerReason.IO_ERROR,
                disposition=PointerDisposition.ERROR,
            ) from exc


# ---------------------------------------------------------------------------
# Module-level interface
# ---------------------------------------------------------------------------


def get_current_seal(
    repository: CurrentSealRepository,
    repository_id: str,
    branch_id: str,
) -> CurrentSealPointer | None:
    """Read the current seal through ``repository``."""

    if not isinstance(repository, CurrentSealRepository):
        raise ProofSealStoreContractError(
            "repository must be a CurrentSealRepository"
        )
    return repository.get_current_seal(repository_id, branch_id)


def compare_and_swap_current_seal(
    repository: CurrentSealRepository,
    expected: CurrentSealPointer | None,
    new_pointer: CurrentSealPointer,
) -> bool:
    """CAS-publish a current seal through ``repository``."""

    if not isinstance(repository, CurrentSealRepository):
        raise ProofSealStoreContractError(
            "repository must be a CurrentSealRepository"
        )
    return repository.compare_and_swap_current_seal(expected, new_pointer)


__all__ = (
    "CONTRACT_VERSION",
    "EVIDENCE_SUBSET",
    "POINTER_ENVELOPE_SCHEMA",
    "POINTER_STORE_INTERFACE",
    "POINTER_STORE_SCHEMA",
    "CurrentSealRepository",
    "PointerCasRejected",
    "PointerCasResult",
    "PointerDisposition",
    "PointerIntegrityError",
    "PointerReason",
    "PointerStoreError",
    "compare_and_swap_current_seal",
    "get_current_seal",
    "namespace_digest",
    "namespace_key",
    "payload_digest_hex",
    "pointer_payload_bytes",
)
