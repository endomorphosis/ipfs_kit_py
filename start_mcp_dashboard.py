#!/usr/bin/env python3
"""
Start MCP Dashboard - Easy access to the IPFS Kit MCP Dashboard

This script provides easy access to the MCP dashboard that was moved during 
repository reorganization. It ensures the dashboard starts properly and is 
accessible on the expected port.

Usage:
    python start_mcp_dashboard.py [--port 8004] [--background]
"""

import argparse
import sys
import subprocess
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Start MCP Dashboard")
    parser.add_argument("--port", type=int, default=8004, help="Port to run dashboard on")
    parser.add_argument("--background", action="store_true", help="Run in background")
    args = parser.parse_args()
    
    # Find the dashboard file
    script_dir = Path(__file__).parent
    dashboard_paths = [
        script_dir / "scripts" / "development" / "consolidated_mcp_dashboard.py",
        script_dir / "dashboard.py",
        script_dir / "deprecated_dashboards" / "integrated_mcp_server_with_dashboard.py"
    ]
    
    dashboard_file = None
    for path in dashboard_paths:
        if path.exists():
            dashboard_file = path
            break
    
    if not dashboard_file:
        print("Error: Could not find MCP dashboard file")
        sys.exit(1)
    
    print(f"Starting MCP Dashboard: {dashboard_file}")
    print(f"Dashboard will be available at: http://127.0.0.1:{args.port}")
    print()
    
    # Set environment variable for port if needed
    env = os.environ.copy()
    env["MCP_DASHBOARD_PORT"] = str(args.port)
    
    # Run the dashboard
    if args.background:
        print("Starting in background...")
        proc = subprocess.Popen([
            sys.executable, str(dashboard_file)
        ], env=env)
        print(f"Dashboard started with PID: {proc.pid}")
    else:
        print("Starting in foreground (Ctrl+C to stop)...")
        subprocess.run([
            sys.executable, str(dashboard_file)
        ], env=env)

if __name__ == "__main__":
    main()