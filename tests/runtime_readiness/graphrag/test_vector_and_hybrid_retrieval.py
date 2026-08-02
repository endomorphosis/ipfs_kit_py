"""Runtime-readiness tests for bounded GraphRAG vector and hybrid retrieval."""

from __future__ import annotations

import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path


def _load_modules():
    root = Path(__file__).resolve().parents[3] / "ipfs_kit_py" / "graphrag"
    package_name = "ipfs_kit_py.graphrag_retrieval_boundary"
    package = types.ModuleType(package_name)
    package.__path__ = [str(root)]
    sys.modules[package_name] = package
    loaded = {}
    for name in ("vector_index", "retrieval"):
        qualified = f"{package_name}.{name}"
        spec = importlib.util.spec_from_file_location(qualified, root / f"{name}.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        spec.loader.exec_module(module)
        loaded[name] = module
    return loaded


modules = _load_modules()
vectors = modules["vector_index"]
retrieval = modules["retrieval"]


def _identity():
    return vectors.VectorIndexIdentity(
        "index-1", "model-1", "tokenizer-1", 3, "cosine", "source-1", "source-version-1"
    )


def _record(number, *, identity=None, tenant="a"):
    angle = number * 0.31
    return vectors.VectorRecord(
        f"record-{number:03d}",
        (math.cos(angle), math.sin(angle), math.cos(angle * 0.5)),
        {"document_id": f"document-{number:03d}", "tenant": tenant},
        identity,
    )


class _EmptyBackend:
    def rebuild(self, records, identity):
        self.records = tuple(records)

    def search(self, query, limit, filters=None):
        return ()


class VectorIndexTests(unittest.TestCase):
    def test_ann_recall_p95_and_identity_are_pinned(self):
        identity = _identity()
        records = tuple(_record(value, identity=identity) for value in range(80))
        exact = vectors.ExactVectorIndex(identity)
        ann = vectors.ANNVectorIndex(identity)
        exact.rebuild(records, identity=identity)
        ann.rebuild(records, identity=identity)
        queries = tuple(record.vector for record in records[::7])
        benchmark = vectors.benchmark_ann_recall(ann, exact, queries, k=10, p95_floor_seconds=0.000_001)
        self.assertGreaterEqual(benchmark.recall_at_k, 0.95)
        self.assertGreaterEqual(benchmark.query_p95_seconds, benchmark.p95_floor_seconds)
        self.assertEqual(10, benchmark.k)
        wrong = vectors.VectorIndexIdentity("index-2", "model-1", "tokenizer-1", 3, "cosine")
        with self.assertRaises(vectors.VectorIdentityMismatchError):
            ann.search(queries[0], identity=wrong)
        with self.assertRaises(vectors.VectorIdentityMismatchError):
            exact.add(_record(99, identity=wrong))

    def test_add_update_delete_and_rebuild_have_one_snapshot(self):
        identity = _identity()
        index = vectors.ExactVectorIndex(identity)
        index.add(_record(1, identity=identity), identity=identity)
        index.add(_record(2, identity=identity), identity=identity)
        index.update(vectors.VectorRecord("record-002", (0.0, 1.0, 0.0), {"document_id": "document-002", "tenant": "a"}, identity))
        index.delete("record-001", identity=identity)
        clean = vectors.ExactVectorIndex(identity)
        clean.rebuild((vectors.VectorRecord("record-002", (0.0, 1.0, 0.0), {"document_id": "document-002", "tenant": "a"}, identity),), identity=identity)
        self.assertEqual(index.snapshot(), clean.snapshot())
        self.assertEqual(index.search((0.0, 1.0, 0.0)), clean.search((0.0, 1.0, 0.0)))

    def test_filters_and_tie_breaks_are_deterministic(self):
        identity = _identity()
        index = vectors.ExactVectorIndex(identity)
        index.rebuild((
            vectors.VectorRecord("z-record", (1, 0, 0), {"tenant": "a"}, identity),
            vectors.VectorRecord("a-record", (1, 0, 0), {"tenant": "a"}, identity),
            vectors.VectorRecord("other", (1, 0, 0), {"tenant": "b"}, identity),
        ))
        results = index.search((1, 0, 0), filters={"tenant": "a"})
        self.assertEqual(("a-record", "z-record"), tuple(value.record_id for value in results))
        with self.assertRaises(vectors.VectorValidationError):
            index.search((float("nan"), 0, 0))


class HybridRetrieverTests(unittest.TestCase):
    def test_weights_filters_ties_and_advisory_boundary(self):
        identity = _identity()
        index = vectors.ExactVectorIndex(identity)
        index.rebuild((
            vectors.VectorRecord("z", (1, 0, 0), {"document_id": "z", "tenant": "a"}, identity),
            vectors.VectorRecord("a", (1, 0, 0), {"document_id": "a", "tenant": "a"}, identity),
            vectors.VectorRecord("hidden", (1, 0, 0), {"document_id": "hidden", "tenant": "b"}, identity),
        ))

        def lexical(query, limit, filters):
            return [
                {"document_id": "z", "score": 2.0, "metadata": {"tenant": "a"}},
                {"document_id": "a", "score": 2.0, "metadata": {"tenant": "a"}},
                {"document_id": "hidden", "score": 99.0, "metadata": {"tenant": "b"}},
            ]

        retriever = retrieval.HybridRetriever(index, lexical)
        response = retriever.search((1, 0, 0), "term", filters={"tenant": "a"}, vector_weight=2, lexical_weight=2)
        self.assertEqual((0.5, 0.5), (response.weights.vector, response.weights.lexical))
        self.assertEqual(("a", "z"), tuple(value.document_id for value in response.results))
        self.assertFalse(response.authoritative)
        self.assertTrue(all(not value.authoritative for value in response.results))
        with self.assertRaises(retrieval.HybridRetrievalError):
            retrieval.HybridWeights(float("inf"), 1)
        with self.assertRaises(retrieval.HybridRetrievalError):
            retrieval.HybridWeights(0, 0)

    def test_exact_fallback_is_opt_in_bounded_and_explicit(self):
        identity = _identity()
        index = vectors.ANNVectorIndex(identity, backend=_EmptyBackend())
        index.rebuild((_record(1, identity=identity), _record(2, identity=identity)))
        retriever = retrieval.HybridRetriever(index, max_exact_fallback_candidates=2)
        response = retriever.search(_record(1).vector, allow_exact_fallback=True)
        self.assertTrue(response.exact_fallback_used)
        self.assertEqual("used", response.exact_fallback_reason)
        limited = retrieval.HybridRetriever(index, max_exact_fallback_candidates=1).search(
            _record(1).vector, allow_exact_fallback=True
        )
        self.assertFalse(limited.exact_fallback_used)
        self.assertEqual("candidate_limit_exceeded", limited.exact_fallback_reason)


if __name__ == "__main__":
    unittest.main()
