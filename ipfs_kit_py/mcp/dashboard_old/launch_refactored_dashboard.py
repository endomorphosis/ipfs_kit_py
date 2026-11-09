#!/usr/bin/env python3
"""
Simple launcher for the refactored unified MCP dashboard.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the Python path to enable imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from mcp.dashboard.refactored_unified_mcp_dashboard import RefactoredUnifiedMCPDashboard

    print("🚀 Starting Refactored Unified MCP Dashboard...")
    print("🌐 Dashboard will be available at: http://127.0.0.1:8004")
    print("📁 Static files served from: mcp/dashboard/static/")
    print("📄 Templates from: mcp/dashboard/templates/")
    print("=" * 60)

    dashboard = RefactoredUnifiedMCPDashboard()
    dashboard.run()

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Make sure you're running from the correct directory")
    print("💡 Required: /home/devel/ipfs_kit_py/")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error starting dashboard: {e}")
    sys.exit(1)
