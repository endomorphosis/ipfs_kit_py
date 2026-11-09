#!/usr/bin/env python3
"""
IPFS Kit Program State CLI

A lightweight CLI tool for accessing program state without heavy dependencies.
This tool can quickly retrieve system status, file counts, bandwidth info, etc.
from the program state storage.

Usage:
    ipfs-kit-state --summary                    # Show overall state summary
    ipfs-kit-state --system                     # Show system metrics
    ipfs-kit-state --files                      # Show file statistics  
    ipfs-kit-state --storage                    # Show storage backend status
    ipfs-kit-state --network                    # Show network status
    ipfs-kit-state --get key                    # Get specific state value
    ipfs-kit-state --json                       # Output in JSON format
"""

import sys
import os
import json
import argparse
from pathlib import Path


def print_summary(reader, json_output=False):
    """Print state summary"""
    summary = reader.get_summary()
    
    if json_output:
        print(json.dumps(summary, indent=2))
        return
    
    print("IPFS Kit Program State Summary")
    print("=" * 40)
    
    if not summary:
        print("No state data available")
        return
    
    print(f"Bandwidth: ↓{summary.get('bandwidth_in', 0):,} ↑{summary.get('bandwidth_out', 0):,} bytes")
    print(f"Peers: {summary.get('peer_count', 0)}")
    print(f"Files: {summary.get('total_files', 0):,} total, {summary.get('pinned_files', 0):,} pinned")
    print(f"Storage Backends: {summary.get('backends_active', 0)} active")
    print(f"Network Health: {summary.get('network_health', 'unknown')}")
    print(f"Cluster Status: {summary.get('cluster_status', 'unknown')}")


def print_detailed_state(reader, category, json_output=False):
    """Print detailed state for a specific category"""
    state_key = f"{category}_state"
    state_data = reader.get_value(state_key, {})
    
    if json_output:
        print(json.dumps(state_data, indent=2))
        return
    
    print(f"IPFS Kit {category.title()} State")
    print("=" * 40)
    
    if not state_data:
        print(f"No {category} state data available")
        return
    
    for key, value in state_data.items():
        if key == 'last_updated':
            # Convert timestamp to readable format
            try:
                import datetime
                dt = datetime.datetime.fromtimestamp(value)
                print(f"{key}: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            except:
                print(f"{key}: {value}")
        elif isinstance(value, list):
            print(f"{key}: {len(value)} items")
            if value and len(value) <= 5:  # Show first few items if small list
                for item in value[:3]:
                    print(f"  - {item}")
                if len(value) > 3:
                    print(f"  ... and {len(value) - 3} more")
        elif isinstance(value, dict):
            print(f"{key}: {len(value)} entries")
        else:
            print(f"{key}: {value}")


def main():
    parser = argparse.ArgumentParser(
        description="IPFS Kit Program State CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--summary', action='store_true',
                       help='Show overall state summary')
    parser.add_argument('--system', action='store_true',
                       help='Show system metrics')
    parser.add_argument('--files', action='store_true', 
                       help='Show file statistics')
    parser.add_argument('--storage', action='store_true',
                       help='Show storage backend status')
    parser.add_argument('--network', action='store_true',
                       help='Show network status')
    parser.add_argument('--get', metavar='KEY',
                       help='Get specific state value')
    parser.add_argument('--json', action='store_true',
                       help='Output in JSON format')
    parser.add_argument('--state-dir', metavar='DIR',
                       help='Program state directory (default: ~/.ipfs_kit/program_state)')
    
    args = parser.parse_args()
    
    # If no arguments provided, show summary
    if not any([args.summary, args.system, args.files, args.storage, args.network, args.get]):
        args.summary = True
    
    try:
        # Import the fast state reader with minimal dependencies
        sys.path.insert(0, str(Path(__file__).parent))
        from program_state import FastStateReader
        
        reader = FastStateReader(args.state_dir)
        
        if args.summary:
            print_summary(reader, args.json)
        elif args.system:
            print_detailed_state(reader, 'system', args.json)
        elif args.files:
            print_detailed_state(reader, 'file', args.json)
        elif args.storage:
            print_detailed_state(reader, 'storage', args.json)
        elif args.network:
            print_detailed_state(reader, 'network', args.json)
        elif args.get:
            value = reader.get_value(args.get)
            if args.json:
                print(json.dumps(value, indent=2))
            else:
                print(f"{args.get}: {value}")
                
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("The program state database has not been initialized yet.", file=sys.stderr)
        print("Start the IPFS Kit daemon to begin collecting state.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error accessing program state: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
