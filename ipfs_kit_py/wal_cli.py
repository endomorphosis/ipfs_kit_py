# ipfs_kit_py/wal_cli.py

import os
import sys
import time
import json
import logging
import argparse
import textwrap
from datetime import datetime
from typing import Dict, List, Any, Optional

from ipfs_kit_py import IPFSSimpleAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WALCommandLine:
    """Command line interface for WAL management."""
    
    def __init__(self):
        """Initialize the command line interface."""
        self.api = None
        self.parser = self._create_parser()
    
    def _create_parser(self):
        """Create the argument parser."""
        parser = argparse.ArgumentParser(
            description="IPFS Kit WAL (Write-Ahead Log) Management CLI",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=textwrap.dedent("""
                Examples:
                  # Show WAL statistics
                  wal-cli status
                  
                  # List pending operations
                  wal-cli list pending
                  
                  # Show details of a specific operation
                  wal-cli show <operation_id>
                  
                  # Wait for an operation to complete
                  wal-cli wait <operation_id>
                  
                  # Clean up old operations
                  wal-cli cleanup
            """)
        )
        
        parser.add_argument("--debug", action="store_true", help="Enable debug logging")
        parser.add_argument("--config", help="Path to configuration file")
        
        subparsers = parser.add_subparsers(dest="command", help="Command to execute")
        
        # Status command
        status_parser = subparsers.add_parser("status", help="Show WAL status")
        
        # List command
        list_parser = subparsers.add_parser("list", help="List operations")
        list_parser.add_argument(
            "operation_type",
            choices=["pending", "processing", "completed", "failed", "all"],
            help="Type of operations to list"
        )
        list_parser.add_argument(
            "--limit", 
            type=int, 
            default=10,
            help="Maximum number of operations to show"
        )
        list_parser.add_argument(
            "--backend",
            choices=["ipfs", "s3", "storacha", "all"],
            default="all",
            help="Filter by backend"
        )
        
        # Show command
        show_parser = subparsers.add_parser("show", help="Show operation details")
        show_parser.add_argument(
            "operation_id",
            help="ID of the operation to show"
        )
        
        # Wait command
        wait_parser = subparsers.add_parser("wait", help="Wait for operation to complete")
        wait_parser.add_argument(
            "operation_id",
            help="ID of the operation to wait for"
        )
        wait_parser.add_argument(
            "--timeout",
            type=int,
            default=60,
            help="Maximum time to wait in seconds"
        )
        
        # Cleanup command
        cleanup_parser = subparsers.add_parser("cleanup", help="Clean up old operations")
        
        # Health command
        health_parser = subparsers.add_parser("health", help="Show backend health status")
        health_parser.add_argument(
            "--backend",
            choices=["ipfs", "s3", "storacha", "all"],
            default="all",
            help="Filter by backend"
        )
        
        # Add command (for testing)
        add_parser = subparsers.add_parser("add", help="Add test operation to WAL")
        add_parser.add_argument(
            "file_path",
            help="Path to file to add"
        )
        add_parser.add_argument(
            "--backend",
            choices=["ipfs", "s3", "storacha"],
            default="ipfs",
            help="Backend to use"
        )
        
        return parser
    
    def run(self, args=None):
        """Run the command line interface."""
        args = self.parser.parse_args(args)
        
        # Handle debug flag
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Initialize API
        self.api = IPFSSimpleAPI(config_path=args.config)
        
        # Check if WAL is enabled
        wal_status = self.api.get_wal_stats()
        if not wal_status.get("enabled", False):
            print("Error: WAL is not enabled in the configuration")
            return 1
        
        # Dispatch command
        if args.command == "status":
            return self._cmd_status()
        elif args.command == "list":
            return self._cmd_list(args)
        elif args.command == "show":
            return self._cmd_show(args)
        elif args.command == "wait":
            return self._cmd_wait(args)
        elif args.command == "cleanup":
            return self._cmd_cleanup()
        elif args.command == "health":
            return self._cmd_health(args)
        elif args.command == "add":
            return self._cmd_add(args)
        else:
            self.parser.print_help()
            return 0
    
    def _cmd_status(self):
        """Handle the status command."""
        stats = self.api.get_wal_stats()
        
        if not stats.get("success", False):
            print(f"Error: {stats.get('error', 'Unknown error')}")
            return 1
        
        stats = stats.get("stats", {})
        
        print("\n=== WAL Status ===")
        print(f"Total operations: {stats.get('total_operations', 0)}")
        print(f"Pending: {stats.get('pending', 0)}")
        print(f"Processing: {stats.get('processing', 0)}")
        print(f"Completed: {stats.get('completed', 0)}")
        print(f"Failed: {stats.get('failed', 0)}")
        print(f"Retrying: {stats.get('retrying', 0)}")
        print(f"Partitions: {stats.get('partitions', 0)}")
        print(f"Archives: {stats.get('archives', 0)}")
        print(f"Processing active: {stats.get('processing_active', False)}")
        
        # Show backend health if available
        try:
            health_stats = self.api.wal.health_monitor.get_status()
            print("\nBackend Health:")
            for backend, status in health_stats.items():
                print(f"  {backend}: {status.get('status', 'unknown')}")
        except (AttributeError, TypeError):
            # Health monitor not available
            pass
        
        return 0
    
    def _cmd_list(self, args):
        """Handle the list command."""
        operation_type = args.operation_type
        limit = args.limit
        backend_filter = args.backend
        
        # Get operations based on type
        if operation_type == "pending":
            result = self.api.get_pending_operations(limit=limit)
            operations = result.get("operations", [])
        else:
            # For other types, we need to get all operations and filter
            # This is not ideal for large WAL files, but serves as an example
            # A real implementation would have backend methods for this
            print("This feature is not fully implemented yet.")
            print("Currently only 'pending' operations can be listed.")
            return 1
        
        # Filter by backend if needed
        if backend_filter != "all":
            operations = [op for op in operations if op.get("backend") == backend_filter]
        
        # Display operations
        if operations:
            print(f"\n=== {operation_type.capitalize()} Operations ===")
            for op in operations:
                op_id = op.get("operation_id", "unknown")
                op_type = op.get("operation_type", "unknown")
                backend = op.get("backend", "unknown")
                status = op.get("status", "unknown")
                timestamp = op.get("timestamp")
                
                # Format timestamp
                if timestamp:
                    if isinstance(timestamp, (int, float)):
                        timestamp = datetime.fromtimestamp(timestamp / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"ID: {op_id}")
                print(f"  Type: {op_type}")
                print(f"  Backend: {backend}")
                print(f"  Status: {status}")
                print(f"  Timestamp: {timestamp}")
                print()
        else:
            print(f"No {operation_type} operations found.")
        
        return 0
    
    def _cmd_show(self, args):
        """Handle the show command."""
        operation_id = args.operation_id
        
        # Get operation details
        operation = self.api.get_wal_status(operation_id)
        
        if not operation.get("success", False):
            print(f"Error: {operation.get('error', 'Unknown error')}")
            return 1
        
        # Display operation details
        print(f"\n=== Operation Details: {operation_id} ===")
        for key, value in operation.items():
            if key == "success":
                continue
                
            # Format timestamps
            if "time" in key.lower() and isinstance(value, (int, float)):
                formatted_time = datetime.fromtimestamp(value / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
                print(f"{key}: {formatted_time}")
            # Format dictionaries/lists with JSON
            elif isinstance(value, (dict, list)):
                print(f"{key}:")
                print(json.dumps(value, indent=2))
            else:
                print(f"{key}: {value}")
        
        return 0
    
    def _cmd_wait(self, args):
        """Handle the wait command."""
        operation_id = args.operation_id
        timeout = args.timeout
        
        print(f"Waiting for operation {operation_id} to complete (timeout: {timeout}s)...")
        
        # Wait for operation
        result = self.api.wait_for_operation(
            operation_id,
            timeout=timeout,
            check_interval=1
        )
        
        if not result.get("success", False):
            print(f"Error: {result.get('error', 'Unknown error')}")
            return 1
        
        status = result.get("status")
        if status == "completed":
            print(f"Operation completed successfully!")
            # Display result if available
            if "result" in result:
                print("\nResult:")
                print(json.dumps(result["result"], indent=2))
        elif status == "failed":
            print(f"Operation failed: {result.get('error', 'Unknown error')}")
            return 1
        else:
            print(f"Operation status: {status}")
            return 1
        
        return 0
    
    def _cmd_cleanup(self):
        """Handle the cleanup command."""
        print("Cleaning up old operations...")
        
        result = self.api.cleanup_wal()
        
        if not result.get("success", False):
            print(f"Error: {result.get('error', 'Unknown error')}")
            return 1
        
        print(f"Cleaned up {result.get('removed_count', 0)} old operations.")
        return 0
    
    def _cmd_health(self, args):
        """Handle the health command."""
        backend_filter = args.backend
        
        try:
            if backend_filter == "all":
                health_stats = self.api.wal.health_monitor.get_status()
                
                print("\n=== Backend Health ===")
                for backend, status in health_stats.items():
                    print(f"Backend: {backend}")
                    print(f"  Status: {status.get('status', 'unknown')}")
                    print(f"  Last check: {datetime.fromtimestamp(status.get('last_check', 0)).strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # Show check history
                    history = status.get('check_history', [])
                    if history:
                        success_rate = sum(1 for h in history if h) / len(history) if history else 0
                        print(f"  Check history: {' '.join('✓' if h else '✗' for h in history)}")
                        print(f"  Success rate: {success_rate:.1%}")
                    print()
            else:
                health_stats = self.api.wal.health_monitor.get_status(backend_filter)
                
                print(f"\n=== {backend_filter.upper()} Backend Health ===")
                print(f"Status: {health_stats.get('status', 'unknown')}")
                print(f"Last check: {datetime.fromtimestamp(health_stats.get('last_check', 0)).strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Show check history
                history = health_stats.get('check_history', [])
                if history:
                    success_rate = sum(1 for h in history if h) / len(history) if history else 0
                    print(f"Check history: {' '.join('✓' if h else '✗' for h in history)}")
                    print(f"Success rate: {success_rate:.1%}")
        except (AttributeError, TypeError):
            print("Error: Health monitor not available")
            return 1
        
        return 0
    
    def _cmd_add(self, args):
        """Handle the add command (for testing)."""
        file_path = args.file_path
        backend = args.backend
        
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            return 1
        
        print(f"Adding file {file_path} to {backend}...")
        
        # Add file to backend
        if backend == "ipfs":
            result = self.api.add(file_path)
        else:
            print(f"Error: Backend {backend} not supported for this demo")
            return 1
        
        # Display result
        print("\nResult:")
        print(json.dumps(result, indent=2))
        
        # If operation is queued in WAL, suggest waiting
        if result.get("operation_id") and result.get("status") == "pending":
            print(f"\nOperation queued in WAL. To wait for completion, run:")
            print(f"  wal-cli wait {result['operation_id']}")
        
        return 0


def main():
    """Main entry point for WAL CLI."""
    cli = WALCommandLine()
    return cli.run()

if __name__ == "__main__":
    sys.exit(main())