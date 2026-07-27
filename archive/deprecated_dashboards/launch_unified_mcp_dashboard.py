#!/usr/bin/env python3
"""
IPFS Kit MCP Dashboard Launcher
==============================

This script launches the unified MCP server with dashboard on a single port,
replacing the need for separate MCP server and dashboard processes.

Usage:
    python launch_unified_mcp_dashboard.py [--port 8083] [--host 127.0.0.1]
"""

import os
import sys
import subprocess
import argparse
import time
import signal
from pathlib import Path

def main():
    """Main launcher function"""
    parser = argparse.ArgumentParser(description="Launch Unified MCP Dashboard Server")
    parser.add_argument("--port", type=int, default=8083, help="Port to run on (default: 8083)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    print("🚀 IPFS Kit - Unified MCP Dashboard Server")
    print("=" * 50)
    print(f"Starting unified server on {args.host}:{args.port}")
    print()
    print("Features:")
    print("  📊 Web Dashboard Interface")
    print("  🔧 MCP Server JSON-RPC API")
    print("  🌐 Single Port Operation")
    print("  📡 JSON-RPC Communication")
    print()
    
    # Construct command
    script_path = Path(__file__).parent / "unified_mcp_dashboard_server.py"
    
    cmd = [sys.executable, str(script_path)]
    cmd.extend(["--host", args.host])
    cmd.extend(["--port", str(args.port)])
    
    if args.debug:
        cmd.append("--debug")
    
    print(f"Command: {' '.join(cmd)}")
    print()
    
    try:
        # Handle Ctrl+C gracefully
        def signal_handler(signum, frame):
            print("\n🛑 Shutting down server...")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start the unified server
        print("🔄 Starting server...")
        result = subprocess.run(cmd, check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Server failed to start: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
