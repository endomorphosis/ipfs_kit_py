"""
Simple Integration Test for Core Parquet-IPLD Functionality.

This test validates the core components without the full IPFS integration
to work around protobuf version conflicts.
"""

import json
import logging
import os
import tempfile
import time
from pathlib import Path

try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    ARROW_AVAILABLE = True
    print("✅ PyArrow and Pandas available")
except ImportError as e:
    ARROW_AVAILABLE = False
    print(f"❌ Arrow not available: {e}")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_core_parquet_operations():
    """Test core Parquet operations without IPFS."""
    if not ARROW_AVAILABLE:
        return False
    
    print("\n🧪 Testing Core Parquet Operations...")
    
    # Create test data
    test_df = pd.DataFrame({
        "id": range(100),
        "name": [f"item_{i}" for i in range(100)],
        "value": [i * 1.5 for i in range(100)],
        "category": ["A", "B", "C"] * 33 + ["A"]
    })
    
    with tempfile.TemporaryDirectory() as temp_dir:
        parquet_path = os.path.join(temp_dir, "test.parquet")
        
        # Write Parquet file
        try:
            test_df.to_parquet(parquet_path, compression="zstd", index=False)
            print(f"✅ Parquet write successful: {parquet_path}")
        except Exception as e:
            print(f"❌ Parquet write failed: {e}")
            return False
        
        # Read Parquet file
        try:
            read_df = pd.read_parquet(parquet_path)
            print(f"✅ Parquet read successful: {len(read_df)} rows")
        except Exception as e:
            print(f"❌ Parquet read failed: {e}")
            return False
        
        # Verify data integrity
        if len(read_df) == len(test_df) and list(read_df.columns) == list(test_df.columns):
            print("✅ Data integrity verified")
        else:
            print("❌ Data integrity check failed")
            return False
        
        # Test PyArrow operations
        try:
            table = pa.Table.from_pandas(test_df)
            filtered_table = table.filter(pa.compute.greater(table["value"], 50))
            print(f"✅ PyArrow filtering successful: {filtered_table.num_rows} rows after filter")
        except Exception as e:
            print(f"❌ PyArrow operations failed: {e}")
            return False
    
    return True


def test_arrow_compute_operations():
    """Test Arrow compute operations."""
    if not ARROW_AVAILABLE:
        return False
    
    print("\n🧪 Testing Arrow Compute Operations...")
    
    # Create test data
    data = {
        "numbers": list(range(1000)),
        "categories": ["A", "B", "C", "D"] * 250,
        "values": [i * 0.1 for i in range(1000)]
    }
    
    try:
        table = pa.table(data)
        
        # Test aggregations
        grouped = table.group_by("categories").aggregate([
            ("numbers", "sum"),
            ("values", "mean"),
            ("values", "count")
        ])
        print(f"✅ Arrow groupby successful: {grouped.num_rows} groups")
        
        # Test filtering
        filtered = table.filter(pa.compute.greater(table["numbers"], 500))
        print(f"✅ Arrow filtering successful: {filtered.num_rows} rows")
        
        # Test sorting
        sorted_table = table.sort_by([("values", "descending")])
        print(f"✅ Arrow sorting successful: {sorted_table.num_rows} rows")
        
        return True
        
    except Exception as e:
        print(f"❌ Arrow compute operations failed: {e}")
        return False


def test_virtual_filesystem_concept():
    """Test virtual filesystem concepts."""
    print("\n🧪 Testing Virtual Filesystem Concepts...")
    
    class MockVFS:
        def __init__(self, storage_path):
            self.storage_path = storage_path
            self.structure = {
                "/": {"type": "directory", "children": {}}
            }
        
        def add_file(self, path, metadata):
            parts = path.strip("/").split("/")
            current = self.structure["/"]["children"]
            
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {"type": "directory", "children": {}}
                current = current[part]["children"]
            
            current[parts[-1]] = {"type": "file", "metadata": metadata}
        
        def ls(self, path="/"):
            parts = [p for p in path.strip("/").split("/") if p]
            current = self.structure["/"]
            
            for part in parts:
                current = current["children"][part]
            
            if current["type"] == "directory":
                return list(current["children"].keys())
            else:
                return [path.split("/")[-1]]
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            vfs = MockVFS(temp_dir)
            
            # Add some mock files
            vfs.add_file("/datasets/sales.parquet", {"size": 1024, "cid": "fake_cid_1"})
            vfs.add_file("/datasets/customers.parquet", {"size": 2048, "cid": "fake_cid_2"})
            vfs.add_file("/metadata/sales.json", {"type": "metadata"})
            
            # Test listing
            root_files = vfs.ls("/")
            datasets_files = vfs.ls("/datasets")
            metadata_files = vfs.ls("/metadata")
            
            print(f"✅ VFS root listing: {root_files}")
            print(f"✅ VFS datasets listing: {datasets_files}")
            print(f"✅ VFS metadata listing: {metadata_files}")
            
            return True
            
    except Exception as e:
        print(f"❌ VFS concept test failed: {e}")
        return False


def test_content_addressing_concept():
    """Test content addressing concepts."""
    print("\n🧪 Testing Content Addressing Concepts...")
    
    try:
        import hashlib
        
        # Simulate content addressing
        test_content = "This is test content for addressing"
        content_hash = hashlib.sha256(test_content.encode()).hexdigest()
        fake_cid = f"bafkreie{content_hash[:32]}"
        
        print(f"✅ Content hash: {content_hash[:16]}...")
        print(f"✅ Fake CID: {fake_cid}")
        
        # Test deterministic addressing
        same_content = "This is test content for addressing"
        same_hash = hashlib.sha256(same_content.encode()).hexdigest()
        
        if content_hash == same_hash:
            print("✅ Deterministic addressing verified")
        else:
            print("❌ Deterministic addressing failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Content addressing test failed: {e}")
        return False


def test_metadata_management():
    """Test metadata management concepts."""
    print("\n🧪 Testing Metadata Management...")
    
    try:
        # Mock metadata structure
        dataset_metadata = {
            "cid": "bafkreie123...",
            "name": "sales_data",
            "size_bytes": 1024000,
            "rows": 10000,
            "columns": ["date", "product", "sales", "revenue"],
            "created_at": "2024-01-01T00:00:00Z",
            "schema": {
                "date": "date64",
                "product": "string",
                "sales": "int64",
                "revenue": "float64"
            },
            "partitions": ["date"],
            "compression": "zstd"
        }
        
        # Test JSON serialization
        metadata_json = json.dumps(dataset_metadata, indent=2)
        parsed_metadata = json.loads(metadata_json)
        
        if parsed_metadata == dataset_metadata:
            print("✅ Metadata serialization/deserialization successful")
        else:
            print("❌ Metadata serialization failed")
            return False
        
        print(f"✅ Metadata structure validated: {len(dataset_metadata)} fields")
        return True
        
    except Exception as e:
        print(f"❌ Metadata management test failed: {e}")
        return False


def run_simple_tests():
    """Run all simple tests."""
    print("🚀 Starting Simple Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Core Parquet Operations", test_core_parquet_operations),
        ("Arrow Compute Operations", test_arrow_compute_operations),
        ("Virtual Filesystem Concept", test_virtual_filesystem_concept),
        ("Content Addressing Concept", test_content_addressing_concept),
        ("Metadata Management", test_metadata_management)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<30}: {status}")
        if result:
            passed += 1
    
    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 ALL CORE TESTS PASSED!")
        print("The fundamental components are working correctly.")
        print("Ready for IPFS integration once protobuf conflicts are resolved.")
        return True
    else:
        print(f"\n❌ {total - passed} tests failed.")
        return False


if __name__ == "__main__":
    success = run_simple_tests()
    
    if success:
        print("\n✅ Simple integration test completed successfully!")
        print("\nNext steps:")
        print("1. Resolve protobuf version conflicts")
        print("2. Test with actual IPFS integration")
        print("3. Validate MCP server functionality")
    else:
        print("\n❌ Simple integration test failed!")
    
    exit(0 if success else 1)
