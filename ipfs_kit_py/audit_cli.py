#!/usr/bin/env python3
# ipfs_kit_py/audit_cli.py

"""
Audit CLI Module for IPFS Kit

This module provides CLI commands for audit logging operations including
viewing, querying, exporting, and reporting on audit events.

Following the standard architecture pattern:
Core (audit_logging.py) → CLI Integration (this file) → Unified CLI
"""

import argparse
import json
import sys
from typing import Optional

# Import core audit MCP tools
from ipfs_kit_py.mcp.servers.audit_mcp_tools import (
    audit_view,
    audit_query,
    audit_export,
    audit_report,
    audit_statistics,
    audit_track_backend,
    audit_track_vfs,
    audit_integrity_check,
    audit_retention_policy
)


def audit_view_cli(args):
    """CLI handler for viewing audit events."""
    result = audit_view(
        limit=args.limit,
        event_type=args.event_type,
        action=args.action,
        user_id=args.user_id,
        status=args.status,
        hours_ago=args.hours
    )
    
    if result.get("success"):
        print(f"Found {result['count']} audit events")
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for event in result.get("events", []):
                print(f"\nEvent Type: {event['event_type']}")
                print(f"Action: {event['action']}")
                print(f"User: {event.get('user_id', 'N/A')}")
                print(f"Status: {event.get('status', 'N/A')}")
                print(f"Time: {event['timestamp']}")
                if event.get('details'):
                    print(f"Details: {event['details']}")
        return 0
    else:
        print(f"Error: {result.get('error')}", file=sys.stderr)
        return 1


def audit_query_cli(args):
    """CLI handler for querying audit events."""
    result = audit_query(
        start_time=args.start_time,
        end_time=args.end_time,
        event_types=args.event_types.split(',') if args.event_types else None,
        users=args.users.split(',') if args.users else None,
        resources=args.resources.split(',') if args.resources else None,
        statuses=args.statuses.split(',') if args.statuses else None,
        limit=args.limit
    )
    
    if result.get("success"):
        print(f"Query returned {result['count']} events")
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for event in result.get("events", []):
                print(f"\n{event['event_type']}: {event['action']}")
                print(f"  User: {event.get('user_id', 'N/A')}")
                print(f"  Status: {event.get('status', 'N/A')}")
                print(f"  Time: {event['timestamp']}")
        return 0
    else:
        print(f"Error: {result.get('error')}", file=sys.stderr)
        return 1


def audit_export_cli(args):
    """CLI handler for exporting audit events."""
    result = audit_export(
        format=args.format,
        output_path=args.output,
        event_type=args.event_type,
        hours_ago=args.hours
    )
    
    if result.get("success"):
        if args.output:
            print(f"Exported {result['count']} events to {result['output_path']}")
            print(f"Format: {result['format']}")
            print(f"File size: {result.get('file_size_bytes', 0)} bytes")
        else:
            print(result['data'])
        return 0
    else:
        print(f"Error: {result.get('error')}", file=sys.stderr)
        return 1


def audit_report_cli(args):
    """CLI handler for generating audit reports."""
    result = audit_report(
        report_type=args.type,
        hours_ago=args.hours,
        group_by=args.group_by
    )
    
    if result.get("success"):
        print(f"Report Type: {result['report_type']}")
        print(f"Time Range: Last {result['time_range_hours']} hours")
        print(f"Generated: {result['generated_at']}")
        print("\nReport Data:")
        print(json.dumps(result['report_data'], indent=2))
        return 0
    else:
        print(f"Error: {result.get('error')}", file=sys.stderr)
        return 1


def audit_stats_cli(args):
    """CLI handler for audit statistics."""
    result = audit_statistics(hours_ago=args.hours)
    
    if result.get("success"):
        stats = result['statistics']
        print("Audit Statistics")
        print("=" * 50)
        print(f"Total Events: {stats['total_events']}")
        print(f"Unique Users: {stats['unique_users']}")
        print(f"Unique Resources: {stats['unique_resources']}")
        print(f"Success Rate: {stats['success_rate']:.2f}%")
        print(f"\nEvent Types:")
        for event_type, count in stats['event_types'].items():
            print(f"  {event_type}: {count}")
        print(f"\nTop Actions:")
        for action, count in sorted(stats['actions'].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {action}: {count}")
        
        if args.json:
            print("\n" + json.dumps(result, indent=2))
        return 0
    else:
        print(f"Error: {result.get('error')}", file=sys.stderr)
        return 1


def audit_track_cli(args):
    """CLI handler for tracking operations."""
    if args.resource_type == "backend":
        result = audit_track_backend(
            backend_id=args.resource_id,
            operation=args.operation,
            user_id=args.user_id,
            details=json.loads(args.details) if args.details else None
        )
    elif args.resource_type == "vfs":
        result = audit_track_vfs(
            bucket_id=args.resource_id,
            operation=args.operation,
            path=args.path,
            user_id=args.user_id,
            details=json.loads(args.details) if args.details else None
        )
    else:
        print(f"Error: Unknown resource type: {args.resource_type}", file=sys.stderr)
        return 1
    
    if result.get("success"):
        print(f"Tracked {args.resource_type} operation: {args.operation}")
        print(f"Resource ID: {args.resource_id}")
        print(f"Event ID: {result['event_id']}")
        print(f"Timestamp: {result['timestamp']}")
        return 0
    else:
        print(f"Error: {result.get('error')}", file=sys.stderr)
        return 1


def audit_integrity_cli(args):
    """CLI handler for integrity check."""
    result = audit_integrity_check()
    
    if result.get("success"):
        print(f"Audit Log Integrity Check")
        print("=" * 50)
        print(f"Integrity Valid: {'✓ YES' if result['integrity_valid'] else '✗ NO'}")
        print(f"Events Checked: {result['total_events_checked']}")
        
        if result.get('issues'):
            print("\nIssues Found:")
            for issue in result['issues']:
                print(f"  • {issue}")
        else:
            print("\nNo integrity issues found.")
        
        print(f"\nChecked at: {result['checked_at']}")
        return 0 if result['integrity_valid'] else 1
    else:
        print(f"Error: {result.get('error')}", file=sys.stderr)
        return 1


def audit_retention_cli(args):
    """CLI handler for retention policy."""
    result = audit_retention_policy(
        action=args.action,
        retention_days=args.retention_days,
        auto_cleanup=args.auto_cleanup
    )
    
    if result.get("success"):
        policy = result['current_policy']
        print("Audit Log Retention Policy")
        print("=" * 50)
        print(f"Retention Days: {policy['retention_days']}")
        print(f"Auto Cleanup: {'Enabled' if policy['auto_cleanup'] else 'Disabled'}")
        print(f"Max Cached Events: {policy['max_cached_events']}")
        
        if args.action == "set" and result.get('changes'):
            print("\nChanges Applied:")
            for key, value in result['changes'].items():
                print(f"  {key}: {value}")
        return 0
    else:
        print(f"Error: {result.get('error')}", file=sys.stderr)
        return 1


def main():
    """Main CLI entry point for audit commands."""
    parser = argparse.ArgumentParser(description="IPFS Kit Audit CLI")
    subparsers = parser.add_subparsers(dest="command", help="Audit command to execute")
    
    # audit view
    view_parser = subparsers.add_parser("view", help="View recent audit events")
    view_parser.add_argument("--limit", type=int, default=100, help="Maximum number of events")
    view_parser.add_argument("--event-type", help="Filter by event type")
    view_parser.add_argument("--action", help="Filter by action")
    view_parser.add_argument("--user-id", help="Filter by user ID")
    view_parser.add_argument("--status", help="Filter by status")
    view_parser.add_argument("--hours", type=int, default=24, help="Show events from last N hours")
    view_parser.add_argument("--json", action="store_true", help="Output as JSON")
    view_parser.set_defaults(func=audit_view_cli)
    
    # audit query
    query_parser = subparsers.add_parser("query", help="Query audit log with advanced filtering")
    query_parser.add_argument("--start-time", help="Start time (ISO format)")
    query_parser.add_argument("--end-time", help="End time (ISO format)")
    query_parser.add_argument("--event-types", help="Comma-separated list of event types")
    query_parser.add_argument("--users", help="Comma-separated list of user IDs")
    query_parser.add_argument("--resources", help="Comma-separated list of resource IDs")
    query_parser.add_argument("--statuses", help="Comma-separated list of statuses")
    query_parser.add_argument("--limit", type=int, default=1000, help="Maximum number of results")
    query_parser.add_argument("--json", action="store_true", help="Output as JSON")
    query_parser.set_defaults(func=audit_query_cli)
    
    # audit export
    export_parser = subparsers.add_parser("export", help="Export audit logs to file")
    export_parser.add_argument("--format", default="json", choices=["json", "jsonl", "csv"], help="Export format")
    export_parser.add_argument("--output", "-o", help="Output file path")
    export_parser.add_argument("--event-type", help="Filter by event type")
    export_parser.add_argument("--hours", type=int, default=24, help="Export events from last N hours")
    export_parser.set_defaults(func=audit_export_cli)
    
    # audit report
    report_parser = subparsers.add_parser("report", help="Generate audit reports")
    report_parser.add_argument("--type", default="summary", 
                               choices=["summary", "security", "compliance", "user_activity"],
                               help="Report type")
    report_parser.add_argument("--hours", type=int, default=24, help="Report for last N hours")
    report_parser.add_argument("--group-by", help="Group results by field")
    report_parser.set_defaults(func=audit_report_cli)
    
    # audit stats
    stats_parser = subparsers.add_parser("stats", help="Get audit statistics")
    stats_parser.add_argument("--hours", type=int, default=24, help="Statistics for last N hours")
    stats_parser.add_argument("--json", action="store_true", help="Output as JSON")
    stats_parser.set_defaults(func=audit_stats_cli)
    
    # audit track
    track_parser = subparsers.add_parser("track", help="Track operation in audit log")
    track_parser.add_argument("resource_type", choices=["backend", "vfs"], help="Resource type")
    track_parser.add_argument("resource_id", help="Resource ID")
    track_parser.add_argument("operation", help="Operation performed")
    track_parser.add_argument("--user-id", help="User ID")
    track_parser.add_argument("--path", help="Path (for VFS operations)")
    track_parser.add_argument("--details", help="Additional details (JSON string)")
    track_parser.set_defaults(func=audit_track_cli)
    
    # audit integrity
    integrity_parser = subparsers.add_parser("integrity", help="Check audit log integrity")
    integrity_parser.set_defaults(func=audit_integrity_cli)
    
    # audit retention
    retention_parser = subparsers.add_parser("retention", help="Manage retention policy")
    retention_parser.add_argument("action", choices=["get", "set"], help="Action to perform")
    retention_parser.add_argument("--retention-days", type=int, help="Retention period in days")
    retention_parser.add_argument("--auto-cleanup", type=lambda x: x.lower() == 'true', 
                                  help="Enable auto-cleanup (true/false)")
    retention_parser.set_defaults(func=audit_retention_cli)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
