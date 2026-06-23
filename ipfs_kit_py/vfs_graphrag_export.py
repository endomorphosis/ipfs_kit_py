"""Portable export/import bundles for VFS GraphRAG indexes.

The bundle format is intentionally dependency-free and directory based.  Each
record family is written as deterministic JSONL plus a manifest that records
schema versions, counts, byte sizes, and SHA-256 checksums for every artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .vfs_graphrag_index import VFSGraphRAGIndex
from .vfs_graphrag_schema import (
    CHECKPOINT_SCHEMA,
    CHUNK_SCHEMA,
    EMBEDDING_SCHEMA,
    ENTITY_SCHEMA,
    EXPORT_MANIFEST_SCHEMA,
    OBJECT_SCHEMA,
    RELATIONSHIP_SCHEMA,
    SCHEMA_VERSION,
    SNAPSHOT_SCHEMA,
    SerializableRecord,
    VFSExportManifest,
    record_from_dict,
    stable_id,
    utc_now_iso,
)


JSONValue = Any
IndexTarget = Union[VFSGraphRAGIndex, str, Path]

IMPORT_MODES = {"metadata-only", "metadata-plus-indexes", "full-snapshot"}


@dataclass(frozen=True)
class BundleArtifact:
    """Manifest entry for a single exported file."""

    path: str
    schema: str
    count: int
    checksum: str
    bytes: int
    required: bool = True

    def to_dict(self) -> Dict[str, JSONValue]:
        return {
            "path": self.path,
            "schema": self.schema,
            "count": self.count,
            "checksum": self.checksum,
            "bytes": self.bytes,
            "required": self.required,
        }


class VFSGraphRAGBundleError(ValueError):
    """Raised when a VFS GraphRAG bundle is missing or fails validation."""


class VFSGraphRAGExportBundle:
    """Export/import helper for portable VFS GraphRAG metadata bundles."""

    _RECORD_ARTIFACTS: Tuple[Tuple[str, str, str], ...] = (
        ("metadata", "metadata.jsonl", OBJECT_SCHEMA),
        ("chunks", "chunks.jsonl", CHUNK_SCHEMA),
        ("embeddings", "embeddings.jsonl", EMBEDDING_SCHEMA),
        ("graph_nodes", "graph.nodes.jsonl", ENTITY_SCHEMA),
        ("graph_edges", "graph.edges.jsonl", RELATIONSHIP_SCHEMA),
        ("snapshots", "snapshots.jsonl", SNAPSHOT_SCHEMA),
        ("checkpoints", "checkpoints.jsonl", CHECKPOINT_SCHEMA),
    )

    _METADATA_ONLY_KEYS = {"metadata", "checkpoints"}
    _INDEX_KEYS = {
        "metadata",
        "chunks",
        "embeddings",
        "graph_nodes",
        "graph_edges",
        "snapshots",
        "checkpoints",
    }
    _FULL_KEYS = _INDEX_KEYS | {"filesystem", "journal"}

    def __init__(self, index: VFSGraphRAGIndex) -> None:
        self.index = index

    def export_index(
        self,
        output_path: Union[str, Path],
        *,
        filesystem_map: Optional[Mapping[str, Any]] = None,
        filesystem_maps: Optional[Mapping[str, Any]] = None,
        journal_entries: Optional[Iterable[Mapping[str, Any]]] = None,
        include_filesystem: bool = True,
        include_journal: bool = True,
        export_format: str = "jsonl",
        format: str = "directory",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write a directory bundle and return the manifest dictionary."""

        if format != "directory":
            raise ValueError("Only directory bundle format is currently supported")
        if export_format != "jsonl":
            raise ValueError("Only jsonl export_format is currently supported")
        if filesystem_map is not None and filesystem_maps is not None:
            raise ValueError("Use either filesystem_map or filesystem_maps, not both")
        bundle_path = Path(output_path)
        bundle_path.mkdir(parents=True, exist_ok=True)

        artifacts: Dict[str, Dict[str, JSONValue]] = {}
        counts: Dict[str, int] = {}
        for key, filename, schema in self._RECORD_ARTIFACTS:
            records = self._records_for_key(key)
            payload = self._jsonl_payload(record.to_dict() for record in records)
            artifact = self._write_artifact(bundle_path, filename, payload, schema=schema, count=len(records))
            artifacts[key] = artifact.to_dict()
            counts[key] = len(records)

        if include_filesystem:
            fs_payload = self._canonical_json(filesystem_map or filesystem_maps or self._default_filesystem_map())
            artifacts["filesystem"] = self._write_artifact(
                bundle_path,
                "filesystem.json",
                fs_payload,
                schema="ipfs_kit_py.vfs.graphrag.filesystem_map.v1",
                count=1,
            ).to_dict()

        if include_journal:
            journal_rows = [dict(entry) for entry in (journal_entries or [])]
            journal_payload = self._jsonl_payload(journal_rows)
            artifacts["journal"] = self._write_artifact(
                bundle_path,
                "journal.jsonl",
                journal_payload,
                schema="ipfs_kit_py.vfs.graphrag.journal_slice.v1",
                count=len(journal_rows),
                required=False,
            ).to_dict()

        manifest = self._build_manifest(
            artifacts=artifacts,
            counts=counts,
            export_format=export_format,
            metadata=metadata,
        )
        self._atomic_write_text(bundle_path / "manifest.json", self._canonical_json(manifest))
        return manifest

    @classmethod
    def import_index(
        cls,
        input_path: Union[str, Path],
        target: IndexTarget,
        *,
        mode: str = "metadata-plus-indexes",
        verify_checksums: bool = True,
        namespace: Optional[str] = None,
        storage_format: str = "jsonl",
    ) -> Dict[str, Any]:
        """Import a bundle into an index instance or index root path."""

        if mode not in IMPORT_MODES:
            raise ValueError(f"mode must be one of: {', '.join(sorted(IMPORT_MODES))}")
        bundle_path = cls._bundle_path(input_path)
        manifest = cls.load_manifest(bundle_path, verify_checksums=verify_checksums)
        index = cls._target_index(target, namespace=namespace or manifest.get("namespace"), storage_format=storage_format)

        allowed = cls._allowed_keys_for_mode(mode)
        imported_counts: Dict[str, int] = {}
        for key, _filename, _schema in cls._RECORD_ARTIFACTS:
            if key not in allowed or key not in manifest.get("artifacts", {}):
                continue
            records = cls._read_record_artifact(bundle_path, manifest["artifacts"][key])
            index.put_records(records)
            imported_counts[key] = len(records)

        filesystem_map = None
        journal_entries: List[Dict[str, Any]] = []
        if mode == "full-snapshot":
            if "filesystem" in manifest.get("artifacts", {}):
                filesystem_map = cls._read_json_artifact(bundle_path, manifest["artifacts"]["filesystem"])
            if "journal" in manifest.get("artifacts", {}):
                journal_entries = cls._read_jsonl_artifact(bundle_path, manifest["artifacts"]["journal"])

        return {
            "success": True,
            "mode": mode,
            "manifest": manifest,
            "index": index,
            "imported_counts": imported_counts,
            "filesystem_map": filesystem_map,
            "journal_entries": journal_entries,
        }

    @classmethod
    def load_manifest(
        cls,
        input_path: Union[str, Path],
        *,
        verify_checksums: bool = True,
    ) -> Dict[str, Any]:
        """Load and optionally validate a bundle manifest."""

        bundle_path = cls._bundle_path(input_path)
        manifest_path = bundle_path / "manifest.json"
        if not manifest_path.exists():
            raise VFSGraphRAGBundleError(f"Bundle manifest not found: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != EXPORT_MANIFEST_SCHEMA:
            raise VFSGraphRAGBundleError(f"Unsupported bundle manifest schema: {manifest.get('schema')!r}")
        if verify_checksums:
            cls.verify_manifest(bundle_path, manifest)
        return manifest

    @classmethod
    def verify_manifest(cls, input_path: Union[str, Path], manifest: Optional[Mapping[str, Any]] = None) -> bool:
        """Validate every artifact checksum and bundle checksum."""

        bundle_path = cls._bundle_path(input_path)
        manifest_data = dict(manifest or cls.load_manifest(bundle_path, verify_checksums=False))
        artifact_checksums: Dict[str, str] = {}
        for key, artifact in manifest_data.get("artifacts", {}).items():
            path = bundle_path / str(artifact["path"])
            if not path.exists():
                raise VFSGraphRAGBundleError(f"Bundle artifact missing: {path}")
            checksum = cls._file_checksum(path)
            expected = str(artifact.get("checksum"))
            if checksum != expected:
                raise VFSGraphRAGBundleError(
                    f"Checksum mismatch for {artifact['path']}: expected {expected}, got {checksum}"
                )
            artifact_checksums[str(key)] = checksum

        bundle_checksum = cls._bundle_checksum(artifact_checksums)
        expected_bundle_checksum = manifest_data.get("bundle_checksum")
        if expected_bundle_checksum and bundle_checksum != expected_bundle_checksum:
            raise VFSGraphRAGBundleError(
                f"Bundle checksum mismatch: expected {expected_bundle_checksum}, got {bundle_checksum}"
            )
        return True

    def _records_for_key(self, key: str) -> List[SerializableRecord]:
        if key == "metadata":
            return list(self.index.query_objects())
        if key == "chunks":
            return list(self.index.query_chunks())
        if key == "embeddings":
            return list(self.index.query_embeddings())
        if key == "graph_nodes":
            return list(self.index.query_graph_nodes())
        if key == "graph_edges":
            return list(self.index.query_graph_edges())
        if key == "snapshots":
            return list(self.index.query_snapshots())
        if key == "checkpoints":
            return list(self.index.query_checkpoints())
        raise KeyError(key)

    def _default_filesystem_map(self) -> Dict[str, Any]:
        objects = self.index.query_objects()
        path_map = {
            record.normalized_path or record.path: {
                "record_id": record.record_id,
                "content_id": record.content_id,
                "backend": record.backend,
                "protocol": record.protocol,
                "namespace": record.namespace,
            }
            for record in objects
        }
        return {
            "namespace": self.index.namespace,
            "path_map": path_map,
            "backends": sorted({record.backend for record in objects}),
            "protocols": sorted({record.protocol for record in objects}),
        }

    def _build_manifest(
        self,
        *,
        artifacts: Mapping[str, Mapping[str, Any]],
        counts: Mapping[str, int],
        export_format: str,
        metadata: Optional[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        artifact_checksums = {
            key: str(artifact["checksum"])
            for key, artifact in sorted(artifacts.items())
        }
        content_ids = sorted(
            str(record.content_id)
            for record in self.index.query_objects()
            if record.content_id not in (None, "")
        )
        manifest_record = VFSExportManifest(
            namespace=self.index.namespace,
            export_format=export_format,
            object_count=int(counts.get("metadata", 0)),
            chunk_count=int(counts.get("chunks", 0)),
            embedding_count=int(counts.get("embeddings", 0)),
            entity_count=int(counts.get("graph_nodes", 0)),
            relationship_count=int(counts.get("graph_edges", 0)),
            snapshot_count=int(counts.get("snapshots", 0)),
            checkpoint_count=int(counts.get("checkpoints", 0)),
            files={key: str(artifact["path"]) for key, artifact in sorted(artifacts.items())},
            content_cids=content_ids,
            metadata=dict(metadata or {}),
        )
        manifest = manifest_record.to_dict()
        manifest["created_at"] = utc_now_iso()
        manifest["artifacts"] = {key: dict(value) for key, value in sorted(artifacts.items())}
        manifest["counts"] = dict(counts)
        manifest["capabilities"] = {
            "metadata_only": True,
            "metadata_plus_indexes": True,
            "full_snapshot": "filesystem" in artifacts,
            "checksum_algorithm": "sha256",
        }
        manifest["bundle_checksum"] = self._bundle_checksum(artifact_checksums)
        manifest["manifest_id"] = stable_id(
            "vfsmanifest",
            manifest["namespace"],
            manifest["schema_version"],
            manifest["export_format"],
            manifest["bundle_checksum"],
        )
        return manifest

    @staticmethod
    def _allowed_keys_for_mode(mode: str) -> set:
        if mode == "metadata-only":
            return set(VFSGraphRAGExportBundle._METADATA_ONLY_KEYS)
        if mode == "metadata-plus-indexes":
            return set(VFSGraphRAGExportBundle._INDEX_KEYS)
        return set(VFSGraphRAGExportBundle._FULL_KEYS)

    @staticmethod
    def _bundle_path(input_path: Union[str, Path]) -> Path:
        path = Path(input_path)
        return path.parent if path.name == "manifest.json" else path

    @staticmethod
    def _target_index(
        target: IndexTarget,
        *,
        namespace: Optional[str],
        storage_format: str,
    ) -> VFSGraphRAGIndex:
        if isinstance(target, VFSGraphRAGIndex):
            return target
        return VFSGraphRAGIndex(target, namespace=namespace or "default", storage_format=storage_format)

    @staticmethod
    def _read_record_artifact(bundle_path: Path, artifact: Mapping[str, Any]) -> List[SerializableRecord]:
        rows = VFSGraphRAGExportBundle._read_jsonl_artifact(bundle_path, artifact)
        return [record_from_dict(row) for row in rows]

    @staticmethod
    def _read_json_artifact(bundle_path: Path, artifact: Mapping[str, Any]) -> Dict[str, Any]:
        path = bundle_path / str(artifact["path"])
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _read_jsonl_artifact(bundle_path: Path, artifact: Mapping[str, Any]) -> List[Dict[str, Any]]:
        path = bundle_path / str(artifact["path"])
        rows = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    @staticmethod
    def _write_artifact(
        bundle_path: Path,
        filename: str,
        payload: str,
        *,
        schema: str,
        count: int,
        required: bool = True,
    ) -> BundleArtifact:
        path = bundle_path / filename
        VFSGraphRAGExportBundle._atomic_write_text(path, payload)
        return BundleArtifact(
            path=filename,
            schema=schema,
            count=count,
            checksum=VFSGraphRAGExportBundle._file_checksum(path),
            bytes=path.stat().st_size,
            required=required,
        )

    @staticmethod
    def _jsonl_payload(rows: Iterable[Mapping[str, Any]]) -> str:
        lines = [
            json.dumps(dict(row), sort_keys=True, separators=(",", ":"), default=str)
            for row in rows
        ]
        return "\n".join(lines) + ("\n" if lines else "")

    @staticmethod
    def _canonical_json(value: Mapping[str, Any]) -> str:
        return json.dumps(dict(value), sort_keys=True, indent=2, default=str) + "\n"

    @staticmethod
    def _file_checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"

    @staticmethod
    def _bundle_checksum(artifact_checksums: Mapping[str, str]) -> str:
        payload = json.dumps(dict(sorted(artifact_checksums.items())), sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _atomic_write_text(path: Path, payload: str) -> None:
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


def export_index(index: VFSGraphRAGIndex, output_path: Union[str, Path], **options: Any) -> Dict[str, Any]:
    """Export ``index`` to a portable VFS GraphRAG bundle."""

    return VFSGraphRAGExportBundle(index).export_index(output_path, **options)


def import_index(input_path: Union[str, Path], target: IndexTarget, **options: Any) -> Dict[str, Any]:
    """Import a portable VFS GraphRAG bundle into ``target``."""

    return VFSGraphRAGExportBundle.import_index(input_path, target, **options)


def load_manifest(input_path: Union[str, Path], **options: Any) -> Dict[str, Any]:
    """Load a VFS GraphRAG export manifest."""

    return VFSGraphRAGExportBundle.load_manifest(input_path, **options)


def verify_manifest(input_path: Union[str, Path], manifest: Optional[Mapping[str, Any]] = None) -> bool:
    """Validate artifact checksums for a VFS GraphRAG export bundle."""

    return VFSGraphRAGExportBundle.verify_manifest(input_path, manifest)


__all__ = [
    "BundleArtifact",
    "IMPORT_MODES",
    "VFSGraphRAGBundleError",
    "VFSGraphRAGExportBundle",
    "export_index",
    "import_index",
    "load_manifest",
    "verify_manifest",
]
