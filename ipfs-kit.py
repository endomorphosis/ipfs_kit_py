#!/usr/bin/env python3
"""
IPFS Kit Command Line Interface

A simplified CLI for IPFS Kit with common operations.
"""

import argparse
import sys
import os
import logging
from pathlib import Path

# Ensure the package is in the Python path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ipfs_kit_cli")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="IPFS Kit CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add a file to IPFS")
    add_parser.add_argument("path", help="Path to file or directory to add")
    add_parser.add_argument("--recursive", "-r", action="store_true", help="Add directory recursively")
    add_parser.add_argument("--wrap", "-w", action="store_true", help="Wrap files with directory")
    
    # Cat command
    cat_parser = subparsers.add_parser("cat", help="Retrieve the contents of a file from IPFS")
    cat_parser.add_argument("cid", help="Content ID to retrieve")
    cat_parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    
    # Pin command
    pin_parser = subparsers.add_parser("pin", help="Pin content to local storage")
    pin_parser.add_argument("cid", help="Content ID to pin")
    
    # Daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Manage IPFS daemon")
    daemon_parser.add_argument("action", choices=["start", "stop", "status"], help="Daemon action")
    
    # Server command
    server_parser = subparsers.add_parser("server", help="Run the MCP server")
    server_parser.add_argument("--port", type=int, default=9990, help="Port to run the server on")
    server_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    
    # Config command
    config_parser = subparsers.add_parser("config", help="Manage IPFS Kit configuration")
    config_parser.add_argument("action", choices=["show", "init", "edit"], help="Config action")
    
    # Debug command
    debug_parser = subparsers.add_parser("debug", help="Run diagnostic tests")
    debug_parser.add_argument("--all", action="store_true", help="Run all tests")
    
    return parser.parse_args()

def main():
    """Main CLI entry point."""
    args = parse_args()
    
    if not args.command:
        print("Error: No command specified")
        print("Run with --help for usage information")
        return 1
    
    try:
        # Import APIs after we've handled --help cases
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
        
        # Create API instance
        api = IPFSSimpleAPI()
        
        # Execute command
        if args.command == "add":
            handle_add(api, args)
        elif args.command == "cat":
            handle_cat(api, args)
        elif args.command == "pin":
            handle_pin(api, args)
        elif args.command == "daemon":
            handle_daemon(api, args)
        elif args.command == "server":
            handle_server(args)
        elif args.command == "config":
            handle_config(args)
        elif args.command == "debug":
            handle_debug(api, args)
        else:
            print(f"Error: Unknown command '{args.command}'")
            return 1
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130
    except Exception as e:
        print(f"Error: {e}")
        if "--debug" in sys.argv:
            import traceback
            traceback.print_exc()
        return 1
    
    return 0

def handle_add(api, args):
    """Handle 'add' command."""
    print(f"Adding {args.path}...")
    result = api.add(args.path, recursive=args.recursive, wrap=args.wrap)
    if "Hash" in result:
        print(f"Added {result['Hash']}")
    elif "cid" in result:
        print(f"Added {result['cid']}")
    else:
        print(f"Added: {result}")
    return 0

def handle_cat(api, args):
    """Handle 'cat' command."""
    content = api.cat(args.cid)
    if args.output:
        with open(args.output, "wb") as f:
            f.write(content)
        print(f"Content written to {args.output}")
    else:
        # Try to decode as text, fall back to binary if it fails
        try:
            print(content.decode("utf-8"))
        except UnicodeDecodeError:
            print("Binary content (not displayed)")
    return 0

def handle_pin(api, args):
    """Handle 'pin' command."""
    print(f"Pinning {args.cid}...")
    result = api.pin_add(args.cid)
    print(f"Pinned: {result}")
    return 0

def handle_daemon(api, args):
    """Handle 'daemon' command."""
    if args.action == "start":
        print("Starting IPFS daemon...")
        api.start_daemon()
        print("Daemon started")
    elif args.action == "stop":
        print("Stopping IPFS daemon...")
        api.stop_daemon()
        print("Daemon stopped")
    elif args.action == "status":
        status = api.daemon_status()
        if status.get("running", False):
            print("IPFS daemon is running")
        else:
            print("IPFS daemon is not running")
    return 0

def handle_server(args):
    """Handle 'server' command."""
    from ipfs_kit_py.mcp.server import MCPServer
    
    print(f"Starting MCP server on http://{args.host}:{args.port}")
    server = MCPServer(host=args.host, port=args.port)
    server.start()
    return 0

def handle_config(args):
    """Handle 'config' command."""
    import json
    import tempfile
    import subprocess
    from ipfs_kit_py.high_level_api import DEFAULT_CONFIG_PATH
    
    if args.action == "show":
        try:
            with open(DEFAULT_CONFIG_PATH, "r") as f:
                config = json.load(f)
            print(json.dumps(config, indent=2))
        except FileNotFoundError:
            print(f"Config file not found at {DEFAULT_CONFIG_PATH}")
            print("Run 'ipfs-kit config init' to create it")
    elif args.action == "init":
        if os.path.exists(DEFAULT_CONFIG_PATH):
            print(f"Config file already exists at {DEFAULT_CONFIG_PATH}")
            response = input("Overwrite? (y/n): ")
            if response.lower() != "y":
                return 0
        
        # Create config dir if it doesn't exist
        os.makedirs(os.path.dirname(DEFAULT_CONFIG_PATH), exist_ok=True)
        
        # Copy example config
        example_path = os.path.join(root_dir, "config.json.example")
        if os.path.exists(example_path):
            with open(example_path, "r") as src, open(DEFAULT_CONFIG_PATH, "w") as dst:
                dst.write(src.read())
            print(f"Created config file at {DEFAULT_CONFIG_PATH}")
        else:
            print("Example config not found, creating minimal config")
            with open(DEFAULT_CONFIG_PATH, "w") as f:
                json.dump({
                    "ipfs": {"auto_start": True},
                    "logging": {"level": "info"}
                }, f, indent=2)
            print(f"Created minimal config at {DEFAULT_CONFIG_PATH}")
    elif args.action == "edit":
        if not os.path.exists(DEFAULT_CONFIG_PATH):
            print(f"Config file not found at {DEFAULT_CONFIG_PATH}")
            print("Run 'ipfs-kit config init' to create it")
            return 1
        
        # Determine editor
        editor = os.environ.get("EDITOR", "nano")
        
        # Open config in editor
        subprocess.run([editor, DEFAULT_CONFIG_PATH])
        print(f"Config file edited at {DEFAULT_CONFIG_PATH}")
    return 0

def handle_debug(api, args):
    """Handle 'debug' command."""
    print("Running diagnostics...")
    
    # Check IPFS daemon
    print("\nIPFS Daemon:")
    try:
        status = api.daemon_status()
        if status.get("running", False):
            print("✅ IPFS daemon is running")
        else:
            print("❌ IPFS daemon is not running")
    except Exception as e:
        print(f"❌ Error checking daemon status: {e}")
    
    # Check version info
    print("\nVersion Info:")
    try:
        version = api.version()
        print(f"✅ IPFS version: {version}")
    except Exception as e:
        print(f"❌ Error getting version: {e}")
    
    # Check peer info
    print("\nPeer Info:")
    try:
        peer_id = api.id()
        print(f"✅ Peer ID: {peer_id.get('ID', 'unknown')}")
    except Exception as e:
        print(f"❌ Error getting peer info: {e}")
    
    # If --all flag is set, run more extensive tests
    if args.all:
        print("\nAdditional Tests:")
        
        # Test add/cat
        try:
            # Create temp file
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(b"Hello IPFS!")
                temp_path = f.name
            
            # Add file
            add_result = api.add(temp_path)
            if "Hash" in add_result:
                cid = add_result["Hash"]
            elif "cid" in add_result:
                cid = add_result["cid"]
            else:
                cid = None
            
            if cid:
                print(f"✅ Added test file with CID: {cid}")
                
                # Cat file
                content = api.cat(cid)
                if content == b"Hello IPFS!":
                    print("✅ Successfully retrieved test file")
                else:
                    print("❌ Retrieved content does not match")
            else:
                print("❌ Failed to add test file")
                
            # Clean up
            os.unlink(temp_path)
        except Exception as e:
            print(f"❌ Error in add/cat test: {e}")
    
    print("\nDiagnostics complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())