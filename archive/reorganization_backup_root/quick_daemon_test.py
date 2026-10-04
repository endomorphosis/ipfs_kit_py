#!/usr/bin/env python3
"""
Quick test for daemon manager indexing functionality.
"""

import sys
import time
from pathlib import Path

# Add the package to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager

def quick_test():
    print("🔧 Quick Daemon Manager Index Test")
    
    daemon_manager = EnhancedDaemonManager()
    
    # Check IPFS status
    ipfs_running = daemon_manager._is_ipfs_daemon_running()
    print(f"IPFS daemon: {'Running' if ipfs_running else 'Not running'}")
    
    if ipfs_running:
        # Get pin count
        pin_count = daemon_manager._get_pin_count()
        print(f"Total pins: {pin_count}")
        
        # Update pin index once
        print("Updating pin index with real data...")
        daemon_manager._update_pin_index()
        
        # Check if file was created
        pin_file = daemon_manager.ipfs_kit_path / 'pin_metadata' / 'parquet_storage' / 'pins.parquet'
        if pin_file.exists():
            stat = pin_file.stat()
            print(f"✅ Pin index updated: {stat.st_size} bytes")
            
            # Read back and show sample
            import pandas as pd
            df = pd.read_parquet(pin_file)
            print(f"Records in index: {len(df)}")
            if len(df) > 0:
                print("Sample pin:")
                sample = df.iloc[0]
                print(f"  CID: {sample['cid']}")
                print(f"  Size: {sample['size_bytes']} bytes")
        else:
            print("❌ Pin index file not created")
            
        # Update program state
        print("Updating program state...")
        daemon_manager._update_program_state()
        
        state_dir = daemon_manager.ipfs_kit_path / 'program_state' / 'parquet'
        if state_dir.exists():
            state_files = list(state_dir.glob('*.parquet'))
            print(f"✅ Program state files: {len(state_files)}")
        else:
            print("❌ Program state not created")
    
    print("✅ Quick test complete")

if __name__ == "__main__":
    quick_test()
