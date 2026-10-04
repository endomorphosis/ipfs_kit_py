"""Verified semantic-object and model-pinned projection storage.

``VerifiedSemanticBlockStore`` implements ``VerifiedSemanticStore@1``.  It
composes ``SemanticWorldArtifactStore`` and datasets program-identity profiles.
It does not mint CIDs, decide equivalence, proof validity, prediction truth,
safe reuse, or task completion.

Authority rules (normative, fail-closed):

* Every retrieved block is rehashed through the kit coordination store.
* Projection identity binds every required model, tokenizer, preprocessor,
  metric, dtype, quantization, and privacy field.
* Vector bytes are stored before any projection record may reference them.
* Semantic-object subjects are stored before a projection may cite them.
* NaN, infinity, dimension mismatch, unspecified byte order, unpinned models
  or preprocessors, score-derived identity, and authoritative ANN claims fail
  closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Final, Mapping, Sequence

from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    PROJECTION_REQUIRED_FIELDS,
    ProgramIdentityError,
    ProjectionIdentity,
    ProjectionIndexManifestIdentity,
    ProjectionSubjectKind,
    SemanticObjectEnvelope,
    projection_from_bindings,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
)
from ipfs_kit_py.semantic_world_store.artifacts import (
    ARTIFACT_MODULE_INTERFACE,
    CanonicalVectorBytes,
    SemanticWorldArtifactAdmissionError,
    SemanticWorldArtifactConflictError,
    SemanticWorldArtifactError,
    SemanticWorldArtifactIntegrityError,
    SemanticWorldArtifactKind,
    SemanticWorldArtifactNotFound,
    SemanticWorldArtifactStore,
    SemanticWorldWriteResult,
    pack_canonical_vector,
)


VERIFIED_SEMANTIC_STORE_INTERFACE: Final[str] = "VerifiedSemanticStore@1"
PROJECTION_RECORD_INTERFACE: Final[str] = "ProjectionRecord@1"
PROJECTION_INDEX_MANIFEST_INTERFACE: Final[str] = "ProjectionIndexManifest@1"

_SCORE_IDENTITY_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "distance",
        "embedding_score",
        "knn",
        "nearest",
        "rank",
        "score",
        "scores",
        "similarity",
    }
)
_MUTABLE_DOCUMENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "document_id",
        "doc_id",
        "mutable_id",
        "row_id",
        "unresolved_id",
    }
)


class VerifiedSemanticStoreError(SemanticWorldArtifactError):
    """Base error for verified semantic/projection storage."""


class VerifiedSemanticStoreAdmissionError(
    VerifiedSemanticStoreError, SemanticWorldArtifactAdmissionError
):
    """Raised when a verified-store write is rejected."""


class VerifiedSemanticStoreIntegrityError(
    VerifiedSemanticStoreError, SemanticWorldArtifactIntegrityError
):
    """Raised when a retrieved block fails claimed-CID rehash or profile checks."""


class VerifiedSemanticStoreNotFound(
    VerifiedSemanticStoreError, SemanticWorldArtifactNotFound
):
    """Raised when a required verified block is absent."""


def _wrap_identity_error(exc: Exception) -> VerifiedSemanticStoreAdmissionError:
    return VerifiedSemanticStoreAdmissionError(str(exc))


def _reject_score_derived_identity(payload: Mapping[str, Any], *, path: str = "$") -> None:
    extra = set(payload) & _SCORE_IDENTITY_FIELDS
    if extra:
        raise VerifiedSemanticStoreAdmissionError(
            f"{path} rejects score-derived identity fields {sorted(extra)}"
        )
    extra_docs = set(payload) & _MUTABLE_DOCUMENT_FIELDS
    if extra_docs:
        raise VerifiedSemanticStoreAdmissionError(
            f"{path} rejects mutable unresolved document identity {sorted(extra_docs)}"
        )


def _require_projection_bindings(identity: ProjectionIdentity) -> None:
    payload = identity.to_dict()
    missing = [field for field in PROJECTION_REQUIRED_FIELDS if field not in payload]
    if missing:
        raise VerifiedSemanticStoreAdmissionError(
            f"projection identity missing required fields {missing}"
        )
    if payload.get("authoritative") is not False:
        raise VerifiedSemanticStoreAdmissionError(
            "projections are non-authoritative; they cannot mint semantic identity"
        )
    for field in (
        "model_cid",
        "tokenizer_cid",
        "preprocessing_profile_cid",
        "normalization_profile_cid",
    ):
        value = payload.get(field)
        if type(value) is not str or not value:
            raise VerifiedSemanticStoreAdmissionError(
                f"unpinned model or preprocessor: {field} must be a CID"
            )
    if payload.get("byte_order") not in {"little", "big"}:
        raise VerifiedSemanticStoreAdmissionError("unspecified byte order")
    if "quantization_profile_cid" not in payload:
        raise VerifiedSemanticStoreAdmissionError(
            "projection identity must bind quantization_profile_cid"
        )
    if type(payload.get("privacy_class")) is not str or not payload["privacy_class"]:
        raise VerifiedSemanticStoreAdmissionError(
            "projection identity must bind privacy_class"
        )
    if type(payload.get("metric")) is not str or not payload["metric"]:
        raise VerifiedSemanticStoreAdmissionError(
            "projection identity must bind metric"
        )
    if type(payload.get("dtype")) is not str or not payload["dtype"]:
        raise VerifiedSemanticStoreAdmissionError(
            "projection identity must bind dtype"
        )


@dataclass(frozen=True, slots=True)
class ProjectionRecord:
    """ProjectionRecord@1: stored, model-pinned, non-authoritative projection."""

    identity: ProjectionIdentity

    SCHEMA: ClassVar[str] = (
        "ipfs-datasets.software-contracts.projection-identity@1"
    )
    INTERFACE: ClassVar[str] = PROJECTION_RECORD_INTERFACE

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ProjectionIdentity):
            raise VerifiedSemanticStoreAdmissionError(
                "ProjectionRecord.identity must be a ProjectionIdentity"
            )
        _require_projection_bindings(self.identity)
        _reject_score_derived_identity(self.identity.to_dict(), path="projection")

    @property
    def projection_cid(self) -> str:
        return self.identity.projection_cid

    def to_payload(self) -> dict[str, Any]:
        return self.identity.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return self.to_payload()

    @classmethod
    def from_identity(cls, identity: ProjectionIdentity) -> "ProjectionRecord":
        return cls(identity=identity)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ProjectionRecord":
        _reject_score_derived_identity(payload, path="projection")
        try:
            identity = ProjectionIdentity.from_dict(payload)
        except ProgramIdentityError as exc:
            raise _wrap_identity_error(exc) from exc
        return cls(identity=identity)

    @classmethod
    def from_bindings(cls, **fields: Any) -> "ProjectionRecord":
        _reject_score_derived_identity(fields, path="projection")
        try:
            identity = projection_from_bindings(**fields)
        except (ProgramIdentityError, TypeError) as exc:
            raise _wrap_identity_error(exc) from exc
        return cls(identity=identity)


@dataclass(frozen=True, slots=True)
class ProjectionIndexManifest:
    """ProjectionIndexManifest@1: rebuildable, non-authoritative index generation."""

    identity: ProjectionIndexManifestIdentity

    SCHEMA: ClassVar[str] = (
        "ipfs-datasets.software-contracts.projection-index-manifest-identity@1"
    )
    INTERFACE: ClassVar[str] = PROJECTION_INDEX_MANIFEST_INTERFACE

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ProjectionIndexManifestIdentity):
            raise VerifiedSemanticStoreAdmissionError(
                "ProjectionIndexManifest.identity must be a "
                "ProjectionIndexManifestIdentity"
            )
        if self.identity.authoritative:
            raise VerifiedSemanticStoreAdmissionError(
                "index manifests are non-authoritative"
            )
        if not self.identity.rebuildable:
            raise VerifiedSemanticStoreAdmissionError(
                "index manifests must be rebuildable"
            )
        for field in ("model_cid", "tokenizer_cid", "preprocessing_profile_cid"):
            value = getattr(self.identity, field)
            if type(value) is not str or not value:
                raise VerifiedSemanticStoreAdmissionError(
                    f"unpinned model or preprocessor: {field} must be a CID"
                )
        if self.identity.byte_order not in {"little", "big"}:
            raise VerifiedSemanticStoreAdmissionError("unspecified byte order")

    @property
    def projection_index_manifest_cid(self) -> str:
        return self.identity.projection_index_manifest_cid

    def to_payload(self) -> dict[str, Any]:
        return self.identity.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return self.to_payload()

    @classmethod
    def from_identity(
        cls, identity: ProjectionIndexManifestIdentity
    ) -> "ProjectionIndexManifest":
        return cls(identity=identity)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ProjectionIndexManifest":
        _reject_score_derived_identity(payload, path="projection_index_manifest")
        try:
            identity = ProjectionIndexManifestIdentity.from_dict(payload)
        except ProgramIdentityError as exc:
            raise _wrap_identity_error(exc) from exc
        return cls(identity=identity)


def _as_semantic_object(
    value: SemanticObjectEnvelope | Mapping[str, Any],
) -> SemanticObjectEnvelope:
    if isinstance(value, SemanticObjectEnvelope):
        _reject_score_derived_identity(value.to_dict(), path="semantic_object")
        return value
    if not isinstance(value, Mapping):
        raise VerifiedSemanticStoreAdmissionError(
            "semantic object must be a SemanticObjectEnvelope or mapping"
        )
    _reject_score_derived_identity(value, path="semantic_object")
    try:
        return SemanticObjectEnvelope.from_dict(value)
    except ProgramIdentityError as exc:
        raise _wrap_identity_error(exc) from exc


def _as_projection_record(
    value: ProjectionRecord | ProjectionIdentity | Mapping[str, Any],
) -> ProjectionRecord:
    if isinstance(value, ProjectionRecord):
        return value
    if isinstance(value, ProjectionIdentity):
        return ProjectionRecord.from_identity(value)
    if not isinstance(value, Mapping):
        raise VerifiedSemanticStoreAdmissionError(
            "projection must be a ProjectionRecord, ProjectionIdentity, or mapping"
        )
    return ProjectionRecord.from_payload(value)


def _as_index_manifest(
    value: ProjectionIndexManifest | ProjectionIndexManifestIdentity | Mapping[str, Any],
) -> ProjectionIndexManifest:
    if isinstance(value, ProjectionIndexManifest):
        return value
    if isinstance(value, ProjectionIndexManifestIdentity):
        return ProjectionIndexManifest.from_identity(value)
    if not isinstance(value, Mapping):
        raise VerifiedSemanticStoreAdmissionError(
            "index manifest must be a ProjectionIndexManifest, identity, or mapping"
        )
    return ProjectionIndexManifest.from_payload(value)


class VerifiedSemanticBlockStore:
    """VerifiedSemanticStore@1 facade over kit CID/block verification."""

    INTERFACE: ClassVar[str] = VERIFIED_SEMANTIC_STORE_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore | SemanticWorldArtifactStore,
    ) -> None:
        if isinstance(store, SemanticWorldArtifactStore):
            self._artifacts = store
        elif isinstance(store, DurableCoordinationStore):
            self._artifacts = SemanticWorldArtifactStore(store)
        else:
            raise TypeError(
                "store must be a DurableCoordinationStore or SemanticWorldArtifactStore"
            )

    @property
    def artifacts(self) -> SemanticWorldArtifactStore:
        return self._artifacts

    @property
    def store(self) -> DurableCoordinationStore:
        return self._artifacts.store

    def close(self) -> None:
        self._artifacts.close()

    def __enter__(self) -> "VerifiedSemanticBlockStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _translate(self, exc: Exception) -> Exception:
        if isinstance(exc, VerifiedSemanticStoreError):
            return exc
        if isinstance(exc, SemanticWorldArtifactNotFound):
            return VerifiedSemanticStoreNotFound(str(exc))
        if isinstance(exc, SemanticWorldArtifactConflictError):
            return VerifiedSemanticStoreAdmissionError(str(exc))
        if isinstance(exc, SemanticWorldArtifactIntegrityError):
            return VerifiedSemanticStoreIntegrityError(str(exc))
        if isinstance(exc, SemanticWorldArtifactAdmissionError):
            return VerifiedSemanticStoreAdmissionError(str(exc))
        if isinstance(exc, ProgramIdentityError):
            return VerifiedSemanticStoreAdmissionError(str(exc))
        return exc

    def put_semantic_object(
        self,
        envelope: SemanticObjectEnvelope | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> SemanticWorldWriteResult:
        """Persist a verified semantic-object envelope."""

        record = _as_semantic_object(envelope)
        payload = record.to_dict()
        try:
            return self._artifacts.put_artifact(
                SemanticWorldArtifactKind.SEMANTIC_OBJECT,
                payload,
                expected_cid=expected_cid or record.semantic_object_cid,
                operation_id=operation_id,
                replicate=replicate,
            )
        except SemanticWorldArtifactError as exc:
            raise self._translate(exc) from exc

    def get_verified_semantic_object(self, cid: str) -> SemanticObjectEnvelope:
        """Load a semantic object and re-verify its claimed CID."""

        try:
            artifact = self._artifacts.get_verified_artifact(
                cid, expected_kind=SemanticWorldArtifactKind.SEMANTIC_OBJECT
            )
            envelope = SemanticObjectEnvelope.from_dict(dict(artifact["payload"]))
        except (SemanticWorldArtifactError, ProgramIdentityError) as exc:
            raise self._translate(exc) from exc
        if envelope.semantic_object_cid != artifact["identity_cid"]:
            raise VerifiedSemanticStoreIntegrityError(
                "semantic-object CID does not rehash canonical identity bytes"
            )
        return envelope

    def put_vector_bytes(
        self,
        values: Sequence[Any] | bytes,
        *,
        dtype: str,
        byte_order: str,
        dimension: int,
        expected_cid: str | None = None,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> SemanticWorldWriteResult:
        """Store canonical vector bytes.  Must precede any projection that cites them."""

        try:
            return self._artifacts.put_vector_bytes(
                values,
                dtype=dtype,
                byte_order=byte_order,
                dimension=dimension,
                expected_cid=expected_cid,
                operation_id=operation_id,
                replicate=replicate,
            )
        except SemanticWorldArtifactError as exc:
            raise self._translate(exc) from exc

    def get_verified_vector(self, cid: str) -> CanonicalVectorBytes:
        """Load packed vector bytes and rehash the claimed raw CID."""

        try:
            return self._artifacts.get_verified_vector(cid)
        except SemanticWorldArtifactError as exc:
            raise self._translate(exc) from exc

    def put_projection_record(
        self,
        record: ProjectionRecord | ProjectionIdentity | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> SemanticWorldWriteResult:
        """Persist a model-pinned projection after its subject and vector exist."""

        projection = _as_projection_record(record)
        identity = projection.identity
        if identity.subject_kind != ProjectionSubjectKind.SEMANTIC_OBJECT.value:
            raise VerifiedSemanticStoreAdmissionError(
                "this store admits semantic_object projection subjects only"
            )
        try:
            subject = self.get_verified_semantic_object(identity.subject_cid)
        except VerifiedSemanticStoreNotFound as exc:
            raise VerifiedSemanticStoreAdmissionError(
                "store-before-reference: subject_cid is not a stored semantic object"
            ) from exc
        if subject.semantic_object_cid != identity.subject_cid:
            raise VerifiedSemanticStoreIntegrityError(
                "projection subject CID does not match the stored semantic object"
            )
        try:
            vector = self.get_verified_vector(identity.vector_cid)
        except VerifiedSemanticStoreNotFound as exc:
            raise VerifiedSemanticStoreAdmissionError(
                "store-before-reference: vector_cid is not stored"
            ) from exc
        if vector.dimension != identity.dimension:
            raise VerifiedSemanticStoreAdmissionError(
                "dimension mismatch: projection dimension does not match stored vector"
            )
        if vector.dtype != identity.dtype:
            raise VerifiedSemanticStoreAdmissionError(
                "projection dtype does not match stored vector dtype"
            )
        if vector.byte_order != identity.byte_order:
            raise VerifiedSemanticStoreAdmissionError(
                "projection byte_order does not match stored vector byte_order"
            )
        if vector.bytes_cid != identity.vector_cid:
            raise VerifiedSemanticStoreIntegrityError(
                "projection vector_cid does not rehash stored packed bytes"
            )
        try:
            return self._artifacts.put_artifact(
                SemanticWorldArtifactKind.PROJECTION_RECORD,
                projection.to_payload(),
                expected_cid=expected_cid or projection.projection_cid,
                operation_id=operation_id,
                replicate=replicate,
            )
        except SemanticWorldArtifactError as exc:
            raise self._translate(exc) from exc

    def get_verified_projection_record(self, cid: str) -> ProjectionRecord:
        """Load a projection record and re-verify identity, vector, and subject."""

        try:
            artifact = self._artifacts.get_verified_artifact(
                cid, expected_kind=SemanticWorldArtifactKind.PROJECTION_RECORD
            )
            record = ProjectionRecord.from_payload(dict(artifact["payload"]))
        except (SemanticWorldArtifactError, ProgramIdentityError) as exc:
            raise self._translate(exc) from exc
        if record.projection_cid != artifact["identity_cid"]:
            raise VerifiedSemanticStoreIntegrityError(
                "projection CID does not rehash canonical identity bytes"
            )
        _require_projection_bindings(record.identity)
        vector = self.get_verified_vector(record.identity.vector_cid)
        if (
            vector.dimension != record.identity.dimension
            or vector.dtype != record.identity.dtype
            or vector.byte_order != record.identity.byte_order
            or vector.bytes_cid != record.identity.vector_cid
        ):
            raise VerifiedSemanticStoreIntegrityError(
                "stored projection does not re-verify against its vector bytes"
            )
        subject = self.get_verified_semantic_object(record.identity.subject_cid)
        if subject.semantic_object_cid != record.identity.subject_cid:
            raise VerifiedSemanticStoreIntegrityError(
                "stored projection does not re-verify against its subject"
            )
        return record

    def put_projection_index_manifest(
        self,
        manifest: ProjectionIndexManifest
        | ProjectionIndexManifestIdentity
        | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> SemanticWorldWriteResult:
        """Persist a rebuildable projection index manifest after its source exists."""

        record = _as_index_manifest(manifest)
        try:
            self.get_verified_semantic_object(record.identity.source_cid)
        except VerifiedSemanticStoreNotFound as exc:
            raise VerifiedSemanticStoreAdmissionError(
                "store-before-reference: source_cid is not a stored semantic object"
            ) from exc
        try:
            return self._artifacts.put_artifact(
                SemanticWorldArtifactKind.PROJECTION_INDEX_MANIFEST,
                record.to_payload(),
                expected_cid=expected_cid or record.projection_index_manifest_cid,
                operation_id=operation_id,
                replicate=replicate,
            )
        except SemanticWorldArtifactError as exc:
            raise self._translate(exc) from exc

    def get_verified_projection_index_manifest(
        self, cid: str
    ) -> ProjectionIndexManifest:
        """Load an index manifest and re-verify its claimed CID and source."""

        try:
            artifact = self._artifacts.get_verified_artifact(
                cid,
                expected_kind=SemanticWorldArtifactKind.PROJECTION_INDEX_MANIFEST,
            )
            record = ProjectionIndexManifest.from_payload(dict(artifact["payload"]))
        except (SemanticWorldArtifactError, ProgramIdentityError) as exc:
            raise self._translate(exc) from exc
        if record.projection_index_manifest_cid != artifact["identity_cid"]:
            raise VerifiedSemanticStoreIntegrityError(
                "index-manifest CID does not rehash canonical identity bytes"
            )
        source = self.get_verified_semantic_object(record.identity.source_cid)
        if source.semantic_object_cid != record.identity.source_cid:
            raise VerifiedSemanticStoreIntegrityError(
                "index manifest source_cid does not re-verify"
            )
        return record

    def get_verified_block(self, cid: str) -> Mapping[str, Any]:
        """Re-verify any admitted semantic-world block by identity or storage CID."""

        try:
            return self._artifacts.get_verified_artifact(cid)
        except SemanticWorldArtifactError as exc:
            raise self._translate(exc) from exc


VerifiedSemanticStore = VerifiedSemanticBlockStore


__all__ = [
    "ARTIFACT_MODULE_INTERFACE",
    "PROJECTION_INDEX_MANIFEST_INTERFACE",
    "PROJECTION_RECORD_INTERFACE",
    "VERIFIED_SEMANTIC_STORE_INTERFACE",
    "ProjectionIndexManifest",
    "ProjectionRecord",
    "VerifiedSemanticBlockStore",
    "VerifiedSemanticStore",
    "VerifiedSemanticStoreAdmissionError",
    "VerifiedSemanticStoreError",
    "VerifiedSemanticStoreIntegrityError",
    "VerifiedSemanticStoreNotFound",
    "pack_canonical_vector",
]
