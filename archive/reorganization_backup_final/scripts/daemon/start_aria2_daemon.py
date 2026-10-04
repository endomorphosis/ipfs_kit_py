#!/usr/bin/env python3
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

    python daemon_manager.py --daemons aria2 --start

The daemon manager supports multiple daemon types and operations.
"""

import sys
import os
import subprocess
import warnings
import argparse

def main():
    """Start Aria2 daemon using the new daemon_manager."""
    # Show deprecation warning
    warnings.warn(
        "start_aria2_daemon.py is deprecated and will be removed in a future version. "
        "Please use daemon_manager.py instead.",
        DeprecationWarning, stacklevel=2
    )
    
    print("Starting Aria2 daemon using the new daemon_manager module...")
    
    # Check if daemon_manager.py exists
    daemon_manager_path = os.path.join(os.path.dirname(__file__), "daemon_manager.py")
    if not os.path.exists(daemon_manager_path):
        print("ERROR: daemon_manager.py not found. Please make sure it's in the same directory.")
        return 1
    
    # Parse original arguments
    parser = argparse.ArgumentParser(description="Start Aria2 daemon for testing")
    parser.add_argument("--rpc-secret", help="RPC secret for Aria2 daemon", default="ipfs_kit_secret")
    parser.add_argument("--port", type=int, help="RPC port for Aria2 daemon", default=6800)
    parser.add_argument("--dir", help="Download directory", default="/tmp/aria2_downloads")
    args = parser.parse_args()
    
    # Build command for daemon_manager
    cmd = [
        sys.executable,
        daemon_manager_path,
        "--daemons", "aria2",
        "--start"
    ]
    
    # Run daemon_manager
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print("\n----------------------------------------------------------")
            print("Aria2 daemon is running successfully!")
            print("----------------------------------------------------------")
            print("To check daemon status: python daemon_manager.py --status")
            print("To stop the daemon: python daemon_manager.py --daemons aria2 --stop")
            print("----------------------------------------------------------\n")
            
        return result.returncode
    except KeyboardInterrupt:
        print("\nStopping Aria2 daemon startup...")
        return 0
    except Exception as e:
        print(f"Error running daemon manager: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())