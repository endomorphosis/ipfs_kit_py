#!/usr/bin/env python3
"""
Test script for enhanced pin metadata functionality.
"""

import os
import sys
import tempfile
import shutil
import anyio
import pandas as pd
from pathlib import Path

# Add the ipfs_kit_py directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ipfs_kit_py'))

from ipfs_kit_py.simple_pin_manager import SimplePinManager

async def test_enhanced_pin_metadata():
    """Test enhanced pin metadata file creation."""
    print("🧪 Testing Enhanced Pin Metadata...")
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir) / "test_pins"
        print(f"📁 Using test directory: {test_dir}")
        
        # Initialize SimplePinManager
        pin_manager = SimplePinManager(data_dir=str(test_dir))
        
        # Initialize shard files
        await pin_manager._initialize_shard_files()
        
        # Check that initialization files were created
        pin_metadata_dir = test_dir / "pin_metadata"
        
        expected_files = [
            "pin_metadata_shard_index.parquet",
            "pin_metadata_shard_index.car", 
            "pin_metadata.parquet"
        ]
        
        print("\n📋 Checking initialized files:")
        for file_name in expected_files:
            file_path = pin_metadata_dir / file_name
            if file_path.exists():
                print(f"  ✅ {file_name} - Created")
                if file_name.endswith('.parquet'):
                    df = pd.read_parquet(file_path)
                    print(f"     📊 Columns: {list(df.columns)}")
                    print(f"     📏 Shape: {df.shape}")
            else:
                print(f"  ❌ {file_name} - Missing")
        
        # Test PIN operation
        print("\n🔗 Testing PIN operation with metadata creation...")
        
        test_cid = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        
        result = await pin_manager.add_pin_operation(
            cid_or_file=test_cid,
            name="test_file.txt",
            recursive=True,
            metadata={"test": "data", "source": "test_script"}
        )
        
        print(f"📌 PIN Result: {result}")
        
        # Check updated files
        print("\n📋 Checking files after PIN operation:")
        for file_name in expected_files:
            file_path = pin_metadata_dir / file_name
            if file_path.exists() and file_name.endswith('.parquet'):
                df = pd.read_parquet(file_path)
                print(f"  📊 {file_name}:")
                print(f"     📏 Shape: {df.shape}")
                if not df.empty:
                    print(f"     📄 Sample data:")
                    for col in df.columns:
                        print(f"       {col}: {df[col].iloc[0] if len(df) > 0 else 'N/A'}")
        
        # Test multiple PINs to verify sharding
        print("\n🔗 Testing multiple PINs for sharding...")
        
        test_cids = [
            "QmTest1234567890abcdef1234567890abcdef123456",
            "QmTest9876543210fedcba9876543210fedcba654321",
            "QmTestAAAABBBBCCCCDDDDEEEEFFFF1111222233334444"
        ]
        
        for i, cid in enumerate(test_cids):
            result = await pin_manager.add_pin_operation(
                cid_or_file=cid,
                name=f"test_file_{i}.txt",
                recursive=True,
                metadata={"batch": "test", "index": i}
            )
            print(f"📌 PIN {i+1} Result: {result['success']}")
        
        # Check final state
        print("\n📋 Final file state:")
        for file_name in expected_files:
            file_path = pin_metadata_dir / file_name
            if file_path.exists():
                if file_name.endswith('.parquet'):
                    df = pd.read_parquet(file_path)
                    print(f"  📊 {file_name}: {df.shape[0]} entries")
                else:
                    size = file_path.stat().st_size
                    print(f"  📁 {file_name}: {size} bytes")
        
        print("\n✨ Enhanced Pin Metadata Test Complete!")

if __name__ == "__main__":
    anyio.run(test_enhanced_pin_metadata)
