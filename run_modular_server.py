#!/usr/bin/env python3

import sys
import os
import argparse
import logging

# Add current directory to Python path for imports
sys.path.insert(0, os.path.abspath('.'))

from mcp.ipfs_kit.modular_enhanced_mcp_server import ModularEnhancedMCPServer

def main():
    """Main entry point for modular server."""
    
    parser = argparse.ArgumentParser(description="Modular Enhanced MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--config-dir", default="/tmp/ipfs_kit_config", help="Configuration directory")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start server
    server = ModularEnhancedMCPServer(host=args.host, port=args.port)
    
    print("=" * 60)
    print("🚀 MODULAR ENHANCED MCP SERVER")
    print("=" * 60)
    print(f"📍 Host: {args.host}")
    print(f"🚪 Port: {args.port}")
    print(f"📁 Config: {args.config_dir}")
    print(f"🔧 Debug: {args.debug}")
    print("=" * 60)
    
    server.start()

if __name__ == "__main__":
    main()
