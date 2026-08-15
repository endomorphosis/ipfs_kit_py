"""Immutable assurance artifact storage over DurableCoordinationStore (AAE-034).

``DurableAssuranceArtifactStore`` is a thin typed admission layer: closed
artifact kinds, datasets schema projections, recomputed CIDs, size bounds, and
signature gates for signed campaign/promotion receipts.  It does not open a
second object store, WAL, daemon, envelope hierarchy, or content-identity path.

Authority rules (normative, fail-closed):

* Typed payloads are re-derived through datasets ``from_dict`` / ``to_dict``;
  kit storage never redefines datasets schemas.
* Signed receipts must pass
  ``require_verified_signature_before_persistence`` before the first durable
  write, content addressing, Merkle inclusion, or seal eligibility, and again
  on verified read.
* Callers supply ``expected_cid``; storage recomputes canonical dag-json bytes
  and refuses any mismatch.
* Closed ``AssuranceArtifactKind`` only; wrong-kind reads and writes fail.
* Oversized canonical records fail before durable write.
* Corrupt local/backend bytes that do not re-verify their CID never surface as
  successful artifacts.
* ``operation_id`` is an idempotency key: same id + same CID is a no-op success;
  same id + different CID is a conflict.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from types import MappingProxyType
from typing import Any, Final, Mapping, Optional

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    DurableCoordinationStore,
    cid_for_artifact,
    cid_for_bytes,
)
from ipfs_kit_py.adversarial_assurance_store.contracts import (
    MAX_ARTIFACT_BYTES,
    AssuranceArtifactKind,
    AssuranceArtifactStoreContractError,
    AssuranceArtifactWriteResult,
    AssuranceProviderStatus,
    coerce_assurance_artifact_kind,
    is_signed_receipt_kind,
    project_assurance_payload,
    require_verified_signature_gate,
    validate_operation_id,
    validate_semantic_dag_json_cid,
)

# ---------------------------------------------------------------------------
# Schema / limits
# ---------------------------------------------------------------------------

ARTIFACT_MODULE_INTERFACE: Final[str] = "DurableAssuranceArtifactStore@1"
# Storage admits datasets-owned wire records only; no alternate kit envelope.
ASSURANCE_STORED_ARTIFACT_INTERFACE: Final[str] = "datasets-wire-record@1"

_OPS_DB_NAME: Final[str] = "assurance_artifact_ops.sqlite3"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AssuranceArtifactError(ValueError):
    """Base error for immutable assurance artifact admission or retrieval."""


class AssuranceArtifactAdmissionError(AssuranceArtifactError):
    """Raised when a write is rejected by closed admission policy."""


class AssuranceArtifactIntegrityError(AssuranceArtifactError):
    """Raised when bytes, CID, kind, signature, or shape do not verify."""


class AssuranceArtifactNotFound(AssuranceArtifactError, KeyError):
    """Raised when no verified block exists for a CID."""


class AssuranceArtifactConflictError(AssuranceArtifactError):
    """Raised when an operation_id is reused for a different artifact CID."""


# ---------------------------------------------------------------------------
# Canonical form helpers
# ---------------------------------------------------------------------------


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AssuranceArtifactAdmissionError(
            f"artifact is not canonical JSON: {exc}"
        ) from exc


def seal_assurance_artifact(
    kind: AssuranceArtifactKind | str,
    payload: Mapping[str, Any],
    *,
    enforce_signature_gate: bool = True,
) -> dict[str, Any]:
    """Project, size-bound, and (for signed receipts) signature-gate a payload.

    Signature verification for signed kinds runs before content addressing and
    before any durable write.  The sealed form is the datasets ``to_dict()``
    wire record — no alternate kit envelope is introduced.
    """

    try:
        artifact_kind = coerce_assurance_artifact_kind(kind)
    except AssuranceArtifactStoreContractError as exc:
        raise AssuranceArtifactAdmissionError(str(exc)) from exc

    # Signature gate first for signed receipts (before content addressing).
    if enforce_signature_gate and is_signed_receipt_kind(artifact_kind):
        try:
            require_verified_signature_gate(payload)
        except AssuranceArtifactStoreContractError as exc:
            raise AssuranceArtifactAdmissionError(str(exc)) from exc

    try:
        sealed = project_assurance_payload(
            artifact_kind,
            payload,
            enforce_signature_gate=False,
        )
    except AssuranceArtifactStoreContractError as exc:
        raise AssuranceArtifactAdmissionError(str(exc)) from exc

    data = _canonical_bytes(sealed)
    if len(data) > MAX_ARTIFACT_BYTES:
        raise AssuranceArtifactAdmissionError(
            f"artifact exceeds MAX_ARTIFACT_BYTES ({len(data)} > {MAX_ARTIFACT_BYTES})"
        )
    return sealed


def cid_for_assurance_artifact(
    kind: AssuranceArtifactKind | str,
    payload: Mapping[str, Any],
    *,
    enforce_signature_gate: bool = True,
) -> str:
    """Return the dag-json CIDv1 of the sealed datasets wire record.

    For signed receipt kinds this still enforces the signature gate before the
    CID is computed (content addressing must not precede authenticity).
    """

    sealed = seal_assurance_artifact(
        kind, payload, enforce_signature_gate=enforce_signature_gate
    )
    return cid_for_artifact(sealed)


def admit_stored_record(
    kind: AssuranceArtifactKind | str,
    record: Mapping[str, Any],
    *,
    enforce_signature_gate: bool = True,
) -> dict[str, Any]:
    """Validate a retrieved or candidate datasets wire record and re-seal it."""

    try:
        artifact_kind = coerce_assurance_artifact_kind(kind)
    except AssuranceArtifactStoreContractError as exc:
        raise AssuranceArtifactIntegrityError(str(exc)) from exc

    if not isinstance(record, Mapping):
        raise AssuranceArtifactIntegrityError("stored artifact must be a mapping")

    if enforce_signature_gate and is_signed_receipt_kind(artifact_kind):
        try:
            require_verified_signature_gate(record)
        except AssuranceArtifactStoreContractError as exc:
            raise AssuranceArtifactIntegrityError(str(exc)) from exc

    try:
        sealed = project_assurance_payload(
            artifact_kind,
            record,
            enforce_signature_gate=False,
        )
    except AssuranceArtifactStoreContractError as exc:
        raise AssuranceArtifactIntegrityError(str(exc)) from exc

    data = _canonical_bytes(sealed)
    if len(data) > MAX_ARTIFACT_BYTES:
        raise AssuranceArtifactIntegrityError(
            f"artifact exceeds MAX_ARTIFACT_BYTES ({len(data)} > {MAX_ARTIFACT_BYTES})"
        )
    return sealed


def _infer_kind_from_record(record: Mapping[str, Any]) -> AssuranceArtifactKind:
    """Infer closed kind from datasets schema / header when present."""

    from ipfs_kit_py.adversarial_assurance_store.contracts import (
        datasets_schema_for_kind,
        assurance_artifact_kinds,
    )

    header = record.get("header")
    if isinstance(header, Mapping):
        header_kind = header.get("artifact_kind")
        if isinstance(header_kind, str) and header_kind:
            try:
                return coerce_assurance_artifact_kind(header_kind)
            except AssuranceArtifactStoreContractError as exc:
                raise AssuranceArtifactIntegrityError(str(exc)) from exc

    schema = record.get("schema")
    if not isinstance(schema, str) or not schema:
        raise AssuranceArtifactIntegrityError(
            "stored artifact must declare a datasets schema or header.artifact_kind"
        )
    for kind_token in assurance_artifact_kinds():
        if datasets_schema_for_kind(kind_token) == schema:
            return coerce_assurance_artifact_kind(kind_token)
    raise AssuranceArtifactIntegrityError(
        f"unknown datasets schema for stored artifact: {schema!r}"
    )


# ---------------------------------------------------------------------------
# Operation-id index (rebuildable acceleration; blocks remain authoritative)
# ---------------------------------------------------------------------------


class _OperationIndex:
    """Local operation_id → CID bindings next to the coordination store root."""

    def __init__(self, store: DurableCoordinationStore) -> None:
        self._path = store.root / _OPS_DB_NAME
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(self._path), timeout=30, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS artifact_operations (
              operation_id TEXT PRIMARY KEY,
              cid TEXT NOT NULL,
              kind TEXT NOT NULL
            );
            """
        )
        self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def lookup(self, operation_id: str) -> tuple[str, str] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT cid, kind FROM artifact_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
        if row is None:
            return None
        return str(row["cid"]), str(row["kind"])

    def bind(self, operation_id: str, cid: str, kind: str) -> None:
        with self._lock:
            existing = self._connection.execute(
                "SELECT cid, kind FROM artifact_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["cid"]) != cid or str(existing["kind"]) != kind:
                    raise AssuranceArtifactConflictError(
                        f"operation_id {operation_id!r} already bound to a different artifact"
                    )
                return
            with self._connection:
                self._connection.execute(
                    "INSERT INTO artifact_operations(operation_id, cid, kind) VALUES(?,?,?)",
                    (operation_id, cid, kind),
                )


# ---------------------------------------------------------------------------
# Store implementation
# ---------------------------------------------------------------------------


class DurableAssuranceArtifactStore:
    """Immutable typed assurance artifact store over ``DurableCoordinationStore``.

    Implements the ``put_artifact`` / ``get_verified_artifact`` surface of
    ``AssuranceArtifactStore@1``.
    """

    def __init__(self, store: DurableCoordinationStore) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store
        self._ops = _OperationIndex(store)

    @property
    def store(self) -> DurableCoordinationStore:
        """Injected coordination store (diagnostics / composition only)."""

        return self._store

    def close(self) -> None:
        self._ops.close()

    def __enter__(self) -> "DurableAssuranceArtifactStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def put_artifact(
        self,
        kind: AssuranceArtifactKind | str,
        payload: Mapping[str, Any],
        *,
        expected_cid: str,
        operation_id: str,
        replicate: bool = True,
    ) -> AssuranceArtifactWriteResult:
        """Admit, project, signature-gate, verify CID, and durably store one artifact."""

        try:
            operation_id = validate_operation_id(operation_id)
            expected_cid = validate_semantic_dag_json_cid(
                expected_cid, "expected_cid"
            )
        except AssuranceArtifactStoreContractError as exc:
            raise AssuranceArtifactAdmissionError(str(exc)) from exc

        try:
            artifact_kind = coerce_assurance_artifact_kind(kind)
        except AssuranceArtifactStoreContractError as exc:
            raise AssuranceArtifactAdmissionError(str(exc)) from exc

        # Seal enforces signature-before-content-addressing for signed receipts,
        # datasets projection, and size bounds — all before DurableCoordinationStore.put.
        sealed = seal_assurance_artifact(
            artifact_kind, payload, enforce_signature_gate=True
        )
        actual_cid = cid_for_artifact(sealed)
        if actual_cid != expected_cid:
            raise AssuranceArtifactIntegrityError(
                f"forged or mismatched artifact CID: computed {actual_cid}, "
                f"expected {expected_cid}"
            )

        prior = self._ops.lookup(operation_id)
        if prior is not None:
            prior_cid, prior_kind = prior
            if prior_cid != expected_cid or prior_kind != artifact_kind.value:
                raise AssuranceArtifactConflictError(
                    f"operation_id {operation_id!r} already bound to a different artifact"
                )
            try:
                self.get_verified_artifact(
                    expected_cid, expected_kind=artifact_kind
                )
            except AssuranceArtifactNotFound as exc:
                raise AssuranceArtifactIntegrityError(
                    f"operation_id {operation_id!r} is bound but block is missing"
                ) from exc
            return AssuranceArtifactWriteResult(
                expected_cid,
                artifact_kind,
                True,
                AssuranceProviderStatus.NOT_REQUESTED,
                False,
                "unchanged",
            )

        try:
            local = self._store.put(
                sealed,
                expected_cid=expected_cid,
                codec="dag-json",
                replicate=False,
            )
        except ArtifactIntegrityError as exc:
            raise AssuranceArtifactIntegrityError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise AssuranceArtifactAdmissionError(str(exc)) from exc

        cid = str(local["cid"])
        if cid != expected_cid:
            raise AssuranceArtifactIntegrityError(
                f"store returned unexpected CID {cid}, expected {expected_cid}"
            )

        self._ops.bind(operation_id, expected_cid, artifact_kind.value)

        if not replicate:
            return AssuranceArtifactWriteResult(
                expected_cid,
                artifact_kind,
                True,
                AssuranceProviderStatus.NOT_REQUESTED,
                False,
                "not_requested" if not local.get("created", True) else "stored",
            )
        if self._store.backend is None:
            return AssuranceArtifactWriteResult(
                expected_cid,
                artifact_kind,
                True,
                AssuranceProviderStatus.UNAVAILABLE,
                False,
                "provider_unavailable",
            )

        try:
            remote = self._store.put(
                sealed,
                expected_cid=expected_cid,
                codec="dag-json",
                replicate=True,
            )
        except ArtifactIntegrityError:
            return AssuranceArtifactWriteResult(
                expected_cid,
                artifact_kind,
                True,
                AssuranceProviderStatus.CORRUPT,
                False,
                "provider_corrupt",
            )
        except Exception:
            return AssuranceArtifactWriteResult(
                expected_cid,
                artifact_kind,
                True,
                AssuranceProviderStatus.FAILED,
                False,
                "provider_failed",
            )

        if remote.get("cid") != expected_cid or remote.get("replicated") is not True:
            return AssuranceArtifactWriteResult(
                expected_cid,
                artifact_kind,
                True,
                AssuranceProviderStatus.CORRUPT,
                False,
                "provider_corrupt",
            )
        return AssuranceArtifactWriteResult(
            expected_cid,
            artifact_kind,
            True,
            AssuranceProviderStatus.AVAILABLE,
            True,
            "replicated",
        )

    def get_verified_artifact(
        self,
        cid: str,
        *,
        expected_kind: Optional[AssuranceArtifactKind | str] = None,
    ) -> Mapping[str, Any]:
        """Load, re-project, and re-verify an assurance artifact by CID.

        Returns a read-only mapping of the datasets wire record.  Signed
        receipts are signature-gated again through the datasets authority.
        """

        try:
            cid = validate_semantic_dag_json_cid(cid, "cid")
        except AssuranceArtifactStoreContractError as exc:
            raise AssuranceArtifactIntegrityError(str(exc)) from exc

        try:
            raw = self._store.get(cid)
        except ArtifactNotFound as exc:
            raise AssuranceArtifactNotFound(cid) from exc
        except ArtifactIntegrityError as exc:
            raise AssuranceArtifactIntegrityError(str(exc)) from exc
        except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AssuranceArtifactIntegrityError(str(exc)) from exc

        if not isinstance(raw, Mapping):
            raise AssuranceArtifactIntegrityError(
                f"{cid} did not decode to a mapping"
            )

        try:
            data = self._store.get_bytes(cid)
        except ArtifactNotFound as exc:
            raise AssuranceArtifactNotFound(cid) from exc
        except ArtifactIntegrityError as exc:
            raise AssuranceArtifactIntegrityError(str(exc)) from exc
        if cid_for_bytes(data, "dag-json") != cid:
            raise AssuranceArtifactIntegrityError(
                f"local bytes do not match {cid}"
            )

        if expected_kind is not None:
            try:
                wanted = coerce_assurance_artifact_kind(expected_kind)
            except AssuranceArtifactStoreContractError as exc:
                raise AssuranceArtifactIntegrityError(str(exc)) from exc
        else:
            wanted = _infer_kind_from_record(raw)

        sealed = admit_stored_record(
            wanted, raw, enforce_signature_gate=True
        )
        recomputed = cid_for_artifact(sealed)
        if recomputed != cid:
            raise AssuranceArtifactIntegrityError(
                f"forged stored artifact: recomputed {recomputed}, expected {cid}"
            )

        if expected_kind is not None:
            # Re-check header/schema kind after projection.
            inferred = _infer_kind_from_record(sealed)
            if inferred is not wanted:
                raise AssuranceArtifactIntegrityError(
                    f"wrong artifact kind: stored {inferred.value}, "
                    f"expected {wanted.value}"
                )

        # Return a shallow freeze of the datasets wire record.
        return MappingProxyType(dict(sealed))


__all__ = [
    "ARTIFACT_MODULE_INTERFACE",
    "ASSURANCE_STORED_ARTIFACT_INTERFACE",
    "MAX_ARTIFACT_BYTES",
    "AssuranceArtifactError",
    "AssuranceArtifactAdmissionError",
    "AssuranceArtifactIntegrityError",
    "AssuranceArtifactNotFound",
    "AssuranceArtifactConflictError",
    "seal_assurance_artifact",
    "cid_for_assurance_artifact",
    "admit_stored_record",
    "DurableAssuranceArtifactStore",
]
