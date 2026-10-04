#!/usr/bin/env python3
"""
Create enhanced pin metadata files in the actual user directory.
"""

import os
import sys
import anyio
from pathlib import Path

# Add the ipfs_kit_py directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ipfs_kit_py'))

from ipfs_kit_py.simple_pin_manager import SimplePinManager

async def create_enhanced_metadata():
    """Create enhanced metadata files in the user directory."""
    print("🚀 Creating Enhanced Pin Metadata Files...")
    
    # Use actual user directory
    user_ipfs_dir = Path.home() / ".ipfs_kit"
    print(f"📁 Using directory: {user_ipfs_dir}")
    
    # Initialize SimplePinManager with user directory
    pin_manager = SimplePinManager(data_dir=str(user_ipfs_dir))
    
    # Initialize shard files
    print("🔧 Initializing shard files...")
    await pin_manager._initialize_shard_files()
    
    # Check that files were created
    pin_metadata_dir = user_ipfs_dir / "pin_metadata"
    
    expected_files = [
        "pin_metadata_shard_index.parquet",
        "pin_metadata_shard_index.car", 
        "pin_metadata.parquet"
    ]
    
    print("\n📋 Checking created files:")
    for file_name in expected_files:
        file_path = pin_metadata_dir / file_name
        if file_path.exists():
            print(f"  ✅ {file_name} - Created")
            if file_name.endswith('.parquet'):
                import pandas as pd
                df = pd.read_parquet(file_path)
                print(f"     📊 Columns: {list(df.columns)}")
                print(f"     📏 Shape: {df.shape}")
        else:
            print(f"  ❌ {file_name} - Not created")
    
    # Perform a test PIN operation to populate the files
    print("\n🔗 Performing test PIN operation...")
    
    # Use a test CID
    test_cid = "QmTestEnhancedMetadata123456789abcdef"
    
    try:
        result = await pin_manager.add_pin_operation(
            cid_or_file=test_cid,
            name="enhanced_metadata_test.txt",
            recursive=True,
            metadata={"purpose": "enhanced_metadata_test", "version": "1.0"}
        )
        
        print(f"📌 PIN Result: {result.get('success', False)}")
        if not result.get('success', False):
            print(f"   Error: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"📌 PIN Error: {e}")
    
    # Check final state
    print("\n📋 Final file state:")
    for file_name in expected_files:
        file_path = pin_metadata_dir / file_name
        if file_path.exists():
            if file_name.endswith('.parquet'):
                import pandas as pd
                df = pd.read_parquet(file_path)
                print(f"  📊 {file_name}: {df.shape[0]} entries")
                if not df.empty:
                    print(f"     📋 Columns: {list(df.columns)}")
            else:
                size = file_path.stat().st_size
                print(f"  📁 {file_name}: {size} bytes")
    
    print("\n✨ Enhanced Pin Metadata Files Created!")
    print(f"📍 Location: {pin_metadata_dir}")
    print("🎯 Files ready for use with PIN operations!")

if __name__ == "__main__":
    anyio.run(create_enhanced_metadata)
