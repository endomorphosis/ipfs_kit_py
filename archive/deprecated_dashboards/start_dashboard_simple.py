#!/usr/bin/env python3

import sys
import os
import uvicorn
import logging

# Add project path
sys.path.insert(0, "/home/devel/ipfs_kit_py")


def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Try importing dashboard
    try:
        from ipfs_kit_py.dashboard.comprehensive_mcp_dashboard import ComprehensiveMCPDashboard

        logger.info("✅ Dashboard imported successfully")
    except Exception as e:
        logger.error(f"❌ Failed to import dashboard: {e}")
        return

    # Create configuration
    config = {
        "data_dir": "~/.ipfs_kit/data",
        "port": 8085,
        "mcp_server_url": "http://127.0.0.1:8085",
    }

    # Initialize dashboard
    try:
        dashboard = ComprehensiveMCPDashboard(config)
        logger.info("✅ Dashboard initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize dashboard: {e}")
        return

    # Check if logs routes are registered
    logs_routes = [r for r in dashboard.app.routes if hasattr(r, "path") and "/api/logs" in r.path]
    logger.info(f"✅ Found {len(logs_routes)} logs routes registered")

    # Start server
    logger.info("🚀 Starting dashboard server on http://127.0.0.1:8085")
    logger.info("📊 Dashboard logs available at: http://127.0.0.1:8085/api/logs")

    try:
        uvicorn.run(dashboard.app, host="127.0.0.1", port=8085, log_level="info")
    except KeyboardInterrupt:
        logger.info("👋 Server stopped")


if __name__ == "__main__":
    main()
