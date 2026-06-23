from pathlib import Path

from ipfs_kit_py.feature_exposure import dispatch_feature_tool, feature_tool_definitions
from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard
from ipfs_kit_py.unified_cli_dispatcher import UnifiedCLIDispatcher


REQUIRED_FEATURE_TOOLS = {
    "walrus_status",
    "walrus_list",
    "walrus_get",
    "walrus_put",
    "walrus_delete",
    "fsspec_list_protocols",
    "fsspec_backend_status",
    "fsspec_read",
    "fsspec_write",
    "vfs_graphrag_status",
    "vfs_graphrag_search",
    "vfs_graphrag_metadata_search",
    "vfs_graphrag_vector_search",
    "vfs_graphrag_hybrid_search",
    "vfs_graphrag_graph_search",
    "vfs_graphrag_graph_hybrid_search",
    "vfs_graphrag_export",
}


def test_feature_tool_definitions_and_dispatch_are_aligned():
    names = {tool["name"] for tool in feature_tool_definitions()}

    assert REQUIRED_FEATURE_TOOLS <= names
    for name in REQUIRED_FEATURE_TOOLS:
        result = dispatch_feature_tool(name, {"method": "unknown"})
        assert result is not None, name

    assert dispatch_feature_tool("not_a_real_feature_tool", {}) is None


def test_unified_cli_registers_feature_commands():
    parser = UnifiedCLIDispatcher().parser

    walrus = parser.parse_args(["walrus", "status"])
    assert walrus.command == "walrus"
    assert walrus.walrus_action == "status"

    fsspec = parser.parse_args(["fsspec", "protocols"])
    assert fsspec.command == "fsspec"
    assert fsspec.fsspec_action == "protocols"

    graphrag = parser.parse_args(["graphrag", "search", "hello", "--method", "graph_hybrid_search"])
    assert graphrag.command == "graphrag"
    assert graphrag.graphrag_action == "search"
    assert graphrag.method == "graph_hybrid_search"


def test_consolidated_dashboard_registers_feature_tools(tmp_path):
    dashboard = ConsolidatedMCPDashboard({"host": "127.0.0.1", "port": 0, "data_dir": str(tmp_path)})
    names = {tool["name"] for tool in dashboard._tools_list()["result"]["tools"]}

    assert REQUIRED_FEATURE_TOOLS <= names


def test_browser_sdks_expose_feature_namespaces():
    repo_root = Path(__file__).resolve().parents[1]
    static_sdk = (repo_root / "static" / "mcp-sdk.js").read_text(encoding="utf-8")
    dashboard_sdk = (repo_root / "ipfs_kit_py" / "mcp" / "dashboard" / "static" / "mcp-sdk.js").read_text(encoding="utf-8")
    sdk_types = (repo_root / "static" / "mcp-sdk.d.ts").read_text(encoding="utf-8")

    for body in (static_sdk, dashboard_sdk):
        assert "window.MCP.Walrus" in body
        assert "window.MCP.FSSpec" in body
        assert "window.MCP.VFSGraphRAG" in body
        assert "vfs_graphrag_graph_hybrid_search" in body

    assert "WalrusNamespace" in sdk_types
    assert "FSSpecNamespace" in sdk_types
    assert "VFSGraphRAGNamespace" in sdk_types
    assert "graphHybridSearch" in sdk_types
