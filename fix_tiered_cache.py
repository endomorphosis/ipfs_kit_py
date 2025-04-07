#!/usr/bin/env python3
"""
Fix script for tiered_cache.py.

This script adds the missing _get_default_partitioning_config method to ParquetCIDCache
and also fixes the plasma_client attribute error.
"""
import os
import re

def fix_tiered_cache():
    """Add missing methods to tiered_cache.py."""
    file_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/tiered_cache.py'
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    modified = False
    
    # Add the missing _get_default_partitioning_config method to ParquetCIDCache
    if 'def _get_default_partitioning_config' not in content:
        # Look for the class definition
        class_match = re.search(r'class ParquetCIDCache[^:]*:', content)
        if class_match:
            # Find the first method after __init__
            init_end = content.find('def __init__', class_match.end())
            if init_end > 0:
                # Find the end of the __init__ method
                next_method = content.find('def ', init_end + 1)
                if next_method > 0:
                    # Insert the method before the next method
                    method_code = """
    def _get_default_partitioning_config(self) -> Dict[str, Any]:
        \"\"\"Get default partitioning configuration.
        
        Returns:
            Dictionary with default partitioning configuration
        \"\"\"
        return {
            "method": "hive",
            "columns": ["year", "month", "day"],
            "max_rows_per_partition": 100000,
            "max_file_size": 256 * 1024 * 1024,  # 256MB
            "enable_statistics": True,
            "compression": "zstd",
            "compression_level": 3
        }
                    
"""
                    content = content[:next_method] + method_code + content[next_method:]
                    modified = True
                    print("Added _get_default_partitioning_config method to ParquetCIDCache")
    
    # Initialize plasma_client attribute in __init__ to prevent errors when cleaning up
    if 'self.plasma_client = None' not in content:
        init_pos = content.find('def __init__', content.find('class ParquetCIDCache'))
        if init_pos > 0:
            # Find the end of the __init__ method declarations
            init_body_start = content.find(':', init_pos)
            if init_body_start > 0:
                # Add the attribute initialization right after the first line of the method body
                indent_match = re.search(r'\n(\s+)', content[init_body_start:init_body_start+100])
                if indent_match:
                    indent = indent_match.group(1)
                    insertion_pos = init_body_start + indent_match.start() + len(indent_match.group(0))
                    plasma_init = f"{indent}self.plasma_client = None\n"
                    content = content[:insertion_pos] + plasma_init + content[insertion_pos:]
                    modified = True
                    print("Added plasma_client initialization to ParquetCIDCache.__init__")
    
    # Write the modified content back to the file if changes were made
    if modified:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Successfully updated {file_path}")
    else:
        print("No modifications needed")

if __name__ == "__main__":
    fix_tiered_cache()
