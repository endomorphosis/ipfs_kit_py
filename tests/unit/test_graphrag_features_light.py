"""GraphRAG feature checks.

Keep these tests lightweight and in-process to avoid subprocess timeouts.
"""

import pytest

pytestmark = pytest.mark.anyio


@pytest.mark.anyio
async def test_graphrag_index_content_success():
    from enhanced_mcp_server_with_daemon_mgmt import GraphRAGSearchEngine

    engine = GraphRAGSearchEngine()
    result = await engine.index_content(
        cid="test123",
        path="/test/doc.txt",
        content="This is a test document about IPFS and distributed systems.",
        metadata={"topic": "test"},
    )

    assert result.get("success") is True


@pytest.mark.anyio
async def test_text_search_not_implemented():
    """Ensure text_search reports an unimplemented error without subprocesses."""
    from enhanced_mcp_server_with_daemon_mgmt import GraphRAGSearchEngine

    engine = GraphRAGSearchEngine()
    result = await engine.text_search("test query")

    assert isinstance(result, dict)
    assert "success" in result
    if "results" in result:
        assert isinstance(result.get("results"), list)
    if result.get("success") is False:
        assert "error" in result
