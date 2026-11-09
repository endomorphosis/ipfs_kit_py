#!/usr/bin/env python3
"""
FS Journal CLI Integration - Fast FS Journal commands for CLI

This module provides lightweight FS Journal commands that use the fast index
for instant responses without loading heavy dependencies.
"""

import argparse
import json
import sys
from typing import Dict, List, Any, Optional

def register_fs_journal_commands(subparsers):
    """Register FS Journal commands with the CLI parser."""
    
    # Main FS Journal parser
    fs_parser = subparsers.add_parser(
        'fs-journal', 
        help='Filesystem Journal operations',
        description='Monitor and query the filesystem journal'
    )
    fs_subparsers = fs_parser.add_subparsers(dest='fs_command', help='FS Journal commands')
    
    # FS Journal status command
    status_parser = fs_subparsers.add_parser(
        'status',
        help='Show FS Journal status',
        description='Display current filesystem journal status and statistics'
    )
    status_parser.set_defaults(func=handle_fs_status)
    
    # Recent operations command
    recent_parser = fs_subparsers.add_parser(
        'recent',
        help='List recent operations',
        description='List recent filesystem operations'
    )
    recent_parser.add_argument(
        '--limit', '-l',
        type=int,
        default=20,
        help='Maximum number of operations to show'
    )
    recent_parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Time period in hours to search'
    )
    recent_parser.set_defaults(func=handle_fs_recent)
    
    # Failed operations command
    failed_parser = fs_subparsers.add_parser(
        'failed',
        help='List failed operations',
        description='List failed filesystem operations'
    )
    failed_parser.add_argument(
        '--limit', '-l',
        type=int,
        default=20,
        help='Maximum number of operations to show'
    )
    failed_parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Time period in hours to search'
    )
    failed_parser.set_defaults(func=handle_fs_failed)
    
    # Virtual filesystem listing command
    files_parser = fs_subparsers.add_parser(
        'files',
        help='List virtual filesystem',
        description='List files in the virtual filesystem'
    )
    files_parser.add_argument(
        'path',
        nargs='?',
        default='',
        help='Path prefix to filter by'
    )
    files_parser.add_argument(
        '--limit', '-l',
        type=int,
        default=50,
        help='Maximum number of files to show'
    )
    files_parser.set_defaults(func=handle_fs_files)
    
    # File info command
    info_parser = fs_subparsers.add_parser(
        'info',
        help='Get file information',
        description='Get detailed information about a specific file'
    )
    info_parser.add_argument(
        'path',
        help='Path of the file to get information about'
    )
    info_parser.set_defaults(func=handle_fs_info)
    
    # FS Journal statistics command
    stats_parser = fs_subparsers.add_parser(
        'stats',
        help='Show FS Journal statistics',
        description='Display detailed filesystem journal statistics'
    )
    stats_parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Time period in hours for statistics'
    )
    stats_parser.set_defaults(func=handle_fs_stats)
    
    # FS Journal health check command
    health_parser = fs_subparsers.add_parser(
        'health',
        help='Check FS Journal health',
        description='Perform filesystem journal health check'
    )
    health_parser.set_defaults(func=handle_fs_health)

def handle_fs_status(api, args, kwargs=None):
    """Handle FS Journal status command using Parquet data."""
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
            fs_result = reader.read_fs_journal_operations()
            
            if fs_result['success']:
                operations = fs_result['operations']
                
                # Calculate statistics
                total_operations = len(operations)
                successful_operations = len([op for op in operations if op.get('success', True)])
                failed_operations = total_operations - successful_operations
                
                # Calculate breakdowns
                operation_breakdown = {}
                backend_breakdown = {}
                
                for op in operations:
                    op_type = op.get('operation', op.get('operation_type', 'unknown'))
                    backend = op.get('backend', op.get('backend_type', 'unknown'))
                    
                    operation_breakdown[op_type] = operation_breakdown.get(op_type, 0) + 1
                    backend_breakdown[backend] = backend_breakdown.get(backend, 0) + 1
                
                # Format output
                output = []
                output.append("📁 FS Journal Status (from Parquet data)")
                output.append("=" * 60)
                output.append(f"Total Operations: {total_operations}")
                output.append(f"Successful: {successful_operations}")
                output.append(f"Failed: {failed_operations}")
                
                # Success rate
                if total_operations > 0:
                    success_rate = (successful_operations / total_operations) * 100
                    output.append(f"Success Rate: {success_rate:.1f}%")
                
                # Operation breakdown
                if operation_breakdown:
                    output.append("\n📊 Operation Breakdown:")
                    for op_type, count in operation_breakdown.items():
                        output.append(f"  {op_type}: {count}")
                
                # Backend breakdown
                if backend_breakdown:
                    output.append("\n🔧 Backend Breakdown:")
                    for backend, count in backend_breakdown.items():
                        output.append(f"  {backend}: {count}")
                
                # Virtual filesystem stats (estimated from operations)
                file_ops = [op for op in operations if op.get('operation') in ['write', 'read']]
                if file_ops:
                    output.append("\n💾 Virtual Filesystem (estimated from operations):")
                    unique_files = len(set(op.get('path', '') for op in file_ops if op.get('path')))
                    total_size = sum(op.get('size', 0) for op in file_ops if op.get('size'))
                    output.append(f"  file: {unique_files} ({total_size:,} bytes)")
                    output.append(f"  Total: {unique_files} files ({total_size:,} bytes)")
                
                output.append(f"\n📂 Data source: Parquet files ({len(fs_result.get('sources', []))} files)")
                output.append(f"🕐 Generated: {fs_result.get('timestamp', 'unknown')}")
                
                return "\n".join(output)
            else:
                print(f"⚠️  Parquet FS Journal data failed: {fs_result.get('error', 'Unknown error')}")
                print("🔄 Falling back to fast index...")
                
        except ImportError as e:
            print(f"⚠️  Parquet reader not available: {e}")
            print("🔄 Falling back to fast index...")
        except Exception as e:
            print(f"⚠️  Parquet FS Journal error: {e}")
            print("🔄 Falling back to fast index...")
        
        # Fallback to original fast index
        # Import the fast reader locally to avoid heavy imports at module level  
        from fs_journal_fast_index import FastFSJournalReader
        
        reader = FastFSJournalReader()
        status = reader.get_status()
        
        if 'error' in status:
            return f"Error: {status['error']}"
        
        # Format output
        output = []
        output.append("📁 FS Journal Status (from fast index)")
        output.append("=" * 50)
        output.append(f"Total Operations: {status['total_operations']}")
        output.append(f"Successful: {status['successful_operations']}")
        output.append(f"Failed: {status['failed_operations']}")
        
        # Success rate
        total = status['total_operations']
        successful = status['successful_operations']
        if total > 0:
            success_rate = (successful / total) * 100
            output.append(f"Success Rate: {success_rate:.1f}%")
        
        # Operation breakdown
        if status.get('operation_breakdown'):
            output.append("\n📊 Operation Breakdown:")
            for op_type, count in status['operation_breakdown'].items():
                output.append(f"  {op_type}: {count}")
        
        # Backend breakdown
        if status.get('backend_breakdown'):
            output.append("\n🔧 Backend Breakdown:")
            for backend, count in status['backend_breakdown'].items():
                output.append(f"  {backend}: {count}")
        
        # Virtual filesystem stats
        if status.get('virtual_filesystem'):
            output.append("\n💾 Virtual Filesystem:")
            total_size = 0
            total_files = 0
            for file_type, stats in status['virtual_filesystem'].items():
                count = stats['count']
                size = stats['total_size']
                total_files += count
                total_size += size
                output.append(f"  {file_type}: {count} ({size:,} bytes)")
            output.append(f"  Total: {total_files} files ({total_size:,} bytes)")
        
        output.append(f"\n🕐 Last Updated: {status.get('last_updated', 'unknown')}")
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: FS Journal fast index not available. Please ensure the system is properly initialized."
    except Exception as e:
        return f"Error getting FS Journal status: {e}"

def handle_fs_recent(api, args, kwargs=None):
    """Handle FS Journal recent operations command using Parquet data."""
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
            fs_result = reader.read_fs_journal_operations()
            
            if fs_result['success']:
                operations = fs_result['operations']
                
                # Filter by time window
                hours = getattr(args, 'hours', 24)
                cutoff_time = datetime.now() - timedelta(hours=hours)
                
                # Filter operations by time window
                filtered_ops = []
                for op in operations:
                    timestamp_str = op.get('timestamp', op.get('datetime', ''))
                    if timestamp_str:
                        try:
                            # Handle both string and float timestamps
                            if isinstance(timestamp_str, (int, float)):
                                # Unix timestamp
                                timestamp = datetime.fromtimestamp(timestamp_str)
                            else:
                                # ISO string timestamp
                                timestamp = datetime.fromisoformat(str(timestamp_str).replace('Z', '+00:00'))
                            
                            if timestamp >= cutoff_time:
                                filtered_ops.append(op)
                        except (ValueError, TypeError, OSError) as e:
                            # If parsing fails, include the operation
                            print(f"⚠️  Timestamp parsing error for {timestamp_str}: {e}")
                            filtered_ops.append(op)
                    else:
                        # If no timestamp, include the operation
                        filtered_ops.append(op)
                
                # Apply limit
                limit = getattr(args, 'limit', 20)
                filtered_ops = filtered_ops[:limit]
                
                if not filtered_ops:
                    return f"No operations found in the last {hours} hours from Parquet data."
                
                # Format output
                output = []
                output.append(f"📋 Recent Operations (from Parquet, last {hours}h, showing {len(filtered_ops)} of {len(operations)})")
                output.append("=" * 80)
                
                for i, op in enumerate(filtered_ops, 1):
                    success = op.get('success', True)
                    status_emoji = "✅" if success else "❌"
                    operation_type = op.get('operation', op.get('operation_type', 'unknown')).upper()
                    
                    output.append(f"\n{status_emoji} Operation {i}: {operation_type}")
                    output.append(f"  Path: {op.get('path', 'unknown')}")
                    if op.get('backend', op.get('backend_name')):
                        output.append(f"  Backend: {op.get('backend', op.get('backend_name'))}")
                    if op.get('size'):
                        output.append(f"  Size: {op['size']:,} bytes")
                    output.append(f"  Time: {op.get('timestamp', op.get('datetime', 'unknown'))}")
                    if op.get('duration_ms'):
                        output.append(f"  Duration: {op['duration_ms']}ms")
                    if not success and op.get('error_message', op.get('error')):
                        output.append(f"  Error: {op.get('error_message', op.get('error'))}")
                
                output.append(f"\n📂 Data source: Parquet files ({len(fs_result.get('sources', []))} files)")
                
                return "\n".join(output)
            else:
                print(f"⚠️  Parquet FS Journal data failed: {fs_result.get('error', 'Unknown error')}")
                print("🔄 Falling back to fast index...")
                
        except ImportError as e:
            print(f"⚠️  Parquet reader not available: {e}")
            print("🔄 Falling back to fast index...")
        except Exception as e:
            print(f"⚠️  Parquet FS Journal error: {e}")
            print("🔄 Falling back to fast index...")
        
        # Fallback to original fast index
        from fs_journal_fast_index import FastFSJournalReader
        
        reader = FastFSJournalReader()
        operations = reader.list_recent_operations(limit=getattr(args, 'limit', 20), hours=getattr(args, 'hours', 24))
        
        if not operations:
            return f"No operations found in the last {getattr(args, 'hours', 24)} hours."
        
        if isinstance(operations, list) and len(operations) == 1 and 'error' in operations[0]:
            return f"Error: {operations[0]['error']}"
        
        # Format output
        output = []
        output.append(f"📋 Recent Operations (from fast index, last {getattr(args, 'hours', 24)}h, showing up to {getattr(args, 'limit', 20)})")
        output.append("=" * 70)
        
        for op in operations:
            status_emoji = "✅" if op['success'] else "❌"
            output.append(f"\n{status_emoji} {op['operation_type'].upper()}")
            output.append(f"  Path: {op['path']}")
            if op.get('backend_name'):
                output.append(f"  Backend: {op['backend_name']}")
            if op.get('size'):
                output.append(f"  Size: {op['size']:,} bytes")
            output.append(f"  Time: {op.get('datetime', 'unknown')}")
            if op.get('duration_ms'):
                output.append(f"  Duration: {op['duration_ms']}ms")
            if not op['success'] and op.get('error_message'):
                output.append(f"  Error: {op['error_message']}")
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: FS Journal fast index not available."
    except Exception as e:
        return f"Error getting recent operations: {e}"

def handle_fs_failed(api, args, kwargs=None):
    """Handle FS Journal failed operations command."""
    try:
        from fs_journal_fast_index import FastFSJournalReader
        
        reader = FastFSJournalReader()
        operations = reader.list_failed_operations(limit=args.limit, hours=args.hours)
        
        if not operations:
            return f"No failed operations found in the last {args.hours} hours."
        
        if isinstance(operations, list) and len(operations) == 1 and 'error' in operations[0]:
            return f"Error: {operations[0]['error']}"
        
        # Format output
        output = []
        output.append(f"❌ Failed Operations (last {args.hours}h, showing up to {args.limit})")
        output.append("=" * 70)
        
        for op in operations:
            output.append(f"\n🔹 {op['operation_type'].upper()}")
            output.append(f"  Path: {op['path']}")
            if op.get('backend_name'):
                output.append(f"  Backend: {op['backend_name']}")
            if op.get('size'):
                output.append(f"  Size: {op['size']:,} bytes")
            output.append(f"  Time: {op.get('datetime', 'unknown')}")
            if op.get('duration_ms'):
                output.append(f"  Duration: {op['duration_ms']}ms")
            if op.get('error_message'):
                output.append(f"  Error: {op['error_message']}")
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: FS Journal fast index not available."
    except Exception as e:
        return f"Error getting failed operations: {e}"

def handle_fs_files(api, args, kwargs=None):
    """Handle FS Journal files listing command."""
    try:
        from fs_journal_fast_index import FastFSJournalReader
        
        reader = FastFSJournalReader()
        files = reader.list_virtual_files(path_prefix=args.path, limit=args.limit)
        
        if not files:
            prefix_msg = f" with prefix '{args.path}'" if args.path else ""
            return f"No files found{prefix_msg}."
        
        if isinstance(files, list) and len(files) == 1 and 'error' in files[0]:
            return f"Error: {files[0]['error']}"
        
        # Format output
        output = []
        prefix_msg = f" (prefix: '{args.path}')" if args.path else ""
        output.append(f"📁 Virtual Filesystem{prefix_msg} (showing up to {args.limit})")
        output.append("=" * 70)
        
        # Group by directories and files
        directories = [f for f in files if f['file_type'] == 'directory']
        files_only = [f for f in files if f['file_type'] == 'file']
        
        if directories:
            output.append("\n📂 Directories:")
            for dir_info in sorted(directories, key=lambda x: x['path']):
                output.append(f"  📂 {dir_info['path']}")
                if dir_info.get('backend_name'):
                    output.append(f"     Backend: {dir_info['backend_name']}")
                output.append(f"     Modified: {dir_info.get('modified_datetime', 'unknown')}")
        
        if files_only:
            output.append(f"\n📄 Files ({len(files_only)}):")
            total_size = 0
            for file_info in sorted(files_only, key=lambda x: x['path']):
                size_str = f" ({file_info['size']:,} bytes)" if file_info.get('size') else ""
                output.append(f"  📄 {file_info['path']}{size_str}")
                if file_info.get('backend_name'):
                    output.append(f"     Backend: {file_info['backend_name']}")
                if file_info.get('hash'):
                    output.append(f"     Hash: {file_info['hash'][:16]}...")
                output.append(f"     Modified: {file_info.get('modified_datetime', 'unknown')}")
                if file_info.get('size'):
                    total_size += file_info['size']
            
            if total_size > 0:
                output.append(f"\n💾 Total Size: {total_size:,} bytes ({total_size/1024/1024:.1f} MB)")
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: FS Journal fast index not available."
    except Exception as e:
        return f"Error listing files: {e}"

def handle_fs_info(api, args, kwargs=None):
    """Handle FS Journal file info command."""
    try:
        from fs_journal_fast_index import FastFSJournalReader
        
        reader = FastFSJournalReader()
        file_info = reader.get_file_info(args.path)
        
        if not file_info:
            return f"File not found: {args.path}"
        
        if 'error' in file_info:
            return f"Error: {file_info['error']}"
        
        # Format output
        output = []
        output.append(f"📄 File Information: {args.path}")
        output.append("=" * 70)
        
        # Basic info
        file_type_emoji = "📂" if file_info['file_type'] == 'directory' else "📄"
        output.append(f"Type: {file_type_emoji} {file_info['file_type']}")
        
        if file_info.get('size'):
            output.append(f"Size: {file_info['size']:,} bytes ({file_info['size']/1024/1024:.1f} MB)")
        
        if file_info.get('backend_name'):
            output.append(f"Backend: {file_info['backend_name']}")
        
        if file_info.get('hash'):
            output.append(f"Hash: {file_info['hash']}")
        
        output.append(f"Created: {file_info.get('created_datetime', 'unknown')}")
        output.append(f"Modified: {file_info.get('modified_datetime', 'unknown')}")
        
        # Metadata
        if file_info.get('metadata'):
            output.append("\n🏷️ Metadata:")
            for key, value in file_info['metadata'].items():
                output.append(f"  {key}: {value}")
        
        # Recent operations
        if file_info.get('recent_operations'):
            output.append("\n📋 Recent Operations:")
            for op in file_info['recent_operations']:
                status_emoji = "✅" if op['success'] else "❌"
                output.append(f"  {status_emoji} {op['operation_type']} - {op.get('datetime', 'unknown')}")
                if not op['success'] and op.get('error_message'):
                    output.append(f"     Error: {op['error_message']}")
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: FS Journal fast index not available."
    except Exception as e:
        return f"Error getting file info: {e}"

def handle_fs_stats(api, args, kwargs=None):
    """Handle FS Journal statistics command."""
    try:
        from fs_journal_fast_index import FastFSJournalReader
        
        reader = FastFSJournalReader()
        stats = reader.get_statistics(hours=args.hours)
        
        if 'error' in stats:
            return f"Error: {stats['error']}"
        
        # Format output
        output = []
        output.append(f"📈 FS Journal Statistics (last {args.hours} hours)")
        output.append("=" * 60)
        
        totals = stats.get('totals', {})
        output.append(f"Total Operations: {totals.get('total', 0)}")
        output.append(f"Successful: {totals.get('successful', 0)}")
        output.append(f"Failed: {totals.get('failed', 0)}")
        
        # Success rate
        total = totals.get('total', 0)
        successful = totals.get('successful', 0)
        if total > 0:
            success_rate = (successful / total) * 100
            output.append(f"Success Rate: {success_rate:.1f}%")
        
        # Average duration
        avg_duration = totals.get('avg_duration', 0)
        if avg_duration > 0:
            output.append(f"Average Duration: {avg_duration:.1f}ms")
        
        # Total data processed
        total_size = totals.get('total_size', 0)
        if total_size > 0:
            output.append(f"Total Data: {total_size:,} bytes ({total_size/1024/1024:.1f} MB)")
        
        # Breakdown by operation type
        breakdown = stats.get('breakdown', {})
        if breakdown:
            output.append("\n📊 Operation Breakdown:")
            for op_type, backends in breakdown.items():
                output.append(f"\n  {op_type.upper()}:")
                for backend, statuses in backends.items():
                    for status, data in statuses.items():
                        count = data['count']
                        avg_dur = data.get('avg_duration_ms', 0)
                        size = data.get('total_size', 0)
                        output.append(f"    {backend} ({status}): {count} ops")
                        if avg_dur > 0:
                            output.append(f"      Avg Duration: {avg_dur:.1f}ms")
                        if size > 0:
                            output.append(f"      Total Size: {size:,} bytes")
        
        output.append(f"\n🕐 Generated: {stats.get('generated_at', 'unknown')}")
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: FS Journal fast index not available."
    except Exception as e:
        return f"Error getting FS Journal statistics: {e}"

def handle_fs_health(api, args, kwargs=None):
    """Handle FS Journal health check command."""
    try:
        from fs_journal_fast_index import FastFSJournalReader
        
        reader = FastFSJournalReader()
        health = reader.health_check()
        
        # Format output
        output = []
        status_emoji = "✅" if health['status'] == 'healthy' else "❌"
        output.append(f"{status_emoji} FS Journal Health Check")
        output.append("=" * 50)
        output.append(f"Status: {health['status']}")
        
        if health.get('database_accessible'):
            output.append("✅ Database: Accessible")
            output.append(f"📊 Total Operations: {health.get('total_operations', 0)}")
            output.append(f"📁 Virtual Files: {health.get('virtual_files', 0)}")
            output.append(f"📄 Parquet Files: {health.get('parquet_files', 0)}")
        else:
            output.append("❌ Database: Not accessible")
        
        if health.get('free_disk_gb') != 'unknown':
            output.append(f"💾 Free Disk Space: {health['free_disk_gb']:.1f} GB")
        
        output.append(f"📂 Base Path: {health.get('base_path', 'unknown')}")
        
        if 'error' in health:
            output.append(f"\n❌ Error: {health['error']}")
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: FS Journal fast index not available."
    except Exception as e:
        return f"Error checking FS Journal health: {e}"

# Standalone CLI for testing
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FS Journal CLI Tool")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    register_fs_journal_commands(subparsers)
    
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        result = args.func(None, args)
        print(result)
    else:
        parser.print_help()
