#!/usr/bin/env python3
"""
This test script is the properly named version of the original:
run_mcp_communication_test.py

It has been moved to the appropriate test directory for better organization.
"""

# Original content follows:

#!/usr/bin/env python
"""
DEPRECATED: This script has been replaced by mcp_test_runner.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

"""
DEPRECATED: This script has been replaced by network_simulator.py

This file is kept for backward compatibility. Please use the unified network simulator instead,
which provides comprehensive network testing capabilities:

    python network_simulator.py --scenario intermittent

The network simulator supports multiple scenarios including communication tests,
network partitions, and more options.
"""

import sys
import os
import subprocess
import warnings

def main():
    """Run the communication test using the new network_simulator."""
    # Show deprecation warning
    warnings.warn(
        "run_mcp_communication_test.py is deprecated and will be removed in a future version. "
        "Please use network_simulator.py instead.",
        DeprecationWarning, stacklevel=2
    )

    print("Running communication test using the new network_simulator module...")

    # Check if network_simulator.py exists
    network_simulator_path = os.path.join(os.path.dirname(__file__), "network_simulator.py")
    if not os.path.exists(network_simulator_path):
        print("ERROR: network_simulator.py not found. Please make sure it's in the same directory.")
        return 1

    # Get command line arguments, skipping the script name
    args = sys.argv[1:]

    # Parse the original arguments
    import argparse
    parser = argparse.ArgumentParser(description="Run MCP communication tests")
    parser.add_argument("--force-webrtc", action="store_true",
                      help="Force WebRTC tests even if dependencies missing")
    parser.add_argument("--force-libp2p", action="store_true",
                      help="Force libp2p tests even if dependencies missing")
    parser.add_argument("--verbose", "-v", action="store_true",
                      help="Enable verbose output")
    parser.add_argument("--test-only", action="store",
                      choices=["webrtc", "websocket", "libp2p", "integrated"],
                      help="Run only a specific test")

    try:
        original_args = parser.parse_args(args)
    except SystemExit:
        # If argparse exits (e.g., with --help), just pass through to the new script
        cmd = [sys.executable, network_simulator_path, "--help"]
        return subprocess.call(cmd)

    # Set environment variables based on original args
    if original_args.force_webrtc:
        os.environ["FORCE_WEBRTC_TESTS"] = "1"
        os.environ["IPFS_KIT_FORCE_WEBRTC"] = "1"

    if original_args.force_libp2p:
        os.environ["FORCE_LIBP2P_TESTS"] = "1"

    # Build command for network simulator - use intermittent scenario as the closest match
    cmd = [
        sys.executable,
        network_simulator_path,
        "--scenario", "intermittent",
        "--nodes", "3",
        "--duration", "60"
    ]

    # Add verbosity if specified
    if original_args.verbose:
        cmd.append("--verbose")

    # Run network_simulator
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        print("\nStopping network test...")
        return 0
    except Exception as e:
        print(f"Error running network test: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
