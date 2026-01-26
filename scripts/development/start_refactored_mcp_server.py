#!/usr/bin/env python3
"""
Start the refactored IPFS Kit MCP Server

This script starts the refactored MCP server that mirrors CLI functionality
while efficiently reading metadata from ~/.ipfs_kit/ and delegating to
the intelligent daemon for backend synchronization.
"""

import anyio
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from ipfs_kit_py.mcp_server.server import main

if __name__ == "__main__":
    anyio.run(main)
