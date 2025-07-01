#!/usr/bin/env python3
"""
Add missing methods to tiered_cache.py:
1. _get_default_partitioning_config method
2. Initialize plasma_client attribute
"""

import os
import re

def apply_fix():
    """Apply fixes to the tiered_cache.py file."""
    file_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/tiered_cache.py'
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the ParquetCIDCache class
    class_match = re.search(r'class ParquetCIDCache:', content)
    if not class_match:
        print("Error: ParquetCIDCache class not found")
        return False
    
    # Find and modify initialization of partitioning_config
    partitioning_match = re.search(r'self\.partitioning_config\s*=\s*self\.config\.get\("partitioning",\s*\{\}\)', content)
    if partitioning_match:
        content = content.replace(
            partitioning_match.group(0),
            'self.partitioning_config = self.config.get("partitioning", self._get_default_partitioning_config())'
        )
        print("Updated partitioning_config initialization")
    
    # Find the ParquetCIDCache.__init__ method 
    init_match = re.search(r'def __init__\(self[^:]*:([^_]*)def', content[class_match.start():], re.DOTALL)
    if init_match:
        init_body = init_match.group(1)
        # Add the plasma_client attribute if not present
        if 'self.plasma_client' not in init_body:
            # Find the indentation level
            indent_match = re.search(r'(\s+)self', init_body)
            indent = indent_match.group(1) if indent_match else '        '
            # Find the last line to add it after
            lines = init_body.strip().split('\n')
            if lines:
                # Add plasma_client at the beginning of init
                new_init_body = f"{indent}self.plasma_client = None\n{init_body}"
                content = content.replace(init_body, new_init_body)
                print("Added plasma_client initialization")
    
    # Add the _get_default_partitioning_config method if it doesn't exist
    if '_get_default_partitioning_config' not in content:
        # Find the init method
        init_end = content.find('def __init__', class_match.start()) + len('def __init__')
        if init_end > len('def __init__'):
            # Find the end of init method
            next_method = content.find('def ', init_end)
            if next_method > init_end:
                # Create the method
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
                # Insert the method
                content = content[:next_method] + method_code + content[next_method:]
                print("Added _get_default_partitioning_config method")
    
    # Write the updated content back to the file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("Fix applied successfully!")
    return True

if __name__ == "__main__":
    apply_fix()
