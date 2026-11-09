#!/usr/bin/env python3
"""
Direct dashboard runner - bypasses package cache issues
"""

import sys
import os
from pathlib import Path
import importlib.util

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import dashboard directly from file using importlib
dashboard_file = project_root / "ipfs_kit_py" / "dashboard" / "comprehensive_mcp_dashboard.py"
spec = importlib.util.spec_from_file_location("comprehensive_mcp_dashboard", dashboard_file)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load dashboard from {dashboard_file}")
dashboard_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard_module)

if __name__ == "__main__":
    import uvicorn

    print("🔧 Creating comprehensive MCP dashboard...")

    # Use a config dict to create a truly standalone dashboard
    config = {
        "host": "127.0.0.1",
        "port": 8086,  # Use different port to avoid conflicts
        "mcp_server_url": None,  # Disable MCP server connections
        "data_dir": "~/.ipfs_kit",
        "debug": True,
        "update_interval": 5,
        "standalone_mode": True,  # Explicitly enable standalone mode
    }

    try:
        # Create the dashboard and get the FastAPI app
        print(f"🔧 Config being passed: {config}")
        dashboard = dashboard_module.ComprehensiveMCPDashboard(config)
        print(f"🔧 Dashboard standalone_mode: {dashboard.standalone_mode}")
        print(f"🔧 Dashboard mcp_server_url: {dashboard.mcp_server_url}")
        app = dashboard.app

        print("🚀 Starting comprehensive MCP dashboard directly...")
        print("📊 Dashboard will be available at: http://127.0.0.1:8086")
        if dashboard.standalone_mode:
            print("🔧 Running in standalone mode - MCP features disabled")
        else:
            print(f"🔗 Connecting to MCP server at: {dashboard.mcp_server_url}")

        # Run with uvicorn
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8086,
            reload=False,  # Disable reload since we're running directly
            log_level="info",
        )
    except Exception as e:
        print(f"❌ Error creating dashboard: {e}")
        print("💡 Try stopping other ipfs-kit processes first: pkill -f 'ipfs-kit'")
        sys.exit(1)
