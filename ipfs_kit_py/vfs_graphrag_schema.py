"""Canonical VFS GraphRAG metadata schemas.

This module is intentionally dependency-free.  Later index, adapter, and export
layers can import these records without requiring optional GraphRAG, Arrow, or
vector-store packages.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, ClassVar, Dict, Iterable, List, Mapping, Optional, Type, TypeVar


SCHEMA_VERSION = "1.0.0"
SCHEMA_NAMESPACE = "ipfs_kit_py.vfs.graphrag"

OBJECT_SCHEMA = f"{SCHEMA_NAMESPACE}.object.v1"
CHUNK_SCHEMA = f"{SCHEMA_NAMESPACE}.chunk.v1"
EMBEDDING_SCHEMA = f"{SCHEMA_NAMESPACE}.embedding.v1"
ENTITY_SCHEMA = f"{SCHEMA_NAMESPACE}.entity.v1"
RELATIONSHIP_SCHEMA = f"{SCHEMA_NAMESPACE}.relationship.v1"
SNAPSHOT_SCHEMA = f"{SCHEMA_NAMESPACE}.snapshot.v1"
CHECKPOINT_SCHEMA = f"{SCHEMA_NAMESPACE}.checkpoint.v1"
EXPORT_MANIFEST_SCHEMA = f"{SCHEMA_NAMESPACE}.export_manifest.v1"

DEFAULT_NAMESPACE = "default"
DEFAULT_MIME_TYPE = "application/octet-stream"

JSONValue = Any
MigrationHook = Callable[[Dict[str, JSONValue]], Dict[str, JSONValue]]
T = TypeVar("T", bound="SerializableRecord")

_SCHEMA_MIGRATIONS: Dict[str, MigrationHook] = {}


def utc_now_iso() -> str:
    """Return a stable UTC timestamp string for newly-created records."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_vfs_path(path: str) -> str:
    """Normalize a VFS path for stable identity and filtering."""

    if not path:
        return "/"
    if "://" in path:
        protocol, remainder = path.split("://", 1)
        remainder = _collapse_slashes(remainder.lstrip("/"))
        return f"{protocol}://{remainder}"
    return _collapse_slashes("/" + path.lstrip("/"))


def stable_id(prefix: str, *parts: Any) -> str:
    """Build a deterministic identifier from canonical JSON-encoded parts."""

    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def register_schema_migration(from_schema: str, hook: MigrationHook) -> None:
    """Register a migration hook from an older schema id to the current shape."""

    _SCHEMA_MIGRATIONS[from_schema] = hook


def migrate_record_dict(data: Mapping[str, JSONValue]) -> Dict[str, JSONValue]:
    """Apply a registered migration hook when a record uses an older schema id."""

    migrated = dict(data)
    schema = migrated.get("schema")
    if schema in _SCHEMA_MIGRATIONS:
        migrated = _SCHEMA_MIGRATIONS[str(schema)](migrated)
    return migrated


def to_jsonl(records: Iterable["SerializableRecord"]) -> str:
    """Serialize records as newline-delimited JSON."""

    return "\n".join(record.to_json() for record in records)


def records_from_jsonl(lines: str, record_type: Type[T]) -> List[T]:
    """Deserialize newline-delimited JSON into one concrete record type."""

    return [record_type.from_json(line) for line in lines.splitlines() if line.strip()]


def _collapse_slashes(path: str) -> str:
    while "//" in path:
        path = path.replace("//", "/")
    return path


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _arrow_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json_default)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@dataclass
class SerializableRecord:
    """Base serialization helper for canonical records."""

    schema: ClassVar[str]

    def to_dict(self, *, arrow_friendly: bool = False) -> Dict[str, JSONValue]:
        data = asdict(self)
        data["schema"] = self.schema
        if arrow_friendly:
            data = {key: _arrow_value(value) for key, value in data.items()}
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), default=_json_default)

    @classmethod
    def from_dict(cls: Type[T], data: Mapping[str, JSONValue]) -> T:
        migrated = migrate_record_dict(data)
        migrated.pop("schema", None)
        allowed = cls.__dataclass_fields__.keys()  # type: ignore[attr-defined]
        return cls(**{key: value for key, value in migrated.items() if key in allowed})

    @classmethod
    def from_json(cls: Type[T], payload: str) -> T:
        return cls.from_dict(json.loads(payload))

    def to_arrow_dict(self) -> Dict[str, JSONValue]:
        return self.to_dict(arrow_friendly=True)


@dataclass
class VFSObjectRecord(SerializableRecord):
    """Canonical metadata for a VFS file, directory, dataset, or content object."""

    schema: ClassVar[str] = OBJECT_SCHEMA

    record_id: str = ""
    namespace: str = DEFAULT_NAMESPACE
    backend: str = "ipfs"
    protocol: str = "ipfs"
    path: str = ""
    normalized_path: str = ""
    content_id: Optional[str] = None
    content_hash: Optional[str] = None
    mime_type: str = DEFAULT_MIME_TYPE
    size_bytes: int = 0
    object_type: str = "file"
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    indexed_at: str = field(default_factory=utc_now_iso)
    tags: List[str] = field(default_factory=list)
    lineage: Dict[str, JSONValue] = field(default_factory=dict)
    security: Dict[str, JSONValue] = field(default_factory=dict)
    export: Dict[str, JSONValue] = field(default_factory=dict)
    metadata: Dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.normalized_path:
            self.normalized_path = normalize_vfs_path(self.path)
        if not self.record_id:
            self.record_id = stable_id(
                "vfsrec",
                self.namespace,
                self.backend,
                self.protocol,
                self.normalized_path,
                self.content_id,
                self.content_hash,
            )


@dataclass
class VFSChunkRecord(SerializableRecord):
    """Searchable chunk derived from a canonical VFS object."""

    schema: ClassVar[str] = CHUNK_SCHEMA

    chunk_id: str = ""
    parent_record_id: str = ""
    namespace: str = DEFAULT_NAMESPACE
    path: str = ""
    content_id: Optional[str] = None
    chunk_index: int = 0
    byte_start: Optional[int] = None
    byte_end: Optional[int] = None
    text_start: Optional[int] = None
    text_end: Optional[int] = None
    text_hash: Optional[str] = None
    extraction_method: str = "unknown"
    language: Optional[str] = None
    text: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.text_hash is None and self.text is not None:
            self.text_hash = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        if not self.chunk_id:
            self.chunk_id = stable_id(
                "vfschunk",
                self.parent_record_id,
                self.chunk_index,
                self.byte_start,
                self.byte_end,
                self.text_start,
                self.text_end,
                self.text_hash,
            )


@dataclass
class VFSEmbeddingRecord(SerializableRecord):
    """Embedding metadata for a chunk vector stored outside the schema record."""

    schema: ClassVar[str] = EMBEDDING_SCHEMA

    embedding_id: str = ""
    chunk_id: str = ""
    parent_record_id: str = ""
    model_id: str = ""
    dimension: int = 0
    vector_store_id: Optional[str] = None
    embedding_vector_id: Optional[str] = None
    embedding_checksum: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.embedding_id:
            self.embedding_id = stable_id(
                "vfsemb",
                self.chunk_id,
                self.model_id,
                self.dimension,
                self.vector_store_id,
                self.embedding_vector_id,
                self.embedding_checksum,
            )


@dataclass
class VFSEntityRecord(SerializableRecord):
    """Knowledge graph entity with provenance back to VFS records and chunks."""

    schema: ClassVar[str] = ENTITY_SCHEMA

    entity_id: str = ""
    name: str = ""
    entity_type: str = "entity"
    aliases: List[str] = field(default_factory=list)
    source_record_ids: List[str] = field(default_factory=list)
    source_chunk_ids: List[str] = field(default_factory=list)
    confidence: Optional[float] = None
    provenance: Dict[str, JSONValue] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.entity_id:
            self.entity_id = stable_id("vfsentity", self.name, self.entity_type, self.aliases)


@dataclass
class VFSRelationshipRecord(SerializableRecord):
    """Knowledge graph relationship or filesystem topology edge."""

    schema: ClassVar[str] = RELATIONSHIP_SCHEMA

    relationship_id: str = ""
    subject_id: str = ""
    predicate: str = ""
    object_id: str = ""
    relationship_type: str = "semantic"
    source_record_ids: List[str] = field(default_factory=list)
    source_chunk_ids: List[str] = field(default_factory=list)
    confidence: Optional[float] = None
    provenance: Dict[str, JSONValue] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.relationship_id:
            self.relationship_id = stable_id(
                "vfsrel",
                self.subject_id,
                self.predicate,
                self.object_id,
                self.relationship_type,
            )


@dataclass
class VFSSnapshotRecord(SerializableRecord):
    """Exportable filesystem/index snapshot metadata."""

    schema: ClassVar[str] = SNAPSHOT_SCHEMA

    snapshot_id: str = ""
    namespace: str = DEFAULT_NAMESPACE
    backend_bindings: Dict[str, JSONValue] = field(default_factory=dict)
    root_paths: List[str] = field(default_factory=list)
    index_cids: Dict[str, str] = field(default_factory=dict)
    metadata_cids: Dict[str, str] = field(default_factory=dict)
    vector_index_cids: Dict[str, str] = field(default_factory=dict)
    graph_export_cids: Dict[str, str] = field(default_factory=dict)
    journal_range: Dict[str, JSONValue] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            self.snapshot_id = stable_id(
                "vfssnap",
                self.namespace,
                self.root_paths,
                self.index_cids,
                self.metadata_cids,
                self.vector_index_cids,
                self.graph_export_cids,
                self.journal_range,
            )


@dataclass
class VFSCheckpointRecord(SerializableRecord):
    """Incremental indexing checkpoint for journal and backend cursors."""

    schema: ClassVar[str] = CHECKPOINT_SCHEMA

    checkpoint_id: str = ""
    namespace: str = DEFAULT_NAMESPACE
    backend: str = "ipfs"
    checkpoint_type: str = "journal"
    cursor: Dict[str, JSONValue] = field(default_factory=dict)
    journal_entry_id: Optional[str] = None
    journal_timestamp: Optional[str] = None
    bucket_last_updated: Optional[str] = None
    git_snapshot_id: Optional[str] = None
    metadata_schema_version: str = SCHEMA_VERSION
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.checkpoint_id:
            self.checkpoint_id = stable_id(
                "vfsckpt",
                self.namespace,
                self.backend,
                self.checkpoint_type,
                self.cursor,
                self.journal_entry_id,
                self.journal_timestamp,
                self.bucket_last_updated,
                self.git_snapshot_id,
                self.metadata_schema_version,
            )


@dataclass
class VFSExportManifest(SerializableRecord):
    """Manifest describing a portable VFS GraphRAG metadata export bundle."""

    schema: ClassVar[str] = EXPORT_MANIFEST_SCHEMA

    manifest_id: str = ""
    namespace: str = DEFAULT_NAMESPACE
    schema_version: str = SCHEMA_VERSION
    created_at: str = field(default_factory=utc_now_iso)
    exporter: str = "ipfs_kit_py"
    export_format: str = "jsonl"
    object_count: int = 0
    chunk_count: int = 0
    embedding_count: int = 0
    entity_count: int = 0
    relationship_count: int = 0
    snapshot_count: int = 0
    checkpoint_count: int = 0
    files: Dict[str, str] = field(default_factory=dict)
    root_cid: Optional[str] = None
    content_cids: List[str] = field(default_factory=list)
    metadata: Dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.manifest_id:
            self.manifest_id = stable_id(
                "vfsmanifest",
                self.namespace,
                self.schema_version,
                self.export_format,
                self.files,
                self.root_cid,
                self.content_cids,
            )


RECORD_TYPES: Dict[str, Type[SerializableRecord]] = {
    OBJECT_SCHEMA: VFSObjectRecord,
    CHUNK_SCHEMA: VFSChunkRecord,
    EMBEDDING_SCHEMA: VFSEmbeddingRecord,
    ENTITY_SCHEMA: VFSEntityRecord,
    RELATIONSHIP_SCHEMA: VFSRelationshipRecord,
    SNAPSHOT_SCHEMA: VFSSnapshotRecord,
    CHECKPOINT_SCHEMA: VFSCheckpointRecord,
    EXPORT_MANIFEST_SCHEMA: VFSExportManifest,
}


def record_from_dict(data: Mapping[str, JSONValue]) -> SerializableRecord:
    """Deserialize a canonical record using its embedded schema id."""

    migrated = migrate_record_dict(data)
    schema = migrated.get("schema")
    record_type = RECORD_TYPES.get(str(schema))
    if record_type is None:
        raise ValueError(f"Unsupported VFS GraphRAG schema: {schema!r}")
    return record_type.from_dict(migrated)


def record_from_json(payload: str) -> SerializableRecord:
    """Deserialize a canonical record from JSON using its embedded schema id."""

    return record_from_dict(json.loads(payload))


__all__ = [
    "CHECKPOINT_SCHEMA",
    "CHUNK_SCHEMA",
    "DEFAULT_MIME_TYPE",
    "DEFAULT_NAMESPACE",
    "EMBEDDING_SCHEMA",
    "ENTITY_SCHEMA",
    "EXPORT_MANIFEST_SCHEMA",
    "OBJECT_SCHEMA",
    "RECORD_TYPES",
    "RELATIONSHIP_SCHEMA",
    "SCHEMA_NAMESPACE",
    "SCHEMA_VERSION",
    "SNAPSHOT_SCHEMA",
    "SerializableRecord",
    "VFSCheckpointRecord",
    "VFSChunkRecord",
    "VFSEmbeddingRecord",
    "VFSEntityRecord",
    "VFSExportManifest",
    "VFSObjectRecord",
    "VFSRelationshipRecord",
    "VFSSnapshotRecord",
    "migrate_record_dict",
    "normalize_vfs_path",
    "record_from_dict",
    "record_from_json",
    "records_from_jsonl",
    "register_schema_migration",
    "stable_id",
    "to_jsonl",
    "utc_now_iso",
]
