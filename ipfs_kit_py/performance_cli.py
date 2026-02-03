#!/usr/bin/env python3
"""
Performance CLI Module for IPFS Kit

This module provides CLI commands for performance optimization:
- Cache management and statistics
- Performance metrics and monitoring
- Bottleneck detection
- Resource usage tracking
- Baseline management

Part of Phase 9: Performance Optimization
"""

import argparse
import json
import sys
from typing import Optional

# Import performance MCP tools
from ipfs_kit_py.mcp.servers.performance_mcp_tools import (
    performance_get_cache_stats,
    performance_clear_cache,
    performance_invalidate_cache,
    performance_get_metrics,
    performance_get_bottlenecks,
    performance_get_resource_usage,
    performance_set_baseline,
    performance_get_monitor_stats,
    performance_get_batch_stats,
    performance_reset_cache_stats,
    performance_get_summary
)


def cache_stats_cli(args):
    """CLI handler for cache statistics"""
    result = performance_get_cache_stats()
    
    if result.get("success"):
        stats = result.get("statistics", {})
        print("Cache Statistics:")
        print(f"  Total requests: {stats.get('total_requests', 0)}")
        print(f"  Hits: {stats.get('hits', 0)} (Memory: {stats.get('memory_hits', 0)}, Disk: {stats.get('disk_hits', 0)})")
        print(f"  Misses: {stats.get('misses', 0)}")
        print(f"  Hit rate: {stats.get('hit_rate_percent', 0):.2f}%")
        print(f"  Memory cache size: {stats.get('memory_size', 0)} entries")
        print(f"  Disk cache size: {stats.get('disk_size', 0)} entries")
        print(f"  Sets: {stats.get('sets', 0)}")
        print(f"  Deletes: {stats.get('deletes', 0)}")
        print(f"  Invalidations: {stats.get('invalidations', 0)}")
        
        if args.json:
            print("\nJSON Output:")
            print(json.dumps(result, indent=2))
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def cache_clear_cli(args):
    """CLI handler for clearing cache"""
    result = performance_clear_cache(tier=args.tier)
    
    if result.get("success"):
        print(result.get("message", "Cache cleared"))
        if args.json:
            print(json.dumps(result, indent=2))
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def cache_invalidate_cli(args):
    """CLI handler for cache invalidation"""
    result = performance_invalidate_cache(pattern=args.pattern)
    
    if result.get("success"):
        print(result.get("message", "Cache invalidated"))
        print(f"Invalidations: {result.get('invalidations', 0)}")
        if args.json:
            print(json.dumps(result, indent=2))
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def metrics_cli(args):
    """CLI handler for performance metrics"""
    result = performance_get_metrics(
        operation_name=args.operation,
        timeframe=args.timeframe
    )
    
    if result.get("success"):
        metrics = result.get("metrics", {})
        print(f"Performance Metrics: {metrics.get('operation_name', 'all')}")
        print(f"  Timeframe: {metrics.get('timeframe', 'N/A')}")
        print(f"  Total operations: {metrics.get('count', 0)}")
        
        if metrics.get('count', 0) > 0:
            print(f"  Successful: {metrics.get('successful', 0)}")
            print(f"  Failed: {metrics.get('failed', 0)}")
            print(f"  Success rate: {metrics.get('success_rate', 0):.1f}%")
            
            if 'avg_duration' in metrics:
                print(f"\n  Duration Statistics:")
                print(f"    Average: {metrics['avg_duration']:.3f}s")
                print(f"    Minimum: {metrics.get('min_duration', 0):.3f}s")
                print(f"    Maximum: {metrics.get('max_duration', 0):.3f}s")
                print(f"    Median: {metrics.get('median_duration', 0):.3f}s")
                if 'p95_duration' in metrics:
                    print(f"    P95: {metrics['p95_duration']:.3f}s")
                if 'p99_duration' in metrics:
                    print(f"    P99: {metrics['p99_duration']:.3f}s")
        
        if args.json:
            print("\nJSON Output:")
            print(json.dumps(result, indent=2))
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def bottlenecks_cli(args):
    """CLI handler for bottleneck detection"""
    result = performance_get_bottlenecks(
        cpu_threshold=args.cpu_threshold,
        memory_threshold=args.memory_threshold,
        slow_operation_factor=args.slow_factor
    )
    
    if result.get("success"):
        count = result.get("count", 0)
        print(f"Detected {count} bottleneck(s):")
        
        if count > 0:
            bottlenecks = result.get("bottlenecks", [])
            
            # Group by severity
            by_severity = {}
            for b in bottlenecks:
                severity = b['severity']
                if severity not in by_severity:
                    by_severity[severity] = []
                by_severity[severity].append(b)
            
            for severity in ['critical', 'high', 'medium', 'low']:
                if severity in by_severity:
                    print(f"\n{severity.upper()} Severity:")
                    for b in by_severity[severity]:
                        print(f"  - {b['type']}: {b['description']}")
                        print(f"    Value: {b['metric_value']:.2f} (threshold: {b['threshold']:.2f})")
                        print(f"    Recommendation: {b['recommendation']}")
        else:
            print("No bottlenecks detected")
        
        if args.json:
            print("\nJSON Output:")
            print(json.dumps(result, indent=2))
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def resources_cli(args):
    """CLI handler for resource usage"""
    result = performance_get_resource_usage()
    
    if result.get("success"):
        usage = result.get("usage", {})
        print("Resource Usage:")
        print(f"  Process CPU: {usage.get('cpu_percent', 0):.1f}%")
        print(f"  Process Memory: {usage.get('memory_mb', 0):.1f} MB ({usage.get('memory_percent', 0):.1f}%)")
        print(f"  Process Threads: {usage.get('num_threads', 0)}")
        print(f"\n  System CPU: {usage.get('system_cpu_percent', 0):.1f}%")
        print(f"  System Memory: {usage.get('system_memory_percent', 0):.1f}%")
        print(f"  System Disk: {usage.get('system_disk_usage_percent', 0):.1f}%")
        
        if args.json:
            print("\nJSON Output:")
            print(json.dumps(result, indent=2))
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def baseline_cli(args):
    """CLI handler for setting baseline"""
    result = performance_set_baseline(operation_name=args.operation)
    
    if result.get("success"):
        print(result.get("message", "Baseline set"))
        if args.json:
            print(json.dumps(result, indent=2))
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def monitor_stats_cli(args):
    """CLI handler for monitor statistics"""
    result = performance_get_monitor_stats()
    
    if result.get("success"):
        stats = result.get("statistics", {})
        print("Monitor Statistics:")
        print(f"  Total operations tracked: {stats.get('total_operations_tracked', 0)}")
        print(f"  Active operations: {stats.get('active_operations', 0)}")
        print(f"  Resource samples: {stats.get('resource_samples_collected', 0)}")
        print(f"  Unique operations: {stats.get('unique_operations', 0)}")
        print(f"  Baselines set: {stats.get('baselines_set', 0)}")
        
        if args.json:
            print("\nJSON Output:")
            print(json.dumps(result, indent=2))
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def batch_stats_cli(args):
    """CLI handler for batch statistics"""
    result = performance_get_batch_stats()
    
    if result.get("success"):
        stats = result.get("statistics", {})
        print("Batch Statistics:")
        print(f"  Total operations: {stats.get('total_operations', 0)}")
        print(f"  Pending: {stats.get('pending', 0)}")
        print(f"  Running: {stats.get('running', 0)}")
        print(f"  Successful: {stats.get('successful', 0)}")
        print(f"  Failed: {stats.get('failed', 0)}")
        print(f"  Skipped: {stats.get('skipped', 0)}")
        
        if args.json:
            print("\nJSON Output:")
            print(json.dumps(result, indent=2))
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def summary_cli(args):
    """CLI handler for performance summary"""
    result = performance_get_summary()
    
    if result.get("success"):
        print("Performance Summary:")
        
        # Cache
        cache = result.get("cache", {})
        if cache:
            print("\nCache:")
            print(f"  Hit rate: {cache.get('hit_rate_percent', 0):.2f}%")
            print(f"  Memory size: {cache.get('memory_size', 0)} entries")
            print(f"  Disk size: {cache.get('disk_size', 0)} entries")
        
        # Monitor
        monitor = result.get("monitor", {})
        if monitor:
            print("\nMonitor:")
            print(f"  Operations tracked: {monitor.get('total_operations_tracked', 0)}")
            print(f"  Active operations: {monitor.get('active_operations', 0)}")
        
        # Batch
        batch = result.get("batch", {})
        if batch:
            print("\nBatch:")
            print(f"  Total operations: {batch.get('total_operations', 0)}")
            print(f"  Successful: {batch.get('successful', 0)}")
        
        # Resources
        resources = result.get("resources", {})
        if resources and 'error' not in resources:
            print("\nResources:")
            print(f"  CPU: {resources.get('cpu_percent', 0):.1f}%")
            print(f"  Memory: {resources.get('memory_mb', 0):.1f} MB")
        
        if args.json:
            print("\nJSON Output:")
            print(json.dumps(result, indent=2))
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def create_parser():
    """Create argument parser for performance CLI"""
    parser = argparse.ArgumentParser(
        prog='ipfs-kit performance',
        description='Performance optimization and monitoring'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Performance commands')
    
    # cache stats command
    cache_stats_parser = subparsers.add_parser('cache-stats', help='Get cache statistics')
    cache_stats_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # cache clear command
    cache_clear_parser = subparsers.add_parser('cache-clear', help='Clear cache')
    cache_clear_parser.add_argument('--tier', default='all', choices=['memory', 'disk', 'all'],
                                   help='Cache tier to clear (default: all)')
    cache_clear_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # cache invalidate command
    cache_invalidate_parser = subparsers.add_parser('cache-invalidate', help='Invalidate cache by pattern')
    cache_invalidate_parser.add_argument('--pattern', required=True, help='Pattern to match (supports * wildcard)')
    cache_invalidate_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # metrics command
    metrics_parser = subparsers.add_parser('metrics', help='Get performance metrics')
    metrics_parser.add_argument('--operation', help='Filter by operation name')
    metrics_parser.add_argument('--timeframe', default='1h', help='Timeframe (1h, 24h, 7d, all)')
    metrics_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # bottlenecks command
    bottlenecks_parser = subparsers.add_parser('bottlenecks', help='Detect bottlenecks')
    bottlenecks_parser.add_argument('--cpu-threshold', type=float, default=80.0,
                                   help='CPU threshold percentage (default: 80)')
    bottlenecks_parser.add_argument('--memory-threshold', type=float, default=80.0,
                                   help='Memory threshold percentage (default: 80)')
    bottlenecks_parser.add_argument('--slow-factor', type=float, default=2.0,
                                   help='Slow operation factor (default: 2.0)')
    bottlenecks_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # resources command
    resources_parser = subparsers.add_parser('resources', help='Get resource usage')
    resources_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # baseline command
    baseline_parser = subparsers.add_parser('baseline', help='Set performance baseline')
    baseline_parser.add_argument('--operation', required=True, help='Operation name')
    baseline_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # monitor-stats command
    monitor_stats_parser = subparsers.add_parser('monitor-stats', help='Get monitor statistics')
    monitor_stats_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # batch-stats command
    batch_stats_parser = subparsers.add_parser('batch-stats', help='Get batch statistics')
    batch_stats_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # summary command
    summary_parser = subparsers.add_parser('summary', help='Get performance summary')
    summary_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    return parser


def main(argv=None):
    """Main entry point for performance CLI"""
    parser = create_parser()
    args = parser.parse_args(argv)
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Dispatch to appropriate handler
    handlers = {
        'cache-stats': cache_stats_cli,
        'cache-clear': cache_clear_cli,
        'cache-invalidate': cache_invalidate_cli,
        'metrics': metrics_cli,
        'bottlenecks': bottlenecks_cli,
        'resources': resources_cli,
        'baseline': baseline_cli,
        'monitor-stats': monitor_stats_cli,
        'batch-stats': batch_stats_cli,
        'summary': summary_cli,
    }
    
    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
