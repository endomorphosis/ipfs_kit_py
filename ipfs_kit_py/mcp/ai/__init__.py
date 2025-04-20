"""
AI/ML Package for MCP Server

This package provides AI/ML capabilities for the MCP server, including:
1. Model Registry - Version-controlled model storage and metadata
2. Dataset Manager - Version-controlled dataset storage and processing
3. Distributed Training - Training job orchestration and monitoring
4. Framework Integration - Integration with ML frameworks like LangChain, etc.

Part of the MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).
"""

# Import modules
try:
    from ipfs_kit_py.mcp.ai.ai_ml_integrator import get_instance as get_ai_ml_integrator
    from ipfs_kit_py.mcp.ai.dataset_manager import get_instance as get_dataset_manager
except ImportError:
    # These might not be available yet
    pass

# Package version
__version__ = "0.1.0"
