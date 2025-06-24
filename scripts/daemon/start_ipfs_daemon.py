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
which provides comprehensive daemon management for IPFS and other daemons:

    python daemon_manager.py --daemons ipfs --start

The daemon manager supports starting, stopping, checking status, and monitoring multiple daemon types.
"""

import sys
import os
import subprocess
import warnings

def main():
    """Start IPFS daemon using the new daemon_manager."""
    # Show deprecation warning
    warnings.warn(
        "start_ipfs_daemon.py is deprecated and will be removed in a future version. "
        "Please use daemon_manager.py instead.",
        DeprecationWarning, stacklevel=2
    )

    print("Starting IPFS daemon using the new daemon_manager module...")

    # Check if daemon_manager.py exists
    daemon_manager_path = os.path.join(os.path.dirname(__file__), "daemon_manager.py")
    if not os.path.exists(daemon_manager_path):
        print("ERROR: daemon_manager.py not found. Please make sure it's in the same directory.")
        return 1

    # Build command
    cmd = [
        sys.executable,
        daemon_manager_path,
        "--daemons", "ipfs",
        "--start"
    ]

    # Run daemon_manager
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)

        if result.returncode == 0:
            print("\n----------------------------------------------------------")
            print("IPFS daemon is running successfully!")
            print("----------------------------------------------------------")
            print("To check daemon status: python daemon_manager.py --status")
            print("To stop the daemon: python daemon_manager.py --daemons ipfs --stop")
            print("----------------------------------------------------------\n")

            return 0
        else:
            print("Failed to start IPFS daemon. See log output for details.")
            return 1
    except KeyboardInterrupt:
        print("\nStopping IPFS daemon startup...")
        return 0
    except Exception as e:
        print(f"Error running daemon manager: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
