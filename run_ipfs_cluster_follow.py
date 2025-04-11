#!/usr/bin/env python3
"""
Wrapper script to run IPFS Cluster Follow with proper imports.
"""
import os
import sys
import argparse

# Ensure the parent directory is in the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Run the IPFS Cluster Follow."""
    parser = argparse.ArgumentParser(description="Run IPFS Cluster Follow")
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--fake-daemon', action='store_true', help='Run in fake daemon mode for testing')
    args = parser.parse_args()
    
    # Set up logging if debug mode is enabled
    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        print("Debug logging enabled")
    
    # Import the module properly
    from ipfs_kit_py import ipfs_cluster_follow
    
    # Pass the arguments to the main function if the module has set_debug method
    if args.debug and hasattr(ipfs_cluster_follow, 'set_debug'):
        ipfs_cluster_follow.set_debug(True)
    
    if args.fake_daemon:
        print("Running in fake daemon mode")
        # Just import and return success
        sys.exit(0)
    
    # Run the actual follow service
    result = ipfs_cluster_follow.run_follow()
    sys.exit(0 if result else 1)

if __name__ == "__main__":
    main()