"""Immutable governor artifact storage over DurableCoordinationStore (SCG-019).

``DurableSemanticGovernorStore`` is a thin typed admission layer: closed artifact
kinds, recomputed CIDs, size/privacy bounds, and known envelope versions.  It
does not open a second object store, WAL, daemon, or content-identity path.

Authority rules (normative, fail-closed):

* Callers supply ``expected_cid``; storage recomputes canonical dag-json bytes
  and refuses any mismatch (forged identity).
* Closed ``GovernorArtifactKind`` only; wrong-kind reads and writes fail.
* Envelope schema is exactly version ``@1``; unknown versions fail.
* Oversized canonical records fail before durable write.
* Private raw source and related private-field markers are rejected recursively.
* Corrupt local/backend bytes that do not re-verify their CID never surface as
  successful artifacts.
* ``operation_id`` is an idempotency key: same id + same CID is a no-op success;
  same id + different CID is a conflict.
"""

from __future__ import annotations

import json
import re
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
from ipfs_kit_py.semantic_governor_store.contracts import (
    GovernorArtifactKind,
    GovernorArtifactWriteResult,
    GovernorProviderStatus,
    SemanticGovernorStoreContractError,
    validate_operation_id,
    validate_semantic_dag_json_cid,
)

# ---------------------------------------------------------------------------
# Schema / limits
# ---------------------------------------------------------------------------

ARTIFACT_MODULE_INTERFACE: Final[str] = "DurableSemanticGovernorStore@1"
GOVERNOR_STORED_ARTIFACT_INTERFACE: Final[str] = "GovernorStoredArtifact@1"
GOVERNOR_STORED_ARTIFACT_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-governor-store.artifact@1"
)
# Canonical sealed record ceiling (dag-json bytes). Matches common kit 1 MiB
# single-blob admission and the supervisor single-file proposal bound.
MAX_ARTIFACT_BYTES: Final[int] = 1_048_576
ARTIFACT_SCHEMA_VERSION: Final[int] = 1

_OPS_DB_NAME: Final[str] = "governor_artifact_ops.sqlite3"
_SCHEMA_VERSION_SUFFIX: Final[re.Pattern[str]] = re.compile(r"@(\d+)$")

# Field-name markers that must never appear in public durable governor blocks.
# Mirrored from datasets semantic-governor base so kit storage stays fail-closed
# even when domain contracts are not imported.
PRIVATE_FIELD_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "cookie",
        "credential",
        "hidden_witness",
        "password",
        "private_key",
        "private_premise",
        "private_source",
        "private_witness",
        "raw_private_source",
        "raw_source",
        "raw_source_text",
        "refresh_token",
        "secret",
        "session_token",
        "source_bytes",
        "source_text",
        "witness",
    }
)

_SEALED_FIELDS: Final[frozenset[str]] = frozenset(
    ("schema", "interface_id", "kind", "payload")
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GovernorArtifactError(ValueError):
    """Base error for immutable governor artifact admission or retrieval."""


class GovernorArtifactAdmissionError(GovernorArtifactError):
    """Raised when a write is rejected by closed admission policy."""


class GovernorArtifactIntegrityError(GovernorArtifactError):
    """Raised when bytes, CID, kind, or sealed shape do not verify."""


class GovernorArtifactNotFound(GovernorArtifactError, KeyError):
    """Raised when no verified block exists for a CID."""


class GovernorArtifactConflictError(GovernorArtifactError):
    """Raised when an operation_id is reused for a different artifact CID."""


# ---------------------------------------------------------------------------
# Private / structured admission helpers
# ---------------------------------------------------------------------------


def _key_is_private(name: str) -> bool:
    lowered = name.lower()
    if lowered in PRIVATE_FIELD_MARKERS:
        return True
    for marker in PRIVATE_FIELD_MARKERS:
        if marker in lowered:
            return True
    return False


def reject_private_raw_source(value: Any, *, path: str = "$") -> None:
    """Fail closed when private raw source or related private fields are present."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                raise GovernorArtifactAdmissionError(
                    f"{path} map keys must be str, got {type(key).__name__}"
                )
            key_path = f"{path}.{key}"
            if _key_is_private(key):
                raise GovernorArtifactAdmissionError(
                    f"{key_path} rejects private raw source / private field {key!r}"
                )
            reject_private_raw_source(item, path=key_path)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            reject_private_raw_source(item, path=f"{path}[{index}]")
        return


def _require_structured_json_value(value: Any, *, path: str = "$") -> None:
    """Admit only strict dag-json scalars/containers (no float/bytes/host types)."""

    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        return
    if isinstance(value, str):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _require_structured_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                raise GovernorArtifactAdmissionError(
                    f"{path} map keys must be str, got {type(key).__name__}"
                )
            _require_structured_json_value(item, path=f"{path}.{key}")
        return
    raise GovernorArtifactAdmissionError(
        f"{path} must be strict DAG-JSON (no floats, bytes, or host types); "
        f"got {type(value).__name__}"
    )


def _coerce_kind(kind: GovernorArtifactKind | str) -> GovernorArtifactKind:
    if isinstance(kind, GovernorArtifactKind):
        return kind
    if isinstance(kind, str):
        try:
            return GovernorArtifactKind(kind)
        except ValueError as exc:
            raise GovernorArtifactAdmissionError(
                f"unknown governor artifact kind: {kind!r}"
            ) from exc
    raise GovernorArtifactAdmissionError(
        "kind must be a GovernorArtifactKind or its closed string value"
    )


def _schema_version(schema: str) -> int | None:
    match = _SCHEMA_VERSION_SUFFIX.search(schema)
    if match is None:
        return None
    return int(match.group(1))


def validate_stored_artifact_schema(schema: object) -> str:
    """Require the exact closed storage-envelope schema URI at version 1."""

    if not isinstance(schema, str) or not schema:
        raise GovernorArtifactAdmissionError(
            "artifact schema must be a non-empty string"
        )
    version = _schema_version(schema)
    if version is None:
        raise GovernorArtifactAdmissionError(
            "artifact schema must declare a version suffix @N"
        )
    if version != ARTIFACT_SCHEMA_VERSION:
        raise GovernorArtifactAdmissionError(
            f"unknown artifact schema version: expected @{ARTIFACT_SCHEMA_VERSION}, "
            f"got @{version}"
        )
    if schema != GOVERNOR_STORED_ARTIFACT_SCHEMA:
        raise GovernorArtifactAdmissionError(
            f"unknown artifact schema: {schema!r}"
        )
    return schema


def seal_governor_artifact(
    kind: GovernorArtifactKind | str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the closed, content-addressed storage envelope for a payload."""

    artifact_kind = _coerce_kind(kind)
    if not isinstance(payload, Mapping):
        raise GovernorArtifactAdmissionError("payload must be a mapping")
    # Copy once so callers cannot mutate the sealed dict later via shared refs.
    body = dict(payload)
    _require_structured_json_value(body, path="payload")
    reject_private_raw_source(body, path="payload")
    sealed = {
        "schema": GOVERNOR_STORED_ARTIFACT_SCHEMA,
        "interface_id": GOVERNOR_STORED_ARTIFACT_INTERFACE,
        "kind": artifact_kind.value,
        "payload": body,
    }
    # Validate the sealed envelope as a whole for private markers (keys on the
    # envelope itself are fixed and public; this catches payload nesting).
    reject_private_raw_source(sealed, path="$")
    data = _canonical_bytes(sealed)
    if len(data) > MAX_ARTIFACT_BYTES:
        raise GovernorArtifactAdmissionError(
            f"artifact exceeds MAX_ARTIFACT_BYTES ({len(data)} > {MAX_ARTIFACT_BYTES})"
        )
    return sealed


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
        raise GovernorArtifactAdmissionError(
            f"artifact is not canonical JSON: {exc}"
        ) from exc


def cid_for_governor_artifact(
    kind: GovernorArtifactKind | str,
    payload: Mapping[str, Any],
) -> str:
    """Return the dag-json CIDv1 of the sealed storage envelope."""

    sealed = seal_governor_artifact(kind, payload)
    return cid_for_artifact(sealed)


def admit_sealed_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a retrieved or candidate sealed envelope and return a plain dict."""

    if not isinstance(record, Mapping):
        raise GovernorArtifactIntegrityError("sealed artifact must be a mapping")
    actual = frozenset(record)
    if actual != _SEALED_FIELDS:
        missing = sorted(_SEALED_FIELDS - actual)
        unknown = sorted(actual - _SEALED_FIELDS)
        problems: list[str] = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        raise GovernorArtifactIntegrityError(
            "sealed artifact has " + "; ".join(problems)
        )
    try:
        validate_stored_artifact_schema(record["schema"])
    except GovernorArtifactAdmissionError as exc:
        raise GovernorArtifactIntegrityError(str(exc)) from exc
    if record.get("interface_id") != GOVERNOR_STORED_ARTIFACT_INTERFACE:
        raise GovernorArtifactIntegrityError(
            "unknown sealed artifact interface_id"
        )
    try:
        kind = _coerce_kind(record["kind"])
    except GovernorArtifactAdmissionError as exc:
        raise GovernorArtifactIntegrityError(str(exc)) from exc
    payload = record["payload"]
    if not isinstance(payload, Mapping):
        raise GovernorArtifactIntegrityError("payload must be a mapping")
    body = dict(payload)
    try:
        _require_structured_json_value(body, path="payload")
        reject_private_raw_source(body, path="payload")
    except GovernorArtifactAdmissionError as exc:
        raise GovernorArtifactIntegrityError(str(exc)) from exc
    sealed = {
        "schema": GOVERNOR_STORED_ARTIFACT_SCHEMA,
        "interface_id": GOVERNOR_STORED_ARTIFACT_INTERFACE,
        "kind": kind.value,
        "payload": body,
    }
    data = _canonical_bytes(sealed)
    if len(data) > MAX_ARTIFACT_BYTES:
        raise GovernorArtifactIntegrityError(
            f"artifact exceeds MAX_ARTIFACT_BYTES ({len(data)} > {MAX_ARTIFACT_BYTES})"
        )
    # Round-trip canonical identity: retrieved JSON must match sealed form.
    if _canonical_bytes(dict(record)) != data:
        # Allow key-order differences by comparing against sorted re-encode of
        # the admitted shape only when content is equivalent under cid.
        if cid_for_artifact(dict(record)) != cid_for_artifact(sealed):
            raise GovernorArtifactIntegrityError(
                "sealed artifact is not in canonical form"
            )
    return sealed


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
                    raise GovernorArtifactConflictError(
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


class DurableSemanticGovernorStore:
    """Immutable typed governor artifact store over ``DurableCoordinationStore``.

    Implements the ``put_artifact`` / ``get_verified_artifact`` surface of
    ``SemanticGovernorStore@1``.  Later modules (history, policy CAS, recovery)
    compose the same coordination store without a second engine.
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

    def __enter__(self) -> "DurableSemanticGovernorStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def put_artifact(
        self,
        kind: GovernorArtifactKind,
        payload: Mapping[str, Any],
        *,
        expected_cid: str,
        operation_id: str,
        replicate: bool = True,
    ) -> GovernorArtifactWriteResult:
        """Admit, seal, verify CID, and durably store one immutable artifact."""

        try:
            operation_id = validate_operation_id(operation_id)
            expected_cid = validate_semantic_dag_json_cid(
                expected_cid, "expected_cid"
            )
        except SemanticGovernorStoreContractError as exc:
            raise GovernorArtifactAdmissionError(str(exc)) from exc

        artifact_kind = _coerce_kind(kind)
        sealed = seal_governor_artifact(artifact_kind, payload)
        actual_cid = cid_for_artifact(sealed)
        if actual_cid != expected_cid:
            raise GovernorArtifactIntegrityError(
                f"forged or mismatched artifact CID: computed {actual_cid}, "
                f"expected {expected_cid}"
            )

        prior = self._ops.lookup(operation_id)
        if prior is not None:
            prior_cid, prior_kind = prior
            if prior_cid != expected_cid or prior_kind != artifact_kind.value:
                raise GovernorArtifactConflictError(
                    f"operation_id {operation_id!r} already bound to a different artifact"
                )
            # Idempotent replay: ensure the block is still present and verified.
            try:
                self.get_verified_artifact(
                    expected_cid, expected_kind=artifact_kind
                )
            except GovernorArtifactNotFound as exc:
                raise GovernorArtifactIntegrityError(
                    f"operation_id {operation_id!r} is bound but block is missing"
                ) from exc
            return GovernorArtifactWriteResult(
                expected_cid,
                artifact_kind,
                True,
                GovernorProviderStatus.NOT_REQUESTED,
                False,
                "unchanged",
            )

        # Local durability first; optional provider replication is projected
        # truthfully without masking a successful local write.
        try:
            local = self._store.put(
                sealed,
                expected_cid=expected_cid,
                codec="dag-json",
                replicate=False,
            )
        except ArtifactIntegrityError as exc:
            raise GovernorArtifactIntegrityError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise GovernorArtifactAdmissionError(str(exc)) from exc

        cid = str(local["cid"])
        if cid != expected_cid:
            raise GovernorArtifactIntegrityError(
                f"store returned unexpected CID {cid}, expected {expected_cid}"
            )

        self._ops.bind(operation_id, expected_cid, artifact_kind.value)

        if not replicate:
            return GovernorArtifactWriteResult(
                expected_cid,
                artifact_kind,
                True,
                GovernorProviderStatus.NOT_REQUESTED,
                False,
                "not_requested" if not local.get("created", True) else "stored",
            )
        if self._store.backend is None:
            return GovernorArtifactWriteResult(
                expected_cid,
                artifact_kind,
                True,
                GovernorProviderStatus.UNAVAILABLE,
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
            return GovernorArtifactWriteResult(
                expected_cid,
                artifact_kind,
                True,
                GovernorProviderStatus.CORRUPT,
                False,
                "provider_corrupt",
            )
        except Exception:
            return GovernorArtifactWriteResult(
                expected_cid,
                artifact_kind,
                True,
                GovernorProviderStatus.FAILED,
                False,
                "provider_failed",
            )

        if remote.get("cid") != expected_cid or remote.get("replicated") is not True:
            return GovernorArtifactWriteResult(
                expected_cid,
                artifact_kind,
                True,
                GovernorProviderStatus.CORRUPT,
                False,
                "provider_corrupt",
            )
        return GovernorArtifactWriteResult(
            expected_cid,
            artifact_kind,
            True,
            GovernorProviderStatus.AVAILABLE,
            True,
            "replicated",
        )

    def get_verified_artifact(
        self,
        cid: str,
        *,
        expected_kind: Optional[GovernorArtifactKind] = None,
    ) -> Mapping[str, Any]:
        """Load and re-verify a sealed governor artifact by CID.

        Returns a read-only mapping of the sealed envelope
        (``schema``, ``interface_id``, ``kind``, ``payload``).
        """

        try:
            cid = validate_semantic_dag_json_cid(cid, "cid")
        except SemanticGovernorStoreContractError as exc:
            raise GovernorArtifactIntegrityError(str(exc)) from exc

        try:
            raw = self._store.get(cid)
        except ArtifactNotFound as exc:
            raise GovernorArtifactNotFound(cid) from exc
        except ArtifactIntegrityError as exc:
            raise GovernorArtifactIntegrityError(str(exc)) from exc
        except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GovernorArtifactIntegrityError(str(exc)) from exc

        if not isinstance(raw, Mapping):
            raise GovernorArtifactIntegrityError(
                f"{cid} did not decode to a mapping"
            )

        # Recompute identity from retrieved bytes path: store.get already checks
        # canonical form; re-check sealed governor shape and CID explicitly.
        try:
            data = self._store.get_bytes(cid)
        except ArtifactNotFound as exc:
            raise GovernorArtifactNotFound(cid) from exc
        except ArtifactIntegrityError as exc:
            raise GovernorArtifactIntegrityError(str(exc)) from exc
        if cid_for_bytes(data, "dag-json") != cid:
            raise GovernorArtifactIntegrityError(
                f"local bytes do not match {cid}"
            )

        sealed = admit_sealed_record(raw)
        recomputed = cid_for_artifact(sealed)
        if recomputed != cid:
            raise GovernorArtifactIntegrityError(
                f"forged sealed artifact: recomputed {recomputed}, expected {cid}"
            )

        kind = GovernorArtifactKind(sealed["kind"])
        if expected_kind is not None:
            wanted = _coerce_kind(expected_kind)
            if kind is not wanted:
                raise GovernorArtifactIntegrityError(
                    f"wrong artifact kind: stored {kind.value}, "
                    f"expected {wanted.value}"
                )

        return MappingProxyType(
            {
                "schema": sealed["schema"],
                "interface_id": sealed["interface_id"],
                "kind": sealed["kind"],
                "payload": MappingProxyType(dict(sealed["payload"])),
            }
        )


__all__ = [
    "ARTIFACT_MODULE_INTERFACE",
    "GOVERNOR_STORED_ARTIFACT_INTERFACE",
    "GOVERNOR_STORED_ARTIFACT_SCHEMA",
    "MAX_ARTIFACT_BYTES",
    "ARTIFACT_SCHEMA_VERSION",
    "PRIVATE_FIELD_MARKERS",
    "GovernorArtifactError",
    "GovernorArtifactAdmissionError",
    "GovernorArtifactIntegrityError",
    "GovernorArtifactNotFound",
    "GovernorArtifactConflictError",
    "reject_private_raw_source",
    "validate_stored_artifact_schema",
    "seal_governor_artifact",
    "cid_for_governor_artifact",
    "admit_sealed_record",
    "DurableSemanticGovernorStore",
]
