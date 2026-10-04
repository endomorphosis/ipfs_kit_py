#!/usr/bin/env python3
"""
Quick verification of pin metadata files in the actual user directory.
"""

import pandas as pd
from pathlib import Path
import os

def check_pin_metadata():
    """Check the actual pin metadata files in user directory."""
    
    pin_metadata_dir = Path.home() / ".ipfs_kit" / "pin_metadata"
    
    print(f"🔍 Checking pin metadata directory: {pin_metadata_dir}")
    
    if not pin_metadata_dir.exists():
        print("❌ Pin metadata directory doesn't exist yet")
        print("💡 Create it by running a PIN operation first")
        return
    
    print(f"📁 Directory exists: {pin_metadata_dir}")
    print("📋 Contents:")
    
    for item in pin_metadata_dir.iterdir():
        print(f"  📄 {item.name}")
    
    # Check specific files
    expected_files = [
        "pin_metadata_shard_index.parquet",
        "pin_metadata_shard_index.car", 
        "pin_metadata.parquet",
        "pins.parquet"
    ]
    
    print("\n🔎 Checking expected files:")
    for file_name in expected_files:
        file_path = pin_metadata_dir / file_name
        if file_path.exists():
            print(f"  ✅ {file_name}")
            if file_name.endswith('.parquet'):
                try:
                    df = pd.read_parquet(file_path)
                    print(f"     📊 Shape: {df.shape}")
                    print(f"     📋 Columns: {list(df.columns)}")
                    if not df.empty:
                        print(f"     📄 Sample entry count: {len(df)}")
                except Exception as e:
                    print(f"     ❌ Error reading: {e}")
            else:
                size = file_path.stat().st_size
                print(f"     📏 Size: {size} bytes")
        else:
            print(f"  ⚠️  {file_name} - Not found")
    
    print("\n✨ Pin metadata verification complete!")

if __name__ == "__main__":
    check_pin_metadata()
