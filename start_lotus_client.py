#!/usr/bin/env python
"""
Lotus Client Runner with Auto-Daemon Management

This script creates a simple Lotus client with automatic daemon management
and provides a command-line interface for common Lotus operations.

It demonstrates the auto-daemon capability, automatically starting the daemon
when needed and ensuring it stays running during operations.
"""

import argparse
import json
import logging
import os
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("lotus_client")

# Add the bin directory to PATH explicitly
bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
os.environ["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"
os.environ["LOTUS_BIN"] = os.path.join(bin_dir, "lotus")

# Remove environment variable if it exists to allow actual daemon startup
if "LOTUS_SKIP_DAEMON_LAUNCH" in os.environ:
    del os.environ["LOTUS_SKIP_DAEMON_LAUNCH"]

# Import Lotus components
from ipfs_kit_py.lotus_kit import lotus_kit, LOTUS_AVAILABLE

def create_client(use_simulation=None, custom_path=None, lite_mode=True):
    """Create a Lotus client instance with auto-daemon management.
    
    Args:
        use_simulation (bool, optional): Force simulation mode on/off. 
            If None, auto-detect based on Lotus availability.
        custom_path (str, optional): Custom path for Lotus repo.
        lite_mode (bool): Use lite mode for faster startup.
        
    Returns:
        lotus_kit: Configured Lotus client
    """
    # Determine simulation mode if not explicitly set
    if use_simulation is None:
        use_simulation = not LOTUS_AVAILABLE
        if not LOTUS_AVAILABLE:
            logger.warning("Lotus binary not available - using simulation mode")
    
    # Set up metadata for client creation
    metadata = {
        "auto_start_daemon": True,       # Always enable auto-daemon management
        "simulation_mode": use_simulation,
        "lite": lite_mode,               # Lite mode for faster startup
        "daemon_flags": {            
            "bootstrap": False,          # Skip bootstrap for faster startup
        },
        "daemon_startup_timeout": 60,    # Give daemon time to start
        "daemon_health_check_interval": 30,  # Check daemon health frequently
    }
    
    # Debug log the configuration
    logger.debug("Creating Lotus client with configuration:")
    logger.debug(f"  - auto_start_daemon: {metadata['auto_start_daemon']}")
    logger.debug(f"  - simulation_mode: {metadata['simulation_mode']}")
    logger.debug(f"  - lite_mode: {metadata['lite']}")
    logger.debug(f"  - Lotus binary available: {LOTUS_AVAILABLE}")
    
    # Verify LOTUS_SKIP_DAEMON_LAUNCH environment variable
    skip_env = os.environ.get("LOTUS_SKIP_DAEMON_LAUNCH")
    logger.debug(f"  - LOTUS_SKIP_DAEMON_LAUNCH env: {skip_env if skip_env else 'Not set'}")
    
    # Add custom path if specified
    if custom_path:
        custom_path = os.path.abspath(os.path.expanduser(custom_path))
        metadata["lotus_path"] = custom_path
        logger.info(f"Using custom Lotus path: {custom_path}")
        os.makedirs(custom_path, exist_ok=True)
    
    # Create client
    return lotus_kit(metadata=metadata)

def check_daemon_status(client):
    """Check and report daemon status."""
    try:
        status = client.daemon_status()
        if status.get("process_running", False):
            pid = status.get("pid", "unknown")
            logger.info(f"Daemon running with PID {pid}")
        else:
            logger.info("Daemon not running")
        
        return status
    except Exception as e:
        logger.error(f"Error checking daemon status: {str(e)}")
        return {"success": False, "error": str(e)}

def run_command(client, command, args):
    """Run a Lotus command with arguments."""
    start_time = time.time()
    result = None
    
    try:
        # Check daemon status before command if not a daemon management command
        if command not in ("daemon_status", "daemon_start", "daemon_stop"):
            logger.debug(f"Checking daemon status before executing '{command}'")
            daemon_status = client.daemon_status()
            daemon_running = daemon_status.get("process_running", False)
            
            if not daemon_running and client.auto_start_daemon:
                logger.info("Daemon not running, auto-start will be triggered by API call")
        
        # Route the command to the appropriate method
        if command == "wallet_list":
            result = client.list_wallets()
        elif command == "peers":
            result = client.net_peers()
        elif command == "chain_head":
            result = client.get_chain_head()
        elif command == "miners":
            result = client.list_miners()
        elif command == "deals":
            result = client.client_list_deals()
        elif command == "version":
            result = client.check_connection()
        elif command == "daemon_status":
            result = check_daemon_status(client)
        elif command == "daemon_start":
            result = client.daemon_start()
        elif command == "daemon_stop":
            force = getattr(args, "force", False)
            result = client.daemon_stop(force=force)
        else:
            raise ValueError(f"Unknown command: {command}")
        
        # Check if daemon auto-started during the command
        if command not in ("daemon_status", "daemon_start", "daemon_stop"):
            logger.debug(f"Checking if daemon was auto-started during '{command}'")
            new_status = client.daemon_status()
            new_daemon_running = new_status.get("process_running", False)
            
            if new_daemon_running and not daemon_running:
                logger.info("Daemon was automatically started during the operation")
                result["daemon_auto_started"] = True
        
        # Calculate execution time
        elapsed = time.time() - start_time
        
        # Add timing information
        if result:
            result["elapsed_seconds"] = elapsed
        
        return result
    
    except Exception as e:
        logger.error(f"Error executing command '{command}': {str(e)}")
        
        # Try to determine if it was a daemon-related error
        if "daemon not running" in str(e).lower() or "connection refused" in str(e).lower():
            logger.error("The error appears to be related to daemon connectivity")
            
            # Check daemon status to confirm
            try:
                daemon_status = client.daemon_status()
                if not daemon_status.get("process_running", False):
                    logger.error("Confirmed: Daemon is not running")
                else:
                    logger.error("Daemon is running but may not be ready or accessible")
            except Exception as status_error:
                logger.error(f"Error checking daemon status: {status_error}")
        
        return {"success": False, "error": str(e), "elapsed_seconds": time.time() - start_time}

def main():
    """Main function to parse arguments and execute commands."""
    parser = argparse.ArgumentParser(
        description="Lotus Client Runner with Auto-Daemon Management")
    
    # Client configuration
    parser.add_argument("--simulate", action="store_true", 
                        help="Force simulation mode")
    parser.add_argument("--no-simulate", action="store_true", 
                        help="Disable simulation mode (force real daemon)")
    parser.add_argument("--lotus-path", type=str, 
                        help="Custom path for Lotus repo")
    parser.add_argument("--disable-lite", action="store_true", 
                        help="Disable lite mode (for full node functionality)")
    
    # Command selection
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Wallet commands
    wallet_parser = subparsers.add_parser("wallet_list", help="List wallets")
    
    # Network commands
    peers_parser = subparsers.add_parser("peers", help="List network peers")
    
    # Chain commands
    chain_parser = subparsers.add_parser("chain_head", help="Get chain head")
    
    # Storage provider commands
    miners_parser = subparsers.add_parser("miners", help="List miners")
    
    # Deals commands
    deals_parser = subparsers.add_parser("deals", help="List client deals")
    
    # System commands
    version_parser = subparsers.add_parser("version", help="Check Lotus version")
    
    # Daemon commands
    daemon_status_parser = subparsers.add_parser("daemon_status", help="Check daemon status")
    daemon_start_parser = subparsers.add_parser("daemon_start", help="Start the daemon")
    daemon_stop_parser = subparsers.add_parser("daemon_stop", help="Stop the daemon")
    daemon_stop_parser.add_argument("--force", action="store_true", help="Force stop with SIGKILL")
    
    # Output format
    parser.add_argument("--json", action="store_true", 
                        help="Output in JSON format")
    parser.add_argument("--pretty", action="store_true", 
                        help="Pretty print JSON output")
    
    # Debug options
    parser.add_argument("--debug", action="store_true", 
                        help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine simulation mode
    use_simulation = None  # Auto-detect
    if args.simulate:
        use_simulation = True
    elif args.no_simulate:
        use_simulation = False
    
    # Create client
    client = create_client(
        use_simulation=use_simulation,
        custom_path=args.lotus_path,
        lite_mode=not args.disable_lite
    )
    
    # If no command specified, show help
    if not args.command:
        parser.print_help()
        return
    
    # Execute command
    result = run_command(client, args.command, args)
    
    # Display result
    if args.json or args.pretty:
        if args.pretty:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(json.dumps(result))
    else:
        # Human-readable format
        print(f"\nCommand: {args.command}")
        print(f"Success: {result.get('success', False)}")
        print(f"Time: {result.get('elapsed_seconds', 0):.3f} seconds")
        
        if result.get("simulated", False):
            print("Mode: SIMULATION")
        
        if "error" in result:
            print(f"Error: {result['error']}")
        
        # Display result details based on command
        if args.command == "wallet_list" and "result" in result:
            print("\nWallets:")
            for wallet in result["result"]:
                print(f"  {wallet}")
        
        elif args.command == "peers" and "result" in result:
            print(f"\nPeers: {len(result.get('result', []))}")
            for peer in result.get("result", [])[:5]:  # Show first 5 peers
                addr = peer.get("Addr", "unknown")
                peer_id = peer.get("ID", "unknown")
                print(f"  {peer_id} - {addr}")
            if len(result.get("result", [])) > 5:
                print(f"  ... and {len(result.get('result', [])) - 5} more")
        
        elif args.command == "miners" and "result" in result:
            print(f"\nMiners: {len(result.get('result', []))}")
            for miner in result.get("result", [])[:5]:  # Show first 5 miners
                print(f"  {miner}")
            if len(result.get("result", [])) > 5:
                print(f"  ... and {len(result.get('result', [])) - 5} more")
        
        elif args.command == "deals" and "result" in result:
            deals = result.get("result", [])
            print(f"\nDeals: {len(deals)}")
            for deal in deals[:3]:  # Show first 3 deals
                provider = deal.get("Provider", "unknown")
                piece_cid = deal.get("PieceCID", {"/":" unknown"}).get("/", "unknown")
                state = deal.get("State", "unknown")
                print(f"  Provider: {provider}, State: {state}")
                print(f"  Piece CID: {piece_cid}")
                print()
            if len(deals) > 3:
                print(f"  ... and {len(deals) - 3} more")
        
        elif args.command == "daemon_status":
            print("\nDaemon Status:")
            if result.get("process_running", False):
                print(f"  PID: {result.get('pid', 'unknown')}")
                daemon_info = result.get("daemon_info", {})
                if daemon_info.get("api_responding", False):
                    print("  API: Responding")
                else:
                    print("  API: Not responding")
                
                if "api_socket_exists" in daemon_info:
                    print(f"  API Socket: {'Exists' if daemon_info['api_socket_exists'] else 'Missing'}")
                if "repo_lock_exists" in daemon_info:
                    print(f"  Repo Lock: {'Exists' if daemon_info['repo_lock_exists'] else 'Missing'}")
            else:
                print("  Status: Not running")

if __name__ == "__main__":
    main()