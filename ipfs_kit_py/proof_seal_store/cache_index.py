"""Exact-key candidate cache index and admission records (IPS-021).

Kit storage authority for proof-cache *hints* only.  Accelerate issues verified
admission records; this index stores them under an exact cache key and returns
:class:`CacheCandidate` values that always require fresh verification.

Fail-closed guarantees:

* only accelerate-issued, cryptographically/signature-verified pass admissions
  may enter the active index;
* unverified, simulated, stale, or non-pass metadata is rejected at write time
  and cannot be queried as accepted on read;
* key / CID / kind / admission mismatches miss or quarantine the entry;
* every successful lookup is a candidate hint (never acceptance authority);
* tombstones and quarantine hide poisoned or invalidated keys;
* index files are written atomically and are rebuildable from durable records;
* cold construction needs an explicit root and never opens a network/daemon path.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Final

from ipfs_kit_py.proof_seal_store.contracts import (
    MAX_CACHE_KEY_BYTES,
    MAX_CID_BYTES,
    MAX_IDENTIFIER_BYTES,
    MAX_SAFE_INTEGER,
    ArtifactKind,
    ArtifactReference,
    ArtifactRole,
    CacheCandidate,
    ExplicitRootRequiredError,
    ProofSealStoreContractError,
    RoleCollapseError,
    StoreRoot,
    coerce_artifact_kind,
    validate_explicit_root_path,
)

EVIDENCE_SUBSET: Final[str] = "ips/proof-cache-index@1"
CACHE_INDEX_SCHEMA: Final[str] = "ipfs_kit_py/proof_seal_store/cache-index@1"
CACHE_INDEX_INTERFACE: Final[str] = "ProofCacheIndex@1"
ADMISSION_RECORD_SCHEMA: Final[str] = (
    "ipfs_kit_py/proof_seal_store/candidate-admission-record@1"
)
ADMISSION_RECORD_INTERFACE: Final[str] = "CandidateAdmissionRecord@1"
CONTRACT_VERSION: Final[int] = 1

_INDEX_DIR: Final[str] = "cache_index"
_ENTRIES_DIR: Final[str] = "entries"
_TOMBSTONES_DIR: Final[str] = "tombstones"
_QUARANTINE_DIR: Final[str] = "quarantine"
_RECORD_SUFFIX: Final[str] = ".json"
_MAX_RECORD_BYTES: Final[int] = 256 * 1024
_MAX_REASON_BYTES: Final[int] = 512
_HEX64_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_CID_LIKE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(b[a-z2-7]{20,}|Qm[1-9A-HJ-NP-Za-km-z]{44}|baguqeer[a-z0-9]{50,}|"
    r"sha256:[0-9a-f]{64})$"
)
_ID_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/#@+\-]{0,511}$"
)

# Issuers that may write verified admission records into the index.
ALLOWED_ADMISSION_ISSUERS: Final[frozenset[str]] = frozenset(
    {
        "accelerate",
        "ipfs_accelerate_py",
        "ipfs_accelerate_py.agent_supervisor.proof.incremental_sealing",
    }
)

# Terminal outcomes that may be indexed as candidate-producing admissions.
# Non-pass outcomes (fail/unknown/timeout/simulated/stale/…) are rejected.
PASS_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "proved",
        "integrity_verified",
        "signed_assertion_verified",
    }
)

# Explicitly rejected terminal statuses (non-pass / non-admissible).
REJECTED_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "disproved",
        "not_modeled",
        "failed",
        "proof_failed",
        "unknown",
        "timeout",
        "unavailable",
        "cancelled",
        "invalid",
        "simulated",
        "stale",
        "pass",  # bare "pass" is not a closed evidence terminal
        "ok",
        "success",
        "verified",  # generic overclaim
        "zk_verified",
    }
)

# Proof modes that must never enter the production candidate index.
FORBIDDEN_PROOF_MODES: Final[frozenset[str]] = frozenset(
    {
        "simulated",
        "mock",
        "structural",
        "test_only_simulated",
    }
)

_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class IndexEntryState(str, Enum):
    """Closed lifecycle states for an exact-key index entry."""

    ACTIVE = "active"
    TOMBSTONED = "tombstoned"
    QUARANTINED = "quarantined"


class IndexDisposition(str, Enum):
    """Closed outcomes for index put/lookup operations."""

    STORED = "stored"
    ALREADY_EXISTS = "already_exists"
    HIT = "hit"
    MISS = "miss"
    TOMBSTONED = "tombstoned"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"
    ERROR = "error"
    REBUILT = "rebuilt"


class IndexReason(str, Enum):
    """Closed diagnostic reasons for index outcomes."""

    OK = "ok"
    ALREADY_EXISTS = "already_exists"
    NOT_FOUND = "not_found"
    MALFORMED = "malformed"
    UNVERIFIED = "unverified"
    NON_PASS = "non_pass"
    SIMULATED = "simulated"
    STALE = "stale"
    KEY_MISMATCH = "key_mismatch"
    CID_MISMATCH = "cid_mismatch"
    KIND_MISMATCH = "kind_mismatch"
    ADMISSION_MISMATCH = "admission_mismatch"
    ISSUER_REJECTED = "issuer_rejected"
    FORBIDDEN_KIND = "forbidden_kind"
    TOMBSTONED = "tombstoned"
    QUARANTINED = "quarantined"
    POISONED = "poisoned"
    CORRUPTED = "corrupted"
    ROLE_COLLAPSE = "role_collapse"
    OVER_BUDGET = "over_budget"
    IO_ERROR = "io_error"
    FSYNC_FAILED = "fsync_failed"
    SHORT_WRITE = "short_write"
    NOT_ACCEPTED = "not_accepted"


class AcceptanceQueryStatus(str, Enum):
    """Closed acceptance-query answers.

    The index is never acceptance authority.  Every query returns
    :attr:`NOT_ACCEPTED` (or a typed miss/quarantine) so stale/simulated/
    non-pass metadata cannot be read as accepted.
    """

    NOT_ACCEPTED = "not_accepted"
    MISS = "miss"
    TOMBSTONED = "tombstoned"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CacheIndexError(ProofSealStoreContractError):
    """A proof-cache index operation failed closed."""

    def __init__(
        self,
        message: str,
        *,
        reason: IndexReason = IndexReason.IO_ERROR,
        disposition: IndexDisposition | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.disposition = disposition


class CacheIndexIntegrityError(CacheIndexError):
    """Key, CID, kind, or admission integrity verification failed."""


class CacheIndexAdmissionError(CacheIndexError):
    """An admission record was rejected before index entry."""


# ---------------------------------------------------------------------------
# Result records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndexPutResult:
    """Outcome of recording an admission, tombstone, or quarantine."""

    disposition: IndexDisposition
    reason: IndexReason
    cache_key: str = ""
    candidate: CacheCandidate | None = None
    record: CandidateAdmissionRecord | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.disposition in {
            IndexDisposition.STORED,
            IndexDisposition.ALREADY_EXISTS,
            IndexDisposition.TOMBSTONED,
            IndexDisposition.QUARANTINED,
            IndexDisposition.REBUILT,
        }

    @property
    def stored(self) -> bool:
        return self.disposition in {
            IndexDisposition.STORED,
            IndexDisposition.ALREADY_EXISTS,
        }


@dataclass(frozen=True)
class IndexLookupResult:
    """Outcome of an exact-key candidate lookup."""

    disposition: IndexDisposition
    reason: IndexReason
    cache_key: str = ""
    candidate: CacheCandidate | None = None
    record: CandidateAdmissionRecord | None = None
    state: IndexEntryState | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return (
            self.disposition is IndexDisposition.HIT
            and self.candidate is not None
            and self.candidate.requires_fresh_verification is True
        )

    @property
    def hit(self) -> bool:
        return bool(self)

    @property
    def is_acceptance(self) -> bool:
        """Lookups never grant acceptance."""

        return False


@dataclass(frozen=True)
class AcceptanceQueryResult:
    """Result of an acceptance query against the index.

    Always non-accepting: the index is a candidate hint store only.
    """

    status: AcceptanceQueryStatus
    reason: IndexReason
    cache_key: str = ""
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return False

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class IndexRebuildResult:
    """Outcome of a corruption-aware index rebuild scan."""

    disposition: IndexDisposition
    reason: IndexReason
    scanned: int = 0
    active: int = 0
    tombstoned: int = 0
    quarantined: int = 0
    corrupted: int = 0
    removed: int = 0
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.disposition is IndexDisposition.REBUILT


# ---------------------------------------------------------------------------
# Admission record
# ---------------------------------------------------------------------------


def _utf8_size(value: str) -> int:
    return len(value.encode("utf-8"))


def _require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise CacheIndexAdmissionError(
            f"{field_name} must be a string",
            reason=IndexReason.MALFORMED,
            disposition=IndexDisposition.REJECTED,
        )
    return value


def _identifier(value: Any, field_name: str) -> str:
    text = _require_str(value, field_name).strip()
    if not text:
        raise CacheIndexAdmissionError(
            f"{field_name} must be a non-empty identifier",
            reason=IndexReason.MALFORMED,
            disposition=IndexDisposition.REJECTED,
        )
    if _utf8_size(text) > MAX_IDENTIFIER_BYTES:
        raise CacheIndexAdmissionError(
            f"{field_name} exceeds identifier bound",
            reason=IndexReason.OVER_BUDGET,
            disposition=IndexDisposition.REJECTED,
        )
    if not _ID_RE.fullmatch(text):
        raise CacheIndexAdmissionError(
            f"{field_name} is not a bounded identifier",
            reason=IndexReason.MALFORMED,
            disposition=IndexDisposition.REJECTED,
        )
    return text


def _cache_key(value: Any, field_name: str = "cache_key") -> str:
    text = _require_str(value, field_name).strip()
    if not text:
        raise CacheIndexAdmissionError(
            f"{field_name} must be non-empty",
            reason=IndexReason.MALFORMED,
            disposition=IndexDisposition.REJECTED,
        )
    if _utf8_size(text) > MAX_CACHE_KEY_BYTES:
        raise CacheIndexAdmissionError(
            f"{field_name} exceeds cache key bound",
            reason=IndexReason.OVER_BUDGET,
            disposition=IndexDisposition.REJECTED,
        )
    if "\x00" in text:
        raise CacheIndexAdmissionError(
            f"{field_name} must not contain NUL",
            reason=IndexReason.MALFORMED,
            disposition=IndexDisposition.REJECTED,
        )
    return text


def _cid(value: Any, field_name: str) -> str:
    text = _require_str(value, field_name).strip()
    if not text:
        raise CacheIndexAdmissionError(
            f"{field_name} must be a non-empty CID",
            reason=IndexReason.MALFORMED,
            disposition=IndexDisposition.REJECTED,
        )
    if _utf8_size(text) > MAX_CID_BYTES:
        raise CacheIndexAdmissionError(
            f"{field_name} exceeds CID bound",
            reason=IndexReason.OVER_BUDGET,
            disposition=IndexDisposition.REJECTED,
        )
    if not _CID_LIKE_RE.fullmatch(text):
        raise CacheIndexAdmissionError(
            f"{field_name} must be a strict CID-like content identity",
            reason=IndexReason.MALFORMED,
            disposition=IndexDisposition.REJECTED,
        )
    return text


def _non_negative_int(
    value: Any, field_name: str, *, maximum: int = MAX_SAFE_INTEGER
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CacheIndexAdmissionError(
            f"{field_name} must be an integer",
            reason=IndexReason.MALFORMED,
            disposition=IndexDisposition.REJECTED,
        )
    if value < 0:
        raise CacheIndexAdmissionError(
            f"{field_name} must be non-negative",
            reason=IndexReason.MALFORMED,
            disposition=IndexDisposition.REJECTED,
        )
    if value > maximum:
        raise CacheIndexAdmissionError(
            f"{field_name} exceeds bound {maximum}",
            reason=IndexReason.OVER_BUDGET,
            disposition=IndexDisposition.REJECTED,
        )
    return value


def _reason_text(value: Any, field_name: str = "reason") -> str:
    text = _require_str(value, field_name).strip()
    if not text:
        raise CacheIndexAdmissionError(
            f"{field_name} must be non-empty",
            reason=IndexReason.MALFORMED,
            disposition=IndexDisposition.REJECTED,
        )
    if _utf8_size(text) > _MAX_REASON_BYTES:
        raise CacheIndexAdmissionError(
            f"{field_name} exceeds reason bound",
            reason=IndexReason.OVER_BUDGET,
            disposition=IndexDisposition.REJECTED,
        )
    return text


def _normalize_terminal_status(value: Any) -> str:
    text = _require_str(value, "terminal_status").strip().lower().replace("-", "_")
    if not text:
        raise CacheIndexAdmissionError(
            "terminal_status must be non-empty",
            reason=IndexReason.MALFORMED,
            disposition=IndexDisposition.REJECTED,
        )
    if text in REJECTED_TERMINAL_STATUSES:
        if text in {"simulated"}:
            reason = IndexReason.SIMULATED
        elif text in {"stale"}:
            reason = IndexReason.STALE
        else:
            reason = IndexReason.NON_PASS
        raise CacheIndexAdmissionError(
            f"terminal_status {text!r} is not indexable as a verified pass",
            reason=reason,
            disposition=IndexDisposition.REJECTED,
        )
    if text not in PASS_TERMINAL_STATUSES:
        raise CacheIndexAdmissionError(
            f"terminal_status {text!r} is not a closed pass status",
            reason=IndexReason.NON_PASS,
            disposition=IndexDisposition.REJECTED,
        )
    return text


def _normalize_proof_mode(value: Any) -> str:
    if value is None or value == "":
        return ""
    text = _require_str(value, "proof_mode").strip().lower().replace("-", "_")
    if text in FORBIDDEN_PROOF_MODES:
        raise CacheIndexAdmissionError(
            f"proof_mode {text!r} cannot enter the candidate index",
            reason=IndexReason.SIMULATED,
            disposition=IndexDisposition.REJECTED,
        )
    if _utf8_size(text) > MAX_IDENTIFIER_BYTES:
        raise CacheIndexAdmissionError(
            "proof_mode exceeds identifier bound",
            reason=IndexReason.OVER_BUDGET,
            disposition=IndexDisposition.REJECTED,
        )
    return text


def _normalize_issuer(value: Any) -> str:
    text = _identifier(value, "issuer")
    # Accept exact allowlist entries or a dotted accelerate prefix.
    if text in ALLOWED_ADMISSION_ISSUERS:
        return text
    if text.startswith("ipfs_accelerate_py.") or text.startswith("accelerate."):
        return text
    raise CacheIndexAdmissionError(
        f"issuer {text!r} is not an accelerate admission authority",
        reason=IndexReason.ISSUER_REJECTED,
        disposition=IndexDisposition.REJECTED,
    )


def cache_key_digest(cache_key: str) -> str:
    """Return the sha2-256 hex digest used as the on-disk exact-key token."""

    key = _cache_key(cache_key)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CandidateAdmissionRecord:
    """Accelerate-issued verified admission that may be indexed as a candidate.

    Kit never decides proof validity.  This record is a durable *claim* that
    accelerate already performed cryptographic/signature verification under a
    pass terminal status.  The index stores it only as a candidate hint.
    """

    cache_key: str
    artifact: ArtifactReference
    admission_id: str
    issuer: str
    terminal_status: str
    verified: bool = True
    cryptographically_verified: bool = True
    simulated: bool = False
    stale: bool = False
    proof_mode: str = ""
    verification_receipt_cid: str = ""
    policy_cid: str = ""
    generation: int = 0
    schema: str = ADMISSION_RECORD_SCHEMA
    contract_version: int = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "cache_key", _cache_key(self.cache_key))

        if not isinstance(self.artifact, ArtifactReference):
            if isinstance(self.artifact, Mapping):
                try:
                    object.__setattr__(
                        self, "artifact", ArtifactReference.from_dict(self.artifact)
                    )
                except (ProofSealStoreContractError, TypeError, ValueError) as exc:
                    raise CacheIndexAdmissionError(
                        f"artifact is not a valid ArtifactReference: {exc}",
                        reason=IndexReason.MALFORMED,
                        disposition=IndexDisposition.REJECTED,
                    ) from exc
            else:
                raise CacheIndexAdmissionError(
                    "artifact must be an ArtifactReference",
                    reason=IndexReason.MALFORMED,
                    disposition=IndexDisposition.REJECTED,
                )
        if self.artifact.role is not ArtifactRole.ADMITTED:
            raise CacheIndexAdmissionError(
                "admission artifact role must be admitted",
                reason=IndexReason.ROLE_COLLAPSE,
                disposition=IndexDisposition.REJECTED,
            )

        object.__setattr__(self, "admission_id", _identifier(self.admission_id, "admission_id"))
        object.__setattr__(self, "issuer", _normalize_issuer(self.issuer))
        object.__setattr__(
            self, "terminal_status", _normalize_terminal_status(self.terminal_status)
        )
        object.__setattr__(self, "proof_mode", _normalize_proof_mode(self.proof_mode))

        if self.verified is not True:
            raise CacheIndexAdmissionError(
                "unverified admissions cannot enter the candidate index",
                reason=IndexReason.UNVERIFIED,
                disposition=IndexDisposition.REJECTED,
            )
        object.__setattr__(self, "verified", True)

        if self.cryptographically_verified is not True:
            raise CacheIndexAdmissionError(
                "cryptographically_verified must be True; "
                "proofs must be verified before cache admission",
                reason=IndexReason.UNVERIFIED,
                disposition=IndexDisposition.REJECTED,
            )
        object.__setattr__(self, "cryptographically_verified", True)

        if self.simulated is not False:
            raise CacheIndexAdmissionError(
                "simulated admissions cannot enter the candidate index",
                reason=IndexReason.SIMULATED,
                disposition=IndexDisposition.REJECTED,
            )
        object.__setattr__(self, "simulated", False)

        if self.stale is not False:
            raise CacheIndexAdmissionError(
                "stale admissions cannot enter the candidate index",
                reason=IndexReason.STALE,
                disposition=IndexDisposition.REJECTED,
            )
        object.__setattr__(self, "stale", False)

        if self.verification_receipt_cid not in (None, ""):
            object.__setattr__(
                self,
                "verification_receipt_cid",
                _cid(self.verification_receipt_cid, "verification_receipt_cid"),
            )
        else:
            object.__setattr__(self, "verification_receipt_cid", "")

        if self.policy_cid not in (None, ""):
            object.__setattr__(self, "policy_cid", _cid(self.policy_cid, "policy_cid"))
        else:
            object.__setattr__(self, "policy_cid", "")

        object.__setattr__(
            self, "generation", _non_negative_int(self.generation, "generation")
        )

        if self.schema != ADMISSION_RECORD_SCHEMA:
            raise CacheIndexAdmissionError(
                "CandidateAdmissionRecord schema mismatch",
                reason=IndexReason.MALFORMED,
                disposition=IndexDisposition.REJECTED,
            )
        if self.contract_version != CONTRACT_VERSION:
            raise CacheIndexAdmissionError(
                "CandidateAdmissionRecord contract_version mismatch",
                reason=IndexReason.MALFORMED,
                disposition=IndexDisposition.REJECTED,
            )

    @property
    def cid(self) -> str:
        return self.artifact.cid

    @property
    def kind(self) -> ArtifactKind:
        return self.artifact.kind

    @property
    def is_indexable(self) -> bool:
        """Return whether this record may produce an active candidate entry."""

        return (
            self.verified is True
            and self.cryptographically_verified is True
            and self.simulated is False
            and self.stale is False
            and self.terminal_status in PASS_TERMINAL_STATUSES
            and (not self.proof_mode or self.proof_mode not in FORBIDDEN_PROOF_MODES)
        )

    @property
    def is_acceptance_authority(self) -> bool:
        """Admission records are never acceptance authority by themselves."""

        return False

    def as_cache_candidate(self) -> CacheCandidate:
        """Project the record as a candidate hint requiring fresh verification."""

        return CacheCandidate(cache_key=self.cache_key, artifact=self.artifact)

    def matches_binding(
        self,
        *,
        cache_key: str | None = None,
        cid: str | None = None,
        kind: ArtifactKind | str | None = None,
        admission_id: str | None = None,
    ) -> bool:
        """Return whether supplied bindings match this record exactly."""

        if cache_key is not None and cache_key != self.cache_key:
            return False
        if cid is not None and cid != self.artifact.cid:
            return False
        if kind is not None:
            try:
                closed = coerce_artifact_kind(kind, field_name="kind")
            except ProofSealStoreContractError:
                return False
            if closed is not self.artifact.kind:
                return False
        if admission_id is not None and admission_id != self.admission_id:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "contract_version": self.contract_version,
            "cache_key": self.cache_key,
            "artifact": self.artifact.to_dict(),
            "admission_id": self.admission_id,
            "issuer": self.issuer,
            "terminal_status": self.terminal_status,
            "verified": self.verified,
            "cryptographically_verified": self.cryptographically_verified,
            "simulated": self.simulated,
            "stale": self.stale,
            "proof_mode": self.proof_mode,
            "verification_receipt_cid": self.verification_receipt_cid,
            "policy_cid": self.policy_cid,
            "generation": self.generation,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CandidateAdmissionRecord:
        if not isinstance(payload, Mapping):
            raise CacheIndexAdmissionError(
                "CandidateAdmissionRecord payload must be an object",
                reason=IndexReason.MALFORMED,
                disposition=IndexDisposition.REJECTED,
            )
        return cls(
            cache_key=payload.get("cache_key"),
            artifact=payload.get("artifact"),
            admission_id=payload.get("admission_id"),
            issuer=payload.get("issuer"),
            terminal_status=payload.get("terminal_status"),
            verified=payload.get("verified", True),
            cryptographically_verified=payload.get("cryptographically_verified", True),
            simulated=payload.get("simulated", False),
            stale=payload.get("stale", False),
            proof_mode=payload.get("proof_mode", ""),
            verification_receipt_cid=payload.get("verification_receipt_cid", ""),
            policy_cid=payload.get("policy_cid", ""),
            generation=payload.get("generation", 0),
            schema=payload.get("schema", ADMISSION_RECORD_SCHEMA),
            contract_version=payload.get("contract_version", CONTRACT_VERSION),
        )


# ---------------------------------------------------------------------------
# On-disk envelope helpers
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


def _parse_json_object(data: bytes) -> dict[str, Any]:
    if type(data) is not bytes:
        raise CacheIndexIntegrityError(
            "index record must be exact bytes",
            reason=IndexReason.MALFORMED,
            disposition=IndexDisposition.REJECTED,
        )
    if len(data) > _MAX_RECORD_BYTES:
        raise CacheIndexIntegrityError(
            "index record exceeds byte budget",
            reason=IndexReason.OVER_BUDGET,
            disposition=IndexDisposition.REJECTED,
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CacheIndexIntegrityError(
            "index record is not UTF-8",
            reason=IndexReason.CORRUPTED,
            disposition=IndexDisposition.REJECTED,
        ) from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CacheIndexIntegrityError(
            "index record is not valid JSON",
            reason=IndexReason.CORRUPTED,
            disposition=IndexDisposition.REJECTED,
        ) from exc
    if not isinstance(payload, dict):
        raise CacheIndexIntegrityError(
            "index record must be a JSON object",
            reason=IndexReason.CORRUPTED,
            disposition=IndexDisposition.REJECTED,
        )
    return payload


@dataclass(frozen=True)
class _IndexEnvelope:
    """Durable on-disk envelope for an exact-key index entry."""

    state: IndexEntryState
    cache_key: str
    key_digest: str
    record: CandidateAdmissionRecord | None
    reason: str = ""
    schema: str = CACHE_INDEX_SCHEMA
    contract_version: int = CONTRACT_VERSION

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": self.schema,
            "contract_version": self.contract_version,
            "state": self.state.value,
            "cache_key": self.cache_key,
            "key_digest": self.key_digest,
            "reason": self.reason,
        }
        if self.record is not None:
            body["record"] = self.record.to_dict()
        else:
            body["record"] = None
        return body

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> _IndexEnvelope:
        if not isinstance(payload, Mapping):
            raise CacheIndexIntegrityError(
                "index envelope must be an object",
                reason=IndexReason.CORRUPTED,
                disposition=IndexDisposition.REJECTED,
            )
        if payload.get("schema", CACHE_INDEX_SCHEMA) != CACHE_INDEX_SCHEMA:
            raise CacheIndexIntegrityError(
                "index envelope schema mismatch",
                reason=IndexReason.CORRUPTED,
                disposition=IndexDisposition.REJECTED,
            )
        contract_version = payload.get("contract_version", CONTRACT_VERSION)
        if isinstance(contract_version, bool) or not isinstance(contract_version, int):
            raise CacheIndexIntegrityError(
                "index envelope contract_version must be an integer",
                reason=IndexReason.CORRUPTED,
                disposition=IndexDisposition.REJECTED,
            )
        if contract_version != CONTRACT_VERSION:
            raise CacheIndexIntegrityError(
                "index envelope contract_version mismatch",
                reason=IndexReason.CORRUPTED,
                disposition=IndexDisposition.REJECTED,
            )
        try:
            state = IndexEntryState(payload.get("state"))
        except (TypeError, ValueError) as exc:
            raise CacheIndexIntegrityError(
                "index envelope state is not closed",
                reason=IndexReason.CORRUPTED,
                disposition=IndexDisposition.REJECTED,
            ) from exc
        cache_key = _cache_key(payload.get("cache_key"))
        key_digest = _require_str(payload.get("key_digest"), "key_digest").strip()
        if not _HEX64_RE.fullmatch(key_digest):
            raise CacheIndexIntegrityError(
                "key_digest must be 64 lowercase hex characters",
                reason=IndexReason.CORRUPTED,
                disposition=IndexDisposition.REJECTED,
            )
        if key_digest != cache_key_digest(cache_key):
            raise CacheIndexIntegrityError(
                "key_digest does not bind cache_key",
                reason=IndexReason.KEY_MISMATCH,
                disposition=IndexDisposition.QUARANTINED,
            )
        record_payload = payload.get("record")
        record: CandidateAdmissionRecord | None
        if record_payload is None:
            record = None
            if state is IndexEntryState.ACTIVE:
                raise CacheIndexIntegrityError(
                    "active index envelope requires an admission record",
                    reason=IndexReason.CORRUPTED,
                    disposition=IndexDisposition.QUARANTINED,
                )
        else:
            try:
                record = CandidateAdmissionRecord.from_dict(record_payload)
            except CacheIndexAdmissionError as exc:
                # Non-indexable on-disk metadata is treated as corruption/poison.
                raise CacheIndexIntegrityError(
                    f"index envelope admission record is not indexable: {exc}",
                    reason=exc.reason
                    if isinstance(exc.reason, IndexReason)
                    else IndexReason.CORRUPTED,
                    disposition=IndexDisposition.QUARANTINED,
                ) from exc
            if record.cache_key != cache_key:
                raise CacheIndexIntegrityError(
                    "admission record cache_key does not match envelope",
                    reason=IndexReason.KEY_MISMATCH,
                    disposition=IndexDisposition.QUARANTINED,
                )
        reason = payload.get("reason", "")
        if reason in (None, ""):
            reason_text = ""
        else:
            reason_text = _reason_text(reason, "reason")
        return cls(
            state=state,
            cache_key=cache_key,
            key_digest=key_digest,
            record=record,
            reason=reason_text,
        )


# ---------------------------------------------------------------------------
# ProofCacheIndex
# ---------------------------------------------------------------------------


class ProofCacheIndex:
    """Exact-key candidate cache index over verified admission records.

    Construction requires an explicit :class:`StoreRoot`.  Lookups never decide
    acceptance; they only return :class:`CacheCandidate` hints.
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
                "ProofCacheIndex requires an explicit StoreRoot; "
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
            raise CacheIndexError(
                "index root must not be a symlink",
                reason=IndexReason.MALFORMED,
                disposition=IndexDisposition.REJECTED,
            )
        if create:
            self._ensure_layout()

    # -- properties ---------------------------------------------------------

    @property
    def root(self) -> StoreRoot:
        return self._root

    @property
    def root_path(self) -> Path:
        return self._root_path

    @property
    def index_path(self) -> Path:
        return self._root_path / _INDEX_DIR

    # -- public API ---------------------------------------------------------

    def record_verified_admission(
        self,
        record: CandidateAdmissionRecord | Mapping[str, Any],
        *,
        expected_cache_key: str | None = None,
        expected_cid: str | None = None,
        expected_kind: ArtifactKind | str | None = None,
        expected_admission_id: str | None = None,
    ) -> IndexPutResult:
        """Index a verified accelerate admission as an exact-key candidate.

        Unverified, simulated, stale, or non-pass records are rejected.
        Optional expected bindings must match or the write is rejected /
        quarantined (never silently stored under the wrong key/CID/kind).
        """

        try:
            admission = (
                record
                if isinstance(record, CandidateAdmissionRecord)
                else CandidateAdmissionRecord.from_dict(record)
            )
        except CacheIndexAdmissionError as exc:
            return IndexPutResult(
                IndexDisposition.REJECTED,
                exc.reason,
                diagnostics={"error": str(exc)},
            )
        except (ProofSealStoreContractError, TypeError, ValueError) as exc:
            return IndexPutResult(
                IndexDisposition.REJECTED,
                IndexReason.MALFORMED,
                diagnostics={"error": str(exc)},
            )

        if not admission.is_indexable:
            return IndexPutResult(
                IndexDisposition.REJECTED,
                IndexReason.UNVERIFIED,
                cache_key=admission.cache_key,
                record=admission,
            )

        # Explicit caller bindings (key/CID/kind/admission) must match exactly.
        mismatch = self._binding_mismatch_reason(
            admission,
            expected_cache_key=expected_cache_key,
            expected_cid=expected_cid,
            expected_kind=expected_kind,
            expected_admission_id=expected_admission_id,
        )
        if mismatch is not None:
            return IndexPutResult(
                IndexDisposition.REJECTED,
                mismatch,
                cache_key=admission.cache_key,
                record=admission,
                diagnostics={
                    "expected_cache_key": expected_cache_key or "",
                    "expected_cid": expected_cid or "",
                    "expected_kind": (
                        expected_kind.value
                        if isinstance(expected_kind, ArtifactKind)
                        else (expected_kind or "")
                    ),
                    "expected_admission_id": expected_admission_id or "",
                },
            )

        with self._lock:
            try:
                return self._store_active_locked(admission)
            except CacheIndexError as exc:
                return IndexPutResult(
                    exc.disposition or IndexDisposition.ERROR,
                    exc.reason,
                    cache_key=admission.cache_key,
                    record=admission,
                    diagnostics={"error": str(exc)},
                )
            except OSError as exc:
                return IndexPutResult(
                    IndexDisposition.ERROR,
                    IndexReason.IO_ERROR,
                    cache_key=admission.cache_key,
                    record=admission,
                    diagnostics={"error": str(exc)},
                )

    def lookup_candidate(self, cache_key: str) -> CacheCandidate | None:
        """Return an exact-key candidate hint, never an acceptance decision.

        Misses, tombstones, quarantines, and integrity failures return ``None``.
        """

        result = self.lookup_result(cache_key)
        if result.hit and result.candidate is not None:
            # Defensive: never surface a candidate that claims acceptance.
            if result.candidate.requires_fresh_verification is not True:
                return None
            if result.candidate.is_acceptance_authority:
                return None
            if result.candidate.role is not ArtifactRole.CANDIDATE:
                return None
            return result.candidate
        return None

    def lookup_result(self, cache_key: str) -> IndexLookupResult:
        """Exact-key lookup with typed disposition (hit/miss/tombstone/…)."""

        try:
            key = _cache_key(cache_key)
        except CacheIndexAdmissionError as exc:
            return IndexLookupResult(
                IndexDisposition.REJECTED,
                exc.reason,
                diagnostics={"error": str(exc)},
            )

        with self._lock:
            try:
                return self._lookup_locked(key)
            except CacheIndexError as exc:
                return IndexLookupResult(
                    exc.disposition or IndexDisposition.ERROR,
                    exc.reason,
                    cache_key=key,
                    diagnostics={"error": str(exc)},
                )
            except OSError as exc:
                return IndexLookupResult(
                    IndexDisposition.ERROR,
                    IndexReason.IO_ERROR,
                    cache_key=key,
                    diagnostics={"error": str(exc)},
                )

    def tombstone(
        self,
        cache_key: str,
        *,
        reason: str = "tombstone",
        expected_cid: str | None = None,
        expected_admission_id: str | None = None,
    ) -> IndexPutResult:
        """Tombstone an exact key so it can no longer be returned as a candidate."""

        try:
            key = _cache_key(cache_key)
            reason_text = _reason_text(reason)
        except CacheIndexAdmissionError as exc:
            return IndexPutResult(
                IndexDisposition.REJECTED,
                exc.reason,
                diagnostics={"error": str(exc)},
            )

        with self._lock:
            try:
                # Optional binding checks against any active record.
                existing = self._read_envelope_for_key(
                    key, preferred=IndexEntryState.ACTIVE
                )
                if existing is not None and existing.record is not None:
                    if expected_cid is not None and existing.record.cid != expected_cid:
                        # CID mismatch on tombstone: quarantine rather than
                        # silently tombstone the wrong artifact binding.
                        return self._quarantine_locked(
                            key,
                            reason="tombstone_cid_mismatch",
                            record=existing.record,
                            reason_code=IndexReason.CID_MISMATCH,
                        )
                    if (
                        expected_admission_id is not None
                        and existing.record.admission_id != expected_admission_id
                    ):
                        return self._quarantine_locked(
                            key,
                            reason="tombstone_admission_mismatch",
                            record=existing.record,
                            reason_code=IndexReason.ADMISSION_MISMATCH,
                        )
                return self._write_state_locked(
                    key=key,
                    state=IndexEntryState.TOMBSTONED,
                    record=existing.record if existing is not None else None,
                    reason=reason_text,
                    disposition=IndexDisposition.TOMBSTONED,
                    reason_code=IndexReason.TOMBSTONED,
                )
            except CacheIndexError as exc:
                return IndexPutResult(
                    exc.disposition or IndexDisposition.ERROR,
                    exc.reason,
                    cache_key=key,
                    diagnostics={"error": str(exc)},
                )
            except OSError as exc:
                return IndexPutResult(
                    IndexDisposition.ERROR,
                    IndexReason.IO_ERROR,
                    cache_key=key,
                    diagnostics={"error": str(exc)},
                )

    def quarantine(
        self,
        cache_key: str,
        *,
        reason: str = "quarantine",
        record: CandidateAdmissionRecord | None = None,
    ) -> IndexPutResult:
        """Quarantine an exact key (poisoning / integrity mismatch)."""

        try:
            key = _cache_key(cache_key)
            reason_text = _reason_text(reason)
        except CacheIndexAdmissionError as exc:
            return IndexPutResult(
                IndexDisposition.REJECTED,
                exc.reason,
                diagnostics={"error": str(exc)},
            )

        with self._lock:
            try:
                return self._quarantine_locked(
                    key,
                    reason=reason_text,
                    record=record,
                    reason_code=IndexReason.QUARANTINED,
                )
            except CacheIndexError as exc:
                return IndexPutResult(
                    exc.disposition or IndexDisposition.ERROR,
                    exc.reason,
                    cache_key=key,
                    diagnostics={"error": str(exc)},
                )
            except OSError as exc:
                return IndexPutResult(
                    IndexDisposition.ERROR,
                    IndexReason.IO_ERROR,
                    cache_key=key,
                    diagnostics={"error": str(exc)},
                )

    def query_acceptance(self, cache_key: str) -> AcceptanceQueryResult:
        """Query whether the index accepts a proof for ``cache_key``.

        Always returns a non-accepting status.  Stale, simulated, non-pass,
        tombstoned, quarantined, and even verified-candidate entries are never
        reported as accepted — acceptance is accelerate's authority after
        fresh verification.
        """

        try:
            key = _cache_key(cache_key)
        except CacheIndexAdmissionError as exc:
            return AcceptanceQueryResult(
                AcceptanceQueryStatus.REJECTED,
                exc.reason,
                diagnostics={"error": str(exc)},
            )

        result = self.lookup_result(key)
        if result.disposition is IndexDisposition.TOMBSTONED:
            return AcceptanceQueryResult(
                AcceptanceQueryStatus.TOMBSTONED,
                IndexReason.TOMBSTONED,
                cache_key=key,
            )
        if result.disposition is IndexDisposition.QUARANTINED:
            return AcceptanceQueryResult(
                AcceptanceQueryStatus.QUARANTINED,
                IndexReason.QUARANTINED,
                cache_key=key,
            )
        if result.disposition is IndexDisposition.MISS:
            return AcceptanceQueryResult(
                AcceptanceQueryStatus.MISS,
                IndexReason.NOT_FOUND,
                cache_key=key,
            )
        if result.disposition is IndexDisposition.REJECTED:
            return AcceptanceQueryResult(
                AcceptanceQueryStatus.REJECTED,
                result.reason,
                cache_key=key,
            )
        # Hits (and any other disposition) still cannot be accepted via index.
        return AcceptanceQueryResult(
            AcceptanceQueryStatus.NOT_ACCEPTED,
            IndexReason.NOT_ACCEPTED,
            cache_key=key,
            diagnostics={
                "index_disposition": result.disposition.value,
                "requires_fresh_verification": True,
            },
        )

    def rebuild(self) -> IndexRebuildResult:
        """Scan durable envelopes, quarantine corruption, and report counts.

        Mutable indexes are rebuildable from durable admission/tombstone/
        quarantine records.  Corrupted files are moved into quarantine when
        a cache key can still be recovered; otherwise they are removed.
        """

        with self._lock:
            try:
                self._ensure_layout()
                scanned = 0
                active = 0
                tombstoned = 0
                quarantined = 0
                corrupted = 0
                removed = 0

                for state, directory in (
                    (IndexEntryState.ACTIVE, self._entries_dir()),
                    (IndexEntryState.TOMBSTONED, self._tombstones_dir()),
                    (IndexEntryState.QUARANTINED, self._quarantine_dir()),
                ):
                    if not directory.exists():
                        continue
                    for path in sorted(directory.rglob(f"*{_RECORD_SUFFIX}")):
                        if path.is_symlink() or not path.is_file():
                            continue
                        scanned += 1
                        try:
                            envelope = self._read_envelope_path(path)
                        except CacheIndexError:
                            # Unrecoverable corruption: remove the bad file.
                            # A synthetic quarantine key cannot rebind the
                            # original digest, so deletion is the fail-closed
                            # rebuild action.
                            corrupted += 1
                            try:
                                os.unlink(path)
                                removed += 1
                            except OSError:
                                pass
                            continue

                        # Path digest must bind the envelope key.
                        if path.stem != envelope.key_digest:
                            corrupted += 1
                            self._quarantine_locked(
                                envelope.cache_key,
                                reason="rebuild_path_digest_mismatch",
                                record=envelope.record,
                                reason_code=IndexReason.POISONED,
                            )
                            if state is IndexEntryState.ACTIVE:
                                try:
                                    os.unlink(path)
                                    removed += 1
                                except OSError:
                                    pass
                            quarantined += 1
                            continue

                        if envelope.state is not state:
                            # Relocate to the state claimed by the envelope.
                            corrupted += 1
                            self._write_state_locked(
                                key=envelope.cache_key,
                                state=envelope.state,
                                record=envelope.record,
                                reason=envelope.reason or "rebuild_state_repair",
                                disposition=IndexDisposition.QUARANTINED
                                if envelope.state is IndexEntryState.QUARANTINED
                                else IndexDisposition.STORED,
                                reason_code=IndexReason.CORRUPTED,
                            )
                            if path.exists():
                                try:
                                    # Remove the misplaced source after rewrite.
                                    if (
                                        self._path_for_digest(envelope.state, envelope.key_digest)
                                        != path
                                    ):
                                        os.unlink(path)
                                        removed += 1
                                except OSError:
                                    pass

                        if envelope.state is IndexEntryState.ACTIVE:
                            active += 1
                        elif envelope.state is IndexEntryState.TOMBSTONED:
                            tombstoned += 1
                        else:
                            quarantined += 1

                return IndexRebuildResult(
                    IndexDisposition.REBUILT,
                    IndexReason.OK,
                    scanned=scanned,
                    active=active,
                    tombstoned=tombstoned,
                    quarantined=quarantined,
                    corrupted=corrupted,
                    removed=removed,
                )
            except CacheIndexError as exc:
                return IndexRebuildResult(
                    IndexDisposition.ERROR,
                    exc.reason,
                    diagnostics={"error": str(exc)},
                )
            except OSError as exc:
                return IndexRebuildResult(
                    IndexDisposition.ERROR,
                    IndexReason.IO_ERROR,
                    diagnostics={"error": str(exc)},
                )

    # -- internal helpers ---------------------------------------------------

    def _binding_mismatch_reason(
        self,
        admission: CandidateAdmissionRecord,
        *,
        expected_cache_key: str | None,
        expected_cid: str | None,
        expected_kind: ArtifactKind | str | None,
        expected_admission_id: str | None,
    ) -> IndexReason | None:
        if expected_cache_key is not None:
            try:
                expected_key = _cache_key(expected_cache_key)
            except CacheIndexAdmissionError:
                return IndexReason.KEY_MISMATCH
            if expected_key != admission.cache_key:
                return IndexReason.KEY_MISMATCH
        if expected_cid is not None:
            try:
                expected = _cid(expected_cid, "expected_cid")
            except CacheIndexAdmissionError:
                return IndexReason.CID_MISMATCH
            if expected != admission.cid:
                return IndexReason.CID_MISMATCH
        if expected_kind is not None:
            try:
                closed = coerce_artifact_kind(expected_kind, field_name="expected_kind")
            except ProofSealStoreContractError:
                return IndexReason.KIND_MISMATCH
            if closed is not admission.kind:
                return IndexReason.KIND_MISMATCH
        if expected_admission_id is not None:
            try:
                expected_id = _identifier(expected_admission_id, "expected_admission_id")
            except CacheIndexAdmissionError:
                return IndexReason.ADMISSION_MISMATCH
            if expected_id != admission.admission_id:
                return IndexReason.ADMISSION_MISMATCH
        return None

    def _store_active_locked(self, admission: CandidateAdmissionRecord) -> IndexPutResult:
        key = admission.cache_key
        digest = cache_key_digest(key)

        tombstone_path = self._path_for_digest(IndexEntryState.TOMBSTONED, digest)
        quarantine_path = self._path_for_digest(IndexEntryState.QUARANTINED, digest)
        active_path = self._path_for_digest(IndexEntryState.ACTIVE, digest)

        if quarantine_path.exists() and not quarantine_path.is_symlink():
            # Quarantined keys stay dark until an operator rebuild clears them.
            return IndexPutResult(
                IndexDisposition.QUARANTINED,
                IndexReason.QUARANTINED,
                cache_key=key,
                record=admission,
            )

        if active_path.exists() and not active_path.is_symlink():
            try:
                existing = self._read_envelope_path(active_path)
            except CacheIndexError:
                return self._quarantine_locked(
                    key,
                    reason="existing_active_corrupted",
                    record=admission,
                    reason_code=IndexReason.CORRUPTED,
                )
            if existing.record is not None:
                if (
                    existing.record.cid == admission.cid
                    and existing.record.kind is admission.kind
                    and existing.record.admission_id == admission.admission_id
                ):
                    candidate = admission.as_cache_candidate()
                    return IndexPutResult(
                        IndexDisposition.ALREADY_EXISTS,
                        IndexReason.ALREADY_EXISTS,
                        cache_key=key,
                        candidate=candidate,
                        record=existing.record,
                    )
                # Same key, different CID/kind/admission → poisoning.
                return self._quarantine_locked(
                    key,
                    reason="poisoned_conflicting_admission",
                    record=admission,
                    reason_code=IndexReason.POISONED,
                )

        envelope = _IndexEnvelope(
            state=IndexEntryState.ACTIVE,
            cache_key=key,
            key_digest=digest,
            record=admission,
            reason="",
        )
        self._atomic_write_path(active_path, envelope.to_dict())
        # Ensure the key has a single precedence state after publish.
        for other_path in (tombstone_path, quarantine_path):
            if other_path.exists() and not other_path.is_symlink():
                try:
                    os.unlink(other_path)
                except OSError as exc:
                    raise CacheIndexError(
                        f"unable to clear superseded index state: {exc}",
                        reason=IndexReason.IO_ERROR,
                        disposition=IndexDisposition.ERROR,
                    ) from exc
        candidate = admission.as_cache_candidate()
        return IndexPutResult(
            IndexDisposition.STORED,
            IndexReason.OK,
            cache_key=key,
            candidate=candidate,
            record=admission,
        )

    def _lookup_locked(self, key: str) -> IndexLookupResult:
        digest = cache_key_digest(key)

        # Precedence: quarantine > tombstone > active.
        for state, disposition, reason in (
            (
                IndexEntryState.QUARANTINED,
                IndexDisposition.QUARANTINED,
                IndexReason.QUARANTINED,
            ),
            (
                IndexEntryState.TOMBSTONED,
                IndexDisposition.TOMBSTONED,
                IndexReason.TOMBSTONED,
            ),
            (IndexEntryState.ACTIVE, IndexDisposition.HIT, IndexReason.OK),
        ):
            path = self._path_for_digest(state, digest)
            if not path.exists():
                continue
            if path.is_symlink():
                return self._quarantine_lookup_failure(
                    key, reason="symlink_rejected", reason_code=IndexReason.CORRUPTED
                )
            try:
                envelope = self._read_envelope_path(path)
            except CacheIndexError as exc:
                # Integrity failure on read → quarantine the key.
                self._quarantine_locked(
                    key,
                    reason=f"lookup_{exc.reason.value}",
                    record=None,
                    reason_code=exc.reason
                    if isinstance(exc.reason, IndexReason)
                    else IndexReason.CORRUPTED,
                )
                return IndexLookupResult(
                    IndexDisposition.QUARANTINED,
                    IndexReason.QUARANTINED
                    if exc.reason
                    not in {
                        IndexReason.KEY_MISMATCH,
                        IndexReason.CID_MISMATCH,
                        IndexReason.KIND_MISMATCH,
                        IndexReason.ADMISSION_MISMATCH,
                        IndexReason.POISONED,
                        IndexReason.CORRUPTED,
                        IndexReason.SIMULATED,
                        IndexReason.STALE,
                        IndexReason.NON_PASS,
                        IndexReason.UNVERIFIED,
                    }
                    else exc.reason,
                    cache_key=key,
                    state=IndexEntryState.QUARANTINED,
                    diagnostics={"error": str(exc)},
                )

            if envelope.cache_key != key:
                self._quarantine_locked(
                    key,
                    reason="lookup_key_mismatch",
                    record=envelope.record,
                    reason_code=IndexReason.KEY_MISMATCH,
                )
                return IndexLookupResult(
                    IndexDisposition.QUARANTINED,
                    IndexReason.KEY_MISMATCH,
                    cache_key=key,
                    state=IndexEntryState.QUARANTINED,
                )

            if envelope.key_digest != digest:
                self._quarantine_locked(
                    key,
                    reason="lookup_digest_mismatch",
                    record=envelope.record,
                    reason_code=IndexReason.KEY_MISMATCH,
                )
                return IndexLookupResult(
                    IndexDisposition.QUARANTINED,
                    IndexReason.KEY_MISMATCH,
                    cache_key=key,
                    state=IndexEntryState.QUARANTINED,
                )

            if state is IndexEntryState.ACTIVE:
                if envelope.record is None or not envelope.record.is_indexable:
                    self._quarantine_locked(
                        key,
                        reason="lookup_non_indexable_record",
                        record=envelope.record,
                        reason_code=IndexReason.UNVERIFIED,
                    )
                    return IndexLookupResult(
                        IndexDisposition.QUARANTINED,
                        IndexReason.UNVERIFIED,
                        cache_key=key,
                        state=IndexEntryState.QUARANTINED,
                    )
                # Cross-check admission bindings inside the record.
                if envelope.record.cache_key != key:
                    self._quarantine_locked(
                        key,
                        reason="lookup_record_key_mismatch",
                        record=envelope.record,
                        reason_code=IndexReason.KEY_MISMATCH,
                    )
                    return IndexLookupResult(
                        IndexDisposition.QUARANTINED,
                        IndexReason.KEY_MISMATCH,
                        cache_key=key,
                        state=IndexEntryState.QUARANTINED,
                    )
                candidate = envelope.record.as_cache_candidate()
                if candidate.requires_fresh_verification is not True:
                    raise RoleCollapseError(
                        "index candidate lost requires_fresh_verification"
                    )
                return IndexLookupResult(
                    IndexDisposition.HIT,
                    IndexReason.OK,
                    cache_key=key,
                    candidate=candidate,
                    record=envelope.record,
                    state=IndexEntryState.ACTIVE,
                )

            return IndexLookupResult(
                disposition,
                reason,
                cache_key=key,
                record=envelope.record,
                state=state,
            )

        return IndexLookupResult(
            IndexDisposition.MISS,
            IndexReason.NOT_FOUND,
            cache_key=key,
        )

    def _quarantine_lookup_failure(
        self, key: str, *, reason: str, reason_code: IndexReason
    ) -> IndexLookupResult:
        self._quarantine_locked(
            key, reason=reason, record=None, reason_code=reason_code
        )
        return IndexLookupResult(
            IndexDisposition.QUARANTINED,
            reason_code,
            cache_key=key,
            state=IndexEntryState.QUARANTINED,
        )

    def _quarantine_locked(
        self,
        key: str,
        *,
        reason: str,
        record: CandidateAdmissionRecord | None,
        reason_code: IndexReason,
    ) -> IndexPutResult:
        return self._write_state_locked(
            key=key,
            state=IndexEntryState.QUARANTINED,
            record=record,
            reason=reason,
            disposition=IndexDisposition.QUARANTINED,
            reason_code=reason_code,
        )

    def _write_state_locked(
        self,
        *,
        key: str,
        state: IndexEntryState,
        record: CandidateAdmissionRecord | None,
        reason: str,
        disposition: IndexDisposition,
        reason_code: IndexReason,
    ) -> IndexPutResult:
        digest = cache_key_digest(key)
        envelope = _IndexEnvelope(
            state=state,
            cache_key=key,
            key_digest=digest,
            record=record,
            reason=reason,
        )
        target = self._path_for_digest(state, digest)
        self._atomic_write_path(target, envelope.to_dict())

        # Remove the key from other state directories so precedence is unique.
        for other in IndexEntryState:
            if other is state:
                continue
            other_path = self._path_for_digest(other, digest)
            if other_path.exists() and not other_path.is_symlink():
                try:
                    os.unlink(other_path)
                except OSError:
                    pass

        candidate = record.as_cache_candidate() if record is not None else None
        return IndexPutResult(
            disposition,
            reason_code,
            cache_key=key,
            candidate=candidate if state is IndexEntryState.ACTIVE else None,
            record=record,
            diagnostics={"state": state.value, "reason": reason},
        )

    def _read_envelope_for_key(
        self, key: str, *, preferred: IndexEntryState
    ) -> _IndexEnvelope | None:
        digest = cache_key_digest(key)
        order = [preferred] + [s for s in IndexEntryState if s is not preferred]
        for state in order:
            path = self._path_for_digest(state, digest)
            if path.exists() and not path.is_symlink():
                try:
                    return self._read_envelope_path(path)
                except CacheIndexError:
                    return None
        return None

    def _read_envelope_path(self, path: Path) -> _IndexEnvelope:
        if path.is_symlink():
            raise CacheIndexIntegrityError(
                "index path is a symlink",
                reason=IndexReason.CORRUPTED,
                disposition=IndexDisposition.QUARANTINED,
            )
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise CacheIndexError(
                f"unable to open index record: {exc}",
                reason=IndexReason.IO_ERROR,
                disposition=IndexDisposition.ERROR,
            ) from exc
        try:
            with os.fdopen(descriptor, "rb") as stream:
                data = stream.read(_MAX_RECORD_BYTES + 1)
        except OSError as exc:
            raise CacheIndexError(
                f"unable to read index record: {exc}",
                reason=IndexReason.IO_ERROR,
                disposition=IndexDisposition.ERROR,
            ) from exc
        payload = _parse_json_object(data)
        return _IndexEnvelope.from_dict(payload)

    def _atomic_write_path(self, path: Path, payload: Mapping[str, Any]) -> None:
        data = _canonical_json_bytes(payload)
        if len(data) > _MAX_RECORD_BYTES:
            raise CacheIndexError(
                "index record exceeds byte budget",
                reason=IndexReason.OVER_BUDGET,
                disposition=IndexDisposition.REJECTED,
            )
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.parent.is_symlink():
            raise CacheIndexError(
                "index parent directory must not be a symlink",
                reason=IndexReason.CORRUPTED,
                disposition=IndexDisposition.ERROR,
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
                    raise CacheIndexError(
                        f"short write: wrote {written} of {len(data)} bytes",
                        reason=IndexReason.SHORT_WRITE,
                        disposition=IndexDisposition.ERROR,
                    )
                stream.flush()
                try:
                    os.fsync(stream.fileno())
                except OSError as exc:
                    raise CacheIndexError(
                        f"fsync of index record failed: {exc}",
                        reason=IndexReason.FSYNC_FAILED,
                        disposition=IndexDisposition.ERROR,
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
                raise CacheIndexError(
                    f"unable to open parent directory for fsync: {exc}",
                    reason=IndexReason.FSYNC_FAILED,
                    disposition=IndexDisposition.ERROR,
                ) from exc
            try:
                try:
                    os.fsync(dir_fd)
                except OSError as exc:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                    raise CacheIndexError(
                        f"fsync of parent directory failed: {exc}",
                        reason=IndexReason.FSYNC_FAILED,
                        disposition=IndexDisposition.ERROR,
                    ) from exc
            finally:
                os.close(dir_fd)
        except CacheIndexError:
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
            raise CacheIndexError(
                f"index write failed: {exc}",
                reason=IndexReason.IO_ERROR,
                disposition=IndexDisposition.ERROR,
            ) from exc

    def _ensure_layout(self) -> None:
        try:
            self._root_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as exc:
            raise CacheIndexError(
                f"unable to create index root: {exc}",
                reason=IndexReason.IO_ERROR,
                disposition=IndexDisposition.ERROR,
            ) from exc
        if self._root_path.is_symlink():
            raise CacheIndexError(
                "index root must not be a symlink",
                reason=IndexReason.MALFORMED,
                disposition=IndexDisposition.REJECTED,
            )
        for directory in (
            self.index_path,
            self._entries_dir(),
            self._tombstones_dir(),
            self._quarantine_dir(),
        ):
            if directory.is_symlink():
                raise CacheIndexError(
                    f"index path must not be a symlink: {directory}",
                    reason=IndexReason.CORRUPTED,
                    disposition=IndexDisposition.ERROR,
                )
            try:
                directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            except OSError as exc:
                raise CacheIndexError(
                    f"unable to create index directory {directory}: {exc}",
                    reason=IndexReason.IO_ERROR,
                    disposition=IndexDisposition.ERROR,
                ) from exc

    def _entries_dir(self) -> Path:
        return self.index_path / _ENTRIES_DIR

    def _tombstones_dir(self) -> Path:
        return self.index_path / _TOMBSTONES_DIR

    def _quarantine_dir(self) -> Path:
        return self.index_path / _QUARANTINE_DIR

    def _path_for_digest(self, state: IndexEntryState, digest: str) -> Path:
        if not _HEX64_RE.fullmatch(digest):
            raise CacheIndexError(
                "digest token must be 64 lowercase hex characters",
                reason=IndexReason.MALFORMED,
                disposition=IndexDisposition.REJECTED,
            )
        if state is IndexEntryState.ACTIVE:
            base = self._entries_dir()
        elif state is IndexEntryState.TOMBSTONED:
            base = self._tombstones_dir()
        else:
            base = self._quarantine_dir()
        shard = digest[:2]
        return base / shard / f"{digest}{_RECORD_SUFFIX}"


__all__ = [
    "ADMISSION_RECORD_INTERFACE",
    "ADMISSION_RECORD_SCHEMA",
    "ALLOWED_ADMISSION_ISSUERS",
    "AcceptanceQueryResult",
    "AcceptanceQueryStatus",
    "CACHE_INDEX_INTERFACE",
    "CACHE_INDEX_SCHEMA",
    "CONTRACT_VERSION",
    "CandidateAdmissionRecord",
    "CacheIndexAdmissionError",
    "CacheIndexError",
    "CacheIndexIntegrityError",
    "EVIDENCE_SUBSET",
    "FORBIDDEN_PROOF_MODES",
    "IndexDisposition",
    "IndexEntryState",
    "IndexLookupResult",
    "IndexPutResult",
    "IndexReason",
    "IndexRebuildResult",
    "PASS_TERMINAL_STATUSES",
    "ProofCacheIndex",
    "REJECTED_TERMINAL_STATUSES",
    "cache_key_digest",
]
