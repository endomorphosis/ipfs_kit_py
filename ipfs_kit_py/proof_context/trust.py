"""Fail-closed trust admission for proof-context artifacts (PCCE-072).

This module is deliberately a *reader* over the existing proof-seal store.  It
does not implement a cache, signer, block store, current-root pointer, or
publication path.  A successful decision binds exact canonical descriptor and
subject bytes to the caller's current repository/environment expectation.  It
also rehashes the complete declared artifact closure before an injected live
provenance authority may approve the decision.

The signature and live-provenance authorities are ports, not marker fields.
When either required authority is absent, raises, or returns a non-boolean
answer, admission fails closed.  Unit-test authorities exercise this boundary;
they are not evidence that an external production authority is installed.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final, Protocol, runtime_checkable

from ipfs_kit_py.proof_seal_store.contracts import (
    MAX_SAFE_INTEGER,
    ArtifactKind,
    ArtifactReference,
    ArtifactRole,
    CacheCandidate,
    ProofSealStoreContractError,
    coerce_artifact_kind,
)
from ipfs_kit_py.proof_seal_store.local_store import (
    LocalStoreIntegrityError,
    LocalStoreNotFoundError,
    content_cid_for_bytes,
    verify_content_identity,
)

CONTRACT_VERSION: Final[int] = 1
TRUST_ADMISSION_INTERFACE: Final[str] = "KitProofContextTrustAdmission@1"
TRUST_EVIDENCE_SCHEMA: Final[str] = "ipfs-kit.proof-context/trust-evidence@1"
TRUST_GRANT_SCHEMA: Final[str] = "ipfs-kit.proof-context/trust-grant@1"
TRUST_EXPECTATION_SCHEMA: Final[str] = "ipfs-kit.proof-context/trust-expectation@1"
SIGNATURE_DOMAIN: Final[str] = "ipfs-kit.proof-context/trust-evidence-signature@1"

MAX_DESCRIPTOR_BYTES: Final[int] = 1_048_576
MAX_REFERENCES: Final[int] = 128
MAX_TEXT_BYTES: Final[int] = 4_096
MAX_SIGNATURE_BYTES: Final[int] = 64

_CID_RE: Final[re.Pattern[str]] = re.compile(
    r"^(b[a-z2-7]{20,}|Qm[1-9A-HJ-NP-Za-km-z]{44}|"
    r"baguqeer[a-z0-9]{50,}|sha256:[0-9a-f]{64})$"
)
_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@+\-]{0,511}$")
_TREE_RE: Final[re.Pattern[str]] = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")

_ROOT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema",
        "contract_version",
        "subject",
        "producer",
        "repository_id",
        "tree_id",
        "environment_cid",
        "policy_cid",
        "generation",
        "parent_seal_cids",
        "provenance",
        "freshness",
        "terminal_status",
        "evidence_mode",
        "cache_key",
        "references",
        "signature",
    }
)
_REFERENCE_FIELDS: Final[frozenset[str]] = frozenset(
    {"cid", "kind", "byte_length", "payload_schema"}
)
_SIGNATURE_FIELDS: Final[frozenset[str]] = frozenset({"algorithm", "signer", "value"})


class AdmissionReason(str, Enum):
    """Closed reason codes for a trust decision."""

    ADMITTED = "admitted"
    MALFORMED = "malformed"
    UNKNOWN_FIELD = "unknown_field"
    OVER_BUDGET = "over_budget"
    NON_CANONICAL = "non_canonical"
    DESCRIPTOR_CID_MISMATCH = "descriptor_cid_mismatch"
    SUBJECT_BINDING_MISMATCH = "subject_binding_mismatch"
    PRODUCER_MISMATCH = "producer_mismatch"
    REPOSITORY_MISMATCH = "repository_mismatch"
    TREE_MISMATCH = "tree_mismatch"
    ENVIRONMENT_MISMATCH = "environment_mismatch"
    POLICY_MISMATCH = "policy_mismatch"
    GENERATION_MISMATCH = "generation_mismatch"
    PARENT_MISMATCH = "parent_mismatch"
    STATUS_MISMATCH = "status_mismatch"
    CACHE_KEY_MISMATCH = "cache_key_mismatch"
    REFERENCE_MISMATCH = "reference_mismatch"
    SIMULATED = "simulated"
    PROVENANCE_NOT_LIVE = "provenance_not_live"
    STALE = "stale"
    SIGNATURE_REQUIRED = "signature_required"
    SIGNATURE_BINDING_MISMATCH = "signature_binding_mismatch"
    SIGNATURE_AUTHORITY_UNAVAILABLE = "signature_authority_unavailable"
    SIGNATURE_INVALID = "signature_invalid"
    SUBJECT_MISSING = "subject_missing"
    SUBJECT_CORRUPT = "subject_corrupt"
    SUBJECT_SCHEMA_MISMATCH = "subject_schema_mismatch"
    REFERENCE_MISSING = "reference_missing"
    REFERENCE_CORRUPT = "reference_corrupt"
    REFERENCE_SCHEMA_MISMATCH = "reference_schema_mismatch"
    MISSING_EVIDENCE = "missing_evidence"
    PROVENANCE_AUTHORITY_UNAVAILABLE = "provenance_authority_unavailable"
    PROVENANCE_INVALID = "provenance_invalid"
    CACHE_CANDIDATE_INVALID = "cache_candidate_invalid"
    CACHE_ARTIFACT_MISMATCH = "cache_artifact_mismatch"


class EvidenceProvenance(str, Enum):
    """Closed origin claims.  Only ``live`` can be admitted."""

    LIVE = "live"
    REPLAYED = "replayed"
    SIMULATED = "simulated"
    SYNTHETIC = "synthetic"


class EvidenceFreshness(str, Enum):
    """Closed freshness claims.  The live authority must confirm ``current``."""

    CURRENT = "current"
    STALE = "stale"


class EvidenceMode(str, Enum):
    """Closed proof/evidence modes accepted by the descriptor parser."""

    CRYPTOGRAPHIC = "cryptographic"
    INTEGRITY = "integrity"
    SIGNED_ASSERTION = "signed_assertion"
    SEAL = "seal"
    SIMULATED = "simulated"


class SignatureStatus(str, Enum):
    """Truthful signature-gate outcome."""

    NOT_REQUIRED = "not_required"
    VERIFIED = "verified"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class ProvenanceStatus(str, Enum):
    """Truthful live-provenance-gate outcome."""

    UNAVAILABLE = "unavailable"
    VERIFIED = "verified"
    INVALID = "invalid"


class TrustContractError(ValueError):
    """A descriptor or expectation is outside the closed trust contract."""

    def __init__(self, message: str, *, reason: AdmissionReason) -> None:
        super().__init__(message)
        self.reason = reason


class AuthorityUnavailableError(RuntimeError):
    """An injected signature or live-provenance authority is unavailable."""


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TrustContractError(
            "payload is not canonical-JSON encodable",
            reason=AdmissionReason.MALFORMED,
        ) from exc


def _strict_fields(payload: Mapping[str, Any], allowed: frozenset[str], *, context: str) -> None:
    unknown = set(payload) - allowed
    missing = allowed - set(payload)
    if unknown:
        raise TrustContractError(
            f"{context} contains unknown fields",
            reason=AdmissionReason.UNKNOWN_FIELD,
        )
    if missing:
        raise TrustContractError(
            f"{context} is missing required fields",
            reason=AdmissionReason.MALFORMED,
        )


def _text(value: Any, field_name: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str:
        raise TrustContractError(f"{field_name} must be a string", reason=AdmissionReason.MALFORMED)
    if value.strip() != value or (not value and not allow_empty):
        raise TrustContractError(
            f"{field_name} must be exact non-whitespace text",
            reason=AdmissionReason.MALFORMED,
        )
    if len(value.encode("utf-8")) > MAX_TEXT_BYTES:
        raise TrustContractError(
            f"{field_name} exceeds its byte budget", reason=AdmissionReason.OVER_BUDGET
        )
    return value


def _identifier(value: Any, field_name: str) -> str:
    text = _text(value, field_name)
    if not _IDENTIFIER_RE.fullmatch(text):
        raise TrustContractError(
            f"{field_name} is not a bounded identifier",
            reason=AdmissionReason.MALFORMED,
        )
    return text


def _cid(value: Any, field_name: str) -> str:
    text = _text(value, field_name)
    if not _CID_RE.fullmatch(text):
        raise TrustContractError(
            f"{field_name} is not a strict content identity",
            reason=AdmissionReason.MALFORMED,
        )
    return text


def _generation(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= MAX_SAFE_INTEGER:
        raise TrustContractError(
            "generation must be a bounded non-negative integer",
            reason=AdmissionReason.MALFORMED,
        )
    return value


def _enum(value: Any, enum_type: type[Enum], field_name: str) -> Any:
    if isinstance(value, enum_type):
        return value
    if type(value) is not str:
        raise TrustContractError(
            f"{field_name} must be a closed string value",
            reason=AdmissionReason.MALFORMED,
        )
    try:
        return enum_type(value)
    except ValueError as exc:
        raise TrustContractError(
            f"{field_name} is not a closed value", reason=AdmissionReason.MALFORMED
        ) from exc


def _closed_sequence(value: Any, field_name: str, *, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise TrustContractError(f"{field_name} must be an array", reason=AdmissionReason.MALFORMED)
    if len(value) > maximum:
        raise TrustContractError(
            f"{field_name} exceeds its item budget", reason=AdmissionReason.OVER_BUDGET
        )
    return tuple(value)


class _DuplicateKey(ValueError):
    pass


def _pairs_to_dict(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _parse_json_object(data: bytes, *, context: str) -> dict[str, Any]:
    if type(data) is not bytes:
        raise TrustContractError(f"{context} must be exact bytes", reason=AdmissionReason.MALFORMED)
    if not data or len(data) > MAX_DESCRIPTOR_BYTES:
        reason = AdmissionReason.OVER_BUDGET if data else AdmissionReason.MALFORMED
        raise TrustContractError(f"{context} has an invalid byte size", reason=reason)
    try:
        text = data.decode("utf-8")
        payload = json.loads(
            text,
            object_pairs_hook=_pairs_to_dict,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
    except (_DuplicateKey, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise TrustContractError(
            f"{context} is not strict UTF-8 JSON", reason=AdmissionReason.MALFORMED
        ) from exc
    if not isinstance(payload, dict):
        raise TrustContractError(
            f"{context} must be a JSON object", reason=AdmissionReason.MALFORMED
        )
    return payload


@dataclass(frozen=True)
class EvidenceReference:
    """Exact immutable artifact binding used by the trust closure."""

    cid: str
    kind: ArtifactKind
    byte_length: int
    payload_schema: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "cid", _cid(self.cid, "cid"))
        try:
            kind = coerce_artifact_kind(self.kind, field_name="kind")
        except ProofSealStoreContractError as exc:
            raise TrustContractError(
                "kind is outside the closed artifact vocabulary",
                reason=AdmissionReason.MALFORMED,
            ) from exc
        object.__setattr__(self, "kind", kind)
        if type(self.byte_length) is not int or not 0 < self.byte_length <= MAX_DESCRIPTOR_BYTES:
            raise TrustContractError(
                "byte_length must be a positive bounded integer",
                reason=AdmissionReason.MALFORMED,
            )
        object.__setattr__(
            self, "payload_schema", _identifier(self.payload_schema, "payload_schema")
        )

    @property
    def artifact_reference(self) -> ArtifactReference:
        return ArtifactReference(
            cid=self.cid,
            kind=self.kind,
            byte_length=self.byte_length,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cid": self.cid,
            "kind": self.kind.value,
            "byte_length": self.byte_length,
            "payload_schema": self.payload_schema,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EvidenceReference:
        if not isinstance(payload, Mapping):
            raise TrustContractError(
                "reference must be an object", reason=AdmissionReason.MALFORMED
            )
        _strict_fields(payload, _REFERENCE_FIELDS, context="reference")
        return cls(
            cid=payload.get("cid"),
            kind=payload.get("kind"),
            byte_length=payload.get("byte_length"),
            payload_schema=payload.get("payload_schema"),
        )


def _normalize_references(value: Any) -> tuple[EvidenceReference, ...]:
    raw = _closed_sequence(value, "references", maximum=MAX_REFERENCES)
    references = tuple(
        item if isinstance(item, EvidenceReference) else EvidenceReference.from_dict(item)
        for item in raw
    )
    identities = tuple(item.cid for item in references)
    if len(set(identities)) != len(identities):
        raise TrustContractError(
            "references must not repeat a CID", reason=AdmissionReason.MALFORMED
        )
    ordered = tuple(
        sorted(
            references,
            key=lambda item: (
                item.cid,
                item.kind.value,
                item.payload_schema,
                item.byte_length,
            ),
        )
    )
    return ordered


@dataclass(frozen=True)
class SignatureClaim:
    """Detached Ed25519 claim; verification belongs to the injected authority."""

    algorithm: str
    signer: str
    value: str

    def __post_init__(self) -> None:
        if self.algorithm != "ed25519":
            raise TrustContractError(
                "signature algorithm must be ed25519",
                reason=AdmissionReason.MALFORMED,
            )
        object.__setattr__(self, "signer", _identifier(self.signer, "signer"))
        encoded = _text(self.value, "signature.value")
        try:
            decoded = base64.b64decode(
                encoded + "=" * (-len(encoded) % 4),
                altchars=b"-_",
                validate=True,
            )
        except (ValueError, base64.binascii.Error) as exc:
            raise TrustContractError(
                "signature.value must be unpadded base64url",
                reason=AdmissionReason.MALFORMED,
            ) from exc
        if len(decoded) != MAX_SIGNATURE_BYTES or "=" in encoded:
            raise TrustContractError(
                "signature.value must encode exactly 64 bytes without padding",
                reason=AdmissionReason.MALFORMED,
            )

    @property
    def signature_bytes(self) -> bytes:
        return base64.b64decode(
            self.value + "=" * (-len(self.value) % 4),
            altchars=b"-_",
            validate=True,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "algorithm": self.algorithm,
            "signer": self.signer,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SignatureClaim:
        if not isinstance(payload, Mapping):
            raise TrustContractError(
                "signature must be an object or null", reason=AdmissionReason.MALFORMED
            )
        _strict_fields(payload, _SIGNATURE_FIELDS, context="signature")
        return cls(
            algorithm=payload.get("algorithm"),
            signer=payload.get("signer"),
            value=payload.get("value"),
        )


@dataclass(frozen=True)
class TrustEvidence:
    """Closed canonical descriptor around one immutable subject and its closure."""

    subject: EvidenceReference
    producer: str
    repository_id: str
    tree_id: str
    environment_cid: str
    policy_cid: str
    generation: int
    parent_seal_cids: tuple[str, ...]
    provenance: EvidenceProvenance
    freshness: EvidenceFreshness
    terminal_status: str
    evidence_mode: EvidenceMode
    cache_key: str
    references: tuple[EvidenceReference, ...]
    signature: SignatureClaim | None
    schema: str = TRUST_EVIDENCE_SCHEMA
    contract_version: int = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.schema != TRUST_EVIDENCE_SCHEMA or self.contract_version != CONTRACT_VERSION:
            raise TrustContractError(
                "trust evidence schema/version mismatch",
                reason=AdmissionReason.MALFORMED,
            )
        if not isinstance(self.subject, EvidenceReference):
            if isinstance(self.subject, Mapping):
                object.__setattr__(self, "subject", EvidenceReference.from_dict(self.subject))
            else:
                raise TrustContractError(
                    "subject must be an EvidenceReference",
                    reason=AdmissionReason.MALFORMED,
                )
        object.__setattr__(self, "producer", _identifier(self.producer, "producer"))
        object.__setattr__(self, "repository_id", _identifier(self.repository_id, "repository_id"))
        tree = _text(self.tree_id, "tree_id")
        if not _TREE_RE.fullmatch(tree):
            raise TrustContractError(
                "tree_id must be a lowercase Git tree identity",
                reason=AdmissionReason.MALFORMED,
            )
        object.__setattr__(self, "tree_id", tree)
        object.__setattr__(self, "environment_cid", _cid(self.environment_cid, "environment_cid"))
        object.__setattr__(self, "policy_cid", _cid(self.policy_cid, "policy_cid"))
        object.__setattr__(self, "generation", _generation(self.generation))

        raw_parents = _closed_sequence(
            self.parent_seal_cids, "parent_seal_cids", maximum=MAX_REFERENCES
        )
        parents = tuple(
            _cid(item, f"parent_seal_cids[{index}]") for index, item in enumerate(raw_parents)
        )
        if len(set(parents)) != len(parents):
            raise TrustContractError(
                "parent_seal_cids must not repeat", reason=AdmissionReason.MALFORMED
            )
        object.__setattr__(self, "parent_seal_cids", parents)
        object.__setattr__(
            self, "provenance", _enum(self.provenance, EvidenceProvenance, "provenance")
        )
        object.__setattr__(self, "freshness", _enum(self.freshness, EvidenceFreshness, "freshness"))
        object.__setattr__(
            self, "evidence_mode", _enum(self.evidence_mode, EvidenceMode, "evidence_mode")
        )
        object.__setattr__(
            self, "terminal_status", _identifier(self.terminal_status, "terminal_status")
        )
        object.__setattr__(self, "cache_key", _text(self.cache_key, "cache_key", allow_empty=True))
        object.__setattr__(self, "references", _normalize_references(self.references))
        if self.subject.cid in {item.cid for item in self.references}:
            raise TrustContractError(
                "subject must not be repeated in references",
                reason=AdmissionReason.MALFORMED,
            )
        if self.signature is not None and not isinstance(self.signature, SignatureClaim):
            if isinstance(self.signature, Mapping):
                object.__setattr__(self, "signature", SignatureClaim.from_dict(self.signature))
            else:
                raise TrustContractError(
                    "signature must be a SignatureClaim or null",
                    reason=AdmissionReason.MALFORMED,
                )

    def to_dict(self, *, include_signature: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": self.schema,
            "contract_version": self.contract_version,
            "subject": self.subject.to_dict(),
            "producer": self.producer,
            "repository_id": self.repository_id,
            "tree_id": self.tree_id,
            "environment_cid": self.environment_cid,
            "policy_cid": self.policy_cid,
            "generation": self.generation,
            "parent_seal_cids": list(self.parent_seal_cids),
            "provenance": self.provenance.value,
            "freshness": self.freshness.value,
            "terminal_status": self.terminal_status,
            "evidence_mode": self.evidence_mode.value,
            "cache_key": self.cache_key,
            "references": [item.to_dict() for item in self.references],
        }
        if include_signature:
            payload["signature"] = self.signature.to_dict() if self.signature else None
        return payload

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.to_dict())

    def signing_bytes(self) -> bytes:
        return _canonical_json_bytes(
            {"domain": SIGNATURE_DOMAIN, "evidence": self.to_dict(include_signature=False)}
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> TrustEvidence:
        if not isinstance(payload, Mapping):
            raise TrustContractError(
                "trust evidence must be an object", reason=AdmissionReason.MALFORMED
            )
        _strict_fields(payload, _ROOT_FIELDS, context="trust evidence")
        raw_signature = payload.get("signature")
        return cls(
            subject=EvidenceReference.from_dict(payload.get("subject")),
            producer=payload.get("producer"),
            repository_id=payload.get("repository_id"),
            tree_id=payload.get("tree_id"),
            environment_cid=payload.get("environment_cid"),
            policy_cid=payload.get("policy_cid"),
            generation=payload.get("generation"),
            parent_seal_cids=payload.get("parent_seal_cids"),
            provenance=payload.get("provenance"),
            freshness=payload.get("freshness"),
            terminal_status=payload.get("terminal_status"),
            evidence_mode=payload.get("evidence_mode"),
            cache_key=payload.get("cache_key"),
            references=payload.get("references"),
            signature=(
                SignatureClaim.from_dict(raw_signature) if raw_signature is not None else None
            ),
            schema=payload.get("schema"),
            contract_version=payload.get("contract_version"),
        )

    @classmethod
    def from_canonical_bytes(cls, data: bytes) -> TrustEvidence:
        payload = _parse_json_object(data, context="trust evidence descriptor")
        evidence = cls.from_dict(payload)
        if evidence.canonical_bytes() != data:
            raise TrustContractError(
                "trust evidence bytes are not the unique canonical encoding",
                reason=AdmissionReason.NON_CANONICAL,
            )
        return evidence


_STATUS_MODE: Final[Mapping[str, EvidenceMode]] = {
    "proved": EvidenceMode.CRYPTOGRAPHIC,
    "integrity_verified": EvidenceMode.INTEGRITY,
    "signed_assertion_verified": EvidenceMode.SIGNED_ASSERTION,
    "sealed": EvidenceMode.SEAL,
}
_TRUST_ROOT_KINDS: Final[frozenset[ArtifactKind]] = frozenset(
    {
        ArtifactKind.PROOF_OBJECT,
        ArtifactKind.PROOF_RECEIPT,
        ArtifactKind.CHECKPOINT_SEAL,
        ArtifactKind.DELTA_SEAL,
    }
)
_SEAL_ROOT_KINDS: Final[frozenset[ArtifactKind]] = frozenset(
    {ArtifactKind.CHECKPOINT_SEAL, ArtifactKind.DELTA_SEAL}
)


def _kind_status_is_closed(kind: ArtifactKind, terminal_status: str, mode: EvidenceMode) -> bool:
    if kind in _SEAL_ROOT_KINDS:
        return terminal_status == "sealed" and mode is EvidenceMode.SEAL
    return terminal_status != "sealed" and mode is not EvidenceMode.SEAL


@dataclass(frozen=True)
class TrustExpectation:
    """Caller-owned exact current context against which evidence is admitted."""

    subject: EvidenceReference
    producer: str
    repository_id: str
    tree_id: str
    environment_cid: str
    policy_cid: str
    generation: int
    parent_seal_cids: tuple[str, ...]
    terminal_status: str
    evidence_mode: EvidenceMode
    cache_key: str
    references: tuple[EvidenceReference, ...]
    signature_required: bool
    signer: str = ""
    signature_algorithm: str = ""
    schema: str = TRUST_EXPECTATION_SCHEMA
    contract_version: int = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.schema != TRUST_EXPECTATION_SCHEMA or self.contract_version != CONTRACT_VERSION:
            raise TrustContractError(
                "trust expectation schema/version mismatch",
                reason=AdmissionReason.MALFORMED,
            )
        if not isinstance(self.subject, EvidenceReference):
            raise TrustContractError(
                "expectation subject must be an EvidenceReference",
                reason=AdmissionReason.MALFORMED,
            )
        if self.subject.kind not in _TRUST_ROOT_KINDS:
            raise TrustContractError(
                "expectation subject kind is outside receipt/proof/seal admission",
                reason=AdmissionReason.MALFORMED,
            )
        object.__setattr__(self, "producer", _identifier(self.producer, "producer"))
        object.__setattr__(self, "repository_id", _identifier(self.repository_id, "repository_id"))
        if not _TREE_RE.fullmatch(_text(self.tree_id, "tree_id")):
            raise TrustContractError(
                "tree_id must be a lowercase Git tree identity",
                reason=AdmissionReason.MALFORMED,
            )
        object.__setattr__(self, "environment_cid", _cid(self.environment_cid, "environment_cid"))
        object.__setattr__(self, "policy_cid", _cid(self.policy_cid, "policy_cid"))
        object.__setattr__(self, "generation", _generation(self.generation))
        parents = tuple(
            _cid(item, f"parent_seal_cids[{index}]")
            for index, item in enumerate(
                _closed_sequence(
                    self.parent_seal_cids,
                    "parent_seal_cids",
                    maximum=MAX_REFERENCES,
                )
            )
        )
        if len(set(parents)) != len(parents):
            raise TrustContractError(
                "parent_seal_cids must not repeat", reason=AdmissionReason.MALFORMED
            )
        object.__setattr__(self, "parent_seal_cids", parents)
        status = _identifier(self.terminal_status, "terminal_status")
        mode = _enum(self.evidence_mode, EvidenceMode, "evidence_mode")
        if _STATUS_MODE.get(status) is not mode:
            raise TrustContractError(
                "terminal_status and evidence_mode are not a closed pair",
                reason=AdmissionReason.MALFORMED,
            )
        if not _kind_status_is_closed(self.subject.kind, status, mode):
            raise TrustContractError(
                "subject kind and terminal status are not a closed pair",
                reason=AdmissionReason.MALFORMED,
            )
        object.__setattr__(self, "terminal_status", status)
        object.__setattr__(self, "evidence_mode", mode)
        object.__setattr__(self, "cache_key", _text(self.cache_key, "cache_key", allow_empty=True))
        object.__setattr__(self, "references", _normalize_references(self.references))
        if type(self.signature_required) is not bool:
            raise TrustContractError(
                "signature_required must be a boolean",
                reason=AdmissionReason.MALFORMED,
            )
        if self.signature_required:
            object.__setattr__(self, "signer", _identifier(self.signer, "signer"))
            if self.signature_algorithm != "ed25519":
                raise TrustContractError(
                    "required signature algorithm must be ed25519",
                    reason=AdmissionReason.MALFORMED,
                )
        elif self.signer or self.signature_algorithm:
            raise TrustContractError(
                "optional unsigned expectations cannot carry signer bindings",
                reason=AdmissionReason.MALFORMED,
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "contract_version": self.contract_version,
            "subject": self.subject.to_dict(),
            "producer": self.producer,
            "repository_id": self.repository_id,
            "tree_id": self.tree_id,
            "environment_cid": self.environment_cid,
            "policy_cid": self.policy_cid,
            "generation": self.generation,
            "parent_seal_cids": list(self.parent_seal_cids),
            "terminal_status": self.terminal_status,
            "evidence_mode": self.evidence_mode.value,
            "cache_key": self.cache_key,
            "references": [item.to_dict() for item in self.references],
            "signature_required": self.signature_required,
            "signer": self.signer,
            "signature_algorithm": self.signature_algorithm,
        }

    @property
    def cid(self) -> str:
        return content_cid_for_bytes(_canonical_json_bytes(self.to_dict()))


@dataclass(frozen=True)
class VerifiedArtifact:
    """One exact-byte, schema-checked immutable read supplied to live authority."""

    reference: EvidenceReference
    data: bytes
    payload: Mapping[str, Any]


@runtime_checkable
class VerifiedByteReader(Protocol):
    """Read-only subset of the canonical immutable store."""

    def get_verified_bytes(self, reference: ArtifactReference) -> bytes:
        """Return exact rehashed bytes or fail closed."""


@runtime_checkable
class SignatureAuthority(Protocol):
    """Injected installed authority for detached signature verification."""

    def verify_signature(
        self,
        *,
        algorithm: str,
        signer: str,
        message: bytes,
        signature: bytes,
    ) -> bool:
        """Return exact ``True`` only for a valid signature."""


@runtime_checkable
class LiveProvenanceAuthority(Protocol):
    """Injected authority that compares the descriptor with current live state."""

    def verify_live_provenance(
        self,
        *,
        evidence: TrustEvidence,
        expectation: TrustExpectation,
        subject: VerifiedArtifact,
        references: tuple[VerifiedArtifact, ...],
    ) -> bool:
        """Return exact ``True`` only after a current live observation."""


@dataclass(frozen=True)
class TrustGrant:
    """Deterministic immutable result of all local and injected trust checks."""

    evidence_descriptor_cid: str
    expectation_cid: str
    subject: EvidenceReference
    generation: int
    parent_seal_cids: tuple[str, ...]
    verified_reference_cids: tuple[str, ...]
    signature_status: SignatureStatus
    provenance_status: ProvenanceStatus
    schema: str = TRUST_GRANT_SCHEMA
    interface: str = TRUST_ADMISSION_INTERFACE
    qualification_credit: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "interface": self.interface,
            "evidence_descriptor_cid": self.evidence_descriptor_cid,
            "expectation_cid": self.expectation_cid,
            "subject": self.subject.to_dict(),
            "generation": self.generation,
            "parent_seal_cids": list(self.parent_seal_cids),
            "verified_reference_cids": list(self.verified_reference_cids),
            "signature_status": self.signature_status.value,
            "provenance_status": self.provenance_status.value,
            "qualification_credit": self.qualification_credit,
        }

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.to_dict())

    @property
    def cid(self) -> str:
        return content_cid_for_bytes(self.canonical_bytes)


@dataclass(frozen=True)
class TrustAdmissionResult:
    """Typed fail-closed admission result."""

    admitted: bool
    reason: AdmissionReason
    checks: tuple[str, ...] = ()
    evidence: TrustEvidence | None = None
    grant: TrustGrant | None = None
    signature_status: SignatureStatus = SignatureStatus.NOT_REQUIRED
    provenance_status: ProvenanceStatus = ProvenanceStatus.UNAVAILABLE

    def __post_init__(self) -> None:
        if self.admitted is not (self.reason is AdmissionReason.ADMITTED):
            raise ValueError("admitted and reason must agree")
        if self.admitted and self.grant is None:
            raise ValueError("admitted results require a TrustGrant")
        if not self.admitted and self.grant is not None:
            raise ValueError("rejected results cannot carry a TrustGrant")

    @property
    def may_reuse(self) -> bool:
        return self.admitted

    @property
    def may_publish(self) -> bool:
        return self.admitted

    @property
    def qualification_credit(self) -> bool:
        return False

    def __bool__(self) -> bool:
        return self.admitted


def _failed(
    reason: AdmissionReason,
    *,
    checks: list[str],
    evidence: TrustEvidence | None = None,
    signature_status: SignatureStatus = SignatureStatus.NOT_REQUIRED,
    provenance_status: ProvenanceStatus = ProvenanceStatus.UNAVAILABLE,
) -> TrustAdmissionResult:
    return TrustAdmissionResult(
        admitted=False,
        reason=reason,
        checks=tuple(checks),
        evidence=evidence,
        signature_status=signature_status,
        provenance_status=provenance_status,
    )


def _payload_cids(value: Any) -> frozenset[str]:
    found: set[str] = set()

    def visit(item: Any) -> None:
        if type(item) is str and _CID_RE.fullmatch(item):
            found.add(item)
        elif isinstance(item, Mapping):
            for key, nested in item.items():
                if type(key) is not str:
                    continue
                visit(nested)
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for nested in item:
                visit(nested)

    visit(value)
    return frozenset(found)


def _artifact_matches(left: ArtifactReference, right: ArtifactReference) -> bool:
    return (
        left.cid == right.cid
        and left.kind is right.kind
        and left.byte_length == right.byte_length
        and left.role is ArtifactRole.ADMITTED
        and right.role is ArtifactRole.ADMITTED
    )


class TrustAdmissionVerifier:
    """Read-only fail-closed verifier over canonical store contracts."""

    def __init__(
        self,
        reader: VerifiedByteReader,
        *,
        live_provenance_authority: LiveProvenanceAuthority | None,
        signature_authority: SignatureAuthority | None = None,
    ) -> None:
        if not callable(getattr(reader, "get_verified_bytes", None)):
            raise TypeError("reader must implement get_verified_bytes")
        self._reader = reader
        self._live_authority = live_provenance_authority
        self._signature_authority = signature_authority

    def admit(
        self,
        descriptor_bytes: bytes,
        *,
        claimed_descriptor_cid: str,
        expectation: TrustExpectation,
        cache_candidate: CacheCandidate | None = None,
    ) -> TrustAdmissionResult:
        """Verify one descriptor, subject, closure, signature, and live context."""

        checks: list[str] = []
        if not isinstance(expectation, TrustExpectation):
            return _failed(AdmissionReason.MALFORMED, checks=checks)
        if type(descriptor_bytes) is not bytes:
            return _failed(AdmissionReason.MALFORMED, checks=checks)
        if not descriptor_bytes or len(descriptor_bytes) > MAX_DESCRIPTOR_BYTES:
            reason = AdmissionReason.OVER_BUDGET if descriptor_bytes else AdmissionReason.MALFORMED
            return _failed(reason, checks=checks)
        try:
            claimed = _cid(claimed_descriptor_cid, "claimed_descriptor_cid")
        except TrustContractError as exc:
            return _failed(exc.reason, checks=checks)
        if not verify_content_identity(claimed, descriptor_bytes):
            return _failed(AdmissionReason.DESCRIPTOR_CID_MISMATCH, checks=checks)
        checks.append("descriptor_bytes_cid")

        try:
            evidence = TrustEvidence.from_canonical_bytes(descriptor_bytes)
        except TrustContractError as exc:
            return _failed(exc.reason, checks=checks)
        checks.append("descriptor_schema_canonical")

        mismatch = self._expectation_mismatch(evidence, expectation)
        if mismatch is not None:
            return _failed(mismatch, checks=checks, evidence=evidence)
        checks.append("current_context_bindings")

        if cache_candidate is not None:
            candidate_reason = self._cache_candidate_reason(cache_candidate, evidence, expectation)
            if candidate_reason is not None:
                return _failed(candidate_reason, checks=checks, evidence=evidence)
            checks.append("cache_candidate_binding")

        signature_status, signature_reason = self._verify_signature(evidence, expectation)
        if signature_reason is not None:
            return _failed(
                signature_reason,
                checks=checks,
                evidence=evidence,
                signature_status=signature_status,
            )
        checks.append("signature_policy")

        subject, subject_reason = self._load_artifact(
            evidence.subject,
            missing=AdmissionReason.SUBJECT_MISSING,
            corrupt=AdmissionReason.SUBJECT_CORRUPT,
            schema_mismatch=AdmissionReason.SUBJECT_SCHEMA_MISMATCH,
        )
        if subject_reason is not None or subject is None:
            return _failed(
                subject_reason or AdmissionReason.SUBJECT_CORRUPT,
                checks=checks,
                evidence=evidence,
                signature_status=signature_status,
            )
        checks.append("subject_bytes_cid_schema")

        verified_references: list[VerifiedArtifact] = []
        for reference in evidence.references:
            verified, reference_reason = self._load_artifact(
                reference,
                missing=AdmissionReason.REFERENCE_MISSING,
                corrupt=AdmissionReason.REFERENCE_CORRUPT,
                schema_mismatch=AdmissionReason.REFERENCE_SCHEMA_MISMATCH,
            )
            if reference_reason is not None or verified is None:
                return _failed(
                    reference_reason or AdmissionReason.REFERENCE_CORRUPT,
                    checks=checks,
                    evidence=evidence,
                    signature_status=signature_status,
                )
            verified_references.append(verified)
        checks.append("transitive_bytes_cid_schema")

        if not self._closure_is_complete(evidence, subject, verified_references):
            return _failed(
                AdmissionReason.MISSING_EVIDENCE,
                checks=checks,
                evidence=evidence,
                signature_status=signature_status,
            )
        checks.append("transitive_closure")

        provenance_status, provenance_reason = self._verify_live_provenance(
            evidence,
            expectation,
            subject,
            tuple(verified_references),
        )
        if provenance_reason is not None:
            return _failed(
                provenance_reason,
                checks=checks,
                evidence=evidence,
                signature_status=signature_status,
                provenance_status=provenance_status,
            )
        checks.append("live_provenance")

        grant = TrustGrant(
            evidence_descriptor_cid=claimed,
            expectation_cid=expectation.cid,
            subject=evidence.subject,
            generation=evidence.generation,
            parent_seal_cids=evidence.parent_seal_cids,
            verified_reference_cids=tuple(item.reference.cid for item in verified_references),
            signature_status=signature_status,
            provenance_status=provenance_status,
        )
        return TrustAdmissionResult(
            admitted=True,
            reason=AdmissionReason.ADMITTED,
            checks=tuple(checks),
            evidence=evidence,
            grant=grant,
            signature_status=signature_status,
            provenance_status=provenance_status,
        )

    @staticmethod
    def _expectation_mismatch(
        evidence: TrustEvidence, expectation: TrustExpectation
    ) -> AdmissionReason | None:
        if evidence.subject != expectation.subject:
            return AdmissionReason.SUBJECT_BINDING_MISMATCH
        if evidence.producer != expectation.producer:
            return AdmissionReason.PRODUCER_MISMATCH
        if evidence.repository_id != expectation.repository_id:
            return AdmissionReason.REPOSITORY_MISMATCH
        if evidence.tree_id != expectation.tree_id:
            return AdmissionReason.TREE_MISMATCH
        if evidence.environment_cid != expectation.environment_cid:
            return AdmissionReason.ENVIRONMENT_MISMATCH
        if evidence.policy_cid != expectation.policy_cid:
            return AdmissionReason.POLICY_MISMATCH
        if evidence.generation != expectation.generation:
            return AdmissionReason.GENERATION_MISMATCH
        if evidence.parent_seal_cids != expectation.parent_seal_cids:
            return AdmissionReason.PARENT_MISMATCH
        if evidence.references != expectation.references:
            return AdmissionReason.REFERENCE_MISMATCH
        if evidence.provenance is EvidenceProvenance.SIMULATED:
            return AdmissionReason.SIMULATED
        if evidence.evidence_mode is EvidenceMode.SIMULATED:
            return AdmissionReason.SIMULATED
        if evidence.provenance is not EvidenceProvenance.LIVE:
            return AdmissionReason.PROVENANCE_NOT_LIVE
        if evidence.freshness is EvidenceFreshness.STALE:
            return AdmissionReason.STALE
        if evidence.terminal_status != expectation.terminal_status:
            return AdmissionReason.STATUS_MISMATCH
        if evidence.evidence_mode is not expectation.evidence_mode:
            return AdmissionReason.STATUS_MISMATCH
        if evidence.cache_key != expectation.cache_key:
            return AdmissionReason.CACHE_KEY_MISMATCH
        if _STATUS_MODE.get(evidence.terminal_status) is not evidence.evidence_mode:
            return AdmissionReason.STATUS_MISMATCH
        if not _kind_status_is_closed(
            evidence.subject.kind,
            evidence.terminal_status,
            evidence.evidence_mode,
        ):
            return AdmissionReason.STATUS_MISMATCH
        if evidence.subject.kind not in _TRUST_ROOT_KINDS:
            return AdmissionReason.SUBJECT_BINDING_MISMATCH
        return None

    @staticmethod
    def _cache_candidate_reason(
        candidate: CacheCandidate,
        evidence: TrustEvidence,
        expectation: TrustExpectation,
    ) -> AdmissionReason | None:
        if not isinstance(candidate, CacheCandidate):
            return AdmissionReason.CACHE_CANDIDATE_INVALID
        if (
            candidate.role is not ArtifactRole.CANDIDATE
            or candidate.requires_fresh_verification is not True
            or candidate.is_acceptance_authority
        ):
            return AdmissionReason.CACHE_CANDIDATE_INVALID
        if not expectation.cache_key or candidate.cache_key != expectation.cache_key:
            return AdmissionReason.CACHE_KEY_MISMATCH
        if not _artifact_matches(candidate.artifact, evidence.subject.artifact_reference):
            return AdmissionReason.CACHE_ARTIFACT_MISMATCH
        return None

    def _verify_signature(
        self, evidence: TrustEvidence, expectation: TrustExpectation
    ) -> tuple[SignatureStatus, AdmissionReason | None]:
        claim = evidence.signature
        if not expectation.signature_required:
            if claim is not None:
                return (
                    SignatureStatus.INVALID,
                    AdmissionReason.SIGNATURE_BINDING_MISMATCH,
                )
            return SignatureStatus.NOT_REQUIRED, None
        if claim is None:
            return SignatureStatus.MISSING, AdmissionReason.SIGNATURE_REQUIRED
        if claim.signer != expectation.signer or claim.algorithm != expectation.signature_algorithm:
            return SignatureStatus.INVALID, AdmissionReason.SIGNATURE_BINDING_MISMATCH
        if self._signature_authority is None:
            return (
                SignatureStatus.UNAVAILABLE,
                AdmissionReason.SIGNATURE_AUTHORITY_UNAVAILABLE,
            )
        try:
            verified = self._signature_authority.verify_signature(
                algorithm=claim.algorithm,
                signer=claim.signer,
                message=evidence.signing_bytes(),
                signature=claim.signature_bytes,
            )
        except Exception:  # noqa: BLE001 - an injected authority must fail closed
            return (
                SignatureStatus.UNAVAILABLE,
                AdmissionReason.SIGNATURE_AUTHORITY_UNAVAILABLE,
            )
        if type(verified) is not bool:
            return (
                SignatureStatus.UNAVAILABLE,
                AdmissionReason.SIGNATURE_AUTHORITY_UNAVAILABLE,
            )
        if not verified:
            return SignatureStatus.INVALID, AdmissionReason.SIGNATURE_INVALID
        return SignatureStatus.VERIFIED, None

    def _load_artifact(
        self,
        reference: EvidenceReference,
        *,
        missing: AdmissionReason,
        corrupt: AdmissionReason,
        schema_mismatch: AdmissionReason,
    ) -> tuple[VerifiedArtifact | None, AdmissionReason | None]:
        try:
            data = self._reader.get_verified_bytes(reference.artifact_reference)
        except LocalStoreNotFoundError:
            return None, missing
        except LocalStoreIntegrityError:
            return None, corrupt
        except Exception:  # noqa: BLE001 - an injected reader must fail closed
            return None, corrupt
        if type(data) is not bytes:
            return None, corrupt
        if len(data) != reference.byte_length or not verify_content_identity(reference.cid, data):
            return None, corrupt
        try:
            payload = _parse_json_object(data, context="referenced artifact")
        except TrustContractError:
            return None, corrupt
        if _canonical_json_bytes(payload) != data:
            return None, corrupt
        if payload.get("schema") != reference.payload_schema:
            return None, schema_mismatch
        return VerifiedArtifact(reference=reference, data=data, payload=payload), None

    @staticmethod
    def _closure_is_complete(
        evidence: TrustEvidence,
        subject: VerifiedArtifact,
        references: list[VerifiedArtifact],
    ) -> bool:
        by_cid = {item.reference.cid: item for item in references}
        required_roots = {
            evidence.environment_cid,
            evidence.policy_cid,
            *evidence.parent_seal_cids,
        }
        if not required_roots.issubset(by_cid):
            return False

        declared = set(by_cid)
        reachable = set(required_roots)
        discovered = set(_payload_cids(subject.payload))
        if not discovered.issubset(declared | {evidence.subject.cid}):
            return False
        reachable.update(discovered & declared)

        scanned: set[str] = set()
        while reachable - scanned:
            cid = min(reachable - scanned)
            scanned.add(cid)
            payload = by_cid[cid].payload
            nested = set(_payload_cids(payload))
            if not nested.issubset(declared | {evidence.subject.cid}):
                return False
            reachable.update(nested & declared)
        return reachable == declared

    def _verify_live_provenance(
        self,
        evidence: TrustEvidence,
        expectation: TrustExpectation,
        subject: VerifiedArtifact,
        references: tuple[VerifiedArtifact, ...],
    ) -> tuple[ProvenanceStatus, AdmissionReason | None]:
        if self._live_authority is None:
            return (
                ProvenanceStatus.UNAVAILABLE,
                AdmissionReason.PROVENANCE_AUTHORITY_UNAVAILABLE,
            )
        try:
            verified = self._live_authority.verify_live_provenance(
                evidence=evidence,
                expectation=expectation,
                subject=subject,
                references=references,
            )
        except Exception:  # noqa: BLE001 - an injected authority must fail closed
            return (
                ProvenanceStatus.UNAVAILABLE,
                AdmissionReason.PROVENANCE_AUTHORITY_UNAVAILABLE,
            )
        if type(verified) is not bool:
            return (
                ProvenanceStatus.UNAVAILABLE,
                AdmissionReason.PROVENANCE_AUTHORITY_UNAVAILABLE,
            )
        if not verified:
            return ProvenanceStatus.INVALID, AdmissionReason.PROVENANCE_INVALID
        return ProvenanceStatus.VERIFIED, None


def admit_evidence(
    reader: VerifiedByteReader,
    descriptor_bytes: bytes,
    *,
    claimed_descriptor_cid: str,
    expectation: TrustExpectation,
    live_provenance_authority: LiveProvenanceAuthority | None,
    signature_authority: SignatureAuthority | None = None,
) -> TrustAdmissionResult:
    """Convenience wrapper for receipt/proof/seal trust admission."""

    return TrustAdmissionVerifier(
        reader,
        live_provenance_authority=live_provenance_authority,
        signature_authority=signature_authority,
    ).admit(
        descriptor_bytes,
        claimed_descriptor_cid=claimed_descriptor_cid,
        expectation=expectation,
    )


def admit_cache_candidate(
    reader: VerifiedByteReader,
    candidate: CacheCandidate,
    descriptor_bytes: bytes,
    *,
    claimed_descriptor_cid: str,
    expectation: TrustExpectation,
    live_provenance_authority: LiveProvenanceAuthority | None,
    signature_authority: SignatureAuthority | None = None,
) -> TrustAdmissionResult:
    """Admit an exact cache candidate without writing or promoting the index."""

    return TrustAdmissionVerifier(
        reader,
        live_provenance_authority=live_provenance_authority,
        signature_authority=signature_authority,
    ).admit(
        descriptor_bytes,
        claimed_descriptor_cid=claimed_descriptor_cid,
        expectation=expectation,
        cache_candidate=candidate,
    )


__all__ = [
    "CONTRACT_VERSION",
    "MAX_DESCRIPTOR_BYTES",
    "SIGNATURE_DOMAIN",
    "TRUST_ADMISSION_INTERFACE",
    "TRUST_EVIDENCE_SCHEMA",
    "TRUST_EXPECTATION_SCHEMA",
    "TRUST_GRANT_SCHEMA",
    "AdmissionReason",
    "AuthorityUnavailableError",
    "EvidenceFreshness",
    "EvidenceMode",
    "EvidenceProvenance",
    "EvidenceReference",
    "LiveProvenanceAuthority",
    "ProvenanceStatus",
    "SignatureAuthority",
    "SignatureClaim",
    "SignatureStatus",
    "TrustAdmissionResult",
    "TrustAdmissionVerifier",
    "TrustContractError",
    "TrustEvidence",
    "TrustExpectation",
    "TrustGrant",
    "VerifiedArtifact",
    "VerifiedByteReader",
    "admit_cache_candidate",
    "admit_evidence",
]
