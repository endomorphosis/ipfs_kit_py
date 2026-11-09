#!/usr/bin/env python3
"""
IPFS Kit CLI - Bucket Index Commands

Simple CLI for testing bucket index functionality.
"""

import sys
import os
import argparse

# Add the parent directory to the Python path (now in ipfs_kit_py/cli/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ipfs_kit_py.enhanced_bucket_index import EnhancedBucketIndex, format_size
    BUCKET_INDEX_AVAILABLE = True
except ImportError:
    BUCKET_INDEX_AVAILABLE = False
    print("Warning: Bucket index not available - missing dependencies")

def handle_bucket_list(args):
    """Handle bucket list command."""
    if not BUCKET_INDEX_AVAILABLE:
        print("❌ Bucket index not available")
        return
    
    try:
        bucket_index = EnhancedBucketIndex()
        bucket_index.refresh_index()
        
        buckets = bucket_index.list_buckets(detailed=args.detailed)
        
        if args.metrics:
            metrics = bucket_index.get_comprehensive_metrics()
            print(f"📊 BUCKET INDEX METRICS")
            print(f"{'=' * 40}")
            print(f"Total Buckets: {metrics.get('total_buckets', 0)}")
            print(f"Total Files: {metrics.get('total_files', 0)}")
            print(f"Total Size: {format_size(metrics.get('total_size', 0))}")
            print()
        
        if buckets:
            print(f"📋 Found {len(buckets)} virtual filesystems:")
            for bucket in buckets:
                if args.detailed:
                    print(f"   • {bucket['bucket_name']} ({bucket['bucket_type']})")
                    print(f"     Created: {bucket['created_at']}")
                    print(f"     Files: {bucket['file_count']}, Size: {format_size(bucket['total_size'])}")
                    print(f"     Path: {bucket['storage_path']}")
                else:
                    print(f"   • {bucket['name']} ({bucket['type']}) - {bucket['file_count']} files, {format_size(bucket['size'])}")
        else:
            print("📋 No virtual filesystems found")
            
    except Exception as e:
        print(f"❌ Error listing buckets: {e}")

def handle_bucket_info(args):
    """Handle bucket info command."""
    if not BUCKET_INDEX_AVAILABLE:
        print("❌ Bucket index not available")
        return
    
    try:
        bucket_index = EnhancedBucketIndex()
        bucket_index.refresh_index()
        
        bucket_info = bucket_index.get_bucket_info(args.bucket_name)
        
        if bucket_info:
            print(f"📄 Bucket '{args.bucket_name}' details:")
            print(f"   Type: {bucket_info['bucket_type']}")
            print(f"   Created: {bucket_info['created_at']}")
            print(f"   Modified: {bucket_info['last_modified']}")
            print(f"   Files: {bucket_info['file_count']}")
            print(f"   Size: {format_size(bucket_info['total_size'])}")
            print(f"   Structure: {bucket_info['structure_type']}")
            print(f"   Path: {bucket_info['storage_path']}")
            if bucket_info.get('metadata'):
                print(f"   Metadata: {bucket_info['metadata']}")
        else:
            print(f"❌ Bucket '{args.bucket_name}' not found")
            
    except Exception as e:
        print(f"❌ Error getting bucket info: {e}")

def handle_bucket_search(args):
    """Handle bucket search command."""
    if not BUCKET_INDEX_AVAILABLE:
        print("❌ Bucket index not available")
        return
    
    try:
        bucket_index = EnhancedBucketIndex()
        bucket_index.refresh_index()
        
        results = bucket_index.search_buckets(args.query, args.type)
        
        if results:
            print(f"🔍 Found {len(results)} buckets matching '{args.query}':")
            for bucket in results:
                print(f"   • {bucket['bucket_name']} ({bucket['bucket_type']})")
                if args.verbose:
                    print(f"     Files: {bucket['file_count']}, Size: {format_size(bucket['total_size'])}")
                    print(f"     Path: {bucket['storage_path']}")
        else:
            print(f"🔍 No buckets found matching '{args.query}'")
            
    except Exception as e:
        print(f"❌ Error searching buckets: {e}")

def handle_bucket_types(args):
    """Handle bucket types command."""
    if not BUCKET_INDEX_AVAILABLE:
        print("❌ Bucket index not available")
        return
    
    try:
        bucket_index = EnhancedBucketIndex()
        bucket_index.refresh_index()
        
        bucket_types = bucket_index.get_bucket_types()
        
        if bucket_types:
            print("📂 Bucket Types Distribution:")
            for bucket_type, count in bucket_types.items():
                print(f"   • {bucket_type}: {count} buckets")
        else:
            print("📂 No bucket types found")
            
    except Exception as e:
        print(f"❌ Error getting bucket types: {e}")

def handle_bucket_analytics(args):
    """Handle bucket analytics command."""
    if not BUCKET_INDEX_AVAILABLE:
        print("❌ Bucket index not available")
        return
    
    try:
        bucket_index = EnhancedBucketIndex()
        bucket_index.refresh_index()
        
        metrics = bucket_index.get_comprehensive_metrics()
        
        print(f"📊 COMPREHENSIVE BUCKET ANALYTICS")
        print(f"{'=' * 50}")
        print(f"Total Buckets: {metrics.get('total_buckets', 0)}")
        print(f"Total Files: {metrics.get('total_files', 0)}")
        print(f"Total Size: {format_size(metrics.get('total_size', 0))}")
        
        if metrics.get('bucket_types'):
            print(f"\nBucket Types:")
            for bucket_type, count in metrics['bucket_types'].items():
                print(f"   • {bucket_type}: {count}")
        
        if metrics.get('average_files_per_bucket') is not None:
            print(f"\nAverages:")
            print(f"   • Files per bucket: {metrics['average_files_per_bucket']:.1f}")
            print(f"   • Size per bucket: {format_size(metrics.get('average_size_per_bucket', 0))}")
        
        if metrics.get('size_stats'):
            stats = metrics['size_stats']
            print(f"\nSize Statistics:")
            print(f"   • Min: {format_size(stats.get('min', 0))}")
            print(f"   • Max: {format_size(stats.get('max', 0))}")
            print(f"   • Avg: {format_size(stats.get('avg', 0))}")
        
        if metrics.get('file_stats'):
            stats = metrics['file_stats']
            print(f"\nFile Count Statistics:")
            print(f"   • Min: {stats.get('min', 0)}")
            print(f"   • Max: {stats.get('max', 0)}")
            print(f"   • Avg: {stats.get('avg', 0):.1f}")
            
    except Exception as e:
        print(f"❌ Error getting analytics: {e}")

def handle_bucket_refresh(args):
    """Handle bucket refresh command."""
    if not BUCKET_INDEX_AVAILABLE:
        print("❌ Bucket index not available")
        return
    
    try:
        bucket_index = EnhancedBucketIndex()
        bucket_count = bucket_index.refresh_index()
        
        print(f"✅ Bucket index refreshed successfully")
        print(f"   Indexed {bucket_count} buckets")
        
    except Exception as e:
        print(f"❌ Error refreshing index: {e}")

def main():
    parser = argparse.ArgumentParser(description="IPFS Kit Bucket Index CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Bucket list command
    list_parser = subparsers.add_parser('list', help='List all virtual filesystems')
    list_parser.add_argument('--detailed', action='store_true', help='Show detailed information')
    list_parser.add_argument('--metrics', action='store_true', help='Show metrics summary')
    
    # Bucket info command
    info_parser = subparsers.add_parser('info', help='Get bucket details')
    info_parser.add_argument('bucket_name', help='Name of the bucket')
    
    # Bucket search command
    search_parser = subparsers.add_parser('search', help='Search buckets')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--type', choices=['name', 'type', 'structure', 'metadata', 'all'], 
                              default='all', help='Search type')
    search_parser.add_argument('--verbose', action='store_true', help='Show detailed results')
    
    # Bucket types command
    types_parser = subparsers.add_parser('types', help='Show bucket type distribution')
    
    # Bucket analytics command
    analytics_parser = subparsers.add_parser('analytics', help='Show comprehensive analytics')
    
    # Bucket refresh command
    refresh_parser = subparsers.add_parser('refresh', help='Refresh bucket index')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Route to appropriate handler
    handlers = {
        'list': handle_bucket_list,
        'info': handle_bucket_info,
        'search': handle_bucket_search,
        'types': handle_bucket_types,
        'analytics': handle_bucket_analytics,
        'refresh': handle_bucket_refresh
    }
    
    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"Unknown command: {args.command}")

if __name__ == "__main__":
    main()
