#!/usr/bin/env python3
"""
Simple CLI for IPFS-Kit MCP operations - bypasses problematic imports
"""

import argparse
import anyio
import sys
from pathlib import Path

def create_simple_parser():
    """Create a minimal parser for MCP operations."""
    parser = argparse.ArgumentParser(description='IPFS-Kit MCP CLI')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # MCP commands
    mcp_parser = subparsers.add_parser('mcp', help='MCP server management')
    mcp_subparsers = mcp_parser.add_subparsers(dest='mcp_action', help='MCP actions')
    
    # MCP start
    start_parser = mcp_subparsers.add_parser('start', help='Start MCP server and dashboard')
    start_parser.add_argument('--port', type=int, default=8004, help='Port for MCP server (default: 8004)')
    start_parser.add_argument('--host', default='127.0.0.1', help='Host for MCP server (default: 127.0.0.1)')
    start_parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    # MCP stop
    stop_parser = mcp_subparsers.add_parser('stop', help='Stop MCP server and dashboard')
    
    # MCP status
    status_parser = mcp_subparsers.add_parser('status', help='Check MCP server status')
    
    return parser

async def handle_mcp_command(args):
    """Handle MCP commands with minimal dependencies."""
    try:
        # Import standalone MCP manager (not the full one)
        from standalone_mcp_manager import StandaloneMCPManager
        mcp_manager = StandaloneMCPManager()
    except ImportError as e:
        print(f"❌ Failed to import StandaloneMCPManager: {e}")
        return 1
        
    if args.mcp_action == 'start':
        print("🚀 Starting integrated MCP server + dashboard...")
        try:
            # The start_server method now handles integrated mode
            success = mcp_manager.start_server(
                host=args.host,
                port=args.port,
                debug=args.debug
            )
            if not success:
                print("❌ Failed to start integrated MCP server")
                return 1
        except Exception as e:
            print(f"❌ Failed to start MCP services: {e}")
            return 1
            
    elif args.mcp_action == 'stop':
        print("🛑 Stopping integrated MCP server + dashboard...")
        try:
            mcp_manager.stop_server()
            # No need to stop dashboard separately in integrated mode
        except Exception as e:
            print(f"❌ Failed to stop MCP services: {e}")
            return 1
            
    elif args.mcp_action == 'status':
        print("📊 Checking MCP server status...")
        try:
            server_status = mcp_manager.get_server_status()
            dashboard_status = mcp_manager.get_dashboard_status()
            
            print(f"MCP Server: {server_status['status']} - {server_status['details']}")
            print(f"Dashboard: {dashboard_status['status']} - {dashboard_status['details']}")
        except Exception as e:
            print(f"❌ Failed to get MCP status: {e}")
            return 1
    
    return 0

async def simple_main():
    """Simple main function."""
    parser = create_simple_parser()
    args = parser.parse_args()
    
    if args.command == 'mcp':
        return await handle_mcp_command(args)
    else:
        print("❌ No valid command specified. Use --help for usage information.")
        return 1

def simple_sync_main():
    """Synchronous entry point."""
    return anyio.run(simple_main)

if __name__ == '__main__':
    sys.exit(simple_sync_main())
