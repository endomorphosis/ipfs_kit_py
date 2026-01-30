#!/usr/bin/env python3
"""
IPFS Kit Enhanced Pin CLI

Command-line interface for the enhanced pin metadata index that integrates
with ipfs_kit_py's virtual filesystem and hierarchical storage management.

This CLI provides unified access to pin metadata, analytics, and VFS operations
from the command line, making it easy to monitor and manage IPFS content.

Usage:
    python enhanced_pin_cli.py metrics          # Show comprehensive metrics
    python enhanced_pin_cli.py vfs              # Show VFS analytics
    python enhanced_pin_cli.py pins             # List pins with details
    python enhanced_pin_cli.py track <cid>      # Track a specific pin
    python enhanced_pin_cli.py analytics        # Show storage analytics
    python enhanced_pin_cli.py status           # Show system status
"""

import os
import sys
import time
import json
import argparse
import anyio
from pathlib import Path

# Add ipfs_kit_py to path
# Add project root to path (now in ipfs_kit_py/cli/)
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ipfs_kit_py.enhanced_pin_index import (
        get_global_enhanced_pin_index, 
        get_cli_pin_metrics,
        EnhancedPinMetadataIndex
    )
    ENHANCED_INDEX_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Enhanced pin index not available: {e}")
    ENHANCED_INDEX_AVAILABLE = False
    
    # Fallback to basic implementation
    try:
        from ipfs_kit_py.pins import get_global_pin_index
        BASIC_INDEX_AVAILABLE = True
    except ImportError:
        BASIC_INDEX_AVAILABLE = False


def format_bytes(bytes_val: int) -> str:
    """Format bytes as human-readable string."""
    if bytes_val == 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


def print_banner():
    """Print CLI banner."""
    print("🚀 IPFS Kit Enhanced Pin CLI")
    print("=" * 50)


def print_metrics(metrics_data: dict):
    """Print comprehensive metrics."""
    traffic = metrics_data.get("traffic_metrics", {})
    performance = metrics_data.get("performance_metrics", {})
    vfs = metrics_data.get("vfs_analytics", {})
    
    print("📊 COMPREHENSIVE METRICS")
    print("-" * 30)
    
    # Basic statistics
    total_pins = traffic.get("total_pins", 0)
    total_size = traffic.get("total_size_bytes", 0)
    vfs_mounts = traffic.get("vfs_mounts", 0)
    
    print(f"Total Pins: {total_pins:,}")
    print(f"Total Size: {format_bytes(total_size)}")
    print(f"VFS Mounts: {vfs_mounts}")
    print(f"Directory Pins: {traffic.get('directory_pins', 0)}")
    print(f"File Pins: {traffic.get('file_pins', 0)}")
    print()
    
    # Access patterns
    hour_access = traffic.get("pins_accessed_last_hour", 0)
    day_access = traffic.get("pins_accessed_last_day", 0)
    total_access = traffic.get("total_access_count", 0)
    
    print("🔍 ACCESS PATTERNS")
    print("-" * 20)
    print(f"Last Hour: {hour_access} pins")
    print(f"Last Day: {day_access} pins")
    print(f"Total Accesses: {total_access:,}")
    print()
    
    # Storage analytics
    tier_dist = traffic.get("tier_distribution", {})
    if tier_dist:
        print("💾 STORAGE TIERS")
        print("-" * 15)
        for tier, count in tier_dist.items():
            print(f"  {tier}: {count} pins")
        print()
    
    # Content integrity
    verified = traffic.get("verified_pins", 0)
    corrupted = traffic.get("corrupted_pins", 0)
    unverified = traffic.get("unverified_pins", 0)
    
    print("🔒 CONTENT INTEGRITY")
    print("-" * 20)
    print(f"Verified: {verified}")
    print(f"Corrupted: {corrupted}")
    print(f"Unverified: {unverified}")
    if verified + corrupted > 0:
        integrity_rate = verified / (verified + corrupted) * 100
        print(f"Integrity Rate: {integrity_rate:.1f}%")
    print()
    
    # Performance metrics
    cache_perf = performance.get("cache_performance", {})
    if cache_perf:
        print("⚡ PERFORMANCE")
        print("-" * 15)
        print(f"Cache Hit Rate: {cache_perf.get('cache_hit_rate', 0):.1%}")
        print(f"Total Requests: {cache_perf.get('total_requests', 0):,}")
        print()


def print_vfs_analytics(vfs_data: dict):
    """Print VFS-specific analytics."""
    print("🗂️  VFS ANALYTICS")
    print("-" * 20)
    
    total_vfs_pins = vfs_data.get("total_vfs_pins", 0)
    mount_points = vfs_data.get("mount_points", {})
    operations = vfs_data.get("operations_summary", {})
    
    print(f"VFS Pins: {total_vfs_pins}")
    print(f"Mount Points: {len(mount_points)}")
    print()
    
    if mount_points:
        print("📁 MOUNT POINTS:")
        for mount_point, pin_count in mount_points.items():
            print(f"  {mount_point}: {pin_count} pins")
        print()
    
    if operations:
        print("⚙️  VFS OPERATIONS (24h):")
        for op_type, stats in operations.items():
            success_rate = stats.get('success_rate', 0) * 100
            avg_duration = stats.get('avg_duration_ms', 0)
            print(f"  {op_type}: {stats.get('count', 0)} ops, "
                  f"{success_rate:.1f}% success, {avg_duration:.1f}ms avg")
        print()


def print_pin_list(index):
    """Print detailed pin list."""
    print("📌 PIN DETAILS")
    print("-" * 15)
    
    if hasattr(index, 'pin_metadata'):
        pins = list(index.pin_metadata.values())[:20]  # Show first 20
        
        for pin in pins:
            print(f"CID: {pin.cid[:16]}...")
            print(f"  Size: {format_bytes(pin.size_bytes)}")
            print(f"  Type: {pin.type}")
            if pin.vfs_path:
                print(f"  VFS Path: {pin.vfs_path}")
            if pin.mount_point:
                print(f"  Mount Point: {pin.mount_point}")
            print(f"  Accesses: {pin.access_count}")
            print(f"  Hotness: {pin.hotness_score:.2f}")
            print(f"  Tiers: {', '.join(pin.storage_tiers)}")
            print()
        
        if len(index.pin_metadata) > 20:
            print(f"... and {len(index.pin_metadata) - 20} more pins")
    else:
        print("No detailed pin information available (using basic index)")


def print_analytics(index):
    """Print storage analytics."""
    print("📈 STORAGE ANALYTICS")
    print("-" * 20)
    
    if ENHANCED_INDEX_AVAILABLE and hasattr(index, 'get_comprehensive_metrics'):
        metrics = index.get_comprehensive_metrics()
        
        # Hot pins analysis
        hot_pins = metrics.hot_pins[:5]  # Top 5
        print("🔥 HOT PINS (Top 5):")
        for i, cid in enumerate(hot_pins, 1):
            pin_details = index.get_pin_details(cid)
            if pin_details:
                print(f"  {i}. {cid[:16]}... (hotness: {pin_details.hotness_score:.2f})")
        print()
        
        # Largest pins
        largest = metrics.largest_pins[:5]  # Top 5
        print("📦 LARGEST PINS (Top 5):")
        for i, pin_info in enumerate(largest, 1):
            print(f"  {i}. {pin_info['cid']} - {pin_info['size_human']}")
            if pin_info.get('vfs_path'):
                print(f"      VFS: {pin_info['vfs_path']}")
        print()
        
        # Storage recommendations
        recommendations = metrics.storage_recommendations
        if recommendations:
            print("💡 RECOMMENDATIONS:")
            for rec in recommendations:
                priority = rec.get('priority', 'medium').upper()
                print(f"  [{priority}] {rec.get('message', 'No message')}")
            print()
    else:
        print("Advanced analytics not available (using basic index)")


def print_status(index):
    """Print system status."""
    print("🏥 SYSTEM STATUS")
    print("-" * 15)
    
    if ENHANCED_INDEX_AVAILABLE and hasattr(index, 'get_performance_metrics'):
        performance = index.get_performance_metrics()
        
        # Background services
        bg_services = performance.get("background_services", {})
        print(f"Background Services: {'Running' if bg_services.get('running') else 'Stopped'}")
        print(f"Update Interval: {bg_services.get('update_interval', 0)}s")
        print(f"Last Update Duration: {bg_services.get('last_update_duration', 0):.2f}s")
        print()
        
        # Capabilities
        capabilities = performance.get("capabilities", {})
        print("🔧 CAPABILITIES:")
        print(f"  Analytics: {'✓' if capabilities.get('analytics_enabled') else '✗'}")
        print(f"  Predictions: {'✓' if capabilities.get('predictions_enabled') else '✗'}")
        print(f"  VFS Integration: {'✓' if capabilities.get('vfs_integration') else '✗'}")
        print(f"  Journal Sync: {'✓' if capabilities.get('journal_sync') else '✗'}")
        print()
        
        # Storage info
        storage = performance.get("storage_info", {})
        print("💾 STORAGE:")
        print(f"  Data Directory: {storage.get('data_directory', 'Unknown')}")
        parquet_files = storage.get("parquet_files", {})
        if parquet_files:
            print(f"  Pins Parquet: {'✓' if parquet_files.get('pins_exists') else '✗'}")
            print(f"  Analytics Parquet: {'✓' if parquet_files.get('analytics_exists') else '✗'}")
        print()
    else:
        print("Detailed status not available (using basic index)")


async def track_pin(index, cid: str):
    """Track a specific pin and show detailed information."""
    print(f"🔍 TRACKING PIN: {cid}")
    print("-" * (20 + len(cid)))
    
    if ENHANCED_INDEX_AVAILABLE and hasattr(index, 'get_pin_details'):
        pin_details = index.get_pin_details(cid)
        if pin_details:
            print(f"CID: {pin_details.cid}")
            print(f"Size: {format_bytes(pin_details.size_bytes)}")
            print(f"Type: {pin_details.type}")
            print(f"Name: {pin_details.name or 'None'}")
            print(f"VFS Path: {pin_details.vfs_path or 'None'}")
            print(f"Mount Point: {pin_details.mount_point or 'None'}")
            print(f"Is Directory: {pin_details.is_directory}")
            print(f"Primary Tier: {pin_details.primary_tier}")
            print(f"Storage Tiers: {', '.join(pin_details.storage_tiers) or 'None'}")
            print(f"Replication Factor: {pin_details.replication_factor}")
            print(f"Access Count: {pin_details.access_count}")
            print(f"Last Accessed: {time.ctime(pin_details.last_accessed) if pin_details.last_accessed else 'Never'}")
            print(f"Hotness Score: {pin_details.hotness_score:.2f}")
            print(f"Access Pattern: {pin_details.access_pattern}")
            print(f"Integrity Status: {pin_details.integrity_status}")
            if pin_details.predicted_access_time:
                print(f"Predicted Next Access: {time.ctime(pin_details.predicted_access_time)}")
            
            # Record this access for tracking
            index.record_enhanced_access(cid, access_pattern="cli_track")
            print(f"\n✓ Recorded CLI access for tracking")
        else:
            print(f"❌ Pin {cid} not found in index")
    else:
        print("Detailed pin tracking not available (using basic index)")


async def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(description="IPFS Kit Enhanced Pin CLI")
    parser.add_argument("command", choices=["metrics", "vfs", "pins", "track", "analytics", "status", "demo"],
                       help="Command to execute")
    parser.add_argument("cid", nargs="?", help="CID for track command")
    parser.add_argument("--data-dir", help="Data directory for enhanced index")
    
    args = parser.parse_args()
    
    print_banner()
    
    if not ENHANCED_INDEX_AVAILABLE and not BASIC_INDEX_AVAILABLE:
        print("❌ No pin index implementation available")
        print("Please ensure ipfs_kit_py and its dependencies are installed")
        return 1
    
    # Initialize index
    try:
        if ENHANCED_INDEX_AVAILABLE:
            index = get_global_enhanced_pin_index(
                data_dir=args.data_dir,
                enable_analytics=True,
                enable_predictions=True
            )
            print("✓ Using enhanced pin index with VFS integration")
        else:
            from ipfs_kit_py.pins import get_global_pin_index
            index = get_global_pin_index()
            print("✓ Using basic pin index")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize pin index: {e}")
        return 1
    
    # Execute command
    try:
        if args.command == "metrics":
            if ENHANCED_INDEX_AVAILABLE:
                metrics_data = get_cli_pin_metrics()
                print_metrics(metrics_data)
            else:
                print("Basic metrics not yet implemented for fallback index")
                
        elif args.command == "vfs":
            if ENHANCED_INDEX_AVAILABLE and hasattr(index, 'get_vfs_analytics'):
                vfs_data = index.get_vfs_analytics()
                print_vfs_analytics(vfs_data)
            else:
                print("VFS analytics not available (requires enhanced index)")
                
        elif args.command == "pins":
            print_pin_list(index)
            
        elif args.command == "track":
            if not args.cid:
                print("❌ CID required for track command")
                return 1
            await track_pin(index, args.cid)
            
        elif args.command == "analytics":
            print_analytics(index)
            
        elif args.command == "status":
            print_status(index)
            
        elif args.command == "demo":
            print("🎭 RUNNING DEMO")
            print("-" * 15)
            
            # Add some demo data
            demo_cids = [
                ("QmDemoFile123456789abcdef", "sequential", "/vfs/demo/file1.txt"),
                ("QmDemoVideo234567890bcdefg", "streaming", "/vfs/demo/video.mp4"),
                ("QmDemoData345678901cdefgh", "random", "/vfs/demo/data.json")
            ]
            
            for cid, pattern, vfs_path in demo_cids:
                if ENHANCED_INDEX_AVAILABLE and hasattr(index, 'record_enhanced_access'):
                    index.record_enhanced_access(
                        cid=cid,
                        access_pattern=pattern,
                        vfs_path=vfs_path,
                        tier="ipfs"
                    )
                    print(f"✓ Added demo pin: {cid[:16]}... ({pattern})")
                else:
                    print(f"✓ Would add demo pin: {cid[:16]}... ({pattern})")
            
            print()
            print("Demo data added! Try running other commands to see the results.")
        
    except Exception as e:
        print(f"❌ Command failed: {e}")
        return 1
    
    return 0


def print_access_history():
    """Print access history from enhanced pin index."""
    if not ENHANCED_INDEX_AVAILABLE:
        print("⚠️ Enhanced pin index not available")
        if BASIC_INDEX_AVAILABLE:
            print("📊 Basic pin index in use")
        return
    
    try:
        enhanced_index = get_global_enhanced_pin_index()
        # Get recent access patterns
        access_data = enhanced_index.query_access_patterns(limit=20)
        
        if not access_data:
            print("📭 No access history found")
            return
        
        print("\n📜 Recent Access History:")
        print("=" * 80)
        
        for record in access_data:
            timestamp = record.get('timestamp', 'unknown')
            cid = record.get('cid', 'unknown')[:12] + '...'
            access_type = record.get('access_type', 'unknown')
            print(f"🕐 {timestamp} | 📎 {cid} | 🔄 {access_type}")
        
    except Exception as e:
        print(f"❌ Error getting access history: {e}")
        print("📊 Using basic pin index fallback")
        if BASIC_INDEX_AVAILABLE:
            try:
                basic_index = get_global_pin_index()
                pins = basic_index.get_all_pins()
                print(f"📊 Total pins: {len(pins)}")
            except Exception as basic_error:
                print(f"❌ Basic index also failed: {basic_error}")


def print_performance_metrics():
    """Print performance metrics from enhanced pin index."""
    if not ENHANCED_INDEX_AVAILABLE:
        print("⚠️ Enhanced pin index not available")
        if BASIC_INDEX_AVAILABLE:
            print("📊 Basic pin index in use")
        return
    
    try:
        enhanced_index = get_global_enhanced_pin_index()
        metrics = enhanced_index.get_performance_metrics()
        
        print("\n⚡ Performance Metrics:")
        print("=" * 50)
        
        # Cache performance
        cache = metrics.get('cache_performance', {})
        print(f"🗄️  Cache Hit Rate: {cache.get('cache_hit_rate', 0):.1%}")
        print(f"📊 Total Cached: {cache.get('total_pins_cached', 0)}")
        print(f"🔄 Total Requests: {cache.get('total_requests', 0)}")
        
        # Integration metrics
        integration = metrics.get('integration_metrics', {})
        print(f"🔗 VFS Integrations: {integration.get('vfs_integrations', 0)}")
        print(f"📝 Journal Syncs: {integration.get('journal_syncs', 0)}")
        print(f"📈 Analytics Runs: {integration.get('analytics_runs', 0)}")
        
        # Background services
        bg = metrics.get('background_services', {})
        status = "🟢 Running" if bg.get('running', False) else "🔴 Stopped"
        print(f"⚙️  Background Services: {status}")
        
        # Capabilities
        caps = metrics.get('capabilities', {})
        print(f"🔬 Analytics: {'✅' if caps.get('analytics_enabled', False) else '❌'}")
        print(f"🔮 Predictions: {'✅' if caps.get('predictions_enabled', False) else '❌'}")
        
    except Exception as e:
        print(f"❌ Error getting performance metrics: {e}")
        print("📊 Using basic pin index fallback")
        if BASIC_INDEX_AVAILABLE:
            try:
                basic_index = get_global_pin_index()
                pins = basic_index.get_all_pins()
                print(f"📊 Total pins: {len(pins)}")
            except Exception as basic_error:
                print(f"❌ Basic index also failed: {basic_error}")


if __name__ == "__main__":
    exit_code = anyio.run(main)
    sys.exit(exit_code)
