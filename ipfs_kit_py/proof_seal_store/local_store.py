"""Hermetic immutable local proof-object store (IPS-019).

Persists closed-kind proof-seal artifact bytes under an explicit store root.
No default user-state path, no daemon, and no network are used.

Fail-closed guarantees:

* every put rehashes bytes against the content identity (CID or ``sha256:``);
* every get rehashes on read and rejects kind/CID/byte mismatches;
* writes are published atomically after file and parent-directory fsync;
* short writes, fsync failure, and readback mismatch abort without admitting;
* symlink substitution and path escape are rejected;
* identical (kind, bytes) puts deduplicate to the existing admitted reference.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Final

from ipfs_kit_py.proof_certificate_store import (
    CertificateTransportError,
    cid_for_certificate_bytes,
    decode_certificate_cid,
)
from ipfs_kit_py.proof_seal_store.contracts import (
    DEFAULT_MAX_ARTIFACT_BYTES,
    MAX_ARTIFACT_BYTES_BOUND,
    ArtifactKind,
    ArtifactKindError,
    ArtifactReference,
    CacheCandidate,
    CurrentSealPointer,
    ExplicitRootRequiredError,
    ForbiddenArtifactError,
    ProofSealStoreContractError,
    SealTransitionRecord,
    StoreGetDisposition,
    StorePutDisposition,
    StoreRoot,
    coerce_artifact_kind,
    validate_explicit_root_path,
)

EVIDENCE_SUBSET: Final[str] = "ips/local-proof-store@1"
LOCAL_STORE_SCHEMA: Final[str] = "ipfs_kit_py/proof_seal_store/local-store@1"
LOCAL_STORE_INTERFACE: Final[str] = "HermeticProofSealStore@1"

_OBJECTS_DIR: Final[str] = "objects"
_BLOB_SUFFIX: Final[str] = ".blob"
_SHA256_CID_RE: Final[re.Pattern[str]] = re.compile(r"^sha256:([0-9a-f]{64})$")
_SAFE_CID_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._+\-]+$")

_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


# ---------------------------------------------------------------------------
# Errors / closed reason codes
# ---------------------------------------------------------------------------


class LocalStoreReason(str, Enum):
    """Closed diagnostic reasons for hermetic local store outcomes."""

    OK = "ok"
    ALREADY_EXISTS = "already_exists"
    NOT_FOUND = "not_found"
    MALFORMED = "malformed"
    OVER_BUDGET = "over_budget"
    CID_MISMATCH = "cid_mismatch"
    KIND_MISMATCH = "kind_mismatch"
    INTEGRITY_FAILED = "integrity_failed"
    CORRUPTED = "corrupted"
    SYMLINK_REJECTED = "symlink_rejected"
    PATH_ESCAPE = "path_escape"
    SHORT_WRITE = "short_write"
    FSYNC_FAILED = "fsync_failed"
    READBACK_FAILED = "readback_failed"
    IO_ERROR = "io_error"
    FORBIDDEN_KIND = "forbidden_kind"
    UNSUPPORTED = "unsupported"


class LocalStoreError(ProofSealStoreContractError):
    """A hermetic local store operation failed closed."""

    def __init__(
        self,
        message: str,
        *,
        reason: LocalStoreReason = LocalStoreReason.IO_ERROR,
        disposition: StorePutDisposition | StoreGetDisposition | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.disposition = disposition


class LocalStoreIntegrityError(LocalStoreError):
    """CID, kind, or byte integrity verification failed."""


class LocalStorePathError(LocalStoreError):
    """Path escape or symlink fencing rejected the operation."""


class LocalStoreDurabilityError(LocalStoreError):
    """Short write, fsync, or readback durability check failed."""


class LocalStoreNotFoundError(LocalStoreError):
    """Requested admitted object is absent."""


class LocalStoreUnsupportedError(LocalStoreError):
    """Operation is outside the hermetic object-store surface."""


# ---------------------------------------------------------------------------
# Result records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LocalPutResult:
    """Outcome of an immutable put attempt."""

    disposition: StorePutDisposition
    reason: LocalStoreReason
    reference: ArtifactReference | None = None
    cid: str = ""
    byte_length: int = 0
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.disposition in {
            StorePutDisposition.STORED,
            StorePutDisposition.ALREADY_EXISTS,
        }

    @property
    def stored(self) -> bool:
        return bool(self)


@dataclass(frozen=True)
class LocalGetResult:
    """Outcome of a verified get attempt."""

    disposition: StoreGetDisposition
    reason: LocalStoreReason
    data: bytes | None = None
    reference: ArtifactReference | None = None
    byte_length: int = 0
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.disposition is StoreGetDisposition.HIT and self.data is not None

    @property
    def hit(self) -> bool:
        return bool(self)


# ---------------------------------------------------------------------------
# Content identity helpers
# ---------------------------------------------------------------------------


def content_digest_hex(data: bytes) -> str:
    """Return the lowercase sha2-256 hex digest of exact ``data``."""

    if type(data) is not bytes:
        raise LocalStoreError(
            "artifact payload must be exact bytes",
            reason=LocalStoreReason.MALFORMED,
            disposition=StorePutDisposition.REJECTED,
        )
    return hashlib.sha256(data).hexdigest()


def content_cid_for_bytes(data: bytes) -> str:
    """Return the canonical raw CIDv1 for exact artifact bytes."""

    if type(data) is not bytes:
        raise LocalStoreError(
            "artifact payload must be exact bytes",
            reason=LocalStoreReason.MALFORMED,
            disposition=StorePutDisposition.REJECTED,
        )
    return cid_for_certificate_bytes(data)


def content_identity_for_bytes(data: bytes) -> str:
    """Alias for :func:`content_cid_for_bytes` (plan content identity)."""

    return content_cid_for_bytes(data)


def sha256_content_id(data: bytes) -> str:
    """Return a ``sha256:<hex>`` content identity for exact ``data``."""

    return f"sha256:{content_digest_hex(data)}"


def _digest_from_identity(identity: str) -> bytes | None:
    """Extract the sha2-256 digest bound by a supported content identity."""

    if type(identity) is not str or not identity or identity.strip() != identity:
        return None
    if len(identity) > 256 or "/" in identity or "\\" in identity or "\x00" in identity:
        return None
    sha_match = _SHA256_CID_RE.fullmatch(identity)
    if sha_match is not None:
        return bytes.fromhex(sha_match.group(1))
    try:
        return decode_certificate_cid(identity).digest
    except CertificateTransportError:
        return None


def verify_content_identity(identity: str, data: bytes) -> bool:
    """Return whether ``identity`` binds the exact sha2-256 of ``data``."""

    if type(data) is not bytes:
        return False
    digest = _digest_from_identity(identity)
    if digest is None:
        return False
    return hashlib.sha256(data).digest() == digest


def _path_safe_cid_token(cid: str) -> str:
    """Map a content identity to a single path component (no separators)."""

    if type(cid) is not str or not cid or cid.strip() != cid:
        raise LocalStorePathError(
            "CID token is malformed",
            reason=LocalStoreReason.MALFORMED,
            disposition=StorePutDisposition.REJECTED,
        )
    if "/" in cid or "\\" in cid or "\x00" in cid or cid in {".", ".."}:
        raise LocalStorePathError(
            "CID token contains path separators or escape components",
            reason=LocalStoreReason.PATH_ESCAPE,
            disposition=StorePutDisposition.REJECTED,
        )
    token = cid.replace(":", "_")
    if not _SAFE_CID_TOKEN_RE.fullmatch(token):
        raise LocalStorePathError(
            "CID token is not filesystem-safe",
            reason=LocalStoreReason.PATH_ESCAPE,
            disposition=StorePutDisposition.REJECTED,
        )
    if ".." in token:
        raise LocalStorePathError(
            "CID token contains path escape sequence",
            reason=LocalStoreReason.PATH_ESCAPE,
            disposition=StorePutDisposition.REJECTED,
        )
    return token


def _thread_lock(root: Path) -> threading.RLock:
    key = os.path.abspath(os.fspath(root))
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class HermeticProofSealStore:
    """Mandatory hermetic local store for immutable closed-kind artifacts.

    Construction requires an explicit :class:`StoreRoot`.  There is no default
    under ``~``, ``$XDG_*``, ``~/.ipfs``, or any daemon path.
    """

    __test__ = False

    def __init__(
        self,
        root: StoreRoot | str | Path | os.PathLike[str] | None,
        *,
        max_artifact_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
        create: bool = True,
    ) -> None:
        if root is None:
            raise ExplicitRootRequiredError(
                "HermeticProofSealStore requires an explicit StoreRoot; "
                "no default user-state or daemon root exists"
            )
        if isinstance(root, StoreRoot):
            store_root = root
        else:
            store_root = StoreRoot.require(root)
        # Re-validate so callers cannot smuggle a relative/home path via Path.
        validate_explicit_root_path(store_root.root_path, field_name="root_path")

        if (
            isinstance(max_artifact_bytes, bool)
            or not isinstance(max_artifact_bytes, int)
            or max_artifact_bytes <= 0
            or max_artifact_bytes > MAX_ARTIFACT_BYTES_BOUND
        ):
            raise ProofSealStoreContractError(
                "max_artifact_bytes must be a positive integer within the declared bound"
            )

        self._root = store_root
        self._root_path = Path(store_root.root_path)
        self.max_artifact_bytes = max_artifact_bytes
        self._lock = _thread_lock(self._root_path)

        if self._root_path.exists() and self._root_path.is_symlink():
            raise LocalStorePathError(
                "store root must not be a symlink",
                reason=LocalStoreReason.SYMLINK_REJECTED,
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

    def put_immutable(
        self,
        kind: ArtifactKind | str,
        data: bytes,
        *,
        claimed_cid: str | None = None,
    ) -> ArtifactReference:
        """Persist immutable closed-kind bytes and return an admitted reference.

        Identical (kind, bytes) puts deduplicate.  Mismatched CID/kind/bytes,
        path escape, symlink, short write, fsync/readback failure, and
        corruption fail closed by raising :class:`LocalStoreError`.
        """

        result = self.put_immutable_result(kind, data, claimed_cid=claimed_cid)
        if result.reference is not None and result.stored:
            return result.reference
        raise LocalStoreError(
            f"put_immutable failed closed: {result.reason.value}",
            reason=result.reason,
            disposition=result.disposition,
        )

    def get_verified_bytes(self, reference: ArtifactReference) -> bytes:
        """Load and rehash admitted bytes; fail closed on integrity mismatch."""

        result = self.get_verified_bytes_result(reference)
        if result.hit and result.data is not None:
            return result.data
        error_cls: type[LocalStoreError]
        if result.reason is LocalStoreReason.NOT_FOUND:
            error_cls = LocalStoreNotFoundError
        elif result.reason in {
            LocalStoreReason.CID_MISMATCH,
            LocalStoreReason.KIND_MISMATCH,
            LocalStoreReason.INTEGRITY_FAILED,
            LocalStoreReason.CORRUPTED,
        }:
            error_cls = LocalStoreIntegrityError
        elif result.reason in {
            LocalStoreReason.SYMLINK_REJECTED,
            LocalStoreReason.PATH_ESCAPE,
        }:
            error_cls = LocalStorePathError
        else:
            error_cls = LocalStoreError
        raise error_cls(
            f"get_verified_bytes failed closed: {result.reason.value}",
            reason=result.reason,
            disposition=result.disposition,
        )

    def lookup_candidate(self, cache_key: str) -> CacheCandidate | None:
        """Candidate index is provided by a later task; always a miss here."""

        if type(cache_key) is not str or not cache_key.strip():
            raise ProofSealStoreContractError("cache_key must be a non-empty string")
        return None

    def get_current_seal(
        self, repository_id: str, branch_id: str
    ) -> CurrentSealPointer | None:
        """Current-seal CAS is provided by a later task; always absent here."""

        if type(repository_id) is not str or not repository_id.strip():
            raise ProofSealStoreContractError("repository_id must be a non-empty string")
        if type(branch_id) is not str or not branch_id.strip():
            raise ProofSealStoreContractError("branch_id must be a non-empty string")
        return None

    def compare_and_swap_current_seal(
        self,
        expected: CurrentSealPointer | None,
        new_pointer: CurrentSealPointer,
    ) -> bool:
        """Current-seal CAS is outside this hermetic object-store surface."""

        if not isinstance(new_pointer, CurrentSealPointer):
            raise ProofSealStoreContractError("new_pointer must be a CurrentSealPointer")
        if expected is not None and not isinstance(expected, CurrentSealPointer):
            raise ProofSealStoreContractError(
                "expected must be CurrentSealPointer or None"
            )
        raise LocalStoreUnsupportedError(
            "compare_and_swap_current_seal is not provided by HermeticProofSealStore; "
            "use the CAS/pointer task surface",
            reason=LocalStoreReason.UNSUPPORTED,
        )

    def begin_transition(self, record: SealTransitionRecord) -> SealTransitionRecord:
        """WAL transitions are outside this hermetic object-store surface."""

        if not isinstance(record, SealTransitionRecord):
            raise ProofSealStoreContractError("record must be a SealTransitionRecord")
        raise LocalStoreUnsupportedError(
            "begin_transition is not provided by HermeticProofSealStore; "
            "use the WAL/recovery task surface",
            reason=LocalStoreReason.UNSUPPORTED,
        )

    # -- result-oriented API ------------------------------------------------

    def put_immutable_result(
        self,
        kind: ArtifactKind | str,
        data: bytes,
        *,
        claimed_cid: str | None = None,
    ) -> LocalPutResult:
        """Put with a structured fail-closed result (no raise on store faults)."""

        try:
            closed_kind = coerce_artifact_kind(kind, field_name="kind")
        except ForbiddenArtifactError:
            return LocalPutResult(
                StorePutDisposition.REJECTED,
                LocalStoreReason.FORBIDDEN_KIND,
                cid=claimed_cid or "",
            )
        except ArtifactKindError:
            return LocalPutResult(
                StorePutDisposition.REJECTED,
                LocalStoreReason.MALFORMED,
                cid=claimed_cid or "",
            )

        if type(data) is not bytes:
            return LocalPutResult(
                StorePutDisposition.REJECTED,
                LocalStoreReason.MALFORMED,
                cid=claimed_cid or "",
            )
        if len(data) > self.max_artifact_bytes:
            return LocalPutResult(
                StorePutDisposition.REJECTED,
                LocalStoreReason.OVER_BUDGET,
                cid=claimed_cid or "",
                byte_length=len(data),
            )

        digest_hex = content_digest_hex(data)
        computed_cid = content_cid_for_bytes(data)
        if claimed_cid is not None:
            if type(claimed_cid) is not str or not claimed_cid:
                return LocalPutResult(
                    StorePutDisposition.REJECTED,
                    LocalStoreReason.MALFORMED,
                    byte_length=len(data),
                )
            if not verify_content_identity(claimed_cid, data):
                return LocalPutResult(
                    StorePutDisposition.REJECTED,
                    LocalStoreReason.CID_MISMATCH,
                    cid=claimed_cid,
                    byte_length=len(data),
                )
            # Prefer the caller-claimed identity when it rehashes correctly so
            # sha256: and external CIDv1 codecs round-trip as admitted.
            target_cid = claimed_cid
        else:
            target_cid = computed_cid

        try:
            # Path is digest-keyed so identical bytes under one kind always
            # collide on the same object file (content-addressed dedupe).
            path = self._object_path_for_digest(
                closed_kind, digest_hex, create_parent=True
            )
        except LocalStorePathError as exc:
            return LocalPutResult(
                StorePutDisposition.REJECTED,
                exc.reason,
                cid=target_cid,
                byte_length=len(data),
            )
        except LocalStoreError as exc:
            return LocalPutResult(
                StorePutDisposition.ERROR,
                exc.reason,
                cid=target_cid,
                byte_length=len(data),
            )

        with self._lock:
            try:
                return self._write_object_locked(
                    path=path,
                    kind=closed_kind,
                    cid=target_cid,
                    data=data,
                )
            except LocalStoreDurabilityError as exc:
                return LocalPutResult(
                    StorePutDisposition.ERROR,
                    exc.reason,
                    cid=target_cid,
                    byte_length=len(data),
                )
            except LocalStoreIntegrityError as exc:
                return LocalPutResult(
                    StorePutDisposition.REJECTED,
                    exc.reason,
                    cid=target_cid,
                    byte_length=len(data),
                )
            except LocalStorePathError as exc:
                return LocalPutResult(
                    StorePutDisposition.REJECTED,
                    exc.reason,
                    cid=target_cid,
                    byte_length=len(data),
                )
            except LocalStoreError as exc:
                return LocalPutResult(
                    StorePutDisposition.ERROR,
                    exc.reason,
                    cid=target_cid,
                    byte_length=len(data),
                )
            except OSError:
                return LocalPutResult(
                    StorePutDisposition.ERROR,
                    LocalStoreReason.IO_ERROR,
                    cid=target_cid,
                    byte_length=len(data),
                )

    def get_verified_bytes_result(
        self, reference: ArtifactReference | Mapping[str, Any]
    ) -> LocalGetResult:
        """Get with a structured fail-closed result (no raise on store faults)."""

        try:
            ref = (
                reference
                if isinstance(reference, ArtifactReference)
                else ArtifactReference.from_dict(reference)
            )
        except (ProofSealStoreContractError, TypeError, ValueError):
            return LocalGetResult(
                StoreGetDisposition.REJECTED,
                LocalStoreReason.MALFORMED,
            )

        if ref.byte_length > self.max_artifact_bytes:
            return LocalGetResult(
                StoreGetDisposition.REJECTED,
                LocalStoreReason.OVER_BUDGET,
                reference=ref,
                byte_length=ref.byte_length,
            )

        digest = _digest_from_identity(ref.cid)
        if digest is None:
            return LocalGetResult(
                StoreGetDisposition.REJECTED,
                LocalStoreReason.MALFORMED,
                reference=ref,
            )

        try:
            path = self._object_path_for_digest(
                ref.kind, digest.hex(), create_parent=False
            )
        except LocalStorePathError as exc:
            disposition = (
                StoreGetDisposition.REJECTED
                if exc.reason
                in {LocalStoreReason.SYMLINK_REJECTED, LocalStoreReason.PATH_ESCAPE}
                else StoreGetDisposition.ERROR
            )
            return LocalGetResult(disposition, exc.reason, reference=ref)
        except LocalStoreError as exc:
            return LocalGetResult(
                StoreGetDisposition.ERROR, exc.reason, reference=ref
            )

        with self._lock:
            return self._read_object_locked(path, ref)

    def contains(self, reference: ArtifactReference) -> bool:
        """Return whether a verified get would hit for ``reference``."""

        return self.get_verified_bytes_result(reference).hit

    # -- path / fencing -----------------------------------------------------

    def _ensure_root(self) -> None:
        try:
            self._root_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as exc:
            raise LocalStoreError(
                f"unable to create store root: {exc}",
                reason=LocalStoreReason.IO_ERROR,
            ) from exc
        if self._root_path.is_symlink():
            raise LocalStorePathError(
                "store root must not be a symlink",
                reason=LocalStoreReason.SYMLINK_REJECTED,
            )
        if not self._root_path.is_dir():
            raise LocalStorePathError(
                "store root must be a directory",
                reason=LocalStoreReason.PATH_ESCAPE,
            )
        objects = self._root_path / _OBJECTS_DIR
        if objects.is_symlink():
            raise LocalStorePathError(
                "objects directory must not be a symlink",
                reason=LocalStoreReason.SYMLINK_REJECTED,
            )
        try:
            objects.mkdir(mode=0o700, exist_ok=True)
        except OSError as exc:
            raise LocalStoreError(
                f"unable to create objects directory: {exc}",
                reason=LocalStoreReason.IO_ERROR,
            ) from exc
        if objects.is_symlink() or not objects.is_dir():
            raise LocalStorePathError(
                "objects directory must be a real directory",
                reason=LocalStoreReason.SYMLINK_REJECTED
                if objects.is_symlink()
                else LocalStoreReason.PATH_ESCAPE,
            )

    def _resolved_root(self) -> Path:
        try:
            if self._root_path.is_symlink():
                raise LocalStorePathError(
                    "store root must not be a symlink",
                    reason=LocalStoreReason.SYMLINK_REJECTED,
                )
            return self._root_path.resolve(strict=True)
        except LocalStorePathError:
            raise
        except OSError as exc:
            raise LocalStoreError(
                f"store root is not resolvable: {exc}",
                reason=LocalStoreReason.IO_ERROR,
            ) from exc

    def _object_path(
        self,
        kind: ArtifactKind,
        cid: str,
        *,
        create_parent: bool,
    ) -> Path:
        """Return a fenced object path for a content identity.

        Paths are content-digest keyed (``objects/<kind>/<aa>/<digest>.blob``)
        so identical bytes under one kind always address one object file.
        """

        digest = _digest_from_identity(cid)
        if digest is None:
            # Still fence unsafe tokens before rejecting as malformed.
            _path_safe_cid_token(cid)
            raise LocalStorePathError(
                "content identity is not a strict CID or sha256 digest",
                reason=LocalStoreReason.MALFORMED,
                disposition=StorePutDisposition.REJECTED,
            )
        return self._object_path_for_digest(
            kind, digest.hex(), create_parent=create_parent
        )

    def _object_path_for_digest(
        self,
        kind: ArtifactKind,
        digest_hex: str,
        *,
        create_parent: bool,
    ) -> Path:
        """Return a fenced object path under ``objects/<kind>/<shard>/<digest>.blob``."""

        if type(digest_hex) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest_hex):
            raise LocalStorePathError(
                "digest token must be 64 lowercase hex characters",
                reason=LocalStoreReason.MALFORMED,
                disposition=StorePutDisposition.REJECTED,
            )

        if create_parent:
            self._ensure_root()

        root = self._resolved_root()
        shard = digest_hex[:2]
        path = (
            root
            / _OBJECTS_DIR
            / kind.value
            / shard
            / f"{digest_hex}{_BLOB_SUFFIX}"
        )

        # Walk and fence every ancestor component under the store root.
        current = root
        relative_parts = path.relative_to(root).parts
        for index, part in enumerate(relative_parts):
            if part in {"", ".", ".."} or "/" in part or "\\" in part or "\x00" in part:
                raise LocalStorePathError(
                    "object path component is unsafe",
                    reason=LocalStoreReason.PATH_ESCAPE,
                )
            current = current / part
            is_final = index == len(relative_parts) - 1
            if current.is_symlink():
                raise LocalStorePathError(
                    "symlink rejected on object path",
                    reason=LocalStoreReason.SYMLINK_REJECTED,
                )
            if not is_final:
                if create_parent:
                    try:
                        current.mkdir(mode=0o700, exist_ok=True)
                    except OSError as exc:
                        raise LocalStoreError(
                            f"unable to create object directory: {exc}",
                            reason=LocalStoreReason.IO_ERROR,
                        ) from exc
                    # Re-check after mkdir against concurrent symlink substitution.
                    if current.is_symlink():
                        raise LocalStorePathError(
                            "symlink rejected after directory create",
                            reason=LocalStoreReason.SYMLINK_REJECTED,
                        )
                if current.exists() and not current.is_dir():
                    raise LocalStorePathError(
                        "object path ancestor is not a directory",
                        reason=LocalStoreReason.PATH_ESCAPE,
                    )

        # Final containment check against resolved parents.
        try:
            if path.parent.exists():
                resolved_parent = path.parent.resolve(strict=True)
                resolved_parent.relative_to(root)
            # Even if the leaf does not exist, ensure the logical path stays
            # under root (relative_to raises on escape).
            path.resolve(strict=False).relative_to(root)
        except (OSError, ValueError) as exc:
            raise LocalStorePathError(
                "object path escapes store root",
                reason=LocalStoreReason.PATH_ESCAPE,
            ) from exc

        if path.is_symlink():
            raise LocalStorePathError(
                "object path is a symlink",
                reason=LocalStoreReason.SYMLINK_REJECTED,
            )
        return path

    # -- durable write / verified read --------------------------------------

    def _write_object_locked(
        self,
        *,
        path: Path,
        kind: ArtifactKind,
        cid: str,
        data: bytes,
    ) -> LocalPutResult:
        reference = ArtifactReference(
            cid=cid, kind=kind, byte_length=len(data)
        )

        if path.exists() or path.is_symlink():
            if path.is_symlink():
                raise LocalStorePathError(
                    "existing object path is a symlink",
                    reason=LocalStoreReason.SYMLINK_REJECTED,
                )
            existing = self._read_object_locked(path, reference)
            if existing.hit and existing.data == data:
                return LocalPutResult(
                    StorePutDisposition.ALREADY_EXISTS,
                    LocalStoreReason.ALREADY_EXISTS,
                    reference=reference,
                    cid=cid,
                    byte_length=len(data),
                )
            # Existing bytes under the same kind/CID do not match — fail closed.
            reason = (
                existing.reason
                if existing.reason is not LocalStoreReason.NOT_FOUND
                else LocalStoreReason.CORRUPTED
            )
            if existing.hit and existing.data != data:
                reason = LocalStoreReason.CORRUPTED
            raise LocalStoreIntegrityError(
                "existing object does not match put payload",
                reason=reason,
                disposition=StorePutDisposition.REJECTED,
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
                    raise LocalStoreDurabilityError(
                        f"short write: wrote {written} of {len(data)} bytes",
                        reason=LocalStoreReason.SHORT_WRITE,
                        disposition=StorePutDisposition.ERROR,
                    )
                stream.flush()
                try:
                    os.fsync(stream.fileno())
                except OSError as exc:
                    raise LocalStoreDurabilityError(
                        f"fsync of object file failed: {exc}",
                        reason=LocalStoreReason.FSYNC_FAILED,
                        disposition=StorePutDisposition.ERROR,
                    ) from exc
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, path)
            temporary_name = ""

            # Parent directory fsync so the directory entry is durable.
            try:
                dir_fd = os.open(path.parent, os.O_RDONLY)
            except OSError as exc:
                # Best-effort cleanup of the published path on fencing failure.
                try:
                    os.unlink(path)
                except OSError:
                    pass
                raise LocalStoreDurabilityError(
                    f"unable to open parent directory for fsync: {exc}",
                    reason=LocalStoreReason.FSYNC_FAILED,
                    disposition=StorePutDisposition.ERROR,
                ) from exc
            try:
                try:
                    os.fsync(dir_fd)
                except OSError as exc:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                    raise LocalStoreDurabilityError(
                        f"fsync of parent directory failed: {exc}",
                        reason=LocalStoreReason.FSYNC_FAILED,
                        disposition=StorePutDisposition.ERROR,
                    ) from exc
            finally:
                os.close(dir_fd)

        except LocalStoreDurabilityError:
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
            raise LocalStoreError(
                f"object write failed: {exc}",
                reason=LocalStoreReason.IO_ERROR,
                disposition=StorePutDisposition.ERROR,
            ) from exc

        # Mandatory readback rehash after publication.
        readback = self._read_object_locked(path, reference)
        if not readback.hit or readback.data != data:
            try:
                if path.exists() and not path.is_symlink():
                    os.unlink(path)
            except OSError:
                pass
            raise LocalStoreDurabilityError(
                "readback after put failed integrity verification",
                reason=LocalStoreReason.READBACK_FAILED,
                disposition=StorePutDisposition.ERROR,
            )

        return LocalPutResult(
            StorePutDisposition.STORED,
            LocalStoreReason.OK,
            reference=reference,
            cid=cid,
            byte_length=len(data),
        )

    def _read_object_locked(
        self,
        path: Path,
        reference: ArtifactReference,
    ) -> LocalGetResult:
        if path.is_symlink():
            return LocalGetResult(
                StoreGetDisposition.REJECTED,
                LocalStoreReason.SYMLINK_REJECTED,
                reference=reference,
            )
        if not path.exists():
            return LocalGetResult(
                StoreGetDisposition.MISS,
                LocalStoreReason.NOT_FOUND,
                reference=reference,
            )

        # Kind is encoded in the path; a wrong-kind reference resolves to a
        # different path and is a miss unless an object was stored under that
        # kind.  Additionally verify the path kind component matches.
        try:
            relative = path.resolve(strict=False).relative_to(self._resolved_root())
        except (OSError, ValueError):
            return LocalGetResult(
                StoreGetDisposition.REJECTED,
                LocalStoreReason.PATH_ESCAPE,
                reference=reference,
            )
        parts = relative.parts
        if len(parts) < 4 or parts[0] != _OBJECTS_DIR:
            return LocalGetResult(
                StoreGetDisposition.REJECTED,
                LocalStoreReason.PATH_ESCAPE,
                reference=reference,
            )
        path_kind = parts[1]
        if path_kind != reference.kind.value:
            return LocalGetResult(
                StoreGetDisposition.KIND_MISMATCH,
                LocalStoreReason.KIND_MISMATCH,
                reference=reference,
            )

        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError:
            return LocalGetResult(
                StoreGetDisposition.ERROR,
                LocalStoreReason.IO_ERROR,
                reference=reference,
            )
        try:
            with os.fdopen(descriptor, "rb") as stream:
                metadata = os.fstat(stream.fileno())
                if not stat.S_ISREG(metadata.st_mode):
                    return LocalGetResult(
                        StoreGetDisposition.REJECTED,
                        LocalStoreReason.MALFORMED,
                        reference=reference,
                    )
                if metadata.st_size > self.max_artifact_bytes:
                    return LocalGetResult(
                        StoreGetDisposition.REJECTED,
                        LocalStoreReason.OVER_BUDGET,
                        reference=reference,
                        byte_length=metadata.st_size,
                    )
                # Read and rehash before treating size/reference metadata as
                # decisive so on-disk corruption is reported as CORRUPTED even
                # when the tampered payload has a different length.
                data = stream.read(self.max_artifact_bytes + 1)
        except OSError:
            return LocalGetResult(
                StoreGetDisposition.ERROR,
                LocalStoreReason.IO_ERROR,
                reference=reference,
            )

        if len(data) > self.max_artifact_bytes:
            return LocalGetResult(
                StoreGetDisposition.REJECTED,
                LocalStoreReason.OVER_BUDGET,
                reference=reference,
                byte_length=len(data),
            )

        if not verify_content_identity(reference.cid, data):
            # Existing object bytes do not bind the admitted content identity.
            return LocalGetResult(
                StoreGetDisposition.INTEGRITY_FAILED,
                LocalStoreReason.CORRUPTED,
                reference=reference,
                byte_length=len(data),
            )

        if reference.byte_length > 0 and len(data) != reference.byte_length:
            # Content binds the CID but the reference metadata is inconsistent.
            return LocalGetResult(
                StoreGetDisposition.INTEGRITY_FAILED,
                LocalStoreReason.INTEGRITY_FAILED,
                reference=reference,
                byte_length=len(data),
            )

        return LocalGetResult(
            StoreGetDisposition.HIT,
            LocalStoreReason.OK,
            data=data,
            reference=ArtifactReference(
                cid=reference.cid,
                kind=reference.kind,
                byte_length=len(data),
            ),
            byte_length=len(data),
        )


__all__ = [
    "EVIDENCE_SUBSET",
    "HermeticProofSealStore",
    "LOCAL_STORE_INTERFACE",
    "LOCAL_STORE_SCHEMA",
    "LocalGetResult",
    "LocalPutResult",
    "LocalStoreDurabilityError",
    "LocalStoreError",
    "LocalStoreIntegrityError",
    "LocalStoreNotFoundError",
    "LocalStorePathError",
    "LocalStoreReason",
    "LocalStoreUnsupportedError",
    "content_cid_for_bytes",
    "content_digest_hex",
    "content_identity_for_bytes",
    "sha256_content_id",
    "verify_content_identity",
]
