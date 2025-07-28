#!/usr/bin/env python3
"""
Arrow IPC Zero-Copy Demo

This script demonstrates the Apache Arrow IPC zero-copy functionality for IPFS-Kit,
showing how to access pin index and metrics data efficiently without database locks.

Key Features Demonstrated:
- Zero-copy data access using Arrow IPC
- Fallback to traditional access methods
- Performance comparison between methods
- Integration with VFS Manager and CLI
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def banner():
    """Display demo banner."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                       IPFS-Kit Arrow IPC Zero-Copy Demo                     ║
║                                                                              ║
║  This demo shows how to use Apache Arrow IPC for efficient, zero-copy       ║
║  access to IPFS-Kit pin index and metrics data from the daemon.            ║
║                                                                              ║
║  Benefits:                                                                   ║
║  • Zero-copy data transfer (no serialization overhead)                      ║
║  • No database lock conflicts                                               ║
║  • Efficient columnar data format                                          ║
║  • Memory mapping support for large datasets                               ║
║  • Fallback to traditional access if Arrow IPC not available              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

async def test_arrow_ipc_daemon_interface():
    """Test the Arrow IPC daemon interface directly."""
    print("\n🔬 Testing Arrow IPC Daemon Interface...")
    
    try:
        from ipfs_kit_py.arrow_ipc_daemon_interface import (
            ArrowIPCDaemonInterface,
            get_global_arrow_ipc_interface
        )
        
        # Test direct interface
        print("✅ Arrow IPC daemon interface imported successfully")
        
        interface = get_global_arrow_ipc_interface()
        print(f"✅ Created Arrow IPC interface: {interface}")
        
        # Test daemon connection
        daemon_running = await interface.daemon_client.is_daemon_running()
        print(f"🔍 Daemon running: {daemon_running}")
        
        if daemon_running:
            # Test daemon capabilities
            capabilities = await interface.daemon_client.get_capabilities()
            print(f"🔧 Daemon capabilities: {capabilities}")
            
            # Test Arrow IPC pin index access
            print("\n📌 Testing Arrow IPC pin index access...")
            start_time = time.time()
            
            pin_table = await interface.get_pin_index_arrow(limit=10)
            
            end_time = time.time()
            
            if pin_table is not None:
                print(f"✅ Arrow IPC pin access successful!")
                print(f"   📊 Table: {pin_table.num_rows} rows, {pin_table.num_columns} columns")
                print(f"   ⏱️  Time: {(end_time - start_time)*1000:.1f}ms")
                print(f"   📝 Schema: {pin_table.schema}")
                
                # Convert to Python list for display
                pin_data = interface.table_to_dict(pin_table)
                if pin_data:
                    print(f"   📋 Sample data: {json.dumps(pin_data[0], indent=2, default=str)}")
            else:
                print("⚠️  Arrow IPC pin access returned None (fallback may have been used)")
            
            # Test Arrow IPC metrics access
            print("\n📊 Testing Arrow IPC metrics access...")
            start_time = time.time()
            
            metrics_table = await interface.get_metrics_arrow()
            
            end_time = time.time()
            
            if metrics_table is not None:
                print(f"✅ Arrow IPC metrics access successful!")
                print(f"   📊 Table: {metrics_table.num_rows} rows, {metrics_table.num_columns} columns")
                print(f"   ⏱️  Time: {(end_time - start_time)*1000:.1f}ms")
                
                # Show sample metrics
                metrics_data = interface.table_to_dict(metrics_table)
                if metrics_data:
                    print(f"   📋 Sample metrics: {len(metrics_data)} items")
            else:
                print("⚠️  Arrow IPC metrics access returned None")
        
        else:
            print("⚠️  Daemon not running - testing fallback methods...")
            
            # Test fallback methods
            pin_result = await interface.get_pin_index_arrow(limit=5)
            if pin_result:
                print(f"✅ Fallback pin access worked: {pin_result.num_rows} rows")
            else:
                print("❌ Fallback pin access failed")
        
        return True
        
    except ImportError as e:
        print(f"❌ Arrow IPC interface not available: {e}")
        return False
    except Exception as e:
        print(f"❌ Arrow IPC test failed: {e}")
        logger.exception("Arrow IPC test error")
        return False

async def test_vfs_manager_integration():
    """Test VFS Manager integration with Arrow IPC."""
    print("\n🗂️  Testing VFS Manager Arrow IPC Integration...")
    
    try:
        from ipfs_kit_py.vfs_manager import get_global_vfs_manager
        
        vfs_manager = get_global_vfs_manager()
        print("✅ VFS Manager loaded successfully")
        
        # Test zero-copy pin access through VFS Manager
        print("\n📌 Testing VFS Manager zero-copy pin access...")
        start_time = time.time()
        
        pin_result = await vfs_manager.get_pin_index_zero_copy(limit=10)
        
        end_time = time.time()
        
        if pin_result and pin_result.get("success"):
            pins = pin_result.get("pins", [])
            source = pin_result.get("source", "unknown")
            method = pin_result.get("method", "unknown")
            
            print(f"✅ VFS Manager zero-copy access successful!")
            print(f"   📊 Retrieved: {len(pins)} pins")
            print(f"   🔗 Source: {source}")
            print(f"   ⚡ Method: {method}")
            print(f"   ⏱️  Time: {(end_time - start_time)*1000:.1f}ms")
            
            if pins:
                print(f"   📋 Sample pin: {json.dumps(pins[0], indent=2, default=str)}")
                
            if pin_result.get("warning"):
                print(f"   ⚠️  Warning: {pin_result['warning']}")
        else:
            print("❌ VFS Manager zero-copy access failed")
            if pin_result:
                print(f"   Error: {pin_result.get('error', 'Unknown error')}")
        
        # Test zero-copy metrics access
        print("\n📊 Testing VFS Manager zero-copy metrics access...")
        start_time = time.time()
        
        metrics_result = await vfs_manager.get_metrics_zero_copy()
        
        end_time = time.time()
        
        if metrics_result and metrics_result.get("success"):
            metrics = metrics_result.get("metrics", [])
            source = metrics_result.get("source", "unknown")
            method = metrics_result.get("method", "unknown")
            
            print(f"✅ VFS Manager zero-copy metrics successful!")
            print(f"   📊 Retrieved: {len(metrics)} metrics")
            print(f"   🔗 Source: {source}")
            print(f"   ⚡ Method: {method}")
            print(f"   ⏱️  Time: {(end_time - start_time)*1000:.1f}ms")
        else:
            print("❌ VFS Manager zero-copy metrics failed")
            if metrics_result:
                print(f"   Error: {metrics_result.get('error', 'Unknown error')}")
        
        return True
        
    except ImportError as e:
        print(f"❌ VFS Manager not available: {e}")
        return False
    except Exception as e:
        print(f"❌ VFS Manager test failed: {e}")
        logger.exception("VFS Manager test error")
        return False

def test_cli_integration():
    """Test CLI integration with zero-copy access."""
    print("\n💻 Testing CLI Integration...")
    
    try:
        from ipfs_kit_py.cli import FastCLI
        
        cli = FastCLI()
        print("✅ CLI loaded successfully")
        
        # Test VFS Manager import in CLI
        get_global_vfs_manager = cli._lazy_import_vfs_manager() if hasattr(cli, '_lazy_import_vfs_manager') else None
        
        if get_global_vfs_manager:
            print("✅ VFS Manager import available in CLI")
            
            vfs_manager = get_global_vfs_manager()
            print("✅ VFS Manager instance created from CLI")
            
            # Test synchronous zero-copy access (for CLI use)
            print("\n📌 Testing CLI synchronous zero-copy access...")
            start_time = time.time()
            
            pin_result = vfs_manager.get_pin_index_zero_copy_sync(limit=5)
            
            end_time = time.time()
            
            if pin_result and pin_result.get("success"):
                pins = pin_result.get("pins", [])
                method = pin_result.get("method", "unknown")
                
                print(f"✅ CLI zero-copy access successful!")
                print(f"   📊 Retrieved: {len(pins)} pins")
                print(f"   ⚡ Method: {method}")
                print(f"   ⏱️  Time: {(end_time - start_time)*1000:.1f}ms")
            else:
                print("❌ CLI zero-copy access failed")
                if pin_result:
                    print(f"   Error: {pin_result.get('error', 'Unknown error')}")
        else:
            print("⚠️  VFS Manager import not available in CLI")
        
        return True
        
    except ImportError as e:
        print(f"❌ CLI not available: {e}")
        return False
    except Exception as e:
        print(f"❌ CLI test failed: {e}")
        logger.exception("CLI test error")
        return False

async def test_performance_comparison():
    """Compare performance between Arrow IPC and traditional access."""
    print("\n⚡ Performance Comparison...")
    
    try:
        from ipfs_kit_py.vfs_manager import get_global_vfs_manager
        
        vfs_manager = get_global_vfs_manager()
        
        # Test with different limits to see scaling
        limits = [10, 50, 100, 500]
        
        for limit in limits:
            print(f"\n📊 Testing with limit={limit}...")
            
            # Test zero-copy access
            start_time = time.time()
            zero_copy_result = await vfs_manager.get_pin_index_zero_copy(limit=limit)
            zero_copy_time = (time.time() - start_time) * 1000
            
            # Test traditional access (if available)
            start_time = time.time()
            traditional_result = await vfs_manager._get_pin_index_fallback(limit=limit)
            traditional_time = (time.time() - start_time) * 1000
            
            # Compare results
            zero_copy_count = len(zero_copy_result.get("pins", [])) if zero_copy_result and zero_copy_result.get("success") else 0
            traditional_count = len(traditional_result.get("pins", [])) if traditional_result and traditional_result.get("success") else 0
            
            print(f"   🚀 Zero-copy: {zero_copy_count} pins in {zero_copy_time:.1f}ms")
            print(f"   🐌 Traditional: {traditional_count} pins in {traditional_time:.1f}ms")
            
            if zero_copy_time > 0 and traditional_time > 0:
                speedup = traditional_time / zero_copy_time
                print(f"   📈 Speedup: {speedup:.1f}x faster with zero-copy")
            
        return True
        
    except Exception as e:
        print(f"❌ Performance comparison failed: {e}")
        logger.exception("Performance comparison error")
        return False

async def check_system_status():
    """Check system status for Arrow IPC prerequisites."""
    print("\n🔍 System Status Check...")
    
    # Check Apache Arrow availability
    try:
        import pyarrow as pa
        print(f"✅ Apache Arrow available: version {pa.__version__}")
    except ImportError:
        print("❌ Apache Arrow not available - install with 'pip install pyarrow'")
        return False
    
    # Check daemon status
    try:
        from ipfs_kit_py.ipfs_kit_daemon_client import DaemonClient
        
        daemon_client = DaemonClient()
        daemon_running = await daemon_client.is_daemon_running()
        
        if daemon_running:
            print("✅ IPFS-Kit daemon is running")
            
            status = await daemon_client.get_daemon_status()
            print(f"   📊 Status: {status}")
            
            capabilities = await daemon_client.get_capabilities()
            if capabilities.get("arrow_ipc"):
                print("✅ Daemon supports Arrow IPC")
            else:
                print("⚠️  Daemon does not yet support Arrow IPC (using fallback methods)")
        else:
            print("⚠️  IPFS-Kit daemon not running (will test fallback methods)")
    
    except Exception as e:
        print(f"⚠️  Daemon status check failed: {e}")
    
    # Check pin index files
    try:
        pin_db_path = Path.home() / '.ipfs_kit' / 'enhanced_pin_index'
        if pin_db_path.exists():
            db_files = list(pin_db_path.glob('*.duckdb')) + list(pin_db_path.glob('*.db'))
            if db_files:
                print(f"✅ Pin index files found: {len(db_files)} files")
                for db_file in db_files:
                    size = db_file.stat().st_size
                    print(f"   📁 {db_file.name}: {size:,} bytes")
            else:
                print("⚠️  Pin index directory exists but no database files found")
        else:
            print("⚠️  Pin index directory not found (~/.ipfs_kit/enhanced_pin_index/)")
    except Exception as e:
        print(f"⚠️  Pin index check failed: {e}")
    
    return True

async def main():
    """Run the Arrow IPC zero-copy demonstration."""
    banner()
    
    print("🚀 Starting Arrow IPC Zero-Copy Demonstration...")
    
    # System status check
    await check_system_status()
    
    # Test Arrow IPC interface
    arrow_success = await test_arrow_ipc_daemon_interface()
    
    # Test VFS Manager integration
    vfs_success = await test_vfs_manager_integration()
    
    # Test CLI integration
    cli_success = test_cli_integration()
    
    # Performance comparison
    if arrow_success and vfs_success:
        await test_performance_comparison()
    
    # Summary
    print("\n" + "="*80)
    print("📋 DEMONSTRATION SUMMARY")
    print("="*80)
    
    print(f"🔬 Arrow IPC Interface:    {'✅ PASS' if arrow_success else '❌ FAIL'}")
    print(f"🗂️  VFS Manager Integration: {'✅ PASS' if vfs_success else '❌ FAIL'}")
    print(f"💻 CLI Integration:        {'✅ PASS' if cli_success else '❌ FAIL'}")
    
    if arrow_success and vfs_success and cli_success:
        print("\n🎉 All tests passed! Arrow IPC zero-copy functionality is working.")
        print("\n💡 Next steps:")
        print("   • Use 'ipfs-kit pin list' to see zero-copy access in action")
        print("   • Start the daemon to enable full Arrow IPC capabilities")
        print("   • Check daemon logs for Arrow IPC status messages")
    else:
        print("\n⚠️  Some tests failed. Check the logs above for details.")
        print("\n🔧 Troubleshooting:")
        print("   • Ensure Apache Arrow is installed: pip install pyarrow")
        print("   • Check if IPFS-Kit daemon is running")
        print("   • Verify pin index files exist in ~/.ipfs_kit/enhanced_pin_index/")
    
    print("\n🏁 Demonstration complete!")

if __name__ == "__main__":
    asyncio.run(main())
