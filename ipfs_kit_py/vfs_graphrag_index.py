"""Local storage for canonical VFS GraphRAG index records.

The index intentionally depends only on the schema module and the Python
standard library.  Optional Parquet support is enabled only when pandas and a
Parquet engine are already installed; JSONL remains the default durable format.
"""

from __future__ import annotations

import json
import os
import tempfile
import hashlib
import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Type, TypeVar, Union

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
    stable_id,
    record_from_dict,
    record_from_json,
)


RecordInput = Union[SerializableRecord, Mapping[str, Any]]
T = TypeVar("T", bound=SerializableRecord)
SymbolCandidate = Tuple[str, str]

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


class VFSGraphRAGDependencyError(ImportError):
    """Raised when an optional ipfs_datasets_py GraphRAG component is requested."""


@dataclass
class VFSGraphRAGAdapterConfig:
    """Configuration for dependency-gated ipfs_datasets_py adapter creation."""

    namespace: str = DEFAULT_NAMESPACE
    use_mocks: bool = True
    vector_store_type: str = "faiss"
    embedding_model_id: str = "mock-embedding"
    chunk_size: int = 1000
    chunk_overlap: int = 0
    component_kwargs: Dict[str, Mapping[str, Any]] = field(default_factory=dict)


def _import_optional_symbol(
    candidates: Sequence[SymbolCandidate],
    dependency_name: str,
) -> Any:
    errors: List[str] = []
    for module_name, symbol_name in candidates:
        try:
            module = importlib.import_module(module_name)
            return getattr(module, symbol_name)
        except Exception as exc:
            errors.append(f"{module_name}.{symbol_name}: {exc}")
    tried = ", ".join(f"{module}.{symbol}" for module, symbol in candidates)
    raise VFSGraphRAGDependencyError(
        f"{dependency_name} requires optional ipfs_datasets_py support. "
        f"Could not import any of: {tried}. Import errors: {'; '.join(errors)}"
    )


def _instantiate_optional(
    candidates: Sequence[SymbolCandidate],
    dependency_name: str,
    kwargs: Optional[Mapping[str, Any]] = None,
) -> Any:
    component = _import_optional_symbol(candidates, dependency_name)
    try:
        return component(**dict(kwargs or {}))
    except TypeError:
        if kwargs:
            raise
        return component()


def _get_value(item: Any, *names: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        for name in names:
            if name in item:
                return item[name]
        return default
    for name in names:
        if hasattr(item, name):
            return getattr(item, name)
    return default


def _call_first(component: Any, method_names: Sequence[str], *args: Any, **kwargs: Any) -> Any:
    for name in method_names:
        method = getattr(component, name, None)
        if callable(method):
            return method(*args, **kwargs)
    raise AttributeError(f"{type(component).__name__} does not expose any of: {', '.join(method_names)}")


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _vector_checksum(vector: Any) -> Optional[str]:
    if vector is None:
        return None
    payload = json.dumps(vector, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class MockUnifiedGraphRAGProcessor:
    """Small deterministic processor for tests and dependency-free operation."""

    def process(self, query: str, **kwargs: Any) -> Dict[str, Any]:
        return {
            "answer": query,
            "results": [],
            "metadata": {"mock": True, **kwargs},
        }


class MockEmbeddingProvider:
    """Deterministic embedding provider used by default tests."""

    def __init__(self, dimension: int = 3) -> None:
        self.dimension = dimension

    def embed(self, texts: Sequence[str], **_: Any) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vectors.append([digest[i] / 255.0 for i in range(self.dimension)])
        return vectors


class MockChunker:
    """Fixed-size text chunker with optional character overlap."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 0) -> None:
        self.chunk_size = max(1, int(chunk_size))
        self.chunk_overlap = max(0, int(chunk_overlap))

    def chunk(self, text: str, **_: Any) -> List[Dict[str, Any]]:
        if not text:
            return []
        step = max(1, self.chunk_size - min(self.chunk_overlap, self.chunk_size - 1))
        chunks = []
        for index, start in enumerate(range(0, len(text), step)):
            end = min(len(text), start + self.chunk_size)
            chunks.append({"text": text[start:end], "chunk_index": index, "text_start": start, "text_end": end})
            if end == len(text):
                break
        return chunks


class MockVectorStore:
    """In-memory vector store compatible with the adapter call surface."""

    def __init__(self) -> None:
        self.vectors: Dict[str, Any] = {}

    def add(self, vectors: Sequence[Any], ids: Optional[Sequence[str]] = None, **_: Any) -> List[str]:
        stored_ids = list(ids or [stable_id("mockvec", index, vector) for index, vector in enumerate(vectors)])
        for vector_id, vector in zip(stored_ids, vectors):
            self.vectors[vector_id] = vector
        return stored_ids

    def search(self, query_vector: Any, top_k: int = 10, **_: Any) -> List[Dict[str, Any]]:
        return [
            {"id": vector_id, "score": 1.0 if vector == query_vector else 0.0}
            for vector_id, vector in list(self.vectors.items())[:top_k]
        ]


class MockKnowledgeGraphExtractor:
    """Simple extractor that treats capitalized words as entities."""

    def extract(self, text: str, **_: Any) -> Dict[str, Any]:
        entities = []
        seen = set()
        for token in text.replace(".", " ").replace(",", " ").split():
            name = token.strip()
            if name[:1].isupper() and name not in seen:
                seen.add(name)
                entities.append({"name": name, "entity_type": "term", "confidence": 1.0})
        relationships = []
        for left, right in zip(entities, entities[1:]):
            relationships.append(
                {"subject": left["name"], "predicate": "near", "object": right["name"], "confidence": 1.0}
            )
        return {"entities": entities, "relationships": relationships}


class MockQueryOptimizer:
    """Dependency-free query optimizer used by tests."""

    def optimize(self, query: str, **_: Any) -> Dict[str, Any]:
        return {"query": query.strip(), "optimized_query": query.strip(), "strategy": "mock"}


class VFSGraphRAGProcessorAdapter:
    """Adapter for UnifiedGraphRAGProcessor-compatible components."""

    def __init__(self, processor: Any) -> None:
        self.processor = processor

    @classmethod
    def from_ipfs_datasets(cls, **kwargs: Any) -> "VFSGraphRAGProcessorAdapter":
        processor = _instantiate_optional(
            [
                ("ipfs_datasets_py.graphrag_processor", "UnifiedGraphRAGProcessor"),
                ("ipfs_datasets_py.unified_graphrag", "UnifiedGraphRAGProcessor"),
                ("ipfs_datasets_py", "UnifiedGraphRAGProcessor"),
            ],
            "UnifiedGraphRAGProcessor",
            kwargs,
        )
        return cls(processor)

    def query(self, query: str, **kwargs: Any) -> Dict[str, Any]:
        result = _call_first(self.processor, ("process", "query", "search", "run"), query, **kwargs)
        return self.normalize_result(result)

    def normalize_result(self, result: Any) -> Dict[str, Any]:
        answer = _get_value(result, "answer", "response", "text", default=None)
        raw_results = _as_list(_get_value(result, "results", "documents", "chunks", default=[]))
        return {
            "answer": answer,
            "results": [self._normalize_hit(hit) for hit in raw_results],
            "metadata": dict(_get_value(result, "metadata", default={}) or {}),
        }

    def _normalize_hit(self, hit: Any) -> Dict[str, Any]:
        return {
            "record_id": _get_value(hit, "record_id", "parent_record_id"),
            "chunk_id": _get_value(hit, "chunk_id", "id"),
            "text": _get_value(hit, "text", "content"),
            "score": _get_value(hit, "score", "similarity", default=None),
            "metadata": dict(_get_value(hit, "metadata", default={}) or {}),
        }


class VFSChunkingAdapter:
    """Adapter that normalizes backend chunker output into VFSChunkRecord."""

    def __init__(self, chunker: Any, *, namespace: str = DEFAULT_NAMESPACE) -> None:
        self.chunker = chunker
        self.namespace = namespace

    @classmethod
    def from_ipfs_datasets(cls, *, namespace: str = DEFAULT_NAMESPACE, **kwargs: Any) -> "VFSChunkingAdapter":
        chunker = _instantiate_optional(
            [
                ("ipfs_datasets_py.unixfs_integration", "FixedSizeChunker"),
                ("ipfs_datasets_py.chunking", "Chunker"),
                ("ipfs_datasets_py", "FixedSizeChunker"),
            ],
            "chunking",
            kwargs,
        )
        return cls(chunker, namespace=namespace)

    def chunk_text(
        self,
        text: str,
        *,
        parent_record_id: str,
        path: str = "",
        content_id: Optional[str] = None,
        **kwargs: Any,
    ) -> List[VFSChunkRecord]:
        raw_chunks = _call_first(self.chunker, ("chunk", "chunk_text", "split_text", "split"), text, **kwargs)
        return [
            self._normalize_chunk(
                chunk,
                index=index,
                parent_record_id=parent_record_id,
                path=path,
                content_id=content_id,
            )
            for index, chunk in enumerate(_as_list(raw_chunks))
        ]

    def _normalize_chunk(
        self,
        chunk: Any,
        *,
        index: int,
        parent_record_id: str,
        path: str,
        content_id: Optional[str],
    ) -> VFSChunkRecord:
        text = chunk if isinstance(chunk, str) else _get_value(chunk, "text", "content", default="")
        return VFSChunkRecord(
            parent_record_id=parent_record_id,
            namespace=self.namespace,
            path=path,
            content_id=content_id,
            chunk_index=int(_get_value(chunk, "chunk_index", "index", default=index)),
            byte_start=_get_value(chunk, "byte_start", "start_byte"),
            byte_end=_get_value(chunk, "byte_end", "end_byte"),
            text_start=_get_value(chunk, "text_start", "start"),
            text_end=_get_value(chunk, "text_end", "end"),
            text=str(text),
            extraction_method=str(_get_value(chunk, "extraction_method", "method", default="ipfs_datasets_py")),
            language=_get_value(chunk, "language", "lang"),
            metadata=dict(_get_value(chunk, "metadata", default={}) or {}),
        )


class VFSEmbeddingAdapter:
    """Adapter that calls embedding providers and emits embedding metadata records."""

    def __init__(self, provider: Any, *, model_id: str = "unknown", vector_store_id: Optional[str] = None) -> None:
        self.provider = provider
        self.model_id = model_id
        self.vector_store_id = vector_store_id

    @classmethod
    def from_ipfs_datasets(cls, *, model_id: str = "unknown", **kwargs: Any) -> "VFSEmbeddingAdapter":
        provider = _instantiate_optional(
            [
                ("ipfs_datasets_py.ipfs_embeddings_py", "IPFSEmbeddings"),
                ("ipfs_datasets_py.ipfs_embeddings_py", "MultiModelEmbeddingGenerator"),
                ("ipfs_datasets_py.embeddings", "IPFSEmbeddings"),
            ],
            "embeddings",
            kwargs,
        )
        return cls(provider, model_id=model_id)

    def embed_chunks(
        self,
        chunks: Sequence[VFSChunkRecord],
        *,
        parent_record_id: Optional[str] = None,
        vector_store_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[List[VFSEmbeddingRecord], List[Any]]:
        texts = [chunk.text or "" for chunk in chunks]
        raw_embeddings = _call_first(
            self.provider,
            ("embed", "embed_documents", "generate_embeddings", "encode"),
            texts,
            **kwargs,
        )
        vectors = _as_list(_get_value(raw_embeddings, "embeddings", "vectors", default=raw_embeddings))
        records: List[VFSEmbeddingRecord] = []
        for chunk, vector in zip(chunks, vectors):
            dimension = len(vector) if hasattr(vector, "__len__") else int(_get_value(vector, "dimension", default=0))
            records.append(
                VFSEmbeddingRecord(
                    chunk_id=chunk.chunk_id,
                    parent_record_id=parent_record_id or chunk.parent_record_id,
                    model_id=self.model_id,
                    dimension=dimension,
                    vector_store_id=vector_store_id or self.vector_store_id,
                    embedding_checksum=_vector_checksum(vector),
                    metadata={"source": "ipfs_datasets_py"},
                )
            )
        return records, vectors


class VFSVectorStoreAdapter:
    """Adapter for optional FAISS, Qdrant, Elasticsearch, or custom vector stores."""

    _VECTOR_STORE_CANDIDATES: Dict[str, Sequence[SymbolCandidate]] = {
        "faiss": [
            ("ipfs_datasets_py.vector_stores", "FAISSVectorStore"),
            ("ipfs_datasets_py.ipfs_knn_index", "IPFSKnnIndex"),
        ],
        "qdrant": [("ipfs_datasets_py.vector_stores", "QdrantVectorStore")],
        "elasticsearch": [("ipfs_datasets_py.vector_stores", "ElasticsearchVectorStore")],
        "ipld": [("ipfs_datasets_py.ipld.vector_store", "IPLDVectorStore")],
    }

    def __init__(self, store: Any, *, store_id: str = "vector-store") -> None:
        self.store = store
        self.store_id = store_id

    @classmethod
    def from_ipfs_datasets(cls, store_type: str = "faiss", **kwargs: Any) -> "VFSVectorStoreAdapter":
        normalized = store_type.lower()
        candidates = cls._VECTOR_STORE_CANDIDATES.get(normalized)
        if candidates is None:
            raise ValueError(f"Unknown vector store type: {store_type!r}")
        store = _instantiate_optional(candidates, f"{store_type} vector store", kwargs)
        return cls(store, store_id=normalized)

    def add_embeddings(
        self,
        embeddings: Sequence[VFSEmbeddingRecord],
        vectors: Sequence[Any],
        **kwargs: Any,
    ) -> List[VFSEmbeddingRecord]:
        ids = [record.embedding_id for record in embeddings]
        raw_ids = _call_first(self.store, ("add", "add_vectors", "upsert", "add_embeddings"), vectors, ids=ids, **kwargs)
        stored_ids = [str(value) for value in _as_list(raw_ids)] or ids
        updated = []
        for record, vector_id in zip(embeddings, stored_ids):
            updated.append(
                VFSEmbeddingRecord(
                    embedding_id=record.embedding_id,
                    chunk_id=record.chunk_id,
                    parent_record_id=record.parent_record_id,
                    model_id=record.model_id,
                    dimension=record.dimension,
                    vector_store_id=record.vector_store_id or self.store_id,
                    embedding_vector_id=vector_id,
                    embedding_checksum=record.embedding_checksum,
                    created_at=record.created_at,
                    metadata=dict(record.metadata),
                )
            )
        return updated

    def search(self, query_vector: Any, *, top_k: int = 10, **kwargs: Any) -> List[Dict[str, Any]]:
        raw_results = _call_first(self.store, ("search", "query", "similarity_search"), query_vector, top_k=top_k, **kwargs)
        return [
            {
                "embedding_vector_id": _get_value(item, "embedding_vector_id", "id", "vector_id"),
                "chunk_id": _get_value(item, "chunk_id"),
                "score": _get_value(item, "score", "similarity", "distance"),
                "metadata": dict(_get_value(item, "metadata", default={}) or {}),
            }
            for item in _as_list(raw_results)
        ]


class VFSKnowledgeGraphAdapter:
    """Adapter that normalizes extractor output into entity and relationship records."""

    def __init__(self, extractor: Any) -> None:
        self.extractor = extractor

    @classmethod
    def from_ipfs_datasets(cls, **kwargs: Any) -> "VFSKnowledgeGraphAdapter":
        extractor = _instantiate_optional(
            [
                ("ipfs_datasets_py.knowledge_graph_extraction", "KnowledgeGraphExtractor"),
                ("ipfs_datasets_py", "KnowledgeGraphExtractor"),
            ],
            "knowledge graph extraction",
            kwargs,
        )
        return cls(extractor)

    def extract(
        self,
        text: str,
        *,
        source_record_ids: Optional[Sequence[str]] = None,
        source_chunk_ids: Optional[Sequence[str]] = None,
        **kwargs: Any,
    ) -> Tuple[List[VFSEntityRecord], List[VFSRelationshipRecord]]:
        raw_graph = _call_first(self.extractor, ("extract", "extract_graph", "extract_knowledge_graph"), text, **kwargs)
        entities = [
            self._normalize_entity(entity, source_record_ids=source_record_ids, source_chunk_ids=source_chunk_ids)
            for entity in _as_list(_get_value(raw_graph, "entities", "nodes", default=[]))
        ]
        relationships = [
            self._normalize_relationship(rel, source_record_ids=source_record_ids, source_chunk_ids=source_chunk_ids)
            for rel in _as_list(_get_value(raw_graph, "relationships", "edges", default=[]))
        ]
        return entities, relationships

    def _normalize_entity(
        self,
        entity: Any,
        *,
        source_record_ids: Optional[Sequence[str]],
        source_chunk_ids: Optional[Sequence[str]],
    ) -> VFSEntityRecord:
        return VFSEntityRecord(
            name=str(_get_value(entity, "name", "text", "label", default="")),
            entity_type=str(_get_value(entity, "entity_type", "type", default="entity")),
            aliases=list(_get_value(entity, "aliases", default=[]) or []),
            source_record_ids=list(source_record_ids or _get_value(entity, "source_record_ids", default=[]) or []),
            source_chunk_ids=list(source_chunk_ids or _get_value(entity, "source_chunk_ids", default=[]) or []),
            confidence=_get_value(entity, "confidence", "score"),
            provenance=dict(_get_value(entity, "provenance", default={}) or {}),
            metadata=dict(_get_value(entity, "metadata", default={}) or {}),
        )

    def _normalize_relationship(
        self,
        relationship: Any,
        *,
        source_record_ids: Optional[Sequence[str]],
        source_chunk_ids: Optional[Sequence[str]],
    ) -> VFSRelationshipRecord:
        return VFSRelationshipRecord(
            subject_id=str(_get_value(relationship, "subject_id", "subject", "source", default="")),
            predicate=str(_get_value(relationship, "predicate", "relationship_type", "type", default="related_to")),
            object_id=str(_get_value(relationship, "object_id", "object", "target", default="")),
            relationship_type=str(_get_value(relationship, "relationship_type", "type", default="semantic")),
            source_record_ids=list(source_record_ids or _get_value(relationship, "source_record_ids", default=[]) or []),
            source_chunk_ids=list(source_chunk_ids or _get_value(relationship, "source_chunk_ids", default=[]) or []),
            confidence=_get_value(relationship, "confidence", "score"),
            provenance=dict(_get_value(relationship, "provenance", default={}) or {}),
            metadata=dict(_get_value(relationship, "metadata", default={}) or {}),
        )


class VFSQueryOptimizerAdapter:
    """Adapter for ipfs_datasets_py GraphRAG query optimizers."""

    def __init__(self, optimizer: Any) -> None:
        self.optimizer = optimizer

    @classmethod
    def from_ipfs_datasets(cls, **kwargs: Any) -> "VFSQueryOptimizerAdapter":
        optimizer = _instantiate_optional(
            [
                ("ipfs_datasets_py.rag_query_optimizer", "UnifiedGraphRAGQueryOptimizer"),
                ("ipfs_datasets_py.rag_query_optimizer", "GraphRAGQueryOptimizer"),
                ("ipfs_datasets_py.query_optimizer", "HybridQueryOptimizer"),
            ],
            "query optimizer",
            kwargs,
        )
        return cls(optimizer)

    def optimize(self, query: str, **kwargs: Any) -> Dict[str, Any]:
        result = _call_first(self.optimizer, ("optimize", "rewrite", "plan_query"), query, **kwargs)
        return {
            "query": query,
            "optimized_query": _get_value(result, "optimized_query", "query", "rewritten_query", default=query),
            "strategy": _get_value(result, "strategy", "plan", default=None),
            "metadata": dict(_get_value(result, "metadata", default={}) or {}),
        }


@dataclass
class VFSGraphRAGAdapters:
    """Bundle of GraphRAG-related adapters for VFS indexing workflows."""

    processor: VFSGraphRAGProcessorAdapter
    embeddings: VFSEmbeddingAdapter
    chunking: VFSChunkingAdapter
    vector_store: VFSVectorStoreAdapter
    knowledge_graph: VFSKnowledgeGraphAdapter
    query_optimizer: VFSQueryOptimizerAdapter

    @classmethod
    def create(cls, config: Optional[VFSGraphRAGAdapterConfig] = None) -> "VFSGraphRAGAdapters":
        cfg = config or VFSGraphRAGAdapterConfig()
        if cfg.use_mocks:
            return cls(
                processor=VFSGraphRAGProcessorAdapter(MockUnifiedGraphRAGProcessor()),
                embeddings=VFSEmbeddingAdapter(MockEmbeddingProvider(), model_id=cfg.embedding_model_id),
                chunking=VFSChunkingAdapter(
                    MockChunker(chunk_size=cfg.chunk_size, chunk_overlap=cfg.chunk_overlap),
                    namespace=cfg.namespace,
                ),
                vector_store=VFSVectorStoreAdapter(MockVectorStore(), store_id=f"{cfg.vector_store_type}:mock"),
                knowledge_graph=VFSKnowledgeGraphAdapter(MockKnowledgeGraphExtractor()),
                query_optimizer=VFSQueryOptimizerAdapter(MockQueryOptimizer()),
            )
        kwargs = cfg.component_kwargs
        return cls(
            processor=VFSGraphRAGProcessorAdapter.from_ipfs_datasets(**dict(kwargs.get("processor", {}))),
            embeddings=VFSEmbeddingAdapter.from_ipfs_datasets(
                model_id=cfg.embedding_model_id,
                **dict(kwargs.get("embeddings", {})),
            ),
            chunking=VFSChunkingAdapter.from_ipfs_datasets(
                namespace=cfg.namespace,
                **dict(kwargs.get("chunking", {})),
            ),
            vector_store=VFSVectorStoreAdapter.from_ipfs_datasets(
                cfg.vector_store_type,
                **dict(kwargs.get("vector_store", {})),
            ),
            knowledge_graph=VFSKnowledgeGraphAdapter.from_ipfs_datasets(**dict(kwargs.get("knowledge_graph", {}))),
            query_optimizer=VFSQueryOptimizerAdapter.from_ipfs_datasets(**dict(kwargs.get("query_optimizer", {}))),
        )


def create_vfs_graphrag_adapters(
    config: Optional[VFSGraphRAGAdapterConfig] = None,
) -> VFSGraphRAGAdapters:
    """Create a complete adapter bundle, using mock adapters by default."""

    return VFSGraphRAGAdapters.create(config)


__all__ = [
    "MockChunker",
    "MockEmbeddingProvider",
    "MockKnowledgeGraphExtractor",
    "MockQueryOptimizer",
    "MockUnifiedGraphRAGProcessor",
    "MockVectorStore",
    "VFSChunkingAdapter",
    "VFSEmbeddingAdapter",
    "VFSGraphRAGAdapterConfig",
    "VFSGraphRAGAdapters",
    "VFSGraphRAGDependencyError",
    "VFSGraphRAGIndex",
    "VFSGraphRAGProcessorAdapter",
    "VFSKnowledgeGraphAdapter",
    "VFSQueryOptimizerAdapter",
    "VFSVectorStoreAdapter",
    "create_vfs_graphrag_adapters",
]
