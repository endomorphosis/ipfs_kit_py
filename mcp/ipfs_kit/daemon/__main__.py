#!/usr/bin/env python3
"""
Main entry point for IPFS Kit Daemon module.
Allows running: python -m mcp.ipfs_kit.daemon
"""

from .ipfs_kit_daemon import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
