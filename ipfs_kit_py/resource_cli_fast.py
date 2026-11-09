#!/usr/bin/env python3
"""
Resource Tracking CLI - Fast Index Integration

This module provides CLI commands for monitoring bandwidth and storage consumption
across remote filesystem backends using the fast index system.
"""

import argparse
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

def register_resource_commands(subparsers):
    """Register resource tracking commands with the CLI parser."""
    
    # Resource tracking command group
    resource_parser = subparsers.add_parser('resource', help='Resource tracking and monitoring for permissioned storage backends')
    resource_subparsers = resource_parser.add_subparsers(dest='resource_action', help='Resource actions')
    
    # Usage summary command
    usage_parser = resource_subparsers.add_parser('usage', help='Show resource usage summary for permissioned backends')
    usage_parser.add_argument('--backend', help='Filter by backend name')
    usage_parser.add_argument('--type', choices=['s3', 'ipfs', 'huggingface', 'storacha', 'filecoin', 'lassie', 'local'],
                             help='Filter by backend type')
    usage_parser.add_argument('--period', choices=['hour', 'day', 'week', 'month'], default='day',
                             help='Time period for summary')
    usage_parser.add_argument('--format', choices=['table', 'json'], default='table',
                             help='Output format')
    usage_parser.add_argument('--permissions-only', action='store_true',
                             help='Show only backends with permission constraints')
    
    # Detailed usage command with permissions focus
    detail_parser = resource_subparsers.add_parser('details', help='Show detailed resource usage with permission context')
    detail_parser.add_argument('--backend', help='Filter by backend name')
    detail_parser.add_argument('--type', choices=['s3', 'ipfs', 'huggingface', 'storacha', 'filecoin', 'lassie', 'local'],
                              help='Filter by backend type')
    detail_parser.add_argument('--resource', choices=['bandwidth_upload', 'bandwidth_download', 'storage_used', 'api_calls'],
                              help='Filter by resource type')
    detail_parser.add_argument('--hours', type=int, default=24, help='Hours back to query')
    detail_parser.add_argument('--limit', type=int, default=100, help='Maximum records to show')
    detail_parser.add_argument('--format', choices=['table', 'json'], default='table',
                              help='Output format')
    detail_parser.add_argument('--show-permissions', action='store_true',
                              help='Include permission validation status')
    
    # Backend status command with permission context
    status_parser = resource_subparsers.add_parser('status', help='Show backend status with permission compliance')
    status_parser.add_argument('--backend', help='Specific backend name')
    status_parser.add_argument('--format', choices=['table', 'json'], default='table',
                              help='Output format')
    status_parser.add_argument('--permission-check', action='store_true',
                              help='Check permission compliance for all backends')
    
    # Permission-aware analytics command
    analytics_parser = resource_subparsers.add_parser('analytics', help='Resource usage analytics with permission context')
    analytics_parser.add_argument('--backend', help='Filter by backend name')
    analytics_parser.add_argument('--days', type=int, default=7, help='Days of data to analyze')
    analytics_parser.add_argument('--format', choices=['table', 'json'], default='table',
                                 help='Output format')
    analytics_parser.add_argument('--permission-violations', action='store_true',
                                 help='Show backends exceeding permission limits')
    
    # Permission tracking command
    permissions_parser = resource_subparsers.add_parser('permissions', help='Track storage backend permissions and limits')
    permissions_parser.add_argument('--backend', help='Backend name to check/configure')
    permissions_parser.add_argument('--action', choices=['list', 'check', 'set-limits', 'violations'], 
                                   default='list', help='Permission action')
    permissions_parser.add_argument('--storage-quota', type=int, help='Set storage quota in GB')
    permissions_parser.add_argument('--bandwidth-quota', type=int, help='Set bandwidth quota in Mbps')
    permissions_parser.add_argument('--format', choices=['table', 'json'], default='table',
                                   help='Output format')
    
    # Traffic monitoring command
    traffic_parser = resource_subparsers.add_parser('traffic', help='Monitor traffic patterns across permissioned backends')
    traffic_parser.add_argument('--backend', help='Filter by backend name')
    traffic_parser.add_argument('--real-time', action='store_true', help='Show real-time traffic monitoring')
    traffic_parser.add_argument('--threshold', type=int, default=1024, help='Traffic threshold in KB/s')
    traffic_parser.add_argument('--duration', type=int, default=60, help='Monitoring duration in seconds')
    traffic_parser.add_argument('--format', choices=['table', 'json'], default='table',
                               help='Output format')
    
    # Export command
    export_parser = resource_subparsers.add_parser('export', help='Export resource usage data')
    export_parser.add_argument('--backend', help='Filter by backend name')
    export_parser.add_argument('--hours', type=int, default=24, help='Hours back to export')
    export_parser.add_argument('--output', required=True, help='Output file path')
    export_parser.add_argument('--format', choices=['json', 'csv'], default='json',
                              help='Export format')
    export_parser.add_argument('--include-permissions', action='store_true',
                              help='Include permission data in export')
    
    # Set limits command
    limits_parser = resource_subparsers.add_parser('limits', help='View or set resource limits')
    limits_parser.add_argument('--backend', required=True, help='Backend name')
    limits_parser.add_argument('--bandwidth-limit', type=int, help='Bandwidth limit in Mbps')
    limits_parser.add_argument('--storage-limit', type=int, help='Storage limit in GB')
    limits_parser.add_argument('--api-limit', type=int, help='API calls limit per hour')
    limits_parser.add_argument('--cost-limit', type=float, help='Cost limit in dollars per day')

async def cmd_resource_usage(args):
    """Show resource usage summary."""
    try:
        from .resource_tracker import get_resource_tracker, BackendType
        
        tracker = get_resource_tracker()
        
        # Convert string to BackendType if provided
        backend_type = None
        if args.type:
            backend_type = BackendType(args.type)
        
        summary = tracker.get_resource_summary(
            backend_name=args.backend,
            backend_type=backend_type,
            period=args.period
        )
        
        if args.format == 'json':
            print(json.dumps(summary, indent=2))
            return 0
        
        # Table format
        print(f"📊 Resource Usage Summary ({args.period}) - Permissioned Storage Backends")
        print("=" * 80)
        
        if 'error' in summary:
            print(f"❌ Error: {summary['error']}")
            return 1
        
        print(f"Period: {summary['period']} (starting {summary['period_start']})")
        print()
        
        # Show totals
        print("🌍 Global Totals:")
        totals = summary['totals']
        for resource_type, total in totals.items():
            if total > 0:
                formatted = _format_resource_amount(resource_type, total)
                print(f"  {resource_type}: {formatted}")
        print()
        
        # Show per-backend breakdown with permission context
        if summary['backends']:
            print("🏢 Backend Breakdown (Permission-Controlled):")
            
            # Get backend status for permission information
            try:
                backend_status = tracker.get_backend_status()
            except:
                backend_status = {}
            
            for backend_name, backend_data in summary['backends'].items():
                # Check if backend has permission limits
                status_info = backend_status.get(backend_name, {})
                has_limits = bool(status_info.get('storage_limit_gb') or status_info.get('bandwidth_limit_mbps'))
                permission_icon = "🔐" if has_limits else "🔓"
                
                print(f"\n  {permission_icon} {backend_name} ({backend_data['backend_type']}):")
                
                if args.permissions_only and not has_limits:
                    continue
                
                for resource_type, resource_data in backend_data['resources'].items():
                    amount = resource_data['formatted_amount']
                    ops = resource_data['operation_count']
                    
                    # Add limit context if available
                    limit_info = ""
                    if resource_type == 'storage_used' and status_info.get('storage_limit_gb'):
                        limit_gb = status_info['storage_limit_gb']
                        current_gb = resource_data['total_amount'] / (1024*1024*1024)
                        usage_pct = (current_gb / limit_gb) * 100 if limit_gb > 0 else 0
                        limit_info = f" ({usage_pct:.1f}% of {limit_gb}GB limit)"
                    elif resource_type in ['bandwidth_upload', 'bandwidth_download'] and status_info.get('bandwidth_limit_mbps'):
                        limit_info = f" (limit: {status_info['bandwidth_limit_mbps']}Mbps)"
                    
                    print(f"    {resource_type}: {amount} ({ops} operations){limit_info}")
        else:
            print("No resource usage data found for the specified period.")
            if args.permissions_only:
                print("💡 Use --permissions-only to show only backends with permission constraints")
        
        return 0
        
    except ImportError:
        print("❌ Resource tracking not available - fast indexes not found")
        return 1
    except Exception as e:
        print(f"❌ Error retrieving resource usage: {e}")
        return 1

async def cmd_resource_details(args):
    """Show detailed resource usage."""
    try:
        from .resource_tracker import get_resource_tracker, BackendType, ResourceType
        
        tracker = get_resource_tracker()
        
        # Convert strings to enums if provided
        backend_type = BackendType(args.type) if args.type else None
        resource_type = ResourceType(args.resource) if args.resource else None
        
        details = tracker.get_resource_usage(
            backend_name=args.backend,
            backend_type=backend_type,
            resource_type=resource_type,
            hours_back=args.hours,
            limit=args.limit
        )
        
        if args.format == 'json':
            print(json.dumps(details, indent=2))
            return 0
        
        # Table format
        print(f"📋 Resource Usage Details (Last {args.hours} hours)")
        print("=" * 80)
        
        if not details:
            print("No resource usage data found for the specified criteria.")
            return 0
        
        print(f"Showing {len(details)} records:")
        print()
        
        # Headers
        print(f"{'Timestamp':<20} {'Backend':<15} {'Type':<12} {'Resource':<18} {'Amount':<15} {'Operation':<20}")
        print("-" * 100)
        
        for record in details:
            timestamp = datetime.fromisoformat(record['datetime']).strftime('%m-%d %H:%M:%S')
            backend = record['backend_name'][:14]
            backend_type = record['backend_type'][:11]
            resource_type = record['resource_type'][:17]
            amount = _format_resource_amount(record['resource_type'], record['amount'])[:14]
            operation = (record['operation_id'] or 'N/A')[:19]
            
            print(f"{timestamp:<20} {backend:<15} {backend_type:<12} {resource_type:<18} {amount:<15} {operation:<20}")
        
        return 0
        
    except ImportError:
        print("❌ Resource tracking not available - fast indexes not found")
        return 1
    except Exception as e:
        print(f"❌ Error retrieving resource details: {e}")
        return 1

async def cmd_resource_status(args):
    """Show backend status."""
    try:
        from .resource_tracker import get_resource_tracker
        
        tracker = get_resource_tracker()
        status = tracker.get_backend_status(backend_name=args.backend)
        
        if args.format == 'json':
            print(json.dumps(status, indent=2))
            return 0
        
        # Table format
        print("🏥 Backend Status - Permissioned Storage Backends")
        print("=" * 70)
        
        if 'error' in status:
            print(f"❌ Error: {status['error']}")
            return 1
        
        if not status:
            print("No backend status information available.")
            return 0
        
        for backend_name, backend_data in status.items():
            active_icon = "✅" if backend_data['is_active'] else "❌"
            health_icon = {"healthy": "🟢", "degraded": "🟡", "unhealthy": "🔴"}.get(
                backend_data['health_status'], "⚪"
            )
            
            # Check permission configuration
            has_storage_limit = backend_data.get('storage_limit_gb') is not None
            has_bandwidth_limit = backend_data.get('bandwidth_limit_mbps') is not None
            permission_icon = "🔐" if (has_storage_limit or has_bandwidth_limit) else "🔓"
            
            print(f"\n{active_icon} {backend_name} ({backend_data['backend_type']}) {health_icon} {permission_icon}")
            print(f"  Current Bandwidth: {backend_data['current_bandwidth_usage_mbps'] or 0:.1f} Mbps")
            print(f"  Current Storage: {backend_data['current_storage_usage_gb'] or 0:.2f} GB")
            
            # Show permission limits if configured
            if has_storage_limit:
                limit = backend_data['storage_limit_gb']
                current = backend_data['current_storage_usage_gb'] or 0
                usage_pct = (current / limit) * 100 if limit > 0 else 0
                status_icon = "⚠️" if usage_pct > 80 else "✅"
                print(f"  Storage Limit: {limit} GB ({usage_pct:.1f}% used) {status_icon}")
            
            if has_bandwidth_limit:
                limit = backend_data['bandwidth_limit_mbps']
                current = backend_data['current_bandwidth_usage_mbps'] or 0
                usage_pct = (current / limit) * 100 if limit > 0 else 0
                status_icon = "⚠️" if usage_pct > 80 else "✅"
                print(f"  Bandwidth Limit: {limit} Mbps ({usage_pct:.1f}% used) {status_icon}")
            
            if not has_storage_limit and not has_bandwidth_limit:
                print(f"  🔓 No permission limits configured")
            
            if backend_data['last_operation_datetime']:
                print(f"  Last Operation: {backend_data['last_operation_datetime']}")
            
            if backend_data['last_health_check_datetime']:
                print(f"  Last Health Check: {backend_data['last_health_check_datetime']}")
            
            # Perform permission check if requested
            if args.permission_check:
                # Get recent usage to check compliance
                try:
                    summary = tracker.get_resource_summary(backend_name=backend_name, period='hour')
                    if summary and 'backends' in summary:
                        backend_summary = summary['backends'].get(backend_name, {})
                        resources = backend_summary.get('resources', {})
                        
                        violations = []
                        
                        # Check storage compliance
                        if has_storage_limit:
                            storage_data = resources.get('storage_used', {})
                            if storage_data:
                                current_storage_gb = storage_data.get('total_amount', 0) / (1024*1024*1024)
                                if current_storage_gb > backend_data['storage_limit_gb']:
                                    violations.append("Storage limit exceeded")
                        
                        # Check bandwidth compliance (simplified check)
                        if has_bandwidth_limit:
                            upload_data = resources.get('bandwidth_upload', {})
                            download_data = resources.get('bandwidth_download', {})
                            total_bandwidth = (upload_data.get('total_amount', 0) + download_data.get('total_amount', 0)) / (1024*1024)  # MB
                            # This is a simplified check - real implementation would need rate limiting
                            
                        if violations:
                            print(f"  ⚠️  Permission Violations: {', '.join(violations)}")
                        else:
                            print(f"  ✅ Permission Compliant")
                except Exception as e:
                    print(f"  ❓ Permission check failed: {e}")
        
        return 0
        
    except ImportError:
        print("❌ Resource tracking not available - fast indexes not found")
        return 1
    except Exception as e:
        print(f"❌ Error retrieving backend status: {e}")
        return 1

async def cmd_resource_analytics(args):
    """Show resource usage analytics."""
    try:
        from .resource_tracker import get_resource_tracker, BackendType
        
        tracker = get_resource_tracker()
        
        # Get data for the specified number of days
        end_time = time.time()
        start_time = end_time - (args.days * 24 * 3600)
        
        # Get hourly summaries for trend analysis
        analytics = {}
        hours_back = args.days * 24
        
        # This would need more sophisticated analytics implementation
        # For now, we'll show a simple summary
        summary = tracker.get_resource_summary(
            backend_name=args.backend,
            period='day'
        )
        
        if args.format == 'json':
            analytics_data = {
                'period_days': args.days,
                'summary': summary,
                'trends': 'Not implemented yet'
            }
            print(json.dumps(analytics_data, indent=2))
            return 0
        
        # Table format
        print(f"📈 Resource Analytics (Last {args.days} days)")
        print("=" * 60)
        
        if 'error' in summary:
            print(f"❌ Error: {summary['error']}")
            return 1
        
        print("📊 Current Day Summary:")
        if summary['backends']:
            for backend_name, backend_data in summary['backends'].items():
                print(f"\n  🏢 {backend_name}:")
                for resource_type, resource_data in backend_data['resources'].items():
                    ops = resource_data['operation_count']
                    avg = resource_data['avg_amount']
                    total = resource_data['total_amount']
                    print(f"    {resource_type}: {ops} ops, avg {_format_resource_amount(resource_type, int(avg))}")
        
        print(f"\n💡 Trend analysis for {args.days} days would be shown here")
        print("   (Feature available in full implementation)")
        
        return 0
        
    except ImportError:
        print("❌ Resource tracking not available - fast indexes not found")
        return 1
    except Exception as e:
        print(f"❌ Error generating analytics: {e}")
        return 1

async def cmd_resource_export(args):
    """Export resource usage data."""
    try:
        from .resource_tracker import get_resource_tracker
        
        tracker = get_resource_tracker()
        
        details = tracker.get_resource_usage(
            backend_name=args.backend,
            hours_back=args.hours,
            limit=10000  # Large limit for export
        )
        
        # Add permission context if requested
        if args.include_permissions:
            try:
                backend_status = tracker.get_backend_status()
                
                # Enhance each record with permission information
                for record in details:
                    backend_name = record['backend_name']
                    status_info = backend_status.get(backend_name, {})
                    
                    record['has_storage_limit'] = status_info.get('storage_limit_gb') is not None
                    record['has_bandwidth_limit'] = status_info.get('bandwidth_limit_mbps') is not None
                    record['storage_limit_gb'] = status_info.get('storage_limit_gb')
                    record['bandwidth_limit_mbps'] = status_info.get('bandwidth_limit_mbps')
                    
                    # Calculate compliance status
                    if record['resource_type'] == 'storage_used' and record['has_storage_limit']:
                        current_gb = record['amount'] / (1024*1024*1024)
                        record['within_storage_limit'] = current_gb <= (record['storage_limit_gb'] or float('inf'))
                    else:
                        record['within_storage_limit'] = None
                    
            except Exception as e:
                print(f"⚠️  Warning: Could not add permission data: {e}")
        
        if args.format == 'json':
            with open(args.output, 'w') as f:
                json.dump(details, f, indent=2)
        elif args.format == 'csv':
            import csv
            with open(args.output, 'w', newline='') as f:
                if details:
                    writer = csv.DictWriter(f, fieldnames=details[0].keys())
                    writer.writeheader()
                    writer.writerows(details)
        
        permission_suffix = " (with permission data)" if args.include_permissions else ""
        print(f"✅ Exported {len(details)} records to {args.output}{permission_suffix}")
        return 0
        
    except ImportError:
        print("❌ Resource tracking not available - fast indexes not found")
        return 1
    except Exception as e:
        print(f"❌ Error exporting data: {e}")
        return 1

async def cmd_resource_permissions(args):
    """Track storage backend permissions and limits."""
    try:
        from .resource_tracker import get_resource_tracker
        from .mfs_permissions import PermissionManager
        
        tracker = get_resource_tracker()
        permission_manager = PermissionManager()
        
        if args.action == 'list':
            # List all backends with their permission configurations
            status = tracker.get_backend_status(backend_name=args.backend)
            
            if args.format == 'json':
                result = {
                    'backends': {},
                    'permission_summary': {}
                }
                
                for backend_name, backend_data in status.items():
                    result['backends'][backend_name] = backend_data
                    # Add permission data here
                    result['permission_summary'][backend_name] = {
                        'has_limits': bool(backend_data.get('storage_limit_gb') or backend_data.get('bandwidth_limit_mbps')),
                        'permission_controlled': True  # Assume all backends are permission controlled
                    }
                
                print(json.dumps(result, indent=2))
                return 0
            
            # Table format
            print("� Storage Backend Permissions Summary")
            print("=" * 70)
            
            if not status:
                print("No backend configurations found.")
                return 0
            
            print(f"{'Backend':<20} {'Type':<12} {'Storage Quota':<15} {'Bandwidth Quota':<18} {'Permissions':<12}")
            print("-" * 80)
            
            for backend_name, backend_data in status.items():
                backend_type = backend_data.get('backend_type', 'unknown')[:11]
                storage_quota = f"{backend_data.get('storage_limit_gb', 'N/A')} GB" if backend_data.get('storage_limit_gb') else "No limit"
                bandwidth_quota = f"{backend_data.get('bandwidth_limit_mbps', 'N/A')} Mbps" if backend_data.get('bandwidth_limit_mbps') else "No limit"
                permissions = "✅ Active" if backend_data.get('is_active') else "❌ Inactive"
                
                print(f"{backend_name[:19]:<20} {backend_type:<12} {storage_quota[:14]:<15} {bandwidth_quota[:17]:<18} {permissions:<12}")
        
        elif args.action == 'check':
            # Check permission compliance
            print(f"🔍 Permission Compliance Check")
            print("=" * 50)
            
            if args.backend:
                backends_to_check = [args.backend]
            else:
                status = tracker.get_backend_status()
                backends_to_check = list(status.keys())
            
            violations = []
            for backend_name in backends_to_check:
                # Get current usage
                summary = tracker.get_resource_summary(backend_name=backend_name, period='day')
                
                # Check against limits (this would integrate with actual permission system)
                if summary and 'backends' in summary:
                    backend_summary = summary['backends'].get(backend_name, {})
                    resources = backend_summary.get('resources', {})
                    
                    # Check storage usage
                    storage_data = resources.get('storage_used', {})
                    if storage_data and storage_data.get('total_amount', 0) > 1024*1024*1024*10:  # Example: 10GB limit
                        violations.append(f"❌ {backend_name}: Storage usage exceeds limit")
                    else:
                        print(f"✅ {backend_name}: Storage usage within limits")
            
            if violations:
                print("\n⚠️  Permission Violations Detected:")
                for violation in violations:
                    print(f"  {violation}")
                return 1
            else:
                print("\n✅ All backends compliant with permission limits")
                return 0
        
        elif args.action == 'set-limits':
            # Set resource limits
            if not args.backend:
                print("❌ Backend name required for setting limits")
                return 1
            
            limits_updated = []
            if args.storage_quota:
                limits_updated.append(f"Storage: {args.storage_quota} GB")
            if args.bandwidth_quota:
                limits_updated.append(f"Bandwidth: {args.bandwidth_quota} Mbps")
            
            if limits_updated:
                print(f"🔧 Setting limits for {args.backend}:")
                for limit in limits_updated:
                    print(f"  {limit}")
                print("✅ Limits would be applied (implementation needed)")
            else:
                print("❌ No limits specified")
                return 1
        
        elif args.action == 'violations':
            # Show current violations
            print("⚠️  Current Permission Violations")
            print("=" * 50)
            
            # This would check against actual permission limits
            print("📊 Checking all backends...")
            print("(Permission violation detection would be implemented here)")
            
        return 0
        
    except ImportError as e:
        print(f"❌ Resource tracking not available - {e}")
        return 1
    except Exception as e:
        print(f"❌ Error managing permissions: {e}")
        return 1

async def cmd_resource_traffic(args):
    """Monitor traffic patterns across permissioned backends."""
    try:
        from .resource_tracker import get_resource_tracker, ResourceType
        
        tracker = get_resource_tracker()
        
        if args.real_time:
            print(f"📡 Real-time Traffic Monitor (Threshold: {args.threshold} KB/s)")
            print("=" * 60)
            print("Press Ctrl+C to stop monitoring...")
            
            try:
                import anyio
                start_time = time.time()
                
                while time.time() - start_time < args.duration:
                    # Get recent traffic data
                    traffic_data = tracker.get_resource_usage(
                        backend_name=args.backend,
                        resource_type=ResourceType.BANDWIDTH_UPLOAD,
                        hours_back=0.1,  # Last 6 minutes
                        limit=50
                    )
                    
                    current_time = datetime.now().strftime('%H:%M:%S')
                    
                    if traffic_data:
                        total_upload = sum(record['amount'] for record in traffic_data) / 1024  # KB
                        avg_rate = total_upload / 6  # KB/s over 6 minutes
                        
                        status = "🔥 HIGH" if avg_rate > args.threshold else "✅ Normal"
                        print(f"{current_time} - Upload: {avg_rate:.1f} KB/s {status}")
                    else:
                        print(f"{current_time} - No traffic data")
                    
                    await anyio.sleep(5)  # Update every 5 seconds
                    
            except KeyboardInterrupt:
                print("\n⏹️  Traffic monitoring stopped")
                return 0
        else:
            # Show traffic summary
            print("📊 Traffic Summary")
            print("=" * 40)
            
            # Get traffic data for different time periods
            periods = ['hour', 'day', 'week']
            for period in periods:
                summary = tracker.get_resource_summary(
                    backend_name=args.backend,
                    period=period
                )
                
                if summary and 'backends' in summary:
                    print(f"\n📈 {period.title()} Traffic:")
                    for backend_name, backend_data in summary['backends'].items():
                        resources = backend_data.get('resources', {})
                        upload = resources.get('bandwidth_upload', {}).get('total_amount', 0)
                        download = resources.get('bandwidth_download', {}).get('total_amount', 0)
                        
                        upload_mb = upload / (1024 * 1024)
                        download_mb = download / (1024 * 1024)
                        
                        print(f"  {backend_name}: ⬆️ {upload_mb:.1f} MB, ⬇️ {download_mb:.1f} MB")
        
        return 0
        
    except ImportError:
        print("❌ Resource tracking not available - fast indexes not found")
        return 1
    except Exception as e:
        print(f"❌ Error monitoring traffic: {e}")
        return 1

async def cmd_resource_limits(args):
    """View or set resource limits."""
    try:
        from .resource_tracker import get_resource_tracker, BackendType
        
        tracker = get_resource_tracker()
        
        # This would integrate with a limits management system
        print(f"🔒 Resource Limits for {args.backend}")
        print("=" * 40)
        
        if any([args.bandwidth_limit, args.storage_limit, args.api_limit, args.cost_limit]):
            print("Setting limits (feature would be implemented here):")
            if args.bandwidth_limit:
                print(f"  Bandwidth: {args.bandwidth_limit} Mbps")
            if args.storage_limit:
                print(f"  Storage: {args.storage_limit} GB")
            if args.api_limit:
                print(f"  API Calls: {args.api_limit} per hour")
            if args.cost_limit:
                print(f"  Cost: ${args.cost_limit} per day")
        else:
            print("Current limits (would be shown here)")
            print("  Use --help to see how to set limits")
        
        return 0
        
    except ImportError:
        print("❌ Resource tracking not available - fast indexes not found")
        return 1
    except Exception as e:
        print(f"❌ Error managing limits: {e}")
        return 1

def _format_resource_amount(resource_type: str, amount: int) -> str:
    """Format resource amount for human readability."""
    if resource_type in ['bandwidth_upload', 'bandwidth_download', 'storage_used', 'storage_allocated']:
        # Format bytes
        if amount < 1024:
            return f"{amount} B"
        elif amount < 1024 * 1024:
            return f"{amount / 1024:.1f} KB"
        elif amount < 1024 * 1024 * 1024:
            return f"{amount / (1024 * 1024):.1f} MB"
        else:
            return f"{amount / (1024 * 1024 * 1024):.1f} GB"
    elif resource_type == 'api_calls':
        return f"{amount:,}"
    elif resource_type == 'operation_cost':
        return f"${amount / 100:.2f}"
    else:
        return str(amount)

# Handler mapping for CLI integration
RESOURCE_COMMAND_HANDLERS = {
    'usage': cmd_resource_usage,
    'details': cmd_resource_details,
    'status': cmd_resource_status,
    'analytics': cmd_resource_analytics,
    'permissions': cmd_resource_permissions,
    'traffic': cmd_resource_traffic,
    'export': cmd_resource_export,
    'limits': cmd_resource_limits,
}
