#!/usr/bin/env python3
"""
Refactored IPFS-Kit CLI Tool

A lightweight CLI tool that delegates backend management to the IPFS-Kit daemon
while providing direct access to IPFS-Kit libraries for retrieval operations
and reading from parquet indexes for routing decisions.

Usage:
    ipfs-kit-cli daemon start                    # Start the daemon
    ipfs-kit-cli daemon stop                     # Stop the daemon  
    ipfs-kit-cli daemon status                   # Get daemon status
    ipfs-kit-cli backend list                    # List backend health
    ipfs-kit-cli backend restart <name>          # Restart a backend
    ipfs-kit-cli ipfs cat <cid>                  # Retrieve content (direct IPFS Kit)
    ipfs-kit-cli ipfs add <file>                 # Add content (direct IPFS Kit)
    ipfs-kit-cli route find <cid>                # Find backends for CID (parquet index)
    ipfs-kit-cli route suggest                   # Suggest backend for new pin
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import daemon client
try:
    from ipfs_kit_daemon_client import daemon_client, route_reader
    DAEMON_CLIENT_AVAILABLE = True
except ImportError as e:
    logger.error(f"Daemon client not available: {e}")
    DAEMON_CLIENT_AVAILABLE = False
    daemon_client = None
    route_reader = None

# Import IPFS Kit for direct operations
try:
    from ipfs_kit_py.ipfs_kit import IPFSKit
    IPFS_KIT_AVAILABLE = True
except ImportError as e:
    logger.error(f"IPFS Kit not available: {e}")
    IPFS_KIT_AVAILABLE = False


class IPFSKitCLI:
    """
    Lightweight CLI tool for IPFS-Kit that uses daemon for management
    and direct IPFS-Kit access for retrieval operations.
    """
    
    def __init__(self):
        self.ipfs_kit = None
        self._initialize_ipfs_kit()
    
    def _initialize_ipfs_kit(self):
        """Initialize IPFS Kit for direct retrieval operations."""
        if IPFS_KIT_AVAILABLE:
            try:
                # Initialize without auto-starting daemons - that's the daemon's job
                config = {"auto_start_daemons": False}
                self.ipfs_kit = IPFSKit(config)
                logger.debug("IPFS Kit initialized for retrieval operations")
            except Exception as e:
                logger.warning(f"IPFS Kit initialization failed: {e}")
                self.ipfs_kit = None
    
    # Daemon management commands
    
    async def daemon_start(self) -> Dict[str, Any]:
        """Start the IPFS-Kit daemon."""
        if not DAEMON_CLIENT_AVAILABLE or not daemon_client:
            return {"error": "Daemon client not available"}
        
        result = await daemon_client.start_daemon()
        return result
    
    async def daemon_stop(self) -> Dict[str, Any]:
        """Stop the IPFS-Kit daemon."""
        if not DAEMON_CLIENT_AVAILABLE or not daemon_client:
            return {"error": "Daemon client not available"}
        
        result = await daemon_client.stop_daemon()
        return result
    
    async def daemon_status(self) -> Dict[str, Any]:
        """Get daemon status."""
        if not DAEMON_CLIENT_AVAILABLE or not daemon_client:
            return {"error": "Daemon client not available"}
        
        status = await daemon_client.get_daemon_status()
        return status
    
    # Backend management commands
    
    async def backend_list(self) -> Dict[str, Any]:
        """List backend health status."""
        if not DAEMON_CLIENT_AVAILABLE or not daemon_client:
            return {"error": "Daemon client not available"}
        
        health = await daemon_client.get_backend_health()
        return health
    
    async def backend_restart(self, backend_name: str) -> Dict[str, Any]:
        """Restart a specific backend."""
        if not DAEMON_CLIENT_AVAILABLE or not daemon_client:
            return {"error": "Daemon client not available"}
        
        result = await daemon_client.restart_backend(backend_name)
        return result
    
    # IPFS operations (direct IPFS Kit usage)
    
    def ipfs_cat(self, cid: str) -> Dict[str, Any]:
        """Retrieve content from IPFS."""
        if not self.ipfs_kit:
            return {"error": "IPFS Kit not available"}
        
        try:
            # Use the proper IPFS Kit method
            if hasattr(self.ipfs_kit, 'ipfs'):
                result = self.ipfs_kit.ipfs.cat(cid)
            else:
                # Try direct call
                result = self.ipfs_kit(operation="cat", cid=cid)
            return {"success": True, "content": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def ipfs_add(self, file_path: str) -> Dict[str, Any]:
        """Add file to IPFS."""
        if not self.ipfs_kit:
            return {"error": "IPFS Kit not available"}
        
        try:
            if not os.path.exists(file_path):
                return {"success": False, "error": f"File not found: {file_path}"}
            
            # Use the proper IPFS Kit method
            if hasattr(self.ipfs_kit, 'ipfs'):
                result = self.ipfs_kit.ipfs.add(file_path)
            else:
                result = self.ipfs_kit(operation="add", file_path=file_path)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def ipfs_add_str(self, content: str) -> Dict[str, Any]:
        """Add string content to IPFS."""
        if not self.ipfs_kit:
            return {"error": "IPFS Kit not available"}
        
        try:
            # Use the proper IPFS Kit method
            if hasattr(self.ipfs_kit, 'ipfs'):
                result = self.ipfs_kit.ipfs.add_str(content)
            else:
                result = self.ipfs_kit(operation="add_str", content=content)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def ipfs_stat(self, cid: str) -> Dict[str, Any]:
        """Get IPFS object statistics."""
        if not self.ipfs_kit:
            return {"error": "IPFS Kit not available"}
        
        try:
            # Use the proper IPFS Kit method
            if hasattr(self.ipfs_kit, 'ipfs'):
                result = self.ipfs_kit.ipfs.ipfs_stat_path(cid)
            else:
                result = self.ipfs_kit(operation="stat", cid=cid)
            return {"success": True, "stats": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def ipfs_id(self) -> Dict[str, Any]:
        """Get IPFS node ID."""
        if not self.ipfs_kit:
            return {"error": "IPFS Kit not available"}
        
        try:
            # Use the proper IPFS Kit method
            if hasattr(self.ipfs_kit, 'ipfs'):
                result = self.ipfs_kit.ipfs.ipfs_id()
            else:
                result = self.ipfs_kit(operation="id")
            return {"success": True, "id": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Routing operations (direct parquet index access)
    
    def route_find(self, cid: str) -> Dict[str, Any]:
        """Find which backends have a specific CID."""
        if not route_reader:
            return {"error": "Route reader not available"}
        
        try:
            backends = route_reader.find_backends_for_cid(cid)
            return {"cid": cid, "backends": backends}
        except Exception as e:
            return {"error": str(e)}
    
    def route_suggest(self) -> Dict[str, Any]:
        """Suggest best backend for new pin."""
        if not route_reader:
            return {"error": "Route reader not available"}
        
        try:
            backend = route_reader.suggest_backend_for_new_pin()
            stats = route_reader.get_backend_stats()
            return {
                "suggested_backend": backend,
                "backend_stats": stats
            }
        except Exception as e:
            return {"error": str(e)}
    
    def route_stats(self) -> Dict[str, Any]:
        """Get backend statistics from routing index."""
        if not route_reader:
            return {"error": "Route reader not available"}
        
        try:
            stats = route_reader.get_backend_stats()
            return {"backend_stats": stats}
        except Exception as e:
            return {"error": str(e)}


def print_json(data: Dict[str, Any], indent: int = 2):
    """Pretty print JSON data."""
    print(json.dumps(data, indent=indent, default=str))


def print_status(result: Dict[str, Any]):
    """Print operation status in a user-friendly way."""
    if result.get("success"):
        print("✅ Success")
        if "message" in result:
            print(f"   {result['message']}")
    elif result.get("error"):
        print("❌ Error")
        print(f"   {result['error']}")
    else:
        print("ℹ️  Status")
    
    # Print additional details
    for key, value in result.items():
        if key not in ["success", "error", "message"]:
            if isinstance(value, (dict, list)):
                print(f"   {key}:")
                print(json.dumps(value, indent=4, default=str))
            else:
                print(f"   {key}: {value}")


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="IPFS-Kit CLI Tool with daemon-based architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ipfs-kit-cli daemon start
  ipfs-kit-cli daemon status
  ipfs-kit-cli backend list
  ipfs-kit-cli backend restart ipfs
  ipfs-kit-cli ipfs cat QmHash...
  ipfs-kit-cli ipfs add myfile.txt
  ipfs-kit-cli route find QmHash...
  ipfs-kit-cli route suggest
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Daemon commands
    daemon_parser = subparsers.add_parser("daemon", help="Daemon management")
    daemon_subparsers = daemon_parser.add_subparsers(dest="daemon_action")
    
    daemon_subparsers.add_parser("start", help="Start the daemon")
    daemon_subparsers.add_parser("stop", help="Stop the daemon")
    daemon_subparsers.add_parser("status", help="Get daemon status")
    
    # Backend commands
    backend_parser = subparsers.add_parser("backend", help="Backend management")
    backend_subparsers = backend_parser.add_subparsers(dest="backend_action")
    
    backend_subparsers.add_parser("list", help="List backend health")
    restart_parser = backend_subparsers.add_parser("restart", help="Restart a backend")
    restart_parser.add_argument("name", help="Backend name to restart")
    
    # IPFS commands
    ipfs_parser = subparsers.add_parser("ipfs", help="IPFS operations")
    ipfs_subparsers = ipfs_parser.add_subparsers(dest="ipfs_action")
    
    cat_parser = ipfs_subparsers.add_parser("cat", help="Retrieve content")
    cat_parser.add_argument("cid", help="Content ID to retrieve")
    
    add_parser = ipfs_subparsers.add_parser("add", help="Add file to IPFS")
    add_parser.add_argument("file", help="File path to add")
    
    add_str_parser = ipfs_subparsers.add_parser("add-str", help="Add string to IPFS")
    add_str_parser.add_argument("content", help="String content to add")
    
    stat_parser = ipfs_subparsers.add_parser("stat", help="Get object statistics")
    stat_parser.add_argument("cid", help="Content ID to stat")
    
    ipfs_subparsers.add_parser("id", help="Get IPFS node ID")
    
    # Route commands
    route_parser = subparsers.add_parser("route", help="Routing operations")
    route_subparsers = route_parser.add_subparsers(dest="route_action")
    
    find_parser = route_subparsers.add_parser("find", help="Find backends for CID")
    find_parser.add_argument("cid", help="Content ID to find")
    
    route_subparsers.add_parser("suggest", help="Suggest backend for new pin")
    route_subparsers.add_parser("stats", help="Get backend statistics")
    
    # Global options
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize CLI
    cli = IPFSKitCLI()
    
    result = None
    
    try:
        # Handle commands
        if args.command == "daemon":
            if args.daemon_action == "start":
                result = await cli.daemon_start()
            elif args.daemon_action == "stop":
                result = await cli.daemon_stop()
            elif args.daemon_action == "status":
                result = await cli.daemon_status()
            else:
                daemon_parser.print_help()
                return
        
        elif args.command == "backend":
            if args.backend_action == "list":
                result = await cli.backend_list()
            elif args.backend_action == "restart":
                result = await cli.backend_restart(args.name)
            else:
                backend_parser.print_help()
                return
        
        elif args.command == "ipfs":
            if args.ipfs_action == "cat":
                result = cli.ipfs_cat(args.cid)
            elif args.ipfs_action == "add":
                result = cli.ipfs_add(args.file)
            elif args.ipfs_action == "add-str":
                result = cli.ipfs_add_str(args.content)
            elif args.ipfs_action == "stat":
                result = cli.ipfs_stat(args.cid)
            elif args.ipfs_action == "id":
                result = cli.ipfs_id()
            else:
                ipfs_parser.print_help()
                return
        
        elif args.command == "route":
            if args.route_action == "find":
                result = cli.route_find(args.cid)
            elif args.route_action == "suggest":
                result = cli.route_suggest()
            elif args.route_action == "stats":
                result = cli.route_stats()
            else:
                route_parser.print_help()
                return
        
        else:
            parser.print_help()
            return
        
        # Output result
        if result:
            if args.json:
                print_json(result)
            else:
                print_status(result)
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        if args.debug:
            import traceback
            traceback.print_exc()
        else:
            print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
