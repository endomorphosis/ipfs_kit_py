#!/usr/bin/env python3
"""
Resource Tracking Demo - Bandwidth and Storage Monitoring

This script demonstrates how to use the resource tracking system to monitor
bandwidth and storage consumption across remote filesystem backends.
"""

import anyio
import time
import random
from pathlib import Path

# Import the resource tracking components
from ipfs_kit_py.resource_tracker import (
    get_resource_tracker, 
    ResourceMetric, 
    ResourceType, 
    BackendType,
    track_bandwidth_upload,
    track_bandwidth_download,
    track_storage_usage,
    track_api_call
)

from ipfs_kit_py.resource_tracking_decorators import (
    track_operation,
    track_upload,
    track_download,
    track_api
)

async def demo_basic_tracking():
    """Demonstrate basic resource tracking functionality."""
    print("🚀 Starting Resource Tracking Demo")
    print("=" * 50)
    
    # Get the resource tracker instance
    tracker = get_resource_tracker()
    
    # Simulate some backend operations
    backends = [
        ("s3_primary", BackendType.S3),
        ("ipfs_gateway", BackendType.IPFS),
        ("huggingface_hub", BackendType.HUGGINGFACE),
        ("storacha_endpoint", BackendType.STORACHA)
    ]
    
    print("📊 Simulating backend operations...")
    
    for i in range(10):
        backend_name, backend_type = random.choice(backends)
        
        # Simulate different types of operations
        operation_type = random.choice(['upload', 'download', 'api_call', 'storage'])
        
        if operation_type == 'upload':
            bytes_uploaded = random.randint(1024, 50 * 1024 * 1024)  # 1KB to 50MB
            track_bandwidth_upload(backend_name, backend_type, bytes_uploaded, 
                                 f"upload_op_{i}", f"/test/file_{i}.dat")
            print(f"  📤 {backend_name}: Uploaded {bytes_uploaded / (1024*1024):.1f} MB")
            
        elif operation_type == 'download':
            bytes_downloaded = random.randint(1024, 100 * 1024 * 1024)  # 1KB to 100MB
            track_bandwidth_download(backend_name, backend_type, bytes_downloaded,
                                   f"download_op_{i}", f"/test/file_{i}.dat")
            print(f"  📥 {backend_name}: Downloaded {bytes_downloaded / (1024*1024):.1f} MB")
            
        elif operation_type == 'storage':
            bytes_stored = random.randint(1024, 20 * 1024 * 1024)  # 1KB to 20MB
            track_storage_usage(backend_name, backend_type, bytes_stored,
                              f"storage_op_{i}", f"/test/file_{i}.dat")
            print(f"  💾 {backend_name}: Stored {bytes_stored / (1024*1024):.1f} MB")
            
        elif operation_type == 'api_call':
            track_api_call(backend_name, backend_type, f"api_op_{i}", 
                         {"endpoint": "/api/v1/files", "method": "GET"})
            print(f"  🔧 {backend_name}: API call made")
        
        # Update backend status periodically
        if i % 3 == 0:
            tracker.update_backend_status(
                backend_name=backend_name,
                backend_type=backend_type,
                is_active=True,
                bandwidth_usage_mbps=random.uniform(0.1, 10.0),
                storage_usage_gb=random.uniform(1.0, 100.0),
                health_status=random.choice(['healthy', 'degraded', 'healthy', 'healthy']),
                metadata={"last_check": time.time()}
            )
        
        # Small delay to spread operations over time
        await anyio.sleep(0.1)
    
    print("\n✅ Simulated operations completed!")

async def demo_context_manager():
    """Demonstrate the context manager for complex operations."""
    print("\n🔄 Context Manager Demo")
    print("=" * 30)
    
    # Simulate a complex bulk upload operation
    with track_operation('s3_primary', BackendType.S3, 'bulk_upload', '/bulk/data/') as op_tracker:
        print("  🔄 Starting bulk upload operation...")
        
        # Simulate uploading multiple files
        for i in range(5):
            file_size = random.randint(1024 * 1024, 10 * 1024 * 1024)  # 1MB to 10MB
            op_tracker.add_bandwidth_upload(file_size)
            op_tracker.add_storage_usage(file_size)
            op_tracker.add_api_call({"file": f"bulk_file_{i}.dat", "size": file_size})
            
            print(f"    📤 Uploaded file_{i}.dat ({file_size / (1024*1024):.1f} MB)")
            await anyio.sleep(0.05)
        
        # Get operation summary
        summary = op_tracker.get_summary()
        print(f"  📊 Operation Summary: {summary['resources']}")

@track_upload('demo_backend', BackendType.S3)
async def simulated_upload_function(data: bytes, filename: str):
    """Example function with upload tracking decorator."""
    print(f"  🔄 Uploading {filename} ({len(data)} bytes)...")
    await anyio.sleep(0.1)  # Simulate upload time
    return {"status": "success", "size": len(data), "filename": filename}

@track_api('demo_backend', BackendType.S3) 
async def simulated_api_function(endpoint: str):
    """Example function with API call tracking decorator."""
    print(f"  🔧 Making API call to {endpoint}...")
    await anyio.sleep(0.05)  # Simulate API call time
    return {"status": "success", "endpoint": endpoint}

async def demo_decorators():
    """Demonstrate automatic tracking with decorators."""
    print("\n🎯 Decorator Demo")
    print("=" * 20)
    
    # Test upload decorator
    test_data = b"X" * (2 * 1024 * 1024)  # 2MB of test data
    result = await simulated_upload_function(test_data, "test_file.dat")
    print(f"  ✅ Upload result: {result['status']}")
    
    # Test API decorator  
    result = await simulated_api_function("/api/v1/status")
    print(f"  ✅ API result: {result['status']}")

async def demo_reporting():
    """Demonstrate resource usage reporting."""
    print("\n📋 Resource Usage Report")
    print("=" * 30)
    
    tracker = get_resource_tracker()
    
    # Get usage summary
    print("📊 Usage Summary (Current Day):")
    summary = tracker.get_resource_summary(period='day')
    
    if 'backends' in summary and summary['backends']:
        for backend_name, backend_data in summary['backends'].items():
            print(f"\n  🏢 {backend_name} ({backend_data['backend_type']}):")
            for resource_type, resource_data in backend_data['resources'].items():
                formatted_amount = resource_data['formatted_amount']
                operations = resource_data['operation_count']
                print(f"    {resource_type}: {formatted_amount} ({operations} ops)")
    else:
        print("  No usage data available yet")
    
    # Get backend status
    print("\n🏥 Backend Status:")
    status = tracker.get_backend_status()
    if status:
        for backend_name, backend_info in status.items():
            active_icon = "✅" if backend_info['is_active'] else "❌"
            health_icon = {"healthy": "🟢", "degraded": "🟡", "unhealthy": "🔴"}.get(
                backend_info['health_status'], "⚪"
            )
            print(f"  {active_icon} {backend_name} {health_icon}")
            print(f"    Bandwidth: {backend_info['current_bandwidth_usage_mbps'] or 0:.1f} Mbps")
            print(f"    Storage: {backend_info['current_storage_usage_gb'] or 0:.2f} GB")
    else:
        print("  No backend status available")
    
    # Get recent detailed usage
    print("\n📋 Recent Activity (Last Hour):")
    recent_usage = tracker.get_resource_usage(hours_back=1, limit=10)
    if recent_usage:
        for record in recent_usage[:5]:  # Show last 5 records
            timestamp = record['datetime'][:16]  # YYYY-MM-DD HH:MM
            backend = record['backend_name']
            resource = record['resource_type']
            amount = _format_amount(record['resource_type'], record['amount'])
            print(f"  {timestamp} | {backend} | {resource}: {amount}")
    else:
        print("  No recent activity")

def _format_amount(resource_type: str, amount: int) -> str:
    """Format resource amount for display."""
    if resource_type in ['bandwidth_upload', 'bandwidth_download', 'storage_used']:
        if amount < 1024:
            return f"{amount} B"
        elif amount < 1024 * 1024:
            return f"{amount / 1024:.1f} KB"
        elif amount < 1024 * 1024 * 1024:
            return f"{amount / (1024 * 1024):.1f} MB"
        else:
            return f"{amount / (1024 * 1024 * 1024):.1f} GB"
    elif resource_type == 'api_calls':
        return f"{amount} calls"
    else:
        return str(amount)

async def main():
    """Run the complete resource tracking demo."""
    print("🎯 IPFS Kit Resource Tracking Demo")
    print("=" * 60)
    print("This demo shows how to track bandwidth and storage consumption")
    print("across remote filesystem backends using fast indexes.")
    print()
    
    try:
        # Run all demo functions
        await demo_basic_tracking()
        await demo_context_manager()
        await demo_decorators()
        await demo_reporting()
        
        print("\n" + "=" * 60)
        print("🎉 Demo completed successfully!")
        print("\n💡 Key Features Demonstrated:")
        print("  ✅ Automatic resource tracking")
        print("  ✅ Real-time usage monitoring")
        print("  ✅ Backend status tracking")
        print("  ✅ Fast SQLite-based indexing")
        print("  ✅ Decorator-based integration")
        print("  ✅ Context manager for complex operations")
        print("\n📈 Use the CLI for detailed monitoring:")
        print("  ipfs-kit resource usage --period day")
        print("  ipfs-kit resource details --hours 24")
        print("  ipfs-kit resource status")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    anyio.run(main)
