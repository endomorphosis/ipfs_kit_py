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
    """Handle WAL status command using Parquet data."""
    try:
        # Try Parquet data access first
        try:
            import sys
            from pathlib import Path
            
            # Add package to path for import
            package_root = Path(__file__).parent / 'ipfs_kit_py'
            if package_root.exists():
                sys.path.insert(0, str(package_root.parent))
                from ipfs_kit_py.parquet_data_reader import get_parquet_reader
            else:
                # We're probably already in the package
                from parquet_data_reader import get_parquet_reader
            
            reader = get_parquet_reader()
            wal_result = reader.read_wal_operations()
            
            if wal_result['success']:
                operations = wal_result['operations']
                
                # Calculate status breakdown
                status_counts = {}
                backend_counts = {}
                
                for op in operations:
                    status = op.get('status', 'unknown')
                    backend = op.get('backend_type', 'unknown')
                    
                    status_counts[status] = status_counts.get(status, 0) + 1
                    backend_counts[backend] = backend_counts.get(backend, 0) + 1
                
                # Format output
                output = []
                output.append("📊 WAL Status (from Parquet data)")
                output.append("=" * 50)
                output.append(f"Total Operations: {len(operations)}")
                
                for status, count in status_counts.items():
                    if status == 'pending':
                        output.append(f"Pending: {count}")
                    elif status == 'failed':
                        output.append(f"Failed: {count}")
                    elif status == 'completed':
                        output.append(f"Completed: {count}")
                    else:
                        output.append(f"{status.title()}: {count}")
                
                if backend_counts:
                    output.append("\n🔧 Backend Breakdown:")
                    for backend, count in backend_counts.items():
                        output.append(f"  {backend}: {count}")
                
                output.append(f"\n📂 Data source: Parquet files ({len(wal_result.get('sources', []))} files)")
                
                return "\n".join(output)
            else:
                print(f"⚠️  Parquet WAL data failed: {wal_result.get('error', 'Unknown error')}")
                print("🔄 Falling back to fast index...")
                
        except ImportError as e:
            print(f"⚠️  Parquet reader not available: {e}")
            print("🔄 Falling back to fast index...")
        except Exception as e:
            print(f"⚠️  Parquet WAL error: {e}")
            print("🔄 Falling back to fast index...")
        
        # Fallback to original fast index
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
    """Handle WAL pending operations command using Parquet data."""
    try:
        # Try Parquet data access first
        try:
            import sys
            from pathlib import Path
            
            # Add package to path for import
            package_root = Path(__file__).parent / 'ipfs_kit_py'
            if package_root.exists():
                sys.path.insert(0, str(package_root.parent))
                from ipfs_kit_py.parquet_data_reader import get_parquet_reader
            else:
                # We're probably already in the package
                from parquet_data_reader import get_parquet_reader
            
            reader = get_parquet_reader()
            wal_result = reader.read_wal_operations()
            
            if wal_result['success']:
                operations = wal_result['operations']
                
                # Filter for pending operations
                pending_ops = [op for op in operations if op.get('status') == 'pending']
                
                # Apply limit
                limit = getattr(args, 'limit', 50)
                pending_ops = pending_ops[:limit]
                
                if not pending_ops:
                    return "No pending operations found in Parquet data."
                
                # Format output
                output = []
                output.append(f"📋 Pending Operations (from Parquet, showing {len(pending_ops)} of {len([op for op in operations if op.get('status') == 'pending'])})")
                output.append("=" * 70)
                
                for i, op in enumerate(pending_ops, 1):
                    output.append(f"\n🔹 Operation {i}")
                    output.append(f"  ID: {op.get('operation_id', op.get('id', 'unknown'))}")
                    output.append(f"  Type: {op.get('operation_type', 'unknown')} on {op.get('backend_type', 'unknown')}")
                    if op.get('path'):
                        output.append(f"  Path: {op['path']}")
                    if op.get('size'):
                        output.append(f"  Size: {op['size']} bytes")
                    output.append(f"  Created: {op.get('created_datetime', op.get('timestamp', 'unknown'))}")
                    if op.get('retry_count', 0) > 0:
                        output.append(f"  Retries: {op['retry_count']}")
                
                output.append(f"\n📂 Data source: Parquet files ({len(wal_result.get('sources', []))} files)")
                
                return "\n".join(output)
            else:
                print(f"⚠️  Parquet WAL data failed: {wal_result.get('error', 'Unknown error')}")
                print("🔄 Falling back to fast index...")
                
        except ImportError as e:
            print(f"⚠️  Parquet reader not available: {e}")
            print("🔄 Falling back to fast index...")
        except Exception as e:
            print(f"⚠️  Parquet WAL error: {e}")
            print("🔄 Falling back to fast index...")
        
        # Fallback to original fast index
        from wal_fast_index import FastWALReader
        
        reader = FastWALReader()
        operations = reader.list_pending_operations(limit=getattr(args, 'limit', 50))
        
        if not operations:
            return "No pending operations found."
        
        if isinstance(operations, list) and len(operations) == 1 and 'error' in operations[0]:
            return f"Error: {operations[0]['error']}"
        
        # Format output
        output = []
        output.append(f"📋 Pending Operations (from fast index, showing up to {getattr(args, 'limit', 50)})")
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
    """Handle WAL failed operations command using Parquet data."""
    try:
        # Try Parquet data access first
        try:
            import sys
            from pathlib import Path
            
            # Add package to path for import
            package_root = Path(__file__).parent / 'ipfs_kit_py'
            if package_root.exists():
                sys.path.insert(0, str(package_root.parent))
                from ipfs_kit_py.parquet_data_reader import get_parquet_reader
            else:
                # We're probably already in the package
                from parquet_data_reader import get_parquet_reader
            
            reader = get_parquet_reader()
            wal_result = reader.read_wal_operations()
            
            if wal_result['success']:
                operations = wal_result['operations']
                
                # Filter for failed operations
                failed_ops = [op for op in operations if op.get('status') == 'failed']
                
                # Apply limit
                limit = getattr(args, 'limit', 50)
                failed_ops = failed_ops[:limit]
                
                if not failed_ops:
                    return "No failed operations found in Parquet data."
                
                # Format output
                output = []
                output.append(f"❌ Failed Operations (from Parquet, showing {len(failed_ops)} of {len([op for op in operations if op.get('status') == 'failed'])})")
                output.append("=" * 70)
                
                for i, op in enumerate(failed_ops, 1):
                    output.append(f"\n🔹 Operation {i}")
                    output.append(f"  ID: {op.get('operation_id', op.get('id', 'unknown'))}")
                    output.append(f"  Type: {op.get('operation_type', 'unknown')} on {op.get('backend_type', 'unknown')}")
                    if op.get('path'):
                        output.append(f"  Path: {op['path']}")
                    if op.get('error_message'):
                        output.append(f"  Error: {op['error_message']}")
                    output.append(f"  Failed: {op.get('updated_datetime', op.get('timestamp', 'unknown'))}")
                    output.append(f"  Retries: {op.get('retry_count', 0)}")
                
                output.append(f"\n📂 Data source: Parquet files ({len(wal_result.get('sources', []))} files)")
                
                return "\n".join(output)
            else:
                print(f"⚠️  Parquet WAL data failed: {wal_result.get('error', 'Unknown error')}")
                print("🔄 Falling back to fast index...")
                
        except ImportError as e:
            print(f"⚠️  Parquet reader not available: {e}")
            print("🔄 Falling back to fast index...")
        except Exception as e:
            print(f"⚠️  Parquet WAL error: {e}")
            print("🔄 Falling back to fast index...")
        
        # Fallback to original fast index
        from wal_fast_index import FastWALReader
        
        reader = FastWALReader()
        operations = reader.list_failed_operations(limit=getattr(args, 'limit', 50))
        
        if not operations:
            return "No failed operations found."
        
        if isinstance(operations, list) and len(operations) == 1 and 'error' in operations[0]:
            return f"Error: {operations[0]['error']}"
        
        # Format output
        output = []
        output.append(f"❌ Failed Operations (from fast index, showing up to {getattr(args, 'limit', 50)})")
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
    """Handle WAL statistics command using Parquet data."""
    try:
        # Try Parquet data access first
        try:
            import sys
            from pathlib import Path
            from datetime import datetime, timedelta
            
            # Add package to path for import
            package_root = Path(__file__).parent / 'ipfs_kit_py'
            if package_root.exists():
                sys.path.insert(0, str(package_root.parent))
                from ipfs_kit_py.parquet_data_reader import get_parquet_reader
            else:
                # We're probably already in the package
                from parquet_data_reader import get_parquet_reader
            
            reader = get_parquet_reader()
            wal_result = reader.read_wal_operations()
            
            if wal_result['success']:
                operations = wal_result['operations']
                
                # Filter by time window if specified
                hours = getattr(args, 'hours', 24)
                cutoff_time = datetime.now() - timedelta(hours=hours)
                
                # Filter operations by time window
                filtered_ops = []
                for op in operations:
                    timestamp_str = op.get('timestamp', op.get('created_datetime', ''))
                    if timestamp_str:
                        try:
                            # Try parsing the timestamp
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            if timestamp >= cutoff_time:
                                filtered_ops.append(op)
                        except ValueError:
                            # If parsing fails, include the operation
                            filtered_ops.append(op)
                    else:
                        # If no timestamp, include the operation
                        filtered_ops.append(op)
                
                # Calculate statistics
                total = len(filtered_ops)
                completed = len([op for op in filtered_ops if op.get('status') == 'completed'])
                failed = len([op for op in filtered_ops if op.get('status') == 'failed'])
                pending = len([op for op in filtered_ops if op.get('status') == 'pending'])
                
                # Calculate breakdown
                breakdown = {}
                for op in filtered_ops:
                    op_type = op.get('operation_type', 'unknown')
                    backend = op.get('backend_type', 'unknown')
                    status = op.get('status', 'unknown')
                    
                    if op_type not in breakdown:
                        breakdown[op_type] = {}
                    if backend not in breakdown[op_type]:
                        breakdown[op_type][backend] = {}
                    breakdown[op_type][backend][status] = breakdown[op_type][backend].get(status, 0) + 1
                
                # Format output
                output = []
                output.append(f"📈 WAL Statistics (from Parquet, last {hours} hours)")
                output.append("=" * 70)
                
                output.append(f"Total Operations: {total}")
                output.append(f"Completed: {completed}")
                output.append(f"Failed: {failed}")
                output.append(f"Pending: {pending}")
                
                # Success rate
                if total > 0:
                    success_rate = (completed / total) * 100
                    output.append(f"Success Rate: {success_rate:.1f}%")
                
                # Breakdown by operation type and backend
                if breakdown:
                    output.append("\n🔧 Operation Breakdown:")
                    for op_type, backends in breakdown.items():
                        output.append(f"\n  {op_type}:")
                        for backend, statuses in backends.items():
                            for status, count in statuses.items():
                                output.append(f"    {backend} ({status}): {count}")
                
                output.append(f"\n📂 Data source: Parquet files ({len(wal_result.get('sources', []))} files)")
                output.append(f"🕐 Generated: {datetime.now().isoformat()}")
                
                return "\n".join(output)
            else:
                print(f"⚠️  Parquet WAL data failed: {wal_result.get('error', 'Unknown error')}")
                print("🔄 Falling back to fast index...")
                
        except ImportError as e:
            print(f"⚠️  Parquet reader not available: {e}")
            print("🔄 Falling back to fast index...")
        except Exception as e:
            print(f"⚠️  Parquet WAL error: {e}")
            print("🔄 Falling back to fast index...")
        
        # Fallback to original fast index
        from wal_fast_index import FastWALReader
        
        reader = FastWALReader()
        stats = reader.get_statistics(hours=getattr(args, 'hours', 24))
        
        if 'error' in stats:
            return f"Error: {stats['error']}"
        
        # Format output
        output = []
        output.append(f"📈 WAL Statistics (from fast index, last {getattr(args, 'hours', 24)} hours)")
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
