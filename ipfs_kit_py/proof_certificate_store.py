"""Non-authoritative, bounded candidate context for proof certificates.

Candidate indexes are hints only.  They are parsed only after an fd-anchored,
no-follow read and must have the exact small schema below before a caller sees
any CID.  Certificate verification remains the accelerator's responsibility.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .content_addressed_artifact_store import (
    ArtifactGetResult,
    ArtifactPutResult,
    ArtifactStoreReason,
    ContentAddressedArtifactStore,
    _SecureDirectory,
    canonical_dag_json_bytes,
    is_canonical_dag_json,
    validate_dag_json_cid,
)


MAX_CANDIDATE_INDEX_BYTES = 16_384
MAX_CANDIDATE_LOCATOR_BYTES = 4_096
MAX_CANDIDATE_JSON_DEPTH = 4


@dataclass(frozen=True)
class CandidateContext:
    locator: str
    certificate_cid: str | None
    context_cid: str | None
    authoritative: bool = False
    requires_verification: bool = True


@dataclass(frozen=True)
class CandidateContextResult:
    found: bool
    candidate: CandidateContext | None = None
    reason: ArtifactStoreReason = ArtifactStoreReason.NOT_FOUND


def _bounded_depth(value: Any, depth: int = 0) -> bool:
    if depth > MAX_CANDIDATE_JSON_DEPTH:
        return False
    if isinstance(value, dict):
        return all(isinstance(key, str) and _bounded_depth(item, depth + 1) for key, item in value.items())
    if isinstance(value, list):
        return all(_bounded_depth(item, depth + 1) for item in value)
    return value is None or isinstance(value, (str, int, float, bool))


class ProofCertificateStore:
    """Persist candidates without treating local transport as proof authority."""

    authoritative = False

    def __init__(self, root: str | os.PathLike[str], *, max_blob_bytes: int = 1_048_576):
        self.root = Path(os.path.abspath(os.fspath(root)))
        self.artifacts = ContentAddressedArtifactStore(self.root / "artifacts", max_blob_bytes=max_blob_bytes)
        self.index_root = self.root / "candidate-index"
        self.index_quarantine_root = self.root / "candidate-index-quarantine"
        self._root = _SecureDirectory(self.root)
        if self._root.fd is not None:
            for name in ("candidate-index", "candidate-index-quarantine"):
                fd = self._root.child(name, create=True)
                if fd is not None:
                    os.close(fd)

    @staticmethod
    def _index_name(locator: str) -> str:
        if not isinstance(locator, str) or not locator or len(locator.encode("utf-8")) > MAX_CANDIDATE_LOCATOR_BYTES:
            raise ValueError("candidate locator must be a non-empty bounded string")
        return hashlib.sha256(locator.encode("utf-8")).hexdigest() + ".json"

    def _index_directory(self, *, quarantine: bool = False) -> int | None:
        return self._root.child("candidate-index-quarantine" if quarantine else "candidate-index", create=True)

    def _quarantine_index(self, index_fd: int, name: str, reason: ArtifactStoreReason) -> None:
        quarantine = self._index_directory(quarantine=True)
        if quarantine is None:
            return
        try:
            os.replace(name, f"{name}.{reason.value}.{uuid.uuid4().hex}",
                       src_dir_fd=index_fd, dst_dir_fd=quarantine)
            os.fsync(quarantine)
        except OSError:
            pass
        finally:
            os.close(quarantine)

    def _quarantine_index_name(self, name: str, reason: ArtifactStoreReason) -> None:
        """Quarantine after the read descriptor has been closed."""
        index = self._index_directory()
        if index is None:
            return
        try:
            self._quarantine_index(index, name, reason)
        finally:
            os.close(index)

    def put_certificate(self, certificate: Any, *, claimed_cid: str | None = None) -> ArtifactPutResult:
        return (self.artifacts.put_bytes(certificate, claimed_cid=claimed_cid)
                if isinstance(certificate, bytes) else self.artifacts.put(certificate, claimed_cid=claimed_cid))

    def get_certificate(self, cid: str) -> ArtifactGetResult:
        return self.artifacts.get_bytes(cid)

    @staticmethod
    def _valid_cid_or_none(value: Any) -> bool:
        return value is None or (isinstance(value, str) and validate_dag_json_cid(value))

    def put_candidate(
        self, locator: str, *, certificate: Any | None = None,
        certificate_cid: str | None = None, context: Any | None = None,
        context_cid: str | None = None,
    ) -> CandidateContextResult:
        try:
            name = self._index_name(locator)
        except (TypeError, UnicodeError, ValueError):
            return CandidateContextResult(False, reason=ArtifactStoreReason.CORRUPT)
        if certificate is not None:
            result = self.put_certificate(certificate, claimed_cid=certificate_cid)
            if not result.accepted:
                return CandidateContextResult(False, reason=result.reason)
            certificate_cid = result.cid
        if context is not None:
            result = self.artifacts.put(context, claimed_cid=context_cid)
            if not result.accepted:
                return CandidateContextResult(False, reason=result.reason)
            context_cid = result.cid
        if not self._valid_cid_or_none(certificate_cid) or not self._valid_cid_or_none(context_cid):
            return CandidateContextResult(False, reason=ArtifactStoreReason.INVALID_CID)
        record = {"certificate_cid": certificate_cid, "context_cid": context_cid, "locator": locator}
        try:
            encoded = canonical_dag_json_bytes(record)
        except (TypeError, ValueError, RecursionError):
            return CandidateContextResult(False, reason=ArtifactStoreReason.CORRUPT)
        if len(encoded) > MAX_CANDIDATE_INDEX_BYTES:
            return CandidateContextResult(False, reason=ArtifactStoreReason.TOO_LARGE)
        index = self._index_directory()
        if index is None:
            return CandidateContextResult(False, reason=ArtifactStoreReason.PATH_ESCAPE)
        temporary = f".index-{hashlib.sha256(name.encode()).hexdigest()[:16]}-{uuid.uuid4().hex}"
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=index)
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            # rename replaces a hostile leaf itself; it never follows it.
            os.replace(temporary, name, src_dir_fd=index, dst_dir_fd=index)
            os.fsync(index)
        except OSError:
            return CandidateContextResult(False, reason=ArtifactStoreReason.IO_ERROR)
        finally:
            try:
                os.unlink(temporary, dir_fd=index)
            except OSError:
                pass
            os.close(index)
        # Do not report a publication merely because rename succeeded: a
        # concurrent leaf substitution must still be observed through the
        # anchored no-follow reader before the hint is handed to a caller.
        verified = self.get_candidate(locator)
        if (verified.found and verified.candidate is not None
                and verified.candidate.certificate_cid == certificate_cid
                and verified.candidate.context_cid == context_cid):
            return verified
        return CandidateContextResult(False, reason=verified.reason)

    def get_candidate(self, locator: str) -> CandidateContextResult:
        try:
            name = self._index_name(locator)
        except (TypeError, UnicodeError, ValueError):
            return CandidateContextResult(False, reason=ArtifactStoreReason.CORRUPT)
        index = self._index_directory()
        if index is None:
            return CandidateContextResult(False, reason=ArtifactStoreReason.PATH_ESCAPE)
        try:
            try:
                info = os.stat(name, dir_fd=index, follow_symlinks=False)
            except FileNotFoundError:
                return CandidateContextResult(False, reason=ArtifactStoreReason.NOT_FOUND)
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                self._quarantine_index(index, name, ArtifactStoreReason.SYMLINK)
                return CandidateContextResult(False, reason=ArtifactStoreReason.SYMLINK)
            if info.st_size > MAX_CANDIDATE_INDEX_BYTES:
                self._quarantine_index(index, name, ArtifactStoreReason.TOO_LARGE)
                return CandidateContextResult(False, reason=ArtifactStoreReason.TOO_LARGE)
            fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=index)
            with os.fdopen(fd, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    self._quarantine_index(index, name, ArtifactStoreReason.SYMLINK)
                    return CandidateContextResult(False, reason=ArtifactStoreReason.SYMLINK)
                raw = stream.read(MAX_CANDIDATE_INDEX_BYTES + 1)
        except OSError:
            self._quarantine_index(index, name, ArtifactStoreReason.SYMLINK)
            return CandidateContextResult(False, reason=ArtifactStoreReason.IO_ERROR)
        finally:
            os.close(index)
        if len(raw) > MAX_CANDIDATE_INDEX_BYTES:
            self._quarantine_index_name(name, ArtifactStoreReason.TOO_LARGE)
            return CandidateContextResult(False, reason=ArtifactStoreReason.TOO_LARGE)
        try:
            # Validate the bounded canonical byte profile before parsing.  A
            # hostile deeply nested disk record must be quarantined, not reach
            # the recursive stdlib decoder first.
            if not is_canonical_dag_json(raw):
                self._quarantine_index_name(name, ArtifactStoreReason.CORRUPT)
                return CandidateContextResult(False, reason=ArtifactStoreReason.CORRUPT)
            record = json.loads(raw.decode("utf-8"))
            if (not _bounded_depth(record)
                    or set(record) != {"certificate_cid", "context_cid", "locator"}
                    or record["locator"] != locator
                    or not self._valid_cid_or_none(record["certificate_cid"])
                    or not self._valid_cid_or_none(record["context_cid"])):
                self._quarantine_index_name(name, ArtifactStoreReason.CORRUPT)
                return CandidateContextResult(False, reason=ArtifactStoreReason.CORRUPT)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, RecursionError):
            self._quarantine_index_name(name, ArtifactStoreReason.CORRUPT)
            return CandidateContextResult(False, reason=ArtifactStoreReason.CORRUPT)
        return CandidateContextResult(True, CandidateContext(locator, record["certificate_cid"], record["context_cid"]), ArtifactStoreReason.OK)


CandidateContextArtifactStore = ProofCertificateStore
KitProofCertificateStore = ProofCertificateStore
