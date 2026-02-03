#!/usr/bin/env python3
"""
Audit Analytics CLI Module for IPFS Kit

This module provides CLI commands for advanced audit analytics operations including
pattern recognition, anomaly detection, event correlation, and visual reporting.

Following the standard architecture pattern:
Core (audit_analytics.py) → CLI Integration (this file) → Unified CLI

Part of Phase 8: Enhanced Audit Capabilities
"""

import argparse
import json
import sys
from typing import Optional

# Import analytics MCP tools
from ipfs_kit_py.mcp.servers.audit_analytics_mcp_tools import (
    audit_analytics_get_patterns,
    audit_analytics_detect_anomalies,
    audit_analytics_correlate_events,
    audit_analytics_reconstruct_timeline,
    audit_analytics_analyze_causation,
    audit_analytics_assess_impact,
    audit_analytics_get_compliance_score,
    audit_analytics_get_statistics,
    audit_analytics_analyze_trends,
    audit_analytics_generate_report
)


def patterns_cli(args):
    """CLI handler for pattern recognition"""
    result = audit_analytics_get_patterns(
        timeframe_hours=args.hours,
        event_types=args.types.split(',') if args.types else None,
        min_confidence=args.confidence
    )
    
    if result.get("success"):
        patterns = result.get("patterns", [])
        print(f"Found {len(patterns)} patterns (filtered from {result['total_patterns']} total)")
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for i, pattern in enumerate(patterns, 1):
                print(f"\n{i}. Pattern: {pattern['pattern_type']}")
                print(f"   Description: {pattern['description']}")
                print(f"   Confidence: {pattern['confidence']:.2f}")
                print(f"   Occurrences: {pattern['occurrence_count']}")
                if pattern.get('first_seen'):
                    print(f"   First seen: {pattern['first_seen']}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def anomalies_cli(args):
    """CLI handler for anomaly detection"""
    result = audit_analytics_detect_anomalies(
        threshold=args.threshold,
        lookback_days=args.days,
        min_deviation=args.min_deviation
    )
    
    if result.get("success"):
        anomalies = result.get("anomalies", [])
        print(f"Detected {len(anomalies)} anomalies (filtered from {result['total_anomalies']} total)")
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            # Group by severity
            by_severity = {}
            for anomaly in anomalies:
                severity = anomaly['severity']
                if severity not in by_severity:
                    by_severity[severity] = []
                by_severity[severity].append(anomaly)
            
            for severity in ['critical', 'high', 'medium', 'low']:
                if severity in by_severity:
                    print(f"\n{severity.upper()} Severity Anomalies:")
                    for anomaly in by_severity[severity]:
                        print(f"  - {anomaly['anomaly_type']}: {anomaly['description']}")
                        print(f"    Deviation: {anomaly['deviation']:.2f} std devs")
                        if anomaly.get('recommendation'):
                            print(f"    Recommendation: {anomaly['recommendation']}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def correlate_cli(args):
    """CLI handler for event correlation"""
    result = audit_analytics_correlate_events(
        event_id=args.event_id,
        time_window=args.window,
        max_results=args.max_results
    )
    
    if result.get("success"):
        events = result.get("events", [])
        print(f"Found {len(events)} correlated events")
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for i, event in enumerate(events, 1):
                print(f"\n{i}. Event: {event['event_id']}")
                print(f"   Timestamp: {event['timestamp']}")
                print(f"   Action: {event['action']}")
                print(f"   User: {event.get('user_id', 'N/A')}")
                print(f"   Resource: {event.get('resource', 'N/A')}")
                print(f"   Correlation: {event['correlation_score']:.2f} ({event['correlation_reason']})")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def timeline_cli(args):
    """CLI handler for timeline reconstruction"""
    result = audit_analytics_reconstruct_timeline(
        operation_id=args.operation_id,
        include_metadata=args.metadata
    )
    
    if result.get("success"):
        print(f"Timeline for operation: {result['operation_id']}")
        print(f"Duration: {result['duration_seconds']:.2f} seconds")
        print(f"Events: {result['event_count']}")
        print(f"Subsystems: {', '.join(result['subsystems'])}")
        print(f"Summary: {result['summary']}")
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            events = result.get("events", [])
            print(f"\nTimeline ({len(events)} events):")
            for event in events:
                print(f"  {event['timestamp']}: {event['action']} by {event.get('user_id', 'system')}")
                if event.get('resource'):
                    print(f"    Resource: {event['resource']}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def causation_cli(args):
    """CLI handler for causation analysis"""
    result = audit_analytics_analyze_causation(
        effect_event_id=args.event_id,
        max_depth=args.max_depth
    )
    
    if result.get("success"):
        print(f"Causation chain for event: {result['effect_event_id']}")
        print(f"Chain length: {result['chain_length']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Explanation: {result['explanation']}")
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            cause_events = result.get("cause_events", [])
            if cause_events:
                print(f"\nCause events ({len(cause_events)}):")
                for i, event in enumerate(cause_events, 1):
                    print(f"  {i}. {event['timestamp']}: {event['action']}")
                    print(f"     Resource: {event.get('resource', 'N/A')}")
                    print(f"     Correlation: {event['correlation_score']:.2f}")
            
            effect = result.get("effect_event")
            if effect:
                print(f"\nEffect event:")
                print(f"  {effect['timestamp']}: {effect['action']}")
                print(f"  Resource: {effect.get('resource', 'N/A')}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def impact_cli(args):
    """CLI handler for impact assessment"""
    result = audit_analytics_assess_impact(
        event_id=args.event_id,
        time_window=args.window
    )
    
    if result.get("success"):
        print(f"Impact assessment for event: {result['event_id']}")
        print(f"Impact level: {result['impact_level'].upper()}")
        print(f"Impact score: {result['impact_score']:.2f}")
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\nAffected resources: {len(result['affected_resources'])}")
            for resource in result['affected_resources'][:5]:
                print(f"  - {resource}")
            if len(result['affected_resources']) > 5:
                print(f"  ... and {len(result['affected_resources']) - 5} more")
            
            print(f"\nAffected users: {len(result['affected_users'])}")
            for user in list(result['affected_users'])[:5]:
                print(f"  - {user}")
            
            print(f"\nDownstream events: {result['downstream_event_count']}")
            
            print(f"\nRecommendations:")
            for rec in result['recommendations']:
                print(f"  - {rec}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def compliance_cli(args):
    """CLI handler for compliance scoring"""
    # Load policy rules from file
    policy_rules = []
    if args.policy:
        try:
            with open(args.policy, 'r') as f:
                policy_rules = json.load(f)
        except Exception as e:
            print(f"Error loading policy file: {e}", file=sys.stderr)
            sys.exit(1)
    
    result = audit_analytics_get_compliance_score(
        policy_rules=policy_rules,
        time_range_days=args.days
    )
    
    if result.get("success"):
        print(f"Compliance Score: {result['compliance_percentage']:.1f}%")
        print(f"Overall score: {result['overall_score']:.3f}")
        print(f"Total violations: {result['total_violations']}")
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get('policy_scores'):
                print(f"\nPolicy scores:")
                for policy, score in result['policy_scores'].items():
                    print(f"  {policy}: {score:.1%}")
            
            violations = result.get('violations', [])
            if violations:
                print(f"\nTop violations ({len(violations)}):")
                for violation in violations[:5]:
                    print(f"  - {violation.get('description', 'Violation')}")
            
            recommendations = result.get('recommendations', [])
            if recommendations:
                print(f"\nRecommendations:")
                for rec in recommendations:
                    print(f"  - {rec}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def statistics_cli(args):
    """CLI handler for statistics"""
    result = audit_analytics_get_statistics(
        group_by=args.group_by,
        time_range_hours=args.hours,
        top_n=args.top
    )
    
    if result.get("success"):
        print(f"Statistics grouped by: {result['group_by']}")
        print(f"Time range: {result['time_range_hours']} hours")
        print(f"Total groups: {result['total_groups']}")
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            stats = result.get("statistics", [])
            print(f"\nTop {len(stats)} {result['group_by']}:")
            for i, stat in enumerate(stats, 1):
                print(f"{i:2}. {stat['category']}: {stat['count']} events ({stat.get('percentage', 0):.1f}%)")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def trends_cli(args):
    """CLI handler for trend analysis"""
    result = audit_analytics_analyze_trends(
        metric=args.metric,
        period=args.period,
        days=args.days
    )
    
    if result.get("success"):
        print(f"Trend analysis for: {result['metric']}")
        print(f"Period: {result['period']}")
        print(f"Days analyzed: {result['days']}")
        print(f"Data points: {result['data_points']}")
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            trends = result.get("trends", [])
            if trends:
                print(f"\nTrend data:")
                for point in trends[-10:]:  # Show last 10 points
                    change_str = f"(Δ {point['change']:+.1f})" if point.get('change') else ""
                    print(f"  {point['timestamp']}: {point['value']:.1f} {change_str}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def report_cli(args):
    """CLI handler for report generation"""
    result = audit_analytics_generate_report(
        report_type=args.type,
        time_range_days=args.days,
        include_charts=not args.no_charts
    )
    
    if result.get("success"):
        print(f"Generated {result['report_type']} report")
        print(f"Events analyzed: {result['events_analyzed']}")
        print(f"Generated at: {result['generated_at']}")
        
        # Save or display report
        if args.output:
            try:
                with open(args.output, 'w') as f:
                    json.dump(result, f, indent=2)
                print(f"Report saved to: {args.output}")
            except Exception as e:
                print(f"Error saving report: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(json.dumps(result, indent=2))
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def create_parser():
    """Create argument parser for audit analytics CLI"""
    parser = argparse.ArgumentParser(
        prog='ipfs-kit audit-analytics',
        description='Advanced audit analytics and reporting'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Analytics commands')
    
    # patterns command
    patterns_parser = subparsers.add_parser('patterns', help='Detect patterns in audit events')
    patterns_parser.add_argument('--hours', type=int, default=24, help='Hours to analyze (default: 24)')
    patterns_parser.add_argument('--types', help='Comma-separated event types to analyze')
    patterns_parser.add_argument('--confidence', type=float, default=0.5, help='Minimum confidence (default: 0.5)')
    patterns_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # anomalies command
    anomalies_parser = subparsers.add_parser('anomalies', help='Detect anomalous behavior')
    anomalies_parser.add_argument('--threshold', type=float, default=2.0, help='Standard deviation threshold (default: 2.0)')
    anomalies_parser.add_argument('--days', type=int, default=7, help='Days to analyze (default: 7)')
    anomalies_parser.add_argument('--min-deviation', type=float, default=1.5, help='Minimum deviation (default: 1.5)')
    anomalies_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # correlate command
    correlate_parser = subparsers.add_parser('correlate', help='Correlate related events')
    correlate_parser.add_argument('--event-id', required=True, help='Reference event ID')
    correlate_parser.add_argument('--window', type=int, default=300, help='Time window in seconds (default: 300)')
    correlate_parser.add_argument('--max-results', type=int, default=50, help='Maximum results (default: 50)')
    correlate_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # timeline command
    timeline_parser = subparsers.add_parser('timeline', help='Reconstruct operation timeline')
    timeline_parser.add_argument('--operation-id', required=True, help='Operation ID')
    timeline_parser.add_argument('--metadata', action='store_true', help='Include full metadata')
    timeline_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # causation command
    causation_parser = subparsers.add_parser('causation', help='Analyze event causation')
    causation_parser.add_argument('--event-id', required=True, help='Effect event ID')
    causation_parser.add_argument('--max-depth', type=int, default=10, help='Maximum chain depth (default: 10)')
    causation_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # impact command
    impact_parser = subparsers.add_parser('impact', help='Assess event impact')
    impact_parser.add_argument('--event-id', required=True, help='Event ID to assess')
    impact_parser.add_argument('--window', type=int, default=600, help='Time window in seconds (default: 600)')
    impact_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # compliance command
    compliance_parser = subparsers.add_parser('compliance', help='Calculate compliance score')
    compliance_parser.add_argument('--policy', help='Policy rules JSON file')
    compliance_parser.add_argument('--days', type=int, default=30, help='Days to analyze (default: 30)')
    compliance_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # stats command
    stats_parser = subparsers.add_parser('stats', help='Get statistical summaries')
    stats_parser.add_argument('--group-by', default='event_type', 
                            choices=['event_type', 'user_id', 'action', 'status'],
                            help='Field to group by (default: event_type)')
    stats_parser.add_argument('--hours', type=int, default=24, help='Hours to analyze (default: 24)')
    stats_parser.add_argument('--top', type=int, default=10, help='Number of top results (default: 10)')
    stats_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # trends command
    trends_parser = subparsers.add_parser('trends', help='Analyze trends over time')
    trends_parser.add_argument('--metric', default='event_count',
                              choices=['event_count', 'failed_auth', 'unique_users'],
                              help='Metric to analyze (default: event_count)')
    trends_parser.add_argument('--period', default='daily', choices=['hourly', 'daily'],
                              help='Time period (default: daily)')
    trends_parser.add_argument('--days', type=int, default=7, help='Days to analyze (default: 7)')
    trends_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # report command
    report_parser = subparsers.add_parser('report', help='Generate visual report')
    report_parser.add_argument('--type', required=True,
                              choices=['timeline', 'heatmap', 'compliance', 'activity'],
                              help='Report type')
    report_parser.add_argument('--days', type=int, default=7, help='Days to include (default: 7)')
    report_parser.add_argument('--output', help='Output file (JSON format)')
    report_parser.add_argument('--no-charts', action='store_true', help='Exclude chart data')
    
    return parser


def main(argv=None):
    """Main entry point for audit analytics CLI"""
    parser = create_parser()
    args = parser.parse_args(argv)
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Dispatch to appropriate handler
    handlers = {
        'patterns': patterns_cli,
        'anomalies': anomalies_cli,
        'correlate': correlate_cli,
        'timeline': timeline_cli,
        'causation': causation_cli,
        'impact': impact_cli,
        'compliance': compliance_cli,
        'stats': statistics_cli,
        'trends': trends_cli,
        'report': report_cli,
    }
    
    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
