#!/usr/bin/env python3
"""
Enhanced runner for the Modular Enhanced MCP Server.
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.abspath('.'))

from mcp.ipfs_kit.modular_enhanced_mcp_server import ModularEnhancedMCPServer

def main():
    """Main entry point for modular server with enhanced features."""
    
    parser = argparse.ArgumentParser(
        description="Modular Enhanced MCP Server with comprehensive backend monitoring"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--config-dir", default="/tmp/ipfs_kit_config", help="Configuration directory")
    parser.add_argument("--log-dir", default="/tmp/ipfs_kit_logs", help="Log directory")
    parser.add_argument("--no-monitoring", action="store_true", help="Disable backend monitoring")
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start server
    server = ModularEnhancedMCPServer(host=args.host, port=args.port)
    
    print("=" * 80)
    print("🚀 MODULAR ENHANCED MCP SERVER")
    print("=" * 80)
    print(f"📍 Host: {args.host}")
    print(f"🚪 Port: {args.port}")
    print(f"📁 Config: {args.config_dir}")
    print(f"� Logs: {args.log_dir}")
    print(f"�🔧 Debug: {args.debug}")
    print(f"🔍 Monitoring: {'Disabled' if args.no_monitoring else 'Enabled'}")
    print(f"🌐 Dashboard: http://{args.host}:{args.port}")
    print("=" * 80)
    
    server.start()

if __name__ == "__main__":
    main()
