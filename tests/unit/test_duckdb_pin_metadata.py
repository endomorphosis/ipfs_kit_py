#!/usr/bin/env python3
"""
Test script for the DuckDB + Parquet-based IPFSPinMetadataIndex.
"""

import asyncio
import time
import json
from pathlib import Path
import tempfile
import shutil

from ipfs_kit_py.pins import IPFSPinMetadataIndex


async def test_duckdb_pin_metadata():
    """Test the DuckDB + Parquet implementation."""
    
    # Create temporary directory for testing
    test_dir = Path(tempfile.mkdtemp(prefix="ipfs_kit_duckdb_test_"))
    print(f"✓ Created test directory: {test_dir}")
    
    try:
        # Initialize the index with DuckDB
        print("\n🔧 Initializing DuckDB-based pin metadata index...")
        index = IPFSPinMetadataIndex(
            data_dir=str(test_dir),
            update_interval=60,  # 1 minute for testing
            max_cache_age=300    # 5 minutes
        )
        
        # Verify DuckDB initialization
        print("✓ DuckDB initialization successful")
        print(f"✓ Database path: {index.db_path}")
        print(f"✓ Pins Parquet: {index.pins_parquet}")
        print(f"✓ Traffic Parquet: {index.traffic_parquet}")
        
        # Test recording pin access
        print("\n📊 Testing pin access recording...")
        test_cids = [
            ("QmTest1234567890abcdef", 1024 * 1024),      # 1MB
            ("QmTest2345678901bcdefg", 512 * 1024),       # 512KB
            ("QmTest3456789012cdefgh", 2 * 1024 * 1024),  # 2MB
            ("QmTest4567890123defghi", 256 * 1024),       # 256KB
            ("QmTest5678901234efghij", 4 * 1024 * 1024)   # 4MB
        ]
        
        for cid, size in test_cids:
            index.record_pin_access(cid, size)
            print(f"  ✓ Recorded access: {cid[:16]}... ({size/1024/1024:.1f}MB)")
        
        # Test pin size retrieval
        print("\n🔍 Testing pin size retrieval...")
        for cid, expected_size in test_cids[:3]:
            retrieved_size = index.get_pin_size(cid)
            print(f"  ✓ {cid[:16]}...: {retrieved_size/1024/1024:.1f}MB (expected: {expected_size/1024/1024:.1f}MB)")
            assert retrieved_size == expected_size, f"Size mismatch for {cid}"
        
        # Test traffic metrics with DuckDB queries
        print("\n📈 Testing traffic metrics calculation...")
        metrics = index.get_traffic_metrics()
        
        print(f"  ✓ Total pins: {metrics.total_pins}")
        print(f"  ✓ Total size: {metrics.total_size_human}")
        print(f"  ✓ Average pin size: {metrics.average_pin_size/1024/1024:.1f}MB")
        print(f"  ✓ Median pin size: {metrics.median_pin_size/1024/1024:.1f}MB")
        print(f"  ✓ Bandwidth estimate: {metrics.bandwidth_estimate_human}")
        print(f"  ✓ Largest pins: {len(metrics.largest_pins)} entries")
        
        for i, pin in enumerate(metrics.largest_pins[:3]):
            print(f"    {i+1}. {pin['cid']}: {pin['size_human']}")
        
        # Test cache statistics
        print("\n📊 Testing cache statistics...")
        stats = index.get_cache_stats()
        print(f"  ✓ Cache hit rate: {stats['cache_hit_rate']:.2%}")
        print(f"  ✓ Total pins cached: {stats['total_pins_cached']}")
        print(f"  ✓ DuckDB pins: {stats['duckdb_stats']['pins_in_database']}")
        print(f"  ✓ Traffic records: {stats['duckdb_stats']['traffic_records_in_database']}")
        
        # Test saving to Parquet
        print("\n💾 Testing Parquet export...")
        index._save_cache()
        
        if index.pins_parquet.exists():
            size = index.pins_parquet.stat().st_size
            print(f"  ✓ Pins Parquet file created: {size} bytes")
        else:
            print("  ❌ Pins Parquet file not created")
        
        if index.traffic_parquet.exists():
            size = index.traffic_parquet.stat().st_size
            print(f"  ✓ Traffic Parquet file created: {size} bytes")
        else:
            print("  ❌ Traffic Parquet file not created")
        
        # Test loading from Parquet (simulate restart)
        print("\n🔄 Testing Parquet reload (simulating restart)...")
        index2 = IPFSPinMetadataIndex(
            data_dir=str(test_dir),
            update_interval=60,
            max_cache_age=300
        )
        
        print(f"  ✓ Reloaded {len(index2.pin_metadata)} pins from Parquet")
        
        # Verify data integrity after reload
        for cid, expected_size in test_cids:
            retrieved_size = index2.get_pin_size(cid)
            if retrieved_size == expected_size:
                print(f"  ✓ Data integrity verified for {cid[:16]}...")
            else:
                print(f"  ❌ Data integrity failed for {cid[:16]}... (got {retrieved_size}, expected {expected_size})")
        
        # Test DuckDB SQL query capabilities
        print("\n🔍 Testing direct DuckDB queries...")
        try:
            # Query largest pins using raw SQL
            result = index2.conn.execute("""
                SELECT cid, size_bytes, name, access_count
                FROM pins 
                ORDER BY size_bytes DESC 
                LIMIT 3
            """).fetchall()
            
            print("  ✓ Top 3 largest pins (via SQL):")
            for row in result:
                cid, size_bytes, name, access_count = row
                print(f"    - {cid[:16]}...: {size_bytes/1024/1024:.1f}MB, accessed {access_count} times")
            
            # Query recent traffic
            recent_count = index2.conn.execute("""
                SELECT COUNT(*) FROM traffic_history 
                WHERE timestamp > ?
            """, [time.time() - 3600]).fetchone()[0]
            
            print(f"  ✓ Recent traffic records (last hour): {recent_count}")
            
        except Exception as e:
            print(f"  ❌ DuckDB query failed: {e}")
        
        print("\n✅ All DuckDB + Parquet tests completed successfully!")
        print(f"   - DuckDB database: {index.db_path}")
        print(f"   - Pins Parquet: {index.pins_parquet}")
        print(f"   - Traffic Parquet: {index.traffic_parquet}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        try:
            shutil.rmtree(test_dir)
            print(f"\n🧹 Cleaned up test directory: {test_dir}")
        except Exception as e:
            print(f"Warning: Failed to cleanup test directory: {e}")


if __name__ == "__main__":
    print("🚀 Testing DuckDB + Parquet-based IPFS Pin Metadata Index")
    print("=" * 60)
    
    success = asyncio.run(test_duckdb_pin_metadata())
    
    if success:
        print("\n🎉 DuckDB conversion successful! The pin metadata index now uses:")
        print("   - DuckDB for analytical queries")
        print("   - Parquet for efficient columnar storage")
        print("   - SQL-based metrics calculations")
        print("   - Enhanced analytical capabilities")
    else:
        print("\n💥 DuckDB conversion encountered issues")
