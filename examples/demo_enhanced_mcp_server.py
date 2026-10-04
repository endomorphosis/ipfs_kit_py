#!/usr/bin/env python3
"""
Demo script for the Enhanced MCP Server with Service Management.

This script demonstrates the new service configuration and monitoring capabilities.
"""

import anyio
import sys
import logging
from pathlib import Path

# Add the package to the path
sys.path.insert(0, str(Path(__file__).parent / "ipfs_kit_py"))

from ipfs_kit_py.enhanced_mcp_server import EnhancedMCPServer
from ipfs_kit_py.service_registry import get_service_registry

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_enhanced_server():
    """Demonstrate the enhanced MCP server."""
    logger.info("🚀 Starting Enhanced MCP Server Demo")
    
    # Create and setup the server
    server = EnhancedMCPServer(host="127.0.0.1", port=8004)
    
    # Add some demo services
    service_registry = get_service_registry()
    
    # Add IPFS service
    await service_registry.add_service("ipfs", {
        "host": "127.0.0.1",
        "port": 5001,
        "gateway_port": 8080
    })
    
    # Add S3 service
    await service_registry.add_service("s3", {
        "region": "us-east-1",
        "bucket": "my-ipfs-backup"
    })
    
    # Add Storacha service
    await service_registry.add_service("storacha", {
        "endpoint": "https://api.storacha.network",
        "space": "default-space"
    })
    
    logger.info("✅ Demo services added")
    logger.info("🌐 Dashboard will be available at http://127.0.0.1:8004")
    logger.info("📊 Service management API at http://127.0.0.1:8004/api/services/")
    logger.info("🛑 Press Ctrl+C to stop the server")
    
    # Start the server
    await server.start()


if __name__ == "__main__":
    try:
        anyio.run(demo_enhanced_server)
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)