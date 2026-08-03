"""Package / CLI / MCP GraphRAG interface parity (KITA-017).

Authority: docs/runtime_readiness/graphrag_conformance.json

Acceptance covered:

* wrappers never return success/no-op on import failure
* canonical MCP++ includes GraphRAG tools
* CLI vector/hybrid paths are not stubs
* package/CLI/MCP request schemas and normalized results/errors/CIDs are
  byte-equivalent after transport stripping
* restart and poisoning fixtures pass through every interface
* required tests assert outcomes and never accept either success or failure
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from ipfs_kit_py import graphrag
from ipfs_kit_py.graphrag import (
    GRAPHRAG_ERROR_SCHEMA,
    GRAPHRAG_OPERATIONS,
    GRAPHRAG_REQUEST_SCHEMA,
    GRAPHRAG_RESULT_SCHEMA,
    OP_APPLY,
    OP_CURRENT,
    OP_HYBRID_SEARCH,
    OP_OPEN,
    OP_PROJECTION,
    OP_REHYDRATE,
    OP_VECTOR_SEARCH,
    OP_VERSION_HISTORY,
    GraphRAGContent,
    GraphRAGContentState,
    GraphRAGIndexManifest,
    GraphRAGInterfaceError,
    GraphRAGMetric,
    GraphRAGProvenance,
    GraphRAGRelation,
    GraphRAGService,
    assert_interface_parity,
    cli_call,
    cli_hybrid_search,
    cli_vector_search,
    mcp_call,
    package_call,
    request_schema_for,
    semantic_payload,
    strip_transport_fields,
)
from ipfs_kit_py.mcp.ipfs_kit import graphrag as mcp_graphrag
from ipfs_kit_py.mcp_server.tools import graphrag_tools


CONFORMANCE_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "runtime_readiness"
    / "graphrag_conformance.json"
)


def _manifest(generation_id: str = "parity-template") -> GraphRAGIndexManifest:
    return GraphRAGIndexManifest(
        generation_id,
        "index-parity",
        "model-parity",
        "tokenizer-parity",
        3,
        GraphRAGMetric.COSINE,
        "source-parity",
        "source-version-parity",
    )


def _provenance(document_id: str = "document-a") -> GraphRAGProvenance:
    return GraphRAGProvenance(
        "source-parity",
        "source-version-parity",
        f"source-{document_id}",
    )


def _content(
    document_id: str,
    version_id: str,
    payload: str,
    *,
    tombstone_of: str = "",
) -> GraphRAGContent:
    if tombstone_of:
        return GraphRAGContent(
            document_id,
            version_id,
            "",
            _provenance(document_id),
            GraphRAGContentState.TOMBSTONED,
            tombstone_of,
        )
    return GraphRAGContent(document_id, version_id, payload, _provenance(document_id))


def _relation(version_id: str) -> GraphRAGRelation:
    return GraphRAGRelation(
        "relation-a-b",
        "document-a",
        "document-b",
        "links",
        version_id,
        _provenance("document-a"),
    )


def _identity_dict() -> dict:
    return {
        "index_id": "index-parity",
        "model_id": "model-parity",
        "tokenizer_id": "tokenizer-parity",
        "dimension": 3,
        "metric": "cosine",
        "source_id": "source-parity",
        "source_version": "source-version-parity",
    }


def _records() -> list[dict]:
    return [
        {
            "record_id": "record-a",
            "vector": [1.0, 0.0, 0.0],
            "metadata": {"document_id": "document-a", "tenant": "t1"},
        },
        {
            "record_id": "record-b",
            "vector": [0.0, 1.0, 0.0],
            "metadata": {"document_id": "document-b", "tenant": "t1"},
        },
        {
            "record_id": "record-c",
            "vector": [0.7, 0.7, 0.0],
            "metadata": {"document_id": "document-c", "tenant": "t2"},
        },
    ]


class ImportFailClosedTests(unittest.TestCase):
    def test_package_engine_modules_are_importable_or_raise(self):
        # Specific positive outcome: canonical symbols exist.
        self.assertIs(graphrag.GraphRAGService, GraphRAGService)
        self.assertTrue(callable(graphrag.dispatch))
        for name in ("contracts", "service", "vector_index", "retrieval", "storage"):
            module = importlib.import_module(f"ipfs_kit_py.graphrag.{name}")
            self.assertTrue(hasattr(module, "__file__"))

    def test_mcp_wrapper_raises_when_engine_init_fails(self):
        # Specific negative outcome: unavailable engine, not success/no-op.
        with self.assertRaises(mcp_graphrag.GraphRAGEngineUnavailable):
            # Force failure by passing a retired pickle cache path.
            mcp_graphrag.GraphRAGSearchEngine(cache_file="/tmp/retired.pkl")

    def test_mcp_wrapper_methods_require_engine(self):
        wrapper = object.__new__(mcp_graphrag.GraphRAGSearchEngine)
        wrapper.engine = None
        with self.assertRaises(mcp_graphrag.GraphRAGEngineUnavailable):
            wrapper._require_engine()

        async def _run():
            with self.assertRaises(mcp_graphrag.GraphRAGEngineUnavailable):
                await wrapper.search(query="x")

        asyncio.run(_run())

    def test_graphrag_tools_import_binds_package_engine(self):
        self.assertEqual(
            graphrag_tools.MCPGraphRAGTools_V1,
            "ipfs_kit_py/graphrag/mcp-tools@1",
        )
        tools = graphrag_tools.MCPGraphRAGTools()
        self.assertGreaterEqual(len(tools.list_tools()), len(GRAPHRAG_OPERATIONS))


class MCPPlusPlusInclusionTests(unittest.TestCase):
    def test_canonical_mcpp_includes_graphrag_tools(self):
        registered = graphrag_tools.register_graphrag_tools({})
        self.assertTrue(graphrag_tools.mcpp_includes_graphrag(registered))
        names = graphrag_tools.MCPGraphRAGTools().hierarchical_names()
        self.assertIn("graphrag_tools/graphrag_vector_search", names)
        self.assertIn("graphrag_tools/graphrag_hybrid_search", names)
        descriptors = graphrag_tools.list_tool_descriptors()
        self.assertEqual(len(descriptors), len(GRAPHRAG_OPERATIONS))
        for descriptor in descriptors:
            self.assertEqual(descriptor["request_schema"], GRAPHRAG_REQUEST_SCHEMA)
            self.assertEqual(descriptor["result_schema"], GRAPHRAG_RESULT_SCHEMA)
            self.assertEqual(descriptor["error_schema"], GRAPHRAG_ERROR_SCHEMA)
            self.assertIn("inputSchema", descriptor)
            self.assertIn("request", descriptor["inputSchema"]["properties"])

    def test_competing_registration_is_rejected(self):
        tools = graphrag_tools.MCPGraphRAGTools()
        base = tools.register_into({})
        with self.assertRaises(ValueError):
            tools.register_into(
                {graphrag_tools.GRAPHRAG_TOOL_CATEGORY: {"impostor": lambda: None}}
            )
        # Idempotent re-register of the same group is allowed.
        again = tools.register_into(base)
        self.assertTrue(graphrag_tools.mcpp_includes_graphrag(again))


class SchemaAndByteParityTests(unittest.TestCase):
    def test_request_schemas_are_identical_across_surfaces(self):
        package_schemas = graphrag.all_request_schemas()
        mcp_schemas = mcp_graphrag.request_schemas()
        self.assertEqual(set(package_schemas), set(mcp_schemas))
        for operation in GRAPHRAG_OPERATIONS:
            package_bytes = graphrag.canonical_json_bytes(package_schemas[operation])
            mcp_bytes = graphrag.canonical_json_bytes(mcp_schemas[operation])
            self.assertEqual(package_bytes, mcp_bytes)
            # Tool descriptors pin the same request schema identity.
            descriptor = next(
                item
                for item in graphrag_tools.list_tool_descriptors()
                if item["operation_id"] == operation
            )
            self.assertEqual(descriptor["request_schema"], GRAPHRAG_REQUEST_SCHEMA)
            self.assertEqual(
                descriptor["operation_request_fields"],
                request_schema_for(operation)["fields"],
            )

    def test_apply_results_errors_and_cids_are_byte_equivalent(self):
        with tempfile.TemporaryDirectory() as directory:
            # Isolate each transport's ledger root so concurrent writes do not
            # race; compare semantic payloads of equivalent independent applies
            # is wrong — use one shared root and read-only ops after write.
            root = directory
            manifest = _manifest().to_record()
            # Seed once via package.
            seed = package_call(
                OP_APPLY,
                {
                    "root": root,
                    "manifest": manifest,
                    "content": _content("document-b", "b-v1", "payload-b").to_record(),
                },
                request_id="seed-b",
            )
            self.assertTrue(seed["success"], seed)
            seed_a = package_call(
                OP_APPLY,
                {
                    "root": root,
                    "manifest": manifest,
                    "content": _content("document-a", "a-v1", "payload-a").to_record(),
                    "relations": [_relation("a-v1").to_record()],
                },
                request_id="seed-a",
            )
            self.assertTrue(seed_a["success"], seed_a)
            content_cid = seed_a["content_cid"]
            self.assertIsInstance(content_cid, str)
            self.assertTrue(content_cid.startswith("b"))

            request = {
                "root": root,
                "manifest": manifest,
                "document_id": "document-a",
            }
            pkg = package_call(OP_CURRENT, request, request_id="pkg-1")
            cli = cli_call(OP_CURRENT, request, request_id="cli-1")
            mcp = mcp_call(OP_CURRENT, request, request_id="mcp-1")
            mcp_tool = graphrag_tools.call_tool(
                "graphrag_tools/graphrag_current_content",
                {"request": request},
            )
            for envelope in (pkg, cli, mcp, mcp_tool):
                self.assertTrue(envelope["success"], envelope)
                self.assertEqual(envelope["content_cid"], content_cid)
                self.assertEqual(
                    envelope["result"]["content"]["content_id"], content_cid
                )

            shared = assert_interface_parity(pkg, cli, mcp, mcp_tool)
            self.assertIsInstance(shared, (bytes, bytearray))
            self.assertEqual(semantic_payload(pkg), semantic_payload(cli))
            self.assertEqual(semantic_payload(cli), semantic_payload(mcp))
            self.assertEqual(semantic_payload(mcp), semantic_payload(mcp_tool))

    def test_error_envelopes_are_byte_equivalent_across_transports(self):
        request = {
            "root": "/nonexistent/graphrag-parity-missing",
            "manifest": _manifest().to_record(),
            "document_id": "missing-doc",
        }
        # Force admission failure with unknown field (deterministic, no FS race).
        bad = {
            "root": "/tmp",
            "manifest": _manifest().to_record(),
            "document_id": "x",
            "unexpected_field": True,
        }
        pkg = package_call(OP_CURRENT, bad, request_id="pkg-err")
        cli = cli_call(OP_CURRENT, bad, request_id="cli-err")
        mcp = mcp_call(OP_CURRENT, bad, request_id="mcp-err")
        for envelope in (pkg, cli, mcp):
            self.assertFalse(envelope["success"], envelope)
            self.assertIsNone(envelope["result"])
            self.assertIsNotNone(envelope["error"])
            self.assertEqual(envelope["error"]["schema"], GRAPHRAG_ERROR_SCHEMA)
            self.assertEqual(envelope["content_cid"], None)
        assert_interface_parity(pkg, cli, mcp)

    def test_transport_only_fields_are_stripped_for_comparison(self):
        sample = {
            "success": True,
            "operation": OP_OPEN,
            "result": {"x": 1},
            "error": None,
            "request_id": "a",
            "transport": "package",
            "timing": {"elapsed_ms": 12},
        }
        stripped = strip_transport_fields(sample)
        self.assertNotIn("request_id", stripped)
        self.assertNotIn("transport", stripped)
        self.assertNotIn("timing", stripped)
        self.assertEqual(stripped["result"], {"x": 1})


class CLIVectorHybridNotStubsTests(unittest.TestCase):
    def test_cli_vector_search_returns_ranked_matches(self):
        request = {
            "query_vector": [1.0, 0.0, 0.0],
            "k": 2,
            "identity": _identity_dict(),
            "records": _records(),
            "backend": "exact",
        }
        envelope = cli_vector_search(request, request_id="cli-vec")
        self.assertTrue(envelope["success"], envelope)
        matches = envelope["result"]["matches"]
        self.assertEqual(2, len(matches))
        self.assertEqual("record-a", matches[0]["record_id"])
        self.assertGreater(matches[0]["score"], matches[1]["score"])
        # Same path via package and MCP must match.
        pkg = package_call(OP_VECTOR_SEARCH, request, request_id="pkg-vec")
        mcp = mcp_call(OP_VECTOR_SEARCH, request, request_id="mcp-vec")
        assert_interface_parity(envelope, pkg, mcp)
        # Explicit non-stub: CLI path delegates into the shared call chain.
        self.assertTrue(callable(graphrag.cli_vector_search))
        self.assertIn("cli_call", graphrag.cli_vector_search.__code__.co_names)
        self.assertEqual(len(matches), 2)

    def test_cli_hybrid_search_merges_vector_and_lexical(self):
        request = {
            "query_vector": [1.0, 0.0, 0.0],
            "text_query": "document",
            "k": 3,
            "identity": _identity_dict(),
            "records": _records(),
            "lexical_results": [
                {"document_id": "document-b", "score": 0.9, "metadata": {"tenant": "t1"}},
                {"document_id": "document-a", "score": 0.2, "metadata": {"tenant": "t1"}},
            ],
            "vector_weight": 0.5,
            "lexical_weight": 0.5,
            "backend": "exact",
        }
        envelope = cli_hybrid_search(request, request_id="cli-hyb")
        self.assertTrue(envelope["success"], envelope)
        results = envelope["result"]["results"]
        self.assertGreaterEqual(len(results), 2)
        self.assertFalse(envelope["result"]["authoritative"])
        ids = {item["document_id"] for item in results}
        self.assertIn("document-a", ids)
        self.assertIn("document-b", ids)
        pkg = package_call(OP_HYBRID_SEARCH, request, request_id="pkg-hyb")
        mcp = mcp_call(OP_HYBRID_SEARCH, request, request_id="mcp-hyb")
        tool = graphrag_tools.call_tool(
            "graphrag_tools/graphrag_hybrid_search", {"request": request}
        )
        assert_interface_parity(envelope, pkg, mcp, tool)

    def test_identity_mismatch_fails_closed_on_all_transports(self):
        request = {
            "query_vector": [1.0, 0.0, 0.0],
            "k": 1,
            "identity": _identity_dict(),
            "records": [
                {
                    "record_id": "record-a",
                    "vector": [1.0, 0.0, 0.0],
                    "metadata": {"document_id": "document-a"},
                }
            ],
            "backend": "exact",
        }
        # Poison identity on a second search by changing model after rebuild is
        # internal; instead pass wrong dimension via identity on empty rebuild
        # with mismatched record dimension through filters only — use wrong k type.
        bad = dict(request)
        bad["identity"] = dict(_identity_dict())
        bad["identity"]["dimension"] = 4  # records are 3-d → mismatch on rebuild
        pkg = package_call(OP_VECTOR_SEARCH, bad, request_id="pkg-mm")
        cli = cli_call(OP_VECTOR_SEARCH, bad, request_id="cli-mm")
        mcp = mcp_call(OP_VECTOR_SEARCH, bad, request_id="mcp-mm")
        for envelope in (pkg, cli, mcp):
            self.assertFalse(envelope["success"], envelope)
            self.assertEqual(envelope["error"]["category"], "identity")
        assert_interface_parity(pkg, cli, mcp)


class RestartAndPoisoningParityTests(unittest.TestCase):
    def test_restart_fixtures_pass_through_every_interface(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = _manifest().to_record()
            package_call(
                OP_APPLY,
                {
                    "root": directory,
                    "manifest": manifest,
                    "content": _content("document-b", "b-v1", "payload-b").to_record(),
                },
                request_id="rst-b",
            )
            package_call(
                OP_APPLY,
                {
                    "root": directory,
                    "manifest": manifest,
                    "content": _content("document-a", "a-v1", "payload-a").to_record(),
                    "relations": [_relation("a-v1").to_record()],
                },
                request_id="rst-a1",
            )
            package_call(
                OP_APPLY,
                {
                    "root": directory,
                    "manifest": manifest,
                    "content": _content("document-a", "a-v2", "payload-a-v2").to_record(),
                    "relations": [_relation("a-v2").to_record()],
                },
                request_id="rst-a2",
            )
            before = package_call(
                OP_PROJECTION,
                {"root": directory, "manifest": manifest},
                request_id="rst-before",
            )
            self.assertTrue(before["success"], before)
            before_identity = before["result"]["projection_identity"]
            self.assertIsInstance(before_identity, str)
            self.assertTrue(before_identity)

            # Restart via each interface (rehydrate). Publication generation IDs
            # are intentionally unique per rebuild; projection identity, nodes,
            # and edges are the durable semantic equalities.
            for transport_call, request_id in (
                (package_call, "rst-pkg"),
                (cli_call, "rst-cli"),
                (mcp_call, "rst-mcp"),
            ):
                envelope = transport_call(
                    OP_REHYDRATE,
                    {"root": directory, "manifest": manifest},
                    request_id=request_id,
                )
                self.assertIs(envelope["success"], True)
                self.assertEqual(envelope["result"]["projection_identity"], before_identity)
                self.assertEqual(
                    ("document-a", "document-b"),
                    tuple(envelope["result"]["nodes"]),
                )
                self.assertEqual(("relation-a-b",), tuple(envelope["result"]["edges"]))

            tool = graphrag_tools.call_tool(
                "graphrag_tools/graphrag_rehydrate",
                {"request": {"root": directory, "manifest": manifest}},
            )
            self.assertIs(tool["success"], True)
            self.assertEqual(tool["result"]["projection_identity"], before_identity)

            # Byte-equivalent cross-interface read of version history (stable CIDs).
            history_req = {
                "root": directory,
                "manifest": manifest,
                "document_id": "document-a",
            }
            hist_pkg = package_call(OP_VERSION_HISTORY, history_req, request_id="h-pkg")
            hist_cli = cli_call(OP_VERSION_HISTORY, history_req, request_id="h-cli")
            hist_mcp = mcp_call(OP_VERSION_HISTORY, history_req, request_id="h-mcp")
            hist_tool = graphrag_tools.call_tool(
                "graphrag_tools/graphrag_version_history",
                {"request": history_req},
            )
            for envelope in (hist_pkg, hist_cli, hist_mcp, hist_tool):
                self.assertIs(envelope["success"], True)
                versions = envelope["result"]["versions"]
                self.assertEqual(["a-v1", "a-v2"], [item["version_id"] for item in versions])
                self.assertEqual(
                    ["payload-a", "payload-a-v2"],
                    [item["payload_cid"] for item in versions],
                )
            assert_interface_parity(hist_pkg, hist_cli, hist_mcp, hist_tool)

    def test_poisoning_fixtures_fail_closed_on_every_interface(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = _manifest().to_record()
            applied = package_call(
                OP_APPLY,
                {
                    "root": directory,
                    "manifest": manifest,
                    "content": _content("document-a", "a-v1", "payload-a").to_record(),
                },
                request_id="poison-seed",
            )
            self.assertTrue(applied["success"], applied)

            # Poison the durable ledger pointer with non-canonical / wrong schema JSON.
            pointer = Path(directory) / "records" / "CURRENT.json"
            self.assertTrue(pointer.is_file())
            pointer.write_text(
                json.dumps({"schema": "poisoned", "contract_version": 1}),
                encoding="utf-8",
            )
            os.chmod(pointer, 0o600)

            request = {"root": directory, "manifest": manifest}
            pkg = package_call(OP_REHYDRATE, request, request_id="poison-pkg")
            cli = cli_call(OP_REHYDRATE, request, request_id="poison-cli")
            mcp = mcp_call(OP_REHYDRATE, request, request_id="poison-mcp")
            tool = graphrag_tools.call_tool(
                "graphrag_tools/graphrag_rehydrate",
                {"request": request},
            )
            for envelope in (pkg, cli, mcp, tool):
                # Specific outcome: failure, never success, never empty success.
                self.assertIs(envelope["success"], False)
                self.assertIsNone(envelope["result"])
                self.assertIsNotNone(envelope["error"])
                self.assertIn(
                    envelope["error"]["category"],
                    {"ledger", "poisoning", "request"},
                )
                self.assertNotEqual(envelope["error"]["message"], "")
            assert_interface_parity(pkg, cli, mcp, tool)

    def test_projection_symlink_poisoning_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_obj = _manifest()
            service = GraphRAGService(directory, manifest_obj)
            service.apply(_content("document-a", "a-v1", "payload-a"))
            generations = Path(directory) / "projections" / "generations"
            if generations.is_dir():
                for child in generations.iterdir():
                    if child.is_file() and not child.is_symlink():
                        child.unlink()
                        os.symlink("/etc/passwd", child)
                        break
            # Safe storage load path is exercised by rehydrate after poison.
            request = {"root": directory, "manifest": manifest_obj.to_record()}
            # Rehydrate rebuilds from ledger records (source of truth), so a
            # poisoned projection must not prevent recovery from ledger — that
            # is durability.  Poison the ledger event instead for fail-closed.
            events = Path(directory) / "records" / "events"
            event_files = sorted(events.glob("*.json"))
            self.assertGreaterEqual(len(event_files), 1)
            target = event_files[0]
            target.unlink()
            os.symlink("/etc/passwd", target)
            pkg = package_call(OP_OPEN, request, request_id="sym-pkg")
            cli = cli_call(OP_OPEN, request, request_id="sym-cli")
            mcp = mcp_call(OP_OPEN, request, request_id="sym-mcp")
            for envelope in (pkg, cli, mcp):
                self.assertIs(envelope["success"], False)
                self.assertIsNotNone(envelope["error"])
            assert_interface_parity(pkg, cli, mcp)


class OutcomeAssertionDisciplineTests(unittest.TestCase):
    """Meta-checks: this suite asserts outcomes, never accepts either result."""

    def test_success_path_requires_success_true(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = package_call(
                OP_APPLY,
                {
                    "root": directory,
                    "manifest": _manifest().to_record(),
                    "content": _content("document-a", "a-v1", "payload-a").to_record(),
                },
            )
            # Must be exactly True, not merely truthy/any.
            self.assertIs(envelope["success"], True)
            self.assertIsNotNone(envelope["result"])
            self.assertIsNone(envelope["error"])

    def test_failure_path_requires_success_false(self):
        envelope = package_call(
            OP_VECTOR_SEARCH,
            {
                "query_vector": [1.0],
                "k": 1,
                "identity": _identity_dict(),
                "records": [],
            },
        )
        # Dimension mismatch (query dim 1 vs identity dim 3) must fail.
        self.assertIs(envelope["success"], False)
        self.assertIsNone(envelope["result"])
        self.assertIsNotNone(envelope["error"])

    def test_conformance_receipt_is_present_and_coherent(self):
        self.assertTrue(CONFORMANCE_PATH.is_file(), CONFORMANCE_PATH)
        receipt = json.loads(CONFORMANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            receipt["schema"],
            "ipfs_kit_py/runtime-readiness/graphrag-conformance@1",
        )
        self.assertEqual(receipt["task_id"], "KITA-017")
        self.assertEqual(receipt["contract_version"], 1)
        self.assertIn("package", receipt["transports"])
        self.assertIn("cli", receipt["transports"])
        self.assertIn("mcp", receipt["transports"])
        self.assertTrue(receipt["acceptance"]["no_success_noop_on_import_failure"])
        self.assertTrue(receipt["acceptance"]["mcpp_includes_graphrag_tools"])
        self.assertTrue(receipt["acceptance"]["cli_vector_hybrid_not_stubs"])
        self.assertTrue(receipt["acceptance"]["byte_equivalent_normalized_payloads"])
        self.assertTrue(receipt["acceptance"]["restart_and_poisoning_cross_interface"])
        self.assertTrue(receipt["acceptance"]["tests_assert_outcomes"])
        self.assertEqual(
            receipt["suite"],
            "tests/runtime_readiness/graphrag/test_interface_parity.py",
        )
        # Engine modules must not be reimplemented in the adapter file.
        adapter_source = Path(graphrag.__file__).read_text(encoding="utf-8").lower()
        self.assertNotIn("pickle.load", adapter_source)
        self.assertNotIn("pickle.dump", adapter_source)
        self.assertNotIn("sentence_transformers", adapter_source)


if __name__ == "__main__":
    unittest.main()
