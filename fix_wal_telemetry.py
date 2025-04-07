#!/usr/bin/env python3
"""
Fix directory creation issues in WAL telemetry module.

This script patches the WAL telemetry module to ensure directories are created
before file operations, preventing FileNotFoundError exceptions.
"""

import os
import re

def fix_wal_telemetry():
    """Fix directory creation issues in WAL telemetry.py."""
    # Path to the WAL telemetry module
    telemetry_file = "ipfs_kit_py/wal_telemetry.py"
    
    # Read the file content
    with open(telemetry_file, 'r') as f:
        content = f.read()
    
    # Fix the _store_metrics_arrow method
    store_arrow_pattern = r'def _store_metrics_arrow\(self\):(.*?)pq\.write_table\(table, metrics_file\)'
    store_arrow_replacement = r'def _store_metrics_arrow(self):\1# Ensure directory exists\n        os.makedirs(os.path.dirname(metrics_file), exist_ok=True)\n        pq.write_table(table, metrics_file)'
    
    # Fix the _store_metrics_json method
    store_json_pattern = r'def _store_metrics_json\(self\):(.*?)with open\(metrics_file, \'w\'\) as f:'
    store_json_replacement = r'def _store_metrics_json(self):\1# Ensure directory exists\n        os.makedirs(os.path.dirname(metrics_file), exist_ok=True)\n        with open(metrics_file, \'w\') as f:'
    
    # Fix the _clean_up_old_metrics method
    clean_metrics_pattern = r'def _clean_up_old_metrics\(self\):(.*?)for filename in os\.listdir\(self\.metrics_path\):'
    clean_metrics_replacement = r'def _clean_up_old_metrics(self):\1# Ensure directory exists before listing\n        if not os.path.exists(self.metrics_path):\n            return\n        \n        for filename in os.listdir(self.metrics_path):'
    
    # Apply the fixes
    content = re.sub(store_arrow_pattern, store_arrow_replacement, content, flags=re.DOTALL)
    content = re.sub(store_json_pattern, store_json_replacement, content, flags=re.DOTALL)
    content = re.sub(clean_metrics_pattern, clean_metrics_replacement, content, flags=re.DOTALL)
    
    # Write the fixed content back to the file
    with open(telemetry_file, 'w') as f:
        f.write(content)
    
    print(f"Fixed WAL telemetry in {telemetry_file}")
    return True

if __name__ == "__main__":
    fix_wal_telemetry()