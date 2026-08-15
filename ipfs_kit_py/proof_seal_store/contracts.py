"""Narrow kit ProofSealStore protocol and closed artifact kinds (IPS-018).

This module is an inert, closed, versioned contract surface for the kit storage
authority over proof-seal artifacts.  It defines:

* the exact closed set of public artifact kinds the store may persist;
* forbidden proving-key / witness kinds that public APIs must reject;
* mandatory explicit store roots (no implicit home or daemon paths);
* distinct candidate, admitted, and current record types that cannot collapse;
* the ``ProofSealStore`` protocol boundary for local store, cache index,
  forest, WAL, CAS, and recovery implementers.

Rules (fail-closed):

* kit carries bytes, CIDs, and opaque canonical records only — it never decides
  whether a proof is valid or may be reused;
* cache candidates are hints that always require fresh verification;
* admitted immutable artifacts and the namespaced current-seal pointer are
  separate roles and types;
* public proving-key and witness material is rejected at construction;
* cold import stays hermetic: no datasets, no network, no default user state.

Interfaces: ``ProofSealStore``, ``ArtifactKind``, ``ArtifactReference``,
``CacheCandidate``, ``CurrentSealPointer``, ``SealTransitionRecord``.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

PROOF_SEAL_STORE_NAMESPACE: Final[str] = "ipfs_kit_py/proof_seal_store"
PROOF_SEAL_STORE_CONTRACTS_NAMESPACE: Final[str] = (
    f"{PROOF_SEAL_STORE_NAMESPACE}/contracts"
)
EVIDENCE_SUBSET: Final[str] = "ips/store-protocol@1"

ARTIFACT_REFERENCE_SCHEMA: Final[str] = (
    f"{PROOF_SEAL_STORE_CONTRACTS_NAMESPACE}/artifact-reference@{SCHEMA_MAJOR}"
)
CACHE_CANDIDATE_SCHEMA: Final[str] = (
    f"{PROOF_SEAL_STORE_CONTRACTS_NAMESPACE}/cache-candidate@{SCHEMA_MAJOR}"
)
CURRENT_SEAL_POINTER_SCHEMA: Final[str] = (
    f"{PROOF_SEAL_STORE_CONTRACTS_NAMESPACE}/current-seal-pointer@{SCHEMA_MAJOR}"
)
SEAL_TRANSITION_RECORD_SCHEMA: Final[str] = (
    f"{PROOF_SEAL_STORE_CONTRACTS_NAMESPACE}/seal-transition-record@{SCHEMA_MAJOR}"
)
STORE_ROOT_SCHEMA: Final[str] = (
    f"{PROOF_SEAL_STORE_CONTRACTS_NAMESPACE}/store-root@{SCHEMA_MAJOR}"
)
PROOF_SEAL_STORE_PROTOCOL_SCHEMA: Final[str] = (
    f"{PROOF_SEAL_STORE_CONTRACTS_NAMESPACE}/proof-seal-store@{SCHEMA_MAJOR}"
)

# Public interface aliases (plan: ArtifactKind@1, ProofSealStore@1, …).
ArtifactKind_V1: Final[str] = (
    f"{PROOF_SEAL_STORE_CONTRACTS_NAMESPACE}/artifact-kind@{SCHEMA_MAJOR}"
)
ArtifactReference_V1: Final[str] = ARTIFACT_REFERENCE_SCHEMA
CacheCandidate_V1: Final[str] = CACHE_CANDIDATE_SCHEMA
CurrentSealPointer_V1: Final[str] = CURRENT_SEAL_POINTER_SCHEMA
SealTransitionRecord_V1: Final[str] = SEAL_TRANSITION_RECORD_SCHEMA
ProofSealStore_V1: Final[str] = PROOF_SEAL_STORE_PROTOCOL_SCHEMA
StoreRoot_V1: Final[str] = STORE_ROOT_SCHEMA

MAX_IDENTIFIER_BYTES: Final[int] = 512
MAX_PATH_BYTES: Final[int] = 4_096
MAX_CID_BYTES: Final[int] = 256
MAX_CACHE_KEY_BYTES: Final[int] = 4_096
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1
MAX_ARTIFACT_BYTES_BOUND: Final[int] = 1 << 30  # declared bound, not a body
DEFAULT_MAX_ARTIFACT_BYTES: Final[int] = 16 * 1_048_576

_ID_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/#@+\-]{0,511}$"
)
_CID_LIKE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(b[a-z2-7]{20,}|Qm[1-9A-HJ-NP-Za-km-z]{44}|baguqeer[a-z0-9]{50,}|"
    r"sha256:[0-9a-f]{64})$"
)

# Paths / roots that must never be used as implicit store roots.
_FORBIDDEN_ROOT_BASENAMES: Final[frozenset[str]] = frozenset(
    {
        ".ipfs",
        ".ipfs_kit",
        ".ipfs-kit",
        ".iroh",
        ".cache",
        ".local",
        ".config",
    }
)
_FORBIDDEN_ROOT_SUBSTRINGS: Final[tuple[str, ...]] = (
    "/.ipfs/",
    "/.ipfs_kit/",
    "/.iroh/",
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProofSealStoreContractError(ValueError):
    """A value is outside the finite ProofSealStore contract."""


class ArtifactKindError(ProofSealStoreContractError):
    """An artifact kind is unknown, open-ended, or publicly forbidden."""


class ForbiddenArtifactError(ArtifactKindError):
    """Proving-key or witness material was presented to a public surface."""


class ExplicitRootRequiredError(ProofSealStoreContractError):
    """A store root was missing, relative, home-relative, or otherwise implicit."""


class RoleCollapseError(ProofSealStoreContractError):
    """Candidate, admitted, and current roles were conflated."""


class SealTransitionError(ProofSealStoreContractError):
    """A seal-transition record is inconsistent or out of contract."""


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class ArtifactKind(str, Enum):
    """Closed public artifact kinds the kit seal store may persist.

    Exactly covers the required immutable proof-seal artifacts.  Proving keys
    and witness material are not members and are rejected separately.
    """

    PROOF_OBJECT = "proof_object"
    PROOF_RECEIPT = "proof_receipt"
    VERIFICATION_KEY = "verification_key"
    PROOF_MANIFEST = "proof_manifest"
    MERKLE_NODE = "merkle_node"
    CHECKPOINT_SEAL = "checkpoint_seal"
    DELTA_SEAL = "delta_seal"
    TOMBSTONE = "tombstone"
    INVALIDATION_RECORD = "invalidation_record"


REQUIRED_ARTIFACT_KINDS: Final[frozenset[ArtifactKind]] = frozenset(ArtifactKind)

REQUIRED_ARTIFACT_KIND_VALUES: Final[frozenset[str]] = frozenset(
    kind.value for kind in ArtifactKind
)

# Kinds that may appear as a repository/branch current seal root.
SEAL_ARTIFACT_KINDS: Final[frozenset[ArtifactKind]] = frozenset(
    {
        ArtifactKind.CHECKPOINT_SEAL,
        ArtifactKind.DELTA_SEAL,
    }
)

# Kinds that may appear as immutable admitted blobs (all closed kinds).
ADMITTED_ARTIFACT_KINDS: Final[frozenset[ArtifactKind]] = REQUIRED_ARTIFACT_KINDS

# Kinds that a cache candidate may point at (never seals-as-current).
CANDIDATE_ARTIFACT_KINDS: Final[frozenset[ArtifactKind]] = frozenset(
    {
        ArtifactKind.PROOF_OBJECT,
        ArtifactKind.PROOF_RECEIPT,
        ArtifactKind.VERIFICATION_KEY,
        ArtifactKind.PROOF_MANIFEST,
        ArtifactKind.MERKLE_NODE,
        ArtifactKind.TOMBSTONE,
        ArtifactKind.INVALIDATION_RECORD,
        ArtifactKind.CHECKPOINT_SEAL,
        ArtifactKind.DELTA_SEAL,
    }
)


class ForbiddenArtifactKind(str, Enum):
    """Closed set of materials that public store APIs must reject."""

    PROVING_KEY = "proving_key"
    WITNESS = "witness"
    PRIVATE_WITNESS = "private_witness"
    WITNESS_MATERIAL = "witness_material"
    SECRET_WITNESS = "secret_witness"
    PROVER_WITNESS = "prover_witness"


FORBIDDEN_ARTIFACT_KIND_VALUES: Final[frozenset[str]] = frozenset(
    kind.value for kind in ForbiddenArtifactKind
)

# Extra aliases callers may try; all map to the forbidden set.
_FORBIDDEN_KIND_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "proving-key",
        "proving_keys",
        "witnesses",
        "private_input",
        "private_inputs",
        "private-witness",
        "witness-material",
        "pk",
        "provingKey",
        "witnessMaterial",
    }
)


class ArtifactRole(str, Enum):
    """Closed storage roles that cannot be silently promoted across types.

    * ``candidate`` — exact-key cache index hint; never acceptance authority.
    * ``admitted`` — immutable, rehashed, kind-bound bytes already persisted.
    * ``current`` — repository/branch current-seal pointer after CAS.
    """

    CANDIDATE = "candidate"
    ADMITTED = "admitted"
    CURRENT = "current"


ARTIFACT_ROLES: Final[frozenset[ArtifactRole]] = frozenset(ArtifactRole)

# Roles that claim durable acceptance-relevant storage (never candidates).
ADMITTED_OR_CURRENT_ROLES: Final[frozenset[ArtifactRole]] = frozenset(
    {
        ArtifactRole.ADMITTED,
        ArtifactRole.CURRENT,
    }
)


class SealTransitionPhase(str, Enum):
    """Closed WAL phases for a seal transition (plan §9)."""

    INTENT = "intent"
    PROOF_EXECUTION = "proof_execution"
    RECEIPT_PERSISTENCE = "receipt_persistence"
    FOREST_UPDATE = "forest_update"
    AGGREGATE_GENERATION = "aggregate_generation"
    SEAL_PERSISTENCE = "seal_persistence"
    CURRENT_ROOT_CAS = "current_root_cas"
    CLEANUP = "cleanup"


SEAL_TRANSITION_PHASES: Final[tuple[SealTransitionPhase, ...]] = tuple(
    SealTransitionPhase
)


class SealTransitionState(str, Enum):
    """Closed lifecycle states for a seal transition journal record."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMMITTED = "committed"
    ABORTED = "aborted"
    FAILED = "failed"
    RECOVERING = "recovering"


class StorePutDisposition(str, Enum):
    """Closed put outcomes for immutable artifacts."""

    STORED = "stored"
    ALREADY_EXISTS = "already_exists"
    REJECTED = "rejected"
    ERROR = "error"


class StoreGetDisposition(str, Enum):
    """Closed get outcomes for verified reads."""

    HIT = "hit"
    MISS = "miss"
    INTEGRITY_FAILED = "integrity_failed"
    KIND_MISMATCH = "kind_mismatch"
    REJECTED = "rejected"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _utf8_size(value: str) -> int:
    return len(value.encode("utf-8"))


def _require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ProofSealStoreContractError(f"{field_name} must be a string")
    return value


def _identifier(value: Any, field_name: str) -> str:
    text = _require_str(value, field_name).strip()
    if not text:
        raise ProofSealStoreContractError(f"{field_name} must be a non-empty identifier")
    if _utf8_size(text) > MAX_IDENTIFIER_BYTES:
        raise ProofSealStoreContractError(f"{field_name} exceeds identifier bound")
    if not _ID_RE.fullmatch(text):
        raise ProofSealStoreContractError(f"{field_name} is not a bounded identifier")
    return text


def _cid(value: Any, field_name: str) -> str:
    text = _require_str(value, field_name).strip()
    if not text:
        raise ProofSealStoreContractError(f"{field_name} must be a non-empty CID")
    if _utf8_size(text) > MAX_CID_BYTES:
        raise ProofSealStoreContractError(f"{field_name} exceeds CID bound")
    if not _CID_LIKE_RE.fullmatch(text):
        raise ProofSealStoreContractError(
            f"{field_name} must be a strict CID-like content identity"
        )
    return text


def _optional_cid(value: Any, field_name: str) -> str:
    if value is None or value == "":
        return ""
    return _cid(value, field_name)


def _non_negative_int(value: Any, field_name: str, *, maximum: int = MAX_SAFE_INTEGER) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProofSealStoreContractError(f"{field_name} must be an integer")
    if value < 0:
        raise ProofSealStoreContractError(f"{field_name} must be non-negative")
    if value > maximum:
        raise ProofSealStoreContractError(f"{field_name} exceeds bound {maximum}")
    return value


def _enum(value: Any, enum_cls: type[Enum], field_name: str) -> Enum:
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError as exc:
            raise ProofSealStoreContractError(
                f"{field_name} must be a closed {enum_cls.__name__} value"
            ) from exc
    raise ProofSealStoreContractError(
        f"{field_name} must be a closed {enum_cls.__name__} value"
    )


def is_forbidden_artifact_kind(kind: Any) -> bool:
    """Return whether ``kind`` names publicly rejected proving-key/witness material."""

    if isinstance(kind, ForbiddenArtifactKind):
        return True
    if isinstance(kind, ArtifactKind):
        return False
    if not isinstance(kind, str):
        return False
    normalized = kind.strip()
    if not normalized:
        return False
    if normalized in FORBIDDEN_ARTIFACT_KIND_VALUES:
        return True
    if normalized in _FORBIDDEN_KIND_ALIASES:
        return True
    lowered = normalized.lower().replace("-", "_")
    if lowered in FORBIDDEN_ARTIFACT_KIND_VALUES:
        return True
    if lowered in {alias.lower().replace("-", "_") for alias in _FORBIDDEN_KIND_ALIASES}:
        return True
    return False


def coerce_artifact_kind(kind: Any, *, field_name: str = "kind") -> ArtifactKind:
    """Parse a closed public artifact kind or raise.

    Forbidden proving-key / witness kinds raise ``ForbiddenArtifactError``.
    Unknown open-ended kinds raise ``ArtifactKindError``.
    """

    if is_forbidden_artifact_kind(kind):
        label = kind.value if isinstance(kind, Enum) else str(kind)
        raise ForbiddenArtifactError(
            f"{field_name} rejects public proving-key/witness material: {label!r}"
        )
    if isinstance(kind, ArtifactKind):
        return kind
    if isinstance(kind, str):
        try:
            return ArtifactKind(kind.strip())
        except ValueError as exc:
            raise ArtifactKindError(
                f"{field_name} must be a closed ArtifactKind; got {kind!r}"
            ) from exc
    raise ArtifactKindError(f"{field_name} must be a closed ArtifactKind")


def assert_public_artifact_kind(kind: Any, *, field_name: str = "kind") -> ArtifactKind:
    """Alias for :func:`coerce_artifact_kind` used at public API boundaries."""

    return coerce_artifact_kind(kind, field_name=field_name)


def closed_artifact_kind_values() -> frozenset[str]:
    """Return the exact closed public kind value set."""

    return REQUIRED_ARTIFACT_KIND_VALUES


def kinds_exactly_cover_required() -> bool:
    """Return whether :class:`ArtifactKind` exactly equals the required set."""

    required = {
        "proof_object",
        "proof_receipt",
        "verification_key",
        "proof_manifest",
        "merkle_node",
        "checkpoint_seal",
        "delta_seal",
        "tombstone",
        "invalidation_record",
    }
    return set(REQUIRED_ARTIFACT_KIND_VALUES) == required and len(ArtifactKind) == len(
        required
    )


def _is_home_relative(path_text: str) -> bool:
    if path_text.startswith("~"):
        return True
    expanded = os.path.expanduser(path_text)
    return expanded != path_text


def _looks_like_forbidden_user_state_root(path_text: str) -> bool:
    normalized = path_text.replace("\\", "/").rstrip("/")
    basename = PurePosixPath(normalized).name
    if basename in _FORBIDDEN_ROOT_BASENAMES:
        return True
    for fragment in _FORBIDDEN_ROOT_SUBSTRINGS:
        if fragment in f"{normalized}/":
            return True
    return False


def validate_explicit_root_path(path: Any, *, field_name: str = "root_path") -> str:
    """Require an absolute, non-home, non-daemon-default filesystem root."""

    if path is None:
        raise ExplicitRootRequiredError(f"{field_name} is mandatory; implicit roots are forbidden")
    if isinstance(path, Path):
        path_text = str(path)
    else:
        path_text = _require_str(path, field_name).strip()
    if not path_text:
        raise ExplicitRootRequiredError(f"{field_name} is mandatory; empty roots are forbidden")
    if _utf8_size(path_text) > MAX_PATH_BYTES:
        raise ExplicitRootRequiredError(f"{field_name} exceeds path bound")
    if _is_home_relative(path_text):
        raise ExplicitRootRequiredError(
            f"{field_name} must not be home-relative; expand and pass an absolute path"
        )
    # Reject relative paths on both POSIX and Windows conventions.
    pure_posix = PurePosixPath(path_text)
    pure_windows = PureWindowsPath(path_text)
    if not pure_posix.is_absolute() and not pure_windows.is_absolute():
        raise ExplicitRootRequiredError(
            f"{field_name} must be an absolute path; relative roots are forbidden"
        )
    if _looks_like_forbidden_user_state_root(path_text):
        raise ExplicitRootRequiredError(
            f"{field_name} must not target implicit daemon/user-state roots"
        )
    return path_text


def assert_roles_disjoint() -> None:
    """Structural assertion that candidate / admitted / current stay partitioned."""

    roles = {role.value for role in ArtifactRole}
    if roles != {"candidate", "admitted", "current"}:
        raise RoleCollapseError("ArtifactRole vocabulary drifted from the closed set")
    if ArtifactRole.CANDIDATE in ADMITTED_OR_CURRENT_ROLES:
        raise RoleCollapseError("candidate must never be treated as admitted/current")
    if ArtifactRole.ADMITTED is ArtifactRole.CURRENT:
        raise RoleCollapseError("admitted and current roles must remain distinct")
    if ArtifactRole.CANDIDATE is ArtifactRole.ADMITTED:
        raise RoleCollapseError("candidate and admitted roles must remain distinct")


def assert_not_role_collapse(
    *,
    role: ArtifactRole | str,
    claimed_as: ArtifactRole | str,
    field_name: str = "role",
) -> None:
    """Reject attempts to treat one storage role as another."""

    actual = _enum(role, ArtifactRole, field_name)
    claimed = _enum(claimed_as, ArtifactRole, "claimed_as")
    if actual is not claimed:
        raise RoleCollapseError(
            f"cannot collapse {actual.value!r} into {claimed.value!r}; "
            "candidate, admitted, and current remain distinct"
        )


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StoreRoot:
    """Mandatory explicit filesystem root for a hermetic proof-seal store.

    Implementations must receive this value at construction.  There is no
    default under ``~``, ``$XDG_*``, ``~/.ipfs``, or similar user state.
    """

    root_path: str
    schema: str = STORE_ROOT_SCHEMA
    contract_version: int = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "root_path", validate_explicit_root_path(self.root_path, field_name="root_path")
        )
        if self.schema != STORE_ROOT_SCHEMA:
            raise ProofSealStoreContractError("StoreRoot schema mismatch")
        if self.contract_version != CONTRACT_VERSION:
            raise ProofSealStoreContractError("StoreRoot contract_version mismatch")

    @property
    def path(self) -> Path:
        return Path(self.root_path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "contract_version": self.contract_version,
            "root_path": self.root_path,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> StoreRoot:
        if not isinstance(payload, Mapping):
            raise ProofSealStoreContractError("StoreRoot payload must be an object")
        return cls(
            root_path=payload.get("root_path"),
            schema=payload.get("schema", STORE_ROOT_SCHEMA),
            contract_version=payload.get("contract_version", CONTRACT_VERSION),
        )

    @classmethod
    def require(cls, root: StoreRoot | str | Path | None) -> StoreRoot:
        """Coerce an explicit root or raise ``ExplicitRootRequiredError``."""

        if root is None:
            raise ExplicitRootRequiredError(
                "explicit StoreRoot is mandatory; no default root exists"
            )
        if isinstance(root, StoreRoot):
            return root
        return cls(root_path=root)


@dataclass(frozen=True)
class ArtifactReference:
    """Immutable admitted artifact identity (CID + closed kind + role).

    Role is always :attr:`ArtifactRole.ADMITTED`.  This type is never a cache
    candidate and never a current-seal pointer.
    """

    cid: str
    kind: ArtifactKind
    byte_length: int = 0
    role: ArtifactRole = ArtifactRole.ADMITTED
    schema: str = ARTIFACT_REFERENCE_SCHEMA
    contract_version: int = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "cid", _cid(self.cid, "cid"))
        object.__setattr__(
            self, "kind", coerce_artifact_kind(self.kind, field_name="kind")
        )
        object.__setattr__(
            self,
            "byte_length",
            _non_negative_int(
                self.byte_length, "byte_length", maximum=MAX_ARTIFACT_BYTES_BOUND
            ),
        )
        role = _enum(self.role, ArtifactRole, "role")
        if role is not ArtifactRole.ADMITTED:
            raise RoleCollapseError(
                "ArtifactReference role must be admitted; "
                "use CacheCandidate or CurrentSealPointer for other roles"
            )
        object.__setattr__(self, "role", role)
        if self.schema != ARTIFACT_REFERENCE_SCHEMA:
            raise ProofSealStoreContractError("ArtifactReference schema mismatch")
        if self.contract_version != CONTRACT_VERSION:
            raise ProofSealStoreContractError(
                "ArtifactReference contract_version mismatch"
            )
        if self.kind not in ADMITTED_ARTIFACT_KINDS:
            raise ArtifactKindError(
                f"ArtifactReference kind {self.kind.value!r} is not admitable"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "contract_version": self.contract_version,
            "cid": self.cid,
            "kind": self.kind.value,
            "byte_length": self.byte_length,
            "role": self.role.value,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ArtifactReference:
        if not isinstance(payload, Mapping):
            raise ProofSealStoreContractError(
                "ArtifactReference payload must be an object"
            )
        return cls(
            cid=payload.get("cid"),
            kind=payload.get("kind"),
            byte_length=payload.get("byte_length", 0),
            role=payload.get("role", ArtifactRole.ADMITTED),
            schema=payload.get("schema", ARTIFACT_REFERENCE_SCHEMA),
            contract_version=payload.get("contract_version", CONTRACT_VERSION),
        )


@dataclass(frozen=True)
class CacheCandidate:
    """Exact-key cache index hint that never decides acceptance.

    Role is always :attr:`ArtifactRole.CANDIDATE`.  Callers must rehash bytes,
    recompute the complete cache key, and re-verify cryptography/signatures
    before any admission decision (which is accelerate's authority, not kit's).
    """

    cache_key: str
    artifact: ArtifactReference
    role: ArtifactRole = ArtifactRole.CANDIDATE
    requires_fresh_verification: bool = True
    schema: str = CACHE_CANDIDATE_SCHEMA
    contract_version: int = CONTRACT_VERSION

    def __post_init__(self) -> None:
        key = _require_str(self.cache_key, "cache_key").strip()
        if not key:
            raise ProofSealStoreContractError("cache_key must be non-empty")
        if _utf8_size(key) > MAX_CACHE_KEY_BYTES:
            raise ProofSealStoreContractError("cache_key exceeds bound")
        object.__setattr__(self, "cache_key", key)

        if not isinstance(self.artifact, ArtifactReference):
            if isinstance(self.artifact, Mapping):
                object.__setattr__(
                    self, "artifact", ArtifactReference.from_dict(self.artifact)
                )
            else:
                raise ProofSealStoreContractError(
                    "CacheCandidate.artifact must be an ArtifactReference"
                )

        role = _enum(self.role, ArtifactRole, "role")
        if role is not ArtifactRole.CANDIDATE:
            raise RoleCollapseError(
                "CacheCandidate role must be candidate; "
                "candidates cannot be admitted or current"
            )
        object.__setattr__(self, "role", role)

        if self.requires_fresh_verification is not True:
            raise RoleCollapseError(
                "CacheCandidate.requires_fresh_verification must be True; "
                "indexes never decide acceptance"
            )
        object.__setattr__(self, "requires_fresh_verification", True)

        if self.schema != CACHE_CANDIDATE_SCHEMA:
            raise ProofSealStoreContractError("CacheCandidate schema mismatch")
        if self.contract_version != CONTRACT_VERSION:
            raise ProofSealStoreContractError("CacheCandidate contract_version mismatch")

        # The nested reference is admitted *bytes*, but the index entry itself
        # remains a candidate.  Collapsing those roles is rejected elsewhere.
        if self.artifact.role is not ArtifactRole.ADMITTED:
            raise RoleCollapseError(
                "CacheCandidate.artifact must reference admitted bytes; "
                "the candidate wrapper never upgrades that admission into acceptance"
            )

    @property
    def cid(self) -> str:
        return self.artifact.cid

    @property
    def kind(self) -> ArtifactKind:
        return self.artifact.kind

    @property
    def is_acceptance_authority(self) -> bool:
        """Candidates are never acceptance authority."""

        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "contract_version": self.contract_version,
            "cache_key": self.cache_key,
            "artifact": self.artifact.to_dict(),
            "role": self.role.value,
            "requires_fresh_verification": self.requires_fresh_verification,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CacheCandidate:
        if not isinstance(payload, Mapping):
            raise ProofSealStoreContractError("CacheCandidate payload must be an object")
        return cls(
            cache_key=payload.get("cache_key"),
            artifact=payload.get("artifact"),
            role=payload.get("role", ArtifactRole.CANDIDATE),
            requires_fresh_verification=payload.get(
                "requires_fresh_verification", True
            ),
            schema=payload.get("schema", CACHE_CANDIDATE_SCHEMA),
            contract_version=payload.get("contract_version", CONTRACT_VERSION),
        )


@dataclass(frozen=True)
class CurrentSealPointer:
    """Repository/branch-namespaced current-seal pointer for CAS.

    Role is always :attr:`ArtifactRole.CURRENT`.  This is not a cache candidate
    and is not merely an admitted blob reference: it is the durable head after
    expected-parent compare-and-swap.
    """

    repository_id: str
    branch_id: str
    seal_cid: str
    seal_kind: ArtifactKind
    generation: int
    parent_seal_cid: str = ""
    role: ArtifactRole = ArtifactRole.CURRENT
    schema: str = CURRENT_SEAL_POINTER_SCHEMA
    contract_version: int = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "repository_id", _identifier(self.repository_id, "repository_id")
        )
        object.__setattr__(self, "branch_id", _identifier(self.branch_id, "branch_id"))
        object.__setattr__(self, "seal_cid", _cid(self.seal_cid, "seal_cid"))
        kind = coerce_artifact_kind(self.seal_kind, field_name="seal_kind")
        if kind not in SEAL_ARTIFACT_KINDS:
            raise ArtifactKindError(
                "CurrentSealPointer.seal_kind must be checkpoint_seal or delta_seal"
            )
        object.__setattr__(self, "seal_kind", kind)
        object.__setattr__(
            self,
            "generation",
            _non_negative_int(self.generation, "generation"),
        )
        object.__setattr__(
            self, "parent_seal_cid", _optional_cid(self.parent_seal_cid, "parent_seal_cid")
        )
        role = _enum(self.role, ArtifactRole, "role")
        if role is not ArtifactRole.CURRENT:
            raise RoleCollapseError(
                "CurrentSealPointer role must be current; "
                "use CacheCandidate or ArtifactReference for other roles"
            )
        object.__setattr__(self, "role", role)
        if self.schema != CURRENT_SEAL_POINTER_SCHEMA:
            raise ProofSealStoreContractError("CurrentSealPointer schema mismatch")
        if self.contract_version != CONTRACT_VERSION:
            raise ProofSealStoreContractError(
                "CurrentSealPointer contract_version mismatch"
            )
        if self.parent_seal_cid and self.parent_seal_cid == self.seal_cid:
            raise SealTransitionError(
                "CurrentSealPointer parent_seal_cid must differ from seal_cid"
            )

    @property
    def namespace_key(self) -> str:
        return f"{self.repository_id}#{self.branch_id}"

    def as_artifact_reference(self) -> ArtifactReference:
        """Project the seal bytes identity as an admitted reference.

        The pointer itself remains ``current``; the projection is a separate
        admitted-role value and does not collapse roles.
        """

        return ArtifactReference(cid=self.seal_cid, kind=self.seal_kind)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "contract_version": self.contract_version,
            "repository_id": self.repository_id,
            "branch_id": self.branch_id,
            "seal_cid": self.seal_cid,
            "seal_kind": self.seal_kind.value,
            "generation": self.generation,
            "parent_seal_cid": self.parent_seal_cid,
            "role": self.role.value,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CurrentSealPointer:
        if not isinstance(payload, Mapping):
            raise ProofSealStoreContractError(
                "CurrentSealPointer payload must be an object"
            )
        return cls(
            repository_id=payload.get("repository_id"),
            branch_id=payload.get("branch_id"),
            seal_cid=payload.get("seal_cid"),
            seal_kind=payload.get("seal_kind"),
            generation=payload.get("generation"),
            parent_seal_cid=payload.get("parent_seal_cid", ""),
            role=payload.get("role", ArtifactRole.CURRENT),
            schema=payload.get("schema", CURRENT_SEAL_POINTER_SCHEMA),
            contract_version=payload.get("contract_version", CONTRACT_VERSION),
        )


@dataclass(frozen=True)
class SealTransitionRecord:
    """WAL-bound seal transition journal record (opaque CID bindings only).

    Kit never decides proof validity.  This record binds repository/branch
    namespace, expected parent, intended seal, and the current phase for
    durable recovery.  Bodies of proofs/receipts are referenced by CID.
    """

    transition_id: str
    repository_id: str
    branch_id: str
    phase: SealTransitionPhase
    state: SealTransitionState
    expected_parent_seal_cid: str = ""
    new_seal_cid: str = ""
    new_seal_kind: ArtifactKind | None = None
    generation: int = 0
    artifact_cids: tuple[str, ...] = ()
    schema: str = SEAL_TRANSITION_RECORD_SCHEMA
    contract_version: int = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "transition_id", _identifier(self.transition_id, "transition_id")
        )
        object.__setattr__(
            self, "repository_id", _identifier(self.repository_id, "repository_id")
        )
        object.__setattr__(self, "branch_id", _identifier(self.branch_id, "branch_id"))
        object.__setattr__(
            self, "phase", _enum(self.phase, SealTransitionPhase, "phase")
        )
        object.__setattr__(
            self, "state", _enum(self.state, SealTransitionState, "state")
        )
        object.__setattr__(
            self,
            "expected_parent_seal_cid",
            _optional_cid(self.expected_parent_seal_cid, "expected_parent_seal_cid"),
        )
        object.__setattr__(
            self, "new_seal_cid", _optional_cid(self.new_seal_cid, "new_seal_cid")
        )
        if self.new_seal_kind is None or self.new_seal_kind == "":
            object.__setattr__(self, "new_seal_kind", None)
        else:
            kind = coerce_artifact_kind(self.new_seal_kind, field_name="new_seal_kind")
            if kind not in SEAL_ARTIFACT_KINDS:
                raise ArtifactKindError(
                    "SealTransitionRecord.new_seal_kind must be a seal kind"
                )
            object.__setattr__(self, "new_seal_kind", kind)
        object.__setattr__(
            self, "generation", _non_negative_int(self.generation, "generation")
        )

        if isinstance(self.artifact_cids, (str, bytes)) or not isinstance(
            self.artifact_cids, Sequence
        ):
            raise ProofSealStoreContractError("artifact_cids must be a sequence of CIDs")
        cids = tuple(_cid(item, f"artifact_cids[{index}]") for index, item in enumerate(self.artifact_cids))
        if len(set(cids)) != len(cids):
            raise SealTransitionError("artifact_cids must not contain duplicates")
        object.__setattr__(self, "artifact_cids", cids)

        if self.schema != SEAL_TRANSITION_RECORD_SCHEMA:
            raise ProofSealStoreContractError("SealTransitionRecord schema mismatch")
        if self.contract_version != CONTRACT_VERSION:
            raise ProofSealStoreContractError(
                "SealTransitionRecord contract_version mismatch"
            )

        # Committed transitions that claim a new seal must bind kind + CID.
        if self.state is SealTransitionState.COMMITTED:
            if not self.new_seal_cid:
                raise SealTransitionError(
                    "committed SealTransitionRecord requires new_seal_cid"
                )
            if self.new_seal_kind is None:
                raise SealTransitionError(
                    "committed SealTransitionRecord requires new_seal_kind"
                )
            # Committed may finalize at seal persistence, CAS, or cleanup.
            if self.phase not in {
                SealTransitionPhase.SEAL_PERSISTENCE,
                SealTransitionPhase.CURRENT_ROOT_CAS,
                SealTransitionPhase.CLEANUP,
            }:
                raise SealTransitionError(
                    "committed SealTransitionRecord phase is not a terminal seal phase"
                )

    @property
    def namespace_key(self) -> str:
        return f"{self.repository_id}#{self.branch_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "contract_version": self.contract_version,
            "transition_id": self.transition_id,
            "repository_id": self.repository_id,
            "branch_id": self.branch_id,
            "phase": self.phase.value,
            "state": self.state.value,
            "expected_parent_seal_cid": self.expected_parent_seal_cid,
            "new_seal_cid": self.new_seal_cid,
            "new_seal_kind": (
                self.new_seal_kind.value if self.new_seal_kind is not None else ""
            ),
            "generation": self.generation,
            "artifact_cids": list(self.artifact_cids),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SealTransitionRecord:
        if not isinstance(payload, Mapping):
            raise ProofSealStoreContractError(
                "SealTransitionRecord payload must be an object"
            )
        kind = payload.get("new_seal_kind") or None
        return cls(
            transition_id=payload.get("transition_id"),
            repository_id=payload.get("repository_id"),
            branch_id=payload.get("branch_id"),
            phase=payload.get("phase"),
            state=payload.get("state"),
            expected_parent_seal_cid=payload.get("expected_parent_seal_cid", ""),
            new_seal_cid=payload.get("new_seal_cid", ""),
            new_seal_kind=kind,
            generation=payload.get("generation", 0),
            artifact_cids=payload.get("artifact_cids", ()),
            schema=payload.get("schema", SEAL_TRANSITION_RECORD_SCHEMA),
            contract_version=payload.get("contract_version", CONTRACT_VERSION),
        )


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ProofSealStore(Protocol):
    """Narrow storage protocol for immutable proof-seal artifacts.

    Implementations:

    * require an explicit :class:`StoreRoot` (no implicit defaults);
    * rehash bytes on every read;
    * treat cache lookups as :class:`CacheCandidate` only;
    * publish current seals only via expected-parent CAS;
    * never accept proving keys or witness material on public methods;
    * never decide proof validity or reuse acceptance.
    """

    @property
    def root(self) -> StoreRoot:
        """Return the mandatory explicit store root."""

    def put_immutable(
        self,
        kind: ArtifactKind | str,
        data: bytes,
        *,
        claimed_cid: str | None = None,
    ) -> ArtifactReference:
        """Persist immutable closed-kind bytes and return an admitted reference."""

    def get_verified_bytes(self, reference: ArtifactReference) -> bytes:
        """Load and rehash admitted bytes; fail closed on integrity mismatch."""

    def lookup_candidate(self, cache_key: str) -> CacheCandidate | None:
        """Return an exact-key candidate hint, never an acceptance decision."""

    def get_current_seal(
        self, repository_id: str, branch_id: str
    ) -> CurrentSealPointer | None:
        """Read the repository/branch current-seal pointer."""

    def compare_and_swap_current_seal(
        self,
        expected: CurrentSealPointer | None,
        new_pointer: CurrentSealPointer,
    ) -> bool:
        """CAS-publish a current seal only when the expected parent still holds."""

    def begin_transition(self, record: SealTransitionRecord) -> SealTransitionRecord:
        """Journal the start of a durable seal transition."""


def ensure_protocol_method_names() -> frozenset[str]:
    """Return the closed set of :class:`ProofSealStore` protocol method names."""

    return frozenset(
        {
            "root",
            "put_immutable",
            "get_verified_bytes",
            "lookup_candidate",
            "get_current_seal",
            "compare_and_swap_current_seal",
            "begin_transition",
        }
    )


def reject_if_forbidden_kind(kind: Any, *, field_name: str = "kind") -> None:
    """Raise :class:`ForbiddenArtifactError` when ``kind`` is proving-key/witness."""

    if is_forbidden_artifact_kind(kind):
        coerce_artifact_kind(kind, field_name=field_name)


def candidate_is_not_admitted(candidate: CacheCandidate) -> bool:
    """Return True when a candidate remains a non-accepting hint."""

    if not isinstance(candidate, CacheCandidate):
        raise ProofSealStoreContractError("expected CacheCandidate")
    if candidate.role is not ArtifactRole.CANDIDATE:
        return False
    if candidate.is_acceptance_authority:
        return False
    if not candidate.requires_fresh_verification:
        return False
    return True


def current_is_not_candidate(pointer: CurrentSealPointer) -> bool:
    """Return True when a current pointer is not a cache candidate."""

    if not isinstance(pointer, CurrentSealPointer):
        raise ProofSealStoreContractError("expected CurrentSealPointer")
    return pointer.role is ArtifactRole.CURRENT


def admitted_is_not_current(reference: ArtifactReference) -> bool:
    """Return True when an admitted reference is not a current pointer."""

    if not isinstance(reference, ArtifactReference):
        raise ProofSealStoreContractError("expected ArtifactReference")
    return reference.role is ArtifactRole.ADMITTED


__all__ = [
    "ADMITTED_ARTIFACT_KINDS",
    "ADMITTED_OR_CURRENT_ROLES",
    "ARTIFACT_REFERENCE_SCHEMA",
    "ARTIFACT_ROLES",
    "ArtifactKind",
    "ArtifactKindError",
    "ArtifactKind_V1",
    "ArtifactReference",
    "ArtifactReference_V1",
    "ArtifactRole",
    "CACHE_CANDIDATE_SCHEMA",
    "CANDIDATE_ARTIFACT_KINDS",
    "CONTRACT_VERSION",
    "CURRENT_SEAL_POINTER_SCHEMA",
    "CacheCandidate",
    "CacheCandidate_V1",
    "CurrentSealPointer",
    "CurrentSealPointer_V1",
    "DEFAULT_MAX_ARTIFACT_BYTES",
    "EVIDENCE_SUBSET",
    "ExplicitRootRequiredError",
    "FORBIDDEN_ARTIFACT_KIND_VALUES",
    "ForbiddenArtifactError",
    "ForbiddenArtifactKind",
    "MAX_ARTIFACT_BYTES_BOUND",
    "MAX_CACHE_KEY_BYTES",
    "MAX_CID_BYTES",
    "MAX_IDENTIFIER_BYTES",
    "MAX_PATH_BYTES",
    "PROOF_SEAL_STORE_NAMESPACE",
    "PROOF_SEAL_STORE_PROTOCOL_SCHEMA",
    "ProofSealStore",
    "ProofSealStoreContractError",
    "ProofSealStore_V1",
    "REQUIRED_ARTIFACT_KINDS",
    "REQUIRED_ARTIFACT_KIND_VALUES",
    "RoleCollapseError",
    "SEAL_ARTIFACT_KINDS",
    "SEAL_TRANSITION_PHASES",
    "SEAL_TRANSITION_RECORD_SCHEMA",
    "SCHEMA_VERSION",
    "STORE_ROOT_SCHEMA",
    "SealTransitionError",
    "SealTransitionPhase",
    "SealTransitionRecord",
    "SealTransitionRecord_V1",
    "SealTransitionState",
    "StoreGetDisposition",
    "StorePutDisposition",
    "StoreRoot",
    "StoreRoot_V1",
    "admitted_is_not_current",
    "assert_not_role_collapse",
    "assert_public_artifact_kind",
    "assert_roles_disjoint",
    "candidate_is_not_admitted",
    "closed_artifact_kind_values",
    "coerce_artifact_kind",
    "current_is_not_candidate",
    "ensure_protocol_method_names",
    "is_forbidden_artifact_kind",
    "kinds_exactly_cover_required",
    "reject_if_forbidden_kind",
    "validate_explicit_root_path",
]
