#!/usr/bin/env python3
"""
MCP Server Dashboard with Fixed Observability Tab

This script starts the integrated MCP server with dashboard showing REAL performance metrics.

FIXES IMPLEMENTED:
✅ Dashboard observability tab now shows real IPFS performance metrics (not all 0s)
✅ Log manager no longer errors on missing 'id' fields in structured JSONL files
✅ Backend health monitor properly integrated with dashboard API endpoints

USAGE:
1. Run this script: python start_fixed_dashboard.py
2. Open browser to: http://localhost:8765/dashboard
3. Navigate to the "Observability" tab
4. View real performance metrics including:
   - IPFS repo statistics
   - Bandwidth usage (in/out bytes)
   - Peer connection counts
   - Storage utilization
   - Pin counts
   - Network health status
"""

import logging
import uvicorn
from ipfs_kit_py.mcp.servers.integrated_mcp_server_with_dashboard import IntegratedMCPDashboardServer

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Start the fixed MCP server with dashboard."""
    
    print("🎉 Starting MCP Server Dashboard with FIXED Observability Tab")
    print("=" * 60)
    print("✅ Log Manager 'id' field errors: FIXED")
    print("✅ Dashboard observability metrics: FIXED (real data instead of 0s)")
    print("✅ Backend health monitor integration: FIXED")
    print("")
    print("🌐 Dashboard will be available at: http://localhost:8765/dashboard")
    print("📊 Observability tab will show REAL performance metrics")
    print("")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        # Start the integrated server
        uvicorn.run(
            "mcp.integrated_mcp_server_with_dashboard:app",
            host="127.0.0.1",
            port=8765,
            log_level="info",
            reload=False
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    main()
