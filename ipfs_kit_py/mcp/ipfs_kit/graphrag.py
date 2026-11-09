"""
GraphRAG Search Engine for IPFS Kit (MCP Wrapper).

This module acts as a thin wrapper around the centralized GraphRAGSearchEngine
from the ipfs_kit_py library, ensuring the MCP layer uses the core search functionalities.
"""

import logging
from typing import Dict, Any

try:
    # Primary import path
    from ipfs_kit_py.graphrag import GraphRAGSearchEngine as CoreGraphRAGSearchEngine
except ImportError:
    # Fallback for development
    import sys
    import os
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from ipfs_kit_py.graphrag import GraphRAGSearchEngine as CoreGraphRAGSearchEngine

logger = logging.getLogger(__name__)

class GraphRAGSearchEngine:
    """
    MCP Wrapper for the core GraphRAGSearchEngine.
    Delegates all search and indexing tasks to the centralized library component.
    """

    def __init__(self, **kwargs):
        """Initializes the wrapper and the underlying core GraphRAGSearchEngine."""
        logger.info("=== MCP GraphRAGSearchEngine Wrapper initializing ===")
        try:
            self.engine = CoreGraphRAGSearchEngine(**kwargs)
            logger.info("✓ Centralized GraphRAGSearchEngine initialized.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize CoreGraphRAGSearchEngine: {e}", exc_info=True)
            self.engine = None
        logger.info("=== MCP GraphRAGSearchEngine Wrapper initialization complete ===")

    async def index_content(self, **kwargs) -> Dict[str, Any]:
        """Delegates content indexing to the core engine."""
        if not self.engine:
            return {"success": False, "error": "GraphRAG engine not initialized."}
        
        return await self.engine.index_content(**kwargs)

    async def search(self, **kwargs) -> Dict[str, Any]:
        """Delegates search operations to the core engine."""
        if not self.engine:
            return {"success": False, "error": "GraphRAG engine not initialized."}
            
        return await self.engine.search(**kwargs)

    def cleanup(self):
        """Cleans up resources if the underlying engine has a cleanup method."""
        if self.engine:
            logger.info("Cleaning up MCP GraphRAGSearchEngine wrapper...")
            if hasattr(self.engine, 'cleanup'):
                self.engine.cleanup()
            logger.info("✓ MCP GraphRAGSearchEngine wrapper cleaned up.")
