#!/usr/bin/env python
"""Script to run all tests with WebRTC dependencies forced."""

import os
import sys
import subprocess

def main():
    """Run all tests with WebRTC dependencies forced."""
    # Set environment variables to force WebRTC dependencies
    os.environ["IPFS_KIT_FORCE_WEBRTC"] = "1"
    os.environ["FORCE_WEBRTC_TESTS"] = "1"
    os.environ["IPFS_KIT_RUN_ALL_TESTS"] = "1"
    
    # Import the module to set the environment variables
    print("Importing IPFS Kit components to apply environment variables...")
    import ipfs_kit_py.webrtc_streaming
    print(f"HAVE_WEBRTC: {ipfs_kit_py.webrtc_streaming.HAVE_WEBRTC}")
    
    # Run pytest with all tests
    print("\nRunning all tests...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "--no-summary", "--no-header"],
        capture_output=True,
        text=True,
        env=os.environ
    )
    
    # Print output
    print("\nTest Output:")
    print(result.stdout)
    
    # Print errors
    if result.stderr:
        print("\nErrors:")
        print(result.stderr)
    
    # Report results
    print("\nTest Summary:")
    # Extract summary lines from output
    lines = result.stdout.splitlines()
    summary_line = next((line for line in reversed(lines) if "=" in line and "in" in line), "")
    if summary_line:
        print(summary_line)
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())