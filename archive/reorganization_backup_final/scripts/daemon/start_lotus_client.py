#!/usr/bin/env python
"""
DEPRECATED: This script has been replaced by daemon_manager.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

"""
DEPRECATED: This script has been replaced by daemon_manager.py

This file is kept for backward compatibility. Please use the unified daemon manager instead,
which provides comprehensive daemon management capabilities:

    python daemon_manager.py --daemons lotus --start

The daemon manager supports multiple daemon types and operations.
"""

import sys
import os
import subprocess
import warnings
import argparse

def main():
    """Start Lotus client using the new daemon_manager."""
    # Show deprecation warning
    warnings.warn(
        "start_lotus_client.py is deprecated and will be removed in a future version. "
        "Please use daemon_manager.py instead.",
        DeprecationWarning, stacklevel=2
    )
    
    print("Starting Lotus client using the new daemon_manager module...")
    
    # Check if daemon_manager.py exists
    daemon_manager_path = os.path.join(os.path.dirname(__file__), "daemon_manager.py")
    if not os.path.exists(daemon_manager_path):
        print("ERROR: daemon_manager.py not found. Please make sure it's in the same directory.")
        return 1
    
    # Parse original arguments to maintain compatibility
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
    
    # Various commands that we won't need to implement in detail for the deprecation notice
    for cmd in ["wallet_list", "peers", "chain_head", "miners", "deals", "version", 
                "daemon_status", "daemon_start", "daemon_stop"]:
        subparsers.add_parser(cmd, help=f"{cmd} command")
    
    # Output format
    parser.add_argument("--json", action="store_true", 
                        help="Output in JSON format")
    parser.add_argument("--pretty", action="store_true", 
                        help="Pretty print JSON output")
    
    # Debug options
    parser.add_argument("--debug", action="store_true", 
                        help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Build command for daemon_manager based on the command provided
    cmd = [
        sys.executable,
        daemon_manager_path,
        "--daemons", "lotus"
    ]
    
    # Map the original command to daemon_manager actions
    if args.command == "daemon_start" or not args.command:
        cmd.append("--start")
    elif args.command == "daemon_stop":
        cmd.append("--stop")
    elif args.command == "daemon_status" or args.command in ["wallet_list", "peers", "chain_head", "miners", "deals", "version"]:
        cmd.append("--status")
    
    # Add --lite-mode if not disabled
    if not args.disable_lite:
        cmd.append("--lite-mode")
    
    # Run daemon_manager
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print("\n----------------------------------------------------------")
            print("Lotus client operation completed successfully!")
            print("----------------------------------------------------------")
            print("To check daemon status: python daemon_manager.py --status")
            print("To stop the daemon: python daemon_manager.py --daemons lotus --stop")
            print("----------------------------------------------------------\n")
            
        return result.returncode
    except KeyboardInterrupt:
        print("\nStopping Lotus client operation...")
        return 0
    except Exception as e:
        print(f"Error running daemon manager: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())