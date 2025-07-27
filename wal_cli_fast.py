#!/usr/bin/env python3
"""
WAL CLI Integration - Fast WAL commands for CLI

This module provides lightweight WAL commands that use the fast index
for instant responses without loading heavy dependencies.
"""

import argparse
import json
import sys
from typing import Dict, List, Any, Optional

def register_wal_commands(subparsers):
    """Register WAL commands with the CLI parser."""
    
    # Main WAL parser
    wal_parser = subparsers.add_parser(
        'wal', 
        help='Write-Ahead Log operations',
        description='Manage and monitor the Write-Ahead Log system'
    )
    wal_subparsers = wal_parser.add_subparsers(dest='wal_command', help='WAL commands')
    
    # WAL status command
    status_parser = wal_subparsers.add_parser(
        'status',
        help='Show WAL status',
        description='Display current WAL status and statistics'
    )
    status_parser.set_defaults(func=handle_wal_status)
    
    # WAL pending operations command
    pending_parser = wal_subparsers.add_parser(
        'pending',
        help='List pending operations',
        description='List operations waiting to be processed'
    )
    pending_parser.add_argument(
        '--limit', '-l',
        type=int,
        default=20,
        help='Maximum number of operations to show'
    )
    pending_parser.set_defaults(func=handle_wal_pending)
    
    # WAL failed operations command
    failed_parser = wal_subparsers.add_parser(
        'failed',
        help='List failed operations',
        description='List operations that have failed'
    )
    failed_parser.add_argument(
        '--limit', '-l',
        type=int,
        default=20,
        help='Maximum number of operations to show'
    )
    failed_parser.set_defaults(func=handle_wal_failed)
    
    # WAL statistics command
    stats_parser = wal_subparsers.add_parser(
        'stats',
        help='Show WAL statistics',
        description='Display detailed WAL statistics'
    )
    stats_parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Time period in hours for statistics'
    )
    stats_parser.set_defaults(func=handle_wal_stats)
    
    # WAL health check command
    health_parser = wal_subparsers.add_parser(
        'health',
        help='Check WAL health',
        description='Perform WAL health check'
    )
    health_parser.set_defaults(func=handle_wal_health)
    
    # WAL operation details command
    get_parser = wal_subparsers.add_parser(
        'get',
        help='Get operation details',
        description='Get details of a specific WAL operation'
    )
    get_parser.add_argument(
        'operation_id',
        help='ID of the operation to retrieve'
    )
    get_parser.set_defaults(func=handle_wal_get)

def handle_wal_status(api, args, kwargs=None):
    """Handle WAL status command."""
    try:
        # Import the fast reader locally to avoid heavy imports at module level  
        from wal_fast_index import FastWALReader
        
        reader = FastWALReader()
        status = reader.get_status()
        
        if 'error' in status:
            return f"Error: {status['error']}"
        
        # Format output
        output = []
        output.append("📊 WAL Status")
        output.append("=" * 50)
        output.append(f"Total Operations: {status['total_operations']}")
        output.append(f"Pending: {status['pending_operations']}")
        output.append(f"Failed: {status['failed_operations']}")
        output.append(f"Completed: {status['completed_operations']}")
        
        if status.get('processing_operations', 0) > 0:
            output.append(f"Processing: {status['processing_operations']}")
        
        if status.get('backend_breakdown'):
            output.append("\n🔧 Backend Breakdown:")
            for backend, count in status['backend_breakdown'].items():
                output.append(f"  {backend}: {count}")
        
        if status.get('stats'):
            output.append(f"\n🕐 Last Updated: {status.get('last_updated', 'unknown')}")
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: WAL fast index not available. Please ensure the system is properly initialized."
    except Exception as e:
        return f"Error getting WAL status: {e}"

def handle_wal_pending(api, args, kwargs=None):
    """Handle WAL pending operations command."""
    try:
        from wal_fast_index import FastWALReader
        
        reader = FastWALReader()
        operations = reader.list_pending_operations(limit=args.limit)
        
        if not operations:
            return "No pending operations found."
        
        if isinstance(operations, list) and len(operations) == 1 and 'error' in operations[0]:
            return f"Error: {operations[0]['error']}"
        
        # Format output
        output = []
        output.append(f"📋 Pending Operations (showing up to {args.limit})")
        output.append("=" * 60)
        
        for op in operations:
            output.append(f"\n🔹 {op['id'][:8]}...")
            output.append(f"  Type: {op['operation_type']} on {op['backend_type']}")
            if op.get('path'):
                output.append(f"  Path: {op['path']}")
            if op.get('size'):
                output.append(f"  Size: {op['size']} bytes")
            output.append(f"  Created: {op.get('created_datetime', 'unknown')}")
            if op.get('retry_count', 0) > 0:
                output.append(f"  Retries: {op['retry_count']}")
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: WAL fast index not available."
    except Exception as e:
        return f"Error getting pending operations: {e}"

def handle_wal_failed(api, args, kwargs=None):
    """Handle WAL failed operations command."""
    try:
        from wal_fast_index import FastWALReader
        
        reader = FastWALReader()
        operations = reader.list_failed_operations(limit=args.limit)
        
        if not operations:
            return "No failed operations found."
        
        if isinstance(operations, list) and len(operations) == 1 and 'error' in operations[0]:
            return f"Error: {operations[0]['error']}"
        
        # Format output
        output = []
        output.append(f"❌ Failed Operations (showing up to {args.limit})")
        output.append("=" * 60)
        
        for op in operations:
            output.append(f"\n🔹 {op['id'][:8]}...")
            output.append(f"  Type: {op['operation_type']} on {op['backend_type']}")
            if op.get('path'):
                output.append(f"  Path: {op['path']}")
            if op.get('error_message'):
                output.append(f"  Error: {op['error_message']}")
            output.append(f"  Failed: {op.get('updated_datetime', 'unknown')}")
            output.append(f"  Retries: {op.get('retry_count', 0)}")
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: WAL fast index not available."
    except Exception as e:
        return f"Error getting failed operations: {e}"

def handle_wal_stats(api, args, kwargs=None):
    """Handle WAL statistics command."""
    try:
        from wal_fast_index import FastWALReader
        
        reader = FastWALReader()
        stats = reader.get_statistics(hours=args.hours)
        
        if 'error' in stats:
            return f"Error: {stats['error']}"
        
        # Format output
        output = []
        output.append(f"📈 WAL Statistics (last {args.hours} hours)")
        output.append("=" * 60)
        
        totals = stats.get('totals', {})
        output.append(f"Total Operations: {totals.get('total', 0)}")
        output.append(f"Completed: {totals.get('completed', 0)}")
        output.append(f"Failed: {totals.get('failed', 0)}")
        output.append(f"Pending: {totals.get('pending', 0)}")
        
        # Success rate
        total = totals.get('total', 0)
        completed = totals.get('completed', 0)
        if total > 0:
            success_rate = (completed / total) * 100
            output.append(f"Success Rate: {success_rate:.1f}%")
        
        # Breakdown by operation type and backend
        breakdown = stats.get('breakdown', {})
        if breakdown:
            output.append("\n🔧 Operation Breakdown:")
            for op_type, backends in breakdown.items():
                output.append(f"\n  {op_type}:")
                for backend, statuses in backends.items():
                    for status, count in statuses.items():
                        output.append(f"    {backend} ({status}): {count}")
        
        output.append(f"\n🕐 Generated: {stats.get('generated_at', 'unknown')}")
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: WAL fast index not available."
    except Exception as e:
        return f"Error getting WAL statistics: {e}"

def handle_wal_health(api, args, kwargs=None):
    """Handle WAL health check command."""
    try:
        from wal_fast_index import FastWALReader
        
        reader = FastWALReader()
        health = reader.health_check()
        
        # Format output
        output = []
        status_emoji = "✅" if health['status'] == 'healthy' else "❌"
        output.append(f"{status_emoji} WAL Health Check")
        output.append("=" * 50)
        output.append(f"Status: {health['status']}")
        
        if health.get('database_accessible'):
            output.append("✅ Database: Accessible")
            output.append(f"📊 Total Operations: {health.get('total_operations', 0)}")
            output.append(f"📁 Parquet Files: {health.get('parquet_files', 0)}")
        else:
            output.append("❌ Database: Not accessible")
        
        if health.get('free_disk_gb') != 'unknown':
            output.append(f"💾 Free Disk Space: {health['free_disk_gb']:.1f} GB")
        
        output.append(f"📂 Base Path: {health.get('base_path', 'unknown')}")
        
        if 'error' in health:
            output.append(f"\n❌ Error: {health['error']}")
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: WAL fast index not available."
    except Exception as e:
        return f"Error checking WAL health: {e}"

def handle_wal_get(api, args, kwargs=None):
    """Handle WAL get operation command."""
    try:
        from wal_fast_index import FastWALReader
        
        reader = FastWALReader()
        operation = reader.get_operation(args.operation_id)
        
        if not operation:
            return f"Operation {args.operation_id} not found."
        
        if 'error' in operation:
            return f"Error: {operation['error']}"
        
        # Format output
        output = []
        output.append(f"🔍 Operation Details: {operation['id'][:8]}...")
        output.append("=" * 60)
        output.append(f"ID: {operation['id']}")
        output.append(f"Type: {operation['operation_type']}")
        output.append(f"Backend: {operation['backend_type']}")
        output.append(f"Status: {operation['status']}")
        
        if operation.get('path'):
            output.append(f"Path: {operation['path']}")
        if operation.get('size'):
            output.append(f"Size: {operation['size']} bytes")
        
        output.append(f"Created: {operation.get('created_datetime', 'unknown')}")
        output.append(f"Updated: {operation.get('updated_datetime', 'unknown')}")
        
        if operation.get('retry_count', 0) > 0:
            output.append(f"Retry Count: {operation['retry_count']}")
        
        if operation.get('error_message'):
            output.append(f"Error: {operation['error_message']}")
        
        if operation.get('metadata'):
            output.append(f"\nMetadata:")
            for key, value in operation['metadata'].items():
                output.append(f"  {key}: {value}")
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: WAL fast index not available."
    except Exception as e:
        return f"Error getting operation details: {e}"

# Standalone CLI for testing
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WAL CLI Tool")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    register_wal_commands(subparsers)
    
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        result = args.func(None, args)
        print(result)
    else:
        parser.print_help()
