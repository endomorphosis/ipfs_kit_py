#!/usr/bin/env python3
"""
Enhanced MCP Server Startup Script

This script starts the Enhanced MCP Server that mirrors CLI functionality
while adapting to the MCP protocol requirements.
"""

import sys
import anyio
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ipfs_kit_py.mcp.enhanced_server import main

if __name__ == "__main__":
    anyio.run(main())
