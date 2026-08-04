"""Durability checks for the canonical GraphRAG service."""

from __future__ import annotations

import importlib.util
import tempfile
import types
import unittest
from pathlib import Path
import sys


def _load_modules():
    root = Path(__file__).resolve().parents[3] / "ipfs_kit_py" / "graphrag"
    package_name = "ipfs_kit_py.graphrag_durability_boundary"
    package = types.ModuleType(package_name)
    package.__path__ = [str(root)]
    sys.modules[package_name] = package
    loaded = {}
    for name in ("contracts", "storage", "projections", "service"):
        qualified = f"{package_name}.{name}"
        spec = importlib.util.spec_from_file_location(qualified, root / f"{name}.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        spec.loader.exec_module(module)
        loaded[name] = module
    return loaded


modules = _load_modules()
contracts = modules["contracts"]
service_module = modules["service"]
storage = modules["storage"]


def _manifest(generation_id="template"):
    return contracts.GraphRAGIndexManifest(
        generation_id, "index-1", "model-1", "tokenizer-1", 3,
        contracts.GraphRAGMetric.COSINE, "source-1", "source-version-1",
    )


def _content(document_id, version_id, payload, *, tombstone_of=""):
    provenance = contracts.GraphRAGProvenance("source-1", "source-version-1", f"source-{document_id}")
    if tombstone_of:
        return contracts.GraphRAGContent(document_id, version_id, "", provenance, contracts.GraphRAGContentState.TOMBSTONED, tombstone_of)
    return contracts.GraphRAGContent(document_id, version_id, payload, provenance)


def _relation(version_id):
    provenance = contracts.GraphRAGProvenance("source-1", "source-version-1", "source-document-a")
    return contracts.GraphRAGRelation("relation-a-b", "document-a", "document-b", "links", version_id, provenance)


class RestartAndRebuildTests(unittest.TestCase):
    def _service(self, directory):
        return service_module.GraphRAGService(directory, _manifest())

    def test_restart_preserves_versions_edges_and_projection_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self._service(directory)
            service.apply(_content("document-b", "b-v1", "payload-b"))
            service.apply(_content("document-a", "a-v1", "payload-a"), relations=(_relation("a-v1"),))
            service.apply(_content("document-a", "a-v2", "payload-a-v2"), relations=(_relation("a-v2"),))
            before = service.projection
            assert before is not None
            restarted = service_module.GraphRAGService.open(directory, _manifest())
            self.assertEqual(before.identity, restarted.projection.identity)
            self.assertEqual(("a-v1", "a-v2"), tuple(value.version_id for value in restarted.version_history("document-a")))
            self.assertEqual(
                ("payload-a", "payload-a-v2"),
                tuple(value.payload_cid for value in restarted.version_history("document-a")),
            )
            self.assertEqual("a-v2", restarted.current_content("document-a").version_id)
            self.assertEqual(("document-a", "document-b"), tuple(value.document_id for value in restarted.projection.nodes))
            self.assertEqual(("relation-a-b",), tuple(value.relation_id for value in restarted.projection.edges))

    def test_incremental_and_clean_rebuild_are_identical_and_tombstones_do_not_resurrect(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self._service(directory)
            service.apply(_content("document-b", "b-v1", "payload-b"))
            service.apply(_content("document-a", "a-v1", "payload-a"), relations=(_relation("a-v1"),))
            service.delete_content(_content("document-a", "a-v2", "", tombstone_of="a-v1"))
            incremental = service.projection
            clean = service.clean_rebuild().projection
            self.assertEqual(incremental.identity, clean.identity)
            self.assertEqual(("document-b",), tuple(value.document_id for value in clean.nodes))
            self.assertEqual((), clean.edges)
            with self.assertRaises(service_module.GraphRAGVersionError):
                service.apply(_content("document-a", "a-v3", "payload-resurrection"))

    def test_crash_before_generation_keeps_previous_generation_readable_and_restart_catches_up(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self._service(directory)
            service.apply(_content("document-a", "a-v1", "payload-a"))
            prior_id = service.index_generation.generation_id

            def crash_before_publication():
                raise RuntimeError("crash")

            with self.assertRaises(RuntimeError):
                service.apply(
                    _content("document-b", "b-v1", "payload-b"),
                    before_publish=crash_before_publication,
                )
            projection_store = storage.SafeGraphRAGStorage(Path(directory) / "projections")
            self.assertEqual(prior_id, projection_store.load_generation().manifest.generation_id)
            restarted = service_module.GraphRAGService.open(directory, _manifest())
            self.assertEqual(("document-a", "document-b"), tuple(value.document_id for value in restarted.projection.nodes))

    def test_corrupt_projection_rebuilds_from_non_executable_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self._service(directory)
            service.apply(_content("document-a", "a-v1", "payload-a"))
            current = Path(directory) / "projections" / "CURRENT.json"
            current.write_bytes(b"not-json")
            current.chmod(0o600)
            restarted = service_module.GraphRAGService.open(directory, _manifest())
            self.assertEqual(("document-a",), tuple(value.document_id for value in restarted.projection.nodes))


if __name__ == "__main__":
    unittest.main()
