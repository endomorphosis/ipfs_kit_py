"""Deterministic, inert projections of durable GraphRAG records.

This module deliberately has no graph, RDF, or vector-provider dependency.
It produces small immutable value objects which are sufficient to prove the
identity of those views.  Provider-backed indexes may consume these records,
but never become the authority for content or history.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

from .contracts import (
    GraphRAGContent,
    GraphRAGContentState,
    GraphRAGGeneration,
    GraphRAGHistoryEntry,
    GraphRAGRelation,
    canonical_json_bytes,
    content_identity,
)


PROJECTION_SCHEMA: Final[str] = "ipfs_kit_py/graphrag/projection@1"


class GraphProjectionError(ValueError):
    """Durable records cannot form a coherent graph projection."""


@dataclass(frozen=True)
class GraphProjection:
    """A deterministic graph/RDF-shaped view of a record ledger.

    ``versions`` includes every admitted content version, including the final
    tombstone.  ``nodes`` and ``edges`` contain only the live graph, which is
    what prevents a deleted document or one of its incident relations from
    being accidentally reintroduced by an incremental projection.
    """

    nodes: tuple[GraphRAGContent, ...]
    edges: tuple[GraphRAGRelation, ...]
    versions: Mapping[str, tuple[GraphRAGContent, ...]]
    history: tuple[GraphRAGHistoryEntry, ...]
    source_event_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_event_id, str) or not self.source_event_id:
            raise GraphProjectionError("source_event_id must be a non-empty identity")
        if not isinstance(self.versions, Mapping):
            raise GraphProjectionError("versions must be a mapping")
        if not all(isinstance(item, GraphRAGContent) for item in self.nodes):
            raise GraphProjectionError("nodes must contain GraphRAGContent values")
        if not all(isinstance(item, GraphRAGRelation) for item in self.edges):
            raise GraphProjectionError("edges must contain GraphRAGRelation values")
        if not all(isinstance(item, GraphRAGHistoryEntry) for item in self.history):
            raise GraphProjectionError("history must contain GraphRAGHistoryEntry values")
        nodes = tuple(sorted(self.nodes, key=lambda value: value.document_id))
        edges = tuple(sorted(self.edges, key=lambda value: value.relation_id))
        history = tuple(sorted(self.history, key=lambda value: value.history_id))
        if len({item.document_id for item in nodes}) != len(nodes):
            raise GraphProjectionError("live graph nodes must have unique document IDs")
        if len({item.relation_id for item in edges}) != len(edges):
            raise GraphProjectionError("live graph edges must have unique relation IDs")
        if any(item.state is not GraphRAGContentState.ACTIVE for item in nodes):
            raise GraphProjectionError("live graph nodes must be active")
        node_ids = {item.document_id for item in nodes}
        if any(edge.source_document_id not in node_ids or edge.target_document_id not in node_ids for edge in edges):
            raise GraphProjectionError("live graph edges must only reference live nodes")
        normalized_versions: dict[str, tuple[GraphRAGContent, ...]] = {}
        for document_id, values in self.versions.items():
            if not isinstance(document_id, str) or not values:
                raise GraphProjectionError("version histories must be non-empty")
            records = tuple(values)
            if any(not isinstance(value, GraphRAGContent) or value.document_id != document_id for value in records):
                raise GraphProjectionError("version history contains an invalid content record")
            if len({value.version_id for value in records}) != len(records):
                raise GraphProjectionError("version IDs cannot repeat within a document")
            normalized_versions[document_id] = records
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "edges", edges)
        object.__setattr__(self, "history", history)
        object.__setattr__(self, "versions", MappingProxyType(dict(sorted(normalized_versions.items()))))

    def identity_payload(self) -> dict[str, object]:
        """Return the stable identity projection, excluding publication IDs."""

        return {
            "schema": PROJECTION_SCHEMA,
            "nodes": [item.to_record() for item in self.nodes],
            "edges": [item.to_record() for item in self.edges],
            "versions": {
                document_id: [item.to_record() for item in values]
                for document_id, values in self.versions.items()
            },
            "history": [item.to_record() for item in self.history],
            "source_event_id": self.source_event_id,
        }

    @property
    def identity(self) -> str:
        return content_identity(self.identity_payload())

    @property
    def cid(self) -> str:
        return self.identity

    @property
    def rdf_triples(self) -> tuple[tuple[str, str, str], ...]:
        """A provider-neutral RDF-like edge view with a deterministic order."""

        return tuple((edge.source_document_id, edge.relation_type, edge.target_document_id) for edge in self.edges)


@dataclass(frozen=True)
class IndexGeneration:
    """Links a safely published generation to its authoritative projection."""

    generation: GraphRAGGeneration
    projection: GraphProjection
    source_event_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.generation, GraphRAGGeneration) or not isinstance(self.projection, GraphProjection):
            raise GraphProjectionError("generation and projection have invalid types")
        if self.source_event_id != self.projection.source_event_id:
            raise GraphProjectionError("generation source identity differs from projection")

    @property
    def identity(self) -> str:
        # Publication generation IDs intentionally do not affect equivalence.
        return self.projection.identity

    @property
    def generation_id(self) -> str:
        return self.generation.manifest.generation_id


def projection_bytes(projection: GraphProjection) -> bytes:
    """Canonical bytes useful to projection adapters without serialization code."""

    if not isinstance(projection, GraphProjection):
        raise GraphProjectionError("projection must be GraphProjection")
    return canonical_json_bytes(projection.identity_payload())
