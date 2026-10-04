"""Immutable semantic-world artifact storage over DurableCoordinationStore.

``SemanticWorldArtifactStore`` is a thin typed admission layer: closed artifact
kinds, recomputed kit CIDs, canonical vector byte vectors, size/privacy bounds,
and known envelope versions.  It does not open a second object store, WAL,
daemon, or content-identity path.

Authority rules (normative, fail-closed):

* Storage CIDs are minted only by ``coordination_storage.cid_for_bytes`` /
  ``cid_for_artifact``.  This module never encodes CIDv1 itself.
* Callers may supply ``expected_cid``; storage recomputes identity and refuses
  any mismatch (forged identity).
* Every retrieved block is rehashed against its CID before it is returned.
* Closed ``SemanticWorldArtifactKind`` only; wrong-kind reads and writes fail.
* Envelope schema is exactly version ``@1``; unknown versions fail.
* Vector bytes are packed to a deterministic dtype/byte-order layout.  NaN,
  infinity, dimension mismatch, and unspecified byte order fail closed.
* Oversized canonical records fail before durable write.
* Private raw-source and related private-field markers are rejected recursively.
* Corrupt present-block bytes that do not re-verify their CID never surface as
  successful artifacts.
* Immutable puts are idempotent: same identity + same bytes is a no-op success.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import struct
import threading
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Final, Mapping, Optional, Sequence

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    DurableCoordinationStore,
    cid_for_artifact,
    cid_for_bytes,
    validate_transport_cid,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    SemanticGovernorStoreContractError,
    validate_operation_id,
    validate_verified_cid,
)


# ---------------------------------------------------------------------------
# Schema / limits
# ---------------------------------------------------------------------------

ARTIFACT_MODULE_INTERFACE: Final[str] = "SemanticWorldArtifactStore@1"
STORED_ARTIFACT_INTERFACE: Final[str] = "SemanticWorldStoredArtifact@1"
STORED_ARTIFACT_SCHEMA: Final[str] = "ipfs-kit.semantic-world-store.artifact@1"
CANONICAL_VECTOR_BYTES_INTERFACE: Final[str] = "CanonicalVectorBytes@1"
ARTIFACT_SCHEMA_VERSION: Final[int] = 1
MAX_ARTIFACT_BYTES: Final[int] = 1_048_576
MAX_VECTOR_DIMENSION: Final[int] = 1_048_576
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1

_OPS_DB_NAME: Final[str] = "semantic_world_artifact_index.sqlite3"
_SCHEMA_VERSION_SUFFIX: Final[re.Pattern[str]] = re.compile(r"@(\d+)$")
_HEX: Final[re.Pattern[str]] = re.compile(r"\A[0-9a-f]*\Z")

_SEALED_FIELDS: Final[frozenset[str]] = frozenset(
    ("schema", "interface_id", "kind", "payload")
)
_VECTOR_PAYLOAD_FIELDS: Final[frozenset[str]] = frozenset(
    ("dtype", "byte_order", "dimension", "bytes_hex", "bytes_cid")
)

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

_FLOAT_DTYPES: Final[frozenset[str]] = frozenset(
    {"float32", "float16", "bfloat16"}
)
_INT_DTYPES: Final[frozenset[str]] = frozenset({"int8", "uint8", "int32"})
ADMITTED_DTYPES: Final[frozenset[str]] = _FLOAT_DTYPES | _INT_DTYPES
ADMITTED_BYTE_ORDERS: Final[frozenset[str]] = frozenset({"little", "big"})

_DTYPE_WIDTH: Final[Mapping[str, int]] = MappingProxyType(
    {
        "float32": 4,
        "float16": 2,
        "bfloat16": 2,
        "int8": 1,
        "uint8": 1,
        "int32": 4,
    }
)
_INT_RANGES: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        "int8": (-128, 127),
        "uint8": (0, 255),
        "int32": (-(1 << 31), (1 << 31) - 1),
    }
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SemanticWorldArtifactError(ValueError):
    """Base error for immutable semantic-world artifact admission or retrieval."""


class SemanticWorldArtifactAdmissionError(SemanticWorldArtifactError):
    """Raised when a write is rejected by closed admission policy."""


class SemanticWorldArtifactIntegrityError(SemanticWorldArtifactError):
    """Raised when bytes, CID, kind, or sealed shape do not verify."""


class SemanticWorldArtifactNotFound(SemanticWorldArtifactError, KeyError):
    """Raised when no verified block exists for a CID."""


class SemanticWorldArtifactConflictError(SemanticWorldArtifactError):
    """Raised when an identity or operation_id is rebound to different bytes."""


# ---------------------------------------------------------------------------
# Closed kinds / write result
# ---------------------------------------------------------------------------


class SemanticWorldArtifactKind(str, Enum):
    """Closed taxonomy of semantic-world storage admission kinds."""

    SEMANTIC_OBJECT = "semantic_object"
    VECTOR_BYTES = "vector_bytes"
    PROJECTION_RECORD = "projection_record"
    PROJECTION_INDEX_MANIFEST = "projection_index_manifest"


@dataclass(frozen=True, slots=True)
class SemanticWorldWriteResult:
    """Verified local write; identity CID is the caller-facing address."""

    cid: str
    storage_cid: str
    kind: SemanticWorldArtifactKind
    created: bool
    local_durable: bool
    reason_code: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cid": self.cid,
            "storage_cid": self.storage_cid,
            "kind": self.kind.value,
            "created": self.created,
            "local_durable": self.local_durable,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class CanonicalVectorBytes:
    """Deterministic packed vector admitted for durable storage."""

    dtype: str
    byte_order: str
    dimension: int
    packed_bytes: bytes

    @property
    def bytes_hex(self) -> str:
        return self.packed_bytes.hex()

    @property
    def bytes_cid(self) -> str:
        return cid_for_bytes(self.packed_bytes, "raw")

    def payload(self) -> dict[str, Any]:
        return {
            "dtype": self.dtype,
            "byte_order": self.byte_order,
            "dimension": self.dimension,
            "bytes_hex": self.bytes_hex,
            "bytes_cid": self.bytes_cid,
        }


# ---------------------------------------------------------------------------
# Private / structured admission helpers
# ---------------------------------------------------------------------------


def _key_is_private(name: str) -> bool:
    lowered = name.lower()
    if lowered in PRIVATE_FIELD_MARKERS:
        return True
    return any(marker in lowered for marker in PRIVATE_FIELD_MARKERS)


def reject_private_raw_source(value: Any, *, path: str = "$") -> None:
    """Fail closed when private raw source or related private fields are present."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                raise SemanticWorldArtifactAdmissionError(
                    f"{path} map keys must be str, got {type(key).__name__}"
                )
            key_path = f"{path}.{key}"
            if _key_is_private(key):
                raise SemanticWorldArtifactAdmissionError(
                    f"{key_path} rejects private raw source / private field {key!r}"
                )
            reject_private_raw_source(item, path=key_path)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            reject_private_raw_source(item, path=f"{path}[{index}]")


def _require_structured_json_value(value: Any, *, path: str = "$") -> None:
    """Admit only strict dag-json scalars/containers (no float/bytes/host types)."""

    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        if value < -MAX_SAFE_INTEGER or value > MAX_SAFE_INTEGER:
            raise SemanticWorldArtifactAdmissionError(
                f"{path} integer is outside the safe JSON range"
            )
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
                raise SemanticWorldArtifactAdmissionError(
                    f"{path} map keys must be str, got {type(key).__name__}"
                )
            _require_structured_json_value(item, path=f"{path}.{key}")
        return
    raise SemanticWorldArtifactAdmissionError(
        f"{path} must be strict DAG-JSON (no floats, bytes, or host types); "
        f"got {type(value).__name__}"
    )


def _coerce_kind(
    kind: SemanticWorldArtifactKind | str,
) -> SemanticWorldArtifactKind:
    if isinstance(kind, SemanticWorldArtifactKind):
        return kind
    if isinstance(kind, str):
        try:
            return SemanticWorldArtifactKind(kind)
        except ValueError as exc:
            raise SemanticWorldArtifactAdmissionError(
                f"unknown semantic-world artifact kind: {kind!r}"
            ) from exc
    raise SemanticWorldArtifactAdmissionError(
        "kind must be a SemanticWorldArtifactKind or its closed string value"
    )


def _schema_version(schema: str) -> int | None:
    match = _SCHEMA_VERSION_SUFFIX.search(schema)
    if match is None:
        return None
    return int(match.group(1))


def validate_stored_artifact_schema(schema: object) -> str:
    """Require the exact closed storage-envelope schema URI at version 1."""

    if not isinstance(schema, str) or not schema:
        raise SemanticWorldArtifactAdmissionError(
            "artifact schema must be a non-empty string"
        )
    version = _schema_version(schema)
    if version is None:
        raise SemanticWorldArtifactAdmissionError(
            "artifact schema must declare a version suffix @N"
        )
    if version != ARTIFACT_SCHEMA_VERSION:
        raise SemanticWorldArtifactAdmissionError(
            f"unknown artifact schema version: expected @{ARTIFACT_SCHEMA_VERSION}, "
            f"got @{version}"
        )
    if schema != STORED_ARTIFACT_SCHEMA:
        raise SemanticWorldArtifactAdmissionError(
            f"unknown artifact schema: {schema!r}"
        )
    return schema


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
        raise SemanticWorldArtifactAdmissionError(
            f"artifact is not canonical JSON: {exc}"
        ) from exc


def seal_semantic_world_artifact(
    kind: SemanticWorldArtifactKind | str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the closed, content-addressed storage envelope for a payload."""

    artifact_kind = _coerce_kind(kind)
    if not isinstance(payload, Mapping):
        raise SemanticWorldArtifactAdmissionError("payload must be a mapping")
    body = dict(payload)
    _require_structured_json_value(body, path="payload")
    reject_private_raw_source(body, path="payload")
    sealed = {
        "schema": STORED_ARTIFACT_SCHEMA,
        "interface_id": STORED_ARTIFACT_INTERFACE,
        "kind": artifact_kind.value,
        "payload": body,
    }
    reject_private_raw_source(sealed, path="$")
    data = _canonical_bytes(sealed)
    if len(data) > MAX_ARTIFACT_BYTES:
        raise SemanticWorldArtifactAdmissionError(
            f"artifact exceeds MAX_ARTIFACT_BYTES ({len(data)} > {MAX_ARTIFACT_BYTES})"
        )
    return sealed


def cid_for_semantic_world_artifact(
    kind: SemanticWorldArtifactKind | str,
    payload: Mapping[str, Any],
) -> str:
    """Return the dag-json CIDv1 of the sealed storage envelope."""

    return cid_for_artifact(seal_semantic_world_artifact(kind, payload))


def admit_sealed_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a retrieved or candidate sealed envelope and return a plain dict."""

    if not isinstance(record, Mapping):
        raise SemanticWorldArtifactIntegrityError("sealed artifact must be a mapping")
    actual = frozenset(record)
    if actual != _SEALED_FIELDS:
        missing = sorted(_SEALED_FIELDS - actual)
        unknown = sorted(actual - _SEALED_FIELDS)
        problems: list[str] = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        raise SemanticWorldArtifactIntegrityError(
            "sealed artifact has " + "; ".join(problems)
        )
    try:
        validate_stored_artifact_schema(record["schema"])
    except SemanticWorldArtifactAdmissionError as exc:
        raise SemanticWorldArtifactIntegrityError(str(exc)) from exc
    if record.get("interface_id") != STORED_ARTIFACT_INTERFACE:
        raise SemanticWorldArtifactIntegrityError(
            "unknown sealed artifact interface_id"
        )
    try:
        kind = _coerce_kind(record["kind"])
    except SemanticWorldArtifactAdmissionError as exc:
        raise SemanticWorldArtifactIntegrityError(str(exc)) from exc
    payload = record["payload"]
    if not isinstance(payload, Mapping):
        raise SemanticWorldArtifactIntegrityError("payload must be a mapping")
    body = dict(payload)
    try:
        _require_structured_json_value(body, path="payload")
        reject_private_raw_source(body, path="payload")
    except SemanticWorldArtifactAdmissionError as exc:
        raise SemanticWorldArtifactIntegrityError(str(exc)) from exc
    sealed = {
        "schema": STORED_ARTIFACT_SCHEMA,
        "interface_id": STORED_ARTIFACT_INTERFACE,
        "kind": kind.value,
        "payload": body,
    }
    data = _canonical_bytes(sealed)
    if len(data) > MAX_ARTIFACT_BYTES:
        raise SemanticWorldArtifactIntegrityError(
            f"artifact exceeds MAX_ARTIFACT_BYTES ({len(data)} > {MAX_ARTIFACT_BYTES})"
        )
    if cid_for_artifact(dict(record)) != cid_for_artifact(sealed):
        raise SemanticWorldArtifactIntegrityError(
            "sealed artifact is not in canonical form"
        )
    return sealed


def identity_cid_from_payload(
    kind: SemanticWorldArtifactKind | str,
    payload: Mapping[str, Any],
) -> str:
    """Return the caller-facing identity CID bound inside a sealed payload."""

    artifact_kind = _coerce_kind(kind)
    if artifact_kind is SemanticWorldArtifactKind.SEMANTIC_OBJECT:
        field = "semantic_object_cid"
    elif artifact_kind is SemanticWorldArtifactKind.PROJECTION_RECORD:
        field = "projection_cid"
    elif artifact_kind is SemanticWorldArtifactKind.PROJECTION_INDEX_MANIFEST:
        field = "projection_index_manifest_cid"
    else:
        field = "bytes_cid"
    value = payload.get(field)
    try:
        return validate_verified_cid(value, field)
    except SemanticGovernorStoreContractError as exc:
        raise SemanticWorldArtifactIntegrityError(
            f"payload.{field} must be a canonical transport CID"
        ) from exc


# ---------------------------------------------------------------------------
# Canonical vector byte vectors
# ---------------------------------------------------------------------------


def _require_dtype(dtype: object) -> str:
    if isinstance(dtype, Enum):
        dtype = dtype.value
    if type(dtype) is not str or dtype not in ADMITTED_DTYPES:
        raise SemanticWorldArtifactAdmissionError(
            f"dtype must be one of {sorted(ADMITTED_DTYPES)}"
        )
    return dtype


def _require_byte_order(byte_order: object) -> str:
    if isinstance(byte_order, Enum):
        byte_order = byte_order.value
    if type(byte_order) is not str or not byte_order:
        raise SemanticWorldArtifactAdmissionError("unspecified byte order")
    if byte_order not in ADMITTED_BYTE_ORDERS:
        raise SemanticWorldArtifactAdmissionError(
            "byte_order must be little or big"
        )
    return byte_order


def _require_dimension(dimension: object) -> int:
    if type(dimension) is not int or isinstance(dimension, bool):
        raise SemanticWorldArtifactAdmissionError(
            "dimension must be a positive integer"
        )
    if dimension < 1 or dimension > MAX_VECTOR_DIMENSION:
        raise SemanticWorldArtifactAdmissionError(
            f"dimension must be an integer in 1..{MAX_VECTOR_DIMENSION}"
        )
    return dimension


def _endian_prefix(byte_order: str) -> str:
    return "<" if byte_order == "little" else ">"


def _reject_nonfinite(value: float, *, index: int) -> float:
    if math.isnan(value):
        raise SemanticWorldArtifactAdmissionError(f"NaN at vector index {index}")
    if math.isinf(value):
        raise SemanticWorldArtifactAdmissionError(
            f"infinity at vector index {index}"
        )
    return value


def _bfloat16_bytes(value: float, *, byte_order: str, index: int) -> bytes:
    _reject_nonfinite(value, index=index)
    packed32 = struct.pack(">f", value)
    bits = packed32[:2]
    return bits[::-1] if byte_order == "little" else bits


def _from_bfloat16(data: bytes, *, byte_order: str) -> float:
    bits = data[::-1] if byte_order == "little" else data
    return struct.unpack(">f", bits + b"\x00\x00")[0]


def _pack_one(
    value: Any,
    *,
    dtype: str,
    byte_order: str,
    index: int,
) -> bytes:
    if dtype in _FLOAT_DTYPES:
        if type(value) is bool or type(value) not in {int, float}:
            raise SemanticWorldArtifactAdmissionError(
                f"vector[{index}] must be a finite number for {dtype}"
            )
        number = _reject_nonfinite(float(value), index=index)
        if dtype == "bfloat16":
            return _bfloat16_bytes(number, byte_order=byte_order, index=index)
        fmt = _endian_prefix(byte_order) + ("f" if dtype == "float32" else "e")
        packed = struct.pack(fmt, number)
        unpacked = struct.unpack(fmt, packed)[0]
        _reject_nonfinite(float(unpacked), index=index)
        return packed
    if type(value) is bool or type(value) is not int:
        raise SemanticWorldArtifactAdmissionError(
            f"vector[{index}] must be an integer for {dtype}"
        )
    low, high = _INT_RANGES[dtype]
    if value < low or value > high:
        raise SemanticWorldArtifactAdmissionError(
            f"vector[{index}] is outside the {dtype} range"
        )
    fmt = _endian_prefix(byte_order) + {"int8": "b", "uint8": "B", "int32": "i"}[dtype]
    return struct.pack(fmt, value)


def _unpack_one(chunk: bytes, *, dtype: str, byte_order: str, index: int) -> int | float:
    if dtype == "bfloat16":
        value = _from_bfloat16(chunk, byte_order=byte_order)
        return _reject_nonfinite(value, index=index)
    if dtype in _FLOAT_DTYPES:
        fmt = _endian_prefix(byte_order) + ("f" if dtype == "float32" else "e")
        value = float(struct.unpack(fmt, chunk)[0])
        return _reject_nonfinite(value, index=index)
    fmt = _endian_prefix(byte_order) + {"int8": "b", "uint8": "B", "int32": "i"}[dtype]
    return int(struct.unpack(fmt, chunk)[0])


def pack_canonical_vector(
    values: Sequence[Any] | bytes,
    *,
    dtype: str | Enum,
    byte_order: str | Enum,
    dimension: int,
) -> CanonicalVectorBytes:
    """Pack values into deterministic dtype/byte-order bytes.

    NaN, infinity, dimension mismatch, unspecified byte order, and unreviewed
    dtypes fail closed.  Packed bytes are the canonical vector representation;
    their raw CID is the vector identity used by projection records.
    """

    admitted_dtype = _require_dtype(dtype)
    admitted_order = _require_byte_order(byte_order)
    admitted_dimension = _require_dimension(dimension)
    width = _DTYPE_WIDTH[admitted_dtype]
    expected_size = admitted_dimension * width

    if type(values) is bytes:
        if len(values) != expected_size:
            raise SemanticWorldArtifactAdmissionError(
                f"dimension mismatch: packed bytes length {len(values)} "
                f"!= {admitted_dimension} * {width}"
            )
        packed = values
        for index in range(admitted_dimension):
            start = index * width
            _unpack_one(
                packed[start : start + width],
                dtype=admitted_dtype,
                byte_order=admitted_order,
                index=index,
            )
    else:
        if isinstance(values, (str, bytearray, memoryview)) or not isinstance(
            values, Sequence
        ):
            raise SemanticWorldArtifactAdmissionError(
                "vector values must be a sequence of numbers or packed bytes"
            )
        if len(values) != admitted_dimension:
            raise SemanticWorldArtifactAdmissionError(
                f"dimension mismatch: {len(values)} values != dimension {admitted_dimension}"
            )
        packed = b"".join(
            _pack_one(
                item,
                dtype=admitted_dtype,
                byte_order=admitted_order,
                index=index,
            )
            for index, item in enumerate(values)
        )
        if len(packed) != expected_size:
            raise SemanticWorldArtifactAdmissionError(
                "packed vector byte length does not match dimension and dtype"
            )

    return CanonicalVectorBytes(
        dtype=admitted_dtype,
        byte_order=admitted_order,
        dimension=admitted_dimension,
        packed_bytes=packed,
    )


def admit_canonical_vector_payload(payload: Mapping[str, Any]) -> CanonicalVectorBytes:
    """Re-verify a stored vector payload, including claimed raw-byte CID rehash."""

    if not isinstance(payload, Mapping):
        raise SemanticWorldArtifactIntegrityError("vector payload must be a mapping")
    actual = frozenset(payload)
    if actual != _VECTOR_PAYLOAD_FIELDS:
        missing = sorted(_VECTOR_PAYLOAD_FIELDS - actual)
        unknown = sorted(actual - _VECTOR_PAYLOAD_FIELDS)
        problems: list[str] = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        raise SemanticWorldArtifactIntegrityError(
            "vector payload has " + "; ".join(problems)
        )
    try:
        dtype = _require_dtype(payload["dtype"])
        byte_order = _require_byte_order(payload["byte_order"])
        dimension = _require_dimension(payload["dimension"])
    except SemanticWorldArtifactAdmissionError as exc:
        raise SemanticWorldArtifactIntegrityError(str(exc)) from exc
    bytes_hex = payload["bytes_hex"]
    if type(bytes_hex) is not str or not _HEX.fullmatch(bytes_hex) or len(bytes_hex) % 2:
        raise SemanticWorldArtifactIntegrityError(
            "bytes_hex must be lowercase even-length hex"
        )
    try:
        packed = bytes.fromhex(bytes_hex)
    except ValueError as exc:
        raise SemanticWorldArtifactIntegrityError("bytes_hex is not valid hex") from exc
    try:
        vector = pack_canonical_vector(
            packed, dtype=dtype, byte_order=byte_order, dimension=dimension
        )
    except SemanticWorldArtifactAdmissionError as exc:
        raise SemanticWorldArtifactIntegrityError(str(exc)) from exc
    if vector.bytes_hex != bytes_hex:
        raise SemanticWorldArtifactIntegrityError(
            "vector bytes_hex is not the canonical lowercase encoding"
        )
    try:
        claimed = validate_verified_cid(payload["bytes_cid"], "bytes_cid")
    except SemanticGovernorStoreContractError as exc:
        raise SemanticWorldArtifactIntegrityError(
            "bytes_cid must be a canonical transport CID"
        ) from exc
    if claimed != vector.bytes_cid:
        raise SemanticWorldArtifactIntegrityError(
            f"claimed vector CID does not rehash: computed {vector.bytes_cid}, "
            f"claimed {claimed}"
        )
    if validate_transport_cid(claimed) != "raw":
        raise SemanticWorldArtifactIntegrityError(
            "vector bytes_cid must be a raw CID of packed bytes"
        )
    return vector


# ---------------------------------------------------------------------------
# Identity / operation index (rebuildable; blocks remain authoritative)
# ---------------------------------------------------------------------------


class _IdentityIndex:
    """Local identity/operation bindings next to the coordination store root."""

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
            CREATE TABLE IF NOT EXISTS identity_bindings (
              identity_cid TEXT PRIMARY KEY,
              storage_cid TEXT NOT NULL,
              kind TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS identity_bindings_storage
              ON identity_bindings(storage_cid);
            CREATE TABLE IF NOT EXISTS artifact_operations (
              operation_id TEXT PRIMARY KEY,
              identity_cid TEXT NOT NULL,
              storage_cid TEXT NOT NULL,
              kind TEXT NOT NULL
            );
            """
        )
        self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def lookup_identity(self, identity_cid: str) -> tuple[str, str] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT storage_cid, kind FROM identity_bindings WHERE identity_cid = ?",
                (identity_cid,),
            ).fetchone()
        if row is None:
            return None
        return str(row["storage_cid"]), str(row["kind"])

    def lookup_storage(self, storage_cid: str) -> tuple[str, str] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT identity_cid, kind FROM identity_bindings WHERE storage_cid = ?",
                (storage_cid,),
            ).fetchone()
        if row is None:
            return None
        return str(row["identity_cid"]), str(row["kind"])

    def lookup_operation(self, operation_id: str) -> tuple[str, str, str] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT identity_cid, storage_cid, kind FROM artifact_operations "
                "WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
        if row is None:
            return None
        return str(row["identity_cid"]), str(row["storage_cid"]), str(row["kind"])

    def bind_identity(self, identity_cid: str, storage_cid: str, kind: str) -> None:
        with self._lock:
            existing = self._connection.execute(
                "SELECT storage_cid, kind FROM identity_bindings WHERE identity_cid = ?",
                (identity_cid,),
            ).fetchone()
            if existing is not None:
                if str(existing["storage_cid"]) != storage_cid or str(existing["kind"]) != kind:
                    raise SemanticWorldArtifactConflictError(
                        f"identity {identity_cid!r} already bound to a different artifact"
                    )
                return
            with self._connection:
                self._connection.execute(
                    "INSERT INTO identity_bindings(identity_cid, storage_cid, kind) "
                    "VALUES(?,?,?)",
                    (identity_cid, storage_cid, kind),
                )

    def bind_operation(
        self,
        operation_id: str,
        identity_cid: str,
        storage_cid: str,
        kind: str,
    ) -> None:
        with self._lock:
            existing = self._connection.execute(
                "SELECT identity_cid, storage_cid, kind FROM artifact_operations "
                "WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["identity_cid"]) != identity_cid
                    or str(existing["storage_cid"]) != storage_cid
                    or str(existing["kind"]) != kind
                ):
                    raise SemanticWorldArtifactConflictError(
                        f"operation_id {operation_id!r} already bound to a different artifact"
                    )
                return
            with self._connection:
                self._connection.execute(
                    "INSERT INTO artifact_operations"
                    "(operation_id, identity_cid, storage_cid, kind) VALUES(?,?,?,?)",
                    (operation_id, identity_cid, storage_cid, kind),
                )


# ---------------------------------------------------------------------------
# Store implementation
# ---------------------------------------------------------------------------


class SemanticWorldArtifactStore:
    """Immutable typed semantic-world artifact store over ``DurableCoordinationStore``.

    Implements the put/get surface of ``SemanticWorldArtifactStore@1``.  Higher
    layers bind datasets identity profiles without adding a second CID engine.
    """

    def __init__(self, store: DurableCoordinationStore) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store
        self._index = _IdentityIndex(store)
        self._rebuild_identity_index()

    @property
    def store(self) -> DurableCoordinationStore:
        """Injected coordination store (diagnostics / composition only)."""

        return self._store

    def close(self) -> None:
        self._index.close()

    def __enter__(self) -> "SemanticWorldArtifactStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _rebuild_identity_index(self) -> None:
        """Rebind identity CIDs from authoritative sealed blocks."""

        for path in sorted(self._store.blocks_dir.glob("*/*.json")):
            storage_cid = path.stem
            try:
                validate_transport_cid(storage_cid)
                raw = self._store.get(storage_cid)
            except (
                ArtifactNotFound,
                ArtifactIntegrityError,
                TypeError,
                ValueError,
                UnicodeDecodeError,
                json.JSONDecodeError,
            ):
                continue
            if not isinstance(raw, Mapping) or raw.get("schema") != STORED_ARTIFACT_SCHEMA:
                continue
            try:
                sealed = admit_sealed_record(raw)
                kind = _coerce_kind(sealed["kind"])
                identity_cid = identity_cid_from_payload(kind, sealed["payload"])
                if kind is SemanticWorldArtifactKind.VECTOR_BYTES:
                    admit_canonical_vector_payload(sealed["payload"])
                self._index.bind_identity(identity_cid, storage_cid, kind.value)
            except (
                SemanticWorldArtifactError,
                SemanticGovernorStoreContractError,
                ArtifactIntegrityError,
            ):
                continue

    def _rehash_storage_bytes(self, cid: str) -> bytes:
        try:
            data = self._store.get_bytes(cid)
        except ArtifactNotFound as exc:
            raise SemanticWorldArtifactNotFound(cid) from exc
        except ArtifactIntegrityError as exc:
            raise SemanticWorldArtifactIntegrityError(str(exc)) from exc
        codec = validate_transport_cid(cid)
        if cid_for_bytes(data, codec) != cid:
            raise SemanticWorldArtifactIntegrityError(
                f"local bytes do not match {cid}"
            )
        return data

    def _put_sealed(
        self,
        *,
        kind: SemanticWorldArtifactKind,
        payload: Mapping[str, Any],
        identity_cid: str,
        expected_cid: str | None,
        operation_id: str | None,
        replicate: bool,
    ) -> SemanticWorldWriteResult:
        try:
            identity_cid = validate_verified_cid(identity_cid, "identity_cid")
            if expected_cid is not None:
                expected_cid = validate_verified_cid(expected_cid, "expected_cid")
            if operation_id is not None:
                operation_id = validate_operation_id(operation_id)
        except SemanticGovernorStoreContractError as exc:
            raise SemanticWorldArtifactAdmissionError(str(exc)) from exc

        if expected_cid is not None and expected_cid != identity_cid:
            raise SemanticWorldArtifactIntegrityError(
                f"forged or mismatched artifact CID: computed {identity_cid}, "
                f"expected {expected_cid}"
            )

        sealed = seal_semantic_world_artifact(kind, payload)
        storage_cid = cid_for_artifact(sealed)
        payload_identity = identity_cid_from_payload(kind, sealed["payload"])
        if payload_identity != identity_cid:
            raise SemanticWorldArtifactIntegrityError(
                f"payload identity CID {payload_identity} does not match {identity_cid}"
            )

        if operation_id is not None:
            prior_op = self._index.lookup_operation(operation_id)
            if prior_op is not None:
                prior_identity, prior_storage, prior_kind = prior_op
                if (
                    prior_identity != identity_cid
                    or prior_storage != storage_cid
                    or prior_kind != kind.value
                ):
                    raise SemanticWorldArtifactConflictError(
                        f"operation_id {operation_id!r} already bound to a different artifact"
                    )

        prior = self._index.lookup_identity(identity_cid)
        if prior is not None:
            prior_storage, prior_kind = prior
            if prior_storage != storage_cid or prior_kind != kind.value:
                raise SemanticWorldArtifactConflictError(
                    f"identity {identity_cid!r} already bound to a different artifact"
                )
            self.get_verified_artifact(identity_cid, expected_kind=kind)
            if operation_id is not None:
                self._index.bind_operation(
                    operation_id, identity_cid, storage_cid, kind.value
                )
            return SemanticWorldWriteResult(
                identity_cid,
                storage_cid,
                kind,
                False,
                True,
                "unchanged",
            )

        try:
            local = self._store.put(
                sealed,
                expected_cid=storage_cid,
                codec="dag-json",
                replicate=False,
            )
        except ArtifactIntegrityError as exc:
            raise SemanticWorldArtifactIntegrityError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise SemanticWorldArtifactAdmissionError(str(exc)) from exc

        returned = str(local["cid"])
        if returned != storage_cid:
            raise SemanticWorldArtifactIntegrityError(
                f"store returned unexpected CID {returned}, expected {storage_cid}"
            )
        self._rehash_storage_bytes(storage_cid)
        self._index.bind_identity(identity_cid, storage_cid, kind.value)
        if operation_id is not None:
            self._index.bind_operation(
                operation_id, identity_cid, storage_cid, kind.value
            )

        created = bool(local.get("created", True))
        if replicate and self._store.backend is not None:
            try:
                remote = self._store.put(
                    sealed,
                    expected_cid=storage_cid,
                    codec="dag-json",
                    replicate=True,
                )
            except Exception:
                remote = None
            if remote is None or remote.get("cid") != storage_cid:
                return SemanticWorldWriteResult(
                    identity_cid,
                    storage_cid,
                    kind,
                    created,
                    True,
                    "provider_failed",
                )
        reason = "stored" if created else "unchanged"
        if replicate and self._store.backend is None:
            reason = "provider_unavailable"
        return SemanticWorldWriteResult(
            identity_cid,
            storage_cid,
            kind,
            created,
            True,
            reason,
        )

    def put_artifact(
        self,
        kind: SemanticWorldArtifactKind | str,
        payload: Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> SemanticWorldWriteResult:
        """Admit, seal, verify CID, and durably store one immutable artifact."""

        artifact_kind = _coerce_kind(kind)
        sealed = seal_semantic_world_artifact(artifact_kind, payload)
        identity_cid = identity_cid_from_payload(artifact_kind, sealed["payload"])
        if artifact_kind is SemanticWorldArtifactKind.VECTOR_BYTES:
            admit_canonical_vector_payload(sealed["payload"])
        return self._put_sealed(
            kind=artifact_kind,
            payload=sealed["payload"],
            identity_cid=identity_cid,
            expected_cid=expected_cid,
            operation_id=operation_id,
            replicate=replicate,
        )

    def put_vector_bytes(
        self,
        values: Sequence[Any] | bytes,
        *,
        dtype: str | Enum,
        byte_order: str | Enum,
        dimension: int,
        expected_cid: str | None = None,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> SemanticWorldWriteResult:
        """Pack, CID, and store canonical vector bytes before any reference."""

        vector = pack_canonical_vector(
            values, dtype=dtype, byte_order=byte_order, dimension=dimension
        )
        return self._put_sealed(
            kind=SemanticWorldArtifactKind.VECTOR_BYTES,
            payload=vector.payload(),
            identity_cid=vector.bytes_cid,
            expected_cid=expected_cid,
            operation_id=operation_id,
            replicate=replicate,
        )

    def _resolve_storage_cid(self, cid: str) -> tuple[str, str | None]:
        try:
            cid = validate_verified_cid(cid, "cid")
        except SemanticGovernorStoreContractError as exc:
            raise SemanticWorldArtifactIntegrityError(str(exc)) from exc
        bound = self._index.lookup_identity(cid)
        if bound is not None:
            return bound[0], bound[1]
        storage_bound = self._index.lookup_storage(cid)
        if storage_bound is not None:
            return cid, storage_bound[1]
        if self._store.has(cid):
            return cid, None
        raise SemanticWorldArtifactNotFound(cid)

    def get_verified_artifact(
        self,
        cid: str,
        *,
        expected_kind: Optional[SemanticWorldArtifactKind | str] = None,
    ) -> Mapping[str, Any]:
        """Load and re-verify a sealed semantic-world artifact by identity or storage CID."""

        storage_cid, indexed_kind = self._resolve_storage_cid(cid)
        self._rehash_storage_bytes(storage_cid)
        try:
            raw = self._store.get(storage_cid)
        except ArtifactNotFound as exc:
            raise SemanticWorldArtifactNotFound(cid) from exc
        except ArtifactIntegrityError as exc:
            raise SemanticWorldArtifactIntegrityError(str(exc)) from exc
        except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SemanticWorldArtifactIntegrityError(str(exc)) from exc
        if not isinstance(raw, Mapping):
            raise SemanticWorldArtifactIntegrityError(
                f"{storage_cid} did not decode to a mapping"
            )

        sealed = admit_sealed_record(raw)
        recomputed = cid_for_artifact(sealed)
        if recomputed != storage_cid:
            raise SemanticWorldArtifactIntegrityError(
                f"forged sealed artifact: recomputed {recomputed}, expected {storage_cid}"
            )
        kind = SemanticWorldArtifactKind(sealed["kind"])
        if indexed_kind is not None and indexed_kind != kind.value:
            raise SemanticWorldArtifactIntegrityError(
                f"index kind {indexed_kind} does not match stored {kind.value}"
            )
        if expected_kind is not None:
            wanted = _coerce_kind(expected_kind)
            if kind is not wanted:
                raise SemanticWorldArtifactIntegrityError(
                    f"wrong artifact kind: stored {kind.value}, "
                    f"expected {wanted.value}"
                )
        identity_cid = identity_cid_from_payload(kind, sealed["payload"])
        if kind is SemanticWorldArtifactKind.VECTOR_BYTES:
            vector = admit_canonical_vector_payload(sealed["payload"])
            if vector.bytes_cid != identity_cid:
                raise SemanticWorldArtifactIntegrityError(
                    "vector payload CID does not rehash packed bytes"
                )
        self._index.bind_identity(identity_cid, storage_cid, kind.value)
        return MappingProxyType(
            {
                "schema": sealed["schema"],
                "interface_id": sealed["interface_id"],
                "kind": sealed["kind"],
                "payload": MappingProxyType(dict(sealed["payload"])),
                "storage_cid": storage_cid,
                "identity_cid": identity_cid,
            }
        )

    def get_verified_vector(self, cid: str) -> CanonicalVectorBytes:
        """Load and re-verify canonical packed vector bytes."""

        artifact = self.get_verified_artifact(
            cid, expected_kind=SemanticWorldArtifactKind.VECTOR_BYTES
        )
        return admit_canonical_vector_payload(dict(artifact["payload"]))


__all__ = [
    "ADMITTED_BYTE_ORDERS",
    "ADMITTED_DTYPES",
    "ARTIFACT_MODULE_INTERFACE",
    "ARTIFACT_SCHEMA_VERSION",
    "CANONICAL_VECTOR_BYTES_INTERFACE",
    "MAX_ARTIFACT_BYTES",
    "MAX_VECTOR_DIMENSION",
    "PRIVATE_FIELD_MARKERS",
    "STORED_ARTIFACT_INTERFACE",
    "STORED_ARTIFACT_SCHEMA",
    "CanonicalVectorBytes",
    "SemanticWorldArtifactAdmissionError",
    "SemanticWorldArtifactConflictError",
    "SemanticWorldArtifactError",
    "SemanticWorldArtifactIntegrityError",
    "SemanticWorldArtifactKind",
    "SemanticWorldArtifactNotFound",
    "SemanticWorldArtifactStore",
    "SemanticWorldWriteResult",
    "admit_canonical_vector_payload",
    "admit_sealed_record",
    "cid_for_semantic_world_artifact",
    "identity_cid_from_payload",
    "pack_canonical_vector",
    "reject_private_raw_source",
    "seal_semantic_world_artifact",
    "validate_stored_artifact_schema",
]
