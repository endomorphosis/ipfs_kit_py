#!/usr/bin/env python3
"""
Wrapper script to run IPFS Cluster Service with proper imports.
"""
import os
import sys
import argparse

# Ensure the parent directory is in the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Run the IPFS Cluster Service."""
    parser = argparse.ArgumentParser(description="Run IPFS Cluster Service")
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--fake-daemon', action='store_true', help='Run in fake daemon mode for testing')
    args = parser.parse_args()
    
    # Set up logging if debug mode is enabled
    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        print("Debug logging enabled")
    
    # Import the module properly
    from ipfs_kit_py import ipfs_cluster_service
    
    # Check for fake daemon mode
    if args.fake_daemon:
        print("Running in fake daemon mode")
        # Just import and return success
        sys.exit(0)
    
    # Look for run_service or similar function
    if hasattr(ipfs_cluster_service, 'run_service'):
        result = ipfs_cluster_service.run_service()
        sys.exit(0 if result else 1)
    elif hasattr(ipfs_cluster_service, 'main'):
        result = ipfs_cluster_service.main()
        sys.exit(0 if result else 1)
    else:
        # Try to run the init method if available
        if hasattr(ipfs_cluster_service, 'init_service'):
            result = ipfs_cluster_service.init_service()
            sys.exit(0 if result else 1)
        else:
            print("Could not find a suitable entry point in ipfs_cluster_service")
            sys.exit(1)

if __name__ == "__main__":
    main()