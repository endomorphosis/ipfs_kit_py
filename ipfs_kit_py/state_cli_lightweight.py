#!/usr/bin/env python3
"""
Lightweight entry point for IPFS Kit state commands only.
This avoids importing the heavy CLI module and dependencies.
"""

import argparse
import json
import sys
from typing import Any, Dict


def handle_state_command_lightweight(args):
    """Handle state command without importing heavy dependencies."""
    try:
        # Import the completely standalone program state module
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from standalone_program_state import StandaloneFastStateReader
        
        reader = StandaloneFastStateReader()
        
        # Handle specific requests
        if hasattr(args, 'get') and args.get:
            value = reader.get_value(args.get)
            return {
                "key": args.get,
                "value": value
            }
        elif hasattr(args, 'system') and args.system:
            return reader.get_value("system_state", {})
        elif hasattr(args, 'files') and args.files:
            return reader.get_value("file_state", {})
        elif hasattr(args, 'storage') and args.storage:
            return reader.get_value("storage_state", {})
        elif hasattr(args, 'network') and args.network:
            return reader.get_value("network_state", {})
        else:
            # Default to summary
            return reader.get_summary()
            
    except FileNotFoundError:
        return {
            "error": "Program state not available",
            "message": "Start the IPFS Kit daemon to begin collecting state"
        }
    except Exception as e:
        return {
            "error": f"Failed to get program state: {e}",
            "message": "Ensure the IPFS Kit daemon is running"
        }


def format_output_lightweight(result: Any, output_format: str) -> str:
    """Format output for state commands."""
    if output_format == "json":
        return json.dumps(result, indent=2)
    else:  # text format
        if isinstance(result, dict):
            formatted = []
            for key, value in result.items():
                if isinstance(value, dict):
                    formatted.append(f"{key}:")
                    for sub_key, sub_value in value.items():
                        formatted.append(f"  {sub_key}: {sub_value}")
                elif isinstance(value, list):
                    formatted.append(f"{key}: {len(value)} items")
                    for item in value[:3]:  # Show first 3 items
                        formatted.append(f"  - {item}")
                    if len(value) > 3:
                        formatted.append(f"  ... and {len(value) - 3} more")
                else:
                    formatted.append(f"{key}: {value}")
            return "\n".join(formatted)
        else:
            return str(result)


def main():
    """Main entry point for lightweight state CLI."""
    parser = argparse.ArgumentParser(
        description="IPFS Kit State CLI (Lightweight)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # State-specific options
    parser.add_argument(
        "--summary", 
        action="store_true", 
        help="Show state summary (default)"
    )
    parser.add_argument(
        "--system", 
        action="store_true", 
        help="Show system state"
    )
    parser.add_argument(
        "--files", 
        action="store_true", 
        help="Show file state"
    )
    parser.add_argument(
        "--storage", 
        action="store_true", 
        help="Show storage state"
    )
    parser.add_argument(
        "--network", 
        action="store_true", 
        help="Show network state"
    )
    parser.add_argument(
        "--get", 
        help="Get specific state value by key"
    )
    parser.add_argument(
        "--format", 
        choices=["text", "json"], 
        default="text", 
        help="Output format"
    )

    args = parser.parse_args()

    try:
        result = handle_state_command_lightweight(args)
        if result is not None:
            output = format_output_lightweight(result, args.format)
            print(output)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
