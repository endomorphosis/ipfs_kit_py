"""Local storage for canonical VFS GraphRAG index records.

The index intentionally depends only on the schema module and the Python
standard library.  Optional Parquet support is enabled only when pandas and a
Parquet engine are already installed; JSONL remains the default durable format.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Type, TypeVar, Union

from .vfs_graphrag_schema import (
    CHECKPOINT_SCHEMA,
    CHUNK_SCHEMA,
    DEFAULT_NAMESPACE,
    EMBEDDING_SCHEMA,
    ENTITY_SCHEMA,
    OBJECT_SCHEMA,
    RECORD_TYPES,
    RELATIONSHIP_SCHEMA,
    SCHEMA_VERSION,
    SNAPSHOT_SCHEMA,
    SerializableRecord,
    VFSCheckpointRecord,
    VFSChunkRecord,
    VFSEmbeddingRecord,
    VFSEntityRecord,
    VFSObjectRecord,
    VFSRelationshipRecord,
    VFSSnapshotRecord,
    record_from_dict,
    record_from_json,
)


RecordInput = Union[SerializableRecord, Mapping[str, Any]]
T = TypeVar("T", bound=SerializableRecord)

_JSON_FIELDS = {
    "aliases",
    "backend_bindings",
    "content_cids",
    "cursor",
    "export",
    "files",
    "graph_export_cids",
    "index_cids",
    "journal_range",
    "lineage",
    "metadata",
    "metadata_cids",
    "provenance",
    "root_paths",
    "security",
    "source_chunk_ids",
    "source_record_ids",
    "tags",
    "vector_index_cids",
}


class VFSGraphRAGIndex:
    """Persistent local index for VFS GraphRAG schema records.

    Records are kept in memory for simple queries and rewritten atomically to
    per-record-family files on each upsert.  The storage surface is deliberately
    small and deterministic, which keeps it usable without GraphRAG, vector
    store, Arrow, or IPFS runtime dependencies.
    """

    _KIND_SCHEMAS: Dict[str, str] = {
        "objects": OBJECT_SCHEMA,
        "object": OBJECT_SCHEMA,
        "metadata": OBJECT_SCHEMA,
        "metadata_records": OBJECT_SCHEMA,
        "chunks": CHUNK_SCHEMA,
        "chunk": CHUNK_SCHEMA,
        "embeddings": EMBEDDING_SCHEMA,
        "embedding": EMBEDDING_SCHEMA,
        "embedding_metadata": EMBEDDING_SCHEMA,
        "entities": ENTITY_SCHEMA,
        "entity": ENTITY_SCHEMA,
        "graph_nodes": ENTITY_SCHEMA,
        "graph_node": ENTITY_SCHEMA,
        "relationships": RELATIONSHIP_SCHEMA,
        "relationship": RELATIONSHIP_SCHEMA,
        "graph_edges": RELATIONSHIP_SCHEMA,
        "graph_edge": RELATIONSHIP_SCHEMA,
        "snapshots": SNAPSHOT_SCHEMA,
        "snapshot": SNAPSHOT_SCHEMA,
        "checkpoints": CHECKPOINT_SCHEMA,
        "checkpoint": CHECKPOINT_SCHEMA,
    }

    _STORAGE_KINDS: Dict[str, str] = {
        OBJECT_SCHEMA: "objects",
        CHUNK_SCHEMA: "chunks",
        EMBEDDING_SCHEMA: "embeddings",
        ENTITY_SCHEMA: "entities",
        RELATIONSHIP_SCHEMA: "relationships",
        SNAPSHOT_SCHEMA: "snapshots",
        CHECKPOINT_SCHEMA: "checkpoints",
    }

    _ID_FIELDS: Dict[str, str] = {
        OBJECT_SCHEMA: "record_id",
        CHUNK_SCHEMA: "chunk_id",
        EMBEDDING_SCHEMA: "embedding_id",
        ENTITY_SCHEMA: "entity_id",
        RELATIONSHIP_SCHEMA: "relationship_id",
        SNAPSHOT_SCHEMA: "snapshot_id",
        CHECKPOINT_SCHEMA: "checkpoint_id",
    }

    def __init__(
        self,
        root_path: Union[str, Path],
        *,
        namespace: str = DEFAULT_NAMESPACE,
        storage_format: str = "jsonl",
    ) -> None:
        if storage_format not in {"jsonl", "parquet", "auto"}:
            raise ValueError("storage_format must be 'jsonl', 'parquet', or 'auto'")

        self.root_path = Path(root_path)
        self.namespace = namespace
        self.storage_format = self._resolve_storage_format(storage_format)
        self.root_path.mkdir(parents=True, exist_ok=True)
        self._records: Dict[str, Dict[str, SerializableRecord]] = {
            schema: {} for schema in self._STORAGE_KINDS
        }
        self.reload()

    @property
    def format(self) -> str:
        """Return the active on-disk format."""

        return self.storage_format

    def reload(self) -> None:
        """Reload all known record families from disk."""

        self._records = {schema: {} for schema in self._STORAGE_KINDS}
        for schema, kind in self._STORAGE_KINDS.items():
            for record in self._read_records(kind):
                self._records[schema][self._record_id(record)] = record

    def flush(self) -> None:
        """Rewrite all record families to disk."""

        for schema, kind in self._STORAGE_KINDS.items():
            self._write_records(kind, self._records[schema].values())

    def put_record(self, record: RecordInput) -> SerializableRecord:
        """Insert or replace a canonical schema record and persist it."""

        parsed = self._coerce_record(record)
        schema = parsed.to_dict()["schema"]
        if schema not in self._records:
            raise ValueError(f"Unsupported VFS GraphRAG index schema: {schema!r}")

        self._records[schema][self._record_id(parsed)] = parsed
        self._write_records(self._kind_for_schema(schema), self._records[schema].values())
        return parsed

    def put_records(self, records: Iterable[RecordInput]) -> List[SerializableRecord]:
        """Insert or replace records, grouped by kind to minimize disk writes."""

        changed: Dict[str, bool] = {}
        parsed_records = []
        for record in records:
            parsed = self._coerce_record(record)
            schema = parsed.to_dict()["schema"]
            if schema not in self._records:
                raise ValueError(f"Unsupported VFS GraphRAG index schema: {schema!r}")
            self._records[schema][self._record_id(parsed)] = parsed
            changed[schema] = True
            parsed_records.append(parsed)

        for schema in changed:
            self._write_records(self._kind_for_schema(schema), self._records[schema].values())
        return parsed_records

    def get_record(self, schema_or_kind: str, record_id: str) -> Optional[SerializableRecord]:
        """Return one record by schema/kind and deterministic id."""

        schema = self._schema_for(schema_or_kind)
        return self._records[schema].get(record_id)

    def query_records(self, schema_or_kind: str, **filters: Any) -> List[SerializableRecord]:
        """Return records whose top-level fields match every supplied filter."""

        schema = self._schema_for(schema_or_kind)
        records = list(self._records[schema].values())
        if not filters:
            return sorted(records, key=self._record_id)
        return sorted(
            (record for record in records if self._matches(record, filters)),
            key=self._record_id,
        )

    def delete_record(self, schema_or_kind: str, record_id: str) -> bool:
        """Delete a record by id.  Returns True when a record was removed."""

        schema = self._schema_for(schema_or_kind)
        removed = self._records[schema].pop(record_id, None)
        if removed is None:
            return False
        self._write_records(self._kind_for_schema(schema), self._records[schema].values())
        return True

    def stats(self) -> Dict[str, Any]:
        """Return record counts and storage metadata."""

        return {
            "namespace": self.namespace,
            "schema_version": SCHEMA_VERSION,
            "storage_format": self.storage_format,
            "root_path": str(self.root_path),
            "counts": {
                kind: len(self._records[schema])
                for schema, kind in self._STORAGE_KINDS.items()
            },
        }

    def upsert_object(self, record: RecordInput) -> VFSObjectRecord:
        return self._typed_put(record, VFSObjectRecord)

    add_object = upsert_object

    def get_object(self, record_id: str) -> Optional[VFSObjectRecord]:
        return self.get_record("objects", record_id)  # type: ignore[return-value]

    def query_objects(self, **filters: Any) -> List[VFSObjectRecord]:
        return self.query_records("objects", **filters)  # type: ignore[return-value]

    upsert_metadata = upsert_object
    add_metadata = upsert_object
    add_metadata_record = upsert_object
    get_metadata = get_object
    get_metadata_record = get_object
    query_metadata = query_objects
    query_metadata_records = query_objects

    def upsert_chunk(self, record: RecordInput) -> VFSChunkRecord:
        return self._typed_put(record, VFSChunkRecord)

    add_chunk = upsert_chunk

    def get_chunk(self, chunk_id: str) -> Optional[VFSChunkRecord]:
        return self.get_record("chunks", chunk_id)  # type: ignore[return-value]

    def query_chunks(self, **filters: Any) -> List[VFSChunkRecord]:
        return self.query_records("chunks", **filters)  # type: ignore[return-value]

    def upsert_embedding(self, record: RecordInput) -> VFSEmbeddingRecord:
        return self._typed_put(record, VFSEmbeddingRecord)

    add_embedding = upsert_embedding

    def get_embedding(self, embedding_id: str) -> Optional[VFSEmbeddingRecord]:
        return self.get_record("embeddings", embedding_id)  # type: ignore[return-value]

    def query_embeddings(self, **filters: Any) -> List[VFSEmbeddingRecord]:
        return self.query_records("embeddings", **filters)  # type: ignore[return-value]

    def upsert_entity(self, record: RecordInput) -> VFSEntityRecord:
        return self._typed_put(record, VFSEntityRecord)

    add_entity = upsert_entity
    add_graph_node = upsert_entity
    upsert_graph_node = upsert_entity

    def get_entity(self, entity_id: str) -> Optional[VFSEntityRecord]:
        return self.get_record("entities", entity_id)  # type: ignore[return-value]

    get_graph_node = get_entity

    def query_entities(self, **filters: Any) -> List[VFSEntityRecord]:
        return self.query_records("entities", **filters)  # type: ignore[return-value]

    query_graph_nodes = query_entities

    def upsert_relationship(self, record: RecordInput) -> VFSRelationshipRecord:
        return self._typed_put(record, VFSRelationshipRecord)

    add_relationship = upsert_relationship
    add_graph_edge = upsert_relationship
    upsert_graph_edge = upsert_relationship

    def get_relationship(self, relationship_id: str) -> Optional[VFSRelationshipRecord]:
        return self.get_record("relationships", relationship_id)  # type: ignore[return-value]

    get_graph_edge = get_relationship

    def query_relationships(self, **filters: Any) -> List[VFSRelationshipRecord]:
        return self.query_records("relationships", **filters)  # type: ignore[return-value]

    query_graph_edges = query_relationships

    def upsert_snapshot(self, record: RecordInput) -> VFSSnapshotRecord:
        return self._typed_put(record, VFSSnapshotRecord)

    add_snapshot = upsert_snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[VFSSnapshotRecord]:
        return self.get_record("snapshots", snapshot_id)  # type: ignore[return-value]

    def query_snapshots(self, **filters: Any) -> List[VFSSnapshotRecord]:
        return self.query_records("snapshots", **filters)  # type: ignore[return-value]

    def upsert_checkpoint(self, record: RecordInput) -> VFSCheckpointRecord:
        return self._typed_put(record, VFSCheckpointRecord)

    add_checkpoint = upsert_checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> Optional[VFSCheckpointRecord]:
        return self.get_record("checkpoints", checkpoint_id)  # type: ignore[return-value]

    def query_checkpoints(self, **filters: Any) -> List[VFSCheckpointRecord]:
        return self.query_records("checkpoints", **filters)  # type: ignore[return-value]

    def latest_checkpoint(
        self,
        *,
        namespace: Optional[str] = None,
        backend: Optional[str] = None,
        checkpoint_type: Optional[str] = None,
    ) -> Optional[VFSCheckpointRecord]:
        """Return the newest checkpoint matching optional cursor filters."""

        filters: Dict[str, Any] = {}
        if namespace is not None:
            filters["namespace"] = namespace
        if backend is not None:
            filters["backend"] = backend
        if checkpoint_type is not None:
            filters["checkpoint_type"] = checkpoint_type
        records = self.query_checkpoints(**filters)
        if not records:
            return None
        return max(records, key=lambda record: (record.created_at, record.checkpoint_id))

    def checkpoint(
        self,
        *,
        namespace: Optional[str] = None,
        backend: str = "ipfs",
        checkpoint_type: str = "journal",
        cursor: Optional[Mapping[str, Any]] = None,
        journal_entry_id: Optional[str] = None,
        journal_timestamp: Optional[str] = None,
        bucket_last_updated: Optional[str] = None,
        git_snapshot_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> VFSCheckpointRecord:
        """Create and persist a checkpoint record."""

        record = VFSCheckpointRecord(
            namespace=namespace or self.namespace,
            backend=backend,
            checkpoint_type=checkpoint_type,
            cursor=dict(cursor or {}),
            journal_entry_id=journal_entry_id,
            journal_timestamp=journal_timestamp,
            bucket_last_updated=bucket_last_updated,
            git_snapshot_id=git_snapshot_id,
            metadata_schema_version=SCHEMA_VERSION,
            metadata=dict(metadata or {}),
        )
        return self.upsert_checkpoint(record)

    def _typed_put(self, record: RecordInput, record_type: Type[T]) -> T:
        parsed = self._coerce_record(record, record_type)
        return self.put_record(parsed)  # type: ignore[return-value]

    def _coerce_record(
        self,
        record: RecordInput,
        expected_type: Optional[Type[T]] = None,
    ) -> SerializableRecord:
        if isinstance(record, SerializableRecord):
            parsed = record
        else:
            data = dict(record)
            if "schema" in data:
                parsed = record_from_dict(data)
            elif expected_type is not None:
                parsed = expected_type.from_dict(data)
            else:
                raise ValueError("Mapping records must include a schema unless using a typed upsert")
        if expected_type is not None and not isinstance(parsed, expected_type):
            raise TypeError(f"Expected {expected_type.__name__}, got {type(parsed).__name__}")
        return parsed

    def _schema_for(self, schema_or_kind: str) -> str:
        if schema_or_kind in self._KIND_SCHEMAS:
            return self._KIND_SCHEMAS[schema_or_kind]
        if schema_or_kind in self._records:
            return schema_or_kind
        raise ValueError(f"Unknown VFS GraphRAG record kind or schema: {schema_or_kind!r}")

    def _kind_for_schema(self, schema: str) -> str:
        try:
            return self._STORAGE_KINDS[schema]
        except KeyError as exc:
            raise ValueError(f"Unknown VFS GraphRAG schema: {schema!r}") from exc

    def _record_id(self, record: SerializableRecord) -> str:
        data = record.to_dict()
        schema = data["schema"]
        field = self._ID_FIELDS.get(schema)
        if field is None:
            raise ValueError(f"Unsupported VFS GraphRAG schema: {schema!r}")
        return str(data[field])

    def _matches(self, record: SerializableRecord, filters: Mapping[str, Any]) -> bool:
        data = record.to_dict()
        for field, expected in filters.items():
            actual = data.get(field)
            if callable(expected):
                if not expected(actual):
                    return False
            elif isinstance(expected, (set, tuple, list)) and not isinstance(expected, str):
                if isinstance(actual, list):
                    if not any(item in actual for item in expected):
                        return False
                elif actual not in expected:
                    return False
            elif isinstance(actual, list):
                if expected not in actual:
                    return False
            else:
                if actual != expected:
                    return False
        return True

    def _path_for_kind(self, kind: str) -> Path:
        suffix = "parquet" if self.storage_format == "parquet" else "jsonl"
        return self.root_path / f"{kind}.{suffix}"

    def _read_records(self, kind: str) -> List[SerializableRecord]:
        path = self._path_for_kind(kind)
        if not path.exists():
            legacy_jsonl = self.root_path / f"{kind}.jsonl"
            if self.storage_format == "parquet" and legacy_jsonl.exists():
                path = legacy_jsonl
            else:
                return []
        if path.suffix == ".parquet":
            return self._read_parquet(path)
        with path.open("r", encoding="utf-8") as handle:
            return [record_from_json(line) for line in handle if line.strip()]

    def _write_records(self, kind: str, records: Iterable[SerializableRecord]) -> None:
        path = self._path_for_kind(kind)
        ordered = sorted(records, key=self._record_id)
        if self.storage_format == "parquet":
            self._write_parquet(path, ordered)
            return
        lines = [record.to_json() for record in ordered]
        self._atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))

    def _atomic_write_text(self, path: Path, payload: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(path.parent),
            delete=False,
        ) as handle:
            handle.write(payload)
            temp_name = handle.name
        os.replace(temp_name, path)

    def _resolve_storage_format(self, requested: str) -> str:
        if requested == "jsonl":
            return "jsonl"
        if requested == "parquet":
            if not self._parquet_available():
                raise RuntimeError("Parquet storage requires pandas and a Parquet engine")
            return "parquet"
        return "parquet" if self._parquet_available() else "jsonl"

    def _parquet_available(self) -> bool:
        try:
            import pandas  # noqa: F401
            import pyarrow  # noqa: F401
        except Exception:
            return False
        return True

    def _write_parquet(self, path: Path, records: Sequence[SerializableRecord]) -> None:
        try:
            import pandas as pd
        except Exception as exc:
            raise RuntimeError("Parquet storage requires pandas and a Parquet engine") from exc

        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [record.to_arrow_dict() for record in records]
        dataframe = pd.DataFrame(rows)
        temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            dataframe.to_parquet(temp_path, index=False)
            os.replace(temp_path, path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _read_parquet(self, path: Path) -> List[SerializableRecord]:
        try:
            import pandas as pd
        except Exception as exc:
            raise RuntimeError("Parquet storage requires pandas and a Parquet engine") from exc

        dataframe = pd.read_parquet(path)
        records: List[SerializableRecord] = []
        for row in dataframe.to_dict(orient="records"):
            records.append(record_from_dict(self._inflate_arrow_row(row)))
        return records

    def _inflate_arrow_row(self, row: Mapping[str, Any]) -> Dict[str, Any]:
        inflated: Dict[str, Any] = {}
        for key, value in row.items():
            if hasattr(value, "item"):
                value = value.item()
            if key in _JSON_FIELDS and isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            if value != value:  # NaN without importing math/numpy.
                value = None
            inflated[key] = value
        return inflated


__all__ = ["VFSGraphRAGIndex"]
