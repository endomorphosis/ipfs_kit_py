"""Focused runtime-readiness coverage for the inert GraphRAG boundary."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


def _load_modules():
    root = Path(__file__).resolve().parents[3] / "ipfs_kit_py" / "graphrag"
    package_name = "ipfs_kit_py.graphrag_contract_boundary"
    package = types.ModuleType(package_name)
    package.__path__ = [str(root)]
    sys.modules[package_name] = package
    modules = []
    for name in ("contracts", "storage"):
        qualified = f"{package_name}.{name}"
        spec = importlib.util.spec_from_file_location(qualified, root / f"{name}.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        spec.loader.exec_module(module)
        modules.append(module)
    return modules


contracts, storage = _load_modules()


def _generation(generation_id="generation-1"):
    provenance = contracts.GraphRAGProvenance("source-1", "version-1", "source-1")
    content = contracts.GraphRAGContent("document-1", "version-1", "payload-1", provenance)
    manifest = contracts.GraphRAGIndexManifest(
        generation_id, "index-1", "model-1", "tokenizer-1", 3,
        contracts.GraphRAGMetric.COSINE, "source-1", "version-1",
    )
    embedding = contracts.GraphRAGEmbedding(
        "embedding-1", "document-1", "model-1", "tokenizer-1", 3,
        contracts.GraphRAGMetric.COSINE, "vector-1", "index-1", "source-1",
    )
    relation = contracts.GraphRAGRelation("relation-1", "document-1", "document-2", "references", "version-1", provenance)
    # Relations must point to members of this generation, so add its target.
    target = contracts.GraphRAGContent("document-2", "version-1", "payload-2", provenance)
    return contracts.GraphRAGGeneration(manifest, (content, target), (relation,), (embedding,))


class GraphRAGContractsAndStorageTests(unittest.TestCase):
    def test_contracts_are_unique_and_model_dimension_index_mismatches_reject(self):
        generation = _generation()
        schemas = {contracts.GraphRAGRelation.SCHEMA, contracts.GraphRAGHistoryEntry.SCHEMA, contracts.GraphRAGQueryResult.SCHEMA}
        self.assertEqual(3, len(schemas))
        bad = contracts.GraphRAGEmbedding("embedding-2", "document-1", "other-model", "tokenizer-1", 3, contracts.GraphRAGMetric.COSINE, "vector-2", "index-1", "source-1")
        with self.assertRaises(contracts.GraphRAGModelMismatchError):
            generation.manifest.assert_compatible(bad)
        bad = contracts.GraphRAGEmbedding("embedding-2", "document-1", "model-1", "tokenizer-1", 4, contracts.GraphRAGMetric.COSINE, "vector-2", "index-1", "source-1")
        with self.assertRaises(contracts.GraphRAGDimensionMismatchError):
            generation.manifest.assert_compatible(bad)
        bad = contracts.GraphRAGEmbedding("embedding-2", "document-1", "model-1", "tokenizer-1", 3, contracts.GraphRAGMetric.COSINE, "vector-2", "other-index", "source-1")
        with self.assertRaises(contracts.GraphRAGIndexMismatchError):
            generation.manifest.assert_compatible(bad)

    def test_json_generation_round_trip_is_atomic_and_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            store = storage.SafeGraphRAGStorage(directory)
            generation = _generation()
            receipt = store.publish_generation(generation)
            self.assertEqual("generation-1", receipt.generation_id)
            self.assertEqual(generation, store.load_generation())
            with self.assertRaises(storage.GraphRAGGenerationExistsError):
                store.publish_generation(generation)

    def test_symlink_mode_size_and_schema_attacks_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            store = storage.SafeGraphRAGStorage(directory)
            generation = _generation()
            store.publish_generation(generation)
            target = store._generation_path("generation-1")
            target.unlink()
            os.symlink("/etc/passwd", target)
            with self.assertRaises(storage.GraphRAGStorageSecurityError):
                store.load_generation("generation-1")
        with tempfile.TemporaryDirectory() as directory:
            store = storage.SafeGraphRAGStorage(directory)
            generation = _generation()
            store.publish_generation(generation)
            target = store._generation_path("generation-1")
            os.chmod(target, 0o644)
            with self.assertRaises(storage.GraphRAGStorageSecurityError):
                store.load_generation("generation-1")
        with tempfile.TemporaryDirectory() as directory:
            store = storage.SafeGraphRAGStorage(directory)
            generation = _generation()
            target = store._generation_path("generation-1")
            target.write_text(json.dumps({"schema": "not-a-generation"}), encoding="utf-8")
            os.chmod(target, 0o600)
            with self.assertRaises(storage.GraphRAGStorageFormatError):
                store.load_generation("generation-1")
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o755)
            with self.assertRaises(storage.GraphRAGStorageSecurityError):
                storage.SafeGraphRAGStorage(directory)
        with tempfile.NamedTemporaryFile() as file:
            with self.assertRaises(storage.GraphRAGStorageSecurityError):
                storage.SafeGraphRAGStorage(file.name)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(storage.GraphRAGStorageSecurityError):
                storage.SafeGraphRAGStorage(directory, owner_uid=os.geteuid() + 1)
        with tempfile.TemporaryDirectory() as directory:
            store = storage.SafeGraphRAGStorage(directory, max_generation_bytes=100)
            target = store._generation_path("generation-1")
            target.write_bytes(b"x" * 101)
            os.chmod(target, 0o600)
            with self.assertRaises(storage.GraphRAGStorageFormatError):
                store.load_generation("generation-1")

    def test_imports_are_inert(self):
        source = (Path(contracts.__file__).read_text(encoding="utf-8") + Path(storage.__file__).read_text(encoding="utf-8")).lower()
        for forbidden in ("sentence_transformers", "sklearn", "spacy", "pickle.load", "pickle.dump"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
