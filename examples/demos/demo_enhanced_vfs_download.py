#!/usr/bin/env python3
"""
Enhanced VFS Download Demo

Demonstrates the enhanced IPFS VFS extractor with CLI integration
using the sample bucket_files.json data.
"""

import json
import subprocess
import tempfile
import shutil
from pathlib import Path
import time


def simulate_ipfs_upload_for_demo():
    """Simulate IPFS upload process for demo purposes."""
    # Load the sample bucket files
    with open('bucket_files.json', 'r') as f:
        bucket_data = json.load(f)
    
    print("🔧 Enhanced VFS Download Demo Setup")
    print("=" * 50)
    
    # Create temporary demo indexes
    demo_dir = Path("examples/data/vfs_indexes")
    demo_dir.mkdir(exist_ok=True)
    
    # Create individual bucket indexes
    bucket_hashes = {}
    master_buckets = {}
    
    for bucket_name, files in bucket_data.items():
        # Create bucket index
        bucket_index = {
            "metadata": {
                "bucket_name": bucket_name,
                "created_at": "2025-07-28T14:30:00",
                "file_count": len(files),
                "size_mb": sum(f['size_bytes'] for f in files) / (1024*1024)
            },
            "files": files
        }
        
        # Write bucket index
        bucket_file = demo_dir / f"{bucket_name}_index.json"
        with open(bucket_file, 'w') as f:
            json.dump(bucket_index, f, indent=2)
        
        # Simulate IPFS hash for demo
        fake_hash = f"Qm{bucket_name.upper()[:20].ljust(20, 'X')}{'1' * 26}"
        bucket_hashes[bucket_name] = fake_hash
        
        master_buckets[bucket_name] = {
            "ipfs_hash": fake_hash,
            "file_count": len(files),
            "size_bytes": sum(f['size_bytes'] for f in files),
            "created_at": "2025-07-28T14:30:00"
        }
        
        print(f"📦 Created demo index for {bucket_name}")
        print(f"   Simulated hash: {fake_hash}")
        print(f"   Files: {len(files)} | Size: {bucket_index['metadata']['size_mb']:.2f} MB")
    
    # Create master index
    master_index = {
        "metadata": {
            "created_at": "2025-07-28T14:30:00",
            "total_buckets": len(master_buckets),
            "total_files": sum(b['file_count'] for b in master_buckets.values()),
            "total_size_bytes": sum(b['size_bytes'] for b in master_buckets.values())
        },
        "buckets": master_buckets
    }
    
    master_file = demo_dir / "master_index.json"
    with open(master_file, 'w') as f:
        json.dump(master_index, f, indent=2)
    
    master_hash = "QmMASTERINDEXDEMO123456789ABCDEFGHIJKLMNOP"
    
    print(f"\n🌍 Created master index:")
    print(f"   Simulated hash: {master_hash}")
    print(f"   Total buckets: {len(master_buckets)}")
    print(f"   Total files: {master_index['metadata']['total_files']}")
    print(f"   Total size: {master_index['metadata']['total_size_bytes'] / (1024*1024):.2f} MB")
    
    return master_hash, bucket_hashes, demo_dir


def demo_cli_integration():
    """Demonstrate CLI integration features."""
    print("\n🔍 Testing CLI Integration Features")
    print("=" * 40)
    
    try:
        from ipfs_kit_py.enhanced_vfs_extractor import EnhancedIPFSVFSExtractor
        
        extractor = EnhancedIPFSVFSExtractor()
        
        # Test CLI availability
        cli_check = extractor.check_ipfs_kit_cli()
        print(f"📋 CLI Availability Check:")
        if cli_check['available']:
            method_str = ' '.join(cli_check['method'])
            print(f"   ✅ ipfs_kit_py CLI available via: {method_str}")
            
            version_info = cli_check.get('version_info', {})
            if version_info.get('daemon_running'):
                print(f"   ✅ Enhanced daemon is running")
            else:
                print(f"   ⚠️  Enhanced daemon not detected")
        else:
            print(f"   ❌ CLI not available: {cli_check['error']}")
        
        # Test backend detection
        print(f"\n🔍 Backend Detection:")
        backends = extractor._detect_available_backends()
        print(f"   Available backends: {backends}")
        
        # Test pin metadata system (with sample CID)
        sample_cid = "QmY4Q2YxKXR9Zz8qM4c8N5k2z8v3u1L4t6h9q3w2e5r1a"
        print(f"\n📌 Pin Metadata Test:")
        print(f"   Sample CID: {sample_cid}")
        pin_metadata = extractor.get_pin_metadata(sample_cid)
        print(f"   Found in pins: {pin_metadata.get('found', False)}")
        print(f"   Available backends: {pin_metadata.get('backends', [])}")
        
        # Simulate backend benchmarking
        print(f"\n⚡ Backend Performance Simulation:")
        if backends:
            performance = extractor.benchmark_backend_performance(backends[:2], sample_cid)
            for backend, perf_time in performance.items():
                if perf_time != float('inf'):
                    print(f"   {backend}: {perf_time:.3f}s")
                else:
                    print(f"   {backend}: unavailable")
        
        return True
        
    except Exception as e:
        print(f"❌ CLI integration test failed: {e}")
        return False


def demo_enhanced_download():
    """Demonstrate enhanced download workflow."""
    print("\n🚀 Enhanced Download Workflow Demo")
    print("=" * 40)
    
    # Create demo setup
    master_hash, bucket_hashes, demo_dir = simulate_ipfs_upload_for_demo()
    
    print(f"\n📋 Available Demo Commands:")
    print(f"   # Extract master index (shows available buckets)")
    print(f"   ipfs-kit bucket download-vfs {master_hash}")
    print(f"")
    
    for bucket_name, bucket_hash in bucket_hashes.items():
        print(f"   # Extract {bucket_name} with optimization")
        print(f"   ipfs-kit bucket download-vfs {bucket_hash} --bucket-name {bucket_name}")
        print(f"   ipfs-kit bucket download-vfs {bucket_hash} --bucket-name {bucket_name} --workers 4 --benchmark")
        print(f"   ipfs-kit bucket download-vfs {bucket_hash} --bucket-name {bucket_name} --backend ipfs")
        print(f"")
    
    print(f"💡 Enhanced Features:")
    print(f"   ✅ Consults pin metadata index for backend optimization")
    print(f"   ✅ Multiprocessing parallel downloads (auto-detected workers)")
    print(f"   ✅ Backend performance benchmarking")
    print(f"   ✅ Fastest backend auto-selection")
    print(f"   ✅ Real-time download progress with speed metrics")
    print(f"   ✅ Fallback chain: Parquet → IPFS API → Mock detection")
    
    print(f"\n🎯 Performance Optimizations:")
    print(f"   📊 Pin metadata cache for repeated CID lookups")
    print(f"   ⚡ Backend performance cache to avoid re-benchmarking")
    print(f"   🔀 Worker process pool for true parallelism")
    print(f"   📈 Real-time speed monitoring per file")
    print(f"   🎲 Load balancing across fastest backends")
    
    # Show sample bucket analysis
    print(f"\n📦 Sample Bucket Analysis:")
    with open('bucket_files.json', 'r') as f:
        bucket_data = json.load(f)
    
    for bucket_name, files in bucket_data.items():
        total_size = sum(f['size_bytes'] for f in files)
        avg_size = total_size / len(files) if files else 0
        
        print(f"   {bucket_name}:")
        print(f"      Files: {len(files)}")
        print(f"      Total size: {total_size / (1024*1024):.2f} MB")
        print(f"      Average file size: {avg_size / 1024:.1f} KB")
        print(f"      Parallel benefit: {'High' if len(files) > 2 else 'Medium'}")
    
    # Cleanup
    print(f"\n🧹 Demo cleanup: {demo_dir}")
    
    return demo_dir


def main():
    """Run the complete enhanced VFS download demo."""
    print("🔧 Enhanced IPFS VFS Extractor - Complete Demo")
    print("=" * 60)
    print("Features:")
    print("- CLI integration with ipfs_kit_py")
    print("- Pin metadata consultation")  
    print("- Multiprocessing parallel downloads")
    print("- Backend performance optimization")
    print("- Real-time progress monitoring")
    print("")
    
    # Test CLI integration
    cli_success = demo_cli_integration()
    
    # Demo enhanced download workflow
    demo_dir = demo_enhanced_download()
    
    print(f"\n🎉 Demo Complete!")
    print(f"📁 Demo files created in: {demo_dir}")
    print(f"🔧 CLI integration: {'✅ Working' if cli_success else '⚠️  Limited'}")
    
    print(f"\n🚀 Next Steps:")
    print(f"   1. Review the enhanced_ipfs_vfs_extractor.py implementation")
    print(f"   2. Test CLI commands with demo data")
    print(f"   3. Upload real VFS indexes to IPFS")
    print(f"   4. Share master index hashes for optimized parallel downloads")
    print(f"")
    print(f"💡 The system integrates with your existing ipfs_kit_py CLI")
    print(f"   to provide optimized downloads using the fastest available")
    print(f"   virtual filesystem backends with multiprocessing parallelism.")


if __name__ == "__main__":
    main()
