"""Durable GraphRAG service with rehydration and reproducible projections.

Content/history events are the authority.  The graph generation is explicitly
a replaceable projection: it can be stale, missing, or corrupt without losing
data, and it is always reconstructed from closed JSON records rather than
executed or deserialized as code.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from .contracts import (
    GraphRAGContent,
    GraphRAGContentState,
    GraphRAGContractError,
    GraphRAGEmbedding,
    GraphRAGGeneration,
    GraphRAGHistoryEntry,
    GraphRAGHistoryOperation,
    GraphRAGIndexManifest,
    GraphRAGIndexMismatchError,
    GraphRAGRelation,
    canonical_json_bytes,
    content_identity,
)
from .projections import GraphProjection, IndexGeneration
from .storage import (
    GraphRAGStorageError,
    SafeGraphRAGStorage,
)


LEDGER_EVENT_SCHEMA: Final[str] = "ipfs_kit_py/graphrag/record-event@1"
LEDGER_POINTER_SCHEMA: Final[str] = "ipfs_kit_py/graphrag/record-pointer@1"
LEDGER_VERSION: Final[int] = 1
_PRIVATE_DIR_MODE: Final[int] = 0o700
_PRIVATE_FILE_MODE: Final[int] = 0o600
_MAX_EVENT_BYTES: Final[int] = 1_048_576


class GraphRAGServiceError(GraphRAGContractError):
    """Base error for a GraphRAG service operation."""


class GraphRAGLedgerError(GraphRAGServiceError):
    """The source-of-truth ledger is malformed or unsafe."""


class GraphRAGVersionError(GraphRAGServiceError):
    """A requested content/version transition is not append-only."""


class GraphRAGProjectionError(GraphRAGServiceError):
    """A projection could not be safely constructed or published."""


@dataclass(frozen=True)
class _LedgerEvent:
    sequence: int
    previous_event_id: str
    event_id: str
    content: GraphRAGContent
    relations: tuple[GraphRAGRelation, ...]
    embeddings: tuple[GraphRAGEmbedding, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "schema": LEDGER_EVENT_SCHEMA,
            "ledger_version": LEDGER_VERSION,
            "sequence": self.sequence,
            "previous_event_id": self.previous_event_id,
            "content": self.content.to_record(),
            "relations": [item.to_record() for item in self.relations],
            "embeddings": [item.to_record() for item in self.embeddings],
        }

    def record(self) -> dict[str, Any]:
        payload = self.payload()
        return {**payload, "event_id": content_identity(payload)}


@dataclass(frozen=True)
class _LedgerState:
    events: tuple[_LedgerEvent, ...]
    versions: Mapping[str, tuple[GraphRAGContent, ...]]
    current: Mapping[str, GraphRAGContent]
    relations: Mapping[str, GraphRAGRelation]
    embeddings: Mapping[str, GraphRAGEmbedding]
    history: tuple[GraphRAGHistoryEntry, ...]

    @property
    def event_id(self) -> str:
        return self.events[-1].event_id if self.events else "empty-ledger"


class GraphRAGService:
    """Append records first, then publish an atomic, disposable projection.

    ``manifest`` pins all projection identities.  It must remain compatible
    across restarts; callers deliberately get a fail-closed error on model or
    source drift instead of a seemingly successful mixed index.
    """

    def __init__(self, root: str | os.PathLike[str], manifest: GraphRAGIndexManifest) -> None:
        if not isinstance(manifest, GraphRAGIndexManifest):
            raise GraphRAGServiceError("manifest must be GraphRAGIndexManifest")
        self.root = Path(root).expanduser().absolute()
        self.manifest = manifest
        self._owner_uid = os.geteuid()
        self._ensure_dir(self.root)
        self._ensure_dir(self.records_dir)
        self._ensure_dir(self.events_dir)
        self._ensure_dir(self.staging_dir)
        self._projection_storage = SafeGraphRAGStorage(self.root / "projections")
        self._index_generation: IndexGeneration | None = None

    @classmethod
    def open(cls, root: str | os.PathLike[str], manifest: GraphRAGIndexManifest) -> "GraphRAGService":
        """Open the authoritative ledger and rehydrate a safe projection."""

        service = cls(root, manifest)
        service.rehydrate()
        return service

    @property
    def records_dir(self) -> Path:
        return self.root / "records"

    @property
    def events_dir(self) -> Path:
        return self.records_dir / "events"

    @property
    def staging_dir(self) -> Path:
        return self.records_dir / ".staging"

    @property
    def current_path(self) -> Path:
        return self.records_dir / "CURRENT.json"

    @property
    def index_generation(self) -> IndexGeneration | None:
        return self._index_generation

    @property
    def projection(self) -> GraphProjection | None:
        return None if self._index_generation is None else self._index_generation.projection

    def _ensure_dir(self, path: Path) -> None:
        try:
            path.mkdir(mode=_PRIVATE_DIR_MODE, parents=True, exist_ok=False)
        except FileExistsError:
            pass
        except OSError as exc:
            raise GraphRAGLedgerError(f"cannot create ledger directory {path}") from exc
        try:
            info = os.lstat(path)
        except OSError as exc:
            raise GraphRAGLedgerError(f"cannot stat ledger directory {path}") from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or info.st_uid != self._owner_uid:
            raise GraphRAGLedgerError(f"ledger directory is unsafe: {path}")
        if stat.S_IMODE(info.st_mode) != _PRIVATE_DIR_MODE:
            raise GraphRAGLedgerError(f"ledger directory must have mode 0700: {path}")

    def _read_file(self, path: Path, maximum: int) -> bytes:
        self._ensure_dir(path.parent)
        try:
            before = os.lstat(path)
        except OSError as exc:
            raise GraphRAGLedgerError(f"cannot stat ledger file {path}") from exc
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode) or before.st_uid != self._owner_uid:
            raise GraphRAGLedgerError(f"ledger file is unsafe: {path}")
        if stat.S_IMODE(before.st_mode) != _PRIVATE_FILE_MODE or before.st_nlink != 1 or before.st_size > maximum:
            raise GraphRAGLedgerError(f"ledger file has unsafe mode, links, or size: {path}")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags)
        except OSError as exc:
            raise GraphRAGLedgerError(f"cannot safely open ledger file {path}") from exc
        try:
            after = os.fstat(fd)
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino) or after.st_size > maximum:
                raise GraphRAGLedgerError("ledger file changed while being opened")
            data = b""
            while len(data) < after.st_size:
                piece = os.read(fd, min(65536, after.st_size - len(data)))
                if not piece:
                    raise GraphRAGLedgerError("ledger file ended while being read")
                data += piece
            if os.read(fd, 1):
                raise GraphRAGLedgerError("ledger file grew while being read")
            return data
        finally:
            os.close(fd)

    @staticmethod
    def _decode_canonical(data: bytes, name: str) -> Mapping[str, Any]:
        def reject_constant(value: str) -> None:
            raise GraphRAGLedgerError(f"{name} includes non-finite JSON constant {value}")

        def no_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            output: dict[str, Any] = {}
            for key, value in pairs:
                if key in output:
                    raise GraphRAGLedgerError(f"{name} includes a duplicate JSON key")
                output[key] = value
            return output

        try:
            value = json.loads(data.decode("utf-8"), object_pairs_hook=no_duplicate, parse_constant=reject_constant)
        except (UnicodeDecodeError, json.JSONDecodeError, GraphRAGLedgerError) as exc:
            raise GraphRAGLedgerError(f"{name} is not valid JSON") from exc
        if not isinstance(value, Mapping) or canonical_json_bytes(value) != data:
            raise GraphRAGLedgerError(f"{name} is not a canonical JSON object")
        return value

    @staticmethod
    def _fsync_dir(path: Path) -> None:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _write_new(self, path: Path, data: bytes) -> None:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0), _PRIVATE_FILE_MODE)
        try:
            os.fchmod(fd, _PRIVATE_FILE_MODE)
            written = 0
            while written < len(data):
                written += os.write(fd, data[written:])
            os.fsync(fd)
        finally:
            os.close(fd)

    def _event_path(self, sequence: int) -> Path:
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise GraphRAGLedgerError("event sequence must be positive")
        return self.events_dir / f"{sequence:020d}.json"

    def _load_event(self, sequence: int) -> _LedgerEvent:
        raw = self._decode_canonical(self._read_file(self._event_path(sequence), _MAX_EVENT_BYTES), "ledger event")
        required = {"schema", "ledger_version", "sequence", "previous_event_id", "event_id", "content", "relations", "embeddings"}
        if set(raw) != required or raw.get("schema") != LEDGER_EVENT_SCHEMA or raw.get("ledger_version") != LEDGER_VERSION or raw.get("sequence") != sequence:
            raise GraphRAGLedgerError("ledger event has an unsupported schema or field set")
        if not isinstance(raw["previous_event_id"], str) or not isinstance(raw["event_id"], str):
            raise GraphRAGLedgerError("ledger event identities are invalid")
        if (
            not isinstance(raw["content"], Mapping)
            or not isinstance(raw["relations"], list)
            or not isinstance(raw["embeddings"], list)
        ):
            raise GraphRAGLedgerError("ledger event contract fields have invalid JSON types")
        try:
            event = _LedgerEvent(
                sequence,
                raw["previous_event_id"],
                raw["event_id"],
                GraphRAGContent.from_dict(raw["content"]),
                tuple(GraphRAGRelation.from_dict(item) for item in raw["relations"]),
                tuple(GraphRAGEmbedding.from_dict(item) for item in raw["embeddings"]),
            )
        except (GraphRAGContractError, TypeError, AttributeError) as exc:
            raise GraphRAGLedgerError("ledger event has invalid contract records") from exc
        if event.record()["event_id"] != event.event_id:
            raise GraphRAGLedgerError("ledger event identity is not canonical")
        return event

    def _load_events(self) -> tuple[_LedgerEvent, ...]:
        # Path.exists() follows a symlink and reports False for a dangling
        # one.  Treat either form as an unsafe ledger rather than silently
        # accepting it as an empty source of truth.
        if not os.path.lexists(self.current_path):
            return ()
        pointer = self._decode_canonical(self._read_file(self.current_path, 4096), "ledger pointer")
        required = {"schema", "ledger_version", "sequence", "event_id", "sha256"}
        if set(pointer) != required or pointer.get("schema") != LEDGER_POINTER_SCHEMA or pointer.get("ledger_version") != LEDGER_VERSION:
            raise GraphRAGLedgerError("ledger pointer has an unsupported schema or field set")
        sequence = pointer.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise GraphRAGLedgerError("ledger pointer sequence is invalid")
        events = tuple(self._load_event(number) for number in range(1, sequence + 1))
        last = events[-1]
        digest = hashlib.sha256(canonical_json_bytes(last.record())).hexdigest()
        if pointer.get("event_id") != last.event_id or pointer.get("sha256") != digest:
            raise GraphRAGLedgerError("ledger pointer does not bind the final event")
        previous = ""
        for event in events:
            if event.previous_event_id != previous:
                raise GraphRAGLedgerError("ledger event chain is discontinuous")
            previous = event.event_id
        return events

    def _append_event(self, content: GraphRAGContent, relations: Sequence[GraphRAGRelation], embeddings: Sequence[GraphRAGEmbedding]) -> _LedgerEvent:
        state = self._state(self._load_events())
        self._validate_transition(state, content, relations, embeddings)
        sequence = len(state.events) + 1
        draft = _LedgerEvent(sequence, state.event_id if state.events else "", "", content, tuple(relations), tuple(embeddings))
        event = _LedgerEvent(sequence, draft.previous_event_id, content_identity(draft.payload()), content, tuple(relations), tuple(embeddings))
        event_data = canonical_json_bytes(event.record())
        if len(event_data) > _MAX_EVENT_BYTES:
            raise GraphRAGLedgerError("ledger event exceeds its byte bound")
        destination = self._event_path(sequence)
        temporary = self.staging_dir / f"event-{secrets.token_hex(24)}.json"
        try:
            self._write_new(temporary, event_data)
            os.link(temporary, destination, follow_symlinks=False)
            temporary.unlink()
            temporary = None
            self._fsync_dir(self.events_dir)
        except FileExistsError as exc:
            raise GraphRAGVersionError("concurrent ledger writer advanced the event sequence") from exc
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
        pointer = {
            "schema": LEDGER_POINTER_SCHEMA,
            "ledger_version": LEDGER_VERSION,
            "sequence": sequence,
            "event_id": event.event_id,
            "sha256": hashlib.sha256(event_data).hexdigest(),
        }
        temporary_pointer = self.staging_dir / f"current-{secrets.token_hex(24)}.json"
        try:
            self._write_new(temporary_pointer, canonical_json_bytes(pointer))
            os.replace(temporary_pointer, self.current_path)
            self._fsync_dir(self.records_dir)
        finally:
            try:
                temporary_pointer.unlink()
            except FileNotFoundError:
                pass
        return event

    def _validate_transition(self, state: _LedgerState, content: GraphRAGContent, relations: Sequence[GraphRAGRelation], embeddings: Sequence[GraphRAGEmbedding]) -> None:
        if not isinstance(content, GraphRAGContent):
            raise GraphRAGVersionError("content must be GraphRAGContent")
        if content.provenance.source_id != self.manifest.source_id or content.provenance.source_version != self.manifest.source_version:
            raise GraphRAGIndexMismatchError("content provenance differs from the service manifest")
        if not all(isinstance(item, GraphRAGRelation) for item in relations) or not all(isinstance(item, GraphRAGEmbedding) for item in embeddings):
            raise GraphRAGVersionError("relations and embeddings must contain GraphRAG contracts")
        previous = state.current.get(content.document_id)
        known_versions = state.versions.get(content.document_id, ())
        if any(item.version_id == content.version_id for item in known_versions):
            raise GraphRAGVersionError("a document version is immutable and cannot be reused")
        if previous is None:
            if content.state is not GraphRAGContentState.ACTIVE:
                raise GraphRAGVersionError("the first document record must be active")
        elif previous.state is GraphRAGContentState.TOMBSTONED:
            raise GraphRAGVersionError("a tombstoned document cannot be resurrected")
        elif content.state is GraphRAGContentState.TOMBSTONED:
            if content.tombstone_of != previous.version_id:
                raise GraphRAGVersionError("tombstone must name the immediately replaced version")
            if relations or embeddings:
                raise GraphRAGVersionError("a tombstone cannot introduce relations or embeddings")
        elif content.tombstone_of:
            raise GraphRAGVersionError("active replacement cannot name a tombstone target")
        relation_ids: set[str] = set()
        for relation in relations:
            if relation.relation_id in relation_ids or relation.source_document_id != content.document_id or relation.version_id != content.version_id:
                raise GraphRAGVersionError("relations must be unique and owned by the new content version")
            target = state.current.get(relation.target_document_id)
            if target is None or target.state is not GraphRAGContentState.ACTIVE:
                raise GraphRAGVersionError("relations can only target a live admitted document")
            if relation.provenance.source_id != self.manifest.source_id or relation.provenance.source_version != self.manifest.source_version:
                raise GraphRAGIndexMismatchError("relation provenance differs from service manifest")
            existing_relation = state.relations.get(relation.relation_id)
            if (
                existing_relation is not None
                and existing_relation.source_document_id != content.document_id
            ):
                raise GraphRAGVersionError(
                    "relation IDs cannot replace another document's live relation"
                )
            relation_ids.add(relation.relation_id)
        embedding_ids: set[str] = set()
        for embedding in embeddings:
            self.manifest.assert_compatible(embedding)
            if embedding.embedding_id in embedding_ids or embedding.document_id != content.document_id or embedding.source_cid != content.provenance.source_cid:
                raise GraphRAGVersionError("embeddings must be unique and bind the new content provenance")
            existing_embedding = state.embeddings.get(embedding.embedding_id)
            if (
                existing_embedding is not None
                and existing_embedding.document_id != content.document_id
            ):
                raise GraphRAGVersionError(
                    "embedding IDs cannot replace another document's live embedding"
                )
            embedding_ids.add(embedding.embedding_id)

    def _state(self, events: Sequence[_LedgerEvent]) -> _LedgerState:
        versions: dict[str, list[GraphRAGContent]] = {}
        current: dict[str, GraphRAGContent] = {}
        relations: dict[str, GraphRAGRelation] = {}
        embeddings: dict[str, GraphRAGEmbedding] = {}
        history: list[GraphRAGHistoryEntry] = []
        for event in events:
            content = event.content
            # Events were individually checked before publication; repeat the
            # transition validation on rehydration so disk input is never trusted.
            self._validate_transition(
                _LedgerState(tuple(events[:event.sequence - 1]), {key: tuple(value) for key, value in versions.items()}, current, relations, embeddings, tuple(history)),
                content, event.relations, event.embeddings,
            )
            prior = current.get(content.document_id)
            operation = (GraphRAGHistoryOperation.ADDED if prior is None else
                         GraphRAGHistoryOperation.TOMBSTONED if content.state is GraphRAGContentState.TOMBSTONED else
                         GraphRAGHistoryOperation.UPDATED)
            history.append(GraphRAGHistoryEntry(
                f"history-{event.sequence}", content.document_id, content.version_id,
                "" if prior is None else prior.version_id, operation, content.content_id,
            ))
            versions.setdefault(content.document_id, []).append(content)
            current[content.document_id] = content
            # Relations/embeddings are replacement views owned by their source.
            for relation_id, relation in tuple(relations.items()):
                if relation.source_document_id == content.document_id or (content.state is GraphRAGContentState.TOMBSTONED and relation.target_document_id == content.document_id):
                    del relations[relation_id]
            for embedding_id, embedding in tuple(embeddings.items()):
                if embedding.document_id == content.document_id:
                    del embeddings[embedding_id]
            if content.state is GraphRAGContentState.ACTIVE:
                relations.update({relation.relation_id: relation for relation in event.relations})
                embeddings.update({embedding.embedding_id: embedding for embedding in event.embeddings})
        return _LedgerState(tuple(events), {key: tuple(value) for key, value in versions.items()}, dict(current), dict(relations), dict(embeddings), tuple(history))

    def _build_projection(self, state: _LedgerState) -> GraphProjection:
        nodes = tuple(content for _, content in sorted(state.current.items()) if content.state is GraphRAGContentState.ACTIVE)
        return GraphProjection(nodes, tuple(state.relations.values()), state.versions, state.history, state.event_id)

    def _generation_from_state(self, state: _LedgerState, projection: GraphProjection, generation_id: str) -> GraphRAGGeneration:
        manifest = GraphRAGIndexManifest(
            generation_id, self.manifest.index_id, self.manifest.model_id, self.manifest.tokenizer_id,
            self.manifest.dimension, self.manifest.metric, self.manifest.source_id, self.manifest.source_version,
            self.manifest.schema_ids, self.manifest.capability_state,
        )
        # Include the current tombstone record for each deleted document so its
        # history remains self-contained, while GraphProjection keeps it out of
        # the live node/edge view.
        contents = tuple(content for _, content in sorted(state.current.items()))
        return GraphRAGGeneration(manifest, contents, tuple(state.relations.values()), tuple(state.embeddings.values()), state.history)

    def rebuild(self, *, before_publish: Callable[[], None] | None = None) -> IndexGeneration:
        """Rebuild solely from ledger JSON; no payload or provider is executed."""

        state = self._state(self._load_events())
        projection = self._build_projection(state)
        if before_publish is not None:
            if not callable(before_publish):
                raise GraphRAGProjectionError("before_publish must be callable")
            before_publish()
        sequence = len(state.events)
        # Random publication identity prevents an interrupted/repeated rebuild
        # from ever overwriting an immutable safe-storage generation.
        generation_id = f"projection-{sequence}-{secrets.token_hex(12)}"
        generation = self._generation_from_state(state, projection, generation_id)
        try:
            self._projection_storage.publish_generation(generation)
        except GraphRAGStorageError as exc:
            raise GraphRAGProjectionError("projection generation could not be published") from exc
        self._index_generation = IndexGeneration(generation, projection, state.event_id)
        return self._index_generation

    clean_rebuild = rebuild

    def rehydrate(self) -> IndexGeneration:
        """Validate source records and produce a fresh projection after restart."""

        return self.rebuild()

    def apply(self, content: GraphRAGContent, *, relations: Sequence[GraphRAGRelation] = (), embeddings: Sequence[GraphRAGEmbedding] = (), before_publish: Callable[[], None] | None = None) -> IndexGeneration:
        """Append one immutable content transition and refresh its projection."""

        self._append_event(content, relations, embeddings)
        return self.rebuild(before_publish=before_publish)

    add_content = apply
    upsert_content = apply
    update_content = apply

    def delete_content(self, content: GraphRAGContent, *, before_publish: Callable[[], None] | None = None) -> IndexGeneration:
        if not isinstance(content, GraphRAGContent) or content.state is not GraphRAGContentState.TOMBSTONED:
            raise GraphRAGVersionError("delete_content requires a tombstoned GraphRAGContent")
        return self.apply(content, before_publish=before_publish)

    tombstone_content = delete_content

    def version_history(self, document_id: str) -> tuple[GraphRAGContent, ...]:
        if not isinstance(document_id, str):
            raise GraphRAGVersionError("document_id must be a string")
        return self._state(self._load_events()).versions.get(document_id, ())

    def current_content(self, document_id: str) -> GraphRAGContent | None:
        if not isinstance(document_id, str):
            raise GraphRAGVersionError("document_id must be a string")
        return self._state(self._load_events()).current.get(document_id)


# Explicit versioned public aliases for registry/adapters.
GraphRAGService_V1 = GraphRAGService
GraphProjection_V1 = GraphProjection
IndexGeneration_V1 = IndexGeneration
