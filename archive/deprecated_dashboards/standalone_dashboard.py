#!/usr/bin/env python3
"""
IPFS Kit Dashboard - Standalone Mode Launcher
Easy launcher for running the dashboard without MCP dependencies.
"""
import sys
import os
from pathlib import Path
import importlib.util

def main():
    """Launch the dashboard in standalone mode."""
    print("🔧 IPFS Kit Dashboard - Standalone Mode")
    print("=======================================")
    
    # Add the project root to Python path
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    # Import dashboard directly from file using importlib
    dashboard_file = project_root / "ipfs_kit_py" / "dashboard" / "comprehensive_mcp_dashboard.py"
    
    if not dashboard_file.exists():
        print(f"❌ Dashboard file not found: {dashboard_file}")
        print("Make sure you're running this from the ipfs_kit_py root directory.")
        sys.exit(1)
    
    spec = importlib.util.spec_from_file_location("comprehensive_mcp_dashboard", dashboard_file)
    if spec is None or spec.loader is None:
        print(f"❌ Could not load dashboard from {dashboard_file}")
        sys.exit(1)
    
    dashboard_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dashboard_module)
    
    try:
        import uvicorn
    except ImportError:
        print("❌ uvicorn not found. Install with: pip install uvicorn")
        sys.exit(1)
    
    # Standalone configuration
    config = {
        'host': '127.0.0.1',
        'port': 8085,
        'mcp_server_url': None,  # Forces standalone mode
        'data_dir': '~/.ipfs_kit',
        'debug': False,
        'update_interval': 5,
        'standalone_mode': True  # Explicitly enable standalone mode
    }
    
    print(f"📊 Starting dashboard in standalone mode...")
    print(f"🌐 Dashboard URL: http://{config['host']}:{config['port']}")
    print(f"📁 Data directory: {config['data_dir']}")
    print(f"🔧 Features: System metrics, file browsing, service status")
    print(f"❌ Disabled: MCP operations, IPFS daemon control")
    print("")
    print("Press Ctrl+C to stop the dashboard")
    print("")
    
    try:
        # Create the dashboard
        dashboard = dashboard_module.ComprehensiveMCPDashboard(config)
        app = dashboard.app
        
        # Run with uvicorn
        uvicorn.run(
            app,
            host=config['host'],
            port=config['port'],
            reload=False,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting dashboard: {e}")
        print("💡 Make sure no other process is using port 8086")
        sys.exit(1)

if __name__ == "__main__":
    main()
