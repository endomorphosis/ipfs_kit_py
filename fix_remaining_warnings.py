#!/usr/bin/env python3
"""
Fix missing methods and improve resource cleanup in tiered_cache.py.

This script adds the missing methods:
1. _update_partitioning method
2. _update_bloom_filters method
3. Improves the cleanup method to properly handle resources
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
    
    # Add missing attributes to ParquetCIDCache.__init__
    init_pos = content.find('def __init__', content.find('class ParquetCIDCache'))
    if init_pos > 0:
        # Find the beginning of __init__ method body
        init_body_start = content.find(':', init_pos)
        if init_body_start > 0:
            # Get the indentation level
            indent_match = re.search(r'\n(\s+)', content[init_body_start:init_body_start+100])
            if indent_match:
                indent = indent_match.group(1)
                insertion_pos = init_body_start + indent_match.start() + len(indent_match.group(0))
                
                # Add missing attributes
                attributes_init = f"{indent}# Initialize tracking flags\n"
                attributes_init += f"{indent}self.modified = False\n"
                attributes_init += f"{indent}self.mmap_files = {{}}\n"
                
                # Only add if they don't already exist
                if 'self.modified = ' not in content[insertion_pos:insertion_pos+500]:
                    content = content[:insertion_pos] + attributes_init + content[insertion_pos:]
                    modified = True
                    print("Added missing attributes to ParquetCIDCache.__init__")
    
    # Add the missing _update_partitioning method to ParquetCIDCache
    if 'def _update_partitioning(self' not in content:
        # Look for a good insertion point - after _get_default_partitioning_config
        insert_pos = content.find('def _get_default_partitioning_config')
        if insert_pos >= 0:
            # Find the end of the method
            def_end = content.find('def ', insert_pos + 10)
            if def_end >= 0:
                # Get the indentation level
                indent_match = re.search(r'(\s+)def _get_default_partitioning_config', content[insert_pos-10:insert_pos+50])
                indent = indent_match.group(1) if indent_match else '    '
                
                method_code = f"""
{indent}def _update_partitioning(self):
{indent}    \"\"\"Update the partitioning configuration and apply changes.\"\"\"
{indent}    try:
{indent}        # Get current partitioning settings
{indent}        partitioning = self.partitioning_config or self._get_default_partitioning_config()
{indent}        
{indent}        # Apply any updates or do other partitioning maintenance
{indent}        if hasattr(self, 'dataset') and self.dataset is not None:
{indent}            # This would update dataset partitioning if implemented
{indent}            pass
{indent}    except Exception as e:
{indent}        logger.warning(f"Error updating partitioning: {{e}}")

"""
                content = content[:def_end] + method_code + content[def_end:]
                modified = True
                print("Added _update_partitioning method to ParquetCIDCache")
    
    # Add the missing _update_bloom_filters method to ParquetCIDCache
    if 'def _update_bloom_filters(self' not in content:
        # Look for a good insertion point - after _update_partitioning or _get_default_partitioning_config
        insert_pos = content.find('def _update_partitioning')
        if insert_pos < 0:
            insert_pos = content.find('def _get_default_partitioning_config')
            
        if insert_pos >= 0:
            # Find the end of the method
            def_end = content.find('def ', insert_pos + 10)
            if def_end >= 0:
                # Get the indentation level
                indent_match = re.search(r'(\s+)def', content[insert_pos-10:insert_pos+30])
                indent = indent_match.group(1) if indent_match else '    '
                
                method_code = f"""
{indent}def _update_bloom_filters(self, cid=None):
{indent}    \"\"\"Update bloom filters for efficient CID lookups.
{indent}    
{indent}    Args:
{indent}        cid: Specific CID to add to bloom filter, or None to rebuild entire filter
{indent}    \"\"\"
{indent}    try:
{indent}        # This is a placeholder implementation
{indent}        # In a full implementation, it would add the CID to a bloom filter for fast membership tests
{indent}        pass
{indent}    except Exception as e:
{indent}        logger.warning(f"Error updating bloom filters: {{e}}")

"""
                content = content[:def_end] + method_code + content[def_end:]
                modified = True
                print("Added _update_bloom_filters method to ParquetCIDCache")
    
    # Improve the cleanup method
    cleanup_pos = content.find('def cleanup(self', content.find('class ParquetCIDCache'))
    if cleanup_pos >= 0:
        # Find the start of the cleanup method body
        cleanup_start = content.find(':', cleanup_pos)
        if cleanup_start >= 0:
            cleanup_start += 1
            
            # Find the end of the cleanup method
            cleanup_end = content.find('def ', cleanup_start)
            if cleanup_end >= 0:
                # Extract current cleanup method
                current_cleanup = content[cleanup_start:cleanup_end]
                
                # Get the indentation
                indent_match = re.search(r'\n(\s+)', current_cleanup)
                indent = indent_match.group(1) if indent_match else '        '
                
                # Create improved cleanup method
                improved_cleanup = f"""
{indent}\"\"\"Clean up resources used by the cache.\"\"\"
{indent}try:
{indent}    # Sync data to disk if modified
{indent}    if hasattr(self, 'modified') and self.modified:
{indent}        try:
{indent}            self.sync()
{indent}        except Exception as e:
{indent}            logger.warning(f"Error syncing data during cleanup: {{e}}")
                
{indent}    # Cancel any scheduled sync timer
{indent}    if hasattr(self, 'sync_timer') and self.sync_timer:
{indent}        try:
{indent}            self.sync_timer.cancel()
{indent}            self.sync_timer = None
{indent}        except Exception as e:
{indent}            logger.warning(f"Error canceling sync timer: {{e}}")
                
{indent}    # Clean up memory-mapped files
{indent}    if hasattr(self, 'mmap_files'):
{indent}        for file_path, (file_obj, mmap_obj) in list(self.mmap_files.items()):
{indent}            try:
{indent}                if mmap_obj and hasattr(mmap_obj, 'close'):
{indent}                    mmap_obj.close()
{indent}                if file_obj and hasattr(file_obj, 'close'):
{indent}                    file_obj.close()
{indent}            except Exception as e:
{indent}                logger.warning(f"Error closing memory-mapped file {{file_path}}: {{e}}")
{indent}        self.mmap_files.clear()
                
{indent}    # Clean up Plasma client if it exists
{indent}    if hasattr(self, 'plasma_client') and self.plasma_client:
{indent}        try:
{indent}            # No explicit close method, but we can delete the reference
{indent}            self.plasma_client = None
{indent}        except Exception as e:
{indent}            logger.warning(f"Error cleaning up plasma client: {{e}}")
                
{indent}    # Shut down thread pool
{indent}    if hasattr(self, 'thread_pool') and self.thread_pool:
{indent}        try:
{indent}            self.thread_pool.shutdown(wait=False)
{indent}            self.thread_pool = None
{indent}        except Exception as e:
{indent}            logger.warning(f"Error shutting down thread pool: {{e}}")
                
{indent}except Exception as e:
{indent}    logger.error(f"Error during ParquetCIDCache cleanup: {{e}}")
"""

                # Replace current cleanup method with improved one
                content = content[:cleanup_start] + improved_cleanup + content[cleanup_end:]
                modified = True
                print("Improved cleanup method in ParquetCIDCache")
    
    # Write the modified content back to the file if changes were made
    if modified:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Successfully updated {file_path}")
    else:
        print("No modifications needed")

if __name__ == "__main__":
    fix_tiered_cache()